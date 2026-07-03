"""Range-pass telemetry: raw bridge frames + live detection feed, timestamped."""
import json
import os
import sys
import time
import urllib.request

OUT = r"D:\dev\chasebot-hw-v0\artifacts\session\range_telemetry_" + time.strftime("%Y%m%dT%H%M%S")
BRIDGE = "http://192.168.1.11:8765"
FEED = "http://127.0.0.1:8791/status"
PERIOD_S = 0.33
MAX_S = 1200

os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "telemetry.jsonl"), "a", buffering=1)
t0 = time.time()
n = 0
misses = 0
while time.time() - t0 < MAX_S:
    t_iter = time.time()
    row = {"t": round(t_iter - t0, 3), "wall": t_iter}
    try:
        with urllib.request.urlopen(BRIDGE + "/camera.jpg", timeout=4) as r:
            jpg = r.read()
        fname = "frame_%06d.jpg" % n
        with open(os.path.join(OUT, fname), "wb") as f:
            f.write(jpg)
        row["frame"] = fname
        row["bytes"] = len(jpg)
        misses = 0
    except Exception as e:
        row["frame_err"] = repr(e)
        misses += 1
    try:
        with urllib.request.urlopen(FEED, timeout=3) as r:
            s = json.loads(r.read().decode())
        row["det"] = s.get("det")
        row["det_ts"] = s.get("det_ts")
        row["run_state"] = s.get("last")
    except Exception as e:
        row["feed_err"] = repr(e)
    log.write(json.dumps(row) + "\n")
    n += 1
    if misses > 30:
        break
    dt = time.time() - t_iter
    if dt < PERIOD_S:
        time.sleep(PERIOD_S - dt)
print(json.dumps({"frames": n, "duration_s": round(time.time() - t0, 1), "out": OUT}))

