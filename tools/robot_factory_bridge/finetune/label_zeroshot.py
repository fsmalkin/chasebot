"""Zero-shot label golf-ball frames with YOLO-World; emit YOLO-format labels.

Labels every jpg under the given dirs. Writes:
  <out>/images/*.jpg, <out>/labels/*.txt (class 0 = golfball)
  <out>/review/*.jpg   annotated copies of a sample for human spot-check
  <out>/stats.json
Frames with no detection are kept as negatives (empty label file) only if
--keep-negatives; else skipped.
"""
import argparse
import json
import os
import random
import shutil
import sys

from ultralytics import YOLOWorld
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--conf", type=float, default=0.08)
    ap.add_argument("--review-n", type=int, default=24)
    ap.add_argument("--keep-negatives", action="store_true")
    ap.add_argument("--max-per-dir", type=int, default=1200)
    ap.add_argument("--prompt", default="ball",
                    help="'ball' beat 'white golf ball' on lit gstreamer-path frames (2026-07-02 bake-off)")
    ap.add_argument("--model-path", default=r"D:\dev\chasebot-hw-v0\runtime\yolo\yolov8s-worldv2.pt")
    args = ap.parse_args()

    model = YOLOWorld(args.model_path)
    model.set_classes([args.prompt])

    img_dir = os.path.join(args.out, "images")
    lbl_dir = os.path.join(args.out, "labels")
    rev_dir = os.path.join(args.out, "review")
    for d in (img_dir, lbl_dir, rev_dir):
        os.makedirs(d, exist_ok=True)

    stats = {"labeled": 0, "negatives": 0, "skipped": 0, "multi": 0}
    labeled_paths = []
    for src in args.src:
        files = sorted(
            os.path.join(r, f)
            for r, _d, fs in os.walk(src)
            for f in fs
            if f.lower().endswith(".jpg") and "review" not in r
        )[: args.max_per_dir]
        for fp in files:
            im = cv2.imread(fp)
            if im is None:
                continue
            h, w = im.shape[:2]
            res = model.predict(im, conf=args.conf, verbose=False)[0]
            boxes = res.boxes
            name = os.path.splitext(os.path.basename(fp))[0]
            uniq = "%s_%s" % (os.path.basename(os.path.dirname(fp)), name)
            lines = []
            if boxes is not None and len(boxes) > 0:
                if len(boxes) > 1:
                    stats["multi"] += 1
                    # keep only the highest-confidence box (one ball in the house)
                    best_i = int(boxes.conf.argmax())
                    sel = [best_i]
                else:
                    sel = [0]
                for i in sel:
                    x0, y0, x1, y1 = [float(v) for v in boxes.xyxy[i]]
                    cx, cy = (x0 + x1) / 2 / w, (y0 + y1) / 2 / h
                    bw, bh = (x1 - x0) / w, (y1 - y0) / h
                    lines.append("0 %.6f %.6f %.6f %.6f" % (cx, cy, bw, bh))
            if lines:
                shutil.copy(fp, os.path.join(img_dir, uniq + ".jpg"))
                open(os.path.join(lbl_dir, uniq + ".txt"), "w").write("\n".join(lines) + "\n")
                stats["labeled"] += 1
                labeled_paths.append((uniq, [float(v) for v in boxes.xyxy[int(boxes.conf.argmax())]],
                                      float(boxes.conf.max())))
            elif args.keep_negatives:
                shutil.copy(fp, os.path.join(img_dir, uniq + ".jpg"))
                open(os.path.join(lbl_dir, uniq + ".txt"), "w").write("")
                stats["negatives"] += 1
            else:
                stats["skipped"] += 1

    # review montage sample
    for uniq, box, conf in random.sample(labeled_paths, min(args.review_n, len(labeled_paths))):
        im = cv2.imread(os.path.join(img_dir, uniq + ".jpg"))
        x0, y0, x1, y1 = [int(v) for v in box]
        cv2.rectangle(im, (x0, y0), (x1, y1), (0, 255, 0), 1)
        cv2.putText(im, "%.2f" % conf, (x0, max(8, y0 - 3)), cv2.FONT_HERSHEY_PLAIN, 0.8, (0, 255, 0))
        cv2.imwrite(os.path.join(rev_dir, uniq + ".jpg"), im)

    json.dump(stats, open(os.path.join(args.out, "stats.json"), "w"), indent=1)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
