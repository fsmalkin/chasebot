#!/usr/bin/env python3
"""Behavior-neutral runtime sign-chain probe for gather pre-stage manual drive."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import gather_escape_divergence_audit as divergence
import gather_escape_oracle as oracle
import gather_manual_drive_sign_parity_audit as sign_audit
import gather_turn_realization_audit as turn_audit
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import write_json


DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_CAMPAIGN_SUMMARY = (
    sign_audit.DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_CAMPAIGN_SUMMARY
)
DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SCENARIO_ID = (
    sign_audit.DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SCENARIO_ID
)
DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_RUN_INDEX = 0
DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SOURCE_AUDIT_SUMMARY = (
    REPO_ROOT
    / "artifacts"
    / "session"
    / "live_plus45_manual_drive_sign_parity_audit_20260420"
    / "gather_manual_drive_sign_parity_audit"
    / "manual_drive_sign_parity_summary.json"
)
DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_COMMAND_RADPS = 0.05
DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_YAW_RAD = 0.05
DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_TIME_PADDING_S = 0.5

CMD_TOPIC_PRIMARY = "/jetbot_base_controller/cmd_vel"
CMD_TOPIC_SECONDARY = "/cmd_vel"
CMD_TOPIC_NAV = "/cmd_vel_nav"
ODOM_TOPIC_PRIMARY = "/odom"
ODOM_TOPIC_MODEL = "/model/jetbot/odometry"
ODOM_TOPIC_CONTROLLER = "/jetbot_base_controller/odom"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any, *, default: float | None = None) -> float | None:
    return divergence._number(value, default=default)


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _sign(value: float, *, eps: float = 1.0e-6) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return divergence._safe_ratio(numerator, denominator)


def _match_state(expected_sign: int, observed_sign: int) -> bool | None:
    if expected_sign == 0 or observed_sign == 0:
        return None
    return bool(expected_sign == observed_sign)


def _json_from_path(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping JSON payload: {path}")
    return payload


def _ordered_fixture_payloads(fixture_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fixture_label in sign_audit.REPRESENTATIVE_FIXTURE_LABELS:
        payload = fixture_payloads.get(fixture_label)
        if payload is None:
            continue
        ordered.append(payload)
        seen.add(fixture_label)
    for fixture_label, payload in fixture_payloads.items():
        if fixture_label in seen:
            continue
        ordered.append(payload)
    return ordered


def _load_fixture_payloads_from_summary(summary_path: Path) -> dict[str, dict[str, Any]]:
    fixtures_root = summary_path.parent / "fixtures"
    fixture_payloads: dict[str, dict[str, Any]] = {}
    if not fixtures_root.exists():
        return fixture_payloads
    for fixture_label in sign_audit.REPRESENTATIVE_FIXTURE_LABELS:
        fixture_path = fixtures_root / f"{fixture_label}.json"
        if not fixture_path.exists():
            continue
        payload = read_json(fixture_path)
        if isinstance(payload, dict):
            fixture_payloads[fixture_label] = payload
    return fixture_payloads


def load_source_audit_bundle(
    *,
    source_audit_summary_path: Path,
    source_campaign_summary_path: Path,
    scenario_id: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if source_audit_summary_path.exists():
        summary = _json_from_path(source_audit_summary_path)
        fixture_payloads = _load_fixture_payloads_from_summary(source_audit_summary_path)
        if fixture_payloads:
            return summary, fixture_payloads
    summary, fixture_payloads = sign_audit.build_manual_drive_sign_parity_audit_bundle(
        campaign_id="probe_odom_world_sign_chain_source_rebuild",
        campaign_summary_path=source_campaign_summary_path,
        run_index=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_RUN_INDEX,
        scenario_id=scenario_id,
    )
    return summary, fixture_payloads


def _normalize_probe_artifact_paths(paths: dict[str, Any]) -> dict[str, Any]:
    mission_root = Path(str(paths.get("mission_root", "") or "")).resolve()
    if not mission_root.exists():
        return paths
    truth_timeline_path = Path(str(paths.get("truth_timeline_path", "") or ""))
    if truth_timeline_path.exists():
        return paths
    parts = mission_root.parts
    try:
        session_index = parts.index("session")
        session_root = Path(*parts[: session_index + 2])
    except ValueError:
        return paths
    visual_root = session_root / "visual"
    updated = dict(paths)
    updated["session_root"] = str(session_root)
    updated["visual_root"] = str(visual_root)
    updated["truth_timeline_path"] = str((visual_root / "truth_timeline.json").resolve())
    updated["timeline_path"] = str((visual_root / "timeline.json").resolve())
    updated["timeline_events_path"] = str((visual_root / "timeline_events.jsonl").resolve())
    return updated


def _load_run_alignment_context(
    campaign_summary_path: Path,
    *,
    run_index: int,
) -> dict[str, Any]:
    paths = _normalize_probe_artifact_paths(
        divergence.resolve_run_artifact_paths(campaign_summary_path, run_index=run_index)
    )
    state_history_path = Path(paths["state_history_path"])
    truth_timeline_path = Path(paths["truth_timeline_path"])
    timeline_path = Path(paths["timeline_path"])
    timeline_events_path = Path(paths["timeline_events_path"])
    state_rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
    truth_samples = divergence._sorted_truth_samples(read_json(truth_timeline_path))
    timeline_payload = read_json(timeline_path) if timeline_path.exists() else {}
    timeline_event_rows = divergence._read_jsonl(timeline_events_path)
    timeline_anchor = divergence.extract_timeline_utc_anchor(
        timeline_payload if isinstance(timeline_payload, dict) else {},
        timeline_event_rows,
    )
    return {
        "paths": paths,
        "state_history_path": state_history_path,
        "truth_timeline_path": truth_timeline_path,
        "timeline_path": timeline_path,
        "timeline_events_path": timeline_events_path,
        "state_rows": state_rows,
        "truth_samples": truth_samples,
        "timeline_payload": timeline_payload,
        "timeline_event_rows": timeline_event_rows,
        "timeline_anchor": timeline_anchor,
    }


def _predicted_t_s_from_generated_utc(
    generated_utc: Any,
    *,
    timeline_anchor: dict[str, Any] | None,
) -> float | None:
    if timeline_anchor is None:
        return None
    anchor_timestamp = divergence._parse_utc(timeline_anchor.get("timestamp_utc"))
    anchor_t_s = _number(timeline_anchor.get("t_s"))
    sample_timestamp = divergence._parse_utc(generated_utc)
    if anchor_timestamp is None or anchor_t_s is None or sample_timestamp is None:
        return None
    return round(float(anchor_t_s) + (sample_timestamp - anchor_timestamp).total_seconds(), 6)


def extract_requested_command_metrics(
    state_rows: list[dict[str, Any]],
    *,
    timeline_anchor: dict[str, Any] | None,
) -> dict[str, Any]:
    command_rows: list[dict[str, Any]] = []
    for row in state_rows:
        if not isinstance(row, dict):
            continue
        selected_command = row.get("selected_command")
        if not isinstance(selected_command, dict):
            continue
        angular_z = float(_number(selected_command.get("angular_z"), default=0.0) or 0.0)
        if abs(angular_z) < DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_COMMAND_RADPS:
            continue
        predicted_t_s = _predicted_t_s_from_generated_utc(
            row.get("generated_utc"),
            timeline_anchor=timeline_anchor,
        )
        command_rows.append(
            {
                "angular_z": angular_z,
                "t_s": predicted_t_s,
                "generated_utc": str(row.get("generated_utc", "") or ""),
            }
        )
    command_rows.sort(
        key=lambda item: (
            float(_number(item.get("t_s"), default=math.inf) or math.inf),
            str(item.get("generated_utc", "") or ""),
        )
    )
    peak_abs = 0.0
    net_integral = 0.0
    dominant_sign_votes: list[int] = []
    first_nonzero_sign = 0
    last_nonzero_sign = 0
    previous_t_s: float | None = None
    for row in command_rows:
        angular_z = float(row["angular_z"])
        current_sign = _sign(
            angular_z,
            eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_COMMAND_RADPS,
        )
        if current_sign != 0:
            dominant_sign_votes.append(current_sign)
            if first_nonzero_sign == 0:
                first_nonzero_sign = current_sign
            last_nonzero_sign = current_sign
        peak_abs = max(peak_abs, abs(angular_z))
        current_t_s = _number(row.get("t_s"))
        if previous_t_s is not None and current_t_s is not None:
            dt_s = max(float(current_t_s) - float(previous_t_s), 0.0)
            net_integral += angular_z * min(dt_s, 1.0)
        previous_t_s = current_t_s if current_t_s is not None else previous_t_s
    dominant_sign = _sign(net_integral, eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_COMMAND_RADPS)
    if dominant_sign == 0 and dominant_sign_votes:
        vote_sum = sum(dominant_sign_votes)
        dominant_sign = _sign(float(vote_sum), eps=0.5)
    if dominant_sign == 0 and first_nonzero_sign != 0 and first_nonzero_sign == last_nonzero_sign:
        dominant_sign = first_nonzero_sign
    time_values = [
        float(_number(row.get("t_s"), default=math.nan) or math.nan)
        for row in command_rows
        if _number(row.get("t_s")) is not None
    ]
    return {
        "sample_count": len(command_rows),
        "peak_requested_angular_z_radps": round(peak_abs, 6),
        "net_requested_angular_integral_rad": round(net_integral, 6),
        "dominant_command_sign": int(dominant_sign),
        "first_nonzero_command_sign": int(first_nonzero_sign),
        "last_nonzero_command_sign": int(last_nonzero_sign),
        "window_start_t_s": _round_or_none(min(time_values) if time_values else None),
        "window_end_t_s": _round_or_none(max(time_values) if time_values else None),
        "window_scope": "attempt_window",
    }


def build_fixture_local_command_payloads(
    fixtures: list[dict[str, Any]],
    *,
    state_rows: list[dict[str, Any]],
    truth_samples: list[dict[str, Any]],
    timeline_anchor: dict[str, Any] | None,
    scenario_id: str,
) -> dict[str, dict[str, Any]]:
    fixture_payloads: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        fixture_label = str(fixture.get("fixture_label", "") or "")
        if not fixture_label:
            continue
        alignment, enriched_truth, state_window = turn_audit._state_window_for_fixture(
            fixture,
            state_rows=state_rows,
            truth_samples=truth_samples,
            timeline_anchor=timeline_anchor,
            scenario_id=scenario_id,
        )
        matched_truth_t_s = _number(alignment.get("matched_truth_t_s"))
        command_rows = list(state_window)
        if (
            not command_rows
            and isinstance(fixture.get("selected_command"), dict)
            and matched_truth_t_s is not None
        ):
            command_rows = [
                {
                    **fixture,
                    "_estimated_t_s": round(float(matched_truth_t_s), 6),
                }
            ]

        command_times = [
            float(_number(row.get("_estimated_t_s"), default=float(index)) or float(index))
            for index, row in enumerate(command_rows)
        ]
        peak_abs = 0.0
        net_integral = 0.0
        first_nonzero_sign = 0
        last_nonzero_sign = 0
        nonzero_command_sample_count = 0
        for index, row in enumerate(command_rows):
            command = row.get("selected_command", {}) if isinstance(row.get("selected_command"), dict) else {}
            angular_z = float(_number(command.get("angular_z"), default=0.0) or 0.0)
            current_sign = _sign(angular_z, eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_COMMAND_RADPS)
            if current_sign != 0:
                nonzero_command_sample_count += 1
                if first_nonzero_sign == 0:
                    first_nonzero_sign = current_sign
                last_nonzero_sign = current_sign
            current_t_s = command_times[index]
            if index + 1 < len(command_times):
                next_t_s = command_times[index + 1]
            else:
                next_t_s = current_t_s + 1.0 if len(command_rows) == 1 else current_t_s
            dt_s = max(next_t_s - current_t_s, 0.0)
            peak_abs = max(peak_abs, abs(angular_z))
            net_integral += angular_z * dt_s
        dominant_sign = _sign(net_integral, eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_COMMAND_RADPS)
        if dominant_sign == 0 and first_nonzero_sign != 0 and first_nonzero_sign == last_nonzero_sign:
            dominant_sign = first_nonzero_sign
        time_values = [
            float(_number(row.get("_estimated_t_s"), default=math.nan) or math.nan)
            for row in command_rows
            if _number(row.get("_estimated_t_s")) is not None
        ]
        fixture_payloads[fixture_label] = {
            "fixture_label": fixture_label,
            "fixture_index": int(fixture.get("fixture_index", 0) or 0),
            "fixture_generated_utc": str(fixture.get("generated_utc", "") or ""),
            "alignment": alignment,
            "window": {
                "truth_sample_count": len(enriched_truth),
                "state_row_count": len(state_window),
                "start_truth_t_s": _round_or_none(_number(enriched_truth[0].get("t_s")) if enriched_truth else None),
                "end_truth_t_s": _round_or_none(_number(enriched_truth[-1].get("t_s")) if enriched_truth else None),
                "window_scope": "fixture_window",
            },
            "command_metrics": {
                "sample_count": len(command_rows),
                "nonzero_command_sample_count": int(nonzero_command_sample_count),
                "peak_requested_angular_z_radps": round(peak_abs, 6),
                "net_requested_angular_integral_rad": round(net_integral, 6),
                "dominant_command_sign": int(dominant_sign),
                "first_nonzero_command_sign": int(first_nonzero_sign),
                "last_nonzero_command_sign": int(last_nonzero_sign),
                "window_start_t_s": _round_or_none(min(time_values) if time_values else None),
                "window_end_t_s": _round_or_none(max(time_values) if time_values else None),
                "window_scope": "fixture_window",
            },
        }
    return fixture_payloads


def build_fresh_fixture_local_command_payloads(
    state_rows: list[dict[str, Any]],
    *,
    truth_samples: list[dict[str, Any]],
    timeline_anchor: dict[str, Any] | None,
    scenario_id: str,
) -> dict[str, dict[str, Any]]:
    return build_fixture_local_command_payloads(
        oracle.select_representative_fixture_rows(state_rows),
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
        scenario_id=scenario_id,
    )


def build_source_fresh_fixture_window_comparison(
    source_fixture_local_command: dict[str, Any],
    fresh_fixture_local_command: dict[str, Any],
) -> dict[str, Any]:
    source_window = (
        source_fixture_local_command.get("window", {})
        if isinstance(source_fixture_local_command.get("window"), dict)
        else {}
    )
    source_metrics = (
        source_fixture_local_command.get("command_metrics", {})
        if isinstance(source_fixture_local_command.get("command_metrics"), dict)
        else {}
    )
    fresh_window = (
        fresh_fixture_local_command.get("window", {})
        if isinstance(fresh_fixture_local_command.get("window"), dict)
        else {}
    )
    fresh_metrics = (
        fresh_fixture_local_command.get("command_metrics", {})
        if isinstance(fresh_fixture_local_command.get("command_metrics"), dict)
        else {}
    )
    source_start_t_s = _number(source_metrics.get("window_start_t_s"))
    source_end_t_s = _number(source_metrics.get("window_end_t_s"))
    fresh_start_t_s = _number(fresh_metrics.get("window_start_t_s"))
    fresh_end_t_s = _number(fresh_metrics.get("window_end_t_s"))
    source_state_row_count = _number(source_window.get("state_row_count"))
    fresh_state_row_count = _number(fresh_window.get("state_row_count"))
    source_net_integral = _number(source_metrics.get("net_requested_angular_integral_rad"))
    fresh_net_integral = _number(fresh_metrics.get("net_requested_angular_integral_rad"))
    source_dominant_sign = int(source_metrics.get("dominant_command_sign", 0) or 0)
    fresh_dominant_sign = int(fresh_metrics.get("dominant_command_sign", 0) or 0)
    source_first_nonzero_sign = int(source_metrics.get("first_nonzero_command_sign", 0) or 0)
    fresh_first_nonzero_sign = int(fresh_metrics.get("first_nonzero_command_sign", 0) or 0)
    source_last_nonzero_sign = int(source_metrics.get("last_nonzero_command_sign", 0) or 0)
    fresh_last_nonzero_sign = int(fresh_metrics.get("last_nonzero_command_sign", 0) or 0)
    return {
        "delta_direction": "fresh_minus_source",
        "source_window_scope": str(source_window.get("window_scope", "") or ""),
        "fresh_window_scope": str(fresh_window.get("window_scope", "") or ""),
        "source_dominant_command_sign": source_dominant_sign,
        "fresh_dominant_command_sign": fresh_dominant_sign,
        "dominant_command_sign_match": _match_state(source_dominant_sign, fresh_dominant_sign),
        "first_nonzero_sign_match": _match_state(source_first_nonzero_sign, fresh_first_nonzero_sign),
        "last_nonzero_sign_match": _match_state(source_last_nonzero_sign, fresh_last_nonzero_sign),
        "window_start_delta_t_s": _round_or_none(
            float(fresh_start_t_s) - float(source_start_t_s)
            if source_start_t_s is not None and fresh_start_t_s is not None
            else None
        ),
        "window_end_delta_t_s": _round_or_none(
            float(fresh_end_t_s) - float(source_end_t_s)
            if source_end_t_s is not None and fresh_end_t_s is not None
            else None
        ),
        "state_row_count_delta": (
            int(fresh_state_row_count) - int(source_state_row_count)
            if source_state_row_count is not None and fresh_state_row_count is not None
            else None
        ),
        "net_requested_angular_integral_delta_rad": _round_or_none(
            float(fresh_net_integral) - float(source_net_integral)
            if source_net_integral is not None and fresh_net_integral is not None
            else None
        ),
    }


def extract_world_truth_metrics(
    truth_samples: list[dict[str, Any]],
    *,
    start_t_s: float | None,
    end_t_s: float | None,
) -> dict[str, Any]:
    selected_samples: list[dict[str, Any]] = []
    lower_bound = None if start_t_s is None else float(start_t_s) - DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_TIME_PADDING_S
    upper_bound = None if end_t_s is None else float(end_t_s) + DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_TIME_PADDING_S
    for sample in truth_samples:
        sample_t_s = _number(sample.get("t_s"))
        if sample_t_s is None:
            continue
        if lower_bound is not None and float(sample_t_s) < lower_bound:
            continue
        if upper_bound is not None and float(sample_t_s) > upper_bound:
            continue
        selected_samples.append(sample)
    if not selected_samples:
        selected_samples = list(truth_samples)

    step_signs: list[int] = []
    net_yaw_change = 0.0
    abs_yaw_change = 0.0
    previous_yaw: float | None = None
    for sample in selected_samples:
        pose = divergence._truth_sample_robot_pose(sample)
        if pose is None:
            continue
        yaw_rad = float(_number(pose.get("yaw"), default=0.0) or 0.0)
        if previous_yaw is not None:
            yaw_delta = divergence.normalize_angle(yaw_rad - previous_yaw)
            current_sign = _sign(
                yaw_delta,
                eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_YAW_RAD,
            )
            step_signs.append(current_sign)
            net_yaw_change += float(yaw_delta)
            abs_yaw_change += abs(float(yaw_delta))
        previous_yaw = yaw_rad
    dominant_sign = _sign(net_yaw_change, eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_YAW_RAD)
    if dominant_sign == 0:
        vote_sum = sum(step_signs)
        dominant_sign = _sign(float(vote_sum), eps=0.5)
    first_t_s = _number(selected_samples[0].get("t_s")) if selected_samples else None
    last_t_s = _number(selected_samples[-1].get("t_s")) if selected_samples else None
    return {
        "sample_count": len(selected_samples),
        "nonzero_step_count": int(sum(1 for sign in step_signs if sign != 0)),
        "net_yaw_change_rad": round(net_yaw_change, 6),
        "absolute_yaw_change_rad": round(abs_yaw_change, 6),
        "dominant_yaw_sign": int(dominant_sign),
        "window_start_t_s": _round_or_none(first_t_s),
        "window_end_t_s": _round_or_none(last_t_s),
    }


def extract_runtime_probe_world_truth_metrics(runtime_probe_payload: dict[str, Any]) -> dict[str, Any]:
    if "world_truth" not in runtime_probe_payload:
        return {}
    world_truth_payload = runtime_probe_payload.get("world_truth")
    if not isinstance(world_truth_payload, dict):
        return {}
    net_yaw_change = _number(world_truth_payload.get("net_yaw_change_rad"))
    if net_yaw_change is None:
        start_yaw = _number(world_truth_payload.get("start_yaw_rad"))
        end_yaw = _number(world_truth_payload.get("end_yaw_rad"))
        if start_yaw is not None and end_yaw is not None:
            net_yaw_change = divergence.normalize_angle(float(end_yaw) - float(start_yaw))
    absolute_yaw_change = _number(world_truth_payload.get("absolute_yaw_change_rad"))
    if absolute_yaw_change is None:
        absolute_yaw_change = _number(world_truth_payload.get("cumulative_abs_yaw_change_rad"))

    dominant_sign = int(_number(world_truth_payload.get("dominant_yaw_sign"), default=0.0) or 0)
    if dominant_sign == 0 and net_yaw_change is not None:
        dominant_sign = _sign(net_yaw_change, eps=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_MIN_YAW_RAD)
    if dominant_sign == 0:
        first_sign = int(_number(world_truth_payload.get("first_nonzero_sign"), default=0.0) or 0)
        last_sign = int(_number(world_truth_payload.get("last_nonzero_sign"), default=0.0) or 0)
        if first_sign != 0 and first_sign == last_sign:
            dominant_sign = first_sign

    return {
        "sample_count": int(
            _number(
                world_truth_payload.get("sample_count", world_truth_payload.get("message_count", 0)),
                default=0.0,
            )
            or 0
        ),
        "nonzero_step_count": int(_number(world_truth_payload.get("nonzero_step_count"), default=0.0) or 0),
        "net_yaw_change_rad": round(float(net_yaw_change), 6) if net_yaw_change is not None else 0.0,
        "absolute_yaw_change_rad": round(float(absolute_yaw_change), 6) if absolute_yaw_change is not None else 0.0,
        "dominant_yaw_sign": int(dominant_sign),
        "window_start_t_s": _round_or_none(
            _number(world_truth_payload.get("window_start_t_s", world_truth_payload.get("start_t_s")))
        ),
        "window_end_t_s": _round_or_none(
            _number(world_truth_payload.get("window_end_t_s", world_truth_payload.get("end_t_s")))
        ),
    }


def select_world_truth_metrics(
    *,
    truth_samples: list[dict[str, Any]],
    runtime_probe_payload: dict[str, Any],
    start_t_s: float | None,
    end_t_s: float | None,
    expected_probe_session_id: str = "",
) -> dict[str, Any]:
    timeline_metrics = extract_world_truth_metrics(
        truth_samples,
        start_t_s=start_t_s,
        end_t_s=end_t_s,
    )
    runtime_probe_metrics = extract_runtime_probe_world_truth_metrics(runtime_probe_payload)
    runtime_probe_world_truth = (
        runtime_probe_payload.get("world_truth", {})
        if isinstance(runtime_probe_payload.get("world_truth"), dict)
        else {}
    )
    runtime_probe_source_session_id = str(runtime_probe_world_truth.get("source_session_id", "") or "")
    expected_probe_session_id = str(expected_probe_session_id or "")
    runtime_probe_session_matches_expected = (
        None
        if not runtime_probe_source_session_id or not expected_probe_session_id
        else bool(runtime_probe_source_session_id == expected_probe_session_id)
    )
    runtime_probe_sign = int(runtime_probe_metrics.get("dominant_yaw_sign", 0) or 0)
    if runtime_probe_session_matches_expected is False:
        selected_source = "truth_timeline"
        selection_reason = "runtime_probe_world_truth_session_mismatch"
        selected_metrics = timeline_metrics
    elif runtime_probe_sign != 0:
        selected_source = "runtime_probe.world_truth"
        selection_reason = "runtime_probe_world_truth_usable"
        selected_metrics = runtime_probe_metrics
    else:
        selected_source = "truth_timeline"
        selection_reason = (
            "runtime_probe_world_truth_zero_sign" if runtime_probe_metrics else "runtime_probe_world_truth_missing"
        )
        selected_metrics = timeline_metrics

    selected_sign = int(selected_metrics.get("dominant_yaw_sign", 0) or 0)
    timeline_sign = int(timeline_metrics.get("dominant_yaw_sign", 0) or 0)
    return {
        "selected_source": selected_source,
        "selection_reason": selection_reason,
        "selected_metrics": selected_metrics,
        "timeline_metrics": timeline_metrics,
        "runtime_probe_metrics": runtime_probe_metrics,
        "cross_check": {
            "expected_probe_session_id": expected_probe_session_id,
            "runtime_probe_world_truth_source_session_id": runtime_probe_source_session_id,
            "runtime_probe_world_truth_session_matches_expected": runtime_probe_session_matches_expected,
            "selected_world_truth_sign": int(selected_sign),
            "timeline_truth_sign": int(timeline_sign),
            "runtime_probe_world_truth_sign": int(runtime_probe_sign),
            "timeline_matches_selected": _match_state(selected_sign, timeline_sign),
            "runtime_probe_matches_selected": _match_state(selected_sign, runtime_probe_sign),
        },
    }


def _topic_metrics(topic_payload: Any) -> dict[str, Any]:
    return dict(topic_payload) if isinstance(topic_payload, dict) else {}


def _topic_sign(topic_map: dict[str, Any], topic_name: str, *, field_name: str) -> int:
    payload = _topic_metrics(topic_map.get(topic_name))
    return int(payload.get(field_name, 0) or 0)


def _topic_nonzero(topic_map: dict[str, Any], topic_name: str, *, field_name: str) -> bool:
    return _topic_sign(topic_map, topic_name, field_name=field_name) != 0


def classify_runtime_sign_chain(
    *,
    requested_command_metrics: dict[str, Any],
    world_truth_metrics: dict[str, Any],
    runtime_probe_payload: dict[str, Any],
    source_root_cause_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_root_cause_gate = source_root_cause_gate or {}
    cmd_topics = runtime_probe_payload.get("cmd_vel_topics", {})
    odom_topics = runtime_probe_payload.get("odom_topics", {})
    if not isinstance(cmd_topics, dict):
        cmd_topics = {}
    if not isinstance(odom_topics, dict):
        odom_topics = {}

    requested_sign = int(requested_command_metrics.get("dominant_command_sign", 0) or 0)
    world_sign = int(world_truth_metrics.get("dominant_yaw_sign", 0) or 0)
    robot_cmd_sign = _topic_sign(cmd_topics, CMD_TOPIC_PRIMARY, field_name="dominant_angular_sign")
    cmd_vel_sign = _topic_sign(cmd_topics, CMD_TOPIC_SECONDARY, field_name="dominant_angular_sign")
    nav_cmd_sign = _topic_sign(cmd_topics, CMD_TOPIC_NAV, field_name="dominant_angular_sign")
    model_odom_sign = _topic_sign(odom_topics, ODOM_TOPIC_MODEL, field_name="dominant_yaw_sign")
    odom_sign = _topic_sign(odom_topics, ODOM_TOPIC_PRIMARY, field_name="dominant_yaw_sign")
    controller_odom_sign = _topic_sign(odom_topics, ODOM_TOPIC_CONTROLLER, field_name="dominant_yaw_sign")

    command_signs = [sign for sign in (robot_cmd_sign, cmd_vel_sign, nav_cmd_sign) if sign != 0]
    command_topics_consistent = len(set(command_signs)) <= 1 if command_signs else False
    any_command_topic_seen = any(
        _topic_nonzero(cmd_topics, topic_name, field_name="dominant_angular_sign")
        for topic_name in (CMD_TOPIC_PRIMARY, CMD_TOPIC_SECONDARY, CMD_TOPIC_NAV)
    )
    any_odom_topic_seen = any(
        _topic_nonzero(odom_topics, topic_name, field_name="dominant_yaw_sign")
        for topic_name in (ODOM_TOPIC_MODEL, ODOM_TOPIC_PRIMARY, ODOM_TOPIC_CONTROLLER)
    )

    sign_matches = {
        "robot_cmd_to_requested": _match_state(requested_sign, robot_cmd_sign),
        "cmd_vel_to_requested": _match_state(requested_sign, cmd_vel_sign),
        "nav_cmd_to_requested": _match_state(requested_sign, nav_cmd_sign),
        "model_odom_to_requested": _match_state(requested_sign, model_odom_sign),
        "odom_to_requested": _match_state(requested_sign, odom_sign),
        "controller_odom_to_requested": _match_state(requested_sign, controller_odom_sign),
        "model_odom_to_world": _match_state(world_sign, model_odom_sign),
        "odom_to_world": _match_state(world_sign, odom_sign),
        "controller_odom_to_world": _match_state(world_sign, controller_odom_sign),
    }

    if requested_sign == 0 or not any_command_topic_seen or not any_odom_topic_seen or world_sign == 0:
        diagnosis = "runtime_sign_chain_inconclusive"
        decision = "rerun_probe_with_longer_window"
        rationale = (
            "The probe did not capture a stable nonzero sign across the requested command, per-topic cmd_vel, "
            "odom, and truth/world surfaces."
        )
    elif any(
        match is False
        for match in (
            sign_matches["robot_cmd_to_requested"],
            sign_matches["cmd_vel_to_requested"],
            sign_matches["nav_cmd_to_requested"],
        )
        if match is not None
    ) or (command_signs and not command_topics_consistent):
        diagnosis = "command_surface_sign_divergent"
        decision = "inspect_bridge_controller_chain"
        rationale = (
            "The requested turn sign does not stay consistent across the live cmd_vel surfaces, so the bridge or "
            "controller command publication chain is the next narrow runtime check."
        )
    elif sign_matches["model_odom_to_world"] is True and any(
        match is False
        for match in (
            sign_matches["odom_to_world"],
            sign_matches["controller_odom_to_world"],
        )
        if match is not None
    ):
        diagnosis = "odom_publication_chain_divergent"
        decision = "inspect_odom_publication_chain"
        rationale = (
            "The model odom surface agrees with world truth, but the exposed odom-facing surfaces diverge from both; "
            "the next slice should inspect remap/publication flow before changing control authority."
        )
    elif sign_matches["model_odom_to_world"] is False:
        diagnosis = "model_odom_vs_world_divergent"
        decision = "inspect_model_odom_truth_alignment"
        rationale = (
            "The model odom surface itself diverges from world truth, so the runtime sign issue is upstream of odom "
            "remapping and should be narrowed before any behavior patch."
        )
    elif any(
        match is True
        for match in (
            sign_matches["model_odom_to_requested"],
            sign_matches["odom_to_requested"],
            sign_matches["controller_odom_to_requested"],
        )
    ) and not any(
        match is False
        for match in (
            sign_matches["model_odom_to_requested"],
            sign_matches["odom_to_requested"],
            sign_matches["controller_odom_to_requested"],
        )
        if match is not None
    ) and all(
        match is False
        for match in (
            sign_matches["model_odom_to_world"],
            sign_matches["odom_to_world"],
            sign_matches["controller_odom_to_world"],
        )
        if match is not None
    ):
        diagnosis = "world_truth_divergent_from_odom_chain"
        decision = "inspect_truth_alignment_surface"
        rationale = (
            "The command and odom chain stay internally consistent, but truth/world yaw still diverges from that "
            "chain, so the next branch should inspect the world-truth alignment surface."
        )
    elif all(
        match is not False
        for match in (
            sign_matches["robot_cmd_to_requested"],
            sign_matches["cmd_vel_to_requested"],
            sign_matches["nav_cmd_to_requested"],
            sign_matches["model_odom_to_requested"],
            sign_matches["odom_to_requested"],
            sign_matches["controller_odom_to_requested"],
            sign_matches["model_odom_to_world"],
            sign_matches["odom_to_world"],
            sign_matches["controller_odom_to_world"],
        )
    ):
        diagnosis = "sign_chain_aligned"
        decision = "revisit_source_alignment"
        rationale = (
            "The fresh runtime probe did not reproduce the source odom/world sign break across the observable live "
            "surfaces, so the next step is to revisit source-artifact alignment before changing runtime behavior."
        )
    else:
        diagnosis = "runtime_sign_chain_inconclusive"
        decision = "rerun_probe_with_longer_window"
        rationale = (
            "The fresh runtime probe captured mixed sign evidence that does not isolate one runtime surface yet."
        )

    supports_source_odom_world_hypothesis = diagnosis in {
        "odom_publication_chain_divergent",
        "model_odom_vs_world_divergent",
        "world_truth_divergent_from_odom_chain",
    }
    confidence = "high"
    if diagnosis == "runtime_sign_chain_inconclusive":
        confidence = "low"
    elif diagnosis in {"command_surface_sign_divergent", "sign_chain_aligned"}:
        confidence = "medium"
    return {
        "diagnosis": diagnosis,
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "supports_source_odom_world_hypothesis": supports_source_odom_world_hypothesis,
        "source_dominant_diagnosis": str(source_root_cause_gate.get("dominant_diagnosis", "") or ""),
        "requested_command_sign": int(requested_sign),
        "world_truth_sign": int(world_sign),
        "topic_signs": {
            "robot_cmd": int(robot_cmd_sign),
            "cmd_vel": int(cmd_vel_sign),
            "cmd_vel_nav": int(nav_cmd_sign),
            "model_odom": int(model_odom_sign),
            "odom": int(odom_sign),
            "controller_odom": int(controller_odom_sign),
        },
        "command_topics_consistent": bool(command_topics_consistent),
        "sign_matches": sign_matches,
    }


def compute_fixture_probe_payload(
    source_fixture_payload: dict[str, Any],
    *,
    runtime_classification: dict[str, Any],
    requested_command_metrics: dict[str, Any],
    world_truth_metrics: dict[str, Any],
    source_fixture_local_command_payload: dict[str, Any] | None = None,
    fresh_fixture_command_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_diagnosis = str(source_fixture_payload.get("fixture_diagnosis", "") or "")
    relevant_to_probe = source_diagnosis == "odom_world_sign_divergent"
    supports_source_fixture = bool(
        relevant_to_probe and runtime_classification.get("supports_source_odom_world_hypothesis", False)
    )
    sign_matches = (
        source_fixture_payload.get("sign_matches", {})
        if isinstance(source_fixture_payload.get("sign_matches"), dict)
        else {}
    )
    source_odom_metrics = (
        source_fixture_payload.get("odom_metrics", {})
        if isinstance(source_fixture_payload.get("odom_metrics"), dict)
        else {}
    )
    source_world_metrics = (
        source_fixture_payload.get("world_metrics", {})
        if isinstance(source_fixture_payload.get("world_metrics"), dict)
        else {}
    )
    source_command_sign = int(source_fixture_payload.get("command_sign", 0) or 0)
    source_odom_sign = int(source_odom_metrics.get("dominant_yaw_sign", 0) or 0)
    source_world_sign = int(source_world_metrics.get("dominant_yaw_sign", 0) or 0)
    source_fixture_local_command_payload = (
        source_fixture_local_command_payload if isinstance(source_fixture_local_command_payload, dict) else {}
    )
    fresh_requested_sign = int(requested_command_metrics.get("dominant_command_sign", 0) or 0)
    fresh_fixture_command_payload = (
        fresh_fixture_command_payload if isinstance(fresh_fixture_command_payload, dict) else {}
    )
    fresh_fixture_command_metrics = (
        fresh_fixture_command_payload.get("command_metrics", {})
        if isinstance(fresh_fixture_command_payload.get("command_metrics"), dict)
        else {}
    )
    fresh_fixture_command_sign = int(fresh_fixture_command_metrics.get("dominant_command_sign", 0) or 0)
    comparison_command_metrics = (
        fresh_fixture_command_metrics if fresh_fixture_command_metrics else requested_command_metrics
    )
    comparison_requested_sign = (
        fresh_fixture_command_sign if fresh_fixture_command_metrics else fresh_requested_sign
    )
    comparison_sign_source = (
        "fresh_fixture_local_command" if fresh_fixture_command_metrics else "attempt_requested_command"
    )
    fresh_world_sign = int(world_truth_metrics.get("dominant_yaw_sign", 0) or 0)
    requested_window_start_t_s = _number(comparison_command_metrics.get("window_start_t_s"))
    requested_window_end_t_s = _number(comparison_command_metrics.get("window_end_t_s"))
    probe_window_reconstructed = requested_window_start_t_s is not None and requested_window_end_t_s is not None
    source_command_window_scope = "fixture_window"
    probe_command_window_scope = str(
        comparison_command_metrics.get("window_scope", "attempt_window") or "attempt_window"
    )
    requested_vs_world_truth_match = _match_state(fresh_requested_sign, fresh_world_sign)
    source_command_to_fresh_requested = _match_state(source_command_sign, comparison_requested_sign)
    source_command_to_attempt_requested = _match_state(source_command_sign, fresh_requested_sign)
    source_command_to_fixture_requested = _match_state(source_command_sign, fresh_fixture_command_sign)
    if not probe_window_reconstructed:
        if comparison_sign_source == "fresh_fixture_local_command":
            source_probe_command_sign_relation = "noncomparable_fresh_fixture_window_unavailable"
            source_probe_command_sign_reason = "fresh_fixture_local_window_unavailable"
        else:
            source_probe_command_sign_relation = "noncomparable_unbounded_probe_window"
            source_probe_command_sign_reason = "source_fixture_windowed_sign_vs_probe_unbounded_attempt_sign"
        source_probe_command_sign_comparable = False
    elif probe_command_window_scope != "fixture_window":
        source_probe_command_sign_relation = "noncomparable_source_fixture_window_vs_probe_attempt_window"
        source_probe_command_sign_reason = "source_fixture_window_vs_probe_attempt_window"
        source_probe_command_sign_comparable = False
    elif source_command_to_fresh_requested is None:
        source_probe_command_sign_relation = "sign_unavailable"
        source_probe_command_sign_reason = "source_or_probe_command_sign_zero"
        source_probe_command_sign_comparable = False
    elif source_command_to_fresh_requested:
        source_probe_command_sign_relation = "match"
        source_probe_command_sign_reason = "source_and_probe_command_sign_match"
        source_probe_command_sign_comparable = True
    else:
        source_probe_command_sign_relation = "mismatch"
        source_probe_command_sign_reason = "source_and_probe_command_sign_mismatch"
        source_probe_command_sign_comparable = True
    source_fresh_fixture_window_comparison = build_source_fresh_fixture_window_comparison(
        source_fixture_local_command_payload,
        fresh_fixture_command_payload,
    )
    return {
        "generated_utc": _utc_now_iso(),
        "fixture_label": str(source_fixture_payload.get("fixture_label", "") or ""),
        "fixture_index": int(source_fixture_payload.get("fixture_index", 0) or 0),
        "source_fixture_diagnosis": source_diagnosis,
        "source_command_sign": source_command_sign,
        "source_surface_signs": {
            "command": int(source_command_sign),
            "odom": int(source_odom_sign),
            "world": int(source_world_sign),
        },
        "source_sign_matches": sign_matches,
        "source_alignment_matches": {
            "source_command_to_fresh_requested": source_command_to_fresh_requested,
            "source_command_to_fresh_requested_attempt_window": source_command_to_attempt_requested,
            "source_command_to_fresh_requested_fixture_window": source_command_to_fixture_requested,
            "source_odom_to_fresh_world": _match_state(source_odom_sign, fresh_world_sign),
            "source_world_to_fresh_world": _match_state(source_world_sign, fresh_world_sign),
            "requested_to_world_truth": requested_vs_world_truth_match,
        },
        "source_probe_command_sign_comparison": {
            "source_command_sign": int(source_command_sign),
            "probe_requested_command_sign": int(comparison_requested_sign),
            "probe_requested_command_sign_source": comparison_sign_source,
            "probe_attempt_requested_command_sign": int(fresh_requested_sign),
            "probe_fixture_requested_command_sign": int(fresh_fixture_command_sign),
            "sign_match": source_command_to_fresh_requested,
            "comparable": bool(source_probe_command_sign_comparable),
            "probe_window_reconstructed": bool(probe_window_reconstructed),
            "source_window_scope": source_command_window_scope,
            "probe_window_scope": probe_command_window_scope,
            "surface_homologous": bool(source_command_window_scope == probe_command_window_scope == "fixture_window"),
            "requested_vs_world_truth_sign_match": requested_vs_world_truth_match,
            "relation": source_probe_command_sign_relation,
            "reason": source_probe_command_sign_reason,
        },
        "fresh_probe_signs": {
            "requested_command": int(fresh_requested_sign),
            "fixture_local_requested_command": int(fresh_fixture_command_sign),
            "world_truth": int(fresh_world_sign),
        },
        "source_fixture_local_command": source_fixture_local_command_payload,
        "source_fresh_fixture_window_comparison": source_fresh_fixture_window_comparison,
        "fresh_fixture_local_command": fresh_fixture_command_payload,
        "probe_hypothesis_relevant": relevant_to_probe,
        "runtime_probe_supports_source_fixture": supports_source_fixture,
        "runtime_diagnosis": str(runtime_classification.get("diagnosis", "") or ""),
        "runtime_next_action": str(runtime_classification.get("decision", "") or ""),
        "runtime_confidence": str(runtime_classification.get("confidence", "") or ""),
        "runtime_surface_signs": dict(runtime_classification.get("topic_signs", {}) or {}),
        "requested_command_metrics": requested_command_metrics,
        "world_truth_metrics": world_truth_metrics,
    }


def assess_source_alignment(
    ordered_fixture_payloads: list[dict[str, Any]],
    *,
    runtime_classification: dict[str, Any],
) -> dict[str, Any]:
    relevant_payloads = [
        payload for payload in ordered_fixture_payloads if bool(payload.get("probe_hypothesis_relevant", False))
    ]
    command_match_labels: list[str] = []
    command_mismatch_labels: list[str] = []
    command_noncomparable_labels: list[str] = []
    command_scope_mismatch_labels: list[str] = []
    command_unknown_labels: list[str] = []
    world_match_labels: list[str] = []
    world_mismatch_labels: list[str] = []
    world_unknown_labels: list[str] = []
    requested_world_aligned = False

    for payload in relevant_payloads:
        fixture_label = str(payload.get("fixture_label", "") or "")
        source_probe_command_sign_comparison = (
            payload.get("source_probe_command_sign_comparison", {})
            if isinstance(payload.get("source_probe_command_sign_comparison"), dict)
            else {}
        )
        source_alignment_matches = (
            payload.get("source_alignment_matches", {})
            if isinstance(payload.get("source_alignment_matches"), dict)
            else {}
        )
        command_relation = str(source_probe_command_sign_comparison.get("relation", "") or "")
        if command_relation == "match":
            command_match_labels.append(fixture_label)
        elif command_relation == "mismatch":
            command_mismatch_labels.append(fixture_label)
        elif command_relation == "noncomparable_source_fixture_window_vs_probe_attempt_window":
            command_scope_mismatch_labels.append(fixture_label)
        elif command_relation in {
            "noncomparable_unbounded_probe_window",
            "noncomparable_fresh_fixture_window_unavailable",
        }:
            command_noncomparable_labels.append(fixture_label)
        else:
            command_unknown_labels.append(fixture_label)

        world_match = source_alignment_matches.get("source_world_to_fresh_world")
        if world_match is True:
            world_match_labels.append(fixture_label)
        elif world_match is False:
            world_mismatch_labels.append(fixture_label)
        else:
            world_unknown_labels.append(fixture_label)
        requested_world_aligned = requested_world_aligned or bool(
            source_alignment_matches.get("requested_to_world_truth") is True
        )

    runtime_diagnosis = str(runtime_classification.get("diagnosis", "") or "")
    diagnosis = "source_alignment_inconclusive"
    decision = "revisit_source_alignment"
    confidence = "low"
    rationale = "The fresh probe did not isolate a stronger source-alignment explanation yet."

    if runtime_diagnosis != "sign_chain_aligned":
        diagnosis = "runtime_branch_dominant"
        decision = str(runtime_classification.get("decision", "") or "")
        confidence = str(runtime_classification.get("confidence", "") or "medium")
        rationale = (
            "The runtime probe still isolates a live sign-chain surface, so source alignment remains secondary "
            "until that runtime branch is resolved."
        )
    elif command_noncomparable_labels:
        diagnosis = "source_probe_command_sign_noncomparable"
        decision = "reconstruct_probe_command_window"
        confidence = "medium"
        rationale = (
            f"The fresh runtime probe is internally aligned, but {len(command_noncomparable_labels)} of "
            f"{len(relevant_payloads)} relevant frozen source fixtures cannot be compared against the fresh "
            "requested command sign because the probe did not reconstruct a bounded command window."
        )
        if requested_world_aligned:
            rationale += (
                " The fresh requested sign still agrees with fresh world truth, so the immediate next step is "
                "window reconstruction rather than a runtime behavior patch."
            )
    elif command_scope_mismatch_labels:
        diagnosis = "source_probe_command_sign_semantically_noncomparable"
        decision = "build_fresh_fixture_local_comparison"
        confidence = "medium"
        rationale = (
            f"The fresh runtime probe is internally aligned, but {len(command_scope_mismatch_labels)} of "
            f"{len(relevant_payloads)} relevant source command comparisons still mix source fixture-local windows "
            "with one fresh attempt-level command window. Treat that relation as additive only until the fresh side "
            "is reconstructed on a homologous fixture-local surface."
        )
    elif command_mismatch_labels:
        diagnosis = "source_fixture_command_sign_mismatch"
        decision = "inspect_source_fixture_alignment"
        confidence = "medium"
        rationale = (
            f"The fresh runtime probe is internally aligned, but {len(command_mismatch_labels)} of "
            f"{len(relevant_payloads)} relevant frozen source fixtures carry a command sign that disagrees with "
            "the fresh requested command sign."
        )
        if world_match_labels:
            rationale += (
                f" {len(world_match_labels)} relevant fixture world signs still match the fresh world sign, which "
                "points toward source fixture/window alignment rather than a new runtime odom/world break."
            )
        else:
            rationale += " Compare fixture/window alignment before changing runtime behavior."
    elif relevant_payloads:
        diagnosis = "source_alignment_recheck_needed"
        decision = "revisit_source_alignment"
        confidence = "medium"
        rationale = (
            "The runtime probe is aligned and the relevant frozen source fixture command signs do not contradict "
            "the fresh requested sign, so the remaining gap is how the source fixtures map onto the fresh run."
        )

    return {
        "diagnosis": diagnosis,
        "decision": decision,
        "confidence": confidence,
        "rationale": rationale,
        "relevant_fixture_count": len(relevant_payloads),
        "source_command_to_fresh_requested_match_count": len(command_match_labels),
        "source_command_to_fresh_requested_mismatch_count": len(command_mismatch_labels),
        "source_probe_command_sign_noncomparable_count": len(command_noncomparable_labels),
        "source_probe_command_sign_scope_mismatch_count": len(command_scope_mismatch_labels),
        "source_command_to_fresh_requested_unknown_count": len(command_unknown_labels),
        "source_world_to_fresh_world_match_count": len(world_match_labels),
        "source_world_to_fresh_world_mismatch_count": len(world_mismatch_labels),
        "source_world_to_fresh_world_unknown_count": len(world_unknown_labels),
        "source_command_match_fixture_labels": command_match_labels,
        "source_command_mismatch_fixture_labels": command_mismatch_labels,
        "source_command_noncomparable_fixture_labels": command_noncomparable_labels,
        "source_command_scope_mismatch_fixture_labels": command_scope_mismatch_labels,
        "source_world_match_fixture_labels": world_match_labels,
        "source_world_mismatch_fixture_labels": world_mismatch_labels,
    }


def build_odom_world_sign_chain_bundle(
    *,
    campaign_id: str,
    campaign_summary_path: Path,
    runtime_probe_json_path: Path,
    source_audit_summary_path: Path = DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SOURCE_AUDIT_SUMMARY,
    source_campaign_summary_path: Path = DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_CAMPAIGN_SUMMARY,
    run_index: int = DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_RUN_INDEX,
    scenario_id: str = DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SCENARIO_ID,
    runtime_probe_stdout_path: Path | None = None,
    runtime_probe_stderr_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    source_summary, source_fixture_payloads = load_source_audit_bundle(
        source_audit_summary_path=source_audit_summary_path,
        source_campaign_summary_path=source_campaign_summary_path,
        scenario_id=scenario_id,
    )
    source_run_context = _load_run_alignment_context(
        source_campaign_summary_path,
        run_index=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_RUN_INDEX,
    )
    probe_run_context = _load_run_alignment_context(
        campaign_summary_path,
        run_index=run_index,
    )
    source_paths = source_run_context["paths"]
    probe_paths = probe_run_context["paths"]
    source_state_history_path = Path(source_run_context["state_history_path"])
    source_truth_timeline_path = Path(source_run_context["truth_timeline_path"])
    source_timeline_path = Path(source_run_context["timeline_path"])
    source_timeline_events_path = Path(source_run_context["timeline_events_path"])
    source_state_rows = list(source_run_context["state_rows"])
    source_truth_samples = list(source_run_context["truth_samples"])
    source_timeline_anchor = source_run_context["timeline_anchor"]
    state_history_path = Path(probe_run_context["state_history_path"])
    truth_timeline_path = Path(probe_run_context["truth_timeline_path"])
    timeline_path = Path(probe_run_context["timeline_path"])
    timeline_events_path = Path(probe_run_context["timeline_events_path"])
    state_rows = list(probe_run_context["state_rows"])
    truth_samples = list(probe_run_context["truth_samples"])
    timeline_anchor = probe_run_context["timeline_anchor"]
    requested_command_metrics = extract_requested_command_metrics(
        state_rows,
        timeline_anchor=timeline_anchor,
    )
    source_fixture_local_command_payloads = build_fixture_local_command_payloads(
        oracle.select_representative_fixture_rows(source_state_rows),
        state_rows=source_state_rows,
        truth_samples=source_truth_samples,
        timeline_anchor=source_timeline_anchor,
        scenario_id=scenario_id,
    )
    fresh_fixture_command_payloads = build_fresh_fixture_local_command_payloads(
        state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
        scenario_id=scenario_id,
    )
    runtime_probe_payload = _json_from_path(runtime_probe_json_path)
    world_truth_selection = select_world_truth_metrics(
        truth_samples=truth_samples,
        runtime_probe_payload=runtime_probe_payload,
        start_t_s=_number(requested_command_metrics.get("window_start_t_s")),
        end_t_s=_number(requested_command_metrics.get("window_end_t_s")),
        expected_probe_session_id=str(probe_paths.get("session_id", "") or ""),
    )
    world_truth_metrics = world_truth_selection["selected_metrics"]
    runtime_classification = classify_runtime_sign_chain(
        requested_command_metrics=requested_command_metrics,
        world_truth_metrics=world_truth_metrics,
        runtime_probe_payload=runtime_probe_payload,
        source_root_cause_gate=(
            source_summary.get("root_cause_gate", {})
            if isinstance(source_summary.get("root_cause_gate"), dict)
            else {}
        ),
    )
    fixture_payloads = {
        fixture_label: compute_fixture_probe_payload(
            payload,
            runtime_classification=runtime_classification,
            requested_command_metrics=requested_command_metrics,
            world_truth_metrics=world_truth_metrics,
            source_fixture_local_command_payload=source_fixture_local_command_payloads.get(fixture_label),
            fresh_fixture_command_payload=fresh_fixture_command_payloads.get(fixture_label),
        )
        for fixture_label, payload in source_fixture_payloads.items()
    }
    ordered_fixture_payloads = _ordered_fixture_payloads(fixture_payloads)
    relevant_source_fixture_count = int(
        sum(1 for payload in ordered_fixture_payloads if bool(payload.get("probe_hypothesis_relevant", False)))
    )
    supported_source_fixture_count = int(
        sum(
            1
            for payload in ordered_fixture_payloads
            if bool(payload.get("runtime_probe_supports_source_fixture", False))
        )
    )
    source_alignment_assessment = assess_source_alignment(
        ordered_fixture_payloads,
        runtime_classification=runtime_classification,
    )
    next_action = {
        "decision": str(runtime_classification.get("decision", "") or ""),
        "confidence": str(runtime_classification.get("confidence", "") or ""),
        "rationale": str(runtime_classification.get("rationale", "") or ""),
    }
    if (
        str(runtime_classification.get("diagnosis", "") or "") == "sign_chain_aligned"
        and str(source_alignment_assessment.get("diagnosis", "") or "")
        in {
            "source_probe_command_sign_noncomparable",
            "source_probe_command_sign_semantically_noncomparable",
            "source_fixture_command_sign_mismatch",
        }
    ):
        next_action = {
            "decision": str(source_alignment_assessment.get("decision", "") or ""),
            "confidence": str(source_alignment_assessment.get("confidence", "") or ""),
            "rationale": str(source_alignment_assessment.get("rationale", "") or ""),
        }
    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "probe_odom_world_sign_chain",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "source_campaign_summary_path": str(source_campaign_summary_path.resolve()),
        "source_audit_summary_path": str(source_audit_summary_path.resolve()),
        "source_campaign_id": str(source_summary.get("source_campaign_id", "") or source_summary.get("campaign_id", "")),
        "source_run_index": int(source_paths.get("selected_run_index", 0) or 0),
        "source_session_id": str(source_paths.get("session_id", "") or ""),
        "source_mission_root": str(source_paths.get("mission_root", "") or ""),
        "source_visual_root": str(source_paths.get("visual_root", "") or ""),
        "source_state_history_path": str(source_state_history_path),
        "source_truth_timeline_path": str(source_truth_timeline_path),
        "source_timeline_path": str(source_timeline_path),
        "source_timeline_events_path": str(source_timeline_events_path),
        "source_timeline_alignment_anchor": source_timeline_anchor or {},
        "source_fixture_local_command_payload_count": len(source_fixture_local_command_payloads),
        "source_root_cause_gate": source_summary.get("root_cause_gate", {}),
        "source_next_action": source_summary.get("next_action", {}),
        "source_representative_fixture_count": int(source_summary.get("representative_fixture_count", 0) or 0),
        "source_odom_world_sign_divergent_fixture_count": int(
            ((source_summary.get("root_cause_gate", {}) or {}).get("odom_world_sign_divergent_fixture_count", 0))
        ),
        "probe_campaign_summary_path": str(campaign_summary_path.resolve()),
        "probe_campaign_id": str(probe_paths.get("campaign_id", "") or ""),
        "probe_run_index": int(probe_paths.get("selected_run_index", 0) or 0),
        "probe_session_id": str(probe_paths.get("session_id", "") or ""),
        "probe_mission_root": str(probe_paths.get("mission_root", "") or ""),
        "probe_visual_root": str(probe_paths.get("visual_root", "") or ""),
        "probe_state_history_path": str(state_history_path),
        "probe_truth_timeline_path": str(truth_timeline_path),
        "probe_timeline_path": str(timeline_path),
        "probe_timeline_events_path": str(timeline_events_path),
        "runtime_probe_json_path": str(runtime_probe_json_path.resolve()),
        "runtime_probe_stdout_path": str(runtime_probe_stdout_path.resolve()) if runtime_probe_stdout_path else "",
        "runtime_probe_stderr_path": str(runtime_probe_stderr_path.resolve()) if runtime_probe_stderr_path else "",
        "timeline_alignment_anchor": timeline_anchor or {},
        "requested_command_metrics": requested_command_metrics,
        "fresh_fixture_local_command_payload_count": len(fresh_fixture_command_payloads),
        "world_truth_source": str(world_truth_selection.get("selected_source", "") or ""),
        "world_truth_source_reason": str(world_truth_selection.get("selection_reason", "") or ""),
        "world_truth_metrics": world_truth_metrics,
        "timeline_world_truth_metrics": world_truth_selection.get("timeline_metrics", {}),
        "runtime_probe_world_truth_metrics": world_truth_selection.get("runtime_probe_metrics", {}),
        "world_truth_cross_check": world_truth_selection.get("cross_check", {}),
        "runtime_probe": runtime_probe_payload,
        "runtime_classification": runtime_classification,
        "source_alignment_assessment": source_alignment_assessment,
        "next_action": next_action,
        "relevant_source_fixture_count": relevant_source_fixture_count,
        "runtime_supported_source_fixture_count": supported_source_fixture_count,
        "run_context": {
            "requested_world_file": str(((probe_paths.get("campaign_summary", {}) or {}).get("requested_world_file", "")) or ""),
            "requested_surface_profile": str(((probe_paths.get("campaign_summary", {}) or {}).get("requested_surface_profile", "")) or ""),
            "requested_target_layout_json": str(((probe_paths.get("campaign_summary", {}) or {}).get("requested_target_layout_json", "")) or ""),
            "execution_mode": str(((probe_paths.get("campaign_summary", {}) or {}).get("execution_mode", "")) or ""),
            "selected_run": probe_paths.get("run_summary", {}),
        },
        "fixtures": [
            {
                "fixture_label": payload.get("fixture_label", ""),
                "source_fixture_diagnosis": payload.get("source_fixture_diagnosis", ""),
                "probe_hypothesis_relevant": bool(payload.get("probe_hypothesis_relevant", False)),
                "runtime_probe_supports_source_fixture": bool(
                    payload.get("runtime_probe_supports_source_fixture", False)
                ),
                "source_command_sign": payload.get("source_command_sign", 0),
                "source_world_sign": ((payload.get("source_surface_signs", {}) or {}).get("world", 0)),
                "source_command_relation": (
                    ((payload.get("source_probe_command_sign_comparison", {}) or {}).get("relation", ""))
                ),
                "source_command_comparable": bool(
                    ((payload.get("source_probe_command_sign_comparison", {}) or {}).get("comparable", False))
                ),
                "source_fixture_command_sign": (
                    (((payload.get("source_fixture_local_command", {}) or {}).get("command_metrics", {}) or {}).get(
                        "dominant_command_sign",
                        0,
                    ))
                ),
                "fresh_requested_command_sign": ((payload.get("fresh_probe_signs", {}) or {}).get("requested_command", 0)),
                "fresh_fixture_command_sign": (
                    ((payload.get("fresh_probe_signs", {}) or {}).get("fixture_local_requested_command", 0))
                ),
                "source_fresh_fixture_window_sign_match": (
                    ((payload.get("source_fresh_fixture_window_comparison", {}) or {}).get("dominant_command_sign_match"))
                ),
                "fresh_world_truth_sign": ((payload.get("fresh_probe_signs", {}) or {}).get("world_truth", 0)),
                "source_command_to_fresh_requested_match": (
                    (payload.get("source_alignment_matches", {}) or {}).get("source_command_to_fresh_requested")
                ),
                "source_world_to_fresh_world_match": (
                    (payload.get("source_alignment_matches", {}) or {}).get("source_world_to_fresh_world")
                ),
                "runtime_diagnosis": payload.get("runtime_diagnosis", ""),
            }
            for payload in ordered_fixture_payloads
        ],
    }
    return summary, fixture_payloads


def build_scorecard_markdown(summary: dict[str, Any], fixture_payloads: dict[str, dict[str, Any]]) -> str:
    runtime_classification = (
        summary.get("runtime_classification", {})
        if isinstance(summary.get("runtime_classification"), dict)
        else {}
    )
    topic_signs = runtime_classification.get("topic_signs", {}) if isinstance(runtime_classification.get("topic_signs"), dict) else {}
    requested_metrics = (
        summary.get("requested_command_metrics", {})
        if isinstance(summary.get("requested_command_metrics"), dict)
        else {}
    )
    world_metrics = (
        summary.get("world_truth_metrics", {})
        if isinstance(summary.get("world_truth_metrics"), dict)
        else {}
    )
    timeline_world_metrics = (
        summary.get("timeline_world_truth_metrics", {})
        if isinstance(summary.get("timeline_world_truth_metrics"), dict)
        else {}
    )
    runtime_probe_world_metrics = (
        summary.get("runtime_probe_world_truth_metrics", {})
        if isinstance(summary.get("runtime_probe_world_truth_metrics"), dict)
        else {}
    )
    world_truth_cross_check = (
        summary.get("world_truth_cross_check", {})
        if isinstance(summary.get("world_truth_cross_check"), dict)
        else {}
    )
    source_alignment_assessment = (
        summary.get("source_alignment_assessment", {})
        if isinstance(summary.get("source_alignment_assessment"), dict)
        else {}
    )
    lines = [
        "# Probe Odom World Sign Chain Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Source audit: `{summary.get('source_campaign_id', '')}`",
        f"- Probe campaign: `{summary.get('probe_campaign_id', '')}`",
        f"- Runtime diagnosis: `{runtime_classification.get('diagnosis', '')}`",
        f"- Source alignment diagnosis: `{source_alignment_assessment.get('diagnosis', '')}`",
        f"- Confidence: `{runtime_classification.get('confidence', '')}`",
        f"- Next action: `{((summary.get('next_action', {}) or {}).get('decision', ''))}`",
        f"- Relevant source fixtures: `{summary.get('relevant_source_fixture_count', 0)}`",
        f"- Runtime-supported source fixtures: `{summary.get('runtime_supported_source_fixture_count', 0)}`",
        "",
        "## Source Alignment",
        "",
        f"- Relevant source command matches fresh requested sign: `{source_alignment_assessment.get('source_command_to_fresh_requested_match_count', 0)}`",
        f"- Relevant source command mismatches fresh requested sign: `{source_alignment_assessment.get('source_command_to_fresh_requested_mismatch_count', 0)}`",
        f"- Relevant source command comparisons blocked by unbounded probe window: `{source_alignment_assessment.get('source_probe_command_sign_noncomparable_count', 0)}`",
        f"- Relevant source command comparisons blocked by fixture-vs-attempt scope mismatch: `{source_alignment_assessment.get('source_probe_command_sign_scope_mismatch_count', 0)}`",
        f"- Relevant source world matches fresh world sign: `{source_alignment_assessment.get('source_world_to_fresh_world_match_count', 0)}`",
        f"- Relevant source world mismatches fresh world sign: `{source_alignment_assessment.get('source_world_to_fresh_world_mismatch_count', 0)}`",
        f"- Noncomparable source command fixtures: `{', '.join(source_alignment_assessment.get('source_command_noncomparable_fixture_labels', [])) or 'none'}`",
        f"- Scope-mismatched source command fixtures: `{', '.join(source_alignment_assessment.get('source_command_scope_mismatch_fixture_labels', [])) or 'none'}`",
        f"- Mismatched source command fixtures: `{', '.join(source_alignment_assessment.get('source_command_mismatch_fixture_labels', [])) or 'none'}`",
        f"- Matching source world fixtures: `{', '.join(source_alignment_assessment.get('source_world_match_fixture_labels', [])) or 'none'}`",
        "",
        "## Fixture Window Diffs",
        "",
    ]
    for payload in _ordered_fixture_payloads(fixture_payloads):
        if not bool(payload.get("probe_hypothesis_relevant", False)):
            continue
        source_fixture_local_command = (
            payload.get("source_fixture_local_command", {})
            if isinstance(payload.get("source_fixture_local_command"), dict)
            else {}
        )
        fresh_fixture_local_command = (
            payload.get("fresh_fixture_local_command", {})
            if isinstance(payload.get("fresh_fixture_local_command"), dict)
            else {}
        )
        source_metrics = (
            source_fixture_local_command.get("command_metrics", {})
            if isinstance(source_fixture_local_command.get("command_metrics"), dict)
            else {}
        )
        fresh_metrics = (
            fresh_fixture_local_command.get("command_metrics", {})
            if isinstance(fresh_fixture_local_command.get("command_metrics"), dict)
            else {}
        )
        source_fresh_fixture_window_comparison = (
            payload.get("source_fresh_fixture_window_comparison", {})
            if isinstance(payload.get("source_fresh_fixture_window_comparison"), dict)
            else {}
        )
        lines.append(
            f"- `{payload.get('fixture_label', '')}` "
            f"src_window=`{source_metrics.get('window_start_t_s')}..{source_metrics.get('window_end_t_s')}` "
            f"fresh_window=`{fresh_metrics.get('window_start_t_s')}..{fresh_metrics.get('window_end_t_s')}` "
            f"src_sign=`{source_metrics.get('dominant_command_sign', 0)}` "
            f"fresh_sign=`{fresh_metrics.get('dominant_command_sign', 0)}` "
            f"sign_match=`{source_fresh_fixture_window_comparison.get('dominant_command_sign_match')}` "
            f"net_delta_rad=`{source_fresh_fixture_window_comparison.get('net_requested_angular_integral_delta_rad')}` "
            f"start_delta_s=`{source_fresh_fixture_window_comparison.get('window_start_delta_t_s')}` "
            f"end_delta_s=`{source_fresh_fixture_window_comparison.get('window_end_delta_t_s')}`"
        )

    lines.extend(
        [
            "",
        "## Runtime Signs",
        "",
        f"- Requested command sign: `{requested_metrics.get('dominant_command_sign', 0)}`",
        f"- Requested peak angular z rad/s: `{requested_metrics.get('peak_requested_angular_z_radps', 0.0)}`",
        f"- World truth source: `{summary.get('world_truth_source', '')}`",
        f"- World truth source reason: `{summary.get('world_truth_source_reason', '')}`",
        f"- Selected world truth sign: `{world_metrics.get('dominant_yaw_sign', 0)}`",
        f"- Runtime probe world truth sign: `{runtime_probe_world_metrics.get('dominant_yaw_sign', 0)}`",
        f"- Timeline cross-check sign: `{timeline_world_metrics.get('dominant_yaw_sign', 0)}`",
        f"- Timeline matches selected: `{world_truth_cross_check.get('timeline_matches_selected')}`",
        f"- Robot cmd sign: `{topic_signs.get('robot_cmd', 0)}`",
        f"- Cmd vel sign: `{topic_signs.get('cmd_vel', 0)}`",
        f"- Cmd vel nav sign: `{topic_signs.get('cmd_vel_nav', 0)}`",
        f"- Model odom sign: `{topic_signs.get('model_odom', 0)}`",
        f"- Odom sign: `{topic_signs.get('odom', 0)}`",
        f"- Controller odom sign: `{topic_signs.get('controller_odom', 0)}`",
        "",
        "## Fixtures",
        "",
        ]
    )
    for payload in _ordered_fixture_payloads(fixture_payloads):
        source_surface_signs = (
            payload.get("source_surface_signs", {})
            if isinstance(payload.get("source_surface_signs"), dict)
            else {}
        )
        fresh_probe_signs = (
            payload.get("fresh_probe_signs", {})
            if isinstance(payload.get("fresh_probe_signs"), dict)
            else {}
        )
        source_alignment_matches = (
            payload.get("source_alignment_matches", {})
            if isinstance(payload.get("source_alignment_matches"), dict)
            else {}
        )
        lines.append(
            f"- `{payload.get('fixture_label', '')}` source=`{payload.get('source_fixture_diagnosis', '')}` "
            f"relevant=`{bool(payload.get('probe_hypothesis_relevant', False))}` "
            f"runtime_support=`{bool(payload.get('runtime_probe_supports_source_fixture', False))}` "
            f"runtime=`{payload.get('runtime_diagnosis', '')}` "
            f"source_cmd=`{int(payload.get('source_command_sign', 0) or 0)}` "
            f"fresh_cmd=`{int(fresh_probe_signs.get('requested_command', 0) or 0)}` "
            f"source_cmd_relation=`{((payload.get('source_probe_command_sign_comparison', {}) or {}).get('relation', ''))}` "
            f"source_cmd->fresh=`{source_alignment_matches.get('source_command_to_fresh_requested')}` "
            f"source_world=`{int(source_surface_signs.get('world', 0) or 0)}` "
            f"fresh_world=`{int(fresh_probe_signs.get('world_truth', 0) or 0)}` "
            f"source_world->fresh=`{source_alignment_matches.get('source_world_to_fresh_world')}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def _copy_if_needed(source_path: Path | None, destination_path: Path) -> Path | None:
    if source_path is None or not source_path.exists():
        return None
    source_resolved = source_path.resolve()
    destination_resolved = destination_path.resolve()
    if source_resolved == destination_resolved:
        return destination_resolved
    shutil.copyfile(source_resolved, destination_resolved)
    return destination_resolved


def write_odom_world_sign_chain_bundle(
    *,
    campaign_id: str,
    summary: dict[str, Any],
    fixture_payloads: dict[str, dict[str, Any]],
    repo_root: Path = REPO_ROOT,
    runtime_probe_json_path: Path | None = None,
    runtime_probe_stdout_path: Path | None = None,
    runtime_probe_stderr_path: Path | None = None,
) -> dict[str, Path]:
    output_root = ensure_dir(Path(repo_root) / "artifacts" / "session" / campaign_id / "probe_odom_world_sign_chain")
    fixtures_root = ensure_dir(output_root / "fixtures")
    logs_root = ensure_dir(output_root / "logs")
    summary_path = output_root / "odom_world_sign_chain_summary.json"
    scorecard_path = output_root / "scorecard.md"
    runtime_probe_bundle_path = output_root / "runtime_probe.json"
    _copy_if_needed(runtime_probe_json_path, runtime_probe_bundle_path)
    _copy_if_needed(runtime_probe_stdout_path, logs_root / "runtime_probe.stdout.log")
    _copy_if_needed(runtime_probe_stderr_path, logs_root / "runtime_probe.stderr.log")
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary, fixture_payloads), encoding="utf-8")
    for fixture_label, payload in fixture_payloads.items():
        write_json(fixtures_root / f"{fixture_label}.json", payload)
    return {
        "output_root": output_root,
        "fixtures_root": fixtures_root,
        "logs_root": logs_root,
        "summary_path": summary_path,
        "scorecard_path": scorecard_path,
        "runtime_probe_json_path": runtime_probe_bundle_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Correlate a fresh manual-drive runtime sign probe against the frozen odom/world sign-parity audit "
            "so the next runtime-check branch is artifact-backed."
        )
    )
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SCENARIO_ID)
    parser.add_argument(
        "--campaign-summary-path",
        default=str(DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_CAMPAIGN_SUMMARY),
        help="Fresh probe campaign summary from gather_mission_repeatability_runner.py.",
    )
    parser.add_argument(
        "--source-campaign-summary-path",
        default=str(DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_CAMPAIGN_SUMMARY),
    )
    parser.add_argument(
        "--source-audit-summary-path",
        default=str(DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SOURCE_AUDIT_SUMMARY),
    )
    parser.add_argument("--runtime-probe-json-path", required=True)
    parser.add_argument("--runtime-probe-stdout-path", default="")
    parser.add_argument("--runtime-probe-stderr-path", default="")
    parser.add_argument("--run-index", type=int, default=DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_RUN_INDEX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip() or oracle.current_utc_stamp()
    summary, fixture_payloads = build_odom_world_sign_chain_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=Path(args.campaign_summary_path).resolve(),
        runtime_probe_json_path=Path(args.runtime_probe_json_path).resolve(),
        source_audit_summary_path=Path(args.source_audit_summary_path).resolve(),
        source_campaign_summary_path=Path(args.source_campaign_summary_path).resolve(),
        run_index=int(args.run_index),
        scenario_id=str(args.scenario_id or DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SCENARIO_ID),
        runtime_probe_stdout_path=(
            Path(args.runtime_probe_stdout_path).resolve() if str(args.runtime_probe_stdout_path or "").strip() else None
        ),
        runtime_probe_stderr_path=(
            Path(args.runtime_probe_stderr_path).resolve() if str(args.runtime_probe_stderr_path or "").strip() else None
        ),
    )
    output_paths = write_odom_world_sign_chain_bundle(
        campaign_id=campaign_id,
        summary=summary,
        fixture_payloads=fixture_payloads,
        runtime_probe_json_path=Path(args.runtime_probe_json_path).resolve(),
        runtime_probe_stdout_path=(
            Path(args.runtime_probe_stdout_path).resolve() if str(args.runtime_probe_stdout_path or "").strip() else None
        ),
        runtime_probe_stderr_path=(
            Path(args.runtime_probe_stderr_path).resolve() if str(args.runtime_probe_stderr_path or "").strip() else None
        ),
    )
    print(f"PROBE_ODOM_WORLD_SIGN_CHAIN_SUMMARY={output_paths['summary_path']}")
    print(
        json.dumps(
            {
                "campaign_id": summary.get("campaign_id", ""),
                "decision": ((summary.get("next_action", {}) or {}).get("decision", "")),
                "diagnosis": ((summary.get("runtime_classification", {}) or {}).get("diagnosis", "")),
                "runtime_supported_source_fixture_count": summary.get("runtime_supported_source_fixture_count", 0),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if str((summary.get("runtime_classification", {}) or {}).get("diagnosis", "")) != "runtime_sign_chain_inconclusive" else 2


if __name__ == "__main__":
    raise SystemExit(main())
