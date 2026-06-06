import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_open_field_uat_rollup as rollup  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _layout(tmp_path: Path, scene_id: str, *, opposite: bool = False) -> str:
    path = tmp_path / "layouts" / f"{scene_id}.json"
    _write_json(
        path,
        {
            "planner_scene": {
                "scene_id": scene_id,
                "geometry": {
                    "opposite_side_of_circle": opposite,
                    "ball_target_angle_deg": 145.0 if opposite else 20.0,
                    "ball_target_distance_m": 0.7,
                    "robot_ball_distance_m": 1.1,
                    "robot_ball_relative_bearing_abs_deg": 132.0 if opposite else 24.0,
                    "robot_lateral_error_m": 0.08,
                    "robot_yaw_error_deg": 45.0,
                },
            },
            "random_draw": {
                "opposite_side_of_circle": opposite,
                "ball_target_angle_deg": 145.0 if opposite else 20.0,
                "ball_target_distance_m": 0.7,
                "robot_ball_distance_m": 1.1,
                "robot_ball_relative_bearing_abs_deg": 132.0 if opposite else 24.0,
                "robot_lateral_error_m": 0.08,
                "robot_yaw_error_deg": 45.0,
            },
        },
    )
    return str(path)


def _row(tmp_path: Path, scene_id: str, *, route: str, opposite: bool = False, success: bool = True) -> dict:
    return {
        "scene_id": scene_id,
        "route_label": route,
        "layout_path": _layout(tmp_path, scene_id, opposite=opposite),
        "mission_summary_path": f"artifacts/session/{scene_id}/mission_verdict.json",
        "visual_package_summary_path": f"artifacts/session/{scene_id}/fetch_visual_uat_package/package_summary.json",
        "mission": {
            "fetch_to_pose_pass": success,
            "closest_approach_distance_m": 0.196,
            "measured_push_ready_handoff_required": True,
            "measured_push_ready_handoff_pass": success,
            "pre_fetch_local_recovery_applied": route == "nav2_reposition_first",
            "pre_fetch_local_recovery_reason": "pre_contact_nav2_failure_inside_wide_setup_fallback_envelope"
            if route == "nav2_reposition_first"
            else "",
        },
        "visual_package": {"pass": success},
    }


def test_open_field_rollup_counts_strict_successes_and_dedupes_reruns(tmp_path, monkeypatch):
    monkeypatch.setattr(rollup, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(rollup, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    rows = [
        _row(tmp_path, "opbehind_nav2_opposite_circle_left_07", route="nav2_reposition_first", opposite=True),
        _row(tmp_path, "fetch_ready_10", route="fetch_ready_local"),
        _row(tmp_path, "recovery_11", route="recovery_or_reaim"),
        _row(tmp_path, "behind_left_01", route="nav2_reposition_first", success=False),
        _row(tmp_path, "behind_left_01", route="nav2_reposition_first"),
        _row(tmp_path, "opposite_left_deep_13", route="nav2_reposition_first", opposite=True),
        _row(tmp_path, "opposite_right_deep_14", route="nav2_reposition_first", opposite=True),
    ]
    batch = _write_json(tmp_path / "batch_summary.json", {"rows": rows})

    summary = rollup.summarize_rollup(
        SimpleNamespace(
            campaign_id="rollup",
            batch_summary=[str(batch)],
            min_successes=6,
            min_opposite_successes=3,
        )
    )

    assert summary["pass"] is True
    assert summary["attempt_count"] == 7
    assert summary["distinct_scene_count"] == 6
    assert summary["strict_success_count"] == 6
    assert summary["strict_failure_count"] == 0
    assert summary["opposite_success_count"] == 3
    assert summary["pinned_previous_opposite_failure_success"] is True
    assert summary["pre_fetch_local_recovery_applied_success_count"] == 4


def test_open_field_rollup_rejects_visual_delivery_without_push_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(rollup, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(rollup, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    row = _row(tmp_path, "opbehind_nav2_opposite_circle_left_07", route="nav2_reposition_first", opposite=True)
    row["mission"]["measured_push_ready_handoff_pass"] = False
    batch = _write_json(tmp_path / "batch_summary.json", {"rows": [row]})

    summary = rollup.summarize_rollup(
        SimpleNamespace(
            campaign_id="rollup",
            batch_summary=[str(batch)],
            min_successes=1,
            min_opposite_successes=1,
        )
    )

    assert summary["pass"] is False
    assert summary["strict_success_count"] == 0
    assert summary["strict_failure_count"] == 1
    assert "strict_success_count_below_minimum" in summary["issues"]
    assert "pinned_opposite_failure_shape_not_successful" in summary["issues"]
