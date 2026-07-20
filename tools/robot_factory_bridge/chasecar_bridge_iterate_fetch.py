"""Self-play fetch iteration: run approach+push, self-reset to a novel pose, repeat.

Each episode: (1) run the visual fetch controller (with search-scan so the ball is
re-acquired wherever the last push left it), (2) verify the bridge ended locked and
safe, (3) reset = reverse ~0.4 m + a RANDOM turn so the next approach geometry is
novel. Bounded everywhere; aborts on any unsafe end-state. Episode summaries append
to episodes.jsonl for fast analysis.
"""
import json
import os
import random
import subprocess
import sys
import time

REPO = r"D:\dev\chasebot-hw-v0"
SC = os.path.join(REPO, "artifacts", "session", "iterate_runs")
os.makedirs(SC, exist_ok=True)
CAL = "artifacts/session/mono_distance_calibration_bench01/calibration_summary.json"
CTRL = "tools/robot_factory_bridge/chasecar_bridge_visual_fetch_controller.py"
EPLOG = os.path.join(SC, "episodes.jsonl")  # under repo artifacts (gitignored)
N_EPISODES = int(sys.argv[1]) if len(sys.argv) > 1 else 2
MIN_CONF = sys.argv[2] if len(sys.argv) > 2 else "0.25"  # acquire floor; long-range dim-light detections start ~0.14

sys.path.insert(0, os.path.join(REPO, "tools", "robot_factory_bridge"))
import chasecar_bridge_client as c  # noqa: E402

cli = c.BridgeClient("http://192.168.1.11:8765", timeout_s=4.0)


def locked_and_safe():
    try:
        _, h = cli.health()
    except Exception as e:
        return False, {"error": repr(e)}
    ok = (h.get("ok") and h.get("motion_enabled") is False
          and abs(float(h.get("left_motor") or 0)) < 1e-6 and abs(float(h.get("right_motor") or 0)) < 1e-6)
    return ok, h


def wait_for_bridge(max_wait_s=120):
    """Ride out a Wi-Fi flap: reconnect + poll until the bridge answers again."""
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        try:
            _, h = cli.health()
            if h.get("ok"):
                return True
        except Exception:
            pass
        subprocess.run(["netsh", "wlan", "connect", "name=jetbot-mini"], capture_output=True)
        time.sleep(5)
    return False


def force_relock():
    for _ in range(4):
        try:
            cli.stop("iterate:force_stop")
            cli.set_motion_enabled(False, "iterate:force_relock")
            return True
        except Exception:
            time.sleep(2)
    return False


def reset_pose(ep):
    """Reverse ~0.4 m then random turn -> novel approach geometry. Bounded + relocked."""
    rng = random.Random(ep * 7919 + int(time.time()) % 1000)
    turn_dir = rng.choice([-1.0, 1.0])
    turn_dur = rng.uniform(0.25, 0.6)
    cli.set_motion_enabled(True, "iterate:reset")
    try:
        for _ in range(2):  # 2 x 0.6 s reverse (bridge caps a single command at 1.0 s)
            cli.cmd_vel(-0.55, 0.0, 0.6, "iterate:reverse")
            time.sleep(0.62)
        cli.cmd_vel(0.0, turn_dir * 2.3, turn_dur, "iterate:random_turn")
        time.sleep(turn_dur + 0.2)
    finally:
        try:
            cli.stop("iterate:reset_stop")
        except Exception:
            pass
        cli.set_motion_enabled(False, "iterate:reset_relock")
    return {"turn_dir": turn_dir, "turn_dur": round(turn_dur, 2)}


def run_episode(ep):
    art = os.path.join(SC, "ep_%d_%d" % (ep, int(time.time())))
    os.makedirs(art, exist_ok=True)
    cmd = [
        "python", CTRL, "--calibration", CAL,
        "--standoff-m", "0.35", "--push-steps", "10", "--push-linear-x", "0.55",
        "--approach-linear-x", "0.55", "--turn-angular-z", "2.3",
        "--forward-budget", "40", "--max-steps", "140", "--center-deadband", "0.12",
        "--confidence-threshold", "0.08", "--min-confidence", MIN_CONF,
        "--search-scan", "26",
        "--artifact-dir", art,
    ]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=420)
    dur = round(time.time() - t0, 1)
    try:
        out = json.loads(r.stdout)
    except Exception:
        return {"episode": ep, "error": "unparseable", "rc": r.returncode,
                "stdout_tail": r.stdout[-400:], "duration_s": dur}
    steps = out.get("steps") or []
    acts = [s["decision"]["action"] for s in steps]
    det = [s for s in steps if s.get("obs", {}).get("detected")]
    zs = [s["decision"].get("z_m") for s in steps if s["decision"].get("z_m")]
    return {
        "episode": ep, "duration_s": dur,
        "stop_reason": out.get("stop_reason"),
        "scan_steps": out.get("scan_steps"),
        "steps": len(steps), "forwards": acts.count("forward"),
        "turns": acts.count("turn"), "holds": acts.count("hold"),
        "detect_rate": round(len(det) / max(len(steps), 1), 2),
        "z_first": zs[0] if zs else None, "z_last": zs[-1] if zs else None,
        "push": out.get("push"), "final_safe": out.get("final_safe"),
        "issues": out.get("issues"), "artifact_dir": art,
    }


def log(rec):
    print(json.dumps(rec), flush=True)
    with open(EPLOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def main():
    ok, h = locked_and_safe()
    if not ok:
        log({"abort": "preflight_unsafe", "health": {k: h.get(k) for k in ("ok", "motion_enabled")}})
        return 1
    for ep in range(1, N_EPISODES + 1):
        rec = None
        for attempt in range(1, 3):  # ride through Wi-Fi flaps: retry a dropped episode once
            rec = run_episode(ep)
            rec["attempt"] = attempt
            log(rec)
            transient = "bridge_unreachable" in str(rec.get("stop_reason", "")) or rec.get("error")
            if not transient:
                break
            log({"episode": ep, "note": "transient bridge outage; waiting for link"})
            if not wait_for_bridge():
                log({"abort": "bridge_never_recovered", "episode": ep})
                return 1
            force_relock()
        if not rec.get("final_safe"):
            if not (wait_for_bridge() and force_relock()):
                log({"abort": "episode_unsafe_and_unrecoverable", "episode": ep})
                return 1
            log({"episode": ep, "note": "relocked after outage; continuing"})
        ok, _ = locked_and_safe()
        if not ok:
            if not (wait_for_bridge() and force_relock()):
                log({"abort": "not_locked_between_episodes", "episode": ep})
                return 1
        if ep < N_EPISODES:
            rst = reset_pose(ep)
            log({"episode": ep, "reset": rst})
            ok, _ = locked_and_safe()
            if not ok:
                log({"abort": "reset_left_unsafe", "episode": ep})
                return 1
            time.sleep(0.8)
    ok, h = locked_and_safe()
    log({"done": True, "final_locked": ok})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
