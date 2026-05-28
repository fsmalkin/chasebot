#!/usr/bin/env python3
"""Seeded generalized last-meter fetch gate."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import calibrated_golf_fetch_gate as fetch_gate
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
DEFAULT_ARCHITECTURES = ("object_centric_gather_policy_v1", "contact_aware_geometric_shooter")
DEFAULT_RANDOM_CASE_COUNT = 6
DEFAULT_ROBOT_START = {"x": 0.0, "y": 0.0, "yaw": 0.0}
DEFAULT_FETCH_POSE = {
    "x": float(fetch_gate.DEFAULT_FETCH_TARGET["x"]),
    "y": float(fetch_gate.DEFAULT_FETCH_TARGET["y"]),
    "z": float(fetch_gate.DEFAULT_FETCH_TARGET["z"]),
    "radius_m": float(fetch_gate.DEFAULT_FETCH_TARGET["radius_m"]),
}
SAVED_LAYOUTS = {
    "zero": fetch_gate.DEFAULT_CENTERLINE_LAYOUT,
    "left05": fetch_gate.OFF_AXIS_LAYOUTS["left05"],
    "right05": fetch_gate.OFF_AXIS_LAYOUTS["right05"],
}
REQUIRED_GENERALIZATION_TAGS = (
    "target_relative_side",
    "robot_yaw",
    "lateral_offset",
    "ball_target_distance",
    "farther_start",
    "opposite_side_start",
)
ROBOT_OWNED_ARCHITECTURES = {"object_centric_gather_policy_v1"}


@dataclass(frozen=True)
class FetchCase:
    case_id: str
    source: str
    seed: int | None
    coverage_tags: tuple[str, ...]
    robot_start_pose: dict[str, float]
    ball_pose_world: dict[str, float]
    fetch_pose_world: dict[str, float]
    layout_path: Path
    geometry: dict[str, Any]


@dataclass(frozen=True)
class ArchitectureSpec:
    architecture: str
    case: FetchCase
    campaign_id: str
    command: list[str]
    summary_path: Path
    log_path: Path
    robot_owned_contact: bool


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _finite_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round6(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def normalize_angle_rad(angle_rad: float) -> float:
    return math.atan2(math.sin(float(angle_rad)), math.cos(float(angle_rad)))


def _load_first_layout_target(path: Path) -> dict[str, float]:
    payload = read_json(path)
    targets = payload.get("targets", []) if isinstance(payload, dict) else []
    if not isinstance(targets, list) or not targets or not isinstance(targets[0], dict):
        raise ValueError(f"target layout has no first target: {path}")
    first = targets[0]
    return {
        "forward_m": float(first.get("forward_m", 0.0) or 0.0),
        "lateral_m": float(first.get("lateral_m", 0.0) or 0.0),
        "z_m": float(first.get("z_m", 0.021336) or 0.021336),
    }


def world_from_robot_relative(robot_pose: dict[str, float], *, forward_m: float, lateral_m: float, z_m: float) -> dict[str, float]:
    yaw = float(robot_pose["yaw"])
    x = float(robot_pose["x"]) + (math.cos(yaw) * float(forward_m)) - (math.sin(yaw) * float(lateral_m))
    y = float(robot_pose["y"]) + (math.sin(yaw) * float(forward_m)) + (math.cos(yaw) * float(lateral_m))
    return {"x": round(x, 6), "y": round(y, 6), "z": round(float(z_m), 6)}


def robot_relative_from_world(robot_pose: dict[str, float], world_pose: dict[str, float]) -> dict[str, float]:
    yaw = float(robot_pose["yaw"])
    dx = float(world_pose["x"]) - float(robot_pose["x"])
    dy = float(world_pose["y"]) - float(robot_pose["y"])
    forward = (math.cos(yaw) * dx) + (math.sin(yaw) * dy)
    lateral = (-math.sin(yaw) * dx) + (math.cos(yaw) * dy)
    return {"forward_m": round(forward, 6), "lateral_m": round(lateral, 6)}


def _case_geometry(
    *,
    robot_start_pose: dict[str, float],
    ball_pose_world: dict[str, float],
    fetch_pose_world: dict[str, float],
) -> dict[str, Any]:
    ball_to_target_x = float(fetch_pose_world["x"]) - float(ball_pose_world["x"])
    ball_to_target_y = float(fetch_pose_world["y"]) - float(ball_pose_world["y"])
    ball_target_distance = math.hypot(ball_to_target_x, ball_to_target_y)
    line_yaw = math.atan2(ball_to_target_y, ball_to_target_x) if ball_target_distance > 1.0e-9 else 0.0
    robot_from_ball_x = float(robot_start_pose["x"]) - float(ball_pose_world["x"])
    robot_from_ball_y = float(robot_start_pose["y"]) - float(ball_pose_world["y"])
    robot_ball_distance = math.hypot(robot_from_ball_x, robot_from_ball_y)
    lateral_signed = (-math.sin(line_yaw) * robot_from_ball_x) + (math.cos(line_yaw) * robot_from_ball_y)
    yaw_error = normalize_angle_rad(float(robot_start_pose["yaw"]) - line_yaw)
    robot_target_x = float(robot_start_pose["x"]) - float(fetch_pose_world["x"])
    robot_target_y = float(robot_start_pose["y"]) - float(fetch_pose_world["y"])
    ball_target_x = float(ball_pose_world["x"]) - float(fetch_pose_world["x"])
    ball_target_y = float(ball_pose_world["y"]) - float(fetch_pose_world["y"])
    target_side_dot = (robot_target_x * ball_target_x) + (robot_target_y * ball_target_y)
    return {
        "ball_to_target_distance_m": round(ball_target_distance, 6),
        "robot_to_ball_distance_m": round(robot_ball_distance, 6),
        "robot_lateral_to_ball_target_line_m": round(lateral_signed, 6),
        "robot_abs_lateral_to_ball_target_line_m": round(abs(lateral_signed), 6),
        "robot_yaw_error_to_push_line_deg": round(math.degrees(yaw_error), 6),
        "target_relative_side": "same_side" if target_side_dot >= 0.0 else "opposite_side",
        "push_line_yaw_deg": round(math.degrees(line_yaw), 6),
    }


def _write_case_layout(case_dir: Path, *, case_id: str, robot_start_pose: dict[str, float], ball_pose_world: dict[str, float], metadata: dict[str, Any]) -> Path:
    relative = robot_relative_from_world(robot_start_pose, ball_pose_world)
    path = case_dir / f"{case_id}.json"
    payload = {
        "metadata": metadata,
        "targets": [
            {
                "id": "ball_1",
                "forward_m": relative["forward_m"],
                "lateral_m": relative["lateral_m"],
                "visit_tolerance_m": 0.22,
                "min_dwell_s": 0.5,
                "start_visible": True,
                "label": f"Generalized fetch {case_id}",
                "z_m": round(float(ball_pose_world.get("z", 0.021336) or 0.021336), 6),
            }
        ],
    }
    write_json(path, payload)
    return path


def _make_case(
    case_dir: Path,
    *,
    case_id: str,
    source: str,
    seed: int | None,
    coverage_tags: tuple[str, ...],
    robot_start_pose: dict[str, float],
    ball_pose_world: dict[str, float],
    fetch_pose_world: dict[str, float],
) -> FetchCase:
    geometry = _case_geometry(
        robot_start_pose=robot_start_pose,
        ball_pose_world=ball_pose_world,
        fetch_pose_world=fetch_pose_world,
    )
    metadata = {
        "case_id": case_id,
        "source": source,
        "seed": seed,
        "coverage_tags": list(coverage_tags),
        "robot_start_pose": {key: _round6(value) for key, value in robot_start_pose.items()},
        "ball_pose_world": {key: _round6(value) for key, value in ball_pose_world.items()},
        "fetch_pose_world": {key: _round6(value) for key, value in fetch_pose_world.items()},
        "geometry": geometry,
    }
    layout_path = _write_case_layout(
        case_dir,
        case_id=case_id,
        robot_start_pose=robot_start_pose,
        ball_pose_world=ball_pose_world,
        metadata=metadata,
    )
    return FetchCase(
        case_id=case_id,
        source=source,
        seed=seed,
        coverage_tags=coverage_tags,
        robot_start_pose=robot_start_pose,
        ball_pose_world=ball_pose_world,
        fetch_pose_world=fetch_pose_world,
        layout_path=layout_path,
        geometry=geometry,
    )


def build_saved_anchor_cases(case_dir: Path) -> list[FetchCase]:
    cases: list[FetchCase] = []
    for layout_id, raw_path in SAVED_LAYOUTS.items():
        source_path = REPO_ROOT / raw_path
        target = _load_first_layout_target(source_path)
        robot_start = dict(DEFAULT_ROBOT_START)
        ball_pose = world_from_robot_relative(
            robot_start,
            forward_m=float(target["forward_m"]),
            lateral_m=float(target["lateral_m"]),
            z_m=float(target["z_m"]),
        )
        lateral_tag = ("lateral_offset",) if abs(float(target["lateral_m"])) > 0.001 else ()
        cases.append(
            _make_case(
                case_dir,
                case_id=f"saved_{layout_id}",
                source="saved_anchor",
                seed=None,
                coverage_tags=("saved_anchor", "ball_target_distance", *lateral_tag),
                robot_start_pose=robot_start,
                ball_pose_world=ball_pose,
                fetch_pose_world=dict(DEFAULT_FETCH_POSE),
            )
        )
    return cases


def _parametric_case(seed: int, index: int, *, variant: str) -> tuple[dict[str, float], dict[str, float], dict[str, float], tuple[str, ...]]:
    rng = __import__("random").Random(seed)
    fetch_pose = {
        "x": round(0.82 + rng.uniform(-0.20, 0.12), 6),
        "y": round(rng.uniform(-0.16, 0.16), 6),
        "z": 0.001,
        "radius_m": DEFAULT_FETCH_POSE["radius_m"],
    }
    line_yaw = rng.uniform(-0.65, 0.65)
    if variant == "target_distance":
        ball_target_distance = rng.choice([0.34, 0.92])
    elif variant == "farther_start":
        ball_target_distance = rng.uniform(0.70, 0.95)
    else:
        ball_target_distance = rng.uniform(0.42, 0.78)
    ux = math.cos(line_yaw)
    uy = math.sin(line_yaw)
    px = -uy
    py = ux
    ball_pose = {
        "x": round(float(fetch_pose["x"]) - (ux * ball_target_distance), 6),
        "y": round(float(fetch_pose["y"]) - (uy * ball_target_distance), 6),
        "z": 0.021336,
    }
    lateral = rng.uniform(-0.09, 0.09)
    gap = rng.uniform(0.18, 0.38)
    yaw_error = rng.uniform(-0.35, 0.35)
    tags: list[str] = ["target_relative_side", "ball_target_distance"]
    if variant == "opposite_side_start":
        robot_x = float(fetch_pose["x"]) + (ux * rng.uniform(0.18, 0.36)) + (px * lateral)
        robot_y = float(fetch_pose["y"]) + (uy * rng.uniform(0.18, 0.36)) + (py * lateral)
        yaw_error = rng.uniform(1.8, 2.7)
        tags.extend(["opposite_side_start", "robot_yaw"])
    else:
        if variant == "farther_start":
            gap = rng.uniform(0.65, 0.95)
            tags.append("farther_start")
        if variant == "robot_yaw":
            yaw_error = rng.choice([-1.0, 1.0]) * rng.uniform(0.85, 1.45)
            tags.append("robot_yaw")
        if variant == "lateral_offset":
            lateral = rng.choice([-1.0, 1.0]) * rng.uniform(0.22, 0.36)
            tags.append("lateral_offset")
        robot_x = float(ball_pose["x"]) - (ux * gap) + (px * lateral)
        robot_y = float(ball_pose["y"]) - (uy * gap) + (py * lateral)
    if abs(lateral) >= 0.12 and "lateral_offset" not in tags:
        tags.append("lateral_offset")
    if abs(yaw_error) >= 0.75 and "robot_yaw" not in tags:
        tags.append("robot_yaw")
    robot_start = {
        "x": round(robot_x, 6),
        "y": round(robot_y, 6),
        "yaw": round(normalize_angle_rad(line_yaw + yaw_error), 6),
    }
    if index % 2 == 1 and "target_relative_side" not in tags:
        tags.append("target_relative_side")
    return robot_start, ball_pose, fetch_pose, tuple(dict.fromkeys(tags))


def build_seeded_random_cases(case_dir: Path, *, seed: int, count: int) -> list[FetchCase]:
    variants = (
        "opposite_side_start",
        "farther_start",
        "robot_yaw",
        "lateral_offset",
        "target_distance",
        "mixed",
    )
    cases: list[FetchCase] = []
    for index in range(max(int(count), 0)):
        variant = variants[index % len(variants)]
        case_seed = int(seed) + index
        robot_start, ball_pose, fetch_pose, tags = _parametric_case(case_seed, index, variant=variant)
        cases.append(
            _make_case(
                case_dir,
                case_id=f"seed{seed}_case{index + 1:02d}_{variant}",
                source="seeded_random",
                seed=case_seed,
                coverage_tags=tags,
                robot_start_pose=robot_start,
                ball_pose_world=ball_pose,
                fetch_pose_world=fetch_pose,
            )
        )
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run seeded generalized last-meter fetch gates.")
    parser.add_argument("--dashboard-url", default=fetch_gate.DEFAULT_DASHBOARD_URL)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--seed", type=int, default=20260528)
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASE_COUNT)
    parser.add_argument("--include-saved-anchors", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--architecture", action="append", choices=DEFAULT_ARCHITECTURES, default=[])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--provider", default="local_stub")
    parser.add_argument("--world-file", default=fetch_gate.DEFAULT_WORLD_FILE)
    parser.add_argument("--surface-profile", default=fetch_gate.DEFAULT_SURFACE_PROFILE)
    parser.add_argument("--scenario-timeout-s", type=float, default=240.0)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--output-root", type=Path, default=SESSION_ROOT)
    return parser.parse_args()


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _summary_path(campaign_id: str, architecture: str) -> Path:
    if architecture == "contact_aware_geometric_shooter":
        return REPO_ROOT / "artifacts" / "session" / campaign_id / "fetch_geometric_shooter_probe" / "geometric_shooter_probe_summary.json"
    return REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_mission_repeatability" / "campaign_run_summary.json"


def _architecture_slug(architecture: str) -> str:
    return architecture.replace("_v1", "").replace("_", "-")


def _build_object_centric_command(args: argparse.Namespace, *, campaign_id: str, case: FetchCase) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "scripts" / "gather_mission_repeatability_runner.py"),
        "--dashboard-url",
        args.dashboard_url,
        "--execution-mode",
        "direct",
        "--scenario-id",
        "corral_single_ball_place",
        "--scenario-label",
        f"Generalized Fetch {case.case_id}",
        "--mission-objective",
        "fetch_to_pose",
        "--fetch-target-x",
        f"{float(case.fetch_pose_world['x']):.6f}",
        "--fetch-target-y",
        f"{float(case.fetch_pose_world['y']):.6f}",
        "--fetch-target-z",
        f"{float(case.fetch_pose_world['z']):.6f}",
        "--fetch-delivery-radius-m",
        f"{float(case.fetch_pose_world['radius_m']):.6f}",
        "--robot-x",
        f"{float(case.robot_start_pose['x']):.6f}",
        "--robot-y",
        f"{float(case.robot_start_pose['y']):.6f}",
        "--robot-yaw",
        f"{float(case.robot_start_pose['yaw']):.6f}",
        "--runs",
        str(max(int(args.runs), 1)),
        "--campaign-id",
        campaign_id,
        "--timeout-s",
        f"{float(args.timeout_s):.3f}",
        "--scenario-timeout-s",
        f"{float(args.scenario_timeout_s):.3f}",
        "--provider",
        args.provider,
        "--world-file",
        args.world_file,
        "--surface-profile",
        args.surface_profile,
        "--promotion-gate-mode",
        "pass_only",
        "--max-retries-per-target",
        "0",
        "--gather-control-family",
        "object_centric_gather_policy_v1",
        "--target-model-sdf",
        fetch_gate.DEFAULT_BALL_SDF,
        "--zone-model-sdf",
        fetch_gate.DEFAULT_ZONE_SDF,
        "--artifact-kind",
        "gather_mission_fetch_generalization",
        "--target-layout-json",
        _relative_path(case.layout_path),
    ]


def _build_geometric_shooter_command(args: argparse.Namespace, *, campaign_id: str, case: FetchCase) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "scripts" / "fetch_geometric_shooter_probe.py"),
        "--dashboard-url",
        args.dashboard_url,
        "--campaign-id",
        campaign_id,
        "--target-layout-json",
        _relative_path(case.layout_path),
        "--world-file",
        args.world_file,
        "--surface-profile",
        args.surface_profile,
        "--fetch-target-x",
        f"{float(case.fetch_pose_world['x']):.6f}",
        "--fetch-target-y",
        f"{float(case.fetch_pose_world['y']):.6f}",
        "--fetch-target-z",
        f"{float(case.fetch_pose_world['z']):.6f}",
        "--fetch-delivery-radius-m",
        f"{float(case.fetch_pose_world['radius_m']):.6f}",
        "--speed-mode",
        "center",
    ]


def build_architecture_specs(args: argparse.Namespace, *, cases: list[FetchCase], logs_root: Path) -> list[ArchitectureSpec]:
    architectures = args.architecture or list(DEFAULT_ARCHITECTURES)
    specs: list[ArchitectureSpec] = []
    base_campaign_id = str(args.campaign_id)
    for architecture in architectures:
        for case in cases:
            campaign_id = f"{base_campaign_id}_{_architecture_slug(architecture)}_{case.case_id}"
            if architecture == "contact_aware_geometric_shooter":
                command = _build_geometric_shooter_command(args, campaign_id=campaign_id, case=case)
            else:
                command = _build_object_centric_command(args, campaign_id=campaign_id, case=case)
            specs.append(
                ArchitectureSpec(
                    architecture=architecture,
                    case=case,
                    campaign_id=campaign_id,
                    command=command,
                    summary_path=_summary_path(campaign_id, architecture),
                    log_path=logs_root / f"{_architecture_slug(architecture)}_{case.case_id}.log",
                    robot_owned_contact=architecture in ROBOT_OWNED_ARCHITECTURES,
                )
            )
    return specs


def _repeatability_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    runs = summary.get("runs", []) if isinstance(summary.get("runs"), list) else []
    closest_values: list[float] = []
    overshoot_values: list[float] = []
    reasons: set[str] = set()
    for run in runs:
        if not isinstance(run, dict):
            continue
        shot = run.get("shot_outcome", {}) if isinstance(run.get("shot_outcome"), dict) else {}
        closest = _finite_float(shot.get("closest_approach_distance_m"))
        if closest is not None:
            closest_values.append(closest)
        overshoot = _finite_float(run.get("max_overshoot_distance_m"))
        if overshoot is not None:
            overshoot_values.append(overshoot)
        reason = str(run.get("fetch_to_pose_failure_reason", "") or "").strip()
        if reason:
            reasons.add(reason)
    reasons.update(str(reason) for reason in summary.get("fetch_to_pose_failure_reasons", []) or [] if str(reason))
    return {
        "pass": bool(summary.get("promotion_gate_pass", summary.get("pass", False))),
        "run_count": len(runs),
        "fetch_to_pose_pass_count": int(summary.get("fetch_to_pose_pass_count", 0) or 0),
        "fetch_to_pose_fail_count": int(summary.get("fetch_to_pose_fail_count", 0) or 0),
        "required_green_runs": int(summary.get("required_green_runs", len(runs) or 1) or (len(runs) or 1)),
        "fresh_attempt_approach_pass_count": int(summary.get("fresh_attempt_approach_pass_count", 0) or 0),
        "approach_side_pass_count": int(summary.get("approach_side_pass_count", 0) or 0),
        "first_contact_push_alignment_max_deg": _finite_float(summary.get("first_contact_push_alignment_max_deg")),
        "worst_closest_approach_distance_m": round(max(closest_values), 6) if closest_values else None,
        "max_overshoot_distance_m": round(max(overshoot_values), 6) if overshoot_values else None,
        "failure_reasons": sorted(reasons),
        "approach_failure_reasons": list(summary.get("approach_failure_reasons", []) or []),
    }


def _geometric_probe_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    verdict = summary.get("mission_verdict", {}) if isinstance(summary.get("mission_verdict"), dict) else {}
    shot = verdict.get("shot_outcome", {}) if isinstance(verdict.get("shot_outcome"), dict) else {}
    model = summary.get("geometric_shooter", {}) if isinstance(summary.get("geometric_shooter"), dict) else {}
    return {
        "pass": bool(verdict.get("fetch_to_pose_pass", verdict.get("pass", False))),
        "run_count": 1 if verdict else 0,
        "fetch_to_pose_pass_count": 1 if bool(verdict.get("fetch_to_pose_pass", verdict.get("pass", False))) else 0,
        "fetch_to_pose_fail_count": 0 if bool(verdict.get("fetch_to_pose_pass", verdict.get("pass", False))) else 1,
        "required_green_runs": 1,
        "worst_closest_approach_distance_m": _finite_float(shot.get("closest_approach_distance_m")),
        "failure_reasons": [str(verdict.get("fetch_to_pose_failure_reason", "") or shot.get("reason", "") or "")],
        "offline_model_pass": bool(model.get("offline_pass", False)),
        "required_target_center_speed_mps": _finite_float(model.get("required_target_center_speed_mps")),
        "aim_half_angle_deg": _finite_float(model.get("aim_half_angle_deg")),
    }


def _classify_result(result: dict[str, Any], *, delivery_radius_m: float) -> str:
    metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}
    if bool(result.get("dry_run", False)):
        return "dry_run_contract_only"
    if not metrics:
        if int(result.get("return_code", 0) or 0) != 0:
            return "runner_failure"
        return "missing_summary"
    if not bool(metrics.get("pass", False)):
        reasons = {str(reason) for reason in metrics.get("failure_reasons", []) + metrics.get("approach_failure_reasons", [])}
        if "shot_model_infeasible" in reasons or metrics.get("offline_model_pass") is False:
            return "shot_infeasible"
        if "entered_goal_side_before_capture" in reasons or "wrong_side_approach" in reasons:
            return "side_selection"
        if "pre_stage_pose_not_reached" in reasons or "pre_stage_handoff_not_requalified" in reasons:
            return "pre_contact_reorientation"
        if "misaligned_first_contact" in reasons or "missing_first_contact_alignment" in reasons:
            return "first_contact_alignment"
        if "ball_lateral_knock_away" in reasons:
            return "lateral_knock_away"
        closest = _finite_float(metrics.get("worst_closest_approach_distance_m"))
        overshoot = _finite_float(metrics.get("max_overshoot_distance_m"))
        if overshoot is not None and overshoot > float(delivery_radius_m):
            return "overshoot"
        if closest is not None and closest > float(delivery_radius_m):
            return "recovery_failure"
        return "fetch_to_pose_failure"
    if not bool(result.get("robot_owned_contact", False)):
        return "shot_primitive_green_not_robot_owned"
    alignment = _finite_float(metrics.get("first_contact_push_alignment_max_deg"))
    if alignment is not None and alignment > 25.0:
        return "first_contact_alignment_suspect"
    closest = _finite_float(metrics.get("worst_closest_approach_distance_m"))
    if closest is not None and closest <= float(delivery_radius_m):
        return "green_within_delivery_radius"
    return "green_missing_closest_distance"


def run_spec(spec: ArchitectureSpec, *, dry_run: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "architecture": spec.architecture,
        "case_id": spec.case.case_id,
        "case_source": spec.case.source,
        "coverage_tags": list(spec.case.coverage_tags),
        "campaign_id": spec.campaign_id,
        "summary_path": _relative_path(spec.summary_path),
        "log_path": _relative_path(spec.log_path),
        "command": spec.command,
        "robot_owned_contact": bool(spec.robot_owned_contact),
        "dry_run": bool(dry_run),
    }
    if dry_run:
        payload.update({"return_code": 0, "pass": True, "metrics": {"pass": True, "run_count": 0}})
        return payload
    proc = subprocess.run(spec.command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    spec.log_path.parent.mkdir(parents=True, exist_ok=True)
    spec.log_path.write_text((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")
    summary = read_json(spec.summary_path) if spec.summary_path.exists() else {}
    metrics = _geometric_probe_metrics(summary) if spec.architecture == "contact_aware_geometric_shooter" else _repeatability_metrics(summary)
    payload.update(
        {
            "return_code": int(proc.returncode),
            "pass": bool(proc.returncode == 0 and metrics.get("pass", False)),
            "metrics": metrics,
            "summary": summary,
        }
    )
    return payload


def _coverage_summary(cases: list[FetchCase]) -> dict[str, Any]:
    tags = sorted({tag for case in cases for tag in case.coverage_tags})
    missing = [tag for tag in REQUIRED_GENERALIZATION_TAGS if tag not in set(tags)]
    return {
        "required_tags": list(REQUIRED_GENERALIZATION_TAGS),
        "observed_tags": tags,
        "missing_tags": missing,
        "coverage_pass": not missing,
    }


def _freeze_failure_layout(result: dict[str, Any], *, case: FetchCase, freeze_root: Path, classification: str) -> str:
    if case.source != "seeded_random":
        return ""
    safe_classification = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in classification)
    destination = freeze_root / f"{case.case_id}_{result.get('architecture')}_{safe_classification}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(case.layout_path, destination)
    return _relative_path(destination)


def _scorecard(summary: dict[str, Any]) -> str:
    lines = [
        "# Fetch Generalization Gate",
        "",
        f"- Campaign: `{summary.get('campaign_id')}`",
        f"- Dry run: `{summary.get('dry_run')}`",
        f"- Seed: `{summary.get('seed')}`",
        f"- Cases: `{summary.get('case_count')}`",
        f"- Coverage pass: `{summary.get('coverage', {}).get('coverage_pass')}`",
        f"- Gate pass: `{summary.get('pass')}`",
        f"- Recommendation: `{summary.get('recommended_next_action')}`",
        "",
        "| Architecture | Case | Source | Classification | Pass | Robot-owned | Summary |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in summary.get("results", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{result.get('architecture')}`",
                    f"`{result.get('case_id')}`",
                    f"`{result.get('case_source')}`",
                    f"`{result.get('classification')}`",
                    str(bool(result.get("pass", False))).lower(),
                    str(bool(result.get("robot_owned_contact", False))).lower(),
                    f"`{result.get('summary_path')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id).strip() or f"live_fetch_generalization_gate_{current_utc_stamp()}"
    args.campaign_id = campaign_id
    output_root = args.output_root if args.output_root.is_absolute() else REPO_ROOT / args.output_root
    root = ensure_dir(output_root / campaign_id / "fetch_generalization_gate")
    case_dir = ensure_dir(root / "layouts")
    logs_root = ensure_dir(root / "logs")
    freeze_root = ensure_dir(root / "frozen_failure_layouts")

    cases: list[FetchCase] = []
    if bool(args.include_saved_anchors):
        cases.extend(build_saved_anchor_cases(case_dir))
    cases.extend(build_seeded_random_cases(case_dir, seed=int(args.seed), count=int(args.random_cases)))
    specs = build_architecture_specs(args, cases=cases, logs_root=logs_root)

    results: list[dict[str, Any]] = []
    case_by_id = {case.case_id: case for case in cases}
    for spec in specs:
        result = run_spec(spec, dry_run=bool(args.dry_run))
        classification = _classify_result(result, delivery_radius_m=float(spec.case.fetch_pose_world["radius_m"]))
        result["classification"] = classification
        if not bool(result.get("pass", False)):
            frozen_path = _freeze_failure_layout(result, case=spec.case, freeze_root=freeze_root, classification=classification)
            if frozen_path:
                result["frozen_failure_layout_path"] = frozen_path
        results.append(result)
        if bool(args.stop_on_failure) and not bool(result.get("pass", False)):
            break

    coverage = _coverage_summary(cases)
    live_results = [result for result in results if not bool(result.get("dry_run", False))]
    robot_owned_results = [result for result in live_results if bool(result.get("robot_owned_contact", False))]
    robot_owned_green = bool(robot_owned_results) and all(bool(result.get("pass", False)) for result in robot_owned_results)
    pass_value = bool(live_results) and all(bool(result.get("pass", False)) for result in live_results) and bool(coverage["coverage_pass"])
    if bool(args.dry_run):
        next_action = "run_live_saved_anchor_and_seeded_generalization_gate"
    elif not bool(coverage["coverage_pass"]):
        next_action = "expand_seeded_case_coverage"
    elif robot_owned_green:
        next_action = "freeze_failures_or_promote_repeatability_discussion"
    else:
        next_action = "inspect_geometry_classifications_before_tuning"

    summary = {
        "generated_utc": utc_now(),
        "type": "fetch_generalization_gate",
        "campaign_id": campaign_id,
        "goal": "Prove Generalized Last-Meter Fetch",
        "dry_run": bool(args.dry_run),
        "seed": int(args.seed),
        "case_count": len(cases),
        "architecture_count": len(args.architecture or DEFAULT_ARCHITECTURES),
        "pass": pass_value,
        "promotion_allowed": bool(pass_value and robot_owned_green),
        "coverage": coverage,
        "cases": [
            {
                "case_id": case.case_id,
                "source": case.source,
                "seed": case.seed,
                "coverage_tags": list(case.coverage_tags),
                "layout_path": _relative_path(case.layout_path),
                "robot_start_pose": case.robot_start_pose,
                "ball_pose_world": case.ball_pose_world,
                "fetch_pose_world": case.fetch_pose_world,
                "geometry": case.geometry,
            }
            for case in cases
        ],
        "results": results,
        "case_by_id": {case_id: {"layout_path": _relative_path(case.layout_path)} for case_id, case in case_by_id.items()},
        "recommended_next_action": next_action,
    }
    summary_path = root / "generalization_gate_summary.json"
    scorecard_path = root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(_scorecard(summary), encoding="utf-8")
    print(f"FETCH_GENERALIZATION_GATE_SUMMARY={summary_path}")
    print(f"FETCH_GENERALIZATION_GATE_SCORECARD={scorecard_path}")
    print(f"FETCH_GENERALIZATION_GATE_RECOMMENDATION={next_action}")
    return 0 if (summary["pass"] or bool(args.dry_run)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
