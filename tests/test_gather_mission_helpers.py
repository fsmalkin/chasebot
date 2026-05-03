from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gather_mission_helpers import CaptureEnvelope  # noqa: E402
from gather_mission_helpers import DEFAULT_MULTI_BALL_SPAWN_RADIUS_M  # noqa: E402
from gather_mission_helpers import DEFAULT_PRE_STAGE_CLOSE_IN_READY_DISTANCE_M  # noqa: E402
from gather_mission_helpers import DEFAULT_PRE_STAGE_CLOSE_IN_READY_LONGITUDINAL_PROJECTION_M  # noqa: E402
from gather_mission_helpers import DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_LATERAL_ERROR_M  # noqa: E402
from gather_mission_helpers import DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_PROJECTION_M  # noqa: E402
from gather_mission_helpers import DEFAULT_PRE_STAGE_ESCAPE_LINEAR_X_MPS  # noqa: E402
from gather_mission_helpers import DEFAULT_PRE_STAGE_ESCAPE_RELEASE_PROJECTION_M  # noqa: E402
from gather_mission_helpers import DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG  # noqa: E402
from gather_mission_helpers import DEFAULT_ZONE_WORLD_X  # noqa: E402
from gather_mission_helpers import DEFAULT_ZONE_WORLD_Y  # noqa: E402
from gather_mission_helpers import approach_side_verdict  # noqa: E402
from gather_mission_helpers import build_gather_targets  # noqa: E402
from gather_mission_helpers import build_scorecard_markdown  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import capture_loss_detected  # noqa: E402
from gather_mission_helpers import capture_snapshot  # noqa: E402
from gather_mission_helpers import capture_entry_snapshot  # noqa: E402
from gather_mission_helpers import clean_retention_pass  # noqa: E402
from gather_mission_helpers import compute_place_command  # noqa: E402
from gather_mission_helpers import compute_capture_command  # noqa: E402
from gather_mission_helpers import compute_capture_entry_command  # noqa: E402
from gather_mission_helpers import compute_stage_command  # noqa: E402
from gather_mission_helpers import compute_pre_stage_command  # noqa: E402
from gather_mission_helpers import first_contact_push_alignment_deg  # noqa: E402
from gather_mission_helpers import final_three_ball_corral_pass  # noqa: E402
from gather_mission_helpers import front_escape_risk  # noqa: E402
from gather_mission_helpers import gather_run_pass  # noqa: E402
from gather_mission_helpers import goal_side_approach_snapshot  # noqa: E402
from gather_mission_helpers import marginal_capture  # noqa: E402
from gather_mission_helpers import pose_delta_m  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402
from gather_mission_helpers import release_ready  # noqa: E402
from gather_mission_helpers import secure_capture  # noqa: E402
from gather_mission_helpers import settled_in_corral_pass  # noqa: E402
from gather_mission_helpers import summarize_runs  # noqa: E402
from gather_mission_helpers import summarize_release_settle_trace  # noqa: E402
from gather_mission_helpers import zone_dwell_complete  # noqa: E402
from gather_mission_helpers import zone_edge_correction_eligible  # noqa: E402
from gather_mission_helpers import zone_snapshot  # noqa: E402


def test_build_gather_targets_for_single_ball_place():
    targets = build_gather_targets("corral_single_ball_place")
    assert len(targets) == 1
    assert targets[0].id == "ball_1"
    assert targets[0].start_visible is False


def test_build_gather_targets_for_three_ball_zone():
    targets = build_gather_targets("gather_three_ball_zone")
    assert [item.id for item in targets] == ["ball_a", "ball_b", "ball_c"]
    assert targets[1].start_visible is True
    for target in targets:
        assert math.hypot(
            target.forward_m - DEFAULT_ZONE_WORLD_X,
            target.lateral_m - DEFAULT_ZONE_WORLD_Y,
        ) == pytest.approx(DEFAULT_MULTI_BALL_SPAWN_RADIUS_M, abs=1e-6)
    assert targets[1].forward_m > targets[0].forward_m
    assert targets[0].lateral_m > 2.0
    assert targets[2].lateral_m < -2.0


def test_capture_snapshot_detects_captured_ball():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 0.11, "y": 0.01}
    snapshot = capture_snapshot(robot_pose, ball_pose, CaptureEnvelope())
    assert snapshot is not None
    assert snapshot.captured is True
    assert snapshot.ball_ahead is True


def test_capture_snapshot_accepts_forward_slip_with_longer_catcher():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 0.23, "y": 0.0}
    snapshot = capture_snapshot(robot_pose, ball_pose, CaptureEnvelope())
    assert snapshot is not None
    assert snapshot.captured is True
    assert snapshot.within_recapture_window is True


