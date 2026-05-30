from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_saved_anchor_setup_contact_audit as audit  # noqa: E402
from llm_supervisor_core import write_json  # noqa: E402


def _summary(
    *,
    campaign_id: str,
    layout: str,
    passed: bool,
    failure_reason: str = "",
    closest: float = 0.25,
    nav2_status: str = "monitor_success",
    monitor_reason: str = "success",
    lateral_error: float = 0.0,
    alignment_deg: float = 0.0,
    stage_labels: list[str] | None = None,
    maneuver: str = "coast_accept",
    guard_reasons: list[str] | None = None,
    ball_moved_since_fetch: bool = True,
) -> dict:
    return {
        "campaign_id": campaign_id,
        "requested_target_layout_json": f"ros2_config/target_layouts/golf_ball_circle_delivery_{layout}.json",
        "requested_fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        "fetch_to_pose_pass_count": 1 if passed else 0,
        "fetch_to_pose_failure_reasons": [] if not failure_reason else [failure_reason],
        "runs": [
            {
                "fetch_to_pose_pass": passed,
                    "fetch_to_pose_failure_reason": failure_reason,
                    "fetch_delivery_radius_m": 0.3,
                    "first_contact_push_alignment_deg": alignment_deg,
                    "shot_outcome": {
                    "reason": "trajectory_intersects_delivery_radius" if passed else failure_reason,
                    "closest_approach_distance_m": closest,
                    "distance_to_fetch_pose_m": closest,
                    "delivery_radius_m": 0.3,
                    "fetch_ball_moved_since_fetch": ball_moved_since_fetch,
                    "nav2_follow_path_corridor_push": {
                        "dispatch_status": nav2_status,
                        "monitor_cancel_reason": monitor_reason,
                        "monitor_sample": {
                            "lateral_error_m": lateral_error,
                            "delivery_distance_m": closest,
                            "robot_ball_distance_m": 0.15,
                        },
                        "path_progress_last": {"terminal_yaw_error_deg": 4.0},
                    },
                    "ai_push_coast_proposal": {
                        "maneuver_class": maneuver,
                        "relative_errors": {
                            "robot_lateral_error_m": 0.02,
                            "robot_yaw_error_deg": 3.0,
                        },
                        "stage_classification": {
                            "stage_labels": list(stage_labels or []),
                        },
                    },
                    "ai_push_coast_guard": {
                        "accepted": False,
                        "reasons": list(guard_reasons or ["shadow_mode"]),
                    },
                    "ai_push_coast_shadow": {
                        "stage_classification": {
                            "stage_labels": list(stage_labels or []),
                        },
                    },
                },
            }
        ],
    }


def test_saved_anchor_audit_classifies_setup_contact_blocker(tmp_path):
    path = tmp_path / "right05_summary.json"
    write_json(
        path,
        _summary(
            campaign_id="right05",
            layout="right05",
            passed=False,
            failure_reason="missed_delivery_radius_after_nav2_corridor_push_ball_escape",
            closest=0.888115,
            nav2_status="monitor_ball_escape",
            monitor_reason="ball_escape",
            lateral_error=-0.527398,
            alignment_deg=115.0,
            stage_labels=["setup"],
            maneuver="stay_with_nav2",
        ),
    )

    summary = audit.analyze([str(path)])

    row = summary["saved_anchors"][0]
    assert summary["overall_interpretation"] == "repair_setup_contact_before_guarded_live"
    assert row["layout"] == "right05"
    assert row["interpretation"] == "setup_contact_blocker"
    assert row["recommended_next_action"] == "repair_setup_contact_before_guarded_live"
    assert row["stage_labels"] == ["setup", "first_contact", "push_coast", "terminal_arrival"]
    assert row["monitor_lateral_error_m"] == -0.527398


