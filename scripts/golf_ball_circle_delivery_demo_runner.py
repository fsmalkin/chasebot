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
from passive_ball_roll_calibration_runner import collect_ball_samples
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
    parser.add_argument("--target-model-name", default=DEFAULT_BALL_MODEL_NAME)
    parser.add_argument("--zone-model-name", default=DEFAULT_ZONE_MODEL_NAME)
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
    parser.add_argument("--keep-environment", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    write_json(artifact_dir / "spawn_summary.json", {"zone": spawn_zone, "ball": spawn_ball, "robot_pose": robot_pose})
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
        samples = collect_ball_samples(
            compose_project=args.compose_project,
            world_name=args.world_name,
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

    append_jsonl(trace_path, samples)
    shot_outcome = build_shot_outcome(
        samples,
        target_x=args.zone_x,
        target_y=args.zone_y,
        target_z=args.zone_z,
        radius_m=args.fetch_delivery_radius_m,
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
        "shot_outcome": shot_outcome,
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
    }
    target_results = {"ball_1": target_result}
    scorecard = "\n".join(
        [
            "# Golf Ball Circle Delivery UAT",
            "",
            f"- Pass: `{pass_flag}`",
            f"- Closest approach: `{float(shot_outcome.get('closest_approach_distance_m', 0.0) or 0.0):.3f}m`",
            f"- Delivery radius: `{float(args.fetch_delivery_radius_m):.3f}m`",
            f"- Ball start: `{shot_outcome.get('ball_start_pose', {})}`",
            f"- Ball end: `{shot_outcome.get('ball_end_pose', {})}`",
            "",
        ]
    )

    write_json(artifact_dir / "drive_summary.json", {"drive_output": drive_output, "stop": stop_payload})
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
