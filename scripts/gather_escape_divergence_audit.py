#!/usr/bin/env python3
"""Artifact-first divergence audit for gather pre-stage escape behavior."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any

import gather_escape_feasibility_audit as feasibility
import gather_escape_oracle as oracle
import gather_escape_sandbox as sandbox
from gather_mission_helpers import DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M
from gather_mission_helpers import build_zone_spec
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import world_pose_xyyaw
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import write_json


DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CAMPAIGN_SUMMARY = (
    REPO_ROOT
    / "artifacts"
    / "session"
    / "live_plus45_short_horizon_v2_20260419"
    / "gather_mission_repeatability"
    / "campaign_run_summary.json"
)
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_RUN_INDEX = 0
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID = "corral_single_ball_place"
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_PRIMARY_FAMILY = "short_horizon_v2"
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_HORIZON_S = feasibility.DEFAULT_ESCAPE_FEASIBILITY_AUDIT_HORIZON_S
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_ALIGNMENT_TIME_MAX_DELTA_S = 0.75
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_ALIGNMENT_POSE_MAX_DELTA_M = 0.90
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_TURN_REALIZATION_MIN_RATIO = 0.70
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_MIN_WRONG_SIGN_YAW_RAD = 0.15
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CONTACT_GAIN_RATIO_MAX = 0.50
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_EARLY_PROGRESS_GAIN_M = 0.20
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_BALL_STATIC_MAX_MOTION_M = 0.03
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_EARLY_INTERFERENCE_BALL_MOTION_M = 0.03
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_EARLY_INTERFERENCE_CLEARANCE_MARGIN_M = 0.08
DEFAULT_ESCAPE_DIVERGENCE_AUDIT_REQUIRED_DOMINANT_FIXTURES = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        payload = json.loads(raw_line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _number(value: Any, *, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return float(numeric)


def _sign(value: float, *, eps: float = 1.0e-6) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _distance_xy(pose_a: dict[str, Any], pose_b: dict[str, Any]) -> float | None:
    xy_a = world_pose_xyyaw(pose_a)
    xy_b = world_pose_xyyaw(pose_b)
    if xy_a is None or xy_b is None:
        return None
    ax_m, ay_m, _ = xy_a
    bx_m, by_m, _ = xy_b
    return math.hypot(ax_m - bx_m, ay_m - by_m)


def _quat_to_yaw(quaternion: dict[str, Any]) -> float | None:
    qx = _number(quaternion.get("x"))
    qy = _number(quaternion.get("y"))
    qz = _number(quaternion.get("z"))
    qw = _number(quaternion.get("w"))
    if qx is None or qy is None or qz is None or qw is None:
        return None
    siny_cosp = 2.0 * ((qw * qz) + (qx * qy))
    cosy_cosp = 1.0 - 2.0 * ((qy * qy) + (qz * qz))
    return math.atan2(siny_cosp, cosy_cosp)


def _truth_entity_to_world_pose(payload: Any) -> dict[str, float] | None:
    if not isinstance(payload, dict):
        return None
    position = payload.get("position", {})
    if not isinstance(position, dict):
        position = payload
    x_m = _number(position.get("x"))
    y_m = _number(position.get("y"))
    if x_m is None or y_m is None:
        return None
    yaw_rad = _number(payload.get("yaw"))
    if yaw_rad is None:
        orientation = payload.get("orientation", {})
        if isinstance(orientation, dict):
            yaw_rad = _quat_to_yaw(orientation)
    return {
        "x": round(float(x_m), 6),
        "y": round(float(y_m), 6),
        "yaw": round(float(yaw_rad or 0.0), 6),
    }


def _truth_sample_robot_pose(sample: dict[str, Any]) -> dict[str, float] | None:
    return _truth_entity_to_world_pose(sample.get("robot_truth_pose"))


def _truth_sample_ball_pose(sample: dict[str, Any], *, fallback_ball_pose: dict[str, Any] | None = None) -> dict[str, float] | None:
    pose = _truth_entity_to_world_pose(sample.get("true_target_pose"))
    if pose is not None:
        return pose
    if isinstance(sample.get("target_poses_by_name"), dict):
        for value in sample["target_poses_by_name"].values():
            pose = _truth_entity_to_world_pose(value)
            if pose is not None:
                return pose
    if isinstance(fallback_ball_pose, dict):
        xy_yaw = world_pose_xyyaw(fallback_ball_pose)
        if xy_yaw is not None:
            x_m, y_m, yaw_rad = xy_yaw
            return {"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)}
    return None


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if float(denominator) <= 1.0e-9:
        return None
    return round(float(numerator) / float(denominator), 6)


def _candidate_anchor_from_record(record: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    timestamp_utc = _parse_utc(record.get("timestamp_utc"))
    t_s = _number(record.get("t_s"))
    if timestamp_utc is None or t_s is None:
        return None
    return {
        "source": source,
        "timestamp_utc": timestamp_utc.isoformat(),
        "t_s": round(float(t_s), 6),
    }


def extract_timeline_utc_anchor(
    timeline_payload: dict[str, Any],
    timeline_event_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    events = timeline_payload.get("events", [])
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict):
                candidate = _candidate_anchor_from_record(event, source="timeline_json_event")
                if candidate is not None:
                    candidates.append(candidate)
    for row in timeline_event_rows:
        if not isinstance(row, dict):
            continue
        candidate = _candidate_anchor_from_record(row, source="timeline_events_jsonl")
        if candidate is not None:
            candidates.append(candidate)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (_parse_utc(item.get("timestamp_utc")) or datetime.max.replace(tzinfo=timezone.utc)))
    return candidates[0]


def resolve_run_artifact_paths(campaign_summary_path: Path, *, run_index: int = DEFAULT_ESCAPE_DIVERGENCE_AUDIT_RUN_INDEX) -> dict[str, Any]:
    summary = read_json(campaign_summary_path)
    runs = summary.get("runs", []) if isinstance(summary.get("runs"), list) else []
    if not runs:
        raise ValueError(f"Campaign summary has no runs: {campaign_summary_path}")
    resolved_index = int(run_index)
    if resolved_index < 0 or resolved_index >= len(runs):
        raise IndexError(f"Run index {run_index} is out of range for {campaign_summary_path}")
    run = runs[resolved_index]
    if not isinstance(run, dict):
        raise ValueError(f"Campaign run at index {run_index} is not a mapping")
    mission_root = Path(str(run.get("mission_root", "") or "")).resolve()
    if not mission_root.exists():
        raise FileNotFoundError(f"Mission root does not exist: {mission_root}")
    session_id = str(run.get("session_id", "") or "").strip()
    if not session_id:
        parts = mission_root.parts
        try:
            session_id = parts[parts.index("session") + 1]
        except Exception as exc:
            raise ValueError(f"Unable to resolve session_id from {mission_root}") from exc
    session_root = (REPO_ROOT / "artifacts" / "session" / session_id).resolve()
    visual_root = session_root / "visual"
    return {
        "campaign_summary_path": str(campaign_summary_path.resolve()),
        "campaign_summary": summary,
        "selected_run_index": resolved_index,
        "run_summary": run,
        "campaign_id": str(summary.get("campaign_id", "") or ""),
        "session_id": session_id,
        "mission_root": str(mission_root),
        "session_root": str(session_root),
        "visual_root": str(visual_root),
        "state_history_path": str((mission_root / "state_history.jsonl").resolve()),
        "mission_verdict_path": str((mission_root / "mission_verdict.json").resolve()),
        "gather_sequence_path": str((mission_root / "gather_sequence.jsonl").resolve()),
        "truth_timeline_path": str((visual_root / "truth_timeline.json").resolve()),
        "timeline_path": str((visual_root / "timeline.json").resolve()),
        "timeline_events_path": str((visual_root / "timeline_events.jsonl").resolve()),
    }


def extract_representative_fixtures(
    state_history_path: Path,
    *,
    scenario_id: str = DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID,
    attempt: int = 0,
) -> list[dict[str, Any]]:
    zone = build_zone_spec(scenario_id)
    rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=attempt)
    fixtures = oracle.select_representative_fixture_rows(rows)
    for fixture in fixtures:
        robot_pose = fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {}
        ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
        local_pose = sandbox.world_pose_to_local(robot_pose, ball_pose, zone=zone)
        fixture["robot_pose_local"] = local_pose or {}
    return fixtures


def _sorted_truth_samples(truth_payload: Any) -> list[dict[str, Any]]:
    if not isinstance(truth_payload, list):
        return []
    samples = [dict(item) for item in truth_payload if isinstance(item, dict)]
    samples.sort(key=lambda item: float(_number(item.get("t_s"), default=0.0) or 0.0))
    return samples


def _find_nearest_truth_index_by_t_s(truth_samples: list[dict[str, Any]], target_t_s: float) -> tuple[int, float]:
    if not truth_samples:
        return -1, math.inf
    indexed = [
        (index, abs(float(_number(sample.get("t_s"), default=0.0) or 0.0) - float(target_t_s)))
        for index, sample in enumerate(truth_samples)
    ]
    return min(indexed, key=lambda item: item[1])


def _find_nearest_truth_index_by_pose(truth_samples: list[dict[str, Any]], robot_pose: dict[str, Any]) -> tuple[int, float]:
    candidates: list[tuple[int, float]] = []
    for index, sample in enumerate(truth_samples):
        truth_pose = _truth_sample_robot_pose(sample)
        if truth_pose is None:
            continue
        distance_m = _distance_xy(robot_pose, truth_pose)
        if distance_m is None:
            continue
        candidates.append((index, float(distance_m)))
    if not candidates:
        return -1, math.inf
    return min(candidates, key=lambda item: item[1])


def align_fixture_to_truth_sample(
    fixture: dict[str, Any],
    truth_samples: list[dict[str, Any]],
    *,
    timeline_anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fixture_utc = _parse_utc(fixture.get("generated_utc"))
    robot_pose = fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {}
    fallback_index, fallback_pose_delta_m = _find_nearest_truth_index_by_pose(truth_samples, robot_pose)
    if timeline_anchor is None or fixture_utc is None:
        matched_index = fallback_index
        matched_sample = truth_samples[matched_index] if matched_index >= 0 else {}
        matched_t_s = _number(matched_sample.get("t_s"))
        return {
            "source": "pose_fallback",
            "quality": "good"
            if matched_index >= 0 and fallback_pose_delta_m <= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_ALIGNMENT_POSE_MAX_DELTA_M
            else "poor",
            "fixture_generated_utc": fixture_utc.isoformat() if fixture_utc is not None else "",
            "predicted_t_s": None,
            "matched_truth_index": matched_index,
            "matched_truth_t_s": _round_or_none(matched_t_s),
            "time_delta_s": None,
            "pose_delta_m": _round_or_none(fallback_pose_delta_m if math.isfinite(fallback_pose_delta_m) else None),
        }

    anchor_utc = _parse_utc(timeline_anchor.get("timestamp_utc"))
    anchor_t_s = _number(timeline_anchor.get("t_s"))
    if anchor_utc is None or anchor_t_s is None:
        return align_fixture_to_truth_sample(fixture, truth_samples, timeline_anchor=None)

    predicted_t_s = float(anchor_t_s) + (fixture_utc - anchor_utc).total_seconds()
    matched_index, time_delta_s = _find_nearest_truth_index_by_t_s(truth_samples, predicted_t_s)
    matched_sample = truth_samples[matched_index] if matched_index >= 0 else {}
    matched_truth_pose = _truth_sample_robot_pose(matched_sample)
    pose_delta_m = _distance_xy(robot_pose, matched_truth_pose or {})
    quality = (
        "good"
        if matched_index >= 0
        and float(time_delta_s) <= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_ALIGNMENT_TIME_MAX_DELTA_S
        and (pose_delta_m is None or pose_delta_m <= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_ALIGNMENT_POSE_MAX_DELTA_M)
        else "poor"
    )
    return {
        "source": str(timeline_anchor.get("source", "") or "timeline_utc_anchor"),
        "quality": quality,
        "fixture_generated_utc": fixture_utc.isoformat(),
        "predicted_t_s": round(predicted_t_s, 6),
        "matched_truth_index": matched_index,
        "matched_truth_t_s": _round_or_none(_number(matched_sample.get("t_s"))),
        "time_delta_s": _round_or_none(time_delta_s),
        "pose_delta_m": _round_or_none(pose_delta_m),
        "anchor_timestamp_utc": anchor_utc.isoformat(),
        "anchor_t_s": round(float(anchor_t_s), 6),
    }


def _state_rows_within_window(
    state_rows: list[dict[str, Any]],
    *,
    fixture_index: int,
    fixture_utc: datetime | None,
    fixture_truth_t_s: float | None,
    end_truth_t_s: float | None,
) -> list[dict[str, Any]]:
    if fixture_utc is None or fixture_truth_t_s is None or end_truth_t_s is None:
        return []
    selected: list[dict[str, Any]] = []
    for row in state_rows[max(int(fixture_index), 0) :]:
        row_utc = _parse_utc(row.get("generated_utc"))
        if row_utc is None:
            continue
        estimated_t_s = float(fixture_truth_t_s) + (row_utc - fixture_utc).total_seconds()
        if estimated_t_s < float(fixture_truth_t_s) - 1.0e-6:
            continue
        if estimated_t_s > float(end_truth_t_s) + 1.0e-6:
            break
        selected.append({**row, "_estimated_t_s": round(estimated_t_s, 6)})
    return selected


def _truth_window_samples(
    truth_samples: list[dict[str, Any]],
    *,
    start_index: int,
    horizon_s: float,
) -> tuple[list[dict[str, Any]], float | None]:
    if start_index < 0 or start_index >= len(truth_samples):
        return [], None
    start_t_s = _number(truth_samples[start_index].get("t_s"))
    if start_t_s is None:
        return [], None
    end_t_s = float(start_t_s) + float(horizon_s)
    selected = [
        sample
        for sample in truth_samples[start_index:]
        if float(_number(sample.get("t_s"), default=end_t_s + 1.0) or end_t_s + 1.0) <= end_t_s + 1.0e-6
    ]
    if not selected:
        selected = [truth_samples[start_index]]
    return selected, min(end_t_s, float(_number(selected[-1].get("t_s"), default=end_t_s) or end_t_s))


def _enrich_truth_window(
    truth_window: list[dict[str, Any]],
    *,
    fallback_ball_pose: dict[str, Any],
    zone,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    latest_ball_pose = fallback_ball_pose
    for sample in truth_window:
        robot_pose = _truth_sample_robot_pose(sample)
        ball_pose = _truth_sample_ball_pose(sample, fallback_ball_pose=latest_ball_pose) or latest_ball_pose
        if ball_pose is not None:
            latest_ball_pose = ball_pose
        local_pose = None
        if robot_pose is not None and ball_pose is not None:
            local_pose = sandbox.world_pose_to_local(robot_pose, ball_pose, zone=zone)
        enriched.append(
            {
                "t_s": round(float(_number(sample.get("t_s"), default=0.0) or 0.0), 6),
                "robot_pose": robot_pose,
                "ball_pose": ball_pose,
                "local_pose": local_pose,
            }
        )
    return enriched


def _trajectory_yaw_progress(start_local_pose: dict[str, Any], trajectory_local: list[dict[str, Any]]) -> float:
    local_xyyaw = world_pose_xyyaw(start_local_pose)
    if local_xyyaw is None:
        return 0.0
    _, _, previous_yaw = local_xyyaw
    progress_rad = 0.0
    for sample in trajectory_local:
        sample_xyyaw = world_pose_xyyaw(sample)
        if sample_xyyaw is None:
            continue
        _, _, yaw_rad = sample_xyyaw
        progress_rad += abs(normalize_angle(yaw_rad - previous_yaw))
        previous_yaw = yaw_rad
    return round(progress_rad, 6)


def _best_offline_baseline(
    fixture_local_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone,
    audit_contract: feasibility.AuditRepoContract,
    profile_name: str,
) -> dict[str, Any]:
    results = feasibility.search_audit_maneuvers_local(
        fixture_local_pose,
        ball_pose,
        zone=zone,
        audit_contract=audit_contract,
        profile_name=profile_name,
        top_k=1,
        include_trajectories=True,
    )
    if not results:
        return {}
    best = results[0]
    trajectory_local = list(best.trajectory_local) if isinstance(best.trajectory_local, tuple | list) else []
    return {
        "profile_name": profile_name,
        "family_name": str(best.family_name),
        "macro_sequence": list(best.macro_sequence),
        "feasibility_class": str(best.feasibility_class),
        "corridor_clearable": bool(best.corridor_clearable),
        "goal_side_clearable": bool(best.goal_side_clearable),
        "projection_gain_m": round(float(best.projection_gain), 6),
        "lateral_gain_m": round(float(best.lateral_gain), 6),
        "yaw_progress_rad": _trajectory_yaw_progress(fixture_local_pose, trajectory_local),
        "min_ball_clearance_margin_m": round(float(best.min_ball_clearance_margin_m), 6),
    }


def compute_fixture_metrics(
    fixture: dict[str, Any],
    *,
    state_rows: list[dict[str, Any]],
    truth_samples: list[dict[str, Any]],
    timeline_anchor: dict[str, Any] | None,
    scenario_id: str = DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID,
    audit_contract: feasibility.AuditRepoContract | None = None,
) -> dict[str, Any]:
    zone = build_zone_spec(scenario_id)
    audit_contract = audit_contract or feasibility.load_audit_repo_contract()
    alignment = align_fixture_to_truth_sample(fixture, truth_samples, timeline_anchor=timeline_anchor)
    raw_matched_index = alignment.get("matched_truth_index", -1)
    matched_index = -1 if raw_matched_index is None else int(raw_matched_index)
    matched_truth_t_s = _number(alignment.get("matched_truth_t_s"))
    fixture_utc = _parse_utc(fixture.get("generated_utc"))
    ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
    local_pose = fixture.get("robot_pose_local", {}) if isinstance(fixture.get("robot_pose_local"), dict) else {}

    truth_window, end_truth_t_s = _truth_window_samples(
        truth_samples,
        start_index=matched_index,
        horizon_s=DEFAULT_ESCAPE_DIVERGENCE_AUDIT_HORIZON_S,
    )
    enriched_truth = _enrich_truth_window(truth_window, fallback_ball_pose=ball_pose, zone=zone)
    state_window = _state_rows_within_window(
        state_rows,
        fixture_index=int(fixture.get("fixture_index", 0) or 0),
        fixture_utc=fixture_utc,
        fixture_truth_t_s=matched_truth_t_s,
        end_truth_t_s=end_truth_t_s,
    )
    nominal = _best_offline_baseline(local_pose, ball_pose, zone=zone, audit_contract=audit_contract, profile_name="nominal_current")
    combined = _best_offline_baseline(local_pose, ball_pose, zone=zone, audit_contract=audit_contract, profile_name="combined_relaxed")

    commanded_angular_integral = 0.0
    commanded_reverse_displacement = 0.0
    command_sign_flip_count = 0
    mode_flip_count = 0
    sign_flip_count_before_progress = 0
    mode_flip_count_before_progress = 0
    previous_sign = 0
    previous_mode = ""
    first_progress_time_s: float | None = None

    if len(enriched_truth) >= 2:
        start_local = enriched_truth[0].get("local_pose") or local_pose
    else:
        start_local = local_pose

    realized_yaw_progress = 0.0
    realized_reverse_displacement = 0.0
    realized_projection_gain = 0.0
    realized_lateral_gain = 0.0
    realized_min_robot_ball_separation_proxy_m = math.inf
    realized_ball_motion_magnitude_m = 0.0
    time_spent_on_goal_side_s = 0.0
    time_to_interference_s: float | None = None
    realized_net_yaw_change_rad = 0.0
    start_ball_pose = enriched_truth[0].get("ball_pose") if enriched_truth else ball_pose

    if len(enriched_truth) >= 2:
        start_local_pose = enriched_truth[0].get("local_pose")
        start_robot_pose = enriched_truth[0].get("robot_pose")
        if start_local_pose is not None and start_robot_pose is not None:
            start_local_xyyaw = world_pose_xyyaw(start_local_pose)
            start_robot_xyyaw = world_pose_xyyaw(start_robot_pose)
        else:
            start_local_xyyaw = None
            start_robot_xyyaw = None

        for previous, current in zip(enriched_truth, enriched_truth[1:]):
            previous_t_s = float(_number(previous.get("t_s"), default=0.0) or 0.0)
            current_t_s = float(_number(current.get("t_s"), default=previous_t_s) or previous_t_s)
            dt_s = max(current_t_s - previous_t_s, 0.0)
            previous_robot_pose = previous.get("robot_pose")
            current_robot_pose = current.get("robot_pose")
            previous_ball_pose = previous.get("ball_pose")
            current_ball_pose = current.get("ball_pose")
            previous_local_pose = previous.get("local_pose")
            current_local_pose = current.get("local_pose")

            if previous_robot_pose is not None and current_robot_pose is not None:
                previous_robot_xyyaw = world_pose_xyyaw(previous_robot_pose)
                current_robot_xyyaw = world_pose_xyyaw(current_robot_pose)
                if previous_robot_xyyaw is not None and current_robot_xyyaw is not None:
                    _, _, previous_yaw = previous_robot_xyyaw
                    current_x_m, current_y_m, current_yaw = current_robot_xyyaw
                    previous_x_m, previous_y_m, _ = previous_robot_xyyaw
                    realized_yaw_progress += abs(normalize_angle(current_yaw - previous_yaw))
                    dx_m = current_x_m - previous_x_m
                    dy_m = current_y_m - previous_y_m
                    forward_step_m = (math.cos(previous_yaw) * dx_m) + (math.sin(previous_yaw) * dy_m)
                    realized_reverse_displacement += max(-forward_step_m, 0.0)

            if previous_local_pose is not None and current_local_pose is not None and start_local_xyyaw is not None:
                start_projection_m = float(start_local_xyyaw[0])
                start_lateral_abs_m = abs(float(start_local_xyyaw[1]))
                current_local_xyyaw = world_pose_xyyaw(current_local_pose)
                if current_local_xyyaw is not None:
                    projection_gain_m = max(start_projection_m - float(current_local_xyyaw[0]), 0.0)
                    lateral_gain_m = max(start_lateral_abs_m - abs(float(current_local_xyyaw[1])), 0.0)
                    realized_projection_gain = max(realized_projection_gain, projection_gain_m)
                    realized_lateral_gain = max(realized_lateral_gain, lateral_gain_m)
                    if first_progress_time_s is None and projection_gain_m >= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_EARLY_PROGRESS_GAIN_M:
                        first_progress_time_s = current_t_s - float(_number(enriched_truth[0].get("t_s"), default=current_t_s) or current_t_s)
                    if float(current_local_xyyaw[0]) > DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M:
                        time_spent_on_goal_side_s += dt_s

            if current_robot_pose is not None and current_ball_pose is not None:
                separation_m = _distance_xy(current_robot_pose, current_ball_pose)
                if separation_m is not None:
                    realized_min_robot_ball_separation_proxy_m = min(realized_min_robot_ball_separation_proxy_m, separation_m)
                    interference_threshold_m = (
                        float(audit_contract.nominal_clearance_radius_m)
                        + DEFAULT_ESCAPE_DIVERGENCE_AUDIT_EARLY_INTERFERENCE_CLEARANCE_MARGIN_M
                    )
                    if (
                        time_to_interference_s is None
                        and separation_m <= interference_threshold_m
                    ):
                        time_to_interference_s = current_t_s - float(_number(enriched_truth[0].get("t_s"), default=current_t_s) or current_t_s)

            if current_ball_pose is not None and start_ball_pose is not None:
                ball_motion_m = _distance_xy(current_ball_pose, start_ball_pose)
                if ball_motion_m is not None:
                    realized_ball_motion_magnitude_m = max(realized_ball_motion_magnitude_m, ball_motion_m)
                    if (
                        time_to_interference_s is None
                        and ball_motion_m >= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_EARLY_INTERFERENCE_BALL_MOTION_M
                    ):
                        time_to_interference_s = current_t_s - float(_number(enriched_truth[0].get("t_s"), default=current_t_s) or current_t_s)

        if start_robot_xyyaw is not None:
            final_robot_pose = enriched_truth[-1].get("robot_pose")
            final_robot_xyyaw = world_pose_xyyaw(final_robot_pose) if isinstance(final_robot_pose, dict) else None
            if final_robot_xyyaw is not None:
                realized_net_yaw_change_rad = normalize_angle(float(final_robot_xyyaw[2]) - float(start_robot_xyyaw[2]))

    state_times = [float(_number(row.get("_estimated_t_s"), default=0.0) or 0.0) for row in state_window]
    for index, row in enumerate(state_window):
        current_t_s = state_times[index]
        next_t_s = state_times[index + 1] if index + 1 < len(state_window) else (end_truth_t_s or current_t_s)
        dt_s = max(float(next_t_s) - float(current_t_s), 0.0)
        command = row.get("selected_command", {}) if isinstance(row.get("selected_command"), dict) else {}
        angular_z = float(_number(command.get("angular_z"), default=0.0) or 0.0)
        linear_x = float(_number(command.get("linear_x"), default=0.0) or 0.0)
        mode_name = str(command.get("mode", "") or "")
        commanded_angular_integral += abs(angular_z) * dt_s
        commanded_reverse_displacement += max(-linear_x, 0.0) * dt_s
        command_sign = _sign(angular_z)
        if previous_sign != 0 and command_sign != 0 and command_sign != previous_sign:
            command_sign_flip_count += 1
            if first_progress_time_s is None or (current_t_s - float(matched_truth_t_s or current_t_s)) <= float(first_progress_time_s):
                sign_flip_count_before_progress += 1
        if previous_mode and mode_name and mode_name != previous_mode:
            mode_flip_count += 1
            if first_progress_time_s is None or (current_t_s - float(matched_truth_t_s or current_t_s)) <= float(first_progress_time_s):
                mode_flip_count_before_progress += 1
        if command_sign != 0:
            previous_sign = command_sign
        if mode_name:
            previous_mode = mode_name

    command_net_angular = 0.0
    for index, row in enumerate(state_window):
        command = row.get("selected_command", {}) if isinstance(row.get("selected_command"), dict) else {}
        angular_z = float(_number(command.get("angular_z"), default=0.0) or 0.0)
        current_t_s = state_times[index]
        next_t_s = state_times[index + 1] if index + 1 < len(state_window) else (end_truth_t_s or current_t_s)
        dt_s = max(float(next_t_s) - float(current_t_s), 0.0)
        command_net_angular += angular_z * dt_s
    dominant_command_sign = _sign(command_net_angular)
    wrong_sign_yaw = bool(
        dominant_command_sign != 0
        and _sign(realized_net_yaw_change_rad) != 0
        and _sign(realized_net_yaw_change_rad) != dominant_command_sign
        and abs(realized_net_yaw_change_rad) >= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_MIN_WRONG_SIGN_YAW_RAD
    )
    yaw_realization_ratio = _safe_ratio(realized_yaw_progress, commanded_angular_integral)
    turn_realization_acceptable = bool(
        not wrong_sign_yaw
        and (
            yaw_realization_ratio is None
            or float(yaw_realization_ratio) >= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_TURN_REALIZATION_MIN_RATIO
        )
    )

    baseline_projection_target_m = max(
        float(_number(nominal.get("projection_gain_m"), default=0.0) or 0.0),
        float(_number(combined.get("projection_gain_m"), default=0.0) or 0.0),
    )
    baseline_lateral_target_m = max(
        float(_number(nominal.get("lateral_gain_m"), default=0.0) or 0.0),
        float(_number(combined.get("lateral_gain_m"), default=0.0) or 0.0),
    )
    projection_ratio_to_best = _safe_ratio(realized_projection_gain, baseline_projection_target_m)
    lateral_ratio_to_best = _safe_ratio(realized_lateral_gain, baseline_lateral_target_m)
    early_interference = bool(
        time_to_interference_s is not None
        and (first_progress_time_s is None or float(time_to_interference_s) <= float(first_progress_time_s))
    )
    combined_flip_count_before_progress = int(sign_flip_count_before_progress) + int(mode_flip_count_before_progress)
    ball_effectively_static = (
        float(realized_ball_motion_magnitude_m) <= DEFAULT_ESCAPE_DIVERGENCE_AUDIT_BALL_STATIC_MAX_MOTION_M
    )

    turn_realization_limited = bool(
        (yaw_realization_ratio is not None and float(yaw_realization_ratio) < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_TURN_REALIZATION_MIN_RATIO)
        or wrong_sign_yaw
    )
    contact_geometry_limited = bool(
        turn_realization_acceptable
        and projection_ratio_to_best is not None
        and lateral_ratio_to_best is not None
        and float(projection_ratio_to_best) < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CONTACT_GAIN_RATIO_MAX
        and float(lateral_ratio_to_best) < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CONTACT_GAIN_RATIO_MAX
        and early_interference
    )
    control_timing_limited = bool(
        turn_realization_acceptable
        and ball_effectively_static
        and combined_flip_count_before_progress > 2
        and (first_progress_time_s is None or float(first_progress_time_s) > 0.0)
    )

    fixture_blocker = "world_model_mismatch_unresolved"
    if turn_realization_limited:
        fixture_blocker = "turn_realization_limited"
    elif contact_geometry_limited:
        fixture_blocker = "contact_geometry_limited"
    elif control_timing_limited:
        fixture_blocker = "control_timing_limited"

    deltas = {
        "nominal_current": {
            "projection_gain_delta_m": round(realized_projection_gain - float(_number(nominal.get("projection_gain_m"), default=0.0) or 0.0), 6),
            "lateral_gain_delta_m": round(realized_lateral_gain - float(_number(nominal.get("lateral_gain_m"), default=0.0) or 0.0), 6),
            "yaw_progress_delta_rad": round(realized_yaw_progress - float(_number(nominal.get("yaw_progress_rad"), default=0.0) or 0.0), 6),
        },
        "combined_relaxed": {
            "projection_gain_delta_m": round(realized_projection_gain - float(_number(combined.get("projection_gain_m"), default=0.0) or 0.0), 6),
            "lateral_gain_delta_m": round(realized_lateral_gain - float(_number(combined.get("lateral_gain_m"), default=0.0) or 0.0), 6),
            "yaw_progress_delta_rad": round(realized_yaw_progress - float(_number(combined.get("yaw_progress_rad"), default=0.0) or 0.0), 6),
        },
    }

    return {
        "generated_utc": _utc_now_iso(),
        "fixture_label": str(fixture.get("fixture_label", "") or ""),
        "fixture_index": int(fixture.get("fixture_index", 0) or 0),
        "fixture_generated_utc": str(fixture.get("generated_utc", "") or ""),
        "robot_pose": fixture.get("robot_pose", {}) if isinstance(fixture.get("robot_pose"), dict) else {},
        "ball_pose": ball_pose,
        "robot_pose_local": local_pose,
        "pre_stage_snapshot": fixture.get("pre_stage", {}) if isinstance(fixture.get("pre_stage"), dict) else {},
        "selected_command": fixture.get("selected_command", {}) if isinstance(fixture.get("selected_command"), dict) else {},
        "manager_directive": str(fixture.get("manager_directive", "") or ""),
        "controller_debug": {
            "controller_family": str(fixture.get("controller_family", "") or ""),
            "strategy_name": str(fixture.get("strategy_name", "") or ""),
            "objective_name": str(fixture.get("objective_name", "") or ""),
            "progress_score": _round_or_none(_number(fixture.get("progress_score"))),
            "stall_s": _round_or_none(_number(fixture.get("stall_s"))),
            "projected_projection_gain": _round_or_none(_number(fixture.get("projected_projection_gain"))),
            "projected_lateral_gain": _round_or_none(_number(fixture.get("projected_lateral_gain"))),
            "projected_distance_gain": _round_or_none(_number(fixture.get("projected_distance_gain"))),
        },
        "alignment": alignment,
        "window": {
            "truth_sample_count": len(enriched_truth),
            "state_row_count": len(state_window),
            "start_truth_t_s": _round_or_none(_number(enriched_truth[0].get("t_s")) if enriched_truth else None),
            "end_truth_t_s": _round_or_none(_number(enriched_truth[-1].get("t_s")) if enriched_truth else None),
            "horizon_s": round(float(DEFAULT_ESCAPE_DIVERGENCE_AUDIT_HORIZON_S), 6),
        },
        "command_metrics": {
            "commanded_angular_integral_rad": round(commanded_angular_integral, 6),
            "commanded_reverse_displacement_m": round(commanded_reverse_displacement, 6),
            "command_sign_flip_count": int(command_sign_flip_count),
            "mode_flip_count": int(mode_flip_count),
            "command_sign_flip_count_before_projection_gain": int(sign_flip_count_before_progress),
            "mode_flip_count_before_projection_gain": int(mode_flip_count_before_progress),
        },
        "realized_metrics": {
            "realized_yaw_change_rad": round(realized_yaw_progress, 6),
            "realized_net_yaw_change_rad": round(realized_net_yaw_change_rad, 6),
            "realized_reverse_displacement_m": round(realized_reverse_displacement, 6),
            "projection_gain_m": round(realized_projection_gain, 6),
            "lateral_gain_m": round(realized_lateral_gain, 6),
            "minimum_robot_ball_separation_proxy_m": _round_or_none(
                realized_min_robot_ball_separation_proxy_m if math.isfinite(realized_min_robot_ball_separation_proxy_m) else None
            ),
            "ball_motion_magnitude_m": round(realized_ball_motion_magnitude_m, 6),
            "time_spent_on_goal_side_s": round(time_spent_on_goal_side_s, 6),
            "time_to_projection_gain_s": _round_or_none(first_progress_time_s),
            "time_to_interference_s": _round_or_none(time_to_interference_s),
        },
        "offline_baselines": {
            "nominal_current": nominal,
            "combined_relaxed": combined,
        },
        "offline_vs_live_deltas": deltas,
        "classifier_flags": {
            "poor_alignment": str(alignment.get("quality", "")) != "good",
            "turn_realization_limited": turn_realization_limited,
            "turn_realization_ratio_below_threshold": bool(
                yaw_realization_ratio is not None
                and float(yaw_realization_ratio) < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_TURN_REALIZATION_MIN_RATIO
            ),
            "wrong_sign_yaw": wrong_sign_yaw,
            "contact_geometry_limited": contact_geometry_limited,
            "control_timing_limited": control_timing_limited,
            "ball_effectively_static": ball_effectively_static,
            "early_interference": early_interference,
        },
        "derived_metrics": {
            "yaw_realization_ratio": yaw_realization_ratio,
            "projection_ratio_to_best_offline": projection_ratio_to_best,
            "lateral_ratio_to_best_offline": lateral_ratio_to_best,
            "combined_flip_count_before_projection_gain": int(combined_flip_count_before_progress),
            "turn_realization_acceptable": turn_realization_acceptable,
        },
        "fixture_blocker": fixture_blocker,
    }


def decide_dominant_blocker(fixture_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    poor_alignment_count = 0
    turn_fixture_count = 0
    low_ratio_count = 0
    wrong_sign_count = 0
    contact_count = 0
    timing_count = 0

    for payload in fixture_payloads:
        flags = payload.get("classifier_flags", {}) if isinstance(payload.get("classifier_flags"), dict) else {}
        if bool(flags.get("poor_alignment", False)):
            poor_alignment_count += 1
        if bool(flags.get("turn_realization_limited", False)):
            turn_fixture_count += 1
        if bool(flags.get("turn_realization_ratio_below_threshold", False)):
            low_ratio_count += 1
        if bool(flags.get("wrong_sign_yaw", False)):
            wrong_sign_count += 1
        if bool(flags.get("contact_geometry_limited", False)):
            contact_count += 1
        if bool(flags.get("control_timing_limited", False)):
            timing_count += 1

    if poor_alignment_count > 2:
        dominant_blocker = "world_model_mismatch_unresolved"
        coverage_count = poor_alignment_count
        driver = "poor_alignment"
    elif low_ratio_count >= 3 or wrong_sign_count >= 2:
        dominant_blocker = "turn_realization_limited"
        coverage_count = turn_fixture_count
        driver = "yaw_realization" if low_ratio_count >= 3 else "wrong_sign"
    elif contact_count >= 3:
        dominant_blocker = "contact_geometry_limited"
        coverage_count = contact_count
        driver = "contact_geometry"
    elif timing_count >= 3:
        dominant_blocker = "control_timing_limited"
        coverage_count = timing_count
        driver = "control_timing"
    else:
        dominant_blocker = "world_model_mismatch_unresolved"
        coverage_count = max(poor_alignment_count, turn_fixture_count, contact_count, timing_count)
        driver = "no_dominant_blocker"

    live_probe_required = bool(
        poor_alignment_count > 2
        or coverage_count < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_REQUIRED_DOMINANT_FIXTURES
        or dominant_blocker == "world_model_mismatch_unresolved"
    )
    confidence = (
        "low"
        if poor_alignment_count > 2 or coverage_count < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_REQUIRED_DOMINANT_FIXTURES
        else "high"
        if coverage_count >= 4
        else "medium"
    )
    return {
        "dominant_blocker": dominant_blocker,
        "confidence": confidence,
        "dominant_coverage_count": int(coverage_count),
        "poor_alignment_fixture_count": int(poor_alignment_count),
        "turn_fixture_count": int(turn_fixture_count),
        "turn_low_ratio_count": int(low_ratio_count),
        "turn_wrong_sign_count": int(wrong_sign_count),
        "contact_geometry_fixture_count": int(contact_count),
        "control_timing_fixture_count": int(timing_count),
        "dominant_driver": driver,
        "live_probe_required": live_probe_required,
    }


def _aggregate_alignment_source(fixture_payloads: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    counts = Counter(
        str(((payload.get("alignment", {}) or {}).get("source", "")) or "unknown")
        for payload in fixture_payloads
        if isinstance(payload, dict)
    )
    if not counts:
        return "unknown", {}
    if len(counts) == 1:
        return next(iter(counts.keys())), dict(counts)
    return "mixed", dict(counts)


def _aggregate_delta_metrics(fixture_payloads: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    for payload in fixture_payloads:
        deltas = payload.get("offline_vs_live_deltas", {}) if isinstance(payload.get("offline_vs_live_deltas"), dict) else {}
        for profile_name, profile_deltas in deltas.items():
            if not isinstance(profile_deltas, dict):
                continue
            counts[profile_name] = counts.get(profile_name, 0) + 1
            bucket = totals.setdefault(
                profile_name,
                {
                    "projection_gain_delta_m": 0.0,
                    "lateral_gain_delta_m": 0.0,
                    "yaw_progress_delta_rad": 0.0,
                },
            )
            for key in tuple(bucket.keys()):
                bucket[key] += float(_number(profile_deltas.get(key), default=0.0) or 0.0)
    return {
        profile_name: {
            key: round(float(value) / max(counts.get(profile_name, 1), 1), 6)
            for key, value in bucket.items()
        }
        for profile_name, bucket in totals.items()
    }


def _gather_sequence_brief(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    brief_rows: list[dict[str, Any]] = []
    for row in rows:
        brief_rows.append(
            {
                "event_type": str(row.get("event_type", "") or ""),
                "timestamp_utc": str(row.get("timestamp_utc", "") or ""),
                "status": str(row.get("status", "") or row.get("result", {}).get("status", "") or ""),
            }
        )
    return brief_rows


def build_divergence_audit_bundle(
    *,
    campaign_id: str,
    campaign_summary_path: Path = DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CAMPAIGN_SUMMARY,
    run_index: int = DEFAULT_ESCAPE_DIVERGENCE_AUDIT_RUN_INDEX,
    scenario_id: str = DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    paths = resolve_run_artifact_paths(campaign_summary_path, run_index=run_index)
    state_history_path = Path(paths["state_history_path"])
    mission_verdict_path = Path(paths["mission_verdict_path"])
    gather_sequence_path = Path(paths["gather_sequence_path"])
    truth_timeline_path = Path(paths["truth_timeline_path"])
    timeline_path = Path(paths["timeline_path"])
    timeline_events_path = Path(paths["timeline_events_path"])

    state_rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
    representative_fixtures = extract_representative_fixtures(state_history_path, scenario_id=scenario_id, attempt=0)
    truth_samples = _sorted_truth_samples(read_json(truth_timeline_path))
    timeline_payload = read_json(timeline_path) if timeline_path.exists() else {}
    timeline_event_rows = _read_jsonl(timeline_events_path)
    timeline_anchor = extract_timeline_utc_anchor(timeline_payload if isinstance(timeline_payload, dict) else {}, timeline_event_rows)
    audit_contract = feasibility.load_audit_repo_contract()

    fixture_payloads: dict[str, dict[str, Any]] = {}
    for fixture in representative_fixtures:
        payload = compute_fixture_metrics(
            fixture,
            state_rows=state_rows,
            truth_samples=truth_samples,
            timeline_anchor=timeline_anchor,
            scenario_id=scenario_id,
            audit_contract=audit_contract,
        )
        fixture_payloads[str(payload.get("fixture_label", ""))] = payload

    ordered_fixture_payloads = list(fixture_payloads.values())
    blocker_decision = decide_dominant_blocker(ordered_fixture_payloads)
    alignment_source, alignment_source_counts = _aggregate_alignment_source(ordered_fixture_payloads)
    blocker_counts = Counter(str(payload.get("fixture_blocker", "") or "world_model_mismatch_unresolved") for payload in ordered_fixture_payloads)
    mission_verdict = read_json(mission_verdict_path) if mission_verdict_path.exists() else {}
    gather_sequence_rows = _read_jsonl(gather_sequence_path)

    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "gather_escape_divergence_audit",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "primary_trace_family": DEFAULT_ESCAPE_DIVERGENCE_AUDIT_PRIMARY_FAMILY,
        "source_campaign_summary_path": str(campaign_summary_path.resolve()),
        "source_campaign_id": str(paths.get("campaign_id", "") or ""),
        "source_run_index": int(paths.get("selected_run_index", 0) or 0),
        "source_session_id": str(paths.get("session_id", "") or ""),
        "source_mission_root": str(paths.get("mission_root", "") or ""),
        "source_state_history_path": str(state_history_path),
        "source_truth_timeline_path": str(truth_timeline_path),
        "source_timeline_path": str(timeline_path),
        "source_timeline_events_path": str(timeline_events_path),
        "representative_fixture_count": len(ordered_fixture_payloads),
        "alignment_source": alignment_source,
        "alignment_source_counts": alignment_source_counts,
        "timeline_alignment_anchor": timeline_anchor or {},
        "dominant_blocker": blocker_decision["dominant_blocker"],
        "confidence": blocker_decision["confidence"],
        "dominant_blocker_fixture_count": blocker_decision["dominant_coverage_count"],
        "poor_alignment_fixture_count": blocker_decision["poor_alignment_fixture_count"],
        "blocker_counts": dict(blocker_counts),
        "root_cause_gate": blocker_decision,
        "offline_vs_live_delta_metrics": _aggregate_delta_metrics(ordered_fixture_payloads),
        "live_probe_required": blocker_decision["live_probe_required"],
        "live_probe_recommendation": {
            "allowed": blocker_decision["live_probe_required"],
            "reason": (
                "alignment_poor"
                if int(blocker_decision["poor_alignment_fixture_count"]) > 2
                else "insufficient_fixture_coverage"
                if int(blocker_decision["dominant_coverage_count"]) < DEFAULT_ESCAPE_DIVERGENCE_AUDIT_REQUIRED_DOMINANT_FIXTURES
                else "dominant_blocker_unresolved"
            ),
            "canonical_control_family": DEFAULT_ESCAPE_DIVERGENCE_AUDIT_PRIMARY_FAMILY,
            "reuse_motion_probe": True,
        },
        "run_context": {
            "mission_verdict": mission_verdict,
            "gather_sequence": _gather_sequence_brief(gather_sequence_rows),
        },
        "fixtures": [
            {
                "fixture_label": payload.get("fixture_label", ""),
                "fixture_blocker": payload.get("fixture_blocker", ""),
                "alignment_source": ((payload.get("alignment", {}) or {}).get("source", "")),
                "alignment_quality": ((payload.get("alignment", {}) or {}).get("quality", "")),
                "yaw_realization_ratio": ((payload.get("derived_metrics", {}) or {}).get("yaw_realization_ratio")),
                "projection_gain_m": ((payload.get("realized_metrics", {}) or {}).get("projection_gain_m")),
                "lateral_gain_m": ((payload.get("realized_metrics", {}) or {}).get("lateral_gain_m")),
            }
            for payload in ordered_fixture_payloads
        ],
    }
    return summary, fixture_payloads


def build_scorecard_markdown(summary: dict[str, Any], fixture_payloads: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# Gather Escape Divergence Audit Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Source campaign: `{summary.get('source_campaign_id', '')}`",
        f"- Source run index: `{summary.get('source_run_index', 0)}`",
        f"- Dominant blocker: `{summary.get('dominant_blocker', '')}`",
        f"- Confidence: `{summary.get('confidence', '')}`",
        f"- Alignment source: `{summary.get('alignment_source', '')}`",
        f"- Live probe required: `{summary.get('live_probe_required', False)}`",
        "",
        "## Root Cause Gate",
        "",
        f"- Dominant coverage: `{summary.get('dominant_blocker_fixture_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Poor alignment fixtures: `{summary.get('poor_alignment_fixture_count', 0)}`",
        f"- Blocker counts: `{json.dumps(summary.get('blocker_counts', {}), sort_keys=True)}`",
        "",
        "## Aggregate Deltas",
        "",
    ]
    for profile_name, deltas in (summary.get("offline_vs_live_delta_metrics", {}) or {}).items():
        lines.append(
            f"- `{profile_name}` projection_delta=`{float(deltas.get('projection_gain_delta_m', 0.0)):.3f} m` "
            f"lateral_delta=`{float(deltas.get('lateral_gain_delta_m', 0.0)):.3f} m` "
            f"yaw_delta=`{float(deltas.get('yaw_progress_delta_rad', 0.0)):.3f} rad`"
        )
    lines.extend(["", "## Fixtures", ""])
    for fixture_label in (
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    ):
        payload = fixture_payloads.get(fixture_label, {})
        alignment = payload.get("alignment", {}) if isinstance(payload.get("alignment"), dict) else {}
        command_metrics = payload.get("command_metrics", {}) if isinstance(payload.get("command_metrics"), dict) else {}
        realized = payload.get("realized_metrics", {}) if isinstance(payload.get("realized_metrics"), dict) else {}
        derived = payload.get("derived_metrics", {}) if isinstance(payload.get("derived_metrics"), dict) else {}
        lines.append(
            f"- `{fixture_label}` blocker=`{payload.get('fixture_blocker', '')}` "
            f"alignment=`{alignment.get('source', '')}:{alignment.get('quality', '')}` "
            f"yaw_ratio=`{derived.get('yaw_realization_ratio')}` "
            f"flips=`{command_metrics.get('command_sign_flip_count', 0)}/{command_metrics.get('mode_flip_count', 0)}` "
            f"projection=`{float(realized.get('projection_gain_m', 0.0)):.3f} m` "
            f"lateral=`{float(realized.get('lateral_gain_m', 0.0)):.3f} m` "
            f"ball_motion=`{float(realized.get('ball_motion_magnitude_m', 0.0)):.3f} m`"
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit live-vs-offline divergence for the frozen plus45 short_horizon_v2 gather escape evidence."
    )
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default=DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID)
    parser.add_argument("--campaign-summary-path", default=str(DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CAMPAIGN_SUMMARY))
    parser.add_argument("--run-index", type=int, default=DEFAULT_ESCAPE_DIVERGENCE_AUDIT_RUN_INDEX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip() or oracle.current_utc_stamp()
    summary, fixture_payloads = build_divergence_audit_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=Path(args.campaign_summary_path).resolve(),
        run_index=int(args.run_index),
        scenario_id=str(args.scenario_id or DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID),
    )
    output_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_escape_divergence_audit")
    fixtures_root = ensure_dir(output_root / "fixtures")
    summary_path = output_root / "divergence_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary, fixture_payloads), encoding="utf-8")
    for fixture_label, payload in fixture_payloads.items():
        write_json(fixtures_root / f"{fixture_label}.json", payload)
    print(f"GATHER_ESCAPE_DIVERGENCE_AUDIT_SUMMARY={summary_path}")
    print(
        json.dumps(
            {
                "campaign_id": summary.get("campaign_id", ""),
                "dominant_blocker": summary.get("dominant_blocker", ""),
                "confidence": summary.get("confidence", ""),
                "alignment_source": summary.get("alignment_source", ""),
                "dominant_blocker_fixture_count": summary.get("dominant_blocker_fixture_count", 0),
                "poor_alignment_fixture_count": summary.get("poor_alignment_fixture_count", 0),
                "live_probe_required": summary.get("live_probe_required", False),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not bool(summary.get("live_probe_required", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
