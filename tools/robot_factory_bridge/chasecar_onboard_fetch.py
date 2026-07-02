#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Onboard mono fetch brain for the JetBot Mini (runs ON the Jetson, Python 3.6).

Stage-2 port of the offboard visual fetch controller: the whole control loop
lives on the robot (localhost camera -> HSV white-ball detector -> the same
decide_fetch_action policy -> localhost cmd_vel), so no Wi-Fi sits inside the
loop. The laptop becomes a viewer.

Deliberately self-contained and Python 3.6 compatible (JetPack 4.4): stdlib +
numpy + cv2 only, no repo imports, no 3.7+ syntax. The decision policy is a
faithful port of decide_fetch_action from chasecar_bridge_visual_fetch_controller
(same guards, same constants); keep them in sync by hand.

Motion architecture (the smoothness fix Wi-Fi never allowed): a 10 Hz setpoint
REFRESHER thread keeps the bridge deadman fed while the ~1 Hz perception loop
updates the setpoint. Setpoints carry an expiry, so a stalled perception loop
coasts to zero within max_setpoint_age_s and the hardware deadman (0.5 s)
backstops everything including SIGKILL.

Usage (on the Jetson):
  python3 chasecar_onboard_fetch.py --dry-run          # perception only, no motion
  python3 chasecar_onboard_fetch.py --push-steps 10    # full fetch episode
