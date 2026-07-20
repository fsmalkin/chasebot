from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_provider_launch_checklist as checklist  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(checklist.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _readiness_payload(*, ready: bool = False) -> dict:
    blockers = [] if ready else ["missing_openai_api_key"]
    return {
        "provider_rerun_ready": ready,
        "openai_api_key_present": ready,
        "blockers": blockers,
        "rerun_contract": {
            "seed": 20260650,
            "random_cases": 100,
            "max_per_route": 3,
            "planner_mode": "llm_supervised_guarded",
            "required_provider_status": "ok_for_all_cases",
            "required_guard_result": "zero_wrong_fetch_dispatches_and_guard_agreement",
            "required_visual_replay": "three_rows_per_route_family_with_browser_watchable_packages",
        },
        "next_commands": {
            "planner_gate": (
                "python scripts\\fetch_planner_seeded_generalization_gate.py "
                "--campaign-id provider_planner_seed20260650_breadth_100x3_20260605 "
                "--seed 20260650 --planner-mode llm_supervised_guarded"
            ),
            "explicit_all_routes_replay": (
                "python scripts\\fetch_planner_route_replay_batch.py "
                "--campaign-id provider_planner_seed20260650_breadth_100x3_20260605_replay "
                "--gate-summary artifacts\\session\\provider_planner_seed20260650_breadth_100x3_20260605_planner\\fetch_planner_handoff_gate\\gate_summary.json"
            ),
            "analysis": (
                "python scripts\\fetch_planner_route_uat_analyzer.py "
                "--campaign-id provider_planner_seed20260650_breadth_100x3_20260605_analysis "
                "--planner-summary artifacts\\session\\provider_planner_seed20260650_breadth_100x3_20260605_planner\\fetch_planner_handoff_gate\\gate_summary.json"
            ),
            "provider_rerun_comparison": (
                "python scripts\\fetch_planner_provider_rerun_comparison.py "
                "--campaign-id provider_planner_seed20260650_provider_rerun_comparison_20260605 "
                "--seed 20260650 "
                "--provider-planner-summary artifacts\\session\\provider_planner_seed20260650_breadth_100x3_20260605_planner\\fetch_planner_handoff_gate\\gate_summary.json "
                "--provider-replay-summary artifacts\\session\\provider_planner_seed20260650_breadth_100x3_20260605_replay\\fetch_planner_route_replay_batch\\batch_summary.json "
                "--provider-route-uat-summary artifacts\\session\\provider_planner_seed20260650_breadth_100x3_20260605_analysis\\fetch_planner_route_uat_analyzer\\route_uat_summary.json"
            ),
        },
    }


def _args(tmp_path: Path, *, key: str = "") -> SimpleNamespace:
    readiness = _write_json(tmp_path / "provider_readiness.json", _readiness_payload(ready=bool(key)))
    return SimpleNamespace(
        campaign_id="provider_launch",
        provider_readiness_summary=str(readiness),
        openai_api_key=key,
    )


def test_provider_launch_checklist_is_plan_ready_while_key_is_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(checklist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checklist, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    summary = checklist.build_summary(_args(tmp_path))

    assert summary["pass"] is True
    assert summary["launch_plan_ready"] is True
    assert summary["provider_launch_ready"] is False
    assert summary["provider_backed_authority_proven"] is False
    assert summary["blockers"] == ["missing_openai_api_key"]
    assert summary["expected_artifacts"]["provider_planner_summary"].endswith("gate_summary.json")
    assert len(summary["launch_steps"]) == 6


def test_provider_launch_checklist_becomes_launch_ready_with_key_and_clean_readiness(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(checklist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checklist, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    summary = checklist.build_summary(_args(tmp_path, key="sk-test"))

    assert summary["pass"] is True
    assert summary["provider_launch_ready"] is True
    assert summary["openai_api_key_present"] is True
    assert summary["blockers"] == []
    assert summary["readiness_level"] == "ready_for_provider_launch"


def test_provider_launch_checklist_scorecard_lists_commands_and_claim_boundaries(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(checklist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checklist, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    scorecard = tmp_path / "scorecard.md"
    summary = checklist.build_summary(_args(tmp_path))

    checklist.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Provider Launch Checklist" in text
    assert "provider_backed_authority_proven: `False`" in text
    assert "provider_planner_gate" in text
    assert "fetch_planner_provider_rerun_comparison.py" in text
    assert "provider_backed_authority_proven_false_until_provider_artifacts_pass" in text
