from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gather_mission_helpers import CaptureEnvelope  # noqa: E402
from gather_mission_helpers import build_gather_targets  # noqa: E402
from gather_mission_helpers import build_scorecard_markdown  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import capture_loss_detected  # noqa: E402
from gather_mission_helpers import capture_snapshot  # noqa: E402
from gather_mission_helpers import compute_place_command  # noqa: E402
from gather_mission_helpers import pose_delta_m  # noqa: E402
from gather_mission_helpers import release_ready  # noqa: E402
from gather_mission_helpers import summarize_runs  # noqa: E402
from gather_mission_helpers import summarize_release_settle_trace  # noqa: E402
from gather_mission_helpers import zone_dwell_complete  # noqa: E402
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
    assert score.inside_zone is True
    assert score.center_inside_zone is True
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
    assert command.linear_x < 0.12


def test_compute_place_command_pushes_faster_when_centered_recapture_is_far_from_zone():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.35, "y": 0.0},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place_recapture"
    assert command.linear_x >= 0.08
    assert command.linear_x < 0.12


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
    assert command.linear_x <= 0.07


def test_compute_place_command_pushes_faster_when_captured_ball_rides_front_rail():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 0.22, "y": 0.0},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place"
    assert command.linear_x >= 0.08
    assert command.linear_x < 0.12


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
    assert command.mode == "place"
    assert command.linear_x >= 0.04
    assert abs(command.angular_z) <= 0.25


def test_compute_place_command_holds_line_for_recapture_finish_push_near_zone():
    zone = build_zone_spec("corral_single_ball_place")
    command = compute_place_command(
        {"x": 1.710093, "y": 0.077149, "yaw": -0.017281},
        {"x": 1.960979, "y": 0.09264},
        zone=zone,
    )
    assert command is not None
    assert command.mode == "place_recapture"
    assert command.linear_x >= 0.018
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
            {"elapsed_s": 0.0, "zone_distance_m": 0.18, "inside_zone": True, "center_inside_zone": True},
            {"elapsed_s": 0.6, "zone_distance_m": 0.26, "inside_zone": False, "center_inside_zone": False},
            {"elapsed_s": 1.1, "zone_distance_m": 0.19, "inside_zone": True, "center_inside_zone": True},
        ],
    )

    assert metrics.surface_profile == "short_turf"
    assert metrics.max_overshoot_distance_m == 0.06
    assert metrics.final_settle_distance_m == 0.19
    assert metrics.release_recontact_count == 1
    assert metrics.settled_inside_zone is True


def test_summarize_runs_and_scorecard_markdown():
    runs = [
        {
            "run_index": 1,
            "pass": True,
            "surface_profile": "short_turf",
            "placed_count": 1,
            "capture_loss_count": 0,
            "final_settle_distance_m": 0.14,
            "max_overshoot_distance_m": 0.03,
            "settle_time_s": 1.2,
            "release_recontact_count": 0,
            "mission_time_s": 12.3,
        },
        {
            "run_index": 2,
            "pass": True,
            "surface_profile": "short_turf",
            "placed_count": 1,
            "capture_loss_count": 1,
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
    assert summary["surface_profiles"] == ["short_turf"]
    assert summary["max_overshoot_distance_max_m"] == 0.05
    assert "PASS" in markdown
    assert "Run 01" in markdown
    assert "short_turf" in markdown
