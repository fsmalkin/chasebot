#!/usr/bin/env python3
"""External ground-truth scorer for mono fetch runs.

This script samples Gazebo truth from sim-gate and compares it with the mono
node JSONL. It never publishes or feeds truth back into the mono node.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import statistics
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from passive_ball_roll_calibration_runner import DEFAULT_DASHBOARD_URL  # noqa: E402
from passive_ball_roll_calibration_runner import DEFAULT_WORLD_NAME  # noqa: E402
from passive_ball_roll_calibration_runner import discover_compose_project  # noqa: E402
from sim_truth_probe import parse_pose_message  # noqa: E402


DEFAULT_ROBOT_MODEL_NAME = "jetbot"
DEFAULT_BALL_MODEL_NAME = "visit_mission_target_ball_1"
DEFAULT_CONTACT_THRESHOLD_M = 0.14
CONTACT_THRESHOLD_REASON = (
    "JetBot chassis center to golf-ball center at touch is expected around "
    "0.12-0.15 m, including the 0.021 m ball radius; 0.14 m is the default "
    "touch threshold and remains configurable."
)


def yaw_from_orientation(orientation: dict[str, Any] | None) -> float:
    orientation = orientation or {}
    x = float(orientation.get("x", 0.0) or 0.0)
    y = float(orientation.get("y", 0.0) or 0.0)
    z = float(orientation.get("z", 0.0) or 0.0)
    w = float(orientation.get("w", 1.0) or 1.0)
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def convert_pose(pose: dict[str, Any] | None) -> dict[str, Any] | None:
    if not pose:
        return None
    position = pose.get("position") if isinstance(pose.get("position"), dict) else {}
    orientation = pose.get("orientation") if isinstance(pose.get("orientation"), dict) else {}
    return {
        "name": pose.get("name", ""),
        "position": position,
        "orientation": orientation,
        "yaw": yaw_from_orientation(orientation),
    }


def parse_header_stamp_seconds(text: str) -> float | None:
    stack: list[str] = []
    stamp_depth: int | None = None
    sec: float | None = None
    nanosec = 0.0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("{"):
            key = line[:-1].strip()
            stack.append(key)
            if key == "stamp" and stamp_depth is None:
                stamp_depth = len(stack)
            continue
        if line == "}":
            if stamp_depth is not None and len(stack) == stamp_depth:
                break
            if stack:
                stack.pop()
            continue
        if stamp_depth is None or ":" not in line:
            continue
        key, raw_value = [part.strip() for part in line.split(":", 1)]
        try:
            value = float(raw_value)
        except ValueError:
            continue
        if key == "sec":
            sec = value
        elif key in {"nsec", "nanosec"}:
            nanosec = value
    if sec is None:
        return None
    return sec + (nanosec / 1.0e9)


def robot_relative_truth(
    robot_pose: dict[str, Any] | None,
    ball_pose: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not robot_pose or not ball_pose:
        return None
    rp = robot_pose.get("position") if isinstance(robot_pose.get("position"), dict) else {}
    bp = ball_pose.get("position") if isinstance(ball_pose.get("position"), dict) else {}
    rx = float(rp.get("x", 0.0) or 0.0)
    ry = float(rp.get("y", 0.0) or 0.0)
    bx = float(bp.get("x", 0.0) or 0.0)
    by = float(bp.get("y", 0.0) or 0.0)
    dx = bx - rx
    dy = by - ry
    yaw = float(robot_pose.get("yaw", 0.0) or 0.0)
    forward = math.cos(yaw) * dx + math.sin(yaw) * dy
    x_right = math.sin(yaw) * dx - math.cos(yaw) * dy
    distance_xy = math.hypot(dx, dy)
    bearing = math.atan2(x_right, forward) if distance_xy > 0.0 else 0.0
    return {
        "forward_m": round(forward, 6),
        "x_right_m": round(x_right, 6),
        "distance_xy_m": round(distance_xy, 6),
        "bearing_rad_right_positive": round(bearing, 6),
    }


def docker_exec_sim_gate(compose_project: str, script: str, *, timeout_s: float) -> tuple[int, str]:
    cmd = ["docker", "compose", "-p", compose_project, "exec", "-T", "sim-gate", "bash", "-lc", script]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return 124, stdout + stderr + f"\ntimeout_after_s={float(timeout_s):.3f}"
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def collect_truth_samples(args: argparse.Namespace) -> list[dict[str, Any]]:
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
python3 - <<'PY'
import json
import subprocess
import time

world_name = {args.world_name!r}
robot_model_name = {args.robot_model_name!r}
ball_model_name = {args.ball_model_name!r}
duration_s = float({float(args.duration_s)!r})
poll_period_s = float({float(args.poll_period_s)!r})
topic = f"/world/{{world_name}}/pose/info"

def parse_header_stamp_seconds(text):
    stack = []
    stamp_depth = None
    sec = None
    nanosec = 0.0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("{{"):
            key = line[:-1].strip()
            stack.append(key)
            if key == "stamp" and stamp_depth is None:
                stamp_depth = len(stack)
            continue
        if line == "}}":
            if stamp_depth is not None and len(stack) == stamp_depth:
                break
            if stack:
                stack.pop()
            continue
        if stamp_depth is None or ":" not in line:
            continue
        key, raw_value = [part.strip() for part in line.split(":", 1)]
        try:
            value = float(raw_value)
        except ValueError:
            continue
        if key == "sec":
            sec = value
        elif key in {{"nsec", "nanosec"}}:
            nanosec = value
    return None if sec is None else sec + (nanosec / 1.0e9)

started = time.monotonic()
deadline = started + max(duration_s, 0.1)
index = 0
while time.monotonic() < deadline:
    tick_started = time.monotonic()
    record = {{
        "sample_index": index,
        "t_s": round(tick_started - started, 6),
        "wall_time_unix_s": time.time(),
        "topic": topic,
        "topic_ok": False,
        "robot_model_name": robot_model_name,
        "ball_model_name": ball_model_name,
        "robot_pose": None,
        "ball_pose": None,
    }}
    try:
        completed = subprocess.run(
            ["gz", "topic", "-e", "-n", "1", "-t", topic],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        record["topic_ok"] = completed.returncode == 0
        if completed.returncode == 0:
            import sys
            sys.path.insert(0, "/workspaces/chasecar/scripts")
            from sim_truth_probe import parse_pose_message
            record["sim_time_s"] = parse_header_stamp_seconds(completed.stdout or "")
            poses = parse_pose_message(completed.stdout or "")
            record["raw_robot_pose"] = next((p for p in poses if p.get("name") == robot_model_name), None)
            record["raw_ball_pose"] = next((p for p in poses if p.get("name") == ball_model_name), None)
    except Exception as exc:
        record["error"] = str(exc)
    print(json.dumps(record, sort_keys=True), flush=True)
    index += 1
    elapsed = time.monotonic() - tick_started
    if elapsed < poll_period_s:
        time.sleep(poll_period_s - elapsed)
PY
"""
    rc, output = docker_exec_sim_gate(
        args.compose_project,
        script,
        timeout_s=float(args.duration_s) + 30.0,
    )
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        raw_robot = row.pop("raw_robot_pose", None)
        raw_ball = row.pop("raw_ball_pose", None)
        row["robot_pose"] = convert_pose(raw_robot)
        row["ball_pose"] = convert_pose(raw_ball)
        row["relative_truth"] = robot_relative_truth(row["robot_pose"], row["ball_pose"])
        rows.append(row)
    if rc != 0 and not rows:
        raise RuntimeError(output.strip() or "truth_sampling_failed")
    return rows


