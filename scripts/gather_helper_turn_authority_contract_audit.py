#!/usr/bin/env python3
"""Artifact-first helper turn-authority contract audit for manual gather pre-stage behavior."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import gather_escape_oracle as oracle
import gather_turn_realization_audit as turn_audit
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import write_json


DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_CAMPAIGN_SUMMARY = (
    turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_CAMPAIGN_SUMMARY
)
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_RUN_INDEX = (
    turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_RUN_INDEX
)
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SCENARIO_ID = (
    turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID
)
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES = 3
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_OFFLINE_DEMAND_RATIO = 0.85
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_BRIDGE_HEADROOM_RATIO = 0.85
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_MINIMUM_VIABLE_RATIO = 1.05
DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SAFE_FOLLOWUP_CAP_RADPS = 1.0
DEFAULT_HELPER_TURN_AUTHORITY_FOLLOW_ON_LANE = "short_horizon_authority_v1"
REPRESENTATIVE_FIXTURE_LABELS: tuple[str, ...] = (
    "first_post_yaw_gate",
    "early_stall",
    "mid_stall",
    "late_stall",
    "terminal_stall",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any, *, default: float | None = None) -> float | None:
    return turn_audit._number(value, default=default)


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return turn_audit._safe_ratio(numerator, denominator)


def compute_fixture_authority_contract(turn_fixture_payload: dict[str, Any]) -> dict[str, Any]:
    fixture_label = str(turn_fixture_payload.get("fixture_label", "") or "")
    fixture_index = int(turn_fixture_payload.get("fixture_index", 0) or 0)
    controller_debug = (
        turn_fixture_payload.get("controller_debug", {})
        if isinstance(turn_fixture_payload.get("controller_debug"), dict)
        else {}
    )
    controller_family = str(controller_debug.get("controller_family", "") or "")
    alignment = (
        turn_fixture_payload.get("alignment", {})
        if isinstance(turn_fixture_payload.get("alignment"), dict)
        else {}
    )
    turn_limit_surfaces = (
        turn_fixture_payload.get("turn_limit_surfaces", {})
        if isinstance(turn_fixture_payload.get("turn_limit_surfaces"), dict)
        else {}
    )
    command_metrics = (
        turn_fixture_payload.get("command_metrics", {})
        if isinstance(turn_fixture_payload.get("command_metrics"), dict)
        else {}
    )
    offline_turn_baseline = (
        turn_fixture_payload.get("offline_turn_baseline", {})
        if isinstance(turn_fixture_payload.get("offline_turn_baseline"), dict)
        else {}
    )
    classifier_flags = (
        turn_fixture_payload.get("classifier_flags", {})
        if isinstance(turn_fixture_payload.get("classifier_flags"), dict)
        else {}
    )

    current_family_surface = str(turn_limit_surfaces.get("active_helper_surface", "") or "")
    current_family_cap_radps = float(
        _number(turn_limit_surfaces.get("active_helper_abs_angular_cap_radps"), default=0.0) or 0.0
    )
    bridge_cap_radps = float(
        _number(turn_limit_surfaces.get("gather_motion_bridge_abs_angular_cap_radps"), default=0.0) or 0.0
    )
    controller_cap_radps = float(
        _number(turn_limit_surfaces.get("diff_drive_controller_abs_angular_cap_radps"), default=0.0) or 0.0
    )
    hardware_cap_radps = float(
        _number(turn_limit_surfaces.get("hardware_abs_angular_cap_radps"), default=0.0) or 0.0
    )
    live_peak_requested_angular_z_radps = float(
        _number(command_metrics.get("peak_requested_angular_z_radps"), default=0.0) or 0.0
    )
    live_commanded_angular_integral_rad = float(
        _number(command_metrics.get("commanded_angular_integral_rad"), default=0.0) or 0.0
    )
    percent_samples_pinned_at_current_family_cap = float(
        _number(command_metrics.get("percent_samples_pinned_at_helper_cap"), default=0.0) or 0.0
    )
    offline_peak_angular_z_radps = float(
        _number(offline_turn_baseline.get("peak_angular_z_radps"), default=0.0) or 0.0
    )
    offline_angular_integral_rad = float(
        _number(offline_turn_baseline.get("angular_integral_rad"), default=0.0) or 0.0
    )

    minimum_viable_cap_radps = max(
        live_peak_requested_angular_z_radps,
        offline_peak_angular_z_radps * DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_MINIMUM_VIABLE_RATIO,
    )
    max_safe_cap_radps = min(
        bridge_cap_radps * DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_BRIDGE_HEADROOM_RATIO,
        controller_cap_radps,
        hardware_cap_radps,
    )

    current_family_below_offline_demand = bool(
        offline_peak_angular_z_radps > 0.0
        and current_family_cap_radps
        <= (offline_peak_angular_z_radps * DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_OFFLINE_DEMAND_RATIO)
    )
    current_family_below_safe_envelope = bool(current_family_cap_radps < max_safe_cap_radps - 1.0e-9)
    strategy_authority_limited = bool(classifier_flags.get("strategy_authority_limited", False))
    sign_parity_limited = bool(classifier_flags.get("sign_parity_limited", False))
    plant_realization_limited = bool(classifier_flags.get("plant_realization_limited", False))

    authority_gap_confirmed = bool(
        strategy_authority_limited
        and current_family_below_offline_demand
        and current_family_below_safe_envelope
    )

    return {
        "generated_utc": _utc_now_iso(),
        "fixture_label": fixture_label,
        "fixture_index": fixture_index,
        "controller_family": controller_family,
        "alignment_quality": str(alignment.get("quality", "") or ""),
        "current_family_surface": current_family_surface,
        "current_family_cap_radps": round(current_family_cap_radps, 6),
        "live_peak_requested_angular_z_radps": round(live_peak_requested_angular_z_radps, 6),
        "live_commanded_angular_integral_rad": round(live_commanded_angular_integral_rad, 6),
        "percent_samples_pinned_at_current_family_cap": round(percent_samples_pinned_at_current_family_cap, 6),
        "downstream_caps": {
            "bridge_cap_radps": round(bridge_cap_radps, 6),
            "controller_cap_radps": round(controller_cap_radps, 6),
            "hardware_cap_radps": round(hardware_cap_radps, 6),
            "max_safe_cap_radps": round(max_safe_cap_radps, 6),
        },
        "offline_turn_demand": {
            "family_name": str(offline_turn_baseline.get("family_name", "") or ""),
            "profile_name": str(offline_turn_baseline.get("profile_name", "") or ""),
            "peak_angular_z_radps": round(offline_peak_angular_z_radps, 6),
            "angular_integral_rad": round(offline_angular_integral_rad, 6),
        },
        "minimum_viable_cap_radps": round(minimum_viable_cap_radps, 6),
        "max_safe_cap_radps": round(max_safe_cap_radps, 6),
        "comparison": {
            "current_family_cap_to_offline_peak_ratio": _round_or_none(
                _safe_ratio(current_family_cap_radps, offline_peak_angular_z_radps)
            ),
            "live_peak_request_to_offline_peak_ratio": _round_or_none(
                _safe_ratio(live_peak_requested_angular_z_radps, offline_peak_angular_z_radps)
            ),
            "live_integral_to_offline_integral_ratio": _round_or_none(
                _safe_ratio(live_commanded_angular_integral_rad, offline_angular_integral_rad)
            ),
            "minimum_viable_to_safe_cap_ratio": _round_or_none(
                _safe_ratio(minimum_viable_cap_radps, max_safe_cap_radps)
            ),
        },
        "confirmation_conditions": {
            "strategy_authority_limited_in_turn_audit": strategy_authority_limited,
            "current_family_below_offline_demand_by_15pct": current_family_below_offline_demand,
            "current_family_below_safe_envelope": current_family_below_safe_envelope,
        },
        "turn_realization_flags": {
            "strategy_authority_limited": strategy_authority_limited,
            "sign_parity_limited": sign_parity_limited,
            "plant_realization_limited": plant_realization_limited,
        },
        "authority_gap_confirmed": authority_gap_confirmed,
    }


def decide_next_action(
    fixture_payloads: list[dict[str, Any]],
    *,
    turn_root_cause_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    turn_root_cause_gate = turn_root_cause_gate or {}
    confirmed_payloads = [payload for payload in fixture_payloads if bool(payload.get("authority_gap_confirmed", False))]
    confirmed_fixture_count = len(confirmed_payloads)
    sign_parity_fixture_count = int(turn_root_cause_gate.get("sign_parity_fixture_count", 0) or 0)
    plant_realization_fixture_count = int(turn_root_cause_gate.get("plant_realization_fixture_count", 0) or 0)
    max_confirmed_minimum_viable_cap_radps = max(
        (
            float(_number(payload.get("minimum_viable_cap_radps"), default=0.0) or 0.0)
            for payload in confirmed_payloads
        ),
        default=0.0,
    )
    safe_followup_overrides = [
        payload
        for payload in confirmed_payloads
        if float(_number(payload.get("minimum_viable_cap_radps"), default=0.0) or 0.0)
        > float(_number(payload.get("max_safe_cap_radps"), default=0.0) or 0.0)
    ]
    dominant_gap = str(turn_root_cause_gate.get("dominant_gap", "") or "")
    sign_parity_supersedes = bool(
        sign_parity_fixture_count >= DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES
        and sign_parity_fixture_count >= confirmed_fixture_count
        and sign_parity_fixture_count >= plant_realization_fixture_count
    )
    plant_realization_supersedes = bool(
        plant_realization_fixture_count >= DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES
        and plant_realization_fixture_count >= confirmed_fixture_count
        and plant_realization_fixture_count > sign_parity_fixture_count
    )

    if dominant_gap == "sign_parity_limited" or sign_parity_supersedes:
        return {
            "decision": "stop_and_branch",
            "blocking_reason": "sign_parity",
            "blocking_detail": (
                "turn_realization_audit_dominant_gap"
                if dominant_gap == "sign_parity_limited"
                else "sign_parity_fixture_count_supersedes_authority_gap"
            ),
            "rationale": (
                "The turn-realization audit says sign parity is the dominant blocker, so a helper authority patch is not the next safe move."
                if dominant_gap == "sign_parity_limited"
                else "The sign-parity flags cover at least as many representative fixtures as the confirmed authority gap, so the next slice should branch to sign-parity diagnosis first."
            ),
            "follow_on_lane_name": "",
            "confirmed_fixture_count": confirmed_fixture_count,
            "required_confirmed_fixture_count": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES,
            "max_confirmed_minimum_viable_cap_radps": round(max_confirmed_minimum_viable_cap_radps, 6),
            "sign_parity_fixture_count": sign_parity_fixture_count,
            "plant_realization_fixture_count": plant_realization_fixture_count,
        }
    if dominant_gap == "plant_realization_limited" or plant_realization_supersedes:
        return {
            "decision": "stop_and_branch",
            "blocking_reason": "plant_realization",
            "blocking_detail": (
                "turn_realization_audit_dominant_gap"
                if dominant_gap == "plant_realization_limited"
                else "plant_realization_fixture_count_supersedes_authority_gap"
            ),
            "rationale": (
                "The turn-realization audit says plant realization is the dominant blocker, so increasing helper authority would not address the leading failure mode."
                if dominant_gap == "plant_realization_limited"
                else "Plant-realization flags cover at least as many representative fixtures as the confirmed authority gap, so the next slice should branch to plant realization before widening helper authority."
            ),
            "follow_on_lane_name": "",
            "confirmed_fixture_count": confirmed_fixture_count,
            "required_confirmed_fixture_count": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES,
            "max_confirmed_minimum_viable_cap_radps": round(max_confirmed_minimum_viable_cap_radps, 6),
            "sign_parity_fixture_count": sign_parity_fixture_count,
            "plant_realization_fixture_count": plant_realization_fixture_count,
        }

    if (
        confirmed_fixture_count >= DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES
        and max_confirmed_minimum_viable_cap_radps
        <= DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SAFE_FOLLOWUP_CAP_RADPS
        and not safe_followup_overrides
    ):
        return {
            "decision": "new_helper_authority_lane",
            "blocking_reason": "",
            "blocking_detail": "",
            "rationale": "The confirmed authority gap covers at least three representative fixtures and fits inside the first safe follow-up authority ceiling.",
            "follow_on_lane_name": DEFAULT_HELPER_TURN_AUTHORITY_FOLLOW_ON_LANE,
            "confirmed_fixture_count": confirmed_fixture_count,
            "required_confirmed_fixture_count": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES,
            "max_confirmed_minimum_viable_cap_radps": round(max_confirmed_minimum_viable_cap_radps, 6),
            "sign_parity_fixture_count": sign_parity_fixture_count,
            "plant_realization_fixture_count": plant_realization_fixture_count,
        }

    blocking_detail = "confirmed_fixture_count_below_threshold"
    rationale = (
        "The authority gap does not yet cover enough representative fixtures to open a behavior-changing helper-authority lane."
    )
    if max_confirmed_minimum_viable_cap_radps > DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SAFE_FOLLOWUP_CAP_RADPS:
        blocking_detail = "minimum_viable_cap_exceeds_followup_ceiling"
        rationale = (
            "The confirmed authority gap would require a helper cap above the first safe follow-up ceiling of 1.0 rad/s."
        )
    elif safe_followup_overrides:
        blocking_detail = "minimum_viable_cap_exceeds_safe_envelope"
        rationale = (
            "At least one confirmed fixture would need more turn authority than the current downstream safe envelope allows."
        )
    return {
        "decision": "stop_and_branch",
        "blocking_reason": "cap_exceeds_safe_followup",
        "blocking_detail": blocking_detail,
        "rationale": rationale,
        "follow_on_lane_name": "",
        "confirmed_fixture_count": confirmed_fixture_count,
        "required_confirmed_fixture_count": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES,
        "max_confirmed_minimum_viable_cap_radps": round(max_confirmed_minimum_viable_cap_radps, 6),
        "sign_parity_fixture_count": sign_parity_fixture_count,
        "plant_realization_fixture_count": plant_realization_fixture_count,
    }


def _ordered_fixture_payloads(fixture_payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fixture_label in REPRESENTATIVE_FIXTURE_LABELS:
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


def _follow_on_patch_definition() -> dict[str, Any]:
    return {
        "lane_name": DEFAULT_HELPER_TURN_AUTHORITY_FOLLOW_ON_LANE,
        "activation_scope": "manual_pre_stage_only",
        "preserve_existing_lanes": [
            "baseline",
            "short_horizon_v1",
            "short_horizon_v2",
        ],
        "requested_angular_cap_radps": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SAFE_FOLLOWUP_CAP_RADPS,
        "candidate_palette_radps": [-1.0, -0.7, -0.35, 0.35, 0.7, 1.0],
        "preserve_structure": "reuse existing gather manager, activation gates, and late baseline handoff",
        "do_not_change": [
            "stage logic",
            "capture-entry logic",
            "bridge cap above 1.2 rad/s",
            "controller configuration",
            "hardware configuration",
            "baseline lane outputs",
            "short_horizon_v1 outputs",
            "short_horizon_v2 outputs",
        ],
    }


def build_helper_turn_authority_contract_audit_bundle(
    *,
    campaign_id: str,
    campaign_summary_path: Path = DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_CAMPAIGN_SUMMARY,
    run_index: int = DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_RUN_INDEX,
    scenario_id: str = DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SCENARIO_ID,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    turn_summary, turn_fixture_payloads = turn_audit.build_turn_realization_audit_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=campaign_summary_path,
        run_index=run_index,
        scenario_id=scenario_id,
    )

    fixture_payloads = {
        fixture_label: compute_fixture_authority_contract(turn_fixture_payload)
        for fixture_label, turn_fixture_payload in turn_fixture_payloads.items()
    }
    ordered_fixture_payloads = _ordered_fixture_payloads(fixture_payloads)
    next_action = decide_next_action(
        ordered_fixture_payloads,
        turn_root_cause_gate=(
            turn_summary.get("root_cause_gate", {})
            if isinstance(turn_summary.get("root_cause_gate"), dict)
            else {}
        ),
    )
    confirmed_fixture_labels = [
        str(payload.get("fixture_label", "") or "")
        for payload in ordered_fixture_payloads
        if bool(payload.get("authority_gap_confirmed", False))
    ]
    max_safe_cap_radps = max(
        (float(_number(payload.get("max_safe_cap_radps"), default=0.0) or 0.0) for payload in ordered_fixture_payloads),
        default=0.0,
    )
    max_minimum_viable_cap_radps = max(
        (
            float(_number(payload.get("minimum_viable_cap_radps"), default=0.0) or 0.0)
            for payload in ordered_fixture_payloads
        ),
        default=0.0,
    )

    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "gather_helper_turn_authority_contract_audit",
        "campaign_id": campaign_id,
        "scenario_id": scenario_id,
        "source_campaign_summary_path": str(Path(campaign_summary_path).resolve()),
        "source_campaign_id": str(turn_summary.get("source_campaign_id", "") or ""),
        "source_run_index": int(turn_summary.get("source_run_index", 0) or 0),
        "source_session_id": str(turn_summary.get("source_session_id", "") or ""),
        "source_mission_root": str(turn_summary.get("source_mission_root", "") or ""),
        "source_state_history_path": str(turn_summary.get("source_state_history_path", "") or ""),
        "source_truth_timeline_path": str(turn_summary.get("source_truth_timeline_path", "") or ""),
        "source_timeline_path": str(turn_summary.get("source_timeline_path", "") or ""),
        "source_timeline_events_path": str(turn_summary.get("source_timeline_events_path", "") or ""),
        "representative_fixture_count": len(ordered_fixture_payloads),
        "alignment_source": str(turn_summary.get("alignment_source", "") or ""),
        "alignment_source_counts": turn_summary.get("alignment_source_counts", {}),
        "timeline_alignment_anchor": turn_summary.get("timeline_alignment_anchor", {}),
        "turn_limit_surfaces": turn_summary.get("turn_limit_surfaces", {}),
        "turn_realization_root_cause_gate": turn_summary.get("root_cause_gate", {}),
        "authority_gap_fixture_count": len(confirmed_fixture_labels),
        "confirmed_fixture_labels": confirmed_fixture_labels,
        "max_minimum_viable_cap_radps": round(max_minimum_viable_cap_radps, 6),
        "max_safe_cap_radps": round(max_safe_cap_radps, 6),
        "authority_gap_gate": {
            "required_confirmed_fixture_count": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_REQUIRED_FIXTURES,
            "safe_followup_cap_ceiling_radps": DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SAFE_FOLLOWUP_CAP_RADPS,
            "follow_on_lane_name": DEFAULT_HELPER_TURN_AUTHORITY_FOLLOW_ON_LANE,
        },
        "next_action": next_action,
        "follow_on_patch_definition": _follow_on_patch_definition(),
        "run_context": turn_summary.get("run_context", {}),
        "fixtures": [
            {
                "fixture_label": payload.get("fixture_label", ""),
                "controller_family": payload.get("controller_family", ""),
                "authority_gap_confirmed": payload.get("authority_gap_confirmed", False),
                "current_family_cap_radps": payload.get("current_family_cap_radps"),
                "live_peak_requested_angular_z_radps": payload.get("live_peak_requested_angular_z_radps"),
                "live_commanded_angular_integral_rad": payload.get("live_commanded_angular_integral_rad"),
                "percent_samples_pinned_at_current_family_cap": payload.get(
                    "percent_samples_pinned_at_current_family_cap"
                ),
                "offline_peak_angular_z_radps": (
                    (payload.get("offline_turn_demand", {}) or {}).get("peak_angular_z_radps")
                ),
                "offline_angular_integral_rad": (
                    (payload.get("offline_turn_demand", {}) or {}).get("angular_integral_rad")
                ),
                "minimum_viable_cap_radps": payload.get("minimum_viable_cap_radps"),
                "max_safe_cap_radps": payload.get("max_safe_cap_radps"),
                "sign_parity_limited": (
                    (payload.get("turn_realization_flags", {}) or {}).get("sign_parity_limited")
                ),
                "plant_realization_limited": (
                    (payload.get("turn_realization_flags", {}) or {}).get("plant_realization_limited")
                ),
            }
            for payload in ordered_fixture_payloads
        ],
    }
    return summary, fixture_payloads


def build_scorecard_markdown(summary: dict[str, Any], fixture_payloads: dict[str, dict[str, Any]]) -> str:
    turn_limit_surfaces = (
        summary.get("turn_limit_surfaces", {})
        if isinstance(summary.get("turn_limit_surfaces"), dict)
        else {}
    )
    next_action = summary.get("next_action", {}) if isinstance(summary.get("next_action"), dict) else {}
    lines = [
        "# Gather Helper Turn Authority Contract Audit Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Source campaign: `{summary.get('source_campaign_id', '')}`",
        f"- Source run index: `{summary.get('source_run_index', 0)}`",
        f"- Representative fixtures: `{summary.get('representative_fixture_count', 0)}`",
        f"- Turn-audit dominant gap: `{((summary.get('turn_realization_root_cause_gate', {}) or {}).get('dominant_gap', ''))}`",
        f"- Authority-gap coverage: `{summary.get('authority_gap_fixture_count', 0)}/{summary.get('representative_fixture_count', 0)}`",
        f"- Next action: `{next_action.get('decision', '')}`",
        f"- Blocking reason: `{next_action.get('blocking_reason', '')}`",
        f"- Proposed follow-on lane: `{next_action.get('follow_on_lane_name', '')}`",
        "",
        "## Shared Turn Surfaces",
        "",
        f"- Gather mission helper cap: `{float(turn_limit_surfaces.get('gather_mission_helper_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Short-horizon helper cap: `{float(turn_limit_surfaces.get('short_horizon_helper_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Bridge cap: `{float(turn_limit_surfaces.get('gather_motion_bridge_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Controller cap: `{float(turn_limit_surfaces.get('diff_drive_controller_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        f"- Hardware cap: `{float(turn_limit_surfaces.get('hardware_abs_angular_cap_radps', 0.0)):.3f} rad/s`",
        "",
        "## Fixtures",
        "",
    ]
    for payload in _ordered_fixture_payloads(fixture_payloads):
        downstream_caps = payload.get("downstream_caps", {}) if isinstance(payload.get("downstream_caps"), dict) else {}
        offline_turn_demand = (
            payload.get("offline_turn_demand", {})
            if isinstance(payload.get("offline_turn_demand"), dict)
            else {}
        )
        flags = (
            payload.get("turn_realization_flags", {})
            if isinstance(payload.get("turn_realization_flags"), dict)
            else {}
        )
        lines.append(
            f"- `{payload.get('fixture_label', '')}` confirmed=`{payload.get('authority_gap_confirmed', False)}` "
            f"family=`{payload.get('controller_family', '')}` "
            f"cap=`{float(payload.get('current_family_cap_radps', 0.0)):.3f}` "
            f"live_peak=`{float(payload.get('live_peak_requested_angular_z_radps', 0.0)):.3f}` "
            f"live_integral=`{float(payload.get('live_commanded_angular_integral_rad', 0.0)):.3f}` "
            f"pinned=`{float(payload.get('percent_samples_pinned_at_current_family_cap', 0.0)):.1f}%` "
            f"downstream=`{float(downstream_caps.get('bridge_cap_radps', 0.0)):.3f}/{float(downstream_caps.get('controller_cap_radps', 0.0)):.3f}/{float(downstream_caps.get('hardware_cap_radps', 0.0)):.3f}` "
            f"safe=`{float(payload.get('max_safe_cap_radps', 0.0)):.3f}` "
            f"offline=`{float(offline_turn_demand.get('peak_angular_z_radps', 0.0)):.3f}/{float(offline_turn_demand.get('angular_integral_rad', 0.0)):.3f}` "
            f"minimum_viable=`{float(payload.get('minimum_viable_cap_radps', 0.0)):.3f}` "
            f"flags=`strategy:{bool(flags.get('strategy_authority_limited', False))},sign:{bool(flags.get('sign_parity_limited', False))},plant:{bool(flags.get('plant_realization_limited', False))}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_helper_turn_authority_contract_audit_bundle(
    *,
    campaign_id: str,
    summary: dict[str, Any],
    fixture_payloads: dict[str, dict[str, Any]],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Path]:
    output_root = ensure_dir(Path(repo_root) / "artifacts" / "session" / campaign_id / "gather_helper_turn_authority_contract_audit")
    fixtures_root = ensure_dir(output_root / "fixtures")
    summary_path = output_root / "helper_turn_authority_contract_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary, fixture_payloads), encoding="utf-8")
    for fixture_label, payload in fixture_payloads.items():
        write_json(fixtures_root / f"{fixture_label}.json", payload)
    return {
        "output_root": output_root,
        "fixtures_root": fixtures_root,
        "summary_path": summary_path,
        "scorecard_path": scorecard_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit whether the frozen live helper family under-requests turn authority relative to the best offline maneuver."
    )
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default=DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SCENARIO_ID)
    parser.add_argument(
        "--campaign-summary-path",
        default=str(DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_CAMPAIGN_SUMMARY),
    )
    parser.add_argument("--run-index", type=int, default=DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_RUN_INDEX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip() or oracle.current_utc_stamp()
    summary, fixture_payloads = build_helper_turn_authority_contract_audit_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=Path(args.campaign_summary_path).resolve(),
        run_index=int(args.run_index),
        scenario_id=str(args.scenario_id or DEFAULT_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SCENARIO_ID),
    )
    output_paths = write_helper_turn_authority_contract_audit_bundle(
        campaign_id=campaign_id,
        summary=summary,
        fixture_payloads=fixture_payloads,
    )
    print(f"GATHER_HELPER_TURN_AUTHORITY_CONTRACT_AUDIT_SUMMARY={output_paths['summary_path']}")
    print(
        json.dumps(
            {
                "campaign_id": summary.get("campaign_id", ""),
                "decision": ((summary.get("next_action", {}) or {}).get("decision", "")),
                "blocking_reason": ((summary.get("next_action", {}) or {}).get("blocking_reason", "")),
                "follow_on_lane_name": ((summary.get("next_action", {}) or {}).get("follow_on_lane_name", "")),
                "authority_gap_fixture_count": summary.get("authority_gap_fixture_count", 0),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
