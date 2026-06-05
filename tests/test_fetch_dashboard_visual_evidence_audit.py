from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_dashboard_visual_evidence_audit as audit  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "dashboard_audit",
        "dashboard_plan": str(tmp_path / "runtime" / "dashboard" / "fetch_plan_data.json"),
        "min_uat_samples": 2,
        "min_file_bytes": 10,
        "audit_all_evidence_cards": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write(path: Path, content: bytes = b"x" * 20) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sample(label: str, route: str, session: str) -> dict:
    prefix = f"/artifacts/session/{session}"
    return {
        "label": label,
        "route": route,
        "session_id": session,
        "video_url": f"{prefix}/visual/raw_camera_browser.mp4",
        "topdown_url": f"{prefix}/visual/topdown_telemetry_browser.mp4",
        "world_url": f"{prefix}/visual/world_stream.mp4",
        "contact_sheet_url": f"{prefix}/visual/keyframe_review_contact_sheet.png",
        "scorecard_url": f"{prefix}/fetch_visual_uat_package/scorecard.md",
        "interpretation": "delivery pass",
    }


def _green_dashboard(tmp_path: Path) -> Path:
    for session in ("session_a", "session_b"):
        for rel in (
            "visual/raw_camera_browser.mp4",
            "visual/topdown_telemetry_browser.mp4",
            "visual/world_stream.mp4",
            "visual/keyframe_review_contact_sheet.png",
            "fetch_visual_uat_package/scorecard.md",
        ):
            _write(tmp_path / "artifacts" / "session" / session / rel)
    for rel in (
        "artifacts/session/rollup/fetch_planner_breadth_rollup/scorecard.md",
        "artifacts/session/milestone/fetch_generalized_milestone_readiness/scorecard.md",
        "artifacts/session/physical_gap/fetch_physical_onboard_proof_gap/scorecard.md",
        "artifacts/session/runbook/fetch_robot_side_rehearsal_preflight/scorecard.md",
        "artifacts/session/hardware/fetch_hardware_rehearsal_runner/scorecard.md",
        "artifacts/session/provider/fetch_planner_provider_rerun_readiness/scorecard.md",
    ):
        _write(tmp_path / rel)
    payload = {
        "status_label": "Three-seed breadth rollup green; seed 20260648 hardware rehearsal green",
        "uat_review_bundle": {
            "title": "Seed 20260648 mixed all-routes video bundle",
            "route_samples": [
                _sample("sample_a", "fetch_ready_local", "session_a"),
                _sample("sample_b", "nav2_reposition_first", "session_b"),
            ],
        },
        "latest_evidence": [
            {
                "title": "Three-seed breadth rollup is green",
                "tone": "green",
                "links": [
                    {
                        "label": "rollup scorecard",
                        "url": "/artifacts/session/rollup/fetch_planner_breadth_rollup/scorecard.md",
                    }
                ],
            },
            {
                "title": "Milestone readiness rollup is UAT-ready",
                "tone": "green",
                "links": [
                    {
                        "label": "milestone scorecard",
                        "url": "/artifacts/session/milestone/fetch_generalized_milestone_readiness/scorecard.md",
                    }
                ],
            },
            {
                "title": "Physical/onboard proof gap is explicit",
                "tone": "yellow",
                "links": [
                    {
                        "label": "physical gap scorecard",
                        "url": "/artifacts/session/physical_gap/fetch_physical_onboard_proof_gap/scorecard.md",
                    }
                ],
            },
            {
                "title": "Robot-side physical runbook is current",
                "tone": "yellow",
                "links": [
                    {
                        "label": "runbook scorecard",
                        "url": "/artifacts/session/runbook/fetch_robot_side_rehearsal_preflight/scorecard.md",
                    }
                ],
            },
            {
                "title": "Seed 20260648 hardware rehearsal is green",
                "tone": "green",
                "links": [
                    {
                        "label": "hardware scorecard",
                        "url": "/artifacts/session/hardware/fetch_hardware_rehearsal_runner/scorecard.md",
                    }
                ],
            },
            {
                "title": "Provider rerun preflight is waiting on OPENAI_API_KEY",
                "tone": "yellow",
                "links": [
                    {
                        "label": "provider scorecard",
                        "url": "/artifacts/session/provider/fetch_planner_provider_rerun_readiness/scorecard.md",
                    }
                ],
            },
        ],
    }
    path = tmp_path / "runtime" / "dashboard" / "fetch_plan_data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(audit.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_dashboard_visual_evidence_audit_scores_green_bundle(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _green_dashboard(tmp_path)

    summary = audit.build_summary(_args(tmp_path))

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "dashboard_visual_evidence_links_green"
    assert summary["uat_sample_count"] == 2
    assert summary["uat_sample_pass_count"] == 2
    assert summary["evidence_card_pass_count"] == 6
    assert summary["all_evidence_cards_audited"] is False
    assert summary["route_counts"] == {"fetch_ready_local": 1, "nav2_reposition_first": 1}


def test_dashboard_visual_evidence_audit_fails_on_missing_keyframe_sheet(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _green_dashboard(tmp_path)
    (tmp_path / "artifacts" / "session" / "session_a" / "visual" / "keyframe_review_contact_sheet.png").unlink()

    summary = audit.build_summary(_args(tmp_path))

    assert summary["pass"] is False
    assert any("contact_sheet_url:linked_file_missing" in issue for issue in summary["issues"])


def test_dashboard_visual_evidence_audit_requires_current_proof_cards(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    dashboard = _green_dashboard(tmp_path)
    payload = audit.json.loads(dashboard.read_text(encoding="utf-8"))
    payload["latest_evidence"] = [
        row for row in payload["latest_evidence"] if row["title"] != "Physical/onboard proof gap is explicit"
    ]
    dashboard.write_text(audit.json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    summary = audit.build_summary(_args(tmp_path))

    assert summary["pass"] is False
    assert "missing_evidence_card:Physical/onboard proof gap is explicit" in summary["issues"]


def test_dashboard_visual_evidence_audit_fails_on_tiny_video(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _green_dashboard(tmp_path)
    _write(
        tmp_path / "artifacts" / "session" / "session_a" / "visual" / "raw_camera_browser.mp4",
        b"x",
    )

    summary = audit.build_summary(_args(tmp_path))

    assert summary["pass"] is False
    assert any("video_url:linked_file_below_10_bytes" in issue for issue in summary["issues"])


def test_dashboard_visual_evidence_scorecard_lists_browser_links(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _green_dashboard(tmp_path)
    summary = audit.build_summary(_args(tmp_path))
    scorecard = tmp_path / "scorecard.md"

    audit.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Dashboard Visual Evidence Audit" in text
    assert "raw_camera_browser.mp4" in text
    assert "keyframe_review_contact_sheet.png" in text


def test_dashboard_visual_evidence_full_card_sweep_catches_archival_tiny_link(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    dashboard = _green_dashboard(tmp_path)
    payload = audit.json.loads(dashboard.read_text(encoding="utf-8"))
    _write(tmp_path / "artifacts" / "session" / "old" / "tiny.md", b"x")
    payload["latest_evidence"].append(
        {
            "title": "Historical card",
            "tone": "green",
            "links": [{"label": "tiny", "url": "/artifacts/session/old/tiny.md"}],
        }
    )
    dashboard.write_text(audit.json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    default_summary = audit.build_summary(_args(tmp_path))
    full_summary = audit.build_summary(_args(tmp_path, audit_all_evidence_cards=True))

    assert default_summary["pass"] is True
    assert full_summary["pass"] is False
    assert any("Historical card" in issue for issue in full_summary["issues"])
