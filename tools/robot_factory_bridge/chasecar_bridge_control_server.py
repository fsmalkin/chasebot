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
import urllib.parse
import urllib.request

REPO = r"D:\dev\chasebot-hw-v0"
BRIDGE = os.environ.get("CHASECAR_BRIDGE_URL", "http://192.168.1.11:8765")
ROBOT_HOST = os.environ.get("CHASECAR_ROBOT_HOST", "192.168.1.11")
ROBOT_USER = os.environ.get("CHASECAR_ROBOT_USER", "jetson")
CAL = "artifacts/session/mono_distance_calibration_bench01/calibration_summary.json"
CTRL = "tools/robot_factory_bridge/chasecar_bridge_visual_fetch_controller.py"
RUNDIR = os.path.join(REPO, "artifacts", "session", "dashboard_runs")
MODEL = os.path.join(REPO, "runtime", "yolo", "yolov5m.onnx")
CUSTOM_PT = os.path.join(REPO, "runtime", "yolo", "golfball_finetune.pt")  # best: bench fine-tune
WORLD_PT = os.path.join(REPO, "runtime", "yolo", "yolov8s-worldv2.pt")  # zero-shot "ball" prompt
K_PX_M = 9.621  # real-bench calibration (equiv_diameter_px)
ARUCO_DICTIONARY_NAME = os.environ.get("CHASECAR_ARUCO_DICTIONARY", "DICT_4X4_50")
ARUCO_MARKER_ID = os.environ.get("CHASECAR_ARUCO_MARKER_ID", "0")
ARUCO_MARKER_SIZE_M = os.environ.get("CHASECAR_ARUCO_MARKER_SIZE_M", "0.10")
ARUCO_FOCAL_PX = os.environ.get("CHASECAR_ARUCO_FOCAL_PX", "225.317")

sys.path.insert(0, os.path.join(REPO, "tools", "robot_factory_bridge"))
from chasecar_bridge_aruco_target import ArucoTargetDetector

state = {"proc": None, "running": False, "starting": False, "last": "idle", "outfile": None}
lock = threading.Lock()

# manual 2D jog: armed on first press, watchdog relocks after idle
jog = {"armed": False, "last_cmd": 0.0}
jog_lock = threading.Lock()


def jog_watchdog():
    while True:
        time.sleep(0.4)
        with jog_lock:
            expired = jog["armed"] and (time.time() - jog["last_cmd"]) > 1.5
            if expired:
                jog["armed"] = False
        if expired:
            bridge_post("/stop", {"source": "dashboard_jog_idle"})
            bridge_post("/motion", {"enabled": False, "source": "dashboard_jog_idle"})

# latest annotated frame + detection info, maintained by the detector thread
cam = {
    "jpeg": None,
    "ts": 0.0,
    "det": None,
    "err": "starting",
    "target": None,
    "target_ts": None,
    "target_err": "starting",
    "last_view": 0.0,
    "fail_streak": 0,
}
cam_lock = threading.Lock()


