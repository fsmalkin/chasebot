"""Laptop control server: GO/STOP fetch dashboard with live YOLO overlay.

Serves http://100.112.221.6:8791/ — green GO runs the mono fetch approach+push
against the robot bridge; red STOP kills the run and locks the bridge. The
camera feed is annotated by a background YOLO thread (bbox + confidence +
calibrated distance) so the operator sees exactly what perception sees.
"""
import http.server
import io
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

REPO = r"D:\dev\chasebot-hw-v0"
BRIDGE = "http://192.168.1.11:8765"
CAL = "artifacts/session/mono_distance_calibration_bench01/calibration_summary.json"
CTRL = "tools/robot_factory_bridge/chasecar_bridge_visual_fetch_controller.py"
RUNDIR = os.path.join(REPO, "artifacts", "session", "dashboard_runs")
MODEL = os.path.join(REPO, "runtime", "yolo", "yolov5m.onnx")
CUSTOM_PT = os.path.join(REPO, "runtime", "yolo", "golfball_finetune.pt")  # best: bench fine-tune
WORLD_PT = os.path.join(REPO, "runtime", "yolo", "yolov8s-worldv2.pt")  # zero-shot "ball" prompt
K_PX_M = 9.621  # real-bench calibration (equiv_diameter_px)

sys.path.insert(0, os.path.join(REPO, "tools", "robot_factory_bridge"))

state = {"proc": None, "running": False, "last": "idle", "outfile": None}
lock = threading.Lock()

# latest annotated frame + detection info, maintained by the detector thread
cam = {"jpeg": None, "ts": 0.0, "det": None, "err": "starting", "last_view": 0.0, "fail_streak": 0}
cam_lock = threading.Lock()


def bridge_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BRIDGE + path, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read()
    except Exception as e:
        return str(e).encode()