def read_node_log(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def nearest_node_match(
    truth_row: dict[str, Any],
    node_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float | None, str]:
    if not node_rows:
        return None, None, "none"
    target_sim = truth_row.get("sim_time_s")
    if target_sim is not None:
        rows_with_sim = [row for row in node_rows if row.get("sim_time_s") is not None]
        if rows_with_sim:
            node = min(
                rows_with_sim,
                key=lambda row: abs(float(row.get("sim_time_s", 0.0) or 0.0) - float(target_sim)),
            )
            delta = abs(float(node.get("sim_time_s", 0.0) or 0.0) - float(target_sim))
            return node, delta, "sim_time"
    target_wall = truth_row.get("wall_time_unix_s")
    if target_wall is not None:
        node = min(
            node_rows,
            key=lambda row: abs(float(row.get("wall_time_unix_s", 0.0) or 0.0) - float(target_wall)),
        )
        delta = abs(float(node.get("wall_time_unix_s", 0.0) or 0.0) - float(target_wall))
        return node, delta, "wall_time"
    target_t = float(truth_row.get("t_s", 0.0) or 0.0)
    first_sim = float(node_rows[0].get("sim_time_s", 0.0) or 0.0)
    node = min(node_rows, key=lambda row: abs((float(row.get("sim_time_s", 0.0) or 0.0) - first_sim) - target_t))
    delta = abs((float(node.get("sim_time_s", 0.0) or 0.0) - first_sim) - target_t)
    return node, delta, "elapsed_sim_offset"


def nearest_truth_match(
    node_row: dict[str, Any],
    truth_samples: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float | None, str]:
    if not truth_samples:
        return None, None, "none"
    node_sim = node_row.get("sim_time_s")
    if node_sim is not None:
        rows_with_sim = [row for row in truth_samples if row.get("sim_time_s") is not None]
        if rows_with_sim:
            truth = min(
                rows_with_sim,
                key=lambda row: abs(float(row.get("sim_time_s", 0.0) or 0.0) - float(node_sim)),
            )
            delta = abs(float(truth.get("sim_time_s", 0.0) or 0.0) - float(node_sim))
            return truth, delta, "sim_time"
    node_wall = node_row.get("wall_time_unix_s")
    if node_wall is not None:
        truth = min(
            truth_samples,
            key=lambda row: abs(float(row.get("wall_time_unix_s", 0.0) or 0.0) - float(node_wall)),
        )
        delta = abs(float(truth.get("wall_time_unix_s", 0.0) or 0.0) - float(node_wall))
        return truth, delta, "wall_time"
    return None, None, "none"


def pose_status_expected(mono_pose: dict[str, Any], true_distance_xy_m: float) -> str:
    max_range = mono_pose.get("max_reliable_range_m")
    if max_range is not None and true_distance_xy_m > float(max_range):
        return "bearing_only"
    return "metric"


def _finite_numbers(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return values


def _error_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "rms": None, "median": None, "max_abs": None}
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 6),
        "rms": round(math.sqrt(statistics.fmean([value * value for value in values])), 6),
        "median": round(statistics.median(values), 6),
        "max_abs": round(max(abs(value) for value in values), 6),
    }


