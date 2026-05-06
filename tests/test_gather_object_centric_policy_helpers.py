from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_object_centric_policy_helpers import (  # noqa: E402
    OBJECT_CENTRIC_GOAL_SIDE_ORBIT_MIN_BALL_DISTANCE_M,
    OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS,
    OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS,
    OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS,
    PlaceControlCommand,
    decide_object_centric_gather_command,
)


def test_policy_returns_pre_stage_ready_at_measured_handoff_pose():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}
    robot_pose = {"x": 0.1, "y": 0.0, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.active is True
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_ready"
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] == -0.9
    assert decision.diagnostics["guard_rejection_reason"] == ""


def test_policy_goal_side_far_from_ball_orbits_toward_behind_port():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_pre_stage_goal_side_orbit"
    assert decision.command.linear_x > 0.0
    assert decision.command.target_speed_scale <= 0.75
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] > 0.0


def test_policy_goal_side_near_ball_keeps_reverse_clearance_escape():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 4.9, "y": 0.0, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_pre_stage_escape_goal_side"
    assert decision.command.linear_x < 0.0


def test_policy_goal_side_near_ball_with_safe_lateral_offset_keeps_orbit():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 4.67, "y": -0.50, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_pre_stage_goal_side_orbit"
    assert decision.command.linear_x > 0.0
    assert (
        decision.diagnostics["capture_snapshot"]["distance_m"]
        < OBJECT_CENTRIC_GOAL_SIDE_ORBIT_MIN_BALL_DISTANCE_M
    )
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] >= 0.42


def test_policy_goal_side_close_ball_with_large_lateral_offset_keeps_orbit():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 4.75, "y": -0.54, "yaw": -0.19}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_pre_stage_goal_side_orbit"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["capture_snapshot"]["distance_m"] < 0.90
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] >= 0.52


def test_policy_goal_side_very_close_ball_requires_wide_lateral_offset_for_orbit():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.12, "y": -0.61, "yaw": 0.16}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_pre_stage_goal_side_orbit"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["capture_snapshot"]["distance_m"] < 0.70
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] >= 0.60


def test_policy_close_pre_stage_pose_settles_push_line_yaw_before_handoff():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 6.136, "y": -0.059, "yaw": math.radians(57.5)}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert abs(decision.command.angular_z) > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.55
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_early_close_pre_stage_pose_starts_yaw_settle_before_timeout_band():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.948132, "y": -0.136165, "yaw": 1.001381}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert abs(decision.command.angular_z) > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_near_close_pre_stage_pose_commits_to_yaw_settle_before_turn_oscillation():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.911839, "y": -0.145406, "yaw": 1.072802}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert abs(decision.command.angular_z) >= 0.12
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.46
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_near_close_yaw_settle_does_not_smooth_against_live_turn_sign():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.912485, "y": -0.151344, "yaw": 1.030145}
    previous = PlaceControlCommand(
        mode="object_pre_stage_traverse",
        linear_x=0.04,
        angular_z=-0.224136,
        target_speed_scale=0.75,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert abs(decision.command.angular_z) >= 0.12
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_deep_close_pre_stage_pose_settles_yaw_inside_close_in_band():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 6.06265, "y": -0.191109, "yaw": 1.341382}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.35
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.55
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_wide_close_pre_stage_pose_settles_yaw_before_late_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 6.020522, "y": -0.20968, "yaw": 1.169332}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.55
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_late_close_pre_stage_pose_starts_yaw_settle_one_tick_before_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.986644, "y": -0.257485, "yaw": 0.92759}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.26
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.53
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_outer_close_pre_stage_pose_settles_yaw_before_timeout_retry_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.97738, "y": -0.193106, "yaw": 1.134449}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_close_pre_stage_yaw_reverse_starts_before_timeout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 5.927344, "y": -0.136523, "yaw": 2.052325}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.46
    assert 35.0 < decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 75.0


def test_policy_close_pre_stage_yaw_reverse_starts_from_near_zero_target_x():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 5.953678, "y": -0.150874, "yaw": 1.918024}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_reverse_to_handoff"
    assert decision.command.linear_x < -0.055
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50
    assert 65.0 < decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 75.0


def test_policy_close_pre_stage_yaw_reverse_starts_at_latest_timing_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 5.923898, "y": -0.123942, "yaw": 1.778081}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["target_x_m"] <= 0.04
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.46
    assert 75.0 < decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 90.0


def test_policy_close_pre_stage_pose_reverses_last_gap_after_yaw_settles():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.948132, "y": -0.136165, "yaw": 3.072987}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_reverse_to_handoff"
    assert decision.raw_command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50


def test_policy_near_close_pre_stage_pose_reverses_after_yaw_settles():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.911839, "y": -0.145406, "yaw": 2.792527}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_near_close_reverse_to_handoff"
    assert decision.raw_command.linear_x < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.46


def test_policy_near_close_reverse_does_not_smooth_first_live_reverse_step():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.914592, "y": -0.147942, "yaw": 2.780675}
    previous = PlaceControlCommand(
        mode="object_pre_stage_close_yaw_settle",
        linear_x=0.0,
        angular_z=0.717628,
        target_speed_scale=0.0,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_near_close_reverse_to_handoff"
    assert decision.command.linear_x == decision.raw_command.linear_x
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert decision.command.linear_x < -0.06
    assert decision.diagnostics["smoothing_applied"] is False


def test_policy_wide_close_pre_stage_pose_reverses_after_yaw_settles():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 6.020522, "y": -0.20968, "yaw": 2.792527}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_wide_close_reverse_to_handoff"
    assert decision.raw_command.linear_x < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.55


def test_policy_outer_close_pre_stage_pose_reverses_after_yaw_settles():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.97738, "y": -0.193106, "yaw": 2.792527}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_outer_close_reverse_to_handoff"
    assert decision.raw_command.linear_x < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50


def test_policy_late_close_pre_stage_pose_reverses_instead_of_zero_turn_loop():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 6.036482, "y": -0.228467, "yaw": 3.094729}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_late_close_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.47
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] > 0.22
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.26
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.53
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 35.0


def test_policy_outer_close_reverse_recovers_latest_fresh_timeout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.968, "y": -0.172, "yaw": -2.945}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_outer_close_reverse_to_handoff"
    assert decision.raw_command.linear_x < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 35.0


def test_policy_outer_close_reverse_uses_decisive_speed_at_latest_pre_stage_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.979, "y": -0.167, "yaw": 3.060}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_outer_close_reverse_to_handoff"
    assert decision.raw_command.linear_x <= -0.10
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.43
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.22
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.50
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 35.0


def test_policy_near_wide_close_yaw_settle_starts_at_latest_fresh_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.910259, "y": -0.174449, "yaw": 0.883673}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.48
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.46
    assert abs(decision.diagnostics["behind_ball"]["robot_lateral_signed_m"]) <= 0.18
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) > 35.0


def test_policy_near_wide_yaw_reverse_starts_before_final_timeout_tick():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.915344, "y": -0.166998, "yaw": 2.292822}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_near_wide_yaw_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.48
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.46
    assert abs(decision.diagnostics["behind_ball"]["robot_lateral_signed_m"]) <= 0.18
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) > 35.0
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) <= 60.0


def test_policy_transition_close_yaw_settle_starts_before_latest_goal_side_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.890296, "y": -0.190439, "yaw": 0.738384}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.50
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.44
    assert abs(decision.diagnostics["behind_ball"]["robot_lateral_signed_m"]) <= 0.20
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) > 35.0


def test_policy_transition_close_yaw_reverse_starts_from_latest_safe_pose():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.890296, "y": -0.190439, "yaw": 2.292822}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_transition_close_yaw_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.50
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.44
    assert abs(decision.diagnostics["behind_ball"]["robot_lateral_signed_m"]) <= 0.20
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) > 35.0
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) <= 60.0


def test_policy_transition_close_yaw_reverse_starts_at_latest_near_zero_target_x():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.925717, "y": -0.187602, "yaw": 2.077483}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_transition_close_yaw_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.50
    assert decision.diagnostics["behind_ball"]["target_x_m"] <= 0.04
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.44
    assert abs(decision.diagnostics["behind_ball"]["robot_lateral_signed_m"]) <= 0.20
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) > 35.0
    assert abs(decision.diagnostics["behind_ball"]["yaw_error_deg"]) <= 65.0


def test_policy_near_wide_close_reverse_can_finish_after_yaw_settles():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.910259, "y": -0.174449, "yaw": 2.792527}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_pre_stage_near_wide_close_reverse_to_handoff"
    assert decision.command.linear_x < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.35
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.48
    assert abs(decision.diagnostics["behind_ball"]["robot_lateral_signed_m"]) <= 0.18


def test_policy_close_stage_pose_settles_push_line_yaw_before_capture_entry():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.952377, "y": -0.042184, "yaw": math.radians(148.0)}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.14
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.10
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.48
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 20.0


def test_policy_near_close_stage_pose_starts_yaw_settle_before_plus45_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261}
    robot_pose = {"x": 4.879861, "y": 2.653546, "yaw": -1.235716}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="stage",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_stage_close_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.21
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.15
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.56
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 20.0


def test_policy_stage_close_nudges_latest_two_mm_radius_miss_into_ready():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 6.038, "y": -0.146, "yaw": 3.073}
    previous = PlaceControlCommand(
        mode="object_stage_turn_to_behind",
        linear_x=0.0,
        angular_z=0.6,
        target_speed_scale=0.0,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="stage",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_stage_close_nudge_to_ready"
    assert decision.raw_command.linear_x > 0.0
    assert decision.command.linear_x == decision.raw_command.linear_x
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["behind_ball"]["target_distance_m"] > 0.18
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.23
    assert decision.diagnostics["behind_ball"]["robot_lateral_error_m"] <= 0.16
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] <= -0.56
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] <= 35.0


def test_policy_capture_entry_close_does_not_smooth_against_live_lateral_sign():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.945102, "y": -0.058705, "yaw": -2.919554}
    previous = PlaceControlCommand(
        mode="object_capture_entry_close",
        linear_x=0.025,
        angular_z=0.6,
        target_speed_scale=0.55,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture_entry",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_entry_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.raw_command.angular_z < 0.0
    assert decision.command.angular_z < 0.0
    assert abs(decision.command.angular_z) <= OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.26


def test_policy_capture_entry_holds_after_ready_blip_instead_of_reclosing():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.935217, "y": -0.107312, "yaw": 2.573024}
    previous = PlaceControlCommand(
        mode="capture_entry_ready",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.0,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture_entry",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_entry_ready_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["behind_ball"]["target_distance_m"] <= 0.28


def test_policy_capture_command_is_object_centric_and_bounded():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.10}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_capture_push"
    assert abs(decision.command.linear_x) <= OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS
    assert abs(decision.command.angular_z) <= OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS
    assert decision.diagnostics["push_line"]["ball_to_zone_distance_m"] > 0.0
    assert decision.diagnostics["ball_zone_progress"]["distance_m"] > 0.0


def test_policy_capture_recenters_wide_local_ball_before_place_loss_timeout():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.486433, "y": 0.416483, "z": 0.05}
    ball_pose = {"x": 4.486433, "y": 0.416483, "z": 0.05}
    robot_pose = {"x": 4.992832, "y": 0.150434, "yaw": -2.845231}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.62
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.24
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.50
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_capture_entry_recenters_close_lateral_mouth_error():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.947554, "y": -0.098633, "yaw": 2.556716}
    previous = PlaceControlCommand(
        mode="object_capture_entry_close",
        linear_x=0.025,
        angular_z=0.578431,
        target_speed_scale=0.55,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture_entry",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_entry_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert abs(decision.command.angular_z) >= 0.12
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.62
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.05


def test_policy_capture_close_yaw_settle_holds_near_seated_live_pose():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.339553, "y": -0.203181}
    robot_pose = {"x": 5.560562, "y": 0.02417, "yaw": -2.467577}
    previous = PlaceControlCommand(
        mode="object_capture_push",
        linear_x=0.065,
        angular_z=0.8,
        target_speed_scale=0.75,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert abs(decision.command.angular_z) > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.36
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_capture_close_yaw_settle_continues_after_first_live_settle_step():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.373613, "y": 0.156017}
    robot_pose = {"x": 5.645472, "y": -0.088877, "yaw": 2.272719}
    previous = PlaceControlCommand(
        mode="object_capture_close_yaw_settle",
        linear_x=0.0,
        angular_z=0.498154,
        target_speed_scale=0.0,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.46
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_capture_close_yaw_settle_holds_late_recapture_before_rollout():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.296844, "y": 0.317001}
    robot_pose = {"x": 5.585366, "y": -0.036934, "yaw": 2.516666}
    previous = PlaceControlCommand(
        mode="object_capture_push",
        linear_x=0.08,
        angular_z=-0.092095,
        target_speed_scale=0.75,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.46
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 35.0


def test_policy_capture_close_yaw_settle_holds_live_capture_mouth_before_first_contact():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 6.036625, "y": -0.127944, "yaw": 2.821123}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.62
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 12.0


def test_policy_capture_close_yaw_settle_before_place_at_first_contact_misalignment():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 5.780432, "y": -0.095608, "yaw": 2.711446}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.46
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert 20.0 < decision.diagnostics["behind_ball"]["yaw_error_deg"] < 35.0


def test_policy_capture_close_yaw_settle_before_secure_handoff_at_latest_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 5.736081, "y": -0.066102, "yaw": 2.894863}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.02
    assert 12.0 < decision.diagnostics["behind_ball"]["yaw_error_deg"] < 20.0


def test_policy_capture_close_yaw_settle_keeps_latest_secure_zero_boundary_from_place_handoff():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 5.731545, "y": -0.079249, "yaw": 2.811904}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_close_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.02
    assert 12.0 < decision.diagnostics["behind_ball"]["yaw_error_deg"] < 20.0


def test_policy_capture_holds_when_place_loss_recapture_starts_inside_zone():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.415264, "y": 0.027782, "z": 0.05}
    ball_pose = {"x": 2.388145, "y": 0.028296, "z": 0.05}
    robot_pose = {"x": 3.579527, "y": 0.00103, "yaw": -3.11493}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_zone_entry_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert abs(decision.command.angular_z) <= 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_capture_holds_when_place_loss_recapture_starts_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.192000, "y": 0.340000, "z": 0.05}
    ball_pose = {"x": 2.154000, "y": 0.347000, "z": 0.05}
    robot_pose = {"x": 4.128000, "y": -0.034000, "yaw": -1.983000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_zone_entry_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.55
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_capture_holds_latest_zero_retrieval_edge_instead_of_repush():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.048, "y": -0.389, "z": 0.05}
    ball_pose = {"x": 2.017, "y": -0.396, "z": 0.05}
    robot_pose = {"x": 3.804, "y": -0.014, "yaw": 2.508}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_zone_entry_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.82


