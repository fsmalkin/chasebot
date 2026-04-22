from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import probe_odom_world_sign_chain as audit  # noqa: E402


SOURCE_CAMPAIGN_SUMMARY_PATH = audit.DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_CAMPAIGN_SUMMARY
SOURCE_AUDIT_SUMMARY_PATH = audit.DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SOURCE_AUDIT_SUMMARY
RECOVERED_PROBE_CAMPAIGN_SUMMARY_PATH = (
    REPO_ROOT
    / "artifacts"
    / "session"
    / "live_plus45_probe_odom_world_sign_chain_20260420_post_recovery_rerun_retry1_live_probe"
    / "gather_mission_repeatability"
    / "campaign_run_summary.json"
)
RECOVERED_RUNTIME_PROBE_JSON_PATH = (
    REPO_ROOT
    / "artifacts"
    / "session"
    / "live_plus45_probe_odom_world_sign_chain_20260420_post_recovery_rerun_retry1"
    / "probe_odom_world_sign_chain"
    / "runtime_probe.json"
)

SOURCE_EXPECTED = {
    "early_stall": {
        "window_start_t_s": 18.668,
        "window_end_t_s": 29.88599,
        "dominant_command_sign": 1,
        "net_requested_angular_integral_rad": 2.192867,
        "state_row_count": 22,
    },
    "mid_stall": {
        "window_start_t_s": 25.052,
        "window_end_t_s": 36.259906,
        "dominant_command_sign": 1,
        "net_requested_angular_integral_rad": 0.745898,
        "state_row_count": 22,
    },
    "late_stall": {
        "window_start_t_s": 31.39,
        "window_end_t_s": 37.801761,
        "dominant_command_sign": -1,
        "net_requested_angular_integral_rad": -1.063729,
        "state_row_count": 13,
    },
    "terminal_stall": {
        "window_start_t_s": 37.679,
        "window_end_t_s": 37.679,
        "dominant_command_sign": 1,
        "net_requested_angular_integral_rad": 0.8,
        "state_row_count": 1,
    },
}

FRESH_EXPECTED = {
    "early_stall": {
        "window_start_t_s": 18.816,
        "window_end_t_s": 30.080076,
        "dominant_command_sign": -1,
        "net_requested_angular_integral_rad": -0.307799,
        "state_row_count": 21,
    },
    "mid_stall": {
        "window_start_t_s": 24.542,
        "window_end_t_s": 36.005026,
        "dominant_command_sign": -1,
        "net_requested_angular_integral_rad": -0.285746,
        "state_row_count": 21,
    },
    "late_stall": {
        "window_start_t_s": 31.094,
        "window_end_t_s": 37.982542,
        "dominant_command_sign": 1,
        "net_requested_angular_integral_rad": 0.822182,
        "state_row_count": 13,
    },
    "terminal_stall": {
        "window_start_t_s": 37.469,
        "window_end_t_s": 37.469,
        "dominant_command_sign": 1,
        "net_requested_angular_integral_rad": 0.374983,
        "state_row_count": 1,
    },
}


def _reconstruct_fixture_local_command_payloads(campaign_summary_path: Path) -> dict[str, dict]:
    run_context = audit._load_run_alignment_context(campaign_summary_path, run_index=0)
    return audit.build_fixture_local_command_payloads(
        audit.oracle.select_representative_fixture_rows(run_context["state_rows"]),
        state_rows=run_context["state_rows"],
        truth_samples=run_context["truth_samples"],
        timeline_anchor=run_context["timeline_anchor"],
        scenario_id=audit.DEFAULT_PROBE_ODOM_WORLD_SIGN_CHAIN_SCENARIO_ID,
    )


@pytest.mark.parametrize(
    ("campaign_summary_path", "expected_by_label"),
    [
        (SOURCE_CAMPAIGN_SUMMARY_PATH, SOURCE_EXPECTED),
        (RECOVERED_PROBE_CAMPAIGN_SUMMARY_PATH, FRESH_EXPECTED),
    ],
)
def test_reconstructs_saved_fixture_window_provenance(
    campaign_summary_path: Path,
    expected_by_label: dict[str, dict[str, float | int]],
):
    payloads = _reconstruct_fixture_local_command_payloads(campaign_summary_path)

    for fixture_label, expected in expected_by_label.items():
        payload = payloads[fixture_label]
        metrics = payload["command_metrics"]
        window = payload["window"]
        assert metrics["window_start_t_s"] == pytest.approx(expected["window_start_t_s"], abs=1.0e-6)
        assert metrics["window_end_t_s"] == pytest.approx(expected["window_end_t_s"], abs=1.0e-6)
        assert metrics["dominant_command_sign"] == expected["dominant_command_sign"]
        assert metrics["net_requested_angular_integral_rad"] == pytest.approx(
            expected["net_requested_angular_integral_rad"],
            abs=1.0e-6,
        )
        assert window["state_row_count"] == expected["state_row_count"]
        assert window["window_scope"] == "fixture_window"


def test_recovered_live_bundle_preserves_source_fixture_mismatch_with_provenance():
    summary, fixture_payloads = audit.build_odom_world_sign_chain_bundle(
        campaign_id="live_plus45_probe_odom_world_sign_chain_20260420_post_recovery_rerun_retry1",
        campaign_summary_path=RECOVERED_PROBE_CAMPAIGN_SUMMARY_PATH,
        runtime_probe_json_path=RECOVERED_RUNTIME_PROBE_JSON_PATH,
        source_audit_summary_path=SOURCE_AUDIT_SUMMARY_PATH,
        source_campaign_summary_path=SOURCE_CAMPAIGN_SUMMARY_PATH,
    )

    assert summary["runtime_classification"]["diagnosis"] == "sign_chain_aligned"
    assert summary["source_alignment_assessment"]["diagnosis"] == "source_fixture_command_sign_mismatch"
    assert summary["source_fixture_local_command_payload_count"] == 5
    assert summary["fresh_fixture_local_command_payload_count"] == 5

    expected_sign_match = {
        "early_stall": False,
        "mid_stall": False,
        "late_stall": False,
        "terminal_stall": True,
    }
    for fixture_label, dominant_sign_match in expected_sign_match.items():
        fixture_payload = fixture_payloads[fixture_label]
        assert fixture_payload["source_fixture_local_command"]["command_metrics"]["window_scope"] == "fixture_window"
        assert fixture_payload["fresh_fixture_local_command"]["command_metrics"]["window_scope"] == "fixture_window"
        assert fixture_payload["source_fresh_fixture_window_comparison"]["dominant_command_sign_match"] is dominant_sign_match
