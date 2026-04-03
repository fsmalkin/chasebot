from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import visit_mission_runner as visit_runner  # noqa: E402
from visit_mission_runner import build_visit_targets  # noqa: E402
from visit_mission_runner import decision_signature  # noqa: E402
from visit_mission_runner import deterministic_visit_decision  # noqa: E402
from visit_mission_runner import feedback_indicates_goal_success  # noqa: E402
from visit_mission_runner import mission_belief_distance_m  # noqa: E402
from visit_mission_runner import mission_truth_distance_m  # noqa: E402
from visit_mission_runner import mission_vision_truth_delta_m  # noqa: E402
from visit_mission_runner import detection_matches_active_truth  # noqa: E402
from visit_mission_runner import off_truth_centering_during_search  # noqa: E402
from visit_mission_runner import search_bias_release_ready  # noqa: E402
from visit_mission_runner import truth_missing_after_goal_failure  # noqa: E402
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


def test_deterministic_visit_decision_prefers_track_when_visibility_flickers_during_active_pursuit():
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
    assert decision["intent"] == "track_target"
    assert decision["args"] == {}


def test_deterministic_visit_decision_reacquires_when_stale_lock_loses_visibility():
    contract = _load_contract()
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": "session-1",
        "sim_gate_ready": True,
        "perception": {"detection_topic_seen": True, "target_visible_now": False},
        "belief": {
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "latest_goal_pose": None,
        },
        "brain": {"target_locked": True, "goal_in_progress": False, "track_active": False, "target_visible_recent": False},
        "outcome": {"nav_goal_recent": False, "cmd_vel_recent": False, "feedback_recent": False, "boundary_activity_seen": False},
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


def test_deterministic_visit_decision_does_not_acquire_off_truth_visible_target():
    contract = _load_contract()
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": "session-1",
        "sim_gate_ready": True,
        "perception": {
            "detection_topic_seen": True,
            "target_visible_now": True,
            "latest_detection_world": {"x": 0.08, "y": 0.73},
            "latest_truth_target_world": {"x": -0.70, "y": -1.44},
        },
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        "brain": {"target_locked": False, "goal_in_progress": False, "track_active": False},
        "outcome": {"nav_goal_recent": False, "cmd_vel_recent": False, "feedback_recent": False, "boundary_activity_seen": False},
    }
    decision = deterministic_visit_decision(state, "visit the ball", contract)
    assert decision["intent"] == "search_for_target"
    assert "diverges from active truth" in decision["rationale_short"]


def test_mission_truth_distance_uses_truth_target_world():
    state = {
        "belief": {"latest_robot_pose": {"x": 1.0, "y": 2.0}},
        "perception": {"latest_truth_target_world": {"x": 1.3, "y": 2.4}},
    }
    assert math.isclose(mission_truth_distance_m(state), 0.5, abs_tol=1e-6)


def test_mission_truth_distance_fails_closed_without_truth_target_world():
    state = {
        "belief": {
            "latest_robot_pose": {"x": 1.0, "y": 2.0},
            "latest_target_distance_m": 0.12,
        },
        "perception": {},
    }
    assert mission_truth_distance_m(state) is None


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


def test_visit_success_fails_closed_when_truth_target_is_missing():
    state = {
        "belief": {
            "latest_robot_pose": {"x": 0.0, "y": 0.0},
            "latest_target_distance_m": 0.05,
        },
        "perception": {},
    }
    assert visit_success(
        state,
        target_locked_seen=True,
        nav_activity_seen=True,
        visit_tolerance_m=0.35,
        elapsed_since_spawn_s=1.5,
        min_dwell_s=1.0,
    ) is False


def test_mission_belief_distance_uses_latest_target_distance():
    state = {"belief": {"latest_target_distance_m": 0.22}}
    assert math.isclose(mission_belief_distance_m(state), 0.22, abs_tol=1e-6)


def test_mission_vision_truth_delta_uses_detection_and_truth_world():
    state = {
        "perception": {
            "latest_detection_world": {"x": -1.0, "y": 0.0},
            "latest_truth_target_world": {"x": 1.1, "y": 0.0},
        }
    }
    assert math.isclose(mission_vision_truth_delta_m(state), 2.1, abs_tol=1e-6)


