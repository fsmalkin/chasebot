#!/usr/bin/env python3
"""Prove the offboard Chasecar command path reaches the locked factory bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from typing import Any

import chasecar_bridge_behavior_runner as behavior_runner
import chasecar_bridge_client as bridge_client


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_SOURCE_PATH = "$HOME/ros2_ws/src/chasecar_runtime"
DEFAULT_ARTIFACT_STEM = "factory_bridge_stack_path_gate"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def ensure_dir(path: Path | str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def default_artifact_dir() -> Path:
    return Path("artifacts") / "session" / ("%s_%s" % (DEFAULT_ARTIFACT_STEM, utc_stamp()))


def windows_path_to_wsl(path: Path | str) -> str:
    resolved = Path(path).resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return resolved.as_posix()
    parts = [part for part in resolved.parts[1:]]
    return "/mnt/%s/%s" % (drive, "/".join(parts))


def command_nonzero(command: dict[str, float]) -> bool:
    return abs(float(command.get("linear_x", 0.0) or 0.0)) > 1.0e-6 or abs(
        float(command.get("angular_z", 0.0) or 0.0)
    ) > 1.0e-6


def runtime_payload(sequence: int, command: dict[str, float], *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        command = {"linear_x": 0.0, "angular_z": 0.0}
    return {
        "manual_drive": {
            "enabled": bool(enabled),
            "sequence": int(sequence),
            "mode": "stack_path_locked_gate",
            "updated_utc": utc_now(),
            "command": command,
            "rationale": "Locked stack-through-bridge transport proof.",
            "source": "chasecar_bridge_stack_path_gate",
        }
    }


def deploy_bridge(args: argparse.Namespace, artifact_dir: Path, *, enable_motion: bool) -> dict[str, Any]:
    if args.skip_deploy:
        payload = {"skipped": True, "enable_motion": bool(enable_motion)}
        write_json(artifact_dir / ("deploy_motion.json" if enable_motion else "deploy_locked.json"), payload)
        return payload
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(REPO_ROOT / "scripts" / "deploy_robot_factory_bridge.ps1"),
        "-RobotHost",
        args.robot_host,
        "-RobotUser",
        args.robot_user,
        "-Port",
        str(args.port),
        "-Start",
        "-Camera",
    ]
    if enable_motion:
        command.extend(["-EnableMotion", "-MaxMotorSpeed", str(args.max_motor_speed)])
    result = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=args.deploy_timeout_s)
    payload = {
        "skipped": False,
        "enable_motion": bool(enable_motion),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    write_json(artifact_dir / ("deploy_motion.json" if enable_motion else "deploy_locked.json"), payload)
    if result.returncode != 0:
        raise RuntimeError("deploy_bridge_failed:%s" % result.returncode)
    return payload


def deploy_bridge_locked(args: argparse.Namespace, artifact_dir: Path) -> dict[str, Any]:
    return deploy_bridge(args, artifact_dir, enable_motion=False)


def camera_readiness_summary(client: bridge_client.BridgeClient, args: argparse.Namespace, phase: str) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(args.camera_ready_timeout_s))
    checks: list[dict[str, Any]] = []
    while True:
        check: dict[str, Any] = {"checked_utc": utc_now()}
        try:
            status, health = client.health()
            camera = health.get("camera", {}) if isinstance(health, dict) else {}
            cached_fps = float(camera.get("cached_fps", 0.0) or 0.0)
            frame_age_s = camera.get("frame_age_s")
            cached_bytes = int(camera.get("cached_bytes", 0) or 0)
            ready = (
                status == 200
                and bool(camera.get("enabled", False))
                and bool(camera.get("loaded", False))
                and cached_fps >= float(args.camera_min_fps)
                and cached_bytes >= int(args.camera_min_frame_bytes)
                and frame_age_s is not None
                and float(frame_age_s) <= float(args.camera_max_frame_age_s)
            )
            check.update({"http_status": status, "ok": bool(health.get("ok", False)), "camera": camera, "ready": ready})
            checks.append(check)
            if ready:
                break
        except Exception as exc:
            check.update({"ready": False, "error": repr(exc)})
            checks.append(check)
        if time.monotonic() >= deadline:
            break
        time.sleep(0.25)

    latest = checks[-1] if checks else {}
    latest_camera = latest.get("camera", {}) if isinstance(latest.get("camera"), dict) else {}
    issues: list[str] = []
    if not latest.get("ready", False):
        if not bool(latest_camera.get("enabled", False)):
            issues.append("camera_not_enabled")
        if not bool(latest_camera.get("loaded", False)):
            issues.append("camera_not_loaded")
        if int(latest_camera.get("cached_bytes", 0) or 0) < int(args.camera_min_frame_bytes):
            issues.append("camera_frame_too_small")
        if float(latest_camera.get("cached_fps", 0.0) or 0.0) < float(args.camera_min_fps):
            issues.append("camera_fps_below_min")
        frame_age_s = latest_camera.get("frame_age_s")
        if frame_age_s is None or float(frame_age_s) > float(args.camera_max_frame_age_s):
            issues.append("camera_frame_stale_or_missing")
    return {
        "phase": phase,
        "pass": bool(latest.get("ready", False)),
        "checks": checks,
        "latest": latest,
        "issues": issues,
    }


def safe_final_state(final_health: dict[str, Any]) -> bool:
    response = final_health.get("response") if isinstance(final_health.get("response"), dict) else final_health
    return bool(
        response.get("motion_enabled") is False
        and abs(float(response.get("left_motor", 0.0) or 0.0)) < 1.0e-6
        and abs(float(response.get("right_motor", 0.0) or 0.0)) < 1.0e-6
    )


def relay_bash(args: argparse.Namespace, artifact_dir: Path, runtime_path: Path, *, require_motion_enabled: bool) -> str:
    artifact_wsl = windows_path_to_wsl(artifact_dir)
    runtime_wsl = windows_path_to_wsl(runtime_path)
    require_flag = " \\\n  --require-motion-enabled" if require_motion_enabled else ""
    return f"""set -eo pipefail
