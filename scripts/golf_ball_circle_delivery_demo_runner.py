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
from gather_mission_runner import fetch_model_provenance


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
DEFAULT_BALL_SDF = REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf"
DEFAULT_ZONE_SDF = REPO_ROOT / "ros2_config" / "golf_ball_delivery_zone_marker.sdf"
DEFAULT_BALL_MODEL_NAME = "visit_mission_target_ball_1"
DEFAULT_ZONE_MODEL_NAME = "golf_ball_delivery_zone"
DEFAULT_ROBOT_MODEL_NAME = "jetbot"
NAV2_REPOSITION_RESULT_MARKER = "NAV2_REPOSITION_RESULT="
NAV2_REPOSITION_BEHAVIOR_TREE = "/workspaces/chasecar/ros2_config/behavior_trees/navigate_to_pose_w_replanning.xml"
ROUTE_FETCH_READY = "fetch_ready_local"
ROUTE_NAV2_REPOSITION = "nav2_reposition_first"
ROUTE_RECOVERY_OR_REAIM = "recovery_or_reaim"
ROUTE_EXECUTOR_LOCAL_FETCH = "local_fetch_to_pose"
ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH = "nav2_forward_reposition_then_fetch"
ROUTE_EXECUTOR_RECOVERY = "bounded_recovery_reaim"
EXECUTABLE_PLANNER_FETCH_ROUTES = {ROUTE_FETCH_READY, ROUTE_NAV2_REPOSITION, ROUTE_RECOVERY_OR_REAIM}
NAV2_SETUP_PLANNER_ROUTES = {ROUTE_NAV2_REPOSITION, ROUTE_RECOVERY_OR_REAIM}
ROUTE_EXECUTOR_BY_LABEL = {
    ROUTE_FETCH_READY: ROUTE_EXECUTOR_LOCAL_FETCH,
    ROUTE_NAV2_REPOSITION: ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH,
    ROUTE_RECOVERY_OR_REAIM: ROUTE_EXECUTOR_RECOVERY,
}


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


def transform_point_between_robot_frames(
    *,
    point_pose: dict[str, Any],
    source_robot_pose: dict[str, Any],
    target_robot_pose: dict[str, Any],
) -> dict[str, float]:
    source_x = float(source_robot_pose.get("x", 0.0) or 0.0)
    source_y = float(source_robot_pose.get("y", 0.0) or 0.0)
    source_yaw = float(source_robot_pose.get("yaw", 0.0) or 0.0)
    target_x = float(target_robot_pose.get("x", 0.0) or 0.0)
    target_y = float(target_robot_pose.get("y", 0.0) or 0.0)
    target_yaw = float(target_robot_pose.get("yaw", 0.0) or 0.0)
    point_x = float(point_pose.get("x", 0.0) or 0.0)
    point_y = float(point_pose.get("y", 0.0) or 0.0)
    point_yaw = float(point_pose.get("yaw", 0.0) or 0.0)
    dx = point_x - source_x
    dy = point_y - source_y
    cos_source = math.cos(-source_yaw)
    sin_source = math.sin(-source_yaw)
    local_x = cos_source * dx - sin_source * dy
    local_y = sin_source * dx + cos_source * dy
    cos_target = math.cos(target_yaw)
    sin_target = math.sin(target_yaw)
    return {
        "x": round(target_x + cos_target * local_x - sin_target * local_y, 6),
        "y": round(target_y + sin_target * local_x + cos_target * local_y, 6),
        "yaw": round(normalize_angle_rad(target_yaw + normalize_angle_rad(point_yaw - source_yaw)), 6),
    }


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
    random_draw = layout.get("random_draw", {}) if isinstance(layout.get("random_draw"), dict) else {}
    return {
        "path": str(layout_path),
        "layout_family": str(layout.get("layout_family", "")),
        "random_profile": str(layout.get("random_profile", "") or random_draw.get("random_profile", "")),
        "planner_route_label": str(layout.get("planner_route_label", "") or random_draw.get("planner_route_label", "")),
        "route_executor": str(layout.get("route_executor", "") or random_draw.get("route_executor", "")),
        "random_draw": random_draw,
        "target": target,
    }


def _option_present(explicit_args: set[str], *options: str) -> bool:
    return any(arg == option or arg.startswith(f"{option}=") for arg in explicit_args for option in options)


def _set_route_default(args: argparse.Namespace, explicit_args: set[str], attr: str, value: Any, *options: str) -> None:
    if not _option_present(explicit_args, *options):
        setattr(args, attr, value)


def apply_planner_route_execution_defaults(
    args: argparse.Namespace,
    target_layout: dict[str, Any],
    *,
    explicit_args: set[str] | None = None,
) -> dict[str, Any]:
    """Apply route-owner execution defaults for frozen planner target layouts."""

    explicit_args = explicit_args or set()
    random_draw = target_layout.get("random_draw") if isinstance(target_layout.get("random_draw"), dict) else {}
    route_label = str(
        getattr(args, "planner_route_label", "")
        or target_layout.get("planner_route_label", "")
        or random_draw.get("planner_route_label", "")
        or ""
    ).strip()
    if not route_label:
        return {"applied": False, "reason": "missing_planner_route_label"}
    route_executor = str(
        getattr(args, "route_executor", "")
        or target_layout.get("route_executor", "")
        or random_draw.get("route_executor", "")
        or ROUTE_EXECUTOR_BY_LABEL.get(route_label, "")
    ).strip()
    _set_route_default(args, explicit_args, "planner_route_label", route_label, "--planner-route-label")
    _set_route_default(args, explicit_args, "route_executor", route_executor, "--route-executor")
    robot_pose = random_draw.get("robot_pose") if isinstance(random_draw.get("robot_pose"), dict) else {}
    if route_label not in EXECUTABLE_PLANNER_FETCH_ROUTES:
        return {
            "applied": False,
            "reason": "planner_route_not_local_fetch_executable",
            "planner_route_label": route_label,
            "route_executor": route_executor,
        }

    _set_route_default(args, explicit_args, "forward_only_pre_contact_required", True, "--forward-only-pre-contact-required")
    _set_route_default(args, explicit_args, "drive_mode", "line_servo", "--drive-mode")
    _set_route_default(args, explicit_args, "drive_linear_x_mps", 0.1, "--drive-linear-x-mps")
    if route_label == ROUTE_RECOVERY_OR_REAIM:
        route_drive_duration_s = 58.0
        route_sample_duration_s = 62.0
    elif route_label == ROUTE_NAV2_REPOSITION:
        route_drive_duration_s = 54.0
        route_sample_duration_s = 58.0
    else:
        route_drive_duration_s = 50.0
        route_sample_duration_s = 54.0
    _set_route_default(args, explicit_args, "drive_duration_s", route_drive_duration_s, "--drive-duration-s")
    _set_route_default(args, explicit_args, "sample_duration_s", route_sample_duration_s, "--sample-duration-s")
    _set_route_default(args, explicit_args, "line_servo_push_linear_x_mps", 0.055, "--line-servo-push-linear-x-mps")
    _set_route_default(args, explicit_args, "line_servo_max_angular_z_rps", 0.18, "--line-servo-max-angular-z-rps")
    _set_route_default(args, explicit_args, "line_servo_yaw_gain", 1.2, "--line-servo-yaw-gain")
    _set_route_default(args, explicit_args, "line_servo_min_linear_x_mps", 0.012, "--line-servo-min-linear-x-mps")
    _set_route_default(
        args,
        explicit_args,
        "line_servo_contact_lateral_ready_m",
        0.028,
        "--line-servo-contact-lateral-ready-m",
    )
    _set_route_default(
        args,
        explicit_args,
        "line_servo_contact_yaw_ready_deg",
        3.0,
        "--line-servo-contact-yaw-ready-deg",
    )
    _set_route_default(args, explicit_args, "stop_on_delivery", True, "--stop-on-delivery")
    _set_route_default(args, explicit_args, "delivery_stop_radius_m", 0.2, "--delivery-stop-radius-m")
    _set_route_default(args, explicit_args, "post_delivery_sample_s", 4.0, "--post-delivery-sample-s")
    if route_label in NAV2_SETUP_PLANNER_ROUTES:
        _set_route_default(args, explicit_args, "robot_x", 0.0, "--robot-x")
        _set_route_default(args, explicit_args, "robot_y", 0.0, "--robot-y")
        _set_route_default(args, explicit_args, "robot_yaw", 0.0, "--robot-yaw")
        _set_route_default(args, explicit_args, "nav2_reposition_before_fetch", True, "--nav2-reposition-before-fetch")
        _set_route_default(
            args,
            explicit_args,
            "nav2_reposition_transform_layout_to_current_robot",
            True,
            "--nav2-reposition-transform-layout-to-current-robot",
        )
        _set_route_default(args, explicit_args, "nav2_reposition_frame_id", "odom", "--nav2-reposition-frame-id")
        _set_route_default(
            args,
            explicit_args,
            "nav2_reposition_goal_frame_mode",
            "nav2_relative",
            "--nav2-reposition-goal-frame-mode",
        )
        _set_route_default(args, explicit_args, "nav2_reposition_setup_standoff_m", 0.38, "--nav2-reposition-setup-standoff-m")
        _set_route_default(args, explicit_args, "nav2_reposition_timeout_s", 24.0, "--nav2-reposition-timeout-s")
        _set_route_default(args, explicit_args, "nav2_reposition_server_wait_s", 8.0, "--nav2-reposition-server-wait-s")
        _set_route_default(args, explicit_args, "nav2_reposition_pose_wait_s", 3.0, "--nav2-reposition-pose-wait-s")
    elif robot_pose:
        _set_route_default(args, explicit_args, "robot_x", float(robot_pose.get("x", args.robot_x) or 0.0), "--robot-x")
        _set_route_default(args, explicit_args, "robot_y", float(robot_pose.get("y", args.robot_y) or 0.0), "--robot-y")
        _set_route_default(args, explicit_args, "robot_yaw", float(robot_pose.get("yaw", args.robot_yaw) or 0.0), "--robot-yaw")
    return {
        "applied": True,
        "planner_route_label": route_label,
        "route_executor": route_executor,
        "drive_mode": str(args.drive_mode),
        "nav2_reposition_before_fetch": bool(args.nav2_reposition_before_fetch),
        "route_quality": (
            random_draw.get("route_quality", {})
            if isinstance(random_draw.get("route_quality"), dict)
            else target_layout.get("route_quality", {})
            if isinstance(target_layout.get("route_quality"), dict)
            else {}
        ),
        "line_servo_quality_defaults": {
            "min_linear_x_mps": round(float(args.line_servo_min_linear_x_mps), 6),
            "contact_lateral_ready_m": round(float(args.line_servo_contact_lateral_ready_m), 6),
            "contact_yaw_ready_deg": round(float(args.line_servo_contact_yaw_ready_deg), 6),
        },
        "robot_pose": {
            "x": round(float(args.robot_x), 6),
            "y": round(float(args.robot_y), 6),
            "yaw": round(float(args.robot_yaw), 6),
        },
    }


