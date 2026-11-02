import cv2

class VideoSource:
    def __init__(self, source_path):
        self.source_path = source_path
        self.cap = cv2.VideoCapture(source_path)

    def get_frame(self):
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.source_path)

        success, frame = self.cap.read()
        if not success:
            # Auto-loop back to start of video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            success, frame = self.cap.read()

        return frame if success else None

    def release(self):
        if self.cap:
            self.cap.release()