source /opt/ros/{args.ros_distro}/setup.bash
cd "{args.runtime_source_path}"
ART="{artifact_wsl}"
RUNTIME="{runtime_wsl}"
mkdir -p "$ART"
python3 scripts/gather_motion_bridge.py \\
  --runtime-json "$RUNTIME" \\
  --loop-rate-hz {args.gather_loop_rate_hz} \\
  --max-linear-x {args.max_runtime_linear_x} \\
  --max-angular-z {args.max_runtime_angular_z} \\
  --no-use-sim-time \\
  > "$ART/gather_motion_bridge_stdout.log" 2> "$ART/gather_motion_bridge_stderr.log" &
gather_pid=$!
python3 ros2_scripts/factory_bridge_cmd_vel_relay.py \\
  --base-url {args.base_url} \\
  --summary-path "$ART/relay_summary.json" \\
  --twist-topics /cmd_vel \\
  --twist-stamped-topics "" \\
  --linear-scale {args.linear_scale} \\
  --angular-scale {args.angular_scale} \\
  --max-bridge-linear-x {args.max_bridge_linear_x} \\
  --max-bridge-angular-z {args.max_bridge_angular_z} \\
  --command-duration-s {args.command_duration_s} \\
  --post-rate-hz {args.post_rate_hz} \\
  --stale-stop-s {args.stale_stop_s}{require_flag} \\
  > "$ART/relay_stdout.log" 2> "$ART/relay_stderr.log" &
