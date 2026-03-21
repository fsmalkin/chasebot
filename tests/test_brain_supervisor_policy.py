from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from brain_supervisor_policy import build_policy_snapshot  # noqa: E402
from brain_supervisor_policy import intent_readiness_snapshot  # noqa: E402


def base_state() -> dict[str, object]:
    return {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "scenario_state": "ready",
        "session_id": "20260315T010000Z",
        "motion_evidence": False,
        "perception": {
            "detection_topic_seen": True,
            "target_visible_now": False,
        },
        "belief": {
            "robot_pose_available": True,
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "latest_goal_pose": None,
        },
        "brain": {
            "search_active": False,
            "target_visible_recent": False,
            "target_locked": False,
            "track_active": False,
            "goal_in_progress": False,
            "search_rotation_accum_rad": 0.0,
        },
        "outcome": {
            "feedback_recent": False,
            "nav_goal_recent": False,
            "cmd_vel_recent": False,
            "boundary_activity_seen": False,
        },
    }


def test_policy_prefers_search_when_target_not_visible():
    state = base_state()
    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "search"
    assert policy["preferred_intent"] == "search_for_target"
    assert "search_for_target" in policy["allowed_intents"]
    assert "plan_to_target" not in policy["allowed_intents"]


def test_policy_prefers_acquire_when_target_visible_but_not_locked():
    state = base_state()
    state["perception"]["target_visible_now"] = True  # type: ignore[index]
    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "acquire"
    assert policy["preferred_intent"] == "acquire_target"
    assert "acquire_target" in policy["allowed_intents"]
    assert "plan_to_target" not in policy["allowed_intents"]


def test_policy_prefers_plan_when_target_locked_without_goal():
    state = base_state()
    state["perception"]["target_visible_now"] = True  # type: ignore[index]
    state["brain"]["target_locked"] = True  # type: ignore[index]
    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "plan"
    assert policy["preferred_intent"] == "plan_to_target"
    assert "plan_to_target" in policy["allowed_intents"]
    assert "track_target" not in policy["allowed_intents"]


def test_policy_prefers_track_when_pursuit_is_active():
    state = base_state()
    state["perception"]["target_visible_now"] = True  # type: ignore[index]
    state["brain"]["target_locked"] = True  # type: ignore[index]
    state["brain"]["goal_in_progress"] = True  # type: ignore[index]
    state["outcome"]["nav_goal_recent"] = True  # type: ignore[index]
    state["outcome"]["cmd_vel_recent"] = True  # type: ignore[index]
    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "track"
    assert policy["preferred_intent"] == "track_target"
    assert "track_target" in policy["allowed_intents"]
    assert "safe_stop" in policy["allowed_intents"]
    assert "abort" in policy["allowed_intents"]


def test_policy_reacquires_when_locked_target_is_no_longer_visible():
    state = base_state()
    state["brain"]["target_locked"] = True  # type: ignore[index]
    state["brain"]["track_active"] = True  # type: ignore[index]
    state["outcome"]["nav_goal_recent"] = True  # type: ignore[index]
    state["belief"]["latest_goal_pose"] = {"frame_id": "odom", "x": 0.8, "y": 0.0}  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "search"
    assert policy["preferred_intent"] == "search_for_target"
    assert "search_for_target" in policy["allowed_intents"]
    assert "track_target" not in policy["allowed_intents"]


def test_policy_exposes_safe_stop_on_unsafe_state():
    state = base_state()
    state["scenario_state"] = "error"
    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "stop"
    assert policy["preferred_intent"] == "safe_stop"
    assert "safe_stop" in policy["allowed_intents"]


def test_policy_prefers_search_when_hidden_start_bias_is_active():
    state = base_state()
    state["perception"]["target_visible_now"] = True  # type: ignore[index]
    state["search_bias_active"] = True

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "search"
    assert policy["preferred_intent"] == "search_for_target"
    assert "search_for_target" in policy["allowed_intents"]
    assert "acquire_target" not in policy["allowed_intents"]


def test_intent_readiness_marks_plan_not_allowed_while_searching():
    state = base_state()

    readiness = intent_readiness_snapshot("plan_to_target", state, sim_gate_ready=True)

    assert readiness["ready_to_dispatch"] is False
    assert readiness["policy_allowed"] is False
    assert "policy_not_allowed" in readiness["missing_keys"]
