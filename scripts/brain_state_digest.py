#!/usr/bin/env python3
"""Build compact fixed-shape state digests for LLM supervisor decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from brain_supervisor_policy import build_policy_snapshot

CANONICAL_ARGS_BY_INTENT: dict[str, dict[str, object]] = {
    "search_for_target": {"target_class": "ball"},
    "acquire_target": {"target_class": "ball"},
    "plan_to_target": {"approach_distance_m": 0.25},
    "track_target": {},
    "abort": {},
    "safe_stop": {},
}


def capability_limits() -> Dict[str, list[str]]:
    return {
        "has_now": [
            "perception from the current target pipeline",
            "bounded search-turn until a target becomes visible",
            "goal creation and motion execution through the frozen control path",
            "track, abort, and safe_stop through the fixed intent boundary",
        ],
        "future_llm_uses": [
            "the frozen intent boundary",
            "current perception and state signals",
            "returned feedback and outcome signals",
        ],
        "not_yet": [
            "freeform language understanding",
            "open-ended planning or task decomposition",
            "unbounded action selection outside the frozen set",
            "environment or scenario control from the LLM layer",
        ],
    }


def _clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _clean_bool(value: Any) -> bool:
    return bool(value)


def _clean_number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in {float("inf"), float("-inf")}:
        return None
    return numeric


def _clean_point(value: Any) -> Dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    x = _clean_number(value.get("x"))
    y = _clean_number(value.get("y"))
    if x is None or y is None:
        return None
    return {"x": round(x, 4), "y": round(y, 4)}


def _clean_pose(value: Any) -> Dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    point = _clean_point(value)
    if point is None:
        return None
    yaw = _clean_number(value.get("yaw"))
    if yaw is None:
        return point
    return {"x": point["x"], "y": point["y"], "yaw": round(yaw, 4)}

def _canonical_action_space(contract: Dict[str, Any], state: Dict[str, Any]) -> list[Dict[str, Any]]:
    descriptions: dict[str, str] = {}
    for item in list(contract.get("intents", [])):
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        if name:
            descriptions[name] = _clean_text(item.get("description"))
    policy = build_policy_snapshot(state, sim_gate_ready=bool(state.get("sim_gate_ready", False)))
    gate_hints = policy.get("gate_hints", {}) if isinstance(policy.get("gate_hints"), dict) else {}
    actions: list[Dict[str, Any]] = []
    for intent_name, args in CANONICAL_ARGS_BY_INTENT.items():
        actions.append(
            {
                "name": intent_name,
                "args": dict(args),
                "description": descriptions.get(intent_name, ""),
                "gate_hint": gate_hints.get(intent_name, {}),
            }
        )
    return actions


def build_state_digest(state: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    perception = state.get("perception") if isinstance(state.get("perception"), dict) else {}
    belief = state.get("belief") if isinstance(state.get("belief"), dict) else {}
    outcome = state.get("outcome") if isinstance(state.get("outcome"), dict) else {}
    visited_targets = state.get("visited_targets") if isinstance(state.get("visited_targets"), list) else []
    remaining_targets = state.get("remaining_targets") if isinstance(state.get("remaining_targets"), list) else []
    policy = build_policy_snapshot(state, sim_gate_ready=bool(state.get("sim_gate_ready", False)))

    return {
        "schema_version": 1,
        "session_id": _clean_text(state.get("session_id")),
        "environment_state": _clean_text(state.get("environment_state"), "unknown"),
        "scenario_state": _clean_text(state.get("scenario_state"), "unknown"),
        "phase": _clean_text(state.get("phase"), "unknown"),
        "target_id": _clean_text(state.get("target_id")),
        "target_transition_active": _clean_bool(state.get("target_transition_active")),
        "perception": {
            "detection_topic_seen": _clean_bool(perception.get("detection_topic_seen")),
            "target_visible_now": _clean_bool(perception.get("target_visible_now")),
            "target_visible_ratio": round(_clean_number(perception.get("target_visible_ratio")) or 0.0, 4),
            "latest_detection_world": _clean_point(perception.get("latest_detection_world")),
            "latest_truth_target_world": _clean_point(perception.get("latest_truth_target_world")),
            "truth_alignment_ok": _clean_bool(perception.get("truth_alignment_ok")),
            "truth_status": _clean_text(perception.get("truth_status"), "truth unavailable"),
        },
        "belief": {
            "latest_robot_pose": _clean_pose(belief.get("latest_robot_pose")),
            "latest_goal_pose": _clean_pose(belief.get("latest_goal_pose")),
            "latest_target_distance_m": _clean_number(belief.get("latest_target_distance_m")),
            "distance_trend": _clean_text(belief.get("distance_trend"), "unknown"),
        },
        "brain": {
            "search_state": _clean_text(state.get("brain", {}).get("search_state") if isinstance(state.get("brain"), dict) else "", "unknown"),
            "target_locked": _clean_bool(state.get("brain", {}).get("target_locked") if isinstance(state.get("brain"), dict) else False),
            "goal_in_progress": _clean_bool(state.get("brain", {}).get("goal_in_progress") if isinstance(state.get("brain"), dict) else False),
            "track_active": _clean_bool(state.get("brain", {}).get("track_active") if isinstance(state.get("brain"), dict) else False),
        },
        "mission": {
            "phase": _clean_text(state.get("mission_phase"), "idle"),
            "status": _clean_text(state.get("mission_status"), "idle"),
            "current_target_id": _clean_text(state.get("current_target_id")),
            "visit_index": int(state.get("visit_index", 0) or 0),
            "search_bias_active": _clean_bool(state.get("search_bias_active")),
            "visited_targets": [str(item) for item in visited_targets],
            "remaining_targets": [str(item) for item in remaining_targets],
        },
        "policy": {
            "stage": _clean_text(policy.get("stage"), "blocked"),
            "preferred_intent": _clean_text(policy.get("preferred_intent")),
            "allowed_intents": [str(item) for item in list(policy.get("allowed_intents", []))],
            "reason": _clean_text(policy.get("reason")),
            "unsafe_reasons": [str(item) for item in list(policy.get("unsafe_reasons", []))],
        },
        "outcome": {
            "motion_evidence": _clean_bool(state.get("motion_evidence")),
            "feedback_recent": _clean_bool(outcome.get("feedback_recent")),
            "nav_goal_recent": _clean_bool(outcome.get("nav_goal_recent")),
            "cmd_vel_recent": _clean_bool(outcome.get("cmd_vel_recent")),
            "boundary_activity_seen": _clean_bool(outcome.get("boundary_activity_seen")),
            "last_result": _clean_text(state.get("last_result")),
            "last_feedback": _clean_text(state.get("last_feedback")),
            "last_intent": _clean_text(state.get("last_intent")),
        },
        "frozen_action_space": _canonical_action_space(contract, state),
        "capability_limits": capability_limits(),
    }


def state_digest_hash(digest: Dict[str, Any]) -> str:
    serialized = json.dumps(digest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
