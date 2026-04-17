from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_mission_repeatability_runner as repeatability_runner  # noqa: E402


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