def test_policy_capture_holds_latest_zero_retrieval_edge_after_center_exit():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 1.670, "y": 0.069, "z": 0.05}
    ball_pose = {"x": 1.635, "y": 0.071, "z": 0.05}
    robot_pose = {"x": 3.851, "y": -0.064, "yaw": -3.126}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_zone_entry_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.82


def test_policy_capture_seat_does_not_smooth_stale_turn_at_live_secure_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0}
    robot_pose = {"x": 5.783369, "y": -0.036654, "yaw": 3.09193}
    previous = PlaceControlCommand(
        mode="object_capture_push",
        linear_x=0.065,
        angular_z=0.628937,
        target_speed_scale=0.75,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_capture_seat"
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.03


def test_policy_place_settles_secure_far_zone_yaw_before_pushing():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.556202, "y": 2.117243}
    robot_pose = {"x": 4.69418, "y": 2.378654, "yaw": -1.991557}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_yaw_settle"
    assert decision.raw_command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_late_secure_ball_moving_before_timeout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.70676, "y": -0.360501}
    robot_pose = {"x": 3.932078, "y": -0.30149, "yaw": -3.111639}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x >= 0.07
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_recenters_far_zone_line_before_secure_ball_rolls_diagonal():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.182435, "y": -0.129779, "z": 0.05}
    ball_pose = {"x": 5.147644, "y": -0.146782, "z": 0.05}
    robot_pose = {"x": 5.430798, "y": -0.060672, "yaw": -3.002806}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_far_line_recenter_active_after_high_motion_secure_roll():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.184, "y": -0.050, "z": 0.05}
    ball_pose = {"x": 5.082, "y": -0.066, "z": 0.05}
    robot_pose = {"x": 5.398, "y": -0.055, "yaw": -3.102}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["ball_motion_m"] > 0.05
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_far_line_recenter_uses_world_lateral_on_latest_zero_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.933483, "y": -0.134286, "z": 0.05}
    ball_pose = {"x": 4.899416, "y": -0.145516, "z": 0.05}
    robot_pose = {"x": 5.146427, "y": -0.068133, "yaw": -2.998515}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5
    assert ball_pose["y"] - zone.world_y < -0.14


def test_policy_place_bleeds_forward_push_on_growing_captured_world_lateral_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.359, "y": -0.072, "z": 0.05}
    ball_pose = {"x": 5.332, "y": -0.094, "z": 0.05}
    robot_pose = {"x": 5.563, "y": -0.047, "yaw": -3.122}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert abs(ball_pose["y"] - zone.world_y) > abs(previous_ball_pose["y"] - zone.world_y)
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_bleeding_on_stale_captured_world_lateral_sample():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.272, "y": -0.089, "z": 0.05}
    ball_pose = {"x": 5.272, "y": -0.089, "z": 0.05}
    robot_pose = {"x": 5.457, "y": -0.047, "yaw": 3.116}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.12
    assert abs(ball_pose["y"] - zone.world_y) >= 0.065
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_bleeds_recapture_keepup_on_growing_world_lateral_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.854, "y": -0.088, "z": 0.05}
    ball_pose = {"x": 4.806, "y": -0.096, "z": 0.05}
    robot_pose = {"x": 5.185, "y": -0.047, "yaw": -3.109}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.12
    assert abs(ball_pose["y"] - zone.world_y) > abs(previous_ball_pose["y"] - zone.world_y)
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.0


def test_policy_place_keeps_straight_push_on_tiny_captured_diagonal_roll():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.432000, "y": -0.010000, "z": 0.05}
    ball_pose = {"x": 5.398000, "y": -0.033000, "z": 0.05}
    robot_pose = {"x": 5.660000, "y": -0.048000, "yaw": 3.057000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x >= 0.07
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.04
    assert abs(ball_pose["y"] - zone.world_y) < 0.05
    assert decision.diagnostics["ball_motion_m"] < 0.05
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_straight_push_on_modest_captured_lateral_roll():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.315000, "y": -0.092000, "z": 0.05}
    ball_pose = {"x": 5.276000, "y": -0.083000, "z": 0.05}
    robot_pose = {"x": 5.493000, "y": -0.043000, "yaw": -3.100000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x >= 0.07
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert abs(ball_pose["y"] - zone.world_y) < 0.10
    assert decision.diagnostics["ball_motion_m"] < 0.05
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_straight_push_on_latest_low_lateral_captured_far_line_artifact():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.268000, "y": -0.131000, "z": 0.05}
    ball_pose = {"x": 5.239000, "y": -0.114000, "z": 0.05}
    robot_pose = {"x": 5.462000, "y": -0.052000, "yaw": -3.058000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x >= 0.07
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.05
    assert abs(ball_pose["y"] - zone.world_y) < 0.14
    assert decision.diagnostics["ball_motion_m"] < 0.05
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_straight_recapture_on_latest_low_lateral_far_line_artifact():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.675000, "y": 0.065000, "z": 0.05}
    ball_pose = {"x": 4.637000, "y": 0.079000, "z": 0.05}
    robot_pose = {"x": 5.003000, "y": -0.038000, "yaw": 2.905000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x >= 0.06
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.05
    assert abs(ball_pose["y"] - zone.world_y) < 0.16
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.0


def test_policy_place_settles_yaw_before_far_drive_while_ball_is_seated():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.403833, "y": 0.057156}
    robot_pose = {"x": 5.656816, "y": -0.086838, "yaw": 2.56695}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_yaw_settle"
    assert decision.command.linear_x == 0.0
    assert 0.0 < decision.command.angular_z <= 0.55
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["behind_ball"]["yaw_error_deg"] > 18.0
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_far_recapture_corridor_driving():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.561107, "y": 1.918943}
    robot_pose = {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.raw_command.linear_x > 0.05
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_keeps_modest_far_recapture_when_ball_drifts_laterally():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.334499, "y": -0.087257}
    robot_pose = {"x": 5.633401, "y": -0.00185, "yaw": -3.117466}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.05
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_y_m"] > 0.055
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_recenters_far_recapture_when_lateral_drift_is_large():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.20407, "y": 0.165779}
    robot_pose = {"x": 5.5499, "y": -0.02795, "yaw": 3.049913}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.11
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.5


def test_policy_place_recenters_far_zone_line_after_recapture_edge_slip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.92867, "y": -0.2538, "z": 0.05}
    ball_pose = {"x": 4.894999, "y": -0.270255, "z": 0.05}
    robot_pose = {"x": 5.32373, "y": -0.082834, "yaw": -2.881434}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.target_speed_scale == 0.25
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.12
    assert decision.diagnostics["ball_motion_m"] > 0.03


def test_policy_place_far_keepup_uses_line_recenter_after_ball_rolls_ahead():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.325, "y": -0.222, "z": 0.05}
    ball_pose = {"x": 4.266, "y": -0.234, "z": 0.05}
    robot_pose = {"x": 5.102, "y": -0.077, "yaw": -2.928}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.025
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.85
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["ball_motion_m"] > 0.03


def test_policy_place_far_line_recenter_keeps_contact_on_latest_zero_world_lateral_slip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.987142, "y": -0.417010, "z": 0.05}
    ball_pose = {"x": 3.958357, "y": -0.423311, "z": 0.05}
    robot_pose = {"x": 4.814994, "y": -0.212049, "yaw": -2.429475}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["ball_motion_m"] > 0.025
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert ball_pose["y"] - zone.world_y < -0.30


def test_policy_place_far_line_keeps_contact_on_latest_zero_low_local_world_slip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.832182, "y": -0.207264, "z": 0.05}
    ball_pose = {"x": 4.803191, "y": -0.217022, "z": 0.05}
    robot_pose = {"x": 5.213472, "y": -0.070787, "yaw": -2.677740}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) < 0.10
    assert abs(ball_pose["y"] - zone.world_y) >= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.00


def test_policy_place_far_line_holds_latest_zero_stale_low_local_world_slip_sample():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.803191, "y": -0.217022, "z": 0.05}
    ball_pose = {"x": 4.803191, "y": -0.217022, "z": 0.05}
    robot_pose = {"x": 5.213472, "y": -0.070787, "yaw": -2.623000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(ball_pose["y"] - zone.world_y) >= 0.20


def test_policy_place_far_world_moderate_recenter_keeps_contact_on_latest_zero_rollout():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.749, "y": -0.235, "z": 0.05}
    ball_pose = {"x": 4.721, "y": -0.245, "z": 0.05}
    robot_pose = {"x": 5.188, "y": -0.086, "yaw": -2.594}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.70
    assert abs(ball_pose["y"] - zone.world_y) >= 0.24
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.00


def test_policy_place_keeps_up_when_far_recapture_ball_walks_forward():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.830995, "y": -0.566991}
    robot_pose = {"x": 5.504208, "y": -0.071273, "yaw": -2.656547}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x >= 0.06
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.14


def test_policy_place_preserves_keepup_near_recapture_edge_with_safe_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.851202, "y": -0.548933}
    robot_pose = {"x": 5.404268, "y": -0.105692, "yaw": -2.674277}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x >= 0.06
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.65
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.16
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 2.0


def test_policy_place_keeps_near_zone_recapture_under_object_centric_control():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.183476, "y": -0.376122}
    robot_pose = {"x": 4.023405, "y": -0.251181, "yaw": -3.066374}
    previous = PlaceControlCommand(
        mode="place_recapture",
        linear_x=0.014075,
        angular_z=-0.05,
        target_speed_scale=0.639765,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.025
    assert decision.command.angular_z == decision.raw_command.angular_z
    assert abs(decision.command.angular_z) >= 0.12
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_slows_latest_zero_straight_line_recapture_before_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.823801, "y": 0.012707, "z": 0.05}
    ball_pose = {"x": 3.780092, "y": 0.014187, "z": 0.05}
    robot_pose = {"x": 4.305226, "y": -0.011149, "yaw": 3.107924}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.025
    assert decision.command.target_speed_scale == 0.35
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.04
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.72
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_latest_zero_fast_centerline_far_rollout_before_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.632169, "y": -0.030639, "z": 0.05}
    ball_pose = {"x": 4.571371, "y": -0.028314, "z": 0.05}
    robot_pose = {"x": 4.998237, "y": 0.013698, "yaw": -3.104925}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.05
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.14
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.70


def test_policy_place_coasts_latest_zero_lower_motion_far_centerline_rollout():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.688474, "y": -0.004018, "z": 0.05}
    ball_pose = {"x": 4.647305, "y": 0.008750, "z": 0.05}
    robot_pose = {"x": 4.942696, "y": 0.013339, "yaw": 3.114503}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.040 <= decision.diagnostics["ball_motion_m"] <= 0.050
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.25 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.45
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.05
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.45 <= zone_margin_m <= 1.60


def test_policy_place_keeps_latest_zero_captured_gap_before_far_coast_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.701802, "y": -0.043917, "z": 0.05}
    ball_pose = {"x": 4.664488, "y": -0.060630, "z": 0.05}
    robot_pose = {"x": 5.035712, "y": 0.022386, "yaw": -3.064912}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.35 <= zone_margin_m <= 1.60


def test_policy_place_keeps_latest_zero_recapture_gap_before_far_coast_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.588353, "y": -0.094730, "z": 0.05}
    ball_pose = {"x": 4.550563, "y": -0.111656, "z": 0.05}
    robot_pose = {"x": 5.035712, "y": 0.022386, "yaw": 3.058828}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.35 <= zone_margin_m <= 1.60


def test_policy_place_keeps_latest_zero_captured_gap_at_far_coast_frontier():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.857325, "y": -0.049555, "z": 0.05}
    ball_pose = {"x": 4.817053, "y": -0.084840, "z": 0.05}
    robot_pose = {"x": 5.147602, "y": 0.018506, "yaw": -3.024389}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert 0.08 <= abs(ball_pose["y"] - zone.world_y) <= 0.18
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.60 <= zone_margin_m <= 1.70


def test_policy_place_keeps_latest_zero_recapture_gap_at_far_coast_frontier():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.776606, "y": -0.120278, "z": 0.05}
    ball_pose = {"x": 4.736160, "y": -0.155717, "z": 0.05}
    robot_pose = {"x": 5.147602, "y": 0.018506, "yaw": -3.032934}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert 0.14 <= abs(ball_pose["y"] - zone.world_y) <= 0.18
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.65


def test_policy_place_keeps_latest_zero_positive_captured_gap_before_far_bleed_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.145593, "y": 0.063133, "z": 0.05}
    ball_pose = {"x": 5.113248, "y": 0.081149, "z": 0.05}
    robot_pose = {"x": 5.430494, "y": -0.014828, "yaw": 3.049214}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert 0.05 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert 0.08 <= ball_pose["y"] - zone.world_y <= 0.18
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.90 <= zone_margin_m <= 2.00


def test_policy_place_keeps_latest_zero_positive_recapture_gap_before_far_bleed_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.081249, "y": 0.098972, "z": 0.05}
    ball_pose = {"x": 5.049250, "y": 0.116794, "z": 0.05}
    robot_pose = {"x": 5.405224, "y": -0.012971, "yaw": -3.105527}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert 0.05 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert 0.10 <= ball_pose["y"] - zone.world_y <= 0.18
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.85 <= zone_margin_m <= 1.95


def test_policy_place_keeps_latest_zero_positive_frontier_recapture_from_reversing_to_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.983936, "y": 0.153173, "z": 0.05}
    ball_pose = {"x": 4.950828, "y": 0.171613, "z": 0.05}
    robot_pose = {"x": 5.393864, "y": -0.014255, "yaw": 3.116903}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.42 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.52
    assert 0.16 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.22
    assert 0.16 <= ball_pose["y"] - zone.world_y <= 0.22
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.74 <= zone_margin_m <= 1.86


def test_policy_place_keeps_latest_zero_stale_positive_frontier_recapture_steering_edge_away():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.950828, "y": 0.171613, "z": 0.05}
    ball_pose = {"x": 4.950828, "y": 0.171613, "z": 0.05}
    robot_pose = {"x": 5.390101, "y": -0.013976, "yaw": 2.972343}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.42 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.52
    assert 0.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.22
    assert 0.16 <= ball_pose["y"] - zone.world_y <= 0.22
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.74 <= zone_margin_m <= 1.86


def test_policy_place_holds_latest_zero_positive_opposed_after_recapture_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.884683, "y": 0.208455, "z": 0.05}
    ball_pose = {"x": 4.850814, "y": 0.227320, "z": 0.05}
    robot_pose = {"x": 5.388669, "y": -0.014272, "yaw": -2.928526}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.060
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.58
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.34
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.72


