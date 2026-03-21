#!/usr/bin/env python3
"""Shared deterministic escalation policy for bounded supervisor decisions."""

from __future__ import annotations

from typing import Any, Dict


INTENT_NAMES = (
    "search_for_target",
    "acquire_target",
    "plan_to_target",
    "track_target",
    "abort",
    "safe_stop",
)

COMMON_REQUIRED_KEYS = (
    "control_plane_ready",
    "environment_ready",
    "session_active",
    "sim_gate_ready",
)


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _intent_summary(intent_name: str, policy_stage: str, preferred_intent: str) -> str:
    summaries = {
        "search_for_target": "Use search_for_target(ball) when the environment is ready but the target is not yet visible.",
        "acquire_target": "Use acquire_target(ball) once the ball is visible but not yet locked.",
        "plan_to_target": "Use plan_to_target(0.25) once the target is locked and no goal is active.",
        "track_target": "Use track_target() while pursuit is already active and the target remains actionable.",
        "abort": "Use abort() to cancel active pursuit when the current run should be interrupted.",
        "safe_stop": "Use safe_stop() as the lowest-risk bounded action when the state becomes unsafe or uncertain.",
    }
    if intent_name == preferred_intent:
        return summaries.get(intent_name, "")
    if preferred_intent:
        return f"{summaries.get(intent_name, '')} Current policy stage is {policy_stage}; preferred action is {preferred_intent}."
    return summaries.get(intent_name, "")


def policy_signal_snapshot(state: Dict[str, Any], *, sim_gate_ready: bool | None = None) -> Dict[str, Any]:
    perception = _as_dict(state.get("perception"))
    belief = _as_dict(state.get("belief"))
    brain = _as_dict(state.get("brain"))
    outcome = _as_dict(state.get("outcome"))
    mission = _as_dict(state.get("mission"))

    resolved_sim_gate_ready = _as_bool(state.get("sim_gate_ready", False)) if sim_gate_ready is None else bool(sim_gate_ready)
    target_visible_now = _as_bool(perception.get("target_visible_now", False))
    target_visible_recent = _as_bool(brain.get("target_visible_recent", False)) or target_visible_now
    target_locked = _as_bool(brain.get("target_locked", False))
    nav_goal_recent = _as_bool(outcome.get("nav_goal_recent", False)) or bool(belief.get("latest_goal_pose"))
    motion_active = (
        _as_bool(outcome.get("cmd_vel_recent", False))
        or _as_bool(state.get("motion_evidence", False))
        or _as_bool(brain.get("goal_in_progress", False))
    )
    boundary_activity_seen = _as_bool(outcome.get("boundary_activity_seen", False)) or motion_active
    search_rotation = brain.get("search_rotation_accum_rad", 0.0)
    try:
        search_rotation = float(search_rotation)
    except (TypeError, ValueError):
        search_rotation = 0.0

    return {
        "control_plane_ready": _as_bool(state.get("control_plane_ready", False)),
        "environment_ready": _as_text(state.get("environment_state"), "unknown") == "environment_ready",
        "environment_error": _as_text(state.get("environment_state"), "unknown") == "error",
        "scenario_error": _as_text(state.get("scenario_state"), "unknown") == "error",
        "session_active": bool(_as_text(state.get("session_id"), "")),
        "sim_gate_ready": resolved_sim_gate_ready,
        "robot_pose_available": _as_bool(belief.get("robot_pose_available", False)) or bool(belief.get("latest_robot_pose")),
        "detection_seen": _as_bool(perception.get("detection_topic_seen", False)),
        "target_visible_now": target_visible_now,
        "target_visible_recent": target_visible_recent,
        "target_locked": target_locked,
        "search_active": _as_bool(brain.get("search_active", False)),
        "search_rotation_accum_rad": round(search_rotation, 6),
        "track_active": _as_bool(brain.get("track_active", False)),
        "goal_in_progress": _as_bool(brain.get("goal_in_progress", False)),
        "nav_goal_recent": nav_goal_recent,
        "feedback_recent": _as_bool(outcome.get("feedback_recent", False)),
        "cmd_vel_recent": _as_bool(outcome.get("cmd_vel_recent", False)),
        "motion_evidence": _as_bool(state.get("motion_evidence", False)),
        "boundary_activity_seen": boundary_activity_seen,
        "search_bias_active": _as_bool(state.get("search_bias_active", mission.get("search_bias_active", False))),
        "last_result": _as_text(state.get("last_result"), ""),
        "last_feedback": _as_text(state.get("last_feedback"), ""),
    }


