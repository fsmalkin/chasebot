import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from corral_surface_calibration_helpers import build_surface_calibration_lanes  # noqa: E402
from corral_surface_calibration_helpers import build_surface_calibration_scorecard_markdown  # noqa: E402
from corral_surface_calibration_helpers import compute_ordering_checks  # noqa: E402
from corral_surface_calibration_helpers import choose_canonical_surface_profile  # noqa: E402
from corral_surface_calibration_helpers import summarize_surface_calibration  # noqa: E402
from corral_surface_calibration_helpers import summarize_surface_lane  # noqa: E402


def test_build_surface_calibration_lanes_is_fixed_and_ordered():
    lanes = build_surface_calibration_lanes()
    assert [(item.surface_profile, item.world_file) for item in lanes] == [
        ("baseline", "yolo_test_world_v6_clean_uat.world"),
        ("short_turf", "yolo_test_world_v6_clean_uat_short_turf.world"),
        ("short_grass", "yolo_test_world_v6_clean_uat_short_grass.world"),
    ]


def test_summarize_surface_lane_uses_settled_runs_for_settle_metrics():
    lane = build_surface_calibration_lanes()[1]
    runs = [
        {
            "settled_in_corral_pass": True,
            "final_settle_distance_m": 0.22,
            "max_overshoot_distance_m": 0.08,
            "settle_time_s": 1.8,
            "release_recontact_count": 1,
            "mission_time_s": 74.0,
        },
        {
            "settled_in_corral_pass": False,
            "final_settle_distance_m": 0.0,
            "max_overshoot_distance_m": 0.12,
            "settle_time_s": 0.0,
            "release_recontact_count": 2,
            "mission_time_s": 0.0,
        },
        {
            "settled_in_corral_pass": True,
            "final_settle_distance_m": 0.16,
            "max_overshoot_distance_m": 0.04,
            "settle_time_s": 1.1,
            "release_recontact_count": 0,
            "mission_time_s": 68.0,
        },
    ]

    summary = summarize_surface_lane(lane=lane, runs=runs)

    assert summary["surface_profile"] == "short_turf"
    assert summary["world_file"] == "yolo_test_world_v6_clean_uat_short_turf.world"
    assert summary["runs"] == 3
    assert summary["settled_in_corral_pass_count"] == 2
    assert summary["avg_final_settle_distance_m"] == 0.19
    assert summary["avg_max_overshoot_distance_m"] == 0.08
    assert summary["avg_settle_time_s"] == 1.45
    assert summary["avg_release_recontact_count"] == 1.0
    assert summary["avg_mission_time_s"] == 71.0
    assert summary["all_runs_settled_pass"] is False


def test_compute_ordering_checks_requires_expected_lane_order():
    lane_summaries = [
        {
            "surface_profile": "baseline",
            "settled_in_corral_pass_count": 3,
            "avg_final_settle_distance_m": 0.28,
            "avg_max_overshoot_distance_m": 0.11,
            "avg_settle_time_s": 2.0,
        },
        {
            "surface_profile": "short_turf",
            "settled_in_corral_pass_count": 3,
            "avg_final_settle_distance_m": 0.18,
            "avg_max_overshoot_distance_m": 0.05,
            "avg_settle_time_s": 1.4,
        },
        {
            "surface_profile": "short_grass",
            "settled_in_corral_pass_count": 3,
            "avg_final_settle_distance_m": 0.10,
            "avg_max_overshoot_distance_m": 0.02,
            "avg_settle_time_s": 0.9,
        },
    ]

    ordering = compute_ordering_checks(lane_summaries)

    assert ordering == {
        "settle_distance_order_ok": True,
        "overshoot_order_ok": True,
        "settle_time_order_ok": True,
    }


def test_choose_canonical_surface_prefers_short_turf_then_falls_back_to_short_grass():
    lane_summaries = [
        {"surface_profile": "baseline", "all_runs_settled_pass": False},
        {"surface_profile": "short_turf", "all_runs_settled_pass": True},
        {"surface_profile": "short_grass", "all_runs_settled_pass": True},
    ]

    assert (
        choose_canonical_surface_profile(
            lane_summaries,
            {
                "settle_distance_order_ok": True,
                "overshoot_order_ok": True,
                "settle_time_order_ok": True,
            },
        )
        == "short_turf"
    )
    assert (
        choose_canonical_surface_profile(
            lane_summaries,
            {
                "settle_distance_order_ok": False,
                "overshoot_order_ok": True,
                "settle_time_order_ok": True,
            },
        )
        == "short_grass"
    )


def test_summarize_surface_calibration_and_scorecard():
    lane_summaries = [
        {
            "surface_profile": "baseline",
            "world_file": "yolo_test_world_v6_clean_uat.world",
            "runs": 3,
            "settled_in_corral_pass_count": 2,
            "avg_final_settle_distance_m": 0.24,
            "avg_max_overshoot_distance_m": 0.09,
            "avg_settle_time_s": 1.8,
            "avg_release_recontact_count": 0.7,
            "avg_mission_time_s": 72.0,
            "all_runs_settled_pass": False,
            "repeatability_summary_path": "baseline.json",
        },
        {
            "surface_profile": "short_turf",
            "world_file": "yolo_test_world_v6_clean_uat_short_turf.world",
            "runs": 3,
            "settled_in_corral_pass_count": 3,
            "avg_final_settle_distance_m": 0.15,
            "avg_max_overshoot_distance_m": 0.04,
            "avg_settle_time_s": 1.2,
            "avg_release_recontact_count": 0.3,
            "avg_mission_time_s": 66.0,
            "all_runs_settled_pass": True,
            "repeatability_summary_path": "turf.json",
        },
        {
            "surface_profile": "short_grass",
            "world_file": "yolo_test_world_v6_clean_uat_short_grass.world",
            "runs": 3,
            "settled_in_corral_pass_count": 3,
            "avg_final_settle_distance_m": 0.10,
            "avg_max_overshoot_distance_m": 0.02,
            "avg_settle_time_s": 0.8,
            "avg_release_recontact_count": 0.0,
            "avg_mission_time_s": 62.0,
            "all_runs_settled_pass": True,
            "repeatability_summary_path": "grass.json",
        },
    ]

    summary = summarize_surface_calibration(lane_summaries=lane_summaries)
    markdown = build_surface_calibration_scorecard_markdown(summary=summary, lane_results=lane_summaries)

    assert summary["canonical_surface_profile"] == "short_turf"
    assert summary["settle_distance_order_ok"] is True
    assert summary["overshoot_order_ok"] is True
    assert summary["settle_time_order_ok"] is True
    assert "Canonical surface profile: `short_turf`" in markdown
    assert "short_grass" in markdown
