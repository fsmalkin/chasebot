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
import ctypes
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


def clamp(v, lo, hi):
    return max(float(lo), min(float(hi), float(v)))


def variance(xs):
    if not xs:
        return 0.0
    mean = sum(xs) / float(len(xs))
    return sum((x - mean) * (x - mean) for x in xs) / float(len(xs))


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


# ----------------------------- temporal ball tracker -----------------------------

class BallTracker(object):
    """Tiny alpha-beta tracker over center error and apparent size.

    The detector can arrive at uneven cadence (remote YOLO ~1 Hz, local TRT
    faster).  The tracker keeps velocity terms in normalized-error/s and px/s,
    clamps odd dt values, and damps stale velocity while coasting.
    """

    def __init__(self, alpha=0.45, beta=0.12, min_dt=0.03, max_dt=0.35):
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.min_dt = float(min_dt)
        self.max_dt = float(max_dt)
        self._ready = False
        self._x = 0.0
        self._vx = 0.0
        self._s = 0.0
        self._vs = 0.0
        self._last_state_t = None
        self._last_det_t = None
        self._coasting = False

    @property
    def fresh_s(self):
        if self._last_det_t is None:
            return 999.0
        ref = self._last_state_t if self._last_state_t is not None else time.time()
        return max(0.0, float(ref) - float(self._last_det_t))

    def _dt(self, t):
        if self._last_state_t is None:
            return self.min_dt
        return clamp(float(t) - float(self._last_state_t), self.min_dt, self.max_dt)

    def _advance(self, t):
        if not self._ready:
            return
        dt = self._dt(t)
        self._x += self._vx * dt
        self._s = max(1e-3, self._s + self._vs * dt)
        self._last_state_t = float(t)
        if self._last_det_t is not None and (float(t) - float(self._last_det_t)) > self.max_dt:
            self._vx *= 0.85
            self._vs *= 0.85

    def update(self, obs, t):
        x = float(obs.get("center_error") or 0.0)
        s = float(obs.get("equiv_diameter_px") or 0.0)
        if s <= 0.0:
            return self.predict(t)
        if not self._ready:
            self._x = x
            self._vx = 0.0
            self._s = s
            self._vs = 0.0
            self._ready = True
            self._last_state_t = float(t)
            self._last_det_t = float(t)
            self._coasting = False
            return self.estimate()
        dt = self._dt(t)
        px = self._x + self._vx * dt
        ps = max(1e-3, self._s + self._vs * dt)
        rx = x - px
        rs = s - ps
        self._x = px + self.alpha * rx
        self._s = max(1e-3, ps + self.alpha * rs)
        self._vx += (self.beta * rx) / dt
        self._vs += (self.beta * rs) / dt
        self._last_state_t = float(t)
        self._last_det_t = float(t)
        self._coasting = False
        return self.estimate()

    def predict(self, t):
        if not self._ready:
            return None
        self._advance(t)
        self._coasting = True
        return self.estimate()

    def estimate(self):
        if not self._ready:
            return None
        return {
            "center_error": float(self._x),
            "center_rate": float(self._vx),
            "equiv_diameter_px": float(self._s),
            "size_rate": float(self._vs),
            "coasting": bool(self._coasting),
            "fresh_s": float(self.fresh_s),
        }


def detection_usable(obs, cfg):
    detected = bool(obs.get("detected"))
    confidence = float(obs.get("confidence", 0.0) or 0.0)
    size_px = float(obs.get(cfg["size_key"], 0.0) or 0.0)
    return detected and confidence >= float(cfg["min_confidence"]) and size_px > 0.0


def slew_value(prev, target, max_rate, dt):
    dt = max(0.01, float(dt))
    limit = abs(float(max_rate)) * dt
    delta = clamp(float(target) - float(prev), -limit, limit)
    return float(prev) + delta


