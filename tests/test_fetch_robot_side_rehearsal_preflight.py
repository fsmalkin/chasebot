from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_robot_side_rehearsal_preflight as preflight  # noqa: E402


def test_robot_side_preflight_default_physical_gap_uses_current_proof_cards():
    assert "physical_onboard_proof_gap_current_proof_cards_20260605" in preflight.DEFAULT_PHYSICAL_GAP_SUMMARY


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(preflight.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "robot_side_preflight",
        "readiness_summary": str(tmp_path / "readiness.json"),
        "rehearsal_plan": str(tmp_path / "plan.json"),
        "physical_gap_summary": str(tmp_path / "physical_gap.json"),
        "dashboard_url": "http://100.112.221.6:8883",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _green_fixture(tmp_path: Path):
    args = _args(tmp_path)
    _write_json(
        Path(args.readiness_summary),
        {
            "pass": True,
            "hardware_transfer_ready": True,
            "hardware_proven": False,
        },
    )
    _write_json(
        Path(args.rehearsal_plan),
        {
            "pass": True,
            "hardware_rehearsal_plan_ready": True,
            "hardware_proven": False,
        },
    )
    _write_json(
        Path(args.physical_gap_summary),
        {
            "pass": True,
            "physical_onboard_proof_ready": False,
            "hardware_proven": False,
        },
    )
    return args


def test_robot_side_preflight_ready_without_claiming_hardware_proof(tmp_path: Path):
    summary = preflight.build_summary(_green_fixture(tmp_path))

    assert summary["pass"] is True
    assert summary["local_preflight_ready"] is True
    assert summary["hardware_connected"] is False
    assert summary["hardware_proven"] is False
    assert summary["promotion_evidence"] is False
    assert "control_preflight.json" in summary["required_robot_side_artifacts"][0]
    assert any("physical_claim_summary.json" in item for item in summary["required_robot_side_artifacts"])
    assert summary["physical_claim_template"]["runtime_target"] == "robot_fidelity_orin"
    assert summary["physical_claim_template"]["inference_backend"] == "tensorrt_int8"
    assert summary["physical_claim_template"]["execution_surface"] == "physical_robot"
    assert any("fetch_hardware_rehearsal_runner.py" in command for command in summary["next_commands"])
    assert any("seed20260648_mixed_all_routes_rehearsal" in command for command in summary["next_commands"])
    assert any("fetch_physical_claim_from_run.py" in command for command in summary["next_commands"])
    assert any("fetch_physical_onboard_proof_gap.py" in command for command in summary["next_commands"])


def test_robot_side_preflight_fails_closed_when_readiness_is_stale(tmp_path: Path):
    args = _green_fixture(tmp_path)
    _write_json(Path(args.readiness_summary), {"pass": False, "hardware_transfer_ready": False})

    summary = preflight.build_summary(args)

    assert summary["pass"] is False
    assert "readiness_summary_not_pass" in summary["issues"]
    assert "hardware_transfer_ready_false" in summary["issues"]


def test_robot_side_preflight_fails_closed_when_physical_gap_already_claims_ready(tmp_path: Path):
    args = _green_fixture(tmp_path)
    _write_json(Path(args.physical_gap_summary), {"pass": True, "physical_onboard_proof_ready": True})

    summary = preflight.build_summary(args)

    assert summary["pass"] is False
    assert "physical_gap_should_not_claim_proof_ready" in summary["issues"]


def test_robot_side_preflight_scorecard_lists_next_commands(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = preflight.build_summary(_green_fixture(tmp_path))

    preflight.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "hardware_proven: `False`" in text
    assert "run_dashboard_service.ps1" in text
    assert "keyframe_review_contact_sheet.png" in text
    assert "Physical Claim Template" in text
    assert "fetch_physical_claim_from_run.py" in text
    assert "fetch_physical_onboard_proof_gap.py" in text
