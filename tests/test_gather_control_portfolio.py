from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_control_portfolio as portfolio  # noqa: E402


def _run(
    *,
    passed: bool,
    practical: bool,
    mission_time_s: float,
    pre_stage_pose_reached: bool = True,
    pre_stage_handoff_pass: bool = True,
    staging_pose_reached: bool = True,
    capture_entry_reached: bool = True,
) -> dict[str, object]:
    return {
        "pass": passed,
        "mission_completed_pass": passed,
        "pre_stage_pose_reached": pre_stage_pose_reached,
        "pre_stage_handoff_pass": pre_stage_handoff_pass,
        "staging_pose_reached": staging_pose_reached,
        "capture_entry_reached": capture_entry_reached,
        "final_inside_retrieval_corral": practical,
        "ball_stopped_in_corral": practical,
        "rolled_away_after_release": not practical,
        "settled_in_corral_pass": practical,
        "final_center_inside_zone": practical,
        "final_all_targets_inside_retrieval_corral": practical,
        "final_all_targets_stopped": practical,
        "final_three_ball_corral_pass": practical,
        "mission_time_s": mission_time_s,
        "final_settle_distance_m": 0.04 if practical else 0.8,
        "max_overshoot_distance_m": 0.1 if practical else 1.2,
        "settle_time_s": 1.5 if practical else 0.0,
        "placed_count": 1 if practical else 0,
        "retrieved_count": 1 if practical else 0,
        "capture_loss_count": 0 if practical else 1,
        "post_visit_revisit_count": 0,
    }


def _write_summary(tmp_path: Path, name: str, runs: list[dict[str, object]]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "type": "gather_mission_repeatability",
                "campaign_id": name,
                "scenario_id": "corral_single_ball_place",
                "runs": runs,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_single_branch_summary_scores_mixed_repeatability_runs(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "helper",
        [
            _run(passed=True, practical=True, mission_time_s=12.0),
            _run(
                passed=False,
                practical=False,
                mission_time_s=20.0,
                staging_pose_reached=False,
                capture_entry_reached=False,
            ),
        ],
    )

    summary = portfolio.build_portfolio_summary(
        campaign_id="portfolio_test",
        branch_specs=[("helper", summary_path)],
        baseline_branch="helper",
    )

    branch = summary["branches"][0]
    assert branch["run_count"] == 2
    assert branch["pass_rate"] == 0.5
    assert branch["practical_retrieval_pass_rate"] == 0.5
    assert branch["phase_reach_rates"]["pre_stage_pose_reached"] == 1.0
    assert branch["phase_reach_rates"]["staging_pose_reached"] == 0.5
    assert branch["phase_reach_rates"]["capture_entry_reached"] == 0.5
    assert branch["average_mission_time_s"] == 16.0
    assert branch["corral_placement_metrics"]["practical_retrieval_pass"]["true_count"] == 1
    assert branch["hard_case_stress_status"] == "not_evaluated"
    assert branch["live_promotion_ready"] is False


def test_multiple_branches_identifies_best_observed_but_blocks_promotion(tmp_path: Path):
    helper_path = _write_summary(
        tmp_path,
        "helper",
        [
            _run(passed=True, practical=True, mission_time_s=18.0),
            _run(passed=False, practical=False, mission_time_s=25.0),
        ],
    )
    short_horizon_path = _write_summary(
        tmp_path,
        "short_horizon_v2",
        [
            _run(passed=True, practical=True, mission_time_s=13.0),
            _run(passed=True, practical=True, mission_time_s=14.0),
        ],
    )

    summary = portfolio.build_portfolio_summary(
        campaign_id="portfolio_test",
        branch_specs=[("helper", helper_path), ("short_horizon_v2", short_horizon_path)],
        baseline_branch="helper",
    )

    assert summary["best_observed_branch"] == "short_horizon_v2"
    assert summary["recommended_next_action"] == "collect_hard_case_stress_evidence"
    assert summary["live_promotion_ready"] is False
    assert "hard_case_stress_not_evaluated" in summary["blocking_reasons"]
    helper, short_horizon = summary["branches"]
    assert helper["baseline_comparison"]["is_baseline"] is True
    assert short_horizon["baseline_comparison"]["baseline_branch"] == "helper"
    assert short_horizon["baseline_comparison"]["practical_retrieval_pass_rate_delta"] == 0.5
    assert short_horizon["baseline_comparison"]["average_mission_time_delta_s"] == -8.0


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"final_inside_retrieval_corral": True, "ball_stopped_in_corral": True, "rolled_away_after_release": False}, True),
        ({"final_inside_retrieval_corral": True, "ball_stopped_in_corral": True, "rolled_away_after_release": True}, False),
        ({"final_inside_retrieval_corral": True, "ball_stopped_in_corral": False, "rolled_away_after_release": False}, False),
        ({"final_inside_retrieval_corral": True, "ball_stopped_in_corral": True}, None),
    ],
)
def test_practical_retrieval_scoring_requires_inside_stopped_and_not_rolled(fields: dict[str, object], expected: bool | None):
    assert portfolio.practical_retrieval_pass(fields) is expected


def test_missing_hard_case_evidence_blocks_readiness_even_when_e2e_is_green(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "green_end_to_end",
        [_run(passed=True, practical=True, mission_time_s=11.0)],
    )

    summary = portfolio.build_portfolio_summary(
        campaign_id="portfolio_test",
        branch_specs=[("green_end_to_end", summary_path)],
    )

    branch = summary["branches"][0]
    assert branch["pass_rate"] == 1.0
    assert branch["practical_retrieval_pass_rate"] == 1.0
    assert branch["hard_case_stress"]["missing_fixture_labels"] == list(portfolio.STRESS_FIXTURE_LABELS)
    assert branch["live_promotion_ready"] is False
    assert "hard_case_stress_not_evaluated" in branch["blocking_reasons"]


def test_branch_name_sanitization_for_artifact_paths(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "branch",
        [_run(passed=True, practical=True, mission_time_s=10.0)],
    )

    summary = portfolio.build_portfolio_summary(
        campaign_id="portfolio_test",
        branch_specs=[("Short Horizon V2/../candidate", summary_path)],
    )

    branch = summary["branches"][0]
    assert branch["branch_name"] == "Short Horizon V2/../candidate"
    assert branch["branch_slug"] == "Short_Horizon_V2_candidate"
    assert "/" not in branch["branch_slug"]
    assert "\\" not in branch["branch_slug"]


def test_scorecard_and_bundle_outputs_include_branch_rows_and_next_action(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "helper",
        [_run(passed=True, practical=True, mission_time_s=12.0)],
    )
    summary = portfolio.build_portfolio_summary(
        campaign_id="portfolio_test",
        branch_specs=[("helper", summary_path)],
        baseline_branch="helper",
    )

    paths = portfolio.write_portfolio_bundle(repo_root=tmp_path, campaign_id="portfolio_test", summary=summary)
    scorecard = paths["scorecard_path"].read_text(encoding="utf-8")

    assert paths["summary_path"].exists()
    assert (tmp_path / "artifacts" / "session" / "portfolio_test" / "gather_control_portfolio" / "helper" / "branch_summary.json").exists()
    assert "| `helper` | 1 | 100.0% | 100.0%" in scorecard
    assert "recommended_next_action: `collect_hard_case_stress_evidence`" in scorecard
    assert "hard_case_stress_not_evaluated" in scorecard
