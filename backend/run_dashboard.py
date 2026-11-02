import cv2
import time
from camera.video_source import VideoSource
from vision.detector import VehicleDetector

def main():
    VIDEO_PATH = '../videos/sample.mp4'
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        source = 0
    else:
        cap.release()
        source = VIDEO_PATH

    camera = VideoSource(source)
    detector = VehicleDetector()

    window_name = 'TrafficOS - Vehicle Monitor'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 720, 960)

    prev_time = time.time()

    while True:
        frame = camera.get_frame()
        if frame is None:
            break

        annotated_frame, detections = detector.detect(frame)
        h, w, _ = annotated_frame.shape

        # Calculate FPS
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time

        # --- High-Contrast Top Status Header ---
        header_height = 70
        header = annotated_frame.copy()
        cv2.rectangle(header, (0, 0), (w, header_height), (18, 18, 22), -1)
        cv2.addWeighted(header, 0.90, annotated_frame, 0.10, 0, annotated_frame)
        cv2.line(annotated_frame, (0, header_height), (w, header_height), (0, 255, 120), 2)

        # Bold, clean metrics
        car_count = len(detections)
        cv2.putText(annotated_frame, 'TRAFFIC OS', (20, 32),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 120), 2, cv2.LINE_AA)
        cv2.putText(annotated_frame, f'ACTIVE CARS: {car_count}', (20, 58),
                    cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 230, 255), 2, cv2.LINE_AA)

        cv2.putText(annotated_frame, f'FPS: {fps:.1f}', (w - 140, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(window_name, annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
