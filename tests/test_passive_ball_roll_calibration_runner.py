import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from passive_ball_roll_calibration_runner import direct_velocity_components  # noqa: E402
from passive_ball_roll_calibration_runner import write_direct_velocity_ball_sdf  # noqa: E402


def test_direct_velocity_components_seed_rolling_without_slip():
    request = direct_velocity_components(
        initial_speed_mps=1.0,
        heading_deg=0.0,
        ball_radius_m=0.021336,
    )

    assert request["linear_velocity_mps"] == {"x": 1.0, "y": 0.0, "z": 0.0}
    assert request["angular_velocity_radps"]["x"] == pytest.approx(0.0)
    assert request["angular_velocity_radps"]["y"] == pytest.approx(1.0 / 0.021336)
    assert request["angular_velocity_radps"]["z"] == pytest.approx(0.0)


def test_direct_velocity_components_can_disable_spin_seed():
    request = direct_velocity_components(
        initial_speed_mps=1.0,
        heading_deg=45.0,
        ball_radius_m=0.021336,
        rolling_angular_velocity=False,
    )

    assert request["linear_velocity_mps"]["x"] == pytest.approx(0.707106781)
    assert request["linear_velocity_mps"]["y"] == pytest.approx(0.707106781)
    assert request["angular_velocity_radps"] == {"x": 0.0, "y": 0.0, "z": 0.0}


def test_write_direct_velocity_ball_sdf_injects_one_shot_plugin(tmp_path):
    output_sdf = tmp_path / "direct_velocity_ball.sdf"
    velocity_request = direct_velocity_components(
        initial_speed_mps=1.0,
        heading_deg=0.0,
        ball_radius_m=0.021336,
    )

    write_direct_velocity_ball_sdf(
        base_ball_sdf=REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf",
        output_sdf=output_sdf,
        plugin_library_container_path="/workspaces/chasecar/artifacts/plugin/libinitial.so",
        link_name="link",
        velocity_request=velocity_request,
        delay_s=2.0,
        rolling_resistance_decel_mps2=0.72,
        rolling_resistance_mass_kg=0.04593,
        rolling_resistance_ball_radius_m=0.021336,
        rolling_resistance_stop_speed_threshold_mps=0.03,
    )

    text = output_sdf.read_text(encoding="utf-8")
    assert 'filename="/workspaces/chasecar/artifacts/plugin/libinitial.so"' in text
    assert 'name="chasecar::InitialLinkVelocity"' in text
    assert "<link_name>link</link_name>" in text
    assert "<delay_s>2.000000</delay_s>" in text
    assert "<linear_velocity>1.000000000 0.000000000 0.000000000</linear_velocity>" in text
    assert "<angular_velocity>0.000000000 46.869141357 0.000000000</angular_velocity>" in text
    assert "<rolling_resistance_ball_radius_m>0.021336000</rolling_resistance_ball_radius_m>" in text
    assert "<rolling_resistance_decel_mps2>0.720000000</rolling_resistance_decel_mps2>" in text
