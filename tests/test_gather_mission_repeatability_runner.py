from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_mission_repeatability_runner as repeatability_runner  # noqa: E402


def test_parse_args_allows_region_funnel_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "region_funnel_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "region_funnel_v1"


def test_parse_args_allows_nav2_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "nav2_reacquire_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "nav2_reacquire_v1"


def test_parse_args_allows_constrained_local_planner_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "constrained_local_planner_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "constrained_local_planner_v1"


def test_parse_args_allows_docking_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "docking_reacquire_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "docking_reacquire_v1"


def test_parse_args_allows_handoff_yaw_servo_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "handoff_yaw_servo_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "handoff_yaw_servo_v1"


def test_parse_args_allows_pre_stage_reacquire_fsm_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "pre_stage_reacquire_fsm_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "pre_stage_reacquire_fsm_v1"


def test_parse_args_allows_pre_stage_path_tracker_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "pre_stage_path_tracker_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "pre_stage_path_tracker_v1"


def test_parse_args_allows_pre_stage_trajectory_owner_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "pre_stage_trajectory_owner_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "pre_stage_trajectory_owner_v1"


def test_parse_args_allows_nav2_follow_path_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "nav2_follow_path_reacquire_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "nav2_follow_path_reacquire_v1"


def test_parse_args_allows_nav2_mppi_follow_path_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "nav2_mppi_follow_path_reacquire_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "nav2_mppi_follow_path_reacquire_v1"


def test_parse_args_allows_object_centric_gather_policy_v1(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        ["repeatability", "--gather-control-family", "object_centric_gather_policy_v1"],
    )

    args = repeatability_runner.parse_args()

    assert args.gather_control_family == "object_centric_gather_policy_v1"


def test_parse_args_allows_fetch_to_pose_objective(monkeypatch):
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        [
            "repeatability",
            "--mission-objective",
            "fetch_to_pose",
            "--fetch-target-x",
            "2.8",
            "--fetch-target-y",
            "-0.2",
            "--fetch-delivery-radius-m",
            "0.5",
        ],
    )

    args = repeatability_runner.parse_args()

    assert args.mission_objective == "fetch_to_pose"
    assert args.fetch_target_x == 2.8
    assert args.fetch_target_y == -0.2
    assert args.fetch_delivery_radius_m == 0.5


def test_ensure_environment_ready_noops_when_dashboard_already_ready(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_http_json(url: str, *, timeout_s: float, method: str = "GET", payload=None):
        calls.append((method, url))
        if url.endswith("/api/state"):
            return 200, {"environment_state": "environment_ready"}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)

    repeatability_runner.ensure_environment_ready("http://127.0.0.1:8860", timeout_s=5.0)

    assert calls == [("GET", "http://127.0.0.1:8860/api/state")]


def test_ensure_environment_ready_starts_dashboard_when_stopped(monkeypatch):
    calls: list[tuple[str, str]] = []
    state_responses = iter(
        [
            {"environment_state": "stopped"},
            {"environment_state": "starting"},
            {"environment_state": "environment_ready"},
        ]
    )

    def fake_http_json(url: str, *, timeout_s: float, method: str = "GET", payload=None):
        calls.append((method, url))
        if url.endswith("/api/state"):
            return 200, next(state_responses)
        if url.endswith("/api/env/start"):
            assert method == "POST"
            assert payload == {"scenario_id": "corral_single_ball_place", "world_file": "short_turf.world"}
            return 202, {"accepted": True, "message": "environment start queued"}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)
    monkeypatch.setattr(repeatability_runner.time, "sleep", lambda *_args, **_kwargs: None)

    repeatability_runner.ensure_environment_ready(
        "http://127.0.0.1:8860",
        timeout_s=5.0,
        startup_payload={"scenario_id": "corral_single_ball_place", "world_file": "short_turf.world"},
    )

    assert calls == [
        ("GET", "http://127.0.0.1:8860/api/state"),
        ("POST", "http://127.0.0.1:8860/api/env/start"),
        ("GET", "http://127.0.0.1:8860/api/state"),
        ("GET", "http://127.0.0.1:8860/api/state"),
    ]


def test_prepare_direct_environment_resets_ready_session_with_profile(monkeypatch):
    responses = iter(
        [
            (200, {"environment_state": "environment_ready", "session_id": "old-session"}),
            (202, {"accepted": True, "message": "sim reset queued"}),
            (200, {"environment_state": "starting", "session_id": "old-session"}),
            (200, {"environment_state": "environment_ready", "session_id": "new-session"}),
        ]
    )
    calls: list[tuple[str, str, object]] = []

    def fake_http_json(url: str, *, timeout_s: float, method: str = "GET", payload=None):
        calls.append((method, url, payload))
        return next(responses)

    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)
    monkeypatch.setattr(repeatability_runner.time, "sleep", lambda *_args, **_kwargs: None)

    args = repeatability_runner.argparse.Namespace(
        dashboard_url="http://127.0.0.1:8860",
        scenario_id="corral_single_ball_place",
        world_file="yolo_test_world_v6_clean_uat_short_turf.world",
        surface_profile="short_turf",
        timeout_s=30.0,
    )

    ready_state = repeatability_runner.prepare_direct_environment(args)

    assert ready_state["session_id"] == "new-session"
    assert calls[1] == (
        "POST",
        "http://127.0.0.1:8860/api/sim/reset",
        {
            "scenario_id": "corral_single_ball_place",
            "world_file": "yolo_test_world_v6_clean_uat_short_turf.world",
            "surface_profile": "short_turf",
        },
    )


