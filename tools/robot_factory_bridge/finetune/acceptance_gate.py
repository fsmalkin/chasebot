"""Acceptance gate for golf-ball fine-tune candidates.

PASS requires: zero false positives on the ball-less sweep, and every anchor
in ANCHORS_MIN met (no-regression on proven scenes). Exit 0 = pass, 1 = fail.
Anchors grow as new surfaces are conquered: add a known-ball frame + floor.
"""
import argparse
import glob
import json
import os
import sys

from ultralytics import YOLO

REPO = r"D:\dev\chasebot-hw-v0"

# (tag, path, min conf @640). Registry of proven scenes — append, never relax.
ANCHORS_MIN = [
    ("carpet_near", os.path.join(REPO, "artifacts", "fresh_frame_gstreamer.jpg"), 0.90),
    ("glossy_far", os.path.join(REPO, "artifacts", "ball_placed.jpg"), 0.90),
    # anchors must live in labeled_* dirs (stable copies) — session dirs get
    # overwritten by later recordings (lost frame_000100 that way 2026-07-02)
    ("hardwood_hall", os.path.join(REPO, "artifacts", "finetune_dataset", "labeled_hardwood_v1",
                                   "images", "range_telemetry_20260702_frame_000022.jpg"), 0.80),
]

FP_FRAMES = sorted(set(
    glob.glob(os.path.join(REPO, "artifacts", "session", "iterate_runs", "ep_*", "_cur.jpg"))
    + [os.path.join(REPO, "artifacts", f) for f in (
        "after_pivot.jpg", "after_unwall.jpg", "argus_smoke.jpg", "cam_1640.jpg",
        "debug_frame.jpg", "go_check.jpg", "irl_now.jpg", "new_eyes.jpg",
        "onboard_view.jpg", "post_ep2.jpg", "post_ep3.jpg", "where_ball.jpg")]
))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="candidate .pt")
    ap.add_argument("--fp-conf", type=float, default=0.05)
    args = ap.parse_args()

    m = YOLO(args.model)

    def top(img, conf, imgsz=640):
        r = m.predict(img, conf=conf, imgsz=imgsz, verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            return None
        i = int(r.boxes.conf.argmax())
        return {"conf": round(float(r.boxes.conf[i]), 3),
                "xyxy": [round(float(x)) for x in r.boxes.xyxy[i]]}

    out = {"model": args.model, "anchors": {}, "false_positives": {}, "pass": True}
    for tag, path, floor in ANCHORS_MIN:
        d = top(path, conf=0.05)
        ok = bool(d and d["conf"] >= floor)
        out["anchors"][tag] = {"det": d, "floor": floor, "ok": ok}
        if not ok:
            out["pass"] = False
    for p in FP_FRAMES:
        d = top(p, conf=args.fp_conf)
        if d:
            out["false_positives"][os.path.relpath(p, REPO)] = d
            out["pass"] = False
    out["fp_frames_checked"] = len(FP_FRAMES)

    print(json.dumps(out, indent=2))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
