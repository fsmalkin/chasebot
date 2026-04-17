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
from gather_mission_helpers import DEFAULT_ZONE_WORLD_X  # noqa: E402
from gather_mission_helpers import DEFAULT_ZONE_WORLD_Y  # noqa: E402
from gather_mission_helpers import build_gather_targets  # noqa: E402
from gather_mission_helpers import build_scorecard_markdown  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import capture_loss_detected  # noqa: E402
from gather_mission_helpers import capture_snapshot  # noqa: E402
from gather_mission_helpers import clean_retention_pass  # noqa: E402
from gather_mission_helpers import compute_place_command  # noqa: E402
from gather_mission_helpers import compute_capture_command  # noqa: E402
from gather_mission_helpers import final_three_ball_corral_pass  # noqa: E402
from gather_mission_helpers import front_escape_risk  # noqa: E402
from gather_mission_helpers import gather_run_pass  # noqa: E402
from gather_mission_helpers import marginal_capture  # noqa: E402
from gather_mission_helpers import pose_delta_m  # noqa: E402
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


def test_zone_edge_correction_eligible_accepts_inside_zone_or_near_zone_recapture():
    zone = build_zone_spec("corral_single_ball_place")
    capture = capture_snapshot({"x": 2.0, "y": 0.0, "yaw": 0.0}, {"x": 2.18, "y": 0.01}, CaptureEnvelope())
    inside_zone_score = zone_snapshot({"x": 2.58, "y": 0.0}, zone)
    near_zone_score = zone_snapshot({"x": 2.68, "y": 0.0}, zone)
    far_zone_score = zone_snapshot({"x": 2.90, "y": 0.0}, zone)

    assert zone_edge_correction_eligible(capture=capture, zone_score=inside_zone_score, zone=zone) is True
    assert zone_edge_correction_eligible(capture=capture, zone_score=near_zone_score, zone=zone) is True
    assert zone_edge_correction_eligible(capture=capture, zone_score=far_zone_score, zone=zone) is False


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
    assert summary["zone_edge_correction_count_total"] == 3
    assert summary["place_controller_reentry_count_total"] == 2
    assert summary["post_visit_revisit_count_total"] == 0
    assert summary["max_overshoot_distance_max_m"] == 0.05
    assert "PASS" in markdown
    assert "Run 01" in markdown
    assert "short_turf" in markdown
    assert "handoff=`soft_capture`" in markdown
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
