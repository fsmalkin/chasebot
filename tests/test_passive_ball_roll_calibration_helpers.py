import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from passive_ball_roll_calibration_helpers import GOLF_BALL_MASS_MAX_KG  # noqa: E402
from passive_ball_roll_calibration_helpers import GOLF_BALL_RADIUS_MIN_M  # noqa: E402
from passive_ball_roll_calibration_helpers import GOLF_SHORT_TURF_ROLL_BAND  # noqa: E402
from passive_ball_roll_calibration_helpers import classify_roll_result  # noqa: E402
from passive_ball_roll_calibration_helpers import deceleration_from_stop  # noqa: E402
from passive_ball_roll_calibration_helpers import parse_ball_sdf_profile  # noqa: E402
from passive_ball_roll_calibration_helpers import ramp_exit_speed_mps  # noqa: E402
from passive_ball_roll_calibration_helpers import solid_sphere_inertia_kg_m2  # noqa: E402
from passive_ball_roll_calibration_helpers import summarize_campaign  # noqa: E402
from passive_ball_roll_calibration_helpers import summarize_roll_samples  # noqa: E402


def test_golf_ball_profile_matches_official_size_and_solid_sphere_inertia():
    profile = parse_ball_sdf_profile(REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf")

    assert profile.mass_kg == pytest.approx(GOLF_BALL_MASS_MAX_KG)
    assert profile.radius_m == pytest.approx(GOLF_BALL_RADIUS_MIN_M)
    assert profile.inertia_kg_m2 == pytest.approx(
        solid_sphere_inertia_kg_m2(mass_kg=profile.mass_kg, radius_m=profile.radius_m),
        rel=8e-4,
    )


def test_reference_math_matches_stimpmeter_style_roll_equations():
    assert ramp_exit_speed_mps(vertical_drop_m=0.10) == pytest.approx(math.sqrt(2 * 9.80665 * 0.10 / 1.4))
    assert deceleration_from_stop(1.0, 0.90) == pytest.approx(GOLF_SHORT_TURF_ROLL_BAND.effective_decel_min_mps2)
    assert deceleration_from_stop(1.0, 0.45) == pytest.approx(GOLF_SHORT_TURF_ROLL_BAND.effective_decel_max_mps2)


def test_roll_sample_metrics_compute_distance_speed_and_stop_time():
    samples = [
        {"t_s": 0.0, "position": {"x": 0.0, "y": 0.0}},
        {"t_s": 0.5, "position": {"x": 0.50, "y": 0.0}},
        {"t_s": 1.0, "position": {"x": 0.75, "y": 0.0}},
        {"t_s": 1.5, "position": {"x": 0.75, "y": 0.0}},
        {"t_s": 2.1, "position": {"x": 0.75, "y": 0.0}},
    ]

    metrics = summarize_roll_samples(samples, ground_start_x_m=0.0, stop_speed_threshold_mps=0.03, rest_dwell_s=0.5)

    assert metrics["observed"] is True
    assert metrics["stopped"] is True
    assert metrics["peak_speed_mps"] == pytest.approx(1.0)
    assert metrics["roll_distance_m"] == pytest.approx(0.25)
    assert metrics["stop_time_s"] == pytest.approx(1.6)


def test_roll_sample_metrics_can_start_at_first_motion_for_direct_launch():
    samples = [
        {"t_s": 0.0, "position": {"x": 0.0, "y": 0.0}},
        {"t_s": 0.5, "position": {"x": 0.0, "y": 0.0}},
        {"t_s": 0.6, "position": {"x": 0.10, "y": 0.0}},
        {"t_s": 1.1, "position": {"x": 0.40, "y": 0.0}},
        {"t_s": 1.6, "position": {"x": 0.40, "y": 0.0}},
        {"t_s": 2.2, "position": {"x": 0.40, "y": 0.0}},
    ]

    metrics = summarize_roll_samples(
        samples,
        ground_start_x_m=0.0,
        stop_speed_threshold_mps=0.03,
        rest_dwell_s=0.5,
        start_selection="first_motion",
        motion_start_speed_threshold_mps=0.05,
    )

    assert metrics["start_pose"]["x"] == pytest.approx(0.0)
    assert metrics["start_pose"]["t_s"] == pytest.approx(0.5)
    assert metrics["roll_distance_m"] == pytest.approx(0.40)
    assert metrics["peak_speed_mps"] == pytest.approx(1.0)
    assert metrics["stopped"] is True


def test_roll_classification_flags_under_over_and_in_band():
    base = {
        "observed": True,
        "stopped": True,
        "peak_speed_mps": 1.0,
        "lateral_drift_ratio": 0.0,
    }

    assert classify_roll_result({**base, "roll_distance_m": 0.44}, reference_band=GOLF_SHORT_TURF_ROLL_BAND)["reason"] == "under_roll"
    assert classify_roll_result({**base, "roll_distance_m": 0.60}, reference_band=GOLF_SHORT_TURF_ROLL_BAND)["pass"] is True
    assert classify_roll_result({**base, "roll_distance_m": 0.91}, reference_band=GOLF_SHORT_TURF_ROLL_BAND)["reason"] == "over_roll"


def test_roll_classification_can_use_requested_direct_launch_speed():
    result = classify_roll_result(
        {
            "observed": True,
            "stopped": True,
            "peak_speed_mps": 1.7,
            "reference_initial_speed_mps": 1.0,
            "lateral_drift_ratio": 0.0,
            "roll_distance_m": 0.60,
        },
        reference_band=GOLF_SHORT_TURF_ROLL_BAND,
    )

    assert result["pass"] is True
    assert result["classification_speed_mps"] == pytest.approx(1.0)


def test_campaign_summary_preserves_surface_ball_and_reference_profiles():
    profile = parse_ball_sdf_profile(REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf")
    summary = summarize_campaign(
        campaign_id="unit",
        surface_profile="calibrated_golf_turf",
        world_file="yolo_test_world_v6_calibrated_golf_turf.world",
        ball_profile=profile,
        reference_band=GOLF_SHORT_TURF_ROLL_BAND,
        run_results=[
            {"pass": True, "observed": True, "peak_speed_mps": 1.0, "roll_distance_m": 0.6, "stop_time_s": 1.2, "effective_decel_mps2": 0.8},
            {"pass": False, "observed": True, "peak_speed_mps": 1.0, "roll_distance_m": 1.1, "stop_time_s": 2.0, "effective_decel_mps2": 0.45},
        ],
    )

    assert summary["surface_profile"] == "calibrated_golf_turf"
    assert summary["ball_profile"]["name"] == "calibrated_golf_ball"
    assert summary["reference_band"]["surface_profile"] == "calibrated_golf_turf"
    assert summary["pass_count"] == 1
    assert summary["fail_count"] == 1
    assert summary["pass"] is False