def test_detection_matches_active_truth_requires_close_alignment():
    aligned = {
        "perception": {
            "latest_detection_world": {"x": 1.22, "y": -0.04},
            "latest_truth_target_world": {"x": 1.1, "y": 0.0},
        }
    }
    divergent = {
        "perception": {
            "latest_detection_world": {"x": -1.0, "y": 0.0},
            "latest_truth_target_world": {"x": 1.1, "y": 0.0},
        }
    }
    assert detection_matches_active_truth(aligned, tolerance_m=0.2) is True
    assert detection_matches_active_truth(divergent, tolerance_m=0.2) is False


def test_detection_matches_active_truth_clamps_to_observer_alignment_threshold():
    near_but_wrong = {
        "perception": {
            "latest_detection_world": {"x": -0.52, "y": -0.85},
            "latest_truth_target_world": {"x": 0.02, "y": -1.10},
        }
    }
    assert mission_vision_truth_delta_m(near_but_wrong) > 0.5
    assert detection_matches_active_truth(near_but_wrong) is False
    assert detection_matches_active_truth(near_but_wrong, tolerance_m=0.75) is False


def test_off_truth_centering_during_search_requires_visible_search_and_divergent_truth():
    state = {
        "brain": {
            "search_active": True,
            "search_state": "rotating",
            "target_locked": False,
        },
        "perception": {
            "target_visible_now": True,
            "latest_detection_world": {"x": -0.99, "y": -0.04},
            "latest_truth_target_world": {"x": 1.10, "y": 0.00},
        },
    }
    assert off_truth_centering_during_search(state) is True


def test_off_truth_centering_during_search_ignores_aligned_or_non_visible_states():
    aligned = {
        "brain": {
            "search_active": True,
            "search_state": "centering",
            "target_locked": False,
        },
        "perception": {
            "target_visible_now": True,
            "latest_detection_world": {"x": 1.12, "y": -0.03},
            "latest_truth_target_world": {"x": 1.10, "y": 0.00},
        },
    }
    hidden = {
        "brain": {
            "search_active": True,
            "search_state": "rotating",
            "target_locked": False,
        },
        "perception": {
            "target_visible_now": False,
            "latest_detection_world": {"x": -0.99, "y": -0.04},
            "latest_truth_target_world": {"x": 1.10, "y": 0.00},
        },
    }
    assert off_truth_centering_during_search(aligned) is False
    assert off_truth_centering_during_search(hidden) is False


def test_search_bias_release_ready_holds_after_off_target_rejection_until_new_rotation():
    assert search_bias_release_ready(
        target_locked_seen=False,
        search_active=False,
        search_rotation_accum_rad=0.5,
        search_rotation_baseline_rad=0.5,
        hold_until_monotonic=12.0,
        now_monotonic=10.0,
    ) is False
    assert search_bias_release_ready(
        target_locked_seen=False,
        search_active=False,
        search_rotation_accum_rad=0.7,
        search_rotation_baseline_rad=0.5,
        hold_until_monotonic=12.0,
        now_monotonic=10.0,
    ) is True


def test_feedback_indicates_goal_success_matches_executor_feedback():
    state = {"brain": {"last_feedback_text": "nav goal reached successfully"}}
    assert feedback_indicates_goal_success(state) is True


def test_truth_missing_after_goal_failure_requires_goal_success_and_close_belief_distance():
    state = {
        "belief": {"latest_target_distance_m": 0.22},
        "perception": {"latest_truth_target_world": None},
        "brain": {"last_feedback_text": "nav goal reached successfully"},
    }
    assert truth_missing_after_goal_failure(
        state,
        target_locked_seen=True,
        nav_activity_seen=True,
        goal_success_seen_monotonic=100.0,
        visit_tolerance_m=0.35,
        post_goal_truth_grace_s=2.5,
        now_monotonic=102.6,
    ) is True
    assert truth_missing_after_goal_failure(
        state,
        target_locked_seen=True,
        nav_activity_seen=True,
        goal_success_seen_monotonic=100.0,
        visit_tolerance_m=0.35,
        post_goal_truth_grace_s=2.5,
        now_monotonic=101.0,
    ) is False
    assert truth_missing_after_goal_failure(
        state,
        target_locked_seen=True,
        nav_activity_seen=True,
        goal_success_seen_monotonic=None,
        visit_tolerance_m=0.35,
        post_goal_truth_grace_s=2.5,
        now_monotonic=105.0,
    ) is False