def test_policy_place_holds_latest_zero_deeper_positive_opposed_after_recapture_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.783838, "y": 0.264624, "z": 0.05}
    ball_pose = {"x": 4.749553, "y": 0.283720, "z": 0.05}
    robot_pose = {"x": 5.383468, "y": -0.015347, "yaw": -2.724090}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.060
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.58
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.34
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.72


def test_policy_place_holds_latest_zero_low_motion_positive_recapture_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.093670, "y": 0.088517, "z": 0.05}
    ball_pose = {"x": 5.065083, "y": 0.104806, "z": 0.05}
    robot_pose = {"x": 5.397212, "y": -0.006849, "yaw": -3.125204}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.035
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.32 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.22
    assert 0.08 <= ball_pose["y"] - zone.world_y <= 0.20
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.75 <= zone_margin_m <= 1.95


def test_policy_place_holds_latest_zero_high_x_low_motion_positive_recapture_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.836633, "y": 0.234980, "z": 0.05}
    ball_pose = {"x": 4.808292, "y": 0.251129, "z": 0.05}
    robot_pose = {"x": 5.370789, "y": -0.006129, "yaw": 2.760908}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.035
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.68
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.30
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.60 <= zone_margin_m <= 1.70


def test_policy_place_holds_latest_zero_high_x_positive_opposed_after_recapture_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.779275, "y": 0.267663, "z": 0.05}
    ball_pose = {"x": 4.751609, "y": 0.283428, "z": 0.05}
    robot_pose = {"x": 5.370789, "y": -0.006129, "yaw": 3.102642}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.060
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.65
    assert 0.25 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.34
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.72


def test_policy_place_holds_latest_zero_mid_positive_recapture_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.747586, "y": 0.125330, "z": 0.05}
    ball_pose = {"x": 4.711560, "y": 0.140008, "z": 0.05}
    robot_pose = {"x": 5.213436, "y": 0.008667, "yaw": 3.118028}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.40 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.14
    assert 0.10 <= ball_pose["y"] - zone.world_y <= 0.16
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.50 <= zone_margin_m <= 1.65


def test_policy_place_holds_latest_zero_high_x_positive_recapture_before_reorient():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.454236, "y": 0.244850, "z": 0.05}
    ball_pose = {"x": 4.418055, "y": 0.259592, "z": 0.05}
    robot_pose = {"x": 5.213436, "y": 0.008667, "yaw": 2.951328}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.64 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.12
    assert 0.18 <= ball_pose["y"] - zone.world_y <= 0.28
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.20 <= zone_margin_m <= 1.45


def test_policy_place_holds_latest_zero_lower_margin_high_x_positive_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.418582, "y": 0.171673, "z": 0.05}
    ball_pose = {"x": 4.375669, "y": 0.185747, "z": 0.05}
    robot_pose = {"x": 5.069537, "y": 0.022389, "yaw": 2.978051}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.047
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.64 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.12
    assert 0.18 <= ball_pose["y"] - zone.world_y <= 0.28
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.15 <= zone_margin_m <= 1.45


def test_policy_place_holds_latest_zero_high_x_positive_edge_before_keepup_pulse():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.250287, "y": 0.226867, "z": 0.05}
    ball_pose = {"x": 4.207193, "y": 0.241001, "z": 0.05}
    robot_pose = {"x": 5.069537, "y": 0.022389, "yaw": 2.975463}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.040 <= decision.diagnostics["ball_motion_m"] <= 0.050
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.84 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.92
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.12
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.26
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.00 <= zone_margin_m <= 1.10


def test_policy_place_holds_latest_zero_terminal_positive_edge_before_reorient():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.827238, "y": 0.365612, "z": 0.05}
    ball_pose = {"x": 3.783418, "y": 0.379984, "z": 0.05}
    robot_pose = {"x": 5.069537, "y": 0.022389, "yaw": 1.222878}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.35 <= ball_pose["y"] - zone.world_y <= 0.52
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) >= 0.35
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.40 <= zone_margin_m <= 0.70


def test_policy_place_holds_latest_zero_terminal_positive_edge_before_wide_reel():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.658218, "y": 0.421045, "z": 0.05}
    ball_pose = {"x": 3.614217, "y": 0.435475, "z": 0.05}
    robot_pose = {"x": 5.069537, "y": 0.022389, "yaw": 1.926947}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.30 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.65
    assert 0.35 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.55
    assert 0.35 <= ball_pose["y"] - zone.world_y <= 0.52
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.40 <= zone_margin_m <= 0.70


def test_policy_place_holds_latest_zero_terminal_positive_edge_centered_before_push():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.527847, "y": 0.463802, "z": 0.05}
    ball_pose = {"x": 3.527847, "y": 0.463802, "z": 0.05}
    robot_pose = {"x": 5.062349, "y": 0.026219, "yaw": 2.886947}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.45 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.70
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.10
    assert 0.35 <= ball_pose["y"] - zone.world_y <= 0.52
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.40 <= zone_margin_m <= 0.70


def test_policy_place_holds_latest_zero_terminal_near_positive_edge_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.398383, "y": 0.506261, "z": 0.05}
    ball_pose = {"x": 3.354563, "y": 0.520633, "z": 0.05}
    robot_pose = {"x": 5.023079, "y": 0.022309, "yaw": -2.686914}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.040 <= decision.diagnostics["ball_motion_m"] <= 0.050
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.05 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert 1.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.30
    assert 0.50 <= ball_pose["y"] - zone.world_y <= 0.55
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.30 <= zone_margin_m <= 0.36


def test_policy_place_coasts_latest_zero_high_motion_captured_centerline_earlier():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.074168, "y": 0.025707, "z": 0.05}
    ball_pose = {"x": 5.014116, "y": 0.015989, "z": 0.05}
    robot_pose = {"x": 5.310829, "y": -0.010881, "yaw": -3.091142}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] >= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.14
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.85 <= zone_margin_m <= 1.95


def test_policy_place_coasts_latest_zero_high_motion_recapture_centerline_before_rollthrough():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.834089, "y": -0.013144, "z": 0.05}
    ball_pose = {"x": 4.774553, "y": -0.022778, "z": 0.05}
    robot_pose = {"x": 5.244027, "y": -0.014140, "yaw": 3.121933}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.055 <= decision.diagnostics["ball_motion_m"] <= 0.070
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.52
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert abs(ball_pose["y"] - zone.world_y) <= 0.05
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.50 <= zone_margin_m <= 1.75


def test_policy_place_coasts_latest_zero_negative_world_recapture_frontier():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.992680, "y": -0.037587, "z": 0.05}
    ball_pose = {"x": 4.942463, "y": -0.060065, "z": 0.05}
    robot_pose = {"x": 5.338688, "y": -0.013303, "yaw": 3.117902}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.055 <= decision.diagnostics["ball_motion_m"] <= 0.070
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.55
    assert 0.05 <= decision.diagnostics["capture_snapshot"]["ball_y_m"] <= 0.25
    assert -0.16 <= ball_pose["y"] - zone.world_y <= -0.055
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.85


def test_policy_place_keeps_coasting_latest_zero_negative_world_after_recapture_exit():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.891801, "y": -0.082742, "z": 0.05}
    ball_pose = {"x": 4.837242, "y": -0.107163, "z": 0.05}
    robot_pose = {"x": 5.289944, "y": -0.010968, "yaw": 3.038245}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.055 <= decision.diagnostics["ball_motion_m"] <= 0.070
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.55
    assert 0.05 <= decision.diagnostics["capture_snapshot"]["ball_y_m"] <= 0.25
    assert -0.16 <= ball_pose["y"] - zone.world_y <= -0.055
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.85


def test_policy_place_coasts_latest_zero_early_captured_far_centerline_rollout():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.996024, "y": -0.004648, "z": 0.05}
    ball_pose = {"x": 4.957320, "y": 0.007427, "z": 0.05}
    robot_pose = {"x": 5.159857, "y": 0.007650, "yaw": 2.982949}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.038 <= decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.18 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.25
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.05
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.75 <= zone_margin_m <= 1.85


def test_policy_place_coasts_latest_zero_stale_captured_far_centerline_sample():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.761598, "y": -0.029076, "z": 0.05}
    ball_pose = {"x": 4.761598, "y": -0.029076, "z": 0.05}
    robot_pose = {"x": 4.983624, "y": 0.015523, "yaw": -3.124412}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.18 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.55 <= zone_margin_m <= 1.65


def test_policy_place_coasts_latest_zero_captured_straight_line_before_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.823801, "y": -0.038981, "z": 0.05}
    ball_pose = {"x": 3.790543, "y": -0.039112, "z": 0.05}
    robot_pose = {"x": 4.118000, "y": -0.035000, "yaw": 3.139000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.04
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.72
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_deep_seated_zero_captured_straight_line_before_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.914000, "y": -0.047000, "z": 0.05}
    ball_pose = {"x": 3.879000, "y": -0.045000, "z": 0.05}
    robot_pose = {"x": 4.039000, "y": -0.055000, "yaw": 3.099000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.12
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.04
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.72
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_latest_zero_captured_roll_before_retrieval_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.887, "y": -0.059, "z": 0.05}
    ball_pose = {"x": 3.851, "y": -0.057, "z": 0.05}
    robot_pose = {"x": 3.990, "y": -0.073, "yaw": 3.070}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.033
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.04
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.72
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.55


def test_policy_place_holds_latest_zero_stale_motion_sample_at_retrieval_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.569, "y": -0.040, "z": 0.05}
    ball_pose = {"x": 3.569, "y": -0.040, "z": 0.05}
    robot_pose = {"x": 3.898, "y": -0.066, "yaw": 3.080}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_drive_to_zone"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.35
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_latest_zero_straight_line_recapture_near_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.648964, "y": 0.018627, "z": 0.05}
    ball_pose = {"x": 3.605255, "y": 0.020107, "z": 0.05}
    robot_pose = {"x": 4.169300, "y": -0.006666, "yaw": 3.109100}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.04
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_recenters_near_zone_drift_just_outside_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.211271, "y": -0.502858}
    robot_pose = {"x": 3.884518, "y": -0.315963, "yaw": 3.083363}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.30


def test_policy_place_recenters_outer_near_zone_lateral_drift_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.313873, "y": -0.587876, "z": 0.05}
    robot_pose = {"x": 4.083027, "y": -0.334993, "yaw": -3.09674}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.36


def test_policy_place_shepherds_unsecured_ball_shallow_inside_retrieval_corral():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 2.941005, "y": -0.362959}
    robot_pose = {"x": 3.817853, "y": -0.218638, "yaw": 3.077252}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] < zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 0.45
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False


def test_policy_place_holds_near_zone_when_ball_is_already_coasting():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.267677, "y": -0.129221, "z": 0.05}
    ball_pose = {"x": 3.238527, "y": -0.114502, "z": 0.05}
    robot_pose = {"x": 3.655392, "y": -0.201456, "yaw": 2.968483}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.12
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True


def test_policy_place_keeps_driving_when_coasting_ball_is_not_at_retrieval_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.558271, "y": -0.104743, "z": 0.05}
    ball_pose = {"x": 3.514187, "y": -0.103516, "z": 0.05}
    robot_pose = {"x": 4.035514, "y": -0.102607, "yaw": 3.120045}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.12
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True


def test_policy_place_slows_near_zone_recapture_before_retrieval_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.44868, "y": -0.004756, "z": 0.05}
    ball_pose = {"x": 3.414054, "y": -0.002407, "z": 0.05}
    robot_pose = {"x": 3.738582, "y": -0.031946, "yaw": 3.091737}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.30
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True


def test_policy_place_coasts_latest_plus45_near_zone_roll_before_center_overshoot():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.178, "y": 0.751, "z": 0.05}
    ball_pose = {"x": 3.155, "y": 0.727, "z": 0.05}
    robot_pose = {"x": 3.353616, "y": 0.94591, "yaw": -2.390723}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.12
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.30


def test_policy_place_yaws_shallow_inside_retrieval_when_ball_is_coasting():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.251118, "y": -0.096197, "z": 0.05}
    ball_pose = {"x": 3.205603, "y": -0.094931, "z": 0.05}
    robot_pose = {"x": 3.924290, "y": -0.099114, "yaw": 3.103862}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert abs(decision.command.angular_z) >= 0.10
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True


def test_policy_place_yaws_latest_inside_retrieval_near_miss_without_forward_push():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.565813, "y": 0.225142, "z": 0.05}
    ball_pose = {"x": 2.536631, "y": 0.239875, "z": 0.05}
    robot_pose = {"x": 3.650659, "y": -0.200707, "yaw": 3.097094}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert abs(decision.command.angular_z) >= 0.10
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.30
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False


def test_policy_place_keeps_up_with_shallow_centered_moving_ball_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.993122, "y": -0.467922, "z": 0.05}
    ball_pose = {"x": 2.949666, "y": -0.474024, "z": 0.05}
    robot_pose = {"x": 4.032139, "y": -0.254364, "yaw": 2.975525}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert 0.0 < decision.command.linear_x <= 0.018
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.22
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert 0.45 < decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.80
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False


def test_policy_place_holds_aligned_moving_ball_inside_retrieval_without_forward_sweep():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.968696, "y": 0.032407, "z": 0.05}
    ball_pose = {"x": 2.940879, "y": 0.048312, "z": 0.05}
    robot_pose = {"x": 3.561197, "y": -0.186084, "yaw": -3.111116}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert 0.45 < decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.60
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.20


def test_policy_place_holds_latest_zero_centered_line_roll_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.779, "y": -0.175, "z": 0.05}
    ball_pose = {"x": 2.748, "y": -0.174, "z": 0.05}
    robot_pose = {"x": 3.559, "y": -0.163, "yaw": 2.646}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.45
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.55


def test_policy_place_holds_latest_deep_moving_zero_roll_before_timeout_reentry():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.521, "y": -0.221, "z": 0.05}
    ball_pose = {"x": 2.488, "y": -0.219, "z": 0.05}
    robot_pose = {"x": 3.611, "y": -0.209, "yaw": 2.731}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.36
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.40


def test_policy_place_yaws_offset_recapture_inside_retrieval_without_forward_nudge():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.047, "y": -0.341, "z": 0.05}
    robot_pose = {"x": 3.879, "y": -0.209, "yaw": -3.140}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.08


def test_policy_place_holds_mid_depth_lateral_sweep_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.006, "y": -0.345, "z": 0.05}
    ball_pose = {"x": 2.965, "y": -0.349, "z": 0.05}
    robot_pose = {"x": 3.871, "y": -0.208, "yaw": 2.893}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.70
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70


def test_policy_place_reorients_high_lateral_slip_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.759229, "y": 0.459136, "z": 0.05}
    ball_pose = {"x": 2.724506, "y": 0.465040, "z": 0.05}
    robot_pose = {"x": 3.840780, "y": 0.205087, "yaw": -2.345342}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_reorient"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.75


