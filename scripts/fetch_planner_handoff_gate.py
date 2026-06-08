#!/usr/bin/env python3
"""Planner-gated fetch handoff evidence.

This gate scores whether a high-level planner should dispatch local
``fetch_to_pose`` or choose another bounded route before local fetch is judged.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chasecar_env import load_repo_dotenv
from llm_provider_openai import call_openai_responses
from llm_supervisor_core import DEFAULT_OPENAI_BASE_URL
from llm_supervisor_core import DEFAULT_OPENAI_MODEL
from llm_supervisor_core import DEFAULT_REASONING_EFFORT
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import normalize_openai_base_url
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


load_repo_dotenv(REPO_ROOT)
DEFAULT_SCENE_SET = "mixed_fetch_planner_v1"
DEFAULT_RANDOM_CASES = 20
DEFAULT_SEED = 20260530
PLANNER_MODE_DETERMINISTIC = "deterministic"
PLANNER_MODE_LLM_SHADOW = "llm_shadow"
PLANNER_MODE_LLM_SUPERVISED_GUARDED = "llm_supervised_guarded"
PLANNER_MODES = (
    PLANNER_MODE_DETERMINISTIC,
    PLANNER_MODE_LLM_SHADOW,
    PLANNER_MODE_LLM_SUPERVISED_GUARDED,
)
ROUTE_FETCH_READY = "fetch_ready_local"
ROUTE_NAV2_REPOSITION = "nav2_reposition_first"
ROUTE_SCAN_OR_PERCEIVE = "scan_or_perceive_first"
ROUTE_RECOVERY_OR_REAIM = "recovery_or_reaim"
ROUTE_LOCAL_SETUP_CAPTURE = "local_setup_capture"
ROUTE_NO_GO = "ambiguous_or_unsafe_no_go"
ROUTE_LABELS = (
    ROUTE_FETCH_READY,
    ROUTE_NAV2_REPOSITION,
    ROUTE_SCAN_OR_PERCEIVE,
    ROUTE_RECOVERY_OR_REAIM,
    ROUTE_LOCAL_SETUP_CAPTURE,
    ROUTE_NO_GO,
)
ROUTE_EXECUTOR_LOCAL_FETCH = "local_fetch_to_pose"
ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH = "nav2_forward_reposition_then_fetch"
ROUTE_EXECUTOR_SCAN = "scan_or_perception_refresh"
ROUTE_EXECUTOR_RECOVERY = "bounded_recovery_reaim"
ROUTE_EXECUTOR_LOCAL_SETUP_CAPTURE = "measured_local_setup_capture"
ROUTE_EXECUTOR_NO_GO = "safe_no_go"
ROUTE_EXECUTORS = {
    ROUTE_FETCH_READY: ROUTE_EXECUTOR_LOCAL_FETCH,
    ROUTE_NAV2_REPOSITION: ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH,
    ROUTE_SCAN_OR_PERCEIVE: ROUTE_EXECUTOR_SCAN,
    ROUTE_RECOVERY_OR_REAIM: ROUTE_EXECUTOR_RECOVERY,
    ROUTE_LOCAL_SETUP_CAPTURE: ROUTE_EXECUTOR_LOCAL_SETUP_CAPTURE,
    ROUTE_NO_GO: ROUTE_EXECUTOR_NO_GO,
}
MANEUVER_SCAN = "scan_perceive"
MANEUVER_NO_GO = "safe_no_go"
MANEUVER_NAV2_REPOSITION = "nav2_reposition"
MANEUVER_WRAPAROUND_SETUP = "wraparound_setup"
MANEUVER_RECOVERY_REAIM = "recovery_reaim"
MANEUVER_LOCAL_SETUP_CAPTURE = "local_setup_capture"
MANEUVER_VALIDATE_PUSH_READY = "validate_push_ready"
MANEUVER_LOCAL_FETCH = "local_fetch_to_pose"
MANEUVER_MONITOR_DELIVERY = "monitor_delivery"
MANEUVER_LABELS = (
    MANEUVER_SCAN,
    MANEUVER_NO_GO,
    MANEUVER_NAV2_REPOSITION,
    MANEUVER_WRAPAROUND_SETUP,
    MANEUVER_RECOVERY_REAIM,
    MANEUVER_LOCAL_SETUP_CAPTURE,
    MANEUVER_VALIDATE_PUSH_READY,
    MANEUVER_LOCAL_FETCH,
    MANEUVER_MONITOR_DELIVERY,
)
FETCH_TARGET_POSE = {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.30}
PLANNER_GATE_KIND = "fetch_planner_handoff_gate"
PLANNER_MIXED_PROFILE = "planner_mixed_v1"
HARD_SCENE_SET = "hard_mixed_fetch_planner_v1"
OPPOSITE_BEHIND_SCENE_SET = "opposite_side_and_behind_robot_v1"
OPPOSITE_BEHIND_PROFILE = "opposite_side_and_behind_robot_v1"
BROAD_SPATIAL_SCENE_SET = "broad_spatial_fetch_generalization_v1"
BROAD_SPATIAL_PROFILE = "broad_spatial_fetch_generalization_v1"
OPENAI_TOOL_NAME = "emit_fetch_planner_route"
LLM_SUPERVISED_MIN_CONFIDENCE = 0.90
LLM_PROVIDER_MAX_ATTEMPTS = 2
CONTACT_QUALITY_CLEAN_LATERAL_M = 0.030
CONTACT_QUALITY_CLEAN_YAW_DEG = 3.0
FETCH_READY_LATERAL_LIMIT_M = 0.050
FETCH_READY_YAW_LIMIT_DEG = 6.0
RECOVERY_LATERAL_LIMIT_M = 0.240
RECOVERY_YAW_LIMIT_DEG = 35.0
RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M = 0.900
EXTENDED_RECOVERY_LATERAL_LIMIT_M = 0.360
EXTENDED_RECOVERY_YAW_LIMIT_DEG = 85.0
EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M = 0.950
LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M = 2.600
LOCAL_SETUP_CAPTURE_LATERAL_LIMIT_M = 2.200
LOCAL_SETUP_CAPTURE_YAW_LIMIT_DEG = 180.0
NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M = RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
NAV2_REPOSITION_STANDOFF_LIMIT_M = 1.350


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run planner-gated fetch handoff scoring.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scene-set", default=DEFAULT_SCENE_SET)
    parser.add_argument(
        "--scene-descriptor-json",
        action="append",
        default=[],
        help="Frozen scene descriptor JSON file. Accepts one scene or {'scenes': [...]}. May be repeated.",
    )
    parser.add_argument(
        "--scene-dir",
        default="",
        help="Directory containing frozen scene descriptor JSON files.",
    )
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--planner-mode",
        choices=PLANNER_MODES,
        default=PLANNER_MODE_DETERMINISTIC,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    parser.add_argument("--openai-api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL))
    parser.add_argument("--openai-org-id", default=os.environ.get("OPENAI_ORG_ID", ""))
    parser.add_argument("--openai-project-id", default=os.environ.get("OPENAI_PROJECT_ID", ""))
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--timeout-s", type=float, default=45.0)
    return parser.parse_args()


def _campaign_root(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / PLANNER_GATE_KIND


def _resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _round_pose(x: float, y: float, yaw: float = 0.0, z: float = 0.0) -> dict[str, float]:
    return {
        "x": round(float(x), 6),
        "y": round(float(y), 6),
        "z": round(float(z), 6),
        "yaw": round(float(yaw), 6),
    }


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(number):
        return float(default)
    return number


def _normalize_angle_deg(angle_deg: float) -> float:
    return ((float(angle_deg) + 180.0) % 360.0) - 180.0


def _pose_yaw_deg(pose: dict[str, Any]) -> float:
    return math.degrees(_finite_float(pose.get("yaw"), 0.0))


def _bearing_deg(origin: dict[str, Any], target: dict[str, Any]) -> float:
    dx = _finite_float(target.get("x"), 0.0) - _finite_float(origin.get("x"), 0.0)
    dy = _finite_float(target.get("y"), 0.0) - _finite_float(origin.get("y"), 0.0)
    return math.degrees(math.atan2(dy, dx))


def _augment_spatial_generalization_geometry(scene: dict[str, Any]) -> None:
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    robot_pose = scene.get("robot_pose") if isinstance(scene.get("robot_pose"), dict) else {}
    ball_pose = scene.get("ball_pose") if isinstance(scene.get("ball_pose"), dict) else {}
    target_pose = scene.get("target_pose") if isinstance(scene.get("target_pose"), dict) else dict(FETCH_TARGET_POSE)
    if not robot_pose or not ball_pose:
        return

    robot_to_ball_bearing_deg = _bearing_deg(robot_pose, ball_pose)
    robot_ball_relative_bearing_deg = _normalize_angle_deg(robot_to_ball_bearing_deg - _pose_yaw_deg(robot_pose))
    target_to_ball = (
        _finite_float(ball_pose.get("x"), 0.0) - _finite_float(target_pose.get("x"), 0.0),
        _finite_float(ball_pose.get("y"), 0.0) - _finite_float(target_pose.get("y"), 0.0),
    )
    target_to_robot = (
        _finite_float(robot_pose.get("x"), 0.0) - _finite_float(target_pose.get("x"), 0.0),
        _finite_float(robot_pose.get("y"), 0.0) - _finite_float(target_pose.get("y"), 0.0),
    )
    dot = target_to_ball[0] * target_to_robot[0] + target_to_ball[1] * target_to_robot[1]
    ball_norm = math.hypot(*target_to_ball)
    robot_norm = math.hypot(*target_to_robot)
    target_robot_ball_angle_deg = 0.0
    opposite_side = False
    if ball_norm > 1.0e-9 and robot_norm > 1.0e-9:
        cosine = max(-1.0, min(1.0, dot / (ball_norm * robot_norm)))
        target_robot_ball_angle_deg = math.degrees(math.acos(cosine))
        opposite_side = target_robot_ball_angle_deg >= 90.0

    scene["geometry"] = {
        **geometry,
        "robot_to_ball_bearing_deg": round(float(robot_to_ball_bearing_deg), 6),
        "robot_ball_relative_bearing_deg": round(float(robot_ball_relative_bearing_deg), 6),
        "robot_ball_relative_bearing_abs_deg": round(abs(float(robot_ball_relative_bearing_deg)), 6),
        "target_robot_ball_angle_deg": round(float(target_robot_ball_angle_deg), 6),
        "opposite_side_of_circle": bool(opposite_side),
    }


def _quality_ratio(value: float, clean: float, limit: float) -> float:
    clean = max(float(clean), 0.0)
    limit = max(float(limit), clean + 1.0e-9)
    excess = max(abs(float(value)) - clean, 0.0)
    return max(0.0, min(1.0, excess / (limit - clean)))


def _recovery_admissible_from_geometry(geometry: dict[str, Any]) -> bool:
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    return bool(
        0.34 <= ball_target_distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= RECOVERY_LATERAL_LIMIT_M
        and yaw_error_deg <= RECOVERY_YAW_LIMIT_DEG
    )


def _extended_recovery_admissible_from_geometry(geometry: dict[str, Any]) -> bool:
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    return bool(
        0.34 <= ball_target_distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= EXTENDED_RECOVERY_LATERAL_LIMIT_M
        and yaw_error_deg <= EXTENDED_RECOVERY_YAW_LIMIT_DEG
    )


def _local_setup_capture_admissible_from_geometry(geometry: dict[str, Any]) -> bool:
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    return bool(
        0.34 <= ball_target_distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= LOCAL_SETUP_CAPTURE_LATERAL_LIMIT_M
        and yaw_error_deg <= LOCAL_SETUP_CAPTURE_YAW_LIMIT_DEG
    )


def _geometry_needs_ball_relative_setup_owner(geometry: dict[str, Any]) -> bool:
    robot_ball_relative_bearing_abs_deg = _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0)
    opposite_side = bool(geometry.get("opposite_side_of_circle", False))
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    return bool(
        opposite_side
        or robot_ball_relative_bearing_abs_deg >= 90.0
        or lateral_error_m > RECOVERY_LATERAL_LIMIT_M
        or yaw_error_deg > RECOVERY_YAW_LIMIT_DEG
        or robot_ball_distance_m > NAV2_REPOSITION_STANDOFF_LIMIT_M
    )


def route_admissibility_for_scene(scene: dict[str, Any], route_label: str) -> dict[str, Any]:
    route = str(route_label or "").strip()
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    effective_route = route
    reason = "route_admissible"
    changed = False

    if route == ROUTE_NAV2_REPOSITION and _recovery_admissible_from_geometry(geometry):
        effective_route = ROUTE_RECOVERY_OR_REAIM
        reason = "near_field_setup_prefers_bounded_recovery_reaim"
        changed = True
    elif route in {ROUTE_NAV2_REPOSITION, ROUTE_LOCAL_SETUP_CAPTURE} and _extended_recovery_admissible_from_geometry(
        geometry
    ):
        effective_route = ROUTE_RECOVERY_OR_REAIM
        reason = "close_wide_setup_debt_prefers_bounded_recovery_reaim"
        changed = True
    elif (
        route == ROUTE_NAV2_REPOSITION
        and _geometry_needs_ball_relative_setup_owner(geometry)
        and _local_setup_capture_admissible_from_geometry(geometry)
    ):
        effective_route = ROUTE_LOCAL_SETUP_CAPTURE
        reason = "measured_geometry_requires_local_setup_capture_owner"
        changed = True

    return {
        "requested_route_label": route,
        "route_label": effective_route,
        "route_executor": executor_for_route(effective_route),
        "changed": bool(changed),
        "reason": reason,
        "robot_ball_distance_m": round(float(robot_ball_distance_m), 6),
        "thresholds": {
            "recovery_robot_ball_distance_limit_m": RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M,
            "nav2_reposition_min_robot_ball_distance_m": NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M,
            "local_setup_capture_robot_ball_distance_limit_m": LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M,
        },
    }


def _target_relative_scene(
    *,
    rng: random.Random,
    route_label: str,
    scene_id: str,
    distance_range: tuple[float, float],
    angle_range_deg: tuple[float, float],
    standoff_range: tuple[float, float],
    lateral_range: tuple[float, float],
    yaw_error_range_deg: tuple[float, float],
    ball_confidence: float = 0.98,
    target_confidence: float = 0.99,
    state_age_s: float = 0.15,
    corridor_blocked: bool = False,
    corridor_clearance_m: float = 0.35,
    unsafe_drift_m: float = 0.0,
) -> dict[str, Any]:
    target_x = float(FETCH_TARGET_POSE["x"])
    target_y = float(FETCH_TARGET_POSE["y"])
    distance_m = rng.uniform(*distance_range)
    angle_deg = rng.uniform(*angle_range_deg)
    angle_rad = math.radians(angle_deg)
    push_ux = math.cos(angle_rad)
    push_uy = math.sin(angle_rad)
    ball_x = target_x - (distance_m * push_ux)
    ball_y = target_y - (distance_m * push_uy)
    standoff_m = rng.uniform(*standoff_range)
    lateral_m = rng.uniform(*lateral_range)
    yaw_error_deg = rng.uniform(*yaw_error_range_deg)
    normal_x = -push_uy
    normal_y = push_ux
    robot_x = ball_x - (standoff_m * push_ux) + (lateral_m * normal_x)
    robot_y = ball_y - (standoff_m * push_uy) + (lateral_m * normal_y)
    robot_yaw = angle_rad + math.radians(yaw_error_deg)
    robot_ball_distance_m = math.hypot(robot_x - ball_x, robot_y - ball_y)
    local_envelope = (
        0.34 <= distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= 0.52
        and abs(lateral_m) <= FETCH_READY_LATERAL_LIMIT_M
        and abs(yaw_error_deg) <= FETCH_READY_YAW_LIMIT_DEG
        and not corridor_blocked
        and corridor_clearance_m >= 0.12
        and ball_confidence >= 0.65
        and target_confidence >= 0.65
        and state_age_s <= 2.0
    )
    scene = {
        "generated_utc": utc_now(),
        "type": "fetch_planner_scene_descriptor",
        "scene_set": DEFAULT_SCENE_SET,
        "scene_id": scene_id,
        "expected_route_label": route_label,
        "target_pose": dict(FETCH_TARGET_POSE),
        "ball_pose": _round_pose(ball_x, ball_y, z=0.021336),
        "robot_pose": _round_pose(robot_x, robot_y, yaw=robot_yaw),
        "perception": {
            "ball_confidence": round(float(ball_confidence), 6),
            "target_confidence": round(float(target_confidence), 6),
            "state_age_s": round(float(state_age_s), 6),
        },
        "corridor": {
            "blocked": bool(corridor_blocked),
            "clearance_m": round(float(corridor_clearance_m), 6),
            "unsafe_drift_m": round(float(unsafe_drift_m), 6),
        },
        "geometry": {
            "ball_target_distance_m": round(float(distance_m), 6),
            "ball_target_angle_deg": round(float(angle_deg), 6),
            "robot_ball_distance_m": round(float(robot_ball_distance_m), 6),
            "robot_lateral_error_m": round(abs(float(lateral_m)), 6),
            "robot_lateral_signed_m": round(float(lateral_m), 6),
            "robot_yaw_error_deg": round(float(yaw_error_deg), 6),
        },
        "local_fetch_envelope": {
            "eligible": bool(local_envelope),
            "delivery_radius_m": round(float(FETCH_TARGET_POSE["radius_m"]), 6),
            "requires_robot_owned_contact": True,
            "no_direct_ball_impulse": True,
        },
    }
    _augment_spatial_generalization_geometry(scene)
    return scene


def _refresh_local_fetch_envelope(scene: dict[str, Any]) -> None:
    perception = scene.get("perception") if isinstance(scene.get("perception"), dict) else {}
    corridor = scene.get("corridor") if isinstance(scene.get("corridor"), dict) else {}
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    eligible = (
        0.34 <= _finite_float(geometry.get("ball_target_distance_m"), 999.0) <= 0.85
        and 0.24 <= _finite_float(geometry.get("robot_ball_distance_m"), 999.0) <= 0.52
        and _finite_float(geometry.get("robot_lateral_error_m"), 999.0) <= FETCH_READY_LATERAL_LIMIT_M
        and abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0)) <= FETCH_READY_YAW_LIMIT_DEG
        and not bool(corridor.get("blocked", False))
        and _finite_float(corridor.get("clearance_m"), 0.0) >= 0.12
        and _finite_float(perception.get("ball_confidence"), 0.0) >= 0.65
        and _finite_float(perception.get("target_confidence"), 0.0) >= 0.65
        and _finite_float(perception.get("state_age_s"), 999.0) <= 2.0
    )
    envelope = scene.get("local_fetch_envelope") if isinstance(scene.get("local_fetch_envelope"), dict) else {}
    scene["local_fetch_envelope"] = {
        **envelope,
        "eligible": bool(eligible),
    }


def generate_random_scenes(
    *,
    seed: int,
    random_cases: int,
    scene_set: str = DEFAULT_SCENE_SET,
) -> list[dict[str, Any]]:
    if str(scene_set or "").strip() == HARD_SCENE_SET:
        return generate_hard_scenes(random_cases=random_cases, scene_set=scene_set)
    if str(scene_set or "").strip() == OPPOSITE_BEHIND_SCENE_SET:
        return generate_opposite_behind_scenes(random_cases=random_cases, scene_set=scene_set)
    if str(scene_set or "").strip() == BROAD_SPATIAL_SCENE_SET:
        return generate_broad_spatial_scenes(random_cases=random_cases, scene_set=scene_set)

    rng = random.Random(int(seed))
    case_count = max(int(random_cases), 1)
    route_plan = list(ROUTE_LABELS)
    if case_count < len(route_plan):
        route_plan = [rng.choice(ROUTE_LABELS) for _ in range(case_count)]
    else:
        while len(route_plan) < case_count:
            route_plan.append(rng.choice(ROUTE_LABELS))
        rng.shuffle(route_plan)

    scenes: list[dict[str, Any]] = []
    for index, route_label in enumerate(route_plan[:case_count], start=1):
        scene_id = f"seed{int(seed)}_scene{index:02d}_{route_label}"
        if route_label == ROUTE_FETCH_READY:
            scene = _target_relative_scene(
                rng=rng,
                route_label=route_label,
                scene_id=scene_id,
                distance_range=(0.45, 0.75),
                angle_range_deg=(-25.0, 25.0),
                standoff_range=(0.28, 0.44),
                lateral_range=(-0.04, 0.04),
                yaw_error_range_deg=(-5.0, 5.0),
            )
        elif route_label == ROUTE_NAV2_REPOSITION:
            scene = _target_relative_scene(
                rng=rng,
                route_label=route_label,
                scene_id=scene_id,
                distance_range=(0.45, 0.75),
                angle_range_deg=(-30.0, 30.0),
                standoff_range=(1.05, 1.30),
                lateral_range=(-0.12, 0.12),
                yaw_error_range_deg=(-14.0, 14.0),
            )
        elif route_label == ROUTE_SCAN_OR_PERCEIVE:
            stale = rng.choice([True, False])
            scene = _target_relative_scene(
                rng=rng,
                route_label=route_label,
                scene_id=scene_id,
                distance_range=(0.45, 0.75),
                angle_range_deg=(-25.0, 25.0),
                standoff_range=(0.28, 0.44),
                lateral_range=(-0.08, 0.08),
                yaw_error_range_deg=(-12.0, 12.0),
                ball_confidence=0.35 if not stale else 0.95,
                target_confidence=0.99,
                state_age_s=4.0 if stale else 0.20,
            )
        elif route_label == ROUTE_RECOVERY_OR_REAIM:
            scene = _target_relative_scene(
                rng=rng,
                route_label=route_label,
                scene_id=scene_id,
                distance_range=(0.45, 0.75),
                angle_range_deg=(-30.0, 30.0),
                standoff_range=(0.28, 0.86),
                lateral_range=(-0.24, 0.24),
                yaw_error_range_deg=(-34.0, 34.0),
            )
            geometry = scene["geometry"]
            if (
                float(geometry["robot_lateral_error_m"]) <= FETCH_READY_LATERAL_LIMIT_M
                and abs(float(geometry["robot_yaw_error_deg"])) <= FETCH_READY_YAW_LIMIT_DEG
            ):
                sign = -1.0 if float(geometry["robot_lateral_signed_m"]) < 0 else 1.0
                geometry["robot_lateral_signed_m"] = round(0.18 * sign, 6)
                geometry["robot_lateral_error_m"] = 0.18
        elif route_label == ROUTE_LOCAL_SETUP_CAPTURE:
            scene = _target_relative_scene(
                rng=rng,
                route_label=route_label,
                scene_id=scene_id,
                distance_range=(0.50, 0.82),
                angle_range_deg=(-36.0, 36.0),
                standoff_range=(1.40, 2.20),
                lateral_range=(-0.36, 0.36),
                yaw_error_range_deg=(-150.0, 150.0),
            )
        else:
            scene = _target_relative_scene(
                rng=rng,
                route_label=route_label,
                scene_id=scene_id,
                distance_range=(1.30, 1.85),
                angle_range_deg=(-45.0, 45.0),
                standoff_range=(0.30, 0.50),
                lateral_range=(-0.10, 0.10),
                yaw_error_range_deg=(-12.0, 12.0),
                corridor_blocked=rng.choice([True, False]),
                corridor_clearance_m=rng.uniform(0.04, 0.10),
                unsafe_drift_m=rng.uniform(0.18, 0.35),
            )
        scene["scene_set"] = scene_set
        _augment_spatial_generalization_geometry(scene)
        _refresh_local_fetch_envelope(scene)
        scenes.append(scene)
    return scenes


def _fixed_target_relative_scene(
    *,
    route_label: str,
    scene_id: str,
    distance_m: float,
    angle_deg: float,
    standoff_m: float,
    lateral_m: float,
    yaw_error_deg: float,
    scene_set: str,
    ball_confidence: float = 0.98,
    target_confidence: float = 0.99,
    state_age_s: float = 0.15,
    corridor_blocked: bool = False,
    corridor_clearance_m: float = 0.35,
    unsafe_drift_m: float = 0.0,
) -> dict[str, Any]:
    scene = _target_relative_scene(
        rng=random.Random(1),
        route_label=route_label,
        scene_id=scene_id,
        distance_range=(float(distance_m), float(distance_m)),
        angle_range_deg=(float(angle_deg), float(angle_deg)),
        standoff_range=(float(standoff_m), float(standoff_m)),
        lateral_range=(float(lateral_m), float(lateral_m)),
        yaw_error_range_deg=(float(yaw_error_deg), float(yaw_error_deg)),
        ball_confidence=float(ball_confidence),
        target_confidence=float(target_confidence),
        state_age_s=float(state_age_s),
        corridor_blocked=bool(corridor_blocked),
        corridor_clearance_m=float(corridor_clearance_m),
        unsafe_drift_m=float(unsafe_drift_m),
    )
    scene["scene_set"] = scene_set
    _augment_spatial_generalization_geometry(scene)
    _refresh_local_fetch_envelope(scene)
    return scene


def _scene_with_relative_ball_bearing(
    *,
    route_label: str,
    scene_id: str,
    distance_m: float,
    angle_deg: float,
    standoff_m: float,
    lateral_m: float,
    relative_bearing_deg: float,
    scene_set: str,
    ball_confidence: float = 0.98,
    target_confidence: float = 0.99,
    state_age_s: float = 0.15,
    corridor_blocked: bool = False,
    corridor_clearance_m: float = 0.35,
    unsafe_drift_m: float = 0.0,
    opposite_side_setup: bool = False,
) -> dict[str, Any]:
    scene = _fixed_target_relative_scene(
        route_label=route_label,
        scene_id=scene_id,
        distance_m=distance_m,
        angle_deg=angle_deg,
        standoff_m=standoff_m,
        lateral_m=lateral_m,
        yaw_error_deg=0.0,
        scene_set=scene_set,
        ball_confidence=ball_confidence,
        target_confidence=target_confidence,
        state_age_s=state_age_s,
        corridor_blocked=corridor_blocked,
        corridor_clearance_m=corridor_clearance_m,
        unsafe_drift_m=unsafe_drift_m,
    )
    robot_pose = scene["robot_pose"]
    ball_pose = scene["ball_pose"]
    if opposite_side_setup:
        angle_rad = math.radians(angle_deg)
        normal_x = -math.sin(angle_rad)
        normal_y = math.cos(angle_rad)
        robot_pose["x"] = round(
            float(FETCH_TARGET_POSE["x"]) + (standoff_m * math.cos(angle_rad)) + (lateral_m * normal_x),
            6,
        )
        robot_pose["y"] = round(
            float(FETCH_TARGET_POSE["y"]) + (standoff_m * math.sin(angle_rad)) + (lateral_m * normal_y),
            6,
        )
        scene["geometry"]["robot_ball_distance_m"] = round(
            math.hypot(robot_pose["x"] - ball_pose["x"], robot_pose["y"] - ball_pose["y"]),
            6,
        )

    robot_to_ball_bearing_deg = _bearing_deg(robot_pose, ball_pose)
    robot_pose["yaw"] = round(math.radians(_normalize_angle_deg(robot_to_ball_bearing_deg - relative_bearing_deg)), 6)
    scene["geometry"]["robot_yaw_error_deg"] = round(
        _normalize_angle_deg(math.degrees(float(robot_pose["yaw"])) - float(angle_deg)),
        6,
    )
    _augment_spatial_generalization_geometry(scene)
    _refresh_local_fetch_envelope(scene)
    return scene


def generate_opposite_behind_scenes(
    *,
    random_cases: int = 12,
    scene_set: str = OPPOSITE_BEHIND_SCENE_SET,
) -> list[dict[str, Any]]:
    """Return a deterministic broad-spatial matrix for opposite-side UAT."""

    scenes = [
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="opbehind_nav2_ball_behind_left_01",
            distance_m=0.64,
            angle_deg=24.0,
            standoff_m=1.10,
            lateral_m=0.10,
            relative_bearing_deg=138.0,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="opbehind_nav2_ball_behind_right_02",
            distance_m=0.66,
            angle_deg=-26.0,
            standoff_m=1.12,
            lateral_m=-0.10,
            relative_bearing_deg=-142.0,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="opbehind_nav2_wraparound_left_03",
            distance_m=0.72,
            angle_deg=38.0,
            standoff_m=1.24,
            lateral_m=0.18,
            relative_bearing_deg=168.0,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="opbehind_nav2_wraparound_right_04",
            distance_m=0.74,
            angle_deg=-38.0,
            standoff_m=1.24,
            lateral_m=-0.18,
            relative_bearing_deg=-168.0,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_SCAN_OR_PERCEIVE,
            scene_id="opbehind_scan_stale_behind_05",
            distance_m=0.58,
            angle_deg=12.0,
            standoff_m=0.84,
            lateral_m=0.08,
            relative_bearing_deg=126.0,
            state_age_s=4.0,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_NO_GO,
            scene_id="opbehind_no_go_blocked_behind_06",
            distance_m=0.62,
            angle_deg=-14.0,
            standoff_m=0.86,
            lateral_m=-0.08,
            relative_bearing_deg=-132.0,
            corridor_blocked=True,
            corridor_clearance_m=0.06,
            unsafe_drift_m=0.24,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="opbehind_nav2_opposite_circle_left_07",
            distance_m=0.62,
            angle_deg=160.0,
            standoff_m=0.82,
            lateral_m=0.12,
            relative_bearing_deg=112.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="opbehind_nav2_opposite_circle_right_08",
            distance_m=0.62,
            angle_deg=-160.0,
            standoff_m=0.84,
            lateral_m=-0.12,
            relative_bearing_deg=-116.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_NO_GO,
            scene_id="opbehind_no_go_far_opposite_09",
            distance_m=1.32,
            angle_deg=172.0,
            standoff_m=0.92,
            lateral_m=0.04,
            relative_bearing_deg=148.0,
            opposite_side_setup=True,
            corridor_clearance_m=0.18,
            unsafe_drift_m=0.21,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_FETCH_READY,
            scene_id="opbehind_fetch_ready_local_control_10",
            distance_m=0.55,
            angle_deg=8.0,
            standoff_m=0.34,
            lateral_m=0.018,
            yaw_error_deg=2.2,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_RECOVERY_OR_REAIM,
            scene_id="opbehind_recovery_lateral_debt_11",
            distance_m=0.62,
            angle_deg=-18.0,
            standoff_m=0.76,
            lateral_m=-0.19,
            yaw_error_deg=-24.0,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_RECOVERY_OR_REAIM,
            scene_id="opbehind_recovery_yaw_debt_12",
            distance_m=0.60,
            angle_deg=20.0,
            standoff_m=0.70,
            lateral_m=0.12,
            yaw_error_deg=31.0,
            scene_set=scene_set,
        ),
    ]
    case_count = max(int(random_cases), 1)
    if case_count <= len(scenes):
        return scenes[:case_count]
    extra: list[dict[str, Any]] = []
    while len(scenes) + len(extra) < case_count:
        template = scenes[len(extra) % len(scenes)]
        clone = json.loads(json.dumps(template))
        clone["scene_id"] = f"{template['scene_id']}_repeat{len(extra) + 1:02d}"
        extra.append(clone)
    return scenes + extra


def generate_broad_spatial_scenes(
    *,
    random_cases: int = 18,
    scene_set: str = BROAD_SPATIAL_SCENE_SET,
) -> list[dict[str, Any]]:
    """Return a broad deterministic matrix for generalizable fetch setup UAT."""

    scenes = [
        *generate_opposite_behind_scenes(random_cases=12, scene_set=scene_set),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="broad_nav2_opposite_circle_left_deep_13",
            distance_m=0.76,
            angle_deg=145.0,
            standoff_m=0.96,
            lateral_m=0.18,
            relative_bearing_deg=132.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="broad_nav2_opposite_circle_right_deep_14",
            distance_m=0.76,
            angle_deg=-145.0,
            standoff_m=0.96,
            lateral_m=-0.18,
            relative_bearing_deg=-132.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="broad_nav2_opposite_circle_left_shallow_15",
            distance_m=0.48,
            angle_deg=122.0,
            standoff_m=0.78,
            lateral_m=-0.10,
            relative_bearing_deg=104.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="broad_nav2_opposite_circle_right_shallow_16",
            distance_m=0.48,
            angle_deg=-122.0,
            standoff_m=0.78,
            lateral_m=0.10,
            relative_bearing_deg=-104.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_SCAN_OR_PERCEIVE,
            scene_id="broad_scan_low_confidence_opposite_17",
            distance_m=0.66,
            angle_deg=152.0,
            standoff_m=0.86,
            lateral_m=0.06,
            relative_bearing_deg=118.0,
            ball_confidence=0.35,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_NO_GO,
            scene_id="broad_no_go_blocked_opposite_right_18",
            distance_m=0.70,
            angle_deg=-150.0,
            standoff_m=0.92,
            lateral_m=-0.06,
            relative_bearing_deg=-122.0,
            opposite_side_setup=True,
            corridor_blocked=True,
            corridor_clearance_m=0.05,
            unsafe_drift_m=0.24,
            scene_set=scene_set,
        ),
    ]
    case_count = max(int(random_cases), 1)
    if case_count <= len(scenes):
        return scenes[:case_count]
    extra: list[dict[str, Any]] = []
    while len(scenes) + len(extra) < case_count:
        template = scenes[len(extra) % len(scenes)]
        clone = json.loads(json.dumps(template))
        clone["scene_id"] = f"{template['scene_id']}_repeat{len(extra) + 1:02d}"
        extra.append(clone)
    return scenes + extra


def generate_hard_scenes(*, random_cases: int = 10, scene_set: str = HARD_SCENE_SET) -> list[dict[str, Any]]:
    """Return a deterministic hard mixed matrix for route-owner UAT pressure."""

    scenes = [
        _fixed_target_relative_scene(
            route_label=ROUTE_FETCH_READY,
            scene_id="hard_fetch_ready_wide_left_01",
            distance_m=0.72,
            angle_deg=-38.0,
            standoff_m=0.42,
            lateral_m=0.045,
            yaw_error_deg=5.4,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_FETCH_READY,
            scene_id="hard_fetch_ready_wide_right_02",
            distance_m=0.73,
            angle_deg=38.0,
            standoff_m=0.43,
            lateral_m=-0.044,
            yaw_error_deg=-5.5,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="hard_nav2_opposite_side_left_01",
            distance_m=0.62,
            angle_deg=170.0,
            standoff_m=1.08,
            lateral_m=0.08,
            relative_bearing_deg=112.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _scene_with_relative_ball_bearing(
            route_label=ROUTE_LOCAL_SETUP_CAPTURE,
            scene_id="hard_nav2_opposite_side_right_02",
            distance_m=0.62,
            angle_deg=-170.0,
            standoff_m=1.12,
            lateral_m=-0.10,
            relative_bearing_deg=-116.0,
            opposite_side_setup=True,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_RECOVERY_OR_REAIM,
            scene_id="hard_recovery_large_angle_left_01",
            distance_m=0.68,
            angle_deg=42.0,
            standoff_m=0.84,
            lateral_m=0.22,
            yaw_error_deg=32.0,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_RECOVERY_OR_REAIM,
            scene_id="hard_recovery_large_angle_right_02",
            distance_m=0.68,
            angle_deg=-45.0,
            standoff_m=0.78,
            lateral_m=-0.21,
            yaw_error_deg=-33.0,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_SCAN_OR_PERCEIVE,
            scene_id="hard_scan_low_confidence_01",
            distance_m=0.66,
            angle_deg=35.0,
            standoff_m=0.40,
            lateral_m=0.03,
            yaw_error_deg=4.0,
            ball_confidence=0.35,
            state_age_s=0.20,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_SCAN_OR_PERCEIVE,
            scene_id="hard_scan_stale_opposite_02",
            distance_m=0.62,
            angle_deg=-160.0,
            standoff_m=0.42,
            lateral_m=-0.02,
            yaw_error_deg=-4.0,
            ball_confidence=0.95,
            state_age_s=4.0,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_NO_GO,
            scene_id="hard_no_go_far_target_01",
            distance_m=1.35,
            angle_deg=60.0,
            standoff_m=0.40,
            lateral_m=0.06,
            yaw_error_deg=6.0,
            corridor_clearance_m=0.20,
            unsafe_drift_m=0.20,
            scene_set=scene_set,
        ),
        _fixed_target_relative_scene(
            route_label=ROUTE_NO_GO,
            scene_id="hard_no_go_blocked_corridor_02",
            distance_m=0.68,
            angle_deg=-30.0,
            standoff_m=0.38,
            lateral_m=-0.03,
            yaw_error_deg=-4.0,
            corridor_blocked=True,
            corridor_clearance_m=0.06,
            unsafe_drift_m=0.22,
            scene_set=scene_set,
        ),
    ]
    case_count = max(int(random_cases), 1)
    return scenes[:case_count]


def _scene_payloads_from_file(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    if not payload:
        return []
    if isinstance(payload.get("scenes"), list):
        candidates = payload.get("scenes", [])
    elif isinstance(payload.get("scene"), dict):
        candidates = [payload.get("scene", {})]
    else:
        candidates = [payload]
    scenes: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict) and item:
            scenes.append(dict(item))
    return scenes


def load_frozen_scenes(
    *,
    scene_descriptor_json: list[str] | None = None,
    scene_dir: str = "",
    scene_set: str = DEFAULT_SCENE_SET,
) -> list[dict[str, Any]]:
    paths: list[Path] = []
    for raw_path in list(scene_descriptor_json or []):
        if str(raw_path or "").strip():
            paths.append(_resolve_path(raw_path))
    if str(scene_dir or "").strip():
        directory = _resolve_path(scene_dir)
        if directory.is_dir():
            paths.extend(sorted(path for path in directory.glob("*.json") if path.is_file()))
    scenes: list[dict[str, Any]] = []
    for path in paths:
        for scene in _scene_payloads_from_file(path):
            scene.setdefault("scene_set", scene_set)
            scene.setdefault("source_scene_path", str(path))
            _augment_spatial_generalization_geometry(scene)
            _refresh_local_fetch_envelope(scene)
            scenes.append(scene)
    return scenes


def deterministic_route_label(scene: dict[str, Any]) -> str:
    perception = scene.get("perception") if isinstance(scene.get("perception"), dict) else {}
    corridor = scene.get("corridor") if isinstance(scene.get("corridor"), dict) else {}
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    ball_conf = _finite_float(perception.get("ball_confidence"), 0.0)
    target_conf = _finite_float(perception.get("target_confidence"), 0.0)
    state_age_s = _finite_float(perception.get("state_age_s"), 999.0)
    blocked = bool(corridor.get("blocked", False))
    clearance_m = _finite_float(corridor.get("clearance_m"), 0.0)
    unsafe_drift_m = _finite_float(corridor.get("unsafe_drift_m"), 0.0)
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    needs_local_setup_capture = bool(_geometry_needs_ball_relative_setup_owner(geometry))

    if ball_conf < 0.65 or target_conf < 0.65 or state_age_s > 2.0:
        return ROUTE_SCAN_OR_PERCEIVE
    if blocked or clearance_m < 0.12 or unsafe_drift_m > 0.16 or ball_target_distance_m > 1.20:
        return ROUTE_NO_GO
    if not (0.34 <= ball_target_distance_m <= 0.85):
        return ROUTE_NO_GO
    if (
        0.24 <= robot_ball_distance_m <= 0.52
        and lateral_error_m <= FETCH_READY_LATERAL_LIMIT_M
        and yaw_error_deg <= FETCH_READY_YAW_LIMIT_DEG
    ):
        return ROUTE_FETCH_READY
    if (
        robot_ball_distance_m <= RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= RECOVERY_LATERAL_LIMIT_M
        and yaw_error_deg <= RECOVERY_YAW_LIMIT_DEG
    ):
        return ROUTE_RECOVERY_OR_REAIM
    if _extended_recovery_admissible_from_geometry(geometry):
        return ROUTE_RECOVERY_OR_REAIM
    if needs_local_setup_capture and _local_setup_capture_admissible_from_geometry(geometry):
        return ROUTE_LOCAL_SETUP_CAPTURE
    return ROUTE_NAV2_REPOSITION


def score_route_quality(scene: dict[str, Any], route_label: str = "") -> dict[str, Any]:
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    corridor = scene.get("corridor") if isinstance(scene.get("corridor"), dict) else {}
    perception = scene.get("perception") if isinstance(scene.get("perception"), dict) else {}
    route = str(route_label or deterministic_route_label(scene)).strip()
    lateral_m = abs(_finite_float(geometry.get("robot_lateral_error_m"), 999.0))
    yaw_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    robot_ball_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    ball_target_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    ball_target_angle_deg = abs(_finite_float(geometry.get("ball_target_angle_deg"), 0.0))
    robot_ball_relative_bearing_abs_deg = _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0)
    opposite_side_of_circle = bool(geometry.get("opposite_side_of_circle", False))
    clearance_m = _finite_float(corridor.get("clearance_m"), 0.0)
    blocked = bool(corridor.get("blocked", False))
    ball_conf = _finite_float(perception.get("ball_confidence"), 0.0)
    target_conf = _finite_float(perception.get("target_confidence"), 0.0)
    state_age_s = _finite_float(perception.get("state_age_s"), 999.0)

    flags: list[str] = []
    recommendations: list[str] = []
    non_contact_route = route in {ROUTE_SCAN_OR_PERCEIVE, ROUTE_NO_GO}
    status = "clean"
    risk = "low"
    setup_debt_lateral_m = max(lateral_m - CONTACT_QUALITY_CLEAN_LATERAL_M, 0.0)
    setup_debt_yaw_deg = max(yaw_deg - CONTACT_QUALITY_CLEAN_YAW_DEG, 0.0)

    if ball_conf < 0.65 or target_conf < 0.65 or state_age_s > 2.0:
        flags.append("perception_refresh_required")
    if blocked or clearance_m < 0.12:
        flags.append("corridor_unusable")
    if not 0.34 <= ball_target_m <= 0.85:
        flags.append("target_distance_outside_local_fetch_window")
    if robot_ball_relative_bearing_abs_deg >= 90.0:
        flags.append("ball_behind_robot_heading")
    if opposite_side_of_circle:
        flags.append("opposite_side_of_circle")

    if route == ROUTE_FETCH_READY:
        lateral_ratio = _quality_ratio(lateral_m, CONTACT_QUALITY_CLEAN_LATERAL_M, FETCH_READY_LATERAL_LIMIT_M)
        yaw_ratio = _quality_ratio(yaw_deg, CONTACT_QUALITY_CLEAN_YAW_DEG, FETCH_READY_YAW_LIMIT_DEG)
        severity = max(lateral_ratio, yaw_ratio)
        if lateral_m > CONTACT_QUALITY_CLEAN_LATERAL_M:
            flags.append("initial_lateral_setup_debt")
        if yaw_deg > CONTACT_QUALITY_CLEAN_YAW_DEG:
            flags.append("initial_yaw_setup_debt")
        if lateral_m > FETCH_READY_LATERAL_LIMIT_M or yaw_deg > FETCH_READY_YAW_LIMIT_DEG:
            flags.append("outside_fetch_ready_envelope")
            status = "blocker"
            risk = "high"
        elif severity > 0.0:
            status = "watch"
            risk = "medium" if severity >= 0.45 else "low"
        recommendations.append("local_line_servo_contact")
        if status != "clean":
            recommendations.append("pre_contact_smoothing")
        score = 100.0 - 42.0 * severity
    elif route == ROUTE_RECOVERY_OR_REAIM:
        nominal_recovery = _recovery_admissible_from_geometry(geometry)
        extended_recovery = _extended_recovery_admissible_from_geometry(geometry)
        lateral_limit_m = RECOVERY_LATERAL_LIMIT_M if nominal_recovery else EXTENDED_RECOVERY_LATERAL_LIMIT_M
        yaw_limit_deg = RECOVERY_YAW_LIMIT_DEG if nominal_recovery else EXTENDED_RECOVERY_YAW_LIMIT_DEG
        standoff_limit_m = (
            RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
            if nominal_recovery
            else EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        )
        lateral_ratio = _quality_ratio(lateral_m, FETCH_READY_LATERAL_LIMIT_M, lateral_limit_m)
        yaw_ratio = _quality_ratio(yaw_deg, FETCH_READY_YAW_LIMIT_DEG, yaw_limit_deg)
        standoff_ratio = _quality_ratio(robot_ball_m, 0.52, standoff_limit_m)
        severity = max(lateral_ratio, yaw_ratio, standoff_ratio)
        flags.append("bounded_recovery_required")
        if extended_recovery and not nominal_recovery:
            flags.append("extended_recovery_reaim_required")
        if lateral_m > CONTACT_QUALITY_CLEAN_LATERAL_M:
            flags.append("initial_lateral_setup_debt")
        if yaw_deg > CONTACT_QUALITY_CLEAN_YAW_DEG:
            flags.append("initial_yaw_setup_debt")
        if (
            lateral_m > RECOVERY_LATERAL_LIMIT_M
            or yaw_deg > RECOVERY_YAW_LIMIT_DEG
            or robot_ball_m > RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        ) and extended_recovery:
            flags.append("outside_nominal_recovery_envelope")
        if (
            lateral_m > EXTENDED_RECOVERY_LATERAL_LIMIT_M
            or yaw_deg > EXTENDED_RECOVERY_YAW_LIMIT_DEG
            or robot_ball_m > EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        ):
            flags.append("outside_recovery_envelope")
            status = "blocker"
            risk = "high"
        else:
            status = "watch"
            risk = "high" if severity >= 0.65 else "medium"
        recommendations.extend(["bounded_reaim_before_push", "pre_contact_smoothing"])
        score = 78.0 - 38.0 * severity
    elif route == ROUTE_LOCAL_SETUP_CAPTURE:
        lateral_ratio = _quality_ratio(lateral_m, RECOVERY_LATERAL_LIMIT_M, LOCAL_SETUP_CAPTURE_LATERAL_LIMIT_M)
        yaw_ratio = _quality_ratio(yaw_deg, RECOVERY_YAW_LIMIT_DEG, LOCAL_SETUP_CAPTURE_YAW_LIMIT_DEG)
        standoff_ratio = _quality_ratio(robot_ball_m, RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M, LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M)
        severity = max(lateral_ratio, yaw_ratio, standoff_ratio)
        flags.append("local_setup_capture_required")
        if robot_ball_relative_bearing_abs_deg >= 90.0:
            flags.append("ball_relative_wraparound_required")
        if lateral_m > RECOVERY_LATERAL_LIMIT_M:
            flags.append("wide_lateral_setup_debt")
        if yaw_deg > RECOVERY_YAW_LIMIT_DEG:
            flags.append("wide_yaw_setup_debt")
        if robot_ball_m > NAV2_REPOSITION_STANDOFF_LIMIT_M:
            flags.append("wide_setup_distance_debt")
        if not _local_setup_capture_admissible_from_geometry(geometry):
            flags.append("outside_local_setup_capture_envelope")
            status = "blocker"
            risk = "high"
        else:
            status = "watch"
            risk = "high" if severity >= 0.60 else "medium"
        recommendations.extend(["measured_local_setup_capture", "verify_push_ready_pose_before_fetch"])
        score = 72.0 - 34.0 * severity
    elif route == ROUTE_NAV2_REPOSITION:
        standoff_ratio = _quality_ratio(robot_ball_m, 0.70, NAV2_REPOSITION_STANDOFF_LIMIT_M)
        angle_ratio = _quality_ratio(ball_target_angle_deg, 20.0, 45.0)
        severity = max(standoff_ratio, angle_ratio)
        flags.append("nav2_reposition_required")
        if robot_ball_m < NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M:
            flags.append("nav2_reposition_near_field_not_admissible")
            status = "blocker"
            risk = "high"
            recommendations.extend(["bounded_reaim_before_push", "pre_contact_smoothing"])
            score = 24.0
        elif robot_ball_m > NAV2_REPOSITION_STANDOFF_LIMIT_M:
            flags.append("nav2_setup_distance_watch")
            status = "watch"
            risk = "medium" if severity >= 0.55 else "low"
            recommendations.extend(["nav2_forward_reposition", "verify_setup_pose_before_push"])
            score = 84.0 - 28.0 * severity
        else:
            status = "watch"
            risk = "medium" if severity >= 0.55 else "low"
            recommendations.extend(["nav2_forward_reposition", "verify_setup_pose_before_push"])
            score = 84.0 - 28.0 * severity
        if robot_ball_relative_bearing_abs_deg >= 90.0 or opposite_side_of_circle:
            recommendations.extend(["nav2_wraparound_setup", "verify_push_ready_pose_before_fetch"])
    elif route == ROUTE_SCAN_OR_PERCEIVE:
        status = "blocker"
        risk = "unavailable"
        recommendations.append("scan_or_perception_refresh")
        score = 0.0
    elif route == ROUTE_NO_GO:
        status = "blocker"
        risk = "unavailable"
        recommendations.append("safe_no_go")
        score = 0.0
    else:
        status = "blocker"
        risk = "unknown"
        flags.append("unsupported_route")
        recommendations.append("planner_guard_recheck")
        score = 0.0

    if non_contact_route:
        predicted_first_contact_quality = "not_applicable"
    else:
        predicted_first_contact_quality = status

    return {
        "route_label": route,
        "quality_score": round(max(0.0, min(100.0, float(score))), 3),
        "predicted_contact_quality": status,
        "predicted_first_contact_risk": risk,
        "predicted_first_contact_quality": predicted_first_contact_quality,
        "flags": sorted(set(flags)),
        "recommendations": recommendations,
        "setup_debt": {
            "lateral_m": round(float(setup_debt_lateral_m), 6),
            "yaw_deg": round(float(setup_debt_yaw_deg), 6),
            "robot_ball_distance_m": round(float(robot_ball_m), 6),
            "ball_target_distance_m": round(float(ball_target_m), 6),
            "ball_target_angle_abs_deg": round(float(ball_target_angle_deg), 6),
        },
        "thresholds": {
            "clean_lateral_m": CONTACT_QUALITY_CLEAN_LATERAL_M,
            "clean_yaw_deg": CONTACT_QUALITY_CLEAN_YAW_DEG,
            "fetch_ready_lateral_limit_m": FETCH_READY_LATERAL_LIMIT_M,
            "fetch_ready_yaw_limit_deg": FETCH_READY_YAW_LIMIT_DEG,
            "recovery_lateral_limit_m": RECOVERY_LATERAL_LIMIT_M,
            "recovery_yaw_limit_deg": RECOVERY_YAW_LIMIT_DEG,
            "recovery_robot_ball_distance_limit_m": RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M,
            "extended_recovery_lateral_limit_m": EXTENDED_RECOVERY_LATERAL_LIMIT_M,
            "extended_recovery_yaw_limit_deg": EXTENDED_RECOVERY_YAW_LIMIT_DEG,
            "extended_recovery_robot_ball_distance_limit_m": EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M,
            "local_setup_capture_lateral_limit_m": LOCAL_SETUP_CAPTURE_LATERAL_LIMIT_M,
            "local_setup_capture_yaw_limit_deg": LOCAL_SETUP_CAPTURE_YAW_LIMIT_DEG,
            "local_setup_capture_robot_ball_distance_limit_m": LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M,
            "nav2_reposition_min_robot_ball_distance_m": NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M,
        },
    }


def executor_for_route(route_label: str) -> str:
    return str(ROUTE_EXECUTORS.get(str(route_label or "").strip(), "unsupported_route"))


def default_maneuver_sequence_for_route(scene: dict[str, Any], route_label: str) -> list[str]:
    route = str(route_label or "").strip()
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    opposite = bool(geometry.get("opposite_side_of_circle", False))
    behind = _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0) >= 90.0
    if route == ROUTE_SCAN_OR_PERCEIVE:
        return [MANEUVER_SCAN]
    if route == ROUTE_NO_GO:
        return [MANEUVER_NO_GO]
    if route == ROUTE_FETCH_READY:
        return [MANEUVER_VALIDATE_PUSH_READY, MANEUVER_LOCAL_FETCH, MANEUVER_MONITOR_DELIVERY]
    if route == ROUTE_RECOVERY_OR_REAIM:
        return [
            MANEUVER_RECOVERY_REAIM,
            MANEUVER_VALIDATE_PUSH_READY,
            MANEUVER_LOCAL_FETCH,
            MANEUVER_MONITOR_DELIVERY,
        ]
    if route == ROUTE_LOCAL_SETUP_CAPTURE:
        sequence = [MANEUVER_LOCAL_SETUP_CAPTURE]
        if opposite or behind:
            sequence.append(MANEUVER_WRAPAROUND_SETUP)
        sequence.extend([MANEUVER_VALIDATE_PUSH_READY, MANEUVER_LOCAL_FETCH, MANEUVER_MONITOR_DELIVERY])
        return sequence
    if route == ROUTE_NAV2_REPOSITION:
        sequence = [MANEUVER_NAV2_REPOSITION]
        if opposite or behind:
            sequence.append(MANEUVER_WRAPAROUND_SETUP)
        sequence.extend([MANEUVER_VALIDATE_PUSH_READY, MANEUVER_LOCAL_FETCH, MANEUVER_MONITOR_DELIVERY])
        return sequence
    return [MANEUVER_NO_GO]


def compile_maneuver_plan(
    scene: dict[str, Any],
    route_label: str,
    *,
    proposed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route = str(route_label or "").strip()
    proposed = proposed if isinstance(proposed, dict) else {}
    raw_sequence = proposed.get("maneuver_sequence") if isinstance(proposed.get("maneuver_sequence"), list) else []
    sequence = [str(item).strip() for item in raw_sequence if str(item or "").strip() in MANEUVER_LABELS]
    source = "llm_proposed"
    if not sequence:
        sequence = default_maneuver_sequence_for_route(scene, route)
        source = "deterministic_compiled"

    executable_fetch_route = route in {
        ROUTE_FETCH_READY,
        ROUTE_NAV2_REPOSITION,
        ROUTE_RECOVERY_OR_REAIM,
        ROUTE_LOCAL_SETUP_CAPTURE,
    }
    veto_reasons: list[str] = []
    if executable_fetch_route:
        if MANEUVER_LOCAL_FETCH not in sequence:
            veto_reasons.append("missing_local_fetch_maneuver")
        if MANEUVER_VALIDATE_PUSH_READY not in sequence:
            veto_reasons.append("missing_validate_push_ready_before_fetch")
        elif MANEUVER_LOCAL_FETCH in sequence and sequence.index(MANEUVER_VALIDATE_PUSH_READY) > sequence.index(MANEUVER_LOCAL_FETCH):
            veto_reasons.append("validate_push_ready_after_fetch")
    else:
        if MANEUVER_LOCAL_FETCH in sequence:
            veto_reasons.append("planner_only_route_attempted_local_fetch")

    for blocked in ("cmd_vel", "direct_ball_impulse", "shoot_ball"):
        if blocked in {item.lower() for item in sequence}:
            veto_reasons.append(f"forbidden_maneuver_{blocked}")

    if veto_reasons:
        sequence = default_maneuver_sequence_for_route(scene, route)
        source = "deterministic_compiled_after_veto"

    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    inserted_maneuvers: list[str] = []
    requires_wraparound_setup = bool(
        route in {ROUTE_LOCAL_SETUP_CAPTURE, ROUTE_NAV2_REPOSITION}
        and (
            bool(geometry.get("opposite_side_of_circle", False))
            or _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0) >= 90.0
        )
    )
    if requires_wraparound_setup and MANEUVER_WRAPAROUND_SETUP not in sequence:
        if route == ROUTE_LOCAL_SETUP_CAPTURE and MANEUVER_LOCAL_SETUP_CAPTURE in sequence:
            insert_at = sequence.index(MANEUVER_LOCAL_SETUP_CAPTURE) + 1
        elif route == ROUTE_NAV2_REPOSITION and MANEUVER_NAV2_REPOSITION in sequence:
            insert_at = sequence.index(MANEUVER_NAV2_REPOSITION) + 1
        elif MANEUVER_VALIDATE_PUSH_READY in sequence:
            insert_at = sequence.index(MANEUVER_VALIDATE_PUSH_READY)
        else:
            insert_at = 0
        sequence.insert(insert_at, MANEUVER_WRAPAROUND_SETUP)
        inserted_maneuvers.append(MANEUVER_WRAPAROUND_SETUP)
        if source == "llm_proposed":
            source = "llm_proposed_with_deterministic_required_maneuvers"
    validation_gates = proposed.get("validation_gates") if isinstance(proposed.get("validation_gates"), list) else []
    if not validation_gates and executable_fetch_route:
        validation_gates = [
            "state_not_stale",
            "ball_motion_within_setup_limit",
            "robot_ball_distance_within_push_ready_window",
            "lateral_error_within_push_ready_limit",
            "yaw_error_within_push_ready_limit",
        ]
    elif not validation_gates:
        validation_gates = ["planner_only_route_local_fetch_withheld"]
    replan_triggers = proposed.get("replan_triggers") if isinstance(proposed.get("replan_triggers"), list) else []
    if not replan_triggers:
        replan_triggers = [
            "stale_state",
            "ball_escape",
            "setup_timeout",
            "push_ready_validation_failed",
            "nav2_abort",
        ]
    return {
        "objective": str(proposed.get("objective", "") or "deliver_ball_to_target_circle"),
        "route_label": route,
        "route_executor": executor_for_route(route),
        "source": source,
        "maneuver_sequence": sequence,
        "validation_gates": [str(item) for item in validation_gates],
        "replan_triggers": [str(item) for item in replan_triggers],
        "requires_measured_push_ready_before_fetch": bool(executable_fetch_route),
        "local_fetch_index": sequence.index(MANEUVER_LOCAL_FETCH) if MANEUVER_LOCAL_FETCH in sequence else None,
        "push_ready_index": sequence.index(MANEUVER_VALIDATE_PUSH_READY) if MANEUVER_VALIDATE_PUSH_READY in sequence else None,
        "opposite_side_of_circle": bool(geometry.get("opposite_side_of_circle", False)),
        "robot_ball_relative_bearing_abs_deg": round(
            _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0),
            6,
        ),
        "inserted_maneuvers": inserted_maneuvers,
        "veto_reasons": veto_reasons,
        "valid": not bool(veto_reasons),
        "no_direct_cmd_vel": True,
        "no_direct_ball_impulse": True,
    }


def random_profile_for_scene(scene: dict[str, Any]) -> str:
    explicit = str(scene.get("random_profile", "") or "").strip()
    if explicit:
        return explicit
    scene_set = str(scene.get("scene_set", "") or "").strip()
    if scene_set == OPPOSITE_BEHIND_SCENE_SET:
        return OPPOSITE_BEHIND_PROFILE
    if scene_set == BROAD_SPATIAL_SCENE_SET:
        return BROAD_SPATIAL_PROFILE
    return PLANNER_MIXED_PROFILE


def planner_prompt(scene: dict[str, Any]) -> str:
    return (
        "Plan this robot fetch scene before any local fetch execution.\n"
        "Return one compatible route label plus a bounded maneuver sequence. "
        "The planner may solve open field-like setup challenges with scan, reposition, wraparound setup, "
        "re-aim, push-ready validation, local fetch, recovery, or no-go maneuvers. "
        "Never emit velocity commands. Local fetch may appear only after validate_push_ready.\n"
        f"Allowed labels: {json.dumps(list(ROUTE_LABELS))}\n\n"
        f"Allowed maneuvers: {json.dumps(list(MANEUVER_LABELS))}\n\n"
        f"Scene descriptor:\n{json.dumps(scene, indent=2, sort_keys=True)}"
    )


def build_llm_shadow_request(
    *,
    scene: dict[str, Any],
    model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    return {
        "model": model,
        "store": False,
        "parallel_tool_calls": False,
        "reasoning": {"effort": reasoning_effort},
        "instructions": (
            "You are a high-level field robot planner. Use exactly one function tool. "
            "Generate a bounded maneuver plan for a soccer-field or putting-green-like fetch setup. "
            "Route labels are compatibility summaries; the maneuver sequence is the plan. "
            "Never emit velocity commands and never bypass deterministic validation gates."
        ),
        "input": planner_prompt(scene),
        "tool_choice": "required",
        "tools": [
            {
                "type": "function",
                "name": OPENAI_TOOL_NAME,
                "description": "Submit the fetch planner route label.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "route_label",
                        "objective",
                        "maneuver_sequence",
                        "validation_gates",
                        "replan_triggers",
                        "rationale_short",
                        "confidence",
                    ],
                    "properties": {
                        "route_label": {"type": "string", "enum": list(ROUTE_LABELS)},
                        "objective": {"type": "string"},
                        "maneuver_sequence": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(MANEUVER_LABELS)},
                        },
                        "validation_gates": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "replan_triggers": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "rationale_short": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                },
            }
        ],
    }


def extract_llm_route(raw_response: dict[str, Any]) -> dict[str, Any]:
    for item in list(raw_response.get("output", [])):
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        if str(item.get("name", "")).strip() != OPENAI_TOOL_NAME:
            continue
        try:
            payload = json.loads(str(item.get("arguments", "") or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM route arguments were not JSON: {exc}") from exc
        route_label = str(payload.get("route_label", "")).strip()
        if route_label not in ROUTE_LABELS:
            raise ValueError(f"LLM emitted unsupported route label: {route_label}")
        return {
            "route_label": route_label,
            "objective": str(payload.get("objective", "") or ""),
            "maneuver_sequence": [
                str(item)
                for item in list(payload.get("maneuver_sequence", []))
                if str(item or "").strip()
            ],
            "validation_gates": [
                str(item)
                for item in list(payload.get("validation_gates", []))
                if str(item or "").strip()
            ],
            "replan_triggers": [
                str(item)
                for item in list(payload.get("replan_triggers", []))
                if str(item or "").strip()
            ],
            "rationale_short": str(payload.get("rationale_short", "") or ""),
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
        }
    raise ValueError("LLM response did not contain a fetch planner route tool call.")


def decide_scene(
    scene: dict[str, Any],
    *,
    planner_mode: str = PLANNER_MODE_DETERMINISTIC,
    openai_api_key: str = "",
    openai_model: str = DEFAULT_OPENAI_MODEL,
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL,
    openai_org_id: str = "",
    openai_project_id: str = "",
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    expected_route = str(scene.get("expected_route_label", "") or "")
    guard_route = deterministic_route_label(scene)
    provider_request: dict[str, Any] = {}
    provider_response: dict[str, Any] = {}
    provider_status = "not_used"
    provider_error = ""
    provider_attempts: list[dict[str, Any]] = []
    route_label = guard_route
    rationale = "Deterministic guard classified the scene."
    confidence = 1.0
    planner_mode_effective = PLANNER_MODE_DETERMINISTIC
    llm_route_label = ""
    llm_rationale = ""
    llm_confidence = 0.0
    llm_plan: dict[str, Any] = {}
    llm_supervised_guard: dict[str, Any] = {}

    if planner_mode in {PLANNER_MODE_LLM_SHADOW, PLANNER_MODE_LLM_SUPERVISED_GUARDED}:
        provider_request = build_llm_shadow_request(
            scene=scene,
            model=openai_model,
            reasoning_effort=reasoning_effort,
        )
        if not str(openai_api_key or "").strip():
            provider_status = "skipped_missing_openai_api_key"
            planner_mode_effective = "deterministic_fallback"
            rationale = "LLM shadow request recorded; missing OPENAI_API_KEY so deterministic guard provided the route."
            confidence = 0.0
        else:
            for attempt_index in range(1, LLM_PROVIDER_MAX_ATTEMPTS + 1):
                try:
                    provider_response = call_openai_responses(
                        api_key=openai_api_key,
                        request_payload=provider_request,
                        base_url=normalize_openai_base_url(openai_base_url),
                        timeout_s=timeout_s,
                        org_id=openai_org_id,
                        project_id=openai_project_id,
                    )
                    route = extract_llm_route(provider_response)
                    llm_route_label = route["route_label"]
                    llm_rationale = route["rationale_short"]
                    llm_confidence = float(route["confidence"])
                    llm_plan = {
                        "objective": route.get("objective", ""),
                        "maneuver_sequence": route.get("maneuver_sequence", []),
                        "validation_gates": route.get("validation_gates", []),
                        "replan_triggers": route.get("replan_triggers", []),
                    }
                    route_label = llm_route_label
                    rationale = llm_rationale
                    confidence = llm_confidence
                    provider_status = "ok"
                    provider_error = ""
                    planner_mode_effective = PLANNER_MODE_LLM_SHADOW
                    provider_attempts.append({"attempt": attempt_index, "status": "ok"})
                    break
                except Exception as exc:
                    provider_status = "error"
                    provider_error = str(exc)
                    planner_mode_effective = "deterministic_fallback"
                    rationale = "LLM shadow failed validation; deterministic guard provided the route."
                    confidence = 0.0
                    provider_attempts.append(
                        {
                            "attempt": attempt_index,
                            "status": "error",
                            "error": provider_error,
                        }
                    )

        if planner_mode == PLANNER_MODE_LLM_SUPERVISED_GUARDED:
            veto_reasons: list[str] = []
            if provider_status != "ok":
                veto_reasons.append("provider_not_ok")
            if llm_route_label and llm_route_label != guard_route:
                veto_reasons.append("guard_disagreement")
            if not llm_route_label:
                veto_reasons.append("missing_llm_route")
            if llm_confidence < LLM_SUPERVISED_MIN_CONFIDENCE:
                veto_reasons.append("confidence_below_threshold")
            accepted = not veto_reasons
            if accepted:
                route_label = llm_route_label
                rationale = (
                    f"LLM supervised route accepted under deterministic guard agreement. {llm_rationale}"
                ).strip()
                confidence = llm_confidence
                planner_mode_effective = PLANNER_MODE_LLM_SUPERVISED_GUARDED
            else:
                route_label = guard_route
                rationale = (
                    "LLM supervised route vetoed; deterministic guard provided the route. "
                    f"Reasons: {', '.join(veto_reasons)}."
                )
                confidence = llm_confidence if provider_status == "ok" else 0.0
                planner_mode_effective = "deterministic_fallback"
            llm_supervised_guard = {
                "mode": PLANNER_MODE_LLM_SUPERVISED_GUARDED,
                "accepted": bool(accepted),
                "decision": "accepted" if accepted else "vetoed",
                "veto_reasons": veto_reasons,
                "confidence_threshold": LLM_SUPERVISED_MIN_CONFIDENCE,
                "llm_route_label": llm_route_label,
                "guard_route_label": guard_route,
                "llm_confidence": round(float(llm_confidence), 6),
                "provider_status": provider_status,
            }

    route_admissibility = route_admissibility_for_scene(scene, route_label)
    if bool(route_admissibility.get("changed", False)):
        route_label = str(route_admissibility.get("route_label", route_label) or route_label)
        rationale = (
            f"{rationale} Deterministic route admissibility changed execution to {route_label}: "
            f"{route_admissibility.get('reason', '')}."
        )

    fetch_dispatch = route_label == ROUTE_FETCH_READY
    correct = bool(route_label == expected_route)
    wrong_fetch_dispatch = bool(fetch_dispatch and expected_route != ROUTE_FETCH_READY)
    route_executor = executor_for_route(route_label)
    route_quality = score_route_quality(scene, route_label)
    maneuver_plan = compile_maneuver_plan(
        scene,
        route_label,
        proposed=llm_plan if llm_plan else None,
    )
    return {
        "scene_id": str(scene.get("scene_id", "") or ""),
        "planner_mode": planner_mode,
        "planner_mode_effective": planner_mode_effective,
        "expected_route_label": expected_route,
        "route_label": route_label,
        "route_executor": route_executor,
        "route_executable": bool(route_executor != "unsupported_route"),
        "guard_route_label": guard_route,
        "guard_agrees": bool(route_label == guard_route),
        "correct": correct,
        "should_dispatch_fetch_to_pose": bool(fetch_dispatch),
        "local_fetch_evidence_allowed": bool(fetch_dispatch and expected_route == ROUTE_FETCH_READY),
        "wrong_fetch_ready_dispatch": wrong_fetch_dispatch,
        "rationale_short": rationale,
        "confidence": round(float(confidence), 6),
        "route_quality": route_quality,
        "maneuver_plan": maneuver_plan,
        "route_admissibility": route_admissibility,
        "llm_supervised_guard": llm_supervised_guard,
        "llm_route_label": llm_route_label,
        "llm_rationale_short": llm_rationale,
        "llm_confidence": round(float(llm_confidence), 6),
        "provider_status": provider_status,
        "provider_error": provider_error,
        "provider_attempts": provider_attempts,
        "provider_request": provider_request,
        "provider_response": provider_response,
        "no_direct_cmd_vel": True,
    }


def write_fetch_ready_layout_from_scene(
    path: Path,
    scene: dict[str, Any],
    *,
    scenario_id: str = "golf_ball_circle_delivery_uat",
    route_label: str = "",
    route_executor: str = "",
) -> None:
    ball_pose = scene.get("ball_pose") if isinstance(scene.get("ball_pose"), dict) else {}
    clean_route_label = str(route_label or scene.get("expected_route_label", "") or ROUTE_FETCH_READY).strip()
    clean_route_executor = str(route_executor or executor_for_route(clean_route_label)).strip()
    route_quality = score_route_quality(scene, clean_route_label)
    maneuver_plan = compile_maneuver_plan(scene, clean_route_label)
    random_profile = random_profile_for_scene(scene)
    layout_family = (
        "planner_gated_fetch_ready"
        if clean_route_label == ROUTE_FETCH_READY
        else f"planner_gated_{clean_route_label}"
    )
    write_json(
        path,
        {
            "generated_utc": utc_now(),
            "scenario_id": scenario_id,
            "layout_family": layout_family,
            "random_profile": random_profile,
            "planner_route_label": clean_route_label,
            "route_executor": clean_route_executor,
            "route_quality": route_quality,
            "maneuver_plan": maneuver_plan,
            "planner_scene": scene,
            "random_draw": {
                "random_profile": random_profile,
                "seed": scene.get("seed", ""),
                "scene_set": scene.get("scene_set", ""),
                "planner_route_label": clean_route_label,
                "route_executor": clean_route_executor,
                "route_quality": route_quality,
                "maneuver_plan": maneuver_plan,
                "target_pose": scene.get("target_pose", {}),
                "ball_pose": scene.get("ball_pose", {}),
                "robot_pose": scene.get("robot_pose", {}),
                **(scene.get("geometry", {}) if isinstance(scene.get("geometry"), dict) else {}),
            },
            "targets": [
                {
                    "id": "ball_1",
                    "label": "planner_gated_ball",
                    "start_visible": True,
                    "forward_m": float(ball_pose.get("x", 0.0) or 0.0),
                    "lateral_m": float(ball_pose.get("y", 0.0) or 0.0),
                    "z_m": float(ball_pose.get("z", 0.021336) or 0.021336),
                    "visit_tolerance_m": 0.22,
                    "min_dwell_s": 0.5,
                }
            ],
        },
    )


def write_scene_bundle(root: Path, scene: dict[str, Any], decision: dict[str, Any]) -> dict[str, str]:
    scene_id = str(scene.get("scene_id", "scene") or "scene")
    scene_path = ensure_dir(root / "scene_descriptors") / f"{scene_id}.json"
    decision_path = ensure_dir(root / "decisions") / f"{scene_id}.json"
    request_path = ensure_dir(root / "provider_requests") / f"{scene_id}.json"
    response_path = ensure_dir(root / "provider_responses") / f"{scene_id}.json"
    write_json(scene_path, scene)
    write_json(decision_path, decision)
    write_json(request_path, decision.get("provider_request", {}) if isinstance(decision.get("provider_request"), dict) else {})
    write_json(response_path, decision.get("provider_response", {}) if isinstance(decision.get("provider_response"), dict) else {})
    return {
        "scene_path": str(scene_path),
        "decision_path": str(decision_path),
        "provider_request_path": str(request_path),
        "provider_response_path": str(response_path),
    }


def generate_dashboard_scene(
    *,
    seed: int | None = None,
    scene_set: str = DEFAULT_SCENE_SET,
) -> dict[str, Any]:
    clean_seed = int(seed if seed is not None else (datetime.now(timezone.utc).timestamp() * 1000000))
    scene = generate_random_scenes(seed=clean_seed, random_cases=1, scene_set=scene_set)[0]
    scene["seed"] = clean_seed
    return scene


def summarize_scene_geometry_coverage(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for scene in scenes:
        geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
        rows.append(
            {
                "scene_id": str(scene.get("scene_id", "") or ""),
                "expected_route_label": str(scene.get("expected_route_label", "") or ""),
                "robot_ball_relative_bearing_deg": _finite_float(
                    geometry.get("robot_ball_relative_bearing_deg"),
                    0.0,
                ),
                "robot_ball_relative_bearing_abs_deg": _finite_float(
                    geometry.get("robot_ball_relative_bearing_abs_deg"),
                    0.0,
                ),
                "opposite_side_of_circle": bool(geometry.get("opposite_side_of_circle", False)),
                "ball_target_angle_deg": _finite_float(geometry.get("ball_target_angle_deg"), 0.0),
                "ball_target_distance_m": _finite_float(geometry.get("ball_target_distance_m"), 0.0),
                "robot_ball_distance_m": _finite_float(geometry.get("robot_ball_distance_m"), 0.0),
                "robot_lateral_signed_m": _finite_float(geometry.get("robot_lateral_signed_m"), 0.0),
                "robot_yaw_error_deg": _finite_float(geometry.get("robot_yaw_error_deg"), 0.0),
            }
        )
    behind_count = sum(1 for row in rows if float(row["robot_ball_relative_bearing_abs_deg"]) >= 90.0)
    opposite_count = sum(1 for row in rows if bool(row["opposite_side_of_circle"]))
    executable_count = sum(
        1
        for row in rows
        if str(row["expected_route_label"])
        in {ROUTE_FETCH_READY, ROUTE_NAV2_REPOSITION, ROUTE_RECOVERY_OR_REAIM, ROUTE_LOCAL_SETUP_CAPTURE}
    )
    return {
        "scene_count": len(rows),
        "behind_robot_heading_count": behind_count,
        "opposite_side_of_circle_count": opposite_count,
        "executable_route_count": executable_count,
        "success_bar": {
            "at_least_12_cases": len(rows) >= 12,
            "at_least_6_behind_robot_heading": behind_count >= 6,
            "at_least_3_opposite_side": opposite_count >= 3,
            "at_least_2_executable_candidates": executable_count >= 2,
        },
        "rows": rows,
    }


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = str(args.campaign_id or "").strip() or f"live_fetch_planner_handoff_gate_{current_utc_stamp()}"
    gate_root = _campaign_root(campaign_id)
    ensure_dir(gate_root)
    scene_set = str(args.scene_set or DEFAULT_SCENE_SET)
    scenes = load_frozen_scenes(
        scene_descriptor_json=list(args.scene_descriptor_json or []),
        scene_dir=str(args.scene_dir or ""),
        scene_set=scene_set,
    )
    scene_source = "frozen"
    if not scenes:
        scenes = generate_random_scenes(
            seed=int(args.seed),
            random_cases=max(int(args.random_cases), 1),
            scene_set=scene_set,
        )
        scene_source = "generated"
    results: list[dict[str, Any]] = []
    for scene in scenes:
        scene.setdefault("seed", int(args.seed))
        decision = decide_scene(
            scene,
            planner_mode=str(args.planner_mode),
            openai_api_key=str(args.openai_api_key or ""),
            openai_model=str(args.openai_model or DEFAULT_OPENAI_MODEL),
            openai_base_url=str(args.openai_base_url or DEFAULT_OPENAI_BASE_URL),
            openai_org_id=str(args.openai_org_id or ""),
            openai_project_id=str(args.openai_project_id or ""),
            reasoning_effort=str(args.reasoning_effort or DEFAULT_REASONING_EFFORT),
            timeout_s=float(args.timeout_s),
        )
        paths = write_scene_bundle(gate_root, scene, decision)
        result = {
            **{key: value for key, value in decision.items() if key not in {"provider_request", "provider_response"}},
            "scene_path": paths["scene_path"],
            "decision_path": paths["decision_path"],
            "provider_request_path": paths["provider_request_path"],
            "provider_response_path": paths["provider_response_path"],
        }
        results.append(result)

    pass_count = sum(1 for result in results if bool(result.get("correct", False)))
    fetch_dispatch_count = sum(1 for result in results if bool(result.get("should_dispatch_fetch_to_pose", False)))
    wrong_fetch_dispatch_count = sum(1 for result in results if bool(result.get("wrong_fetch_ready_dispatch", False)))
    guard_agreement_count = sum(1 for result in results if bool(result.get("guard_agrees", False)))
    guard_disagreement_count = len(results) - guard_agreement_count
    llm_supervised_accept_count = sum(
        1
        for result in results
        if isinstance(result.get("llm_supervised_guard"), dict)
        and bool(result["llm_supervised_guard"].get("accepted", False))
    )
    llm_supervised_veto_count = sum(
        1
        for result in results
        if isinstance(result.get("llm_supervised_guard"), dict)
        and str(result["llm_supervised_guard"].get("decision", "") or "") == "vetoed"
    )
    provider_status_counts: dict[str, int] = {}
    planner_mode_effective_counts: dict[str, int] = {}
    for result in results:
        provider_status = str(result.get("provider_status", "") or "missing")
        planner_mode_effective = str(result.get("planner_mode_effective", "") or "missing")
        provider_status_counts[provider_status] = provider_status_counts.get(provider_status, 0) + 1
        planner_mode_effective_counts[planner_mode_effective] = planner_mode_effective_counts.get(planner_mode_effective, 0) + 1
    llm_shadow_provider_ok_count = int(provider_status_counts.get("ok", 0))
    llm_shadow_ready = bool(
        str(args.planner_mode) == PLANNER_MODE_LLM_SHADOW
        and llm_shadow_provider_ok_count == len(results)
        and guard_disagreement_count == 0
        and pass_count == len(results)
        and wrong_fetch_dispatch_count == 0
    )
    llm_supervised_ready = bool(
        str(args.planner_mode) == PLANNER_MODE_LLM_SUPERVISED_GUARDED
        and llm_shadow_provider_ok_count == len(results)
        and llm_supervised_accept_count == len(results)
        and llm_supervised_veto_count == 0
        and guard_disagreement_count == 0
        and pass_count == len(results)
        and wrong_fetch_dispatch_count == 0
    )
    route_counts = {route: sum(1 for result in results if result.get("route_label") == route) for route in ROUTE_LABELS}
    expected_counts = {
        route: sum(1 for result in results if result.get("expected_route_label") == route)
        for route in ROUTE_LABELS
    }
    summary = {
        "generated_utc": utc_now(),
        "type": PLANNER_GATE_KIND,
        "campaign_id": campaign_id,
        "dry_run": bool(args.dry_run),
        "scene_set": scene_set,
        "scene_source": scene_source,
        "seed": int(args.seed),
        "random_cases": len(scenes),
        "planner_mode": str(args.planner_mode),
        "pass": bool(pass_count == len(results) and wrong_fetch_dispatch_count == 0),
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "fetch_dispatch_count": fetch_dispatch_count,
        "wrong_fetch_dispatch_count": wrong_fetch_dispatch_count,
        "guard_agreement_count": guard_agreement_count,
        "guard_disagreement_count": guard_disagreement_count,
        "provider_status_counts": provider_status_counts,
        "planner_mode_effective_counts": planner_mode_effective_counts,
        "llm_shadow_provider_ok_count": llm_shadow_provider_ok_count,
        "llm_shadow_ready": llm_shadow_ready,
        "llm_supervised_accept_count": llm_supervised_accept_count,
        "llm_supervised_veto_count": llm_supervised_veto_count,
        "llm_supervised_ready": llm_supervised_ready,
        "route_counts": route_counts,
        "expected_route_counts": expected_counts,
        "geometry_coverage": summarize_scene_geometry_coverage(scenes),
        "results": results,
    }
    write_json(gate_root / "gate_summary.json", summary)
    write_scorecard(gate_root / "scorecard.md", summary)
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    lines = [
        "# Fetch Planner Handoff Gate",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- scene_set: `{summary.get('scene_set', '')}`",
        f"- scene_source: `{summary.get('scene_source', '')}`",
        f"- planner_mode: `{summary.get('planner_mode', '')}`",
        f"- seed: `{summary.get('seed', '')}`",
        f"- pass: `{bool(summary.get('pass', False))}`",
        f"- route pass/fail: `{summary.get('pass_count', 0)}/{summary.get('fail_count', 0)}`",
        f"- fetch dispatch count: `{summary.get('fetch_dispatch_count', 0)}`",
        f"- wrong fetch-ready dispatches: `{summary.get('wrong_fetch_dispatch_count', 0)}`",
        f"- guard agreement: `{summary.get('guard_agreement_count', 0)}/{summary.get('random_cases', 0)}`",
        f"- provider status counts: `{summary.get('provider_status_counts', {})}`",
        f"- effective planner modes: `{summary.get('planner_mode_effective_counts', {})}`",
        f"- llm_shadow_ready: `{summary.get('llm_shadow_ready', False)}`",
        f"- llm_supervised accepted/vetoed: `{summary.get('llm_supervised_accept_count', 0)}/{summary.get('llm_supervised_veto_count', 0)}`",
        f"- llm_supervised_ready: `{summary.get('llm_supervised_ready', False)}`",
        "",
        "## Routes",
        "",
    ]
    for route in ROUTE_LABELS:
        route_counts = summary.get("route_counts", {}) if isinstance(summary.get("route_counts"), dict) else {}
        expected_counts = summary.get("expected_route_counts", {}) if isinstance(summary.get("expected_route_counts"), dict) else {}
        lines.append(f"- `{route}` expected=`{expected_counts.get(route, 0)}` chosen=`{route_counts.get(route, 0)}`")
    coverage = summary.get("geometry_coverage", {}) if isinstance(summary.get("geometry_coverage"), dict) else {}
    success_bar = coverage.get("success_bar", {}) if isinstance(coverage.get("success_bar"), dict) else {}
    lines.extend(
        [
            "",
            "## Geometry Coverage",
            "",
            f"- scene_count: `{coverage.get('scene_count', 0)}`",
            f"- behind_robot_heading_count: `{coverage.get('behind_robot_heading_count', 0)}`",
            f"- opposite_side_of_circle_count: `{coverage.get('opposite_side_of_circle_count', 0)}`",
            f"- executable_route_count: `{coverage.get('executable_route_count', 0)}`",
            f"- success_bar: `{success_bar}`",
            "",
            "| scene | route | rel bearing deg | opposite side | ball angle deg | ball dist m | robot-ball m | yaw err deg |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in list(coverage.get("rows", [])):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| `{row.get('scene_id', '')}` | `{row.get('expected_route_label', '')}` | "
            f"`{float(row.get('robot_ball_relative_bearing_deg', 0.0)):.1f}` | "
            f"`{bool(row.get('opposite_side_of_circle', False))}` | "
            f"`{float(row.get('ball_target_angle_deg', 0.0)):.1f}` | "
            f"`{float(row.get('ball_target_distance_m', 0.0)):.3f}` | "
            f"`{float(row.get('robot_ball_distance_m', 0.0)):.3f}` | "
            f"`{float(row.get('robot_yaw_error_deg', 0.0)):.1f}` |"
        )
    lines.extend(["", "## Cases", ""])
    for result in list(summary.get("results", [])):
        if not isinstance(result, dict):
            continue
        lines.append(
            f"- `{result.get('scene_id', '')}` expected=`{result.get('expected_route_label', '')}` "
            f"route=`{result.get('route_label', '')}` correct=`{bool(result.get('correct', False))}` "
            f"dispatch_fetch=`{bool(result.get('should_dispatch_fetch_to_pose', False))}` "
            f"guard=`{result.get('guard_route_label', '')}` provider=`{result.get('provider_status', '')}`"
        )
        plan = result.get("maneuver_plan") if isinstance(result.get("maneuver_plan"), dict) else {}
        if plan:
            lines.append(
                f"  - plan=`{' -> '.join(str(item) for item in list(plan.get('maneuver_sequence', [])))}` "
                f"push_ready_before_fetch=`{bool(plan.get('requires_measured_push_ready_before_fetch', False))}` "
                f"source=`{plan.get('source', '')}`"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    summary = run_gate(args)
    summary_path = _campaign_root(str(summary.get("campaign_id", ""))) / "gate_summary.json"
    print(f"FETCH_PLANNER_HANDOFF_GATE_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    sys.exit(main())
