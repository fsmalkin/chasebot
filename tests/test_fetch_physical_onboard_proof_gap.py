from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_physical_onboard_proof_gap as gap  # noqa: E402


def test_physical_gap_default_milestone_readiness_uses_current_proof_cards():
    assert "generalized_fetch_to_pose_milestone_readiness_current_proof_cards_20260605" in (
        gap.DEFAULT_MILESTONE_READINESS
    )


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "physical_gap",
        "milestone_readiness_summary": str(tmp_path / "milestone.json"),
        "physical_claim_summary": "",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gap.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_artifact(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"proof")
    return path


def _milestone(path: Path, *, operator_uat_ready: bool = True) -> Path:
    return _write_json(
        path,
        {
            "operator_uat_ready": operator_uat_ready,
            "hardware_proven": False,
            "milestone_complete": False,
        },
    )


def _physical_claim(tmp_path: Path, path: Path, **overrides) -> Path:
    artifacts = {
        key: str(_write_artifact(tmp_path / "physical" / f"{key}.dat"))
        for key in gap.REQUIRED_ARTIFACT_KEYS
    }
    payload = {
        "runtime_target": "robot_fidelity_orin",
        "inference_backend": "tensorrt_int8",
        "execution_surface": "physical_robot",
        "physical_robot_run": True,
        "onboard_tensorrt_execution": True,
        "physical_camera_evidence": True,
        "field_physics_notes": True,
        "artifacts": artifacts,
    }
    payload.update(overrides)
    return _write_json(path, payload)


def test_physical_gap_is_visible_when_operator_uat_is_ready_but_no_physical_claim(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gap, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _args(tmp_path)
    _milestone(Path(args.milestone_readiness_summary))

    summary = gap.build_summary(args)

    assert summary["pass"] is True
    assert summary["milestone_operator_uat_ready"] is True
    assert summary["hardware_proven"] is False
    assert summary["physical_onboard_proof_ready"] is False
    assert summary["milestone_interpretation"] == "physical_onboard_proof_pending"
    assert "physical_robot_run_not_provided" in summary["open_gates"]
    assert "onboard_tensorrt_execution_not_provided" in summary["open_gates"]


def test_physical_gap_fails_when_milestone_uat_is_not_ready(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gap, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _args(tmp_path)
    _milestone(Path(args.milestone_readiness_summary), operator_uat_ready=False)

    summary = gap.build_summary(args)

    assert summary["pass"] is False
    assert "milestone_operator_uat_not_ready" in summary["issues"]


def test_physical_gap_accepts_complete_physical_claim(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gap, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    claim = tmp_path / "physical_claim.json"
    args = _args(tmp_path, physical_claim_summary=str(claim))
    _milestone(Path(args.milestone_readiness_summary))
    _physical_claim(tmp_path, claim)

    summary = gap.build_summary(args)

    assert summary["pass"] is True
    assert summary["hardware_proven"] is True
    assert summary["physical_onboard_proof_ready"] is True
    assert summary["open_gates"] == []
    assert summary["physical_claim"]["pass"] is True


def test_physical_gap_rejects_sim_gate_claim_as_physical_proof(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gap, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    claim = tmp_path / "physical_claim.json"
    args = _args(tmp_path, physical_claim_summary=str(claim))
    _milestone(Path(args.milestone_readiness_summary))
    _physical_claim(tmp_path, claim, execution_surface="sim_gate")

    summary = gap.build_summary(args)

    assert summary["hardware_proven"] is False
    assert "execution_surface_not_physical_robot" in summary["open_gates"]


def test_physical_gap_scorecard_names_required_schema(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gap, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _args(tmp_path)
    _milestone(Path(args.milestone_readiness_summary))
    summary = gap.build_summary(args)
    scorecard = tmp_path / "scorecard.md"

    gap.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Physical Onboard Proof Gap" in text
    assert "runtime_target" in text
    assert "raw_camera" in text
    assert "hardware_proven: `False`" in text