def test_policy_place_reorients_high_lateral_slip_toward_zone_line_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.803104, "y": -0.362309, "z": 0.05}
    ball_pose = {"x": 2.766990, "y": -0.365452, "z": 0.05}
    robot_pose = {"x": 3.817548, "y": -0.220795, "yaw": 2.395630}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_reorient"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 0.45
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.75


def test_policy_place_reorients_latest_zero_far_behind_high_lateral_before_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.664060, "y": -0.362931, "z": 0.05}
    ball_pose = {"x": 4.664060, "y": -0.362931, "z": 0.05}
    robot_pose = {"x": 5.546890, "y": -0.026923, "yaw": 1.884529}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_reorient"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is False
    assert -0.10 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.10
    assert 0.90 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.00
    assert 0.24 <= abs(ball_pose["y"] - zone.world_y) <= 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.50


def test_policy_place_finish_nudges_deep_high_lateral_ball_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.667740, "y": 0.183822, "z": 0.05}
    ball_pose = {"x": 2.637589, "y": 0.203442, "z": 0.05}
    robot_pose = {"x": 3.508662, "y": -0.252588, "yaw": -2.682095}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert 0.0 < decision.command.linear_x <= 0.006
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.15
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert 0.30 < decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.35
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.75


def test_policy_place_holds_deep_centered_moving_ball_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.617554, "y": -0.225237, "z": 0.05}
    ball_pose = {"x": 2.581719, "y": -0.228089, "z": 0.05}
    robot_pose = {"x": 3.948711, "y": -0.106845, "yaw": 2.473863}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.30
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False


def test_policy_place_shepherds_close_ahead_ball_inside_retrieval_corral():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.049465, "y": -0.356746}
    robot_pose = {"x": 3.775502, "y": -0.244242, "yaw": 3.015136}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 0.45
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] < 0.75
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.45


def test_policy_place_slows_overlap_at_retrieval_edge_before_release():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.169866, "y": -0.102835}
    robot_pose = {"x": 3.871232, "y": -0.082077, "yaw": 3.129361}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert 0.0 < decision.command.linear_x <= 0.006
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True


def test_policy_place_slows_captured_ball_at_retrieval_overlap_edge():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.180359, "y": -0.115793}
    robot_pose = {"x": 3.509673, "y": -0.205807, "yaw": 2.934601}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert 0.0 < decision.command.linear_x <= 0.006
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["capture_snapshot"]["captured"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True


def test_policy_place_holds_unsecured_ball_deep_inside_retrieval_corral():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 2.023, "y": 0.108}
    robot_pose = {"x": 3.530, "y": -0.157, "yaw": -2.843}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.45
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False


def test_policy_place_holds_inside_retrieval_after_ball_passes_zone_center():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.939472, "y": -0.112642}
    robot_pose = {"x": 3.865230, "y": -0.082133, "yaw": 3.129361}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 0.45
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False


def test_policy_place_shepherds_latest_zero_high_x_positive_lateral_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.000, "y": 0.404, "z": 0.05}
    ball_pose = {"x": 2.956, "y": 0.413, "z": 0.05}
    robot_pose = {"x": 4.782, "y": 0.014, "yaw": 2.979}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x > 0.0
    assert decision.command.angular_z < -0.24
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.035
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert 0.50 <= decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.75
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.25
    assert 0.38 <= ball_pose["y"] - zone.world_y <= 0.55


def test_policy_place_shepherds_latest_zero_late_high_x_positive_lateral_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.631, "y": 0.487, "z": 0.05}
    ball_pose = {"x": 2.586, "y": 0.497, "z": 0.05}
    robot_pose = {"x": 4.777, "y": 0.014, "yaw": -3.137}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x > 0.0
    assert decision.command.angular_z < -0.24
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.035
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert 0.50 <= decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.75
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.25
    assert 0.38 <= ball_pose["y"] - zone.world_y <= 0.55


def test_policy_place_recenters_low_x_lateral_drift_before_keepup():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.30795, "y": -0.120153}
    robot_pose = {"x": 5.668368, "y": 0.06432, "yaw": -2.876083}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.08
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20


def test_policy_place_recenters_far_lateral_drift_just_outside_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.383710, "y": -0.465903}
    robot_pose = {"x": 4.935988, "y": -0.213790, "yaw": -3.056155}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_continues_far_lateral_recenter_as_ball_walks_forward():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.170660, "y": -0.741924}
    robot_pose = {"x": 4.876823, "y": -0.285022, "yaw": -2.900606}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32


def test_policy_place_recenters_forward_far_lateral_drift_outside_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.946638, "y": -0.710312}
    robot_pose = {"x": 4.782305, "y": -0.288389, "yaw": -2.919781}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.85
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32


def test_policy_place_keeps_forward_far_lateral_recenter_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.721316, "y": -0.817710, "z": 0.05}
    robot_pose = {"x": 4.658652, "y": -0.308747, "yaw": -2.820309}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.12
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_high_far_lateral_recenter_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.605, "y": -0.795, "z": 0.05}
    robot_pose = {"x": 4.624, "y": -0.304, "yaw": -2.990}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.12
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.32
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_up_just_beyond_far_recapture_edge():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.628719, "y": -0.875709}
    robot_pose = {"x": 4.399423, "y": -0.423122, "yaw": -2.795907}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.85
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_up_at_latest_far_high_x_boundary_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.027779, "y": -0.934714, "z": 0.05}
    robot_pose = {"x": 4.984614, "y": -0.282593, "yaw": -2.684153}
    previous_ball_pose = {"x": 4.066344, "y": -0.909332, "z": 0.05}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.12
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.25
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_up_past_latest_one_point_two_five_x_rollout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.98504, "y": -0.258169, "z": 0.05}
    robot_pose = {"x": 5.225683, "y": -0.074589, "yaw": -2.930867}
    previous_ball_pose = {"x": 4.01819, "y": -0.254788, "z": 0.05}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.25
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_up_past_latest_one_point_three_five_x_rollout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.057319, "y": 0.642927, "z": 0.05}
    ball_pose = {"x": 4.023632, "y": 0.661888, "z": 0.05}
    robot_pose = {"x": 5.298555, "y": 0.016874, "yaw": 2.68879}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.35
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_up_past_latest_one_point_five_five_x_rollout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.465887, "y": 0.565483, "z": 0.05}
    ball_pose = {"x": 3.431916, "y": 0.577206, "z": 0.05}
    robot_pose = {"x": 4.914506, "y": 0.087071, "yaw": 2.858073}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.55
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.65
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_keeps_up_past_latest_one_point_six_five_x_rollout_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.558503, "y": 0.736357, "z": 0.05}
    ball_pose = {"x": 3.516199, "y": 0.758077, "z": 0.05}
    robot_pose = {"x": 5.040532, "y": 0.021292, "yaw": 2.716119}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert decision.command.linear_x > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.65
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_recenters_high_x_far_rollout_that_is_off_zone_line():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.701421, "y": 1.144426, "z": 0.05}
    ball_pose = {"x": 3.664873, "y": 1.173711, "z": 0.05}
    robot_pose = {"x": 5.153666, "y": 0.08338, "yaw": 2.543747}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.018
    assert decision.command.angular_z > 0.22
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.55
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.90


def test_policy_place_recenters_high_x_far_rollout_with_moderate_capture_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.785462, "y": 1.223426, "z": 0.05}
    ball_pose = {"x": 3.750522, "y": 1.255136, "z": 0.05}
    robot_pose = {"x": 5.237953, "y": 0.039057, "yaw": 2.327375}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.018
    assert decision.command.angular_z >= 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.55
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.20
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.90


def test_policy_place_recenters_late_zero_high_x_far_rollout_before_release_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.634386, "y": -1.231736, "z": 0.05}
    ball_pose = {"x": 3.60319, "y": -1.252923, "z": 0.05}
    robot_pose = {"x": 5.27704, "y": -0.186986, "yaw": -2.439828}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.012
    assert decision.command.angular_z <= -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.95
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.90


def test_policy_place_reels_latest_high_x_lateral_rollout_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.161808, "y": -0.568103, "z": 0.05}
    ball_pose = {"x": 4.131349, "y": -0.581556, "z": 0.05}
    robot_pose = {"x": 5.286221, "y": -0.114683, "yaw": -2.959096}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.0 < decision.command.linear_x <= 0.032
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.20
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.20
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_reels_latest_high_x_lateral_rollout_past_one_point_three_five():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.837495, "y": -0.413848, "z": 0.05}
    ball_pose = {"x": 3.807159, "y": -0.421644, "z": 0.05}
    robot_pose = {"x": 5.180412, "y": -0.095391, "yaw": -2.729457}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.35
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.20
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert ball_pose["y"] - zone.world_y < -0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_reels_latest_wide_lateral_rollout_before_release_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.797748, "y": 0.031584, "z": 0.05}
    ball_pose = {"x": 3.763898, "y": 0.032231, "z": 0.05}
    robot_pose = {"x": 5.004266, "y": -0.026968, "yaw": 2.63545}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.40
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_reels_latest_very_wide_lateral_rollout_before_release_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.208579, "y": 0.937607, "z": 0.05}
    ball_pose = {"x": 4.178999, "y": 0.968452, "z": 0.05}
    robot_pose = {"x": 5.220518, "y": 0.035618, "yaw": 2.904654}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.65
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_reels_latest_zero_large_world_high_x_lateral_by_zone_line():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.838, "y": 0.591, "z": 0.05}
    ball_pose = {"x": 3.799, "y": 0.609, "z": 0.05}
    robot_pose = {"x": 5.170, "y": -0.009, "yaw": 2.449}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.0 < decision.command.linear_x <= 0.012
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale <= 0.20
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.10 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.75
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.50
    assert 0.55 <= ball_pose["y"] - zone.world_y <= 0.80
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 0.50


def test_policy_place_holds_latest_zero_large_world_high_x_terminal_lateral_by_zone_line():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.563, "y": 0.723, "z": 0.05}
    ball_pose = {"x": 3.523, "y": 0.743, "z": 0.05}
    robot_pose = {"x": 5.120, "y": 0.013, "yaw": 2.163}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.10 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.75
    assert 0.85 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.00
    assert 0.55 <= ball_pose["y"] - zone.world_y <= 0.80
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 0.50


def test_policy_place_keeps_up_late_zero_far_wide_reel_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.062832, "y": -0.856158, "z": 0.05}
    ball_pose = {"x": 4.029483, "y": -0.876767, "z": 0.05}
    robot_pose = {"x": 5.309757, "y": -0.150806, "yaw": -3.07294}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.018 <= decision.command.linear_x <= 0.022
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.40
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.10


def test_policy_place_reels_latest_zero_high_x_rollout_by_world_lateral_sign():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.975, "y": -0.340, "z": 0.05}
    ball_pose = {"x": 3.942, "y": -0.345, "z": 0.05}
    robot_pose = {"x": 5.248, "y": -0.106, "yaw": -2.514}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.012 <= decision.command.linear_x <= 0.014
    assert decision.command.angular_z < -0.35
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.10
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert abs(ball_pose["y"] - zone.world_y) >= 0.30
    assert abs(ball_pose["y"] - zone.world_y) <= 0.50
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_extends_late_zero_high_x_reel_before_generic_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.622961, "y": 1.070555, "z": 0.05}
    ball_pose = {"x": 3.587062, "y": 1.096598, "z": 0.05}
    robot_pose = {"x": 5.169955, "y": 0.05214, "yaw": 2.723093}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.018 <= decision.command.linear_x <= 0.022
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.10


def test_policy_place_wide_recenters_latest_low_x_lateral_rollout_before_release_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.615568, "y": -0.433458, "z": 0.05}
    ball_pose = {"x": 4.583494, "y": -0.450093, "z": 0.05}
    robot_pose = {"x": 5.479095, "y": -0.059575, "yaw": 3.0124}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.38
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_world_recenters_latest_zero_wide_local_rollout_before_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.870844, "y": -0.344644, "z": 0.05}
    ball_pose = {"x": 3.838564, "y": -0.351698, "z": 0.05}
    robot_pose = {"x": 4.770893, "y": -0.137998, "yaw": -2.151572}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.60
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert abs(ball_pose["y"] - zone.world_y) >= 0.30
    assert abs(ball_pose["y"] - zone.world_y) <= 0.42
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_world_recenters_latest_zero_high_x_wide_local_rollout_before_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.101413, "y": -0.337028, "z": 0.05}
    ball_pose = {"x": 4.067045, "y": -0.343543, "z": 0.05}
    robot_pose = {"x": 5.239489, "y": -0.105649, "yaw": -2.307364}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.90
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.10
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.50
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert abs(ball_pose["y"] - zone.world_y) >= 0.30
    assert abs(ball_pose["y"] - zone.world_y) <= 0.42
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_world_recenters_latest_zero_large_lateral_low_x_rollout_before_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.674749, "y": -0.614686, "z": 0.05}
    ball_pose = {"x": 3.649862, "y": -0.622041, "z": 0.05}
    robot_pose = {"x": 4.324915, "y": -0.376108, "yaw": -2.104318}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.023
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.52
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.50
    assert abs(ball_pose["y"] - zone.world_y) >= 0.55
    assert abs(ball_pose["y"] - zone.world_y) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.76


