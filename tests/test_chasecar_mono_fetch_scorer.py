from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import chasecar_mono_fetch_scorer as scorer  # noqa: E402


def test_score_samples_reports_contact_and_approach_metrics_with_slant_error():
    truth_samples = [
        {
            "sample_index": 0,
            "sim_time_s": 10.0,
            "wall_time_unix_s": 100.0,
            "relative_truth": {
                "distance_xy_m": 1.0,
                "forward_m": 0.8,
                "bearing_rad_right_positive": 0.10,
            },
        },
        {
            "sample_index": 1,
            "sim_time_s": 10.5,
            "wall_time_unix_s": 100.5,
            "relative_truth": {
                "distance_xy_m": 0.13,
                "forward_m": 0.13,
                "bearing_rad_right_positive": 0.01,
            },
        },
    ]
    node_rows = [
        {
            "tick": 1,
            "sim_time_s": 10.0,
            "wall_time_unix_s": 100.0,
            "observation": {"center_error": 0.04},
            "mono_pose": {
                "z_m_forward": 1.1,
                "bearing_rad_right_positive": 0.12,
                "pose_status": "metric",
                "max_reliable_range_m": 2.0,
            },
            "action": {"action": "forward", "reason": "approach"},
        },
        {
            "tick": 2,
            "sim_time_s": 10.5,
            "wall_time_unix_s": 100.5,
            "observation": {"center_error": 0.02},
            "mono_pose": {
                "z_m_forward": 0.4,
                "bearing_rad_right_positive": 0.02,
                "pose_status": "metric",
                "max_reliable_range_m": 2.0,
            },
            "action": {"action": "stop", "reason": "standoff_reached"},
        },
    ]

    verdict = scorer.score_samples(
        truth_samples,
        node_rows,
        contact_threshold_m=0.14,
        min_truth_coverage_ratio=0.75,
    )

    assert verdict["contact"] is True
    assert verdict["pass"] is True
    assert verdict["approach"]["reached_standoff"] is True
    assert verdict["approach"]["true_distance_at_stop_m"] == 0.13
    assert verdict["samples"][0]["mono_distance_error_m"] == 0.1
    assert verdict["samples"][0]["true_forward_m"] == 0.8
    assert verdict["summary"]["compared_count"] == 2
    assert verdict["summary"]["mono_distance_error_m"]["count"] == 2
    assert verdict["summary"]["bearing_error_rad"]["max_abs"] == 0.02
    assert verdict["summary"]["pose_status_correct_fraction"] == 1.0


def test_score_samples_marks_contact_metric_inconclusive_when_truth_coverage_is_low():
    verdict = scorer.score_samples(
        [{"sample_index": 0, "sim_time_s": 1.0, "relative_truth": None}],
        [],
        contact_threshold_m=0.14,
        min_truth_coverage_ratio=0.75,
    )

    assert verdict["contact_metric_conclusive"] is False
    assert verdict["contact"] is None
    assert verdict["pass"] is False
    assert verdict["truth_coverage"]["samples_with_robot_and_ball"] == 0