def test_capture_entry_snapshot_uses_two_band_ready_corridor():
    zone = build_zone_spec("corral_single_ball_place")
    ready_snapshot = capture_entry_snapshot(
        {"x": 0.46, "y": -0.05, "yaw": 0.0},
        {"x": 1.0, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert ready_snapshot is not None
    assert ready_snapshot["capture_entry_reached"] is True

    off_axis_snapshot = capture_entry_snapshot(
        {"x": 0.45, "y": -0.06, "yaw": 0.0},
        {"x": 1.0, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert off_axis_snapshot is not None
    assert off_axis_snapshot["capture_entry_reached"] is False

    long_gap_snapshot = capture_entry_snapshot(
        {"x": 0.44, "y": -0.04, "yaw": 0.0},
        {"x": 1.0, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert long_gap_snapshot is not None
    assert long_gap_snapshot["capture_entry_reached"] is False


def test_capture_entry_snapshot_accepts_plus45_finish_band_and_rejects_adjacent_counterexamples():
    zone = build_zone_spec("corral_single_ball_place")
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    envelope = CaptureEnvelope()

    plus45_ready_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.618, "y": 0.022, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert plus45_ready_snapshot is not None
    assert plus45_ready_snapshot["ball_x_m"] == pytest.approx(0.618, abs=1e-6)
    assert plus45_ready_snapshot["ball_y_m"] == pytest.approx(0.022, abs=1e-6)
    assert plus45_ready_snapshot["bearing_rad"] == pytest.approx(math.atan2(0.022, 0.618), abs=1e-6)
    assert plus45_ready_snapshot["capture_entry_reached"] is True

    edge_ready_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.621198, "y": 0.004607, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert edge_ready_snapshot is not None
    assert edge_ready_snapshot["ball_x_m"] == pytest.approx(0.621198, abs=1e-6)
    assert edge_ready_snapshot["ball_y_m"] == pytest.approx(0.004607, abs=1e-6)
    assert edge_ready_snapshot["bearing_rad"] == pytest.approx(math.atan2(0.004607, 0.621198), abs=1e-6)
    assert edge_ready_snapshot["capture_entry_reached"] is True

    final_ready_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.589, "y": 0.015, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert final_ready_snapshot is not None
    assert final_ready_snapshot["ball_x_m"] == pytest.approx(0.589, abs=1e-6)
    assert final_ready_snapshot["ball_y_m"] == pytest.approx(0.015, abs=1e-6)
    assert final_ready_snapshot["bearing_rad"] == pytest.approx(math.atan2(0.015, 0.589), abs=1e-6)
    assert final_ready_snapshot["capture_entry_reached"] is True

    x_only_counterexample_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.626, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert x_only_counterexample_snapshot is not None
    assert x_only_counterexample_snapshot["capture_entry_reached"] is False

    x_counterexample_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.645, "y": 0.006, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert x_counterexample_snapshot is not None
    assert x_counterexample_snapshot["capture_entry_reached"] is False

    off_axis_counterexample_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.597426, "y": 0.097410, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert off_axis_counterexample_snapshot is not None
    assert off_axis_counterexample_snapshot["ball_x_m"] == pytest.approx(0.597426, abs=1e-6)
    assert off_axis_counterexample_snapshot["ball_y_m"] == pytest.approx(0.097410, abs=1e-6)
    assert off_axis_counterexample_snapshot["bearing_rad"] == pytest.approx(math.atan2(0.097410, 0.597426), abs=1e-6)
    assert off_axis_counterexample_snapshot["capture_entry_reached"] is False

    y_counterexample_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.618, "y": 0.0252, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert y_counterexample_snapshot is not None
    assert y_counterexample_snapshot["ball_x_m"] == pytest.approx(0.618, abs=1e-6)
    assert y_counterexample_snapshot["ball_y_m"] == pytest.approx(0.0252, abs=1e-6)
    assert y_counterexample_snapshot["capture_entry_reached"] is False

    bearing_counterexample_y = math.tan(0.0405) * 0.60
    bearing_counterexample_snapshot = capture_entry_snapshot(
        robot_pose,
        {"x": 0.60, "y": bearing_counterexample_y, "z": 0.05},
        zone=zone,
        envelope=envelope,
    )
    assert bearing_counterexample_snapshot is not None
    assert abs(bearing_counterexample_snapshot["ball_y_m"]) <= 0.025
    assert bearing_counterexample_snapshot["bearing_rad"] > 0.04
    assert bearing_counterexample_snapshot["capture_entry_reached"] is False


def test_compute_capture_entry_command_uses_centered_close_speedup_and_bounds_off_axis():
    zone = build_zone_spec("corral_single_ball_place")
    ready_command = compute_capture_entry_command(
        {"x": 0.46, "y": -0.05, "yaw": 0.0},
        {"x": 1.0, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert ready_command is not None
    assert ready_command.mode == "capture_entry_ready"

    centered_close_command = compute_capture_entry_command(
        {"x": 0.37, "y": -0.01, "yaw": 0.0},
        {"x": 1.0, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert centered_close_command is not None
    assert centered_close_command.mode == "capture_entry"
    assert centered_close_command.linear_x == pytest.approx(0.07, abs=1e-6)
    assert abs(centered_close_command.angular_z) <= 0.25

    closing_command = compute_capture_entry_command(
        {"x": 0.46, "y": -0.09, "yaw": 0.0},
        {"x": 1.0, "y": 0.0, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert closing_command is not None
    assert closing_command.mode == "capture_entry"
    assert 0.0 < closing_command.linear_x < 0.07
    assert closing_command.angular_z > 0.0

    zero_repair_command = compute_capture_entry_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.70, "y": 0.12, "z": 0.05},
        zone=zone,
        envelope=CaptureEnvelope(),
    )
    assert zero_repair_command is not None
    assert zero_repair_command.mode == "capture_entry"
    assert zero_repair_command.linear_x >= 0.03
    assert zero_repair_command.angular_z > 0.0


def test_zone_edge_correction_eligible_accepts_inside_zone_or_near_zone_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    capture = capture_snapshot({"x": 2.0, "y": 0.0, "yaw": 0.0}, {"x": 2.18, "y": 0.01}, CaptureEnvelope())
    inside_zone_score = zone_snapshot({"x": 2.58, "y": 0.0}, zone)
    near_zone_score = zone_snapshot({"x": 2.68, "y": 0.0}, zone)
    far_zone_score = zone_snapshot({"x": 2.90, "y": 0.0}, zone)

    assert zone_edge_correction_eligible(capture=capture, zone_score=inside_zone_score, zone=zone) is True
    assert zone_edge_correction_eligible(capture=capture, zone_score=near_zone_score, zone=zone) is True
    assert zone_edge_correction_eligible(capture=capture, zone_score=far_zone_score, zone=zone) is False


def test_goal_side_approach_snapshot_enforces_staging_and_goal_side_geometry():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}

    goal_side_snapshot = goal_side_approach_snapshot(
        {"x": 1.12, "y": 0.0, "yaw": 0.0},
        ball_pose,
        zone=zone,
    )
    assert goal_side_snapshot is not None
    assert goal_side_snapshot["robot_on_goal_side"] is True
    assert goal_side_snapshot["entered_goal_side_before_capture"] is True
    assert goal_side_snapshot["approach_failure_reason"] == "entered_goal_side_before_capture"

    staged_snapshot = goal_side_approach_snapshot(
        {"x": 0.55, "y": 0.0, "yaw": 0.0},
        ball_pose,
        zone=zone,
    )
    assert staged_snapshot is not None
    assert staged_snapshot["staging_pose_reached"] is True
    assert staged_snapshot["robot_on_goal_side"] is False
    assert staged_snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.45, abs=1e-6)

    lateral_miss_snapshot = goal_side_approach_snapshot(
        {"x": 0.55, "y": 0.19, "yaw": 0.0},
        ball_pose,
        zone=zone,
    )
    assert lateral_miss_snapshot is not None
    assert lateral_miss_snapshot["staging_pose_reached"] is False
    assert lateral_miss_snapshot["robot_lateral_error_m"] == pytest.approx(0.19, abs=1e-6)

    aligned_command = compute_stage_command({"x": 0.55, "y": 0.0, "yaw": 0.0}, ball_pose, zone=zone)
    assert aligned_command is not None
    assert aligned_command.mode == "stage_ready"

    yaw_miss_command = compute_stage_command({"x": 0.55, "y": 0.0, "yaw": math.radians(30.0)}, ball_pose, zone=zone)
    assert yaw_miss_command is not None
    assert yaw_miss_command.mode == "stage_align"


def test_pre_stage_arrival_snapshot_places_pose_farther_behind_ball_on_push_axis():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}

    snapshot = pre_stage_arrival_snapshot({"x": 0.10, "y": 0.0, "yaw": 0.0}, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["pre_stage_pose_world"]["x"] == pytest.approx(0.1, abs=1e-6)
    assert snapshot["pre_stage_pose_world"]["y"] == pytest.approx(0.0, abs=1e-6)
    assert snapshot["pre_stage_pose_reached"] is True


def test_pre_stage_deep_close_handoff_accepts_zero_fixture_and_rejects_adjacent_counterexamples():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    positive_robot_pose = {"x": 6.226953, "y": -0.165494, "yaw": -2.351599}

    snapshot = pre_stage_arrival_snapshot(positive_robot_pose, ball_pose, zone=zone)
    command = compute_pre_stage_command(positive_robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(0.205038, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.778953, abs=1e-6)
    assert snapshot["robot_lateral_error_m"] == pytest.approx(0.165494, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(45.263302, abs=1e-6)
    assert snapshot["deep_close_pre_stage_handoff"] is True
    assert snapshot["pre_stage_pose_reached"] is True
    assert command is not None
    assert command.mode == "pre_stage_ready"

    yaw_counterexample_pose = {"x": 6.226953, "y": -0.165494, "yaw": math.radians(-132.0)}
    yaw_counterexample_snapshot = pre_stage_arrival_snapshot(yaw_counterexample_pose, ball_pose, zone=zone)
    yaw_counterexample_command = compute_pre_stage_command(yaw_counterexample_pose, ball_pose, zone=zone)
    assert yaw_counterexample_snapshot is not None
    assert yaw_counterexample_snapshot["yaw_error_deg"] == pytest.approx(48.0, abs=1e-6)
    assert yaw_counterexample_snapshot["deep_close_pre_stage_handoff"] is False
    assert yaw_counterexample_snapshot["pre_stage_pose_reached"] is False
    assert yaw_counterexample_command is not None
    assert yaw_counterexample_command.mode == "pre_stage_align"

    lateral_counterexample_pose = {"x": 6.24, "y": -0.19, "yaw": -2.351599}
    lateral_counterexample_snapshot = pre_stage_arrival_snapshot(lateral_counterexample_pose, ball_pose, zone=zone)
    lateral_counterexample_command = compute_pre_stage_command(lateral_counterexample_pose, ball_pose, zone=zone)
    assert lateral_counterexample_snapshot is not None
    assert lateral_counterexample_snapshot["pre_stage_pose_distance_m"] <= 0.22
    assert lateral_counterexample_snapshot["robot_longitudinal_projection_m"] <= -0.75
    assert lateral_counterexample_snapshot["robot_lateral_error_m"] == pytest.approx(0.19, abs=1e-6)
    assert lateral_counterexample_snapshot["deep_close_pre_stage_handoff"] is False
    assert lateral_counterexample_snapshot["pre_stage_pose_reached"] is False
    assert lateral_counterexample_command is not None
    assert lateral_counterexample_command.mode == "pre_stage_align"

    projection_counterexample_pose = {"x": 6.188, "y": -0.12, "yaw": -2.351599}
    projection_counterexample_snapshot = pre_stage_arrival_snapshot(projection_counterexample_pose, ball_pose, zone=zone)
    projection_counterexample_command = compute_pre_stage_command(projection_counterexample_pose, ball_pose, zone=zone)
    assert projection_counterexample_snapshot is not None
    assert projection_counterexample_snapshot["pre_stage_pose_distance_m"] <= 0.22
    assert projection_counterexample_snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.74, abs=1e-6)
    assert projection_counterexample_snapshot["robot_lateral_error_m"] <= 0.18
    assert projection_counterexample_snapshot["yaw_error_deg"] < 47.0
    assert projection_counterexample_snapshot["deep_close_pre_stage_handoff"] is False
    assert projection_counterexample_snapshot["pre_stage_pose_reached"] is False
    assert projection_counterexample_command is not None
    assert projection_counterexample_command.mode == "pre_stage_align"


def test_pre_stage_and_stage_commands_back_off_from_near_front_pose():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}
    near_front_pose = {"x": 0.99, "y": 0.0, "yaw": 0.0}

    pre_stage_command = compute_pre_stage_command(near_front_pose, ball_pose, zone=zone)
    stage_command = compute_stage_command(near_front_pose, ball_pose, zone=zone)

    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x < 0.0
    assert stage_command is not None
    assert stage_command.mode == "stage_escape_goal_side"
    assert stage_command.linear_x < 0.0


def test_stage_close_in_align_handoff_uses_live_plus45_fixture():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.885772, "y": 2.793983, "yaw": -1.952911}

    snapshot = goal_side_approach_snapshot(robot_pose, ball_pose, zone=zone)
    stage_command = compute_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["staging_pose_distance_m"] == pytest.approx(0.32076, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.685351, abs=1e-6)
    assert snapshot["robot_lateral_error_m"] == pytest.approx(0.217938, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(23.106442, abs=1e-6)
    assert stage_command is not None
    assert stage_command.mode == "stage_align"
    assert stage_command.linear_x == 0.0


def test_stage_close_in_align_handoff_rejects_nearby_counterexample_and_keeps_traverse():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.895158, "y": 2.813857, "yaw": -2.079348}

    snapshot = goal_side_approach_snapshot(robot_pose, ball_pose, zone=zone)
    stage_command = compute_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["staging_pose_distance_m"] == pytest.approx(0.341089, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.706041, abs=1e-6)
    assert snapshot["robot_lateral_error_m"] == pytest.approx(0.225354, abs=1e-6)
    assert stage_command is not None
    assert stage_command.mode == "stage_traverse"
    assert stage_command.linear_x > 0.0


def test_pre_stage_escape_goal_side_covers_matrix_start_geometries():
    zone = build_zone_spec("corral_single_ball_place")

    for case_name, ball_pose in (
        ("plus45", {"x": 4.555261, "y": 2.155261}),
        ("zero", {"x": 5.448, "y": 0.0}),
        ("minus45", {"x": 4.555261, "y": -2.155261}),
    ):
        snapshot = pre_stage_arrival_snapshot(
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            ball_pose,
            zone=zone,
        )
        pre_stage_command = compute_pre_stage_command(
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            ball_pose,
            zone=zone,
        )

        assert snapshot is not None
        assert snapshot["robot_on_goal_side"] is True, case_name
        assert pre_stage_command is not None
        assert pre_stage_command.mode == "pre_stage_escape_goal_side", case_name
        assert pre_stage_command.linear_x < 0.0, case_name


def test_pre_stage_escape_goal_side_holds_late_goal_side_orbit_fixtures():
    zone = build_zone_spec("corral_single_ball_place")

    for case_name, robot_pose, ball_pose, projection_m, lateral_m, pre_stage_distance_m in (
        (
            "plus45_bad_release_into_orbit_turn",
            {"x": 3.920514, "y": 2.572954, "yaw": -3.105579},
            {"x": 4.555261, "y": 2.155261, "z": 0.05},
            0.15348,
            -0.744187,
            1.28982,
        ),
        (
            "zero_late_orbit_still_goal_side",
            {"x": 5.404071, "y": -0.854385, "yaw": -0.15306},
            {"x": 5.448, "y": 0.0, "z": 0.05},
            0.043929,
            0.854385,
            1.273175,
        ),
        (
            "minus45_late_orbit_still_goal_side",
            {"x": 3.738419, "y": -2.926491, "yaw": -0.654287},
            {"x": 4.555261, "y": -2.155261, "z": 0.05},
            0.032253,
            1.122936,
            1.45948,
        ),
    ):
        snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
        pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

        assert snapshot is not None
        assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(projection_m, abs=1e-6), case_name
        assert snapshot["robot_lateral_signed_m"] == pytest.approx(lateral_m, abs=1e-6), case_name
        assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(pre_stage_distance_m, abs=1e-6), case_name
        assert snapshot["robot_on_goal_side"] is True, case_name
        assert pre_stage_command is not None
        assert pre_stage_command.mode == "pre_stage_escape_goal_side", case_name
        assert pre_stage_command.linear_x < 0.0, case_name


def test_pre_stage_escape_goal_side_uses_real_reverse_on_last_escape_fixture():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 3.912418, "y": 2.573996, "yaw": 2.849607}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(0.158468, abs=1e-6)
    assert snapshot["robot_lateral_signed_m"] == pytest.approx(-0.750649, abs=1e-6)
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(1.297624, abs=1e-6)
    assert snapshot["robot_on_goal_side"] is True
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x <= DEFAULT_PRE_STAGE_ESCAPE_LINEAR_X_MPS


def test_pre_stage_escape_goal_side_scores_reverse_friendly_flank_on_plus45_live_fixture():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": -0.086543, "y": 0.167842, "yaw": -2.31074}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is True
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(4.687569, abs=1e-6)
    assert snapshot["robot_lateral_signed_m"] == pytest.approx(-1.876934, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(2.60435, abs=1e-6)
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x == pytest.approx(-0.18, abs=1e-6)
    assert pre_stage_command.angular_z == pytest.approx(-0.406477, abs=1e-6)
    assert "behind-ball corridor" in pre_stage_command.rationale


@pytest.mark.parametrize(
    ("robot_pose", "expected_projection_m", "expected_lateral_m", "expected_yaw_deg"),
    [
        (
            {"x": -0.086689, "y": 0.168418, "yaw": -2.268614},
            4.687264,
            1.877444,
            5.017992,
        ),
        (
            {"x": 0.219282, "y": 0.422286, "yaw": -2.454174},
            4.291399,
            1.840602,
            5.613812,
        ),
        (
            {"x": 1.135264, "y": 1.161706, "yaw": -2.471441},
            3.120853,
            1.715754,
            6.603139,
        ),
        (
            {"x": 0.599158, "y": 0.651349, "yaw": -2.570035},
            3.860814,
            1.733961,
            12.252159,
        ),
        (
            {"x": 0.750224, "y": 0.751473, "yaw": -2.626576},
            3.683195,
            1.697939,
            15.491719,
        ),
    ],
)
def test_pre_stage_escape_goal_side_keeps_direct_reverse_committed_on_first_attempt_plus45_stall_samples(
    robot_pose,
    expected_projection_m,
    expected_lateral_m,
    expected_yaw_deg,
):
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is True
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(expected_projection_m, abs=1e-6)
    assert snapshot["robot_lateral_error_m"] == pytest.approx(expected_lateral_m, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(expected_yaw_deg, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] >= DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_PROJECTION_M
    assert snapshot["robot_lateral_error_m"] >= DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_LATERAL_ERROR_M
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x == pytest.approx(-0.18, abs=1e-6)
    assert pre_stage_command.angular_z < 0.0
    assert abs(pre_stage_command.angular_z) >= 0.13
    assert "behind-ball corridor" in pre_stage_command.rationale


def test_pre_stage_escape_goal_side_replaces_stalled_goal_side_orbit():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261}
    stalled_orbit_pose = {"x": 3.636369, "y": 2.85088, "yaw": 0.652304}

    pre_stage_command = compute_pre_stage_command(stalled_orbit_pose, ball_pose, zone=zone)

    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x < 0.0


@pytest.mark.parametrize(
    ("robot_pose", "expected_projection_m", "expected_lateral_m", "expected_distance_m", "expected_yaw_deg"),
    [
        (
            {"x": 2.687926, "y": 2.345621, "yaw": -2.520141},
            1.1858,
            1.45501,
            2.543151,
            9.393443,
        ),
        (
            {"x": 2.671368, "y": 2.336296, "yaw": -2.520368},
            1.204102,
            1.460125,
            2.561096,
            9.406449,
        ),
    ],
)
def test_pre_stage_escape_goal_side_commits_to_direct_reverse_on_repeated_plus45_stall_fixtures(
    robot_pose,
    expected_projection_m,
    expected_lateral_m,
    expected_distance_m,
    expected_yaw_deg,
):
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is True
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(expected_projection_m, abs=1e-6)
    assert snapshot["robot_lateral_error_m"] == pytest.approx(expected_lateral_m, abs=1e-6)
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(expected_distance_m, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(expected_yaw_deg, abs=1e-6)
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x == pytest.approx(-0.18, abs=1e-6)
    assert abs(pre_stage_command.angular_z) > 0.20
    assert "behind-ball corridor" in pre_stage_command.rationale


def test_pre_stage_escape_goal_side_releases_into_reverse_traverse_once_robot_is_behind_ball_boundary():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}
    boundary_release_pose = {"x": 0.9, "y": 0.744187, "yaw": 0.0}

    snapshot = pre_stage_arrival_snapshot(boundary_release_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(boundary_release_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(
        DEFAULT_PRE_STAGE_ESCAPE_RELEASE_PROJECTION_M,
        abs=1e-6,
    )
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_traverse"
    assert pre_stage_command.linear_x < 0.0


def test_pre_stage_reverse_traverse_takes_over_after_escape_release_when_push_yaw_is_ready():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.280945, "y": 2.58892, "yaw": -2.398672}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.112673, abs=1e-6)
    assert snapshot["robot_lateral_signed_m"] == pytest.approx(-0.500614, abs=1e-6)
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(0.933005, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(2.433782, abs=1e-6)
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_traverse"
    assert pre_stage_command.linear_x <= -0.18


def test_pre_stage_escape_goal_side_deepens_projection_after_goal_side_is_cleared():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.22314, "y": 2.534634, "yaw": -2.383103}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.033412, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(1.541744, abs=1e-6)
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_escape_goal_side"
    assert pre_stage_command.linear_x <= -0.12


def test_pre_stage_reverse_traverse_stays_active_when_release_yaw_error_is_slightly_above_ready_gate():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.358021, "y": 2.559774, "yaw": -3.000946}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.146564, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(36.94154, abs=1e-6)
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_traverse"
    assert pre_stage_command.linear_x < 0.0


def test_pre_stage_reverse_traverse_keeps_minimum_backing_speed_near_arrival_gate():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.80045, "y": 2.670995, "yaw": -2.842298}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(0.409393, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.538054, abs=1e-6)
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_traverse"
    assert pre_stage_command.linear_x <= -0.18


def test_pre_stage_arrival_snapshot_marks_close_in_reverse_traverse_finish_as_reached():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.852057, "y": 2.736506, "yaw": -2.97762}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(0.344049, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] == pytest.approx(-0.620869, abs=1e-6)
    assert snapshot["robot_lateral_error_m"] == pytest.approx(0.201136, abs=1e-6)
    assert snapshot["yaw_error_deg"] == pytest.approx(35.605059, abs=1e-6)
    assert snapshot["pre_stage_pose_distance_m"] <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_DISTANCE_M
    assert snapshot["robot_longitudinal_projection_m"] <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_LONGITUDINAL_PROJECTION_M
    assert snapshot["pre_stage_pose_reached"] is True
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_align"


def test_pre_stage_close_in_band_rejects_nearby_yaw_counterexample_and_keeps_traverse():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 4.852057, "y": 2.736506, "yaw": -3.006}

    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    pre_stage_command = compute_pre_stage_command(robot_pose, ball_pose, zone=zone)

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert snapshot["pre_stage_pose_distance_m"] == pytest.approx(0.344049, abs=1e-6)
    assert snapshot["robot_longitudinal_projection_m"] <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_LONGITUDINAL_PROJECTION_M
    assert snapshot["yaw_error_deg"] > 37.0
    assert snapshot["pre_stage_pose_reached"] is False
    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_traverse"


def test_pre_stage_and_stage_align_follow_signed_push_yaw_error():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.8, "y": 0.0}

    pre_stage_aligned_pose = {"x": 4.70, "y": 0.0, "yaw": 0.0}
    stage_aligned_pose = {"x": 4.25, "y": 0.0, "yaw": 0.0}

    pre_stage_command = compute_pre_stage_command(pre_stage_aligned_pose, ball_pose, zone=zone)
    stage_command = compute_stage_command(stage_aligned_pose, ball_pose, zone=zone)

    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_align"
    assert pre_stage_command.angular_z > 0.0

    assert stage_command is not None
    assert stage_command.mode == "stage_align"
    assert stage_command.angular_z > 0.0


def test_pre_stage_prefers_align_once_inside_arrival_radius():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.8, "y": 0.0}
    near_pre_stage_pose = {"x": 4.86, "y": 0.18, "yaw": 0.0}

    pre_stage_command = compute_pre_stage_command(near_pre_stage_pose, ball_pose, zone=zone)

    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_align"
    assert pre_stage_command.angular_z > 0.0


def test_pre_stage_turns_to_recover_yaw_once_it_has_crossed_behind_ball():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 3.8, "y": 0.0}
    crossed_behind_pose = {"x": 4.2, "y": 0.0, "yaw": 0.0}

    pre_stage_command = compute_pre_stage_command(crossed_behind_pose, ball_pose, zone=zone)

    assert pre_stage_command is not None
    assert pre_stage_command.mode == "pre_stage_turn"
    assert pre_stage_command.angular_z != 0.0


