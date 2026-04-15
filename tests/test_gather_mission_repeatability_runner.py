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
            assert payload == {}
            return 202, {"accepted": True, "message": "environment start queued"}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(repeatability_runner, "http_json", fake_http_json)
    monkeypatch.setattr(repeatability_runner.time, "sleep", lambda *_args, **_kwargs: None)

    repeatability_runner.ensure_environment_ready("http://127.0.0.1:8860", timeout_s=5.0)

    assert calls == [
        ("GET", "http://127.0.0.1:8860/api/state"),
        ("POST", "http://127.0.0.1:8860/api/env/start"),
        ("GET", "http://127.0.0.1:8860/api/state"),
        ("GET", "http://127.0.0.1:8860/api/state"),
    ]


def test_promotion_gate_pass_for_runs_requires_settled_corral_outcome():
    runs = [
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 0,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
        },
        {
            "pass": True,
            "mission_completed_pass": True,
            "capture_loss_count": 1,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": False,
            "rolled_away_after_release": False,
        },
    ]

    assert repeatability_runner.promotion_gate_pass_for_runs(runs, mode="pass_only") is False
    assert repeatability_runner.promotion_gate_pass_for_runs(runs, mode="strict") is False


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
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "clean_retention_pass": False,
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
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "stop_capture_state": {"captured": True},
                "release_capture_state": {"captured": True},
                "clean_retention_pass": False,
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
    assert summary["stopped_with_ball_captured"] is True
    assert summary["release_started_with_capture"] is True
    assert summary["clean_retention_pass"] is False
    assert summary["final_center_inside_zone"] is True
    assert summary["ball_stopped_in_corral"] is False
    assert summary["rolled_away_after_release"] is False
    assert summary["settled_in_corral_pass"] is False
