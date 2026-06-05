from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_provider_rerun_readiness as readiness  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(readiness.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "provider_ready",
        "latest_fallback_planner_summary": str(tmp_path / "planner" / "gate_summary.json"),
        "dashboard_plan": str(tmp_path / "dashboard.json"),
        "seed": 20260647,
        "random_cases": 80,
        "max_per_route": 3,
        "dashboard_url": "http://127.0.0.1:8883",
        "campaign_suffix": "20260605",
        "openai_api_key": "",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _green_planner(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "seed": 20260647,
            "random_cases": 80,
            "pass_count": 80,
            "wrong_fetch_dispatch_count": 0,
            "provider_status_counts": {"skipped_missing_openai_api_key": 80},
            "planner_mode_effective_counts": {"deterministic_fallback": 80},
            "route_counts": {
                "ambiguous_or_unsafe_no_go": 16,
                "fetch_ready_local": 18,
                "nav2_reposition_first": 11,
                "recovery_or_reaim": 22,
                "scan_or_perceive_first": 13,
            },
        },
    )


def _green_dashboard(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status_label": "Seed 20260647 mixed all-routes 3x UAT is green",
            "status_detail": "Seed20260647 classified 80 generated scenes.",
            "uat_review_bundle": {
                "route_samples": [
                    {
                        "label": f"sample{i}",
                        "video_url": f"/artifacts/session/sample{i}/visual/raw_camera_browser.mp4",
                    }
                    for i in range(15)
                ]
            },
        },
    )


def _green_fixture(tmp_path: Path):
    args = _args(tmp_path)
    _green_planner(Path(args.latest_fallback_planner_summary))
    _green_dashboard(Path(args.dashboard_plan))
    return args


def test_provider_rerun_readiness_blocks_without_openai_key(tmp_path: Path):
    summary = readiness.build_summary(_green_fixture(tmp_path))

    assert summary["pass"] is False
    assert summary["provider_rerun_ready"] is False
    assert summary["provider_backed_authority_proven"] is False
    assert summary["readiness_level"] == "provider_rerun_blocked"
    assert summary["blockers"] == ["missing_openai_api_key"]
    assert summary["latest_fallback_seed"]["pass"] is True


def test_provider_rerun_readiness_passes_when_key_and_fallback_evidence_are_ready(tmp_path: Path):
    args = _green_fixture(tmp_path)
    args.openai_api_key = "sk-test"

    summary = readiness.build_summary(args)

    assert summary["pass"] is True
    assert summary["provider_rerun_ready"] is True
    assert summary["openai_api_key_present"] is True
    assert summary["blockers"] == []
    assert "--planner-mode llm_supervised_guarded" in summary["next_commands"]["planner_gate"]
    assert "--route ambiguous_or_unsafe_no_go" in summary["next_commands"]["explicit_all_routes_replay"]


def test_provider_rerun_readiness_requires_all_route_families(tmp_path: Path):
    args = _green_fixture(tmp_path)
    args.openai_api_key = "sk-test"
    _write_json(
        Path(args.latest_fallback_planner_summary),
        {
            "pass": True,
            "seed": 20260647,
            "random_cases": 80,
            "pass_count": 80,
            "wrong_fetch_dispatch_count": 0,
            "provider_status_counts": {"skipped_missing_openai_api_key": 80},
            "planner_mode_effective_counts": {"deterministic_fallback": 80},
            "route_counts": {"fetch_ready_local": 80},
        },
    )

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert "latest_fallback_seed:route_family_coverage_incomplete" in summary["blockers"]


def test_provider_rerun_readiness_scorecard_names_blocker_and_commands(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = readiness.build_summary(_green_fixture(tmp_path))

    readiness.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "openai_api_key_present: `False`" in text
    assert "`missing_openai_api_key`" in text
    assert "fetch_planner_seeded_generalization_gate.py" in text