def compute_arc_drive_command(err, err_rate, cfg, kp, kd, slew, dt, prev_lx, prev_az):
    turn_scale = float(cfg["turn_angular_z"])
    angular_target = -(float(kp) * float(err) + float(kd) * float(err_rate)) * turn_scale
    angular_target = clamp(angular_target, -2.5, 2.5)
    if abs(float(err)) < (float(cfg["center_deadband"]) / 2.0):
        angular_target = 0.0
    linear_target = float(cfg["approach_linear_x"]) * max(0.35, 1.0 - abs(float(err)))
    linear = slew_value(prev_lx, linear_target, slew, dt)
    angular = slew_value(prev_az, angular_target, slew, dt)
    return linear, angular, linear_target, angular_target


def decide_arc_fetch_action(obs, state, cfg, tracker, args, t_now, prev_lx, prev_az, prev_cmd_t):
    if detection_usable(obs, cfg):
        est = tracker.update(obs, t_now)
    else:
        est = tracker.predict(t_now)
    if est is None or float(est.get("fresh_s", 999.0)) > float(args.coast_s):
        d = decide_fetch_action(obs, state, cfg)
        return d, obs, prev_lx, prev_az, prev_cmd_t

    servo_obs = dict(obs)
    servo_obs["detected"] = True
    servo_obs[cfg["size_key"]] = float(est["equiv_diameter_px"])
    servo_obs["equiv_diameter_px"] = float(est["equiv_diameter_px"])
    servo_obs["center_error"] = float(est["center_error"])
    servo_obs["center_rate"] = float(est["center_rate"])
    servo_obs["confidence"] = max(float(obs.get("confidence", 0.0) or 0.0), float(cfg["min_confidence"]))
    servo_obs["coasting"] = bool(est["coasting"])
    servo_obs["fresh_s"] = round(float(est["fresh_s"]), 3)

    step = int(state.get("step", 0))
    if step >= int(cfg["max_steps"]):
        return {"action": ACT_STOP, "reason": "max_steps_reached"}, servo_obs, prev_lx, prev_az, prev_cmd_t
    size_px = float(servo_obs.get(cfg["size_key"], 0.0) or 0.0)
    if size_px <= 0.0:
        return decide_fetch_action(obs, state, cfg), obs, prev_lx, prev_az, prev_cmd_t
    z_m = float(cfg["k_px_m"]) / size_px
    if z_m <= float(cfg["standoff_m"]):
        return {"action": ACT_STOP, "reason": "standoff_reached", "z_m": round(z_m, 4)}, servo_obs, prev_lx, prev_az, prev_cmd_t
    if int(state.get("forward_steps", 0)) >= int(cfg["forward_budget"]):
        return {"action": ACT_STOP, "reason": "forward_budget_exhausted", "z_m": round(z_m, 4)}, servo_obs, prev_lx, prev_az, prev_cmd_t

    dt = max(0.01, float(t_now) - float(prev_cmd_t))
    lx, az, lx_target, az_target = compute_arc_drive_command(
        servo_obs["center_error"], servo_obs.get("center_rate", 0.0), cfg,
        args.kp, args.kd, args.slew, dt, prev_lx, prev_az)
    d = {"action": ACT_FORWARD, "reason": "arc_approach", "linear_x": lx, "angular_z": az,
         "target_linear_x": round(lx_target, 4), "target_angular_z": round(az_target, 4),
         "z_m": round(z_m, 4), "coasting": bool(est["coasting"]),
         "center_error": round(float(servo_obs["center_error"]), 5)}
    return d, servo_obs, lx, az, float(t_now)


# ----------------------------- remote detector (hybrid mode) -----------------------------

