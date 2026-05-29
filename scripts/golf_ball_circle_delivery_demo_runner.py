#!/usr/bin/env python3
"""Dashboard-backed golf-ball circle delivery UAT runner."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from passive_ball_roll_calibration_runner import DEFAULT_DASHBOARD_URL
from passive_ball_roll_calibration_runner import DEFAULT_WORLD_NAME
from passive_ball_roll_calibration_runner import dashboard_state
from passive_ball_roll_calibration_runner import discover_compose_project
from passive_ball_roll_calibration_runner import docker_exec
from passive_ball_roll_calibration_runner import remove_model
from passive_ball_roll_calibration_runner import spawn_model


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
DEFAULT_BALL_SDF = REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf"
DEFAULT_ZONE_SDF = REPO_ROOT / "ros2_config" / "golf_ball_delivery_zone_marker.sdf"
DEFAULT_BALL_MODEL_NAME = "visit_mission_target_ball_1"
DEFAULT_ZONE_MODEL_NAME = "golf_ball_delivery_zone"
DEFAULT_ROBOT_MODEL_NAME = "jetbot"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_target_layout(args: argparse.Namespace) -> dict[str, Any]:
    raw_path = str(getattr(args, "target_layout_json", "") or "").strip()
    if not raw_path:
        return {}
    layout_path = Path(raw_path)
    if not layout_path.is_absolute():
        layout_path = REPO_ROOT / layout_path
    layout = read_json(layout_path)
    targets = layout.get("targets", []) if isinstance(layout, dict) else []
    target = targets[0] if targets and isinstance(targets[0], dict) else {}
    if not target:
        raise ValueError(f"Target layout has no target entries: {layout_path}")
    args.ball_x = float(target.get("forward_m", args.ball_x))
    args.ball_y = float(target.get("lateral_m", args.ball_y))
    args.ball_z = float(target.get("z_m", args.ball_z))
    return {
        "path": str(layout_path),
        "layout_family": str(layout.get("layout_family", "")),
        "random_draw": layout.get("random_draw", {}) if isinstance(layout.get("random_draw"), dict) else {},
        "target": target,
    }


def set_model_pose(
    *,
    compose_project: str,
    world_name: str,
    model_name: str,
    x: float,
    y: float,
    z: float,
    yaw: float = 0.0,
) -> dict[str, Any]:
    half_yaw = 0.5 * yaw
    qz = math.sin(half_yaw)
    qw = math.cos(half_yaw)
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
MODEL_NAME={json.dumps(model_name)}
MODEL_X={json.dumps(f"{x:.6f}")}
MODEL_Y={json.dumps(f"{y:.6f}")}
MODEL_Z={json.dumps(f"{z:.6f}")}
MODEL_QZ={json.dumps(f"{qz:.6f}")}
MODEL_QW={json.dumps(f"{qw:.6f}")}
gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" position {{ x: $MODEL_X y: $MODEL_Y z: $MODEL_Z }} orientation {{ x: 0 y: 0 z: $MODEL_QZ w: $MODEL_QW }}"
"""
    rc, output = docker_exec(compose_project, script, timeout_s=10.0)
    return {
        "model_name": model_name,
        "pose": {"x": x, "y": y, "z": z, "yaw": yaw},
        "returncode": rc,
        "output": output,
        "pass": rc == 0 and "data: true" in output,
    }


