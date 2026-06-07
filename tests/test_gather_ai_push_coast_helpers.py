from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gather_ai_push_coast_helpers import decide_ai_push_coast_handoff  # noqa: E402
from gather_ai_push_coast_helpers import compute_fetch_push_readiness_setup_command  # noqa: E402
from gather_ai_push_coast_helpers import evaluate_fetch_push_readiness  # noqa: E402


def test_push_readiness_accepts_centered_behind_ball_setup():
    gate = evaluate_fetch_push_readiness(
        robot_pose={"x": 0.65, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert gate["pass"] is True
    assert gate["reason"] == "push_ready"
    assert gate["flags"] == []
    assert gate["relative_errors"]["robot_standoff_m"] == 0.35


def test_push_readiness_rejects_lateral_and_yaw_setup_error():
    gate = evaluate_fetch_push_readiness(
        robot_pose={"x": 0.65, "y": 0.22, "yaw": 0.5},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert gate["pass"] is False
    assert gate["reason"] == "push_readiness_gate_failed"
    assert "robot_lateral_error_out_of_bounds" in gate["flags"]
    assert "robot_yaw_error_out_of_bounds" in gate["flags"]
    assert gate["stage_label"] == "setup"


def test_push_readiness_rejects_robot_ahead_of_ball():
    gate = evaluate_fetch_push_readiness(
        robot_pose={"x": 1.08, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert gate["pass"] is False
    assert "robot_not_behind_ball" in gate["flags"]


def test_push_readiness_accepts_near_delivery_margin_when_geometry_is_ready():
    gate = evaluate_fetch_push_readiness(
        robot_pose={"x": 0.41931, "y": -0.073598, "yaw": -0.004888},
        ball_pose={"x": 0.649039, "y": -0.100751, "z": 0.021336},
        fetch_pose_world={"x": 0.95, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        max_standoff_m=0.58,
    )

    assert gate["pass"] is True
    assert gate["reason"] == "push_ready"
    assert "ball_already_at_delivery_margin" in gate["flags"]
    assert gate["blocking_flags"] == []


def test_push_readiness_near_delivery_margin_keeps_setup_blockers():
    gate = evaluate_fetch_push_readiness(
        robot_pose={"x": 0.064352, "y": -0.016306, "yaw": 0.120132},
        ball_pose={"x": 0.6266, "y": -0.121157, "z": 0.021336},
        fetch_pose_world={"x": 0.95, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        max_standoff_m=0.58,
    )

    assert gate["pass"] is False
    assert "robot_lateral_error_out_of_bounds" in gate["blocking_flags"]
    assert gate["stage_label"] == "setup"


def test_push_readiness_accepts_contact_buffer_repush_standoff():
    gate = evaluate_fetch_push_readiness(
        robot_pose={"x": 0.198343, "y": 0.079393, "yaw": 0.060575},
        ball_pose={"x": 0.367173, "y": 0.072689, "z": 0.021336},
        fetch_pose_world={"x": 0.95, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert gate["pass"] is True
    assert gate["blocking_flags"] == []
    assert gate["relative_errors"]["robot_standoff_m"] >= 0.10


def test_push_readiness_setup_command_backs_off_when_too_close():
    command = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.93, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert command is not None
    assert command.mode == "push_readiness_backoff"
    assert command.linear_x < 0.0
    assert command.angular_z == 0.0


def test_push_readiness_setup_command_yaw_aligns_before_push():
    command = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.76, "y": 0.0, "yaw": 0.65},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert command is not None
    assert command.mode == "push_readiness_yaw_align"
    assert command.linear_x == 0.0
    assert command.angular_z < 0.0


def test_push_readiness_setup_command_holds_forward_motion_near_minimum_standoff():
    command = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.865, "y": 0.223, "yaw": -0.57},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert command is not None
    assert command.linear_x <= 0.0
    assert command.angular_z > 0.0


def test_push_readiness_setup_command_prioritizes_large_lateral_recenter_arc():
    command = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.50, "y": 0.30, "yaw": -0.25},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert command is not None
    assert command.mode == "push_readiness_lateral_align"
    assert 0.05 <= command.linear_x <= 0.056
    assert command.angular_z <= -0.40


def test_push_readiness_setup_command_large_lateral_error_overrides_yaw_only():
    command = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.50, "y": 0.30, "yaw": -0.52},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert command is not None
    assert command.mode == "push_readiness_lateral_align"
    assert command.linear_x > 0.0


def test_push_readiness_setup_command_recenter_arc_is_symmetric():
    plus = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.50, "y": 0.30, "yaw": 0.0},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )
    minus = compute_fetch_push_readiness_setup_command(
        robot_pose={"x": 0.50, "y": -0.30, "yaw": 0.0},
        ball_pose={"x": 1.0, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.6, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
    )

    assert plus is not None
    assert minus is not None
    assert plus.angular_z == -minus.angular_z
    assert plus.linear_x == minus.linear_x


def test_shadow_decision_stays_with_nav2_before_corridor_attempt():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.2, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.6, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.0, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_attempted=False,
        distance_to_fetch_pose_m=0.4,
        closest_approach_distance_m=0.4,
        mode="shadow",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "stay_with_nav2"
    assert decision["ai_push_coast_guard"]["accepted"] is False
    assert "shadow_mode" in decision["ai_push_coast_guard"]["reasons"]
    assert "ai_push_coast_latency_ms" in decision
    assert decision["ai_push_coast_shadow"]["stage_classification"]["primary_stage"] == "unknown"


def test_guarded_live_terminal_repush_accepts_bounded_stop_short():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.45, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.72, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_corridor_push={"dispatch_status": "goal_finished", "success": True},
        nav2_attempted=True,
        terminal_correction_attempted=False,
        distance_to_fetch_pose_m=0.4,
        closest_approach_distance_m=0.4,
        latest_still_s=0.6,
        ball_moved_since_fetch=True,
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is True
    assert decision["ai_push_coast_guard"]["deterministic_routine"] == "object_centric_fetch_to_pose"
    assert decision["ai_push_coast_shadow"]["trajectory"]["predicted_closest_approach_m"] < 0.4
    assert "terminal_arrival" in decision["ai_push_coast_shadow"]["input_digest"]["stage_labels"]


def test_guarded_live_terminal_repush_accepts_nav2_settled_near_contract_miss():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.43, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.599235, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_corridor_push={
            "dispatch_status": "goal_finished",
            "success": False,
            "first_contact_confirmed": True,
        },
        nav2_attempted=True,
        terminal_correction_attempted=False,
        distance_to_fetch_pose_m=0.520765,
        closest_approach_distance_m=0.520765,
        latest_still_s=None,
        terminal_settled_after_nav2=True,
        ball_moved_since_fetch=True,
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is True
    assert "ball_not_settled_for_terminal_correction" not in decision["ai_push_coast_guard"]["reasons"]
    assert "predicted_terminal_correction_not_sufficient" not in decision["ai_push_coast_guard"]["reasons"]
    assert decision["ai_push_coast_shadow"]["input_digest"]["terminal_settled_after_nav2"] is True


def test_guarded_live_vetoes_second_terminal_correction():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.45, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.72, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_attempted=True,
        terminal_correction_attempted=True,
        distance_to_fetch_pose_m=0.4,
        closest_approach_distance_m=0.4,
        latest_still_s=0.6,
        ball_moved_since_fetch=True,
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "abort_reaim"
    assert decision["ai_push_coast_guard"]["accepted"] is False
    assert "terminal_correction_budget_exhausted" in decision["ai_push_coast_guard"]["reasons"]
    assert "terminal_correction" in decision["ai_push_coast_proposal"]["stage_classification"]["stage_labels"]


def test_shadow_stage_classification_uses_contact_flags_and_terminal_reason():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.35, "y": 0.08, "yaw": 0.0},
        ball_pose={"x": 0.72, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_attempted=True,
        distance_to_fetch_pose_m=0.451645,
        closest_approach_distance_m=0.451645,
        approach_contact_metrics={
            "stable_contact_approach_pass": False,
            "flags": [
                "pre_contact_lateral_error",
                "ball_lateral_knock_away",
                "contact_trajectory_angle_error",
            ],
        },
        shot_outcome={"reason": "missed_delivery_radius_after_fetch_to_pose_ball_stopped_short"},
        mode="shadow",
    )

    stage = decision["ai_push_coast_shadow"]["stage_classification"]
    assert stage["primary_stage"] == "setup"
    assert stage["stage_labels"] == ["setup", "first_contact", "push_coast", "terminal_arrival"]
    assert stage["contact_quality_flags"] == [
        "pre_contact_lateral_error",
        "ball_lateral_knock_away",
        "contact_trajectory_angle_error",
    ]


def test_guarded_live_rejects_setup_stage_recenter():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.45, "y": 0.35, "yaw": 0.0},
        ball_pose={"x": 0.72, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_attempted=True,
        distance_to_fetch_pose_m=0.4,
        closest_approach_distance_m=0.4,
        latest_still_s=0.6,
        ball_moved_since_fetch=True,
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "recenter_right"
    assert decision["ai_push_coast_guard"]["accepted"] is False
    assert "maneuver_recenter_right_not_terminal_live" in decision["ai_push_coast_guard"]["reasons"]
    assert "stage_setup_not_live" in decision["ai_push_coast_guard"]["reasons"]


def test_guarded_live_requires_observed_object_motion():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.45, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.72, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_attempted=True,
        distance_to_fetch_pose_m=0.4,
        closest_approach_distance_m=0.4,
        latest_still_s=0.6,
        ball_moved_since_fetch=False,
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is False
    assert "object_motion_not_observed" in decision["ai_push_coast_guard"]["reasons"]


def test_guarded_live_rejects_capture_entry_timeout_stage():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.45, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.72, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_attempted=True,
        distance_to_fetch_pose_m=0.4,
        closest_approach_distance_m=0.4,
        latest_still_s=0.6,
        ball_moved_since_fetch=True,
        shot_outcome={"reason": "capture_entry_timeout"},
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is False
    assert "stage_setup_not_live" in decision["ai_push_coast_guard"]["reasons"]


def test_guarded_live_accepts_terminal_repush_after_capture_warning_with_confirmed_motion():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.43, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.599235, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_corridor_push={
            "dispatch_status": "goal_finished",
            "success": False,
            "first_contact_confirmed": True,
        },
        nav2_attempted=True,
        terminal_correction_attempted=False,
        distance_to_fetch_pose_m=0.520765,
        closest_approach_distance_m=0.520765,
        terminal_settled_after_nav2=True,
        ball_moved_since_fetch=True,
        approach_contact_metrics={
            "stable_contact_approach_pass": False,
            "flags": ["capture_yaw_watch", "capture_yaw_sign_crossing_watch"],
        },
        capture_geometry_gate={
            "pass": False,
            "flags": ["capture_yaw_watch", "capture_yaw_sign_crossing_watch"],
            "capture_yaw_travel_deg": 81.0,
            "capture_yaw_span_deg": 45.0,
            "capture_yaw_sign_crossing_count": 2,
        },
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is True
    assert "capture_geometry_gate_failed" not in decision["ai_push_coast_guard"]["reasons"]
    assert "stage_setup_not_live" not in decision["ai_push_coast_guard"]["reasons"]
    assert decision["ai_push_coast_shadow"]["stage_classification"]["primary_stage"] == "setup"
    assert decision["ai_push_coast_shadow"]["input_digest"]["capture_geometry_gate_pass"] is False


def test_guarded_live_terminal_repush_accepts_contact_quality_flags_after_measured_motion():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.62, "y": 0.055, "yaw": 0.0},
        ball_pose={"x": 0.73, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_corridor_push={"dispatch_status": "goal_finished", "success": True},
        nav2_attempted=True,
        terminal_correction_attempted=False,
        distance_to_fetch_pose_m=0.390543,
        closest_approach_distance_m=0.390543,
        terminal_settled_after_nav2=True,
        ball_moved_since_fetch=True,
        approach_contact_metrics={
            "stable_contact_approach_pass": False,
            "flags": ["ball_lateral_knock_away", "contact_trajectory_angle_error"],
        },
        shot_outcome={"reason": "missed_delivery_radius"},
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is True
    assert "stage_first_contact_not_live" not in decision["ai_push_coast_guard"]["reasons"]
    assert "stage_push_coast_not_live" not in decision["ai_push_coast_guard"]["reasons"]
    assert decision["ai_push_coast_shadow"]["stage_classification"]["stage_labels"] == [
        "first_contact",
        "push_coast",
        "terminal_arrival",
    ]


def test_guarded_live_rejects_terminal_repush_when_setup_flags_are_current_blockers():
    decision = decide_ai_push_coast_handoff(
        robot_pose={"x": 0.43, "y": 0.0, "yaw": 0.0},
        ball_pose={"x": 0.599235, "y": 0.0, "z": 0.05},
        fetch_pose_world={"x": 1.12, "y": 0.0, "z": 0.001},
        delivery_radius_m=0.3,
        nav2_corridor_push={
            "dispatch_status": "goal_finished",
            "success": False,
            "first_contact_confirmed": True,
        },
        nav2_attempted=True,
        terminal_correction_attempted=False,
        distance_to_fetch_pose_m=0.520765,
        closest_approach_distance_m=0.520765,
        terminal_settled_after_nav2=True,
        ball_moved_since_fetch=True,
        approach_contact_metrics={
            "stable_contact_approach_pass": False,
            "flags": ["pre_contact_lateral_error", "capture_yaw_watch"],
        },
        capture_geometry_gate={
            "pass": False,
            "flags": ["capture_yaw_watch", "capture_yaw_sign_crossing_watch"],
            "capture_yaw_travel_deg": 140.0,
            "capture_yaw_span_deg": 70.0,
            "capture_yaw_sign_crossing_count": 2,
        },
        mode="guarded_live",
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is False
    assert "capture_geometry_gate_failed" in decision["ai_push_coast_guard"]["reasons"]
    assert "stage_setup_not_live" in decision["ai_push_coast_guard"]["reasons"]