def _make_runner(monkeypatch, scenario_id: str = "visit_three_ball_sequence") -> visit_runner.VisitMissionRunner:
    monkeypatch.setattr(visit_runner, "choose_docker_cli", lambda: "docker")
    args = SimpleNamespace(
        dashboard_url="http://127.0.0.1:8860",
        contract=str(CONTRACT_PATH),
        scenario_id=scenario_id,
        task="visit the ball",
        dispatch_cooldown_s=1.0,
        search_timeout_s=20.0,
        post_goal_truth_grace_s=2.5,
        target_model_sdf=str(REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"),
        target_model_name="visit_mission_target",
    )
    runner = visit_runner.VisitMissionRunner(args)
    runner._container_id = lambda project_name, service_name: "sim-gate-1"
    runner._docker_exec = lambda container_id, script: (0, "ok")
    return runner


def test_visible_start_rotates_robot_toward_spawned_target(monkeypatch, tmp_path):
    runner = _make_runner(monkeypatch)
    target = next(item for item in runner.targets if item.id == "ball_3")
    state = {
        "compose_project": "chasecar_dashboard_test",
        "world_name": "yolo_test_world",
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
    }

    payload = runner._spawn_target_from_mission_anchor(state, target, tmp_path)
    bearing = math.atan2(
        float(payload["target_world"]["y"]) - float(payload["robot_pose_after_spawn"]["y"]),
        float(payload["target_world"]["x"]) - float(payload["robot_pose_after_spawn"]["x"]),
    )
    turned_yaw = float(payload["robot_pose_after_spawn"]["yaw"])

    assert math.isclose(visit_runner.normalize_angle(turned_yaw - bearing), 0.0, abs_tol=1e-6)


def test_hidden_start_rotates_robot_away_from_spawned_target(monkeypatch, tmp_path):
    runner = _make_runner(monkeypatch)
    target = next(item for item in runner.targets if item.id == "ball_1")
    state = {
        "compose_project": "chasecar_dashboard_test",
        "world_name": "yolo_test_world",
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
    }

    payload = runner._spawn_target_from_mission_anchor(state, target, tmp_path)
    bearing = math.atan2(
        float(payload["target_world"]["y"]) - float(payload["robot_pose_after_spawn"]["y"]),
        float(payload["target_world"]["x"]) - float(payload["robot_pose_after_spawn"]["x"]),
    )
    turned_yaw = float(payload["robot_pose_after_spawn"]["yaw"])

    assert math.isclose(abs(visit_runner.normalize_angle(turned_yaw - bearing)), math.pi, abs_tol=1e-6)


def test_search_dispatch_in_flight_suppresses_duplicate_dispatch(monkeypatch):
    runner = _make_runner(monkeypatch)
    decision = {
        "status": "recommendation",
        "intent": "search_for_target",
        "args": {"target_class": "ball"},
    }
    runner.last_decision_signature = decision_signature(decision)
    runner.last_state_hash = "prior"
    runner.last_dispatch_monotonic = 100.0
    state = {"brain": {"search_active": True}}

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 101.0)

    assert runner._should_dispatch_decision(decision=decision, state_hash="new", state=state) is False


def test_own_intent_preserves_primary_search_intent(monkeypatch):
    runner = _make_runner(monkeypatch)
    target = next(item for item in runner.targets if item.id == "ball_1")
    decision = {
        "status": "recommendation",
        "intent": "search_for_target",
        "args": {"target_class": "ball"},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 123.0)

    first, owned_intent, owned_args, owned_since = runner._own_intent(
        target=target,
        attempt=0,
        decision=decision,
        state_hash="search-hash",
        first_dispatched_intent="",
        announce=False,
    )

    assert first == "search_for_target"
    assert owned_intent == "search_for_target"
    assert owned_args == {"target_class": "ball"}
    assert owned_since == 123.0


