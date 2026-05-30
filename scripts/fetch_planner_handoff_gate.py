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
FETCH_TARGET_POSE = {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.30}
PLANNER_GATE_KIND = "fetch_planner_handoff_gate"
PLANNER_MIXED_PROFILE = "planner_mixed_v1"
OPENAI_TOOL_NAME = "emit_fetch_planner_route"


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run planner-gated fetch handoff scoring.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scene-set", default=DEFAULT_SCENE_SET)
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


def _round_pose(x: float, y: float, yaw: float = 0.0, z: float = 0.0) -> dict[str, float]:
    return {
        "x": round(float(x), 6),
        "y": round(float(y), 6),
        "z": round(float(z), 6),
        "yaw": round(float(yaw), 6),
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
        and abs(lateral_m) <= 0.12
        and abs(yaw_error_deg) <= 18.0
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
        0.34 <= float(geometry.get("ball_target_distance_m", 999.0) or 999.0) <= 0.85
        and 0.24 <= float(geometry.get("robot_ball_distance_m", 999.0) or 999.0) <= 0.52
        and float(geometry.get("robot_lateral_error_m", 999.0) or 999.0) <= 0.12
        and abs(float(geometry.get("robot_yaw_error_deg", 999.0) or 999.0)) <= 18.0
        and not bool(corridor.get("blocked", False))
        and float(corridor.get("clearance_m", 0.0) or 0.0) >= 0.12
        and float(perception.get("ball_confidence", 0.0) or 0.0) >= 0.65
        and float(perception.get("target_confidence", 0.0) or 0.0) >= 0.65
        and float(perception.get("state_age_s", 999.0) or 999.0) <= 2.0
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
                lateral_range=(-0.08, 0.08),
                yaw_error_range_deg=(-12.0, 12.0),
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
            if float(geometry["robot_lateral_error_m"]) <= 0.12 and abs(float(geometry["robot_yaw_error_deg"])) <= 18.0:
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


def deterministic_route_label(scene: dict[str, Any]) -> str:
    perception = scene.get("perception") if isinstance(scene.get("perception"), dict) else {}
    corridor = scene.get("corridor") if isinstance(scene.get("corridor"), dict) else {}
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    ball_conf = float(perception.get("ball_confidence", 0.0) or 0.0)
    target_conf = float(perception.get("target_confidence", 0.0) or 0.0)
    state_age_s = float(perception.get("state_age_s", 999.0) or 999.0)
    blocked = bool(corridor.get("blocked", False))
    clearance_m = float(corridor.get("clearance_m", 0.0) or 0.0)
    unsafe_drift_m = float(corridor.get("unsafe_drift_m", 0.0) or 0.0)
    ball_target_distance_m = float(geometry.get("ball_target_distance_m", 999.0) or 999.0)
    robot_ball_distance_m = float(geometry.get("robot_ball_distance_m", 999.0) or 999.0)
    lateral_error_m = float(geometry.get("robot_lateral_error_m", 999.0) or 999.0)
    yaw_error_deg = abs(float(geometry.get("robot_yaw_error_deg", 999.0) or 999.0))

    if ball_conf < 0.65 or target_conf < 0.65 or state_age_s > 2.0:
        return ROUTE_SCAN_OR_PERCEIVE
    if blocked or clearance_m < 0.12 or unsafe_drift_m > 0.16 or ball_target_distance_m > 1.20:
        return ROUTE_NO_GO
    if not (0.34 <= ball_target_distance_m <= 0.85):
        return ROUTE_NO_GO
    if 0.24 <= robot_ball_distance_m <= 0.52 and lateral_error_m <= 0.12 and yaw_error_deg <= 18.0:
        return ROUTE_FETCH_READY
    if robot_ball_distance_m <= 0.70 and lateral_error_m <= 0.24 and yaw_error_deg <= 35.0:
        return ROUTE_RECOVERY_OR_REAIM
    return ROUTE_NAV2_REPOSITION


def planner_prompt(scene: dict[str, Any]) -> str:
    return (
        "Classify this robot fetch scene before any local fetch execution.\n"
        "Return exactly one route label. Only fetch_ready_local may dispatch local fetch_to_pose.\n"
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
    return {
        "scene_id": str(scene.get("scene_id", "") or ""),
        "planner_mode": planner_mode,
        "planner_mode_effective": planner_mode_effective,
        "expected_route_label": expected_route,
        "route_label": route_label,
        "guard_route_label": guard_route,
        "guard_agrees": bool(route_label == guard_route),
        "correct": correct,
        "should_dispatch_fetch_to_pose": bool(fetch_dispatch),
        "local_fetch_evidence_allowed": bool(fetch_dispatch and expected_route == ROUTE_FETCH_READY),
        "wrong_fetch_ready_dispatch": wrong_fetch_dispatch,
        "rationale_short": rationale,
        "confidence": round(float(confidence), 6),
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
) -> None:
    ball_pose = scene.get("ball_pose") if isinstance(scene.get("ball_pose"), dict) else {}
    write_json(
        path,
        {
            "generated_utc": utc_now(),
            "scenario_id": scenario_id,
            "layout_family": "planner_gated_fetch_ready",
            "random_profile": PLANNER_MIXED_PROFILE,
            "planner_scene": scene,
            "random_draw": {
                "random_profile": PLANNER_MIXED_PROFILE,
                "seed": scene.get("seed", ""),
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
    scenes = generate_random_scenes(
        seed=int(args.seed),
        random_cases=max(int(args.random_cases), 1),
        scene_set=str(args.scene_set or DEFAULT_SCENE_SET),
    )
    results: list[dict[str, Any]] = []
    for scene in scenes:
        scene["seed"] = int(args.seed)
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
        "scene_set": str(args.scene_set or DEFAULT_SCENE_SET),
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