def test_first_contact_alignment_verdict_passes_and_fails_on_angle_gate():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}

    aligned_robot_pose = {"x": 0.55, "y": 0.0, "yaw": math.radians(DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG - 5.0)}
    aligned_angle = first_contact_push_alignment_deg(aligned_robot_pose, ball_pose, zone=zone)
    assert aligned_angle == pytest.approx(DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG - 5.0, abs=1e-6)
    assert (
        approach_side_verdict(
            entered_goal_side_before_capture=False,
            staging_pose_reached=True,
            first_contact_push_alignment_deg=aligned_angle,
        )
        == {"pass": True, "reason": ""}
    )

    misaligned_robot_pose = {"x": 0.55, "y": 0.0, "yaw": math.radians(DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG + 5.0)}
    misaligned_angle = first_contact_push_alignment_deg(misaligned_robot_pose, ball_pose, zone=zone)
    assert misaligned_angle == pytest.approx(DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG + 5.0, abs=1e-6)
    assert approach_side_verdict(
        entered_goal_side_before_capture=False,
        staging_pose_reached=True,
        first_contact_push_alignment_deg=misaligned_angle,
    ) == {"pass": False, "reason": "misaligned_first_contact"}

    assert approach_side_verdict(
        entered_goal_side_before_capture=True,
        staging_pose_reached=True,
        first_contact_push_alignment_deg=aligned_angle,
    ) == {"pass": False, "reason": "entered_goal_side_before_capture"}


