from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_capture_entry_diagnostic_analyzer as analyzer  # noqa: E402
from llm_supervisor_core import write_json  # noqa: E402


def _write_state_history(mission_root: Path, rows: list[dict]) -> None:
    mission_root.mkdir(parents=True)
    (mission_root / "state_history.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _capture_entry_row(
    *,
    ball_x: float,
    ball_y: float,
    bearing: float,
    linear_x: float,
    mode: str = "object_capture_entry_lateral_recenter",
    elapsed_s: float = 1.0,
    robot_delta: float = 0.02,
    timeout_cause: str = "ready_band_never_reached",
) -> dict:
    return {
        "phase": "capture_entry",
        "capture": {
            "ball_ahead": True,
            "ball_x_m": ball_x,
            "ball_y_m": ball_y,
            "bearing_rad": bearing,
            "within_recapture_window": True,
        },
        "capture_entry": {
            "capture_entry_reached": False,
            "ball_x_m": ball_x,
            "ball_y_m": ball_y,
            "bearing_rad": bearing,
        },
        "capture_entry_diagnostics": {
            "elapsed_s": elapsed_s,
            "robot_delta_from_handoff_m": robot_delta,
            "ball_delta_from_handoff_m": 0.0,
            "timeout_cause": timeout_cause,
            "ready_signal": False,
            "selected_command": {
                "mode": mode,
                "linear_x": linear_x,
                "angular_z": 0.18,
            },
        },
        "selected_command": {
            "mode": mode,
            "linear_x": linear_x,
            "angular_z": 0.18,
        },
    }


def _summary(path: Path, mission_root: Path, *, passed: bool, failure_reason: str) -> None:
    write_json(
        path,
        {
            "campaign_id": "right05",
            "requested_target_layout_json": "ros2_config/target_layouts/golf_ball_circle_delivery_right05.json",
            "runs": [
                {
                    "run_index": 1,
                    "mission_root": str(mission_root),
                    "fetch_to_pose_pass": passed,
                    "fetch_to_pose_failure_reason": failure_reason,
                    "fresh_attempt_approach": {
                        "capture_entry": {
                            "pass": passed,
                            "reached": passed,
                            "time_s": 6.031,
                            "failure_reason": failure_reason,
                        }
                    },
                }
            ],
        },
    )


def test_capture_entry_analyzer_classifies_recenter_without_forward_progress(tmp_path):
    mission_root = tmp_path / "mission"
    _write_state_history(
        mission_root,
        [
            _capture_entry_row(ball_x=0.621, ball_y=-0.145, bearing=-0.229, linear_x=0.0, elapsed_s=0.6),
            _capture_entry_row(ball_x=0.605, ball_y=-0.098, bearing=-0.161, linear_x=0.0, elapsed_s=4.1),
            _capture_entry_row(ball_x=0.611, ball_y=0.050, bearing=0.082, linear_x=0.0, elapsed_s=6.0),
        ],
    )
    summary_path = tmp_path / "summary.json"
    _summary(summary_path, mission_root, passed=False, failure_reason="capture_entry_timeout")

    summary = analyzer.analyze([str(summary_path)])

    row = summary["runs"][0]
    assert summary["overall_interpretation"] == "repair_recenter_forward_progress"
    assert row["classification"] == "recenter_without_forward_progress"
    assert row["zero_linear_recenter_count"] == 3
    assert row["forward_command_count"] == 0
    assert row["final_sample"]["timeout_cause"] == "ready_band_never_reached"


def test_capture_entry_analyzer_classifies_forward_closure_gap(tmp_path):
    mission_root = tmp_path / "mission"
    _write_state_history(
        mission_root,
        [
            _capture_entry_row(
                ball_x=0.63,
                ball_y=0.02,
                bearing=0.02,
                linear_x=0.025,
                mode="object_capture_entry_recenter_with_progress",
                robot_delta=0.12,
            ),
            _capture_entry_row(
                ball_x=0.61,
                ball_y=0.02,
                bearing=0.02,
                linear_x=0.025,
                mode="object_capture_entry_recenter_with_progress",
                robot_delta=0.16,
            ),
        ],
    )
    summary_path = tmp_path / "summary.json"
    _summary(summary_path, mission_root, passed=False, failure_reason="capture_entry_timeout")

    summary = analyzer.analyze([str(summary_path)])

    row = summary["runs"][0]
    assert row["classification"] == "insufficient_forward_closure"
    assert row["forward_command_count"] == 2


def test_capture_entry_analyzer_classifies_pass(tmp_path):
    mission_root = tmp_path / "mission"
    _write_state_history(
        mission_root,
        [
            _capture_entry_row(
                ball_x=0.52,
                ball_y=0.01,
                bearing=0.01,
                linear_x=0.0,
                mode="capture_entry_ready",
                timeout_cause="",
            )
        ],
    )
    summary_path = tmp_path / "summary.json"
    _summary(summary_path, mission_root, passed=True, failure_reason="")

    summary = analyzer.analyze([str(summary_path)])

    assert summary["overall_interpretation"] == "capture_entry_requalified"
    assert summary["runs"][0]["classification"] == "capture_entry_pass"


def test_delivery_pass_with_missing_capture_entry_flag_is_watchlist(tmp_path):
    mission_root = tmp_path / "mission"
    _write_state_history(
        mission_root,
        [
            _capture_entry_row(
                ball_x=0.58,
                ball_y=-0.12,
                bearing=-0.2,
                linear_x=0.035,
                mode="capture_entry_ready",
                timeout_cause="ready_dwell_not_completed",
            )
        ],
    )
    summary_path = tmp_path / "summary.json"
    _summary(summary_path, mission_root, passed=True, failure_reason="")
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["runs"][0]["fresh_attempt_approach"]["capture_entry"]["pass"] = False
    payload["runs"][0]["fresh_attempt_approach"]["capture_entry"]["reached"] = False
    write_json(summary_path, payload)

    summary = analyzer.analyze([str(summary_path)])

    assert summary["overall_interpretation"] == "capture_entry_requalified"
    assert summary["capture_entry_blocker_count"] == 0
    assert summary["runs"][0]["classification"] == "delivery_pass_capture_entry_watchlist"
