from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_pre_stage_command_authority_audit as audit  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _fresh_attempt(*, handoff: bool = False, reason: str = "entered_goal_side_before_capture") -> dict[str, object]:
    return {
        "pass": handoff,
        "reason": reason,
        "pre_stage": {
            "pose_reached": handoff,
            "handoff_pass": handoff,
            "pose_world": {"x": 6.348, "y": 0.0},
            "time_s": 30.0,
        },
        "stage": {"pose_reached": False, "time_s": 0.0},
        "capture_entry": {
            "entered_goal_side_before_capture": reason == "entered_goal_side_before_capture",
            "failure_reason": reason,
            "pass": False,
            "reached": False,
            "time_s": 0.0,
        },
    }


def _case(case_id: str, *, mission_root: Path | None = None, handoff: bool = False) -> dict[str, object]:
    run: dict[str, object] = {
        "pass": False,
        "pre_stage_handoff_pass": handoff,
        "pre_stage_pose_reached": handoff,
        "mission_verdict": {
            "mission_error": "pre_stage_timeout",
            "failure_stage": "pre_stage",
            "failure_reason": "pre_stage_timeout",
        },
    }
    if mission_root is not None:
        run["mission_root"] = str(mission_root)
    return {
        "case_id": case_id,
        "run_count": 1,
        "pass_count": 0,
        "promotion_gate_pass": False,
        "fresh_attempt_approach": _fresh_attempt(handoff=handoff),
        "pre_stage_handoff_pass": handoff,
        "pre_stage_pose_reached": handoff,
        "runs": [run],
    }


def _matrix_summary(tmp_path: Path, name: str, *, cases: list[dict[str, object]]) -> Path:
    return _write_json(
        tmp_path / f"{name}.json",
        {
            "type": "gather_goal_side_matrix",
            "campaign_id": name,
            "gather_control_family": name,
            "case_pass_count": 0,
            "promotion_gate_pass": False,
            "cases": cases,
        },
    )


def _row(
    *,
    x: float,
    y: float = 0.0,
    yaw: float = 0.0,
    linear_x: float = 0.14,
    angular_z: float = 0.2,
    projection: float = 5.0,
    lateral: float = 0.5,
    distance: float = 6.0,
    yaw_error: float = 180.0,
    waypoint_distance: float = 6.0,
    measured_ready: bool = False,
    ball_motion: float = 0.0,
    clearance: float = 1.0,
    projected_gain: float = 0.16,
) -> dict[str, object]:
    return {
        "attempt": 1,
        "attempt_kind": "initial_visit",
        "phase": "pre_stage",
        "controller_family": "pre_stage_path_tracker_v1",
        "pre_stage": {
            "robot_longitudinal_projection_m": projection,
            "robot_lateral_error_m": lateral,
            "pre_stage_pose_distance_m": distance,
            "yaw_error_deg": yaw_error,
            "pre_stage_pose_reached": measured_ready,
        },
        "pre_stage_path_tracker_measured_handoff_ready": measured_ready,
        "pre_stage_path_tracker_projected_handoff_ready": False,
        "pre_stage_path_tracker_waypoint_distance_m": waypoint_distance,
        "pre_stage_path_tracker_ball_motion_m": ball_motion,
        "pre_stage_path_tracker_min_ball_clearance_m": clearance,
        "projected_projection_gain": projected_gain,
        "projected_distance_gain": projected_gain,
        "projected_lateral_gain": projected_gain,
        "pre_stage_path_tracker_projected_yaw_gain_deg": 8.0,
        "robot_pose": {"x": x, "y": y, "yaw": yaw},
        "selected_command": {
            "linear_x": linear_x,
            "angular_z": angular_z,
            "mode": "pre_stage_path_tracker",
        },
    }


def test_parse_branch_spec_accepts_name_path_and_rejects_malformed():
    assert audit.parse_branch_spec("pre_stage_path_tracker_v1=summary.json") == (
        "pre_stage_path_tracker_v1",
        Path("summary.json"),
    )

    for spec in ("pre_stage_path_tracker_v1", "=summary.json", "pre_stage_path_tracker_v1="):
        with pytest.raises(argparse.ArgumentTypeError):
            audit.parse_branch_spec(spec)


def test_summarizes_state_history_and_selected_command_metrics(tmp_path: Path):
    mission_root = tmp_path / "mission"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            _row(x=0.0, projection=5.0, distance=6.0, waypoint_distance=6.0),
            _row(x=0.2, yaw=0.12, projection=4.7, distance=5.7, waypoint_distance=5.6),
        ],
    )
    summary_path = _matrix_summary(tmp_path, "path_tracker", cases=[_case("zero", mission_root=mission_root)])

    summary = audit.build_command_authority_summary(
        campaign_id="authority_test",
        branch_specs=[("pre_stage_path_tracker_v1", summary_path)],
    )

    case = summary["branches"][0]["cases"][0]
    metrics = case["metrics"]
    assert case["state_history_status"] == "available"
    assert case["fresh_pre_stage_row_count"] == 2
    assert metrics["nonzero_command_count"] == 2
    assert metrics["robot_displacement_m"] == 0.2
    assert metrics["projection_reduction_m"] == 0.3
    assert metrics["motion_realized"] is True
    assert metrics["objective_progress_observed"] is True
    assert metrics["projected_progress_expected"] is True
    assert "timeout_despite_progress" in case["labels"]
    assert summary["recommended_next_action"] == audit.RECOMMEND_ARCHITECTURE_REVIEW