def test_capture_snapshot_accepts_wider_lateral_capture_with_broader_spur():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 0.16, "y": 0.065}
    snapshot = capture_snapshot(robot_pose, ball_pose, CaptureEnvelope())
    assert snapshot is not None
    assert snapshot.captured is True
    assert snapshot.within_capture_window is True


def test_marginal_capture_detects_ball_near_front_or_side_of_spur():
    centered = capture_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 0.16, "y": 0.0}, CaptureEnvelope())
    front_rail = capture_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 0.07, "y": 0.0}, CaptureEnvelope())
    lateral_bias = capture_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 0.16, "y": 0.05}, CaptureEnvelope())

    assert marginal_capture(centered) is False
    assert marginal_capture(front_rail) is True
    assert marginal_capture(lateral_bias) is True


def test_front_escape_risk_detects_ball_riding_spur_mouth():
    centered = capture_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 0.18, "y": 0.0}, CaptureEnvelope())
    front_loaded = capture_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 0.31, "y": 0.0}, CaptureEnvelope())

    assert secure_capture(centered, CaptureEnvelope()) is True
    assert secure_capture(front_loaded, CaptureEnvelope()) is False
    assert front_escape_risk(centered, CaptureEnvelope()) is False
    assert front_escape_risk(front_loaded, CaptureEnvelope()) is True


