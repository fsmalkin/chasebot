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


DEFAULT_SCENE_SET = "mixed_fetch_planner_v1"
DEFAULT_RANDOM_CASES = 20
DEFAULT_SEED = 20260530
PLANNER_MODE_DETERMINISTIC = "deterministic"
PLANNER_MODE_LLM_SHADOW = "llm_shadow"
ROUTE_FETCH_READY = "fetch_ready_local"
ROUTE_NAV2_REPOSITION = "nav2_reposition_first"
ROUTE_SCAN_OR_PERCEIVE = "scan_or_perceive_first"
ROUTE_RECOVERY_OR_REAIM = "recovery_or_reaim"
ROUTE_NO_GO = "ambiguous_or_unsafe_no_go"
ROUTE_LABELS = (
    ROUTE_FETCH_READY,
    ROUTE_NAV2_REPOSITION,
    ROUTE_SCAN_OR_PERCEIVE,
    ROUTE_RECOVERY_OR_REAIM,
    ROUTE_NO_GO,
)
ROUTE_EXECUTOR_LOCAL_FETCH = "local_fetch_to_pose"
ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH = "nav2_forward_reposition_then_fetch"
ROUTE_EXECUTOR_SCAN = "scan_or_perception_refresh"
ROUTE_EXECUTOR_RECOVERY = "bounded_recovery_reaim"
ROUTE_EXECUTOR_NO_GO = "safe_no_go"
ROUTE_EXECUTORS = {
    ROUTE_FETCH_READY: ROUTE_EXECUTOR_LOCAL_FETCH,
    ROUTE_NAV2_REPOSITION: ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH,
    ROUTE_SCAN_OR_PERCEIVE: ROUTE_EXECUTOR_SCAN,
    ROUTE_RECOVERY_OR_REAIM: ROUTE_EXECUTOR_RECOVERY,
    ROUTE_NO_GO: ROUTE_EXECUTOR_NO_GO,
}
FETCH_TARGET_POSE = {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.30}
PLANNER_GATE_KIND = "fetch_planner_handoff_gate"
PLANNER_MIXED_PROFILE = "planner_mixed_v1"
OPENAI_TOOL_NAME = "emit_fetch_planner_route"
CONTACT_QUALITY_CLEAN_LATERAL_M = 0.030
CONTACT_QUALITY_CLEAN_YAW_DEG = 3.0
FETCH_READY_LATERAL_LIMIT_M = 0.050
FETCH_READY_YAW_LIMIT_DEG = 6.0
RECOVERY_LATERAL_LIMIT_M = 0.240
RECOVERY_YAW_LIMIT_DEG = 35.0
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
        choices=(PLANNER_MODE_DETERMINISTIC, PLANNER_MODE_LLM_SHADOW),
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


def _quality_ratio(value: float, clean: float, limit: float) -> float:
    clean = max(float(clean), 0.0)
    limit = max(float(limit), clean + 1.0e-9)
    excess = max(abs(float(value)) - clean, 0.0)
    return max(0.0, min(1.0, excess / (limit - clean)))


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
    return {
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
                standoff_range=(0.80, 1.25),
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
                standoff_range=(0.28, 0.48),
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
        _refresh_local_fetch_envelope(scene)
        scenes.append(scene)
    return scenes


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
    if robot_ball_distance_m <= 0.70 and lateral_error_m <= 0.24 and yaw_error_deg <= 35.0:
        return ROUTE_RECOVERY_OR_REAIM
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
        lateral_ratio = _quality_ratio(lateral_m, FETCH_READY_LATERAL_LIMIT_M, RECOVERY_LATERAL_LIMIT_M)
        yaw_ratio = _quality_ratio(yaw_deg, FETCH_READY_YAW_LIMIT_DEG, RECOVERY_YAW_LIMIT_DEG)
        standoff_ratio = _quality_ratio(robot_ball_m, 0.52, 0.70)
        severity = max(lateral_ratio, yaw_ratio, standoff_ratio)
        flags.append("bounded_recovery_required")
        if lateral_m > CONTACT_QUALITY_CLEAN_LATERAL_M:
            flags.append("initial_lateral_setup_debt")
        if yaw_deg > CONTACT_QUALITY_CLEAN_YAW_DEG:
            flags.append("initial_yaw_setup_debt")
        if lateral_m > RECOVERY_LATERAL_LIMIT_M or yaw_deg > RECOVERY_YAW_LIMIT_DEG or robot_ball_m > 0.70:
            flags.append("outside_recovery_envelope")
            status = "blocker"
            risk = "high"
        else:
            status = "watch"
            risk = "high" if severity >= 0.65 else "medium"
        recommendations.extend(["bounded_reaim_before_push", "pre_contact_smoothing"])
        score = 78.0 - 38.0 * severity
    elif route == ROUTE_NAV2_REPOSITION:
        standoff_ratio = _quality_ratio(robot_ball_m, 0.70, NAV2_REPOSITION_STANDOFF_LIMIT_M)
        angle_ratio = _quality_ratio(ball_target_angle_deg, 20.0, 45.0)
        severity = max(standoff_ratio, angle_ratio)
        flags.append("nav2_reposition_required")
        if robot_ball_m > NAV2_REPOSITION_STANDOFF_LIMIT_M:
            flags.append("nav2_setup_distance_watch")
        status = "watch"
        risk = "medium" if severity >= 0.55 else "low"
        recommendations.extend(["nav2_forward_reposition", "verify_setup_pose_before_push"])
        score = 84.0 - 28.0 * severity
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
        },
    }


