from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_provider_rerun_comparison as comparison  # noqa: E402


ROUTES = {
    "ambiguous_or_unsafe_no_go": 22,
    "fetch_ready_local": 23,
    "nav2_reposition_first": 16,
    "recovery_or_reaim": 15,
    "scan_or_perceive_first": 24,
}


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(comparison.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "provider_compare",
        "seed": 20260650,
        "baseline_rollup_summary": str(tmp_path / "baseline" / "breadth_rollup_summary.json"),
        "provider_planner_summary": str(tmp_path / "provider" / "gate_summary.json"),
        "provider_replay_summary": str(tmp_path / "provider" / "batch_summary.json"),
        "provider_route_uat_summary": str(tmp_path / "provider" / "route_uat_summary.json"),
        "min_baseline_random_cases": 300,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _green_baseline(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "total_random_cases": 300,
            "rows": [
                {
                    "seed": 20260648,
                    "pass": True,
                    "random_cases": 100,
                    "wrong_fetch_dispatch_count": 0,
                    "route_counts": {**ROUTES, "fetch_ready_local": 19},
                    "scorecard_path": "artifacts/session/seed48/scorecard.md",
                },
                {
                    "seed": 20260649,
                    "pass": True,
                    "random_cases": 100,
                    "wrong_fetch_dispatch_count": 0,
                    "route_counts": {**ROUTES, "fetch_ready_local": 28},
                    "scorecard_path": "artifacts/session/seed49/scorecard.md",
                },
                {
                    "seed": 20260650,
                    "pass": True,
                    "random_cases": 100,
                    "wrong_fetch_dispatch_count": 0,
                    "route_counts": ROUTES,
                    "scorecard_path": "artifacts/session/seed50/scorecard.md",
                },
            ],
        },
    )


def _provider_result(veto_reasons: list[str]) -> dict:
    return {
        "llm_supervised_guard": {
            "decision": "vetoed",
            "veto_reasons": veto_reasons,
        }
    }


def _green_provider(path: Path, *, accepted: int = 100, vetoed: int = 0, veto_reasons: list[str] | None = None) -> Path:
    veto_reasons = veto_reasons or []
    return _write_json(
        path,
        {
            "pass": True,
            "planner_mode": "llm_supervised_guarded",
            "seed": 20260650,
            "random_cases": 100,
            "pass_count": 100,
            "fail_count": 0,
            "provider_status_counts": {"ok": 100},
            "planner_mode_effective_counts": {
                "llm_supervised_guarded": accepted,
                "deterministic_fallback": vetoed,
            },
            "guard_agreement_count": 100,
            "guard_disagreement_count": 0,
            "wrong_fetch_dispatch_count": 0,
            "llm_supervised_accept_count": accepted,
            "llm_supervised_veto_count": vetoed,
            "route_counts": ROUTES,
            "results": [_provider_result(veto_reasons) for _ in range(vetoed)],
        },
    )


def _green_replay(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "selected_count": 9,
            "mission_pass_count": 9,
            "mission_fail_count": 0,
            "visual_package_pass_count": 9,
            "route_only_pass_count": 0,
            "requested_route_count": {
                "fetch_ready_local": 3,
                "nav2_reposition_first": 3,
                "recovery_or_reaim": 3,
            },
        },
    )


def _green_route_uat(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "milestone_interpretation": "randomized_route_owner_visual_uat_green",
            "execution_quality_status": "clean",
            "setup_quality_status": "clean",
            "contact_quality_status": "clean",
            "contact_watch_count": 0,
            "first_contact_blocker_count": 0,
        },
    )


def _green_fixture(tmp_path: Path, **provider_overrides):
    args = _args(tmp_path)
    _green_baseline(Path(args.baseline_rollup_summary))
    _green_provider(Path(args.provider_planner_summary), **provider_overrides)
    _green_replay(Path(args.provider_replay_summary))
    _green_route_uat(Path(args.provider_route_uat_summary))
    return args


def test_provider_rerun_comparison_accepts_strict_provider_visual_uat(tmp_path: Path):
    summary = comparison.build_summary(_green_fixture(tmp_path))

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "provider_rerun_strict_visual_uat_green"
    assert summary["strict_provider_authority_ready"] is True
    assert summary["guarded_provider_rerun_ready"] is True
    assert summary["provider_planner"]["route_deltas_from_baseline_seed"]["fetch_ready_local"] == 0


def test_provider_rerun_comparison_accepts_confidence_guarded_fallback(tmp_path: Path):
    args = _green_fixture(tmp_path, accepted=99, vetoed=1, veto_reasons=["confidence_below_threshold"])

    summary = comparison.build_summary(args)

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "provider_rerun_guarded_visual_uat_green"
    assert summary["strict_provider_authority_ready"] is False
    assert summary["guarded_provider_rerun_ready"] is True
    assert summary["provider_planner"]["llm_supervised_veto_reason_counts"] == {"confidence_below_threshold": 1}


def test_provider_rerun_comparison_blocks_non_confidence_veto(tmp_path: Path):
    args = _green_fixture(tmp_path, accepted=99, vetoed=1, veto_reasons=["route_family_disagreement"])

    summary = comparison.build_summary(args)

    assert summary["pass"] is False
    assert "provider_planner:non_confidence_veto:route_family_disagreement" in summary["blockers"]


def test_provider_rerun_comparison_requires_visual_replay_and_clean_analyzer(tmp_path: Path):
    args = _green_fixture(tmp_path)
    _write_json(
        Path(args.provider_route_uat_summary),
        {
            "pass": True,
            "execution_quality_status": "clean",
            "setup_quality_status": "clean",
            "contact_quality_status": "watch",
            "contact_watch_count": 1,
            "first_contact_blocker_count": 0,
        },
    )

    summary = comparison.build_summary(args)

    assert summary["pass"] is False
    assert "provider_route_uat:contact_quality_not_clean" in summary["blockers"]
    assert "provider_route_uat:contact_watch_nonzero" in summary["blockers"]


def test_provider_rerun_comparison_scorecard_contains_route_deltas(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = comparison.build_summary(_green_fixture(tmp_path))

    comparison.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Planner Provider Rerun Comparison" in text
    assert "route deltas from baseline seed" in text
    assert "provider_rerun_comparison_ready: `True`" in text
