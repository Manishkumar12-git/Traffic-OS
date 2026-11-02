from ultralytics import YOLO

# Load the lightweight nano model (will auto-download on first run)
model = YOLO("yolo11n.pt")

# Run inference on Ultralytics sample image
results = model("https://ultralytics.com/images/bus.jpg")

for result in results:
    result.show()

print("YOLO is working perfectly!")