def test_latest_mission_verdict_path_maps_container_repo_path(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(repeatability_runner, "REPO_ROOT", tmp_path)

    path = repeatability_runner._latest_mission_verdict_path(
        {
            "latest_artifacts": {
                "mission_verdict": "/workspaces/chasecar/artifacts/session/s1/golf/mission_verdict.json",
            }
        }
    )

    assert path == str(tmp_path / "artifacts" / "session" / "s1" / "golf" / "mission_verdict.json")


def test_prepare_direct_environment_starts_stopped_session_with_profile(monkeypatch):
    responses = iter(
        [
            (200, {"environment_state": "stopped", "session_id": ""}),
            (200, {"environment_state": "stopped"}),
            (202, {"accepted": True, "message": "environment start queued"}),
            (200, {"environment_state": "starting", "session_id": ""}),
            (200, {"environment_state": "environment_ready", "session_id": "fresh-session"}),
            (200, {"environment_state": "environment_ready", "session_id": "fresh-session"}),
        ]
    )
    calls: list[tuple[str, str, object]] = []

    def fake_http_json(url: str, *, timeout_s: float, method: str = "GET", payload=None):
        calls.append((method, url, payload))
        return next(responses)

    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)
    monkeypatch.setattr(repeatability_runner.time, "sleep", lambda *_args, **_kwargs: None)

    args = repeatability_runner.argparse.Namespace(
        dashboard_url="http://127.0.0.1:8860",
        scenario_id="gather_three_ball_zone",
        world_file="yolo_test_world_v6_clean_uat_short_turf.world",
        surface_profile="short_turf",
        timeout_s=30.0,
    )

    ready_state = repeatability_runner.prepare_direct_environment(args)

    assert ready_state["session_id"] == "fresh-session"
    assert ("POST", "http://127.0.0.1:8860/api/env/start", {
        "scenario_id": "gather_three_ball_zone",
        "world_file": "yolo_test_world_v6_clean_uat_short_turf.world",
        "surface_profile": "short_turf",
    }) in calls


def test_wait_for_dashboard_slot_waits_until_scenario_not_running(monkeypatch):
    ensure_calls: list[tuple[str, float]] = []
    state_responses = iter(
        [
            {"environment_state": "environment_ready", "scenario_state": "running"},
            {"environment_state": "environment_ready", "scenario_state": "ready"},
        ]
    )

    def fake_ensure_environment_ready(dashboard_url: str, timeout_s: float) -> None:
        ensure_calls.append((dashboard_url, timeout_s))

    def fake_http_json(url: str, *, timeout_s: float, method: str = "GET", payload=None):
        assert method == "GET"
        assert url == "http://127.0.0.1:8860/api/state"
        return 200, next(state_responses)

    monkeypatch.setattr(repeatability_runner, "ensure_environment_ready", fake_ensure_environment_ready)
    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)
    monkeypatch.setattr(repeatability_runner.time, "sleep", lambda *_args, **_kwargs: None)

    repeatability_runner.wait_for_dashboard_slot("http://127.0.0.1:8860", timeout_s=5.0)

    assert ensure_calls == [
        ("http://127.0.0.1:8860", 5.0),
        ("http://127.0.0.1:8860", 5.0),
    ]


def test_promotion_gate_pass_for_runs_requires_settled_corral_outcome():
    runs = [
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 0,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 1,
        },
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 1,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": False,
            "rolled_away_after_release": False,
            "post_visit_revisit_count": 0,
        },
    ]

    assert repeatability_runner.promotion_gate_pass_for_runs(runs, mode="pass_only") is False
    assert repeatability_runner.promotion_gate_pass_for_runs(runs, mode="strict") is False


def test_promotion_gate_pass_for_runs_supports_three_ball_final_corral_outcome():
    runs = [
        {
            "scenario_id": "gather_three_ball_zone",
            "pass": True,
            "mission_completed_pass": True,
            "final_all_targets_inside_retrieval_corral": True,
            "final_all_targets_stopped": True,
            "final_three_ball_corral_pass": True,
            "post_visit_revisit_count": 0,
        }
    ]

    assert repeatability_runner.promotion_gate_pass_for_runs(runs, mode="pass_only") is True
    assert repeatability_runner.promotion_gate_pass_for_runs(runs, mode="strict") is True


