from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_pre_stage_path_tracker_helpers as tracker  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
ZERO_BALL = {"x": 5.448, "y": 0.0, "z": 0.05}
PLUS45_BALL = {"x": 4.555261, "y": 2.155261, "z": 0.05}


def _decision(robot_pose, ball_pose=ZERO_BALL, *, snapshot=None, previous_waypoint_index=0, ball_motion_m=None, stall_s=0.0):
    return tracker.decide_pre_stage_path_tracker_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot if snapshot is not None else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE),
        previous_waypoint_index=previous_waypoint_index,
        stall_s=stall_s,
        ball_motion_m=ball_motion_m,
    )


def _assert_path_clear(robot_pose, ball_pose):
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)
    waypoints = tracker.build_pre_stage_path_tracker_waypoints(robot_pose, ball_pose, zone=ZONE, snapshot=snapshot)

    assert [waypoint.kind for waypoint in waypoints] == [
        tracker.WAYPOINT_ESCAPE,
        tracker.WAYPOINT_APPROACH,
        tracker.WAYPOINT_PORT,
        tracker.WAYPOINT_YAW_ALIGN,
    ]
    starts = [robot_pose, *[waypoint.pose for waypoint in waypoints[:-1]]]
    for start_pose, waypoint in zip(starts, waypoints):
        clearance_m = tracker._segment_ball_clearance(start_pose, waypoint.pose, ball_pose)
        assert clearance_m is not None
        assert clearance_m >= tracker.DEFAULT_PATH_TRACKER_MIN_BALL_CLEARANCE_M


def test_pre_stage_path_tracker_public_interface_exports_family_and_payload_fields():
    decision = tracker.PreStagePathTrackerDecision(
        active=False,
        waypoint_index=2,
        waypoint_kind="port",
        release_blockers=("yaw_not_aligned",),
        rejection_reasons=("predicted_ball_contact",),
    )

    payload = decision.to_dict()

    assert tracker.PRE_STAGE_PATH_TRACKER_CONTROL_FAMILY == "pre_stage_path_tracker_v1"
    assert payload["active"] is False
    assert payload["waypoint_index"] == 2
    assert payload["waypoint_kind"] == "port"
    assert payload["release_blockers"] == ["yaw_not_aligned"]
    assert payload["rejection_reasons"] == ["predicted_ball_contact"]


def test_path_tracker_stays_inactive_when_handoff_ready():
    decision = _decision({"x": 6.348, "y": 0.0, "yaw": math.pi})

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "pre_stage_handoff_ready"
    assert decision.release_blockers == ()


def test_zero_and_plus45_generate_safe_multi_waypoint_paths():
    _assert_path_clear({"x": 0.0, "y": 0.0, "yaw": 0.0}, ZERO_BALL)
    _assert_path_clear({"x": 0.0, "y": 0.0, "yaw": 0.0}, PLUS45_BALL)


def test_zero_start_selects_non_contacting_path_command():
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0})

    assert decision.active is True
    assert decision.waypoint_index == 0
    assert decision.waypoint_kind == tracker.WAYPOINT_ESCAPE
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_path_tracker"
    assert decision.command.linear_x > 0.0
    assert decision.min_ball_clearance_m is not None
    assert decision.min_ball_clearance_m >= tracker.DEFAULT_PATH_TRACKER_MIN_BALL_CLEARANCE_M
    assert decision.rejection_reasons == ()


def test_plus45_start_improves_goal_side_and_lateral_progress():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, PLUS45_BALL, zone=ZONE)
    decision = _decision(robot_pose, PLUS45_BALL, snapshot=snapshot)

    assert snapshot is not None
    assert decision.active is True
    assert decision.waypoint_kind == tracker.WAYPOINT_ESCAPE
    assert decision.projected_snapshot is not None
    assert decision.projected_snapshot["robot_longitudinal_projection_m"] < snapshot["robot_longitudinal_projection_m"]
    assert decision.projected_snapshot["robot_lateral_error_m"] < snapshot["robot_lateral_error_m"]
    assert decision.rejection_reasons == ()


def test_tracker_advances_waypoints_only_from_measured_progress():
    snapshot = pre_stage_arrival_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, ZERO_BALL, zone=ZONE)
    waypoints = tracker.build_pre_stage_path_tracker_waypoints(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        ZERO_BALL,
        zone=ZONE,
        snapshot=snapshot,
    )
    robot_pose = {**waypoints[0].pose, "yaw": 0.0}
    robot_snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL, zone=ZONE)

    decision = _decision(robot_pose, ZERO_BALL, snapshot=robot_snapshot, previous_waypoint_index=0)

    assert decision.active is True
    assert decision.waypoint_reached is True
    assert decision.waypoint_index == 1
    assert decision.waypoint_kind == tracker.WAYPOINT_APPROACH


def test_tracker_rejects_ball_contacting_port_motion():
    robot_pose = {"x": 5.7, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL, zone=ZONE)
    decision = _decision(robot_pose, ZERO_BALL, snapshot=snapshot, previous_waypoint_index=2)

    assert decision.active is True
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_path_tracker_hold"
    assert decision.accepted_count == 0
    assert decision.rejected_count == 1
    assert tracker.REJECTION_SEGMENT_BALL_CLEARANCE in decision.rejection_reasons


def test_ball_motion_guard_aborts_and_disables_override():
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0}, ball_motion_m=0.051)

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "ball_motion_guard"
    assert decision.release_blockers == ("ball_motion_guard",)
    assert decision.ball_motion_m == pytest.approx(0.051)


def test_final_yaw_alignment_is_yaw_only():
    robot_pose = {"x": 6.348, "y": 0.0, "yaw": math.radians(100.0)}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL, zone=ZONE)
    decision = _decision(robot_pose, ZERO_BALL, snapshot=snapshot, previous_waypoint_index=3)

    assert decision.active is True
    assert decision.waypoint_index == 3
    assert decision.waypoint_kind == tracker.WAYPOINT_YAW_ALIGN
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_path_tracker_yaw_align"
    assert decision.command.linear_x == 0.0
    assert 0.0 < decision.command.angular_z <= tracker.DEFAULT_PATH_TRACKER_YAW_MAX_ANGULAR_Z


def test_release_condition_hands_back_to_baseline_inside_safe_envelope():
    snapshot = {
        "push_direction_yaw_deg": 180.0,
        "pre_stage_pose_world": {"x": 6.348, "y": 0.0},
        "pre_stage_pose_distance_m": 0.42,
        "robot_longitudinal_projection_m": -0.55,
        "robot_lateral_error_m": 0.16,
        "robot_lateral_signed_m": 0.16,
        "yaw_error_deg": 15.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }

    decision = _decision({"x": 6.0, "y": 0.16, "yaw": math.radians(165.0)}, snapshot=snapshot)

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "baseline_safe_release"
    assert decision.release_blockers == ()


def test_waypoint_progress_timeout_holds_command_with_fixed_rejection_reason():
    decision = _decision(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        stall_s=tracker.DEFAULT_PATH_TRACKER_STALL_TIMEOUT_S + 0.1,
    )

    assert decision.active is True
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_path_tracker_hold"
    assert tracker.REJECTION_WAYPOINT_PROGRESS_STALL in decision.rejection_reasons
