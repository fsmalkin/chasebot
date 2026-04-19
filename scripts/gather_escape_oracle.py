#!/usr/bin/env python3
"""Truth-state oracle for pre-contact gather escape sequences."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import write_json
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import pre_stage_arrival_snapshot
from gather_mission_helpers import world_pose_xyyaw
from gather_mission_helpers import build_zone_spec


DEFAULT_ESCAPE_ORACLE_CAMPAIGNS: tuple[tuple[str, str], ...] = (
    (
        "baseline",
        "artifacts/session/live_plus45_baseline_shv1_compare_20260419/gather_mission_repeatability/campaign_run_summary.json",
    ),
    (
        "short_horizon_v1",
        "artifacts/session/live_plus45_short_horizon_v1_yawgate_20260419/gather_mission_repeatability/campaign_run_summary.json",
    ),
    (
        "short_horizon_v2",
        "artifacts/session/live_plus45_short_horizon_v2_20260419/gather_mission_repeatability/campaign_run_summary.json",
    ),
)
DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY = "short_horizon_v2"
DEFAULT_ESCAPE_ORACLE_CONTROL_PROFILE = "control_v1"
DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE = "deep_escape_v1"
DEFAULT_ESCAPE_ORACLE_CONTROL_HORIZON_S = 4.0
DEFAULT_ESCAPE_ORACLE_DEEP_HORIZON_S = 8.0
DEFAULT_ESCAPE_ORACLE_STEP_S = 0.5
DEFAULT_ESCAPE_ORACLE_CONTROL_DEPTH = 2
DEFAULT_ESCAPE_ORACLE_DEEP_DEPTH = 3
DEFAULT_ESCAPE_ORACLE_TOP_K = 10
DEFAULT_ESCAPE_ORACLE_SWITCH_PENALTY = 0.03
DEFAULT_ESCAPE_ORACLE_STATIONARY_PENALTY = 0.05
DEFAULT_ESCAPE_ORACLE_REQUIRED_FIXTURES = 5
DEFAULT_ESCAPE_ORACLE_REQUIRED_STABLE_CLEARS = 4
DEFAULT_ESCAPE_ORACLE_STABLE_CLEAR_WINDOW_S = 1.0
DEFAULT_ESCAPE_ORACLE_NEAR_CLEAR_MIN_LATERAL_GAIN_M = 0.45
DEFAULT_ESCAPE_ORACLE_NEAR_CLEAR_MIN_PROJECTION_GAIN_M = 0.20

MIRRORED_ESCAPE_FAMILIES: tuple[str, ...] = (
    "soft_arc",
    "hard_arc",
    "reset_reflank_v2",
    "wide_reflank",
    "wide_reflank_v3",
    "retreat_pivot",
    "loop_around",
    "clear_then_realign",
    "pivot_reset",
)


@dataclass(frozen=True)
class EscapeMacroSegment:
    linear_x: float
    angular_z: float
    duration_s: float


@dataclass(frozen=True)
class EscapeMacro:
    name: str
    family_name: str
    segments: tuple[EscapeMacroSegment, ...]

    @property
    def has_stationary_segment(self) -> bool:
        return any(abs(float(item.linear_x)) < 1.0e-9 for item in self.segments)


@dataclass(frozen=True)
class EscapeSearchProfile:
    name: str
    horizon_s: float
    step_s: float
    depth: int
    top_k: int
    stable_clear_window_s: float
    include_deep_macros: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EscapeSequenceResult:
    family_name: str
    macro_sequence: tuple[str, ...]
    goal_side_cleared: bool
    stable_goal_side_cleared: bool
    feasibility_class: str
    projection_gain: float
    lateral_gain: float
    distance_gain: float
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]
    total_rollout_s: float
    score_key: tuple[float, float, float, float, float]
    progress_score: float
    promoting: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_escape_search_profile(search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE) -> EscapeSearchProfile:
    normalized = str(search_profile or "").strip() or DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE
    if normalized == DEFAULT_ESCAPE_ORACLE_CONTROL_PROFILE:
        return EscapeSearchProfile(
            name=DEFAULT_ESCAPE_ORACLE_CONTROL_PROFILE,
            horizon_s=DEFAULT_ESCAPE_ORACLE_CONTROL_HORIZON_S,
            step_s=DEFAULT_ESCAPE_ORACLE_STEP_S,
            depth=DEFAULT_ESCAPE_ORACLE_CONTROL_DEPTH,
            top_k=DEFAULT_ESCAPE_ORACLE_TOP_K,
            stable_clear_window_s=DEFAULT_ESCAPE_ORACLE_STABLE_CLEAR_WINDOW_S,
            include_deep_macros=False,
        )
    if normalized == DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE:
        return EscapeSearchProfile(
            name=DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
            horizon_s=DEFAULT_ESCAPE_ORACLE_DEEP_HORIZON_S,
            step_s=DEFAULT_ESCAPE_ORACLE_STEP_S,
            depth=DEFAULT_ESCAPE_ORACLE_DEEP_DEPTH,
            top_k=DEFAULT_ESCAPE_ORACLE_TOP_K,
            stable_clear_window_s=DEFAULT_ESCAPE_ORACLE_STABLE_CLEAR_WINDOW_S,
            include_deep_macros=True,
        )
    raise ValueError(f"Unsupported search profile: {search_profile}")


def build_escape_macro_library(search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE) -> dict[str, EscapeMacro]:
    profile = resolve_escape_search_profile(search_profile)

    def _macro(name: str, family_name: str, segments: list[tuple[float, float, float]]) -> EscapeMacro:
        return EscapeMacro(
            name=name,
            family_name=family_name,
            segments=tuple(EscapeMacroSegment(*item) for item in segments),
        )

    macro_library = {
        "reverse_straight": _macro("reverse_straight", "straight", [(-0.18, 0.0, 2.0)]),
        "reverse_arc_left_soft": _macro("reverse_arc_left_soft", "soft_arc", [(-0.18, 0.25, 2.0)]),
        "reverse_arc_right_soft": _macro("reverse_arc_right_soft", "soft_arc", [(-0.18, -0.25, 2.0)]),
        "reverse_arc_left_hard": _macro("reverse_arc_left_hard", "hard_arc", [(-0.18, 0.55, 2.0)]),
        "reverse_arc_right_hard": _macro("reverse_arc_right_hard", "hard_arc", [(-0.18, -0.55, 2.0)]),
        "reset_reflank_left_v2": _macro(
            "reset_reflank_left_v2",
            "reset_reflank_v2",
            [(-0.18, 0.8, 1.0), (-0.18, 0.25, 1.0)],
        ),
        "reset_reflank_right_v2": _macro(
            "reset_reflank_right_v2",
            "reset_reflank_v2",
            [(-0.18, -0.8, 1.0), (-0.18, -0.25, 1.0)],
        ),
        "wide_reflank_left": _macro(
            "wide_reflank_left",
            "wide_reflank",
            [(-0.18, 1.1, 1.0), (-0.18, 0.55, 1.0)],
        ),
        "wide_reflank_right": _macro(
            "wide_reflank_right",
            "wide_reflank",
            [(-0.18, -1.1, 1.0), (-0.18, -0.55, 1.0)],
        ),
        "pivot_reset_left": _macro(
            "pivot_reset_left",
            "pivot_reset",
            [(0.0, 1.2, 1.0), (-0.18, 0.65, 1.0)],
        ),
        "pivot_reset_right": _macro(
            "pivot_reset_right",
            "pivot_reset",
            [(0.0, -1.2, 1.0), (-0.18, -0.65, 1.0)],
        ),
    }
    if profile.include_deep_macros:
        macro_library.update(
            {
                "wide_reflank_left_v3": _macro(
                    "wide_reflank_left_v3",
                    "wide_reflank_v3",
                    [(-0.18, 1.30, 1.5), (-0.18, 0.85, 1.0), (-0.18, 0.35, 1.0)],
                ),
                "wide_reflank_right_v3": _macro(
                    "wide_reflank_right_v3",
                    "wide_reflank_v3",
                    [(-0.18, -1.30, 1.5), (-0.18, -0.85, 1.0), (-0.18, -0.35, 1.0)],
                ),
                "retreat_pivot_left": _macro(
                    "retreat_pivot_left",
                    "retreat_pivot",
                    [(-0.10, 1.15, 1.0), (0.0, 1.35, 0.5), (-0.18, 0.95, 1.0), (-0.18, 0.30, 1.0)],
                ),
                "retreat_pivot_right": _macro(
                    "retreat_pivot_right",
                    "retreat_pivot",
                    [(-0.10, -1.15, 1.0), (0.0, -1.35, 0.5), (-0.18, -0.95, 1.0), (-0.18, -0.30, 1.0)],
                ),
                "loop_around_left": _macro(
                    "loop_around_left",
                    "loop_around",
                    [(-0.18, 1.20, 1.5), (-0.18, 0.80, 1.0), (-0.14, -0.40, 1.0)],
                ),
                "loop_around_right": _macro(
                    "loop_around_right",
                    "loop_around",
                    [(-0.18, -1.20, 1.5), (-0.18, -0.80, 1.0), (-0.14, 0.40, 1.0)],
                ),
                "clear_then_realign_left": _macro(
                    "clear_then_realign_left",
                    "clear_then_realign",
                    [(-0.18, 1.10, 1.5), (-0.18, 0.45, 1.0), (-0.16, -0.20, 1.0)],
                ),
                "clear_then_realign_right": _macro(
                    "clear_then_realign_right",
                    "clear_then_realign",
                    [(-0.18, -1.10, 1.5), (-0.18, -0.45, 1.0), (-0.16, 0.20, 1.0)],
                ),
            }
        )
    return macro_library


def rollout_macro_sequence(
    robot_pose: dict[str, Any],
    macro_sequence: tuple[EscapeMacro, ...],
    *,
    step_s: float = DEFAULT_ESCAPE_ORACLE_STEP_S,
    horizon_s: float = DEFAULT_ESCAPE_ORACLE_CONTROL_HORIZON_S,
) -> list[dict[str, float]] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    x_m, y_m, yaw_rad = robot_xyyaw
    elapsed_s = 0.0
    samples: list[dict[str, float]] = []
    for macro in macro_sequence:
        for segment in macro.segments:
            remaining_s = max(float(segment.duration_s), 0.0)
            while remaining_s > 1.0e-9 and elapsed_s < float(horizon_s) - 1.0e-9:
                dt_s = min(float(step_s), remaining_s, float(horizon_s) - elapsed_s)
                if dt_s <= 1.0e-9:
                    break
                x_m += float(segment.linear_x) * math.cos(yaw_rad) * dt_s
                y_m += float(segment.linear_x) * math.sin(yaw_rad) * dt_s
                yaw_rad = normalize_angle(yaw_rad + (float(segment.angular_z) * dt_s))
                elapsed_s += dt_s
                remaining_s -= dt_s
                samples.append(
                    {
                        "elapsed_s": round(elapsed_s, 6),
                        "x": round(x_m, 6),
                        "y": round(y_m, 6),
                        "yaw": round(yaw_rad, 6),
                    }
                )
            if elapsed_s >= float(horizon_s) - 1.0e-9:
                break
        if elapsed_s >= float(horizon_s) - 1.0e-9:
            break
    return samples


def classify_escape_result(
    *,
    stable_goal_side_cleared: bool,
    lateral_gain: float,
    projection_gain: float,
) -> str:
    if stable_goal_side_cleared:
        return "clearable"
    if (
        float(lateral_gain) >= DEFAULT_ESCAPE_ORACLE_NEAR_CLEAR_MIN_LATERAL_GAIN_M
        and float(projection_gain) >= DEFAULT_ESCAPE_ORACLE_NEAR_CLEAR_MIN_PROJECTION_GAIN_M
    ):
        return "near_clear"
    return "not_clearable"


def evaluate_escape_sequence(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    macro_sequence: tuple[EscapeMacro, ...],
    *,
    zone=None,
    search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
) -> EscapeSequenceResult | None:
    profile = resolve_escape_search_profile(search_profile)
    zone = zone or build_zone_spec("corral_single_ball_place")
    start_snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(start_snapshot, dict):
        return None
    trajectory_samples = rollout_macro_sequence(
        robot_pose,
        macro_sequence,
        step_s=profile.step_s,
        horizon_s=profile.horizon_s,
    )
    if not trajectory_samples:
        return None
    projected_robot_pose = {
        "x": float(trajectory_samples[-1]["x"]),
        "y": float(trajectory_samples[-1]["y"]),
        "yaw": float(trajectory_samples[-1]["yaw"]),
    }
    projected_snapshot = pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
    if not isinstance(projected_snapshot, dict):
        return None
    total_rollout_s = float(trajectory_samples[-1]["elapsed_s"])
    stable_window_start_s = max(total_rollout_s - float(profile.stable_clear_window_s), 0.0)
    stable_goal_side_cleared = True
    stable_window_sample_count = 0
    for sample in trajectory_samples:
        if float(sample["elapsed_s"]) + 1.0e-9 < stable_window_start_s:
            continue
        stable_window_sample_count += 1
        sample_snapshot = pre_stage_arrival_snapshot(
            {"x": sample["x"], "y": sample["y"], "yaw": sample["yaw"]},
            ball_pose,
            zone=zone,
        )
        if bool((sample_snapshot or {}).get("robot_on_goal_side", True)):
            stable_goal_side_cleared = False
            break
    if stable_window_sample_count <= 0:
        stable_goal_side_cleared = False

    start_projection = float(start_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    start_lateral = float(start_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    start_distance = float(start_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    end_projection = float(projected_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    end_lateral = float(projected_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    end_distance = float(projected_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    projection_gain = start_projection - end_projection
    lateral_gain = start_lateral - end_lateral
    distance_gain = start_distance - end_distance
    switch_penalty = DEFAULT_ESCAPE_ORACLE_SWITCH_PENALTY if len({item.name for item in macro_sequence}) > 1 else 0.0
    stationary_penalty = (
        DEFAULT_ESCAPE_ORACLE_STATIONARY_PENALTY
        if any(item.has_stationary_segment for item in macro_sequence)
        else 0.0
    )
    goal_side_cleared = not bool(projected_snapshot.get("robot_on_goal_side", False))
    feasibility_class = classify_escape_result(
        stable_goal_side_cleared=stable_goal_side_cleared,
        lateral_gain=lateral_gain,
        projection_gain=projection_gain,
    )
    score_key = (
        1.0 if stable_goal_side_cleared else 0.0,
        round(lateral_gain, 6),
        round(projection_gain, 6),
        round(distance_gain, 6),
        round(-(switch_penalty + stationary_penalty), 6),
    )
    progress_score = (
        (score_key[0] * 1000.0)
        + (score_key[1] * 100.0)
        + (score_key[2] * 10.0)
        + score_key[3]
        + score_key[4]
    )
    return EscapeSequenceResult(
        family_name=str(macro_sequence[0].family_name),
        macro_sequence=tuple(item.name for item in macro_sequence),
        goal_side_cleared=goal_side_cleared,
        stable_goal_side_cleared=stable_goal_side_cleared,
        feasibility_class=feasibility_class,
        projection_gain=round(projection_gain, 6),
        lateral_gain=round(lateral_gain, 6),
        distance_gain=round(distance_gain, 6),
        projected_robot_pose=projected_robot_pose,
        projected_snapshot=projected_snapshot,
        total_rollout_s=round(total_rollout_s, 6),
        score_key=score_key,
        progress_score=round(progress_score, 6),
        promoting=stable_goal_side_cleared,
    )


def load_pre_stage_attempt_rows(state_history_path: Path, *, attempt: int = 0) -> list[dict[str, Any]]:
    attempt_rows: dict[int, list[dict[str, Any]]] = {}
    for raw_line in state_history_path.read_text(encoding="utf-8").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        payload = json.loads(raw_line)
        if str(payload.get("phase")) != "pre_stage":
            continue
        raw_attempt = payload.get("attempt", -1)
        parsed_attempt = -1 if raw_attempt is None else int(raw_attempt)
        if parsed_attempt < 0:
            continue
        attempt_rows.setdefault(parsed_attempt, []).append(payload)
    requested_attempt = int(attempt)
    if requested_attempt in attempt_rows:
        return attempt_rows[requested_attempt]
    if requested_attempt == 0 and attempt_rows:
        earliest_attempt = min(attempt_rows.keys())
        return attempt_rows[earliest_attempt]
    return []


def _pick_unique_index(anchor_index: int, *, used: set[int], row_count: int) -> int:
    anchor_index = max(0, min(int(anchor_index), max(row_count - 1, 0)))
    if anchor_index not in used:
        used.add(anchor_index)
        return anchor_index
    for offset in range(1, row_count):
        lower = anchor_index - offset
        upper = anchor_index + offset
        if lower >= 0 and lower not in used:
            used.add(lower)
            return lower
        if upper < row_count and upper not in used:
            used.add(upper)
            return upper
    return anchor_index


def select_representative_fixture_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    row_count = len(rows)
    post_yaw_gate_index = next(
        (
            index
            for index, row in enumerate(rows)
            if float(((row.get("pre_stage") or {}).get("yaw_error_deg", 0.0)) or 0.0) <= 45.0
        ),
        0,
    )
    remaining = max(row_count - 1 - post_yaw_gate_index, 0)
    anchor_indices = (
        post_yaw_gate_index,
        post_yaw_gate_index + round(remaining * 0.25),
        post_yaw_gate_index + round(remaining * 0.50),
        post_yaw_gate_index + round(remaining * 0.75),
        row_count - 1,
    )
    labels = (
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    )
    used: set[int] = set()
    fixtures: list[dict[str, Any]] = []
    for label, anchor_index in zip(labels, anchor_indices):
        resolved_index = _pick_unique_index(anchor_index, used=used, row_count=row_count)
        row = dict(rows[resolved_index])
        row["fixture_label"] = label
        row["fixture_index"] = resolved_index
        fixtures.append(row)
    return fixtures


def search_escape_sequences(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone=None,
    macro_library: dict[str, EscapeMacro] | None = None,
    search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
) -> list[EscapeSequenceResult]:
    profile = resolve_escape_search_profile(search_profile)
    zone = zone or build_zone_spec("corral_single_ball_place")
    macro_library = dict(macro_library or build_escape_macro_library(profile.name))
    results: list[EscapeSequenceResult] = []
    macro_names = tuple(macro_library.keys())
    for sequence_names in itertools.product(macro_names, repeat=max(int(profile.depth), 1)):
        macro_sequence = tuple(macro_library[name] for name in sequence_names)
        result = evaluate_escape_sequence(
            robot_pose,
            ball_pose,
            macro_sequence,
            zone=zone,
            search_profile=profile.name,
        )
        if result is not None:
            results.append(result)
    results.sort(key=lambda item: (item.score_key, item.progress_score, item.macro_sequence), reverse=True)
    return results[: max(int(profile.top_k), 1)]


def _family_projection_for_fixture(
    fixture: dict[str, Any],
    *,
    family_name: str,
    macro_library: dict[str, EscapeMacro],
    zone,
    search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
) -> EscapeSequenceResult | None:
    profile = resolve_escape_search_profile(search_profile)
    allowed_names = [name for name, macro in macro_library.items() if macro.family_name == family_name]
    if not allowed_names:
        return None
    best_result: EscapeSequenceResult | None = None
    for sequence_names in itertools.product(tuple(allowed_names), repeat=max(int(profile.depth), 1)):
        macro_sequence = tuple(macro_library[name] for name in sequence_names)
        result = evaluate_escape_sequence(
            fixture["robot_pose"],
            fixture["ball_pose"],
            macro_sequence,
            zone=zone,
            search_profile=profile.name,
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


def aggregate_family_rollups(
    representative_fixtures: list[dict[str, Any]],
    *,
    macro_library: dict[str, EscapeMacro] | None = None,
    zone=None,
    search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
) -> list[dict[str, Any]]:
    profile = resolve_escape_search_profile(search_profile)
    zone = zone or build_zone_spec("corral_single_ball_place")
    macro_library = dict(macro_library or build_escape_macro_library(profile.name))
    rollups: list[dict[str, Any]] = []
    for family_name in MIRRORED_ESCAPE_FAMILIES:
        best_results = [
            _family_projection_for_fixture(
                fixture,
                family_name=family_name,
                macro_library=macro_library,
                zone=zone,
                search_profile=profile.name,
            )
            for fixture in representative_fixtures
        ]
        valid_results = [item for item in best_results if isinstance(item, EscapeSequenceResult)]
        if not valid_results:
            continue
        rollups.append(
            {
                "family_name": family_name,
                "fixture_count": len(valid_results),
                "goal_side_clear_count": sum(1 for item in valid_results if item.goal_side_cleared),
                "stable_goal_side_clear_count": sum(1 for item in valid_results if item.stable_goal_side_cleared),
                "near_clear_count": sum(1 for item in valid_results if item.feasibility_class == "near_clear"),
                "mean_lateral_gain": round(sum(item.lateral_gain for item in valid_results) / len(valid_results), 6),
                "mean_projection_gain": round(sum(item.projection_gain for item in valid_results) / len(valid_results), 6),
                "mean_distance_gain": round(sum(item.distance_gain for item in valid_results) / len(valid_results), 6),
                "best_results": [item.to_dict() for item in valid_results],
            }
        )
    rollups.sort(
        key=lambda item: (
            int(item["stable_goal_side_clear_count"]),
            int(item["near_clear_count"]),
            float(item["mean_lateral_gain"]),
            float(item["mean_projection_gain"]),
            str(item["family_name"]),
        ),
        reverse=True,
    )
    return rollups


def select_best_escape_macro_family(family_rollups: list[dict[str, Any]]) -> str:
    if not family_rollups:
        return ""
    best = max(
        family_rollups,
        key=lambda item: (
            int(item.get("stable_goal_side_clear_count", 0)),
            int(item.get("near_clear_count", 0)),
            float(item.get("mean_lateral_gain", 0.0)),
            float(item.get("mean_projection_gain", 0.0)),
            str(item.get("family_name", "")),
        ),
    )
    return str(best.get("family_name", ""))


def _macro_win_counts(fixture_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    win_counts: dict[str, int] = {}
    for fixture in fixture_results:
        top_sequences = fixture.get("top_sequences", [])
        if not isinstance(top_sequences, list) or not top_sequences:
            continue
        best = top_sequences[0]
        macro_sequence = best.get("macro_sequence", [])
        if isinstance(macro_sequence, list) and macro_sequence:
            macro_name = str(macro_sequence[0])
            win_counts[macro_name] = win_counts.get(macro_name, 0) + 1
    return [
        {"macro_name": name, "win_count": win_counts[name]}
        for name in sorted(win_counts.keys(), key=lambda item: (-win_counts[item], item))
    ]


def build_oracle_summary(
    trace_specs: list[tuple[str, Path]],
    *,
    campaign_id: str,
    scenario_id: str = "corral_single_ball_place",
    search_profile: str = DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
) -> dict[str, Any]:
    profile = resolve_escape_search_profile(search_profile)
    zone = build_zone_spec(scenario_id)
    macro_library = build_escape_macro_library(profile.name)
    trace_summaries: list[dict[str, Any]] = []
    primary_fixture_results: list[dict[str, Any]] = []

    for family_name, state_history_path in trace_specs:
        rows = load_pre_stage_attempt_rows(state_history_path, attempt=0)
        representative_rows = select_representative_fixture_rows(rows)
        fixture_results: list[dict[str, Any]] = []
        for fixture in representative_rows:
            robot_pose = fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {}
            ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
            top_sequences = search_escape_sequences(
                robot_pose,
                ball_pose,
                zone=zone,
                macro_library=macro_library,
                search_profile=profile.name,
            )
            top_payload = [item.to_dict() for item in top_sequences]
            best_result = top_sequences[0] if top_sequences else None
            pre_stage_snapshot = fixture.get("pre_stage", {}) if isinstance(fixture.get("pre_stage"), dict) else {}
            fixture_results.append(
                {
                    "fixture_label": str(fixture.get("fixture_label", "")),
                    "fixture_index": int(fixture.get("fixture_index", 0) or 0),
                    "generated_utc": str(fixture.get("generated_utc", "")),
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "pre_stage_snapshot": pre_stage_snapshot,
                    "top_sequences": top_payload,
                    "goal_side_clear_available": bool(best_result.goal_side_cleared) if best_result is not None else False,
                    "stable_goal_side_clear_available": (
                        bool(best_result.stable_goal_side_cleared) if best_result is not None else False
                    ),
                    "feasibility_class": (
                        str(best_result.feasibility_class) if best_result is not None else "not_clearable"
                    ),
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
            )
        stable_clear_count = sum(1 for item in fixture_results if bool(item.get("stable_goal_side_clear_available", False)))
        near_clear_count = sum(1 for item in fixture_results if str(item.get("feasibility_class", "")) == "near_clear")
        family_rollups = aggregate_family_rollups(
            representative_rows,
            macro_library=macro_library,
            zone=zone,
            search_profile=profile.name,
        )
        selected_family = select_best_escape_macro_family(family_rollups)
        trace_summary = {
            "trace_family": family_name,
            "search_profile": profile.name,
            "state_history_path": str(state_history_path),
            "representative_fixture_count": len(fixture_results),
            "goal_side_clear_count": sum(1 for item in fixture_results if bool(item.get("goal_side_clear_available", False))),
            "stable_goal_side_clear_count": stable_clear_count,
            "near_clear_count": near_clear_count,
            "feasibility_class": (
                "clearable"
                if stable_clear_count >= DEFAULT_ESCAPE_ORACLE_REQUIRED_STABLE_CLEARS
                else "near_clear"
                if near_clear_count > 0
                else "not_clearable"
            ),
            "fixture_results": fixture_results,
            "macro_win_counts": _macro_win_counts(fixture_results),
            "family_rollups": family_rollups,
            "selected_v3_family": selected_family,
            "wave_2_gate_pass": stable_clear_count >= DEFAULT_ESCAPE_ORACLE_REQUIRED_STABLE_CLEARS,
        }
        trace_summaries.append(trace_summary)
        if family_name == DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY:
            primary_fixture_results = fixture_results

    if not primary_fixture_results and trace_summaries:
        primary_fixture_results = list(trace_summaries[0].get("fixture_results", []))

    primary_clear_count = sum(1 for item in primary_fixture_results if bool(item.get("goal_side_clear_available", False)))
    primary_stable_clear_count = sum(
        1 for item in primary_fixture_results if bool(item.get("stable_goal_side_clear_available", False))
    )
    primary_near_clear_count = sum(1 for item in primary_fixture_results if str(item.get("feasibility_class", "")) == "near_clear")
    selected_primary_rollups = next(
        (
            item.get("family_rollups", [])
            for item in trace_summaries
            if str(item.get("trace_family")) == DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY
        ),
        trace_summaries[0].get("family_rollups", []) if trace_summaries else [],
    )
    selected_v3_family = select_best_escape_macro_family(selected_primary_rollups)
    return {
        "generated_utc": _utc_now_iso(),
        "type": "gather_escape_oracle",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "search_profile": profile.name,
        "search_profile_config": profile.to_dict(),
        "primary_trace_family": DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY,
        "required_goal_side_clear_fixtures": DEFAULT_ESCAPE_ORACLE_REQUIRED_STABLE_CLEARS,
        "representative_fixture_count": len(primary_fixture_results),
        "primary_goal_side_clear_count": primary_clear_count,
        "stable_goal_side_clear_count": primary_stable_clear_count,
        "near_clear_count": primary_near_clear_count,
        "feasibility_class": (
            "clearable"
            if primary_stable_clear_count >= DEFAULT_ESCAPE_ORACLE_REQUIRED_STABLE_CLEARS
            else "near_clear"
            if primary_near_clear_count > 0
            else "not_clearable"
        ),
        "wave_2_gate_pass": primary_stable_clear_count >= DEFAULT_ESCAPE_ORACLE_REQUIRED_STABLE_CLEARS,
        "selected_v3_family": selected_v3_family,
        "trace_summaries": trace_summaries,
    }


def _default_trace_specs() -> list[tuple[str, Path]]:
    return [
        (
            family_name,
            _state_history_path_from_campaign_summary((REPO_ROOT / relative_path).resolve()),
        )
        for family_name, relative_path in DEFAULT_ESCAPE_ORACLE_CAMPAIGNS
    ]


def _state_history_path_from_campaign_summary(summary_path: Path) -> Path:
    summary = read_json(summary_path)
    runs = summary.get("runs", []) if isinstance(summary.get("runs"), list) else []
    if not runs:
        raise ValueError(f"Campaign summary has no runs: {summary_path}")
    mission_root = runs[0].get("mission_root", "")
    if not mission_root:
        raise ValueError(f"Campaign summary is missing mission_root for first run: {summary_path}")
    return Path(mission_root).resolve() / "state_history.jsonl"


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


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Escape Oracle Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Scenario: `{summary.get('scenario_id', '')}`",
        f"- Search profile: `{summary.get('search_profile', '')}`",
        f"- Primary trace family: `{summary.get('primary_trace_family', '')}`",
        f"- Wave 2 gate: `{summary.get('stable_goal_side_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}` stable clears",
        f"- Gate pass: `{bool(summary.get('wave_2_gate_pass', False))}`",
        f"- Feasibility class: `{summary.get('feasibility_class', '')}`",
        f"- Selected `short_horizon_v3` family: `{summary.get('selected_v3_family', '') or 'none'}`",
        "",
        "## Trace Families",
        "",
    ]
    for trace_summary in summary.get("trace_summaries", []):
        lines.append(
            f"- `{trace_summary.get('trace_family', '')}` summary: "
            f"profile=`{trace_summary.get('search_profile', '')}` "
            f"fixtures=`{trace_summary.get('representative_fixture_count', 0)}` "
            f"stable_clear=`{trace_summary.get('stable_goal_side_clear_count', 0)}` "
            f"near_clear=`{trace_summary.get('near_clear_count', 0)}` "
            f"feasibility=`{trace_summary.get('feasibility_class', '')}` "
            f"gate_pass=`{bool(trace_summary.get('wave_2_gate_pass', False))}` "
            f"selected_family=`{trace_summary.get('selected_v3_family', '') or 'none'}`"
        )
        for family_rollup in trace_summary.get("family_rollups", []):
            lines.append(
                f"  - family `{family_rollup.get('family_name', '')}` stable_clear=`{family_rollup.get('stable_goal_side_clear_count', 0)}` "
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
                f"  - `{fixture.get('fixture_label', '')}` stable_clear_available=`{bool(fixture.get('stable_goal_side_clear_available', False))}` "
                f"feasibility=`{fixture.get('feasibility_class', '')}` "
                f"best=`{macro_sequence or 'none'}` "
                f"end_projection=`{float(fixture.get('end_projection_m', 0.0)):.3f}` "
                f"end_lateral=`{float(fixture.get('end_lateral_error_m', 0.0)):.3f}` "
                f"end_distance=`{float(fixture.get('end_pre_stage_distance_m', 0.0)):.3f}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a truth-state oracle over gather pre-stage escape traces.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument(
        "--search-profile",
        default=DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE,
        choices=(DEFAULT_ESCAPE_ORACLE_CONTROL_PROFILE, DEFAULT_ESCAPE_ORACLE_DEFAULT_PROFILE),
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
    campaign_id = str(args.campaign_id or "").strip() or current_utc_stamp()
    output_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_escape_oracle")
    trace_specs = _resolve_trace_specs_from_args(args)
    summary = build_oracle_summary(
        trace_specs,
        campaign_id=campaign_id,
        scenario_id=args.scenario_id,
        search_profile=args.search_profile,
    )
    summary_path = output_root / "oracle_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    print(f"GATHER_ESCAPE_ORACLE_SUMMARY={summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if bool(summary.get("wave_2_gate_pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
