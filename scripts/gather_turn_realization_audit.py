#!/usr/bin/env python3
"""Artifact-first turn-realization contract audit for manual gather pre-stage behavior."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import gather_escape_divergence_audit as divergence
import gather_escape_feasibility_audit as feasibility
import gather_escape_oracle as oracle
import gather_escape_reference as reference
import gather_short_horizon_helpers as short_horizon_helpers
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import write_json


DEFAULT_TURN_REALIZATION_AUDIT_CAMPAIGN_SUMMARY = divergence.DEFAULT_ESCAPE_DIVERGENCE_AUDIT_CAMPAIGN_SUMMARY
DEFAULT_TURN_REALIZATION_AUDIT_RUN_INDEX = divergence.DEFAULT_ESCAPE_DIVERGENCE_AUDIT_RUN_INDEX
DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID = divergence.DEFAULT_ESCAPE_DIVERGENCE_AUDIT_SCENARIO_ID
DEFAULT_TURN_REALIZATION_AUDIT_PRIMARY_FAMILY = divergence.DEFAULT_ESCAPE_DIVERGENCE_AUDIT_PRIMARY_FAMILY
DEFAULT_TURN_REALIZATION_AUDIT_HORIZON_S = divergence.DEFAULT_ESCAPE_DIVERGENCE_AUDIT_HORIZON_S
DEFAULT_TURN_REALIZATION_AUDIT_REQUIRED_DOMINANT_FIXTURES = 3
DEFAULT_TURN_REALIZATION_AUDIT_DOWNSTREAM_HEADROOM_RATIO = 0.85
DEFAULT_TURN_REALIZATION_AUDIT_OFFLINE_DEMAND_RATIO = 0.85
DEFAULT_TURN_REALIZATION_AUDIT_REALIZATION_RATIO_MIN = (
    divergence.DEFAULT_ESCAPE_DIVERGENCE_AUDIT_TURN_REALIZATION_MIN_RATIO
)
DEFAULT_TURN_REALIZATION_AUDIT_REALIZED_STEP_MIN_RAD = 0.02

GATHER_MISSION_HELPERS_PATH = REPO_ROOT / "scripts" / "gather_mission_helpers.py"
GATHER_MOTION_BRIDGE_PATH = REPO_ROOT / "scripts" / "gather_motion_bridge.py"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _number(value: Any, *, default: float | None = None) -> float | None:
    return divergence._number(value, default=default)


def _sign(value: float, *, eps: float = 1.0e-6) -> int:
    return divergence._sign(value, eps=eps)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return divergence._safe_ratio(numerator, denominator)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _max_abs_clamp_bound_from_text(text: str, *, source_label: str) -> float:
    pattern = re.compile(
        r"clamp\((?P<expr>.+?),\s*(?P<minimum>-?\d+(?:\.\d+)?),\s*(?P<maximum>-?\d+(?:\.\d+)?)\)"
    )
    max_abs = 0.0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "clamp(" not in line:
            continue
        match = pattern.search(line)
        if match is None:
            continue
        max_abs = max(
            max_abs,
            abs(float(match.group("minimum"))),
            abs(float(match.group("maximum"))),
        )
    if max_abs <= 0.0:
        raise ValueError(f"Unable to resolve clamp cap from {source_label}")
    return round(max_abs, 6)


def _function_block(path: Path, *, function_name: str) -> str:
    text = _read_text(path)
    marker = f"def {function_name}("
    start_index = text.find(marker)
    if start_index < 0:
        raise ValueError(f"Unable to resolve function block {function_name} from {path}")
    tail = text[start_index:]
    lines = tail.splitlines()
    block_lines: list[str] = []
    for index, line in enumerate(lines):
        if index > 0 and line.startswith("def "):
            break
        block_lines.append(line)
    return "\n".join(block_lines)


def _cli_default(path: Path, *, arg_name: str) -> float:
    pattern = re.compile(
        rf'add_argument\("{re.escape(arg_name)}".*?default=(?P<value>\d+(?:\.\d+)?)'
    )
    match = pattern.search(_read_text(path))
    if match is None:
        raise ValueError(f"Unable to resolve CLI default for {arg_name} from {path}")
    return round(float(match.group("value")), 6)


def load_turn_limit_surfaces() -> dict[str, Any]:
    audit_contract = feasibility.load_audit_repo_contract()
    gather_mission_cap = _max_abs_clamp_bound_from_text(
        _function_block(GATHER_MISSION_HELPERS_PATH, function_name="compute_pre_stage_command"),
        source_label=f"{GATHER_MISSION_HELPERS_PATH}:compute_pre_stage_command",
    )
    short_horizon_cap = round(float(short_horizon_helpers.DEFAULT_SHORT_HORIZON_ANGULAR_LIMIT), 6)
    bridge_cap = _cli_default(GATHER_MOTION_BRIDGE_PATH, arg_name="--max-angular-z")
    controller_cap = round(float(audit_contract.controller_max_angular_velocity_radps), 6)
    hardware_cap = round(float(audit_contract.hardware_max_angular_velocity_radps), 6)
    downstream_cap = round(min(bridge_cap, controller_cap, hardware_cap), 6)
    return {
        "gather_mission_helper_abs_angular_cap_radps": gather_mission_cap,
        "short_horizon_helper_abs_angular_cap_radps": short_horizon_cap,
        "gather_motion_bridge_abs_angular_cap_radps": bridge_cap,
        "diff_drive_controller_abs_angular_cap_radps": controller_cap,
        "hardware_abs_angular_cap_radps": hardware_cap,
        "effective_manual_drive_downstream_cap_radps": downstream_cap,
        "sources": {
            "gather_mission_helpers": str(GATHER_MISSION_HELPERS_PATH),
            "short_horizon_helpers": str((REPO_ROOT / "scripts" / "gather_short_horizon_helpers.py").resolve()),
            "gather_motion_bridge": str(GATHER_MOTION_BRIDGE_PATH),
            "diff_drive_controller": str(feasibility.CONTROLLERS_PATH),
            "hardware_constraints": str(feasibility.HARDWARE_CONSTRAINTS_PATH),
        },
    }


def _active_helper_surface(
    controller_family: str,
    turn_surfaces: dict[str, Any],
) -> tuple[str, float]:
    if str(controller_family or "").strip() in {"short_horizon_v1", "short_horizon_v2"}:
        return (
            "short_horizon_helper_abs_angular_cap_radps",
            float(turn_surfaces["short_horizon_helper_abs_angular_cap_radps"]),
        )
    return (
        "gather_mission_helper_abs_angular_cap_radps",
        float(turn_surfaces["gather_mission_helper_abs_angular_cap_radps"]),
    )


def _expected_turn_sign_from_macro_sequence(macro_sequence: list[str] | tuple[str, ...]) -> int:
    left_count = sum(1 for item in macro_sequence if "_left" in str(item))
    right_count = sum(1 for item in macro_sequence if "_right" in str(item))
    if left_count > right_count:
        return 1
    if right_count > left_count:
        return -1
    return 0


def _macro_turn_contract(
    maneuver_name: str,
    *,
    maneuver_library: dict[str, oracle.EscapeMacro],
    profile_name: str,
    audit_contract: feasibility.AuditRepoContract,
) -> tuple[float, float, int]:
    maneuver = maneuver_library[maneuver_name]
    adapted = feasibility._adapt_maneuver_for_profile(
        maneuver,
        profile_name=profile_name,
        audit_contract=audit_contract,
    )
    peak_angular_z = max(abs(float(segment.angular_z)) for segment in adapted.segments)
    angular_integral = sum(abs(float(segment.angular_z)) * float(segment.duration_s) for segment in adapted.segments)
    net_turn = sum(float(segment.angular_z) * float(segment.duration_s) for segment in adapted.segments)
    return round(peak_angular_z, 6), round(angular_integral, 6), _sign(net_turn)


def _select_offline_turn_baseline(
    local_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone,
    audit_contract: feasibility.AuditRepoContract,
    maneuver_library: dict[str, oracle.EscapeMacro],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    feasibility_rank = {
        "corridor_clearable": 3,
        "goal_side_clearable": 2,
        "near_clear": 1,
        "not_clearable": 0,
    }
    profile_order = {"nominal_current": 0, "combined_relaxed": 1}
    for profile_name in ("nominal_current", "combined_relaxed"):
        results = feasibility.search_audit_maneuvers_local(
            local_pose,
            ball_pose,
            zone=zone,
            audit_contract=audit_contract,
            maneuver_library=maneuver_library,
            profile_name=profile_name,
            top_k=1,
            include_trajectories=True,
        )
        if not results:
            continue
        best = results[0]
        maneuver_name = str(best.macro_sequence[0]) if best.macro_sequence else ""
        peak_angular_z, angular_integral, net_turn_sign = _macro_turn_contract(
            maneuver_name,
            maneuver_library=maneuver_library,
            profile_name=profile_name,
            audit_contract=audit_contract,
        )
        expected_turn_sign = net_turn_sign or _expected_turn_sign_from_macro_sequence(best.macro_sequence)
        candidates.append(
            {
                "profile_name": profile_name,
                "family_name": str(best.family_name),
                "macro_sequence": list(best.macro_sequence),
                "feasibility_class": str(best.feasibility_class),
                "projection_gain_m": round(float(best.projection_gain), 6),
                "lateral_gain_m": round(float(best.lateral_gain), 6),
                "distance_gain_m": round(float(best.distance_gain), 6),
                "peak_angular_z_radps": peak_angular_z,
                "angular_integral_rad": angular_integral,
                "expected_turn_sign": int(expected_turn_sign),
                "yaw_progress_rad": divergence._trajectory_yaw_progress(local_pose, list(best.trajectory_local)),
            }
        )
    if not candidates:
        return {}
    best_candidate = max(
        candidates,
        key=lambda item: (
            int(feasibility_rank.get(str(item.get("feasibility_class", "")), 0)),
            float(item.get("projection_gain_m", 0.0)),
            float(item.get("lateral_gain_m", 0.0)),
            float(item.get("yaw_progress_rad", 0.0)),
            -int(profile_order.get(str(item.get("profile_name", "")), 99)),
        ),
    )
    return best_candidate


def _state_window_for_fixture(
    fixture: dict[str, Any],
    *,
    state_rows: list[dict[str, Any]],
    truth_samples: list[dict[str, Any]],
    timeline_anchor: dict[str, Any] | None,
    scenario_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    zone = divergence.build_zone_spec(scenario_id)
    alignment = divergence.align_fixture_to_truth_sample(fixture, truth_samples, timeline_anchor=timeline_anchor)
    matched_index = int(alignment.get("matched_truth_index", -1) or -1)
    matched_truth_t_s = _number(alignment.get("matched_truth_t_s"))
    fixture_utc = divergence._parse_utc(fixture.get("generated_utc"))
    ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
    truth_window, end_truth_t_s = divergence._truth_window_samples(
        truth_samples,
        start_index=matched_index,
        horizon_s=DEFAULT_TURN_REALIZATION_AUDIT_HORIZON_S,
    )
    enriched_truth = divergence._enrich_truth_window(truth_window, fallback_ball_pose=ball_pose, zone=zone)
    state_window = divergence._state_rows_within_window(
        state_rows,
        fixture_index=int(fixture.get("fixture_index", 0) or 0),
        fixture_utc=fixture_utc,
        fixture_truth_t_s=matched_truth_t_s,
        end_truth_t_s=end_truth_t_s,
    )
    return alignment, enriched_truth, state_window


def _episode_count(
    signs: list[int],
    *,
    opposite_of: int,
) -> int:
    if opposite_of == 0:
        return 0
    episodes = 0
    active = False
    for sign in signs:
        current_wrong = sign != 0 and sign == -opposite_of
        if current_wrong and not active:
            episodes += 1
        active = current_wrong
    return episodes


def compute_fixture_turn_contract(
    fixture: dict[str, Any],
    *,
    state_rows: list[dict[str, Any]],
    truth_samples: list[dict[str, Any]],
    timeline_anchor: dict[str, Any] | None,
    turn_surfaces: dict[str, Any],
    scenario_id: str = DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID,
    audit_contract: feasibility.AuditRepoContract | None = None,
    maneuver_library: dict[str, oracle.EscapeMacro] | None = None,
) -> dict[str, Any]:
    zone = divergence.build_zone_spec(scenario_id)
    audit_contract = audit_contract or feasibility.load_audit_repo_contract()
    maneuver_library = maneuver_library or reference.build_reference_maneuver_library()
    base_metrics = divergence.compute_fixture_metrics(
        fixture,
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
        scenario_id=scenario_id,
        audit_contract=audit_contract,
    )
    alignment, enriched_truth, state_window = _state_window_for_fixture(
        fixture,
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
        scenario_id=scenario_id,
    )
    local_pose = fixture.get("robot_pose_local", {}) if isinstance(fixture.get("robot_pose_local"), dict) else {}
    ball_pose = fixture.get("ball_pose", {}) if isinstance(fixture.get("ball_pose"), dict) else {}
    controller_debug = base_metrics.get("controller_debug", {}) if isinstance(base_metrics.get("controller_debug"), dict) else {}
    controller_family = str(controller_debug.get("controller_family", "") or "")
    helper_surface_name, active_helper_cap = _active_helper_surface(controller_family, turn_surfaces)
    downstream_cap = float(turn_surfaces["effective_manual_drive_downstream_cap_radps"])
    bridge_cap = float(turn_surfaces["gather_motion_bridge_abs_angular_cap_radps"])
    controller_cap = float(turn_surfaces["diff_drive_controller_abs_angular_cap_radps"])
    hardware_cap = float(turn_surfaces["hardware_abs_angular_cap_radps"])

    command_rows = list(state_window)
    if not command_rows and isinstance(fixture.get("selected_command"), dict):
        command_rows = [
            {
                **fixture,
                "_estimated_t_s": float(_number(alignment.get("matched_truth_t_s"), default=0.0) or 0.0),
            }
        ]
    command_times = [
        float(_number(row.get("_estimated_t_s"), default=float(index)) or float(index))
        for index, row in enumerate(command_rows)
    ]

    peak_requested_angular_z = 0.0
    nonzero_command_sample_count = 0
    pinned_at_helper_cap_count = 0
    command_net_angular = 0.0
    commanded_angular_integral = 0.0

    for index, row in enumerate(command_rows):
        command = row.get("selected_command", {}) if isinstance(row.get("selected_command"), dict) else {}
        angular_z = float(_number(command.get("angular_z"), default=0.0) or 0.0)
        current_t_s = command_times[index]
        if index + 1 < len(command_times):
            next_t_s = command_times[index + 1]
        else:
            next_t_s = current_t_s + 1.0 if len(command_rows) == 1 else current_t_s
        dt_s = max(next_t_s - current_t_s, 0.0)
        peak_requested_angular_z = max(peak_requested_angular_z, abs(angular_z))
        commanded_angular_integral += abs(angular_z) * dt_s
        if abs(angular_z) > 1.0e-6:
            nonzero_command_sample_count += 1
            if abs(abs(angular_z) - active_helper_cap) <= 1.0e-6:
                pinned_at_helper_cap_count += 1
        command_net_angular += angular_z * dt_s

    offline_turn_baseline = _select_offline_turn_baseline(
        local_pose,
        ball_pose,
        zone=zone,
        audit_contract=audit_contract,
        maneuver_library=maneuver_library,
    )
    dominant_command_sign = _sign(command_net_angular)
    target_turn_sign = dominant_command_sign or int(offline_turn_baseline.get("expected_turn_sign", 0) or 0)

    command_signs: list[int] = []
    for row in command_rows:
        command = row.get("selected_command", {}) if isinstance(row.get("selected_command"), dict) else {}
        command_signs.append(_sign(float(_number(command.get("angular_z"), default=0.0) or 0.0)))
    wrong_sign_command_episode_count = _episode_count(command_signs, opposite_of=target_turn_sign)
    wrong_sign_command_sample_count = sum(
        1 for sign in command_signs if target_turn_sign != 0 and sign != 0 and sign == -target_turn_sign
    )

    realized_yaw_signs: list[int] = []
    for previous, current in zip(enriched_truth, enriched_truth[1:]):
        previous_robot_pose = previous.get("robot_pose")
        current_robot_pose = current.get("robot_pose")
        previous_xyyaw = divergence.world_pose_xyyaw(previous_robot_pose) if isinstance(previous_robot_pose, dict) else None
        current_xyyaw = divergence.world_pose_xyyaw(current_robot_pose) if isinstance(current_robot_pose, dict) else None
        if previous_xyyaw is None or current_xyyaw is None:
            continue
        yaw_delta = divergence.normalize_angle(float(current_xyyaw[2]) - float(previous_xyyaw[2]))
        if abs(yaw_delta) < DEFAULT_TURN_REALIZATION_AUDIT_REALIZED_STEP_MIN_RAD:
            realized_yaw_signs.append(0)
        else:
            realized_yaw_signs.append(_sign(yaw_delta))
    wrong_sign_realized_yaw_episode_count = _episode_count(realized_yaw_signs, opposite_of=target_turn_sign)
    wrong_sign_realized_yaw_step_count = sum(
        1 for sign in realized_yaw_signs if target_turn_sign != 0 and sign != 0 and sign == -target_turn_sign
    )

    yaw_realization_ratio = _number(
        ((base_metrics.get("derived_metrics", {}) or {}).get("yaw_realization_ratio")),
        default=None,
    )
    offline_peak_angular_z = float(_number(offline_turn_baseline.get("peak_angular_z_radps"), default=0.0) or 0.0)
    offline_angular_integral = float(
        _number(offline_turn_baseline.get("angular_integral_rad"), default=0.0) or 0.0
    )

    peak_materially_below_downstream_cap = bool(
        downstream_cap > 0.0
        and peak_requested_angular_z <= (downstream_cap * DEFAULT_TURN_REALIZATION_AUDIT_DOWNSTREAM_HEADROOM_RATIO)
    )
    peak_materially_below_offline_demand = bool(
        offline_peak_angular_z > 0.0
        and peak_requested_angular_z <= (offline_peak_angular_z * DEFAULT_TURN_REALIZATION_AUDIT_OFFLINE_DEMAND_RATIO)
    )
    integral_materially_below_offline_demand = bool(
        offline_angular_integral > 0.0
        and commanded_angular_integral <= (offline_angular_integral * DEFAULT_TURN_REALIZATION_AUDIT_OFFLINE_DEMAND_RATIO)
    )
    request_adequate_for_offline = bool(
        (offline_peak_angular_z <= 1.0e-9 or peak_requested_angular_z >= (offline_peak_angular_z * DEFAULT_TURN_REALIZATION_AUDIT_OFFLINE_DEMAND_RATIO))
        or (
            offline_angular_integral > 1.0e-9
            and commanded_angular_integral >= (offline_angular_integral * DEFAULT_TURN_REALIZATION_AUDIT_OFFLINE_DEMAND_RATIO)
        )
    )

    strategy_authority_limited = bool(
        peak_materially_below_downstream_cap
        and (peak_materially_below_offline_demand or integral_materially_below_offline_demand)
    )
    sign_parity_limited = bool(
        wrong_sign_realized_yaw_episode_count >= 1 and wrong_sign_realized_yaw_step_count >= 2
    )
    plant_realization_limited = bool(
        request_adequate_for_offline
        and yaw_realization_ratio is not None
        and float(yaw_realization_ratio) < DEFAULT_TURN_REALIZATION_AUDIT_REALIZATION_RATIO_MIN
    )

    fixture_gap = "mixed_turn_contract_limited"
    if strategy_authority_limited:
        fixture_gap = "strategy_authority_limited"
    elif sign_parity_limited:
        fixture_gap = "sign_parity_limited"
    elif plant_realization_limited:
        fixture_gap = "plant_realization_limited"

    comparison = {
        "live_to_offline_peak_request_ratio": _safe_ratio(peak_requested_angular_z, offline_peak_angular_z),
        "live_to_offline_angular_integral_ratio": _safe_ratio(commanded_angular_integral, offline_angular_integral),
        "peak_materially_below_downstream_cap": peak_materially_below_downstream_cap,
        "peak_materially_below_offline_demand": peak_materially_below_offline_demand,
        "integral_materially_below_offline_demand": integral_materially_below_offline_demand,
        "request_adequate_for_offline": request_adequate_for_offline,
    }

    command_metrics = base_metrics.get("command_metrics", {}) if isinstance(base_metrics.get("command_metrics"), dict) else {}
    command_metrics = {
        **command_metrics,
        "commanded_angular_integral_rad": round(commanded_angular_integral, 6),
        "peak_requested_angular_z_radps": round(peak_requested_angular_z, 6),
        "nonzero_command_sample_count": int(nonzero_command_sample_count),
        "samples_pinned_at_helper_cap": int(pinned_at_helper_cap_count),
        "percent_samples_pinned_at_helper_cap": round(
            (float(pinned_at_helper_cap_count) / float(nonzero_command_sample_count) * 100.0)
            if nonzero_command_sample_count > 0
            else 0.0,
            6,
        ),
        "dominant_command_sign": int(dominant_command_sign),
        "wrong_sign_command_episode_count": int(wrong_sign_command_episode_count),
        "wrong_sign_command_sample_count": int(wrong_sign_command_sample_count),
        "headroom_to_helper_cap_radps": round(active_helper_cap - peak_requested_angular_z, 6),
        "headroom_to_bridge_cap_radps": round(bridge_cap - peak_requested_angular_z, 6),
        "headroom_to_controller_cap_radps": round(controller_cap - peak_requested_angular_z, 6),
        "headroom_to_hardware_cap_radps": round(hardware_cap - peak_requested_angular_z, 6),
    }

    realized_metrics = base_metrics.get("realized_metrics", {}) if isinstance(base_metrics.get("realized_metrics"), dict) else {}
    realized_metrics = {
        **realized_metrics,
        "wrong_sign_realized_yaw_episode_count": int(wrong_sign_realized_yaw_episode_count),
        "wrong_sign_realized_yaw_step_count": int(wrong_sign_realized_yaw_step_count),
        "realized_yaw_change_per_commanded_angular_rad": _round_or_none(yaw_realization_ratio),
    }

    return {
        **base_metrics,
        "alignment": alignment,
        "turn_limit_surfaces": {
            "active_helper_surface": helper_surface_name,
            "active_helper_abs_angular_cap_radps": round(active_helper_cap, 6),
            "gather_motion_bridge_abs_angular_cap_radps": bridge_cap,
            "diff_drive_controller_abs_angular_cap_radps": controller_cap,
            "hardware_abs_angular_cap_radps": hardware_cap,
            "effective_manual_drive_downstream_cap_radps": round(downstream_cap, 6),
        },
        "command_metrics": command_metrics,
        "realized_metrics": realized_metrics,
        "offline_turn_baseline": {
            **offline_turn_baseline,
            "comparison": comparison,
        },
        "classifier_flags": {
            "strategy_authority_limited": strategy_authority_limited,
            "sign_parity_limited": sign_parity_limited,
            "plant_realization_limited": plant_realization_limited,
        },
        "fixture_gap": fixture_gap,
    }


def decide_dominant_gap(fixture_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    strategy_count = 0
    sign_parity_count = 0
    plant_count = 0
    for payload in fixture_payloads:
        flags = payload.get("classifier_flags", {}) if isinstance(payload.get("classifier_flags"), dict) else {}
        if bool(flags.get("strategy_authority_limited", False)):
            strategy_count += 1
        if bool(flags.get("sign_parity_limited", False)):
            sign_parity_count += 1
        if bool(flags.get("plant_realization_limited", False)):
            plant_count += 1

    if strategy_count >= DEFAULT_TURN_REALIZATION_AUDIT_REQUIRED_DOMINANT_FIXTURES:
        dominant_gap = "strategy_authority_limited"
        coverage_count = strategy_count
    elif sign_parity_count >= DEFAULT_TURN_REALIZATION_AUDIT_REQUIRED_DOMINANT_FIXTURES:
        dominant_gap = "sign_parity_limited"
        coverage_count = sign_parity_count
    elif plant_count >= DEFAULT_TURN_REALIZATION_AUDIT_REQUIRED_DOMINANT_FIXTURES:
        dominant_gap = "plant_realization_limited"
        coverage_count = plant_count
    else:
        dominant_gap = "mixed_turn_contract_limited"
        coverage_count = max(strategy_count, sign_parity_count, plant_count)

    confidence = (
        "high"
        if coverage_count >= 4
        else "medium"
        if coverage_count >= DEFAULT_TURN_REALIZATION_AUDIT_REQUIRED_DOMINANT_FIXTURES
        else "low"
    )
    return {
        "dominant_gap": dominant_gap,
        "confidence": confidence,
        "dominant_coverage_count": int(coverage_count),
        "strategy_authority_fixture_count": int(strategy_count),
        "sign_parity_fixture_count": int(sign_parity_count),
        "plant_realization_fixture_count": int(plant_count),
    }


def _aggregate_alignment_source(fixture_payloads: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    return divergence._aggregate_alignment_source(fixture_payloads)


def _next_action_recommendation(dominant_gap: str) -> dict[str, str]:
    if dominant_gap == "strategy_authority_limited":
        return {
            "recommended_focus": "helper_turn_authority_contract_audit",
            "rationale": "The live pre-stage path is not requesting the same turn authority that the best offline escape maneuver demands.",
        }
    if dominant_gap == "sign_parity_limited":
        return {
            "recommended_focus": "manual_drive_sign_parity_audit",
            "rationale": "The realized yaw repeatedly opposes the requested turn sign, so the next slice should inspect bridge, diff-drive, odom, and world-sign parity.",
        }
    if dominant_gap == "plant_realization_limited":
        return {
            "recommended_focus": "manual_drive_plant_realization_audit",
            "rationale": "Requested turn authority is adequate, but the robot does not realize the expected yaw progress in the world.",
        }
    return {
        "recommended_focus": "mixed_turn_contract_review",
        "rationale": "The current fixtures do not point to one dominant turn contract gap yet; resolve the mixed signals before changing live behavior.",
    }


def build_turn_realization_audit_bundle(
    *,
    campaign_id: str,
    campaign_summary_path: Path = DEFAULT_TURN_REALIZATION_AUDIT_CAMPAIGN_SUMMARY,
    run_index: int = DEFAULT_TURN_REALIZATION_AUDIT_RUN_INDEX,
    scenario_id: str = DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    paths = divergence.resolve_run_artifact_paths(campaign_summary_path, run_index=run_index)
    state_history_path = Path(paths["state_history_path"])
    mission_verdict_path = Path(paths["mission_verdict_path"])
    gather_sequence_path = Path(paths["gather_sequence_path"])
    truth_timeline_path = Path(paths["truth_timeline_path"])
    timeline_path = Path(paths["timeline_path"])
    timeline_events_path = Path(paths["timeline_events_path"])

    state_rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
    representative_fixtures = divergence.extract_representative_fixtures(
        state_history_path,
        scenario_id=scenario_id,
        attempt=0,
    )
    truth_samples = divergence._sorted_truth_samples(read_json(truth_timeline_path))
    timeline_payload = read_json(timeline_path) if timeline_path.exists() else {}
    timeline_event_rows = divergence._read_jsonl(timeline_events_path)
    timeline_anchor = divergence.extract_timeline_utc_anchor(
        timeline_payload if isinstance(timeline_payload, dict) else {},
        timeline_event_rows,
    )
    audit_contract = feasibility.load_audit_repo_contract()
    turn_surfaces = load_turn_limit_surfaces()
    maneuver_library = reference.build_reference_maneuver_library()

    fixture_payloads: dict[str, dict[str, Any]] = {}
    for fixture in representative_fixtures:
        payload = compute_fixture_turn_contract(
            fixture,
            state_rows=state_rows,
            truth_samples=truth_samples,
            timeline_anchor=timeline_anchor,
            scenario_id=scenario_id,
            turn_surfaces=turn_surfaces,
            audit_contract=audit_contract,
            maneuver_library=maneuver_library,
        )
        fixture_payloads[str(payload.get("fixture_label", ""))] = payload

    ordered_fixture_payloads = list(fixture_payloads.values())
    gap_decision = decide_dominant_gap(ordered_fixture_payloads)
    alignment_source, alignment_source_counts = _aggregate_alignment_source(ordered_fixture_payloads)
    gap_counts = Counter(str(payload.get("fixture_gap", "") or "mixed_turn_contract_limited") for payload in ordered_fixture_payloads)
    mission_verdict = read_json(mission_verdict_path) if mission_verdict_path.exists() else {}
    gather_sequence_rows = divergence._read_jsonl(gather_sequence_path)

    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "gather_turn_realization_audit",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "primary_trace_family": DEFAULT_TURN_REALIZATION_AUDIT_PRIMARY_FAMILY,
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
        "turn_limit_surfaces": turn_surfaces,
        "dominant_gap": gap_decision["dominant_gap"],
        "confidence": gap_decision["confidence"],
        "dominant_gap_fixture_count": gap_decision["dominant_coverage_count"],
        "gap_counts": dict(gap_counts),
        "root_cause_gate": gap_decision,
        "next_action_recommendation": _next_action_recommendation(str(gap_decision["dominant_gap"])),
        "run_context": {
            "mission_verdict": mission_verdict,
            "gather_sequence": divergence._gather_sequence_brief(gather_sequence_rows),
        },
        "fixtures": [
            {
                "fixture_label": payload.get("fixture_label", ""),
                "fixture_gap": payload.get("fixture_gap", ""),
                "alignment_quality": ((payload.get("alignment", {}) or {}).get("quality", "")),
                "peak_requested_angular_z_radps": ((payload.get("command_metrics", {}) or {}).get("peak_requested_angular_z_radps")),
                "percent_samples_pinned_at_helper_cap": ((payload.get("command_metrics", {}) or {}).get("percent_samples_pinned_at_helper_cap")),
                "wrong_sign_realized_yaw_episode_count": ((payload.get("realized_metrics", {}) or {}).get("wrong_sign_realized_yaw_episode_count")),
                "realized_yaw_change_per_commanded_angular_rad": ((payload.get("realized_metrics", {}) or {}).get("realized_yaw_change_per_commanded_angular_rad")),
                "offline_family_name": ((payload.get("offline_turn_baseline", {}) or {}).get("family_name", "")),
                "offline_profile_name": ((payload.get("offline_turn_baseline", {}) or {}).get("profile_name", "")),
            }
            for payload in ordered_fixture_payloads
        ],
    }
    return summary, fixture_payloads


def build_scorecard_markdown(summary: dict[str, Any], fixture_payloads: dict[str, dict[str, Any]]) -> str:
    surfaces = summary.get("turn_limit_surfaces", {}) if isinstance(summary.get("turn_limit_surfaces"), dict) else {}
    lines = [
        "# Gather Turn Realization Audit Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Source campaign: `{summary.get('source_campaign_id', '')}`",
        f"- Source run index: `{summary.get('source_run_index', 0)}`",
        f"- Dominant gap: `{summary.get('dominant_gap', '')}`",
        f"- Confidence: `{summary.get('confidence', '')}`",
        f"- Alignment source: `{summary.get('alignment_source', '')}`",
        f"- Next action: `{((summary.get('next_action_recommendation', {}) or {}).get('recommended_focus', ''))}`",
        "",
        "## Turn Limit Surfaces",
        "",
        f"- Gather mission helper cap: `{float(surfaces.get('gather_mission_helper_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Short-horizon helper cap: `{float(surfaces.get('short_horizon_helper_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Gather motion bridge cap: `{float(surfaces.get('gather_motion_bridge_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Diff-drive controller cap: `{float(surfaces.get('diff_drive_controller_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Hardware cap: `{float(surfaces.get('hardware_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        "",
        "## Root Cause Gate",
        "",
        f"- Dominant coverage: `{summary.get('dominant_gap_fixture_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Gap counts: `{json.dumps(summary.get('gap_counts', {}), sort_keys=True)}`",
        "",
        "## Fixtures",
        "",
    ]
    for fixture_label in (
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    ):
        payload = fixture_payloads.get(fixture_label, {})
        command_metrics = payload.get("command_metrics", {}) if isinstance(payload.get("command_metrics"), dict) else {}
        realized_metrics = payload.get("realized_metrics", {}) if isinstance(payload.get("realized_metrics"), dict) else {}
        offline_turn_baseline = payload.get("offline_turn_baseline", {}) if isinstance(payload.get("offline_turn_baseline"), dict) else {}
        comparison = offline_turn_baseline.get("comparison", {}) if isinstance(offline_turn_baseline.get("comparison"), dict) else {}
        turn_limit_surfaces = payload.get("turn_limit_surfaces", {}) if isinstance(payload.get("turn_limit_surfaces"), dict) else {}
        lines.append(
            f"- `{fixture_label}` gap=`{payload.get('fixture_gap', '')}` "
            f"helper_cap=`{float(turn_limit_surfaces.get('active_helper_abs_angular_cap_radps', 0.0)):.3f}` "
            f"peak_request=`{float(command_metrics.get('peak_requested_angular_z_radps', 0.0)):.3f}` "
            f"pinned=`{float(command_metrics.get('percent_samples_pinned_at_helper_cap', 0.0)):.1f}%` "
            f"downstream_headroom=`{float(command_metrics.get('headroom_to_bridge_cap_radps', 0.0)):.3f}/{float(command_metrics.get('headroom_to_controller_cap_radps', 0.0)):.3f}/{float(command_metrics.get('headroom_to_hardware_cap_radps', 0.0)):.3f}` "
            f"yaw_ratio=`{realized_metrics.get('realized_yaw_change_per_commanded_angular_rad')}` "
            f"wrong_sign=`{int(realized_metrics.get('wrong_sign_realized_yaw_episode_count', 0))}` "
            f"offline_family=`{offline_turn_baseline.get('family_name', '')}:{offline_turn_baseline.get('profile_name', '')}` "
            f"offline_peak_ratio=`{comparison.get('live_to_offline_peak_request_ratio')}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit manual gather turn-realization contract gaps on frozen plus45 short_horizon_v2 evidence."
    )
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default=DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID)
    parser.add_argument("--campaign-summary-path", default=str(DEFAULT_TURN_REALIZATION_AUDIT_CAMPAIGN_SUMMARY))
    parser.add_argument("--run-index", type=int, default=DEFAULT_TURN_REALIZATION_AUDIT_RUN_INDEX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip() or oracle.current_utc_stamp()
    summary, fixture_payloads = build_turn_realization_audit_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=Path(args.campaign_summary_path).resolve(),
        run_index=int(args.run_index),
        scenario_id=str(args.scenario_id or DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID),
    )
    output_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_turn_realization_audit")
    fixtures_root = ensure_dir(output_root / "fixtures")
    summary_path = output_root / "turn_realization_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary, fixture_payloads), encoding="utf-8")
    for fixture_label, payload in fixture_payloads.items():
        write_json(fixtures_root / f"{fixture_label}.json", payload)
    print(f"GATHER_TURN_REALIZATION_AUDIT_SUMMARY={summary_path}")
    print(
        json.dumps(
            {
                "campaign_id": summary.get("campaign_id", ""),
                "dominant_gap": summary.get("dominant_gap", ""),
                "confidence": summary.get("confidence", ""),
                "dominant_gap_fixture_count": summary.get("dominant_gap_fixture_count", 0),
                "alignment_source": summary.get("alignment_source", ""),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if str(summary.get("dominant_gap", "")) != "mixed_turn_contract_limited" else 2


if __name__ == "__main__":
    raise SystemExit(main())
