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
from gather_mission_helpers import summarize_runs  # noqa: E402
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


def test_summarize_runs_and_scorecard_markdown():
    runs = [
        {"run_index": 1, "pass": True, "placed_count": 1, "capture_loss_count": 0, "mission_time_s": 12.3},
        {"run_index": 2, "pass": True, "placed_count": 1, "capture_loss_count": 1, "mission_time_s": 13.7},
    ]
    summary = summarize_runs(runs)
    summary["promotion_gate_pass"] = True
    markdown = build_scorecard_markdown(
        scenario_label="Corral Single Ball Place",
        summary=summary,
        runs=runs,
    )
    assert summary["pass_count"] == 2
    assert "PASS" in markdown
    assert "Run 01" in markdown