def test_owned_intent_status_holds_acquire_until_lock(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {
        "brain": {"target_locked": False, "target_visible_recent": True},
        "perception": {"target_visible_now": True},
        "outcome": {},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 101.0)

    in_flight, transitioned, terminal_reason = runner._owned_intent_status(
        state=state,
        intent_name="acquire_target",
        owned_since_monotonic=100.0,
    )

    assert in_flight is True
    assert transitioned is False
    assert terminal_reason == ""


def test_owned_intent_status_keeps_search_owned_while_last_intent_is_search(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {
        "brain": {
            "target_locked": False,
            "search_active": False,
            "last_intent": "search_for_target",
            "last_feedback_text": "safe_stop: robot stopped",
        },
        "perception": {"target_visible_now": False},
        "outcome": {},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 110.0)

    in_flight, transitioned, terminal_reason = runner._owned_intent_status(
        state=state,
        intent_name="search_for_target",
        owned_since_monotonic=100.0,
    )

    assert in_flight is True
    assert transitioned is False
    assert terminal_reason == ""


def test_owned_intent_status_keeps_search_owned_while_centering(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {
        "brain": {
            "target_locked": False,
            "search_active": True,
            "search_state": "centering",
            "last_intent": "search_for_target",
        },
        "perception": {"target_visible_now": True},
        "outcome": {},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 110.0)

    in_flight, transitioned, terminal_reason = runner._owned_intent_status(
        state=state,
        intent_name="search_for_target",
        owned_since_monotonic=100.0,
    )

    assert in_flight is True
    assert transitioned is False
    assert terminal_reason == ""


def test_owned_intent_status_keeps_search_owned_during_startup_grace(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {
        "brain": {
            "target_locked": False,
            "search_active": False,
            "last_intent": "safe_stop",
            "last_feedback_text": "safe_stop: robot stopped",
        },
        "perception": {"target_visible_now": False},
        "outcome": {},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 103.5)

    in_flight, transitioned, terminal_reason = runner._owned_intent_status(
        state=state,
        intent_name="search_for_target",
        owned_since_monotonic=100.0,
    )

    assert in_flight is True
    assert transitioned is False
    assert terminal_reason == ""


def test_owned_intent_status_keeps_search_owned_until_mission_search_timeout(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {
        "brain": {
            "target_locked": False,
            "search_active": False,
            "last_intent": "safe_stop",
            "last_feedback_text": "safe_stop: robot stopped",
        },
        "perception": {"target_visible_now": False},
        "outcome": {},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 118.0)

    in_flight, transitioned, terminal_reason = runner._owned_intent_status(
        state=state,
        intent_name="search_for_target",
        owned_since_monotonic=100.0,
    )

    assert in_flight is True
    assert transitioned is False
    assert terminal_reason == ""


def test_owned_intent_status_transitions_plan_after_goal_activity(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {
        "brain": {"goal_in_progress": True},
        "perception": {},
        "outcome": {"nav_goal_recent": True},
    }

    monkeypatch.setattr(visit_runner.time, "monotonic", lambda: 105.0)

    in_flight, transitioned, terminal_reason = runner._owned_intent_status(
        state=state,
        intent_name="plan_to_target",
        owned_since_monotonic=100.0,
    )

    assert in_flight is False
    assert transitioned is True
    assert terminal_reason == ""


# --- 409 ownership guard tests ---


def test_executor_confirms_search_when_search_is_active(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {"brain": {"search_active": True, "last_intent": "search_for_target"}}
    assert runner._executor_confirms_intent(state, "search_for_target") is True


def test_executor_rejects_search_when_different_intent_is_active(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {"brain": {"search_active": False, "last_intent": "acquire_target"}}
    assert runner._executor_confirms_intent(state, "search_for_target") is False


def test_executor_confirms_acquire_when_last_intent_matches(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {"brain": {"last_intent": "acquire_target", "target_locked": False}}
    assert runner._executor_confirms_intent(state, "acquire_target") is True


def test_executor_rejects_acquire_when_already_locked(monkeypatch):
    runner = _make_runner(monkeypatch)
    state = {"brain": {"last_intent": "acquire_target", "target_locked": True}}
    assert runner._executor_confirms_intent(state, "acquire_target") is False