def bridge_get(path, timeout=5):
    try:
        with urllib.request.urlopen(BRIDGE + path, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None
    except Exception as e:
        return 502, str(e).encode(), None


def detector_loop():
    """Continuously: grab bridge frame -> detector -> annotate -> cache.

    Backend priority: golfball_finetune.pt (bench-trained single class) ->
    yolov8s-worldv2.pt zero-shot prompted with "ball" (IRL-validated 2026-07-02:
    0 false positives across archived bench frames at conf 0.05, only detector
    to find the far-ball-on-glossy-mat case) -> yolov5m ONNX "sports ball".
    """
    # Ensemble: fine-tune first (0.97 conf in its trained scene, but scene-blind
    # elsewhere — went 0.0 on the wood-floor room live 2026-07-02); YOLO-World
    # zero-shot takes any frame the fine-tune misses (generalizes across scenes,
    # 0 FP at conf 0.05 on this bench).
    ult = world = None
    try:
        if os.path.isfile(CUSTOM_PT):
            from ultralytics import YOLO as _UY
            ult = _UY(CUSTOM_PT)
        if os.path.isfile(WORLD_PT):
            from ultralytics import YOLOWorld as _UW
            world = _UW(WORLD_PT)
            world.set_classes(["ball"])
        if ult is not None or world is not None:
            print("detector backend: %s" % "+".join(
                n for n, m in (("finetune", ult), ("yolo-world:ball", world)) if m is not None), flush=True)
    except Exception as e:
        print("ultralytics backend failed (%r); falling back to ONNX" % e, flush=True)
        ult = world = None
    try:
        import chasecar_bridge_yolo_onnx_probe as yp
        err = yp.load_detector_dependencies(require_onnx=ult is None)
        if err:
            raise RuntimeError(err)
        from PIL import Image, ImageDraw
        sess = inp = dtype = None
        if ult is None and world is None:
            import onnxruntime as ort
            sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
            inp = sess.get_inputs()[0]
            dtype = yp.np.float16 if "float16" in str(inp.type).lower() else yp.np.float32
    except Exception as e:
        with cam_lock:
            cam["err"] = "detector init failed: %r" % e
        return
    while True:
        t0 = time.time()
        with cam_lock:
            idle = (time.time() - cam["last_view"]) > 15.0
        if idle:  # nobody watching -> don't load the robot's Wi-Fi
            time.sleep(1.0)
            continue
        code, raw, _ = bridge_get("/camera.jpg", timeout=6)
        # data flywheel: every episode's frames land in the training inbox,
        # tagged with the outcome by _watch — failed runs on new surfaces ARE
        # the next training set (owner call 2026-07-02)
        if code == 200 and raw and len(raw) >= 500:
            with lock:
                epdir = state.get("epdir") if state["running"] else None
            if epdir:
                try:
                    fn = os.path.join(epdir, "frame_%d.jpg" % int(time.time() * 1000))
                    with open(fn, "wb") as f:
                        f.write(raw)
                except Exception:
                    pass
        if code != 200 or not raw or len(raw) < 500:
            with cam_lock:
                cam["err"] = "camera unreachable"
                cam["det"] = None
                cam["fail_streak"] += 1
                streak = cam["fail_streak"]
            if streak % 4 == 0:  # self-heal a Wi-Fi flap
                subprocess.run(["netsh", "wlan", "connect", "name=jetbot-mini"], capture_output=True)
            time.sleep(1.0)
            continue
        with cam_lock:
            cam["fail_streak"] = 0
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            w, h = img.size
            if ult is not None or world is not None:
                best = None
                for name, model, floor in (("ft", ult, 0.10), ("yw", world, 0.05)):
                    if model is None:
                        continue
                    r = model.predict(img, conf=floor, imgsz=640, verbose=False)[0]
                    if r.boxes is not None and len(r.boxes) > 0:
                        i = int(r.boxes.conf.argmax())
                        bx = [float(v) for v in r.boxes.xyxy[i]]
                        cxx = (bx[0] + bx[2]) / 2.0
                        best = {"bbox_xyxy": bx, "confidence": float(r.boxes.conf[i]),
                                "center_error": (cxx - w / 2.0) / (w / 2.0), "src": name}
                        break  # fine-tune wins when it fires; World covers its blind scenes
            else:
                tens, scale, pad = yp.letterbox(img, 640, dtype=dtype)
                out = sess.run(None, {inp.name: tens})
                dets = yp.decode_yolov5_output(
                    out[0], width=w, height=h, scale=scale, pad=pad,
                    confidence_threshold=0.10, class_names={"sports ball"}, iou_threshold=0.45,
                )
                best = yp.select_best_detection(dets, min_area_ratio=0.0)
            d = ImageDraw.Draw(img)
            # center crosshair + deadband guides
            d.line([(w / 2, 0), (w / 2, h)], fill=(90, 90, 90))
            det_info = None
            if best:
                x0, y0, x1, y1 = best["bbox_xyxy"]
                conf = float(best.get("confidence") or 0.0)
                eq = ((max(0.0, x1 - x0)) * (max(0.0, y1 - y0))) ** 0.5
                z = (K_PX_M / eq) if eq > 0 else None
                col = (40, 220, 90) if conf >= 0.25 else (250, 200, 40)
                d.rectangle([x0, y0, x1, y1], outline=col, width=2)
                label = "%.2f  z=%.2fm" % (conf, z) if z else "%.2f" % conf
                d.text((max(2, x0), max(2, y0 - 12)), label, fill=col)
                det_info = {"confidence": round(conf, 3), "z_m": round(z, 3) if z else None,
                            "center_error": best.get("center_error"), "equiv_px": round(eq, 1),
                            "src": best.get("src")}
            else:
                d.text((4, 4), "no ball", fill=(240, 80, 60))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            with cam_lock:
                cam["jpeg"] = buf.getvalue()
                cam["ts"] = time.time()
                cam["det"] = det_info
                cam["err"] = ""
        except Exception as e:
            with cam_lock:
                cam["err"] = "overlay error: %r" % e
        # cadence: ensemble is ~30ms on the GPU; 0.3s shrinks the verdict lag
        # the onboard scan sees (heading lag caught live 2026-07-02)
        dt = time.time() - t0
        if dt < 0.3:
            time.sleep(0.3 - dt)


def hard_stop():
    with lock:
        p = state["proc"]
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        state["running"] = False
        state["last"] = "STOPPED"
    bridge_post("/stop", {"source": "dashboard_stop"})
    bridge_post("/motion", {"enabled": False, "source": "dashboard_stop"})
    # terminating the local ssh can orphan the remote episode process; kill it
    # explicitly (harmless post-relock either way — bridge refuses motion)
    threading.Thread(target=lambda: subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "jetson@192.168.1.11",
         "pkill -f chasecar_onboard_fetch.py"], capture_output=True, timeout=15), daemon=True).start()


def _watch(p, outfile):
    p.wait()
    reason = "exit %s" % p.returncode
    try:
        with open(outfile, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip().startswith("{")]
        data = json.loads(lines[-1])  # episode summary is the last JSON line
        reason = data.get("stop_reason", reason)
        if (data.get("push") or {}).get("executed"):
            reason += " (+push %d)" % data["push"]["executed"]
    except Exception:
        pass
    with lock:
        if state["last"] != "STOPPED":
            state["last"] = "done: " + reason
        state["running"] = False
        epdir = state.pop("epdir", None)
    bridge_post("/motion", {"enabled": False, "source": "dashboard_postlock"})
    if epdir and os.path.isdir(epdir):
        tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40]
        try:
            os.rename(epdir, epdir + "_" + tag)
        except Exception:
            pass


