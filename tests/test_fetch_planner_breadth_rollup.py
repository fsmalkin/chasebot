from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_breadth_rollup as rollup  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rollup.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _gate(tmp_path: Path, seed: int, *, provider_ok: bool = False, contact_watch: int = 0) -> Path:
    provider_status = {"ok": 100} if provider_ok else {"skipped_missing_openai_api_key": 100}
    path = tmp_path / f"seed{seed}" / "gate_summary.json"
    return _write_json(
        path,
        {
            "pass": True,
            "seed": seed,
            "random_cases": 100,
            "scorecard_path": f"artifacts/session/seed{seed}/scorecard.md",
            "planner_summary": {
                "pass_count": 100,
                "fail_count": 0,
                "wrong_fetch_dispatch_count": 0,
                "route_counts": {
                    "fetch_ready_local": 20,
                    "nav2_reposition_first": 20,
                    "recovery_or_reaim": 20,
                    "scan_or_perceive_first": 20,
                    "ambiguous_or_unsafe_no_go": 20,
                },
                "provider_status_counts": provider_status,
                "planner_mode_effective_counts": {"deterministic_fallback": 0 if provider_ok else 100},
            },
            "replay_summary": {
                "selected_count": 9,
                "mission_pass_count": 9,
                "mission_fail_count": 0,
                "visual_package_pass_count": 9,
            },
            "analyzer_summary": {
                "execution_quality_status": "clean",
                "setup_quality_status": "clean",
                "contact_quality_status": "clean",
                "contact_watch_count": contact_watch,
                "first_contact_blocker_count": 0,
            },
        },
    )


def _args(*paths: Path):
    return SimpleNamespace(campaign_id="rollup", gate_summary=[str(path) for path in paths])


def test_breadth_rollup_aggregates_green_deterministic_gates(tmp_path: Path):
    first = _gate(tmp_path, 20260649)
    second = _gate(tmp_path, 20260650)

    summary = rollup.build_summary(_args(first, second))

    assert summary["pass"] is True
    assert summary["provider_backed_authority_ready"] is False
    assert summary["total_random_cases"] == 200
    assert summary["total_planner_pass_count"] == 200
    assert summary["total_selected_count"] == 18
    assert summary["total_mission_pass_count"] == 18
    assert summary["total_visual_package_pass_count"] == 18
    assert summary["total_contact_watch_count"] == 0
    assert summary["provider_status_counts"] == {"skipped_missing_openai_api_key": 200}
    assert summary["route_counts"]["fetch_ready_local"] == 40


def test_breadth_rollup_marks_provider_ready_only_when_all_provider_ok(tmp_path: Path):
    first = _gate(tmp_path, 20260649, provider_ok=True)
    second = _gate(tmp_path, 20260650, provider_ok=True)

    summary = rollup.build_summary(_args(first, second))

    assert summary["pass"] is True
    assert summary["provider_backed_authority_ready"] is True
    assert summary["provider_ok_count"] == 200


def test_breadth_rollup_fails_closed_on_contact_watch(tmp_path: Path):
    gate = _gate(tmp_path, 20260650, contact_watch=1)

    summary = rollup.build_summary(_args(gate))

    assert summary["pass"] is False
    assert "seed20260650:contact_watch_nonzero" in summary["issues"]


def test_breadth_rollup_scorecard_lists_totals(tmp_path: Path):
    summary = rollup.build_summary(_args(_gate(tmp_path, 20260650)))
    scorecard = tmp_path / "scorecard.md"

    rollup.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Planner Breadth Rollup" in text
    assert "random_cases: `100`" in text
    assert "wrong_fetch_dispatches: `0`" in text
    assert "deterministic_fallback_evidence_only_until_provider_ok_rerun" in text
