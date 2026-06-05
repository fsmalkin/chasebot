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


def _session_script(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    session = tmp_path / "session"
    path.write_text(
        "\n".join(
            [
                "import json",
                "from pathlib import Path",
                f"session = Path({str(session)!r})",
                "(session / 'visual').mkdir(parents=True, exist_ok=True)",
                "(session / 'readiness_report.json').write_text(json.dumps({'status': 'pass'}), encoding='utf-8')",
                "(session / 'visual' / 'operator_status.json').write_text('{}', encoding='utf-8')",
                "print(f'Session directory: {session}')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
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
    script = _session_script(tmp_path, "session_step.py")
    plan = _plan(
        tmp_path,
        planned_steps=[
            {
                "id": "runtime_stack_smoke",
                "command": f"python {script}",
                "required_artifacts": [
                    "session:readiness_report.json",
                    "session:visual/operator_status.json",
                ],
            }
        ],
    )

    summary = runner.build_summary(
        _args(tmp_path, plan_summary=str(plan), step_id="runtime_stack_smoke", execute=True)
    )

    assert summary["pass"] is True
    assert summary["mode"] == "execute"
    assert summary["execution"]["id"] == "runtime_stack_smoke"
    assert summary["execution"]["returncode"] == 0
    assert summary["execution_artifacts"]["pass"] is True


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


def test_rehearsal_runner_reads_bom_json(tmp_path: Path):
    path = tmp_path / "bom.json"
    path.write_text('{"pass": true}\n', encoding="utf-8-sig")

    payload, issues = runner.read_json(path)

    assert issues == []
    assert payload["pass"] is True


def test_rehearsal_runner_validates_replay_batch_artifacts(tmp_path: Path):
    session = tmp_path / "artifacts" / "session" / "row_session"
    visual = session / "visual"
    visual.mkdir(parents=True)
    for name in (
        "raw_camera_browser.mp4",
        "topdown_telemetry_browser.mp4",
        "world_stream.mp4",
        "keyframe_review_contact_sheet.png",
    ):
        (visual / name).write_bytes(b"ok")
    mission = tmp_path / "mission_verdict.json"
    _write_json(mission, {"pass": True, "control_preflight": {"pass": True}})
    package = tmp_path / "package_summary.json"
    _write_json(
        package,
        {
            "pass": True,
            "keyframe_reviews": [{"ok": True, "path": str(visual / "keyframe_review_contact_sheet.png")}],
            "videos": [
                {"name": "raw_camera_browser.mp4", "browser_playable": True, "path": str(visual / "raw_camera_browser.mp4")},
                {
                    "name": "topdown_telemetry_browser.mp4",
                    "browser_playable": True,
                    "path": str(visual / "topdown_telemetry_browser.mp4"),
                },
                {"name": "world_stream.mp4", "browser_playable": True, "path": str(visual / "world_stream.mp4")},
            ],
        },
    )
    batch = tmp_path / "batch_summary.json"
    _write_json(
        batch,
        {
            "pass": True,
            "selected_count": 1,
            "mission_fail_count": 0,
            "visual_package_pass_count": 1,
            "rows": [
                {
                    "scene_id": "saved_anchor_zero",
                    "mission_summary_path": str(mission),
                    "visual_package_summary_path": str(package),
                }
            ],
        },
    )

    summary = runner.validate_replay_batch_artifacts(str(batch))

    assert summary["pass"] is True
    assert summary["issues"] == []
    assert len(summary["artifacts"]) == 3


def test_rehearsal_runner_validates_seeded_gate_artifacts(tmp_path: Path):
    session = tmp_path / "artifacts" / "session" / "seeded_row_session"
    visual = session / "visual"
    visual.mkdir(parents=True)
    for name in (
        "raw_camera_browser.mp4",
        "topdown_telemetry_browser.mp4",
        "world_stream.mp4",
        "keyframe_review_contact_sheet.png",
    ):
        (visual / name).write_bytes(b"ok")
    mission = tmp_path / "mission_verdict.json"
    _write_json(mission, {"pass": True, "control_preflight": {"pass": True}})
    package = tmp_path / "package_summary.json"
    _write_json(
        package,
        {
            "pass": True,
            "keyframe_reviews": [{"ok": True, "path": str(visual / "keyframe_review_contact_sheet.png")}],
            "videos": [
                {"name": "raw_camera_browser.mp4", "browser_playable": True, "path": str(visual / "raw_camera_browser.mp4")},
                {
                    "name": "topdown_telemetry_browser.mp4",
                    "browser_playable": True,
                    "path": str(visual / "topdown_telemetry_browser.mp4"),
                },
                {"name": "world_stream.mp4", "browser_playable": True, "path": str(visual / "world_stream.mp4")},
            ],
        },
    )
    replay = tmp_path / "batch_summary.json"
    _write_json(
        replay,
        {
            "pass": True,
            "selected_count": 1,
            "mission_fail_count": 0,
            "visual_package_pass_count": 1,
            "rows": [
                {
                    "scene_id": "seed20260635_scene01",
                    "mission_summary_path": str(mission),
                    "visual_package_summary_path": str(package),
                }
            ],
        },
    )
    planner = tmp_path / "planner_gate.json"
    _write_json(planner, {"pass": True})
    analyzer = tmp_path / "route_uat_summary.json"
    _write_json(analyzer, {"pass": True})
    gate = tmp_path / "gate_summary.json"
    _write_json(
        gate,
        {
            "pass": True,
            "planner_gate_pass": True,
            "replay_pass": True,
            "analyzer_pass": True,
            "expected_executable_count": 1,
            "planner_summary_path": str(planner),
            "replay_summary_path": str(replay),
            "analyzer_summary_path": str(analyzer),
        },
    )

    summary = runner.validate_seeded_gate_artifacts(str(gate))

    assert summary["pass"] is True
    assert summary["issues"] == []
    assert summary["seeded_gate_summary"].endswith("gate_summary.json")
    assert any(row["spec"] == "seeded_gate_replay_batch_validation" for row in summary["artifacts"])
