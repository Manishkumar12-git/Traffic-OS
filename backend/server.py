import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import cv2
import random
import threading
import time
import webbrowser
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from camera.video_source import VideoSource
from vision.detector import VehicleDetector

app = FastAPI(title="TrafficOS True Dual Mode AI & Manual Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_PATH = "../videos/traffic.mp4"
camera = VideoSource(VIDEO_PATH)
detector = VehicleDetector()

class EnforcementEngine:
    def __init__(self, speed_limit_kmh=60):
        self.speed_limit = speed_limit_kmh
        self.is_active = True
        self.vehicle_tracks = {}
        self.mock_plates = [
            "DL 01 AB 4921", "MH 12 PK 8820", "UP 16 BZ 1092", 
            "KA 03 MG 6514", "HR 26 DQ 7731", "GJ 01 ER 9043"
        ]
        self.last_challan_time = {}

    def process_violations(self, detections, gate_y, current_phase):
        if not self.is_active:
            return []

        challans = []
        current_time = time.time()

        for idx, det in enumerate(detections):
            x1, y1, x2, y2 = det["bbox"]
            cy = (y1 + y2) // 2
            v_type = det["class"].lower()
            track_id = idx + 1

            if track_id not in self.vehicle_tracks:
                self.vehicle_tracks[track_id] = {"y": cy, "t": current_time, "speed": 48 + (track_id * 8) % 28}
            else:
                prev = self.vehicle_tracks[track_id]
                dt = current_time - prev["t"]
                dy = abs(cy - prev["y"])
                if dt > 0.4:
                    calculated = int(38 + (dy * 2.2) % 44)
                    self.vehicle_tracks[track_id]["speed"] = calculated
                    self.vehicle_tracks[track_id]["y"] = cy
                    self.vehicle_tracks[track_id]["t"] = current_time

            speed = self.vehicle_tracks[track_id].get("speed", 52)
            violation = None
            section = "Sec 177 MVA"
            fine = 0

            # RLVD Check
            if current_phase != "EW_GREEN" and abs(cy - gate_y) < 45 and (track_id % 4 == 0):
                violation = "RED LIGHT JUMP (RLVD TRAP)"
                section = "Sec 184 MVA - Dangerous Driving"
                fine = 5000
            elif speed > self.speed_limit:
                violation = f"OVERSPEEDING ({speed} km/h)"
                section = "Sec 183(1) MVA - Excessive Speed"
                fine = 2000
            elif v_type in ["motorcycle", "bike"] and (track_id % 3 == 0):
                violation = "NO HELMET DETECTED"
                section = "Sec 129 MVA - Protective Headgear"
                fine = 1000
            elif v_type == "car" and (track_id % 5 == 0):
                violation = "SEATBELT INFRACTION"
                section = "Sec 194B MVA - Failure to use Belt"
                fine = 1000

            if violation and abs(cy - gate_y) < 60:
                if track_id not in self.last_challan_time or (current_time - self.last_challan_time[track_id]) > 6.0:
                    plate = self.mock_plates[track_id % len(self.mock_plates)]
                    self.last_challan_time[track_id] = current_time
                    challans.append({
                        "id": f"CH-{int(current_time * 100) % 100000}",
                        "plate": plate,
                        "type": v_type.upper(),
                        "violation": violation,
                        "section": section,
                        "fine": f"₹{fine}",
                        "speed": f"{speed} km/h",
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "bbox": [x1, y1, x2, y2]
                    })

        return challans

enforcer = EnforcementEngine(speed_limit_kmh=60)

# Dual-Mode System State
system_state = {
    "control_mode": "AUTONOMOUS_AI",  # "AUTONOMOUS_AI" ya "MANUAL_COP_MODE"
    "ai_reasoning": "AI Autopilot Online. Actively scanning multi-junction queue shockwaves.",
    "active_camera": "J2",
    "watchdog_healthy": True,
    "emergency_active": False,
    "emergency_type": "AMBULANCE",
    "emergency_timeout": 0,
    "challan_engine_active": True,
    "spoof_alert": False,
    "spoof_reason": "",
    "avg_wait_time": 22,
    "total_cleared_pcu": 1340,
    "fuel_saved_liters": 145.2,
    "fuel_saved_rupees": 13939,
    "co2_saved_kg": 334.8,
    "total_challans_issued": 18,
    "total_fine_collected": 24000,
    "recent_challan_records": [
        {"id": "CH-98102", "plate": "DL 03 CA 9999", "type": "CIVILIAN SUV", "violation": "ILLEGAL EMERGENCY HOOTER / BEACON SPOOF", "section": "Sec 182A MVA - Unauthorized Beacon", "fine": "₹10000", "speed": "58 km/h", "timestamp": "12:04:12"},
        {"id": "CH-84192", "plate": "HR 26 DQ 7731", "type": "CAR", "violation": "RED LIGHT JUMP (RLVD TRAP)", "section": "Sec 184 MVA - Dangerous Driving", "fine": "₹5000", "speed": "64 km/h", "timestamp": "12:06:40"}
    ],
    "junctions": {
        "J1": {"name": "North Gate", "phase": "EW_GREEN", "timer": 25, "manual_locked": False, "ew_pcu": 8.5, "ns_pcu": 4.2, "ew_vehicles": {"bike": 5, "car": 3, "bus": 1}, "ns_vehicles": {"bike": 4, "car": 2, "bus": 0}},
        "J2": {"name": "Central Interchange", "phase": "EW_GREEN", "timer": 32, "manual_locked": False, "ew_pcu": 12.0, "ns_pcu": 7.5, "ew_vehicles": {"bike": 6, "car": 5, "bus": 2}, "ns_vehicles": {"bike": 5, "car": 3, "bus": 1}},
        "J3": {"name": "Tech Corridor", "phase": "NS_GREEN", "timer": 14, "manual_locked": False, "ew_pcu": 3.2, "ns_pcu": 9.8, "ew_vehicles": {"bike": 2, "car": 2, "bus": 0}, "ns_vehicles": {"bike": 8, "car": 3, "bus": 2}}
    },
    "recent_logs": [
        {"timestamp": datetime.now().strftime("%H:%M:%S"), "event": "TrafficOS Dual Controller Ready (AI + Manual)", "type": "INFO"}
    ]
}

def add_log(event: str, log_type: str):
    system_state["recent_logs"].insert(0, {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "event": event,
        "type": log_type
    })
    system_state["recent_logs"] = system_state["recent_logs"][:8]

async def generate_frames():
    prev_time = time.time()
    
    while True:
        frame = camera.get_frame()
        if frame is None:
            await asyncio.sleep(0.04)
            continue

        annotated_frame, detections = detector.detect(frame)
        h, w, _ = annotated_frame.shape

        bike_count = sum(1 for d in detections if d["class"].lower() in ["motorcycle", "bike"])
        car_count = sum(1 for d in detections if d["class"].lower() in ["car"])
        bus_count = sum(1 for d in detections if d["class"].lower() in ["bus", "truck"])
        total_vehicles = len(detections)

        active_j = system_state.get("active_camera", "J2")
        ew_pcu = round((bike_count * 0.5) + (car_count * 1.0) + (bus_count * 2.8), 1)
        system_state["junctions"][active_j]["ew_vehicles"] = {"bike": bike_count, "car": car_count, "bus": bus_count}
        system_state["junctions"][active_j]["ew_pcu"] = ew_pcu

        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time

        gate_y = int(h * 0.65)
        current_phase = system_state["junctions"][active_j]["phase"]
        
        violations = enforcer.process_violations(detections, gate_y, current_phase) if enforcer.is_active else []

        for ch in violations:
            bx1, by1, bx2, by2 = ch["bbox"]
            cv2.rectangle(annotated_frame, (bx1, by1), (bx2, by2), (0, 0, 255), 3)

            tag_text = f"{ch['violation']} | {ch['plate']} ({ch['fine']})"
            cv2.rectangle(annotated_frame, (bx1, max(0, by1 - 32)), (bx1 + len(tag_text) * 9 + 10, max(24, by1)), (0, 0, 180), -1)
            cv2.rectangle(annotated_frame, (bx1, max(0, by1 - 32)), (bx1 + len(tag_text) * 9 + 10, max(24, by1)), (0, 0, 255), 1)
            cv2.putText(annotated_frame, tag_text, (bx1 + 6, max(18, by1 - 10)),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

            system_state["total_challans_issued"] += 1
            fine_val = int(ch["fine"].replace("₹", ""))
            system_state["total_fine_collected"] += fine_val
            
            system_state["recent_challan_records"].insert(0, {
                "id": ch["id"],
                "plate": ch["plate"],
                "type": ch["type"],
                "violation": ch["violation"],
                "section": ch["section"],
                "fine": ch["fine"],
                "speed": ch["speed"],
                "timestamp": ch["timestamp"]
            })
            system_state["recent_challan_records"] = system_state["recent_challan_records"][:6]
            add_log(f"VIOLATION: {ch['plate']} — {ch['violation']} ({ch['fine']})", "ALERT")

        overlay = annotated_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), (10, 14, 24), -1)
        cv2.addWeighted(overlay, 0.85, annotated_frame, 0.15, 0, annotated_frame)
        cv2.line(annotated_frame, (0, 60), (w, 60), (0, 255, 180), 2)

        j_name = system_state["junctions"][active_j]["name"]
        cv2.putText(annotated_frame, f"TRAFFICOS NODE [{active_j} - {j_name.upper()}]", (25, 38),
                    cv2.FONT_HERSHEY_DUPLEX, 0.70, (0, 255, 180), 2, cv2.LINE_AA)
        cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (w - 140, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        line_color = (0, 0, 255) if current_phase != "EW_GREEN" else (0, 255, 120)
        cv2.line(annotated_frame, (30, gate_y), (w - 30, gate_y), line_color, 2)
        cordon_label = "RLVD LASER TRIPWIRE [ARMED - RED LIGHT]" if current_phase != "EW_GREEN" else "FLOW GATE [PERMITTED - GREEN]"
        cv2.putText(annotated_frame, cordon_label, (40, gate_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_color, 1, cv2.LINE_AA)

        cv2.rectangle(overlay, (20, 80), (320, 255), (12, 16, 28), -1)
        cv2.addWeighted(overlay, 0.85, annotated_frame, 0.15, 0, annotated_frame)
        cv2.rectangle(annotated_frame, (20, 80), (320, 255), (0, 255, 180), 1)

        cv2.putText(annotated_frame, f"TOTAL VEHICLES : {total_vehicles:02d}", (35, 112),
                    cv2.FONT_HERSHEY_DUPLEX, 0.62, (0, 230, 255), 2, cv2.LINE_AA)
        cv2.putText(annotated_frame, f"INDIAN PCU     : {ew_pcu}", (35, 142),
                    cv2.FONT_HERSHEY_DUPLEX, 0.62, (0, 255, 150), 2, cv2.LINE_AA)
        cv2.line(annotated_frame, (35, 158), (305, 158), (50, 70, 100), 1)

        cv2.putText(annotated_frame, f"Cars / Sedans  : {car_count}", (35, 182),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(annotated_frame, f"Motorcycles    : {bike_count}", (35, 206),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 190, 255), 1, cv2.LINE_AA)
        cv2.putText(annotated_frame, f"Heavy Freight  : {bus_count}", (35, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 80, 255), 1, cv2.LINE_AA)

        ch_x = w - 240
        ch_color = (0, 60, 255) if enforcer.is_active else (80, 80, 80)
        cv2.rectangle(overlay, (ch_x, 80), (w - 20, 220), (12, 16, 28), -1)
        cv2.addWeighted(overlay, 0.85, annotated_frame, 0.15, 0, annotated_frame)
        cv2.rectangle(annotated_frame, (ch_x, 80), (w - 20, 220), ch_color, 1)

        cv2.putText(annotated_frame, "ENFORCEMENT RADAR", (ch_x + 10, 108),
                    cv2.FONT_HERSHEY_DUPLEX, 0.48, (0, 100, 255), 1, cv2.LINE_AA)
        cv2.line(annotated_frame, (ch_x + 10, 118), (w - 30, 118), (50, 70, 100), 1)

        cv2.putText(annotated_frame, f"Challans : {system_state['total_challans_issued']}", (ch_x + 10, 146),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(annotated_frame, f"Fines    : ₹{system_state['total_fine_collected']:,}", (ch_x + 10, 174),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 255), 1, cv2.LINE_AA)

        radar_status = "RLVD/ANPR: ACTIVE" if enforcer.is_active else "RADAR: FROZEN [PAUSED]"
        radar_stat_color = (0, 255, 150) if enforcer.is_active else (0, 100, 255)
        cv2.putText(annotated_frame, radar_status, (ch_x + 10, 202),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, radar_stat_color, 1, cv2.LINE_AA)

        if system_state["spoof_alert"]:
            cv2.rectangle(annotated_frame, (w // 2 - 280, h - 60), (w // 2 + 280, h - 15), (0, 0, 180), -1)
            cv2.putText(annotated_frame, "FAKE SIREN / BEACON SPOOF DETECTED — CORRIDOR DENIED", (w // 2 - 265, h - 32),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        elif system_state["emergency_active"]:
            v_name = "108 AMBULANCE" if system_state["emergency_type"] == "AMBULANCE" else "GOVT VIP CONVOY"
            cv2.rectangle(annotated_frame, (w // 2 - 270, h - 60), (w // 2 + 270, h - 15), (0, 0, 160), -1)
            cv2.putText(annotated_frame, f"PRIORITY PASS ACTIVE: 1x {v_name} [2s CLEARANCE]", (w // 2 - 250, h - 32),
                        cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

        success, buffer = cv2.imencode(".jpg", annotated_frame)
        if not success:
            await asyncio.sleep(0.01)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )
        await asyncio.sleep(0.01)

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# WebSocket Loop
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    next_ai_decision = random.randint(4, 8)
    ai_ticker = 0

    try:
        while True:
            ai_ticker += 1

            # =========================================================
            # AUTONOMOUS AI AGENT (RUNS STRICTLY IN AUTONOMOUS_AI MODE)
            # =========================================================
            if system_state["control_mode"] == "AUTONOMOUS_AI" and not system_state["emergency_active"]:
                if ai_ticker >= next_ai_decision:
                    ai_ticker = 0
                    next_ai_decision = random.randint(4, 9)

                    action_type = random.choices(
                        ["SURGE_UP", "SURGE_DOWN", "EMERGENCY_PASS", "FAKE_SIREN_ATTEMPT", "RLVD_TRAP"],
                        weights=[0.40, 0.25, 0.15, 0.10, 0.10],
                        k=1
                    )[0]

                    target_j = random.choice(["J1", "J2", "J3"])
                    direction = random.choice(["EW", "NS"])
                    j_obj = system_state["junctions"][target_j]

                    # 1. AI Traffic Increase & Auto Phase Adaptation
                    if action_type == "SURGE_UP" and not j_obj.get("manual_locked", False):
                        new_bikes = random.randint(10, 20)
                        new_cars = random.randint(5, 11)
                        new_buses = random.randint(2, 5)
                        calc_pcu = round((new_bikes * 0.5) + (new_cars * 1.0) + (new_buses * 2.8), 1)

                        if direction == "EW":
                            j_obj["ew_vehicles"] = {"bike": new_bikes, "car": new_cars, "bus": new_buses}
                            j_obj["ew_pcu"] = calc_pcu
                            if calc_pcu > j_obj["ns_pcu"]:
                                j_obj["phase"] = "EW_GREEN"
                                j_obj["timer"] = min(50, max(25, int(calc_pcu * 1.4)))
                                system_state["ai_reasoning"] = f"AI AUTOPILOT: {target_j} E-W surge ({calc_pcu} PCU) > N-S. Auto-extending Green to {j_obj['timer']}s."
                                add_log(f"AI ADAPT: {target_j} E-W surge ({calc_pcu} PCU) -> Green {j_obj['timer']}s", "ALERT")
                        else:
                            j_obj["ns_vehicles"] = {"bike": new_bikes, "car": new_cars, "bus": new_buses}
                            j_obj["ns_pcu"] = calc_pcu
                            if calc_pcu > j_obj["ew_pcu"]:
                                j_obj["phase"] = "NS_GREEN"
                                j_obj["timer"] = min(50, max(25, int(calc_pcu * 1.4)))
                                system_state["ai_reasoning"] = f"AI AUTOPILOT: {target_j} N-S surge ({calc_pcu} PCU) > E-W. Auto-extending Green to {j_obj['timer']}s."
                                add_log(f"AI ADAPT: {target_j} N-S surge ({calc_pcu} PCU) -> Green {j_obj['timer']}s", "ALERT")

                    # 2. AI Traffic Clearance
                    elif action_type == "SURGE_DOWN":
                        if direction == "EW":
                            j_obj["ew_vehicles"] = {"bike": random.randint(2, 5), "car": random.randint(1, 3), "bus": random.randint(0, 1)}
                            j_obj["ew_pcu"] = round((j_obj["ew_vehicles"]["bike"] * 0.5) + (j_obj["ew_vehicles"]["car"] * 1.0) + (j_obj["ew_vehicles"]["bus"] * 2.8), 1)
                            system_state["ai_reasoning"] = f"AI AUTOPILOT: {target_j} E-W queue dissipated to {j_obj['ew_pcu']} PCU. Normal intervals restored."
                        else:
                            j_obj["ns_vehicles"] = {"bike": random.randint(2, 5), "car": random.randint(1, 3), "bus": random.randint(0, 1)}
                            j_obj["ns_pcu"] = round((j_obj["ns_vehicles"]["bike"] * 0.5) + (j_obj["ns_vehicles"]["car"] * 1.0) + (j_obj["ns_vehicles"]["bus"] * 2.8), 1)
                            system_state["ai_reasoning"] = f"AI AUTOPILOT: {target_j} N-S queue dissipated to {j_obj['ns_pcu']} PCU. Normal intervals restored."

                    # 3. Autonomous Emergency Pass
                    elif action_type == "EMERGENCY_PASS":
                        is_vip = random.random() < 0.35
                        v_type = "GOV_VIP" if is_vip else "AMBULANCE"
                        system_state["emergency_active"] = True
                        system_state["emergency_type"] = v_type
                        system_state["emergency_timeout"] = 2
                        system_state["ai_reasoning"] = f"AI AUTOPILOT: Priority vehicle detected! Enforcing 2s green wave for {v_type}."
                        for j in system_state["junctions"].values():
                            j["phase"] = "EW_GREEN"
                            j["timer"] = 30
                        v_label = "Govt VIP Convoy" if is_vip else "108 Ambulance"
                        add_log(f"AI PRIORITY: 1x {v_label} verified -> 2s corridor pass", "EMERGENCY")

                    # 4. Autonomous Fake Siren Catch
                    elif action_type == "FAKE_SIREN_ATTEMPT" and enforcer.is_active:
                        system_state["spoof_alert"] = True
                        system_state["spoof_reason"] = "Acoustic siren detected, but optical livery classified Civilian SUV. CAD token invalid."
                        system_state["total_challans_issued"] += 1
                        system_state["total_fine_collected"] += 10000
                        system_state["recent_challan_records"].insert(0, {
                            "id": f"CH-SP-{int(time.time()*100)%100000}",
                            "plate": "DL 03 CA 9999",
                            "type": "BLACK SUV (CIVILIAN)",
                            "violation": "ILLEGAL EMERGENCY HOOTER / BEACON SPOOF",
                            "section": "Sec 182A MVA - Unauthorized Beacon",
                            "fine": "₹10000",
                            "speed": "54 km/h",
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        })
                        system_state["recent_challan_records"] = system_state["recent_challan_records"][:6]
                        system_state["ai_reasoning"] = "AI ZERO-TRUST: Fake siren caught! Preemption denied & ₹10,000 fine issued."
                        add_log("AI SECURITY: Civilian fake siren caught! Preemption REJECTED & ₹10,000 fine issued.", "ALERT")

                    # 5. Autonomous RLVD Catch
                    elif action_type == "RLVD_TRAP" and enforcer.is_active:
                        system_state["total_challans_issued"] += 1
                        system_state["total_fine_collected"] += 5000
                        system_state["recent_challan_records"].insert(0, {
                            "id": f"CH-RL-{int(time.time()*100)%100000}",
                            "plate": "HR 26 DQ 1088",
                            "type": "SEDAN CAR",
                            "violation": "RED LIGHT JUMP (RLVD LASER TRAP)",
                            "section": "Sec 184 MVA - Dangerous Driving",
                            "fine": "₹5000",
                            "speed": "62 km/h",
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        })
                        system_state["recent_challan_records"] = system_state["recent_challan_records"][:6]
                        system_state["ai_reasoning"] = "AI RLVD RADAR: Red light violator auto-captured at stop-line cordon. ₹5,000 challan issued."
                        add_log("AI RLVD: Red light violator auto-captured at stop-line cordon. ₹5,000 challan issued.", "ALERT")

            # Emergency Timeout Handshake
            if system_state["emergency_active"]:
                system_state["emergency_timeout"] -= 1
                if system_state["emergency_timeout"] <= 0:
                    system_state["emergency_active"] = False

            # Signal Countdown Clock (Only counts down if junction is not locked in Manual Mode)
            for j in system_state["junctions"].values():
                if not system_state["emergency_active"]:
                    if system_state["control_mode"] == "AUTONOMOUS_AI" and not j.get("manual_locked", False):
                        if j["timer"] > 1:
                            j["timer"] -= 1
                        else:
                            if j["ew_pcu"] >= j["ns_pcu"]:
                                j["phase"] = "EW_GREEN"
                                j["timer"] = min(45, max(18, int(j["ew_pcu"] * 1.4)))
                            else:
                                j["phase"] = "NS_GREEN"
                                j["timer"] = min(45, max(18, int(j["ns_pcu"] * 1.4)))
                    elif system_state["control_mode"] == "MANUAL_COP_MODE":
                        # In Manual Cop Mode, countdown still ticks down but maintains user phase
                        if j["timer"] > 1:
                            j["timer"] -= 1
                        else:
                            j["timer"] = 60 # Keep user's chosen phase held

            system_state["fuel_saved_liters"] = round(system_state["fuel_saved_liters"] + 0.02, 2)
            system_state["fuel_saved_rupees"] = int(system_state["fuel_saved_liters"] * 96)
            system_state["co2_saved_kg"] = round(system_state["co2_saved_kg"] + 0.04, 2)

            await websocket.send_json(system_state)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass

# Explicit Mode and Signal Control APIs
@app.post("/api/mode/{mode_name}")
def set_control_mode(mode_name: str):
    if mode_name in ["AUTONOMOUS_AI", "MANUAL_COP_MODE"]:
        system_state["control_mode"] = mode_name
        if mode_name == "AUTONOMOUS_AI":
            for j in system_state["junctions"].values():
                j["manual_locked"] = False
            system_state["ai_reasoning"] = "System returned to 100% Autonomous AI. Signals adapting by PCU load."
            add_log("Control Mode switched to: AUTONOMOUS AI", "INFO")
        else:
            system_state["ai_reasoning"] = "MANUAL COP MODE ENGAGED. Traffic Police commands will strictly hold without AI override."
            add_log("Control Mode switched to: MANUAL COP MODE", "INFO")
    return {"status": "ok", "control_mode": system_state["control_mode"]}

@app.post("/api/signal/{j_id}/{phase}")
def force_signal_phase(j_id: str, phase: str):
    j_id = j_id.upper()
    if j_id in system_state["junctions"] and phase in ["EW_GREEN", "NS_GREEN"]:
        system_state["control_mode"] = "MANUAL_COP_MODE" # Instantly engage manual lock
        j_obj = system_state["junctions"][j_id]
        j_obj["phase"] = phase
        j_obj["timer"] = 60 # Hold for 60 seconds
        j_obj["manual_locked"] = True
        system_state["ai_reasoning"] = f"MANUAL COP OVERRIDE: {j_id} locked to {phase} (60s hold). AI adaptation paused."
        add_log(f"MANUAL SIGNAL OVERRIDE: {j_id} set to {phase}", "INFO")
        return {"status": "ok", "junction": j_id, "phase": phase, "control_mode": system_state["control_mode"]}
    return {"status": "error", "message": "Invalid junction or phase"}

@app.post("/api/trigger/{action}")
def trigger_action(action: str):
    if action == "toggle_mode":
        new_mode = "MANUAL_COP_MODE" if system_state["control_mode"] == "AUTONOMOUS_AI" else "AUTONOMOUS_AI"
        return set_control_mode(new_mode)

    elif action == "rush_hour":
        target_j = "J1"
        system_state["junctions"][target_j]["ew_vehicles"] = {"bike": 18, "car": 9, "bus": 5}
        system_state["junctions"][target_j]["ew_pcu"] = 32.0
        system_state["junctions"][target_j]["phase"] = "EW_GREEN"
        system_state["junctions"][target_j]["timer"] = 45
        system_state["ai_reasoning"] = "DEMO SURGE: J1 corridor flooded with 32 PCU. Phase locked to EW_GREEN 45s."
        add_log(f"MANUAL SURGE: {target_j} spiked to 32 PCU", "ALERT")

    elif action == "ambulance":
        system_state["emergency_active"] = True
        system_state["emergency_type"] = "AMBULANCE"
        system_state["emergency_timeout"] = 2
        system_state["ai_reasoning"] = "PRIORITY OVERRIDE: 1x 108 Ambulance dispatched with 2s fast-pass."
        for j in system_state["junctions"].values():
            j["phase"] = "EW_GREEN"
        add_log("MANUAL EMS: 1x 108 Ambulance verified -> 2s priority wave", "EMERGENCY")

    elif action == "gov_vip":
        system_state["emergency_active"] = True
        system_state["emergency_type"] = "GOV_VIP"
        system_state["emergency_timeout"] = 2
        system_state["ai_reasoning"] = "PRIORITY OVERRIDE: 1x Govt Motorcade dispatched with 2s fast-pass."
        for j in system_state["junctions"].values():
            j["phase"] = "EW_GREEN"
        add_log("MANUAL VIP: 1x Govt Motorcade priority pass (2s)", "EMERGENCY")

    elif action == "reset_ambulance":
        system_state["emergency_active"] = False
        system_state["ai_reasoning"] = "Emergency corridor preemption cleared."
        add_log("Priority wave cleared -> Normal flow", "INFO")

    elif action == "spoof_test":
        system_state["spoof_alert"] = True
        system_state["spoof_reason"] = "Acoustic siren detected, but optical livery check FAILED (Civilian SUV). CAD Token Invalid."
        system_state["ai_reasoning"] = "DEMO TEST: Simulated illegal beacon spoof. Preemption denied & ₹10,000 fine issued."
        if enforcer.is_active:
            system_state["total_challans_issued"] += 1
            system_state["total_fine_collected"] += 10000
            system_state["recent_challan_records"].insert(0, {
                "id": f"CH-SP-{int(time.time()*100)%100000}",
                "plate": "DL 03 CA 9999",
                "type": "BLACK SUV (CIVILIAN)",
                "violation": "ILLEGAL EMERGENCY HOOTER / BEACON SPOOF",
                "section": "Sec 182A MVA - Unauthorized Beacon & Hooter",
                "fine": "₹10000",
                "speed": "54 km/h",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            system_state["recent_challan_records"] = system_state["recent_challan_records"][:6]
        add_log("SECURITY ALERT: Fake Siren Spoof caught! Corridor DENIED. ₹10,000 fine issued.", "ALERT")

    elif action == "rlvd_test":
        system_state["ai_reasoning"] = "DEMO TEST: Red Light Jump (RLVD) laser trap breach simulated."
        if enforcer.is_active:
            system_state["total_challans_issued"] += 1
            system_state["total_fine_collected"] += 5000
            system_state["recent_challan_records"].insert(0, {
                "id": f"CH-RL-{int(time.time()*100)%100000}",
                "plate": "HR 26 DQ 1088",
                "type": "SEDAN CAR",
                "violation": "RED LIGHT JUMP (RLVD LASER TRAP)",
                "section": "Sec 184 MVA - Dangerous Driving / Red Light Jump",
                "fine": "₹5000",
                "speed": "62 km/h",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            system_state["recent_challan_records"] = system_state["recent_challan_records"][:6]
        add_log("RLVD TRAP TRIGGERED: Vehicle crossed stop line during RED. ₹5,000 challan issued.", "ALERT")

    elif action == "wrong_way_test":
        system_state["wrong_way_alert"] = True
        system_state["ai_reasoning"] = "DEMO TEST: Opposite counter-flow vehicle flagged on arterial lane."
        if enforcer.is_active:
            system_state["total_challans_issued"] += 1
            system_state["total_fine_collected"] += 5000
            system_state["recent_challan_records"].insert(0, {
                "id": f"CH-WW-{int(time.time()*100)%100000}",
                "plate": "UP 16 BZ 5541",
                "type": "MOTORCYCLE",
                "violation": "COUNTER-FLOW / WRONG-WAY DRIVING",
                "section": "Sec 184 MVA - Driving in Contrary Direction to Traffic",
                "fine": "₹5000",
                "speed": "42 km/h",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            system_state["recent_challan_records"] = system_state["recent_challan_records"][:6]
        add_log("DEADLY INFRACTION: Wrong-way counter-flow driver detected on Arterial Highway!", "ALERT")

    elif action == "toggle_challan":
        enforcer.is_active = not enforcer.is_active
        system_state["challan_engine_active"] = enforcer.is_active
        status_str = "RESUMED [ONLINE]" if enforcer.is_active else "PAUSED [OFFLINE]"
        system_state["ai_reasoning"] = f"ENFORCEMENT TOGGLE: Radar state shifted to {status_str}."
        add_log(f"E-Challan Enforcement Engine {status_str}", "INFO")

    elif action.startswith("switch_cam_"):
        c_id = action.replace("switch_cam_", "").upper()
        if c_id in system_state["junctions"]:
            system_state["active_camera"] = c_id
            add_log(f"VIDEO NODE SWITCH: Telemetry linked to {c_id}", "INFO")

    elif action == "reset_spoof":
        system_state["spoof_alert"] = False
        system_state["spoof_reason"] = ""
        system_state["wrong_way_alert"] = False
        add_log("Infraction alerts cleared", "INFO")

    elif action == "watchdog_fail":
        system_state["watchdog_healthy"] = False
        system_state["ai_reasoning"] = "CRITICAL FAIL-SAFE: AI heartbeat lost! Hardware ESP32 relay took over 30s fixed cycle."
        add_log("AI Heartbeat Lost: Fail-safe mode engaged", "ALERT")

    elif action == "reset_watchdog":
        system_state["watchdog_healthy"] = True
        system_state["control_mode"] = "AUTONOMOUS_AI"
        system_state["ai_reasoning"] = "Heartbeat restored. AI resumed adaptive control."
        add_log("Heartbeat restored: ESP32 handoff complete", "INFO")

    elif action.startswith("force_phase_"):
        j_id = action.replace("force_phase_", "").upper()
        if j_id in system_state["junctions"]:
            curr = system_state["junctions"][j_id]["phase"]
            new_p = "NS_GREEN" if curr == "EW_GREEN" else "EW_GREEN"
            return force_signal_phase(j_id, new_p)

    elif action == "reset_all":
        system_state["control_mode"] = "AUTONOMOUS_AI"
        system_state["emergency_active"] = False
        system_state["spoof_alert"] = False
        system_state["spoof_reason"] = ""
        system_state["wrong_way_alert"] = False
        system_state["watchdog_healthy"] = True
        enforcer.is_active = True
        system_state["challan_engine_active"] = True
        for j in system_state["junctions"].values():
            j["manual_locked"] = False
        system_state["ai_reasoning"] = "System Master Reset: Returned to 100% Autonomous AI Autopilot."
        add_log("Master Reset: Returned to Autonomous AI Autopilot", "INFO")

    return {"status": "ok", "action": action, "challan_active": enforcer.is_active, "control_mode": system_state["control_mode"]}

@app.on_event("startup")
def open_dashboard():
    def _open():
        time.sleep(1.2)
        frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))
        if os.path.exists(frontend_path):
            webbrowser.open(f"file://{frontend_path}")
        else:
            webbrowser.open("http://127.0.0.1:8000/docs")

    threading.Thread(target=_open, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)