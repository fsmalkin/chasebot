"""Split a static-camera session into stable segments; save one upscaled
representative frame per segment for human bbox annotation."""
import json
import os
import sys

import cv2
import numpy as np

SRC = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)

files = sorted(f for f in os.listdir(SRC) if f.endswith(".jpg"))
prev = None
seg_start = 0
segments = []
idx_of = {}
for i, f in enumerate(files):
    g = cv2.cvtColor(cv2.imread(os.path.join(SRC, f)), cv2.COLOR_BGR2GRAY)
    if prev is not None:
        d = cv2.absdiff(g, prev)
        changed = int((d > 30).sum())
        if changed > 800:  # scene changed (ball moved / person / robot)
            if i - seg_start >= 8:  # keep only stable segments
                segments.append((seg_start, i - 1))
            seg_start = i
    prev = g
    idx_of[f] = i
if len(files) - seg_start >= 8:
    segments.append((seg_start, len(files) - 1))

manifest = []
for si, (a, b) in enumerate(segments):
    mid = files[(a + b) // 2]
    im = cv2.imread(os.path.join(SRC, mid))
    big = cv2.resize(im, (960, 720), interpolation=cv2.INTER_NEAREST)
    rep = "seg%02d_%s_n%d.png" % (si, mid[:-4], b - a + 1)
    cv2.imwrite(os.path.join(OUT, rep), big)
    manifest.append({"segment": si, "start": files[a], "end": files[b], "n": b - a + 1, "rep": rep})

json.dump(manifest, open(os.path.join(OUT, "segments.json"), "w"), indent=1)
print(json.dumps({"segments": len(segments), "frames": len(files)}))
