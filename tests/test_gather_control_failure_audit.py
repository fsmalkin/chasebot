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
    fsm_path = _matrix_summary(
        tmp_path,
        "pre_stage_fsm",
        family="pre_stage_reacquire_fsm_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "pre_stage_fsm_zero"),
            _case("plus45", mission_root=tmp_path / "pre_stage_fsm_plus45"),
        ],
    )
    path_tracker_path = _matrix_summary(
        tmp_path,
        "pre_stage_path_tracker",
        family="pre_stage_path_tracker_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "pre_stage_path_tracker_zero"),
            _case("plus45", mission_root=tmp_path / "pre_stage_path_tracker_plus45"),
        ],
    )
    trajectory_owner_path = _matrix_summary(
        tmp_path,
        "pre_stage_trajectory_owner",
        family="pre_stage_trajectory_owner_v1",
        cases=[
            _case("zero", mission_root=tmp_path / "pre_stage_trajectory_owner_zero"),
            _case("plus45", mission_root=tmp_path / "pre_stage_trajectory_owner_plus45"),
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
            ("pre_stage_reacquire_fsm_v1", fsm_path),
            ("pre_stage_path_tracker_v1", path_tracker_path),
            ("pre_stage_trajectory_owner_v1", trajectory_owner_path),
        ],
    )

    assert summary["recommended_next_action"] == audit.RECOMMENDED_RETIRE_BLOCKED_AND_DESIGN_NAV2_FOLLOW_PATH
    assert "constrained_local_planner_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "docking_reacquire_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "handoff_yaw_servo_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "pre_stage_reacquire_fsm_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "pre_stage_path_tracker_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    assert "pre_stage_trajectory_owner_v1_zero_plus45_pre_stage_handoff_blocked" in summary["blocking_reasons"]
    handoff_branch = next(branch for branch in summary["branches"] if branch["branch_name"] == "handoff_yaw_servo_v1")
    assert "handoff_yaw_servo_zero_plus45_pre_stage_handoff_blocked" in handoff_branch["failure_labels"]
    fsm_branch = next(branch for branch in summary["branches"] if branch["branch_name"] == "pre_stage_reacquire_fsm_v1")
    assert "pre_stage_fsm_zero_plus45_pre_stage_handoff_blocked" in fsm_branch["failure_labels"]
    path_branch = next(branch for branch in summary["branches"] if branch["branch_name"] == "pre_stage_path_tracker_v1")
    assert "pre_stage_path_tracker_zero_plus45_pre_stage_handoff_blocked" in path_branch["failure_labels"]
    trajectory_branch = next(
        branch for branch in summary["branches"] if branch["branch_name"] == "pre_stage_trajectory_owner_v1"
    )
    assert "pre_stage_trajectory_owner_zero_plus45_pre_stage_handoff_blocked" in trajectory_branch["failure_labels"]


def test_failure_audit_does_not_final_closeout_without_pre_stage_trajectory_owner_candidate(tmp_path: Path):
    branch_specs = []
    for name in (
        "region_funnel_v1",
        "nav2_reacquire_v1",
        "constrained_local_planner_v1",
        "docking_reacquire_v1",
        "handoff_yaw_servo_v1",
        "pre_stage_reacquire_fsm_v1",
        "pre_stage_path_tracker_v1",
    ):
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

    assert summary["recommended_next_action"] != audit.RECOMMENDED_RETIRE_BLOCKED_AND_DESIGN_NAV2_FOLLOW_PATH


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