def test_policy_place_world_recenters_latest_zero_moderate_lateral_recapture_before_snowball():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 5.064, "y": -0.275, "z": 0.05}
    ball_pose = {"x": 5.040, "y": -0.292, "z": 0.05}
    robot_pose = {"x": 5.488, "y": -0.055, "yaw": -2.531}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.0 < decision.command.linear_x <= 0.020
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.45
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.70
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.55
    assert abs(ball_pose["y"] - zone.world_y) >= 0.24
    assert abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_world_recenters_latest_zero_mid_x_large_world_lateral_before_local_flip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.577, "y": -0.619, "z": 0.05}
    ball_pose = {"x": 4.547, "y": -0.640, "z": 0.05}
    robot_pose = {"x": 5.393, "y": -0.121, "yaw": -2.343}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.012 <= decision.command.linear_x <= 0.020
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.025
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.90
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.15
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.50
    assert abs(ball_pose["y"] - zone.world_y) >= 0.55
    assert abs(ball_pose["y"] - zone.world_y) <= 0.70
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_world_recenters_latest_zero_wide_moderate_x_before_local_flip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.658, "y": -0.562, "z": 0.05}
    ball_pose = {"x": 4.631, "y": -0.581, "z": 0.05}
    robot_pose = {"x": 5.393, "y": -0.121, "yaw": -1.880}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.025
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.45
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.70
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.65
    assert abs(ball_pose["y"] - zone.world_y) >= 0.55
    assert abs(ball_pose["y"] - zone.world_y) <= 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_world_recenters_latest_zero_low_x_wide_lateral_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.579, "y": -0.386, "z": 0.05}
    ball_pose = {"x": 4.551, "y": -0.396, "z": 0.05}
    robot_pose = {"x": 5.395, "y": -0.072, "yaw": -1.773}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.025
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.35
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.70
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert abs(ball_pose["y"] - zone.world_y) >= 0.24
    assert abs(ball_pose["y"] - zone.world_y) <= 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_world_recenters_latest_zero_terminal_low_x_wide_lateral_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.476, "y": -0.284, "z": 0.05}
    ball_pose = {"x": 4.440027, "y": -0.290317, "z": 0.05}
    robot_pose = {"x": 5.240979, "y": -0.100375, "yaw": -1.751912}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.22
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.04
    assert 0.30 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.35
    assert 0.70 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert 0.24 <= abs(ball_pose["y"] - zone.world_y) <= 0.35
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_world_recenters_latest_zero_extreme_local_lateral_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.622, "y": -0.445, "z": 0.05}
    ball_pose = {"x": 4.592893, "y": -0.458779, "z": 0.05}
    robot_pose = {"x": 5.404459, "y": -0.074242, "yaw": -1.348913}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.04
    assert 0.15 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.35
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.95
    assert 0.35 <= abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_world_recenters_latest_zero_near_side_lateral_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.734, "y": -0.450, "z": 0.05}
    ball_pose = {"x": 4.703464, "y": -0.468906, "z": 0.05}
    robot_pose = {"x": 5.423427, "y": -0.070814, "yaw": -1.142728}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.04
    assert 0.0 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.10
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.95
    assert 0.35 <= abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_far_wide_recenters_latest_zero_opposed_local_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.718, "y": 0.154, "z": 0.05}
    ball_pose = {"x": 3.668598, "y": 0.162922, "z": 0.05}
    robot_pose = {"x": 4.763059, "y": -0.013893, "yaw": -2.496476}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert abs(ball_pose["y"] - zone.world_y) <= 0.22
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.80


def test_policy_place_far_wide_recenters_latest_zero_far_opposed_local_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.494, "y": -0.087, "z": 0.05}
    ball_pose = {"x": 4.439139, "y": -0.087542, "z": 0.05}
    robot_pose = {"x": 5.528977, "y": -0.01284, "yaw": 2.424944}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert abs(ball_pose["y"] - zone.world_y) <= 0.22
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.40


def test_policy_place_coasts_latest_zero_pre_entry_roll_before_corral_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.568, "y": -0.192, "z": 0.05}
    ball_pose = {"x": 3.527, "y": -0.194, "z": 0.05}
    robot_pose = {"x": 4.568, "y": -0.124, "yaw": -2.992}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] >= 0.035
    assert 0.90 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.25
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.15 <= zone_margin_m <= 0.55


def test_policy_place_coasts_latest_zero_high_x_pre_entry_roll_before_corral_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.624, "y": 0.009, "z": 0.05}
    ball_pose = {"x": 3.570, "y": 0.007, "z": 0.05}
    robot_pose = {"x": 4.877, "y": -0.021, "yaw": 3.091}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] >= 0.035
    assert 1.25 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.45
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert abs(ball_pose["y"] - zone.world_y) <= 0.25
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.15 <= zone_margin_m <= 0.55


def test_policy_place_coasts_latest_zero_centered_recapture_before_mouth_keepup():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.615, "y": -0.036, "z": 0.05}
    ball_pose = {"x": 3.571, "y": -0.041, "z": 0.05}
    robot_pose = {"x": 4.374, "y": 0.004, "yaw": 3.141}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] >= 0.040
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.16
    assert abs(ball_pose["y"] - zone.world_y) <= 0.06
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.30 <= zone_margin_m <= 0.75


def test_policy_place_world_recenters_latest_zero_high_lateral_rollout_before_local_flip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.883, "y": 0.593, "z": 0.05}
    ball_pose = {"x": 3.848882, "y": 0.615557, "z": 0.05}
    robot_pose = {"x": 4.875360, "y": -0.015286, "yaw": 1.897709}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.05
    assert 0.90 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.10
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert 0.55 <= abs(ball_pose["y"] - zone.world_y) <= 0.75
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 0.75
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.15


def test_policy_place_reels_latest_zero_low_x_medium_lateral_far_gap_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.784, "y": -0.235, "z": 0.05}
    ball_pose = {"x": 3.753, "y": -0.237, "z": 0.05}
    robot_pose = {"x": 4.881, "y": -0.129, "yaw": 2.890}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_recapture_reel"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z > 0.35
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.025
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.00 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.12
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.45
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.75


def test_policy_place_keeps_up_with_moving_far_middle_lateral_rollout_before_release_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.570348, "y": -0.320465, "z": 0.05}
    ball_pose = {"x": 4.531365, "y": -0.341697, "z": 0.05}
    robot_pose = {"x": 5.223762, "y": -0.077807, "yaw": -3.056275}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert 0.014 <= decision.command.linear_x <= 0.025
    assert decision.command.angular_z < -0.40
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.65
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_keeps_up_with_latest_zero_low_x_line_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.878253, "y": 0.129931, "z": 0.05}
    ball_pose = {"x": 4.844693, "y": 0.161069, "z": 0.05}
    robot_pose = {"x": 5.294000, "y": -0.058000, "yaw": 2.936000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z > 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.10
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40


def test_policy_place_holds_latest_zero_positive_opposed_line_before_snowball():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.528858, "y": 0.217481, "z": 0.05}
    ball_pose = {"x": 4.493511, "y": 0.232716, "z": 0.05}
    robot_pose = {"x": 5.145268, "y": 0.003916, "yaw": 3.082245}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.60 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert 0.14 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.22
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_positive_wide_opposed_line_before_rollout_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.372414, "y": 0.284912, "z": 0.05}
    ball_pose = {"x": 4.337899, "y": 0.299790, "z": 0.05}
    robot_pose = {"x": 5.103579, "y": 0.004679, "yaw": -2.601807}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.45 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.60
    assert 0.60 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert 0.22 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_high_x_positive_opposed_line_before_rollout_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.657, "y": 0.301808, "z": 0.05}
    ball_pose = {"x": 4.621495, "y": 0.319886, "z": 0.05}
    robot_pose = {"x": 5.482888, "y": -0.026772, "yaw": 3.020832}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.75 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.95
    assert 0.20 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.30
    assert 0.30 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_fast_positive_opposed_before_far_side_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.648128, "y": 0.206717, "z": 0.05}
    ball_pose = {"x": 4.604320, "y": 0.223064, "z": 0.05}
    robot_pose = {"x": 5.375099, "y": -0.010905, "yaw": -2.979352}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert 0.20 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_high_x_fast_positive_opposed_before_far_side_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.393274, "y": 0.301815, "z": 0.05}
    ball_pose = {"x": 4.349659, "y": 0.318089, "z": 0.05}
    robot_pose = {"x": 5.362127, "y": -0.009972, "yaw": -3.105013}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.95 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert 0.30 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_moderate_positive_opposed_before_near_zone():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.147038, "y": 0.167583, "z": 0.05}
    ball_pose = {"x": 4.104446, "y": 0.181214, "z": 0.05}
    robot_pose = {"x": 4.847874, "y": 0.016581, "yaw": 3.097649}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is True
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.80
    assert 0.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.16
    assert 0.12 <= ball_pose["y"] - zone.world_y <= 0.22
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.90 <= zone_margin_m <= 1.00


def test_policy_place_holds_latest_zero_low_margin_positive_opposed_before_edge_reel():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.975873, "y": 0.222360, "z": 0.05}
    ball_pose = {"x": 3.934435, "y": 0.235621, "z": 0.05}
    robot_pose = {"x": 4.813371, "y": 0.008225, "yaw": -2.568902}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.70
    assert 0.60 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert 0.20 <= ball_pose["y"] - zone.world_y <= 0.28
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.75 <= zone_margin_m <= 0.85


def test_policy_place_holds_latest_zero_edge_margin_positive_opposed_before_near_reel():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.849075, "y": 0.262938, "z": 0.05}
    ball_pose = {"x": 3.805951, "y": 0.276738, "z": 0.05}
    robot_pose = {"x": 4.801918, "y": -0.000259, "yaw": -2.479539}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.28
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.70
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.90
    assert 0.25 <= ball_pose["y"] - zone.world_y <= 0.32
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.65 <= zone_margin_m <= 0.70


def test_policy_place_holds_latest_zero_positive_world_edge_before_keepup_repush():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.579356, "y": 0.264971, "z": 0.05}
    ball_pose = {"x": 4.537200, "y": 0.282980, "z": 0.05}
    robot_pose = {"x": 5.385365, "y": -0.029575, "yaw": 2.845454}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.85 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert 0.25 <= ball_pose["y"] - zone.world_y <= 0.35
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.35 <= zone_margin_m <= 1.45


def test_policy_place_holds_latest_zero_high_lateral_positive_world_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.715903, "y": 0.633831, "z": 0.05}
    ball_pose = {"x": 3.670265, "y": 0.653327, "z": 0.05}
    robot_pose = {"x": 5.308419, "y": 0.001316, "yaw": 1.998205}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.75
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.20 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert 1.15 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.30
    assert 0.60 <= ball_pose["y"] - zone.world_y <= 0.70
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.60 <= zone_margin_m <= 0.70


def test_policy_place_holds_latest_zero_stale_positive_world_edge_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.802505, "y": 0.596835, "z": 0.05}
    ball_pose = {"x": 3.802505, "y": 0.596835, "z": 0.05}
    robot_pose = {"x": 5.323044, "y": -0.012464, "yaw": 2.653985}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.75
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.70
    assert 0.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.25
    assert 0.55 <= ball_pose["y"] - zone.world_y <= 0.65
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.75 <= zone_margin_m <= 0.80


def test_policy_place_holds_latest_zero_mid_margin_positive_world_edge_repush():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.014290, "y": 0.506363, "z": 0.05}
    ball_pose = {"x": 3.975250, "y": 0.523040, "z": 0.05}
    robot_pose = {"x": 5.361003, "y": -0.030679, "yaw": 2.839245}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.75
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.40 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.55
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.15
    assert 0.50 <= ball_pose["y"] - zone.world_y <= 0.55
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.85 <= zone_margin_m <= 0.95


def test_policy_place_holds_latest_zero_low_x_positive_world_edge_before_wide_flip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.246321, "y": 0.335636, "z": 0.05}
    ball_pose = {"x": 4.209800, "y": 0.352040, "z": 0.05}
    robot_pose = {"x": 5.210430, "y": -0.003143, "yaw": 2.014821}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.03 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 0.70 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.80
    assert 0.30 <= ball_pose["y"] - zone.world_y <= 0.40
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 1.05 <= zone_margin_m <= 1.10


def test_policy_place_holds_latest_zero_terminal_positive_world_edge_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.796629, "y": 0.537616, "z": 0.05}
    ball_pose = {"x": 3.758530, "y": 0.554729, "z": 0.05}
    robot_pose = {"x": 5.209441, "y": -0.000869, "yaw": 1.963221}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.75
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.03 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.00 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.15
    assert 1.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.20
    assert 0.50 <= ball_pose["y"] - zone.world_y <= 0.60
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.70 <= zone_margin_m <= 0.75


def test_policy_place_holds_latest_zero_low_x_same_side_positive_world_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.886587, "y": 0.379864, "z": 0.05}
    ball_pose = {"x": 3.849514, "y": 0.392980, "z": 0.05}
    robot_pose = {"x": 5.063476, "y": -0.000434, "yaw": 1.278013}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.03 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.10
    assert 1.20 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.30
    assert 0.35 <= ball_pose["y"] - zone.world_y <= 0.45
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.70 <= zone_margin_m <= 0.80


def test_policy_place_holds_latest_zero_near_mouth_positive_world_edge_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.300028, "y": 0.587886, "z": 0.05}
    ball_pose = {"x": 3.254783, "y": 0.603395, "z": 0.05}
    robot_pose = {"x": 5.010124, "y": 0.012534, "yaw": 3.001789}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.06
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.75 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.90
    assert 0.25 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.45
    assert 0.55 <= ball_pose["y"] - zone.world_y <= 0.65
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.25 <= zone_margin_m <= 0.35


def test_policy_place_holds_latest_zero_stale_near_mouth_positive_world_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.254783, "y": 0.603395, "z": 0.05}
    ball_pose = {"x": 3.254783, "y": 0.603395, "z": 0.05}
    robot_pose = {"x": 5.008563, "y": 0.012798, "yaw": 2.937189}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.80 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.90
    assert 0.20 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.30
    assert 0.55 <= ball_pose["y"] - zone.world_y <= 0.65
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.25 <= zone_margin_m <= 0.35


def test_policy_place_holds_latest_zero_high_x_positive_wide_opposed_line_before_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.550151, "y": 0.356213, "z": 0.05}
    ball_pose = {"x": 4.512567, "y": 0.375350, "z": 0.05}
    robot_pose = {"x": 5.475768, "y": -0.026923, "yaw": -2.818501}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.75 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.95
    assert 0.65 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert 0.30 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_large_positive_opposed_line_before_snowball():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.589, "y": 0.374, "z": 0.05}
    ball_pose = {"x": 4.554, "y": 0.394, "z": 0.05}
    robot_pose = {"x": 5.392, "y": -0.010, "yaw": 2.892}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.75 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 0.16 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.25
    assert 0.38 <= ball_pose["y"] - zone.world_y <= 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_holds_latest_zero_large_positive_wide_opposed_line_before_abort():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.412, "y": 0.475, "z": 0.05}
    ball_pose = {"x": 4.377, "y": 0.494, "z": 0.05}
    robot_pose = {"x": 5.386, "y": -0.007, "yaw": -2.850}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_line_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.60
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.75 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 0.70 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert 0.38 <= ball_pose["y"] - zone.world_y <= 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] >= zone.retrieval_radius_m + 1.00


def test_policy_place_keeps_forward_contact_for_far_moderate_world_offset_before_local_recovery():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.956169, "y": 0.101029, "z": 0.05}
    ball_pose = {"x": 4.921975, "y": 0.113752, "z": 0.05}
    robot_pose = {"x": 5.335107, "y": -0.004048, "yaw": -2.933367}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.65
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.38
    assert 0.06 <= abs(ball_pose["y"] - zone.world_y) <= 0.22
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.00


def test_policy_place_keeps_up_when_far_recovery_is_world_centered_but_locally_wide():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.211, "y": 0.045, "z": 0.05}
    ball_pose = {"x": 4.159, "y": 0.047, "z": 0.05}
    robot_pose = {"x": 4.831, "y": -0.002, "yaw": -2.500}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.65
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) >= 0.38
    assert abs(ball_pose["y"] - zone.world_y) <= 0.08
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_recenters_latest_zero_low_x_opposed_wide_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.111, "y": -0.140, "z": 0.05}
    ball_pose = {"x": 4.067, "y": -0.154, "z": 0.05}
    robot_pose = {"x": 4.616, "y": -0.006, "yaw": 2.661}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.06
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.58
    assert 0.38 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.50
    assert 0.14 <= abs(ball_pose["y"] - zone.world_y) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.50