def test_approach_side_rollup_uses_fresh_attempt_fields_even_when_run_fails():
    runs = [
        {
            "pass": False,
            "fresh_attempt_approach": {
                "pass": True,
                "reason": "",
                "pre_stage": {
                    "pose_world": {"x": 1.5, "y": 0.0, "yaw_deg": 90.0},
                    "pose_reached": True,
                    "time_s": 0.75,
                    "handoff_pass": True,
                },
                "stage": {
                    "pose_reached": True,
                    "time_s": 1.5,
                },
                "capture_entry": {
                    "pass": True,
                    "entered_goal_side_before_capture": False,
                    "first_contact_push_alignment_deg": 10.0,
                    "push_direction_yaw_deg": 5.0,
                    "failure_reason": "",
                },
            },
        },
        {
            "pass": False,
            "latest_approach_progress": {
                "pass": False,
                "reason": "capture_entry_timeout",
                "pre_stage": {
                    "pose_world": {"x": 1.45, "y": 0.18, "yaw_deg": 90.0},
                    "pose_reached": True,
                    "time_s": 1.5,
                    "handoff_pass": True,
                },
                "stage": {
                    "pose_reached": True,
                    "time_s": 2.25,
                },
                "capture_entry": {
                    "pass": False,
                    "entered_goal_side_before_capture": False,
                    "first_contact_push_alignment_deg": 18.0,
                    "push_direction_yaw_deg": 170.0,
                    "failure_reason": "capture_entry_timeout",
                },
            },
            "fresh_attempt_approach": {
                "pass": False,
                "reason": "entered_goal_side_before_capture",
                "pre_stage": {
                    "pose_world": {"x": 1.4, "y": 0.2, "yaw_deg": 90.0},
                    "pose_reached": False,
                    "time_s": 1.25,
                    "handoff_pass": False,
                },
                "stage": {
                    "pose_reached": False,
                    "time_s": 1.75,
                },
                "capture_entry": {
                    "pass": False,
                    "entered_goal_side_before_capture": True,
                    "first_contact_push_alignment_deg": 25.0,
                    "push_direction_yaw_deg": 180.0,
                    "failure_reason": "entered_goal_side_before_capture",
                },
            },
        },
    ]

    rollup = repeatability_runner._approach_side_rollup(runs)

    assert rollup["fresh_attempt_approach_pass_count"] == 1
    assert rollup["fresh_attempt_approach_fail_count"] == 1
    assert rollup["fresh_attempt_pre_stage_pose_reached_count"] == 1
    assert rollup["approach_side_pass_count"] == 1
    assert rollup["pre_stage_pose_reached_count"] == 2
    assert rollup["pre_stage_handoff_pass_count"] == 2
    assert rollup["fresh_attempt_capture_entry_pass_count"] == 1
    assert rollup["pre_stage_time_avg_s"] == 1.125
    assert rollup["pre_stage_time_min_s"] == 0.75
    assert rollup["pre_stage_time_max_s"] == 1.5
    assert rollup["staging_pose_reached_count"] == 2
    assert rollup["entered_goal_side_before_capture_count"] == 0
    assert rollup["approach_side_reasons"] == ["capture_entry_timeout"]
    assert rollup["fresh_attempt_approach_reasons"] == ["entered_goal_side_before_capture"]
    assert rollup["fresh_attempt_capture_entry_failure_reasons"] == ["entered_goal_side_before_capture"]


def test_approach_side_rollup_uses_latest_retry_progress_for_top_level_counts():
    runs = [
        {
            "pass": False,
            "fresh_attempt_approach": {
                "pass": False,
                "reason": "entered_goal_side_before_capture",
                "pre_stage": {
                    "pose_world": {"x": 0.1, "y": 0.0, "yaw_deg": 90.0},
                    "pose_reached": True,
                    "time_s": 1.0,
                    "handoff_pass": True,
                },
                "stage": {
                    "pose_reached": True,
                    "time_s": 0.75,
                },
                "capture_entry": {
                    "pass": False,
                    "entered_goal_side_before_capture": True,
                    "first_contact_push_alignment_deg": None,
                    "push_direction_yaw_deg": 15.0,
                    "failure_reason": "entered_goal_side_before_capture",
                },
            },
            "latest_approach_progress": {
                "pass": False,
                "reason": "capture_entry_timeout",
                "pre_stage": {
                    "pose_world": {"x": 0.25, "y": 0.05, "yaw_deg": 90.0},
                    "pose_reached": True,
                    "time_s": 2.5,
                    "handoff_pass": True,
                },
                "stage": {
                    "pose_reached": True,
                    "time_s": 1.5,
                },
                "capture_entry": {
                    "pass": False,
                    "entered_goal_side_before_capture": False,
                    "first_contact_push_alignment_deg": 7.5,
                    "push_direction_yaw_deg": 90.0,
                    "time_s": 4.0,
                    "failure_reason": "capture_entry_timeout",
                },
            },
        }
    ]

    rollup = repeatability_runner._approach_side_rollup(runs)

    assert rollup["fresh_attempt_capture_entry_goal_side_entry_count"] == 1
    assert rollup["fresh_attempt_approach_reasons"] == ["entered_goal_side_before_capture"]
    assert rollup["fresh_attempt_pre_stage_time_avg_s"] == 1.0
    assert rollup["entered_goal_side_before_capture_count"] == 0
    assert rollup["approach_side_reasons"] == ["capture_entry_timeout"]
    assert rollup["approach_failure_reasons"] == ["capture_entry_timeout"]
    assert rollup["pre_stage_time_avg_s"] == 2.5
    assert rollup["stage_time_avg_s"] == 1.5
    assert rollup["latest_approach_progress_pass_count"] == 0
    assert rollup["latest_approach_capture_entry_goal_side_entry_count"] == 0


