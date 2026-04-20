#!/usr/bin/env python3
"""Hand-scripted truth-state reference maneuvers for gather escape feasibility."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gather_escape_oracle as oracle
import gather_escape_sandbox as sandbox
from gather_mission_helpers import DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M
from gather_mission_helpers import build_zone_spec
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import write_json


DEFAULT_ESCAPE_REFERENCE_CAMPAIGNS: tuple[tuple[str, str], ...] = oracle.DEFAULT_ESCAPE_ORACLE_CAMPAIGNS
DEFAULT_ESCAPE_REFERENCE_PRIMARY_TRACE_FAMILY = oracle.DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY
DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE = "reference_v1"
DEFAULT_ESCAPE_REFERENCE_HORIZON_S = 14.0
DEFAULT_ESCAPE_REFERENCE_STEP_S = 0.25
DEFAULT_ESCAPE_REFERENCE_STABLE_CLEAR_WINDOW_S = 1.5
DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_PROJECTION_M = sandbox.DEFAULT_ESCAPE_SANDBOX_CORRIDOR_MAX_PROJECTION_M
DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_LATERAL_M = sandbox.DEFAULT_ESCAPE_SANDBOX_CORRIDOR_MAX_LATERAL_M
DEFAULT_ESCAPE_REFERENCE_TOP_K = 10
DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS = 4
DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS = 4
DEFAULT_ESCAPE_REFERENCE_NEAR_CLEAR_MIN_LATERAL_GAIN_M = sandbox.DEFAULT_ESCAPE_SANDBOX_NEAR_CLEAR_MIN_LATERAL_GAIN_M
DEFAULT_ESCAPE_REFERENCE_NEAR_CLEAR_MIN_PROJECTION_GAIN_M = sandbox.DEFAULT_ESCAPE_SANDBOX_NEAR_CLEAR_MIN_PROJECTION_GAIN_M
DEFAULT_ESCAPE_REFERENCE_STATIONARY_PENALTY = 0.05

MIRRORED_REFERENCE_FAMILIES: tuple[str, ...] = (
    "wide_loop",
    "retreat_loop",
    "three_point_commit",
    "sweep_then_align",
    "forward_clear",
)


@dataclass(frozen=True)
class ReferenceSearchProfile:
    name: str
    horizon_s: float
    step_s: float
    stable_clear_window_s: float
    corridor_max_projection_m: float
    corridor_max_lateral_m: float
    top_k: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReferenceSequenceResult:
    family_name: str
    macro_sequence: tuple[str, ...]
    corridor_clearable: bool
    goal_side_clearable: bool
    feasibility_class: str
    projection_gain: float
    lateral_gain: float
    distance_gain: float
    projected_local_pose: dict[str, float]
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]
    total_rollout_s: float
    score_key: tuple[float, float, float, float, float]
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


def resolve_reference_search_profile(
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
) -> ReferenceSearchProfile:
    normalized = str(search_profile or "").strip() or DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE
    if normalized != DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE:
        raise ValueError(f"Unsupported reference profile: {search_profile}")
    return ReferenceSearchProfile(
        name=DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
        horizon_s=DEFAULT_ESCAPE_REFERENCE_HORIZON_S,
        step_s=DEFAULT_ESCAPE_REFERENCE_STEP_S,
        stable_clear_window_s=DEFAULT_ESCAPE_REFERENCE_STABLE_CLEAR_WINDOW_S,
        corridor_max_projection_m=DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_PROJECTION_M,
        corridor_max_lateral_m=DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_LATERAL_M,
        top_k=DEFAULT_ESCAPE_REFERENCE_TOP_K,
    )


def build_reference_maneuver_library(
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
) -> dict[str, oracle.EscapeMacro]:
    resolve_reference_search_profile(search_profile)

    def _macro(name: str, family_name: str, segments: list[tuple[float, float, float]]) -> oracle.EscapeMacro:
        return oracle.EscapeMacro(
            name=name,
            family_name=family_name,
            segments=tuple(oracle.EscapeMacroSegment(*item) for item in segments),
        )

    return {
        "wide_loop_left": _macro(
            "wide_loop_left",
            "wide_loop",
            [(0.18, 1.20, 1.50), (0.18, 0.70, 1.00), (-0.18, 0.55, 1.25), (-0.18, 0.15, 1.00)],
        ),
        "wide_loop_right": _macro(
            "wide_loop_right",
            "wide_loop",
            [(0.18, -1.20, 1.50), (0.18, -0.70, 1.00), (-0.18, -0.55, 1.25), (-0.18, -0.15, 1.00)],
        ),
        "retreat_loop_left": _macro(
            "retreat_loop_left",
            "retreat_loop",
            [(-0.18, 0.95, 1.25), (-0.18, 0.55, 1.00), (0.18, 1.05, 1.50), (0.16, 0.30, 1.00)],
        ),
        "retreat_loop_right": _macro(
            "retreat_loop_right",
            "retreat_loop",
            [(-0.18, -0.95, 1.25), (-0.18, -0.55, 1.00), (0.18, -1.05, 1.50), (0.16, -0.30, 1.00)],
        ),
        "three_point_commit_left": _macro(
            "three_point_commit_left",
            "three_point_commit",
            [(-0.18, 1.00, 1.00), (0.0, -1.35, 0.75), (0.18, -0.95, 1.25), (-0.18, 0.45, 1.25)],
        ),
        "three_point_commit_right": _macro(
            "three_point_commit_right",
            "three_point_commit",
            [(-0.18, -1.00, 1.00), (0.0, 1.35, 0.75), (0.18, 0.95, 1.25), (-0.18, -0.45, 1.25)],
        ),
        "sweep_then_align_left": _macro(
            "sweep_then_align_left",
            "sweep_then_align",
            [(0.16, 1.10, 1.25), (0.18, 0.60, 0.75), (-0.18, 0.80, 1.25), (-0.18, 0.20, 1.00)],
        ),
        "sweep_then_align_right": _macro(
            "sweep_then_align_right",
            "sweep_then_align",
            [(0.16, -1.10, 1.25), (0.18, -0.60, 0.75), (-0.18, -0.80, 1.25), (-0.18, -0.20, 1.00)],
        ),
        "forward_clear_left": _macro(
            "forward_clear_left",
            "forward_clear",
            [(0.18, 1.25, 1.50), (0.18, 0.80, 1.00), (0.0, -1.10, 0.50), (-0.18, 0.45, 1.25)],
        ),
        "forward_clear_right": _macro(
            "forward_clear_right",
            "forward_clear",
            [(0.18, -1.25, 1.50), (0.18, -0.80, 1.00), (0.0, 1.10, 0.50), (-0.18, -0.45, 1.25)],
        ),
    }


def classify_reference_result(
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
        float(lateral_gain) >= DEFAULT_ESCAPE_REFERENCE_NEAR_CLEAR_MIN_LATERAL_GAIN_M
        and float(projection_gain) >= DEFAULT_ESCAPE_REFERENCE_NEAR_CLEAR_MIN_PROJECTION_GAIN_M
    ):
        return "near_clear"
    return "not_clearable"


def evaluate_reference_maneuver(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    maneuver: oracle.EscapeMacro,
    *,
    zone=None,
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
    include_trajectories: bool = False,
) -> ReferenceSequenceResult | None:
    profile = resolve_reference_search_profile(search_profile)
    zone = zone or build_zone_spec("corral_single_ball_place")
    start_local_pose = sandbox.world_pose_to_local(robot_pose, ball_pose, zone=zone)
    if start_local_pose is None:
        return None
    start_snapshot = sandbox.local_snapshot(start_local_pose)
    local_samples = sandbox.rollout_macro_sequence_local(
        start_local_pose,
        (maneuver,),
        step_s=profile.step_s,
        horizon_s=profile.horizon_s,
    )
    if not local_samples:
        return None
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
        and not bool(projected_snapshot["robot_on_goal_side"])
        and end_projection <= float(profile.corridor_max_projection_m)
        and end_lateral <= float(profile.corridor_max_lateral_m)
    )
    goal_side_clearable = bool(stable_goal_side_cleared and not corridor_clearable)
    stationary_penalty = DEFAULT_ESCAPE_REFERENCE_STATIONARY_PENALTY if maneuver.has_stationary_segment else 0.0
    feasibility_class = classify_reference_result(
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
        round(-stationary_penalty, 6),
    )
    progress_score = (
        (score_key[0] * 10000.0)
        + (score_key[1] * 1000.0)
        + (score_key[2] * 100.0)
        + (score_key[3] * 10.0)
        + score_key[4]
        + score_key[5]
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
    return ReferenceSequenceResult(
        family_name=str(maneuver.family_name),
        macro_sequence=(str(maneuver.name),),
        corridor_clearable=corridor_clearable,
        goal_side_clearable=goal_side_clearable,
        feasibility_class=feasibility_class,
        projection_gain=round(projection_gain, 6),
        lateral_gain=round(lateral_gain, 6),
        distance_gain=round(distance_gain, 6),
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


def search_reference_maneuvers(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone=None,
    maneuver_library: dict[str, oracle.EscapeMacro] | None = None,
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
    top_k: int | None = None,
    allowed_maneuver_names: tuple[str, ...] | None = None,
    include_trajectories: bool = False,
) -> list[ReferenceSequenceResult]:
    profile = resolve_reference_search_profile(search_profile)
    zone = zone or build_zone_spec("corral_single_ball_place")
    maneuver_library = dict(maneuver_library or build_reference_maneuver_library(profile.name))
    maneuver_names = tuple(allowed_maneuver_names or tuple(maneuver_library.keys()))
    results: list[ReferenceSequenceResult] = []
    for maneuver_name in maneuver_names:
        maneuver = maneuver_library[maneuver_name]
        result = evaluate_reference_maneuver(
            robot_pose,
            ball_pose,
            maneuver,
            zone=zone,
            search_profile=profile.name,
            include_trajectories=include_trajectories,
        )
        if result is not None:
            results.append(result)
    results.sort(key=lambda item: (item.score_key, item.progress_score, item.macro_sequence), reverse=True)
    return results[: max(int(top_k or profile.top_k), 1)]


def _family_projection_for_fixture(
    fixture: dict[str, Any],
    *,
    family_name: str,
    maneuver_library: dict[str, oracle.EscapeMacro],
    zone,
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
) -> ReferenceSequenceResult | None:
    allowed_names = tuple(
        name for name, maneuver in maneuver_library.items() if str(maneuver.family_name) == str(family_name)
    )
    if not allowed_names:
        return None
    results = search_reference_maneuvers(
        fixture.get("robot_pose", {}),
        fixture.get("ball_pose", {}),
        zone=zone,
        maneuver_library=maneuver_library,
        search_profile=search_profile,
        top_k=1,
        allowed_maneuver_names=allowed_names,
        include_trajectories=False,
    )
    return results[0] if results else None


def aggregate_reference_family_rollups(
    representative_fixtures: list[dict[str, Any]],
    *,
    maneuver_library: dict[str, oracle.EscapeMacro] | None = None,
    zone=None,
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
) -> list[dict[str, Any]]:
    profile = resolve_reference_search_profile(search_profile)
    zone = zone or build_zone_spec("corral_single_ball_place")
    maneuver_library = dict(maneuver_library or build_reference_maneuver_library(profile.name))
    rollups: list[dict[str, Any]] = []
    for family_name in MIRRORED_REFERENCE_FAMILIES:
        best_results = [
            _family_projection_for_fixture(
                fixture,
                family_name=family_name,
                maneuver_library=maneuver_library,
                zone=zone,
                search_profile=profile.name,
            )
            for fixture in representative_fixtures
        ]
        valid_results = [item for item in best_results if isinstance(item, ReferenceSequenceResult)]
        if not valid_results:
            continue
        corridor_clear_count = sum(1 for item in valid_results if item.corridor_clearable)
        goal_side_clear_count = sum(1 for item in valid_results if item.goal_side_clearable or item.corridor_clearable)
        near_clear_count = sum(1 for item in valid_results if item.feasibility_class == "near_clear")
        feasibility_class = (
            "corridor_clearable"
            if corridor_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS
            else "goal_side_clearable"
            if goal_side_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS
            else "near_clear"
            if near_clear_count > 0
            else "not_clearable"
        )
        rollups.append(
            {
                "family_name": family_name,
                "fixture_count": len(valid_results),
                "corridor_clear_count": corridor_clear_count,
                "stable_goal_side_clear_count": goal_side_clear_count,
                "near_clear_count": near_clear_count,
                "feasibility_class": feasibility_class,
                "mean_lateral_gain": round(sum(item.lateral_gain for item in valid_results) / len(valid_results), 6),
                "mean_projection_gain": round(sum(item.projection_gain for item in valid_results) / len(valid_results), 6),
                "mean_distance_gain": round(sum(item.distance_gain for item in valid_results) / len(valid_results), 6),
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
            str(item["family_name"]),
        ),
        reverse=True,
    )
    return rollups


def select_best_reference_family(family_rollups: list[dict[str, Any]]) -> str:
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
        for family_name, relative_path in DEFAULT_ESCAPE_REFERENCE_CAMPAIGNS
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


def _fixture_payload(
    fixture: dict[str, Any],
    *,
    top_sequences: list[ReferenceSequenceResult],
) -> dict[str, Any]:
    best_result = top_sequences[0] if top_sequences else None
    return {
        "fixture_label": str(fixture.get("fixture_label", "")),
        "fixture_index": int(fixture.get("fixture_index", 0) or 0),
        "generated_utc": str(fixture.get("generated_utc", "")),
        "robot_pose": fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {},
        "ball_pose": fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {},
        "robot_pose_local": fixture.get("robot_pose_local", {}) if isinstance(fixture.get("robot_pose_local"), dict) else {},
        "pre_stage_snapshot": fixture.get("pre_stage", {}) if isinstance(fixture.get("pre_stage"), dict) else {},
        "top_sequences": [item.to_dict() for item in top_sequences],
        "corridor_clear_available": bool(best_result.corridor_clearable) if best_result is not None else False,
        "goal_side_clear_available": (
            bool(best_result.goal_side_clearable or best_result.corridor_clearable) if best_result is not None else False
        ),
        "feasibility_class": str(best_result.feasibility_class) if best_result is not None else "not_clearable",
        "end_projection_m": (
            float(best_result.projected_snapshot.get("robot_longitudinal_projection_m", 0.0))
            if best_result is not None
            else 0.0
        ),
        "end_lateral_error_m": (
            float(best_result.projected_snapshot.get("robot_lateral_error_m", 0.0))
            if best_result is not None
            else 0.0
        ),
        "end_pre_stage_distance_m": (
            float(best_result.projected_snapshot.get("pre_stage_pose_distance_m", 0.0))
            if best_result is not None
            else 0.0
        ),
    }


def _summarize_trace_family(
    trace_family: str,
    representative_rows: list[dict[str, Any]],
    *,
    maneuver_library: dict[str, oracle.EscapeMacro],
    zone,
    search_profile: str,
    include_trajectories: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    fixture_results: list[dict[str, Any]] = []
    trajectory_payloads: dict[str, dict[str, Any]] = {}
    for fixture in representative_rows:
        robot_pose = fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {}
        ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
        top_sequences = search_reference_maneuvers(
            robot_pose,
            ball_pose,
            zone=zone,
            maneuver_library=maneuver_library,
            search_profile=search_profile,
            include_trajectories=include_trajectories,
        )
        payload = _fixture_payload(fixture, top_sequences=top_sequences)
        fixture_results.append(payload)
        if include_trajectories:
            trajectory_payloads[str(payload["fixture_label"])] = {
                "generated_utc": _utc_now_iso(),
                "trace_family": trace_family,
                "fixture_label": payload["fixture_label"],
                "fixture_index": payload["fixture_index"],
                "robot_pose": payload["robot_pose"],
                "robot_pose_local": payload["robot_pose_local"],
                "ball_pose": payload["ball_pose"],
                "top_sequences": payload["top_sequences"],
            }
    family_rollups = aggregate_reference_family_rollups(
        representative_rows,
        maneuver_library=maneuver_library,
        zone=zone,
        search_profile=search_profile,
    )
    selected_family = select_best_reference_family(family_rollups)
    selected_rollup = next(
        (item for item in family_rollups if str(item.get("family_name", "")) == selected_family),
        None,
    )
    corridor_clear_count = int((selected_rollup or {}).get("corridor_clear_count", 0))
    goal_side_clear_count = int((selected_rollup or {}).get("stable_goal_side_clear_count", 0))
    near_clear_count = int((selected_rollup or {}).get("near_clear_count", 0))
    feasibility_class = (
        "corridor_clearable"
        if corridor_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS
        else "goal_side_clearable"
        if goal_side_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS
        else "near_clear"
        if near_clear_count > 0
        else "not_clearable"
    )
    trace_summary = {
        "trace_family": trace_family,
        "search_profile": search_profile,
        "representative_fixture_count": len(fixture_results),
        "fixture_results": fixture_results,
        "family_rollups": family_rollups,
        "selected_primary_family": selected_family,
        "corridor_clear_count": corridor_clear_count,
        "stable_goal_side_clear_count": goal_side_clear_count,
        "near_clear_count": near_clear_count,
        "feasibility_class": feasibility_class,
        "corridor_gate_pass": corridor_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS,
        "goal_side_gate_pass": goal_side_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS,
    }
    return trace_summary, trajectory_payloads


def build_reference_bundle(
    trace_specs: list[tuple[str, Path]],
    *,
    campaign_id: str,
    scenario_id: str = "corral_single_ball_place",
    search_profile: str = DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    profile = resolve_reference_search_profile(search_profile)
    zone = build_zone_spec(scenario_id)
    maneuver_library = build_reference_maneuver_library(profile.name)
    trace_summaries: list[dict[str, Any]] = []
    primary_trajectories: dict[str, dict[str, Any]] = {}

    for trace_family, state_history_path in trace_specs:
        rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
        representative_rows = oracle.select_representative_fixture_rows(rows)
        for item in representative_rows:
            robot_pose_local = sandbox.world_pose_to_local(item.get("robot_pose", {}), item.get("ball_pose", {}), zone=zone)
            if robot_pose_local is not None:
                item["robot_pose_local"] = robot_pose_local
        trace_summary, trajectories = _summarize_trace_family(
            trace_family,
            representative_rows,
            maneuver_library=maneuver_library,
            zone=zone,
            search_profile=profile.name,
            include_trajectories=(trace_family == DEFAULT_ESCAPE_REFERENCE_PRIMARY_TRACE_FAMILY),
        )
        trace_summary["state_history_path"] = str(state_history_path)
        trace_summaries.append(trace_summary)
        if trace_family == DEFAULT_ESCAPE_REFERENCE_PRIMARY_TRACE_FAMILY:
            primary_trajectories = trajectories

    selected_primary_trace = next(
        (
            item
            for item in trace_summaries
            if str(item.get("trace_family", "")) == DEFAULT_ESCAPE_REFERENCE_PRIMARY_TRACE_FAMILY
        ),
        trace_summaries[0] if trace_summaries else {},
    )
    selected_family = str(selected_primary_trace.get("selected_primary_family", "") or "")
    primary_corridor_clear_count = int(selected_primary_trace.get("corridor_clear_count", 0) or 0)
    primary_goal_side_clear_count = int(selected_primary_trace.get("stable_goal_side_clear_count", 0) or 0)
    primary_near_clear_count = int(selected_primary_trace.get("near_clear_count", 0) or 0)
    decision_outcome = (
        "unlock_sandbox_v2_distillation"
        if primary_corridor_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS
        else "sandbox_v2_corridor_completion"
        if primary_goal_side_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS
        else "geometry_turn_radius_modeling_audit"
    )
    feasibility_class = (
        "corridor_clearable"
        if primary_corridor_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS
        else "goal_side_clearable"
        if primary_goal_side_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS
        else "near_clear"
        if primary_near_clear_count > 0
        else "not_clearable"
    )
    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "gather_escape_reference",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "search_profile": profile.name,
        "search_profile_config": profile.to_dict(),
        "primary_trace_family": DEFAULT_ESCAPE_REFERENCE_PRIMARY_TRACE_FAMILY,
        "required_corridor_clear_fixtures": DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS,
        "required_goal_side_clear_fixtures": DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS,
        "representative_fixture_count": int(selected_primary_trace.get("representative_fixture_count", 0) or 0),
        "selected_primary_family": selected_family,
        "primary_corridor_clear_count": primary_corridor_clear_count,
        "stable_goal_side_clear_count": primary_goal_side_clear_count,
        "near_clear_count": primary_near_clear_count,
        "feasibility_class": feasibility_class,
        "decision_outcome": decision_outcome,
        "corridor_gate_pass": primary_corridor_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_CORRIDOR_CLEARS,
        "goal_side_gate_pass": primary_goal_side_clear_count >= DEFAULT_ESCAPE_REFERENCE_REQUIRED_GOAL_SIDE_CLEARS,
        "trace_summaries": trace_summaries,
    }
    return summary, primary_trajectories


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Escape Reference Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Scenario: `{summary.get('scenario_id', '')}`",
        f"- Search profile: `{summary.get('search_profile', '')}`",
        f"- Primary trace family: `{summary.get('primary_trace_family', '')}`",
        f"- Selected primary family: `{summary.get('selected_primary_family', '') or 'none'}`",
        f"- Corridor gate: `{summary.get('primary_corridor_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Goal-side gate: `{summary.get('stable_goal_side_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Feasibility class: `{summary.get('feasibility_class', '')}`",
        f"- Decision outcome: `{summary.get('decision_outcome', '')}`",
        "",
        "## Trace Families",
        "",
    ]
    for trace_summary in summary.get("trace_summaries", []):
        lines.append(
            f"- `{trace_summary.get('trace_family', '')}` summary: "
            f"selected_family=`{trace_summary.get('selected_primary_family', '') or 'none'}` "
            f"corridor_clear=`{trace_summary.get('corridor_clear_count', 0)}` "
            f"goal_side_clear=`{trace_summary.get('stable_goal_side_clear_count', 0)}` "
            f"near_clear=`{trace_summary.get('near_clear_count', 0)}` "
            f"feasibility=`{trace_summary.get('feasibility_class', '')}`"
        )
        for family_rollup in trace_summary.get("family_rollups", []):
            lines.append(
                f"  - family `{family_rollup.get('family_name', '')}` "
                f"corridor_clear=`{family_rollup.get('corridor_clear_count', 0)}` "
                f"goal_side_clear=`{family_rollup.get('stable_goal_side_clear_count', 0)}` "
                f"near_clear=`{family_rollup.get('near_clear_count', 0)}` "
                f"mean_lateral_gain=`{float(family_rollup.get('mean_lateral_gain', 0.0)):.3f}` "
                f"mean_projection_gain=`{float(family_rollup.get('mean_projection_gain', 0.0)):.3f}`"
            )
        lines.append("")
        lines.append("  Representative fixtures:")
        for fixture in trace_summary.get("fixture_results", []):
            top_sequences = fixture.get("top_sequences", [])
            best_sequence = top_sequences[0] if isinstance(top_sequences, list) and top_sequences else {}
            macro_sequence = " -> ".join(best_sequence.get("macro_sequence", [])) if isinstance(best_sequence, dict) else ""
            lines.append(
                f"  - `{fixture.get('fixture_label', '')}` "
                f"corridor_clear=`{bool(fixture.get('corridor_clear_available', False))}` "
                f"goal_side_clear=`{bool(fixture.get('goal_side_clear_available', False))}` "
                f"feasibility=`{fixture.get('feasibility_class', '')}` "
                f"best=`{macro_sequence or 'none'}` "
                f"end_projection=`{float(fixture.get('end_projection_m', 0.0)):.3f}` "
                f"end_lateral=`{float(fixture.get('end_lateral_error_m', 0.0)):.3f}` "
                f"end_distance=`{float(fixture.get('end_pre_stage_distance_m', 0.0)):.3f}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run hand-scripted truth-state gather escape reference maneuvers.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument(
        "--search-profile",
        default=DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,
        choices=(DEFAULT_ESCAPE_REFERENCE_DEFAULT_PROFILE,),
    )
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
    output_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_escape_reference")
    trajectories_root = ensure_dir(output_root / "trajectories")
    trace_specs = _resolve_trace_specs_from_args(args)
    summary, primary_trajectories = build_reference_bundle(
        trace_specs,
        campaign_id=campaign_id,
        scenario_id=args.scenario_id,
        search_profile=args.search_profile,
    )
    summary_path = output_root / "reference_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    for fixture_label, payload in primary_trajectories.items():
        write_json(trajectories_root / f"{fixture_label}.json", payload)
    print(f"GATHER_ESCAPE_REFERENCE_SUMMARY={summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    decision = str(summary.get("decision_outcome", ""))
    return 0 if decision in {"unlock_sandbox_v2_distillation", "sandbox_v2_corridor_completion"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