def start_approach():
    with lock:
        if state["running"] and state["proc"] and state["proc"].poll() is None:
            return "already running"
        os.makedirs(RUNDIR, exist_ok=True)
        stamp = int(time.time())
        outfile = os.path.join(RUNDIR, "run_%d.json" % stamp)
        epdir = os.path.join(REPO, "artifacts", "finetune_dataset", "inbox", "ep_%d" % stamp)
        os.makedirs(epdir, exist_ok=True)
        state["epdir"] = epdir
        # GO = the validated hybrid loop: onboard brain on the Jetson drives via
        # localhost, consuming this server's fine-tune detection feed. The old
        # offboard controller (CTRL) carried its own weak ONNX detector and lost
        # the ball (3x lost_target on 2026-07-02); keep it only as a fallback.
        cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "jetson@192.168.1.11",
            "python3", "/home/jetson/chasecar_onboard/chasecar_onboard_fetch.py",
            "--detector", "trt",  # local GPU eyes (13.5ms/frame); remote feed stays for the dashboard view
            "--min-confidence", "0.2", "--search-scan", "26", "--lost-limit", "12",
            "--standoff-m", "0.35", "--push-steps", "10",
            "--run-dir", "/home/jetson/chasecar_onboard/runs",
        ]
        bridge_post("/motion", {"enabled": False, "source": "dashboard_prelock"})
        fout = open(outfile, "w", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=REPO, stdout=fout, stderr=subprocess.DEVNULL)
        state["proc"] = p
        state["running"] = True
        state["last"] = "RUNNING"
        state["outfile"] = outfile
        threading.Thread(target=_watch, args=(p, outfile), daemon=True).start()
        return "started"


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Chasecar Fetch</title>
<style>
 body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#0e0f12;color:#e8e8ea;text-align:center;-webkit-user-select:none;user-select:none}
 h2{margin:10px}
 .cam{width:100%;max-width:460px;background:#000;border-radius:8px;margin:6px auto;display:block}
 .status{font-family:ui-monospace,monospace;font-size:13px;color:#9aa0a8;margin:8px;white-space:pre-line}
 .btns{display:flex;gap:14px;justify-content:center;margin:14px;padding:0 12px}
 button{font-size:30px;font-weight:800;border:none;border-radius:18px;padding:30px 20px;flex:1;max-width:230px;color:#fff}
 .go{background:#147a46}.go:active{background:#0d5730}
 .stop{background:#b42318}.stop:active{background:#7a1d16}
</style></head><body>
<h2>Chasecar Fetch</h2>
<img class="cam" id="cam" alt="camera">
<div class="status" id="status">connecting...</div>
<div class="btns">
 <button class="go" id="go">GO</button>
 <button class="stop" id="stop">STOP</button>
</div>
<script>
 function post(p){return fetch(p,{method:'POST'}).then(function(r){return r.json();}).catch(function(e){return {error:''+e};});}
 document.getElementById('go').onclick=function(){document.getElementById('status').textContent='starting...';post('/go');};
 document.getElementById('stop').onclick=function(){document.getElementById('status').textContent='STOPPING...';post('/stop');};
 function tick(){
  document.getElementById('cam').src='/camera.jpg?t='+Date.now();
  fetch('/status').then(function(r){return r.json();}).then(function(s){
   var det = s.det ? ('ball: conf '+s.det.confidence+'  z='+s.det.z_m+'m') : ('ball: '+(s.cam_err||'not detected'));
   document.getElementById('status').textContent='approach: '+s.last+'   |   motion='+s.motion_enabled+'\\n'+det;
  }).catch(function(){document.getElementById('status').textContent='status error';});
 }
 setInterval(tick,800);tick();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ct="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/camera.jpg"):
            with cam_lock:
                jpeg, ts = cam["jpeg"], cam["ts"]
                cam["last_view"] = time.time()
            if jpeg and (time.time() - ts) < 5.0:
                self._send(200, jpeg, "image/jpeg")
            else:  # overlay not ready/stale -> raw passthrough
                code, data, ct = bridge_get("/camera.jpg")
                self._send(code, data, ct or "image/jpeg")
            return
        if self.path.startswith("/status"):
            with lock:
                s = {"running": state["running"], "last": state["last"]}
            with cam_lock:
                s["det"] = cam["det"]
                s["det_ts"] = cam["ts"]
                s["cam_err"] = cam["err"]
                cam["last_view"] = time.time()  # status pollers (onboard brain) keep the detector hot
            code, data, ct = bridge_get("/health")
            try:
                h = json.loads(data)
                s["motion_enabled"] = h.get("motion_enabled")
            except Exception:
                pass
            self._send(200, json.dumps(s), "application/json")
            return
        self._send(200, DASH)

    def do_POST(self):
        if self.path.startswith("/go"):
            self._send(200, json.dumps({"ok": True, "msg": start_approach()}), "application/json")
            return
        if self.path.startswith("/stop"):
            hard_stop()
            self._send(200, json.dumps({"ok": True, "msg": "stopped"}), "application/json")
            return
        self._send(404, "not found")

    def log_message(self, *a):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    threading.Thread(target=detector_loop, daemon=True).start()
    print("control server on 0.0.0.0:8791 (Tailscale http://100.112.221.6:8791/)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8791), Handler).serve_forever()