def summarize_compared_samples(scored: list[dict[str, Any]]) -> dict[str, Any]:
    compared = [
        row
        for row in scored
        if isinstance(row.get("relative_truth"), dict) and isinstance(row.get("mono_pose"), dict)
    ]
    pose_status_rows = [row for row in compared if row.get("pose_status_correct") is not None]
    pose_status_correct = [row for row in pose_status_rows if bool(row.get("pose_status_correct"))]
    return {
        "compared_count": len(compared),
        "mono_distance_error_m": _error_summary(_finite_numbers(compared, "mono_distance_error_m")),
        "bearing_error_rad": _error_summary(_finite_numbers(compared, "bearing_error_rad")),
        "pose_status_correct_fraction": (
            round(len(pose_status_correct) / len(pose_status_rows), 6) if pose_status_rows else None
        ),
    }


def approach_metrics(
    node_rows: list[dict[str, Any]],
    truth_samples: list[dict[str, Any]],
) -> dict[str, Any]:
    standoff_rows = [
        row
        for row in node_rows
        if isinstance(row.get("action"), dict)
        and row.get("action", {}).get("reason") == "standoff_reached"
    ]
    stop_truth = None
    match_delta_s = None
    match_basis = "none"
    if standoff_rows:
        stop_truth, match_delta_s, match_basis = nearest_truth_match(standoff_rows[0], truth_samples)
    rel = stop_truth.get("relative_truth") if isinstance(stop_truth, dict) and isinstance(stop_truth.get("relative_truth"), dict) else None
    approach_rows = []
    for row in node_rows:
        action = row.get("action") if isinstance(row.get("action"), dict) else {}
        reason = str(action.get("reason") or "")
        phase = str(row.get("phase") or "")
        phase_before = row.get("phase_state_before") if isinstance(row.get("phase_state_before"), dict) else {}
        if (
            phase == "approach"
            or str(phase_before.get("phase") or "") == "approach"
            or reason in {"center_target", "approach", "standoff_reached", "pose_not_metric"}
        ):
            approach_rows.append(row)
    center_errors = []
    for row in approach_rows:
        obs = row.get("observation") if isinstance(row.get("observation"), dict) else {}
        value = obs.get("center_error")
        try:
            center_errors.append(float(value))
        except (TypeError, ValueError):
            continue
    return {
        "reached_standoff": bool(standoff_rows),
        "standoff_tick": standoff_rows[0].get("tick") if standoff_rows else None,
        "true_distance_at_stop_m": (
            round(float(rel.get("distance_xy_m")), 6) if rel and rel.get("distance_xy_m") is not None else None
        ),
        "true_forward_at_stop_m": (
            round(float(rel.get("forward_m")), 6) if rel and rel.get("forward_m") is not None else None
        ),
        "stop_truth_match_delta_s": round(float(match_delta_s), 6) if match_delta_s is not None else None,
        "stop_truth_match_basis": match_basis,
        "centering": {
            "sample_count": len(center_errors),
            "mean_abs_center_error": (
                round(statistics.fmean([abs(value) for value in center_errors]), 6) if center_errors else None
            ),
            "max_abs_center_error": (
                round(max(abs(value) for value in center_errors), 6) if center_errors else None
            ),
            "center_error_at_standoff": (
                standoff_rows[0].get("observation", {}).get("center_error")
                if standoff_rows and isinstance(standoff_rows[0].get("observation"), dict)
                else None
            ),
        },
    }


