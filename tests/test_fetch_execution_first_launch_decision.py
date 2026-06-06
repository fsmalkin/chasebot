from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_execution_first_launch_decision as launch  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(launch.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _provider(path: Path) -> Path:
    return _write_json(
        path,
        {
            "launch_plan_ready": True,
            "provider_launch_ready": False,
            "blockers": ["missing_openai_api_key"],
            "launch_steps": [
                {"id": "provider_preflight", "command": "python provider_preflight.py"},
                {"id": "provider_gate", "command": "python provider_gate.py"},
                {"id": "provider_replay", "command": "python provider_replay.py"},
            ],
        },
    )


def _robot(path: Path, *, hardware_connected: bool = False) -> Path:
    return _write_json(
        path,
        {
            "local_preflight_ready": True,
            "hardware_connected": hardware_connected,
            "issues": [],
            "next_commands": [
                "powershell dashboard.ps1",
                "python runtime_smoke.py",
                "python saved_anchors.py",
            ],
        },
    )


def _args(tmp_path: Path, **overrides) -> SimpleNamespace:
    provider = _provider(tmp_path / "provider.json")
    robot = _robot(tmp_path / "robot.json")
    payload = {
        "campaign_id": "launch_decision",
        "provider_checklist_summary": str(provider),
        "robot_side_preflight_summary": str(robot),
        "openai_api_key": "",
        "prefer": "auto",
        "allow_physical_launch": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_launch_decision_waits_when_provider_key_and_hardware_are_absent(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(launch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    summary = launch.build_summary(_args(tmp_path))

    assert summary["pass"] is True
    assert summary["launch_ready"] is False
    assert summary["selected_lane"] == "waiting_on_external_gate"
    assert "provider:missing_openai_api_key" in summary["blockers"]
    assert "physical:hardware_connected_false" in summary["blockers"]


def test_launch_decision_selects_provider_when_key_is_present(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(launch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    summary = launch.build_summary(_args(tmp_path, openai_api_key="sk-test"))

    assert summary["launch_ready"] is True
    assert summary["selected_lane"] == "provider_launch"
    assert summary["provider"]["ready"] is True
    assert summary["selected_next_commands"][0] == "python provider_preflight.py"


def test_launch_decision_selects_physical_when_allowed_and_provider_is_blocked(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(launch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    summary = launch.build_summary(_args(tmp_path, allow_physical_launch=True))

    assert summary["launch_ready"] is True
    assert summary["selected_lane"] == "physical_onboard_launch"
    assert summary["physical"]["ready"] is True
    assert summary["selected_next_commands"][0] == "powershell dashboard.ps1"


def test_launch_decision_scorecard_names_selected_commands(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(launch, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    summary = launch.build_summary(_args(tmp_path, openai_api_key="sk-test"))
    scorecard = tmp_path / "scorecard.md"

    launch.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Execution-First Launch Decision" in text
    assert "selected_lane: `provider_launch`" in text
    assert "python provider_preflight.py" in text
    assert "hardware_proven: `False`" in text