def bridge_post(path, body, timeout=5):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BRIDGE + path, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.read()
    except urllib.error.HTTPError as e:
        return False, e.read()
    except Exception as e:
        return False, str(e).encode()


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
    target_detector = None
    target_init_error = ""
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
    try:
        import cv2
        target_detector = ArucoTargetDetector(
            cv2_module=cv2,
            np_module=yp.np,
            dictionary_name=ARUCO_DICTIONARY_NAME,
            marker_id=int(ARUCO_MARKER_ID),
            marker_size_m=float(ARUCO_MARKER_SIZE_M),
            focal_px=float(ARUCO_FOCAL_PX),
        )
        print(
            "target backend: aruco %s id=%d size=%.3fm" % (
                target_detector.dictionary_name,
                target_detector.marker_id,
                target_detector.marker_size_m,
            ),
            flush=True,
        )
    except Exception as e:
        target_init_error = "target detector unavailable: %r" % e
        print(target_init_error, flush=True)
    with cam_lock:
        cam["target_err"] = target_init_error
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
                cam["target"] = None
                cam["target_ts"] = None
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
            frame_ts = time.time()
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
            target_info = None
            target_frame_error = target_init_error
            if target_detector is not None:
                try:
                    target_info = target_detector.detect(img)
                    target_frame_error = ""
                    if target_info is not None:
                        target_info["observed_ts"] = frame_ts
                except Exception as e:
                    target_frame_error = "target detection failed: %r" % e
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
            if target_info:
                target_corners = [tuple(p) for p in target_info["corners_px"]]
                d.line(target_corners + [target_corners[0]], fill=(70, 160, 255), width=3)
                target_label = "target %d  bearing=%+.1f" % (
                    target_info["id"],
                    target_info["bearing_deg"],
                )
                if target_info.get("z_m") is not None:
                    target_label += "  z=%.2fm" % target_info["z_m"]
                tx, ty = target_corners[0]
                d.text((max(2, tx), max(14, ty - 12)), target_label, fill=(70, 160, 255))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            with cam_lock:
                cam["jpeg"] = buf.getvalue()
                cam["ts"] = frame_ts
                cam["det"] = det_info
                cam["err"] = ""
                cam["target"] = target_info
                cam["target_ts"] = frame_ts if target_info is not None else None
                cam["target_err"] = target_frame_error
        except Exception as e:
            with cam_lock:
                cam["err"] = "overlay error: %r" % e
                cam["target"] = None
                cam["target_ts"] = None
        # cadence: ensemble is ~30ms on the GPU; 0.3s shrinks the verdict lag
        # the onboard scan sees (heading lag caught live 2026-07-02)
        dt = time.time() - t0
        if dt < 0.3:
            time.sleep(0.3 - dt)


def _disarm_jog():
    """Prevent the jog idle-watchdog from firing a motion-disable into a fresh episode."""
    with jog_lock:
        jog["armed"] = False


def _robot_ssh_target():
    return "%s@%s" % (ROBOT_USER, ROBOT_HOST)


def remote_pkill_fetch(source, timeout=8.0):
    # bracketed pattern so pkill cannot match the shell running this very
    # command (self-match killed the ssh session -> rc -1, empty stderr;
    # every pkill had silently failed this way until fail-closed surfaced it)
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", _robot_ssh_target(),
        "pkill -f 'chasecar_onboard_fetc[h]' || true",
    ]
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=timeout)
        return {"ok": r.returncode == 0, "returncode": r.returncode, "source": source}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "source": source, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "returncode": None, "source": source, "error": repr(e)}


def _motors_zero(h):
    try:
        lm = abs(float(h.get("left_motor") or 0.0))
        rm = abs(float(h.get("right_motor") or 0.0))
    except Exception:
        return False
    return lm < 1e-6 and rm < 1e-6


def verify_motion_disabled(source, attempts=4, poll_interval=0.5, timeout=0.15):
    """POST stop/disable, then prove the bridge reports locked motors-zero."""
    details = {"verified": False, "checks": [], "post_ok": False, "disable_ok": False}
    ok_stop, body_stop = bridge_post("/stop", {"source": source}, timeout=timeout)
    ok_motion, body_motion = bridge_post("/motion", {"enabled": False, "source": source}, timeout=timeout)
    details["post_ok"] = bool(ok_stop)
    details["disable_ok"] = bool(ok_motion)
    details["stop_body"] = body_stop.decode("utf-8", "replace")[:200]
    details["disable_body"] = body_motion.decode("utf-8", "replace")[:200]
    for i in range(int(attempts)):
        code, data, _ct = bridge_get("/health", timeout=timeout)
        check = {"attempt": i + 1, "code": code}
        try:
            h = json.loads(data)
            check["motion_enabled"] = h.get("motion_enabled")
            check["left_motor"] = h.get("left_motor")
            check["right_motor"] = h.get("right_motor")
            if h.get("motion_enabled") is False and _motors_zero(h):
                check["verified"] = True
                details["checks"].append(check)
                details["verified"] = True
                return details
        except Exception as e:
            check["error"] = repr(e)
            check["body"] = data.decode("utf-8", "replace")[:200] if data else ""
        details["checks"].append(check)
        if i + 1 < int(attempts):
            ok_motion, body_motion = bridge_post("/motion", {"enabled": False, "source": source}, timeout=timeout)
            details["disable_ok"] = details["disable_ok"] or bool(ok_motion)
            details["last_disable_body"] = body_motion.decode("utf-8", "replace")[:200]
            time.sleep(float(poll_interval))
    return details