def score_samples(
    truth_samples: list[dict[str, Any]],
    node_rows: list[dict[str, Any]],
    *,
    contact_threshold_m: float,
    min_truth_coverage_ratio: float,
) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    closest = None
    both_present_count = 0
    for truth in truth_samples:
        rel = truth.get("relative_truth") if isinstance(truth.get("relative_truth"), dict) else None
        if rel:
            both_present_count += 1
        if rel and rel.get("distance_xy_m") is not None:
            dist = float(rel["distance_xy_m"])
            closest = dist if closest is None else min(closest, dist)
        node, match_delta_s, match_basis = nearest_node_match(truth, node_rows)
        mono_pose = node.get("mono_pose") if isinstance(node, dict) and isinstance(node.get("mono_pose"), dict) else None
        row: dict[str, Any] = {
            "sample_index": truth.get("sample_index"),
            "truth_t_s": truth.get("t_s"),
            "truth_sim_time_s": truth.get("sim_time_s"),
            "truth_wall_time_unix_s": truth.get("wall_time_unix_s"),
            "relative_truth": rel,
            "node_tick": node.get("tick") if isinstance(node, dict) else None,
            "node_sim_time_s": node.get("sim_time_s") if isinstance(node, dict) else None,
            "match_delta_s": round(float(match_delta_s), 6) if match_delta_s is not None else None,
            "match_basis": match_basis,
            "mono_pose": mono_pose,
            "action": node.get("action") if isinstance(node, dict) else None,
        }
        if rel and mono_pose:
            true_slant = float(rel.get("distance_xy_m", 0.0) or 0.0)
            true_bearing = float(rel.get("bearing_rad_right_positive", 0.0) or 0.0)
            mono_forward = mono_pose.get("z_m_forward")
            mono_bearing = mono_pose.get("bearing_rad_right_positive")
            if mono_forward is not None:
                row["mono_distance_error_m"] = round(float(mono_forward) - true_slant, 6)
                row["true_slant_range_m"] = round(true_slant, 6)
                row["true_forward_m"] = rel.get("forward_m")
            if mono_bearing is not None:
                row["bearing_error_rad"] = round(float(mono_bearing) - true_bearing, 6)
            expected = pose_status_expected(mono_pose, true_slant)
            row["expected_pose_status"] = expected
            pose_status = str(mono_pose.get("pose_status") or "")
            row["pose_status_correct"] = (
                pose_status == expected
                or (expected == "bearing_only" and pose_status in {"bearing_only", "unavailable"})
            )
        scored.append(row)
    closest_value = float(closest) if closest is not None else None
    total_truth_count = len(truth_samples)
    coverage_ratio = both_present_count / max(total_truth_count, 1)
    contact_metric_conclusive = bool(
        closest_value is not None and coverage_ratio >= float(min_truth_coverage_ratio)
    )
    contact = (
        bool(closest_value <= float(contact_threshold_m))
        if contact_metric_conclusive and closest_value is not None
        else None
    )
    return {
        "samples": scored,
        "sample_count": len(scored),
        "truth_coverage": {
            "samples_with_robot_and_ball": both_present_count,
            "total_samples": total_truth_count,
            "ratio": round(float(coverage_ratio), 6),
            "min_required_ratio": float(min_truth_coverage_ratio),
        },
        "closest_approach_m": round(closest_value, 6) if closest_value is not None else None,
        "contact_threshold_m": float(contact_threshold_m),
        "contact_threshold_reason": CONTACT_THRESHOLD_REASON,
        "contact_metric_conclusive": contact_metric_conclusive,
        "contact": contact,
        "approach": approach_metrics(node_rows, truth_samples),
        "summary": summarize_compared_samples(scored),
        "pass": bool(contact),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--world-name", default=DEFAULT_WORLD_NAME)
    parser.add_argument("--robot-model-name", default=DEFAULT_ROBOT_MODEL_NAME)
    parser.add_argument("--ball-model-name", default=DEFAULT_BALL_MODEL_NAME)
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--poll-period-s", type=float, default=0.1)
    parser.add_argument("--node-log", required=True)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument(
        "--contact-threshold-m",
        type=float,
        default=DEFAULT_CONTACT_THRESHOLD_M,
        help=CONTACT_THRESHOLD_REASON,
    )
    parser.add_argument("--min-truth-coverage-ratio", type=float, default=0.75)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.compose_project:
        args.compose_project = discover_compose_project(args.dashboard_url)
    if not args.compose_project:
        raise SystemExit("compose_project_required")
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else REPO_ROOT / "artifacts" / "session" / ("mono_fetch_scorer_%s" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    truth_samples = collect_truth_samples(args)
    node_rows = read_node_log(Path(args.node_log))
    verdict = {
        "type": "mono_fetch_verdict",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "compose_project": args.compose_project,
        "world_name": args.world_name,
        "robot_model_name": args.robot_model_name,
        "ball_model_name": args.ball_model_name,
        "node_log": str(Path(args.node_log)),
        "truth_samples": truth_samples,
        "node_log_rows": len(node_rows),
        **score_samples(
            truth_samples,
            node_rows,
            contact_threshold_m=float(args.contact_threshold_m),
            min_truth_coverage_ratio=float(args.min_truth_coverage_ratio),
        ),
    }
    output_path = artifact_dir / "mono_fetch_verdict.json"
    verdict["verdict_path"] = str(output_path)
    write_json(output_path, verdict)
    print(json.dumps(verdict, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if verdict.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