relay_pid=$!
sleep {args.relay_window_s}
kill -INT "$gather_pid" 2>/dev/null || true
kill -INT "$relay_pid" 2>/dev/null || true
wait "$gather_pid" 2>/dev/null || true
wait "$relay_pid" 2>/dev/null || true
"""


def run_relay_phase(
    args: argparse.Namespace,
    artifact_dir: Path,
    runtime_path: Path,
    *,
    require_motion_enabled: bool = False,
) -> dict[str, Any]:
    ensure_dir(artifact_dir)
    script_path = artifact_dir / "stack_path_relay.sh"
    script_path.write_text(
        relay_bash(args, artifact_dir, runtime_path, require_motion_enabled=require_motion_enabled),
        encoding="utf-8",
        newline="\n",
    )
    stdout_path = artifact_dir / "wsl_stdout.log"
    stderr_path = artifact_dir / "wsl_stderr.log"
    relay_summary_path = artifact_dir / "relay_summary.json"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            ["wsl", "-d", args.distro, "--", "bash", windows_path_to_wsl(script_path)],
            cwd=str(REPO_ROOT),
            stdout=stdout,
            stderr=stderr,
        )
        try:
            deadline = time.monotonic() + float(args.relay_start_timeout_s)
            while not relay_summary_path.exists():
                if process.poll() is not None:
                    raise RuntimeError("relay_process_exited_before_summary")
                if time.monotonic() >= deadline:
                    raise RuntimeError("relay_summary_not_created")
                time.sleep(0.2)
            exit_code = process.wait(timeout=float(args.relay_finish_timeout_s))
            if exit_code != 0:
                raise RuntimeError("relay_process_failed:%s" % exit_code)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
    return load_json(relay_summary_path)


def relay_counters(relay_summary: dict[str, Any]) -> dict[str, Any]:
    relay = relay_summary.get("relay") if isinstance(relay_summary.get("relay"), dict) else {}
    counters = relay.get("counters") if isinstance(relay.get("counters"), dict) else {}
    return counters


def relay_nonzero_success_events(relay_summary: dict[str, Any]) -> list[dict[str, Any]]:
    relay = relay_summary.get("relay") if isinstance(relay_summary.get("relay"), dict) else {}
    events = relay.get("events") if isinstance(relay.get("events"), list) else []
    successes: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict) or int(event.get("http_status", 0) or 0) != 200:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if not command_nonzero(
            {
                "linear_x": float(payload.get("linear_x", 0.0) or 0.0),
                "angular_z": float(payload.get("angular_z", 0.0) or 0.0),
            }
        ):
            continue
        response = event.get("response") if isinstance(event.get("response"), dict) else {}
        last_command = response.get("last_command") if isinstance(response.get("last_command"), dict) else {}
        if abs(float(last_command.get("left", 0.0) or 0.0)) > 1.0e-6 or abs(
            float(last_command.get("right", 0.0) or 0.0)
        ) > 1.0e-6:
            successes.append(event)
    return successes


def save_snapshot(client: bridge_client.BridgeClient, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    status, image_bytes = bridge_client.snapshot_with_retries(
        client,
        attempts=args.snapshot_attempts,
        interval_s=args.snapshot_retry_interval_s,
    )
    ensure_dir(path.parent)
    path.write_bytes(image_bytes)
    return {"http_status": status, "output": str(path), "bytes": len(image_bytes)}


def score_visual_motion(before_path: Path, after_path: Path, artifact_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    score_args = SimpleNamespace(
        min_visual_shift_px=args.min_visual_shift_px,
        min_visual_shift_score_gain=args.min_visual_shift_score_gain,
        max_static_visual_similarity=args.max_static_visual_similarity,
    )
    score = behavior_runner.analyze_visual_motion(before_path, [after_path], ["after_post_relock"], score_args)
    contact = behavior_runner.maybe_make_contact_sheet(
        [before_path, after_path],
        ["before stack-path motion", "after post-relock"],
        artifact_dir / "before_after_stack_path_motion.jpg",
    )
    score["contact_sheet_path"] = contact.get("output", "") if isinstance(contact, dict) else ""
    score["contact_sheet_result"] = contact
    write_json(artifact_dir / "visual_motion_score.json", score)
    return score


def compute_pass(summary: dict[str, Any]) -> bool:
    if summary.get("issues"):
        return False
    if not bool(summary.get("camera_readiness_gate", {}).get("pass", False)):
        return False
    command = summary.get("command") if isinstance(summary.get("command"), dict) else {}
    if not command_nonzero(command):
        return False
    counters = relay_counters(summary.get("relay_summary", {}))
    if int(counters.get("messages_received", 0) or 0) <= 0:
        return False
    if int(counters.get("cmd_vel_posts", 0) or 0) <= 0:
        return False
    if int(counters.get("http_refusals", 0) or 0) <= 0:
        return False
    if int(counters.get("dry_run_actions", 0) or 0) != 0:
        return False
    if not safe_final_state(summary.get("final_locked_health", {})):
        return False
    if not bool(summary.get("final_camera_readiness_gate", {}).get("pass", False)):
        return False
    if bool(summary.get("execute_motion", False)):
        motion = summary.get("motion_proof") if isinstance(summary.get("motion_proof"), dict) else {}
        if not bool(motion.get("pass", False)):
            return False
    return True


def validate_args(args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    command = {"linear_x": float(args.command_linear_x), "angular_z": float(args.command_angular_z)}
    if not command_nonzero(command):
        issues.append("nonzero_command_required")
    if args.execute_motion and not args.confirm_operator_ready:
        issues.append("operator_ready_confirmation_required")
    if abs(float(args.command_linear_x)) > float(args.max_runtime_linear_x):
        issues.append("command_linear_x_above_runtime_limit")
    if abs(float(args.command_angular_z)) > float(args.max_runtime_angular_z):
        issues.append("command_angular_z_above_runtime_limit")
    if float(args.max_bridge_linear_x) > 0.36:
        issues.append("max_bridge_linear_x_above_conservative_limit")
    if float(args.max_bridge_angular_z) > 0.8:
        issues.append("max_bridge_angular_z_above_locked_gate_limit")
    if args.execute_motion and abs(float(args.command_linear_x)) > 1.0e-6:
        issues.append("live_stack_motion_requires_turn_only")
    if float(args.max_motor_speed) > 1.0:
        issues.append("max_motor_speed_above_1")
    return issues


def run_motion_phase(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_root: Path,
    command: dict[str, float],
) -> dict[str, Any]:
    motion_dir = ensure_dir(artifact_root / "live_motion")
    runtime_path = motion_dir / "runtime" / "stack_path_runtime.json"
    summary: dict[str, Any] = {
        "artifact_dir": str(motion_dir),
        "issues": [],
        "pass": False,
    }
    try:
        summary["before_snapshot"] = save_snapshot(client, motion_dir / "before_locked.jpg", args)
        deploy_bridge(args, motion_dir / "enable_motion", enable_motion=True)
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        motion_camera_ready = camera_readiness_summary(client, args, "motion_enabled")
        summary["camera_readiness_gate"] = motion_camera_ready
        if not motion_camera_ready["pass"]:
            summary["issues"].append("motion_camera_readiness_gate_not_pass")
            return summary
        write_json(runtime_path, runtime_payload(1, command, enabled=True))
        relay_summary = run_relay_phase(args, motion_dir / "relay", runtime_path, require_motion_enabled=True)
        summary["relay_summary"] = relay_summary
        summary["nonzero_success_event_count"] = len(relay_nonzero_success_events(relay_summary))
    except Exception as exc:
        summary["issues"].append("motion_runner_exception:%r" % (exc,))
    finally:
        write_json(runtime_path, runtime_payload(99, command, enabled=False))
        try:
            client.stop("chasecar_bridge_stack_path_gate:motion_finally_stop")
        except Exception as exc:
            summary["issues"].append("motion_finally_stop_failed:%r" % (exc,))
        try:
            deploy_bridge_locked(args, motion_dir / "restore_locked")
        except Exception as exc:
            summary["issues"].append("motion_restore_locked_failed:%r" % (exc,))
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        try:
            summary["after_snapshot"] = save_snapshot(client, motion_dir / "after_post_relock.jpg", args)
            summary["visual_motion"] = score_visual_motion(
                Path(summary["before_snapshot"]["output"]),
                Path(summary["after_snapshot"]["output"]),
                motion_dir,
                args,
            )
        except Exception as exc:
            summary["issues"].append("motion_visual_evidence_failed:%r" % (exc,))

    counters = relay_counters(summary.get("relay_summary", {}))
    summary["relay_counters"] = counters
    summary["pass"] = bool(
        not summary["issues"]
        and int(counters.get("cmd_vel_posts", 0) or 0) > 0
        and int(counters.get("http_refusals", 0) or 0) == 0
        and int(summary.get("nonzero_success_event_count", 0) or 0) > 0
        and bool(summary.get("visual_motion", {}).get("movement_detected", False))
    )
    write_json(motion_dir / "motion_summary.json", summary)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_root = ensure_dir(args.artifact_dir or default_artifact_dir())
    command = {"linear_x": float(args.command_linear_x), "angular_z": float(args.command_angular_z)}
    summary: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_stack_path_gate",
        "artifact_dir": str(artifact_root),
        "base_url": args.base_url,
        "command": command,
        "execute_motion": bool(args.execute_motion),
        "issues": validate_args(args),
        "pass": False,
    }
    write_json(artifact_root / "gate_summary.json", summary)
    if summary["issues"] or args.dry_run:
        summary["plan_only"] = bool(args.dry_run)
        summary["pass"] = not summary["issues"]
        write_json(artifact_root / "gate_summary.json", summary)
        return summary

    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    runtime_path = artifact_root / "runtime" / "stack_path_runtime.json"
    relay_dir = artifact_root / "relay"
    try:
        deploy_bridge_locked(args, artifact_root / "start_locked")
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        camera_ready = camera_readiness_summary(client, args, "start_locked")
        summary["camera_readiness_gate"] = camera_ready
        if not camera_ready["pass"]:
            summary["issues"].append("camera_readiness_gate_not_pass")
            return summary
        write_json(runtime_path, runtime_payload(1, command, enabled=True))
        relay_summary = run_relay_phase(args, relay_dir, runtime_path)
        summary["relay_summary"] = relay_summary
        locked_ok = compute_pass(
            {
                **summary,
                "final_locked_health": {"response": {"motion_enabled": False, "left_motor": 0.0, "right_motor": 0.0}},
                "final_camera_readiness_gate": {"pass": True},
                "execute_motion": False,
            }
        )
        summary["locked_transport_pass"] = bool(locked_ok)
        if args.execute_motion and locked_ok:
            summary["motion_proof"] = run_motion_phase(client, args, artifact_root, command)
    except Exception as exc:
        summary["issues"].append("runner_exception:%r" % (exc,))
    finally:
        write_json(runtime_path, runtime_payload(99, command, enabled=False))
        try:
            deploy_bridge_locked(args, artifact_root / "final_restore_locked")
        except Exception as exc:
            summary["issues"].append("final_restore_locked_failed:%r" % (exc,))
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        try:
            status, payload = client.health()
            summary["final_locked_health"] = {"http_status": status, "response": payload}
            summary["final_camera_readiness_gate"] = camera_readiness_summary(client, args, "final_locked")
        except Exception as exc:
            summary["issues"].append("final_health_failed:%r" % (exc,))

    summary["pass"] = compute_pass(summary)
    write_json(artifact_root / "gate_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a locked stack-through-bridge command transport gate.")
    parser.add_argument("--base-url", default=bridge_client.DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=bridge_client.DEFAULT_TIMEOUT_S)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--execute-motion", action="store_true")
    parser.add_argument("--confirm-operator-ready", action="store_true")

    parser.add_argument("--distro", default="Ubuntu-24.04")
    parser.add_argument("--ros-distro", default="jazzy")
    parser.add_argument("--runtime-source-path", default=DEFAULT_RUNTIME_SOURCE_PATH)
    parser.add_argument("--robot-host", default="192.168.1.11")
    parser.add_argument("--robot-user", default="jetson")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument("--deploy-timeout-s", type=float, default=45.0)
    parser.add_argument("--max-motor-speed", type=float, default=0.7)

    parser.add_argument("--camera-warmup-s", type=float, default=1.0)
    parser.add_argument("--camera-ready-timeout-s", type=float, default=8.0)
    parser.add_argument("--camera-min-fps", type=float, default=2.0)
    parser.add_argument("--camera-max-frame-age-s", type=float, default=1.0)
    parser.add_argument("--camera-min-frame-bytes", type=int, default=100)
    parser.add_argument("--snapshot-attempts", type=int, default=10)
    parser.add_argument("--snapshot-retry-interval-s", type=float, default=0.15)

    parser.add_argument("--command-linear-x", type=float, default=0.0)
    parser.add_argument("--command-angular-z", type=float, default=0.2)
    parser.add_argument("--max-runtime-linear-x", type=float, default=0.10)
    parser.add_argument("--max-runtime-angular-z", type=float, default=0.40)
    parser.add_argument("--gather-loop-rate-hz", type=float, default=10.0)

    parser.add_argument("--relay-window-s", type=float, default=2.5)
    parser.add_argument("--relay-start-timeout-s", type=float, default=8.0)
    parser.add_argument("--relay-finish-timeout-s", type=float, default=12.0)
    parser.add_argument("--linear-scale", type=float, default=3.0)
    parser.add_argument("--angular-scale", type=float, default=4.0)
    parser.add_argument("--max-bridge-linear-x", type=float, default=0.0)
    parser.add_argument("--max-bridge-angular-z", type=float, default=0.8)
    parser.add_argument("--command-duration-s", type=float, default=0.20)
    parser.add_argument("--post-rate-hz", type=float, default=8.0)
    parser.add_argument("--stale-stop-s", type=float, default=0.35)
    parser.add_argument("--min-visual-shift-px", type=float, default=2.0)
    parser.add_argument("--min-visual-shift-score-gain", type=float, default=0.03)
    parser.add_argument("--max-static-visual-similarity", type=float, default=0.975)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