class RemoteDetector(object):
    """Consume the laptop's YOLO detection as a compact advisory feed.

    The laptop control server runs YOLO continuously and serves the latest
    detection at /status (~200 bytes). Only this tiny signal crosses Wi-Fi;
    frames and motor commands stay on the robot. A dropout or stale feed reads
    as a miss -> the policy's lost-target guard stops safely.
    """

    def __init__(self, url, timeout_s=2.0, stale_after_s=3.0):
        self.url = url
        self.timeout_s = timeout_s
        self.stale_after_s = stale_after_s
        self._last_ts = None
        self._last_change = 0.0

    def get_obs(self):
        """Rate-aware: the upstream YOLO runs ~1 Hz while we poll faster. A miss
        only counts when the upstream frame is FRESH (det_ts advanced); between
        updates we report no_new_data so the executor holds course instead of
        ticking the lost counter 3x per real missed frame."""
        try:
            raw = urlopen(Request(self.url), timeout=self.timeout_s).read()
            s = json.loads(raw.decode("utf-8"))
        except Exception:
            s = None
        now = time.time()
        if s is not None:
            ts = s.get("det_ts")
            if ts is not None and ts != self._last_ts:
                self._last_ts = ts
                self._last_change = now
                det = s.get("det")
                if det:
                    return {
                        "detected": True,
                        "equiv_diameter_px": float(det.get("equiv_px") or 0.0),
                        "center_error": float(det.get("center_error") or 0.0),
                        "confidence": float(det.get("confidence") or 0.0),
                        "source": "remote_yolo",
                    }
                return {"detected": False, "source": "remote_fresh_miss"}
        if self._last_change and (now - self._last_change) > self.stale_after_s:
            return {"detected": False, "source": "remote_stale"}  # upstream dead: real miss
        return {"detected": False, "no_new_data": True, "source": "remote_no_new"}


# ----------------------------- onboard TensorRT detector (local GPU) -----------------------------