def test_policy_place_recenters_latest_zero_terminal_low_x_opposed_wide_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.712, "y": -0.272, "z": 0.05}
    ball_pose = {"x": 3.668, "y": -0.287, "z": 0.05}
    robot_pose = {"x": 4.564, "y": 0.027, "yaw": 2.359}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.06
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.58
    assert 0.80 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.90
    assert 0.14 <= abs(ball_pose["y"] - zone.world_y) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.50


def test_policy_place_keeps_tiny_contact_latest_zero_low_x_opposed_wide_near_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.770, "y": 0.279, "z": 0.05}
    ball_pose = {"x": 3.732, "y": 0.291, "z": 0.05}
    robot_pose = {"x": 4.720, "y": -0.009, "yaw": -2.456}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert 0.0 < decision.command.linear_x <= 0.010
    assert decision.command.angular_z < -0.35
    assert decision.command.target_speed_scale == 0.18
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.060
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.50 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.60
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.90
    assert 0.24 <= ball_pose["y"] - zone.world_y <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.50
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.70


def test_policy_place_recenters_latest_zero_extreme_low_x_opposed_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.120444, "y": 0.295190, "z": 0.05}
    ball_pose = {"x": 4.071564, "y": 0.306907, "z": 0.05}
    robot_pose = {"x": 5.234113, "y": -0.004391, "yaw": -2.296676}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.06
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.50 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.60
    assert 1.05 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.12
    assert 0.30 <= ball_pose["y"] - zone.world_y <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.90
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.00


def test_policy_place_recenters_latest_zero_terminal_extreme_opposed_before_second_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.970896, "y": 0.384678, "z": 0.05}
    ball_pose = {"x": 3.932036, "y": 0.400169, "z": 0.05}
    robot_pose = {"x": 5.048162, "y": -0.005350, "yaw": -2.130503}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.20 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.30
    assert 1.15 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.25
    assert 0.39 <= ball_pose["y"] - zone.world_y <= 0.42
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.80
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.85


def test_policy_place_recenters_latest_zero_local_dominant_wide_before_third_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.214682, "y": 0.342074, "z": 0.05}
    ball_pose = {"x": 4.169132, "y": 0.358497, "z": 0.05}
    robot_pose = {"x": 5.349281, "y": -0.021746, "yaw": -2.488967}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.65 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert 1.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.10
    assert 0.34 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.00
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.10


def test_policy_place_recenters_latest_zero_terminal_local_dominant_before_third_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.169132, "y": 0.358497, "z": 0.05}
    ball_pose = {"x": 4.126837, "y": 0.373746, "z": 0.05}
    robot_pose = {"x": 5.349281, "y": -0.021746, "yaw": -2.021567}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.15 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.25
    assert 1.25 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.35
    assert 0.35 <= ball_pose["y"] - zone.world_y <= 0.39
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.95
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.05


def test_policy_place_holds_latest_zero_terminal_extreme_opposed_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.901318, "y": -0.483737, "z": 0.05}
    ball_pose = {"x": 3.864860, "y": -0.495140, "z": 0.05}
    robot_pose = {"x": 5.447247, "y": -0.013957, "yaw": 2.328528}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.80
    assert 1.45 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.55
    assert 0.42 <= abs(ball_pose["y"] - zone.world_y) <= 0.58
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.70
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.90


def test_policy_place_holds_latest_zero_same_side_high_lateral_far_edge_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.827900, "y": 0.524276, "z": 0.05}
    ball_pose = {"x": 3.782314, "y": 0.542019, "z": 0.05}
    robot_pose = {"x": 5.384625, "y": -0.021094, "yaw": 1.570593}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.75
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.60
    assert 1.55 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.65
    assert 0.50 <= abs(ball_pose["y"] - zone.world_y) <= 0.60
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.70
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.75


def test_policy_place_holds_mirrored_terminal_extreme_opposed_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.901318, "y": 0.483737, "z": 0.05}
    ball_pose = {"x": 3.864860, "y": 0.495140, "z": 0.05}
    robot_pose = {"x": 5.447247, "y": 0.013957, "yaw": -2.328528}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.80
    assert 1.45 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.55
    assert 0.42 <= abs(ball_pose["y"] - zone.world_y) <= 0.58
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.70
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.90


def test_policy_place_holds_latest_zero_low_x_same_side_extreme_far_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.592913, "y": 0.679956, "z": 0.05}
    ball_pose = {"x": 3.557150, "y": 0.698551, "z": 0.05}
    robot_pose = {"x": 4.956543, "y": 0.033499, "yaw": 1.498389}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.50 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.65
    assert 1.35 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.50
    assert 0.65 <= abs(ball_pose["y"] - zone.world_y) <= 0.75
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.65


def test_policy_place_holds_mirrored_low_x_same_side_extreme_far_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.592913, "y": -0.679956, "z": 0.05}
    ball_pose = {"x": 3.557150, "y": -0.698551, "z": 0.05}
    robot_pose = {"x": 4.956543, "y": -0.033499, "yaw": -1.498389}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.045
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.50 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.65
    assert 1.35 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.50
    assert 0.65 <= abs(ball_pose["y"] - zone.world_y) <= 0.75
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.65


def test_policy_place_holds_latest_zero_high_x_transition_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.563218, "y": -0.455829, "z": 0.05}
    ball_pose = {"x": 3.499034, "y": -0.476415, "z": 0.05}
    robot_pose = {"x": 5.093592, "y": 0.029633, "yaw": 2.762408}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.060 <= decision.diagnostics["ball_motion_m"] <= 0.075
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.25 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert 1.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.12
    assert 0.42 <= abs(ball_pose["y"] - zone.world_y) <= 0.52
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.50


def test_policy_place_holds_mirrored_high_x_transition_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.563218, "y": 0.455829, "z": 0.05}
    ball_pose = {"x": 3.499034, "y": 0.476415, "z": 0.05}
    robot_pose = {"x": 5.093592, "y": -0.029633, "yaw": -2.762408}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.060 <= decision.diagnostics["ball_motion_m"] <= 0.075
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.25 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert 1.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.12
    assert 0.42 <= abs(ball_pose["y"] - zone.world_y) <= 0.52
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.50


def test_policy_place_holds_latest_zero_slow_transition_opposed_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.685760, "y": 0.512946, "z": 0.05}
    ball_pose = {"x": 3.641796, "y": 0.528984, "z": 0.05}
    robot_pose = {"x": 5.231129, "y": -0.015559, "yaw": -2.768220}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.20 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.40
    assert 1.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.15
    assert 0.42 <= abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert decision.diagnostics["capture_snapshot"]["ball_y_m"] * (ball_pose["y"] - zone.world_y) < 0.0
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.65


def test_policy_place_holds_mirrored_slow_transition_opposed_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.685760, "y": -0.512946, "z": 0.05}
    ball_pose = {"x": 3.641796, "y": -0.528984, "z": 0.05}
    robot_pose = {"x": 5.231129, "y": 0.015559, "yaw": 2.768220}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_far_wide_lateral_recenter"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.04 <= decision.diagnostics["ball_motion_m"] <= 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.20 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.40
    assert 1.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.15
    assert 0.42 <= abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert decision.diagnostics["capture_snapshot"]["ball_y_m"] * (ball_pose["y"] - zone.world_y) < 0.0
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.65


def test_policy_place_holds_latest_zero_paused_near_mouth_wide_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.947829, "y": 0.609253, "z": 0.05}
    ball_pose = {"x": 2.947829, "y": 0.609253, "z": 0.05}
    robot_pose = {"x": 4.836743, "y": 0.022816, "yaw": 2.277518}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z >= 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.60 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.75
    assert 1.04 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.12
    assert 0.55 <= abs(ball_pose["y"] - zone.world_y) <= 0.68
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.08


def test_policy_place_holds_mirrored_paused_near_mouth_wide_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.947829, "y": -0.609253, "z": 0.05}
    ball_pose = {"x": 2.947829, "y": -0.609253, "z": 0.05}
    robot_pose = {"x": 4.836743, "y": -0.022816, "yaw": -2.277518}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.60 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.75
    assert 1.04 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.12
    assert 0.55 <= abs(ball_pose["y"] - zone.world_y) <= 0.68
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.08


def test_policy_place_holds_latest_zero_lateral_rollthrough_before_reorient():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.149741, "y": 0.322811, "z": 0.05}
    ball_pose = {"x": 2.101173, "y": 0.328013, "z": 0.05}
    robot_pose = {"x": 4.767323, "y": -0.006325, "yaw": -2.130600}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.45
    assert abs(ball_pose["y"] - zone.world_y) >= 0.24


def test_policy_place_holds_latest_zero_behind_lateral_rollthrough_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 1.855889, "y": 0.354281, "z": 0.05}
    ball_pose = {"x": 1.806914, "y": 0.359526, "z": 0.05}
    robot_pose = {"x": 4.767323, "y": -0.006325, "yaw": -1.472960}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m


def test_policy_place_holds_latest_zero_high_x_lateral_rollthrough_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.018075, "y": -0.333720, "z": 0.05}
    ball_pose = {"x": 2.967986, "y": -0.344516, "z": 0.05}
    robot_pose = {"x": 4.714681, "y": 0.023380, "yaw": 2.777733}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.05
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 1.45
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) >= 0.90
    assert 0.30 <= abs(ball_pose["y"] - zone.world_y) <= 0.60


def test_policy_place_holds_mirrored_high_x_lateral_rollthrough_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.018075, "y": 0.333720, "z": 0.05}
    ball_pose = {"x": 2.967986, "y": 0.344516, "z": 0.05}
    robot_pose = {"x": 4.714681, "y": -0.023380, "yaw": -2.777733}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.05
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 1.45
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) >= 0.90
    assert 0.30 <= abs(ball_pose["y"] - zone.world_y) <= 0.60


def test_policy_place_keeps_up_when_far_recovery_is_moderately_offset_but_locally_wide():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.018, "y": -0.126, "z": 0.05}
    ball_pose = {"x": 3.936, "y": -0.149, "z": 0.05}
    robot_pose = {"x": 4.534, "y": 0.012, "yaw": 2.651}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.65
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) >= 0.38
    assert abs(ball_pose["y"] - zone.world_y) <= 0.22
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_wide_far_recovery_contact_on_stale_motion_sample():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.036318, "y": -0.117247, "z": 0.05}
    ball_pose = {"x": 4.036318, "y": -0.117247, "z": 0.05}
    robot_pose = {"x": 4.788000, "y": 0.026000, "yaw": 2.639000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.38
    assert abs(ball_pose["y"] - zone.world_y) <= 0.22
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_wide_far_recovery_contact_at_later_low_x_rollout():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.932191, "y": -0.129773, "z": 0.05}
    ball_pose = {"x": 3.882625, "y": -0.135439, "z": 0.05}
    robot_pose = {"x": 4.776000, "y": 0.033000, "yaw": 2.621000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.38
    assert abs(ball_pose["y"] - zone.world_y) <= 0.22
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_wide_far_recovery_contact_with_moderate_world_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.858185, "y": -0.237049, "z": 0.05}
    ball_pose = {"x": 3.807554, "y": -0.250702, "z": 0.05}
    robot_pose = {"x": 4.820729, "y": 0.028630, "yaw": 2.452028}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.95
    assert abs(ball_pose["y"] - zone.world_y) <= 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_wide_far_recovery_contact_with_high_but_bounded_world_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.354979, "y": -0.374257, "z": 0.05}
    ball_pose = {"x": 4.311017, "y": -0.406384, "z": 0.05}
    robot_pose = {"x": 5.049830, "y": 0.024304, "yaw": 2.285337}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.024
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.95
    assert abs(ball_pose["y"] - zone.world_y) <= 0.42
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.60


def test_policy_place_keeps_centered_far_recovery_contact_on_stale_local_widening():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.972872, "y": -0.010848, "z": 0.05}
    ball_pose = {"x": 3.972872, "y": -0.010848, "z": 0.05}
    robot_pose = {"x": 4.405000, "y": 0.013000, "yaw": 2.603000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.018
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.75
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.38
    assert abs(ball_pose["y"] - zone.world_y) <= 0.08
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.40
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 1.00


def test_policy_place_keeps_centered_near_zone_wide_contact_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.571568, "y": -0.013813, "z": 0.05}
    ball_pose = {"x": 3.537423, "y": -0.014054, "z": 0.05}
    robot_pose = {"x": 4.368078, "y": 0.037208, "yaw": 2.692167}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z > 0.0
    assert decision.command.target_speed_scale == 0.25
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["captured"] is False
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.32
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.55
    assert abs(ball_pose["y"] - zone.world_y) <= 0.08
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_reels_outer_near_zone_high_lateral_rollout_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.333699, "y": 0.706385, "z": 0.05}
    ball_pose = {"x": 3.292312, "y": 0.728096, "z": 0.05}
    robot_pose = {"x": 4.762638, "y": 0.006483, "yaw": 3.061473}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.32
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_reels_latest_high_lateral_near_zone_terminal_before_release_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.338958, "y": -0.576612, "z": 0.05}
    ball_pose = {"x": 3.308181, "y": -0.585027, "z": 0.05}
    robot_pose = {"x": 4.912559, "y": -0.144915, "yaw": 2.963194}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.010
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.70
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_reels_latest_zero_low_x_high_lateral_near_zone_terminal():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.587776, "y": 0.126222, "z": 0.05}
    ball_pose = {"x": 3.536379, "y": 0.133725, "z": 0.05}
    robot_pose = {"x": 4.543265, "y": -0.000564, "yaw": -2.576281}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.014
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 0.55 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert abs(ball_pose["y"] - zone.world_y) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.36
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46

def test_policy_place_reels_latest_zero_low_x_medium_lateral_near_zone_terminal():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.601, "y": 0.128, "z": 0.05}
    ball_pose = {"x": 3.550, "y": 0.132, "z": 0.05}
    robot_pose = {"x": 4.512, "y": -0.016, "yaw": -2.711}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.010
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale <= 0.40
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 0.50 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.60
    assert abs(ball_pose["y"] - zone.world_y) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.36
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_reels_latest_zero_wide_lateral_near_zone_final_gap():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.590, "y": 0.066, "z": 0.05}
    ball_pose = {"x": 3.537, "y": 0.072, "z": 0.05}
    robot_pose = {"x": 4.742, "y": 0.013, "yaw": -2.646}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.010
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale <= 0.40
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.00 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 0.50 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert abs(ball_pose["y"] - zone.world_y) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.36
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_latest_zero_same_side_low_x_near_edge_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.355849, "y": 0.425937, "z": 0.05}
    ball_pose = {"x": 3.313291, "y": 0.437436, "z": 0.05}
    robot_pose = {"x": 4.979227, "y": 0.017618, "yaw": 1.940913}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.90 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 1.35 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.45
    assert 0.38 <= abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.34