"""
from __future__ import print_function

import argparse
import io
import json
import math
import os
import threading
import time

try:
    from urllib.request import Request, urlopen  # py3
except ImportError:  # pragma: no cover
    from urllib2 import Request, urlopen  # type: ignore

import cv2
import numpy as np

ACT_TURN = "turn"
ACT_FORWARD = "forward"
ACT_HOLD = "hold"
ACT_STOP = "stop"

# Real-bench mono calibration (equiv_diameter_px), from
# artifacts/session/mono_distance_calibration_bench01/calibration_summary.json
K_PX_M_DEFAULT = 9.621


# ----------------------------- bridge client (localhost) -----------------------------

class Bridge(object):
    def __init__(self, base_url, timeout_s=2.0):
        self.base = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _req(self, method, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(self.base + path, data=data)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        req.get_method = lambda: method
        resp = urlopen(req, timeout=self.timeout_s)
        return resp.read()

    def health(self):
        return json.loads(self._req("GET", "/health").decode("utf-8"))

    def camera_jpeg(self):
        return self._req("GET", "/camera.jpg")

    def set_motion(self, enabled, source):
        return self._req("POST", "/motion", {"enabled": bool(enabled), "source": source})

    def cmd_vel(self, linear_x, angular_z, duration_s, source):
        return self._req("POST", "/cmd_vel", {"linear_x": float(linear_x), "angular_z": float(angular_z),
                                              "duration_s": float(duration_s), "source": source})

    def stop(self, source):
        return self._req("POST", "/stop", {"source": source})


# ----------------------------- perception: white-ball HSV -----------------------------

def detect_ball(bgr, hsv_lo, hsv_hi, min_area_px, min_circularity, floor_zone_frac=0.45):
    """Largest round low-saturation/bright blob ON THE FLOOR -> detection dict or None.

    floor_zone_frac: reject any blob whose bbox bottom is above h*frac — the ball
    sits on the floor, so anything high in the frame (lamps, LEDs, reflections)
    physically cannot be it. Caught live: in a dark room a wall LED scored 0.66.

    Output convention matches the offboard stack exactly:
    equiv_diameter_px = sqrt(w*h); center_error = (cx - W/2)/(W/2).
    """
    h, w = bgr.shape[:2]
    floor_y_min = float(h) * float(floor_zone_frac)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lo, dtype=np.uint8), np.array(hsv_hi, dtype=np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    try:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    except ValueError:  # older cv2 returns 3-tuple
        _, contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_score = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area_px:
            continue
        peri = cv2.arcLength(c, True)
        circ = (4.0 * math.pi * area) / (peri * peri + 1e-9)
        if circ < min_circularity:
            continue
        bx, by, bbw, bbh = cv2.boundingRect(c)
        if (by + bbh) < floor_y_min:
            continue  # above the floor zone: cannot be a ball on the ground
        (_cx, _cy), r = cv2.minEnclosingCircle(c)
        fill = area / (math.pi * r * r + 1e-9)
        score = math.sqrt(max(circ, 0.0) * max(min(fill, 1.0), 0.0))
        if score * area > best_score:
            best_score = score * area
            x, y, bw, bh = cv2.boundingRect(c)
            best = {
                "detected": True,
                "bbox_xyxy": [float(x), float(y), float(x + bw), float(y + bh)],
                "equiv_diameter_px": round(math.sqrt(float(bw) * float(bh)), 3),
                "center_error": round(((x + bw / 2.0) - (w / 2.0)) / (w / 2.0), 6),
                "confidence": round(min(max(score, 0.0), 1.0), 4),
                "area_px": float(area),
            }
    return best


# ----------------------------- policy (port of decide_fetch_action) -----------------------------

def default_config(**over):
    cfg = {
        "k_px_m": K_PX_M_DEFAULT,
        "standoff_m": 0.35,
        "center_deadband": 0.12,
        "forward_budget": 40,
        "lost_limit": 4,
        "min_confidence": 0.35,     # blob-quality floor (color detector scores ~0.6-0.9 on a clean ball)
        "max_steps": 140,
        "turn_angular_z": 2.3,
        "approach_linear_x": 0.55,  # above measured motor stiction (~0.3 motor cmd)
        "size_key": "equiv_diameter_px",
    }
    cfg.update(over)
    return cfg


def decide_fetch_action(obs, state, cfg):
    """Pure decision. Faithful port of the offboard controller's policy."""
    step = int(state.get("step", 0))
    if step >= int(cfg["max_steps"]):
        return {"action": ACT_STOP, "reason": "max_steps_reached"}

    detected = bool(obs.get("detected"))
    confidence = float(obs.get("confidence", 0.0) or 0.0)
    size_px = float(obs.get(cfg["size_key"], 0.0) or 0.0)
    usable = detected and confidence >= float(cfg["min_confidence"]) and size_px > 0.0
    if not usable:
        lost = int(state.get("lost_count", 0)) + 1
        if lost > int(cfg["lost_limit"]):
            return {"action": ACT_STOP, "reason": "lost_target", "lost_count": lost}
        reason = "target_not_detected" if not detected else "low_confidence"
        return {"action": ACT_HOLD, "reason": reason, "lost_count": lost}

    z_m = float(cfg["k_px_m"]) / size_px
    if z_m <= float(cfg["standoff_m"]):
        return {"action": ACT_STOP, "reason": "standoff_reached", "z_m": round(z_m, 4)}

    ce = float(obs.get("center_error", 0.0) or 0.0)
    if abs(ce) > float(cfg["center_deadband"]):
        az = -float(cfg["turn_angular_z"]) if ce > 0 else float(cfg["turn_angular_z"])
        return {"action": ACT_TURN, "reason": "center_target", "angular_z": az, "z_m": round(z_m, 4)}

    if int(state.get("forward_steps", 0)) >= int(cfg["forward_budget"]):
        return {"action": ACT_STOP, "reason": "forward_budget_exhausted", "z_m": round(z_m, 4)}
    return {"action": ACT_FORWARD, "reason": "approach", "linear_x": float(cfg["approach_linear_x"]), "z_m": round(z_m, 4)}


# ----------------------------- 10 Hz setpoint refresher -----------------------------

