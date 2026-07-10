from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hardware_acquisition_unattended_runner as runner  # noqa: E402


def _live_args(tmp_path):
    return runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path / "campaign"),
            "--dashboard-run-dir",
            str(tmp_path / "dashboard_runs"),
            "--stop-file",
            str(tmp_path / "STOP"),
            "--execute-motion",
            "--confirm-owner-unattended",
            "--room-isolated",
            "--cycles",
            "1",
        ]
    )


def _probe(center_error=-0.60, z_m=0.48):
    return {
        "pass": True,
        "median_center_error": center_error,
        "median_z_m": z_m,
        "median_confidence": 0.92,
        "observed_case": "far-left",
        "issues": [],
    }


def test_live_motion_requires_owner_and_isolated_room_confirmations(tmp_path):
    args = runner.parse_args(["--execute-motion", "--artifact-dir", str(tmp_path / "run")])

    issues = runner.validate_args(args)

    assert "owner_unattended_confirmation_required" in issues
    assert "isolated_room_confirmation_required" in issues


def test_probe_summary_requires_repeated_onboard_trt_geometry(tmp_path):
    args = _live_args(tmp_path)
    rows = [
        {
            "dry_run_obs": {
                "detected": True,
                "source": "onboard_trt",
                "confidence": confidence,
                "center_error": center_error,
            },
            "decision": {"z_m": z_m},
        }
        for confidence, center_error, z_m in [
            (0.91, -0.61, 0.48),
            (0.93, -0.60, 0.49),
            (0.92, -0.59, 0.48),
        ]
    ]
    rows.append({"type": "onboard_fetch_episode", "final_safe": True})

    summary = runner.summarize_probe_rows(rows, args)

    assert summary["pass"] is True
    assert summary["observed_case"] == "far-left"
    assert summary["median_center_error"] == -0.60
    assert summary["median_z_m"] == 0.48


def test_reset_geometry_rejects_dead_reckoning_drift(tmp_path):
    args = _live_args(tmp_path)

    close_ok, close_issues = runner.geometry_matches(_probe(), _probe(center_error=-0.45, z_m=0.60), args)
    drift_ok, drift_issues = runner.geometry_matches(_probe(), _probe(center_error=-0.20, z_m=0.90), args)

    assert close_ok is True
    assert close_issues == []
    assert drift_ok is False
    assert "reset_center_error_drift" in drift_issues
    assert "reset_range_drift" in drift_issues


def test_no_contact_episode_and_reverse_reset_require_final_safe():
    episode_ok, episode_issues = runner.episode_qualifies(
        {
            "type": "onboard_fetch_episode",
            "steering": "arc",
            "stop_reason": "standoff_reached",
            "final_safe": True,
        }
    )
    reset_ok, reset_issues = runner.reset_qualifies(
        {
            "type": "onboard_reverse_replay",
            "stop_reason": "reverse_complete",
            "final_safe": True,
        }
    )

    assert episode_ok is True
    assert episode_issues == []
    assert reset_ok is True
    assert reset_issues == []

    pushed_ok, pushed_issues = runner.episode_qualifies(
        {
            "type": "onboard_fetch_episode",
            "steering": "arc",
            "stop_reason": "standoff_then_pushed",
            "final_safe": True,
            "push": {"executed": 10},
        }
    )
    assert pushed_ok is False
    assert "push_executed_in_no_contact_lane" in pushed_issues


def test_campaign_runs_acquire_stop_reset_stop_and_geometry_gate(tmp_path, monkeypatch):
    args = _live_args(tmp_path)
    calls = []

    monkeypatch.setattr(runner, "stop_verified", lambda _args, label: {"pass": True, "label": label})
    monkeypatch.setattr(runner, "run_onboard_probe", lambda _args, _dir, _label: _probe())
    monkeypatch.setattr(runner, "capture_raw_frame", lambda _args, _path: None)
    monkeypatch.setattr(runner, "output_set", lambda _dir, _prefix: set())
    monkeypatch.setattr(runner, "pull_trace", lambda _args, _summary, _dir: {"pass": True})

    def fake_http(_base, path, method="GET", timeout_s=8.0):
        calls.append((method, path))
        if path in ("/go-acquire-only", "/reset"):
            return {"ok": True}
        raise AssertionError("unexpected HTTP call: %s %s" % (method, path))

    def fake_wait(_args, prefix, _before, _timeout):
        if prefix == "run":
            return {
                "summary_path": "run.json",
                "summary": {
                    "type": "onboard_fetch_episode",
                    "steering": "arc",
                    "stop_reason": "standoff_reached",
                    "final_safe": True,
                    "trace": "/home/jetson/chasecar_onboard/runs/onboard_1.jsonl",
                },
                "status_rows": [],
            }
        return {
            "summary_path": "reset.json",
            "summary": {
                "type": "onboard_reverse_replay",
                "stop_reason": "reverse_complete",
                "final_safe": True,
            },
            "status_rows": [],
        }

    monkeypatch.setattr(runner, "http_json", fake_http)
    monkeypatch.setattr(runner, "wait_for_episode", fake_wait)

    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["stop_reason"] == "requested_cycles_complete"
    assert summary["cycles"][0]["pass"] is True
    assert calls == [("POST", "/go-acquire-only"), ("POST", "/reset")]


def test_campaign_never_reverse_replays_an_incomplete_episode(tmp_path, monkeypatch):
    args = _live_args(tmp_path)
    calls = []

    monkeypatch.setattr(runner, "stop_verified", lambda _args, label: {"pass": True, "label": label})
    monkeypatch.setattr(runner, "run_onboard_probe", lambda _args, _dir, _label: _probe())
    monkeypatch.setattr(runner, "capture_raw_frame", lambda _args, _path: None)
    monkeypatch.setattr(runner, "output_set", lambda _dir, _prefix: set())

    def fake_http(_base, path, method="GET", timeout_s=8.0):
        calls.append((method, path))
        return {"ok": True}

    monkeypatch.setattr(runner, "http_json", fake_http)
    monkeypatch.setattr(
        runner,
        "wait_for_episode",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("episode_timeout")),
    )

    summary = runner.run(args)

    assert summary["pass"] is False
    assert summary["stop_reason"] == "campaign_failed"
    assert ("POST", "/go-acquire-only") in calls
    assert ("POST", "/reset") not in calls
