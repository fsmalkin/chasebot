from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_follow_path_research_analyzer as analyzer  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _path_poses() -> list[dict[str, object]]:
    return [
        {"kind": "start", "x": 0.0, "y": 0.0, "yaw": 0.0},
        {"kind": "port", "x": 1.0, "y": -0.2, "yaw": 1.8},
        {"kind": "handoff_align", "x": 1.2, "y": 0.0, "yaw": 3.14159},
        {"kind": "handoff_yaw", "x": 1.0, "y": 0.0, "yaw": 3.14159},
    ]


def _write_mppi_state_history(mission_root: Path) -> None:
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "event_type": "nav2_follow_path_reacquire_dispatch",
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "ball_pose": {"x": 0.4, "y": 0.0},
                "nav2_follow_path_path_poses": _path_poses(),
                "nav2_follow_path_plan": {
                    "controller_id": "MppiFollowPath",
                    "goal_checker_id": "general_goal_checker",
                    "path_poses": _path_poses(),
                },
            },
            {
                "event_type": "nav2_follow_path_reacquire_complete",
                "controller_family": "nav2_mppi_follow_path_reacquire_v1",
                "nav2_follow_path_dispatch_status": "goal_result_timeout",
                "nav2_follow_path_ball_motion_m": 0.0,
                "nav2_follow_path_robot_motion_m": 1.4,
                "nav2_follow_path_terminal_path_distance_m": 0.21,
                "nav2_follow_path_terminal_yaw_error_deg": 69.0,
                "nav2_follow_path_result": {
                    "dispatch_status": "goal_result_timeout",
                    "error": "goal_result_timeout",
                    "timed_out": True,
                },
                "nav2_follow_path_diagnostics": {
                    "status_text": "STATUS_ABORTED",
                    "cmd_vel_counts": {"/jetbot_base_controller/cmd_vel": 10},
                    "cmd_vel_samples": [{"elapsed_s": 1.0, "linear_x": 0.1, "angular_z": 0.2}],
                    "cmd_vel_last": {"elapsed_s": 2.0, "linear_x": 0.08, "angular_z": 0.18},
                    "feedback_count": 3,
                    "feedback_samples": [
                        {"elapsed_s": 0.5, "feedback": {"distance_to_goal": 2.0}},
                        {"elapsed_s": 1.0, "feedback": {"distance_to_goal": 1.2}},
                    ],
                    "feedback_last": {"elapsed_s": 2.0, "feedback": {"distance_to_goal": 1.1}},
                    "path_progress_samples": [
                        {
                            "elapsed_s": 1.0,
                            "nearest_path_index": 1,
                            "nearest_path_kind": "port",
                            "terminal_path_distance_m": 0.8,
                            "terminal_yaw_error_deg": -80.0,
                        },
                        {
                            "elapsed_s": 2.0,
                            "nearest_path_index": 1,
                            "nearest_path_kind": "port",
                            "terminal_path_distance_m": 0.21,
                            "terminal_yaw_error_deg": -69.0,
                        },
                    ],
                    "path_progress_last": {
                        "elapsed_s": 2.0,
                        "nearest_path_index": 1,
                        "nearest_path_kind": "port",
                        "remaining_path_pose_count": 2,
                        "terminal_path_distance_m": 0.21,
                        "terminal_yaw_error_deg": -69.0,
                    },
                },
            },
        ],
    )


def test_analyzer_summarizes_matrix_state_history_and_loaded_params(tmp_path: Path):
    mission_root = tmp_path / "session" / "gather_mission" / "run"
    _write_mppi_state_history(mission_root)
    campaign_root = tmp_path / "matrix_campaign"
    matrix_path = _write_json(
        campaign_root / "gather_goal_side_matrix" / "campaign_summary.json",
        {
            "cases": [
                {
                    "case_id": "zero",
                    "runs": [
                        {
                            "run_index": 1,
                            "pass": False,
                            "pre_stage_handoff_pass": False,
                            "mission_root": str(mission_root),
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        campaign_root / "controller_params" / "mppi_param_comparison.json",
        {
            "loaded": {"prune_distance": 1.2, "PathAlignCritic": {"use_path_orientations": False}},
            "matches": {"nav2_params.yaml": False, "nav2_params_simple.yaml": True},
        },
    )

    summary = analyzer.analyze_artifacts("unit_follow_path", [("may3", matrix_path)])
    run = summary["runs"][0]

    assert summary["run_count"] == 1
    assert run["case_id"] == "zero"
    assert run["dispatch_status"] == "goal_result_timeout"
    assert run["ball_motion_m"] == 0.0
    assert run["path_geometry"]["handoff_align_present"] is True
    assert run["path_progress"]["last_meter_sample_count"] == 2
    assert run["cmd_vel"]["topic_counts"]["/jetbot_base_controller/cmd_vel"] == 10
    assert run["feedback"]["last_distance_to_goal"] == 1.1
    assert run["loaded_controller_params"]["matches"]["nav2_params_simple.yaml"] is True

    output_path = analyzer.write_outputs(summary, repo_root=tmp_path / "repo_out")
    assert output_path.exists()
    assert (output_path.parent / "scorecard.md").exists()


def test_analyzer_expands_research_reset_nested_runs(tmp_path: Path):
    mission_root = tmp_path / "session" / "nested"
    _write_mppi_state_history(mission_root)
    research_path = _write_json(
        tmp_path / "research_reset_summary.json",
        {
            "runs": [
                {
                    "label": "current_8dfe93b_zero",
                    "loaded_param_summary": {"prune_distance": 1.2},
                    "param_matches": {"nav2_params_simple.yaml": True},
                    "runs": [
                        {
                            "run_index": 1,
                            "mission_root": str(mission_root),
                            "pass": False,
                            "pre_stage_handoff_pass": False,
                            "follow_path": {
                                "dispatch_status": "goal_result_timeout",
                                "terminal_path_distance_m": 0.21,
                                "terminal_yaw_error_deg": 69.0,
                                "ball_motion_m": 0.0,
                            },
                        }
                    ],
                }
            ]
        },
    )

    summary = analyzer.analyze_artifacts("unit_research", [("reset", research_path)])
    run = summary["runs"][0]

    assert run["source_kind"] == "research_reset"
    assert run["case_id"] == "zero"
    assert run["run_label"] == "reset:current_8dfe93b_zero:run_1"
    assert run["loaded_controller_params"]["loaded"]["prune_distance"] == 1.2
    assert run["loaded_controller_params"]["matches"]["nav2_params_simple.yaml"] is True
