"""Acceptance gate for fine-tune v2 (two-room): no carpet regression, hardwood gains, 0 FP."""
import glob
import json
import os

from ultralytics import YOLO

REPO = r"D:\dev\chasebot-hw-v0"
BEST = os.path.join(REPO, "artifacts", "finetune_dataset", "train_v2_tworoom", "runs", "ball", "weights", "best.pt")

m = YOLO(BEST)

def top(img, conf=0.05, imgsz=640):
    r = m.predict(img, conf=conf, imgsz=imgsz, verbose=False)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return None
    i = int(r.boxes.conf.argmax())
    return {"conf": round(float(r.boxes.conf[i]), 3), "xyxy": [round(float(x)) for x in r.boxes.xyxy[i]]}

out = {"anchors_640": {}, "anchors_320": {}, "false_positives": {}, "hardwood_sample_640": {}}

anchors = {
    "carpet_near": os.path.join(REPO, "artifacts", "fresh_frame_gstreamer.jpg"),
    "glossy_far": os.path.join(REPO, "artifacts", "ball_placed.jpg"),
    "old_room_wood_transfer": os.path.join(REPO, "artifacts", "cam_revert.jpg"),
}
for tag, p in anchors.items():
    out["anchors_640"][tag] = top(p, imgsz=640)
    out["anchors_320"][tag] = top(p, imgsz=320)

noball = sorted(set(
    glob.glob(os.path.join(REPO, "artifacts", "session", "iterate_runs", "ep_*", "_cur.jpg"))
    + [os.path.join(REPO, "artifacts", f) for f in (
        "after_pivot.jpg", "after_unwall.jpg", "argus_smoke.jpg", "cam_1640.jpg",
        "debug_frame.jpg", "go_check.jpg", "irl_now.jpg", "new_eyes.jpg",
        "onboard_view.jpg", "post_ep2.jpg", "post_ep3.jpg", "where_ball.jpg")]
))
for p in noball:
    d = top(p, conf=0.05)
    if d:
        out["false_positives"][os.path.relpath(p, REPO)] = d
out["fp_frames_checked"] = len(noball)

hw = sorted(glob.glob(os.path.join(REPO, "artifacts", "session", "range_telemetry_20260702", "frame_*.jpg")))
for p in hw[100:2400:400]:
    out["hardwood_sample_640"][os.path.basename(p)] = top(p)

print(json.dumps(out, indent=2))