def test_capture_snapshot_detects_ball_behind_robot():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": -0.05, "y": 0.02}
    snapshot = capture_snapshot(robot_pose, ball_pose, CaptureEnvelope())
    assert snapshot is not None
    assert snapshot.captured is False
    assert snapshot.ball_ahead is False


def test_zone_snapshot_and_dwell_gate():
    zone = build_zone_spec("corral_single_ball_place")
    score = zone_snapshot({"x": zone.world_x + 0.02, "y": zone.world_y - 0.01}, zone)
    assert score is not None
    assert zone.retrieval_radius_m == 0.762
    assert zone.control_radius_m == 0.20
    assert score.inside_zone is True
    assert score.center_inside_zone is True
    assert score.inside_retrieval_corral is True
    assert score.center_inside_retrieval_corral is True
    assert zone_dwell_complete(
        inside_zone=score.inside_zone,
        zone_entry_monotonic=5.0,
        now_monotonic=6.2,
        dwell_s=zone.dwell_s,
    ) is True
    assert zone_dwell_complete(
        inside_zone=score.inside_zone,
        zone_entry_monotonic=5.8,
        now_monotonic=6.2,
        dwell_s=zone.dwell_s,
    ) is False


def test_zone_snapshot_counts_ball_overlap_as_inside_zone():
    zone = build_zone_spec("corral_single_ball_place")
    score = zone_snapshot({"x": zone.world_x + 0.23, "y": zone.world_y}, zone)
    assert score is not None
    assert score.inside_zone is True
    assert score.center_inside_zone is False
    assert score.inside_retrieval_corral is True
    assert score.center_inside_retrieval_corral is True