class Refresher(object):
    """Keeps the bridge deadman fed with the current setpoint at ~10 Hz.

    Setpoints expire: if the perception loop stalls, the refresher publishes
    zeros within max_age_s and the 0.5 s hardware deadman backstops the rest.
    """

    def __init__(self, bridge, hz=10.0, max_age_s=1.5):
        self.bridge = bridge
        self.period = 1.0 / hz
        self.max_age = max_age_s
        self._lock = threading.Lock()
        self._sp = (0.0, 0.0, 0.0)  # linear_x, angular_z, set_time
        self._run = True
        self._t = threading.Thread(target=self._loop)
        self._t.daemon = True

    def start(self):
        self._t.start()

    def set(self, linear_x, angular_z, hold_s=None):
        with self._lock:
            self._sp = (float(linear_x), float(angular_z), time.time())
            self._hold = float(hold_s) if hold_s else None

    def zero(self):
        self.set(0.0, 0.0)

    def _loop(self):
        while self._run:
            with self._lock:
                lx, az, ts = self._sp
                hold = getattr(self, "_hold", None)
            age = time.time() - ts
            limit = hold if hold is not None else self.max_age
            if age > limit:
                lx, az = 0.0, 0.0
            try:
                if abs(lx) > 1e-6 or abs(az) > 1e-6:
                    self.bridge.cmd_vel(lx, az, 0.4, "onboard:refresh")
                # publishing zeros is unnecessary: deadman zeroes 0.5 s after the last cmd
            except Exception:
                pass  # localhost hiccup: deadman covers the gap
            time.sleep(self.period)

    def stop(self):
        self._run = False


# ----------------------------- episode runner -----------------------------

