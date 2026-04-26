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

import gather_control_failure_audit as audit  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _fresh_attempt(*, handoff: bool, reason: str) -> dict[str, object]:
    return {
        "pass": handoff,
        "reason": reason,
        "pre_stage": {
            "pose_reached": handoff,
            "handoff_pass": handoff,
            "pose_world": {"x": 6.348, "y": 0.0},
            "time_s": 19.0,
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


def _case(
    case_id: str,
    *,
    mission_root: Path | None = None,
    fresh_handoff: bool = False,
    fresh_reason: str = "entered_goal_side_before_capture",
    latest_reason: str = "pre_stage_pose_not_reached",
    latest_handoff: bool | None = None,
    goal_side_count: int = 1,
    mission_verdict: dict[str, object] | None = None,
) -> dict[str, object]:
    latest_handoff_value = fresh_handoff if latest_handoff is None else latest_handoff
    run: dict[str, object] = {
        "pass": False,
        "pre_stage_handoff_pass": fresh_handoff,
        "pre_stage_pose_reached": fresh_handoff,
        "latest_approach_progress": {
            "reason": latest_reason,
            "pre_stage": {"handoff_pass": latest_handoff_value, "pose_reached": latest_handoff_value},
            "stage": {"pose_reached": False, "time_s": 0.0},
        },
        "mission_verdict": mission_verdict or {
            "failure_stage": "pre_stage",
            "failure_reason": "pre_stage_timeout",
            "approach_failure_reason": fresh_reason,
        },
    }
    if mission_root is not None:
        run["mission_root"] = str(mission_root)
    fresh = _fresh_attempt(handoff=fresh_handoff, reason=fresh_reason)
    return {
        "case_id": case_id,
        "run_count": 1,
        "pass_count": 0,
        "promotion_gate_pass": False,
        "fresh_attempt_approach": fresh,
        "pre_stage_handoff_pass": fresh_handoff,
        "pre_stage_pose_reached": fresh_handoff,
        "entered_goal_side_before_capture_count": goal_side_count,
        "runs": [run],
    }


def _matrix_summary(
    tmp_path: Path,
    name: str,
    *,
    family: str,
    cases: list[dict[str, object]],
) -> Path:
    return _write_json(
        tmp_path / f"{name}.json",
        {
            "type": "gather_goal_side_matrix",
            "campaign_id": name,
            "gather_control_family": family,
            "case_pass_count": 0,
            "promotion_gate_pass": False,
            "cases": cases,
        },
    )


def test_parse_branch_spec_accepts_name_path_and_rejects_malformed():
    assert audit.parse_branch_spec("nav2_reacquire_v1=summary.json") == (
        "nav2_reacquire_v1",
        Path("summary.json"),
    )

    for spec in ("nav2_reacquire_v1", "=summary.json", "nav2_reacquire_v1="):
        with pytest.raises(argparse.ArgumentTypeError):
            audit.parse_branch_spec(spec)


def test_failure_audit_summarizes_primary_cases_and_fixed_recommendation(tmp_path: Path):
    region_path = _matrix_summary(
        tmp_path,
        "region",
        family="region_funnel_v1",
        cases=[
            _case("plus45", mission_root=tmp_path / "region_plus45"),
            _case("zero", mission_root=tmp_path / "region_zero"),
            _case("minus45", mission_root=tmp_path / "region_minus45"),
        ],
    )
    nav2_path = _matrix_summary(
        tmp_path,
        "nav2",
        family="nav2_reacquire_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "nav2_zero"),
            _case("plus45", mission_root=tmp_path / "nav2_plus45"),
        ],
    )

    summary = audit.build_failure_audit_summary(
        campaign_id="failure_audit_test",
        branch_specs=[("region_funnel_v1", region_path), ("nav2_reacquire_v1", nav2_path)],
    )

    assert summary["recommended_next_action"] == audit.RECOMMENDED_RETIRE_AND_DESIGN
    region = summary["branches"][0]
    assert region["case_order"][:3] == ["zero", "plus45", "minus45"]
    assert [case["case_id"] for case in region["cases"][:2]] == ["zero", "plus45"]
    assert region["primary_pre_stage_handoff_pass"] == {"zero": False, "plus45": False}
    assert "pre_stage_handoff_blocked" in region["failure_labels"]
    assert "goal_side_persistent" in region["failure_labels"]


def test_failure_audit_recommends_next_architecture_when_all_current_candidates_blocked(tmp_path: Path):
    region_path = _matrix_summary(
        tmp_path,
        "region",
        family="region_funnel_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "region_zero"),
            _case("plus45", mission_root=tmp_path / "region_plus45"),
        ],
    )
    nav2_path = _matrix_summary(
        tmp_path,
        "nav2",
        family="nav2_reacquire_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "nav2_zero"),
            _case("plus45", mission_root=tmp_path / "nav2_plus45"),
        ],
    )
    constrained_path = _matrix_summary(
        tmp_path,
        "constrained",
        family="constrained_local_planner_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "constrained_zero"),
            _case("plus45", mission_root=tmp_path / "constrained_plus45"),
        ],
    )
    docking_path = _matrix_summary(
        tmp_path,
        "docking",
        family="docking_reacquire_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "docking_zero"),
            _case("plus45", mission_root=tmp_path / "docking_plus45"),
        ],
    )
    handoff_yaw_path = _matrix_summary(
        tmp_path,
        "handoff_yaw",
        family="handoff_yaw_servo_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "handoff_yaw_zero"),
            _case("plus45", mission_root=tmp_path / "handoff_yaw_plus45"),
        ],
    )

    summary = audit.build_failure_audit_summary(
        campaign_id="failure_audit_test",
        branch_specs=[
            ("region_funnel_v1", region_path),
            ("nav2_reacquire_v1", nav2_path),
            ("constrained_local_planner_v1", constrained_path),
            ("docking_reacquire_v1", docking_path),
            ("handoff_yaw_servo_v1", handoff_yaw_path),
        ],
    )

    assert summary["recommended_next_action"] == audit.RECOMMENDED_RETIRE_BLOCKED_AND_DEFINE_REQUIREMENTS
    assert "constrained_local_planner_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "docking_reacquire_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "handoff_yaw_servo_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    handoff_branch = next(branch for branch in summary["branches"] if branch["branch_name"] == "handoff_yaw_servo_v1")
    assert "handoff_yaw_servo_zero_plus45_pre_stage_handoff_blocked" in handoff_branch["failure_labels"]