def test_mppi_follow_path_timeout_is_classified_from_diagnostics(tmp_path: Path):
    mission_root = tmp_path / "mppi_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "event_type": "nav2_follow_path_reacquire_dispatch",
                "attempt": 1,
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "ball_pose": {"x": 5.448, "y": 0.0},
            },
            {
                "event_type": "nav2_follow_path_reacquire_complete",
                "attempt": 1,
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "nav2_follow_path_dispatch_status": "goal_result_timeout",
                "nav2_follow_path_result": {
                    "dispatch_status": "goal_result_timeout",
                    "feedback_count": 4,
                    "feedback_samples": [{"elapsed_s": 0.5, "feedback": {"distance_to_goal": 0.8}}],
                    "timed_out": True,
                    "cancel_requested": True,
                },
                "nav2_follow_path_diagnostics": {
                    "dispatch_status": "goal_result_timeout",
                    "robot_motion_m": 1.25,
                    "ball_motion_m": 0.0,
                    "completion_terminal_path_distance_m": 0.7,
                    "completion_terminal_yaw_error_deg": 38.0,
                    "feedback_count": 4,
                    "measured_handoff_ready": False,
                    "cancel_requested": True,
                    "status_text": "STATUS_ABORTED",
                    "controller_log_excerpt": {"excerpt": ["controller_server: MPPI goal aborted near terminal"]},
                    "cmd_vel_counts": {"/cmd_vel_nav": 9},
                    "cmd_vel_samples": [{"elapsed_s": 1.0, "topic": "/cmd_vel_nav", "linear_x": 0.12, "angular_z": 0.4}],
                    "odom_count": 6,
                    "odom_delta": {"distance_m": 1.25},
                    "path_progress_samples": [
                        {"elapsed_s": 1.0, "terminal_path_distance_m": 0.72, "terminal_yaw_error_deg": 39.0}
                    ],
                    "path_progress_last": {
                        "elapsed_s": 2.0,
                        "terminal_path_distance_m": 0.7,
                        "terminal_yaw_error_deg": 38.0,
                    },
                },
                "nav2_follow_path_measured_handoff_ready": False,
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "mppi",
        family="nav2_mppi_follow_path_reacquire_v1",
        cases=[_case("plus45", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_mppi_follow_path_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "nav2_goal_timeout" in case["failure_labels"]
    assert "slow_controller_convergence" in case["failure_labels"]
    assert "no_controller_progress" not in case["failure_labels"]
    assert "ball_motion_guard" not in case["failure_labels"]
    assert case["nav2_follow_path_debug"]["nav2_follow_path_timeout_count"] == 1
    assert case["nav2_follow_path_debug"]["nav2_follow_path_feedback_count_max"] == 4
    assert case["nav2_follow_path_debug"]["nav2_follow_path_cancel_requested_count"] == 1
    assert case["nav2_follow_path_debug"]["nav2_follow_path_status_texts"] == ["STATUS_ABORTED"]
    assert case["nav2_follow_path_debug"]["nav2_follow_path_cmd_vel_topic_counts"]["/cmd_vel_nav"] == 9
    assert case["nav2_follow_path_debug"]["nav2_follow_path_cmd_vel_sample_count"] == 1
    assert case["nav2_follow_path_debug"]["nav2_follow_path_odom_count_max"] == 6
    assert case["nav2_follow_path_debug"]["nav2_follow_path_odom_delta_max_m"] == 1.25
    assert case["nav2_follow_path_debug"]["nav2_follow_path_progress_min_terminal_path_distance_m"] == 0.7
    assert case["nav2_follow_path_debug"]["nav2_follow_path_progress_min_abs_terminal_yaw_error_deg"] == 38.0
    assert case["nav2_follow_path_debug"]["nav2_follow_path_controller_log_excerpt"]


def test_capture_entry_timeout_debug_is_summarized_from_state_history(tmp_path: Path):
    mission_root = tmp_path / "mppi_zero_capture_entry"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "phase": "capture_entry",
                "manager_directive": "close_capture_gap",
                "selected_command": {"mode": "capture_entry", "linear_x": 0.02, "angular_z": 0.45},
                "capture_entry": {
                    "ball_x_m": 0.54,
                    "ball_y_m": 0.09,
                    "bearing_rad": 0.16,
                    "robot_longitudinal_projection_m": 0.58,
                    "robot_lateral_error_m": 0.09,
                    "capture_entry_reached": False,
                    "robot_on_goal_side": False,
                },
                "capture_entry_diagnostics": {
                    "elapsed_s": 3.5,
                    "ready_signal": False,
                    "ready_latched": False,
                    "ready_reached_once": False,
                    "timeout_cause": "ready_band_never_reached",
                    "manager_directive": "close_capture_gap",
                    "selected_command_mode": "capture_entry",
                    "robot_delta_from_handoff_m": 0.12,
                    "ball_delta_from_handoff_m": 0.0,
                    "ball_x_m": 0.54,
                    "ball_y_m": 0.09,
                    "bearing_rad": 0.16,
                    "robot_longitudinal_projection_m": 0.58,
                    "robot_lateral_error_m": 0.09,
                },
            },
            {
                "phase": "capture_entry",
                "manager_directive": "close_capture_gap",
                "selected_command": {"mode": "capture_entry", "linear_x": 0.02, "angular_z": 0.42},
                "capture_entry": {
                    "ball_x_m": 0.52,
                    "ball_y_m": 0.085,
                    "bearing_rad": 0.15,
                    "robot_longitudinal_projection_m": 0.56,
                    "robot_lateral_error_m": 0.085,
                    "capture_entry_reached": False,
                    "robot_on_goal_side": False,
                },
                "capture_entry_diagnostics": {
                    "elapsed_s": 4.0,
                    "ready_signal": False,
                    "ready_latched": False,
                    "ready_reached_once": False,
                    "timeout_cause": "ready_band_never_reached",
                    "manager_directive": "close_capture_gap",
                    "selected_command_mode": "capture_entry",
                    "robot_delta_from_handoff_m": 0.18,
                    "ball_delta_from_handoff_m": 0.0,
                    "ball_x_m": 0.52,
                    "ball_y_m": 0.085,
                    "bearing_rad": 0.15,
                    "robot_longitudinal_projection_m": 0.56,
                    "robot_lateral_error_m": 0.085,
                },
            },
        ],
    )
    mission_verdict = {
        "failure_stage": "capture_entry",
        "failure_reason": "capture_entry_timeout",
        "capture_entry_snapshot": {
            "ball_x_m": 0.52,
            "ball_y_m": 0.085,
            "bearing_rad": 0.15,
            "robot_longitudinal_projection_m": 0.56,
            "robot_lateral_error_m": 0.085,
            "capture_entry_reached": False,
        },
        "capture_entry_diagnostics": {
            "elapsed_s": 4.0,
            "timeout_cause": "ready_band_never_reached",
            "manager_directive": "close_capture_gap",
            "selected_command_mode": "capture_entry",
            "robot_delta_from_handoff_m": 0.18,
            "ball_delta_from_handoff_m": 0.0,
            "ball_x_m": 0.52,
            "ball_y_m": 0.085,
            "bearing_rad": 0.15,
            "robot_longitudinal_projection_m": 0.56,
            "robot_lateral_error_m": 0.085,
        },
    }
    matrix_path = _matrix_summary(
        tmp_path,
        "mppi_capture_entry",
        family="nav2_mppi_follow_path_reacquire_v1",
        cases=[
            _case(
                "zero",
                mission_root=mission_root,
                fresh_handoff=True,
                fresh_reason="capture_entry_timeout",
                latest_reason="capture_entry_timeout",
                goal_side_count=0,
                mission_verdict=mission_verdict,
            )
        ],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_mppi_follow_path_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]
    debug = case["capture_entry_debug"]

    assert debug["capture_entry_row_count"] == 2
    assert debug["capture_entry_timeout_count"] == 1
    assert debug["capture_entry_timeout_causes"] == ["ready_band_never_reached"]
    assert debug["capture_entry_command_modes"] == ["capture_entry"]
    assert debug["capture_entry_manager_directives"] == ["close_capture_gap"]
    assert debug["capture_entry_ready_observed_count"] == 0
    assert debug["capture_entry_final_ball_x_m"] == 0.52
    assert debug["capture_entry_final_ball_y_m"] == 0.085
    assert debug["capture_entry_final_bearing_rad"] == 0.15
    assert debug["capture_entry_final_robot_longitudinal_projection_m"] == 0.56
    assert debug["capture_entry_final_robot_lateral_error_m"] == 0.085
    assert debug["capture_entry_robot_delta_from_handoff_max_m"] == 0.18
    assert debug["capture_entry_ball_delta_from_handoff_max_m"] == 0.0