def test_policy_place_holds_latest_zero_mid_x_opposed_near_edge_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.453349, "y": -0.344227, "z": 0.05}
    ball_pose = {"x": 3.406073, "y": -0.355983, "z": 0.05}
    robot_pose = {"x": 4.912046, "y": 0.020860, "yaw": 2.574674}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.00 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.10
    assert 1.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.20
    assert 0.34 <= abs(ball_pose["y"] - zone.world_y) <= 0.52
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.28
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_latest_zero_high_x_opposed_near_edge_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.430477, "y": 0.482467, "z": 0.05}
    ball_pose = {"x": 3.385274, "y": 0.496924, "z": 0.05}
    robot_pose = {"x": 5.027208, "y": 0.011826, "yaw": -2.610997}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.10 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.20
    assert 1.20 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.30
    assert 0.45 <= abs(ball_pose["y"] - zone.world_y) <= 0.52
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.28
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_latest_zero_high_x_final_world_edge_before_rollaway():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.190756, "y": 0.383169, "z": 0.05}
    ball_pose = {"x": 3.137094, "y": 0.394466, "z": 0.05}
    robot_pose = {"x": 5.087228, "y": 0.017337, "yaw": 3.011586}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.35
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.05
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.80 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert 0.30 <= abs(ball_pose["y"] - zone.world_y) <= 0.50
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.12


def test_policy_place_holds_latest_zero_stale_high_x_final_world_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.040647, "y": 0.554660, "z": 0.05}
    ball_pose = {"x": 3.040647, "y": 0.554660, "z": 0.05}
    robot_pose = {"x": 5.022008, "y": 0.016536, "yaw": 2.661431}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.95 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.10
    assert 0.30 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.55
    assert 0.50 <= abs(ball_pose["y"] - zone.world_y) <= 0.65
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.12


def test_policy_place_reorients_latest_zero_far_negative_x_local_escape():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.208882, "y": 0.389998, "z": 0.05}
    ball_pose = {"x": 4.165617, "y": 0.407093, "z": 0.05}
    robot_pose = {"x": 5.393983, "y": -0.019308, "yaw": 1.152615}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_reorient"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.70
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is False
    assert -0.15 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= -0.05
    assert 1.25 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.35
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 1.00


def test_policy_place_reorients_latest_zero_deeper_far_negative_x_local_escape():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.044365, "y": 0.396935, "z": 0.05}
    ball_pose = {"x": 4.005398, "y": 0.412934, "z": 0.05}
    robot_pose = {"x": 5.193506, "y": -0.003195, "yaw": 1.024585}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_reorient"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.70
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is False
    assert -0.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= -0.20
    assert 1.20 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.85


def test_policy_place_reorients_latest_zero_deepest_far_negative_x_local_escape():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 4.011377, "y": 0.394718, "z": 0.05}
    ball_pose = {"x": 4.011377, "y": 0.394718, "z": 0.05}
    robot_pose = {"x": 5.139726, "y": 0.004154, "yaw": 0.902574}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_reorient"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.70
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is False
    assert -0.45 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= -0.35
    assert 1.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.85


def test_policy_place_coasts_latest_zero_final_mouth_gap_before_inside_entry():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.331, "y": -0.086, "z": 0.05}
    ball_pose = {"x": 3.281, "y": -0.088, "z": 0.05}
    robot_pose = {"x": 4.398, "y": 0.016, "yaw": -2.955}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.065
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert 0.95 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.06
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.15


def test_policy_place_coasts_latest_zero_deep_final_mouth_gap_before_inside_entry():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.281, "y": -0.088, "z": 0.05}
    ball_pose = {"x": 3.228, "y": -0.090, "z": 0.05}
    robot_pose = {"x": 4.395, "y": 0.016, "yaw": 3.140}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_coast_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert 0.035 <= decision.diagnostics["ball_motion_m"] <= 0.065
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert 0.95 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.06
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.15


def test_policy_place_reels_latest_zero_high_x_world_lateral_near_mouth_gap():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.470, "y": 0.283, "z": 0.05}
    ball_pose = {"x": 3.421, "y": 0.292, "z": 0.05}
    robot_pose = {"x": 5.252, "y": -0.010, "yaw": 2.526}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.008
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale <= 0.18
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.90
    assert 0.70 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.90
    assert 0.25 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_latest_zero_high_x_world_lateral_near_mouth_terminal():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.421, "y": 0.292, "z": 0.05}
    ball_pose = {"x": 3.369, "y": 0.303, "z": 0.05}
    robot_pose = {"x": 5.247, "y": -0.006, "yaw": 2.438}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.90
    assert 0.90 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.05
    assert 0.25 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.20
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_latest_zero_high_lateral_near_retrieval_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.475907, "y": -0.359758, "z": 0.05}
    ball_pose = {"x": 3.441110, "y": -0.365987, "z": 0.05}
    robot_pose = {"x": 4.970000, "y": -0.106000, "yaw": -3.093000}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.38


def test_policy_place_resteers_latest_zero_positive_lateral_near_retrieval_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.507176, "y": 0.389102, "z": 0.05}
    ball_pose = {"x": 3.458299, "y": 0.402181, "z": 0.05}
    robot_pose = {"x": 4.943821, "y": -0.003726, "yaw": -3.020408}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.50
    assert 0.50 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.65
    assert 0.38 <= ball_pose["y"] - zone.world_y <= 0.42
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.38


def test_policy_place_resteers_latest_zero_low_x_wide_near_zone_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.527, "y": 0.342, "z": 0.05}
    ball_pose = {"x": 3.484, "y": 0.354, "z": 0.05}
    robot_pose = {"x": 4.743, "y": -0.007, "yaw": -2.750}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.00 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.90
    assert 0.34 <= ball_pose["y"] - zone.world_y <= 0.38
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.35
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.40


def test_policy_place_reels_latest_zero_negative_world_near_mouth_by_zone_line():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.335, "y": -0.156, "z": 0.05}
    ball_pose = {"x": 3.276, "y": -0.164, "z": 0.05}
    robot_pose = {"x": 4.235, "y": 0.012, "yaw": 3.117}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x > 0.0
    assert decision.command.angular_z > 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.20
    assert -0.28 <= ball_pose["y"] - zone.world_y <= -0.12


def test_policy_place_near_zone_reels_latest_zero_by_world_lateral_sign():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.253, "y": -0.182, "z": 0.05}
    ball_pose = {"x": 3.223, "y": -0.183, "z": 0.05}
    robot_pose = {"x": 4.331, "y": -0.135, "yaw": -2.782}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.010
    assert decision.command.angular_z > 0.18
    assert decision.command.target_speed_scale == 0.20
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.025
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.95
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.15
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) >= 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.14
    assert abs(ball_pose["y"] - zone.world_y) <= 0.25
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_near_zone_reels_latest_zero_large_world_lateral_by_zone_line():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.144153, "y": -0.771497, "z": 0.05}
    ball_pose = {"x": 3.119905, "y": -0.778663, "z": 0.05}
    robot_pose = {"x": 4.043748, "y": -0.434960, "yaw": -2.580191}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.008
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.15
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.023
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.90
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.15
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.50
    assert abs(ball_pose["y"] - zone.world_y) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_near_zone_reels_low_local_large_world_lateral_before_keepup():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.168082, "y": -0.764419, "z": 0.05}
    ball_pose = {"x": 3.144153, "y": -0.771497, "z": 0.05}
    robot_pose = {"x": 4.049810, "y": -0.432262, "yaw": -2.872271}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.0 < decision.command.linear_x <= 0.008
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.15
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.023
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 0.90
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.15
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert abs(ball_pose["y"] - zone.world_y) >= 0.50
    assert abs(ball_pose["y"] - zone.world_y) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_high_lateral_near_zone_rollout_at_retrieval_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.041383, "y": -0.601431, "z": 0.05}
    ball_pose = {"x": 3.003489, "y": -0.613377, "z": 0.05}
    robot_pose = {"x": 4.619765, "y": -0.121181, "yaw": -2.417913}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.70
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.12


def test_policy_place_coasts_wide_reel_before_retrieval_edge_when_ball_is_already_moving():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.295343, "y": -0.404532, "z": 0.05}
    ball_pose = {"x": 3.258871, "y": -0.411385, "z": 0.05}
    robot_pose = {"x": 4.944388, "y": -0.109132, "yaw": -2.665015}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.12
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.25


def test_policy_place_reels_latest_low_x_medium_lateral_near_zone_gap_before_release_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.538411, "y": -0.298348, "z": 0.05}
    ball_pose = {"x": 3.505316, "y": -0.306313, "z": 0.05}
    robot_pose = {"x": 4.326316, "y": -0.1167, "yaw": 3.083367}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.018 <= decision.command.linear_x <= 0.020
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_keeps_low_x_medium_lateral_reel_across_duplicate_trace_frame():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.164722, "y": -0.756148, "z": 0.05}
    ball_pose = {"x": 3.164722, "y": -0.756148, "z": 0.05}
    robot_pose = {"x": 3.954325, "y": -0.401517, "yaw": -3.028405}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.018 <= decision.command.linear_x <= 0.020
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_latest_zero_low_x_extreme_opposed_near_zone_terminal():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.497070, "y": 0.431968, "z": 0.05}
    ball_pose = {"x": 3.453991, "y": 0.445066, "z": 0.05}
    robot_pose = {"x": 4.857794, "y": -0.006922, "yaw": -2.433951}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 1.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.35
    assert 0.38 <= abs(ball_pose["y"] - zone.world_y) <= 0.52
    assert decision.diagnostics["capture_snapshot"]["ball_y_m"] * (ball_pose["y"] - zone.world_y) < 0.0
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.34
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_latest_zero_low_x_opposed_near_zone_escape_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.477122, "y": -0.322679, "z": 0.05}
    ball_pose = {"x": 3.422627, "y": -0.337330, "z": 0.05}
    robot_pose = {"x": 4.847026, "y": 0.012871, "yaw": 2.541040}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.90 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert 1.05 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.15
    assert 0.32 <= abs(ball_pose["y"] - zone.world_y) <= 0.34
    assert decision.diagnostics["capture_snapshot"]["ball_y_m"] * (ball_pose["y"] - zone.world_y) < 0.0
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.30
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.34


def test_policy_place_resteers_latest_zero_negative_lateral_coast_edge():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.529635, "y": -0.308561, "z": 0.05}
    ball_pose = {"x": 3.477122, "y": -0.322679, "z": 0.05}
    robot_pose = {"x": 4.849861, "y": 0.011502, "yaw": 2.762530}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.10 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.20
    assert 0.75 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert 0.30 <= abs(ball_pose["y"] - zone.world_y) <= 0.34
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.34 <= zone_margin_m <= 0.38


def test_policy_place_coasts_latest_zero_near_zone_lateral_edge_before_mouth():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.383940, "y": 0.411791, "z": 0.05}
    ball_pose = {"x": 3.342856, "y": 0.424938, "z": 0.05}
    robot_pose = {"x": 4.790907, "y": -0.004038, "yaw": -3.092580}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.35 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.50
    assert 0.40 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.55
    assert 0.40 <= ball_pose["y"] - zone.world_y <= 0.46
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.25 <= zone_margin_m <= 0.30


def test_policy_place_holds_latest_zero_stale_near_mouth_edge_sample():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.342856, "y": 0.424938, "z": 0.05}
    ball_pose = {"x": 3.342856, "y": 0.424938, "z": 0.05}
    robot_pose = {"x": 4.789376, "y": -0.003739, "yaw": 2.886606}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.45 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.60
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.10
    assert 0.40 <= ball_pose["y"] - zone.world_y <= 0.46
    zone_margin_m = decision.diagnostics["zone_snapshot"]["zone_distance_m"] - zone.retrieval_radius_m
    assert 0.25 <= zone_margin_m <= 0.30


def test_policy_place_holds_mirrored_low_x_extreme_opposed_near_zone_terminal():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.497070, "y": -0.431968, "z": 0.05}
    ball_pose = {"x": 3.453991, "y": -0.445066, "z": 0.05}
    robot_pose = {"x": 4.857794, "y": 0.006922, "yaw": 2.433951}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.85
    assert 1.10 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.35
    assert 0.38 <= abs(ball_pose["y"] - zone.world_y) <= 0.52
    assert decision.diagnostics["capture_snapshot"]["ball_y_m"] * (ball_pose["y"] - zone.world_y) < 0.0
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.34
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_reels_outer_near_zone_moderate_lateral_rollout_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.540507, "y": -0.323511, "z": 0.05}
    ball_pose = {"x": 3.505914, "y": -0.329375, "z": 0.05}
    robot_pose = {"x": 4.867586, "y": -0.104671, "yaw": 3.124557}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.018 <= decision.command.linear_x <= 0.020
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_near_zone_reel_pushes_moderate_lateral_before_visibility_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.358046, "y": 0.577256, "z": 0.05}
    ball_pose = {"x": 3.320644, "y": 0.590285, "z": 0.05}
    robot_pose = {"x": 4.920858, "y": 0.049215, "yaw": 2.976946}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert 0.018 <= decision.command.linear_x <= 0.020
    assert decision.command.angular_z < -0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.55
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.32
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_coasts_high_x_near_zone_edge_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.19051, "y": 0.410466, "z": 0.05}
    ball_pose = {"x": 3.148718, "y": 0.419865, "z": 0.05}
    robot_pose = {"x": 4.951442, "y": 0.010059, "yaw": 2.749263}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.85
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.18


def test_policy_place_holds_latest_zero_high_x_near_edge_after_availability_fix():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.107086, "y": 0.670495, "z": 0.05}
    ball_pose = {"x": 3.070318, "y": 0.683520, "z": 0.05}
    robot_pose = {"x": 4.870168, "y": 0.044933, "yaw": 2.620018}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.65
    assert abs(ball_pose["y"] - zone.world_y) <= 0.72
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.22


def test_policy_place_holds_latest_zero_high_x_escape_edge_after_inside_rollout():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 1.770361, "y": -0.448410, "z": 0.05}
    ball_pose = {"x": 1.724528, "y": -0.455410, "z": 0.05}
    robot_pose = {"x": 4.819610, "y": 0.000922, "yaw": 2.659589}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["ball_motion_m"] <= 0.055
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.08
    assert 2.50 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.60
    assert 1.80 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 1.90
    assert 0.45 <= abs(ball_pose["y"] - zone.world_y) <= 0.47


