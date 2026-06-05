from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_hardware_rehearsal_runner as runner  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "runner",
        "plan_summary": str(tmp_path / "plan.json"),
        "step_id": "",
        "execute": False,
        "timeout_s": 5,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(runner.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _script(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text("print('ok')\n", encoding="utf-8")
    return path


def _plan(tmp_path: Path, **overrides) -> Path:
    script = _script(tmp_path, "step.py")
    payload = {
        "pass": True,
        "hardware_rehearsal_plan_ready": True,
        "hardware_proven": False,
        "planned_steps": [
            {
                "id": "runtime_stack_smoke",
                "command": f"python {script}",
                "required_artifacts": ["first_uat_summary.json"],
            },
            {
                "id": "saved_anchor_one_run_fetch_rehearsal",
                "command": f"python {script}",
                "required_artifacts": ["control_preflight.json", "visual/raw_camera_browser.mp4"],
            },
        ],
    }
    payload.update(overrides)
    return _write_json(tmp_path / "plan.json", payload)


def test_rehearsal_runner_preflights_all_plan_steps(tmp_path: Path):
    plan = _plan(tmp_path)

    summary = runner.build_summary(_args(tmp_path, plan_summary=str(plan)))

    assert summary["pass"] is True
    assert summary["mode"] == "preflight"
    assert summary["hardware_proven"] is False
    assert summary["next_action"] == "execute_runtime_stack_smoke"
    assert [row["id"] for row in summary["step_preflights"]] == [
        "runtime_stack_smoke",
        "saved_anchor_one_run_fetch_rehearsal",
    ]


def test_rehearsal_runner_fails_closed_when_plan_not_ready(tmp_path: Path):
    plan = _plan(tmp_path, **{"pass": False, "hardware_rehearsal_plan_ready": False})

    summary = runner.build_summary(_args(tmp_path, plan_summary=str(plan)))

    assert summary["pass"] is False
    assert "plan_summary_not_pass" in summary["issues"]
    assert "plan_not_rehearsal_ready" in summary["issues"]


def test_rehearsal_runner_executes_one_named_step(tmp_path: Path):
    plan = _plan(tmp_path)

    summary = runner.build_summary(
        _args(tmp_path, plan_summary=str(plan), step_id="runtime_stack_smoke", execute=True)
    )

    assert summary["pass"] is True
    assert summary["mode"] == "execute"
    assert summary["execution"]["id"] == "runtime_stack_smoke"
    assert summary["execution"]["returncode"] == 0


def test_rehearsal_runner_requires_single_step_for_execute(tmp_path: Path):
    plan = _plan(tmp_path)

    summary = runner.build_summary(_args(tmp_path, plan_summary=str(plan), execute=True))

    assert summary["pass"] is False
    assert "execute_requires_exactly_one_step" in summary["issues"]


def test_rehearsal_runner_scorecard_lists_required_artifacts(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = runner.build_summary(_args(tmp_path, plan_summary=str(_plan(tmp_path))))

    runner.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Hardware Rehearsal Runner" in text
    assert "visual/raw_camera_browser.mp4" in text
    assert "execute_runtime_stack_smoke" in text
