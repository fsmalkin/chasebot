"""Debug YOLO-World on a known-good frame: raw boxes, prompt variants, sizes."""
import cv2
from ultralytics import YOLOWorld

FRAME = r"D:\dev\chasebot-hw-v0\artifacts\irl_overlay.jpg"  # wood floor, yolov5m scored 0.46 here
im = cv2.imread(FRAME)
print("frame shape:", im.shape)

for prompts in (["white golf ball"], ["golf ball"], ["ball"], ["small white ball on the floor"]):
    model = YOLOWorld("yolov8s-worldv2.pt")
    model.set_classes(prompts)
    for imgsz in (640, 1280):
        res = model.predict(im, conf=0.01, imgsz=imgsz, verbose=False)[0]
        n = 0 if res.boxes is None else len(res.boxes)
        tops = []
        if n:
            for i in range(min(n, 3)):
                tops.append("%.3f@%s" % (float(res.boxes.conf[i]), [int(v) for v in res.boxes.xyxy[i]]))
        print("prompt=%-32s imgsz=%-5d boxes=%d  top: %s" % (prompts[0], imgsz, n, "; ".join(tops)))