def stop_status_from_verification(result):
    return "STOPPED (verified)" if result.get("verified") else "STOP UNVERIFIED - CHECK ROBOT"


def hard_stop():
    _disarm_jog()
    with lock:
        p = state["proc"]
        state["running"] = False
        state["starting"] = False
        state["last"] = "STOPPING"
    # Terminating local ssh can orphan the remote episode; kill it before verified relock.
    if p and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            pass
    pkill = remote_pkill_fetch("dashboard_stop", timeout=4.0)
    result = verify_motion_disabled("dashboard_stop")
    result["pkill"] = pkill
    with lock:
        state["last"] = stop_status_from_verification(result)
    return result


def _watch(p, outfile, fout=None):
    p.wait()
    if fout is not None:
        try:
            fout.close()
        except Exception:
            pass
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
        state["running"] = False
        state["starting"] = False
        epdir = state.pop("epdir", None)
        stopped = str(state.get("last", "")).startswith("STOP")
        if not stopped:
            state["last"] = "ending: " + reason
    pkill = remote_pkill_fetch("dashboard_watch_exit", timeout=6.0)
    result = verify_motion_disabled("dashboard_postlock")
    result["pkill"] = pkill
    with lock:
        if not str(state.get("last", "")).startswith("STOP"):
            if result.get("verified"):
                state["last"] = "done: " + reason
            else:
                state["last"] = stop_status_from_verification(result)
    if epdir and os.path.isdir(epdir):
        tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40]
        try:
            os.rename(epdir, epdir + "_" + tag)
        except Exception:
            pass


def _start_remote_episode(cmd, outfile, running_label, started_msg, source, epdir=None):
    _disarm_jog()
    with lock:
        active = bool(state.get("starting")) or (
            state["running"] and state["proc"] and state["proc"].poll() is None
        )
        if active:
            return {"ok": False, "msg": "already running"}
        state["starting"] = True
        state["running"] = False
        state["last"] = "STARTING"
    fout = None
    try:
        os.makedirs(RUNDIR, exist_ok=True)
        if epdir:
            os.makedirs(epdir, exist_ok=True)
        pkill = remote_pkill_fetch(source + "_prestart", timeout=6.0)
        if not pkill.get("ok"):
            raise RuntimeError("remote prestart pkill failed: %s" % json.dumps(pkill, sort_keys=True))
        ok, body = bridge_post("/motion", {"enabled": False, "source": source + "_prelock"}, timeout=0.8)
        if not ok:
            raise RuntimeError("bridge prelock failed: %s" % body.decode("utf-8", "replace")[:200])
        fout = open(outfile, "w", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=REPO, stdout=fout, stderr=subprocess.DEVNULL)
    except Exception as e:
        if fout is not None:
            try:
                fout.close()
            except Exception:
                pass
        msg = "start failed: %r" % (e,)
        with lock:
            state["proc"] = None
            state["running"] = False
            state["starting"] = False
            state["last"] = msg
            if epdir:
                state.pop("epdir", None)
        return {"ok": False, "msg": msg}
    with lock:
        state["proc"] = p
        state["running"] = True
        state["starting"] = False
        state["last"] = running_label
        state["outfile"] = outfile
        if epdir:
            state["epdir"] = epdir
    threading.Thread(target=_watch, args=(p, outfile, fout), daemon=True).start()
    return {"ok": True, "msg": started_msg}


# operator-selectable steering for the next GO. Arc gains are the fixed
# bridge-scale stiction sweep (2026-07-04 multi-seed check: slew=1.00
# had the lowest failure/oscillation mix; default sweep 23/24 vs pulse 9/24).
steer = {"mode": "pulse"}
steer_lock = threading.Lock()
ARC_GAINS = ["--steering", "arc", "--kp", "0.30", "--kd", "0.10",
             "--slew", "1.00", "--turn-gate", "0.55"]


def build_approach_command(mode, push_steps=10):
    push_steps = max(0, min(10, int(push_steps)))
    return [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", _robot_ssh_target(),
        "python3", "/home/jetson/chasecar_onboard/chasecar_onboard_fetch.py",
        "--detector", "trt",  # local GPU eyes; remote feed stays for the dashboard view
        "--min-confidence", "0.2", "--search-scan", "26", "--lost-limit", "12",
        "--standoff-m", "0.35", "--push-steps", str(push_steps),
        "--run-dir", "/home/jetson/chasecar_onboard/runs",
    ] + (ARC_GAINS if mode == "arc" else [])