def jpeg_to_bgr(buf):
    arr = np.frombuffer(buf, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def run(args):
    bridge = Bridge(args.base_url)
    cfg = default_config(standoff_m=args.standoff_m, center_deadband=args.center_deadband,
                         forward_budget=args.forward_budget, lost_limit=args.lost_limit,
                         max_steps=args.max_steps, turn_angular_z=args.turn_angular_z,
                         approach_linear_x=args.approach_linear_x, min_confidence=args.min_confidence,
                         k_px_m=args.k_px_m)
    hsv_lo = tuple(int(v) for v in args.hsv_lo.split(","))
    hsv_hi = tuple(int(v) for v in args.hsv_hi.split(","))

    run_dir = args.run_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
    if not os.path.isdir(run_dir):
        os.makedirs(run_dir)
    trace_path = os.path.join(run_dir, "onboard_%d.jsonl" % int(time.time()))
    trace = io.open(trace_path, "w", encoding="utf-8")

    summary = {"type": "onboard_fetch_episode", "config": cfg, "dry_run": bool(args.dry_run),
               "trace": trace_path, "issues": [], "counts": {}, "phase_log": []}

    h = bridge.health()
    if not (h.get("ok") and h.get("motion_enabled") is False):
        summary["stop_reason"] = "preflight_failed"
        print(json.dumps(summary))
        return 1

    refresher = Refresher(bridge)
    state = {"step": 0, "forward_steps": 0, "lost_count": 0}
    counts = {"forward": 0, "turn": 0, "hold": 0, "detected": 0}
    stop_reason = "unset"
    t_start = time.time()
    try:
        if not args.dry_run:
            bridge.set_motion(True, "onboard:arm")
            refresher.start()

        # --- acquire: rotate until the ball is in frame ---
        scans = 0
        while scans < args.search_scan:
            det = detect_ball(jpeg_to_bgr(bridge.camera_jpeg()), hsv_lo, hsv_hi,
                              args.min_area_px, args.min_circularity,
                              floor_zone_frac=args.floor_zone_frac)
            if det and det["confidence"] >= cfg["min_confidence"]:
                break
            if args.dry_run:
                break
            refresher.set(0.0, cfg["turn_angular_z"], hold_s=0.14)
            scans += 1
            time.sleep(0.55)
        summary["scan_steps"] = scans

        # --- approach loop ---
        while True:
            t_loop = time.time()
            try:
                det = detect_ball(jpeg_to_bgr(bridge.camera_jpeg()), hsv_lo, hsv_hi,
                                  args.min_area_px, args.min_circularity,
                              floor_zone_frac=args.floor_zone_frac)
            except Exception as e:
                det = None
                summary["issues"].append("observe_error:%r" % (e,))
            obs = det if det else {"detected": False}
            d = decide_fetch_action(obs, state, cfg)
            state["step"] += 1
            state["lost_count"] = d.get("lost_count", 0 if obs.get("detected") else state["lost_count"])
            if obs.get("detected"):
                counts["detected"] += 1
            counts[d["action"]] = counts.get(d["action"], 0) + 1
            trace.write(json.dumps({"t": round(time.time() - t_start, 3), "obs": obs, "decision": d,
                                    "state": dict(state)}) + "\n")
            trace.flush()

            if args.dry_run:
                print(json.dumps({"dry_run_obs": obs, "decision": d}))
                if state["step"] >= args.dry_run_frames:
                    stop_reason = "dry_run_complete"
                    break
                time.sleep(0.3)
                continue

            if d["action"] == ACT_STOP:
                refresher.zero()
                stop_reason = d["reason"]
                break
            if d["action"] == ACT_TURN:
                ce = abs(float(obs.get("center_error") or 0.0))
                turn_dur = max(0.08, min(0.16, 0.35 * ce))
                refresher.set(0.0, d["angular_z"], hold_s=turn_dur)
                time.sleep(turn_dur + 0.30)  # settle + let a fresh frame land (local, fast)
            elif d["action"] == ACT_FORWARD:
                refresher.set(d["linear_x"], 0.0)  # rolls continuously; refresher feeds deadman
                state["forward_steps"] += 1
            elif d["action"] == ACT_HOLD:
                if state.get("lost_count", 0) > 1:
                    refresher.zero()
            # pace the perception loop to the camera's ~1.2 fps cache
            dt = time.time() - t_loop
            if dt < 0.35:
                time.sleep(0.35 - dt)

        # --- bounded contact push ---
        if stop_reason == "standoff_reached" and args.push_steps > 0 and not args.dry_run:
            summary["push"] = {"requested": args.push_steps}
            for _i in range(args.push_steps):
                refresher.set(args.push_linear_x, 0.0)
                time.sleep(0.20)
            refresher.zero()
            summary["push"]["executed"] = args.push_steps
            stop_reason = "standoff_then_pushed"
    except Exception as e:
        stop_reason = "exception:%r" % (e,)
        summary["issues"].append(stop_reason)
    finally:
        refresher.stop()
        if not args.dry_run:
            for _i in range(5):
                try:
                    bridge.stop("onboard:final_stop")
                    bridge.set_motion(False, "onboard:final_relock")
                    break
                except Exception:
                    time.sleep(0.4)
    trace.close()

    summary["stop_reason"] = stop_reason
    summary["counts"] = counts
    summary["duration_s"] = round(time.time() - t_start, 1)
    try:
        hf = bridge.health()
        summary["final_safe"] = (hf.get("motion_enabled") is False
                                 and abs(float(hf.get("left_motor") or 0)) < 1e-6
                                 and abs(float(hf.get("right_motor") or 0)) < 1e-6)
    except Exception:
        summary["final_safe"] = False
    print(json.dumps(summary))
    return 0 if summary.get("final_safe") else 1


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8765")
    p.add_argument("--k-px-m", type=float, default=K_PX_M_DEFAULT)
    p.add_argument("--standoff-m", type=float, default=0.35)
    p.add_argument("--center-deadband", type=float, default=0.12)
    p.add_argument("--forward-budget", type=int, default=40)
    p.add_argument("--lost-limit", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=140)
    p.add_argument("--turn-angular-z", type=float, default=2.3)
    p.add_argument("--approach-linear-x", type=float, default=0.55)
    p.add_argument("--min-confidence", type=float, default=0.35)
    p.add_argument("--push-steps", type=int, default=0)
    p.add_argument("--push-linear-x", type=float, default=0.55)
    p.add_argument("--search-scan", type=int, default=0)
    # white golf ball on a dark floor: low saturation + high value
    p.add_argument("--hsv-lo", default="0,0,150")
    p.add_argument("--hsv-hi", default="179,70,255")
    p.add_argument("--min-area-px", type=float, default=12.0)
    p.add_argument("--min-circularity", type=float, default=0.45)
    p.add_argument("--floor-zone-frac", type=float, default=0.45,
                   help="reject blobs whose bbox bottom is above h*frac (ball is on the floor)")
    p.add_argument("--dry-run", action="store_true", help="perception only; never moves")
    p.add_argument("--dry-run-frames", type=int, default=8)
    p.add_argument("--run-dir", default="")
    return p


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