def test_command_realization_limited_when_commands_do_not_move_robot(tmp_path: Path):
    mission_root = tmp_path / "mission"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            _row(x=0.0, yaw=0.0, projection=5.0),
            _row(x=0.01, yaw=0.01, projection=4.99),
        ],
    )
    summary_path = _matrix_summary(tmp_path, "weak_motion", cases=[_case("zero", mission_root=mission_root)])

    summary = audit.build_command_authority_summary(
        campaign_id="authority_test",
        branch_specs=[("pre_stage_path_tracker_v1", summary_path)],
    )

    case = summary["branches"][0]["cases"][0]
    assert "command_realization_limited" in case["labels"]
    assert summary["recommended_next_action"] == audit.RECOMMEND_MOTION_PROBE


def test_geometry_progress_limited_when_motion_realizes_without_objective_progress(tmp_path: Path):
    mission_root = tmp_path / "mission"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            _row(x=0.0, projection=5.0, distance=6.0, waypoint_distance=6.0, projected_gain=0.2),
            _row(x=0.2, projection=4.98, distance=5.98, waypoint_distance=5.98, projected_gain=0.2),
        ],
    )
    summary_path = _matrix_summary(tmp_path, "bad_geometry", cases=[_case("zero", mission_root=mission_root)])

    summary = audit.build_command_authority_summary(
        campaign_id="authority_test",
        branch_specs=[("pre_stage_path_tracker_v1", summary_path)],
    )

    case = summary["branches"][0]["cases"][0]
    assert case["metrics"]["motion_realized"] is True
    assert case["metrics"]["objective_progress_observed"] is False
    assert case["metrics"]["projected_progress_expected"] is True
    assert "geometry_progress_limited" in case["labels"]
    assert summary["recommended_next_action"] == audit.RECOMMEND_ARCHITECTURE_REVIEW


def test_handoff_threshold_mismatch_takes_recommendation_precedence(tmp_path: Path):
    mission_root = tmp_path / "mission"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            _row(x=0.0, measured_ready=True),
            _row(x=0.2, yaw=0.1, measured_ready=True),
        ],
    )
    summary_path = _matrix_summary(tmp_path, "threshold", cases=[_case("zero", mission_root=mission_root)])

    summary = audit.build_command_authority_summary(
        campaign_id="authority_test",
        branch_specs=[("pre_stage_path_tracker_v1", summary_path)],
    )

    case = summary["branches"][0]["cases"][0]
    assert "handoff_threshold_mismatch" in case["labels"]
    assert summary["recommended_next_action"] == audit.RECOMMEND_HANDOFF_GATE_AUDIT


def test_missing_state_history_is_missing_motion_evidence_not_pass_fail(tmp_path: Path):
    mission_root = tmp_path / "missing_mission"
    summary_path = _matrix_summary(tmp_path, "missing", cases=[_case("plus45", mission_root=mission_root)])

    summary = audit.build_command_authority_summary(
        campaign_id="authority_test",
        branch_specs=[("pre_stage_path_tracker_v1", summary_path)],
    )

    case = summary["branches"][0]["cases"][0]
    assert case["state_history_status"] == "missing"
    assert case["missing_evidence"] == [
        "state_history",
        "fresh_pre_stage_rows",
        "selected_command",
        "robot_pose_delta",
    ]
    assert case["labels"] == ["missing_motion_evidence"]
    assert summary["recommended_next_action"] == audit.RECOMMEND_MOTION_PROBE


def test_scorecard_generation_lists_primary_cases(tmp_path: Path):
    mission_root = tmp_path / "mission"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            _row(x=0.0, projection=5.0),
            _row(x=0.2, yaw=0.1, projection=4.7),
        ],
    )
    summary_path = _matrix_summary(
        tmp_path,
        "scorecard",
        cases=[
            _case("minus45", mission_root=mission_root),
            _case("zero", mission_root=mission_root),
        ],
    )
    summary = audit.build_command_authority_summary(
        campaign_id="authority_test",
        branch_specs=[("pre_stage_path_tracker_v1", summary_path)],
    )

    scorecard = audit.build_scorecard_markdown(summary)

    assert "# Gather Pre-Stage Command Authority Audit" in scorecard
    assert "`zero`" in scorecard
    assert "`minus45`" not in scorecard
