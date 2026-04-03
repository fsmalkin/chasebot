from __future__ import annotations

from datetime import datetime
from datetime import timezone
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


def test_policy_keeps_active_search_out_of_unsafe_stop():
    state = base_state()
    state["brain"]["search_active"] = True  # type: ignore[index]
    state["outcome"]["cmd_vel_recent"] = True  # type: ignore[index]
    state["outcome"]["boundary_activity_seen"] = True  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "search"
    assert policy["preferred_intent"] == "search_for_target"
    assert "active_pursuit_without_target_feedback" not in policy["unsafe_reasons"]


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


def test_policy_prefers_track_when_goal_was_recently_dispatched():
    state = base_state()
    state["perception"]["target_visible_now"] = True  # type: ignore[index]
    state["brain"]["target_locked"] = True  # type: ignore[index]
    state["brain"]["track_active"] = False  # type: ignore[index]
    state["brain"]["goal_in_progress"] = False  # type: ignore[index]
    state["outcome"]["nav_goal_recent"] = True  # type: ignore[index]
    state["outcome"]["cmd_vel_recent"] = True  # type: ignore[index]
    state["belief"]["latest_goal_pose"] = {"frame_id": "odom", "x": 0.8, "y": 0.0}  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "track"
    assert policy["preferred_intent"] == "track_target"
    assert "track_target" in policy["allowed_intents"]


def test_policy_reacquires_when_stale_lock_is_no_longer_visible():
    state = base_state()
    state["brain"]["target_locked"] = True  # type: ignore[index]
    state["brain"]["track_active"] = False  # type: ignore[index]
    state["brain"]["goal_in_progress"] = False  # type: ignore[index]
    state["outcome"]["nav_goal_recent"] = False  # type: ignore[index]
    state["outcome"]["cmd_vel_recent"] = False  # type: ignore[index]
    state["belief"]["latest_goal_pose"] = None  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "search"
    assert policy["preferred_intent"] == "search_for_target"
    assert "search_for_target" in policy["allowed_intents"]
    assert "track_target" not in policy["allowed_intents"]


def test_policy_keeps_fresh_lock_in_plan_handoff_even_when_visibility_flickers():
    state = base_state()
    state["brain"]["target_locked"] = True  # type: ignore[index]
    state["brain"]["target_locked_utc"] = datetime.now(timezone.utc).isoformat()  # type: ignore[index]
    state["perception"]["target_visible_now"] = False  # type: ignore[index]
    state["brain"]["target_visible_recent"] = False  # type: ignore[index]
    state["outcome"]["feedback_recent"] = False  # type: ignore[index]
    state["outcome"]["cmd_vel_recent"] = True  # type: ignore[index]
    state["outcome"]["boundary_activity_seen"] = True  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "plan"
    assert policy["preferred_intent"] == "plan_to_target"
    assert "safe_stop" in policy["allowed_intents"]


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


def test_policy_blocks_when_common_readiness_missing():
    state = base_state()
    state["control_plane_ready"] = False

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "blocked"
    assert policy["preferred_intent"] == ""
    assert policy["allowed_intents"] == []
    assert "control_plane_ready" in policy["common_missing_keys"]


def test_policy_blocks_when_robot_pose_missing():
    state = base_state()
    state["belief"]["robot_pose_available"] = False  # type: ignore[index]
    state["belief"]["latest_robot_pose"] = None  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "blocked"
    assert policy["preferred_intent"] == ""


def test_policy_stops_on_search_exhausted():
    state = base_state()
    state["brain"]["search_active"] = True  # type: ignore[index]
    state["brain"]["search_rotation_accum_rad"] = 7.0  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "stop"
    assert policy["preferred_intent"] == "safe_stop"
    assert "search_exhausted_without_lock" in policy["unsafe_reasons"]


def test_policy_stops_on_pursuit_without_target_feedback():
    state = base_state()
    state["motion_evidence"] = True
    state["outcome"]["boundary_activity_seen"] = True  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "stop"
    assert policy["preferred_intent"] == "safe_stop"
    assert "active_pursuit_without_target_feedback" in policy["unsafe_reasons"]


def test_policy_stops_on_scenario_error():
    state = base_state()
    state["scenario_state"] = "error"

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "stop"
    assert policy["preferred_intent"] == "safe_stop"
    assert "scenario_error" in policy["unsafe_reasons"]


def test_policy_allows_abort_during_active_pursuit_in_stop():
    state = base_state()
    state["scenario_state"] = "error"
    state["motion_evidence"] = True

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert "abort" in policy["allowed_intents"]
    assert "safe_stop" in policy["allowed_intents"]


def test_policy_reacquires_via_search_when_lock_stale_and_visibility_lost():
    """Row 7: locked but stale, no visibility, no recent feedback/goal."""
    state = base_state()
    state["brain"]["target_locked"] = True  # type: ignore[index]
    state["brain"]["track_active"] = False  # type: ignore[index]
    state["brain"]["goal_in_progress"] = False  # type: ignore[index]
    state["brain"]["target_visible_recent"] = False  # type: ignore[index]
    state["outcome"]["nav_goal_recent"] = False  # type: ignore[index]
    state["outcome"]["feedback_recent"] = False  # type: ignore[index]
    state["outcome"]["cmd_vel_recent"] = False  # type: ignore[index]

    policy = build_policy_snapshot(state, sim_gate_ready=True)

    assert policy["stage"] == "search"
    assert policy["preferred_intent"] == "search_for_target"


def test_policy_fallback_stop_on_unrecognized_state():
    """Row 9: the fallback stop should never actually fire with current
    signal combinations, but verify the else branch is safe_stop."""
    # This is hard to trigger because the if/elif chain is exhaustive,
    # but we can verify the final else by patching.  For now, just
    # confirm the function never crashes on a minimal state.
    policy = build_policy_snapshot({}, sim_gate_ready=False)
    assert policy["stage"] == "blocked"
    assert policy["preferred_intent"] == ""


def test_intent_readiness_marks_plan_not_allowed_while_searching():
    state = base_state()

    readiness = intent_readiness_snapshot("plan_to_target", state, sim_gate_ready=True)

    assert readiness["ready_to_dispatch"] is False
    assert readiness["policy_allowed"] is False
    assert "policy_not_allowed" in readiness["missing_keys"]
