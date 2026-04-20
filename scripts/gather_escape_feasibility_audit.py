#!/usr/bin/env python3
"""Capability-first feasibility audit for gather pre-stage escape maneuvers."""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import gather_escape_oracle as oracle
import gather_escape_reference as reference
import gather_escape_sandbox as sandbox
from gather_mission_helpers import DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M
from gather_mission_helpers import build_zone_spec
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import write_json


DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CAMPAIGNS: tuple[tuple[str, str], ...] = oracle.DEFAULT_ESCAPE_ORACLE_CAMPAIGNS
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PRIMARY_TRACE_FAMILY = oracle.DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S = 12.0
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STEP_S = 0.25
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STABLE_CLEAR_WINDOW_S = 1.5
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_TOP_K = 10
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_CORRIDOR_CLEARS = 4
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_GOAL_SIDE_CLEARS = 4
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_NEAR_CLEAR_MIN_LATERAL_GAIN_M = (
    reference.DEFAULT_ESCAPE_REFERENCE_NEAR_CLEAR_MIN_LATERAL_GAIN_M
)
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_NEAR_CLEAR_MIN_PROJECTION_GAIN_M = (
    reference.DEFAULT_ESCAPE_REFERENCE_NEAR_CLEAR_MIN_PROJECTION_GAIN_M
)
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STATIONARY_PENALTY = reference.DEFAULT_ESCAPE_REFERENCE_STATIONARY_PENALTY

DEFAULT_ESCAPE_FEASIBILITY_AUDIT_TIGHT_TURN_SCALE = 1.25
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_FOOTPRINT_RADIUS_SCALE = 0.85
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CORRIDOR_RELAXED_MAX_PROJECTION_M = 1.2
DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CORRIDOR_RELAXED_MAX_LATERAL_M = 0.75

DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER: tuple[str, ...] = (
    "nominal_current",
    "tight_turn_relaxed",
    "footprint_relaxed",
    "corridor_relaxed",
    "combined_relaxed",
)

BALL_SDF_PATH = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
HARDWARE_CONSTRAINTS_PATH = REPO_ROOT / "ros2_config" / "config" / "robot_hardware_constraints.yaml"
CONTROLLERS_PATH = REPO_ROOT / "ros2_config" / "config" / "jetbot_controllers.yaml"
NAV2_PARAMS_PATH = REPO_ROOT / "ros2_config" / "params" / "nav2_params_simple.yaml"


@dataclass(frozen=True)
class AuditRepoContract:
    ball_radius_m: float
    robot_radius_m: float
    wheel_separation_m: float
    wheel_radius_m: float
    hardware_max_linear_velocity_mps: float
    hardware_max_angular_velocity_radps: float
    controller_max_linear_velocity_mps: float
    controller_max_angular_velocity_radps: float
    effective_max_linear_velocity_mps: float
    effective_max_angular_velocity_radps: float
    nominal_clearance_radius_m: float
    sources: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeasibilityAuditProfile:
    name: str
    horizon_s: float
    step_s: float
    stable_clear_window_s: float
    corridor_max_projection_m: float
    corridor_max_lateral_m: float
    angular_authority_scale: float
    robot_radius_scale: float
    notes: str

    def effective_robot_radius_m(self, audit_contract: AuditRepoContract) -> float:
        return float(audit_contract.robot_radius_m) * float(self.robot_radius_scale)

    def effective_clearance_radius_m(self, audit_contract: AuditRepoContract) -> float:
        return float(audit_contract.ball_radius_m) + self.effective_robot_radius_m(audit_contract)

    def effective_max_angular_velocity_radps(self, audit_contract: AuditRepoContract) -> float:
        return float(audit_contract.effective_max_angular_velocity_radps) * float(self.angular_authority_scale)

    def to_dict(self, audit_contract: AuditRepoContract) -> dict[str, Any]:
        return {
            **asdict(self),
            "effective_robot_radius_m": round(self.effective_robot_radius_m(audit_contract), 6),
            "effective_clearance_radius_m": round(self.effective_clearance_radius_m(audit_contract), 6),
            "effective_max_angular_velocity_radps": round(
                self.effective_max_angular_velocity_radps(audit_contract),
                6,
            ),
        }


