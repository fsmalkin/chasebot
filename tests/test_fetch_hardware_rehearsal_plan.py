from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_hardware_rehearsal_plan as rehearsal  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "hardware_plan",
        "readiness_summary": str(tmp_path / "readiness.json"),
        "saved_anchor_gate": str(tmp_path / "saved_anchor_gate.json"),
        "seeded_gate": str(tmp_path / "seeded_gate.json"),
        "dashboard_url": "http://127.0.0.1:8883",
        "saved_anchor_campaign_id": "hardware_saved",
        "seeded_campaign_id": "hardware_seed",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rehearsal.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _green_fixture(tmp_path: Path) -> SimpleNamespace:
    args = _args(tmp_path)
    _write_json(
        Path(args.readiness_summary),
        {
            "pass": True,
            "hardware_transfer_ready": True,
            "hardware_proven": False,
            "milestone_interpretation": "planner_routed_fetch_hardware_rehearsal_ready",
        },
    )
    _write_json(Path(args.saved_anchor_gate), {"pass": True})
    _write_json(Path(args.seeded_gate), {"pass": True})
    return args


def test_hardware_rehearsal_plan_is_ready_from_green_readiness(tmp_path: Path):
    summary = rehearsal.build_summary(_green_fixture(tmp_path))

    assert summary["pass"] is True
    assert summary["hardware_rehearsal_plan_ready"] is True
    assert summary["hardware_proven"] is False
    assert summary["promotion_evidence"] is False
    assert summary["runtime_contract"]["runtime_target"] == "robot_fidelity_orin"
    assert summary["runtime_contract"]["inference_backend"] == "tensorrt_int8"
    assert [step["id"] for step in summary["planned_steps"]] == [
        "runtime_stack_smoke",
        "saved_anchor_one_run_fetch_rehearsal",
        "seed20260643_mixed_all_routes_rehearsal",
    ]


def test_hardware_rehearsal_plan_requires_visual_and_controller_artifacts(tmp_path: Path):
    summary = rehearsal.build_summary(_green_fixture(tmp_path))
    saved_anchor = summary["planned_steps"][1]

    assert "control_preflight.json" in saved_anchor["required_artifacts"]
    assert "visual/raw_camera_browser.mp4" in saved_anchor["required_artifacts"]
    assert "visual/keyframe_review_contact_sheet.png" in saved_anchor["required_artifacts"]
    assert "--fresh-dashboard-session-per-run" in saved_anchor["command"]
    assert "--stop-on-fail" in saved_anchor["command"]


def test_hardware_rehearsal_plan_fails_closed_when_readiness_is_not_green(tmp_path: Path):
    args = _green_fixture(tmp_path)
    _write_json(
        Path(args.readiness_summary),
        {
            "pass": False,
            "hardware_transfer_ready": False,
            "hardware_proven": False,
            "milestone_interpretation": "planner_routed_fetch_hardware_rehearsal_incomplete",
        },
    )

    summary = rehearsal.build_summary(args)

    assert summary["pass"] is False
    assert summary["hardware_rehearsal_plan_ready"] is False
    assert "readiness_summary_not_pass" in summary["issues"]
    assert "hardware_transfer_ready_false" in summary["issues"]


def test_hardware_rehearsal_scorecard_includes_commands(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = rehearsal.build_summary(_green_fixture(tmp_path))

    rehearsal.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "scripts/run_first_uat.ps1" in text
    assert "scripts/fetch_planner_route_replay_batch.py" in text
    assert "scan_or_perceive_first" in text
    assert "hardware_proven: `False`" in text
