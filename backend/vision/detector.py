import cv2
from ultralytics import YOLO

class VehicleDetector:
    def __init__(self, model_path='yolo11s.pt'):
        self.model = YOLO(model_path)
        # Target classes + objects YOLO confuses with car roofs from aerial views
        self.valid_car_aliases = {'car', 'cell phone', 'suitcase', 'remote', 'truck', 'bus'}

    def detect(self, frame):
        # imgsz=1024 + conf=0.10 captures tiny cars in top-down shots
        results = self.model.predict(
            source=frame,
            conf=0.10,
            imgsz=1024,
            verbose=False
        )
        
        detections = []
        annotated_frame = frame.copy()

        if results and len(results) > 0:
            result = results[0]
            for box in result.boxes:
                cls_id = int(box.cls[0])
                raw_label = result.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                # Filter out traffic lights, bottles, etc. Only accept vehicles
                if raw_label in self.valid_car_aliases:
                    # Eliminate abnormally huge or microscopic false positives
                    w, h = (x2 - x1), (y2 - y1)
                    if 15 < w < 250 and 20 < h < 350:
                        detections.append({
                            'class': 'Car',
                            'confidence': conf,
                            'bbox': [x1, y1, x2, y2]
                        })

                        # Clean bounding box (Green)
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 120), 2)

                        # Clean label: only "Car" and confidence
                        tag = f'Car {int(conf * 100)}%'
                        cv2.rectangle(annotated_frame, (x1, y1 - 20), (x1 + 80, y1), (0, 255, 120), -1)
                        cv2.putText(annotated_frame, tag, (x1 + 3, y1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        return annotated_frame, detections
