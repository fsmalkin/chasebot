#!/usr/bin/env python3
"""Seeded multi-ball retrieval planning gate.

This gate is the first multi-ball layer above the current one-ball
``fetch_to_pose`` primitive. It generates bounded field scenes, plans a
retrieval order, materializes one local-fetch layout per ball, and records the
commands needed for visual UAT.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import fetch_planner_handoff_gate as planner_gate
import fetch_planner_route_replay_batch as replay_batch
from golf_ball_circle_delivery_demo_runner import set_model_pose
from passive_ball_roll_calibration_runner import DEFAULT_WORLD_NAME
from passive_ball_roll_calibration_runner import remove_model
from passive_ball_roll_calibration_runner import spawn_model


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
GATE_KIND = "fetch_multiball_retrieval_gate"
DEFAULT_SEED = 20260606
DEFAULT_RANDOM_CASES = 6
DEFAULT_BALLS_PER_SCENE = 3
DEFAULT_PROFILE = "open_field_multiball_v1"
DEFAULT_FIELD_BOUNDS = {
    "x_min_m": -1.20,
    "x_max_m": 2.20,
    "y_min_m": -1.35,
    "y_max_m": 1.35,
}
BALL_TARGET_DISTANCE_RANGE_M = (0.45, 0.84)
ROBOT_TARGET_DISTANCE_RANGE_M = (0.70, 1.75)
MIN_BALL_SEPARATION_M = 0.34
MIN_ROBOT_BALL_SEPARATION_M = 0.30
SETUP_STANDOFF_M = 0.38
CORRIDOR_INTERFERENCE_RADIUS_M = 0.22
TARGET_MODEL_NAME_PREFIX = "visit_mission_target_multiball_fetch"
DEFAULT_BALL_SDF = REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf"
MISSION_SUMMARY_MARKER = replay_batch.MISSION_SUMMARY_MARKER
VISUAL_PACKAGE_MARKER = replay_batch.VISUAL_PACKAGE_MARKER

ROUTE_PENALTY = {
    planner_gate.ROUTE_FETCH_READY: 0.00,
    planner_gate.ROUTE_RECOVERY_OR_REAIM: 0.22,
    planner_gate.ROUTE_NAV2_REPOSITION: 0.45,
    planner_gate.ROUTE_SCAN_OR_PERCEIVE: 3.00,
    planner_gate.ROUTE_NO_GO: 9.00,
}
EXECUTABLE_ROUTES = {
    planner_gate.ROUTE_FETCH_READY,
    planner_gate.ROUTE_NAV2_REPOSITION,
    planner_gate.ROUTE_RECOVERY_OR_REAIM,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return cleaned.strip("_") or "scene"


def target_model_name_for_ball(scene_id: str, ball_id: str) -> str:
    return f"{TARGET_MODEL_NAME_PREFIX}_{safe_id(scene_id)}_{safe_id(str(ball_id or 'ball'))}"


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def normalize_angle_rad(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def round_pose(x: float, y: float, *, z: float = 0.0, yaw: float = 0.0) -> dict[str, float]:
    return {
        "x": round(float(x), 6),
        "y": round(float(y), 6),
        "z": round(float(z), 6),
        "yaw": round(float(yaw), 6),
    }


def target_pose() -> dict[str, float]:
    return dict(planner_gate.FETCH_TARGET_POSE)


def in_field_bounds(x: float, y: float, bounds: dict[str, float] | None = None) -> bool:
    clean = bounds or DEFAULT_FIELD_BOUNDS
    return bool(
        finite_float(clean.get("x_min_m"), -999.0) <= x <= finite_float(clean.get("x_max_m"), 999.0)
        and finite_float(clean.get("y_min_m"), -999.0) <= y <= finite_float(clean.get("y_max_m"), 999.0)
    )


def pose_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(finite_float(a.get("x")) - finite_float(b.get("x")), finite_float(a.get("y")) - finite_float(b.get("y")))


def point_segment_distance(point: dict[str, Any], start: dict[str, Any], end: dict[str, Any]) -> float:
    px = finite_float(point.get("x"))
    py = finite_float(point.get("y"))
    sx = finite_float(start.get("x"))
    sy = finite_float(start.get("y"))
    ex = finite_float(end.get("x"))
    ey = finite_float(end.get("y"))
    vx = ex - sx
    vy = ey - sy
    length_sq = vx * vx + vy * vy
    if length_sq <= 1e-12:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / length_sq))
    proj_x = sx + t * vx
    proj_y = sy + t * vy
    return math.hypot(px - proj_x, py - proj_y)


def ball_target_geometry(ball_pose: dict[str, Any], robot_pose: dict[str, Any]) -> dict[str, Any]:
    target = target_pose()
    target_x = finite_float(target.get("x"))
    target_y = finite_float(target.get("y"))
    ball_x = finite_float(ball_pose.get("x"))
    ball_y = finite_float(ball_pose.get("y"))
    robot_x = finite_float(robot_pose.get("x"))
    robot_y = finite_float(robot_pose.get("y"))
    robot_yaw = finite_float(robot_pose.get("yaw"))
    line_yaw = math.atan2(target_y - ball_y, target_x - ball_x)
    ux = math.cos(line_yaw)
    uy = math.sin(line_yaw)
    dx = robot_x - ball_x
    dy = robot_y - ball_y
    lateral_signed = (-uy * dx) + (ux * dy)
    return {
        "ball_target_distance_m": round(math.hypot(target_x - ball_x, target_y - ball_y), 6),
        "ball_target_angle_deg": round(math.degrees(line_yaw), 6),
        "robot_ball_distance_m": round(math.hypot(robot_x - ball_x, robot_y - ball_y), 6),
        "robot_lateral_error_m": round(abs(lateral_signed), 6),
        "robot_lateral_signed_m": round(lateral_signed, 6),
        "robot_yaw_error_deg": round(math.degrees(normalize_angle_rad(robot_yaw - line_yaw)), 6),
    }


def setup_pose_for_ball(ball_pose: dict[str, Any], *, standoff_m: float = SETUP_STANDOFF_M) -> dict[str, float]:
    target = target_pose()
    ball_x = finite_float(ball_pose.get("x"))
    ball_y = finite_float(ball_pose.get("y"))
    line_yaw = math.atan2(finite_float(target.get("y")) - ball_y, finite_float(target.get("x")) - ball_x)
    return round_pose(
        ball_x - float(standoff_m) * math.cos(line_yaw),
        ball_y - float(standoff_m) * math.sin(line_yaw),
        yaw=line_yaw,
    )


def estimated_post_fetch_robot_pose(ball_pose: dict[str, Any], *, standoff_m: float = 0.28) -> dict[str, float]:
    target = target_pose()
    line_yaw = math.atan2(
        finite_float(target.get("y")) - finite_float(ball_pose.get("y")),
        finite_float(target.get("x")) - finite_float(ball_pose.get("x")),
    )
    return round_pose(
        finite_float(target.get("x")) - float(standoff_m) * math.cos(line_yaw),
        finite_float(target.get("y")) - float(standoff_m) * math.sin(line_yaw),
        yaw=line_yaw,
    )


def corridor_interference_count(ball: dict[str, Any], remaining_balls: list[dict[str, Any]]) -> int:
    target = target_pose()
    count = 0
    for other in remaining_balls:
        if str(other.get("id", "")) == str(ball.get("id", "")):
            continue
        distance = point_segment_distance(other.get("pose", {}), ball.get("pose", {}), target)
        if distance <= CORRIDOR_INTERFERENCE_RADIUS_M:
            count += 1
    return count


def sample_robot_pose(rng: random.Random) -> dict[str, float]:
    target = target_pose()
    distance_m = rng.uniform(*ROBOT_TARGET_DISTANCE_RANGE_M)
    angle_rad = rng.uniform(-math.pi, math.pi)
    x = finite_float(target.get("x")) - distance_m * math.cos(angle_rad)
    y = finite_float(target.get("y")) - distance_m * math.sin(angle_rad)
    if not in_field_bounds(x, y):
        x = max(finite_float(DEFAULT_FIELD_BOUNDS["x_min_m"]), min(finite_float(DEFAULT_FIELD_BOUNDS["x_max_m"]), x))
        y = max(finite_float(DEFAULT_FIELD_BOUNDS["y_min_m"]), min(finite_float(DEFAULT_FIELD_BOUNDS["y_max_m"]), y))
    yaw_to_target = math.atan2(finite_float(target.get("y")) - y, finite_float(target.get("x")) - x)
    yaw = normalize_angle_rad(yaw_to_target + math.radians(rng.uniform(-50.0, 50.0)))
    return round_pose(x, y, yaw=yaw)


def sample_ball_pose(rng: random.Random) -> dict[str, float]:
    target = target_pose()
    distance_m = rng.uniform(*BALL_TARGET_DISTANCE_RANGE_M)
    angle_rad = rng.uniform(-math.pi, math.pi)
    return round_pose(
        finite_float(target.get("x")) - distance_m * math.cos(angle_rad),
        finite_float(target.get("y")) - distance_m * math.sin(angle_rad),
        z=0.021336,
    )


def generate_multiball_scenes(
    *,
    seed: int,
    random_cases: int,
    balls_per_scene: int,
    profile: str = DEFAULT_PROFILE,
) -> list[dict[str, Any]]:
    rng = random.Random(int(seed))
    scenes: list[dict[str, Any]] = []
    case_count = max(int(random_cases), 1)
    ball_count = max(int(balls_per_scene), 2)
    for scene_index in range(1, case_count + 1):
        robot_pose = sample_robot_pose(rng)
        balls: list[dict[str, Any]] = []
        rejection_count = 0
        attempts = 0
        while len(balls) < ball_count and attempts < 1000:
            attempts += 1
            pose = sample_ball_pose(rng)
            distance_to_target = pose_distance(pose, target_pose())
            if distance_to_target <= finite_float(target_pose().get("radius_m")) + 0.12:
                rejection_count += 1
                continue
            if not in_field_bounds(finite_float(pose.get("x")), finite_float(pose.get("y"))):
                rejection_count += 1
                continue
            if pose_distance(pose, robot_pose) < MIN_ROBOT_BALL_SEPARATION_M:
                rejection_count += 1
                continue
            if any(pose_distance(pose, other.get("pose", {})) < MIN_BALL_SEPARATION_M for other in balls):
                rejection_count += 1
                continue
            ball_id = f"ball_{len(balls) + 1}"
            balls.append(
                {
                    "id": ball_id,
                    "label": f"retrieval target {len(balls) + 1}",
                    "pose": pose,
                    "target_geometry": ball_target_geometry(pose, robot_pose),
                }
            )
        if len(balls) < ball_count:
            raise RuntimeError(f"Unable to generate bounded multi-ball scene {scene_index} after {attempts} attempts.")
        scene_id = f"seed{int(seed)}_multiball_scene{scene_index:02d}"
        scenes.append(
            {
                "generated_utc": utc_now(),
                "type": "fetch_multiball_scene_descriptor",
                "profile": profile,
                "scene_id": scene_id,
                "seed": int(seed),
                "case_index": scene_index,
                "target_pose": target_pose(),
                "robot_pose": robot_pose,
                "balls": balls,
                "field_bounds": dict(DEFAULT_FIELD_BOUNDS),
                "randomization": {
                    "ball_target_distance_range_m": list(BALL_TARGET_DISTANCE_RANGE_M),
                    "robot_target_distance_range_m": list(ROBOT_TARGET_DISTANCE_RANGE_M),
                    "min_ball_separation_m": MIN_BALL_SEPARATION_M,
                    "min_robot_ball_separation_m": MIN_ROBOT_BALL_SEPARATION_M,
                    "rejection_count": rejection_count,
                    "attempt_count": attempts,
                },
                "constraints": {
                    "robot_owned_contact": True,
                    "no_direct_ball_impulse": True,
                    "local_fetch_primitive": "planner_routed_fetch_to_pose",
                },
            }
        )
    return scenes


def scene_from_multiball_target(
    *,
    multiball_scene: dict[str, Any],
    ball: dict[str, Any],
    robot_pose: dict[str, Any],
    step_index: int,
) -> dict[str, Any]:
    pose = ball.get("pose") if isinstance(ball.get("pose"), dict) else {}
    scene = {
        "generated_utc": utc_now(),
        "type": "fetch_planner_scene_descriptor",
        "scene_set": DEFAULT_PROFILE,
        "scene_id": f"{multiball_scene.get('scene_id', 'scene')}_{ball.get('id', 'ball')}_step{step_index:02d}",
        "expected_route_label": "",
        "target_pose": target_pose(),
        "ball_pose": pose,
        "robot_pose": robot_pose,
        "perception": {
            "ball_confidence": 0.98,
            "target_confidence": 0.99,
            "state_age_s": 0.15,
        },
        "corridor": {
            "blocked": False,
            "clearance_m": 0.35,
            "unsafe_drift_m": 0.0,
        },
        "geometry": ball_target_geometry(pose, robot_pose),
        "local_fetch_envelope": {
            "eligible": False,
            "delivery_radius_m": round(finite_float(target_pose().get("radius_m")), 6),
            "requires_robot_owned_contact": True,
            "no_direct_ball_impulse": True,
        },
        "multiball_context": {
            "parent_scene_id": str(multiball_scene.get("scene_id", "") or ""),
            "ball_id": str(ball.get("id", "") or ""),
            "step_index": int(step_index),
            "remaining_ball_count": len(multiball_scene.get("balls", []) if isinstance(multiball_scene.get("balls"), list) else []),
        },
    }
    planner_gate._augment_spatial_generalization_geometry(scene)
    route_label = planner_gate.deterministic_route_label(scene)
    admissibility = planner_gate.route_admissibility_for_scene(scene, route_label)
    if bool(admissibility.get("changed", False)):
        route_label = str(admissibility.get("route_label", route_label) or route_label)
    scene["expected_route_label"] = route_label
    planner_gate._refresh_local_fetch_envelope(scene)
    return scene


def candidate_cost(
    *,
    ball: dict[str, Any],
    robot_pose: dict[str, Any],
    remaining_balls: list[dict[str, Any]],
    route_label: str,
    route_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    setup_pose = setup_pose_for_ball(ball.get("pose", {}))
    travel_distance_m = pose_distance(robot_pose, setup_pose)
    ball_target_distance_m = pose_distance(ball.get("pose", {}), target_pose())
    interference_count = corridor_interference_count(ball, remaining_balls)
    quality = route_quality if isinstance(route_quality, dict) else {}
    quality_flags = {str(flag) for flag in quality.get("flags", [])} if isinstance(quality.get("flags"), list) else set()
    first_contact_risk = str(quality.get("predicted_first_contact_risk", "") or "").strip()
    predicted_contact_quality = str(quality.get("predicted_contact_quality", "") or "").strip()
    predicted_first_contact_quality = str(quality.get("predicted_first_contact_quality", "") or "").strip()
    setup_debt = quality.get("setup_debt") if isinstance(quality.get("setup_debt"), dict) else {}
    ball_target_angle_abs_deg = abs(finite_float(setup_debt.get("ball_target_angle_abs_deg"), 0.0))
    route_quality_score = finite_float(quality.get("quality_score"), 100.0)

    route_quality_deficit_penalty = max(0.0, (82.0 - route_quality_score) / 82.0)
    direction_alignment_penalty = min(max(ball_target_angle_abs_deg - 12.0, 0.0) / 70.0, 1.45)
    blocker_penalty = 0.0
    if predicted_contact_quality == "blocker" or predicted_first_contact_quality == "blocker":
        blocker_penalty += 1.15
    if "nav2_reposition_near_field_not_admissible" in quality_flags:
        blocker_penalty += 0.80
    if "opposite_side_of_circle" in quality_flags:
        blocker_penalty += 0.35

    quality_penalty = 0.0
    if first_contact_risk == "high":
        quality_penalty += 0.65
    elif first_contact_risk == "medium":
        quality_penalty += 0.25
    if predicted_contact_quality == "watch":
        quality_penalty += 0.10
    if str(route_label) == planner_gate.ROUTE_RECOVERY_OR_REAIM and "ball_behind_robot_heading" in quality_flags:
        quality_penalty += 0.35
    if str(route_label) == planner_gate.ROUTE_RECOVERY_OR_REAIM and "initial_yaw_setup_debt" in quality_flags:
        quality_penalty += 0.20
    cost = (
        travel_distance_m
        + 0.18 * ball_target_distance_m
        + ROUTE_PENALTY.get(str(route_label), 5.0)
        + 0.40 * interference_count
        + quality_penalty
        + route_quality_deficit_penalty
        + direction_alignment_penalty
        + blocker_penalty
    )
    return {
        "score": round(float(cost), 6),
        "travel_distance_to_setup_m": round(float(travel_distance_m), 6),
        "ball_target_distance_m": round(float(ball_target_distance_m), 6),
        "route_penalty": round(float(ROUTE_PENALTY.get(str(route_label), 5.0)), 6),
        "quality_penalty": round(float(quality_penalty), 6),
        "route_quality_deficit_penalty": round(float(route_quality_deficit_penalty), 6),
        "direction_alignment_penalty": round(float(direction_alignment_penalty), 6),
        "blocker_penalty": round(float(blocker_penalty), 6),
        "corridor_interference_count": int(interference_count),
        "setup_pose": setup_pose,
    }


def decide_single_ball_scene(
    scene: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    return planner_gate.decide_scene(
        scene,
        planner_mode=str(args.planner_mode),
        openai_api_key=str(args.openai_api_key or ""),
        openai_model=str(args.openai_model or planner_gate.DEFAULT_OPENAI_MODEL),
        openai_base_url=str(args.openai_base_url or planner_gate.DEFAULT_OPENAI_BASE_URL),
        openai_org_id=str(args.openai_org_id or ""),
        openai_project_id=str(args.openai_project_id or ""),
        reasoning_effort=str(args.reasoning_effort or planner_gate.DEFAULT_REASONING_EFFORT),
        timeout_s=float(args.planner_timeout_s),
    )


def plan_multiball_scene(scene: dict[str, Any], *, args: argparse.Namespace) -> dict[str, Any]:
    remaining = [dict(ball) for ball in scene.get("balls", []) if isinstance(ball, dict)]
    current_robot_pose = dict(scene.get("robot_pose", {}) if isinstance(scene.get("robot_pose"), dict) else {})
    sequence: list[dict[str, Any]] = []
    all_candidates_by_step: list[dict[str, Any]] = []
    for step_index in range(1, len(remaining) + 1):
        candidates: list[dict[str, Any]] = []
        for ball in remaining:
            one_ball_scene = scene_from_multiball_target(
                multiball_scene=scene,
                ball=ball,
                robot_pose=current_robot_pose,
                step_index=step_index,
            )
            decision = decide_single_ball_scene(one_ball_scene, args=args)
            cost = candidate_cost(
                ball=ball,
                robot_pose=current_robot_pose,
                remaining_balls=remaining,
                route_label=str(decision.get("route_label", "")),
                route_quality=decision.get("route_quality") if isinstance(decision.get("route_quality"), dict) else {},
            )
            candidates.append(
                {
                    "ball_id": str(ball.get("id", "") or ""),
                    "one_ball_scene": one_ball_scene,
                    "decision": decision,
                    "cost": cost,
                    "executable_route": str(decision.get("route_label", "")) in EXECUTABLE_ROUTES,
                }
            )
        candidates = sorted(
            candidates,
            key=lambda row: (
                finite_float((row.get("cost") or {}).get("score"), 999.0),
                str(row.get("ball_id", "")),
            ),
        )
        selected = candidates[0]
        selected_ball_id = str(selected.get("ball_id", "") or "")
        selected_ball = next(ball for ball in remaining if str(ball.get("id", "")) == selected_ball_id)
        selected_step = {
            "step_index": step_index,
            "ball_id": selected_ball_id,
            "ball_pose": selected_ball.get("pose", {}),
            "route_label": str((selected.get("decision") or {}).get("route_label", "") or ""),
            "route_executor": str((selected.get("decision") or {}).get("route_executor", "") or ""),
            "maneuver_plan": (selected.get("decision") or {}).get("maneuver_plan", {}),
            "route_quality": (selected.get("decision") or {}).get("route_quality", {}),
            "cost": selected.get("cost", {}),
            "one_ball_scene": selected.get("one_ball_scene", {}),
            "decision": selected.get("decision", {}),
            "estimated_start_robot_pose": current_robot_pose,
            "estimated_setup_pose": (selected.get("cost") or {}).get("setup_pose", {}),
            "estimated_post_fetch_robot_pose": estimated_post_fetch_robot_pose(selected_ball.get("pose", {})),
            "executable_route": bool(selected.get("executable_route", False)),
        }
        sequence.append(selected_step)
        all_candidates_by_step.append(
            {
                "step_index": step_index,
                "current_robot_pose": current_robot_pose,
                "candidates": [
                    {
                        "ball_id": str(candidate.get("ball_id", "") or ""),
                        "route_label": str((candidate.get("decision") or {}).get("route_label", "") or ""),
                        "route_executor": str((candidate.get("decision") or {}).get("route_executor", "") or ""),
                        "route_quality": (candidate.get("decision") or {}).get("route_quality", {}),
                        "cost": candidate.get("cost", {}),
                        "executable_route": bool(candidate.get("executable_route", False)),
                    }
                    for candidate in candidates
                ],
            }
        )
        current_robot_pose = estimated_post_fetch_robot_pose(selected_ball.get("pose", {}))
        remaining = [ball for ball in remaining if str(ball.get("id", "")) != selected_ball_id]
    executable_count = sum(1 for step in sequence if bool(step.get("executable_route", False)))
    return {
        "scene_id": str(scene.get("scene_id", "") or ""),
        "planner_mode": str(args.planner_mode),
        "profile": str(scene.get("profile", DEFAULT_PROFILE) or DEFAULT_PROFILE),
        "target_pose": scene.get("target_pose", {}),
        "initial_robot_pose": scene.get("robot_pose", {}),
        "ball_count": len(scene.get("balls", []) if isinstance(scene.get("balls"), list) else []),
        "retrieval_order": [step.get("ball_id", "") for step in sequence],
        "sequence": sequence,
        "candidate_audit": all_candidates_by_step,
        "executable_step_count": executable_count,
        "planner_ready": bool(executable_count == len(sequence) and sequence),
    }


def write_layout_for_step(root: Path, scene_id: str, step: dict[str, Any]) -> Path:
    ball_id = safe_id(str(step.get("ball_id", "ball") or "ball"))
    layout_path = ensure_dir(root / "target_layouts") / f"{safe_id(scene_id)}_step{int(step.get('step_index', 0)):02d}_{ball_id}.json"
    planner_gate.write_fetch_ready_layout_from_scene(
        layout_path,
        step.get("one_ball_scene", {}) if isinstance(step.get("one_ball_scene"), dict) else {},
        route_label=str(step.get("route_label", "") or ""),
        route_executor=str(step.get("route_executor", "") or ""),
    )
    layout = read_json(layout_path)
    layout["multiball_scene_id"] = scene_id
    layout["multiball_ball_id"] = str(step.get("ball_id", "") or "")
    layout["multiball_step_index"] = int(step.get("step_index", 0) or 0)
    layout["multiball_estimated_start_robot_pose"] = step.get("estimated_start_robot_pose", {})
    layout["multiball_estimated_setup_pose"] = step.get("estimated_setup_pose", {})
    layout["multiball_estimated_post_fetch_robot_pose"] = step.get("estimated_post_fetch_robot_pose", {})
    write_json(layout_path, layout)
    return layout_path


def build_step_command(
    *,
    args: argparse.Namespace,
    layout_path: Path,
    scene_id: str,
    step: dict[str, Any],
    compose_project: str = "",
    expected_session_id: str = "",
) -> list[str]:
    target_model_name = target_model_name_for_ball(scene_id, str(step.get("ball_id", "ball") or "ball"))
    robot_pose = step.get("estimated_start_robot_pose") if isinstance(step.get("estimated_start_robot_pose"), dict) else {}
    if not robot_pose:
        one_ball_scene = step.get("one_ball_scene") if isinstance(step.get("one_ball_scene"), dict) else {}
        robot_pose = one_ball_scene.get("robot_pose") if isinstance(one_ball_scene.get("robot_pose"), dict) else {}
    command = [
        str(args.python_exe or sys.executable),
        str(REPO_ROOT / "scripts" / "golf_ball_circle_delivery_demo_runner.py"),
        "--scenario-id",
        "fetch_multiball_retrieval_v1",
        "--scenario-label",
        "Multi-Ball Retrieval v1",
        "--target-layout-json",
        str(layout_path),
        "--target-model-name",
        target_model_name,
        "--fetch-delivery-radius-m",
        f"{float(args.fetch_delivery_radius_m):.3f}",
        "--forward-only-pre-contact-required",
        "--ai-push-coast-mode",
        "guarded_live",
    ]
    if str(step.get("route_label", "") or "") == planner_gate.ROUTE_NAV2_REPOSITION:
        command.extend(
            [
                "--nav2-reposition-before-fetch",
                "--nav2-reposition-goal-frame-mode",
                str(getattr(args, "nav2_goal_frame_mode", "world_direct") or "world_direct"),
                "--nav2-reposition-timeout-s",
                "48.000",
                "--nav2-reposition-server-wait-s",
                "8.000",
                "--nav2-reposition-pose-wait-s",
                "2.500",
                "--nav2-pre-setup-standoff-m",
                "0.900",
                "--nav2-reposition-refine-attempts",
                "1",
            ]
        )
    if bool(getattr(args, "persistent_field", False)):
        command.extend(
            [
                "--use-existing-target-model",
                "--preserve-robot-pose",
                "--pre-fetch-setup-correction-s",
                "14.000",
            ]
        )
    if robot_pose:
        command.extend(
            [
                "--robot-x",
                f"{finite_float(robot_pose.get('x')):.6f}",
                "--robot-y",
                f"{finite_float(robot_pose.get('y')):.6f}",
                "--robot-yaw",
                f"{finite_float(robot_pose.get('yaw')):.6f}",
            ]
        )
    if str(args.dashboard_url or "").strip():
        command.extend(["--dashboard-url", str(args.dashboard_url).strip()])
    run_compose_project = str(compose_project or args.compose_project or "").strip()
    if run_compose_project:
        command.extend(["--compose-project", run_compose_project])
    if str(expected_session_id or "").strip():
        command.extend(["--expected-session-id", str(expected_session_id).strip()])
    return command


def session_id_for_artifact_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(SESSION_ROOT.resolve())
    except ValueError:
        return ""
    return rel.parts[0] if rel.parts else ""


def build_visual_package_command(
    *,
    args: argparse.Namespace,
    campaign_id: str,
    mission_summary_paths: list[Path],
) -> list[str]:
    command = [
        str(args.python_exe or sys.executable),
        str(REPO_ROOT / "scripts" / "fetch_visual_uat_package.py"),
        "--campaign-id",
        f"{campaign_id}_visual_package",
    ]
    seen_visual_dirs: set[str] = set()
    for mission_path in mission_summary_paths:
        command.extend(["--mission-summary", str(mission_path)])
        session_id = session_id_for_artifact_path(mission_path)
        if session_id:
            visual_dir = SESSION_ROOT / session_id / "visual"
            visual_key = str(visual_dir.resolve())
            if visual_key not in seen_visual_dirs:
                command.extend(["--visual-dir", str(visual_dir)])
                seen_visual_dirs.add(visual_key)
    return command


def run_command(command: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
    timeout = max(float(timeout_s), 1.0)
    try:
        return subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        stderr_text = f"{stderr}\ntimeout_after_s={timeout:.3f}".strip()
        return subprocess.CompletedProcess(command, 124, stdout=str(stdout or ""), stderr=stderr_text)


def extract_marker(output: str, marker: str) -> str:
    for line in str(output or "").splitlines():
        if marker in line:
            return line.split(marker, 1)[1].strip()
    return ""


def write_scene_artifacts(root: Path, scene: dict[str, Any], plan: dict[str, Any]) -> dict[str, str]:
    scene_id = safe_id(str(scene.get("scene_id", "scene") or "scene"))
    scene_path = ensure_dir(root / "scene_descriptors") / f"{scene_id}.json"
    plan_path = ensure_dir(root / "sequence_plans") / f"{scene_id}.json"
    write_json(scene_path, scene)
    write_json(plan_path, plan)
    return {
        "scene_path": artifact_display_path(scene_path),
        "sequence_plan_path": artifact_display_path(plan_path),
    }


def prepare_persistent_field_scene(
    *,
    scene: dict[str, Any],
    compose_project: str,
    world_name: str = DEFAULT_WORLD_NAME,
) -> dict[str, Any]:
    scene_id = str(scene.get("scene_id", "scene") or "scene")
    balls = [ball for ball in scene.get("balls", []) if isinstance(ball, dict)]
    robot_pose = scene.get("robot_pose", {}) if isinstance(scene.get("robot_pose"), dict) else {}
    payload: dict[str, Any] = {
        "enabled": True,
        "scene_id": scene_id,
        "compose_project": compose_project,
        "world_name": world_name,
        "ball_model_sdf": artifact_display_path(REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf"),
        "ball_count": len(balls),
        "balls": [],
        "robot_pose": {},
        "pass": False,
    }
    if not str(compose_project or "").strip():
        payload["reason"] = "missing_compose_project"
        return payload
    all_pass = True
    for ball in balls:
        ball_id = str(ball.get("id", "ball") or "ball")
        pose = ball.get("pose", {}) if isinstance(ball.get("pose"), dict) else {}
        model_name = target_model_name_for_ball(scene_id, ball_id)
        remove_model(compose_project=compose_project, world_name=world_name, model_name=model_name)
        spawn = spawn_model(
            compose_project=compose_project,
            world_name=world_name,
            model_sdf=REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf",
            model_name=model_name,
            x=finite_float(pose.get("x")),
            y=finite_float(pose.get("y")),
            z=finite_float(pose.get("z"), 0.021336),
        )
        all_pass = bool(all_pass and spawn.get("pass", False))
        payload["balls"].append({"ball_id": ball_id, "model_name": model_name, "pose": pose, "spawn": spawn})
    if robot_pose:
        robot_result = set_model_pose(
            compose_project=compose_project,
            world_name=world_name,
            model_name="jetbot",
            x=finite_float(robot_pose.get("x")),
            y=finite_float(robot_pose.get("y")),
            z=0.0,
            yaw=finite_float(robot_pose.get("yaw")),
        )
        all_pass = bool(all_pass and robot_result.get("pass", False))
        payload["robot_pose"] = robot_result
    else:
        all_pass = False
        payload["robot_pose"] = {"pass": False, "reason": "missing_scene_robot_pose"}
    payload["pass"] = bool(all_pass)
    payload["reason"] = "persistent_field_ready" if all_pass else "persistent_field_setup_failed"
    return payload


def materialize_plan_rows(
    root: Path,
    plan: dict[str, Any],
    *,
    args: argparse.Namespace,
    execute_live: bool,
    compose_project: str = "",
    expected_session_id: str = "",
    execution_skipped_reason: str = "",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scene_id = str(plan.get("scene_id", "") or "scene")
    for step in plan.get("sequence", []) if isinstance(plan.get("sequence"), list) else []:
        if not isinstance(step, dict):
            continue
        layout_path = write_layout_for_step(root, scene_id, step)
        command = build_step_command(
            args=args,
            layout_path=layout_path,
            scene_id=scene_id,
            step=step,
            compose_project=compose_project,
            expected_session_id=expected_session_id,
        )
        row = {
            "scene_id": scene_id,
            "step_index": int(step.get("step_index", 0) or 0),
            "ball_id": str(step.get("ball_id", "") or ""),
            "route_label": str(step.get("route_label", "") or ""),
            "route_executor": str(step.get("route_executor", "") or ""),
            "executable_route": bool(step.get("executable_route", False)),
            "layout_path": artifact_display_path(layout_path),
            "command": command,
            "dry_run": not bool(execute_live),
            "execution_skipped_reason": str(execution_skipped_reason or ""),
            "expected_session_id": str(expected_session_id or ""),
            "compose_project": str(compose_project or args.compose_project or ""),
            "returncode": None,
            "failure_reason": "",
            "mission_summary_path": "",
            "mission": {},
            "stdout_tail": "",
            "stderr_tail": "",
        }
        if execute_live:
            completed = run_command(command, timeout_s=float(args.timeout_s))
            output = (completed.stdout or "") + "\n" + (completed.stderr or "")
            mission_summary_raw = extract_marker(output, MISSION_SUMMARY_MARKER)
            row["returncode"] = int(completed.returncode)
            row["stdout_tail"] = "\n".join((completed.stdout or "").splitlines()[-20:])
            row["stderr_tail"] = "\n".join((completed.stderr or "").splitlines()[-20:])
            if mission_summary_raw:
                mission_summary_path = resolve_path(mission_summary_raw)
                row["mission_summary_path"] = artifact_display_path(mission_summary_path)
                row["mission"] = replay_batch.summarize_mission(mission_summary_path)
            if int(completed.returncode) != 0 and not row["failure_reason"]:
                row["failure_reason"] = "runner_returned_nonzero"
        rows.append(row)
        if execute_live and bool(args.stop_on_fail) and not bool((row.get("mission") or {}).get("fetch_to_pose_pass", False)):
            break
    return rows


def pose_from_contact_pose(raw_pose: Any) -> dict[str, float] | None:
    if not isinstance(raw_pose, dict):
        return None
    position = raw_pose.get("position") if isinstance(raw_pose.get("position"), dict) else raw_pose
    if not isinstance(position, dict):
        return None
    return round_pose(
        finite_float(position.get("x")),
        finite_float(position.get("y")),
        z=finite_float(position.get("z")),
        yaw=finite_float(raw_pose.get("yaw")),
    )


def latest_measured_state_from_mission(mission_summary_path: Path) -> dict[str, Any]:
    payload = read_json(mission_summary_path)
    artifact_dir = resolve_path(str(payload.get("artifact_dir", "") or mission_summary_path.parent))
    contact_trace_path = artifact_dir / "contact_trace.jsonl"
    robot_pose = None
    ball_pose = None
    sample_count = 0
    if contact_trace_path.is_file():
        for line in contact_trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            sample_count += 1
            row_robot = pose_from_contact_pose(row.get("robot_pose"))
            row_ball = pose_from_contact_pose(row.get("ball_pose"))
            if row_robot is not None:
                robot_pose = row_robot
            if row_ball is not None:
                ball_pose = row_ball
    shot_outcome = payload.get("shot_outcome") if isinstance(payload.get("shot_outcome"), dict) else {}
    if ball_pose is None and isinstance(shot_outcome.get("ball_end_pose"), dict):
        ball_pose = pose_from_contact_pose(shot_outcome.get("ball_end_pose"))
    pre_fetch_reposition = (
        payload.get("pre_fetch_reposition") if isinstance(payload.get("pre_fetch_reposition"), dict) else {}
    )
    if robot_pose is None and isinstance(pre_fetch_reposition.get("post_reposition_robot_pose"), dict):
        robot_pose = pose_from_contact_pose(pre_fetch_reposition.get("post_reposition_robot_pose"))
    if ball_pose is None and isinstance(pre_fetch_reposition.get("post_reposition_ball_pose"), dict):
        ball_pose = pose_from_contact_pose(pre_fetch_reposition.get("post_reposition_ball_pose"))
    return {
        "available": bool(robot_pose is not None or ball_pose is not None),
        "mission_summary_path": artifact_display_path(mission_summary_path),
        "contact_trace_path": artifact_display_path(contact_trace_path),
        "contact_sample_count": sample_count,
        "robot_pose": robot_pose,
        "ball_pose": ball_pose,
        "fetch_to_pose_pass": bool(payload.get("fetch_to_pose_pass", payload.get("pass", False))),
        "shot_outcome": shot_outcome,
    }


def update_remaining_after_attempt(
    remaining_balls: list[dict[str, Any]],
    *,
    attempted_ball_id: str,
    measured_state: dict[str, Any],
) -> list[dict[str, Any]]:
    attempt_passed = bool(measured_state.get("fetch_to_pose_pass", False))
    measured_ball_pose = measured_state.get("ball_pose") if isinstance(measured_state.get("ball_pose"), dict) else None
    updated: list[dict[str, Any]] = []
    for ball in remaining_balls:
        ball_id = str(ball.get("id", "") or "")
        if ball_id == str(attempted_ball_id):
            if attempt_passed:
                continue
            if measured_ball_pose is not None:
                updated_ball = dict(ball)
                updated_ball["pose"] = dict(measured_ball_pose)
                updated_ball["last_attempt_failed"] = True
                updated.append(updated_ball)
            else:
                updated.append(ball)
        else:
            updated.append(ball)
    return updated


def materialize_replanning_rows(
    root: Path,
    scene: dict[str, Any],
    *,
    args: argparse.Namespace,
    execute_live: bool,
    compose_project: str = "",
    expected_session_id: str = "",
    execution_skipped_reason: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scene_id = str(scene.get("scene_id", "") or "scene")
    remaining = [dict(ball) for ball in scene.get("balls", []) if isinstance(ball, dict)]
    current_robot_pose = dict(scene.get("robot_pose", {}) if isinstance(scene.get("robot_pose"), dict) else {})
    replans: list[dict[str, Any]] = []
    for iteration in range(len(remaining)):
        active_scene = {
            **scene,
            "scene_id": scene_id,
            "robot_pose": current_robot_pose,
            "balls": remaining,
        }
        plan = plan_multiball_scene(active_scene, args=args)
        replans.append(
            {
                "iteration": iteration + 1,
                "robot_pose": current_robot_pose,
                "remaining_ball_ids": [str(ball.get("id", "") or "") for ball in remaining],
                "retrieval_order": plan.get("retrieval_order", []),
                "planner_ready": bool(plan.get("planner_ready", False)),
            }
        )
        sequence = plan.get("sequence") if isinstance(plan.get("sequence"), list) else []
        if not sequence:
            break
        step = dict(sequence[0])
        step["step_index"] = iteration + 1
        step["replanned_live_step"] = True
        layout_path = write_layout_for_step(root, scene_id, step)
        command = build_step_command(
            args=args,
            layout_path=layout_path,
            scene_id=scene_id,
            step=step,
            compose_project=compose_project,
            expected_session_id=expected_session_id,
        )
        row = {
            "scene_id": scene_id,
            "step_index": int(step.get("step_index", 0) or 0),
            "ball_id": str(step.get("ball_id", "") or ""),
            "route_label": str(step.get("route_label", "") or ""),
            "route_executor": str(step.get("route_executor", "") or ""),
            "executable_route": bool(step.get("executable_route", False)),
            "layout_path": artifact_display_path(layout_path),
            "command": command,
            "dry_run": not bool(execute_live),
            "replanned_live_step": True,
            "execution_skipped_reason": str(execution_skipped_reason or ""),
            "expected_session_id": str(expected_session_id or ""),
            "compose_project": str(compose_project or args.compose_project or ""),
            "returncode": None,
            "failure_reason": "",
            "mission_summary_path": "",
            "mission": {},
            "measured_post_step_state": {},
            "stdout_tail": "",
            "stderr_tail": "",
        }
        if execute_live:
            completed = run_command(command, timeout_s=float(args.timeout_s))
            output = (completed.stdout or "") + "\n" + (completed.stderr or "")
            mission_summary_raw = extract_marker(output, MISSION_SUMMARY_MARKER)
            row["returncode"] = int(completed.returncode)
            row["stdout_tail"] = "\n".join((completed.stdout or "").splitlines()[-20:])
            row["stderr_tail"] = "\n".join((completed.stderr or "").splitlines()[-20:])
            if mission_summary_raw:
                mission_summary_path = resolve_path(mission_summary_raw)
                row["mission_summary_path"] = artifact_display_path(mission_summary_path)
                row["mission"] = replay_batch.summarize_mission(mission_summary_path)
                measured_state = latest_measured_state_from_mission(mission_summary_path)
                row["measured_post_step_state"] = measured_state
                if isinstance(measured_state.get("robot_pose"), dict):
                    current_robot_pose = dict(measured_state["robot_pose"])
                else:
                    current_robot_pose = step.get("estimated_post_fetch_robot_pose", current_robot_pose)
                remaining = update_remaining_after_attempt(
                    remaining,
                    attempted_ball_id=str(step.get("ball_id", "") or ""),
                    measured_state=measured_state,
                )
            else:
                current_robot_pose = step.get("estimated_post_fetch_robot_pose", current_robot_pose)
                remaining = [
                    ball for ball in remaining if str(ball.get("id", "") or "") != str(step.get("ball_id", "") or "")
                ]
            if int(completed.returncode) != 0 and not row["failure_reason"]:
                row["failure_reason"] = "runner_returned_nonzero"
        rows.append(row)
        if execute_live and bool(args.stop_on_fail) and not bool((row.get("mission") or {}).get("fetch_to_pose_pass", False)):
            break
    return rows, {"enabled": True, "iterations": replans}


def load_scene_descriptors(paths: list[str]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for raw_path in paths:
        path = resolve_path(raw_path)
        payload = read_json(path)
        if isinstance(payload.get("scenes"), list):
            scenes.extend([scene for scene in payload["scenes"] if isinstance(scene, dict)])
        elif payload:
            scenes.append(payload)
    return scenes


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = str(args.campaign_id or "").strip() or f"live_fetch_multiball_retrieval_gate_{current_utc_stamp()}"
    root = ensure_dir(SESSION_ROOT / campaign_id / GATE_KIND)
    dry_run = bool(args.dry_run)
    fresh_session_per_scene = bool(getattr(args, "fresh_session_per_scene", False))
    run_compose_project = str(args.compose_project or "").strip()
    expected_session_id = str(getattr(args, "expected_session_id", "") or "").strip()
    dashboard_stop_before_start: dict[str, Any] = {}
    dashboard_start: dict[str, Any] = {}
    dashboard_stop_before_package: dict[str, Any] = {}
    live_execution_ready = not dry_run
    live_execution_blocker = ""
    if not dry_run and bool(getattr(args, "fresh_dashboard_session", False)) and not fresh_session_per_scene:
        dashboard_stop_before_start = replay_batch.stop_dashboard_environment(
            str(args.dashboard_url or ""),
            timeout_s=float(args.env_stop_timeout_s),
        )
        dashboard_start = replay_batch.start_dashboard_environment(args)
        start_state = dashboard_start.get("state") if isinstance(dashboard_start.get("state"), dict) else {}
        run_compose_project = str(start_state.get("compose_project", "") or start_state.get("launcher_project", "") or "")
        expected_session_id = str(start_state.get("session_id", "") or "")
        live_execution_ready = replay_batch.dashboard_environment_ready(
            start_state,
            allow_operator_view_degraded=bool(getattr(args, "allow_operator_view_degraded", False)),
        )
        if not live_execution_ready:
            live_execution_blocker = replay_batch.dashboard_start_failure_reason(dashboard_start)
    scenes = load_scene_descriptors(list(args.scene_descriptor_json or []))
    if not scenes:
        scenes = generate_multiball_scenes(
            seed=int(args.seed),
            random_cases=int(args.random_cases),
            balls_per_scene=int(args.balls_per_scene),
            profile=str(args.profile or DEFAULT_PROFILE),
        )
    scene_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    for scene in scenes:
        scene_dashboard_stop_before_start: dict[str, Any] = {}
        scene_dashboard_start: dict[str, Any] = {}
        scene_dashboard_stop_after_scene: dict[str, Any] = {}
        scene_compose_project = run_compose_project
        scene_expected_session_id = expected_session_id
        scene_live_execution_ready = bool(live_execution_ready)
        scene_live_execution_blocker = str(live_execution_blocker or "")
        if not dry_run and fresh_session_per_scene:
            scene_dashboard_stop_before_start = replay_batch.stop_dashboard_environment(
                str(args.dashboard_url or ""),
                timeout_s=float(args.env_stop_timeout_s),
            )
            scene_dashboard_start = replay_batch.start_dashboard_environment(args)
            scene_start_state = (
                scene_dashboard_start.get("state") if isinstance(scene_dashboard_start.get("state"), dict) else {}
            )
            scene_compose_project = str(
                scene_start_state.get("compose_project", "") or scene_start_state.get("launcher_project", "") or ""
            )
            scene_expected_session_id = str(scene_start_state.get("session_id", "") or "")
            scene_live_execution_ready = replay_batch.dashboard_environment_ready(
                scene_start_state,
                allow_operator_view_degraded=bool(getattr(args, "allow_operator_view_degraded", False)),
            )
            if not scene_live_execution_ready:
                scene_live_execution_blocker = replay_batch.dashboard_start_failure_reason(scene_dashboard_start)
        plan = plan_multiball_scene(scene, args=args)
        artifact_paths = write_scene_artifacts(root, scene, plan)
        persistent_field_setup: dict[str, Any] = {"enabled": False}
        scene_execution_ready = bool(scene_live_execution_ready)
        scene_execution_blocker = str(scene_live_execution_blocker or "")
        if scene_execution_ready and bool(getattr(args, "persistent_field", False)):
            persistent_field_setup = prepare_persistent_field_scene(
                scene=scene,
                compose_project=scene_compose_project,
                world_name=DEFAULT_WORLD_NAME,
            )
            setup_path = ensure_dir(root / "persistent_field_setup") / f"{safe_id(str(scene.get('scene_id', 'scene')))}.json"
            write_json(setup_path, persistent_field_setup)
            persistent_field_setup["path"] = artifact_display_path(setup_path)
            if not bool(persistent_field_setup.get("pass", False)):
                scene_execution_ready = False
                scene_execution_blocker = str(persistent_field_setup.get("reason", "persistent_field_setup_failed"))
        live_replan_summary: dict[str, Any] = {"enabled": False}
        if scene_execution_ready and bool(getattr(args, "persistent_field", False)):
            rows, live_replan_summary = materialize_replanning_rows(
                root,
                scene,
                args=args,
                execute_live=scene_execution_ready,
                compose_project=scene_compose_project,
                expected_session_id=scene_expected_session_id,
                execution_skipped_reason=scene_execution_blocker,
            )
        else:
            rows = materialize_plan_rows(
                root,
                plan,
                args=args,
                execute_live=scene_execution_ready,
                compose_project=scene_compose_project,
                expected_session_id=scene_expected_session_id,
                execution_skipped_reason=scene_execution_blocker,
            )
        step_rows.extend(rows)
        scene_pass = bool(plan.get("planner_ready", False))
        if not dry_run:
            scene_rows_for_scene = [row for row in rows if row.get("scene_id") == plan.get("scene_id")]
            scene_pass = bool(
                scene_rows_for_scene
                and len(scene_rows_for_scene) == int(plan.get("ball_count", 0) or 0)
                and all(bool((row.get("mission") or {}).get("fetch_to_pose_pass", False)) for row in scene_rows_for_scene)
            )
        if not dry_run and fresh_session_per_scene and scene_live_execution_ready:
            scene_dashboard_stop_after_scene = replay_batch.stop_dashboard_environment(
                str(args.dashboard_url or ""),
                timeout_s=float(args.env_stop_timeout_s),
            )
        scene_rows.append(
            {
                "scene_id": str(scene.get("scene_id", "") or ""),
                "pass": scene_pass,
                "ball_count": int(plan.get("ball_count", 0) or 0),
                "retrieval_order": plan.get("retrieval_order", []),
                "planner_ready": bool(plan.get("planner_ready", False)),
                "executable_step_count": int(plan.get("executable_step_count", 0) or 0),
                "compose_project": scene_compose_project,
                "expected_session_id": scene_expected_session_id,
                "live_execution_ready": bool(scene_live_execution_ready),
                "live_execution_blocker": scene_live_execution_blocker,
                "dashboard_stop_before_start": scene_dashboard_stop_before_start,
                "dashboard_start": scene_dashboard_start,
                "dashboard_stop_after_scene": scene_dashboard_stop_after_scene,
                "persistent_field_setup": persistent_field_setup,
                "live_replanning": live_replan_summary,
                **artifact_paths,
            }
        )
        if not dry_run and bool(args.stop_on_fail) and not scene_pass:
            break

    planned_step_count = len(step_rows)
    live_pass_count = sum(1 for row in step_rows if bool((row.get("mission") or {}).get("fetch_to_pose_pass", False)))
    planner_ready_scene_count = sum(1 for row in scene_rows if bool(row.get("planner_ready", False)))
    visual_package_command: list[str] = []
    visual_package_summary_path = ""
    visual_package: dict[str, Any] = {}
    visual_package_returncode: int | None = None
    visual_package_stdout_tail = ""
    visual_package_stderr_tail = ""
    if not dry_run and not bool(args.no_visual_package):
        if bool(getattr(args, "fresh_dashboard_session", False)) and live_execution_ready and not fresh_session_per_scene:
            dashboard_stop_before_package = replay_batch.stop_dashboard_environment(
                str(args.dashboard_url or ""),
                timeout_s=float(args.env_stop_timeout_s),
            )
        mission_summary_paths = [
            resolve_path(str(row.get("mission_summary_path", "") or ""))
            for row in step_rows
            if str(row.get("mission_summary_path", "") or "").strip()
        ]
        if mission_summary_paths:
            visual_package_command = build_visual_package_command(
                args=args,
                campaign_id=campaign_id,
                mission_summary_paths=mission_summary_paths,
            )
            completed = run_command(visual_package_command, timeout_s=float(args.package_timeout_s))
            output = (completed.stdout or "") + "\n" + (completed.stderr or "")
            visual_package_returncode = int(completed.returncode)
            visual_package_stdout_tail = "\n".join((completed.stdout or "").splitlines()[-20:])
            visual_package_stderr_tail = "\n".join((completed.stderr or "").splitlines()[-20:])
            package_summary_raw = extract_marker(output, VISUAL_PACKAGE_MARKER)
            if package_summary_raw:
                package_summary_path = resolve_path(package_summary_raw)
                visual_package_summary_path = artifact_display_path(package_summary_path)
                visual_package = read_json(package_summary_path)
    visual_package_required = bool(not dry_run and not bool(args.no_visual_package))
    visual_package_pass = bool(visual_package.get("pass", False))
    summary = {
        "generated_utc": utc_now(),
        "type": GATE_KIND,
        "campaign_id": campaign_id,
        "profile": str(args.profile or DEFAULT_PROFILE),
        "dry_run": dry_run,
        "planner_mode": str(args.planner_mode),
        "persistent_field": bool(getattr(args, "persistent_field", False)),
        "fresh_dashboard_session": bool(getattr(args, "fresh_dashboard_session", False)),
        "fresh_session_per_scene": fresh_session_per_scene,
        "dashboard_url": str(args.dashboard_url or ""),
        "compose_project": run_compose_project,
        "expected_session_id": expected_session_id,
        "live_execution_ready": bool(live_execution_ready),
        "live_execution_blocker": live_execution_blocker,
        "dashboard_stop_before_start": dashboard_stop_before_start,
        "dashboard_start": dashboard_start,
        "dashboard_stop_before_package": dashboard_stop_before_package,
        "seed": int(args.seed),
        "random_cases": int(args.random_cases),
        "balls_per_scene": int(args.balls_per_scene),
        "scene_count": len(scene_rows),
        "planner_ready_scene_count": planner_ready_scene_count,
        "planned_step_count": planned_step_count,
        "live_fetch_to_pose_pass_count": live_pass_count,
        "live_fetch_to_pose_fail_count": 0 if dry_run else planned_step_count - live_pass_count,
        "visual_package_required": visual_package_required,
        "visual_package_pass": visual_package_pass,
        "visual_package_summary_path": visual_package_summary_path,
        "visual_package_command": visual_package_command,
        "visual_package_returncode": visual_package_returncode,
        "visual_package_stdout_tail": visual_package_stdout_tail,
        "visual_package_stderr_tail": visual_package_stderr_tail,
        "visual_package": visual_package,
        "pass": bool(
            scene_rows
            and (planner_ready_scene_count == len(scene_rows))
            and (dry_run or live_pass_count == planned_step_count)
            and (not visual_package_required or visual_package_pass)
        ),
        "promotion_evidence": False,
        "milestone_interpretation": (
            "multiball_retrieval_plan_materialized"
            if dry_run
            else "multiball_sequential_setup_replay_visual_evidence"
        ),
        "field_bounds": dict(DEFAULT_FIELD_BOUNDS),
        "randomization": {
            "ball_target_distance_range_m": list(BALL_TARGET_DISTANCE_RANGE_M),
            "robot_target_distance_range_m": list(ROBOT_TARGET_DISTANCE_RANGE_M),
            "min_ball_separation_m": MIN_BALL_SEPARATION_M,
            "min_robot_ball_separation_m": MIN_ROBOT_BALL_SEPARATION_M,
        },
        "constraints": {
            "robot_owned_contact": True,
            "no_direct_ball_impulse": True,
            "one_ball_fetch_primitive": "planner_routed_fetch_to_pose",
            "same_environment_live_mission_required_for_promotion": True,
        },
        "scene_rows": scene_rows,
        "step_rows": step_rows,
        "summary_path": artifact_display_path(root / "gate_summary.json"),
        "scorecard_path": artifact_display_path(root / "scorecard.md"),
    }
    write_json(root / "gate_summary.json", summary)
    write_scorecard(root / "scorecard.md", summary)
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Multi-Ball Retrieval Gate",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- profile: `{summary.get('profile', '')}`",
        f"- dry_run: `{summary.get('dry_run', False)}`",
        f"- planner_mode: `{summary.get('planner_mode', '')}`",
        f"- fresh_dashboard_session: `{summary.get('fresh_dashboard_session', False)}`",
        f"- fresh_session_per_scene: `{summary.get('fresh_session_per_scene', False)}`",
        f"- live_execution_ready: `{summary.get('live_execution_ready', False)}`",
        f"- expected_session_id: `{summary.get('expected_session_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- scene_count: `{summary.get('scene_count', 0)}`",
        f"- balls_per_scene: `{summary.get('balls_per_scene', 0)}`",
        f"- planned_step_count: `{summary.get('planned_step_count', 0)}`",
        f"- planner_ready_scene_count: `{summary.get('planner_ready_scene_count', 0)}`",
        f"- live_fetch_to_pose_pass_count: `{summary.get('live_fetch_to_pose_pass_count', 0)}`",
        f"- live_fetch_to_pose_fail_count: `{summary.get('live_fetch_to_pose_fail_count', 0)}`",
        f"- visual_package_required: `{summary.get('visual_package_required', False)}`",
        f"- visual_package_pass: `{summary.get('visual_package_pass', False)}`",
        f"- visual_package_summary_path: `{summary.get('visual_package_summary_path', '')}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        "",
        "## Scenes",
        "",
        "| Scene | Pass | Balls | Planner ready | Order |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in summary.get("scene_rows", []) if isinstance(summary.get("scene_rows"), list) else []:
        order = ", ".join(str(item) for item in row.get("retrieval_order", []))
        lines.append(
            f"| `{row.get('scene_id', '')}` | `{row.get('pass', False)}` | "
            f"`{row.get('ball_count', 0)}` | `{row.get('planner_ready', False)}` | `{order}` |"
        )
    lines.extend(
        [
            "",
            "## Retrieval Steps",
            "",
            "| Scene | Step | Ball | Route | Executor | Layout | Mission pass |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("step_rows", []) if isinstance(summary.get("step_rows"), list) else []:
        mission = row.get("mission") if isinstance(row.get("mission"), dict) else {}
        mission_pass = "n/a" if bool(row.get("dry_run", False)) else str(bool(mission.get("fetch_to_pose_pass", False)))
        lines.append(
            f"| `{row.get('scene_id', '')}` | `{row.get('step_index', 0)}` | `{row.get('ball_id', '')}` | "
            f"`{row.get('route_label', '')}` | `{row.get('route_executor', '')}` | "
            f"`{row.get('layout_path', '')}` | `{mission_pass}` |"
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan and optionally replay seeded multi-ball retrieval scenes.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASES)
    parser.add_argument("--balls-per-scene", type=int, default=DEFAULT_BALLS_PER_SCENE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--scene-descriptor-json", action="append", default=[])
    parser.add_argument("--planner-mode", choices=planner_gate.PLANNER_MODES, default=planner_gate.PLANNER_MODE_DETERMINISTIC)
    parser.add_argument("--openai-model", default=planner_gate.DEFAULT_OPENAI_MODEL)
    parser.add_argument("--openai-api-key", default="")
    parser.add_argument("--openai-base-url", default=planner_gate.DEFAULT_OPENAI_BASE_URL)
    parser.add_argument("--openai-org-id", default="")
    parser.add_argument("--openai-project-id", default="")
    parser.add_argument("--reasoning-effort", default=planner_gate.DEFAULT_REASONING_EFFORT)
    parser.add_argument("--planner-timeout-s", type=float, default=45.0)
    parser.add_argument("--dashboard-url", default="")
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--expected-session-id", default="")
    parser.add_argument("--fresh-dashboard-session", action="store_true")
    parser.add_argument("--fresh-session-per-scene", action="store_true")
    parser.add_argument("--allow-operator-view-degraded", action="store_true")
    parser.add_argument("--world-file", default="yolo_test_world_v6_calibrated_golf_turf.world")
    parser.add_argument("--surface-profile", default="calibrated_golf_turf")
    parser.add_argument("--robot-sdf-name", default="jetbot_core_ignition_v1.7.0.sdf")
    parser.add_argument("--nav2-goal-frame-mode", choices=["world_direct", "nav2_relative"], default="world_direct")
    parser.add_argument("--env-ready-timeout-s", type=float, default=replay_batch.DEFAULT_ENV_READY_TIMEOUT_S)
    parser.add_argument("--env-start-attempts", type=int, default=2)
    parser.add_argument("--env-stop-timeout-s", type=float, default=90.0)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=0.300)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--package-timeout-s", type=float, default=180.0)
    parser.add_argument("--no-visual-package", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--persistent-field", action="store_true")
    return parser.parse_args()


def main() -> int:
    summary = run_gate(parse_args())
    print(f"FETCH_MULTIBALL_RETRIEVAL_GATE_SUMMARY={REPO_ROOT / summary['summary_path']}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    sys.exit(main())