class TrtDetector(object):
    """Run the golf-ball fine-tune engine on the Nano's own GPU (TRT 7.1).

    No pycuda on this JetPack: device buffers via ctypes on libcudart. Engine
    is the yolov8n single-class export (input 1x3x320x320 fp32, output
    1x5x2100: cx,cy,w,h,conf in input-pixel scale). 13.5 ms/frame measured
    with trtexec 2026-07-02; local frames make feed lag ~0.1 s, so the
    ego-motion staleness that broke remote-fed runs mostly vanishes.
    """

    H2D, D2H = 1, 2

    def __init__(self, engine_path, conf_floor=0.20, floor_zone_frac=0.45):
        import tensorrt as trt
        self.conf_floor = float(conf_floor)
        self.floor_zone_frac = float(floor_zone_frac)
        self.rt = None
        for name in ("libcudart.so.10.2", "libcudart.so.10.0", "libcudart.so"):
            try:
                self.rt = ctypes.CDLL(name)
                break
            except OSError:
                continue
        if self.rt is None:
            raise RuntimeError("libcudart not found")
        logger = trt.Logger(trt.Logger.WARNING)
        with open(engine_path, "rb") as f:
            self.engine = trt.Runtime(logger).deserialize_cuda_engine(f.read())
        if self.engine is None:
            raise RuntimeError("engine deserialize failed: %s" % engine_path)
        self.ctx = self.engine.create_execution_context()
        self.in_shape = tuple(self.engine.get_binding_shape(0))   # (1,3,320,320)
        self.out_shape = tuple(self.engine.get_binding_shape(1))  # (1,5,2100)
        self.side = int(self.in_shape[2])
        self.h_in = np.empty(self.in_shape, dtype=np.float32)
        self.h_out = np.empty(self.out_shape, dtype=np.float32)
        self.d_in = self._malloc(self.h_in.nbytes)
        self.d_out = self._malloc(self.h_out.nbytes)

    def _malloc(self, nbytes):
        ptr = ctypes.c_void_p()
        if self.rt.cudaMalloc(ctypes.byref(ptr), ctypes.c_size_t(nbytes)) != 0:
            raise RuntimeError("cudaMalloc failed (%d bytes)" % nbytes)
        return ptr

    def _memcpy(self, dst, src, nbytes, kind):
        if self.rt.cudaMemcpy(dst, src, ctypes.c_size_t(nbytes), ctypes.c_int(kind)) != 0:
            raise RuntimeError("cudaMemcpy failed")

    def infer(self, bgr):
        """BGR frame -> best detection dict (offboard obs convention) or None."""
        h0, w0 = bgr.shape[:2]
        s = self.side
        scale = min(float(s) / w0, float(s) / h0)
        nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
        resized = bgr if (nw, nh) == (w0, h0) else cv2.resize(bgr, (nw, nh))
        canvas = np.full((s, s, 3), 114, dtype=np.uint8)
        px, py = (s - nw) // 2, (s - nh) // 2
        canvas[py:py + nh, px:px + nw] = resized
        chw = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        self.h_in[0] = chw
        self._memcpy(self.d_in, self.h_in.ctypes.data, self.h_in.nbytes, self.H2D)
        if not self.ctx.execute_v2([int(self.d_in.value), int(self.d_out.value)]):
            raise RuntimeError("execute_v2 failed")
        self._memcpy(self.h_out.ctypes.data, self.d_out, self.h_out.nbytes, self.D2H)
        out = self.h_out[0]  # (5, 2100)
        i = int(np.argmax(out[4]))
        conf = float(out[4, i])
        if conf < self.conf_floor:
            return None
        cx = (float(out[0, i]) - px) / scale
        cy = (float(out[1, i]) - py) / scale
        bw = float(out[2, i]) / scale
        bh = float(out[3, i]) / scale
        if (cy + bh / 2.0) < h0 * self.floor_zone_frac:
            return None  # above the floor zone: lamps/reflections, not a floor ball
        return {
            "detected": True,
            "bbox_xyxy": [cx - bw / 2.0, cy - bh / 2.0, cx + bw / 2.0, cy + bh / 2.0],
            "equiv_diameter_px": round(math.sqrt(max(bw, 1e-6) * max(bh, 1e-6)), 3),
            "center_error": round((cx - w0 / 2.0) / (w0 / 2.0), 6),
            "confidence": round(conf, 4),
            "source": "onboard_trt",
        }


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
        self.log = []  # (t, linear_x, angular_z, hold_s) — the episode's motion tape

    def start(self):
        self._t.start()

    def set(self, linear_x, angular_z, hold_s=None):
        with self._lock:
            self._sp = (float(linear_x), float(angular_z), time.time())
            self._hold = float(hold_s) if hold_s else None
            self.log.append((self._sp[2], self._sp[0], self._sp[1],
                             self._hold if self._hold is not None else 0.0))

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
    remote = RemoteDetector(args.remote_det_url) if args.detector == "remote" else None
    trt_det = None
    if args.detector == "trt":
        trt_det = TrtDetector(args.trt_engine, conf_floor=args.trt_conf_floor,
                              floor_zone_frac=args.floor_zone_frac)

    def observe():
        if remote is not None:
            return remote.get_obs()
        frame = jpeg_to_bgr(bridge.camera_jpeg())
        if trt_det is not None:
            det = trt_det.infer(frame)
        else:
            det = detect_ball(frame, hsv_lo, hsv_hi,
                              args.min_area_px, args.min_circularity,
                              floor_zone_frac=args.floor_zone_frac)
        return det if det else {"detected": False}

    run_dir = args.run_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
    if not os.path.isdir(run_dir):
        os.makedirs(run_dir)
    trace_path = os.path.join(run_dir, "onboard_%d.jsonl" % int(time.time()))
    trace = io.open(trace_path, "w", encoding="utf-8")

    summary = {"type": "onboard_fetch_episode", "config": cfg, "dry_run": bool(args.dry_run),
               "steering": args.steering,
               "trace": trace_path, "issues": [], "counts": {}, "phase_log": []}

    h = bridge.health()
    if not (h.get("ok") and h.get("motion_enabled") is False):
        summary["stop_reason"] = "preflight_failed"
        print(json.dumps(summary))
        return 1

    refresher = Refresher(bridge)
    state = {"step": 0, "forward_steps": 0, "lost_count": 0}
    counts = {"forward": 0, "turn": 0, "hold": 0, "detected": 0}
    tracker = BallTracker()
    arc_lx = 0.0
    arc_az = 0.0
    arc_cmd_t = time.time()
    stop_reason = "unset"
    t_start = time.time()
    try:
        if not args.dry_run:
            bridge.set_motion(True, "onboard:arm")
            refresher.start()

        # --- acquire: rotate until the ball is in frame ---
        scans = 0
        scan_hits = 0
        discard_next = False  # first fresh verdict after a turn can predate the turn
        while scans < args.search_scan:
            # wait for a FRESH upstream verdict at this heading (upstream runs
            # ~1 Hz; a fixed pause can rotate past the ball unevaluated)
            det = {"detected": False}
            t_wait = time.time()
            while time.time() - t_wait < 2.0:
                det = observe()
                if not det.get("no_new_data"):
                    if discard_next:
                        # verdict is for a frame captured before/during the turn
                        # (feed pipeline lags ~0.5-1s); judge this heading on the
                        # NEXT fresh frame. Caught live 2026-07-02: scan matched a
                        # stale hit, held at the wrong heading, and spun past.
                        discard_next = False
                        det = {"detected": False, "no_new_data": True}
                        continue
                    break
                time.sleep(0.12)
            if det.get("detected") and det.get("confidence", 0.0) >= cfg["min_confidence"]:
                scan_hits += 1
                if scan_hits >= 2:  # debounce: one flickery frame must not end the search
                    break
                time.sleep(0.4)  # hold still, confirm on the next fresh frame
                continue
            scan_hits = 0
            if args.dry_run:
                break
            refresher.set(0.0, cfg["turn_angular_z"], hold_s=0.14)
            scans += 1
            time.sleep(0.55)
            discard_next = True
        summary["scan_steps"] = scans

        # --- approach loop ---
        discard_after_turn = False
        while True:
            t_loop = time.time()
            try:
                obs = observe()
            except Exception as e:
                obs = {"detected": False}
                summary["issues"].append("observe_error:%r" % (e,))
            if obs.get("no_new_data") and not args.dry_run and args.steering != "arc":
                # upstream hasn't produced a new frame yet: hold course (the
                # refresher's max-age auto-coasts to zero if this persists)
                time.sleep(0.15)
                continue
            if discard_after_turn and not args.dry_run and args.steering != "arc":
                # first fresh verdict after a turn can describe a pre-turn frame
                # (feed lag ~0.5-1s): acting on it double-corrects and sweeps the
                # ball across/out of frame (trace onboard_1652156968: err +0.94 ->
                # -0.97 -> lost). Judge the new heading on the NEXT fresh frame.
                discard_after_turn = False
                time.sleep(0.15)
                continue
            if args.steering == "arc":
                d, policy_obs, arc_lx, arc_az, arc_cmd_t = decide_arc_fetch_action(
                    obs, state, cfg, tracker, args, time.time(), arc_lx, arc_az, arc_cmd_t)
            else:
                policy_obs = obs
                d = decide_fetch_action(obs, state, cfg)
            state["step"] += 1
            if args.steering == "arc" and d.get("reason") == "arc_approach":
                state["lost_count"] = 0
            else:
                state["lost_count"] = d.get("lost_count", 0 if obs.get("detected") else state["lost_count"])
            if obs.get("detected"):
                counts["detected"] += 1
            counts[d["action"]] = counts.get(d["action"], 0) + 1
            rec = {"t": round(time.time() - t_start, 3), "obs": obs, "decision": d,
                   "state": dict(state)}
            if args.steering == "arc":
                rec["policy_obs"] = policy_obs
            trace.write(json.dumps(rec) + "\n")
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
                discard_after_turn = True
            elif d["action"] == ACT_FORWARD:
                refresher.set(d["linear_x"], d.get("angular_z", 0.0))  # rolls continuously; refresher feeds deadman
                state["forward_steps"] += 1
            elif d["action"] == ACT_HOLD:
                if state.get("lost_count", 0) > 1:
                    refresher.zero()
            # pace: local TRT eyes support ~8 Hz (15 fps camera, 15 ms infer);
            # remote path self-paces via no_new_data sleeps regardless
            dt = time.time() - t_loop
            if dt < 0.12:
                time.sleep(0.12 - dt)

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
    try:  # motion tape for the dashboard RESET (reverse-replay) button
        with open(os.path.join(run_dir, "last_motion.json"), "w") as f:
            json.dump({"events": refresher.log, "end": time.time()}, f)
    except Exception as e:
        summary["issues"].append("motion_log_write:%r" % (e,))
    try:
        hf = bridge.health()
        summary["final_safe"] = (hf.get("motion_enabled") is False
                                 and abs(float(hf.get("left_motor") or 0)) < 1e-6
                                 and abs(float(hf.get("right_motor") or 0)) < 1e-6)
    except Exception:
        summary["final_safe"] = False
    print(json.dumps(summary))
    return 0 if summary.get("final_safe") else 1