def start_approach(push_steps=10, source="dashboard"):
    stamp = int(time.time())
    outfile = os.path.join(RUNDIR, "run_%d.json" % stamp)
    epdir = os.path.join(REPO, "artifacts", "finetune_dataset", "inbox", "ep_%d" % stamp)
    with steer_lock:
        mode = steer["mode"]
    # GO = the validated hybrid loop: onboard brain on the Jetson drives via
    # localhost, consuming this server's fine-tune detection feed. The old
    # offboard controller (CTRL) carried its own weak ONNX detector and lost
    # the ball (3x lost_target on 2026-07-02); keep it only as a fallback.
    cmd = build_approach_command(mode, push_steps=push_steps)
    label = "RUNNING (%s)" % mode
    return _start_remote_episode(cmd, outfile, label, "started " + mode, source, epdir=epdir)


def start_reset():
    """Dead-reckoned undo: replay the last episode's motion tape backwards."""
    stamp = int(time.time())
    outfile = os.path.join(RUNDIR, "reset_%d.json" % stamp)
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", _robot_ssh_target(),
        "python3", "/home/jetson/chasecar_onboard/chasecar_onboard_fetch.py",
        "--reverse-log", "/home/jetson/chasecar_onboard/runs/last_motion.json",
    ]
    return _start_remote_episode(cmd, outfile, "RESETTING", "reset started", "dashboard_reset")