def test_zone_snapshot_distinguishes_outer_retrieval_from_inner_control():
    zone = build_zone_spec("corral_single_ball_place")
    score = zone_snapshot({"x": zone.world_x + 0.45, "y": zone.world_y}, zone)
    assert score is not None
    assert score.inside_zone is False
    assert score.center_inside_zone is False
    assert score.inside_retrieval_corral is True
    assert score.center_inside_retrieval_corral is True


def test_capture_loss_detected_after_grace_period():
    assert capture_loss_detected(
        captured_now=False,
        last_captured_monotonic=10.0,
        now_monotonic=10.6,
        loss_grace_s=0.5,
    ) is True
    assert capture_loss_detected(
        captured_now=False,
        last_captured_monotonic=10.0,
        now_monotonic=10.3,
        loss_grace_s=0.5,
    ) is False


def test_compute_place_command_uses_gentle_recapture_when_ball_not_captured():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.35, "y": 0.08},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place_recapture"
    assert command.linear_x > 0.0
    assert command.linear_x < 0.09


def test_compute_capture_command_reseats_ball_when_hard_captured_but_not_secure():
    command = compute_capture_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.31, "y": 0.0},
        envelope=CaptureEnvelope(),
    )
    assert command is not None
    assert command.mode == "capture_seat"
    assert command.linear_x >= 0.05
    assert abs(command.angular_z) <= 0.2


def test_compute_place_command_pushes_faster_when_centered_recapture_is_far_from_zone():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.41, "y": 0.0},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place_recapture"
    assert command.linear_x >= 0.05
    assert command.linear_x < 0.09


def test_compute_place_command_limits_forward_speed_when_ball_is_captured():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.15, "y": 0.0},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place"
    assert command.linear_x > 0.0
    assert command.linear_x <= 0.06


def test_compute_place_command_holds_for_marginal_capture_before_final_push():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.07, "y": 0.05},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place_settle"
    assert command.linear_x == 0.0
    assert abs(command.angular_z) <= 0.18


def test_compute_place_command_holds_when_ball_is_already_inside_retrieval_corral():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 1.85, "y": 0.0, "yaw": 0.0},
        {"x": 2.55, "y": 0.02},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "retrieval_hold"
    assert command.linear_x <= 0.006
    assert abs(command.angular_z) <= 0.18


def test_compute_place_command_eases_forward_when_captured_ball_rides_front_rail():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.31, "y": 0.0},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place_retention"
    assert command.linear_x >= 0.04


def test_compute_place_command_softens_turns_near_zone_edge_during_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 1.070938, "y": 0.007575, "yaw": 0.252782},
        {"x": 1.904784, "y": 0.134964},
        zone=zone,
    )
    assert command is not None
    assert command.linear_x > 0.0
    assert abs(command.angular_z) <= 0.75


def test_compute_place_command_holds_line_for_captured_finish_push_near_zone():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 1.697909, "y": 0.076122, "yaw": 0.113702},
        {"x": 1.920374, "y": 0.126778},
        zone=zone,
    )
    assert command is not None
    assert command.mode in {"place", "place_retention", "retrieval_hold"}
    assert command.linear_x >= 0.0
    assert abs(command.angular_z) <= 0.25


def test_compute_place_command_holds_line_for_recapture_finish_push_near_zone():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 1.710093, "y": 0.077149, "yaw": -0.017281},
        {"x": 1.960979, "y": 0.09264},
        zone=zone,
    )
    assert command is not None
    assert command.mode in {"place", "place_recapture", "place_retention", "retrieval_hold"}
    assert command.linear_x >= 0.0
    assert abs(command.angular_z) <= 0.25


