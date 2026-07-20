from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_object_centric_policy_evaluator as evaluator  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_evaluator_scores_matrix_state_history_and_writes_scorecard(tmp_path: Path):
    mission_root = tmp_path / "session" / "run_zero"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "phase": "pre_stage",
                "selected_command": {"mode": "object_pre_stage_traverse", "linear_x": 0.04, "angular_z": 0.0},
                "ball_motion_m": 0.0,
                "object_centric_policy": {
                    "phase": "pre_stage",
                    "selected_command": {"mode": "object_pre_stage_traverse", "linear_x": 0.04, "angular_z": 0.0},
                    "guard_rejection_reason": "",
                },
            },
            {
                "phase": "capture_entry",
                "selected_command": {"mode": "object_capture_entry_close", "linear_x": 0.06, "angular_z": 0.1},
                "capture_entry": {"capture_entry_reached": True},
                "capture_entry_diagnostics": {"ready_reached_once": True},
                "ball_motion_m": 0.0,
            },
            {
                "phase": "capture",
                "selected_command": {"mode": "object_capture_push", "linear_x": 0.10, "angular_z": 0.12},
                "capture": {"captured": True, "ball_x_m": 0.22, "ball_y_m": 0.01},
                "capture_diagnostics": {
                    "captured_now": True,
                    "secure_capture_ready": True,
                    "first_contact_push_alignment_deg": 12.5,
                },
            },
            {
                "phase": "capture",
                "selected_command": {"mode": "capture_handoff", "linear_x": 0.0, "angular_z": 0.0},
                "zone_score": {"center_inside_zone": True},
                "capture_diagnostics": {"zone_entry_handoff_ready": True, "terminal_cause": "zone_entry"},
                "object_centric_policy": {
                    "phase": "capture",
                    "selected_command": {"mode": "object_capture_push", "linear_x": 0.10, "angular_z": 0.12},
                    "terminal_cause": "zone_entry",
                },
            },
        ],
    )
    matrix_path = _write_json(
        tmp_path / "matrix" / "gather_goal_side_matrix" / "campaign_summary.json",
        {
            "cases": [
                {
                    "case_id": "zero",
                    "runs": [
                        {
                            "run_index": 1,
                            "pass": True,
                            "pre_stage_handoff_pass": True,
                            "mission_root": str(mission_root),
                        }
                    ],
                }
            ]
        },
    )

    summary = evaluator.analyze_artifacts("unit_object_policy", [("matrix", matrix_path)])
    run = summary["runs"][0]

    assert summary["run_count"] == 1
    assert summary["pass_count"] == 1
    assert summary["capture_entry_reached_count"] == 1
    assert summary["capture_observed_count"] == 1
    assert summary["zone_entry_observed_count"] == 1
    assert run["case_id"] == "zero"
    assert run["terminal_cause"] == "zone_entry"
    assert run["first_contact_alignment_deg"] == 12.5
    assert run["premature_ball_motion"]["observed"] is False
    assert run["command_summary"]["mode_churn_count"] >= 1
    assert run["object_centric_policy_row_count"] == 2

    output_path = evaluator.write_outputs(summary, repo_root=tmp_path / "repo_out")
    assert output_path.name == "object_centric_policy_summary.json"
    assert (output_path.parent / "scorecard.md").exists()


def test_evaluator_surfaces_premature_motion_and_policy_safety_stop(tmp_path: Path):
    mission_root = tmp_path / "session" / "guarded"
    _write_jsonl(
        mission_root / "state_history.jsonl",
        [
            {
                "phase": "stage",
                "ball_motion_m": 0.08,
                "selected_command": {
                    "mode": "object_policy_ball_motion_guard",
                    "linear_x": 0.0,
                    "angular_z": 0.0,
                },
                "object_centric_policy": {
                    "phase": "stage",
                    "guard_rejection_reason": "ball_motion_guard",
                    "terminal_cause": "ball_motion_guard",
                    "selected_command": {
                        "mode": "object_policy_ball_motion_guard",
                        "linear_x": 0.0,
                        "angular_z": 0.0,
                    },
                },
            }
        ],
    )
    repeatability_path = _write_json(
        tmp_path / "repeatability" / "campaign_run_summary.json",
        {
            "runs": [
                {
                    "case_id": "plus45",
                    "run_index": 1,
                    "pass": False,
                    "pre_stage_handoff_pass": False,
                    "failure_reason": "ball_motion_guard",
                    "mission_root": str(mission_root),
                }
            ]
        },
    )

    summary = evaluator.analyze_artifacts("unit_object_policy_guard", [("plus45", repeatability_path)])
    run = summary["runs"][0]

    assert summary["premature_ball_motion_count"] == 1
    assert summary["safety_stop_count"] == 1
    assert run["premature_ball_motion"]["max_m"] == 0.08
    assert run["terminal_cause"] == "ball_motion_guard"