def test_approach_side_rollup_infers_goal_side_entry_from_approach_reason():
    runs = [
        {
            "pass": False,
            "approach_failure_reason": "entered_goal_side_before_capture",
            "pre_stage_pose_reached": False,
            "pre_stage_handoff_pass": False,
            "pre_stage_time_s": 30.0,
        }
    ]

    rollup = repeatability_runner._approach_side_rollup(runs)

    assert rollup["fresh_attempt_capture_entry_goal_side_entry_count"] == 1
    assert rollup["latest_approach_capture_entry_goal_side_entry_count"] == 1
    assert rollup["entered_goal_side_before_capture_count"] == 1
    assert rollup["fresh_attempt_approach_reasons"] == ["entered_goal_side_before_capture"]
    assert rollup["approach_side_reasons"] == ["entered_goal_side_before_capture"]


def test_enrich_run_with_approach_side_fields_preserves_summary_fresh_attempt(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    summary_path = mission_root / "summary.json"
    verdict_path = mission_root / "mission_verdict.json"
    summary_payload = {
        "fresh_attempt_approach": {
            "pass": True,
            "reason": "",
            "pre_stage": {
                "pose_world": {"x": 1.6, "y": -0.1, "yaw_deg": 90.0},
                "pose_reached": True,
                "time_s": 0.625,
                "handoff_pass": True,
            },
            "stage": {
                "pose_reached": True,
                "time_s": 0.875,
            },
            "capture_entry": {
                "pass": True,
                "entered_goal_side_before_capture": False,
                "first_contact_push_alignment_deg": 9.5,
                "push_direction_yaw_deg": 2.0,
                "failure_reason": "",
            },
        }
    }
    verdict_payload = {
        "pass": False,
        "mission_completed_pass": True,
        "release_gate_blocked_reason": "no_secure_capture",
        "settled_in_corral_pass": False,
    }
    summary_path.write_text(json.dumps(summary_payload), encoding="utf-8")
    verdict_path.write_text(json.dumps(verdict_payload), encoding="utf-8")

    enriched = repeatability_runner._enrich_run_with_approach_side_fields(
        {
            "mission_verdict_path": str(verdict_path),
            "summary_path": str(summary_path),
        }
    )

    assert enriched["fresh_attempt_approach"]["pass"] is True
    assert enriched["fresh_attempt_approach"]["pre_stage"]["pose_world"] == {"x": 1.6, "y": -0.1, "yaw_deg": 90.0}
    assert enriched["fresh_attempt_approach"]["pre_stage"]["handoff_pass"] is True
    assert enriched["fresh_attempt_approach"]["stage"]["pose_reached"] is True
    assert enriched["fresh_attempt_approach"]["capture_entry"]["pass"] is True
    assert enriched["approach_side_pass"] is True
    assert enriched["pre_stage_pose_reached"] is True
    assert enriched["staging_pose_reached"] is True
    assert enriched["entered_goal_side_before_capture"] is False


def test_summarize_gather_artifacts_reads_clean_retention_fields(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    (mission_root / "summary.json").write_text(
        json.dumps(
            {
                "pass": False,
                "mission_completed_pass": True,
                "capture_loss_count": 1,
                "handoff_kind": "zone_entry",
                "settle_exit_reason": "timeout",
                "zone_edge_correction_count": 2,
                "place_controller_reentry_count": 1,
                "post_visit_revisit_count": 0,
                "settle_no_chase_activated": True,
                "settle_no_chase_exit_reason": "settled",
                "release_gate_blocked_reason": "none",
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "clean_retention_pass": False,
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": False,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": False,
            }
        ),
        encoding="utf-8",
    )
    verdict_path.write_text(
        json.dumps(
            {
                "pass": False,
                "mission_completed_pass": True,
                "capture_loss_count": 1,
                "handoff_kind": "zone_entry",
                "settle_exit_reason": "timeout",
                "zone_edge_correction_count": 2,
                "place_controller_reentry_count": 1,
                "post_visit_revisit_count": 0,
                "settle_no_chase_activated": True,
                "settle_no_chase_exit_reason": "settled",
                "release_gate_blocked_reason": "none",
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "stop_capture_state": {"captured": True},
                "release_capture_state": {"captured": True},
                "clean_retention_pass": False,
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": False,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": False,
                "placed_count": 1,
                "surface_profile": "short_turf",
            }
        ),
        encoding="utf-8",
    )
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["pass"] is False
    assert summary["mission_completed_pass"] is True
    assert summary["capture_loss_count"] == 1
    assert summary["handoff_kind"] == "zone_entry"
    assert summary["settle_exit_reason"] == "timeout"
    assert summary["zone_edge_correction_count"] == 2
    assert summary["place_controller_reentry_count"] == 1
    assert summary["post_visit_revisit_count"] == 0
    assert summary["settle_no_chase_activated"] is True
    assert summary["settle_no_chase_exit_reason"] == "settled"
    assert summary["release_gate_blocked_reason"] == "none"
    assert summary["stopped_with_ball_captured"] is True
    assert summary["release_started_with_capture"] is True
    assert summary["clean_retention_pass"] is False
    assert summary["final_inside_retrieval_corral"] is True
    assert summary["final_center_inside_zone"] is True
    assert summary["ball_stopped_in_corral"] is False
    assert summary["rolled_away_after_release"] is False
    assert summary["settled_in_corral_pass"] is False


def test_summarize_gather_artifacts_reads_fetch_to_pose_fields(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    shot_outcome = {
        "pass": True,
        "reason": "trajectory_intersects_delivery_radius",
        "closest_approach_distance_m": 0.12,
    }
    verdict_path.write_text(
        json.dumps(
            {
                "pass": True,
                "mission_completed_pass": True,
                "mission_objective": "fetch_to_pose",
                "fetch_to_pose_reached": True,
                "fetch_to_pose_pass": True,
                "fetch_to_pose_time_s": 4.25,
                "fetch_to_pose_failure_reason": "",
                "fetch_pose_world": {"x": 2.4, "y": 0.0, "z": 0.001, "radius_m": 0.5},
                "fetch_delivery_radius_m": 0.5,
                "shot_outcome": shot_outcome,
                "placed_count": 1,
                "surface_profile": "short_turf",
            }
        ),
        encoding="utf-8",
    )
    (mission_root / "summary.json").write_text(json.dumps({}), encoding="utf-8")
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["mission_objective"] == "fetch_to_pose"
    assert summary["fetch_to_pose_reached"] is True
    assert summary["fetch_to_pose_pass"] is True
    assert summary["fetch_to_pose_time_s"] == 4.25
    assert summary["fetch_pose_world"]["radius_m"] == 0.5
    assert summary["shot_outcome"] == shot_outcome


def test_summarize_gather_artifacts_preserves_fresh_attempt_approach_across_release_failure(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    fresh_attempt_approach = {
        "pass": True,
        "reason": "",
        "pre_stage": {
            "pose_world": {"x": 1.5, "y": -0.2, "yaw_deg": 90.0},
            "pose_reached": True,
            "time_s": 0.5,
            "handoff_pass": True,
        },
        "stage": {
            "pose_reached": True,
            "time_s": 0.75,
        },
        "capture_entry": {
            "pass": True,
            "entered_goal_side_before_capture": False,
            "first_contact_push_alignment_deg": 8.0,
            "push_direction_yaw_deg": 1.5,
            "failure_reason": "",
        },
    }
    (mission_root / "summary.json").write_text(
        json.dumps(
            {
                "pass": False,
                "mission_completed_pass": True,
                "fresh_attempt_approach": fresh_attempt_approach,
            }
        ),
        encoding="utf-8",
    )
    verdict_path.write_text(
        json.dumps(
            {
                "pass": False,
                "mission_completed_pass": True,
                "release_gate_blocked_reason": "no_secure_capture",
                "settled_in_corral_pass": False,
            }
        ),
        encoding="utf-8",
    )
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["pass"] is False
    assert summary["mission_completed_pass"] is True
    assert summary["release_gate_blocked_reason"] == "no_secure_capture"
    assert summary["fresh_attempt_approach"] == fresh_attempt_approach
    assert summary["approach_side_pass"] is True
    assert summary["pre_stage_pose_world"] == {"x": 1.5, "y": -0.2, "yaw_deg": 90.0}
    assert summary["pre_stage_pose_reached"] is True
    assert summary["pre_stage_handoff_pass"] is True
    assert summary["staging_pose_reached"] is True
    assert summary["entered_goal_side_before_capture"] is False


def test_summarize_gather_artifacts_reads_pre_stage_fields(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    payload = {
        "pass": True,
        "mission_completed_pass": True,
        "scenario_id": "corral_single_ball_place",
        "pre_stage": {
            "pose_world": {"x": 1.5, "y": -0.25, "yaw_deg": 90.0},
        },
        "pre_stage_pose_reached": True,
        "pre_stage_time_s": 0.875,
        "pre_stage_handoff_pass": True,
        "approach_side_verdict": {"pass": True, "reason": ""},
        "staging_pose_reached": True,
        "entered_goal_side_before_capture": False,
    }
    (mission_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
    verdict_path.write_text(json.dumps(payload), encoding="utf-8")
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["pre_stage_pose_world"] == {"x": 1.5, "y": -0.25, "yaw_deg": 90.0}
    assert summary["pre_stage_pose_reached"] is True
    assert summary["pre_stage_time_s"] == 0.875
    assert summary["pre_stage_handoff_pass"] is True
    assert summary["fresh_attempt_approach"]["pass"] is True
    assert summary["fresh_attempt_approach"]["pre_stage"]["pose_world"] == {"x": 1.5, "y": -0.25, "yaw_deg": 90.0}
    assert summary["fresh_attempt_approach"]["pre_stage"]["pose_reached"] is True
    assert summary["fresh_attempt_approach"]["pre_stage"]["handoff_pass"] is True
    assert summary["fresh_attempt_approach"]["stage"]["pose_reached"] is True
    assert summary["fresh_attempt_approach"]["capture_entry"]["pass"] is True
    assert summary["fresh_attempt_approach"]["capture_entry"]["entered_goal_side_before_capture"] is False


def test_summarize_gather_artifacts_prefers_close_in_pre_stage_without_goal_side_headline(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    payload = {
        "pass": False,
        "mission_completed_pass": False,
        "scenario_id": "corral_single_ball_place",
        "failure_reason": "capture_entry_timeout",
        "failure_stage": "capture_entry",
        "approach_side_verdict": {"pass": False, "reason": "capture_entry_timeout"},
        "pre_stage_pose_reached": True,
        "pre_stage_handoff_pass": True,
        "staging_pose_reached": True,
        "entered_goal_side_before_capture": False,
        "approach_failure_reason": "capture_entry_timeout",
        "latest_approach_progress": {
            "pass": False,
            "reason": "capture_entry_timeout",
            "pre_stage": {
                "pose_world": {"x": 0.1, "y": 0.0, "yaw_deg": 0.0},
                "pose_reached": True,
                "time_s": 0.55,
                "handoff_pass": True,
            },
            "stage": {
                "pose_reached": True,
                "time_s": 0.8,
            },
            "capture_entry": {
                "pass": False,
                "entered_goal_side_before_capture": False,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": 0.0,
                "time_s": 4.0,
                "failure_reason": "capture_entry_timeout",
            },
        },
        "fresh_attempt_approach": {
            "pass": False,
            "reason": "entered_goal_side_before_capture",
            "pre_stage": {
                "pose_world": {},
                "pose_reached": False,
                "time_s": 0.0,
                "handoff_pass": False,
            },
            "stage": {
                "pose_reached": False,
                "time_s": 0.0,
            },
            "capture_entry": {
                "pass": False,
                "entered_goal_side_before_capture": True,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": 0.0,
                "time_s": 0.0,
                "failure_reason": "entered_goal_side_before_capture",
            },
        },
    }
    (mission_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
    verdict_path.write_text(json.dumps(payload), encoding="utf-8")
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["pre_stage_pose_reached"] is True
    assert summary["pre_stage_handoff_pass"] is True
    assert summary["entered_goal_side_before_capture"] is False
    assert summary["approach_side_verdict"] == {"pass": False, "reason": "capture_entry_timeout"}
    assert summary["approach_side_reason"] == "capture_entry_timeout"
    assert summary["fresh_attempt_approach"]["pre_stage"]["pose_reached"] is False
    assert summary["fresh_attempt_approach"]["capture_entry"]["entered_goal_side_before_capture"] is True
    assert summary["fresh_attempt_approach"]["capture_entry"]["failure_reason"] == "entered_goal_side_before_capture"


def test_summarize_gather_artifacts_reads_three_ball_final_audit_fields(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    payload = {
        "pass": True,
        "mission_completed_pass": True,
        "scenario_id": "gather_three_ball_zone",
        "final_corral_audit": {
            "ball_a": {"distance_to_zone_center_m": 0.2, "inside_retrieval_corral": True, "stopped_in_corral": True},
            "ball_b": {"distance_to_zone_center_m": 0.2, "inside_retrieval_corral": True, "stopped_in_corral": True},
            "ball_c": {"distance_to_zone_center_m": 0.2, "inside_retrieval_corral": True, "stopped_in_corral": True},
        },
        "final_all_targets_inside_retrieval_corral": True,
        "final_all_targets_stopped": True,
        "final_three_ball_corral_pass": True,
        "retrieved_count": 3,
        "placed_count": 3,
        "surface_profile": "short_turf",
        "approach_side_verdict": {"pass": True, "reason": ""},
        "staging_pose_reached": True,
        "entered_goal_side_before_capture": False,
        "first_contact_push_alignment_deg": 11.5,
        "push_direction_yaw_deg": 0.0,
        "stage_time_s": 0.75,
        "approach_failure_reason": "",
        "settle_no_chase_activated": True,
        "settle_no_chase_exit_reason": "corrected",
        "release_gate_blocked_reason": "no_secure_capture",
    }
    (mission_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
    verdict_path.write_text(json.dumps(payload), encoding="utf-8")
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["final_all_targets_inside_retrieval_corral"] is True
    assert summary["final_all_targets_stopped"] is True
    assert summary["final_three_ball_corral_pass"] is True
    assert summary["retrieved_count"] == 3
    assert summary["settle_no_chase_activated"] is True
    assert summary["settle_no_chase_exit_reason"] == "corrected"
    assert summary["release_gate_blocked_reason"] == "no_secure_capture"
    assert set(summary["final_corral_audit"].keys()) == {"ball_a", "ball_b", "ball_c"}
    assert summary["mission_verdict"]["approach_side_verdict"] == {"pass": True, "reason": ""}
    assert summary["mission_verdict"]["entered_goal_side_before_capture"] is False
    assert summary["mission_verdict"]["first_contact_push_alignment_deg"] == 11.5
    assert summary["summary"]["approach_side_verdict"] == {"pass": True, "reason": ""}
    assert summary["summary"]["staging_pose_reached"] is True


def test_summarize_gather_artifacts_recomputes_fresh_approach_for_place_timeout(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    payload = {
        "pass": False,
        "mission_completed_pass": False,
        "scenario_id": "corral_single_ball_place",
        "failure_reason": "place_timeout",
        "failure_stage": "place",
        "surface_profile": "short_turf",
        "approach_side_verdict": {"pass": True, "reason": ""},
        "pre_stage_pose_reached": True,
        "pre_stage_handoff_pass": True,
        "staging_pose_reached": True,
        "capture_entry_reached": True,
        "capture_entry_time_s": 3.141,
        "first_contact_push_alignment_deg": None,
        "approach_failure_reason": "",
        "latest_approach_progress": {
            "pass": True,
            "reason": "",
            "pre_stage": {
                "pose_world": {"x": -1.548, "y": 0.0},
                "pose_reached": True,
                "time_s": 25.813,
                "handoff_pass": True,
            },
            "stage": {
                "pose_reached": True,
                "time_s": 5.812,
            },
            "capture_entry": {
                "pass": True,
                "entered_goal_side_before_capture": False,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": 0.0,
                "time_s": 3.141,
                "failure_reason": "",
            },
        },
        "fresh_attempt_approach": {
            "pass": False,
            "reason": "entered_goal_side_before_capture",
            "pre_stage": {
                "pose_world": {},
                "pose_reached": False,
                "time_s": 0.0,
                "handoff_pass": False,
            },
            "stage": {
                "pose_reached": False,
                "time_s": 0.0,
            },
            "capture_entry": {
                "pass": False,
                "entered_goal_side_before_capture": True,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": 0.0,
                "time_s": 0.0,
                "failure_reason": "entered_goal_side_before_capture",
            },
        },
    }
    (mission_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
    verdict_path.write_text(json.dumps(payload), encoding="utf-8")
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["mission_verdict"]["failure_reason"] == "place_timeout"
    assert summary["summary"]["failure_reason"] == "place_timeout"
    assert summary["approach_side_verdict"] == {"pass": True, "reason": ""}
    assert summary["approach_side_reason"] == ""
    assert summary["fresh_attempt_approach"]["pass"] is False
    assert summary["fresh_attempt_approach"]["capture_entry"]["pass"] is False
    assert summary["fresh_attempt_approach"]["capture_entry"]["failure_reason"] == "entered_goal_side_before_capture"


def test_summarize_gather_artifacts_preserves_close_in_pre_stage_success_before_capture_entry_timeout(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    verdict_path = mission_root / "mission_verdict.json"
    payload = {
        "pass": False,
        "mission_completed_pass": False,
        "scenario_id": "corral_single_ball_place",
        "failure_reason": "capture_entry_timeout",
        "failure_stage": "capture_entry",
        "surface_profile": "short_turf",
        "approach_side_verdict": {"pass": False, "reason": "capture_entry_timeout"},
        "pre_stage_pose_reached": True,
        "pre_stage_handoff_pass": True,
        "staging_pose_reached": True,
        "capture_entry_reached": True,
        "capture_entry_time_s": 4.0,
        "entered_goal_side_before_capture": False,
        "first_contact_push_alignment_deg": None,
        "approach_failure_reason": "capture_entry_timeout",
        "latest_approach_progress": {
            "pass": False,
            "reason": "capture_entry_timeout",
            "pre_stage": {
                "pose_world": {"x": 5.191657, "y": 2.791657},
                "pose_reached": True,
                "time_s": 30.359,
                "handoff_pass": True,
            },
            "stage": {
                "pose_reached": True,
                "time_s": 5.812,
            },
            "capture_entry": {
                "pass": False,
                "entered_goal_side_before_capture": False,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": -135.0,
                "time_s": 4.0,
                "failure_reason": "capture_entry_timeout",
            },
        },
        "fresh_attempt_approach": {
            "pass": False,
            "reason": "entered_goal_side_before_capture",
            "pre_stage": {
                "pose_world": {},
                "pose_reached": False,
                "time_s": 0.0,
                "handoff_pass": False,
            },
            "stage": {
                "pose_reached": False,
                "time_s": 0.0,
            },
            "capture_entry": {
                "pass": False,
                "entered_goal_side_before_capture": True,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": 0.0,
                "time_s": 0.0,
                "failure_reason": "entered_goal_side_before_capture",
            },
        },
    }
    (mission_root / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
    verdict_path.write_text(json.dumps(payload), encoding="utf-8")
    (mission_root / "target_results.json").write_text(json.dumps({"targets": []}), encoding="utf-8")

    summary = repeatability_runner.summarize_gather_artifacts(run_index=1, mission_verdict_path=str(verdict_path))

    assert summary["mission_verdict"]["failure_reason"] == "capture_entry_timeout"
    assert summary["summary"]["failure_reason"] == "capture_entry_timeout"
    assert summary["pre_stage_pose_world"] == {"x": 5.191657, "y": 2.791657}
    assert summary["pre_stage_pose_reached"] is True
    assert summary["pre_stage_handoff_pass"] is True
    assert summary["staging_pose_reached"] is True
    assert summary["capture_entry_reached"] is True
    assert summary["capture_entry_time_s"] == 4.0
    assert summary["entered_goal_side_before_capture"] is False
    assert summary["approach_side_verdict"] == {"pass": False, "reason": "capture_entry_timeout"}
    assert summary["approach_side_reason"] == "capture_entry_timeout"
    assert summary["latest_approach_progress"]["capture_entry"]["time_s"] == 4.0
    assert summary["fresh_attempt_approach"]["pre_stage"]["pose_reached"] is False
    assert summary["fresh_attempt_approach"]["capture_entry"]["failure_reason"] == "entered_goal_side_before_capture"


def test_run_dashboard_scenario_once_ignores_stale_error_result(monkeypatch):
    responses = iter(
        [
            (
                200,
                {
                    "session_id": "old-session",
                    "latest_artifacts": {"mission_verdict": "old-path"},
                    "mission_verdict": {"scenario_id": "corral_single_ball_place"},
                },
            ),
            (202, {"accepted": True}),
            (
                200,
                {
                    "scenario_state": "error",
                    "session_id": "old-session",
                    "latest_artifacts": {"mission_verdict": "old-path"},
                    "mission_verdict": {"scenario_id": "corral_single_ball_place"},
                },
            ),
            (
                200,
                {
                    "scenario_state": "error",
                    "session_id": "new-session",
                    "latest_artifacts": {"mission_verdict": "new-path"},
                    "mission_verdict": {"scenario_id": "corral_single_ball_place"},
                },
            ),
        ]
    )

    def fake_http_json(url: str, *, timeout_s: float, method: str = "GET", payload=None):
        return next(responses)

    captured_paths: list[str] = []

    def fake_summarize_gather_artifacts(*, run_index: int, mission_verdict_path: str):
        captured_paths.append(mission_verdict_path)
        return {"run_index": run_index, "mission_verdict_path": mission_verdict_path, "pass": False}

    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)
    monkeypatch.setattr(repeatability_runner, "summarize_gather_artifacts", fake_summarize_gather_artifacts)
    monkeypatch.setattr(repeatability_runner.time, "sleep", lambda *_args, **_kwargs: None)

    args = repeatability_runner.argparse.Namespace(
        dashboard_url="http://127.0.0.1:8860",
        scenario_id="corral_single_ball_place",
        world_file="",
        surface_profile="",
        scenario_timeout_s=30.0,
    )

    summary, _output = repeatability_runner.run_dashboard_scenario_once(args, run_index=2)

    assert captured_paths == ["new-path"]
    assert summary["mission_verdict_path"] == "new-path"


@pytest.mark.parametrize(
    "family",
    [
        "pre_stage_reacquire_fsm_v1",
        "pre_stage_path_tracker_v1",
        "pre_stage_trajectory_owner_v1",
        "nav2_follow_path_reacquire_v1",
        "nav2_mppi_follow_path_reacquire_v1",
        "object_centric_gather_policy_v1",
    ],
)
def test_main_passes_retries_and_gather_control_family_to_direct_gather_runner(
    tmp_path: Path,
    monkeypatch,
    family: str,
):
    monkeypatch.setattr(repeatability_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(repeatability_runner, "wait_for_dashboard", lambda *args, **kwargs: None)
    monkeypatch.setattr(repeatability_runner, "prepare_direct_environment", lambda args: {"session_id": "session-direct"})
    monkeypatch.setattr(
        repeatability_runner,
        "summarize_gather_run",
        lambda **kwargs: {
            "run_index": kwargs["run_index"],
            "return_code": kwargs["return_code"],
            "pass": False,
            "session_id": "",
            "scenario_id": "corral_single_ball_place",
            "mission_root": "",
            "summary_path": "",
            "mission_verdict_path": "",
            "target_results_path": "",
            "scorecard_path": "",
            "placed_count": 0,
            "capture_loss_count": 0,
            "surface_profile": "short_turf",
            "final_settle_distance_m": 0.0,
            "max_overshoot_distance_m": 0.0,
            "settle_time_s": 0.0,
            "release_recontact_count": 0,
            "mission_time_s": 0.0,
            "route_order": [],
            "target_results": [],
            "mission_verdict": {},
            "summary": {},
        },
    )
    monkeypatch.setattr(repeatability_runner, "_enrich_run_with_approach_side_fields", lambda run_summary: run_summary)
    monkeypatch.setattr(repeatability_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(repeatability_runner, "write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(repeatability_runner, "summarize_runs", lambda runs: {})
    monkeypatch.setattr(repeatability_runner, "_approach_side_rollup", lambda runs: {})
    monkeypatch.setattr(repeatability_runner, "promotion_gate_pass_for_runs", lambda runs, mode: False)

    subprocess_calls: list[list[str]] = []

    def fake_subprocess_run(command, cwd, capture_output, text, check):
        subprocess_calls.append(list(command))
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(repeatability_runner.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(
        repeatability_runner.sys,
        "argv",
        [
            "repeatability",
            "--execution-mode",
            "direct",
            "--runs",
            "1",
            "--provider",
            "local_stub",
            "--max-retries-per-target",
            "0",
            "--gather-control-family",
            family,
            "--target-model-sdf",
            "ros2_config/calibrated_golf_ball.sdf",
            "--zone-model-sdf",
            "ros2_config/golf_ball_delivery_zone_marker.sdf",
            "--artifact-kind",
            "gather_mission_calibrated_golf_policy_probe",
        ],
    )

    exit_code = repeatability_runner.main()

    assert exit_code == 2
    assert len(subprocess_calls) == 1
    assert "--max-retries-per-target" in subprocess_calls[0]
    retry_index = subprocess_calls[0].index("--max-retries-per-target")
    assert subprocess_calls[0][retry_index + 1] == "0"
    assert "--gather-control-family" in subprocess_calls[0]
    family_index = subprocess_calls[0].index("--gather-control-family")
    assert subprocess_calls[0][family_index + 1] == family
    assert "--target-model-sdf" in subprocess_calls[0]
    target_sdf_index = subprocess_calls[0].index("--target-model-sdf")
    assert subprocess_calls[0][target_sdf_index + 1] == "ros2_config/calibrated_golf_ball.sdf"
    assert "--zone-model-sdf" in subprocess_calls[0]
    zone_sdf_index = subprocess_calls[0].index("--zone-model-sdf")
    assert subprocess_calls[0][zone_sdf_index + 1] == "ros2_config/golf_ball_delivery_zone_marker.sdf"
    assert "--artifact-kind" in subprocess_calls[0]
    artifact_kind_index = subprocess_calls[0].index("--artifact-kind")
    assert subprocess_calls[0][artifact_kind_index + 1] == "gather_mission_calibrated_golf_policy_probe"