def test_release_ready_requires_captured_ball_in_release_corridor():
    zone = build_zone_spec("corral_single_ball_place")
    capture = capture_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 0.18, "y": 0.0})
    zone_score = zone_snapshot({"x": zone.world_x + 0.015, "y": zone.world_y}, zone)

    assert release_ready(capture=capture, zone_score=zone_score, zone=zone) is True


def test_pose_delta_m_measures_ball_motion():
    assert pose_delta_m({"x": 1.0, "y": 1.0}, {"x": 1.03, "y": 1.04}) == 0.05
    assert pose_delta_m(None, {"x": 1.0, "y": 1.0}) is None


def test_summarize_release_settle_trace_tracks_overshoot_after_zone_entry():
    zone = build_zone_spec("corral_single_ball_place")
    metrics = summarize_release_settle_trace(
        surface_profile="short_turf",
        zone=zone,
        release_recontact_count=1,
        release_samples=[
            {"elapsed_s": 0.0, "zone_distance_m": 0.18, "inside_zone": True, "center_inside_zone": True, "inside_retrieval_corral": True, "center_inside_retrieval_corral": True},
            {"elapsed_s": 0.6, "zone_distance_m": 0.80, "inside_zone": False, "center_inside_zone": False, "inside_retrieval_corral": False, "center_inside_retrieval_corral": False},
            {"elapsed_s": 1.1, "zone_distance_m": 0.19, "inside_zone": True, "center_inside_zone": True, "inside_retrieval_corral": True, "center_inside_retrieval_corral": True},
        ],
    )

    assert metrics.surface_profile == "short_turf"
    assert metrics.max_overshoot_distance_m == 0.038
    assert metrics.final_settle_distance_m == 0.19
    assert metrics.release_recontact_count == 1
    assert metrics.settled_inside_zone is True
    assert metrics.final_inside_retrieval_corral is True
    assert metrics.final_center_inside_zone is True
    assert metrics.ball_stopped_in_corral is False
    assert metrics.rolled_away_after_release is True
    assert metrics.settled_in_corral_pass is False


def test_summarize_release_settle_trace_marks_stopped_ball_centered_in_corral():
    zone = build_zone_spec("corral_single_ball_place")
    metrics = summarize_release_settle_trace(
        surface_profile="short_turf",
        zone=zone,
        release_recontact_count=1,
        release_samples=[
            {"elapsed_s": 0.0, "zone_distance_m": 0.16, "inside_zone": True, "center_inside_zone": True, "inside_retrieval_corral": True, "center_inside_retrieval_corral": True, "ball_motion_m": 0.009},
            {"elapsed_s": 0.6, "zone_distance_m": 0.15, "inside_zone": True, "center_inside_zone": True, "inside_retrieval_corral": True, "center_inside_retrieval_corral": True, "ball_motion_m": 0.008},
            {"elapsed_s": 1.1, "zone_distance_m": 0.14, "inside_zone": True, "center_inside_zone": True, "inside_retrieval_corral": True, "center_inside_retrieval_corral": True, "ball_motion_m": 0.004},
        ],
    )

    assert metrics.final_inside_retrieval_corral is True
    assert metrics.final_center_inside_zone is True
    assert metrics.ball_stopped_in_corral is True
    assert metrics.rolled_away_after_release is False
    assert metrics.settled_in_corral_pass is True


def test_summarize_runs_and_scorecard_markdown():
    runs = [
        {
            "run_index": 1,
            "pass": True,
            "mission_completed_pass": True,
            "surface_profile": "short_turf",
            "handoff_kind": "soft_capture",
            "settle_exit_reason": "settled",
            "settle_no_chase_activated": True,
            "settle_no_chase_exit_reason": "settled",
            "release_gate_blocked_reason": "none",
            "pre_stage_pose_world": {"x": 1.90, "y": 0.0},
            "pre_stage_pose_reached": True,
            "pre_stage_time_s": 2.4,
            "pre_stage_handoff_pass": True,
            "placed_count": 1,
            "capture_loss_count": 0,
            "zone_edge_correction_count": 1,
            "place_controller_reentry_count": 1,
            "post_visit_revisit_count": 0,
            "stopped_with_ball_captured": True,
            "release_started_with_capture": True,
            "clean_retention_pass": True,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "settled_in_corral_pass": True,
            "final_settle_distance_m": 0.14,
            "max_overshoot_distance_m": 0.03,
            "settle_time_s": 1.2,
            "release_recontact_count": 0,
            "mission_time_s": 12.3,
        },
        {
            "run_index": 2,
            "pass": True,
            "mission_completed_pass": True,
            "surface_profile": "short_turf",
            "handoff_kind": "zone_entry",
            "settle_exit_reason": "corrected",
            "settle_no_chase_activated": False,
            "settle_no_chase_exit_reason": "none",
            "release_gate_blocked_reason": "no_secure_capture",
            "pre_stage_pose_world": {"x": 1.90, "y": 0.0},
            "pre_stage_pose_reached": True,
            "pre_stage_time_s": 2.0,
            "pre_stage_handoff_pass": True,
            "placed_count": 1,
            "capture_loss_count": 1,
            "zone_edge_correction_count": 2,
            "place_controller_reentry_count": 1,
            "post_visit_revisit_count": 0,
            "stopped_with_ball_captured": True,
            "release_started_with_capture": True,
            "clean_retention_pass": False,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "settled_in_corral_pass": True,
            "final_settle_distance_m": 0.16,
            "max_overshoot_distance_m": 0.05,
            "settle_time_s": 1.5,
            "release_recontact_count": 1,
            "mission_time_s": 13.7,
        },
    ]
    summary = summarize_runs(runs)
    summary["promotion_gate_pass"] = True
    markdown = build_scorecard_markdown(
        scenario_label="Corral Single Ball Place",
        summary=summary,
        runs=runs,
    )
    assert summary["pass_count"] == 2
    assert summary["settled_in_corral_pass_count"] == 2
    assert summary["final_inside_retrieval_corral_count"] == 2
    assert summary["clean_retention_pass_count"] == 1
    assert summary["clean_retention_fail_count"] == 1
    assert summary["surface_profiles"] == ["short_turf"]
    assert summary["handoff_kinds"] == ["soft_capture", "zone_entry"]
    assert summary["settle_exit_reasons"] == ["corrected", "settled"]
    assert summary["settle_no_chase_activated_count"] == 1
    assert summary["settle_no_chase_exit_reasons"] == ["settled"]
    assert summary["release_gate_blocked_reasons"] == ["no_secure_capture"]
    assert summary["pre_stage_pose_reached_count"] == 2
    assert summary["pre_stage_handoff_pass_count"] == 2
    assert summary["zone_edge_correction_count_total"] == 3
    assert summary["place_controller_reentry_count_total"] == 2
    assert summary["post_visit_revisit_count_total"] == 0
    assert summary["max_overshoot_distance_max_m"] == 0.05
    assert "PASS" in markdown
    assert "Run 01" in markdown
    assert "short_turf" in markdown
    assert "handoff=`soft_capture`" in markdown
    assert "Pre-stage pose reached" in markdown
    assert "settle_exit=`settled`" in markdown
    assert "settle_no_chase=`True`" in markdown
    assert "release_gate=`none`" in markdown
    assert "settled=`True`" in markdown
    assert "clean_retention" in markdown