def transform_nav2_reposition_layout_to_current_robot(args: argparse.Namespace, target_layout: dict[str, Any]) -> dict[str, Any]:
    random_draw = target_layout.get("random_draw") if isinstance(target_layout.get("random_draw"), dict) else {}
    source_robot_pose = random_draw.get("robot_pose") if isinstance(random_draw.get("robot_pose"), dict) else {}
    source_ball_pose = random_draw.get("ball_pose") if isinstance(random_draw.get("ball_pose"), dict) else {}
    source_target_pose = random_draw.get("target_pose") if isinstance(random_draw.get("target_pose"), dict) else {}
    if not source_robot_pose or not source_ball_pose or not source_target_pose:
        return {"applied": False, "reason": "missing_planner_random_draw_pose"}
    target_robot_pose = {
        "x": float(args.robot_x),
        "y": float(args.robot_y),
        "yaw": float(args.robot_yaw),
    }
    transformed_ball = transform_point_between_robot_frames(
        point_pose=source_ball_pose,
        source_robot_pose=source_robot_pose,
        target_robot_pose=target_robot_pose,
    )
    transformed_target = transform_point_between_robot_frames(
        point_pose=source_target_pose,
        source_robot_pose=source_robot_pose,
        target_robot_pose=target_robot_pose,
    )
    args.ball_x = transformed_ball["x"]
    args.ball_y = transformed_ball["y"]
    args.zone_x = transformed_target["x"]
    args.zone_y = transformed_target["y"]
    return {
        "applied": True,
        "reason": "preserve_planner_geometry_without_robot_teleport",
        "source_robot_pose": source_robot_pose,
        "source_ball_pose": source_ball_pose,
        "source_target_pose": source_target_pose,
        "target_robot_pose": target_robot_pose,
        "transformed_ball_pose": {**transformed_ball, "z": float(args.ball_z)},
        "transformed_target_pose": {
            **transformed_target,
            "z": float(args.zone_z),
            "radius_m": float(args.fetch_delivery_radius_m),
        },
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


def clamp(value: float, lower: float, upper: float) -> float:
    return max(float(lower), min(float(upper), float(value)))


def yaw_to_quaternion(yaw_rad: float) -> dict[str, float]:
    half_yaw = 0.5 * float(yaw_rad)
    return {
        "x": 0.0,
        "y": 0.0,
        "z": round(math.sin(half_yaw), 6),
        "w": round(math.cos(half_yaw), 6),
    }


def build_nav2_reposition_setup_pose(
    *,
    ball_x: float,
    ball_y: float,
    target_x: float,
    target_y: float,
    setup_standoff_m: float,
    frame_id: str = "odom",
) -> dict[str, Any]:
    line_yaw = math.atan2(float(target_y) - float(ball_y), float(target_x) - float(ball_x))
    setup_x = float(ball_x) - math.cos(line_yaw) * float(setup_standoff_m)
    setup_y = float(ball_y) - math.sin(line_yaw) * float(setup_standoff_m)
    return {
        "frame_id": str(frame_id or "odom"),
        "x": round(float(setup_x), 6),
        "y": round(float(setup_y), 6),
        "z": 0.0,
        "yaw": round(float(line_yaw), 6),
        "line_yaw_rad": round(float(line_yaw), 6),
        "setup_standoff_m": round(float(setup_standoff_m), 6),
        "source": "ball_target_line_setup_pose",
        "orientation": yaw_to_quaternion(line_yaw),
    }


def dashboard_robot_pose_from_state(state: dict[str, Any]) -> dict[str, float] | None:
    candidates: list[Any] = []
    if isinstance(state.get("belief"), dict):
        candidates.append(state["belief"].get("latest_robot_pose"))
    if isinstance(state.get("brain"), dict):
        candidates.append(state["brain"].get("latest_robot_pose"))
    candidates.append(state.get("latest_robot_pose"))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        try:
            return {
                "x": float(candidate.get("x", 0.0) or 0.0),
                "y": float(candidate.get("y", 0.0) or 0.0),
                "yaw": float(candidate.get("yaw", 0.0) or 0.0),
            }
        except (TypeError, ValueError):
            continue
    return None


def wait_for_dashboard_robot_pose(dashboard_url: str, *, timeout_s: float = 3.0, poll_s: float = 0.2) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + max(float(timeout_s), 0.1)
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            state = dashboard_state(dashboard_url)
        except Exception as exc:
            last_state = {"error": str(exc)}
            time.sleep(max(float(poll_s), 0.05))
            continue
        last_state = state if isinstance(state, dict) else {}
        pose = dashboard_robot_pose_from_state(last_state)
        if pose is not None:
            return {
                "available": True,
                "pose": pose,
                "elapsed_s": round(time.monotonic() - started, 6),
                "source": "dashboard_state.belief.latest_robot_pose",
            }
        time.sleep(max(float(poll_s), 0.05))
    return {
        "available": False,
        "pose": None,
        "elapsed_s": round(time.monotonic() - started, 6),
        "source": "dashboard_state.belief.latest_robot_pose",
        "last_state_keys": sorted(last_state.keys()) if isinstance(last_state, dict) else [],
        "error": str(last_state.get("error", "")) if isinstance(last_state, dict) else "",
    }


def build_nav2_relative_setup_goal(
    *,
    world_setup_pose: dict[str, Any],
    world_robot_pose: dict[str, Any],
    nav2_robot_pose: dict[str, Any],
    frame_id: str = "odom",
) -> dict[str, Any]:
    world_setup_x = float(world_setup_pose.get("x", 0.0) or 0.0)
    world_setup_y = float(world_setup_pose.get("y", 0.0) or 0.0)
    world_setup_yaw = float(world_setup_pose.get("yaw", 0.0) or 0.0)
    world_robot_x = float(world_robot_pose.get("x", 0.0) or 0.0)
    world_robot_y = float(world_robot_pose.get("y", 0.0) or 0.0)
    world_robot_yaw = float(world_robot_pose.get("yaw", 0.0) or 0.0)
    nav2_robot_x = float(nav2_robot_pose.get("x", 0.0) or 0.0)
    nav2_robot_y = float(nav2_robot_pose.get("y", 0.0) or 0.0)
    nav2_robot_yaw = float(nav2_robot_pose.get("yaw", 0.0) or 0.0)
    goal_yaw = normalize_angle_rad(nav2_robot_yaw + normalize_angle_rad(world_setup_yaw - world_robot_yaw))
    goal = {
        **world_setup_pose,
        "frame_id": str(frame_id or world_setup_pose.get("frame_id") or "odom"),
        "x": round(nav2_robot_x + (world_setup_x - world_robot_x), 6),
        "y": round(nav2_robot_y + (world_setup_y - world_robot_y), 6),
        "yaw": round(goal_yaw, 6),
        "orientation": yaw_to_quaternion(goal_yaw),
        "source": "nav2_relative_from_truth_delta",
        "world_setup_pose": dict(world_setup_pose),
        "world_robot_pose": dict(world_robot_pose),
        "nav2_robot_pose": dict(nav2_robot_pose),
        "frame_delta": {
            "world_dx_m": round(world_setup_x - world_robot_x, 6),
            "world_dy_m": round(world_setup_y - world_robot_y, 6),
            "world_dyaw_rad": round(normalize_angle_rad(world_setup_yaw - world_robot_yaw), 6),
        },
    }
    return goal


def _status_text(status_code: Any) -> str:
    mapping = {
        0: "STATUS_UNKNOWN",
        1: "STATUS_ACCEPTED",
        2: "STATUS_EXECUTING",
        3: "STATUS_CANCELING",
        4: "STATUS_SUCCEEDED",
        5: "STATUS_CANCELED",
        6: "STATUS_ABORTED",
    }
    try:
        return mapping.get(int(status_code), f"STATUS_{int(status_code)}")
    except (TypeError, ValueError):
        return "STATUS_UNKNOWN"


def parse_nav2_reposition_result(output: str, *, rc: int) -> dict[str, Any]:
    for line in reversed(str(output or "").splitlines()):
        text = line.strip()
        if not text.startswith(NAV2_REPOSITION_RESULT_MARKER):
            continue
        raw = text[len(NAV2_REPOSITION_RESULT_MARKER):].strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            break
        if isinstance(payload, dict):
            payload.setdefault("process_returncode", int(rc))
            payload.setdefault("status_text", _status_text(payload.get("status_code")))
            return payload
    return {
        "phase": "nav2_reposition_before_fetch",
        "attempted": True,
        "accepted": False,
        "success": False,
        "dispatch_status": "client_error",
        "status_code": None,
        "status_text": "STATUS_UNKNOWN",
        "elapsed_s": 0.0,
        "error": str(output or "missing_nav2_reposition_result").strip(),
        "process_returncode": int(rc),
    }


def dispatch_nav2_reposition_before_fetch(
    *,
    compose_project: str,
    goal_pose: dict[str, Any],
    timeout_s: float,
    server_wait_s: float,
) -> dict[str, Any]:
    payload = {
        "goal_pose": goal_pose,
        "behavior_tree": NAV2_REPOSITION_BEHAVIOR_TREE,
        "timeout_s": max(float(timeout_s), 0.1),
        "server_wait_s": max(float(server_wait_s), 0.1),
    }
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi
set -u
export NAV2_REPOSITION_PAYLOAD={json.dumps(json.dumps(payload, separators=(",", ":")))}
python3 - <<'PY'
import json
import math
import os
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

MARKER = "NAV2_REPOSITION_RESULT="


def status_text(status_code):
    return {{
        int(GoalStatus.STATUS_UNKNOWN): "STATUS_UNKNOWN",
        int(GoalStatus.STATUS_ACCEPTED): "STATUS_ACCEPTED",
        int(GoalStatus.STATUS_EXECUTING): "STATUS_EXECUTING",
        int(GoalStatus.STATUS_CANCELING): "STATUS_CANCELING",
        int(GoalStatus.STATUS_SUCCEEDED): "STATUS_SUCCEEDED",
        int(GoalStatus.STATUS_CANCELED): "STATUS_CANCELED",
        int(GoalStatus.STATUS_ABORTED): "STATUS_ABORTED",
    }}.get(int(status_code), f"STATUS_{{int(status_code)}}")


def yaw_to_quaternion(yaw):
    half = 0.5 * float(yaw)
    return 0.0, 0.0, math.sin(half), math.cos(half)


def wait_future(node, future, timeout_s):
    deadline = time.monotonic() + max(float(timeout_s), 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        if future.done():
            return True
        rclpy.spin_once(node, timeout_sec=0.1)
    return bool(future.done())


def emit(payload):
    print(MARKER + json.dumps(payload, sort_keys=True), flush=True)


payload = json.loads(os.environ["NAV2_REPOSITION_PAYLOAD"])
goal_pose = payload["goal_pose"]
started = time.monotonic()
rclpy.init()
node = Node("fetch_nav2_reposition_before_fetch_client")
node.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
client = ActionClient(node, NavigateToPose, "/navigate_to_pose")
try:
    server_ready = bool(client.wait_for_server(timeout_sec=max(float(payload["server_wait_s"]), 0.1)))
    if not server_ready:
        emit({{
            "phase": "nav2_reposition_before_fetch",
            "attempted": True,
            "accepted": False,
            "success": False,
            "dispatch_status": "server_unavailable",
            "status_code": int(GoalStatus.STATUS_UNKNOWN),
            "status_text": status_text(GoalStatus.STATUS_UNKNOWN),
            "elapsed_s": round(time.monotonic() - started, 6),
            "error": "nav2_action_server_unavailable",
        }})
    else:
        goal = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = str(goal_pose.get("frame_id") or "odom")
        pose.header.stamp = node.get_clock().now().to_msg()
        pose.pose.position.x = float(goal_pose["x"])
        pose.pose.position.y = float(goal_pose["y"])
        pose.pose.position.z = float(goal_pose.get("z", 0.0) or 0.0)
        qx, qy, qz, qw = yaw_to_quaternion(float(goal_pose["yaw"]))
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        goal.pose = pose
        goal.behavior_tree = str(payload.get("behavior_tree") or "")
        send_future = client.send_goal_async(goal)
        if not wait_future(node, send_future, timeout_s=5.0):
            emit({{
                "phase": "nav2_reposition_before_fetch",
                "attempted": True,
                "accepted": False,
                "success": False,
                "dispatch_status": "send_goal_timeout",
                "status_code": int(GoalStatus.STATUS_UNKNOWN),
                "status_text": status_text(GoalStatus.STATUS_UNKNOWN),
                "elapsed_s": round(time.monotonic() - started, 6),
                "error": "send_goal_timeout",
            }})
        else:
            goal_handle = send_future.result()
            if goal_handle is None:
                emit({{
                    "phase": "nav2_reposition_before_fetch",
                    "attempted": True,
                    "accepted": False,
                    "success": False,
                    "dispatch_status": "send_goal_result_none",
                    "status_code": int(GoalStatus.STATUS_UNKNOWN),
                    "status_text": status_text(GoalStatus.STATUS_UNKNOWN),
                    "elapsed_s": round(time.monotonic() - started, 6),
                    "error": "send_goal_result_none",
                }})
            elif not goal_handle.accepted:
                emit({{
                    "phase": "nav2_reposition_before_fetch",
                    "attempted": True,
                    "accepted": False,
                    "success": False,
                    "dispatch_status": "goal_rejected",
                    "status_code": None,
                    "status_text": "STATUS_REJECTED",
                    "elapsed_s": round(time.monotonic() - started, 6),
                    "error": "goal_rejected",
                }})
            else:
                result_future = goal_handle.get_result_async()
                if not wait_future(node, result_future, timeout_s=float(payload["timeout_s"])):
                    try:
                        goal_handle.cancel_goal_async()
                    except Exception:
                        pass
                    emit({{
                        "phase": "nav2_reposition_before_fetch",
                        "attempted": True,
                        "accepted": True,
                        "success": False,
                        "dispatch_status": "goal_result_timeout",
                        "status_code": int(GoalStatus.STATUS_ABORTED),
                        "status_text": status_text(GoalStatus.STATUS_ABORTED),
                        "elapsed_s": round(time.monotonic() - started, 6),
                        "error": "goal_result_timeout",
                    }})
                else:
                    result = result_future.result()
                    status_code = int(result.status) if result is not None else int(GoalStatus.STATUS_UNKNOWN)
                    success = status_code == int(GoalStatus.STATUS_SUCCEEDED)
                    emit({{
                        "phase": "nav2_reposition_before_fetch",
                        "attempted": True,
                        "accepted": True,
                        "success": bool(success),
                        "dispatch_status": "goal_succeeded" if success else "goal_finished",
                        "status_code": status_code,
                        "status_text": status_text(status_code),
                        "elapsed_s": round(time.monotonic() - started, 6),
                        "error": "" if success else f"goal_status_{{status_code}}",
                    }})
finally:
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
PY
"""
    rc, output = docker_exec_service(compose_project, "gate-stack", script, timeout_s=max(float(timeout_s), 0.1) + 30.0)
    result = parse_nav2_reposition_result(output, rc=rc)
    result.setdefault("goal_pose", dict(goal_pose))
    result.setdefault("behavior_tree", NAV2_REPOSITION_BEHAVIOR_TREE)
    return result


def line_servo_command(
    *,
    robot_pose: dict[str, float],
    ball_pose: dict[str, float],
    target_x: float,
    target_y: float,
    ball_start_pose: dict[str, float] | None = None,
    motion_threshold_m: float = 0.005,
    max_linear_x_mps: float = 0.10,
    push_linear_x_mps: float = 0.055,
    min_linear_x_mps: float = 0.025,
    max_angular_z_rps: float = 0.18,
    yaw_gain: float = 1.20,
    contact_standoff_m: float = 0.11,
    setup_standoff_m: float = 0.20,
    recovery_setup_standoff_m: float = 0.34,
    recovery_max_angular_z_rps: float = 0.45,
    contact_lateral_ready_m: float = 0.035,
    contact_yaw_ready_rad: float = 0.10,
    route_label: str = "",
) -> dict[str, Any]:
    robot_x = float(robot_pose.get("x", 0.0) or 0.0)
    robot_y = float(robot_pose.get("y", 0.0) or 0.0)
    robot_yaw = float(robot_pose.get("yaw", 0.0) or 0.0)
    ball_x = float(ball_pose.get("x", 0.0) or 0.0)
    ball_y = float(ball_pose.get("y", 0.0) or 0.0)
    line_yaw = math.atan2(float(target_y) - ball_y, float(target_x) - ball_x)
    clean_route_label = str(route_label or "").strip()
    effective_setup_standoff_m = max(float(setup_standoff_m), float(contact_standoff_m))
    effective_max_angular_z_rps = float(max_angular_z_rps)
    effective_contact_lateral_ready_m = float(contact_lateral_ready_m)
    recovery_line_acquire_lateral_m = max(float(effective_contact_lateral_ready_m), 0.0)
    recovery_setup_pocket_m = 0.10
    if clean_route_label == "recovery_or_reaim":
        effective_setup_standoff_m = max(effective_setup_standoff_m, float(recovery_setup_standoff_m))
        effective_max_angular_z_rps = max(effective_max_angular_z_rps, float(recovery_max_angular_z_rps))
        effective_contact_lateral_ready_m = min(effective_contact_lateral_ready_m, 0.030)
        recovery_line_acquire_lateral_m = max(effective_contact_lateral_ready_m, 0.080)
        recovery_setup_pocket_m = 0.12
    behind_x = ball_x - math.cos(line_yaw) * float(contact_standoff_m)
    behind_y = ball_y - math.sin(line_yaw) * float(contact_standoff_m)
    setup_x = ball_x - math.cos(line_yaw) * effective_setup_standoff_m
    setup_y = ball_y - math.sin(line_yaw) * effective_setup_standoff_m
    distance_to_contact = math.hypot(behind_x - robot_x, behind_y - robot_y)
    distance_to_setup = math.hypot(setup_x - robot_x, setup_y - robot_y)
    aim_yaw = math.atan2(behind_y - robot_y, behind_x - robot_x)
    setup_yaw = math.atan2(setup_y - robot_y, setup_x - robot_x)
    robot_lateral_error = signed_lateral_error_m(robot_x, robot_y, origin_x=ball_x, origin_y=ball_y, line_yaw_rad=line_yaw)
    line_yaw_error = normalize_angle_rad(line_yaw - robot_yaw)
    yaw_priority_lateral_m = max(float(effective_contact_lateral_ready_m), 0.032)
    contact_final_reaim_active = bool(
        distance_to_contact < 0.14
        and abs(robot_lateral_error) > effective_contact_lateral_ready_m
    )
    recovery_final_reaim_active = bool(clean_route_label == ROUTE_RECOVERY_OR_REAIM and contact_final_reaim_active)
    lateral_reaim_gain = 3.5
    lateral_reaim_limit_rad = 0.45
    if contact_final_reaim_active:
        yaw_priority_lateral_m = min(yaw_priority_lateral_m, max(effective_contact_lateral_ready_m, 0.020))
        lateral_reaim_gain = 4.5
        lateral_reaim_limit_rad = 0.50
    if recovery_final_reaim_active:
        yaw_priority_lateral_m = min(yaw_priority_lateral_m, max(effective_contact_lateral_ready_m * 0.80, 0.020))
        lateral_reaim_gain = 6.5
        lateral_reaim_limit_rad = 0.65
    lateral_reaim = 0.0
    if abs(robot_lateral_error) > yaw_priority_lateral_m:
        lateral_reaim = clamp(float(robot_lateral_error) * lateral_reaim_gain, -lateral_reaim_limit_rad, lateral_reaim_limit_rad)
    lateral_corrected_yaw = normalize_angle_rad(line_yaw - lateral_reaim)
    contact_ready = abs(robot_lateral_error) <= effective_contact_lateral_ready_m and abs(line_yaw_error) <= float(contact_yaw_ready_rad)
    ball_motion_m = 0.0
    if ball_start_pose is not None:
        ball_motion_m = math.hypot(
            ball_x - float(ball_start_pose.get("x", ball_x) or ball_x),
            ball_y - float(ball_start_pose.get("y", ball_y) or ball_y),
        )
    ball_moved = bool(ball_motion_m >= float(motion_threshold_m))
    if ball_moved:
        if abs(robot_lateral_error) > effective_contact_lateral_ready_m:
            phase = "push_coast_realign"
            desired_yaw = lateral_corrected_yaw
            base_linear = min(float(push_linear_x_mps), float(max_linear_x_mps), 0.035)
        else:
            phase = "push_coast"
            desired_yaw = line_yaw
            base_linear = min(float(push_linear_x_mps), float(max_linear_x_mps))
    elif (
        clean_route_label == "recovery_or_reaim"
        and distance_to_setup <= recovery_setup_pocket_m
        and abs(robot_lateral_error) <= recovery_line_acquire_lateral_m
        and distance_to_contact > 0.12
    ):
        phase = "recovery_line_acquire"
        desired_yaw = line_yaw
        base_linear = min(float(max_linear_x_mps), max(float(push_linear_x_mps), 0.055))
        if abs(line_yaw_error) > 0.35:
            base_linear = min(base_linear, 0.035)
        elif abs(line_yaw_error) > 0.25:
            base_linear = min(base_linear, 0.045)
    elif not contact_ready:
        if recovery_final_reaim_active:
            phase = "recovery_final_reaim"
            desired_yaw = lateral_corrected_yaw
            base_linear = min(float(max_linear_x_mps), max(float(min_linear_x_mps), 0.014))
        elif contact_final_reaim_active:
            phase = "contact_final_reaim"
            desired_yaw = lateral_corrected_yaw
            base_linear = min(float(max_linear_x_mps), max(float(min_linear_x_mps), 0.018))
        else:
            phase = "setup_converge" if distance_to_contact > 0.18 else "setup_reaim"
            desired_yaw = setup_yaw if distance_to_contact > 0.20 else lateral_corrected_yaw
            base_linear = min(float(max_linear_x_mps), 0.055)
        if abs(robot_lateral_error) > 0.07 or abs(line_yaw_error) > 0.18:
            base_linear = min(base_linear, 0.035)
        if distance_to_contact < 0.09:
            base_linear = min(base_linear, max(float(min_linear_x_mps), 0.012))
        elif distance_to_contact < 0.14 and (
            abs(robot_lateral_error) > effective_contact_lateral_ready_m
            or abs(line_yaw_error) > float(contact_yaw_ready_rad)
        ):
            base_linear = min(base_linear, max(float(min_linear_x_mps), 0.018))
    elif distance_to_contact > 0.16:
        phase = "setup_converge"
        desired_yaw = setup_yaw
        base_linear = min(float(max_linear_x_mps), 0.075)
    else:
        phase = "first_contact_align"
        desired_yaw = line_yaw
        base_linear = min(float(max_linear_x_mps), max(float(push_linear_x_mps), 0.06))
    yaw_error = normalize_angle_rad(desired_yaw - robot_yaw)
    angular_z = clamp(float(yaw_gain) * yaw_error, -effective_max_angular_z_rps, effective_max_angular_z_rps)
    if abs(yaw_error) > 0.45:
        base_linear = min(base_linear, 0.035)
    elif abs(yaw_error) > 0.25:
        base_linear = min(base_linear, 0.055)
    linear_floor = float(min_linear_x_mps)
    recovery_yaw_hold = bool(
        clean_route_label == ROUTE_RECOVERY_OR_REAIM
        and not ball_moved
        and abs(yaw_error) > 1.25
        and distance_to_contact > 0.20
    )
    recovery_yaw_crawl = bool(
        clean_route_label == ROUTE_RECOVERY_OR_REAIM
        and not ball_moved
        and not recovery_yaw_hold
        and (
            abs(yaw_error) > 0.55
            or (
                distance_to_contact < 0.14
                and abs(robot_lateral_error) > effective_contact_lateral_ready_m
            )
        )
    )
    if recovery_yaw_hold:
        phase = f"{phase}_yaw_hold"
        base_linear = 0.0
        linear_floor = 0.0
    elif recovery_yaw_crawl:
        phase = f"{phase}_yaw_crawl"
        crawl_cap = 0.018 if distance_to_contact < 0.14 else 0.025
        base_linear = min(max(base_linear, float(min_linear_x_mps)), crawl_cap)
    linear_x = clamp(base_linear, linear_floor, float(max_linear_x_mps))
    return {
        "phase": phase,
        "linear_x_mps": round(float(linear_x), 6),
        "angular_z_rps": round(float(angular_z), 6),
        "desired_yaw_rad": round(float(desired_yaw), 6),
        "line_yaw_rad": round(float(line_yaw), 6),
        "aim_yaw_rad": round(float(aim_yaw), 6),
        "setup_yaw_rad": round(float(setup_yaw), 6),
        "yaw_error_rad": round(float(yaw_error), 6),
        "line_yaw_error_rad": round(float(line_yaw_error), 6),
        "robot_lateral_error_m": round(float(robot_lateral_error), 6),
        "contact_lateral_ready_m": round(float(effective_contact_lateral_ready_m), 6),
        "contact_yaw_ready_rad": round(float(contact_yaw_ready_rad), 6),
        "recovery_line_acquire_lateral_m": round(float(recovery_line_acquire_lateral_m), 6),
        "recovery_setup_pocket_m": round(float(recovery_setup_pocket_m), 6),
        "contact_final_reaim_active": contact_final_reaim_active,
        "recovery_final_reaim_active": recovery_final_reaim_active,
        "lateral_reaim_rad": round(float(lateral_reaim), 6),
        "lateral_reaim_gain": round(float(lateral_reaim_gain), 6),
        "yaw_priority_lateral_m": round(float(yaw_priority_lateral_m), 6),
        "contact_ready": contact_ready,
        "recovery_yaw_hold": recovery_yaw_hold,
        "recovery_yaw_crawl": recovery_yaw_crawl,
        "distance_to_contact_m": round(float(distance_to_contact), 6),
        "distance_to_setup_m": round(float(distance_to_setup), 6),
        "ball_motion_m": round(float(ball_motion_m), 6),
        "ball_moved": ball_moved,
        "contact_standoff_m": round(float(contact_standoff_m), 6),
        "setup_standoff_m": round(float(effective_setup_standoff_m), 6),
        "max_angular_z_rps": round(float(effective_max_angular_z_rps), 6),
        "route_label": clean_route_label,
    }


def summarize_line_servo_effective_command(contact_samples: list[dict[str, Any]]) -> dict[str, Any]:
    for sample in contact_samples:
        command = sample.get("line_servo_command") if isinstance(sample, dict) else None
        if not isinstance(command, dict):
            continue
        summary: dict[str, Any] = {}
        numeric_fields = {
            "setup_standoff_m": "line_servo_effective_setup_standoff_m",
            "contact_standoff_m": "line_servo_effective_contact_standoff_m",
            "contact_lateral_ready_m": "line_servo_effective_contact_lateral_ready_m",
            "contact_yaw_ready_rad": "line_servo_effective_contact_yaw_ready_rad",
            "recovery_line_acquire_lateral_m": "line_servo_effective_recovery_line_acquire_lateral_m",
            "recovery_setup_pocket_m": "line_servo_effective_recovery_setup_pocket_m",
            "yaw_priority_lateral_m": "line_servo_effective_yaw_priority_lateral_m",
            "max_angular_z_rps": "line_servo_effective_max_angular_z_rps",
        }
        for source_key, dest_key in numeric_fields.items():
            if source_key not in command:
                continue
            try:
                summary[dest_key] = round(float(command.get(source_key)), 6)
            except (TypeError, ValueError):
                pass
        summary["line_servo_effective_route_label"] = str(command.get("route_label", "") or "")
        return summary
    return {}


def collect_contact_samples(
    *,
    compose_project: str,
    world_name: str,
    robot_model_name: str,
    ball_model_name: str,
    duration_s: float,
    poll_period_s: float,
    stop_on_delivery: bool = False,
    delivery_target_x: float = 0.0,
    delivery_target_y: float = 0.0,
    delivery_radius_m: float = 0.0,
    delivery_stop_radius_m: float = 0.0,
) -> list[dict[str, Any]]:
    effective_stop_radius_m = float(delivery_stop_radius_m) if float(delivery_stop_radius_m) > 0.0 else float(delivery_radius_m)
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
export STOP_ON_DELIVERY={json.dumps("1" if stop_on_delivery else "0")}
export DELIVERY_TARGET_X={json.dumps(f"{delivery_target_x:.6f}")}
export DELIVERY_TARGET_Y={json.dumps(f"{delivery_target_y:.6f}")}
export DELIVERY_RADIUS_M={json.dumps(f"{delivery_radius_m:.6f}")}
export DELIVERY_STOP_RADIUS_M={json.dumps(f"{effective_stop_radius_m:.6f}")}
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
stop_on_delivery = os.environ.get("STOP_ON_DELIVERY", "0") == "1"
delivery_target_x = float(os.environ.get("DELIVERY_TARGET_X", "0.0"))
delivery_target_y = float(os.environ.get("DELIVERY_TARGET_Y", "0.0"))
delivery_radius_m = float(os.environ.get("DELIVERY_RADIUS_M", "0.0"))
delivery_stop_radius_m = float(os.environ.get("DELIVERY_STOP_RADIUS_M", str(delivery_radius_m)))
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
    should_break = False
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
            converted_ball = record["ball_pose"]
            if stop_on_delivery and converted_ball:
                position = converted_ball.get("position") if isinstance(converted_ball.get("position"), dict) else {{}}
                try:
                    dx = float(position.get("x", 0.0)) - delivery_target_x
                    dy = float(position.get("y", 0.0)) - delivery_target_y
                    distance = math.hypot(dx, dy)
                    record["delivery_distance_m"] = round(distance, 6)
                    if distance <= delivery_stop_radius_m:
                        record["delivery_stop_triggered"] = True
                        record["delivery_stop_radius_m"] = round(delivery_stop_radius_m, 6)
                        should_break = True
                except Exception:
                    pass
    except Exception as exc:
        record["error"] = str(exc)
    print(json.dumps(record, sort_keys=True), flush=True)
    index += 1
    if should_break:
        break
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


def collect_line_servo_samples(
    *,
    compose_project: str,
    world_name: str,
    robot_model_name: str,
    ball_model_name: str,
    duration_s: float,
    poll_period_s: float,
    delivery_target_x: float,
    delivery_target_y: float,
    delivery_radius_m: float,
    delivery_stop_radius_m: float = 0.0,
    stop_on_delivery: bool = False,
    motion_threshold_m: float = 0.005,
    max_linear_x_mps: float = 0.10,
    push_linear_x_mps: float = 0.055,
    min_linear_x_mps: float = 0.025,
    max_angular_z_rps: float = 0.18,
    yaw_gain: float = 1.20,
    contact_lateral_ready_m: float = 0.035,
    contact_yaw_ready_rad: float = 0.10,
    route_label: str = "",
) -> list[dict[str, Any]]:
    effective_stop_radius_m = float(delivery_stop_radius_m) if float(delivery_stop_radius_m) > 0.0 else float(delivery_radius_m)
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
export DELIVERY_TARGET_X={json.dumps(f"{delivery_target_x:.6f}")}
export DELIVERY_TARGET_Y={json.dumps(f"{delivery_target_y:.6f}")}
export DELIVERY_RADIUS_M={json.dumps(f"{delivery_radius_m:.6f}")}
export DELIVERY_STOP_RADIUS_M={json.dumps(f"{effective_stop_radius_m:.6f}")}
export STOP_ON_DELIVERY={json.dumps("1" if stop_on_delivery else "0")}
export MOTION_THRESHOLD_M={json.dumps(f"{motion_threshold_m:.6f}")}
export MAX_LINEAR_X_MPS={json.dumps(f"{max_linear_x_mps:.6f}")}
export PUSH_LINEAR_X_MPS={json.dumps(f"{push_linear_x_mps:.6f}")}
export MIN_LINEAR_X_MPS={json.dumps(f"{min_linear_x_mps:.6f}")}
export MAX_ANGULAR_Z_RPS={json.dumps(f"{max_angular_z_rps:.6f}")}
export YAW_GAIN={json.dumps(f"{yaw_gain:.6f}")}
export CONTACT_LATERAL_READY_M={json.dumps(f"{contact_lateral_ready_m:.6f}")}
export CONTACT_YAW_READY_RAD={json.dumps(f"{contact_yaw_ready_rad:.6f}")}
export PLANNER_ROUTE_LABEL={json.dumps(str(route_label or ""))}
python3 - <<'PY'
import json
import math
import os
import subprocess
import time

import rclpy
from geometry_msgs.msg import TwistStamped

import sys
sys.path.insert(0, "/workspaces/chasecar/scripts")
from golf_ball_circle_delivery_demo_runner import line_servo_command
from sim_truth_probe import parse_pose_message

world_name = os.environ["WORLD_NAME"]
robot_model_name = os.environ["ROBOT_MODEL_NAME"]
ball_model_name = os.environ["BALL_MODEL_NAME"]
duration_s = float(os.environ["DURATION_S"])
poll_period_s = float(os.environ["POLL_PERIOD_S"])
delivery_target_x = float(os.environ["DELIVERY_TARGET_X"])
delivery_target_y = float(os.environ["DELIVERY_TARGET_Y"])
delivery_radius_m = float(os.environ["DELIVERY_RADIUS_M"])
delivery_stop_radius_m = float(os.environ["DELIVERY_STOP_RADIUS_M"])
stop_on_delivery = os.environ.get("STOP_ON_DELIVERY", "0") == "1"
motion_threshold_m = float(os.environ["MOTION_THRESHOLD_M"])
max_linear_x_mps = float(os.environ["MAX_LINEAR_X_MPS"])
push_linear_x_mps = float(os.environ["PUSH_LINEAR_X_MPS"])
min_linear_x_mps = float(os.environ["MIN_LINEAR_X_MPS"])
max_angular_z_rps = float(os.environ["MAX_ANGULAR_Z_RPS"])
yaw_gain = float(os.environ["YAW_GAIN"])
contact_lateral_ready_m = float(os.environ["CONTACT_LATERAL_READY_M"])
contact_yaw_ready_rad = float(os.environ["CONTACT_YAW_READY_RAD"])
planner_route_label = os.environ.get("PLANNER_ROUTE_LABEL", "")
topic = f"/world/{{world_name}}/dynamic_pose/info"
started = time.monotonic()
deadline = started + max(duration_s, 0.1)
index = 0
ball_start_xy = None

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

def pose_xy_yaw(converted):
    if not converted:
        return None
    position = converted.get("position") if isinstance(converted.get("position"), dict) else {{}}
    return {{
        "x": float(position.get("x", 0.0) or 0.0),
        "y": float(position.get("y", 0.0) or 0.0),
        "z": float(position.get("z", 0.0) or 0.0),
        "yaw": float(converted.get("yaw", 0.0) or 0.0),
    }}

def publish(pub, node, linear_x, angular_z):
    msg = TwistStamped()
    msg.header.frame_id = "base_link"
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.twist.linear.x = float(linear_x)
    msg.twist.angular.z = float(angular_z)
    pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.0)

rclpy.init(args=None)
node = rclpy.create_node("fetch_line_servo_demo_runner")
pub = node.create_publisher(TwistStamped, "/jetbot_base_controller/cmd_vel", 10)
try:
    while time.monotonic() < deadline:
        tick_started = time.monotonic()
        should_break = False
        record = {{
            "sample_index": index,
            "t_s": round(tick_started - started, 6),
            "topic_ok": False,
            "robot_model_name": robot_model_name,
            "ball_model_name": ball_model_name,
            "robot_pose": None,
            "ball_pose": None,
            "drive_mode": "line_servo",
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
                converted_robot = convert_pose(robot_pose)
                converted_ball = convert_pose(ball_pose)
                record["robot_pose"] = converted_robot
                record["ball_pose"] = converted_ball
                robot_xy = pose_xy_yaw(converted_robot)
                ball_xy = pose_xy_yaw(converted_ball)
                if ball_xy and ball_start_xy is None:
                    ball_start_xy = dict(ball_xy)
                if robot_xy and ball_xy:
                    command = line_servo_command(
                        robot_pose=robot_xy,
                        ball_pose=ball_xy,
                        target_x=delivery_target_x,
                        target_y=delivery_target_y,
                        ball_start_pose=ball_start_xy,
                        motion_threshold_m=motion_threshold_m,
                        max_linear_x_mps=max_linear_x_mps,
                        push_linear_x_mps=push_linear_x_mps,
                        min_linear_x_mps=min_linear_x_mps,
                        max_angular_z_rps=max_angular_z_rps,
                        yaw_gain=yaw_gain,
                        contact_lateral_ready_m=contact_lateral_ready_m,
                        contact_yaw_ready_rad=contact_yaw_ready_rad,
                        route_label=planner_route_label,
                    )
                    record["line_servo_command"] = command
                    publish(pub, node, command["linear_x_mps"], command["angular_z_rps"])
                    dx = ball_xy["x"] - delivery_target_x
                    dy = ball_xy["y"] - delivery_target_y
                    distance = math.hypot(dx, dy)
                    record["delivery_distance_m"] = round(distance, 6)
                    if stop_on_delivery and distance <= delivery_stop_radius_m:
                        record["delivery_stop_triggered"] = True
                        record["delivery_stop_radius_m"] = round(delivery_stop_radius_m, 6)
                        should_break = True
                else:
                    publish(pub, node, 0.0, 0.0)
        except Exception as exc:
            record["error"] = str(exc)
            try:
                publish(pub, node, 0.0, 0.0)
            except Exception:
                pass
        print(json.dumps(record, sort_keys=True), flush=True)
        index += 1
        if should_break:
            break
        elapsed = time.monotonic() - tick_started
        if elapsed < poll_period_s:
            time.sleep(poll_period_s - elapsed)
finally:
    for _ in range(5):
        try:
            publish(pub, node, 0.0, 0.0)
            time.sleep(0.05)
        except Exception:
            pass
    node.destroy_node()
    rclpy.shutdown()
PY
"""
    rc, output = docker_exec(compose_project, script, timeout_s=duration_s + 60.0)
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
        raise RuntimeError(output.strip() or "failed to run line-servo drive loop")
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
    first_contact_quality_flags: list[str] = []
    if first_contact_row:
        if first_contact_lateral is None or abs(first_contact_lateral) > float(lateral_threshold_m):
            first_contact_quality_flags.append("first_contact_lateral_error")
        if first_contact_yaw is None or abs(first_contact_yaw) > yaw_threshold_rad:
            first_contact_quality_flags.append("first_contact_yaw_error")
        if first_contact_ball_lateral is None or abs(first_contact_ball_lateral) > float(ball_lateral_threshold_m):
            first_contact_quality_flags.append("first_contact_ball_lateral_error")
        if contact_angle_rad is not None and abs(contact_angle_rad) > math.radians(float(contact_angle_threshold_deg)):
            first_contact_quality_flags.append("first_contact_trajectory_angle_error")
    else:
        first_contact_quality_flags.append("missing_first_contact")

    return {
        "observed": bool(parsed),
        "stable_contact_approach_pass": not flags,
        "first_contact_quality_pass": not first_contact_quality_flags,
        "flags": flags,
        "first_contact_quality_flags": first_contact_quality_flags,
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


def stop_robot_drive_publishers(compose_project: str) -> dict[str, Any]:
    script = """
set +e
pkill -f '[r]os2 topic pub.*jetbot_base_controller/cmd_vel'
rc=$?
if [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ]; then
  exit 0
fi
exit "$rc"
"""
    rc, output = docker_exec_service(compose_project, "gate-stack", script, timeout_s=10.0)
    return {"returncode": rc, "output": output, "pass": rc == 0}


def publish_zero_stop(compose_project: str) -> dict[str, Any]:
    msg = "{header: {frame_id: base_link}, twist: {linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}}"
    script = f"""
set +e
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
for _ in 1 2 3; do
  ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped {json.dumps(msg)}
  sleep 0.05
done
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
    parser.add_argument("--expected-session-id", default="")
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
    parser.add_argument("--drive-mode", choices=["constant", "line_servo"], default="constant")
    parser.add_argument("--drive-linear-x-mps", type=float, default=0.12)
    parser.add_argument("--drive-duration-s", type=float, default=7.0)
    parser.add_argument("--line-servo-push-linear-x-mps", type=float, default=0.055)
    parser.add_argument("--line-servo-min-linear-x-mps", type=float, default=0.025)
    parser.add_argument("--line-servo-max-angular-z-rps", type=float, default=0.18)
    parser.add_argument("--line-servo-yaw-gain", type=float, default=1.20)
    parser.add_argument("--line-servo-contact-lateral-ready-m", type=float, default=0.035)
    parser.add_argument("--line-servo-contact-yaw-ready-deg", type=float, default=5.729578)
    parser.add_argument("--planner-route-label", default="")
    parser.add_argument("--route-executor", default="")
    parser.add_argument("--nav2-reposition-before-fetch", action="store_true")
    parser.add_argument("--nav2-reposition-frame-id", default="odom")
    parser.add_argument("--nav2-reposition-goal-frame-mode", choices=["nav2_relative", "world_direct"], default="nav2_relative")
    parser.add_argument("--nav2-reposition-transform-layout-to-current-robot", action="store_true")
    parser.add_argument("--nav2-reposition-setup-standoff-m", type=float, default=0.38)
    parser.add_argument("--nav2-reposition-timeout-s", type=float, default=24.0)
    parser.add_argument("--nav2-reposition-server-wait-s", type=float, default=8.0)
    parser.add_argument("--nav2-reposition-pose-wait-s", type=float, default=3.0)
    parser.add_argument("--nav2-reposition-continue-on-failure", action="store_true")
    parser.add_argument("--forward-only-pre-contact-required", action="store_true")
    parser.add_argument("--stop-on-delivery", action="store_true")
    parser.add_argument("--delivery-stop-radius-m", type=float, default=0.0)
    parser.add_argument("--post-delivery-sample-s", type=float, default=0.0)
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
    explicit_args = set(sys.argv[1:])
    target_layout = apply_target_layout(args)
    planner_route_defaults = apply_planner_route_execution_defaults(args, target_layout, explicit_args=explicit_args)
    if args.fetch_target_x is not None:
        args.zone_x = args.fetch_target_x
    if args.fetch_target_y is not None:
        args.zone_y = args.fetch_target_y
    if args.fetch_target_z is not None:
        args.zone_z = args.fetch_target_z
    nav2_layout_transform: dict[str, Any] = {"applied": False, "reason": "nav2_layout_transform_disabled"}
    if bool(args.nav2_reposition_transform_layout_to_current_robot):
        nav2_layout_transform = transform_nav2_reposition_layout_to_current_robot(args, target_layout)
        target_layout["nav2_layout_transform"] = nav2_layout_transform
    delivery_stop_radius_m = (
        float(args.delivery_stop_radius_m)
        if float(args.delivery_stop_radius_m or 0.0) > 0.0
        else float(args.fetch_delivery_radius_m)
    )
    state = dashboard_state(args.dashboard_url)
    args.compose_project = args.compose_project or str(state.get("compose_project", "") or state.get("launcher_project", "") or "")
    if not args.compose_project:
        args.compose_project = discover_compose_project(args.dashboard_url)
    if not args.compose_project:
        raise SystemExit("Unable to discover compose project; pass --compose-project.")
    expected_session_id = str(args.expected_session_id or "").strip()
    state_session_id = str(state.get("session_id", "") or "").strip()
    if expected_session_id and state_session_id and state_session_id != expected_session_id:
        raise SystemExit(
            f"Dashboard session mismatch: expected {expected_session_id}, got {state_session_id}."
        )
    session_id = expected_session_id or state_session_id or make_session_id()
    dashboard_session_binding = {
        "expected_session_id": expected_session_id,
        "state_session_id": state_session_id,
        "artifact_session_id": session_id,
        "dashboard_state_available": bool(state),
        "matched": bool(not expected_session_id or session_id == expected_session_id),
    }
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
            "nav2_layout_transform": nav2_layout_transform,
        },
    )
    if not spawn_zone.get("pass") or not spawn_ball.get("pass") or not robot_pose.get("pass"):
        raise RuntimeError(f"Demo spawn failed; see {artifact_dir / 'spawn_summary.json'}")

    pre_fetch_reposition: dict[str, Any] = {
        "phase": "nav2_reposition_before_fetch",
        "attempted": False,
        "skipped": True,
        "success": None,
        "reason": "nav2_reposition_before_fetch_disabled",
    }
    pre_fetch_reposition_samples: list[dict[str, Any]] = []
    fetch_skipped_after_reposition = False
    if bool(args.nav2_reposition_before_fetch):
        world_setup_pose = build_nav2_reposition_setup_pose(
            ball_x=args.ball_x,
            ball_y=args.ball_y,
            target_x=args.zone_x,
            target_y=args.zone_y,
            setup_standoff_m=args.nav2_reposition_setup_standoff_m,
            frame_id=args.nav2_reposition_frame_id,
        )
        world_robot_pose = dict(robot_pose.get("pose", {}) if isinstance(robot_pose.get("pose"), dict) else {})
        world_robot_pose.setdefault("x", args.robot_x)
        world_robot_pose.setdefault("y", args.robot_y)
        world_robot_pose.setdefault("yaw", args.robot_yaw)
        nav2_pose_sample: dict[str, Any] = {"available": False, "pose": None, "source": ""}
        goal_pose = dict(world_setup_pose)
        if str(args.nav2_reposition_goal_frame_mode) == "nav2_relative":
            nav2_pose_sample = wait_for_dashboard_robot_pose(
                args.dashboard_url,
                timeout_s=args.nav2_reposition_pose_wait_s,
            )
            nav2_robot_pose = nav2_pose_sample.get("pose") if isinstance(nav2_pose_sample.get("pose"), dict) else None
            if nav2_robot_pose is not None:
                goal_pose = build_nav2_relative_setup_goal(
                    world_setup_pose=world_setup_pose,
                    world_robot_pose=world_robot_pose,
                    nav2_robot_pose=nav2_robot_pose,
                    frame_id=args.nav2_reposition_frame_id,
                )
        update_runtime(
            args.gather_runtime_json,
            mission_phase="nav2_reposition",
            gather_phase="nav2_reposition",
            proof_state="visiting",
            zone_pose={"x": args.zone_x, "y": args.zone_y, "z": args.zone_z, "radius_m": args.fetch_delivery_radius_m},
            latest_feedback="Nav2 repositioning to the ball-target setup pose before local fetch.",
        )
        update_runtime(
            args.visit_runtime_json,
            mission_phase="nav2_reposition",
            proof_state="visiting",
            latest_feedback="Nav2 repositioning before contact fetch.",
        )
        pre_fetch_reposition = dispatch_nav2_reposition_before_fetch(
            compose_project=args.compose_project,
            goal_pose=goal_pose,
            timeout_s=args.nav2_reposition_timeout_s,
            server_wait_s=args.nav2_reposition_server_wait_s,
        )
        pre_fetch_reposition["skipped"] = False
        pre_fetch_reposition["goal_pose"] = goal_pose
        pre_fetch_reposition["world_setup_pose"] = world_setup_pose
        pre_fetch_reposition["world_robot_pose"] = world_robot_pose
        pre_fetch_reposition["nav2_pose_sample"] = nav2_pose_sample
        pre_fetch_reposition["goal_frame_mode"] = str(args.nav2_reposition_goal_frame_mode)
        pre_fetch_reposition["configured_timeout_s"] = round(float(args.nav2_reposition_timeout_s), 6)
        pre_fetch_reposition["configured_server_wait_s"] = round(float(args.nav2_reposition_server_wait_s), 6)
        pre_fetch_reposition["configured_pose_wait_s"] = round(float(args.nav2_reposition_pose_wait_s), 6)
        pre_fetch_reposition["continue_on_failure"] = bool(args.nav2_reposition_continue_on_failure)
        pre_fetch_reposition["stop_after_reposition"] = publish_zero_stop(args.compose_project)
        try:
            pre_fetch_reposition_samples = collect_contact_samples(
                compose_project=args.compose_project,
                world_name=args.world_name,
                robot_model_name=args.robot_model_name,
                ball_model_name=args.target_model_name,
                duration_s=0.5,
                poll_period_s=args.poll_period_s,
            )
        except Exception as exc:
            pre_fetch_reposition["post_reposition_sample_error"] = str(exc)
        if pre_fetch_reposition_samples:
            pre_fetch_reposition["post_reposition_sample_count"] = len(pre_fetch_reposition_samples)
            last_sample = pre_fetch_reposition_samples[-1]
            pre_fetch_reposition["post_reposition_robot_pose"] = last_sample.get("robot_pose")
            pre_fetch_reposition["post_reposition_ball_pose"] = last_sample.get("ball_pose")
            append_jsonl(artifact_dir / "pre_fetch_reposition_trace.jsonl", pre_fetch_reposition_samples)
        if not bool(pre_fetch_reposition.get("success", False)) and not bool(args.nav2_reposition_continue_on_failure):
            fetch_skipped_after_reposition = True
        write_json(artifact_dir / "pre_fetch_reposition.json", pre_fetch_reposition)

    update_runtime(
        args.gather_runtime_json,
        mission_phase="fetch_to_pose",
        gather_phase="fetch_to_pose",
        proof_state="fetching",
        zone_pose={"x": args.zone_x, "y": args.zone_y, "z": args.zone_z, "radius_m": args.fetch_delivery_radius_m},
        latest_feedback=(
            "Nav2 reposition failed; local contact fetch is blocked."
            if fetch_skipped_after_reposition
            else "Driving the robot forward to collect and deliver the golf ball."
        ),
    )
    contact_samples: list[dict[str, Any]] = []
    drive_output = ""
    stop_payload: dict[str, Any] = {"returncode": None, "output": "", "pass": None, "skipped": True}
    stop_publishers_payload: dict[str, Any] = {"returncode": None, "output": "", "pass": None, "skipped": True}
    if fetch_skipped_after_reposition:
        drive_output = "local contact fetch skipped because nav2 reposition before fetch failed"
        stop_payload = {"returncode": None, "output": "", "pass": None, "skipped": True, "reason": "nav2_reposition_failed"}
    elif str(args.drive_mode) == "line_servo":
        contact_samples = collect_line_servo_samples(
            compose_project=args.compose_project,
            world_name=args.world_name,
            robot_model_name=args.robot_model_name,
            ball_model_name=args.target_model_name,
            duration_s=args.sample_duration_s,
            poll_period_s=args.poll_period_s,
            delivery_target_x=args.zone_x,
            delivery_target_y=args.zone_y,
            delivery_radius_m=args.fetch_delivery_radius_m,
            delivery_stop_radius_m=delivery_stop_radius_m,
            stop_on_delivery=bool(args.stop_on_delivery),
            motion_threshold_m=args.first_contact_motion_threshold_m,
            max_linear_x_mps=args.drive_linear_x_mps,
            push_linear_x_mps=args.line_servo_push_linear_x_mps,
            min_linear_x_mps=args.line_servo_min_linear_x_mps,
            max_angular_z_rps=args.line_servo_max_angular_z_rps,
            yaw_gain=args.line_servo_yaw_gain,
            contact_lateral_ready_m=args.line_servo_contact_lateral_ready_m,
            contact_yaw_ready_rad=math.radians(args.line_servo_contact_yaw_ready_deg),
            route_label=args.planner_route_label,
        )
        stop_payload = publish_zero_stop(args.compose_project)
    else:
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
                stop_on_delivery=bool(args.stop_on_delivery),
                delivery_target_x=args.zone_x,
                delivery_target_y=args.zone_y,
                delivery_radius_m=args.fetch_delivery_radius_m,
                delivery_stop_radius_m=delivery_stop_radius_m,
            )
        finally:
            delivery_detected_while_sampling = any(
                bool(row.get("delivery_stop_triggered", False)) for row in contact_samples
            )
            if delivery_detected_while_sampling and drive_proc.poll() is None:
                stop_publishers_payload = stop_robot_drive_publishers(args.compose_project)
                drive_proc.terminate()
            try:
                drive_output, _ = drive_proc.communicate(timeout=8.0)
            except subprocess.TimeoutExpired:
                stop_publishers_payload = stop_robot_drive_publishers(args.compose_project)
                drive_proc.kill()
                try:
                    drive_output, _ = drive_proc.communicate(timeout=4.0)
                except subprocess.TimeoutExpired:
                    drive_output = ""
            stop_payload = publish_zero_stop(args.compose_project)

    delivery_stop_triggered = any(bool(row.get("delivery_stop_triggered", False)) for row in contact_samples)
    post_delivery_sample_count = 0
    if delivery_stop_triggered and float(args.post_delivery_sample_s) > 0.0:
        post_samples = collect_contact_samples(
            compose_project=args.compose_project,
            world_name=args.world_name,
            robot_model_name=args.robot_model_name,
            ball_model_name=args.target_model_name,
            duration_s=float(args.post_delivery_sample_s),
            poll_period_s=args.poll_period_s,
        )
        t_offset = float(contact_samples[-1].get("t_s", 0.0) or 0.0) + float(args.poll_period_s) if contact_samples else 0.0
        index_offset = len(contact_samples)
        for index, row in enumerate(post_samples):
            row["sample_index"] = index_offset + index
            row["t_s"] = round(t_offset + float(row.get("t_s", 0.0) or 0.0), 6)
            row["post_delivery_sample"] = True
        post_delivery_sample_count = len(post_samples)
        contact_samples.extend(post_samples)

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
    if fetch_skipped_after_reposition:
        shot_outcome = {
            **shot_outcome,
            "pass": False,
            "reason": "nav2_reposition_failed_before_fetch",
            "nav2_reposition": pre_fetch_reposition,
        }
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
    model_provenance = fetch_model_provenance(
        mission_objective=args.mission_objective,
        target_model_sdf=args.target_model_sdf,
        zone_model_sdf=args.zone_model_sdf,
    )
    pass_flag = bool(shot_outcome.get("pass", False))
    pre_fetch_elapsed_s = float(pre_fetch_reposition.get("elapsed_s", 0.0) or 0.0)
    mission_time_s = pre_fetch_elapsed_s + (0.0 if fetch_skipped_after_reposition else max(float(args.sample_duration_s), float(args.drive_duration_s)))
    random_draw = target_layout.get("random_draw", {}) if isinstance(target_layout.get("random_draw"), dict) else {}
    random_profile = str(target_layout.get("random_profile", "") or random_draw.get("random_profile", ""))
    planner_route_label = str(args.planner_route_label or target_layout.get("planner_route_label", "") or random_draw.get("planner_route_label", "") or "")
    route_executor = str(args.route_executor or target_layout.get("route_executor", "") or random_draw.get("route_executor", "") or "")
    forward_only_pre_contact = bool(float(args.drive_linear_x_mps) >= -1e-9)
    route_quality = (
        planner_route_defaults.get("route_quality", {})
        if isinstance(planner_route_defaults.get("route_quality"), dict)
        else random_draw.get("route_quality", {})
        if isinstance(random_draw.get("route_quality"), dict)
        else target_layout.get("route_quality", {})
        if isinstance(target_layout.get("route_quality"), dict)
        else {}
    )
    route_metadata = {
        "planner_route_label": planner_route_label,
        "route_executor": route_executor,
        "executor_actual": "golf_ball_circle_delivery_demo_runner",
        "route_quality": route_quality,
        "pre_fetch_reposition": pre_fetch_reposition,
        "nav2_reposition_before_fetch": bool(args.nav2_reposition_before_fetch),
        "nav2_reposition_required": bool(args.nav2_reposition_before_fetch),
        "nav2_reposition_success": pre_fetch_reposition.get("success"),
        "nav2_reposition_dispatch_status": str(pre_fetch_reposition.get("dispatch_status", "")),
        "nav2_reposition_status_text": str(pre_fetch_reposition.get("status_text", "")),
        "nav2_reposition_goal_pose": pre_fetch_reposition.get("goal_pose", {}),
        "nav2_layout_transform": nav2_layout_transform,
        "planner_route_execution_defaults": planner_route_defaults,
        "fetch_skipped_after_reposition": bool(fetch_skipped_after_reposition),
        "contact_phase_forward_only": bool(float(args.drive_linear_x_mps) >= -1e-9),
        "forward_only_pre_contact_required": bool(args.forward_only_pre_contact_required),
        "forward_only_pre_contact": forward_only_pre_contact,
        "stop_on_delivery": bool(args.stop_on_delivery),
        "delivery_stop_radius_m": round(float(delivery_stop_radius_m), 6),
        "delivery_stop_triggered": bool(delivery_stop_triggered),
        "post_delivery_sample_s": round(float(args.post_delivery_sample_s), 6),
        "post_delivery_sample_count": int(post_delivery_sample_count),
        "drive_stop_publishers": stop_publishers_payload,
        "drive_linear_x_mps": round(float(args.drive_linear_x_mps), 6),
        "drive_duration_s": round(float(args.drive_duration_s), 6),
        "drive_mode": str(args.drive_mode),
        "line_servo_push_linear_x_mps": round(float(args.line_servo_push_linear_x_mps), 6),
        "line_servo_min_linear_x_mps": round(float(args.line_servo_min_linear_x_mps), 6),
        "line_servo_max_angular_z_rps": round(float(args.line_servo_max_angular_z_rps), 6),
        "line_servo_yaw_gain": round(float(args.line_servo_yaw_gain), 6),
        "line_servo_contact_lateral_ready_m": round(float(args.line_servo_contact_lateral_ready_m), 6),
        "line_servo_contact_yaw_ready_deg": round(float(args.line_servo_contact_yaw_ready_deg), 6),
    }
    route_metadata.update(summarize_line_servo_effective_command(contact_samples))
    if fetch_skipped_after_reposition:
        pass_flag = False
    if bool(args.forward_only_pre_contact_required) and not forward_only_pre_contact:
        pass_flag = False
        shot_outcome = {
            **shot_outcome,
            "pass": False,
            "reason": "forward_only_pre_contact_violation",
        }
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
        "model_provenance": model_provenance,
        "model_provenance_valid": bool(model_provenance.get("model_provenance_valid", True)),
        "target_model_classification": str(model_provenance.get("target_model_classification", "")),
        "target_model_radius_m": model_provenance.get("target_model_radius_m"),
        "random_profile": random_profile,
        "random_draw": random_draw,
        "planner_route": route_metadata,
        "pre_fetch_reposition": pre_fetch_reposition,
        "nav2_layout_transform": nav2_layout_transform,
        "planner_route_execution_defaults": planner_route_defaults,
        "dashboard_session_binding": dashboard_session_binding,
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
        "model_provenance": model_provenance,
        "model_provenance_valid": bool(model_provenance.get("model_provenance_valid", True)),
        "target_model_classification": str(model_provenance.get("target_model_classification", "")),
        "target_model_radius_m": model_provenance.get("target_model_radius_m"),
        "pass": pass_flag,
        "mission_completed_pass": pass_flag,
        "fetch_to_pose_reached": pass_flag,
        "fetch_to_pose_pass": pass_flag,
        "fetch_delivery_radius_m": round(float(args.fetch_delivery_radius_m), 6),
        "fetch_pose_world": shot_outcome["fetch_pose_world"],
        "target_layout_json": str(args.target_layout_json or ""),
        "target_layout": target_layout,
        "random_profile": random_profile,
        "random_draw": random_draw,
        "planner_route": route_metadata,
        "session_id": session_id,
        "dashboard_session_binding": dashboard_session_binding,
        "pre_fetch_reposition": pre_fetch_reposition,
        "nav2_layout_transform": nav2_layout_transform,
        "planner_route_label": planner_route_label,
        "route_executor": route_executor,
        "forward_only_pre_contact_required": bool(args.forward_only_pre_contact_required),
        "forward_only_pre_contact": forward_only_pre_contact,
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
            f"- First-contact quality: `{bool(approach_metrics.get('first_contact_quality_pass', False))}`",
            f"- Approach flags: `{approach_metrics.get('flags', [])}`",
            f"- First-contact flags: `{approach_metrics.get('first_contact_quality_flags', [])}`",
            f"- Planner route: `{planner_route_label}`",
            f"- Route executor: `{route_executor}`",
            f"- Nav2 reposition before fetch: `{bool(args.nav2_reposition_before_fetch)}` "
            f"`{pre_fetch_reposition.get('dispatch_status', 'skipped')}` "
            f"`{pre_fetch_reposition.get('status_text', '')}`",
            f"- Drive mode: `{args.drive_mode}`",
            f"- Delivery stop radius: `{delivery_stop_radius_m:.3f}m`",
            f"- Model provenance: `{bool(model_provenance.get('model_provenance_valid', False))}` "
            f"`{model_provenance.get('model_provenance_reason', '')}`",
            f"- Forward-only pre-contact: `{forward_only_pre_contact}`",
            f"- Ball start: `{shot_outcome.get('ball_start_pose', {})}`",
            f"- Ball end: `{shot_outcome.get('ball_end_pose', {})}`",
            "",
        ]
    )

    write_json(
        artifact_dir / "drive_summary.json",
        {
            "drive_output": drive_output,
            "stop": stop_payload,
            "planner_route": route_metadata,
            "pre_fetch_reposition": pre_fetch_reposition,
            "fetch_skipped_after_reposition": bool(fetch_skipped_after_reposition),
        },
    )
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
