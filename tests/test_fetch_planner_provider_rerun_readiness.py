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
        "breadth_rollup_summary": str(tmp_path / "rollup" / "breadth_rollup_summary.json"),
        "dashboard_plan": str(tmp_path / "dashboard.json"),
        "seed": 20260650,
        "random_cases": 100,
        "max_per_route": 3,
        "min_rollup_random_cases": 300,
        "min_rollup_executable_rows": 27,
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
            "seed": 20260650,
            "random_cases": 100,
            "pass_count": 100,
            "wrong_fetch_dispatch_count": 0,
            "provider_status_counts": {"skipped_missing_openai_api_key": 100},
            "planner_mode_effective_counts": {"deterministic_fallback": 100},
            "route_counts": {
                "ambiguous_or_unsafe_no_go": 19,
                "fetch_ready_local": 19,
                "nav2_reposition_first": 21,
                "recovery_or_reaim": 16,
                "scan_or_perceive_first": 25,
            },
        },
    )


def _green_rollup(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "seeds": [20260648, 20260649, 20260650],
            "gate_count": 3,
            "total_random_cases": 300,
            "total_planner_pass_count": 300,
            "total_wrong_fetch_dispatch_count": 0,
            "total_selected_count": 27,
            "total_mission_pass_count": 27,
            "total_mission_fail_count": 0,
            "total_visual_package_pass_count": 27,
            "total_contact_watch_count": 0,
            "total_first_contact_blocker_count": 0,
            "provider_backed_authority_ready": False,
            "provider_status_counts": {"skipped_missing_openai_api_key": 300},
            "route_counts": {
                "ambiguous_or_unsafe_no_go": 56,
                "fetch_ready_local": 70,
                "nav2_reposition_first": 57,
                "recovery_or_reaim": 52,
                "scan_or_perceive_first": 65,
            },
        },
    )


def _green_dashboard(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status_label": "Three-seed breadth rollup green; seed 20260648 hardware rehearsal green",
            "status_detail": "The rollup covers seeds 20260648, 20260649, and 20260650 across 300 scenes.",
            "latest_evidence": [
                {
                    "title": "Three-seed breadth rollup is green",
                    "metrics": ["Planner breadth: random_cases=300", "Seed 20260650 fresh breadth UAT is green"],
                }
            ],
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
    _green_rollup(Path(args.breadth_rollup_summary))
    _green_dashboard(Path(args.dashboard_plan))
    return args


def test_provider_rerun_readiness_blocks_without_openai_key(tmp_path: Path):
    summary = readiness.build_summary(_green_fixture(tmp_path))

    assert summary["pass"] is False
    assert summary["provider_rerun_ready"] is False
    assert summary["provider_backed_authority_proven"] is False
    assert summary["readiness_level"] == "provider_rerun_blocked"
    assert summary["blockers"] == ["missing_openai_api_key"]
    assert summary["breadth_rollup"]["pass"] is True
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
            "seed": 20260650,
            "random_cases": 100,
            "pass_count": 100,
            "wrong_fetch_dispatch_count": 0,
            "provider_status_counts": {"skipped_missing_openai_api_key": 100},
            "planner_mode_effective_counts": {"deterministic_fallback": 100},
            "route_counts": {"fetch_ready_local": 100},
        },
    )

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert "latest_fallback_seed:route_family_coverage_incomplete" in summary["blockers"]


def test_provider_rerun_readiness_requires_green_breadth_rollup(tmp_path: Path):
    args = _green_fixture(tmp_path)
    args.openai_api_key = "sk-test"
    _write_json(
        Path(args.breadth_rollup_summary),
        {
            "pass": True,
            "seeds": [20260648, 20260649, 20260650],
            "total_random_cases": 300,
            "total_planner_pass_count": 300,
            "total_wrong_fetch_dispatch_count": 1,
            "total_selected_count": 27,
            "total_mission_pass_count": 27,
            "total_mission_fail_count": 0,
            "total_visual_package_pass_count": 27,
            "total_contact_watch_count": 0,
            "total_first_contact_blocker_count": 0,
            "provider_backed_authority_ready": False,
            "provider_status_counts": {"skipped_missing_openai_api_key": 300},
            "route_counts": {
                "ambiguous_or_unsafe_no_go": 56,
                "fetch_ready_local": 70,
                "nav2_reposition_first": 57,
                "recovery_or_reaim": 52,
                "scan_or_perceive_first": 65,
            },
        },
    )

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert "breadth_rollup:breadth_rollup_wrong_fetch_dispatch_count_nonzero" in summary["blockers"]


def test_provider_rerun_readiness_scorecard_names_blocker_and_commands(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = readiness.build_summary(_green_fixture(tmp_path))

    readiness.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "openai_api_key_present: `False`" in text
    assert "## Breadth Rollup Baseline" in text
    assert "total_random_cases: `300`" in text
    assert "`missing_openai_api_key`" in text
    assert "fetch_planner_seeded_generalization_gate.py" in text
