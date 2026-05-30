from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gather_ai_push_coast_helpers import decide_ai_push_coast_handoff  # noqa: E402


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
