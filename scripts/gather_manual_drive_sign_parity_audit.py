#!/usr/bin/env python3
"""Artifact-first manual-drive sign-parity audit for gather pre-stage behavior."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import yaml

import gather_escape_divergence_audit as divergence
import gather_escape_oracle as oracle
import gather_turn_realization_audit as turn_audit
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import write_json


DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_CAMPAIGN_SUMMARY = (
    turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_CAMPAIGN_SUMMARY
)
DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_RUN_INDEX = (
    turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_RUN_INDEX
)
DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SCENARIO_ID = (
    turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_SCENARIO_ID
)
DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_REQUIRED_FIXTURES = 3
DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_NET_SIGN_MIN_RAD = 0.05
DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_WRONG_SIGN_DELTA_MIN_STEPS = 2
REPRESENTATIVE_FIXTURE_LABELS: tuple[str, ...] = (
    "first_post_yaw_gate",
    "early_stall",
    "mid_stall",
    "late_stall",
    "terminal_stall",
)

GATHER_MOTION_BRIDGE_PATH = REPO_ROOT / "scripts" / "gather_motion_bridge.py"
VISUAL_DEMO_OBSERVER_PATH = REPO_ROOT / "scripts" / "visual_demo_observer.py"
DASHBOARD_SERVICE_PATH = REPO_ROOT / "scripts" / "dashboard_service.py"
GATHER_MISSION_RUNNER_PATH = REPO_ROOT / "scripts" / "gather_mission_runner.py"
JETBOT_DIFF_DRIVE_CONFIG_PATH = REPO_ROOT / "ros2_config" / "config" / "jetbot_diff_drive_v1.0.0.yaml"
JETBOT_CONTROLLERS_PATH = REPO_ROOT / "ros2_config" / "config" / "jetbot_controllers.yaml"


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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping in YAML file: {path}")
    return payload


def _controller_ros_params(path: Path) -> dict[str, Any]:
    payload = _read_yaml(path)
    for key, value in payload.items():
        if not str(key).endswith("jetbot_base_controller"):
            continue
        if isinstance(value, dict):
            ros_params = value.get("ros__parameters", {})
            if isinstance(ros_params, dict):
                return ros_params
    raise ValueError(f"Unable to resolve jetbot_base_controller ros__parameters from {path}")


def _controller_sign_surface(path: Path) -> dict[str, Any]:
    ros_params = _controller_ros_params(path)
    left_multiplier = float(_number(ros_params.get("left_wheel_radius_multiplier"), default=1.0) or 1.0)
    right_multiplier = float(_number(ros_params.get("right_wheel_radius_multiplier"), default=1.0) or 1.0)
    wheel_separation = _number(ros_params.get("wheel_separation"), default=None)
    return {
        "path": str(path),
        "left_wheel_radius_multiplier": round(left_multiplier, 6),
        "right_wheel_radius_multiplier": round(right_multiplier, 6),
        "wheel_radius_multiplier_symmetric": abs(left_multiplier - right_multiplier) <= 1.0e-9,
        "negative_radius_multipliers": left_multiplier < 0.0 and right_multiplier < 0.0,
        "wheel_separation_m": _round_or_none(wheel_separation),
    }


def _bridge_sign_preserved(path: Path) -> bool:
    text = _read_text(path)
    return bool(
        re.search(
            r"twist\.angular\.z\s*=\s*clamp\(float\(angular_z\),\s*-self\.max_angular_z,\s*self\.max_angular_z\)",
            text,
        )
    )


def _visual_observer_pose_from_odom(path: Path) -> bool:
    text = _read_text(path)
    return bool(
        "self.latest_odom = msg" in text
        and "def _pose_from_odom" in text
        and "pose = self.latest_odom.pose.pose" in text
        and '"latest_robot_pose"' in text
    )


def _dashboard_truth_fallback_present(path: Path) -> bool:
    text = _read_text(path)
    return bool(
        "latest_robot_pose = _truth_robot_pose(" in text
        or "_truth_robot_pose(" in text
        and "truth_state.get(\"robot_truth_pose\")" in text
    )


def _state_history_logs_belief_pose(path: Path) -> bool:
    text = _read_text(path)
    return bool('"robot_pose": robot_pose' in text and 'belief.get("latest_robot_pose")' in text)


def load_sign_parity_surfaces() -> dict[str, Any]:
    diff_drive_v100 = _controller_sign_surface(JETBOT_DIFF_DRIVE_CONFIG_PATH)
    controllers = _controller_sign_surface(JETBOT_CONTROLLERS_PATH)
    bridge_sign_preserved = _bridge_sign_preserved(GATHER_MOTION_BRIDGE_PATH)
    controller_configs_match = bool(
        abs(
            float(diff_drive_v100["left_wheel_radius_multiplier"])
            - float(controllers["left_wheel_radius_multiplier"])
        )
        <= 1.0e-9
        and abs(
            float(diff_drive_v100["right_wheel_radius_multiplier"])
            - float(controllers["right_wheel_radius_multiplier"])
        )
        <= 1.0e-9
    )
    controller_negative_symmetric = bool(
        diff_drive_v100["wheel_radius_multiplier_symmetric"]
        and controllers["wheel_radius_multiplier_symmetric"]
        and diff_drive_v100["negative_radius_multipliers"]
        and controllers["negative_radius_multipliers"]
    )
    static_config_parity_expected = bool(
        bridge_sign_preserved and controller_negative_symmetric and controller_configs_match
    )
    return {
        "bridge_sign_preserved": bridge_sign_preserved,
        "controller_configs_match": controller_configs_match,
        "controller_negative_symmetric_radius_multipliers": controller_negative_symmetric,
        "static_config_parity_expected": static_config_parity_expected,
        "state_history_robot_pose_from_belief_pose": _state_history_logs_belief_pose(GATHER_MISSION_RUNNER_PATH),
        "visual_latest_robot_pose_from_odom": _visual_observer_pose_from_odom(VISUAL_DEMO_OBSERVER_PATH),
        "dashboard_truth_fallback_present": _dashboard_truth_fallback_present(DASHBOARD_SERVICE_PATH),
        "controller_sign_surfaces": {
            "jetbot_diff_drive_v1_0_0": diff_drive_v100,
            "jetbot_controllers": controllers,
        },
        "sources": {
            "gather_motion_bridge": str(GATHER_MOTION_BRIDGE_PATH),
            "visual_demo_observer": str(VISUAL_DEMO_OBSERVER_PATH),
            "dashboard_service": str(DASHBOARD_SERVICE_PATH),
            "gather_mission_runner": str(GATHER_MISSION_RUNNER_PATH),
            "jetbot_diff_drive_v1_0_0": str(JETBOT_DIFF_DRIVE_CONFIG_PATH),
            "jetbot_controllers": str(JETBOT_CONTROLLERS_PATH),
        },
    }


def _net_sign(value: float, *, min_abs_rad: float = DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_NET_SIGN_MIN_RAD) -> int:
    if abs(float(value)) < float(min_abs_rad):
        return 0
    return 1 if float(value) > 0.0 else -1


def _yaw_metrics_from_robot_pose_rows(
    rows: list[dict[str, Any]],
    *,
    target_turn_sign: int,
) -> dict[str, Any]:
    step_deltas: list[float] = []
    step_signs: list[int] = []
    net_yaw_change_rad = 0.0
    abs_yaw_change_rad = 0.0
    for previous, current in zip(rows, rows[1:]):
        previous_robot_pose = previous.get("robot_pose")
        current_robot_pose = current.get("robot_pose")
        previous_xyyaw = divergence.world_pose_xyyaw(previous_robot_pose) if isinstance(previous_robot_pose, dict) else None
        current_xyyaw = divergence.world_pose_xyyaw(current_robot_pose) if isinstance(current_robot_pose, dict) else None
        if previous_xyyaw is None or current_xyyaw is None:
            continue
        yaw_delta = divergence.normalize_angle(float(current_xyyaw[2]) - float(previous_xyyaw[2]))
        step_deltas.append(round(yaw_delta, 6))
        step_sign = turn_audit._sign(
            yaw_delta,
            eps=turn_audit.DEFAULT_TURN_REALIZATION_AUDIT_REALIZED_STEP_MIN_RAD,
        )
        step_signs.append(step_sign)
        net_yaw_change_rad += float(yaw_delta)
        abs_yaw_change_rad += abs(float(yaw_delta))
    wrong_sign_episode_count = turn_audit._episode_count(step_signs, opposite_of=target_turn_sign)
    wrong_sign_step_count = sum(
        1 for sign in step_signs if target_turn_sign != 0 and sign != 0 and sign == -target_turn_sign
    )
    return {
        "nonzero_step_count": int(sum(1 for sign in step_signs if sign != 0)),
        "step_count": int(len(step_signs)),
        "step_signs": step_signs,
        "step_deltas_rad": step_deltas,
        "net_yaw_change_rad": round(net_yaw_change_rad, 6),
        "absolute_yaw_change_rad": round(abs_yaw_change_rad, 6),
        "dominant_yaw_sign": int(_net_sign(net_yaw_change_rad)),
        "wrong_sign_episode_count": int(wrong_sign_episode_count),
        "wrong_sign_step_count": int(wrong_sign_step_count),
    }


def _match_state(command_sign: int, realized_sign: int) -> bool | None:
    if command_sign == 0 or realized_sign == 0:
        return None
    return bool(command_sign == realized_sign)


def classify_fixture_sign_parity(
    *,
    fixture_label: str,
    fixture_index: int,
    controller_family: str,
    alignment_quality: str,
    target_turn_sign: int,
    command_sign: int,
    odom_metrics: dict[str, Any],
    world_metrics: dict[str, Any],
    turn_flags: dict[str, Any],
    sign_parity_surfaces: dict[str, Any],
) -> dict[str, Any]:
    static_config_parity_expected = bool(sign_parity_surfaces.get("static_config_parity_expected", False))
    odom_dominant_sign = int(odom_metrics.get("dominant_yaw_sign", 0) or 0)
    world_dominant_sign = int(world_metrics.get("dominant_yaw_sign", 0) or 0)
    command_to_odom_sign_match = _match_state(command_sign, odom_dominant_sign)
    command_to_world_sign_match = _match_state(command_sign, world_dominant_sign)
    odom_to_world_sign_match = None
    if odom_dominant_sign != 0 and world_dominant_sign != 0:
        odom_to_world_sign_match = bool(odom_dominant_sign == world_dominant_sign)

    sign_parity_fixture_from_turn_audit = bool(turn_flags.get("sign_parity_limited", False))
    static_sign_surface_mismatch = not static_config_parity_expected
    odom_world_sign_divergent = bool(
        sign_parity_fixture_from_turn_audit
        and (
            odom_to_world_sign_match is False
            or abs(
                int(world_metrics.get("wrong_sign_step_count", 0) or 0)
                - int(odom_metrics.get("wrong_sign_step_count", 0) or 0)
            )
            >= DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_WRONG_SIGN_DELTA_MIN_STEPS
        )
    )
    command_odom_sign_divergent = bool(
        sign_parity_fixture_from_turn_audit
        and command_to_odom_sign_match is False
        and not odom_world_sign_divergent
    )

    fixture_diagnosis = "mixed_sign_chain_unresolved"
    if static_sign_surface_mismatch:
        fixture_diagnosis = "static_sign_surface_mismatch"
    elif odom_world_sign_divergent:
        fixture_diagnosis = "odom_world_sign_divergent"
    elif command_odom_sign_divergent:
        fixture_diagnosis = "command_to_odom_sign_divergent"

    return {
        "generated_utc": _utc_now_iso(),
        "fixture_label": fixture_label,
        "fixture_index": fixture_index,
        "controller_family": controller_family,
        "alignment_quality": alignment_quality,
        "target_turn_sign": int(target_turn_sign),
        "command_sign": int(command_sign),
        "odom_metrics": odom_metrics,
        "world_metrics": world_metrics,
        "sign_matches": {
            "command_to_odom_sign_match": command_to_odom_sign_match,
            "command_to_world_sign_match": command_to_world_sign_match,
            "odom_to_world_sign_match": odom_to_world_sign_match,
        },
        "sign_surface_snapshot": {
            "bridge_sign_preserved": bool(sign_parity_surfaces.get("bridge_sign_preserved", False)),
            "controller_configs_match": bool(sign_parity_surfaces.get("controller_configs_match", False)),
            "controller_negative_symmetric_radius_multipliers": bool(
                sign_parity_surfaces.get("controller_negative_symmetric_radius_multipliers", False)
            ),
            "static_config_parity_expected": static_config_parity_expected,
            "state_history_robot_pose_from_belief_pose": bool(
                sign_parity_surfaces.get("state_history_robot_pose_from_belief_pose", False)
            ),
            "visual_latest_robot_pose_from_odom": bool(
                sign_parity_surfaces.get("visual_latest_robot_pose_from_odom", False)
            ),
            "dashboard_truth_fallback_present": bool(
                sign_parity_surfaces.get("dashboard_truth_fallback_present", False)
            ),
        },
        "classifier_flags": {
            "sign_parity_fixture_from_turn_audit": sign_parity_fixture_from_turn_audit,
            "static_sign_surface_mismatch": static_sign_surface_mismatch,
            "odom_world_sign_divergent": odom_world_sign_divergent,
            "command_odom_sign_divergent": command_odom_sign_divergent,
        },
        "fixture_diagnosis": fixture_diagnosis,
    }


def compute_fixture_sign_parity_contract(
    turn_fixture_payload: dict[str, Any],
    *,
    state_rows: list[dict[str, Any]],
    truth_samples: list[dict[str, Any]],
    timeline_anchor: dict[str, Any] | None,
    sign_parity_surfaces: dict[str, Any],
    scenario_id: str = DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SCENARIO_ID,
) -> dict[str, Any]:
    fixture = {
        "fixture_label": turn_fixture_payload.get("fixture_label", ""),
        "fixture_index": turn_fixture_payload.get("fixture_index", 0),
        "generated_utc": turn_fixture_payload.get("fixture_generated_utc", ""),
        "robot_pose": turn_fixture_payload.get("robot_pose", {}),
        "ball_pose": turn_fixture_payload.get("ball_pose", {}),
        "robot_pose_local": turn_fixture_payload.get("robot_pose_local", {}),
        "selected_command": turn_fixture_payload.get("selected_command", {}),
    }
    alignment, enriched_truth, state_window = turn_audit._state_window_for_fixture(
        fixture,
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
        scenario_id=scenario_id,
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
    turn_flags = (
        turn_fixture_payload.get("classifier_flags", {})
        if isinstance(turn_fixture_payload.get("classifier_flags"), dict)
        else {}
    )
    controller_debug = (
        turn_fixture_payload.get("controller_debug", {})
        if isinstance(turn_fixture_payload.get("controller_debug"), dict)
        else {}
    )
    command_sign = int(command_metrics.get("dominant_command_sign", 0) or 0)
    target_turn_sign = command_sign or int(offline_turn_baseline.get("expected_turn_sign", 0) or 0)
    odom_metrics = _yaw_metrics_from_robot_pose_rows(state_window, target_turn_sign=target_turn_sign)
    world_metrics = _yaw_metrics_from_robot_pose_rows(enriched_truth, target_turn_sign=target_turn_sign)
    payload = classify_fixture_sign_parity(
        fixture_label=str(turn_fixture_payload.get("fixture_label", "") or ""),
        fixture_index=int(turn_fixture_payload.get("fixture_index", 0) or 0),
        controller_family=str(controller_debug.get("controller_family", "") or ""),
        alignment_quality=str(alignment.get("quality", "") or ""),
        target_turn_sign=int(target_turn_sign),
        command_sign=int(command_sign),
        odom_metrics=odom_metrics,
        world_metrics=world_metrics,
        turn_flags=turn_flags,
        sign_parity_surfaces=sign_parity_surfaces,
    )
    payload["alignment"] = alignment
    payload["turn_fixture_gap"] = str(turn_fixture_payload.get("fixture_gap", "") or "")
    return payload


def decide_sign_parity_root_cause(
    fixture_payloads: list[dict[str, Any]],
    *,
    sign_parity_surfaces: dict[str, Any],
) -> dict[str, Any]:
    static_mismatch_count = 0
    odom_world_divergent_count = 0
    command_odom_divergent_count = 0
    turn_sign_parity_fixture_count = 0
    for payload in fixture_payloads:
        flags = payload.get("classifier_flags", {}) if isinstance(payload.get("classifier_flags"), dict) else {}
        if bool(flags.get("sign_parity_fixture_from_turn_audit", False)):
            turn_sign_parity_fixture_count += 1
        if bool(flags.get("static_sign_surface_mismatch", False)):
            static_mismatch_count += 1
        if bool(flags.get("odom_world_sign_divergent", False)):
            odom_world_divergent_count += 1
        if bool(flags.get("command_odom_sign_divergent", False)):
            command_odom_divergent_count += 1

    if not bool(sign_parity_surfaces.get("static_config_parity_expected", False)):
        dominant_diagnosis = "static_sign_surface_mismatch"
        coverage_count = len(fixture_payloads)
    elif odom_world_divergent_count >= DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_REQUIRED_FIXTURES:
        dominant_diagnosis = "odom_world_sign_divergent"
        coverage_count = odom_world_divergent_count
    elif command_odom_divergent_count >= DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_REQUIRED_FIXTURES:
        dominant_diagnosis = "command_to_odom_sign_divergent"
        coverage_count = command_odom_divergent_count
    else:
        dominant_diagnosis = "mixed_sign_chain_unresolved"
        coverage_count = max(static_mismatch_count, odom_world_divergent_count, command_odom_divergent_count)

    confidence = (
        "high"
        if coverage_count >= 4
        else "medium"
        if coverage_count >= DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_REQUIRED_FIXTURES
        else "low"
    )
    return {
        "dominant_diagnosis": dominant_diagnosis,
        "confidence": confidence,
        "dominant_coverage_count": int(coverage_count),
        "turn_sign_parity_fixture_count": int(turn_sign_parity_fixture_count),
        "static_sign_surface_mismatch_fixture_count": int(static_mismatch_count),
        "odom_world_sign_divergent_fixture_count": int(odom_world_divergent_count),
        "command_odom_sign_divergent_fixture_count": int(command_odom_divergent_count),
    }


def _next_action_recommendation(dominant_diagnosis: str) -> dict[str, Any]:
    if dominant_diagnosis == "static_sign_surface_mismatch":
        return {
            "decision": "fix_static_sign_surface",
            "live_probe_required": False,
            "rationale": "The current repo sign surfaces do not already preserve parity, so fix the static bridge/controller surface before trusting another runtime probe.",
        }
    if dominant_diagnosis == "odom_world_sign_divergent":
        return {
            "decision": "probe_odom_world_sign_chain",
            "live_probe_required": True,
            "rationale": "The static repo surfaces say sign should be preserved, but the frozen artifacts still diverge between the odom-facing belief pose and truth/world yaw; a focused runtime sign-chain probe is the next safe slice.",
        }
    if dominant_diagnosis == "command_to_odom_sign_divergent":
        return {
            "decision": "probe_bridge_controller_sign_chain",
            "live_probe_required": True,
            "rationale": "The odom-facing belief pose diverges from the commanded turn sign often enough to justify a focused bridge/controller sign-chain probe before widening control authority.",
        }
    return {
        "decision": "manual_drive_sign_chain_review",
        "live_probe_required": False,
        "rationale": "The frozen artifacts do not isolate one dominant runtime sign-chain failure mode yet; review the mixed evidence before changing live behavior.",
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


def build_manual_drive_sign_parity_audit_bundle(
    *,
    campaign_id: str,
    campaign_summary_path: Path = DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_CAMPAIGN_SUMMARY,
    run_index: int = DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_RUN_INDEX,
    scenario_id: str = DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SCENARIO_ID,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    paths = divergence.resolve_run_artifact_paths(campaign_summary_path, run_index=run_index)
    state_history_path = Path(paths["state_history_path"])
    truth_timeline_path = Path(paths["truth_timeline_path"])
    timeline_path = Path(paths["timeline_path"])
    timeline_events_path = Path(paths["timeline_events_path"])
    state_rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
    truth_samples = divergence._sorted_truth_samples(divergence.read_json(truth_timeline_path))
    timeline_payload = divergence.read_json(timeline_path) if timeline_path.exists() else {}
    timeline_event_rows = divergence._read_jsonl(timeline_events_path)
    timeline_anchor = divergence.extract_timeline_utc_anchor(
        timeline_payload if isinstance(timeline_payload, dict) else {},
        timeline_event_rows,
    )
    sign_parity_surfaces = load_sign_parity_surfaces()
    turn_summary, turn_fixture_payloads = turn_audit.build_turn_realization_audit_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=campaign_summary_path,
        run_index=run_index,
        scenario_id=scenario_id,
    )
    fixture_payloads = {
        fixture_label: compute_fixture_sign_parity_contract(
            turn_fixture_payload,
            state_rows=state_rows,
            truth_samples=truth_samples,
            timeline_anchor=timeline_anchor,
            sign_parity_surfaces=sign_parity_surfaces,
            scenario_id=scenario_id,
        )
        for fixture_label, turn_fixture_payload in turn_fixture_payloads.items()
    }
    ordered_fixture_payloads = _ordered_fixture_payloads(fixture_payloads)
    root_cause_gate = decide_sign_parity_root_cause(
        ordered_fixture_payloads,
        sign_parity_surfaces=sign_parity_surfaces,
    )
    diagnosis_counts = Counter(
        str(payload.get("fixture_diagnosis", "") or "mixed_sign_chain_unresolved")
        for payload in ordered_fixture_payloads
    )
    summary = {
        "generated_utc": _utc_now_iso(),
        "type": "gather_manual_drive_sign_parity_audit",
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
        "sign_parity_surfaces": sign_parity_surfaces,
        "turn_realization_root_cause_gate": turn_summary.get("root_cause_gate", {}),
        "root_cause_gate": root_cause_gate,
        "diagnosis_counts": dict(diagnosis_counts),
        "next_action": _next_action_recommendation(str(root_cause_gate.get("dominant_diagnosis", "") or "")),
        "run_context": turn_summary.get("run_context", {}),
        "fixtures": [
            {
                "fixture_label": payload.get("fixture_label", ""),
                "fixture_diagnosis": payload.get("fixture_diagnosis", ""),
                "command_sign": payload.get("command_sign"),
                "odom_dominant_yaw_sign": ((payload.get("odom_metrics", {}) or {}).get("dominant_yaw_sign")),
                "world_dominant_yaw_sign": ((payload.get("world_metrics", {}) or {}).get("dominant_yaw_sign")),
                "odom_wrong_sign_step_count": ((payload.get("odom_metrics", {}) or {}).get("wrong_sign_step_count")),
                "world_wrong_sign_step_count": ((payload.get("world_metrics", {}) or {}).get("wrong_sign_step_count")),
                "command_to_odom_sign_match": ((payload.get("sign_matches", {}) or {}).get("command_to_odom_sign_match")),
                "command_to_world_sign_match": ((payload.get("sign_matches", {}) or {}).get("command_to_world_sign_match")),
                "odom_to_world_sign_match": ((payload.get("sign_matches", {}) or {}).get("odom_to_world_sign_match")),
            }
            for payload in ordered_fixture_payloads
        ],
    }
    return summary, fixture_payloads


def build_scorecard_markdown(summary: dict[str, Any], fixture_payloads: dict[str, dict[str, Any]]) -> str:
    surfaces = summary.get("sign_parity_surfaces", {}) if isinstance(summary.get("sign_parity_surfaces"), dict) else {}
    next_action = summary.get("next_action", {}) if isinstance(summary.get("next_action"), dict) else {}
    lines = [
        "# Gather Manual Drive Sign Parity Audit Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Source campaign: `{summary.get('source_campaign_id', '')}`",
        f"- Source run index: `{summary.get('source_run_index', 0)}`",
        f"- Representative fixtures: `{summary.get('representative_fixture_count', 0)}`",
        f"- Dominant diagnosis: `{((summary.get('root_cause_gate', {}) or {}).get('dominant_diagnosis', ''))}`",
        f"- Confidence: `{((summary.get('root_cause_gate', {}) or {}).get('confidence', ''))}`",
        f"- Next action: `{next_action.get('decision', '')}`",
        f"- Live probe required: `{bool(next_action.get('live_probe_required', False))}`",
        "",
        "## Static Sign Surfaces",
        "",
        f"- Bridge sign preserved: `{bool(surfaces.get('bridge_sign_preserved', False))}`",
        f"- Controller configs match: `{bool(surfaces.get('controller_configs_match', False))}`",
        f"- Negative symmetric controller multipliers: `{bool(surfaces.get('controller_negative_symmetric_radius_multipliers', False))}`",
        f"- Static config parity expected: `{bool(surfaces.get('static_config_parity_expected', False))}`",
        f"- State history logs belief pose: `{bool(surfaces.get('state_history_robot_pose_from_belief_pose', False))}`",
        f"- Visual latest robot pose from odom: `{bool(surfaces.get('visual_latest_robot_pose_from_odom', False))}`",
        f"- Dashboard truth fallback present: `{bool(surfaces.get('dashboard_truth_fallback_present', False))}`",
        "",
        "## Fixtures",
        "",
    ]
    for payload in _ordered_fixture_payloads(fixture_payloads):
        odom_metrics = payload.get("odom_metrics", {}) if isinstance(payload.get("odom_metrics"), dict) else {}
        world_metrics = payload.get("world_metrics", {}) if isinstance(payload.get("world_metrics"), dict) else {}
        sign_matches = payload.get("sign_matches", {}) if isinstance(payload.get("sign_matches"), dict) else {}
        lines.append(
            f"- `{payload.get('fixture_label', '')}` diagnosis=`{payload.get('fixture_diagnosis', '')}` "
            f"command=`{int(payload.get('command_sign', 0) or 0)}` "
            f"odom=`{int(odom_metrics.get('dominant_yaw_sign', 0) or 0)}` "
            f"world=`{int(world_metrics.get('dominant_yaw_sign', 0) or 0)}` "
            f"odom_wrong=`{int(odom_metrics.get('wrong_sign_step_count', 0) or 0)}` "
            f"world_wrong=`{int(world_metrics.get('wrong_sign_step_count', 0) or 0)}` "
            f"c->o=`{sign_matches.get('command_to_odom_sign_match')}` "
            f"c->w=`{sign_matches.get('command_to_world_sign_match')}` "
            f"o->w=`{sign_matches.get('odom_to_world_sign_match')}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_manual_drive_sign_parity_audit_bundle(
    *,
    campaign_id: str,
    summary: dict[str, Any],
    fixture_payloads: dict[str, dict[str, Any]],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Path]:
    output_root = ensure_dir(Path(repo_root) / "artifacts" / "session" / campaign_id / "gather_manual_drive_sign_parity_audit")
    fixtures_root = ensure_dir(output_root / "fixtures")
    summary_path = output_root / "manual_drive_sign_parity_summary.json"
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
        description="Audit manual-drive sign parity across the command, odom-facing belief pose, and truth/world pose."
    )
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default=DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SCENARIO_ID)
    parser.add_argument(
        "--campaign-summary-path",
        default=str(DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_CAMPAIGN_SUMMARY),
    )
    parser.add_argument("--run-index", type=int, default=DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_RUN_INDEX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip() or oracle.current_utc_stamp()
    summary, fixture_payloads = build_manual_drive_sign_parity_audit_bundle(
        campaign_id=campaign_id,
        campaign_summary_path=Path(args.campaign_summary_path).resolve(),
        run_index=int(args.run_index),
        scenario_id=str(args.scenario_id or DEFAULT_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SCENARIO_ID),
    )
    output_paths = write_manual_drive_sign_parity_audit_bundle(
        campaign_id=campaign_id,
        summary=summary,
        fixture_payloads=fixture_payloads,
    )
    print(f"GATHER_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SUMMARY={output_paths['summary_path']}")
    print(
        json.dumps(
            {
                "campaign_id": summary.get("campaign_id", ""),
                "decision": ((summary.get("next_action", {}) or {}).get("decision", "")),
                "dominant_diagnosis": ((summary.get("root_cause_gate", {}) or {}).get("dominant_diagnosis", "")),
                "dominant_coverage_count": ((summary.get("root_cause_gate", {}) or {}).get("dominant_coverage_count", 0)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if str((summary.get("root_cause_gate", {}) or {}).get("dominant_diagnosis", "")) != "mixed_sign_chain_unresolved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
