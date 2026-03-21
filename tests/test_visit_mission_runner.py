from __future__ import annotations

import math
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from visit_mission_runner import build_visit_targets  # noqa: E402
from visit_mission_runner import deterministic_visit_decision  # noqa: E402
from visit_mission_runner import mission_truth_distance_m  # noqa: E402
from visit_mission_runner import visit_success  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"


def _load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_build_visit_targets_for_single_ball_proof():
    targets = build_visit_targets("visit_single_ball_proof")
    assert len(targets) == 1
    assert targets[0].id == "ball_1"
    assert targets[0].start_visible is False


def test_build_visit_targets_for_three_ball_sequence():
    targets = build_visit_targets("visit_three_ball_sequence")
    assert [item.id for item in targets] == ["ball_1", "ball_2", "ball_3"]
    assert targets[0].start_visible is False
    assert targets[1].start_visible is True
    assert targets[2].start_visible is True


def test_deterministic_visit_decision_prefers_search_when_target_missing():
    contract = _load_contract()
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": "session-1",
        "sim_gate_ready": True,
        "perception": {"detection_topic_seen": True, "target_visible_now": False},
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        "brain": {"target_locked": False, "goal_in_progress": False, "track_active": False},
        "outcome": {"nav_goal_recent": False, "cmd_vel_recent": False, "feedback_recent": False, "boundary_activity_seen": False},
    }
    decision = deterministic_visit_decision(state, "visit the ball", contract)
    assert decision["status"] == "recommendation"
    assert decision["intent"] == "search_for_target"
    assert decision["args"] == {"target_class": "ball"}


def test_deterministic_visit_decision_prefers_plan_when_locked():
    contract = _load_contract()
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": "session-1",
        "sim_gate_ready": True,
        "perception": {"detection_topic_seen": True, "target_visible_now": True},
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        "brain": {"target_locked": True, "goal_in_progress": False, "track_active": False},
        "outcome": {"nav_goal_recent": False, "cmd_vel_recent": False, "feedback_recent": True, "boundary_activity_seen": False},
    }
    decision = deterministic_visit_decision(state, "visit the ball", contract)
    assert decision["intent"] == "plan_to_target"
    assert decision["args"] == {"approach_distance_m": 0.25}


def test_deterministic_visit_decision_reacquires_when_visibility_is_lost_mid_pursuit():
    contract = _load_contract()
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": "session-1",
        "sim_gate_ready": True,
        "perception": {"detection_topic_seen": True, "target_visible_now": False},
        "belief": {
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "latest_goal_pose": {"frame_id": "odom", "x": 0.8, "y": 0.0},
        },
        "brain": {"target_locked": True, "goal_in_progress": False, "track_active": True, "target_visible_recent": False},
        "outcome": {"nav_goal_recent": True, "cmd_vel_recent": False, "feedback_recent": False, "boundary_activity_seen": False},
    }
    decision = deterministic_visit_decision(state, "visit the ball", contract)
    assert decision["intent"] == "search_for_target"
    assert decision["args"] == {"target_class": "ball"}


def test_deterministic_visit_decision_holds_search_during_hidden_start_settle():
    contract = _load_contract()
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": "session-1",
        "sim_gate_ready": True,
        "search_bias_active": True,
        "perception": {"detection_topic_seen": True, "target_visible_now": True},
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        "brain": {"target_locked": False, "goal_in_progress": False, "track_active": False},
        "outcome": {"nav_goal_recent": False, "cmd_vel_recent": False, "feedback_recent": False, "boundary_activity_seen": False},
    }
    decision = deterministic_visit_decision(state, "visit the ball", contract)
    assert decision["intent"] == "search_for_target"
    assert decision["args"] == {"target_class": "ball"}


def test_mission_truth_distance_uses_truth_target_world():
    state = {
        "belief": {"latest_robot_pose": {"x": 1.0, "y": 2.0}},
        "perception": {"latest_truth_target_world": {"x": 1.3, "y": 2.4}},
    }
    assert math.isclose(mission_truth_distance_m(state), 0.5, abs_tol=1e-6)


def test_visit_success_requires_lock_nav_and_distance_tolerance():
    state = {
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0}},
        "perception": {"latest_truth_target_world": {"x": 0.2, "y": 0.1}},
    }
    assert visit_success(
        state,
        target_locked_seen=True,
        nav_activity_seen=True,
        visit_tolerance_m=0.35,
        elapsed_since_spawn_s=1.5,
        min_dwell_s=1.0,
    ) is True
    assert visit_success(
        state,
        target_locked_seen=False,
        nav_activity_seen=True,
        visit_tolerance_m=0.35,
        elapsed_since_spawn_s=1.5,
        min_dwell_s=1.0,
    ) is False
    assert visit_success(
        state,
        target_locked_seen=True,
        nav_activity_seen=False,
        visit_tolerance_m=0.35,
        elapsed_since_spawn_s=1.5,
        min_dwell_s=1.0,
    ) is False
    assert visit_success(
        state,
        target_locked_seen=True,
        nav_activity_seen=True,
        visit_tolerance_m=0.35,
        elapsed_since_spawn_s=0.2,
        min_dwell_s=1.0,
    ) is False