def build_status_payload():
    """Snapshot server perception and bridge-lock state for /status clients."""
    with lock:
        payload = {
            "running": bool(state["running"] or state.get("starting")),
            "last": state["last"],
        }
    with steer_lock:
        payload["steering"] = steer["mode"]
    with cam_lock:
        payload["det"] = cam["det"]
        payload["det_ts"] = cam["ts"]
        payload["cam_err"] = cam["err"]
        payload["target"] = cam["target"]
        payload["target_ts"] = cam["target_ts"]
        payload["target_err"] = cam["target_err"]
        cam["last_view"] = time.time()  # status pollers keep detector threads hot
    _code, data, _ct = bridge_get("/health")
    try:
        health = json.loads(data)
        payload["motion_enabled"] = health.get("motion_enabled")
    except Exception:
        pass
    return payload


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Chasecar Fetch</title>
<style>
 body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#0e0f12;color:#e8e8ea;text-align:center;-webkit-user-select:none;user-select:none;touch-action:manipulation}
 h2{margin:8px;font-size:20px}
 .wrap{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;align-items:flex-start;max-width:980px;margin:0 auto;padding:0 8px}
 .col-cam{flex:1 1 400px;max-width:560px;min-width:300px}
 .col-ctl{flex:0 1 300px;min-width:260px}
 .cam{width:100%;background:#000;border-radius:8px;display:block}
 .status{font-family:ui-monospace,monospace;font-size:12px;color:#9aa0a8;margin:6px;white-space:pre-line;min-height:32px}
 .btns{display:flex;gap:10px;justify-content:center;margin:6px 0}
 .btns button{font-size:22px;font-weight:800;border:none;border-radius:14px;padding:18px 8px;flex:1;color:#fff}
 .go{background:#147a46}.go:active{background:#0d5730}
 .stop{background:#b42318}.stop:active{background:#7a1d16}
 .reset{background:#8a6d1a}.reset:active{background:#5f4b10}
 .seglabel{font-size:11px;color:#6b7280;margin:8px 0 2px;text-transform:uppercase;letter-spacing:.06em}
 .seg{display:flex;margin:0 auto;max-width:280px;border:1px solid #2a2f3a;border-radius:12px;overflow:hidden}
 .seg button{flex:1;font-size:15px;font-weight:700;border:none;padding:12px 8px;background:#1a1d24;color:#8b93a0}
 .seg .pulse.sel{background:#3a4150;color:#fff}
 .seg .arc.sel{background:#1d9e75;color:#fff}
 .seg.locked{opacity:.45;pointer-events:none}
 .pad{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px auto 0;max-width:280px}
 .pad button{font-size:26px;font-weight:700;border:none;border-radius:12px;color:#dfe2e8;background:#23262e;
   aspect-ratio:1;touch-action:none;-webkit-touch-callout:none}
 .pad button:active,.pad button.on{background:#3a4150}
 .pad .mid{background:#151820;color:#6b7280}
 .hint{font-size:11px;color:#6b7280;margin:6px}
 @media (max-width:700px){
  .cam{max-height:36vh;object-fit:contain}
  .btns button{font-size:18px;padding:14px 6px}
  .pad{max-width:240px}.pad button{font-size:22px}
  h2{margin:4px;font-size:16px}
 }
</style></head><body>
<h2>Chasecar Fetch</h2>
<div class="wrap">
 <div class="col-cam">
  <img class="cam" id="cam" alt="camera">
  <div class="status" id="status">connecting...</div>
 </div>
 <div class="col-ctl">
  <div class="seglabel">steering (applies to next GO)</div>
  <div class="seg" id="seg">
   <button class="pulse sel" data-mode="pulse">PULSE</button>
   <button class="arc" data-mode="arc">ARC &#9889;</button>
  </div>
  <div class="btns" style="margin-top:8px">
   <button class="go" id="go">GO</button>
   <button class="reset" id="reset">RESET</button>
   <button class="stop" id="stop">STOP</button>
  </div>
  <div class="pad" id="pad">
   <button data-lx="0.55" data-az="1.2">&#8598;</button>
   <button data-lx="0.55" data-az="0">&#8593;</button>
   <button data-lx="0.55" data-az="-1.2">&#8599;</button>
   <button data-lx="0" data-az="2.3">&#8592;</button>
   <button class="mid" data-lx="0" data-az="0">&#9632;</button>
   <button data-lx="0" data-az="-2.3">&#8594;</button>
   <button data-lx="-0.55" data-az="1.2">&#8601;</button>
   <button data-lx="-0.55" data-az="0">&#8595;</button>
   <button data-lx="-0.55" data-az="-1.2">&#8600;</button>
  </div>
  <div class="hint">hold to drive &middot; release stops &middot; auto-locks when idle</div>
 </div>
</div>
<script>
 function post(p){return fetch(p,{method:'POST'}).then(function(r){return r.json();}).catch(function(e){return {error:''+e};});}
 document.getElementById('go').onclick=function(){document.getElementById('status').textContent='starting...';post('/go');};
 document.getElementById('reset').onclick=function(){document.getElementById('status').textContent='reversing last run...';post('/reset');};
 document.getElementById('stop').onclick=function(){document.getElementById('status').textContent='STOPPING...';post('/stop');};
 function setSeg(mode){Array.prototype.forEach.call(document.querySelectorAll('#seg button'),function(b){b.classList.toggle('sel',b.getAttribute('data-mode')===mode);});}
 Array.prototype.forEach.call(document.querySelectorAll('#seg button'),function(b){
  b.onclick=function(){var mode=b.getAttribute('data-mode');setSeg(mode);post('/steer?mode='+mode).then(function(r){if(!r||!r.ok){/* server rejected (mid-run): tick() resyncs */}});};
 });
 var jogTimer=null;
 function jogSend(lx,az){post('/jog?lx='+lx+'&az='+az);}
 function jogStart(btn){
  var lx=btn.getAttribute('data-lx'), az=btn.getAttribute('data-az');
  if(lx==='0'&&az==='0'){jogEnd();return;}
  jogEnd(); btn.classList.add('on');
  jogSend(lx,az); jogTimer=setInterval(function(){jogSend(lx,az);},250);
 }
 function jogEnd(){
  if(jogTimer){clearInterval(jogTimer);jogTimer=null;}
  var on=document.querySelector('.pad .on'); if(on){on.classList.remove('on');}
  post('/jog_stop');
 }
 Array.prototype.forEach.call(document.querySelectorAll('.pad button'),function(b){
  b.addEventListener('pointerdown',function(e){e.preventDefault();jogStart(b);});
  b.addEventListener('pointerup',jogEnd);
  b.addEventListener('pointerleave',function(){if(jogTimer){jogEnd();}});
  b.addEventListener('pointercancel',jogEnd);
  b.addEventListener('contextmenu',function(e){e.preventDefault();});
 });
 function tick(){
  document.getElementById('cam').src='/camera.jpg?t='+Date.now();
   fetch('/status').then(function(r){return r.json();}).then(function(s){
    var det = s.det ? ('ball: conf '+s.det.confidence+'  z='+s.det.z_m+'m  err='+Number(s.det.center_error).toFixed(2)) : ('ball: '+(s.cam_err||'not detected'));
    var status = document.getElementById('status');
    status.textContent='approach: '+s.last+'   |   motion='+s.motion_enabled+'\\n'+det;
    status.style.color = (s.last && s.last.indexOf('STOP UNVERIFIED') === 0) ? '#ff5c5c' : '#9aa0a8';
    if(s.steering){setSeg(s.steering);}
    document.getElementById('seg').classList.toggle('locked', !!s.running);
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
            self._send(200, json.dumps(build_status_payload()), "application/json")
            return
        self._send(200, DASH)

    def do_POST(self):
        if self.path.startswith("/go-acquire-only"):
            self._send(200, json.dumps(start_approach(push_steps=0, source="unattended_acquire")),
                       "application/json")
            return
        if self.path.startswith("/go"):
            self._send(200, json.dumps(start_approach()), "application/json")
            return
        if self.path.startswith("/reset"):
            self._send(200, json.dumps(start_reset()), "application/json")
            return
        if self.path.startswith("/steer"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            mode = (qs.get("mode", [""])[0] or "").lower()
            if mode not in ("pulse", "arc"):
                self._send(400, json.dumps({"ok": False, "msg": "mode must be pulse|arc"}), "application/json")
                return
            with lock:
                busy = bool(state["running"] or state.get("starting"))
            if busy:
                self._send(200, json.dumps({"ok": False, "msg": "cannot change mid-run"}), "application/json")
                return
            with steer_lock:
                steer["mode"] = mode
            self._send(200, json.dumps({"ok": True, "steering": mode}), "application/json")
            return
        if self.path.startswith("/jog_stop"):
            with jog_lock:
                jog["last_cmd"] = time.time()  # keep armed briefly; idle watchdog relocks
            ok, body = bridge_post("/stop", {"source": "dashboard_jog"})
            self._send(200, json.dumps({"ok": bool(ok),
                                        "msg": "" if ok else body.decode("utf-8", "replace")[:200]}),
                       "application/json")
            return
        if self.path.startswith("/jog"):
            with lock:
                busy = bool(state["running"] or state.get("starting"))
            if busy:
                self._send(200, json.dumps({"ok": False, "msg": "episode running"}), "application/json")
                return
            try:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                lx = max(-0.6, min(0.6, float(qs.get("lx", ["0"])[0])))
                az = max(-2.5, min(2.5, float(qs.get("az", ["0"])[0])))
            except Exception:
                self._send(400, json.dumps({"ok": False, "msg": "bad params"}), "application/json")
                return
            with jog_lock:
                need_arm = not jog["armed"]
                jog["armed"] = True
                jog["last_cmd"] = time.time()
            if need_arm:
                ok, body = bridge_post("/motion", {"enabled": True, "source": "dashboard_jog"})
                if not ok:
                    with jog_lock:
                        jog["armed"] = False
                    self._send(200, json.dumps({"ok": False,
                                                "msg": body.decode("utf-8", "replace")[:200]}),
                               "application/json")
                    return
            ok, body = bridge_post("/cmd_vel", {"linear_x": lx, "angular_z": az,
                                                "duration_s": 0.45, "source": "dashboard_jog"})
            self._send(200, json.dumps({"ok": bool(ok),
                                        "msg": "" if ok else body.decode("utf-8", "replace")[:200]}),
                       "application/json")
            return
        if self.path.startswith("/stop"):
            result = hard_stop()
            self._send(200, json.dumps({"ok": bool(result.get("verified")),
                                        "verified": bool(result.get("verified")),
                                        "msg": stop_status_from_verification(result),
                                        "details": result}), "application/json")
            return
        self._send(404, "not found")

    def log_message(self, *a):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    threading.Thread(target=detector_loop, daemon=True).start()
    threading.Thread(target=jog_watchdog, daemon=True).start()
    print("control server on 0.0.0.0:8791 (Tailscale http://100.112.221.6:8791/)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8791), Handler).serve_forever()
