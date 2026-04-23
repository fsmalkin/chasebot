from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_control_stress_analyzer as stress  # noqa: E402


def _write_summary(tmp_path: Path, name: str, payload: dict[str, object]) -> Path:
    path = tmp_path / f"{name}.json"
    base_payload = {
        "type": "gather_mission_repeatability",
        "campaign_id": name,
        "scenario_id": "corral_single_ball_place",
        "runs": [],
    }
    base_payload.update(payload)
    path.write_text(json.dumps(base_payload, indent=2), encoding="utf-8")
    return path


def _complete_fixture_evidence(*, passed: bool = True) -> list[dict[str, object]]:
    return [
        {"fixture_label": fixture_label, "pass": passed, "evidence_id": f"{fixture_label}_synthetic"}
        for fixture_label in stress.REQUIRED_FIXTURE_LABELS
    ]


def test_complete_passing_fixture_evidence_marks_branch_passing(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "short_horizon_v2",
        {"stress_fixtures": _complete_fixture_evidence(passed=True)},
    )

    summary, branch_bundles = stress.build_control_stress_summary(
        campaign_id="stress_test",
        branch_specs=[("short_horizon_v2", summary_path)],
    )

    branch = summary["branches"][0]
    assert summary["status"] == "passing"
    assert branch["status"] == "passing"
    assert branch["evaluated_fixture_labels"] == list(stress.REQUIRED_FIXTURE_LABELS)
    assert branch["missing_fixture_labels"] == []
    assert branch["failing_fixture_labels"] == []
    assert branch["blocking_reasons"] == []
    assert len(branch_bundles[0][1]) == len(stress.REQUIRED_FIXTURE_LABELS)


def test_missing_and_failing_required_labels_mark_branch_failing(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "candidate",
        {
            "stress_fixtures": [
                {"fixture_label": "early_stall", "status": "passing"},
                {"fixture_label": "mid_stall", "status": "failing", "reason": "synthetic_regression"},
                {"fixture_label": "terminal_stall", "status": "passing"},
            ]
        },
    )

    summary, _ = stress.build_control_stress_summary(
        campaign_id="stress_test",
        branch_specs=[("candidate", summary_path)],
    )

    branch = summary["branches"][0]
    assert summary["status"] == "failing"
    assert branch["status"] == "failing"
    assert branch["evaluated_fixture_labels"] == ["early_stall", "mid_stall", "terminal_stall"]
    assert branch["missing_fixture_labels"] == ["late_stall"]
    assert branch["failing_fixture_labels"] == ["mid_stall"]
    assert "missing_required_fixture_evidence" in branch["blocking_reasons"]
    assert "required_fixture_failed" in branch["blocking_reasons"]


def test_not_evaluated_when_no_usable_fixture_evidence_exists(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "legacy_v1",
        {
            "runs": [
                {"run_index": 0, "pass": True},
                {"run_index": 1, "mission_completed_pass": False},
            ]
        },
    )

    summary, _ = stress.build_control_stress_summary(
        campaign_id="stress_test",
        branch_specs=[("legacy_v1", summary_path)],
    )

    branch = summary["branches"][0]
    assert summary["status"] == "not_evaluated"
    assert branch["status"] == "not_evaluated"
    assert branch["usable_fixture_count"] == 0
    assert branch["missing_fixture_labels"] == list(stress.REQUIRED_FIXTURE_LABELS)
    assert branch["blocking_reasons"] == ["no_usable_fixture_evidence"]


def test_present_fixture_label_without_explicit_pass_fail_is_deterministic_not_evaluated(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "legacy_with_labels",
        {"fixtures": {"early_stall": {"observed": True, "note": "no verdict field"}}},
    )

    summary, _ = stress.build_control_stress_summary(
        campaign_id="stress_test",
        branch_specs=[("legacy_with_labels", summary_path)],
    )

    branch = summary["branches"][0]
    early = branch["fixtures"]["early_stall"]
    assert branch["status"] == "not_evaluated"
    assert early["status"] == "not_evaluated"
    assert early["reason"] == "fixture_label_present_without_explicit_pass_fail"
    assert early["usable_evidence_count"] == 0


def test_branch_name_sanitization_and_duplicate_detection(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "branch",
        {"stress_fixtures": _complete_fixture_evidence(passed=True)},
    )

    summary, _ = stress.build_control_stress_summary(
        campaign_id="stress_test",
        branch_specs=[("Short Horizon V2/../candidate", summary_path)],
    )

    branch = summary["branches"][0]
    assert branch["branch_name"] == "Short Horizon V2/../candidate"
    assert branch["branch_slug"] == "Short_Horizon_V2_candidate"
    assert "/" not in branch["branch_slug"]
    assert "\\" not in branch["branch_slug"]

    with pytest.raises(ValueError, match="Duplicate sanitized branch name"):
        stress.build_control_stress_summary(
            campaign_id="stress_test",
            branch_specs=[
                ("alpha branch", summary_path),
                ("alpha/branch", summary_path),
            ],
        )


def test_output_paths_include_branch_stress_summary_fixtures_and_scorecard(tmp_path: Path):
    summary_path = _write_summary(
        tmp_path,
        "branch",
        {"stress_fixtures": _complete_fixture_evidence(passed=True)},
    )
    summary, branch_bundles = stress.build_control_stress_summary(
        campaign_id="stress_test",
        branch_specs=[("helper", summary_path)],
    )

    paths = stress.write_control_stress_bundle(
        repo_root=tmp_path,
        campaign_id="stress_test",
        summary=summary,
        branch_bundles=branch_bundles,
    )

    output_root = tmp_path / "artifacts" / "session" / "stress_test" / "gather_control_portfolio"
    branch_root = output_root / "helper"
    assert paths["summary_path"] == output_root / "stress_summary.json"
    assert paths["scorecard_path"] == output_root / "stress_scorecard.md"
    assert (branch_root / "stress_summary.json").exists()
    for fixture_label in stress.REQUIRED_FIXTURE_LABELS:
        fixture_path = branch_root / "fixtures" / f"{fixture_label}.json"
        assert fixture_path.exists()
        assert json.loads(fixture_path.read_text(encoding="utf-8"))["fixture_label"] == fixture_label
    scorecard = paths["scorecard_path"].read_text(encoding="utf-8")
    assert "| `helper` | `passing` | 4 / 4 |" in scorecard