@dataclass(frozen=True)
class AuditSequenceResult:
    profile_name: str
    family_name: str
    macro_sequence: tuple[str, ...]
    corridor_clearable: bool
    goal_side_clearable: bool
    stable_goal_side_cleared: bool
    ball_clearance_ok: bool
    feasibility_class: str
    projection_gain: float
    lateral_gain: float
    distance_gain: float
    min_ball_center_distance_m: float
    min_ball_clearance_margin_m: float
    projected_local_pose: dict[str, float]
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]
    total_rollout_s: float
    score_key: tuple[float, float, float, float, float, float, float]
    progress_score: float
    trajectory_local: tuple[dict[str, float], ...] = ()
    trajectory_world: tuple[dict[str, float], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "macro_sequence": list(self.macro_sequence),
            "trajectory_local": list(self.trajectory_local),
            "trajectory_world": list(self.trajectory_world),
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in YAML file: {path}")
    return loaded


def _number(value: Any, *, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ball_radius_from_sdf(path: Path) -> float:
    root = ET.parse(path).getroot()
    collision_radius = root.findtext(".//collision//sphere/radius")
    visual_radius = root.findtext(".//visual//sphere/radius")
    radius = _number(collision_radius) or _number(visual_radius)
    if radius is None or radius <= 0.0:
        raise ValueError(f"Unable to resolve frisbee target ball radius from {path}")
    return float(radius)


def _robot_radius_from_nav2(path: Path) -> float:
    data = _read_yaml(path)
    radii: list[float] = []
    for key in ("local_costmap", "global_costmap"):
        node = data.get(key, {})
        if isinstance(node, dict):
            node = node.get(key, node)
        if not isinstance(node, dict):
            continue
        ros_params = node.get("ros__parameters", {})
        if not isinstance(ros_params, dict):
            continue
        radius = _number(ros_params.get("robot_radius"))
        if radius is not None and radius > 0.0:
            radii.append(float(radius))
    if not radii:
        raise ValueError(f"Unable to resolve robot_radius from {path}")
    return max(radii)


def _hardware_constraints(path: Path) -> dict[str, float]:
    data = _read_yaml(path)
    root = data.get("robot_hardware_constraints", {})
    if not isinstance(root, dict):
        raise ValueError(f"robot_hardware_constraints root missing from {path}")
    drivetrain = root.get("drivetrain", {})
    if not isinstance(drivetrain, dict):
        raise ValueError(f"drivetrain block missing from {path}")
    values = {
        "wheel_separation_m": _number(drivetrain.get("wheel_separation_m")),
        "wheel_radius_m": _number(drivetrain.get("wheel_radius_m")),
        "max_linear_velocity_mps": _number(drivetrain.get("max_linear_velocity_mps")),
        "max_angular_velocity_radps": _number(drivetrain.get("max_angular_velocity_radps")),
    }
    if any(value is None or value <= 0.0 for value in values.values()):
        raise ValueError(f"Incomplete drivetrain limits in {path}")
    return {key: float(value) for key, value in values.items() if value is not None}


def _controller_limits(path: Path) -> dict[str, float]:
    data = _read_yaml(path)
    controller = data.get("/**/jetbot_base_controller", {})
    if not isinstance(controller, dict):
        raise ValueError(f"/**/jetbot_base_controller block missing from {path}")
    ros_params = controller.get("ros__parameters", {})
    if not isinstance(ros_params, dict):
        raise ValueError(f"ros__parameters missing from {path}")
    linear = _number(ros_params.get("linear.x.max_velocity"))
    angular = _number(ros_params.get("angular.z.max_velocity"))
    if linear is None or linear <= 0.0 or angular is None or angular <= 0.0:
        raise ValueError(f"Controller velocity limits missing from {path}")
    return {
        "max_linear_velocity_mps": float(linear),
        "max_angular_velocity_radps": float(angular),
    }


def load_audit_repo_contract() -> AuditRepoContract:
    hardware = _hardware_constraints(HARDWARE_CONSTRAINTS_PATH)
    controller = _controller_limits(CONTROLLERS_PATH)
    ball_radius_m = _ball_radius_from_sdf(BALL_SDF_PATH)
    robot_radius_m = _robot_radius_from_nav2(NAV2_PARAMS_PATH)
    effective_max_linear_velocity_mps = min(
        float(hardware["max_linear_velocity_mps"]),
        float(controller["max_linear_velocity_mps"]),
    )
    effective_max_angular_velocity_radps = min(
        float(hardware["max_angular_velocity_radps"]),
        float(controller["max_angular_velocity_radps"]),
    )
    return AuditRepoContract(
        ball_radius_m=round(ball_radius_m, 6),
        robot_radius_m=round(robot_radius_m, 6),
        wheel_separation_m=round(float(hardware["wheel_separation_m"]), 6),
        wheel_radius_m=round(float(hardware["wheel_radius_m"]), 6),
        hardware_max_linear_velocity_mps=round(float(hardware["max_linear_velocity_mps"]), 6),
        hardware_max_angular_velocity_radps=round(float(hardware["max_angular_velocity_radps"]), 6),
        controller_max_linear_velocity_mps=round(float(controller["max_linear_velocity_mps"]), 6),
        controller_max_angular_velocity_radps=round(float(controller["max_angular_velocity_radps"]), 6),
        effective_max_linear_velocity_mps=round(effective_max_linear_velocity_mps, 6),
        effective_max_angular_velocity_radps=round(effective_max_angular_velocity_radps, 6),
        nominal_clearance_radius_m=round(ball_radius_m + robot_radius_m, 6),
        sources={
            "ball_sdf": str(BALL_SDF_PATH),
            "hardware_constraints": str(HARDWARE_CONSTRAINTS_PATH),
            "controllers": str(CONTROLLERS_PATH),
            "nav2_params": str(NAV2_PARAMS_PATH),
        },
    )


def resolve_audit_profiles(audit_contract: AuditRepoContract) -> dict[str, FeasibilityAuditProfile]:
    nominal_projection = reference.DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_PROJECTION_M
    nominal_lateral = reference.DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_LATERAL_M
    profiles = {
        "nominal_current": FeasibilityAuditProfile(
            name="nominal_current",
            horizon_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S,
            step_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STEP_S,
            stable_clear_window_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STABLE_CLEAR_WINDOW_S,
            corridor_max_projection_m=nominal_projection,
            corridor_max_lateral_m=nominal_lateral,
            angular_authority_scale=1.0,
            robot_radius_scale=1.0,
            notes="Current repo geometry, footprint, and motion contract.",
        ),
        "tight_turn_relaxed": FeasibilityAuditProfile(
            name="tight_turn_relaxed",
            horizon_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S,
            step_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STEP_S,
            stable_clear_window_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STABLE_CLEAR_WINDOW_S,
            corridor_max_projection_m=nominal_projection,
            corridor_max_lateral_m=nominal_lateral,
            angular_authority_scale=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_TIGHT_TURN_SCALE,
            robot_radius_scale=1.0,
            notes="Increase escape angular authority by 25% with nominal corridor and footprint bounds.",
        ),
        "footprint_relaxed": FeasibilityAuditProfile(
            name="footprint_relaxed",
            horizon_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S,
            step_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STEP_S,
            stable_clear_window_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STABLE_CLEAR_WINDOW_S,
            corridor_max_projection_m=nominal_projection,
            corridor_max_lateral_m=nominal_lateral,
            angular_authority_scale=1.0,
            robot_radius_scale=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_FOOTPRINT_RADIUS_SCALE,
            notes="Reduce effective footprint clearance by 15% with nominal turn authority and corridor bounds.",
        ),
        "corridor_relaxed": FeasibilityAuditProfile(
            name="corridor_relaxed",
            horizon_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S,
            step_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STEP_S,
            stable_clear_window_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STABLE_CLEAR_WINDOW_S,
            corridor_max_projection_m=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CORRIDOR_RELAXED_MAX_PROJECTION_M,
            corridor_max_lateral_m=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CORRIDOR_RELAXED_MAX_LATERAL_M,
            angular_authority_scale=1.0,
            robot_radius_scale=1.0,
            notes="Relax safe-side corridor to projection <= 1.2 m and lateral <= 0.75 m.",
        ),
        "combined_relaxed": FeasibilityAuditProfile(
            name="combined_relaxed",
            horizon_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S,
            step_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STEP_S,
            stable_clear_window_s=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STABLE_CLEAR_WINDOW_S,
            corridor_max_projection_m=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CORRIDOR_RELAXED_MAX_PROJECTION_M,
            corridor_max_lateral_m=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CORRIDOR_RELAXED_MAX_LATERAL_M,
            angular_authority_scale=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_TIGHT_TURN_SCALE,
            robot_radius_scale=DEFAULT_ESCAPE_FEASIBILITY_AUDIT_FOOTPRINT_RADIUS_SCALE,
            notes="Apply turn, footprint, and corridor relaxations together.",
        ),
    }
    missing = [name for name in DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER if name not in profiles]
    if missing:
        raise ValueError(f"Missing audit profiles: {missing}")
    return profiles


def _profile(name: str, audit_contract: AuditRepoContract) -> FeasibilityAuditProfile:
    profiles = resolve_audit_profiles(audit_contract)
    if name not in profiles:
        raise ValueError(f"Unsupported audit profile: {name}")
    return profiles[name]


def _mirror_local_pose(local_pose: dict[str, Any]) -> dict[str, float]:
    return {
        "x": round(float(local_pose.get("x", 0.0) or 0.0), 6),
        "y": round(-float(local_pose.get("y", 0.0) or 0.0), 6),
        "yaw": round(-float(local_pose.get("yaw", 0.0) or 0.0), 6),
    }


def _mirror_macro_name(name: str) -> str:
    if "_left" in name:
        return name.replace("_left", "_right")
    if "_right" in name:
        return name.replace("_right", "_left")
    return name


def classify_audit_result(
    *,
    corridor_clearable: bool,
    goal_side_clearable: bool,
    lateral_gain: float,
    projection_gain: float,
) -> str:
    if corridor_clearable:
        return "corridor_clearable"
    if goal_side_clearable:
        return "goal_side_clearable"
    if (
        float(lateral_gain) >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_NEAR_CLEAR_MIN_LATERAL_GAIN_M
        and float(projection_gain) >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_NEAR_CLEAR_MIN_PROJECTION_GAIN_M
    ):
        return "near_clear"
    return "not_clearable"


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _adapt_maneuver_for_profile(
    maneuver: oracle.EscapeMacro,
    *,
    profile_name: str,
    audit_contract: AuditRepoContract,
) -> oracle.EscapeMacro:
    profile = _profile(profile_name, audit_contract)
    effective_max_linear = float(audit_contract.effective_max_linear_velocity_mps)
    effective_max_angular = float(profile.effective_max_angular_velocity_radps(audit_contract))
    segments: list[oracle.EscapeMacroSegment] = []
    for segment in maneuver.segments:
        linear_x = _clamp(float(segment.linear_x), minimum=-effective_max_linear, maximum=effective_max_linear)
        scaled_angular = float(segment.angular_z) * float(profile.angular_authority_scale)
        angular_z = _clamp(scaled_angular, minimum=-effective_max_angular, maximum=effective_max_angular)
        segments.append(
            oracle.EscapeMacroSegment(
                linear_x=round(linear_x, 6),
                angular_z=round(angular_z, 6),
                duration_s=round(float(segment.duration_s), 6),
            )
        )
    return oracle.EscapeMacro(
        name=str(maneuver.name),
        family_name=str(maneuver.family_name),
        segments=tuple(segments),
    )


def _evaluate_audit_maneuver_variant_local(
    start_local_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    maneuver: oracle.EscapeMacro,
    *,
    zone,
    audit_contract: AuditRepoContract,
    profile_name: str = "nominal_current",
    include_trajectories: bool = False,
) -> AuditSequenceResult | None:
    profile = _profile(profile_name, audit_contract)
    local_samples = sandbox.rollout_macro_sequence_local(
        start_local_pose,
        (maneuver,),
        step_s=profile.step_s,
        horizon_s=profile.horizon_s,
    )
    if not local_samples:
        return None

    start_snapshot = sandbox.local_snapshot(start_local_pose)
    end_local_pose = {
        "x": float(local_samples[-1]["x"]),
        "y": float(local_samples[-1]["y"]),
        "yaw": float(local_samples[-1]["yaw"]),
    }
    projected_robot_pose = sandbox.local_pose_to_world(end_local_pose, ball_pose, zone=zone)
    if projected_robot_pose is None:
        return None
    projected_snapshot = sandbox.local_snapshot(end_local_pose)

    total_rollout_s = float(local_samples[-1]["elapsed_s"])
    stable_window_start_s = max(total_rollout_s - float(profile.stable_clear_window_s), 0.0)
    stable_goal_side_cleared = True
    stable_window_sample_count = 0
    for sample in local_samples:
        if float(sample["elapsed_s"]) + 1.0e-9 < stable_window_start_s:
            continue
        stable_window_sample_count += 1
        if float(sample["x"]) > DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M:
            stable_goal_side_cleared = False
            break
    if stable_window_sample_count <= 0:
        stable_goal_side_cleared = False

    clearance_points = [
        {
            "x": float(start_local_pose.get("x", 0.0) or 0.0),
            "y": float(start_local_pose.get("y", 0.0) or 0.0),
        },
        *local_samples,
    ]
    min_ball_center_distance_m = min(math.hypot(float(item["x"]), float(item["y"])) for item in clearance_points)
    min_ball_clearance_margin_m = min_ball_center_distance_m - float(profile.effective_clearance_radius_m(audit_contract))
    ball_clearance_ok = bool(min_ball_clearance_margin_m >= -1.0e-9)

    start_projection = float(start_snapshot["robot_longitudinal_projection_m"])
    start_lateral = float(start_snapshot["robot_lateral_error_m"])
    start_distance = float(start_snapshot["pre_stage_pose_distance_m"])
    end_projection = float(projected_snapshot["robot_longitudinal_projection_m"])
    end_lateral = float(projected_snapshot["robot_lateral_error_m"])
    end_distance = float(projected_snapshot["pre_stage_pose_distance_m"])
    projection_gain = start_projection - end_projection
    lateral_gain = start_lateral - end_lateral
    distance_gain = start_distance - end_distance

    corridor_clearable = bool(
        stable_goal_side_cleared
        and ball_clearance_ok
        and not bool(projected_snapshot["robot_on_goal_side"])
        and end_projection <= float(profile.corridor_max_projection_m)
        and end_lateral <= float(profile.corridor_max_lateral_m)
    )
    goal_side_clearable = bool(stable_goal_side_cleared and ball_clearance_ok and not corridor_clearable)
    stationary_penalty = DEFAULT_ESCAPE_FEASIBILITY_AUDIT_STATIONARY_PENALTY if maneuver.has_stationary_segment else 0.0
    feasibility_class = classify_audit_result(
        corridor_clearable=corridor_clearable,
        goal_side_clearable=goal_side_clearable,
        lateral_gain=lateral_gain,
        projection_gain=projection_gain,
    )
    score_key = (
        1.0 if corridor_clearable else 0.0,
        1.0 if goal_side_clearable else 0.0,
        round(lateral_gain, 6),
        round(projection_gain, 6),
        round(distance_gain, 6),
        round(min_ball_clearance_margin_m, 6),
        round(-stationary_penalty, 6),
    )
    progress_score = (
        (score_key[0] * 10000.0)
        + (score_key[1] * 1000.0)
        + (score_key[2] * 100.0)
        + (score_key[3] * 10.0)
        + score_key[4]
        + (score_key[5] * 0.5)
        + score_key[6]
    )
    trajectory_local: tuple[dict[str, float], ...] = ()
    trajectory_world: tuple[dict[str, float], ...] = ()
    if include_trajectories:
        trajectory_local = tuple(dict(sample) for sample in local_samples)
        world_samples: list[dict[str, float]] = []
        for sample in local_samples:
            world_pose = sandbox.local_pose_to_world(
                {"x": sample["x"], "y": sample["y"], "yaw": sample["yaw"]},
                ball_pose,
                zone=zone,
            )
            if world_pose is None:
                continue
            world_samples.append(
                {
                    "elapsed_s": float(sample["elapsed_s"]),
                    "x": float(world_pose["x"]),
                    "y": float(world_pose["y"]),
                    "yaw": float(world_pose["yaw"]),
                }
            )
        trajectory_world = tuple(world_samples)
    return AuditSequenceResult(
        profile_name=profile.name,
        family_name=str(maneuver.family_name),
        macro_sequence=(str(maneuver.name),),
        corridor_clearable=corridor_clearable,
        goal_side_clearable=goal_side_clearable,
        stable_goal_side_cleared=stable_goal_side_cleared,
        ball_clearance_ok=ball_clearance_ok,
        feasibility_class=feasibility_class,
        projection_gain=round(projection_gain, 6),
        lateral_gain=round(lateral_gain, 6),
        distance_gain=round(distance_gain, 6),
        min_ball_center_distance_m=round(min_ball_center_distance_m, 6),
        min_ball_clearance_margin_m=round(min_ball_clearance_margin_m, 6),
        projected_local_pose={
            "x": round(float(end_local_pose["x"]), 6),
            "y": round(float(end_local_pose["y"]), 6),
            "yaw": round(float(end_local_pose["yaw"]), 6),
        },
        projected_robot_pose={
            "x": round(float(projected_robot_pose["x"]), 6),
            "y": round(float(projected_robot_pose["y"]), 6),
            "yaw": round(float(projected_robot_pose["yaw"]), 6),
        },
        projected_snapshot=projected_snapshot,
        total_rollout_s=round(total_rollout_s, 6),
        score_key=score_key,
        progress_score=round(progress_score, 6),
        trajectory_local=trajectory_local,
        trajectory_world=trajectory_world,
    )


def evaluate_audit_maneuver_local(
    start_local_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    maneuver: oracle.EscapeMacro,
    *,
    zone,
    audit_contract: AuditRepoContract,
    profile_name: str = "nominal_current",
    include_trajectories: bool = False,
) -> AuditSequenceResult | None:
    profile = _profile(profile_name, audit_contract)
    candidates = [maneuver]
    if float(profile.angular_authority_scale) > 1.0 + 1.0e-9:
        candidates.append(_adapt_maneuver_for_profile(maneuver, profile_name=profile.name, audit_contract=audit_contract))
    best_result: AuditSequenceResult | None = None
    for candidate in candidates:
        result = _evaluate_audit_maneuver_variant_local(
            start_local_pose,
            ball_pose,
            candidate,
            zone=zone,
            audit_contract=audit_contract,
            profile_name=profile.name,
            include_trajectories=include_trajectories,
        )
        if result is None:
            continue
        if best_result is None or (result.score_key, result.progress_score, result.macro_sequence) > (
            best_result.score_key,
            best_result.progress_score,
            best_result.macro_sequence,
        ):
            best_result = result
    return best_result


def search_audit_maneuvers_local(
    start_local_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone,
    audit_contract: AuditRepoContract,
    maneuver_library: dict[str, oracle.EscapeMacro] | None = None,
    profile_name: str = "nominal_current",
    top_k: int | None = None,
    allowed_maneuver_names: tuple[str, ...] | None = None,
    include_trajectories: bool = False,
) -> list[AuditSequenceResult]:
    maneuver_library = dict(maneuver_library or reference.build_reference_maneuver_library())
    maneuver_names = tuple(allowed_maneuver_names or tuple(maneuver_library.keys()))
    results: list[AuditSequenceResult] = []
    for maneuver_name in maneuver_names:
        maneuver = maneuver_library[maneuver_name]
        result = evaluate_audit_maneuver_local(
            start_local_pose,
            ball_pose,
            maneuver,
            zone=zone,
            audit_contract=audit_contract,
            profile_name=profile_name,
            include_trajectories=include_trajectories,
        )
        if result is not None:
            results.append(result)
    results.sort(key=lambda item: (item.score_key, item.progress_score, item.macro_sequence), reverse=True)
    return results[: max(int(top_k or DEFAULT_ESCAPE_FEASIBILITY_AUDIT_TOP_K), 1)]


def search_audit_maneuvers(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone,
    audit_contract: AuditRepoContract,
    maneuver_library: dict[str, oracle.EscapeMacro] | None = None,
    profile_name: str = "nominal_current",
    top_k: int | None = None,
    allowed_maneuver_names: tuple[str, ...] | None = None,
    include_trajectories: bool = False,
) -> list[AuditSequenceResult]:
    start_local_pose = sandbox.world_pose_to_local(robot_pose, ball_pose, zone=zone)
    if start_local_pose is None:
        return []
    return search_audit_maneuvers_local(
        start_local_pose,
        ball_pose,
        zone=zone,
        audit_contract=audit_contract,
        maneuver_library=maneuver_library,
        profile_name=profile_name,
        top_k=top_k,
        allowed_maneuver_names=allowed_maneuver_names,
        include_trajectories=include_trajectories,
    )


def _family_projection_for_fixture(
    fixture: dict[str, Any],
    *,
    family_name: str,
    maneuver_library: dict[str, oracle.EscapeMacro],
    zone,
    audit_contract: AuditRepoContract,
    profile_name: str,
) -> AuditSequenceResult | None:
    allowed_names = tuple(
        name for name, maneuver in maneuver_library.items() if str(maneuver.family_name) == str(family_name)
    )
    if not allowed_names:
        return None
    results = search_audit_maneuvers(
        fixture.get("robot_pose", {}),
        fixture.get("ball_pose", {}),
        zone=zone,
        audit_contract=audit_contract,
        maneuver_library=maneuver_library,
        profile_name=profile_name,
        top_k=1,
        allowed_maneuver_names=allowed_names,
        include_trajectories=False,
    )
    return results[0] if results else None


def aggregate_profile_family_rollups(
    representative_fixtures: list[dict[str, Any]],
    *,
    maneuver_library: dict[str, oracle.EscapeMacro] | None = None,
    zone,
    audit_contract: AuditRepoContract,
    profile_name: str,
) -> list[dict[str, Any]]:
    maneuver_library = dict(maneuver_library or reference.build_reference_maneuver_library())
    rollups: list[dict[str, Any]] = []
    for family_name in reference.MIRRORED_REFERENCE_FAMILIES:
        best_results = [
            _family_projection_for_fixture(
                fixture,
                family_name=family_name,
                maneuver_library=maneuver_library,
                zone=zone,
                audit_contract=audit_contract,
                profile_name=profile_name,
            )
            for fixture in representative_fixtures
        ]
        valid_results = [item for item in best_results if isinstance(item, AuditSequenceResult)]
        if not valid_results:
            continue
        corridor_clear_count = sum(1 for item in valid_results if item.corridor_clearable)
        goal_side_clear_count = sum(1 for item in valid_results if item.goal_side_clearable or item.corridor_clearable)
        near_clear_count = sum(1 for item in valid_results if item.feasibility_class == "near_clear")
        feasibility_class = (
            "corridor_clearable"
            if corridor_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_CORRIDOR_CLEARS
            else "goal_side_clearable"
            if goal_side_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_GOAL_SIDE_CLEARS
            else "near_clear"
            if near_clear_count > 0
            else "not_clearable"
        )
        rollups.append(
            {
                "profile_name": profile_name,
                "family_name": family_name,
                "fixture_count": len(valid_results),
                "corridor_clear_count": corridor_clear_count,
                "stable_goal_side_clear_count": goal_side_clear_count,
                "near_clear_count": near_clear_count,
                "feasibility_class": feasibility_class,
                "mean_lateral_gain": round(sum(item.lateral_gain for item in valid_results) / len(valid_results), 6),
                "mean_projection_gain": round(sum(item.projection_gain for item in valid_results) / len(valid_results), 6),
                "mean_distance_gain": round(sum(item.distance_gain for item in valid_results) / len(valid_results), 6),
                "mean_clearance_margin_m": round(
                    sum(item.min_ball_clearance_margin_m for item in valid_results) / len(valid_results),
                    6,
                ),
                "best_results": [item.to_dict() for item in valid_results],
            }
        )
    rollups.sort(
        key=lambda item: (
            int(item["corridor_clear_count"]),
            int(item["stable_goal_side_clear_count"]),
            int(item["near_clear_count"]),
            float(item["mean_lateral_gain"]),
            float(item["mean_projection_gain"]),
            float(item["mean_clearance_margin_m"]),
            str(item["family_name"]),
        ),
        reverse=True,
    )
    return rollups


def select_best_profile_family(family_rollups: list[dict[str, Any]]) -> str:
    if not family_rollups:
        return ""
    best = max(
        family_rollups,
        key=lambda item: (
            int(item.get("corridor_clear_count", 0)),
            int(item.get("stable_goal_side_clear_count", 0)),
            int(item.get("near_clear_count", 0)),
            float(item.get("mean_lateral_gain", 0.0)),
            float(item.get("mean_projection_gain", 0.0)),
            float(item.get("mean_clearance_margin_m", 0.0)),
            str(item.get("family_name", "")),
        ),
    )
    return str(best.get("family_name", ""))


def _state_history_path_from_campaign_summary(summary_path: Path) -> Path:
    summary = read_json(summary_path)
    runs = summary.get("runs", []) if isinstance(summary.get("runs"), list) else []
    if not runs:
        raise ValueError(f"Campaign summary has no runs: {summary_path}")
    mission_root = runs[0].get("mission_root", "")
    if not mission_root:
        raise ValueError(f"Campaign summary is missing mission_root for first run: {summary_path}")
    return Path(mission_root).resolve() / "state_history.jsonl"


def _default_trace_specs() -> list[tuple[str, Path]]:
    return [
        (
            family_name,
            _state_history_path_from_campaign_summary((REPO_ROOT / relative_path).resolve()),
        )
        for family_name, relative_path in DEFAULT_ESCAPE_FEASIBILITY_AUDIT_CAMPAIGNS
    ]


def _resolve_trace_specs_from_args(args: argparse.Namespace) -> list[tuple[str, Path]]:
    if not args.campaign_summary_path:
        return _default_trace_specs()
    trace_specs: list[tuple[str, Path]] = []
    for item in args.campaign_summary_path:
        family_name, _, raw_path = str(item).partition("=")
        family_name = family_name.strip()
        summary_path = Path(raw_path.strip() or family_name).resolve()
        if not raw_path.strip():
            family_name = summary_path.stem
        trace_specs.append((family_name, _state_history_path_from_campaign_summary(summary_path)))
    return trace_specs


def _symmetry_guard_pass(
    best_actual: AuditSequenceResult | None,
    best_mirrored: AuditSequenceResult | None,
) -> bool:
    if best_actual is None or best_mirrored is None:
        return False
    expected_mirror_sequence = tuple(_mirror_macro_name(name) for name in best_actual.macro_sequence)
    return bool(
        best_actual.family_name == best_mirrored.family_name
        and best_actual.feasibility_class == best_mirrored.feasibility_class
        and expected_mirror_sequence == best_mirrored.macro_sequence
        and abs(float(best_actual.projection_gain) - float(best_mirrored.projection_gain)) < 1.0e-6
        and abs(float(best_actual.lateral_gain) - float(best_mirrored.lateral_gain)) < 1.0e-6
        and abs(float(best_actual.min_ball_clearance_margin_m) - float(best_mirrored.min_ball_clearance_margin_m))
        < 1.0e-6
    )


def _sequence_brief(result: AuditSequenceResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    payload = result.to_dict()
    payload["trajectory_local"] = []
    payload["trajectory_world"] = []
    return payload


def classify_fixture_limiter(profile_results: dict[str, dict[str, Any]]) -> str:
    nominal = profile_results.get("nominal_current", {})
    tight_turn = profile_results.get("tight_turn_relaxed", {})
    footprint = profile_results.get("footprint_relaxed", {})
    corridor = profile_results.get("corridor_relaxed", {})
    combined = profile_results.get("combined_relaxed", {})

    if bool(nominal.get("corridor_clear_available", False)):
        return "controller_shape_limited"
    if bool(tight_turn.get("corridor_clear_available", False)):
        return "turn_radius_limited"
    if bool(footprint.get("corridor_clear_available", False)):
        return "footprint_margin_limited"
    if bool(corridor.get("corridor_clear_available", False)):
        return "corridor_margin_limited"
    if bool(combined.get("corridor_clear_available", False)):
        return "mixed_margin_limited"
    if any(bool(item.get("goal_side_clear_available", False)) for item in profile_results.values()):
        return "corridor_completion_limited"
    return "modeling_or_world_limited"


def _count_limiter_classes(fixture_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fixture in fixture_results:
        limiter = str(fixture.get("limiter_class", "") or "")
        if not limiter:
            continue
        counts[limiter] = counts.get(limiter, 0) + 1
    return counts


def _profile_fixture_summary(
    profile_name: str,
    *,
    top_sequences: list[AuditSequenceResult],
    mirrored_top_sequences: list[AuditSequenceResult],
) -> dict[str, Any]:
    best_result = top_sequences[0] if top_sequences else None
    mirrored_best = mirrored_top_sequences[0] if mirrored_top_sequences else None
    return {
        "profile_name": profile_name,
        "corridor_clear_available": bool(best_result.corridor_clearable) if best_result is not None else False,
        "goal_side_clear_available": (
            bool(best_result.goal_side_clearable or best_result.corridor_clearable) if best_result is not None else False
        ),
        "feasibility_class": str(best_result.feasibility_class) if best_result is not None else "not_clearable",
        "best_sequence": _sequence_brief(best_result),
        "mirrored_best_sequence": _sequence_brief(mirrored_best),
        "symmetry_guard_pass": _symmetry_guard_pass(best_result, mirrored_best),
        "expected_mirrored_macro_sequence": [
            _mirror_macro_name(name) for name in (best_result.macro_sequence if best_result is not None else ())
        ],
    }


def _primary_fixture_profile_bundle(
    fixture: dict[str, Any],
    *,
    profile_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_utc": _utc_now_iso(),
        "fixture_label": str(fixture.get("fixture_label", "")),
        "fixture_index": int(fixture.get("fixture_index", 0) or 0),
        "robot_pose": fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {},
        "robot_pose_local": fixture.get("robot_pose_local", {}) if isinstance(fixture.get("robot_pose_local"), dict) else {},
        "ball_pose": fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {},
        "pre_stage_snapshot": fixture.get("pre_stage", {}) if isinstance(fixture.get("pre_stage"), dict) else {},
        "mirrored_robot_pose_local": _mirror_local_pose(
            fixture.get("robot_pose_local", {}) if isinstance(fixture.get("robot_pose_local"), dict) else {}
        ),
        "profile_results": profile_results,
        "limiter_class": classify_fixture_limiter(profile_results),
    }


def _summarize_trace_family(
    trace_family: str,
    representative_rows: list[dict[str, Any]],
    *,
    maneuver_library: dict[str, oracle.EscapeMacro],
    zone,
    audit_contract: AuditRepoContract,
    include_primary_profiles: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    fixture_results: list[dict[str, Any]] = []
    primary_profile_payloads: dict[str, dict[str, Any]] = {}

    for fixture in representative_rows:
        actual_local = fixture.get("robot_pose_local", {}) if isinstance(fixture.get("robot_pose_local"), dict) else {}
        ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
        mirrored_local = _mirror_local_pose(actual_local)
        profile_result_map: dict[str, dict[str, Any]] = {}
        profile_bundle_map: dict[str, dict[str, Any]] = {}
        for profile_name in DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER:
            include_trajectories = bool(include_primary_profiles)
            top_sequences = search_audit_maneuvers_local(
                actual_local,
                ball_pose,
                zone=zone,
                audit_contract=audit_contract,
                maneuver_library=maneuver_library,
                profile_name=profile_name,
                include_trajectories=include_trajectories,
            )
            mirrored_top_sequences = search_audit_maneuvers_local(
                mirrored_local,
                ball_pose,
                zone=zone,
                audit_contract=audit_contract,
                maneuver_library=maneuver_library,
                profile_name=profile_name,
                include_trajectories=include_trajectories,
            )
            profile_result_map[profile_name] = _profile_fixture_summary(
                profile_name,
                top_sequences=top_sequences,
                mirrored_top_sequences=mirrored_top_sequences,
            )
            if include_primary_profiles:
                profile_bundle_map[profile_name] = {
                    "profile_name": profile_name,
                    "profile_config": _profile(profile_name, audit_contract).to_dict(audit_contract),
                    "top_sequences": [item.to_dict() for item in top_sequences],
                    "mirrored_top_sequences": [item.to_dict() for item in mirrored_top_sequences],
                    **profile_result_map[profile_name],
                }
        payload = {
            "fixture_label": str(fixture.get("fixture_label", "")),
            "fixture_index": int(fixture.get("fixture_index", 0) or 0),
            "generated_utc": str(fixture.get("generated_utc", "")),
            "robot_pose": fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {},
            "ball_pose": ball_pose,
            "robot_pose_local": actual_local,
            "pre_stage_snapshot": fixture.get("pre_stage", {}) if isinstance(fixture.get("pre_stage"), dict) else {},
            "profile_results": profile_result_map,
            "limiter_class": classify_fixture_limiter(profile_result_map),
        }
        fixture_results.append(payload)
        if include_primary_profiles:
            primary_profile_payloads[str(payload["fixture_label"])] = _primary_fixture_profile_bundle(
                fixture,
                profile_results=profile_bundle_map,
            )

    profile_summaries: list[dict[str, Any]] = []
    for profile_name in DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER:
        family_rollups = aggregate_profile_family_rollups(
            representative_rows,
            maneuver_library=maneuver_library,
            zone=zone,
            audit_contract=audit_contract,
            profile_name=profile_name,
        )
        selected_family = select_best_profile_family(family_rollups)
        selected_rollup = next(
            (item for item in family_rollups if str(item.get("family_name", "")) == selected_family),
            None,
        )
        corridor_clear_count = int((selected_rollup or {}).get("corridor_clear_count", 0) or 0)
        goal_side_clear_count = int((selected_rollup or {}).get("stable_goal_side_clear_count", 0) or 0)
        near_clear_count = int((selected_rollup or {}).get("near_clear_count", 0) or 0)
        feasibility_class = (
            "corridor_clearable"
            if corridor_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_CORRIDOR_CLEARS
            else "goal_side_clearable"
            if goal_side_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_GOAL_SIDE_CLEARS
            else "near_clear"
            if near_clear_count > 0
            else "not_clearable"
        )
        profile_summaries.append(
            {
                "profile_name": profile_name,
                "profile_config": _profile(profile_name, audit_contract).to_dict(audit_contract),
                "selected_primary_family": selected_family,
                "corridor_clear_count": corridor_clear_count,
                "stable_goal_side_clear_count": goal_side_clear_count,
                "near_clear_count": near_clear_count,
                "symmetry_guard_pass_count": sum(
                    1
                    for fixture in fixture_results
                    if bool(
                        ((fixture.get("profile_results", {}) or {}).get(profile_name, {}) or {}).get(
                            "symmetry_guard_pass",
                            False,
                        )
                    )
                ),
                "feasibility_class": feasibility_class,
                "corridor_gate_pass": corridor_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_CORRIDOR_CLEARS,
                "goal_side_gate_pass": goal_side_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_GOAL_SIDE_CLEARS,
                "family_rollups": family_rollups,
            }
        )

    trace_summary = {
        "trace_family": trace_family,
        "representative_fixture_count": len(fixture_results),
        "fixture_results": fixture_results,
        "limiter_class_counts": _count_limiter_classes(fixture_results),
        "profile_summaries": profile_summaries,
    }
    return trace_summary, primary_profile_payloads


def _profile_summary_by_name(trace_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("profile_name", "")): item
        for item in trace_summary.get("profile_summaries", [])
        if isinstance(item, dict)
    }


def _select_best_profile_summary(profile_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if not profile_summaries:
        return {}
    order_index = {name: index for index, name in enumerate(DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER)}
    return max(
        profile_summaries,
        key=lambda item: (
            int(item.get("corridor_clear_count", 0)),
            int(item.get("stable_goal_side_clear_count", 0)),
            int(item.get("near_clear_count", 0)),
            -int(order_index.get(str(item.get("profile_name", "")), 999)),
        ),
    )


def decide_primary_next_step(trace_summary: dict[str, Any]) -> dict[str, Any]:
    by_name = _profile_summary_by_name(trace_summary)
    nominal = by_name.get("nominal_current", {})
    relaxed_profiles = [by_name.get(name, {}) for name in DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER[1:]]

    if bool(nominal.get("corridor_gate_pass", False)):
        return {
            "decision_outcome": "offline_distillation_from_winning_family",
            "selected_primary_profile": "nominal_current",
            "selected_profile_summary": nominal,
        }

    first_relaxed_corridor = next((item for item in relaxed_profiles if bool(item.get("corridor_gate_pass", False))), None)
    if first_relaxed_corridor is not None:
        return {
            "decision_outcome": "geometry_footprint_turn_radius_contract_audit",
            "selected_primary_profile": str(first_relaxed_corridor.get("profile_name", "")),
            "selected_profile_summary": first_relaxed_corridor,
        }

    first_goal_side = next(
        (
            item
            for item in [nominal, *relaxed_profiles]
            if bool(item.get("goal_side_gate_pass", False))
        ),
        None,
    )
    if first_goal_side is not None:
        return {
            "decision_outcome": "corridor_completion_sandbox",
            "selected_primary_profile": str(first_goal_side.get("profile_name", "")),
            "selected_profile_summary": first_goal_side,
        }

    best_available = _select_best_profile_summary(list(by_name.values()))
    return {
        "decision_outcome": "richer_world_dynamics_validation",
        "selected_primary_profile": str(best_available.get("profile_name", "")),
        "selected_profile_summary": best_available,
    }


def build_feasibility_audit_bundle(
    trace_specs: list[tuple[str, Path]],
    *,
    campaign_id: str,
    scenario_id: str = "corral_single_ball_place",
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    zone = build_zone_spec(scenario_id)
    audit_contract = load_audit_repo_contract()
    maneuver_library = reference.build_reference_maneuver_library()
    trace_summaries: list[dict[str, Any]] = []
    primary_profile_payloads: dict[str, dict[str, Any]] = {}

    for trace_family, state_history_path in trace_specs:
        rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
        representative_rows = oracle.select_representative_fixture_rows(rows)
        for item in representative_rows:
            robot_pose_local = sandbox.world_pose_to_local(item.get("robot_pose", {}), item.get("ball_pose", {}), zone=zone)
            if robot_pose_local is not None:
                item["robot_pose_local"] = robot_pose_local
        trace_summary, profile_payloads = _summarize_trace_family(
            trace_family,
            representative_rows,
            maneuver_library=maneuver_library,
            zone=zone,
            audit_contract=audit_contract,
            include_primary_profiles=(trace_family == DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PRIMARY_TRACE_FAMILY),
        )
        trace_summary["state_history_path"] = str(state_history_path)
        trace_summaries.append(trace_summary)
        if trace_family == DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PRIMARY_TRACE_FAMILY:
            primary_profile_payloads = profile_payloads

    selected_primary_trace = next(
        (
            item
            for item in trace_summaries
            if str(item.get("trace_family", "")) == DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PRIMARY_TRACE_FAMILY
        ),
        trace_summaries[0] if trace_summaries else {},
    )
    decision = decide_primary_next_step(selected_primary_trace)
    selected_profile_summary = decision.get("selected_profile_summary", {}) or {}
    nominal_primary_summary = _profile_summary_by_name(selected_primary_trace).get("nominal_current", {})
    selected_primary_family = str(selected_profile_summary.get("selected_primary_family", "") or "")
    primary_corridor_clear_count = int(selected_profile_summary.get("corridor_clear_count", 0) or 0)
    primary_goal_side_clear_count = int(selected_profile_summary.get("stable_goal_side_clear_count", 0) or 0)
    primary_near_clear_count = int(selected_profile_summary.get("near_clear_count", 0) or 0)
    feasibility_class = str(selected_profile_summary.get("feasibility_class", "") or "not_clearable")

    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "gather_escape_feasibility_audit",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "primary_trace_family": DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PRIMARY_TRACE_FAMILY,
        "audit_repo_contract": audit_contract.to_dict(),
        "profile_order": list(DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER),
        "profile_configs": {
            name: _profile(name, audit_contract).to_dict(audit_contract)
            for name in DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER
        },
        "required_corridor_clear_fixtures": DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_CORRIDOR_CLEARS,
        "required_goal_side_clear_fixtures": DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_GOAL_SIDE_CLEARS,
        "representative_fixture_count": int(selected_primary_trace.get("representative_fixture_count", 0) or 0),
        "selected_primary_profile": str(decision.get("selected_primary_profile", "") or ""),
        "selected_primary_family": selected_primary_family,
        "primary_corridor_clear_count": primary_corridor_clear_count,
        "stable_goal_side_clear_count": primary_goal_side_clear_count,
        "near_clear_count": primary_near_clear_count,
        "nominal_current_corridor_clear_count": int(nominal_primary_summary.get("corridor_clear_count", 0) or 0),
        "nominal_current_goal_side_clear_count": int(
            nominal_primary_summary.get("stable_goal_side_clear_count", 0) or 0
        ),
        "nominal_current_near_clear_count": int(nominal_primary_summary.get("near_clear_count", 0) or 0),
        "nominal_current_feasibility_class": str(nominal_primary_summary.get("feasibility_class", "") or "not_clearable"),
        "feasibility_class": feasibility_class,
        "decision_outcome": str(decision.get("decision_outcome", "") or ""),
        "corridor_gate_pass": primary_corridor_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_CORRIDOR_CLEARS,
        "goal_side_gate_pass": primary_goal_side_clear_count >= DEFAULT_ESCAPE_FEASIBILITY_AUDIT_REQUIRED_GOAL_SIDE_CLEARS,
        "primary_trace_limiter_class_counts": selected_primary_trace.get("limiter_class_counts", {}),
        "trace_summaries": trace_summaries,
    }
    return summary, primary_profile_payloads


def _profile_brief(profile_result: dict[str, Any]) -> str:
    best = profile_result.get("best_sequence", {}) if isinstance(profile_result, dict) else {}
    macro_sequence = " -> ".join(best.get("macro_sequence", [])) if isinstance(best, dict) else ""
    return (
        f"{profile_result.get('feasibility_class', 'not_clearable')}"
        f"/best={macro_sequence or 'none'}"
        f"/symmetry={'pass' if bool(profile_result.get('symmetry_guard_pass', False)) else 'fail'}"
    )


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    contract = summary.get("audit_repo_contract", {})
    lines = [
        "# Gather Escape Feasibility Audit Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Scenario: `{summary.get('scenario_id', '')}`",
        f"- Primary trace family: `{summary.get('primary_trace_family', '')}`",
        f"- Selected primary profile: `{summary.get('selected_primary_profile', '') or 'none'}`",
        f"- Selected primary family: `{summary.get('selected_primary_family', '') or 'none'}`",
        f"- Nominal corridor gate: `{summary.get('nominal_current_corridor_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Selected profile corridor gate: `{summary.get('primary_corridor_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Selected profile goal-side gate: `{summary.get('stable_goal_side_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Feasibility class: `{summary.get('feasibility_class', '')}`",
        f"- Decision outcome: `{summary.get('decision_outcome', '')}`",
        "",
        "## Repo Contract",
        "",
        f"- Ball radius: `{float(contract.get('ball_radius_m', 0.0)):.3f} m`",
        f"- Robot radius: `{float(contract.get('robot_radius_m', 0.0)):.3f} m`",
        f"- Nominal clearance radius: `{float(contract.get('nominal_clearance_radius_m', 0.0)):.3f} m`",
        f"- Effective max linear velocity: `{float(contract.get('effective_max_linear_velocity_mps', 0.0)):.3f} m/s`",
        f"- Effective max angular velocity: `{float(contract.get('effective_max_angular_velocity_radps', 0.0)):.3f} rad/s`",
        "",
        "## Trace Families",
        "",
    ]
    for trace_summary in summary.get("trace_summaries", []):
        lines.append(
            f"- `{trace_summary.get('trace_family', '')}` limiter_counts=`{json.dumps(trace_summary.get('limiter_class_counts', {}), sort_keys=True)}`"
        )
        for profile_summary in trace_summary.get("profile_summaries", []):
            lines.append(
                f"  - profile `{profile_summary.get('profile_name', '')}` "
                f"family=`{profile_summary.get('selected_primary_family', '') or 'none'}` "
                f"corridor_clear=`{profile_summary.get('corridor_clear_count', 0)}` "
                f"goal_side_clear=`{profile_summary.get('stable_goal_side_clear_count', 0)}` "
                f"near_clear=`{profile_summary.get('near_clear_count', 0)}` "
                f"symmetry=`{profile_summary.get('symmetry_guard_pass_count', 0)}/{trace_summary.get('representative_fixture_count', 0)}` "
                f"feasibility=`{profile_summary.get('feasibility_class', '')}`"
            )
        lines.append("")
        lines.append("  Representative fixtures:")
        for fixture in trace_summary.get("fixture_results", []):
            profile_results = fixture.get("profile_results", {}) if isinstance(fixture.get("profile_results"), dict) else {}
            lines.append(
                f"  - `{fixture.get('fixture_label', '')}` limiter=`{fixture.get('limiter_class', '')}` "
                f"nominal=`{_profile_brief(profile_results.get('nominal_current', {}))}` "
                f"tight_turn=`{_profile_brief(profile_results.get('tight_turn_relaxed', {}))}` "
                f"footprint=`{_profile_brief(profile_results.get('footprint_relaxed', {}))}` "
                f"corridor=`{_profile_brief(profile_results.get('corridor_relaxed', {}))}` "
                f"combined=`{_profile_brief(profile_results.get('combined_relaxed', {}))}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a capability-first offline feasibility audit over gather pre-stage escape fixtures."
    )
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument(
        "--campaign-summary-path",
        action="append",
        default=[],
        help="Optional repeated family=campaign_summary.json spec. Defaults to the latest baseline/v1/v2 plus45 campaigns.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip() or oracle.current_utc_stamp()
    output_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_escape_feasibility_audit")
    profiles_root = ensure_dir(output_root / "profiles")
    trace_specs = _resolve_trace_specs_from_args(args)
    summary, primary_profile_payloads = build_feasibility_audit_bundle(
        trace_specs,
        campaign_id=campaign_id,
        scenario_id=args.scenario_id,
    )
    summary_path = output_root / "feasibility_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    for fixture_label, payload in primary_profile_payloads.items():
        write_json(profiles_root / f"{fixture_label}.json", payload)
    print(f"GATHER_ESCAPE_FEASIBILITY_AUDIT_SUMMARY={summary_path}")
    print(
        json.dumps(
            {
                "campaign_id": summary.get("campaign_id", ""),
                "type": summary.get("type", ""),
                "decision_outcome": summary.get("decision_outcome", ""),
                "selected_primary_profile": summary.get("selected_primary_profile", ""),
                "selected_primary_family": summary.get("selected_primary_family", ""),
                "primary_corridor_clear_count": summary.get("primary_corridor_clear_count", 0),
                "stable_goal_side_clear_count": summary.get("stable_goal_side_clear_count", 0),
                "near_clear_count": summary.get("near_clear_count", 0),
                "nominal_current_corridor_clear_count": summary.get("nominal_current_corridor_clear_count", 0),
                "nominal_current_goal_side_clear_count": summary.get("nominal_current_goal_side_clear_count", 0),
                "primary_trace_limiter_class_counts": summary.get("primary_trace_limiter_class_counts", {}),
            },
            indent=2,
            sort_keys=True,
        )
    )
    decision = str(summary.get("decision_outcome", ""))
    return 0 if decision in {
        "offline_distillation_from_winning_family",
        "geometry_footprint_turn_radius_contract_audit",
        "corridor_completion_sandbox",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
