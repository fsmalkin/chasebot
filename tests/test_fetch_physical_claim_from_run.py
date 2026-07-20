from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_physical_claim_from_run as claim  # noqa: E402
import fetch_physical_onboard_proof_gap as gap  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "claim",
        "batch_summary": "",
        "scene_id": "",
        "mission_summary": "",
        "visual_package_summary": "",
        "control_preflight": "",
        "confirm_physical_robot": False,
        "confirm_onboard_tensorrt": False,
        "confirm_physical_camera": False,
        "confirm_field_physics": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(claim.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"proof")
    return path


def _run_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    visual = tmp_path / "artifacts" / "session" / "physical_session" / "visual"
    raw = _write_file(visual / "raw_camera_browser.mp4")
    topdown = _write_file(visual / "topdown_telemetry_browser.mp4")
    world = _write_file(visual / "world_stream.mp4")
    sheet = _write_file(visual / "keyframe_review_contact_sheet.png")
    mission = _write_json(
        tmp_path / "mission_verdict.json",
        {
            "pass": True,
            "local_fetch_dispatched": True,
            "control_preflight": {"pass": True, "controller_name": "jetbot_base_controller"},
        },
    )
    package = _write_json(
        tmp_path / "package_summary.json",
        {
            "pass": True,
            "keyframe_reviews": [{"ok": True, "path": str(sheet)}],
            "videos": [
                {"name": "raw_camera_browser.mp4", "browser_playable": True, "path": str(raw)},
                {"name": "topdown_telemetry_browser.mp4", "browser_playable": True, "path": str(topdown)},
                {"name": "world_stream.mp4", "browser_playable": True, "path": str(world)},
            ],
        },
    )
    batch = _write_json(
        tmp_path / "batch_summary.json",
        {
            "pass": True,
            "rows": [
                {
                    "scene_id": "seed20260648_scene42_fetch_ready_local",
                    "mission_summary_path": str(mission),
                    "visual_package_summary_path": str(package),
                }
            ],
        },
    )
    return batch, mission, package


def _confirmed_args(tmp_path: Path, **overrides):
    batch, _, _ = _run_fixture(tmp_path)
    payload = {
        "batch_summary": str(batch),
        "confirm_physical_robot": True,
        "confirm_onboard_tensorrt": True,
        "confirm_physical_camera": True,
        "confirm_field_physics": True,
    }
    payload.update(overrides)
    return _args(tmp_path, **payload)


def test_physical_claim_generator_extracts_claim_from_batch(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(claim, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(claim, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    generated = claim.build_claim(_confirmed_args(tmp_path), tmp_path / "out")

    assert generated["claim_ready_for_gap_audit"] is True
    assert generated["physical_robot_run"] is True
    assert generated["onboard_tensorrt_execution"] is True
    assert generated["execution_surface"] == "physical_robot"
    assert generated["artifacts"]["raw_camera"].endswith("raw_camera_browser.mp4")
    assert generated["artifacts"]["control_preflight"].endswith("control_preflight.json")


def test_physical_claim_generator_keeps_unconfirmed_claim_out_of_hardware_proof(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(claim, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(claim, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    batch, _, _ = _run_fixture(tmp_path)

    generated = claim.build_claim(_args(tmp_path, batch_summary=str(batch)), tmp_path / "out")

    assert generated["claim_ready_for_gap_audit"] is True
    assert generated["execution_surface"] == "unconfirmed"
    assert generated["physical_robot_run"] is False


def test_physical_claim_generator_accepts_legacy_route_executor_delivery_shape(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(claim, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(claim, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    batch, mission, _ = _run_fixture(tmp_path)
    _write_json(
        mission,
        {
            "pass": True,
            "mission_completed_pass": True,
            "fetch_to_pose_pass": True,
            "route_executor": "local_fetch_to_pose",
            "control_preflight": {"pass": True},
        },
    )

    generated = claim.build_claim(
        _args(
            tmp_path,
            batch_summary=str(batch),
            confirm_physical_robot=True,
            confirm_onboard_tensorrt=True,
            confirm_physical_camera=True,
            confirm_field_physics=True,
        ),
        tmp_path / "out",
    )

    assert generated["claim_ready_for_gap_audit"] is True
    assert generated["artifacts"]["mission_verdict"].endswith("mission_verdict.json")


def test_physical_claim_generator_rejects_route_only_row(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(claim, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(claim, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    batch, mission, _ = _run_fixture(tmp_path)
    _write_json(mission, {"pass": True, "local_fetch_dispatched": False})

    generated = claim.build_claim(
        _args(
            tmp_path,
            batch_summary=str(batch),
            confirm_physical_robot=True,
            confirm_onboard_tensorrt=True,
            confirm_physical_camera=True,
            confirm_field_physics=True,
        ),
        tmp_path / "out",
    )

    assert generated["claim_ready_for_gap_audit"] is False
    assert "no_passing_executable_batch_row" in generated["issues"]


def test_physical_claim_generator_output_passes_gap_audit_when_confirmed(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(claim, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(claim, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(gap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gap, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    milestone = _write_json(tmp_path / "milestone.json", {"operator_uat_ready": True, "hardware_proven": False})
    output_dir = tmp_path / "out"
    generated = claim.build_claim(_confirmed_args(tmp_path), output_dir)
    claim_path = _write_json(output_dir / "physical_claim_summary.json", generated)

    summary = gap.build_summary(
        SimpleNamespace(
            campaign_id="gap",
            milestone_readiness_summary=str(milestone),
            physical_claim_summary=str(claim_path),
        )
    )

    assert summary["hardware_proven"] is True
    assert summary["physical_onboard_proof_ready"] is True


def test_physical_claim_scorecard_lists_gap_command(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(claim, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(claim, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    generated = claim.build_claim(_confirmed_args(tmp_path), tmp_path / "out")
    summary = {
        "campaign_id": "claim",
        "pass": True,
        "issues": [],
        "claim_summary_path": "artifacts/session/claim/fetch_physical_claim_from_run/physical_claim_summary.json",
        "claim": generated,
    }
    scorecard = tmp_path / "scorecard.md"

    claim.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Physical Claim From Run" in text
    assert "fetch_physical_onboard_proof_gap.py" in text
    assert "raw_camera_browser.mp4" in text