def test_failure_audit_does_not_final_closeout_without_handoff_yaw_candidate(tmp_path: Path):
    branch_specs = []
    for name in ("region_funnel_v1", "nav2_reacquire_v1", "constrained_local_planner_v1", "docking_reacquire_v1"):
        path = _matrix_summary(
            tmp_path,
            name,
            family=name,
            cases=[
                _case("zero", mission_root=tmp_path / f"{name}_zero"),
                _case("plus45", mission_root=tmp_path / f"{name}_plus45"),
            ],
        )
        branch_specs.append((name, path))

    summary = audit.build_failure_audit_summary(
        campaign_id="failure_audit_test",
        branch_specs=branch_specs,
    )

    assert summary["recommended_next_action"] != audit.RECOMMENDED_RETIRE_BLOCKED_AND_DEFINE_REQUIREMENTS


def test_nav2_timeout_and_ball_contact_are_extracted_from_state_history(tmp_path: Path):
    mission_root = tmp_path / "nav2_zero"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "event_type": "nav2_reacquire_dispatch",
                "attempt": 1,
                "ball_pose": {"x": 5.448, "y": 0.0},
            },
            {
                "event_type": "nav2_reacquire_complete",
                "attempt": 1,
                "ball_pose": {"x": 5.51, "y": 0.0},
                "nav2_dispatch_status": "goal_result_timeout",
                "nav2_result": {"dispatch_status": "goal_result_timeout"},
                "pre_stage_at_completion": {"pre_stage_pose_reached": False},
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "nav2",
        family="nav2_reacquire_v1",
        cases=[_case("zero", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "nav2_goal_timeout" in case["failure_labels"]
    assert "ball_contact_during_reacquire" in case["failure_labels"]
    assert "post_reacquire_not_handoff_ready" in case["failure_labels"]
    assert case["nav2_debug"]["nav2_dispatch_count"] == 1
    assert case["nav2_debug"]["nav2_goal_timeout_count"] == 1
    assert case["nav2_debug"]["ball_drift_max_m"] >= audit.BALL_DRIFT_CONTACT_THRESHOLD_M


def test_stage_timeout_after_prestage_is_classified_from_verdict(tmp_path: Path):
    matrix_path = _matrix_summary(
        tmp_path,
        "nav2",
        family="nav2_reacquire_v1",
        cases=[
            _case(
                "backside180",
                mission_root=tmp_path / "backside180",
                fresh_handoff=True,
                fresh_reason="staging_pose_not_reached",
                latest_reason="staging_pose_not_reached",
                goal_side_count=0,
                mission_verdict={"failure_stage": "stage", "failure_reason": "goal_side_stage_timeout"},
            )
        ],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )

    assert branch["cases"][0]["failure_labels"] == ["stage_timeout_after_prestage"]


def test_missing_state_history_is_recorded_as_missing_evidence(tmp_path: Path):
    mission_root = tmp_path / "nav2_zero_missing"
    mission_root.mkdir(parents=True)
    matrix_path = _matrix_summary(
        tmp_path,
        "nav2",
        family="nav2_reacquire_v1",
        cases=[_case("zero", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert case["state_history_status"] == "missing"
    assert "state_history_missing" in case["missing_evidence"]
    assert "nav2_goal_timeout" not in case["failure_labels"]


def test_constrained_local_planner_debug_rows_emit_local_failure_labels(tmp_path: Path):
    mission_root = tmp_path / "constrained_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "constrained_local_planner_v1",
                "objective_name": "constrained_local_planner",
                "strategy_name": "advance_left",
                "selected_command": {"mode": "constrained_local_pre_stage"},
                "local_planner_release_reason": "",
                "local_planner_ball_motion_m": 0.061,
                "local_planner_min_ball_clearance_m": 0.72,
                "local_planner_rejection_reasons": ["deeper_goal_side"],
                "projected_projection_gain": 0.12,
                "projected_distance_gain": 0.18,
                "projected_lateral_gain": 0.03,
                "pre_stage": {
                    "robot_on_goal_side": True,
                    "robot_longitudinal_projection_m": 4.7,
                    "pre_stage_pose_distance_m": 5.8,
                    "robot_lateral_error_m": 1.6,
                },
                "local_planner_projected_pre_stage": {
                    "robot_on_goal_side": True,
                    "robot_longitudinal_projection_m": 4.5,
                },
            },
            {
                "controller_family": "constrained_local_planner_v1",
                "objective_name": "constrained_local_planner",
                "strategy_name": "advance_left",
                "selected_command": {"mode": "constrained_local_pre_stage"},
                "local_planner_release_reason": "",
                "local_planner_ball_motion_m": 0.0,
                "local_planner_min_ball_clearance_m": 0.71,
                "pre_stage": {
                    "robot_on_goal_side": True,
                    "robot_longitudinal_projection_m": 4.5,
                    "pre_stage_pose_distance_m": 5.6,
                    "robot_lateral_error_m": 1.5,
                },
                "local_planner_projected_pre_stage": {
                    "robot_on_goal_side": True,
                    "robot_longitudinal_projection_m": 4.3,
                },
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "constrained",
        family="constrained_local_planner_v1",
        cases=[_case("plus45", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="constrained_local_planner_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "local_planner_progress_insufficient" in case["failure_labels"]
    assert "local_planner_release_not_reached" in case["failure_labels"]
    assert "local_planner_goal_side_persistent" in case["failure_labels"]
    assert "ball_contact_during_reacquire" in case["failure_labels"]
    assert case["local_planner_debug"]["local_planner_active_row_count"] == 2
    assert case["local_planner_debug"]["local_planner_release_reason_count"] == 0
    assert case["local_planner_debug"]["local_planner_current_goal_side_row_count"] == 2
    assert case["local_planner_debug"]["local_planner_observed_projection_reduction_m"] == 0.2
    assert case["local_planner_debug"]["local_planner_rejection_reasons"] == ["deeper_goal_side"]


def test_constrained_local_labels_are_branch_scoped(tmp_path: Path):
    mission_root = tmp_path / "region_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "constrained_local_planner_v1",
                "objective_name": "constrained_local_planner",
                "strategy_name": "advance_left",
                "selected_command": {"mode": "constrained_local_pre_stage"},
                "pre_stage": {"robot_on_goal_side": True},
                "local_planner_projected_pre_stage": {"robot_on_goal_side": True},
            }
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "region",
        family="region_funnel_v1",
        cases=[_case("plus45", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="region_funnel_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )

    assert "local_planner_progress_insufficient" not in branch["cases"][0]["failure_labels"]
    assert "local_planner_release_not_reached" not in branch["cases"][0]["failure_labels"]
    assert "local_planner_goal_side_persistent" not in branch["cases"][0]["failure_labels"]


def test_docking_debug_rows_emit_docking_failure_labels(tmp_path: Path):
    mission_root = tmp_path / "docking_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "docking_reacquire_v1",
                "objective_name": "docking_reacquire",
                "docking_reacquire_strategy_name": "yaw_then_pocket",
                "selected_command": {"mode": "docking_reacquire_pre_stage"},
                "docking_reacquire_release_reason": "",
                "docking_reacquire_release_blockers": ["yaw_not_aligned"],
                "docking_reacquire_ball_motion_m": 0.0,
                "docking_reacquire_handoff_ready_measured": False,
                "docking_reacquire_handoff_ready_projected": False,
                "docking_reacquire_projected_pre_stage": {
                    "pre_stage_pose_reached": False,
                    "pre_stage_pose_distance_m": 1.2,
                },
                "pre_stage": {
                    "handoff_pass": False,
                    "pre_stage_pose_distance_m": 1.8,
                },
            },
            {
                "controller_family": "docking_reacquire_v1",
                "objective_name": "docking_reacquire",
                "docking_reacquire_strategy_name": "yaw_then_pocket",
                "selected_command": {"mode": "docking_reacquire_pre_stage"},
                "docking_reacquire_release_reason": "",
                "docking_reacquire_release_blockers": ["yaw_not_aligned"],
                "docking_reacquire_ball_motion_m": 0.012,
                "docking_reacquire_handoff_ready_measured": False,
                "docking_reacquire_handoff_ready_projected": False,
                "docking_reacquire_projected_pre_stage": {"pre_stage_pose_distance_m": 1.0},
                "pre_stage": {"pre_stage_pose_distance_m": 1.6},
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "docking",
        family="docking_reacquire_v1",
        cases=[_case("plus45", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="docking_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "docking_release_not_reached" in case["failure_labels"]
    assert "docking_handoff_yaw_not_aligned" in case["failure_labels"]
    assert "docking_progress_insufficient" in case["failure_labels"]
    assert "ball_contact_during_reacquire" not in case["failure_labels"]
    assert case["docking_debug"]["docking_active_row_count"] == 2
    assert case["docking_debug"]["docking_release_reason_count"] == 0
    assert case["docking_debug"]["docking_release_blockers"] == ["yaw_not_aligned"]
    assert case["docking_debug"]["docking_strategy_counts"] == {"yaw_then_pocket": 2}
    assert case["docking_debug"]["docking_measured_handoff_not_ready_count"] >= 2
    assert case["docking_debug"]["docking_projected_handoff_not_ready_count"] >= 2
    assert case["docking_debug"]["docking_handoff_yaw_blocker_count"] >= 2
    assert case["docking_debug"]["docking_observed_distance_reduction_m"] == 0.2
    assert case["docking_debug"]["docking_projected_distance_min_m"] == 1.0
    assert case["docking_debug"]["docking_max_ball_motion_m"] == 0.012


def test_handoff_yaw_servo_rows_emit_divergence_labels(tmp_path: Path):
    mission_root = tmp_path / "handoff_yaw_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "handoff_yaw_servo_v1",
                "objective_name": "handoff_yaw_servo",
                "strategy_name": "handoff_yaw_servo",
                "selected_command": {"mode": "handoff_yaw_servo_pre_stage"},
                "handoff_yaw_servo_active": True,
                "handoff_yaw_servo_release_reason": "",
                "handoff_yaw_servo_release_blockers": [],
                "handoff_yaw_servo_yaw_error_deg": 64.0,
                "handoff_yaw_servo_angular_z": 0.45,
                "handoff_yaw_servo_ball_motion_m": 0.0,
                "handoff_yaw_servo_handoff_ready_measured": False,
                "handoff_yaw_servo_handoff_ready_projected": False,
                "handoff_yaw_servo_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage": {"pre_stage_pose_reached": False, "handoff_pass": False},
            },
            {
                "controller_family": "handoff_yaw_servo_v1",
                "objective_name": "handoff_yaw_servo",
                "strategy_name": "handoff_yaw_servo",
                "selected_command": {"mode": "handoff_yaw_servo_pre_stage"},
                "handoff_yaw_servo_active": True,
                "handoff_yaw_servo_release_reason": "",
                "handoff_yaw_servo_release_blockers": [],
                "handoff_yaw_servo_yaw_error_deg": 38.0,
                "handoff_yaw_servo_angular_z": 0.32,
                "handoff_yaw_servo_ball_motion_m": 0.01,
                "handoff_yaw_servo_handoff_ready_measured": False,
                "handoff_yaw_servo_handoff_ready_projected": False,
                "handoff_yaw_servo_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage": {"pre_stage_pose_reached": False, "handoff_pass": False},
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "handoff_yaw",
        family="handoff_yaw_servo_v1",
        cases=[
            _case(
                "plus45",
                mission_root=mission_root,
                latest_reason="capture_entry_timeout",
                latest_handoff=True,
            )
        ],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="handoff_yaw_servo_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "fresh_latest_handoff_divergence" in case["failure_labels"]
    assert "late_retry_handoff_not_promotion_ready" in case["failure_labels"]
    assert "ball_contact_during_reacquire" not in case["failure_labels"]
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_active_row_count"] == 2
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_release_reason_count"] == 0
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_strategy_counts"] == {
        "handoff_yaw_servo": 2
    }
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_measured_handoff_not_ready_count"] == 2
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_projected_handoff_not_ready_count"] == 2
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_yaw_error_max_deg"] == 64.0
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_yaw_error_min_deg"] == 38.0
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_max_abs_angular_z"] == 0.45
    assert case["handoff_yaw_servo_debug"]["handoff_yaw_servo_max_ball_motion_m"] == 0.01


def test_write_failure_audit_bundle_writes_summary_and_scorecard(tmp_path: Path):
    matrix_path = _matrix_summary(
        tmp_path,
        "region",
        family="region_funnel_v1",
        cases=[_case("zero", mission_root=tmp_path / "region_zero")],
    )
    summary = audit.build_failure_audit_summary(
        campaign_id="failure_audit_test",
        branch_specs=[("region_funnel_v1", matrix_path)],
    )

    paths = audit.write_failure_audit_bundle(
        repo_root=tmp_path,
        campaign_id="failure_audit_test",
        summary=summary,
    )

    assert paths["summary_path"].exists()
    assert paths["scorecard_path"].exists()
    scorecard = paths["scorecard_path"].read_text(encoding="utf-8")
    assert "# Gather Control Failure Audit" in scorecard
    assert "recommended_next_action" in scorecard
