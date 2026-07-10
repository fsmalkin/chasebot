#!/usr/bin/env python3
"""Run bounded no-contact onboard acquisition cycles with verified reverse reset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any
import urllib.request


SUCCESS_EPISODE_REASON = "standoff_reached"
SUCCESS_RESET_REASON = "reverse_complete"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def http_json(base_url: str, path: str, method: str = "GET", timeout_s: float = 8.0) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = b"" if method.upper() == "POST" else None
    request = urllib.request.Request(url, data=data, method=method.upper())
    with urllib.request.urlopen(request, timeout=float(timeout_s)) as response:
        return json.loads(response.read().decode("utf-8"))


def http_bytes(base_url: str, path: str, timeout_s: float = 8.0) -> bytes:
    url = base_url.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=float(timeout_s)) as response:
        return response.read()


def safe_locked_health(health: dict[str, Any]) -> bool:
    return bool(
        health.get("ok") is True
        and health.get("motion_enabled") is False
        and abs(float(health.get("left_motor", 0.0) or 0.0)) < 1.0e-6
        and abs(float(health.get("right_motor", 0.0) or 0.0)) < 1.0e-6
    )


def live_health_valid(health: dict[str, Any], max_camera_age_s: float, max_motor_abs: float) -> tuple[bool, str]:
    if health.get("ok") is not True:
        return False, "bridge_not_ok"
    camera = health.get("camera") if isinstance(health.get("camera"), dict) else {}
    if not camera.get("enabled") or not camera.get("loaded"):
        return False, "camera_not_ready"
    frame_age = camera.get("frame_age_s")
    if frame_age is None or float(frame_age) > float(max_camera_age_s):
        return False, "camera_stale"
    left = abs(float(health.get("left_motor", 0.0) or 0.0))
    right = abs(float(health.get("right_motor", 0.0) or 0.0))
    if max(left, right) > float(max_motor_abs) + 1.0e-6:
        return False, "motor_bound_exceeded"
    return True, "ok"


def stop_verified(args: argparse.Namespace, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {"label": label, "requested_utc": utc_now(), "pass": False}
    try:
        response = http_json(args.dashboard_url, "/stop", method="POST", timeout_s=10.0)
        result["response"] = response
    except Exception as exc:
        result["stop_error"] = repr(exc)
    try:
        health = http_json(args.bridge_url, "/health", timeout_s=8.0)
        result["health"] = health
        result["pass"] = bool(
            safe_locked_health(health)
            and isinstance(result.get("response"), dict)
            and result["response"].get("verified") is True
        )
    except Exception as exc:
        result["health_error"] = repr(exc)
    return result


def classify_case(center_error: float, center_deadband: float = 0.12, turn_gate: float = 0.55) -> str:
    value = float(center_error)
    if abs(value) <= float(center_deadband):
        return "center"
    if value < -float(turn_gate):
        return "far-left"
    if value > float(turn_gate):
        return "far-right"
    return "mid-left" if value < 0.0 else "mid-right"


def parse_json_lines(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in str(text).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def summarize_probe_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    episode: dict[str, Any] = {}
    for row in rows:
        if isinstance(row.get("dry_run_obs"), dict):
            observations.append(row["dry_run_obs"])
            decisions.append(row.get("decision") if isinstance(row.get("decision"), dict) else {})
        if row.get("type") == "onboard_fetch_episode":
            episode = row

    detected = [
        (obs, decisions[index])
        for index, obs in enumerate(observations)
        if obs.get("detected") is True
        and str(obs.get("source", "")) == "onboard_trt"
        and float(obs.get("confidence", 0.0) or 0.0) >= float(args.min_probe_confidence)
    ]
    result: dict[str, Any] = {
        "type": "hardware_acquisition_probe",
        "observation_count": len(observations),
        "detected_count": len(detected),
        "episode": episode,
        "pass": False,
        "issues": [],
    }
    if episode.get("final_safe") is not True:
        result["issues"].append("probe_not_final_safe")
    if len(detected) < int(args.min_probe_detections):
        result["issues"].append("insufficient_onboard_detections")
    if detected:
        errors = [float(obs.get("center_error", 0.0) or 0.0) for obs, _decision in detected]
        confidences = [float(obs.get("confidence", 0.0) or 0.0) for obs, _decision in detected]
        ranges = [
            float(decision.get("z_m"))
            for _obs, decision in detected
            if decision.get("z_m") is not None
        ]
        result["median_center_error"] = statistics.median(errors)
        result["median_confidence"] = statistics.median(confidences)
        result["observed_case"] = classify_case(result["median_center_error"])
        if ranges:
            result["median_z_m"] = statistics.median(ranges)
        else:
            result["issues"].append("probe_range_missing")
        if args.expected_case != "any" and result["observed_case"] != args.expected_case:
            result["issues"].append("unexpected_case:%s" % result["observed_case"])
        if result.get("median_z_m") is not None:
            if not (float(args.range_min_m) <= float(result["median_z_m"]) <= float(args.range_max_m)):
                result["issues"].append("range_out_of_bounds")
    result["pass"] = not result["issues"]
    return result


def run_onboard_probe(args: argparse.Namespace, artifact_dir: Path, label: str) -> dict[str, Any]:
    command = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
        "%s@%s" % (args.robot_user, args.robot_host),
        "python3", "/home/jetson/chasecar_onboard/chasecar_onboard_fetch.py",
        "--detector", "trt", "--steering", "arc",
        "--kp", "0.30", "--kd", "0.10", "--slew", "1.00", "--turn-gate", "0.55",
        "--min-confidence", "0.2", "--lost-limit", "12", "--standoff-m", "0.35",
        "--dry-run", "--dry-run-frames", str(int(args.probe_frames)),
        "--run-dir", "/home/jetson/chasecar_onboard/runs",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=float(args.probe_timeout_s),
        check=False,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / (label + "_stdout.jsonl")).write_text(completed.stdout, encoding="utf-8")
    (artifact_dir / (label + "_stderr.txt")).write_text(completed.stderr, encoding="utf-8")
    summary = summarize_probe_rows(parse_json_lines(completed.stdout), args)
    summary.update({"label": label, "returncode": completed.returncode, "command": command})
    if completed.returncode != 0:
        summary["issues"].append("probe_process_failed:%d" % completed.returncode)
        summary["pass"] = False
    write_json(artifact_dir / (label + "_summary.json"), summary)
    return summary


def geometry_matches(reference: dict[str, Any], candidate: dict[str, Any], args: argparse.Namespace) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not reference.get("pass"):
        issues.append("reference_probe_failed")
    if not candidate.get("pass"):
        issues.append("candidate_probe_failed")
    if reference.get("median_center_error") is None or candidate.get("median_center_error") is None:
        issues.append("center_error_missing")
    elif abs(float(reference["median_center_error"]) - float(candidate["median_center_error"])) > float(args.reset_error_tolerance):
        issues.append("reset_center_error_drift")
    if reference.get("median_z_m") is None or candidate.get("median_z_m") is None:
        issues.append("range_missing")
    elif abs(float(reference["median_z_m"]) - float(candidate["median_z_m"])) > float(args.reset_range_tolerance_m):
        issues.append("reset_range_drift")
    return not issues, issues


def load_last_json_line(path: Path) -> dict[str, Any]:
    rows = parse_json_lines(path.read_text(encoding="utf-8-sig"))
    if not rows:
        raise RuntimeError("no_json_summary:%s" % path)
    return rows[-1]


def output_set(run_dir: Path, prefix: str) -> set[str]:
    return {str(path.resolve()) for path in run_dir.glob(prefix + "_*.json")}


def newest_output(run_dir: Path, prefix: str, before: set[str]) -> Path:
    candidates = [
        path for path in run_dir.glob(prefix + "_*.json")
        if str(path.resolve()) not in before and path.stat().st_size > 0
    ]
    if not candidates:
        raise RuntimeError("new_%s_summary_missing" % prefix)
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def wait_for_episode(args: argparse.Namespace, prefix: str, before: set[str], timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + float(timeout_s)
    status_rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        if args.stop_file.is_file():
            raise RuntimeError("operator_stop_file_present")
        status = http_json(args.dashboard_url, "/status", timeout_s=5.0)
        health = http_json(args.bridge_url, "/health", timeout_s=5.0)
        health_ok, health_reason = live_health_valid(health, args.max_camera_age_s, args.max_motor_abs)
        status_rows.append({
            "t": round(time.time(), 3),
            "running": bool(status.get("running")),
            "last": status.get("last"),
            "motion_enabled": health.get("motion_enabled"),
            "left_motor": health.get("left_motor"),
            "right_motor": health.get("right_motor"),
            "camera_frame_age_s": (health.get("camera") or {}).get("frame_age_s"),
        })
        if not health_ok:
            raise RuntimeError("live_health_failed:%s" % health_reason)
        if not status.get("running"):
            for _attempt in range(20):
                try:
                    path = newest_output(args.dashboard_run_dir, prefix, before)
                    return {"summary_path": str(path), "summary": load_last_json_line(path), "status_rows": status_rows}
                except RuntimeError:
                    time.sleep(0.10)
            raise RuntimeError("completed_%s_summary_missing" % prefix)
        time.sleep(float(args.poll_interval_s))
    raise RuntimeError("%s_timeout" % prefix)


def episode_qualifies(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if summary.get("type") != "onboard_fetch_episode":
        issues.append("wrong_episode_type")
    if summary.get("steering") != "arc":
        issues.append("wrong_steering_mode")
    if summary.get("stop_reason") != SUCCESS_EPISODE_REASON:
        issues.append("unexpected_stop_reason:%s" % summary.get("stop_reason"))
    if summary.get("final_safe") is not True:
        issues.append("episode_not_final_safe")
    push = summary.get("push") if isinstance(summary.get("push"), dict) else {}
    if int(push.get("executed", 0) or 0) != 0:
        issues.append("push_executed_in_no_contact_lane")
    return not issues, issues


def reset_qualifies(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if summary.get("type") != "onboard_reverse_replay":
        issues.append("wrong_reset_type")
    if summary.get("stop_reason") != SUCCESS_RESET_REASON:
        issues.append("unexpected_reset_reason:%s" % summary.get("stop_reason"))
    if summary.get("final_safe") is not True:
        issues.append("reset_not_final_safe")
    return not issues, issues


def pull_trace(args: argparse.Namespace, summary: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    remote_path = str(summary.get("trace", "") or "")
    result: dict[str, Any] = {"remote_path": remote_path, "pass": False}
    if not remote_path.startswith("/home/jetson/chasecar_onboard/runs/"):
        result["error"] = "unexpected_trace_path"
        return result
    local_path = artifact_dir / Path(remote_path).name
    completed = subprocess.run(
        [
            "scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
            "%s@%s:%s" % (args.robot_user, args.robot_host, remote_path),
            str(local_path),
        ],
        capture_output=True,
        text=True,
        timeout=20.0,
        check=False,
    )
    result.update({
        "local_path": str(local_path),
        "returncode": completed.returncode,
        "stderr": completed.stderr[-500:],
        "pass": bool(completed.returncode == 0 and local_path.is_file() and local_path.stat().st_size > 0),
    })
    return result


def capture_raw_frame(args: argparse.Namespace, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(http_bytes(args.bridge_url, "/camera.jpg", timeout_s=8.0))


def validate_args(args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    if args.execute_motion:
        if not args.confirm_owner_unattended:
            issues.append("owner_unattended_confirmation_required")
        if not args.room_isolated:
            issues.append("isolated_room_confirmation_required")
        if not str(args.stop_file):
            issues.append("stop_file_required")
    if int(args.cycles) < 1 or int(args.cycles) > 5:
        issues.append("cycles_must_be_between_1_and_5")
    if float(args.max_episode_s) > 30.0 or float(args.max_reset_s) > 30.0:
        issues.append("phase_timeout_exceeds_30s")
    return issues


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "type": "hardware_acquisition_unattended_campaign",
        "generated_utc": utc_now(),
        "artifact_dir": str(args.artifact_dir),
        "requested_cycles": int(args.cycles),
        "authorization": {
            "execute_motion": bool(args.execute_motion),
            "owner_unattended_confirmed": bool(args.confirm_owner_unattended),
            "room_isolated_confirmed": bool(args.room_isolated),
            "stop_file": str(args.stop_file),
        },
        "cycles": [],
        "issues": validate_args(args),
        "pass": False,
        "stop_reason": "unset",
    }
    if result["issues"]:
        result["stop_reason"] = "argument_validation_failed"
        write_json(args.artifact_dir / "campaign_summary.json", result)
        return result

    baseline: dict[str, Any] = {}
    try:
        initial_stop = stop_verified(args, "campaign_preflight")
        result["initial_stop"] = initial_stop
        if not initial_stop.get("pass"):
            raise RuntimeError("preflight_stop_unverified")
        if args.stop_file.is_file():
            raise RuntimeError("operator_stop_file_present")
        capture_raw_frame(args, args.artifact_dir / "campaign_preflight_raw.jpg")
        baseline = run_onboard_probe(args, args.artifact_dir, "campaign_preflight_probe")
        result["baseline_probe"] = baseline
        if not baseline.get("pass"):
            raise RuntimeError("baseline_probe_failed")
        if not args.execute_motion:
            result["stop_reason"] = "locked_dry_run_complete"
            result["pass"] = True
            return result

        for index in range(1, int(args.cycles) + 1):
            cycle_dir = args.artifact_dir / ("cycle_%02d" % index)
            cycle_dir.mkdir(parents=True, exist_ok=True)
            cycle: dict[str, Any] = {"index": index, "started_utc": utc_now(), "issues": [], "pass": False}
            result["cycles"].append(cycle)
            pre_probe = run_onboard_probe(args, cycle_dir, "pre_cycle_probe")
            cycle["pre_probe"] = pre_probe
            geometry_ok, geometry_issues = geometry_matches(baseline, pre_probe, args)
            if not geometry_ok:
                cycle["issues"].extend(geometry_issues)
                raise RuntimeError("pre_cycle_geometry_failed")
            capture_raw_frame(args, cycle_dir / "pre_cycle_raw.jpg")

            run_before = output_set(args.dashboard_run_dir, "run")
            start = http_json(args.dashboard_url, "/go-acquire-only", method="POST", timeout_s=10.0)
            cycle["start_response"] = start
            if start.get("ok") is not True:
                raise RuntimeError("acquire_only_start_failed:%s" % start.get("msg"))
            episode_result = wait_for_episode(args, "run", run_before, args.max_episode_s)
            cycle["episode"] = episode_result
            episode_stop = stop_verified(args, "cycle_%02d_post_episode" % index)
            cycle["episode_stop"] = episode_stop
            if not episode_stop.get("pass"):
                raise RuntimeError("post_episode_stop_unverified")
            episode_ok, episode_issues = episode_qualifies(episode_result["summary"])
            cycle["issues"].extend(episode_issues)
            cycle["trace"] = pull_trace(args, episode_result["summary"], cycle_dir)
            if not cycle["trace"].get("pass"):
                cycle["issues"].append("trace_pull_failed")

            reset_before = output_set(args.dashboard_run_dir, "reset")
            reset_start = http_json(args.dashboard_url, "/reset", method="POST", timeout_s=10.0)
            cycle["reset_start_response"] = reset_start
            if reset_start.get("ok") is not True:
                raise RuntimeError("reset_start_failed:%s" % reset_start.get("msg"))
            reset_result = wait_for_episode(args, "reset", reset_before, args.max_reset_s)
            cycle["reset"] = reset_result
            reset_stop = stop_verified(args, "cycle_%02d_post_reset" % index)
            cycle["reset_stop"] = reset_stop
            if not reset_stop.get("pass"):
                raise RuntimeError("post_reset_stop_unverified")
            reset_ok, reset_issues = reset_qualifies(reset_result["summary"])
            cycle["issues"].extend(reset_issues)
            capture_raw_frame(args, cycle_dir / "post_reset_raw.jpg")
            post_probe = run_onboard_probe(args, cycle_dir, "post_reset_probe")
            cycle["post_reset_probe"] = post_probe
            reset_geometry_ok, reset_geometry_issues = geometry_matches(baseline, post_probe, args)
            cycle["issues"].extend(reset_geometry_issues)
            cycle["pass"] = bool(
                episode_ok and reset_ok and reset_geometry_ok and cycle["trace"].get("pass")
                and not cycle["issues"]
            )
            cycle["finished_utc"] = utc_now()
            write_json(cycle_dir / "cycle_summary.json", cycle)
            if not cycle["pass"]:
                raise RuntimeError("cycle_gate_failed")

        result["stop_reason"] = "requested_cycles_complete"
        result["pass"] = True
    except Exception as exc:
        result["issues"].append(repr(exc))
        result["stop_reason"] = "campaign_failed"
    finally:
        result["final_stop"] = stop_verified(args, "campaign_final")
        if not result["final_stop"].get("pass"):
            result["issues"].append("final_stop_unverified")
            result["pass"] = False
        result["finished_utc"] = utc_now()
        write_json(args.artifact_dir / "campaign_summary.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8791")
    parser.add_argument("--bridge-url", default="http://192.168.1.11:8765")
    parser.add_argument("--robot-host", default="192.168.1.11")
    parser.add_argument("--robot-user", default="jetson")
    parser.add_argument("--dashboard-run-dir", type=Path, default=Path("artifacts/session/dashboard_runs"))
    parser.add_argument("--artifact-dir", type=Path,
                        default=Path("artifacts/session") / ("hardware_unattended_%s" % utc_stamp()))
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--execute-motion", action="store_true")
    parser.add_argument("--confirm-owner-unattended", action="store_true")
    parser.add_argument("--room-isolated", action="store_true")
    parser.add_argument("--stop-file", type=Path, default=Path("artifacts/session/HARDWARE_STOP"))
    parser.add_argument("--expected-case", choices=["any", "center", "mid-left", "mid-right", "far-left", "far-right"],
                        default="far-left")
    parser.add_argument("--range-min-m", type=float, default=0.35)
    parser.add_argument("--range-max-m", type=float, default=1.20)
    parser.add_argument("--probe-frames", type=int, default=5)
    parser.add_argument("--min-probe-detections", type=int, default=3)
    parser.add_argument("--min-probe-confidence", type=float, default=0.70)
    parser.add_argument("--probe-timeout-s", type=float, default=45.0)
    parser.add_argument("--reset-error-tolerance", type=float, default=0.25)
    parser.add_argument("--reset-range-tolerance-m", type=float, default=0.25)
    parser.add_argument("--max-episode-s", type=float, default=25.0)
    parser.add_argument("--max-reset-s", type=float, default=25.0)
    parser.add_argument("--poll-interval-s", type=float, default=0.20)
    parser.add_argument("--max-camera-age-s", type=float, default=1.0)
    parser.add_argument("--max-motor-abs", type=float, default=0.36)
    parser.add_argument("--pretty", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