def docker_exec_service(compose_project: str, service: str, script: str, *, timeout_s: float = 60.0) -> tuple[int, str]:
    completed = subprocess.run(
        ["docker", "compose", "-p", compose_project, "exec", "-T", service, "bash", "-lc", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def normalize_angle_rad(angle_rad: float) -> float:
    return math.atan2(math.sin(float(angle_rad)), math.cos(float(angle_rad)))


def quaternion_yaw_rad(orientation: dict[str, Any]) -> float:
    try:
        x = float(orientation.get("x", 0.0) or 0.0)
        y = float(orientation.get("y", 0.0) or 0.0)
        z = float(orientation.get("z", 0.0) or 0.0)
        w = float(orientation.get("w", 1.0) or 1.0)
    except (TypeError, ValueError):
        return 0.0
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def pose_xy_yaw(pose: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(pose, dict):
        return None
    position = pose.get("position") if isinstance(pose.get("position"), dict) else pose
    if not isinstance(position, dict):
        return None
    try:
        x = float(position.get("x", 0.0) or 0.0)
        y = float(position.get("y", 0.0) or 0.0)
        z = float(position.get("z", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if "yaw" in pose:
        try:
            yaw = float(pose.get("yaw", 0.0) or 0.0)
        except (TypeError, ValueError):
            yaw = 0.0
    else:
        orientation = pose.get("orientation") if isinstance(pose.get("orientation"), dict) else {}
        yaw = quaternion_yaw_rad(orientation)
    return {"x": x, "y": y, "z": z, "yaw": yaw}


def signed_lateral_error_m(point_x: float, point_y: float, *, origin_x: float, origin_y: float, line_yaw_rad: float) -> float:
    dx = float(point_x) - float(origin_x)
    dy = float(point_y) - float(origin_y)
    return -math.sin(line_yaw_rad) * dx + math.cos(line_yaw_rad) * dy


def collect_contact_samples(
    *,
    compose_project: str,
    world_name: str,
    robot_model_name: str,
    ball_model_name: str,
    duration_s: float,
    poll_period_s: float,
) -> list[dict[str, Any]]:
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
export WORLD_NAME={json.dumps(world_name)}
export ROBOT_MODEL_NAME={json.dumps(robot_model_name)}
export BALL_MODEL_NAME={json.dumps(ball_model_name)}
export DURATION_S={json.dumps(f"{duration_s:.6f}")}
export POLL_PERIOD_S={json.dumps(f"{poll_period_s:.6f}")}
python3 - <<'PY'
import json
import math
import os
import subprocess
import time

import sys
sys.path.insert(0, "/workspaces/chasecar/scripts")
from sim_truth_probe import parse_pose_message

world_name = os.environ["WORLD_NAME"]
robot_model_name = os.environ["ROBOT_MODEL_NAME"]
ball_model_name = os.environ["BALL_MODEL_NAME"]
duration_s = float(os.environ["DURATION_S"])
poll_period_s = float(os.environ["POLL_PERIOD_S"])
topic = f"/world/{{world_name}}/dynamic_pose/info"
started = time.monotonic()
deadline = started + max(duration_s, 0.1)
index = 0

def yaw_from_orientation(orientation):
    try:
        x = float(orientation.get("x", 0.0) or 0.0)
        y = float(orientation.get("y", 0.0) or 0.0)
        z = float(orientation.get("z", 0.0) or 0.0)
        w = float(orientation.get("w", 1.0) or 1.0)
    except Exception:
        return 0.0
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))

def convert_pose(pose):
    if not pose:
        return None
    position = pose.get("position") if isinstance(pose.get("position"), dict) else {{}}
    orientation = pose.get("orientation") if isinstance(pose.get("orientation"), dict) else {{}}
    return {{
        "name": pose.get("name", ""),
        "position": position,
        "orientation": orientation,
        "yaw": yaw_from_orientation(orientation),
    }}

while time.monotonic() < deadline:
    tick_started = time.monotonic()
    record = {{
        "sample_index": index,
        "t_s": round(tick_started - started, 6),
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
            poses = parse_pose_message(completed.stdout or "")
            robot_pose = next((item for item in poses if item.get("name") == robot_model_name), None)
            ball_pose = next((item for item in poses if item.get("name") == ball_model_name), None)
            record["robot_pose"] = convert_pose(robot_pose)
            record["ball_pose"] = convert_pose(ball_pose)
    except Exception as exc:
        record["error"] = str(exc)
    print(json.dumps(record, sort_keys=True), flush=True)
    index += 1
    elapsed = time.monotonic() - tick_started
    if elapsed < poll_period_s:
        time.sleep(poll_period_s - elapsed)
PY
"""
    rc, output = docker_exec(compose_project, script, timeout_s=duration_s + 30.0)
    samples: list[dict[str, Any]] = []
    for line in output.splitlines():
        text = line.strip()
        if not text or not text.startswith("{"):
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and (isinstance(row.get("robot_pose"), dict) or isinstance(row.get("ball_pose"), dict)):
            samples.append(row)
    if rc != 0 and not samples:
        raise RuntimeError(output.strip() or "failed to sample Gazebo pose topic")
    return samples


def ball_samples_from_contact_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        ball_pose = sample.get("ball_pose") if isinstance(sample.get("ball_pose"), dict) else {}
        position = ball_pose.get("position") if isinstance(ball_pose.get("position"), dict) else {}
        if not isinstance(position, dict):
            continue
        rows.append(
            {
                "sample_index": sample.get("sample_index"),
                "t_s": sample.get("t_s"),
                "topic_ok": sample.get("topic_ok", False),
                "model_name": sample.get("ball_model_name", DEFAULT_BALL_MODEL_NAME),
                "position": position,
                "orientation": ball_pose.get("orientation") if isinstance(ball_pose.get("orientation"), dict) else {},
            }
        )
    return rows


def _sign_changes(values: list[float], *, threshold: float) -> int:
    signs: list[int] = []
    for value in values:
        if abs(value) < threshold:
            continue
        signs.append(1 if value > 0.0 else -1)
    collapsed: list[int] = []
    for sign in signs:
        if not collapsed or collapsed[-1] != sign:
            collapsed.append(sign)
    return max(0, len(collapsed) - 1)


def build_approach_contact_metrics(
    samples: list[dict[str, Any]],
    *,
    ball_start_x: float,
    ball_start_y: float,
    target_x: float,
    target_y: float,
    motion_threshold_m: float = 0.005,
    lateral_threshold_m: float = 0.030,
    yaw_threshold_deg: float = 3.0,
    contact_angle_threshold_deg: float = 5.0,
    ball_lateral_threshold_m: float = 0.030,
    oscillation_yaw_threshold_deg: float = 0.5,
) -> dict[str, Any]:
    line_yaw = math.atan2(float(target_y) - float(ball_start_y), float(target_x) - float(ball_start_x))
    yaw_threshold_rad = math.radians(float(yaw_threshold_deg))
    oscillation_threshold_rad = math.radians(float(oscillation_yaw_threshold_deg))
    parsed: list[dict[str, Any]] = []
    for sample in samples:
        robot_pose = pose_xy_yaw(sample.get("robot_pose") if isinstance(sample.get("robot_pose"), dict) else None)
        ball_pose = pose_xy_yaw(sample.get("ball_pose") if isinstance(sample.get("ball_pose"), dict) else None)
        if robot_pose is None and ball_pose is None:
            continue
        row = {"t_s": float(sample.get("t_s", 0.0) or 0.0), "robot_pose": robot_pose, "ball_pose": ball_pose}
        if robot_pose is not None:
            row["robot_lateral_error_m"] = signed_lateral_error_m(
                robot_pose["x"],
                robot_pose["y"],
                origin_x=ball_start_x,
                origin_y=ball_start_y,
                line_yaw_rad=line_yaw,
            )
            row["robot_yaw_error_rad"] = normalize_angle_rad(robot_pose["yaw"] - line_yaw)
        if ball_pose is not None:
            row["ball_lateral_error_m"] = signed_lateral_error_m(
                ball_pose["x"],
                ball_pose["y"],
                origin_x=ball_start_x,
                origin_y=ball_start_y,
                line_yaw_rad=line_yaw,
            )
            row["ball_displacement_m"] = math.hypot(ball_pose["x"] - ball_start_x, ball_pose["y"] - ball_start_y)
        parsed.append(row)

    first_contact_index: int | None = None
    for index, row in enumerate(parsed):
        if float(row.get("ball_displacement_m", 0.0) or 0.0) >= float(motion_threshold_m):
            first_contact_index = index
            break
    pre_contact = parsed[: first_contact_index + 1] if first_contact_index is not None else parsed
    robot_pre = [row for row in pre_contact if isinstance(row.get("robot_pose"), dict)]
    ball_rows = [row for row in parsed if isinstance(row.get("ball_pose"), dict)]
    lateral_errors = [float(row.get("robot_lateral_error_m", 0.0) or 0.0) for row in robot_pre]
    yaw_errors = [float(row.get("robot_yaw_error_rad", 0.0) or 0.0) for row in robot_pre]
    ball_lateral_errors = [float(row.get("ball_lateral_error_m", 0.0) or 0.0) for row in ball_rows]

    first_contact_row = parsed[first_contact_index] if first_contact_index is not None else {}
    first_contact_robot = first_contact_row.get("robot_pose") if isinstance(first_contact_row.get("robot_pose"), dict) else {}
    first_contact_ball = first_contact_row.get("ball_pose") if isinstance(first_contact_row.get("ball_pose"), dict) else {}
    first_contact_lateral = float(first_contact_row.get("robot_lateral_error_m", 0.0) or 0.0) if first_contact_row else None
    first_contact_yaw = float(first_contact_row.get("robot_yaw_error_rad", 0.0) or 0.0) if first_contact_row else None
    first_contact_ball_lateral = float(first_contact_row.get("ball_lateral_error_m", 0.0) or 0.0) if first_contact_row else None

    contact_angle_rad: float | None = None
    if first_contact_index is not None:
        contact_window = parsed[first_contact_index:]
        endpoint = max(contact_window, key=lambda row: float(row.get("ball_displacement_m", 0.0) or 0.0), default={})
        endpoint_ball = endpoint.get("ball_pose") if isinstance(endpoint.get("ball_pose"), dict) else None
        if endpoint_ball is not None:
            dx = float(endpoint_ball["x"]) - float(ball_start_x)
            dy = float(endpoint_ball["y"]) - float(ball_start_y)
            if math.hypot(dx, dy) >= float(motion_threshold_m):
                contact_angle_rad = normalize_angle_rad(math.atan2(dy, dx) - line_yaw)

    max_abs_lateral = max((abs(value) for value in lateral_errors), default=0.0)
    max_abs_yaw = max((abs(value) for value in yaw_errors), default=0.0)
    max_abs_ball_lateral = max((abs(value) for value in ball_lateral_errors), default=0.0)
    yaw_sign_changes = _sign_changes(yaw_errors, threshold=oscillation_threshold_rad)
    flags: list[str] = []
    if not parsed:
        flags.append("missing_contact_trace")
    if first_contact_index is None:
        flags.append("missing_first_contact_motion")
    if max_abs_lateral > float(lateral_threshold_m):
        flags.append("pre_contact_lateral_error")
    if max_abs_yaw > yaw_threshold_rad:
        flags.append("pre_contact_yaw_error")
    if yaw_sign_changes > 1:
        flags.append("pre_contact_yaw_oscillation")
    if max_abs_ball_lateral > float(ball_lateral_threshold_m):
        flags.append("ball_lateral_knock_away")
    if contact_angle_rad is not None and abs(contact_angle_rad) > math.radians(float(contact_angle_threshold_deg)):
        flags.append("contact_trajectory_angle_error")

    return {
        "observed": bool(parsed),
        "stable_contact_approach_pass": not flags,
        "flags": flags,
        "contact_line_yaw_deg": round(math.degrees(line_yaw), 6),
        "sample_count": len(parsed),
        "first_contact_index": first_contact_index,
        "first_contact_t_s": round(float(first_contact_row.get("t_s", 0.0) or 0.0), 6) if first_contact_row else None,
        "first_contact_robot_pose": first_contact_robot,
        "first_contact_ball_pose": first_contact_ball,
        "first_contact_robot_lateral_error_m": round(first_contact_lateral, 6) if first_contact_lateral is not None else None,
        "first_contact_robot_yaw_error_deg": round(math.degrees(first_contact_yaw), 6) if first_contact_yaw is not None else None,
        "first_contact_ball_lateral_error_m": round(first_contact_ball_lateral, 6) if first_contact_ball_lateral is not None else None,
        "max_abs_robot_lateral_error_pre_contact_m": round(float(max_abs_lateral), 6),
        "max_abs_robot_yaw_error_pre_contact_deg": round(math.degrees(float(max_abs_yaw)), 6),
        "robot_yaw_error_sign_changes_pre_contact": yaw_sign_changes,
        "max_abs_ball_lateral_error_m": round(float(max_abs_ball_lateral), 6),
        "contact_trajectory_angle_error_deg": (
            round(math.degrees(float(contact_angle_rad)), 6) if contact_angle_rad is not None else None
        ),
        "thresholds": {
            "motion_threshold_m": round(float(motion_threshold_m), 6),
            "lateral_threshold_m": round(float(lateral_threshold_m), 6),
            "yaw_threshold_deg": round(float(yaw_threshold_deg), 6),
            "contact_angle_threshold_deg": round(float(contact_angle_threshold_deg), 6),
            "ball_lateral_threshold_m": round(float(ball_lateral_threshold_m), 6),
            "oscillation_yaw_threshold_deg": round(float(oscillation_yaw_threshold_deg), 6),
        },
    }


def start_robot_drive(
    *,
    compose_project: str,
    linear_x_mps: float,
    angular_z_rps: float,
    duration_s: float,
) -> subprocess.Popen[str]:
    msg = (
        "{header: {frame_id: base_link}, twist: {linear: {x: "
        f"{linear_x_mps:.6f}"
        ", y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: "
        f"{angular_z_rps:.6f}"
        "}}}"
    )
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
timeout {max(float(duration_s), 0.1):.3f}s ros2 topic pub -r 20 /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped {json.dumps(msg)}
"""
    return subprocess.Popen(
        ["docker", "compose", "-p", compose_project, "exec", "-T", "gate-stack", "bash", "-lc", script],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def publish_zero_stop(compose_project: str) -> dict[str, Any]:
    msg = "{header: {frame_id: base_link}, twist: {linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}}"
    script = f"""
set +e
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped {json.dumps(msg)}
"""
    rc, output = docker_exec_service(compose_project, "gate-stack", script, timeout_s=10.0)
    return {"returncode": rc, "output": output, "pass": rc == 0}


def update_runtime(path_raw: str, **updates: Any) -> None:
    if not path_raw:
        return
    path = Path(path_raw)
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except json.JSONDecodeError:
            payload = {}
    payload.update(updates)
    payload["updated_utc"] = utc_now()
    write_json(path, payload)


def point_segment_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def build_shot_outcome(
    samples: list[dict[str, Any]],
    *,
    target_x: float,
    target_y: float,
    target_z: float,
    radius_m: float,
) -> dict[str, Any]:
    point = (float(target_x), float(target_y))
    closest = None
    closest_pose: dict[str, Any] = {}
    previous_xy: tuple[float, float] | None = None
    ball_poses: list[dict[str, Any]] = []
    for sample in samples:
        position = sample.get("position") if isinstance(sample.get("position"), dict) else {}
        if not isinstance(position, dict):
            continue
        try:
            current_xy = (float(position.get("x")), float(position.get("y")))
        except (TypeError, ValueError):
            continue
        ball_poses.append({"x": current_xy[0], "y": current_xy[1], "z": float(position.get("z", 0.0) or 0.0)})
        distance = math.hypot(current_xy[0] - point[0], current_xy[1] - point[1])
        if previous_xy is not None:
            distance = min(distance, point_segment_distance(point, previous_xy, current_xy))
        if closest is None or distance < closest:
            closest = distance
            closest_pose = dict(ball_poses[-1])
        previous_xy = current_xy
    start_pose = ball_poses[0] if ball_poses else {}
    end_pose = ball_poses[-1] if ball_poses else {}
    final_distance = (
        math.hypot(float(end_pose.get("x", 0.0)) - point[0], float(end_pose.get("y", 0.0)) - point[1])
        if end_pose
        else None
    )
    pass_flag = bool(closest is not None and closest <= radius_m)
    return {
        "observed": bool(ball_poses),
        "pass": pass_flag,
        "reason": "trajectory_intersects_delivery_radius" if pass_flag else "missed_delivery_radius",
        "fetch_pose_world": {
            "x": round(target_x, 6),
            "y": round(target_y, 6),
            "z": round(target_z, 6),
            "radius_m": round(radius_m, 6),
        },
        "delivery_radius_m": round(radius_m, 6),
        "sample_count": len(ball_poses),
        "ball_start_pose": start_pose,
        "ball_end_pose": end_pose,
        "distance_to_fetch_pose_m": round(float(final_distance), 6) if final_distance is not None else None,
        "closest_approach_distance_m": round(float(closest), 6) if closest is not None else None,
        "closest_pose": closest_pose,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the golf-ball circle delivery dashboard demo.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--world-name", default=DEFAULT_WORLD_NAME)
    parser.add_argument("--world-file", default="yolo_test_world_v6_calibrated_golf_turf.world")
    parser.add_argument("--surface-profile", default="calibrated_golf_turf")
    parser.add_argument("--scenario-id", default="golf_ball_circle_delivery_uat")
    parser.add_argument("--scenario-label", default="Golf Ball Circle Delivery")
    parser.add_argument("--mission-objective", default="fetch_to_pose")
    parser.add_argument("--target-model-sdf", default=str(DEFAULT_BALL_SDF))
    parser.add_argument("--zone-model-sdf", default=str(DEFAULT_ZONE_SDF))
    parser.add_argument("--robot-model-name", default=DEFAULT_ROBOT_MODEL_NAME)
    parser.add_argument("--target-model-name", default=DEFAULT_BALL_MODEL_NAME)
    parser.add_argument("--zone-model-name", default=DEFAULT_ZONE_MODEL_NAME)
    parser.add_argument("--target-layout-json", default="")
    parser.add_argument("--visit-runtime-json", default="")
    parser.add_argument("--gather-runtime-json", default="")
    parser.add_argument("--artifact-kind", default="golf_ball_circle_delivery")
    parser.add_argument("--robot-x", type=float, default=0.06)
    parser.add_argument("--robot-y", type=float, default=0.0)
    parser.add_argument("--robot-yaw", type=float, default=0.0)
    parser.add_argument("--ball-x", type=float, default=0.38)
    parser.add_argument("--ball-y", type=float, default=0.0)
    parser.add_argument("--ball-z", type=float, default=0.021336)
    parser.add_argument("--zone-x", type=float, default=0.95)
    parser.add_argument("--zone-y", type=float, default=0.0)
    parser.add_argument("--zone-z", type=float, default=0.001)
    parser.add_argument("--fetch-target-x", type=float, default=None)
    parser.add_argument("--fetch-target-y", type=float, default=None)
    parser.add_argument("--fetch-target-z", type=float, default=None)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=0.30)
    parser.add_argument("--drive-linear-x-mps", type=float, default=0.12)
    parser.add_argument("--drive-duration-s", type=float, default=7.0)
    parser.add_argument("--sample-duration-s", type=float, default=9.0)
    parser.add_argument("--poll-period-s", type=float, default=0.10)
    parser.add_argument("--first-contact-motion-threshold-m", type=float, default=0.005)
    parser.add_argument("--approach-lateral-threshold-m", type=float, default=0.030)
    parser.add_argument("--approach-yaw-threshold-deg", type=float, default=3.0)
    parser.add_argument("--contact-angle-threshold-deg", type=float, default=5.0)
    parser.add_argument("--ball-lateral-threshold-m", type=float, default=0.030)
    parser.add_argument("--oscillation-yaw-threshold-deg", type=float, default=0.5)
    parser.add_argument("--keep-environment", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_layout = apply_target_layout(args)
    if args.fetch_target_x is not None:
        args.zone_x = args.fetch_target_x
    if args.fetch_target_y is not None:
        args.zone_y = args.fetch_target_y
    if args.fetch_target_z is not None:
        args.zone_z = args.fetch_target_z
    state = dashboard_state(args.dashboard_url)
    args.compose_project = args.compose_project or str(state.get("compose_project", "") or state.get("launcher_project", "") or "")
    if not args.compose_project:
        args.compose_project = discover_compose_project(args.dashboard_url)
    if not args.compose_project:
        raise SystemExit("Unable to discover compose project; pass --compose-project.")
    session_id = str(state.get("session_id", "") or make_session_id())
    artifact_dir = SESSION_ROOT / session_id / args.artifact_kind / make_session_id()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    trace_path = artifact_dir / "ball_trace.jsonl"
    contact_trace_path = artifact_dir / "contact_trace.jsonl"

    update_runtime(
        args.gather_runtime_json,
        mission_status="running",
        mission_phase="setup",
        gather_phase="setup",
        proof_state="visiting",
        surface_profile=args.surface_profile,
        current_target_id="ball_1",
        latest_feedback="Spawning calibrated golf ball and delivery circle.",
    )
    update_runtime(
        args.visit_runtime_json,
        mission_status="running",
        mission_phase="setup",
        proof_state="visiting",
        current_target_id="ball_1",
        latest_feedback="Preparing golf-ball circle delivery demo.",
    )

    remove_model(compose_project=args.compose_project, world_name=args.world_name, model_name=args.target_model_name)
    remove_model(compose_project=args.compose_project, world_name=args.world_name, model_name=args.zone_model_name)
    spawn_zone = spawn_model(
        compose_project=args.compose_project,
        world_name=args.world_name,
        model_sdf=Path(args.zone_model_sdf),
        model_name=args.zone_model_name,
        x=args.zone_x,
        y=args.zone_y,
        z=args.zone_z,
    )
    spawn_ball = spawn_model(
        compose_project=args.compose_project,
        world_name=args.world_name,
        model_sdf=Path(args.target_model_sdf),
        model_name=args.target_model_name,
        x=args.ball_x,
        y=args.ball_y,
        z=args.ball_z,
    )
    robot_pose = set_model_pose(
        compose_project=args.compose_project,
        world_name=args.world_name,
        model_name="jetbot",
        x=args.robot_x,
        y=args.robot_y,
        z=0.0,
        yaw=args.robot_yaw,
    )
    write_json(
        artifact_dir / "spawn_summary.json",
        {
            "zone": spawn_zone,
            "ball": spawn_ball,
            "robot_pose": robot_pose,
            "target_layout": target_layout,
        },
    )
    if not spawn_zone.get("pass") or not spawn_ball.get("pass") or not robot_pose.get("pass"):
        raise RuntimeError(f"Demo spawn failed; see {artifact_dir / 'spawn_summary.json'}")

    update_runtime(
        args.gather_runtime_json,
        mission_phase="fetch_to_pose",
        gather_phase="fetch_to_pose",
        proof_state="fetching",
        zone_pose={"x": args.zone_x, "y": args.zone_y, "z": args.zone_z, "radius_m": args.fetch_delivery_radius_m},
        latest_feedback="Driving the robot forward to collect and deliver the golf ball.",
    )
    drive_proc = start_robot_drive(
        compose_project=args.compose_project,
        linear_x_mps=args.drive_linear_x_mps,
        angular_z_rps=0.0,
        duration_s=args.drive_duration_s,
    )
    try:
        contact_samples = collect_contact_samples(
            compose_project=args.compose_project,
            world_name=args.world_name,
            robot_model_name=args.robot_model_name,
            ball_model_name=args.target_model_name,
            duration_s=args.sample_duration_s,
            poll_period_s=args.poll_period_s,
        )
    finally:
        try:
            drive_output, _ = drive_proc.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            drive_proc.terminate()
            drive_output, _ = drive_proc.communicate(timeout=2.0)
        stop_payload = publish_zero_stop(args.compose_project)

    samples = ball_samples_from_contact_samples(contact_samples)
    append_jsonl(trace_path, samples)
    append_jsonl(contact_trace_path, contact_samples)
    shot_outcome = build_shot_outcome(
        samples,
        target_x=args.zone_x,
        target_y=args.zone_y,
        target_z=args.zone_z,
        radius_m=args.fetch_delivery_radius_m,
    )
    approach_metrics = build_approach_contact_metrics(
        contact_samples,
        ball_start_x=args.ball_x,
        ball_start_y=args.ball_y,
        target_x=args.zone_x,
        target_y=args.zone_y,
        motion_threshold_m=args.first_contact_motion_threshold_m,
        lateral_threshold_m=args.approach_lateral_threshold_m,
        yaw_threshold_deg=args.approach_yaw_threshold_deg,
        contact_angle_threshold_deg=args.contact_angle_threshold_deg,
        ball_lateral_threshold_m=args.ball_lateral_threshold_m,
        oscillation_yaw_threshold_deg=args.oscillation_yaw_threshold_deg,
    )
    pass_flag = bool(shot_outcome.get("pass", False))
    mission_time_s = max(float(args.sample_duration_s), float(args.drive_duration_s))
    target_result = {
        "target_id": "ball_1",
        "mission_completed_pass": pass_flag,
        "pre_stage_handoff_pass": True,
        "capture_entry_reached": True,
        "fetch_to_pose_reached": pass_flag,
        "fetch_to_pose_pass": pass_flag,
        "fetch_to_pose_time_s": round(mission_time_s, 6),
        "fetch_to_pose_failure_reason": "" if pass_flag else str(shot_outcome.get("reason", "missed_delivery_radius")),
        "shot_outcome": shot_outcome,
        "approach_contact_metrics": approach_metrics,
    }
    verdict = {
        "type": "gather_mission",
        "scenario_id": args.scenario_id,
        "scenario_label": args.scenario_label,
        "mission_objective": "fetch_to_pose",
        "surface_profile": args.surface_profile,
        "world_file": args.world_file,
        "target_model_sdf": args.target_model_sdf,
        "zone_model_sdf": args.zone_model_sdf,
        "pass": pass_flag,
        "mission_completed_pass": pass_flag,
        "fetch_to_pose_reached": pass_flag,
        "fetch_to_pose_pass": pass_flag,
        "fetch_delivery_radius_m": round(float(args.fetch_delivery_radius_m), 6),
        "fetch_pose_world": shot_outcome["fetch_pose_world"],
        "target_layout_json": str(args.target_layout_json or ""),
        "target_layout": target_layout,
        "shot_outcome": shot_outcome,
        "approach_contact_metrics": approach_metrics,
        "mission_time_s": round(mission_time_s, 6),
        "artifact_dir": str(artifact_dir),
    }
    summary = {
        **verdict,
        "runs": 1,
        "pass_count": 1 if pass_flag else 0,
        "fail_count": 0 if pass_flag else 1,
        "fetch_to_pose_pass_count": 1 if pass_flag else 0,
        "fetch_to_pose_fail_count": 0 if pass_flag else 1,
        "target_results_path": str(artifact_dir / "target_results.json"),
        "mission_verdict_path": str(artifact_dir / "mission_verdict.json"),
        "trace_path": str(trace_path),
        "contact_trace_path": str(contact_trace_path),
        "approach_metrics_path": str(artifact_dir / "approach_metrics.json"),
    }
    target_results = {"ball_1": target_result}
    scorecard = "\n".join(
        [
            "# Golf Ball Circle Delivery UAT",
            "",
            f"- Pass: `{pass_flag}`",
            f"- Closest approach: `{float(shot_outcome.get('closest_approach_distance_m', 0.0) or 0.0):.3f}m`",
            f"- Delivery radius: `{float(args.fetch_delivery_radius_m):.3f}m`",
            f"- Stable contact approach: `{bool(approach_metrics.get('stable_contact_approach_pass', False))}`",
            f"- Approach flags: `{approach_metrics.get('flags', [])}`",
            f"- Ball start: `{shot_outcome.get('ball_start_pose', {})}`",
            f"- Ball end: `{shot_outcome.get('ball_end_pose', {})}`",
            "",
        ]
    )

    write_json(artifact_dir / "drive_summary.json", {"drive_output": drive_output, "stop": stop_payload})
    write_json(artifact_dir / "approach_metrics.json", approach_metrics)
    write_json(artifact_dir / "target_results.json", target_results)
    write_json(artifact_dir / "mission_verdict.json", verdict)
    write_json(artifact_dir / "summary.json", summary)
    (artifact_dir / "scorecard.md").write_text(scorecard, encoding="utf-8")

    update_runtime(
        args.gather_runtime_json,
        mission_status="completed" if pass_flag else "failed",
        mission_phase="completed" if pass_flag else "failed",
        gather_phase="completed" if pass_flag else "failed",
        proof_state="completed" if pass_flag else "failed",
        latest_feedback="Golf ball entered the delivery circle." if pass_flag else "Golf ball missed the delivery circle.",
        mission_verdict=verdict,
        last_fetch_to_pose_result=shot_outcome,
        last_approach_contact_metrics=approach_metrics,
        zone_pose={"x": args.zone_x, "y": args.zone_y, "z": args.zone_z, "radius_m": args.fetch_delivery_radius_m},
        placed_targets=["ball_1"] if pass_flag else [],
        remaining_targets=[] if pass_flag else ["ball_1"],
    )
    update_runtime(
        args.visit_runtime_json,
        mission_status="completed" if pass_flag else "failed",
        mission_phase="completed" if pass_flag else "failed",
        proof_state="completed" if pass_flag else "failed",
        mission_verdict=verdict,
        latest_feedback="Golf ball circle delivery completed." if pass_flag else "Golf ball circle delivery missed.",
    )
    print(f"GATHER_MISSION_SUMMARY={artifact_dir / 'mission_verdict.json'}")
    return 0 if pass_flag else 2


if __name__ == "__main__":
    sys.exit(main())