def run_reverse(args):
    """Dead-reckoned undo: replay the last episode's motion tape backwards.

    Reconstructs effective setpoint segments (bounded by the next set() or the
    hold/max-age expiry — matching Refresher semantics) and replays them last-
    to-first with negated velocities. Open-loop: stiction/slip drift grows with
    episode length; this parks the robot NEAR its start, not exactly on it.
    """
    MAX_SEG_S, MAX_TOTAL_S, MAX_AGE = 5.0, 90.0, 1.5
    if not os.path.isfile(args.reverse_log):
        print(json.dumps({"type": "onboard_reverse_replay", "stop_reason": "no_motion_tape",
                          "final_safe": True, "issues": ["no episode has recorded a tape yet"]}))
        return 0
    with open(args.reverse_log) as f:
        tape = json.load(f)
    ev = sorted(tape.get("events") or [], key=lambda e: e[0])
    end = float(tape.get("end") or (ev[-1][0] + MAX_AGE if ev else 0))
    segs = []
    for i, (t, lx, az, hold) in enumerate(ev):
        if abs(lx) < 1e-6 and abs(az) < 1e-6:
            continue
        t_next = ev[i + 1][0] if i + 1 < len(ev) else end
        limit = hold if hold > 0 else MAX_AGE
        dur = min(t_next - t, limit, MAX_SEG_S)
        if dur >= 0.04:
            segs.append((lx, az, dur))
    segs.reverse()
    total = sum(d for _l, _a, d in segs)
    scale = min(1.0, MAX_TOTAL_S / total) if total > 0 else 1.0

    bridge = Bridge(args.base_url)
    refresher = Refresher(bridge)
    summary = {"type": "onboard_reverse_replay", "segments": len(segs),
               "replay_s": round(total * scale, 1), "issues": []}
    try:
        bridge.set_motion(True, "onboard:reverse_arm")
        refresher.start()
        for lx, az, dur in segs:
            d = dur * scale
            refresher.set(-lx, -az, hold_s=d)
            time.sleep(d + 0.05)
        refresher.zero()
    except Exception as e:
        summary["issues"].append("reverse_error:%r" % (e,))
    finally:
        refresher.stop()
        try:
            bridge.stop("onboard:reverse_done")
            bridge.set_motion(False, "onboard:reverse_relock")
        except Exception as e:
            summary["issues"].append("relock_error:%r" % (e,))
    try:
        hf = bridge.health()
        summary["final_safe"] = (hf.get("motion_enabled") is False
                                 and abs(float(hf.get("left_motor") or 0)) < 1e-6
                                 and abs(float(hf.get("right_motor") or 0)) < 1e-6)
    except Exception:
        summary["final_safe"] = False
    summary["stop_reason"] = "reverse_complete" if not summary["issues"] else "reverse_issues"
    print(json.dumps(summary))
    return 0 if summary.get("final_safe") else 1