def test_policy_place_holds_mirrored_high_x_near_edge_after_availability_fix():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.107086, "y": -0.670495, "z": 0.05}
    ball_pose = {"x": 3.070318, "y": -0.683520, "z": 0.05}
    robot_pose = {"x": 4.870168, "y": -0.044933, "yaw": -2.620018}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 0.18
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.40
    assert abs(ball_pose["y"] - zone.world_y) >= 0.65
    assert abs(ball_pose["y"] - zone.world_y) <= 0.72
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.22


def test_policy_place_holds_latest_zero_stale_high_x_near_edge_centered_world():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.310973, "y": -0.037442, "z": 0.05}
    ball_pose = {"x": 3.310973, "y": -0.037442, "z": 0.05}
    robot_pose = {"x": 5.246527, "y": -0.009776, "yaw": 2.897721}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z >= 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.80 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert 0.40 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert abs(ball_pose["y"] - zone.world_y) <= 0.12
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.12
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.18


def test_policy_place_holds_mirrored_stale_high_x_near_edge_centered_world():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.310973, "y": 0.037442, "z": 0.05}
    ball_pose = {"x": 3.310973, "y": 0.037442, "z": 0.05}
    robot_pose = {"x": 5.246527, "y": 0.009776, "yaw": -2.897721}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z <= -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] == 0.0
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.80 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert 0.40 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert abs(ball_pose["y"] - zone.world_y) <= 0.12
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m + 0.12
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.18


def test_policy_place_near_zone_keepup_handles_low_lateral_high_x_gap_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.52372, "y": -0.356894, "z": 0.05}
    ball_pose = {"x": 3.483811, "y": -0.364245, "z": 0.05}
    robot_pose = {"x": 4.968986, "y": -0.108068, "yaw": -3.011116}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert 0.014 <= decision.command.linear_x <= 0.022
    assert abs(decision.command.angular_z) <= 0.45
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.05
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_near_zone_keepup_covers_low_x_rollout_gap_before_release_loss():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.583252, "y": -0.150942, "z": 0.05}
    ball_pose = {"x": 3.549544, "y": -0.152589, "z": 0.05}
    robot_pose = {"x": 4.563013, "y": -0.069812, "yaw": -3.014752}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.022
    assert decision.command.angular_z < 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.05
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_near_zone_keepup_past_one_point_eight_x_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.240708, "y": -0.65315, "z": 0.05}
    ball_pose = {"x": 3.210463, "y": -0.6621, "z": 0.05}
    robot_pose = {"x": 4.972427, "y": -0.1554, "yaw": -2.921823}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert 0.014 <= decision.command.linear_x <= 0.022
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.80
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] > zone.retrieval_radius_m
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.46


def test_policy_place_holds_moving_ball_centered_inside_retrieval_before_sweeping():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.083187, "y": 0.278983, "z": 0.05}
    robot_pose = {"x": 3.525153, "y": 0.885092, "yaw": -2.125155}
    previous_ball_pose = {"x": 3.106561, "y": 0.307271, "z": 0.05}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.0
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_place_recenters_high_x_moving_rollout_inside_retrieval_before_push_through():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.004889, "y": -0.349347, "z": 0.05}
    ball_pose = {"x": 2.964278, "y": -0.355296, "z": 0.05}
    robot_pose = {"x": 4.774456, "y": -0.085942, "yaw": 3.088067}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x > 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.18
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 1.40
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.80
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.70
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_place_recenters_latest_zero_inside_retrieval_line_slide():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.040445, "y": -0.321665, "z": 0.05}
    ball_pose = {"x": 2.999010, "y": -0.327499, "z": 0.05}
    robot_pose = {"x": 4.748049, "y": -0.068458, "yaw": -3.073667}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x > 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.18
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] >= 1.40
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.80
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.70
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_place_holds_latest_zero_high_x_negative_edge_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.051366, "y": -0.418591, "z": 0.05}
    ball_pose = {"x": 3.002925, "y": -0.429871, "z": 0.05}
    robot_pose = {"x": 4.843193, "y": -0.008037, "yaw": -3.099394}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.035
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.25
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert 0.38 <= abs(ball_pose["y"] - zone.world_y) <= 0.55
    assert 0.50 <= decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.75
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_place_recenters_latest_zero_inside_retrieval_by_world_line_before_recapture_retry():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.085315, "y": -0.291803, "z": 0.05}
    ball_pose = {"x": 3.030399, "y": -0.295697, "z": 0.05}
    robot_pose = {"x": 3.832284, "y": -0.197219, "yaw": 2.877512}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.22
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.023
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert 0.50 <= decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.80
    assert 0.65 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 0.80
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.75
    assert 0.26 <= abs(ball_pose["y"] - zone.world_y) <= 0.36


def test_policy_place_holds_moving_high_lateral_ball_inside_retrieval_before_capture_fallback():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 2.648292, "y": -0.247354, "z": 0.05}
    robot_pose = {"x": 3.502433, "y": 0.879579, "yaw": 2.661930}
    previous_ball_pose = {"x": 2.672920, "y": -0.217547, "z": 0.05}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.0
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] < 0.30
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 1.0
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True


def test_policy_place_holds_latest_plus45_mid_lateral_roll_inside_retrieval():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.929233, "y": 0.117009, "z": 0.05}
    ball_pose = {"x": 2.904781, "y": 0.088987, "z": 0.05}
    robot_pose = {"x": 3.46805, "y": 0.817685, "yaw": -2.850329}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.58
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.45 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70


def test_policy_place_holds_latest_zero_centerline_rollthrough_before_yaw_snowball():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.502, "y": 0.134, "z": 0.05}
    ball_pose = {"x": 2.453, "y": 0.136, "z": 0.05}
    robot_pose = {"x": 4.549, "y": -0.012, "yaw": -3.108}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.20
    assert abs(ball_pose["y"] - zone.world_y) <= 0.20


def test_policy_place_holds_latest_zero_low_world_lateral_before_reorient_spin():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.033, "y": 0.156, "z": 0.05}
    ball_pose = {"x": 1.985, "y": 0.158, "z": 0.05}
    robot_pose = {"x": 4.549, "y": -0.012, "yaw": -2.176}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_hold"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.55
    assert abs(ball_pose["y"] - zone.world_y) <= 0.20


def test_policy_place_resteers_latest_zero_negative_world_inside_retrieval_by_zone_line():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.158, "y": -0.180, "z": 0.05}
    ball_pose = {"x": 3.101, "y": -0.188, "z": 0.05}
    robot_pose = {"x": 4.786175, "y": 0.012802, "yaw": -2.828038}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x >= 0.0
    assert decision.command.angular_z > 0.20
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.80
    assert -0.34 <= ball_pose["y"] - zone.world_y <= -0.14


def test_policy_place_shepherds_zero_rollthrough_after_ball_crosses_zone_center():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 1.979704, "y": 0.073533, "z": 0.05}
    ball_pose = {"x": 1.935657, "y": 0.075283, "z": 0.05}
    robot_pose = {"x": 3.961225, "y": -0.015208, "yaw": -2.990875}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.12
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 1.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.60


def test_policy_place_recenters_latest_zero_inside_retrieval_lateral_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.547918, "y": 0.333909, "z": 0.05}
    ball_pose = {"x": 2.509207, "y": 0.340186, "z": 0.05}
    robot_pose = {"x": 4.181889, "y": 0.045078, "yaw": -2.165612}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_zone"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.40
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 0.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.25
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) > 1.0


def test_policy_place_recenters_latest_zero_late_inside_retrieval_lateral_drift():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.926303, "y": 0.283516, "z": 0.05}
    ball_pose = {"x": 2.891026, "y": 0.289071, "z": 0.05}
    robot_pose = {"x": 3.993255, "y": 0.078318, "yaw": 2.640572}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < 0.0
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= 0.60
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert 1.00 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.35
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.70
    assert 0.28 <= abs(ball_pose["y"] - zone.world_y) <= 0.38


def test_policy_place_keeps_latest_zero_finish_gap_under_object_control():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.182366, "y": -0.482841, "z": 0.05}
    ball_pose = {"x": 3.147311, "y": -0.489802, "z": 0.05}
    robot_pose = {"x": 4.05454, "y": -0.248286, "yaw": -3.037276}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_recapture_drive"
    assert 0.0 < decision.command.linear_x <= 0.018
    assert decision.command.target_speed_scale == 0.40
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert zone.retrieval_radius_m < decision.diagnostics["zone_snapshot"]["zone_distance_m"]
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.16
    assert decision.diagnostics["capture_snapshot"]["ball_ahead"] is True
    assert decision.diagnostics["capture_snapshot"]["within_recapture_window"] is False
    assert decision.diagnostics["capture_snapshot"]["ball_x_m"] > 0.90
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18


def test_policy_place_resteers_latest_zero_near_mouth_by_world_lateral_after_local_flip():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.426449, "y": 0.459161, "z": 0.05}
    ball_pose = {"x": 3.385675, "y": 0.474269, "z": 0.05}
    robot_pose = {"x": 4.704546, "y": 0.006553, "yaw": 2.650749}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.38
    assert 1.15 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.95
    assert ball_pose["y"] - zone.world_y >= 0.44


def test_policy_place_resteers_latest_zero_low_local_near_mouth_by_world_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.172026, "y": 0.553431, "z": 0.05}
    ball_pose = {"x": 3.131604, "y": 0.568409, "z": 0.05}
    robot_pose = {"x": 4.690089, "y": 0.018092, "yaw": 2.804649}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.20
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.08
    assert ball_pose["y"] - zone.world_y >= 0.50


def test_policy_place_resteers_latest_zero_high_x_near_mouth_by_world_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.206413, "y": 0.455648, "z": 0.05}
    ball_pose = {"x": 3.163730, "y": 0.468886, "z": 0.05}
    robot_pose = {"x": 4.707383, "y": 0.004063, "yaw": 2.936898}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.20
    assert 1.55 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.75
    assert 0.08 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.18
    assert ball_pose["y"] - zone.world_y >= 0.44


def test_policy_place_resteers_latest_zero_high_x_centered_near_mouth_by_world_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 3.136465, "y": 0.490988, "z": 0.05}
    ball_pose = {"x": 3.097423, "y": 0.503482, "z": 0.05}
    robot_pose = {"x": 4.782296, "y": 0.000061, "yaw": 2.858306}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.04
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.12
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 1.85
    assert abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 0.05
    assert ball_pose["y"] - zone.world_y >= 0.50


def test_policy_place_resteers_latest_zero_inside_edge_by_world_lateral_before_reorient():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.654991, "y": 0.745006, "z": 0.05}
    ball_pose = {"x": 2.612631, "y": 0.760702, "z": 0.05}
    robot_pose = {"x": 4.672649, "y": 0.025044, "yaw": -3.125456}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is False
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.15
    assert ball_pose["y"] - zone.world_y >= 0.65


def test_policy_place_resteers_latest_zero_centered_inside_edge_by_world_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.952151, "y": -0.534560, "z": 0.05}
    ball_pose = {"x": 2.901705, "y": -0.548593, "z": 0.05}
    robot_pose = {"x": 4.832566, "y": 0.013280, "yaw": -2.578946}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.15
    assert ball_pose["y"] - zone.world_y <= -0.50


def test_policy_place_resteers_mirrored_centered_inside_edge_by_world_lateral():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.952151, "y": 0.534560, "z": 0.05}
    ball_pose = {"x": 2.901705, "y": 0.548593, "z": 0.05}
    robot_pose = {"x": 4.832566, "y": -0.013280, "yaw": 2.578946}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is True
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.15
    assert ball_pose["y"] - zone.world_y >= 0.50


def test_policy_place_holds_latest_zero_outside_edge_escape_under_place_control():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.150247, "y": -0.757630, "z": 0.05}
    ball_pose = {"x": 2.103989, "y": -0.770498, "z": 0.05}
    robot_pose = {"x": 4.811632, "y": 0.003548, "yaw": 1.951499}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.20
    assert 2.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 3.20
    assert ball_pose["y"] - zone.world_y <= -0.70


def test_policy_place_holds_mirrored_outside_edge_escape_under_place_control():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.150247, "y": 0.757630, "z": 0.05}
    ball_pose = {"x": 2.103989, "y": 0.770498, "z": 0.05}
    robot_pose = {"x": 4.811632, "y": -0.003548, "yaw": -1.951499}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_near_zone_wide_reel"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z < -0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is False
    assert decision.diagnostics["zone_snapshot"]["zone_distance_m"] <= zone.retrieval_radius_m + 0.20
    assert 2.00 <= abs(decision.diagnostics["capture_snapshot"]["ball_y_m"]) <= 3.20
    assert ball_pose["y"] - zone.world_y >= 0.70


def test_policy_place_resteers_mirrored_inside_edge_by_world_lateral_before_reorient():
    zone = build_zone_spec("corral_single_ball_place")
    previous_ball_pose = {"x": 2.654991, "y": -0.745006, "z": 0.05}
    ball_pose = {"x": 2.612631, "y": -0.760702, "z": 0.05}
    robot_pose = {"x": 4.672649, "y": -0.025044, "yaw": 3.125456}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="place",
        zone=zone,
        previous_ball_pose=previous_ball_pose,
    )

    assert decision.command is not None
    assert decision.raw_command is not None
    assert decision.command.mode == "object_place_inside_retrieval_shepherd"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z > 0.45
    assert decision.command.target_speed_scale == 0.0
    assert decision.diagnostics["smoothing_applied"] is False
    assert decision.diagnostics["guard_rejection_reason"] == ""
    assert decision.diagnostics["ball_motion_m"] > 0.03
    assert decision.diagnostics["zone_snapshot"]["inside_retrieval_corral"] is True
    assert decision.diagnostics["zone_snapshot"]["center_inside_retrieval_corral"] is False
    assert 1.70 <= decision.diagnostics["capture_snapshot"]["ball_x_m"] <= 2.15
    assert ball_pose["y"] - zone.world_y <= -0.65


def test_policy_smooths_command_delta_from_previous_command():
    zone = build_zone_spec("corral_single_ball_place")
    previous = PlaceControlCommand(
        mode="object_capture_push",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.75,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 1.0, "y": 0.0},
        phase="capture",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.command.linear_x == OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS
    assert decision.diagnostics["smoothing_applied"] is True


def test_policy_stops_on_pre_contact_ball_motion_guard():
    zone = build_zone_spec("corral_single_ball_place")

    decision = decide_object_centric_gather_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 1.0, "y": 0.08},
        phase="stage",
        zone=zone,
        previous_ball_pose={"x": 1.0, "y": 0.0},
    )

    assert decision.command is not None
    assert decision.command.mode == "object_policy_ball_motion_guard"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["guard_rejection_reason"] == "ball_motion_guard"
