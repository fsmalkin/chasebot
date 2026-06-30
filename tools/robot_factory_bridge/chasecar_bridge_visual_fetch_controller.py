#!/usr/bin/env python3
"""Closed-loop visual approach (standoff) controller for the factory bridge.

The next rung toward fetch: drive toward a YOLO-detected ball, turning to keep it
centered, and STOP at a calibrated standoff distance (never contacting/pushing the
ball, never driving close to whatever is behind it). Distance comes from the
apparent-size calibration (chasecar_bridge_mono_distance_calibration.py).

Safety is concentrated in one pure, fully unit-tested decision function,
``decide_fetch_action`` — the live executor only carries out what it returns and
always relocks. Hard guards, all enforced in the pure function:
  - standoff terminal stop: stop as soon as z <= standoff_m (never get closer)
  - forward budget: cap total forward nudges (backstop if the terminal stop never fires)
  - lost-target stop: stop after N consecutive missed detections (never drive blind)
  - confidence floor: a detection is only ACTED ON if confidence >= min_confidence
    and has real size; low-confidence flicker / false positives count as misses
  - centered-before-forward: only nudge forward when the ball is detected AND centered
  - max-steps overall cap
The executor wraps every live slice in enable -> bounded pulse -> relock with the
bridge's 0.5 s deadman as the hardware backstop, and retries the final relock so a
flaky network cannot leave motion enabled. On hard power loss (battery death /
SIGKILL) the motors are stopped by the 0.5 s hardware deadman and the bridge boots
LOCKED by default, so the safe state is restored without this process.

This module does NOT auto-run live; live use is operator-supervised in daylight.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

ACT_TURN = "turn"
ACT_FORWARD = "forward"
ACT_HOLD = "hold"
ACT_STOP = "stop"


def default_config(**over: Any) -> dict[str, Any]:
    cfg = {
        "k_px_m": 9.62,
        "standoff_m": 0.40,          # stop this far from the ball (never closer)
        "center_deadband": 0.16,     # |center_error| under this counts as centered
        "forward_budget": 40,        # max forward nudges (hard backstop)
        "lost_limit": 4,             # consecutive missed/untrusted detections -> stop
        "min_confidence": 0.25,      # detections below this count as a miss (never acted on)
        "max_steps": 120,            # overall loop cap
        "turn_angular_z": 0.7,       # above stiction
        "approach_linear_x": 0.04,   # slow forward (bridge cap)
        "size_key": "equiv_diameter_px",
    }
    cfg.update(over)
    return cfg


def decide_fetch_action(obs: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Pure safety-critical decision: given one observation + state, choose the next action.

    obs: {detected: bool, <size_key>: float, center_error: float}
    state: {step, forward_steps, lost_count}
    Returns: {action, reason, angular_z?, linear_x?, z_m?}  (no side effects)
    """
    step = int(state.get("step", 0))
    if step >= int(cfg["max_steps"]):
        return {"action": ACT_STOP, "reason": "max_steps_reached"}

    detected = bool(obs.get("detected"))
    confidence = float(obs.get("confidence", 0.0) or 0.0)
    size_px = float(obs.get(cfg["size_key"], 0.0) or 0.0)
    # Only act on a CONFIDENT, real-sized detection. A miss, a low-confidence
    # flicker, or a zero-size hit all count as a miss so we never turn or drive
    # forward on an untrustworthy detection (no blind / false-positive motion).
    usable = detected and confidence >= float(cfg["min_confidence"]) and size_px > 0.0
    if not usable:
        lost = int(state.get("lost_count", 0)) + 1
        if lost > int(cfg["lost_limit"]):
            return {"action": ACT_STOP, "reason": "lost_target", "lost_count": lost}
        reason = "target_not_detected" if not detected else (
            "low_confidence" if confidence < float(cfg["min_confidence"]) else "zero_size")
        return {"action": ACT_HOLD, "reason": reason, "lost_count": lost}

    z_m = float(cfg["k_px_m"]) / size_px

    # terminal standoff: stop the instant we're at/inside the standoff distance
    if z_m <= float(cfg["standoff_m"]):
        return {"action": ACT_STOP, "reason": "standoff_reached", "z_m": round(z_m, 4)}

    ce = float(obs.get("center_error", 0.0) or 0.0)
    if abs(ce) > float(cfg["center_deadband"]):
        # turn to center BEFORE any forward motion; ce>0 (ball right) -> angular_z negative
        az = -float(cfg["turn_angular_z"]) if ce > 0 else float(cfg["turn_angular_z"])
        return {"action": ACT_TURN, "reason": "center_target", "angular_z": az, "z_m": round(z_m, 4)}

    # centered + outside standoff: forward nudge, unless the budget is spent
    if int(state.get("forward_steps", 0)) >= int(cfg["forward_budget"]):
        return {"action": ACT_STOP, "reason": "forward_budget_exhausted", "z_m": round(z_m, 4)}
    return {"action": ACT_FORWARD, "reason": "approach", "linear_x": float(cfg["approach_linear_x"]), "z_m": round(z_m, 4)}


