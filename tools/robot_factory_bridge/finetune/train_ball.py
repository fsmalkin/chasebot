"""Train a single-class golf-ball detector from labeled dirs; report + export.

Merges one or more labeled dirs (images/ + labels/), makes a train/val split,
trains yolov8n (single class), prints val metrics and the best.pt path.
"""
import argparse
import json
import os
import random
import shutil
import sys

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeled", nargs="+", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=2,
                    help="dataloader workers; more blows the Windows commit limit (WinError 1455)")
    args = ap.parse_args()

    pairs = []
    for d in args.labeled:
        img_d, lbl_d = os.path.join(d, "images"), os.path.join(d, "labels")
        if not os.path.isdir(img_d):
            continue
        for f in os.listdir(img_d):
            if not f.endswith(".jpg"):
                continue
            lp = os.path.join(lbl_d, f[:-4] + ".txt")
            if os.path.isfile(lp):
                pairs.append((os.path.join(img_d, f), lp))
    if len(pairs) < 40:
        print(json.dumps({"error": "too_few_labeled", "n": len(pairs)}))
        return 1

    random.Random(7).shuffle(pairs)
    n_val = max(8, int(len(pairs) * args.val_frac))
    splits = {"val": pairs[:n_val], "train": pairs[n_val:]}
    for split, items in splits.items():
        for sub in ("images", "labels"):
            os.makedirs(os.path.join(args.work, split, sub), exist_ok=True)
        for ip, lp in items:
            shutil.copy(ip, os.path.join(args.work, split, "images", os.path.basename(ip)))
            shutil.copy(lp, os.path.join(args.work, split, "labels", os.path.basename(lp)))

    yaml_path = os.path.join(args.work, "ball.yaml")
    with open(yaml_path, "w") as f:
        f.write("path: %s\ntrain: train/images\nval: val/images\nnames:\n  0: golfball\n" % args.work.replace("\\", "/"))

    model = YOLO("yolov8n.pt")
    res = model.train(data=yaml_path, epochs=args.epochs, imgsz=args.imgsz, batch=16,
                      project=os.path.join(args.work, "runs"), name="ball", exist_ok=True,
                      patience=20, verbose=False, workers=args.workers)
    best = os.path.join(args.work, "runs", "ball", "weights", "best.pt")
    m = model.val(data=yaml_path, verbose=False)
    out = {
        "n_train": len(splits["train"]), "n_val": len(splits["val"]),
        "map50": round(float(m.box.map50), 4), "map5095": round(float(m.box.map), 4),
        "precision": round(float(m.box.mp), 4), "recall": round(float(m.box.mr), 4),
        "best": best,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