def test_capture_debug_is_summarized_from_state_history(tmp_path: Path):
    mission_root = tmp_path / "mppi_plus45_capture"
    first_command = {
        "mode": "capture",
        "linear_x": 0.16,
        "angular_z": 0.08,
        "target_speed_scale": 1.0,
    }
    limited_command = {
        "mode": "capture_handoff_hold",
        "linear_x": 0.03,
        "angular_z": 0.30,
        "target_speed_scale": 0.45,
    }
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "phase": "capture",
                "selected_command": first_command,
                "capture": {
                    "ball_x_m": 0.50,
                    "ball_y_m": 0.04,
                    "bearing_rad": 0.08,
                    "captured": False,
                    "within_capture_window": False,
                },
                "capture_diagnostics": {
                    "terminal_cause": "",
                    "command_source": "capture_command",
                    "command_limited": False,
                    "selected_command": first_command,
                    "selected_command_mode": "capture",
                    "linear_x": 0.16,
                    "angular_z": 0.08,
                    "target_speed_scale": 1.0,
                    "capture_snapshot": {
                        "ball_x_m": 0.50,
                        "ball_y_m": 0.04,
                        "bearing_rad": 0.08,
                        "captured": False,
                    },
                    "captured_now": False,
                    "secure_capture_ready": False,
                    "soft_capture_handoff_ready": False,
                    "zone_entry_handoff_ready": False,
                    "first_contact_alignment_seen": False,
                    "robot_delta_from_capture_entry_handoff_m": 0.10,
                    "ball_delta_from_capture_entry_handoff_m": 0.01,
                },
            },
            {
                "phase": "capture",
                "selected_command": limited_command,
                "capture": {
                    "ball_x_m": 0.32,
                    "ball_y_m": 0.02,
                    "bearing_rad": 0.05,
                    "captured": True,
                    "within_capture_window": True,
                },
                "capture_diagnostics": {
                    "terminal_cause": "",
                    "command_source": "near_zone_place_handoff",
                    "command_limited": True,
                    "command_limit_reason": "Near zone gentle hold.",
                    "selected_command": limited_command,
                    "raw_selected_command": {
                        "mode": "place",
                        "linear_x": 0.14,
                        "angular_z": 0.60,
                        "target_speed_scale": 1.0,
                    },
                    "selected_command_mode": "capture_handoff_hold",
                    "linear_x": 0.03,
                    "angular_z": 0.30,
                    "target_speed_scale": 0.45,
                    "capture_snapshot": {
                        "ball_x_m": 0.32,
                        "ball_y_m": 0.02,
                        "bearing_rad": 0.05,
                        "captured": True,
                    },
                    "captured_now": True,
                    "secure_capture_ready": False,
                    "soft_capture_handoff_ready": True,
                    "zone_entry_handoff_ready": False,
                    "first_contact_alignment_seen": True,
                    "first_contact_push_alignment_deg": 7.5,
                    "robot_delta_from_capture_entry_handoff_m": 0.20,
                    "ball_delta_from_capture_entry_handoff_m": 0.03,
                },
            },
        ],
    )
    mission_verdict = {
        "failure_stage": "capture",
        "failure_reason": "capture_timeout",
        "capture_state": {
            "ball_x_m": 0.31,
            "ball_y_m": 0.018,
            "bearing_rad": 0.04,
            "captured": True,
        },
        "capture_diagnostics": {
            "terminal_cause": "capture_timeout",
            "command_source": "near_zone_place_handoff",
            "command_limited": True,
            "command_limit_reason": "Near zone gentle hold.",
            "selected_command": limited_command,
            "selected_command_mode": "capture_handoff_hold",
            "linear_x": 0.03,
            "angular_z": 0.30,
            "target_speed_scale": 0.45,
            "ball_x_m": 0.31,
            "ball_y_m": 0.018,
            "bearing_rad": 0.04,
            "captured_now": True,
            "secure_capture_ready": False,
            "soft_capture_handoff_ready": True,
            "zone_entry_handoff_ready": False,
            "first_contact_alignment_seen": True,
            "first_contact_push_alignment_deg": 7.5,
            "robot_delta_from_capture_entry_handoff_m": 0.20,
            "ball_delta_from_capture_entry_handoff_m": 0.03,
        },
    }
    matrix_path = _matrix_summary(
        tmp_path,
        "mppi_capture",
        family="nav2_mppi_follow_path_reacquire_v1",
        cases=[
            _case(
                "plus45",
                mission_root=mission_root,
                fresh_handoff=True,
                fresh_reason="missing_first_contact_alignment",
                latest_reason="missing_first_contact_alignment",
                goal_side_count=0,
                mission_verdict=mission_verdict,
            )
        ],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_mppi_follow_path_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    debug = branch["cases"][0]["capture_debug"]

    assert debug["capture_row_count"] == 2
    assert debug["capture_command_modes"] == ["capture", "capture_handoff_hold"]
    assert debug["capture_command_sources"] == ["capture_command", "near_zone_place_handoff"]
    assert debug["capture_command_limited_count"] == 1
    assert debug["capture_command_limit_reasons"] == ["Near zone gentle hold."]
    assert debug["capture_linear_x_max"] == 0.16
    assert debug["capture_max_abs_angular_z"] == 0.3
    assert debug["capture_captured_count"] == 1
    assert debug["capture_soft_handoff_ready_count"] == 1
    assert debug["capture_zone_entry_ready_count"] == 0
    assert debug["capture_first_contact_alignment_count"] == 1
    assert debug["capture_first_contact_alignment_final_deg"] == 7.5
    assert debug["capture_terminal_causes"] == ["capture_timeout"]
    assert debug["capture_final_ball_x_m"] == 0.31
    assert debug["capture_final_ball_y_m"] == 0.018
    assert debug["capture_final_bearing_rad"] == 0.04
    assert debug["capture_min_abs_ball_y_m"] == 0.018
    assert debug["capture_robot_delta_from_capture_entry_handoff_max_m"] == 0.2
    assert debug["capture_ball_delta_from_capture_entry_handoff_max_m"] == 0.03


def test_mppi_follow_path_clearance_action_and_handoff_labels_are_extracted(tmp_path: Path):
    clearance_root = tmp_path / "mppi_clearance"
    action_root = tmp_path / "mppi_action"
    handoff_root = tmp_path / "mppi_handoff"
    _write_jsonl(
        clearance_root / "state_history.jsonl",
        [
            {
                "event_type": "nav2_follow_path_reacquire_plan_blocked",
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "nav2_follow_path_dispatch_status": "follow_path_clearance_guard",
                "nav2_follow_path_plan": {"reason": "follow_path_clearance_guard"},
            }
        ],
    )
    _write_jsonl(
        action_root / "state_history.jsonl",
        [
            {
                "event_type": "nav2_follow_path_reacquire_complete",
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "nav2_follow_path_result": {"dispatch_status": "server_unavailable", "error": "no server"},
            }
        ],
    )
    _write_jsonl(
        handoff_root / "state_history.jsonl",
        [
            {
                "event_type": "nav2_follow_path_reacquire_complete",
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "nav2_follow_path_result": {"dispatch_status": "goal_succeeded", "success": True},
                "nav2_follow_path_diagnostics": {
                    "dispatch_status": "goal_succeeded",
                    "robot_motion_m": 1.0,
                    "ball_motion_m": 0.061,
                    "completion_terminal_path_distance_m": 0.08,
                    "measured_handoff_ready": False,
                },
            }
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "mppi_multi",
        family="nav2_mppi_follow_path_reacquire_v1",
        cases=[
            _case(
                "zero",
                mission_root=clearance_root,
                mission_verdict={"failure_stage": "pre_stage", "failure_reason": "nav2_follow_path_path_clearance_guard"},
            ),
            _case(
                "minus45",
                mission_root=action_root,
                mission_verdict={"failure_stage": "pre_stage", "failure_reason": "nav2_follow_path_failed"},
            ),
            _case(
                "backside180",
                mission_root=handoff_root,
                mission_verdict={"failure_stage": "pre_stage", "failure_reason": "nav2_follow_path_post_action_not_handoff_ready"},
            ),
        ],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="nav2_mppi_follow_path_reacquire_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    cases = {case["case_id"]: case for case in branch["cases"]}

    assert "path_clearance_guard" in cases["zero"]["failure_labels"]
    assert "action_error" in cases["minus45"]["failure_labels"]
    assert "handoff_gate_mismatch" in cases["backside180"]["failure_labels"]
    assert "ball_motion_guard" in cases["backside180"]["failure_labels"]
    assert "ball_contact_during_reacquire" in cases["backside180"]["failure_labels"]


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


def test_missing_path_tracker_state_history_is_missing_evidence_not_failure_label(tmp_path: Path):
    mission_root = tmp_path / "path_tracker_zero_missing"
    mission_root.mkdir(parents=True)
    matrix_path = _matrix_summary(
        tmp_path,
        "path_tracker",
        family="pre_stage_path_tracker_v1",
        cases=[_case("zero", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="pre_stage_path_tracker_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert case["state_history_status"] == "missing"
    assert "state_history_missing" in case["missing_evidence"]
    assert case["pre_stage_path_tracker_debug"]["pre_stage_path_tracker_row_count"] == 0
    assert "pre_stage_path_tracker_progress_stalled" not in case["failure_labels"]
    assert "pre_stage_path_tracker_escape_not_converged" not in case["failure_labels"]


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


def test_pre_stage_reacquire_fsm_rows_emit_fsm_failure_labels(tmp_path: Path):
    mission_root = tmp_path / "pre_stage_fsm_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "pre_stage_reacquire_fsm_v1",
                "objective_name": "pre_stage_reacquire_fsm",
                "selected_command": {"mode": "pre_stage_reacquire_fsm"},
                "pre_stage_reacquire_fsm_active": True,
                "pre_stage_reacquire_fsm_phase": "goal_side_escape",
                "pre_stage_reacquire_fsm_release_reason": "",
                "pre_stage_reacquire_fsm_release_blockers": ["robot_on_goal_side"],
                "pre_stage_reacquire_fsm_measured_handoff_ready": False,
                "pre_stage_reacquire_fsm_projected_handoff_ready": False,
                "pre_stage_reacquire_fsm_measured_pre_stage": {
                    "robot_on_goal_side": True,
                    "pre_stage_pose_reached": False,
                },
                "pre_stage_reacquire_fsm_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_reacquire_fsm_projection_m": 5.4,
                "pre_stage_reacquire_fsm_lateral_error_m": 1.1,
                "pre_stage_reacquire_fsm_distance_m": 6.3,
                "pre_stage_reacquire_fsm_yaw_error_deg": 180.0,
                "pre_stage_reacquire_fsm_ball_motion_m": 0.0,
                "pre_stage_reacquire_fsm_min_ball_clearance_m": 5.3,
                "pre_stage_reacquire_fsm_accepted_count": 1,
                "pre_stage_reacquire_fsm_rejected_count": 0,
                "pre_stage_reacquire_fsm_rejection_reasons": [],
            },
            {
                "controller_family": "pre_stage_reacquire_fsm_v1",
                "objective_name": "pre_stage_reacquire_fsm",
                "selected_command": {"mode": "pre_stage_reacquire_fsm"},
                "pre_stage_reacquire_fsm_active": True,
                "pre_stage_reacquire_fsm_phase": "dock_entry",
                "pre_stage_reacquire_fsm_release_reason": "",
                "pre_stage_reacquire_fsm_release_blockers": ["lateral_not_converged"],
                "pre_stage_reacquire_fsm_measured_handoff_ready": False,
                "pre_stage_reacquire_fsm_projected_handoff_ready": False,
                "pre_stage_reacquire_fsm_measured_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_reacquire_fsm_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_reacquire_fsm_projection_m": -0.9,
                "pre_stage_reacquire_fsm_lateral_error_m": 0.85,
                "pre_stage_reacquire_fsm_distance_m": 0.85,
                "pre_stage_reacquire_fsm_yaw_error_deg": 160.0,
                "pre_stage_reacquire_fsm_ball_motion_m": 0.01,
                "pre_stage_reacquire_fsm_min_ball_clearance_m": 1.2,
                "pre_stage_reacquire_fsm_accepted_count": 1,
                "pre_stage_reacquire_fsm_rejected_count": 0,
                "pre_stage_reacquire_fsm_rejection_reasons": [],
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "pre_stage_fsm",
        family="pre_stage_reacquire_fsm_v1",
        cases=[_case("plus45", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="pre_stage_reacquire_fsm_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "pre_stage_fsm_escape_not_converged" in case["failure_labels"]
    assert "pre_stage_fsm_dock_entry_not_converged" in case["failure_labels"]
    assert "pre_stage_fsm_timeout_without_ball_contact" in case["failure_labels"]
    assert "ball_contact_during_reacquire" not in case["failure_labels"]
    debug = case["pre_stage_fsm_debug"]
    assert debug["pre_stage_fsm_active_row_count"] == 2
    assert debug["pre_stage_fsm_phase_counts"] == {"goal_side_escape": 1, "dock_entry": 1}
    assert debug["pre_stage_fsm_final_phase"] == "dock_entry"
    assert debug["pre_stage_fsm_release_reason_count"] == 0
    assert debug["pre_stage_fsm_release_blockers"] == ["robot_on_goal_side", "lateral_not_converged"]
    assert debug["pre_stage_fsm_measured_handoff_not_ready_count"] == 2
    assert debug["pre_stage_fsm_projected_handoff_not_ready_count"] == 2
    assert debug["pre_stage_fsm_projection_min_m"] == -0.9
    assert debug["pre_stage_fsm_projection_max_m"] == 5.4
    assert debug["pre_stage_fsm_lateral_error_min_m"] == 0.85
    assert debug["pre_stage_fsm_lateral_error_max_m"] == 1.1
    assert debug["pre_stage_fsm_distance_min_m"] == 0.85
    assert debug["pre_stage_fsm_distance_max_m"] == 6.3
    assert debug["pre_stage_fsm_yaw_error_min_deg"] == 160.0
    assert debug["pre_stage_fsm_yaw_error_max_deg"] == 180.0
    assert debug["pre_stage_fsm_accepted_count"] == 2
    assert debug["pre_stage_fsm_rejected_count"] == 0
    assert debug["pre_stage_fsm_max_ball_motion_m"] == 0.01
    assert debug["pre_stage_fsm_min_ball_clearance_m"] == 1.2


def test_pre_stage_path_tracker_rows_emit_path_failure_labels(tmp_path: Path):
    mission_root = tmp_path / "pre_stage_path_tracker_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "pre_stage_path_tracker_v1",
                "objective_name": "pre_stage_path_tracker",
                "selected_command": {"mode": "pre_stage_path_tracker"},
                "pre_stage_path_tracker_active": True,
                "pre_stage_path_tracker_waypoint_index": 0,
                "pre_stage_path_tracker_waypoint_kind": "escape",
                "pre_stage_path_tracker_waypoint_count": 4,
                "pre_stage_path_tracker_release_reason": "",
                "pre_stage_path_tracker_release_blockers": ["robot_on_goal_side", "projection_not_cleared"],
                "pre_stage_path_tracker_measured_handoff_ready": False,
                "pre_stage_path_tracker_projected_handoff_ready": False,
                "pre_stage_path_tracker_measured_pre_stage": {
                    "robot_on_goal_side": True,
                    "pre_stage_pose_reached": False,
                },
                "pre_stage_path_tracker_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_path_tracker_projection_m": 4.7,
                "pre_stage_path_tracker_lateral_error_m": 1.7,
                "pre_stage_path_tracker_distance_m": 5.9,
                "pre_stage_path_tracker_yaw_error_deg": 135.0,
                "pre_stage_path_tracker_ball_motion_m": 0.0,
                "pre_stage_path_tracker_min_ball_clearance_m": 3.0,
                "pre_stage_path_tracker_accepted_count": 1,
                "pre_stage_path_tracker_rejected_count": 0,
                "pre_stage_path_tracker_rejection_reasons": [],
            },
            {
                "controller_family": "pre_stage_path_tracker_v1",
                "objective_name": "pre_stage_path_tracker",
                "selected_command": {"mode": "pre_stage_path_tracker_hold"},
                "pre_stage_path_tracker_active": True,
                "pre_stage_path_tracker_waypoint_index": 0,
                "pre_stage_path_tracker_waypoint_kind": "escape",
                "pre_stage_path_tracker_waypoint_count": 4,
                "pre_stage_path_tracker_release_reason": "",
                "pre_stage_path_tracker_release_blockers": [
                    "robot_on_goal_side",
                    "projection_not_cleared",
                    "distance_not_converged",
                ],
                "pre_stage_path_tracker_measured_handoff_ready": False,
                "pre_stage_path_tracker_projected_handoff_ready": False,
                "pre_stage_path_tracker_measured_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_path_tracker_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_path_tracker_projection_m": 2.9,
                "pre_stage_path_tracker_lateral_error_m": 1.1,
                "pre_stage_path_tracker_distance_m": 4.0,
                "pre_stage_path_tracker_yaw_error_deg": 166.0,
                "pre_stage_path_tracker_ball_motion_m": 0.0,
                "pre_stage_path_tracker_min_ball_clearance_m": 3.2,
                "pre_stage_path_tracker_accepted_count": 0,
                "pre_stage_path_tracker_rejected_count": 1,
                "pre_stage_path_tracker_rejection_reasons": ["waypoint_progress_stall"],
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "pre_stage_path_tracker",
        family="pre_stage_path_tracker_v1",
        cases=[_case("plus45", mission_root=mission_root)],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="pre_stage_path_tracker_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "pre_stage_path_tracker_escape_not_converged" in case["failure_labels"]
    assert "pre_stage_path_tracker_progress_stalled" in case["failure_labels"]
    assert "pre_stage_path_tracker_timeout_without_ball_contact" in case["failure_labels"]
    assert "ball_contact_during_reacquire" not in case["failure_labels"]
    debug = case["pre_stage_path_tracker_debug"]
    assert debug["pre_stage_path_tracker_active_row_count"] == 2
    assert debug["pre_stage_path_tracker_waypoint_counts"] == {"escape": 2}
    assert debug["pre_stage_path_tracker_final_waypoint"] == "escape"
    assert debug["pre_stage_path_tracker_command_counts"] == {
        "pre_stage_path_tracker": 1,
        "pre_stage_path_tracker_hold": 1,
    }
    assert debug["pre_stage_path_tracker_release_reason_count"] == 0
    assert debug["pre_stage_path_tracker_release_blockers"] == [
        "robot_on_goal_side",
        "projection_not_cleared",
        "distance_not_converged",
    ]
    assert debug["pre_stage_path_tracker_rejection_reasons"] == ["waypoint_progress_stall"]
    assert debug["pre_stage_path_tracker_measured_handoff_not_ready_count"] == 2
    assert debug["pre_stage_path_tracker_projected_handoff_not_ready_count"] == 2
    assert debug["pre_stage_path_tracker_projection_start_m"] == 4.7
    assert debug["pre_stage_path_tracker_projection_end_m"] == 2.9
    assert debug["pre_stage_path_tracker_projection_min_m"] == 2.9
    assert debug["pre_stage_path_tracker_projection_max_m"] == 4.7
    assert debug["pre_stage_path_tracker_lateral_error_start_m"] == 1.7
    assert debug["pre_stage_path_tracker_lateral_error_end_m"] == 1.1
    assert debug["pre_stage_path_tracker_distance_start_m"] == 5.9
    assert debug["pre_stage_path_tracker_distance_end_m"] == 4.0
    assert debug["pre_stage_path_tracker_yaw_error_start_deg"] == 135.0
    assert debug["pre_stage_path_tracker_yaw_error_end_deg"] == 166.0
    assert debug["pre_stage_path_tracker_accepted_count"] == 1
    assert debug["pre_stage_path_tracker_rejected_count"] == 1
    assert debug["pre_stage_path_tracker_max_ball_motion_m"] == 0.0
    assert debug["pre_stage_path_tracker_min_ball_clearance_m"] == 3.0


def test_pre_stage_trajectory_owner_rows_emit_owner_failure_labels(tmp_path: Path):
    mission_root = tmp_path / "pre_stage_trajectory_owner_plus45"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "controller_family": "pre_stage_trajectory_owner_v1",
                "objective_name": "pre_stage_trajectory_owner",
                "selected_command": {"mode": "pre_stage_trajectory_owner"},
                "pre_stage_trajectory_owner_active": True,
                "pre_stage_trajectory_owner_milestone_index": 0,
                "pre_stage_trajectory_owner_milestone_kind": "escape_clear",
                "pre_stage_trajectory_owner_milestone_count": 4,
                "pre_stage_trajectory_owner_release_reason": "",
                "pre_stage_trajectory_owner_release_blockers": ["robot_on_goal_side", "projection_not_cleared"],
                "pre_stage_trajectory_owner_measured_handoff_ready": False,
                "pre_stage_trajectory_owner_projected_handoff_ready": False,
                "pre_stage_trajectory_owner_measured_pre_stage": {
                    "robot_on_goal_side": True,
                    "pre_stage_pose_reached": False,
                },
                "pre_stage_trajectory_owner_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_trajectory_owner_projection_m": 4.7,
                "pre_stage_trajectory_owner_lateral_error_m": 1.7,
                "pre_stage_trajectory_owner_distance_m": 5.9,
                "pre_stage_trajectory_owner_yaw_error_deg": 135.0,
                "pre_stage_trajectory_owner_ball_motion_m": 0.0,
                "pre_stage_trajectory_owner_min_ball_clearance_m": 3.0,
                "pre_stage_trajectory_owner_replan_count": 0,
                "pre_stage_trajectory_owner_next_replan_count": 0,
                "pre_stage_trajectory_owner_replan_reason": "",
                "pre_stage_trajectory_owner_accepted_count": 1,
                "pre_stage_trajectory_owner_rejected_count": 0,
                "pre_stage_trajectory_owner_rejection_reasons": [],
            },
            {
                "controller_family": "pre_stage_trajectory_owner_v1",
                "objective_name": "pre_stage_trajectory_owner",
                "selected_command": {"mode": "pre_stage_trajectory_owner_abort"},
                "pre_stage_trajectory_owner_active": False,
                "pre_stage_trajectory_owner_milestone_index": 0,
                "pre_stage_trajectory_owner_milestone_kind": "escape_clear",
                "pre_stage_trajectory_owner_milestone_count": 4,
                "pre_stage_trajectory_owner_release_reason": "trajectory_clearance_guard",
                "pre_stage_trajectory_owner_release_blockers": ["segment_clearance_violation"],
                "pre_stage_trajectory_owner_measured_handoff_ready": False,
                "pre_stage_trajectory_owner_projected_handoff_ready": False,
                "pre_stage_trajectory_owner_measured_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_trajectory_owner_projected_pre_stage": {"pre_stage_pose_reached": False},
                "pre_stage_trajectory_owner_projection_m": 2.9,
                "pre_stage_trajectory_owner_lateral_error_m": 1.1,
                "pre_stage_trajectory_owner_distance_m": 4.0,
                "pre_stage_trajectory_owner_yaw_error_deg": 166.0,
                "pre_stage_trajectory_owner_ball_motion_m": 0.0,
                "pre_stage_trajectory_owner_min_ball_clearance_m": 3.2,
                "pre_stage_trajectory_owner_replan_count": 0,
                "pre_stage_trajectory_owner_next_replan_count": 1,
                "pre_stage_trajectory_owner_replan_reason": "trajectory_progress_stalled",
                "pre_stage_trajectory_owner_accepted_count": 0,
                "pre_stage_trajectory_owner_rejected_count": 1,
                "pre_stage_trajectory_owner_rejection_reasons": [
                    "trajectory_progress_stalled",
                    "segment_clearance_violation",
                ],
            },
        ],
    )
    matrix_path = _matrix_summary(
        tmp_path,
        "pre_stage_trajectory_owner",
        family="pre_stage_trajectory_owner_v1",
        cases=[_case("plus45", mission_root=mission_root, goal_side_count=0, fresh_reason="trajectory_progress_stalled")],
    )

    branch = audit.build_branch_failure_summary(
        branch_name="pre_stage_trajectory_owner_v1",
        source_summary_path=matrix_path,
        source_summary=json.loads(matrix_path.read_text(encoding="utf-8")),
    )
    case = branch["cases"][0]

    assert "pre_stage_trajectory_owner_escape_not_converged" in case["failure_labels"]
    assert "pre_stage_trajectory_owner_progress_stalled" in case["failure_labels"]
    assert "pre_stage_trajectory_owner_clearance_guard" in case["failure_labels"]
    assert "pre_stage_trajectory_owner_timeout_without_ball_contact" in case["failure_labels"]
    assert "ball_contact_during_reacquire" not in case["failure_labels"]
    debug = case["pre_stage_trajectory_owner_debug"]
    assert debug["pre_stage_trajectory_owner_active_row_count"] == 2
    assert debug["pre_stage_trajectory_owner_milestone_counts"] == {"escape_clear": 2}
    assert debug["pre_stage_trajectory_owner_final_milestone"] == "escape_clear"
    assert debug["pre_stage_trajectory_owner_command_counts"] == {
        "pre_stage_trajectory_owner": 1,
        "pre_stage_trajectory_owner_abort": 1,
    }
    assert debug["pre_stage_trajectory_owner_release_reason_count"] == 1
    assert debug["pre_stage_trajectory_owner_release_reasons"] == ["trajectory_clearance_guard"]
    assert debug["pre_stage_trajectory_owner_release_blockers"] == [
        "robot_on_goal_side",
        "projection_not_cleared",
        "segment_clearance_violation",
    ]
    assert debug["pre_stage_trajectory_owner_rejection_reasons"] == [
        "trajectory_progress_stalled",
        "segment_clearance_violation",
    ]
    assert debug["pre_stage_trajectory_owner_replan_reasons"] == ["trajectory_progress_stalled"]
    assert debug["pre_stage_trajectory_owner_next_replan_count_max"] == 1.0
    assert debug["pre_stage_trajectory_owner_measured_handoff_not_ready_count"] == 2
    assert debug["pre_stage_trajectory_owner_projected_handoff_not_ready_count"] == 2
    assert debug["pre_stage_trajectory_owner_projection_start_m"] == 4.7
    assert debug["pre_stage_trajectory_owner_projection_end_m"] == 2.9
    assert debug["pre_stage_trajectory_owner_projection_min_m"] == 2.9
    assert debug["pre_stage_trajectory_owner_projection_max_m"] == 4.7
    assert debug["pre_stage_trajectory_owner_lateral_error_start_m"] == 1.7
    assert debug["pre_stage_trajectory_owner_lateral_error_end_m"] == 1.1
    assert debug["pre_stage_trajectory_owner_distance_start_m"] == 5.9
    assert debug["pre_stage_trajectory_owner_distance_end_m"] == 4.0
    assert debug["pre_stage_trajectory_owner_yaw_error_start_deg"] == 135.0
    assert debug["pre_stage_trajectory_owner_yaw_error_end_deg"] == 166.0
    assert debug["pre_stage_trajectory_owner_accepted_count"] == 1
    assert debug["pre_stage_trajectory_owner_rejected_count"] == 1
    assert debug["pre_stage_trajectory_owner_max_ball_motion_m"] == 0.0
    assert debug["pre_stage_trajectory_owner_min_ball_clearance_m"] == 3.0


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