def test_saved_anchor_audit_preserves_terminal_candidate(tmp_path):
    path = tmp_path / "left05_summary.json"
    write_json(
        path,
        _summary(
            campaign_id="left05",
            layout="left05",
            passed=False,
            failure_reason="missed_delivery_radius_after_fetch_to_pose_ball_stopped_short",
            closest=0.451645,
            nav2_status="goal_succeeded",
            monitor_reason="",
            stage_labels=["terminal_arrival"],
            maneuver="terminal_repush",
        ),
    )

    summary = audit.analyze([str(path)])

    row = summary["saved_anchors"][0]
    assert summary["overall_interpretation"] == "guarded_live_terminal_probe_ready"
    assert row["interpretation"] == "guarded_live_terminal_candidate"
    assert row["recommended_next_action"] == "run_narrow_terminal_correction_probe"
    assert row["closest_approach_distance_m"] == 0.451645


def test_saved_anchor_audit_marks_clean_pass_for_ladder(tmp_path):
    path = tmp_path / "zero_summary.json"
    write_json(path, _summary(campaign_id="zero", layout="zero", passed=True, closest=0.0))

    summary = audit.analyze([str(path)])

    row = summary["saved_anchors"][0]
    assert summary["overall_interpretation"] == "saved_anchor_ladder_ready"
    assert row["interpretation"] == "saved_anchor_pass"
    assert row["recommended_next_action"] == "continue_saved_anchor_ladder"


def test_saved_anchor_audit_keeps_passing_contact_watch_on_repeatability_ladder(tmp_path):
    path = tmp_path / "left05_summary.json"
    write_json(
        path,
        _summary(
            campaign_id="left05",
            layout="left05",
            passed=True,
            closest=0.16,
            stage_labels=["setup", "terminal_arrival"],
        ),
    )

    summary = audit.analyze([str(path)])

    row = summary["saved_anchors"][0]
    assert summary["overall_interpretation"] == "saved_anchor_repeatability_ready_with_contact_watch"
    assert row["interpretation"] == "saved_anchor_pass_with_contact_watch"
    assert row["recommended_next_action"] == "run_repeatability_ladder_with_contact_watch"


def test_saved_anchor_audit_treats_no_object_motion_as_first_contact_blocker(tmp_path):
    path = tmp_path / "right05_no_contact_summary.json"
    write_json(
        path,
        _summary(
            campaign_id="right05",
            layout="right05",
            passed=False,
            failure_reason="missed_delivery_radius_after_fetch_to_pose_ball_stopped_short",
            closest=0.568987,
            nav2_status="goal_succeeded",
            monitor_reason="",
            stage_labels=["terminal_arrival"],
            maneuver="terminal_repush",
            guard_reasons=["object_motion_not_observed"],
            ball_moved_since_fetch=False,
        ),
    )

    summary = audit.analyze([str(path)])

    row = summary["saved_anchors"][0]
    assert summary["overall_interpretation"] == "repair_setup_contact_before_guarded_live"
    assert row["interpretation"] == "setup_contact_blocker"
    assert "first_contact" in row["stage_labels"]


def test_saved_anchor_audit_uses_failed_representative_for_partial_repeatability(tmp_path):
    path = tmp_path / "right05_repeat_summary.json"
    payload = _summary(
        campaign_id="right05",
        layout="right05",
        passed=False,
        failure_reason="missed_delivery_radius_after_fetch_to_pose_ball_stopped_short",
        closest=0.463904,
        nav2_status="goal_succeeded",
        monitor_reason="",
        stage_labels=["terminal_arrival"],
        maneuver="terminal_repush",
        guard_reasons=["object_motion_not_observed"],
        ball_moved_since_fetch=False,
    )
    passing_run = _summary(campaign_id="right05", layout="right05", passed=True, closest=0.244184)["runs"][0]
    payload["runs"].append(passing_run)
    payload["required_green_runs"] = 2
    payload["fetch_to_pose_pass_count"] = 1
    payload["fetch_to_pose_fail_count"] = 1
    payload["promotion_gate_pass"] = False
    write_json(path, payload)

    summary = audit.analyze([str(path)])

    row = summary["saved_anchors"][0]
    assert row["pass"] is False
    assert row["closest_approach_distance_m"] == 0.463904
    assert row["interpretation"] == "setup_contact_blocker"
    assert summary["overall_interpretation"] == "repair_setup_contact_before_guarded_live"