def build_policy_snapshot(state: Dict[str, Any], *, sim_gate_ready: bool | None = None) -> Dict[str, Any]:
    signals = policy_signal_snapshot(state, sim_gate_ready=sim_gate_ready)
    common_missing = [name for name in COMMON_REQUIRED_KEYS if not signals.get(name, False)]
    active_pursuit = bool(
        signals["goal_in_progress"]
        or signals["track_active"]
        or signals["nav_goal_recent"]
        or signals["cmd_vel_recent"]
        or signals["boundary_activity_seen"]
        or signals["motion_evidence"]
    )
    unsafe_reasons: list[str] = []
    if signals["environment_error"]:
        unsafe_reasons.append("environment_error")
    if signals["scenario_error"]:
        unsafe_reasons.append("scenario_error")
    if (
        signals["search_active"]
        and signals["search_rotation_accum_rad"] >= 6.0
        and not signals["target_visible_now"]
        and not signals["target_locked"]
    ):
        unsafe_reasons.append("search_exhausted_without_lock")
    if (
        active_pursuit
        and not signals["target_visible_now"]
        and not signals["target_visible_recent"]
        and not signals["target_locked"]
        and not signals["feedback_recent"]
    ):
        unsafe_reasons.append("active_pursuit_without_target_feedback")

    allowed_intents: list[str] = []
    preferred_intent = ""
    policy_stage = "blocked"
    policy_reason = "The supervisor is waiting for the environment to become actionable."

    if common_missing:
        policy_reason = f"Missing common readiness: {', '.join(common_missing)}."
    elif not signals["robot_pose_available"]:
        policy_reason = "Robot pose is required before the bounded supervisor can choose a next step."
    elif signals["search_bias_active"] and not signals["target_locked"] and not active_pursuit:
        policy_stage = "search"
        preferred_intent = "search_for_target"
        allowed_intents = ["search_for_target", "safe_stop"]
        policy_reason = "The current target was spawned out of view, so search remains preferred until visibility settles."
    elif unsafe_reasons:
        policy_stage = "stop"
        preferred_intent = "safe_stop"
        allowed_intents = ["safe_stop"] + (["abort"] if active_pursuit else [])
        policy_reason = f"State is unsafe or inconsistent: {', '.join(unsafe_reasons)}."
    elif not signals["target_visible_now"] and not signals["target_locked"]:
        policy_stage = "search"
        preferred_intent = "search_for_target"
        allowed_intents = ["search_for_target", "safe_stop"] + (["abort"] if active_pursuit else [])
        policy_reason = "The target is not visible yet, so the next bounded step is search."
    elif signals["target_visible_now"] and not signals["target_locked"]:
        policy_stage = "acquire"
        preferred_intent = "acquire_target"
        allowed_intents = ["acquire_target", "safe_stop"] + (["abort"] if active_pursuit else [])
        policy_reason = "The ball is visible but not locked, so acquire_target(ball) is the next bounded step."
    elif (
        signals["target_locked"]
        and not signals["target_visible_now"]
        and not signals["target_visible_recent"]
        and not signals["feedback_recent"]
    ):
        policy_stage = "search"
        preferred_intent = "search_for_target"
        allowed_intents = ["search_for_target", "safe_stop"] + (["abort"] if active_pursuit else [])
        policy_reason = "The target lock is stale and visibility has been lost, so the next bounded step is to reacquire with search."
    elif signals["target_locked"] and not active_pursuit:
        policy_stage = "plan"
        preferred_intent = "plan_to_target"
        allowed_intents = ["plan_to_target", "safe_stop"]
        policy_reason = "The target is locked and no goal is active, so planning is the next bounded step."
    elif active_pursuit:
        policy_stage = "track"
        preferred_intent = "track_target"
        allowed_intents = ["track_target", "safe_stop", "abort"]
        policy_reason = "Pursuit is already active, so the supervisor should stay in track/interrupt space."
    else:
        policy_stage = "stop"
        preferred_intent = "safe_stop"
        allowed_intents = ["safe_stop"]
        policy_reason = "The state is live but does not fit a clearer escalation bucket, so safe_stop is preferred."

    allowed_set = set(allowed_intents)
    gate_hints: Dict[str, Dict[str, Any]] = {}
    for intent_name in INTENT_NAMES:
        required_keys = list(COMMON_REQUIRED_KEYS)
        if intent_name == "search_for_target":
            required_keys.append("robot_pose_available")
        elif intent_name in {"acquire_target", "plan_to_target", "track_target"}:
            required_keys.extend(["robot_pose_available", "detection_seen"])
        missing_keys = [name for name in required_keys if not signals.get(name, False)]
        if intent_name not in allowed_set:
            missing_keys.append("policy_not_allowed")
        gate_hints[intent_name] = {
            "ready": not missing_keys,
            "required_keys": required_keys,
            "missing_keys": missing_keys,
            "policy_allowed": intent_name in allowed_set,
            "summary": _intent_summary(intent_name, policy_stage, preferred_intent),
        }

    return {
        "stage": policy_stage,
        "preferred_intent": preferred_intent,
        "allowed_intents": allowed_intents,
        "common_missing_keys": common_missing,
        "unsafe_reasons": unsafe_reasons,
        "reason": policy_reason,
        "active_pursuit": active_pursuit,
        "signals": signals,
        "gate_hints": gate_hints,
    }