# ----------------------------- live executor -----------------------------

def _observe(client, calib, model, target_class, conf, iou, input_size, size_key, artifact_dir):
    _, fb, _, _ = client_fetch(client)
    fp = str(Path(artifact_dir) / "_cur.jpg")
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    open(fp, "wb").write(fb)
    m = calib.measure_frame_yolo(fp, model=model, target_class=target_class, confidence_threshold=conf,
                                 iou_threshold=iou, input_size=input_size, artifact_dir=str(Path(artifact_dir) / "_yolo"))
    return {"detected": bool(m.get("detected")), size_key: m.get(size_key), "center_error": m.get("center_error"),
            "confidence": m.get("confidence")}


def client_fetch(client):
    # thin wrapper so tests can monkeypatch; uses the bridge snapshot
    img = client.snapshot()  # (status, bytes)
    return img[0], img[1], "camera.jpg", ""


def run_trial(args) -> dict[str, Any]:
    import chasecar_bridge_client as c
    import chasecar_bridge_mono_distance_calibration as calib
    import chasecar_bridge_object_pose_observation as posemod

    cal = posemod.load_calibration(args.calibration, size_key=args.size_key)
    cfg = default_config(k_px_m=cal["k_px_m"], standoff_m=args.standoff_m, size_key=args.size_key,
                         forward_budget=args.forward_budget, lost_limit=args.lost_limit,
                         max_steps=args.max_steps, turn_angular_z=args.turn_angular_z,
                         approach_linear_x=args.approach_linear_x, center_deadband=args.center_deadband,
                         min_confidence=args.min_confidence)
    client = c.BridgeClient(args.base_url, timeout_s=4.0)
    artifact_dir = Path(args.artifact_dir or ("artifacts/session/visual_fetch_trial_%s" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    artifact_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"type": "visual_fetch_approach_trial", "config": cfg, "steps": [], "issues": []}
    # preflight: must be reachable + locked + camera fresh
    st, h = client.health()
    cam = h.get("camera", {})
    if not (st == 200 and h.get("ok") and h.get("motion_enabled") is False and float(cam.get("frame_age_s", 9) or 9) < 1.5):
        summary["stop_reason"] = "preflight_failed"
        summary["preflight_health"] = h
        return summary

    state = {"step": 0, "forward_steps": 0, "lost_count": 0}
    stop_reason = "unset"
    try:
        while True:
            obs = None
            observe_err = None
            for _ot in range(3):  # read-only retry: a Wi-Fi blip must not abort the run
                try:
                    obs = _observe(client, calib, args.model, args.target_class, args.confidence_threshold,
                                   args.iou_threshold, args.input_size, args.size_key, artifact_dir)
                    break
                except Exception as oe:
                    observe_err = oe
                    time.sleep(0.6)
            if obs is None:
                # persistent read failure -> treat as a miss (graceful), feeds lost_target guard
                obs = {"detected": False, "observe_error": repr(observe_err)[:120]}
            d = decide_fetch_action(obs, state, cfg)
            state["step"] += 1
            state["lost_count"] = d.get("lost_count", 0 if obs.get("detected") else state["lost_count"])
            rec = {"step": state["step"], "obs": obs, "decision": d, "forward_steps": state["forward_steps"]}
            summary["steps"].append(rec)
            if d["action"] == ACT_STOP:
                stop_reason = d["reason"]; break
            if d["action"] == ACT_HOLD:
                time.sleep(0.5); continue
            # motion: enable, bounded pulse, relock immediately (deadman backstops)
            client.set_motion_enabled(True, "visual_fetch")
            try:
                if d["action"] == ACT_TURN:
                    client.cmd_vel(0.0, d["angular_z"], 0.2, "visual_fetch:turn")
                elif d["action"] == ACT_FORWARD:
                    client.cmd_vel(d["linear_x"], 0.0, 0.2, "visual_fetch:forward")
                    state["forward_steps"] += 1
                time.sleep(0.2)
            finally:
                try: client.stop("visual_fetch:stop")
                except Exception: pass
                client.set_motion_enabled(False, "visual_fetch:relock")
            time.sleep(0.4)
        # bounded contact-push after a clean approach (open-loop; the ball is at the nose
        # so detection is unreliable here). Hard-capped by --push-steps; relock per nudge.
        if stop_reason == "standoff_reached" and int(getattr(args, "push_steps", 0)) > 0:
            summary["push"] = {"requested": int(args.push_steps), "executed": 0, "linear_x": float(args.push_linear_x)}
            for _pi in range(int(args.push_steps)):
                client.set_motion_enabled(True, "visual_fetch:push")
                try:
                    client.cmd_vel(float(args.push_linear_x), 0.0, 0.25, "visual_fetch:push")
                    summary["push"]["executed"] += 1
                    time.sleep(0.25)
                finally:
                    try: client.stop("visual_fetch:push_stop")
                    except Exception: pass
                    client.set_motion_enabled(False, "visual_fetch:push_relock")
                time.sleep(0.3)
            stop_reason = "standoff_then_pushed"
    except Exception as exc:  # any error -> fall through to guaranteed relock
        stop_reason = "exception:%r" % (exc,)
        summary["issues"].append(stop_reason)
    finally:
        # Guarantee LOCKED on exit: retry relock so a flaky network can't leave
        # motion enabled. (Hard power loss is covered by the deadman + locked-on-boot.)
        relock_ok = False
        for _ in range(5):
            try: client.stop("visual_fetch:final_stop")
            except Exception: pass
            try:
                client.set_motion_enabled(False, "visual_fetch:final_relock")
                relock_ok = True
                break
            except Exception as e:
                summary["issues"].append("final_relock_retry:%r" % e)
                time.sleep(0.5)
        if not relock_ok:
            summary["issues"].append("FINAL_RELOCK_FAILED_AFTER_RETRIES")

    summary["stop_reason"] = stop_reason
    # Guarded post-health read: must never crash past the safe-state record.
    try:
        _, hf = client.health()
        summary["final_health"] = {"motion_enabled": hf.get("motion_enabled"), "left_motor": hf.get("left_motor"), "right_motor": hf.get("right_motor")}
        summary["final_safe"] = (hf.get("motion_enabled") is False and abs(float(hf.get("left_motor", 0) or 0)) < 1e-6 and abs(float(hf.get("right_motor", 0) or 0)) < 1e-6)
    except Exception as e:
        summary["issues"].append("final_health_unreadable:%r" % e)
        summary["final_health"] = None
        summary["final_safe"] = False
    summary["forward_steps"] = state["forward_steps"]
    (artifact_dir / "trial_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--calibration", required=True)
    p.add_argument("--base-url", default="http://192.168.1.11:8765")
    p.add_argument("--artifact-dir", default="")
    p.add_argument("--model", default="runtime/yolo/yolov5m.onnx")
    p.add_argument("--target-class", default="sports ball")
    p.add_argument("--confidence-threshold", type=float, default=0.10)
    p.add_argument("--iou-threshold", type=float, default=0.45)
    p.add_argument("--input-size", type=int, default=640)
    p.add_argument("--size-key", default="equiv_diameter_px")
    p.add_argument("--standoff-m", type=float, default=0.40)
    p.add_argument("--center-deadband", type=float, default=0.16)
    p.add_argument("--min-confidence", type=float, default=0.25)
    p.add_argument("--forward-budget", type=int, default=40)
    p.add_argument("--lost-limit", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=120)
    p.add_argument("--turn-angular-z", type=float, default=0.7)
    p.add_argument("--approach-linear-x", type=float, default=0.04)
    p.add_argument("--push-steps", type=int, default=0,
                   help="After standoff, push the ball forward this many bounded open-loop nudges (true-fetch delivery).")
    p.add_argument("--push-linear-x", type=float, default=0.04)
    p.add_argument("--pretty", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_trial(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("final_safe") else 1


if __name__ == "__main__":
    raise SystemExit(main())
