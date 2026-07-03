"""Train a single-class golf-ball detector from labeled dirs; report + export.

Merges one or more labeled dirs (images/ + labels/), makes a train/val split,
trains yolov8n (single class), prints val metrics and the best.pt path.

Compute policy: batch auto-fits to free VRAM (batch=-1), dataset is RAM-cached,
and dataloader workers adapt to the Windows COMMIT headroom — each spawned
worker maps the CUDA DLL set (~6-8 GB commit); exceeding the commit limit is
the WinError 1455 crash that killed earlier runs.
"""
import argparse
import ctypes
import json
import os
import random
import shutil
import sys

from ultralytics import YOLO


def commit_headroom_gb():
    """Available Windows commit charge (page-file-backed), in GB."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
                    ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64)]
    ms = MEMORYSTATUSEX()
    ms.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
        return 8.0  # conservative default
    return ms.ullAvailPageFile / (1024.0 ** 3)


def auto_workers():
    """~7 GB commit per spawned torch worker; keep a 6 GB safety floor."""
    return max(1, min(8, int((commit_headroom_gb() - 6.0) // 7.0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeled", nargs="+", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=-1,
                    help="-1 = adapt to commit headroom (each worker ~7 GB commit; WinError 1455 guard)")
    ap.add_argument("--batch", type=int, default=-1,
                    help="-1 = ultralytics auto-batch to free VRAM")
    ap.add_argument("--no-cache", action="store_true", help="disable RAM-caching the dataset")
    args = ap.parse_args()
    if args.workers < 0:
        args.workers = auto_workers()
    print(json.dumps({"compute": {"workers": args.workers, "batch": args.batch,
                                  "commit_headroom_gb": round(commit_headroom_gb(), 1),
                                  "cache": not args.no_cache}}))

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
    res = model.train(data=yaml_path, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                      project=os.path.join(args.work, "runs"), name="ball", exist_ok=True,
                      patience=20, verbose=False, workers=args.workers, amp=True,
                      cache=(False if args.no_cache else "ram"))
    best = os.path.join(args.work, "runs", "ball", "weights", "best.pt")
    m = model.val(data=yaml_path, verbose=False,
                  project=os.path.join(args.work, "runs"), name="val", exist_ok=True)
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