def intent_readiness_snapshot(intent_name: str, state: Dict[str, Any], *, sim_gate_ready: bool | None = None) -> Dict[str, Any]:
    policy = build_policy_snapshot(state, sim_gate_ready=sim_gate_ready)
    gate_hints = policy.get("gate_hints", {})
    gate_hint = gate_hints.get(intent_name, {}) if isinstance(gate_hints, dict) else {}
    signals = policy.get("signals", {}) if isinstance(policy.get("signals"), dict) else {}
    readiness = {
        "control_plane_ready": bool(signals.get("control_plane_ready", False)),
        "environment_ready": bool(signals.get("environment_ready", False)),
        "session_active": bool(signals.get("session_active", False)),
        "sim_gate_ready": bool(signals.get("sim_gate_ready", False)),
        "detection_seen": bool(signals.get("detection_seen", False)),
        "target_visible_now": bool(signals.get("target_visible_now", False)),
        "robot_pose_available": bool(signals.get("robot_pose_available", False)),
        "target_locked": bool(signals.get("target_locked", False)),
        "nav_goal_recent": bool(signals.get("nav_goal_recent", False)),
        "feedback_recent": bool(signals.get("feedback_recent", False)),
        "cmd_vel_recent": bool(signals.get("cmd_vel_recent", False)),
        "search_bias_active": bool(signals.get("search_bias_active", False)),
        "policy_stage": str(policy.get("stage", "blocked")),
        "policy_preferred_intent": str(policy.get("preferred_intent", "")),
        "policy_allowed": bool(gate_hint.get("policy_allowed", False)),
        "policy_reason": str(policy.get("reason", "")),
        "unsafe_reasons": list(policy.get("unsafe_reasons", [])),
        "allowed_intents": list(policy.get("allowed_intents", [])),
        "required_keys": list(gate_hint.get("required_keys", [])),
        "missing_keys": list(gate_hint.get("missing_keys", [])),
        "ready_to_dispatch": bool(gate_hint.get("ready", False)),
    }
    return readiness