def executor_for_route(route_label: str) -> str:
    return str(ROUTE_EXECUTORS.get(str(route_label or "").strip(), "unsupported_route"))


def planner_prompt(scene: dict[str, Any]) -> str:
    return (
        "Classify this robot fetch scene before any local fetch execution.\n"
        "Return exactly one route label. fetch_ready_local may dispatch local fetch_to_pose immediately; "
        "nav2_reposition_first must route through a bounded reposition executor first.\n"
        f"Allowed labels: {json.dumps(list(ROUTE_LABELS))}\n\n"
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
            "You are a high-level robot planner. Use exactly one function tool. "
            "Classify whether local fetch is applicable or another bounded route is required. "
            "Never emit velocity commands and never bypass deterministic guards."
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
                    "required": ["route_label", "rationale_short", "confidence"],
                    "properties": {
                        "route_label": {"type": "string", "enum": list(ROUTE_LABELS)},
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
    route_label = guard_route
    rationale = "Deterministic guard classified the scene."
    confidence = 1.0
    planner_mode_effective = PLANNER_MODE_DETERMINISTIC

    if planner_mode == PLANNER_MODE_LLM_SHADOW:
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
                route_label = route["route_label"]
                rationale = route["rationale_short"]
                confidence = float(route["confidence"])
                provider_status = "ok"
                planner_mode_effective = PLANNER_MODE_LLM_SHADOW
            except Exception as exc:
                provider_status = "error"
                provider_error = str(exc)
                planner_mode_effective = "deterministic_fallback"
                rationale = "LLM shadow failed validation; deterministic guard provided the route."
                confidence = 0.0

    fetch_dispatch = route_label == ROUTE_FETCH_READY
    correct = bool(route_label == expected_route)
    wrong_fetch_dispatch = bool(fetch_dispatch and expected_route != ROUTE_FETCH_READY)
    route_executor = executor_for_route(route_label)
    route_quality = score_route_quality(scene, route_label)
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
        "provider_status": provider_status,
        "provider_error": provider_error,
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
            "random_profile": PLANNER_MIXED_PROFILE,
            "planner_route_label": clean_route_label,
            "route_executor": clean_route_executor,
            "route_quality": route_quality,
            "planner_scene": scene,
            "random_draw": {
                "random_profile": PLANNER_MIXED_PROFILE,
                "seed": scene.get("seed", ""),
                "planner_route_label": clean_route_label,
                "route_executor": clean_route_executor,
                "route_quality": route_quality,
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
        "route_counts": route_counts,
        "expected_route_counts": expected_counts,
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
        "",
        "## Routes",
        "",
    ]
    for route in ROUTE_LABELS:
        route_counts = summary.get("route_counts", {}) if isinstance(summary.get("route_counts"), dict) else {}
        expected_counts = summary.get("expected_route_counts", {}) if isinstance(summary.get("expected_route_counts"), dict) else {}
        lines.append(f"- `{route}` expected=`{expected_counts.get(route, 0)}` chosen=`{route_counts.get(route, 0)}`")
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    summary = run_gate(args)
    summary_path = _campaign_root(str(summary.get("campaign_id", ""))) / "gate_summary.json"
    print(f"FETCH_PLANNER_HANDOFF_GATE_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    sys.exit(main())