def test_clean_retention_pass_requires_zero_capture_loss_and_retained_release():
    assert clean_retention_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 0,
            "stopped_with_ball_captured": True,
            "release_started_with_capture": True,
        }
    ) is True
    assert clean_retention_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 1,
            "stopped_with_ball_captured": True,
            "release_started_with_capture": True,
        }
    ) is False


def test_settled_in_corral_pass_requires_retrieval_inside_stop_no_rollaway_and_no_revisit():
    assert settled_in_corral_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 1,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": False,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 0,
        }
    ) is True
    assert settled_in_corral_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 1,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 0,
        }
    ) is True
    assert settled_in_corral_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "final_inside_retrieval_corral": False,
            "final_center_inside_zone": False,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 0,
        }
    ) is False
    assert settled_in_corral_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": False,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 0,
        }
    ) is False
    assert settled_in_corral_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": True,
            "post_visit_revisit_count": 0,
        }
    ) is False
    assert settled_in_corral_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 1,
        }
    ) is False
    assert clean_retention_pass(
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 0,
            "stopped_with_ball_captured": False,
            "release_started_with_capture": True,
        }
    ) is False


def test_final_three_ball_corral_pass_requires_all_targets_inside_stopped_and_no_revisit():
    run = {
        "scenario_id": "gather_three_ball_zone",
        "pass": True,
        "mission_completed_pass": True,
        "final_all_targets_inside_retrieval_corral": True,
        "final_all_targets_stopped": True,
        "final_three_ball_corral_pass": True,
        "post_visit_revisit_count": 0,
    }
    assert final_three_ball_corral_pass(run) is True
    assert gather_run_pass(run) is True
    assert final_three_ball_corral_pass({**run, "final_all_targets_stopped": False, "final_three_ball_corral_pass": False}) is False
    assert gather_run_pass({**run, "post_visit_revisit_count": 1}) is False


def test_summarize_runs_and_scorecard_include_multi_ball_final_audit_fields():
    runs = [
        {
            "run_index": 1,
            "scenario_id": "gather_three_ball_zone",
            "pass": True,
            "mission_completed_pass": True,
            "placed_count": 3,
            "retrieved_count": 3,
            "capture_loss_count": 0,
            "surface_profile": "short_turf",
            "handoff_kind": "zone_entry",
            "settle_exit_reason": "settled",
            "settle_no_chase_activated": True,
            "settle_no_chase_exit_reason": "settled",
            "release_gate_blocked_reason": "none",
            "post_visit_revisit_count": 0,
            "final_all_targets_inside_retrieval_corral": True,
            "final_all_targets_stopped": True,
            "final_three_ball_corral_pass": True,
            "final_corral_audit": {
                "ball_a": {"distance_to_zone_center_m": 0.20, "inside_retrieval_corral": True, "stopped_in_corral": True},
                "ball_b": {"distance_to_zone_center_m": 0.18, "inside_retrieval_corral": True, "stopped_in_corral": True},
                "ball_c": {"distance_to_zone_center_m": 0.21, "inside_retrieval_corral": True, "stopped_in_corral": True},
            },
            "mission_time_s": 32.0,
            "zone_edge_correction_count": 1,
            "place_controller_reentry_count": 0,
            "release_recontact_count": 0,
        },
        {
            "run_index": 2,
            "scenario_id": "gather_three_ball_zone",
            "pass": False,
            "mission_completed_pass": True,
            "placed_count": 3,
            "retrieved_count": 2,
            "capture_loss_count": 0,
            "surface_profile": "short_turf",
            "handoff_kind": "zone_entry",
            "settle_exit_reason": "settled",
            "settle_no_chase_activated": False,
            "settle_no_chase_exit_reason": "none",
            "release_gate_blocked_reason": "no_secure_capture",
            "post_visit_revisit_count": 0,
            "final_all_targets_inside_retrieval_corral": False,
            "final_all_targets_stopped": False,
            "final_three_ball_corral_pass": False,
            "final_corral_audit": {
                "ball_a": {"distance_to_zone_center_m": 0.20, "inside_retrieval_corral": True, "stopped_in_corral": True},
                "ball_b": {"distance_to_zone_center_m": 0.85, "inside_retrieval_corral": False, "stopped_in_corral": False},
                "ball_c": {"distance_to_zone_center_m": 0.21, "inside_retrieval_corral": True, "stopped_in_corral": True},
            },
            "mission_time_s": 38.0,
            "zone_edge_correction_count": 2,
            "place_controller_reentry_count": 0,
            "release_recontact_count": 0,
        },
    ]

    summary = summarize_runs(runs)
    markdown = build_scorecard_markdown(
        scenario_label="Gather Three Ball Zone",
        summary={**summary, "promotion_gate_pass": False},
        runs=runs,
    )

    assert summary["pass_count"] == 1
    assert summary["retrieved_count_avg"] == 2.5
    assert summary["retrieved_count_max"] == 3
    assert summary["final_all_targets_inside_retrieval_corral_count"] == 1
    assert summary["final_all_targets_stopped_count"] == 1
    assert summary["final_three_ball_corral_pass_count"] == 1
    assert summary["final_three_ball_corral_fail_count"] == 1
    assert summary["settle_no_chase_activated_count"] == 1
    assert summary["release_gate_blocked_reasons"] == ["no_secure_capture"]
    assert "Final three-ball corral pass/fail" in markdown
    assert "retrieved_count=`3`" in markdown
