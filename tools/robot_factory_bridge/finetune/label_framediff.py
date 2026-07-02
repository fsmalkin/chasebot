"""Label ball positions by frame-differencing against a median background.

Assumes a STATIC camera and a small ball moved between frames. For each frame:
diff vs the median background -> compact round blob in a ball-plausible size
band -> YOLO-format label. Frames with people/large motion (big diff area) are
skipped. Emits a review montage for human spot-check.
"""
import argparse
import json
import math
import os
import random
import sys

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-d", type=float, default=5.0, help="min blob equiv diameter px")
    ap.add_argument("--max-d", type=float, default=45.0)
    ap.add_argument("--max-motion-px", type=float, default=2500.0,
                    help="skip frames with more changed pixels than this (feet, people)")
    ap.add_argument("--diff-thresh", type=int, default=28)
    ap.add_argument("--review-n", type=int, default=30)
    args = ap.parse_args()

    files = sorted(
        os.path.join(args.src, f) for f in os.listdir(args.src) if f.endswith(".jpg")
    )
    if len(files) < 20:
        print(json.dumps({"error": "too_few_frames", "n": len(files)}))
        return 1

    # median background over a subsample (ball moves; static scene dominates)
    sample = files[:: max(1, len(files) // 60)][:60]
    stack = np.stack([cv2.imread(f).astype(np.float32) for f in sample])
    bg = np.median(stack, axis=0).astype(np.uint8)
    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)

    img_dir = os.path.join(args.out, "images")
    lbl_dir = os.path.join(args.out, "labels")
    rev_dir = os.path.join(args.out, "review")
    for d in (img_dir, lbl_dir, rev_dir):
        os.makedirs(d, exist_ok=True)

    stats = {"labeled": 0, "skipped_motion": 0, "skipped_none": 0, "skipped_shape": 0}
    kept = []
    for fp in files:
        im = cv2.imread(fp)
        if im is None or im.shape[:2] != bg_gray.shape[:2]:
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        d = cv2.absdiff(g, bg_gray)
        _, mask = cv2.threshold(d, args.diff_thresh, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        changed = int(mask.sum() / 255)
        if changed > args.max_motion_px:
            stats["skipped_motion"] += 1
            continue
        if changed < 15:
            stats["skipped_none"] += 1
            continue
        res = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = res[0] if len(res) == 2 else res[1]
        best = None
        best_score = 0.0
        for c in contours:
            a = cv2.contourArea(c)
            if a < 12:
                continue
            x, y, w, h = cv2.boundingRect(c)
            eq = math.sqrt(w * h)
            if not (args.min_d <= eq <= args.max_d):
                continue
            ar = w / max(h, 1)
            if not (0.5 <= ar <= 2.0):
                continue
            peri = cv2.arcLength(c, True)
            circ = 4 * math.pi * a / (peri * peri + 1e-9)
            if circ < 0.4:
                continue
            if circ * a > best_score:
                best_score = circ * a
                best = (x, y, w, h)
        if best is None:
            stats["skipped_shape"] += 1
            continue
        x, y, w, h = best
        H, W = im.shape[:2]
        name = os.path.splitext(os.path.basename(fp))[0]
        cv2.imwrite(os.path.join(img_dir, name + ".jpg"), im)
        with open(os.path.join(lbl_dir, name + ".txt"), "w") as f:
            f.write("0 %.6f %.6f %.6f %.6f\n" % ((x + w / 2) / W, (y + h / 2) / H, w / W, h / H))
        stats["labeled"] += 1
        kept.append((name, best))

    for name, (x, y, w, h) in random.sample(kept, min(args.review_n, len(kept))):
        im = cv2.imread(os.path.join(img_dir, name + ".jpg"))
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0), 1)
        cv2.imwrite(os.path.join(rev_dir, name + ".jpg"), cv2.resize(im, (640, 480), interpolation=cv2.INTER_NEAREST))

    json.dump(stats, open(os.path.join(args.out, "stats.json"), "w"), indent=1)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