def run_selftest():
    class Args(object):
        pass
    cfg = default_config(center_deadband=0.12, turn_angular_z=2.3, approach_linear_x=0.55)
    args = Args()
    args.kp = 0.9
    args.kd = 0.25
    args.slew = 1.5
    args.coast_s = 0.8

    tracker = BallTracker()
    raw_resid = []
    filt_resid = []
    t = 100.0
    last_truth = None
    for i in range(60):
        dt = 0.06 + (0.035 if i % 7 == 0 else 0.0)
        t += dt
        truth_err = 0.70 - 0.010 * i
        truth_size = 24.0 + 0.55 * i
        jitter = (0.050 if i % 2 == 0 else -0.043) + (0.018 if i % 11 == 0 else 0.0)
        dropped = (i % 5 == 0)
        if not dropped:
            obs = {"detected": True, "confidence": 0.8,
                   "center_error": truth_err + jitter,
                   "equiv_diameter_px": truth_size + (1.8 if i % 3 == 0 else -1.2)}
            est = tracker.update(obs, t)
            raw_resid.append(float(obs["center_error"]) - truth_err)
            filt_resid.append(float(est["center_error"]) - truth_err)
            last_truth = (t, truth_err, truth_size)
        else:
            tracker.predict(t)
    raw_var = variance(raw_resid)
    filt_var = variance(filt_resid)
    smoother = filt_var < raw_var * 0.75

    coast_ok = False
    if last_truth is not None:
        coast_t = last_truth[0] + 0.22
        est = tracker.predict(coast_t)
        truth_err = last_truth[1] - 0.010 * (0.22 / 0.07)
        coast_ok = abs(float(est["center_error"]) - truth_err) < 0.12

    prev_lx = 0.0
    prev_az = 0.0
    slew_ok = True
    max_delta = args.slew * 0.10 + 1e-9
    for err in (0.8, 0.45, 0.12, 0.02, -0.18, -0.45):
        lx, az, _lt, _at = compute_arc_drive_command(err, 0.0, cfg, args.kp, args.kd,
                                                      args.slew, 0.10, prev_lx, prev_az)
        if abs(lx - prev_lx) > max_delta or abs(az - prev_az) > max_delta:
            slew_ok = False
        prev_lx, prev_az = lx, az
    _lx, az_pos, _lt, _at = compute_arc_drive_command(0.5, 0.0, cfg, args.kp, args.kd,
                                                      args.slew, 0.10, 0.0, 0.0)
    _lx, az_neg, _lt, _at = compute_arc_drive_command(-0.5, 0.0, cfg, args.kp, args.kd,
                                                      args.slew, 0.10, 0.0, 0.0)
    sign_ok = az_pos < 0.0 and az_neg > 0.0

    verdict = {"type": "onboard_fetch_selftest",
               "ok": bool(smoother and coast_ok and slew_ok and sign_ok),
               "raw_variance": round(raw_var, 7),
               "filtered_variance": round(filt_var, 7),
               "variance_ratio": round((filt_var / raw_var) if raw_var > 0.0 else 0.0, 4),
               "smoother": bool(smoother),
               "coast_ok": bool(coast_ok),
               "slew_ok": bool(slew_ok),
               "sign_ok": bool(sign_ok)}
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict["ok"] else 1


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
    p.add_argument("--steering", choices=["pulse", "arc"], default="pulse",
                   help="pulse keeps the legacy turn/forward behavior; arc enables continuous visual servoing")
    p.add_argument("--kp", type=float, default=0.9, help="arc steering proportional gain")
    p.add_argument("--kd", type=float, default=0.25, help="arc steering derivative gain")
    p.add_argument("--slew", type=float, default=1.5, help="arc max command delta per second")
    p.add_argument("--coast-s", type=float, default=0.8, help="arc tracker coast window before lost handling")
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
    p.add_argument("--detector", choices=["color", "remote", "trt"], default="color",
                   help="'remote' = laptop YOLO feed (hybrid); 'trt' = fine-tune engine on the local GPU")
    p.add_argument("--remote-det-url", default="http://192.168.1.59:8791/status")
    p.add_argument("--trt-engine", default="/home/jetson/chasecar_onboard/golfball_finetune_fp16.engine")
    p.add_argument("--trt-conf-floor", type=float, default=0.20)
    p.add_argument("--dry-run", action="store_true", help="perception only; never moves")
    p.add_argument("--dry-run-frames", type=int, default=8)
    p.add_argument("--run-dir", default="")
    p.add_argument("--reverse-log", default="",
                   help="replay this motion tape backwards (dead-reckoned undo) instead of fetching")
    p.add_argument("--selftest", action="store_true", help="run laptop-only tracker/arc servo checks")
    return p


if __name__ == "__main__":
    _args = build_parser().parse_args()
    if _args.selftest:
        raise SystemExit(run_selftest())
    raise SystemExit(run_reverse(_args) if _args.reverse_log else run(_args))
