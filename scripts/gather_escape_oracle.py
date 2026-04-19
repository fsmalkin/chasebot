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
DEFAULT_ESCAPE_ORACLE_HORIZON_S = 4.0
DEFAULT_ESCAPE_ORACLE_STEP_S = 0.5
DEFAULT_ESCAPE_ORACLE_MACRO_DURATION_S = 2.0
DEFAULT_ESCAPE_ORACLE_DEPTH = 2
DEFAULT_ESCAPE_ORACLE_TOP_K = 10
DEFAULT_ESCAPE_ORACLE_SWITCH_PENALTY = 0.03
DEFAULT_ESCAPE_ORACLE_STATIONARY_PENALTY = 0.05
DEFAULT_ESCAPE_ORACLE_REQUIRED_FIXTURES = 5

MIRRORED_ESCAPE_FAMILIES: tuple[str, ...] = (
    "soft_arc",
    "hard_arc",
    "reset_reflank_v2",
    "wide_reflank",
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
class EscapeSequenceResult:
    family_name: str
    macro_sequence: tuple[str, ...]
    goal_side_cleared: bool
    projection_gain: float
    lateral_gain: float
    distance_gain: float
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]
    score_key: tuple[float, float, float, float, float]
    progress_score: float
    promoting: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_escape_macro_library() -> dict[str, EscapeMacro]:
    def _macro(name: str, family_name: str, segments: list[tuple[float, float, float]]) -> EscapeMacro:
        return EscapeMacro(
            name=name,
            family_name=family_name,
            segments=tuple(EscapeMacroSegment(*item) for item in segments),
        )

    return {
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


def _apply_segment(
    *,
    x_m: float,
    y_m: float,
    yaw_rad: float,
    segment: EscapeMacroSegment,
    step_s: float,
) -> tuple[float, float, float]:
    remaining_s = max(float(segment.duration_s), 0.0)
    while remaining_s > 1.0e-9:
        dt_s = min(float(step_s), remaining_s)
        x_m += float(segment.linear_x) * math.cos(yaw_rad) * dt_s
        y_m += float(segment.linear_x) * math.sin(yaw_rad) * dt_s
        yaw_rad = normalize_angle(yaw_rad + (float(segment.angular_z) * dt_s))
        remaining_s -= dt_s
    return x_m, y_m, yaw_rad


def rollout_macro_sequence(
    robot_pose: dict[str, Any],
    macro_sequence: tuple[EscapeMacro, ...],
    *,
    step_s: float = DEFAULT_ESCAPE_ORACLE_STEP_S,
) -> dict[str, float] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    x_m, y_m, yaw_rad = robot_xyyaw
    for macro in macro_sequence:
        for segment in macro.segments:
            x_m, y_m, yaw_rad = _apply_segment(
                x_m=x_m,
                y_m=y_m,
                yaw_rad=yaw_rad,
                segment=segment,
                step_s=step_s,
            )
    return {"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)}


def evaluate_escape_sequence(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    macro_sequence: tuple[EscapeMacro, ...],
    *,
    zone=None,
    step_s: float = DEFAULT_ESCAPE_ORACLE_STEP_S,
) -> EscapeSequenceResult | None:
    zone = zone or build_zone_spec("corral_single_ball_place")
    start_snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(start_snapshot, dict):
        return None
    projected_robot_pose = rollout_macro_sequence(robot_pose, macro_sequence, step_s=step_s)
    if projected_robot_pose is None:
        return None
    projected_snapshot = pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
    if not isinstance(projected_snapshot, dict):
        return None

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
    score_key = (
        1.0 if goal_side_cleared else 0.0,
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
        projection_gain=round(projection_gain, 6),
        lateral_gain=round(lateral_gain, 6),
        distance_gain=round(distance_gain, 6),
        projected_robot_pose=projected_robot_pose,
        projected_snapshot=projected_snapshot,
        score_key=score_key,
        progress_score=round(progress_score, 6),
        promoting=goal_side_cleared,
    )


def load_pre_stage_attempt_rows(state_history_path: Path, *, attempt: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in state_history_path.read_text(encoding="utf-8").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        payload = json.loads(raw_line)
        if str(payload.get("phase")) != "pre_stage":
            continue
        if int(payload.get("attempt", -1) or -1) != int(attempt):
            continue
        rows.append(payload)
    return rows


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
    depth: int = DEFAULT_ESCAPE_ORACLE_DEPTH,
    top_k: int = DEFAULT_ESCAPE_ORACLE_TOP_K,
) -> list[EscapeSequenceResult]:
    zone = zone or build_zone_spec("corral_single_ball_place")
    macro_library = dict(macro_library or build_escape_macro_library())
    results: list[EscapeSequenceResult] = []
    macro_names = tuple(macro_library.keys())
    for sequence_names in itertools.product(macro_names, repeat=max(int(depth), 1)):
        macro_sequence = tuple(macro_library[name] for name in sequence_names)
        result = evaluate_escape_sequence(robot_pose, ball_pose, macro_sequence, zone=zone)
        if result is not None:
            results.append(result)
    results.sort(key=lambda item: (item.score_key, item.progress_score, item.macro_sequence), reverse=True)
    return results[: max(int(top_k), 1)]


def _family_projection_for_fixture(
    fixture: dict[str, Any],
    *,
    family_name: str,
    macro_library: dict[str, EscapeMacro],
    zone,
    depth: int = DEFAULT_ESCAPE_ORACLE_DEPTH,
) -> EscapeSequenceResult | None:
    allowed_names = [name for name, macro in macro_library.items() if macro.family_name == family_name]
    if not allowed_names:
        return None
    best_result: EscapeSequenceResult | None = None
    for sequence_names in itertools.product(tuple(allowed_names), repeat=max(int(depth), 1)):
        macro_sequence = tuple(macro_library[name] for name in sequence_names)
        result = evaluate_escape_sequence(
            fixture["robot_pose"],
            fixture["ball_pose"],
            macro_sequence,
            zone=zone,
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
) -> list[dict[str, Any]]:
    zone = zone or build_zone_spec("corral_single_ball_place")
    macro_library = dict(macro_library or build_escape_macro_library())
    rollups: list[dict[str, Any]] = []
    for family_name in MIRRORED_ESCAPE_FAMILIES:
        best_results = [
            _family_projection_for_fixture(
                fixture,
                family_name=family_name,
                macro_library=macro_library,
                zone=zone,
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
                "mean_lateral_gain": round(sum(item.lateral_gain for item in valid_results) / len(valid_results), 6),
                "mean_projection_gain": round(sum(item.projection_gain for item in valid_results) / len(valid_results), 6),
                "mean_distance_gain": round(sum(item.distance_gain for item in valid_results) / len(valid_results), 6),
                "best_results": [item.to_dict() for item in valid_results],
            }
        )
    rollups.sort(
        key=lambda item: (
            int(item["goal_side_clear_count"]),
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
            int(item.get("goal_side_clear_count", 0)),
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
) -> dict[str, Any]:
    zone = build_zone_spec(scenario_id)
    macro_library = build_escape_macro_library()
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
        family_rollups = aggregate_family_rollups(representative_rows, macro_library=macro_library, zone=zone)
        selected_family = select_best_escape_macro_family(family_rollups)
        trace_summary = {
            "trace_family": family_name,
            "state_history_path": str(state_history_path),
            "representative_fixture_count": len(fixture_results),
            "fixture_results": fixture_results,
            "macro_win_counts": _macro_win_counts(fixture_results),
            "family_rollups": family_rollups,
            "selected_v3_family": selected_family,
            "wave_2_gate_pass": (
                sum(1 for item in fixture_results if bool(item.get("goal_side_clear_available", False)))
                >= 4
            ),
        }
        trace_summaries.append(trace_summary)
        if family_name == DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY:
            primary_fixture_results = fixture_results

    if not primary_fixture_results and trace_summaries:
        primary_fixture_results = list(trace_summaries[0].get("fixture_results", []))

    primary_clear_count = sum(1 for item in primary_fixture_results if bool(item.get("goal_side_clear_available", False)))
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
        "primary_trace_family": DEFAULT_ESCAPE_ORACLE_PRIMARY_FAMILY,
        "required_goal_side_clear_fixtures": 4,
        "representative_fixture_count": len(primary_fixture_results),
        "primary_goal_side_clear_count": primary_clear_count,
        "wave_2_gate_pass": primary_clear_count >= 4,
        "selected_v3_family": selected_v3_family,
        "trace_summaries": trace_summaries,
    }


def _default_trace_specs() -> list[tuple[str, Path]]:
    return [
        (family_name, (REPO_ROOT / relative_path).resolve())
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
        f"- Primary trace family: `{summary.get('primary_trace_family', '')}`",
        f"- Wave 2 gate: `{summary.get('primary_goal_side_clear_count', 0)}/{summary.get('representative_fixture_count', 0)}` cleared",
        f"- Gate pass: `{bool(summary.get('wave_2_gate_pass', False))}`",
        f"- Selected `short_horizon_v3` family: `{summary.get('selected_v3_family', '') or 'none'}`",
        "",
        "## Trace Families",
        "",
    ]
    for trace_summary in summary.get("trace_summaries", []):
        lines.append(
            f"- `{trace_summary.get('trace_family', '')}` summary: "
            f"fixtures=`{trace_summary.get('representative_fixture_count', 0)}` "
            f"gate_pass=`{bool(trace_summary.get('wave_2_gate_pass', False))}` "
            f"selected_family=`{trace_summary.get('selected_v3_family', '') or 'none'}`"
        )
        for family_rollup in trace_summary.get("family_rollups", []):
            lines.append(
                f"  - family `{family_rollup.get('family_name', '')}` clear=`{family_rollup.get('goal_side_clear_count', 0)}` "
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
                f"  - `{fixture.get('fixture_label', '')}` clear_available=`{bool(fixture.get('goal_side_clear_available', False))}` "
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
    summary = build_oracle_summary(trace_specs, campaign_id=campaign_id, scenario_id=args.scenario_id)
    summary_path = output_root / "oracle_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    print(f"GATHER_ESCAPE_ORACLE_SUMMARY={summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if bool(summary.get("wave_2_gate_pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
