from __future__ import annotations

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
