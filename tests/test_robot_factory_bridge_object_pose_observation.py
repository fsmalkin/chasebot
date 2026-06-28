from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_object_pose_observation as pose  # noqa: E402


def test_metric_estimate_centered():
    out = pose.estimate_object_pose(
        24.0,
        k_px_m=12.0,
        sigma_s_px=0.5,
        object_size_m=0.0427,
        center_error=0.0,
        horizontal_fov_deg=62.2,
    )

    assert out["pose_status"] == pose.POSE_METRIC
    assert out["z_m_forward"] == 0.5  # 12 / 24
    assert out["x_m_right"] == 0.0
    assert out["bearing_rad_right_positive"] == 0.0
    # sigma_d = (z^2 / K) * sigma_s = (0.25/12)*0.5
    assert abs(out["sigma_d_m"] - (0.25 / 12.0) * 0.5) < 1e-6


def test_bearing_sign_follows_center_error():
    right = pose.estimate_object_pose(
        24.0, k_px_m=12.0, sigma_s_px=0.0, object_size_m=0.0427,
        center_error=0.5, horizontal_fov_deg=62.2,
    )
    left = pose.estimate_object_pose(
        24.0, k_px_m=12.0, sigma_s_px=0.0, object_size_m=0.0427,
        center_error=-0.5, horizontal_fov_deg=62.2,
    )

    assert right["bearing_rad_right_positive"] > 0.0
    assert right["x_m_right"] > 0.0
    assert left["bearing_rad_right_positive"] < 0.0
    assert left["x_m_right"] < 0.0


def test_unavailable_when_no_size():
    out = pose.estimate_object_pose(
        0.0, k_px_m=12.0, sigma_s_px=0.5, object_size_m=0.0427,
        center_error=0.0, horizontal_fov_deg=62.2,
    )

    assert out["pose_status"] == pose.POSE_UNAVAILABLE
    assert out["z_m_forward"] is None
    assert out["sigma_d_m"] is None


def test_bearing_only_beyond_calibrated_range():
    out = pose.estimate_object_pose(
        10.0, k_px_m=12.0, sigma_s_px=0.5, object_size_m=0.0427,
        center_error=0.0, horizontal_fov_deg=62.2, max_reliable_range_m=0.8,
    )

    assert out["z_m_forward"] == 1.2  # 12 / 10 > 0.8
    assert out["pose_status"] == pose.POSE_BEARING_ONLY
    assert out["range_exceeded"] is True


def test_bearing_only_when_sigma_exceeds_budget():
    out = pose.estimate_object_pose(
        24.0, k_px_m=12.0, sigma_s_px=0.5, object_size_m=0.0427,
        center_error=0.0, horizontal_fov_deg=62.2, sigma_d_max_m=0.005,
    )

    # sigma_d ~= 0.0104 > 0.005 budget
    assert out["pose_status"] == pose.POSE_BEARING_ONLY
    assert out["sigma_exceeded"] is True


def test_load_calibration_roundtrip(tmp_path):
    summary = {
        "object_size_m": 0.0427,
        "fits": {
            "equiv_diameter_px": {
                "pass": True,
                "K_px_m": 11.95,
                "sigma_s_px": 0.42,
                "max_calibrated_range_m": 1.0,
                "object_size_m": 0.0427,
            }
        },
    }
    path = tmp_path / "calibration_summary.json"
    path.write_text(json.dumps(summary), encoding="utf-8")

    loaded = pose.load_calibration(path)

    assert loaded["k_px_m"] == 11.95
    assert loaded["sigma_s_px"] == 0.42
    assert loaded["max_reliable_range_m"] == 1.0
    assert loaded["size_key"] == "equiv_diameter_px"


def test_load_calibration_rejects_failed_fit(tmp_path):
    summary = {"fits": {"equiv_diameter_px": {"pass": False, "issues": ["need_at_least_two_detected_samples"]}}}
    path = tmp_path / "calibration_summary.json"
    path.write_text(json.dumps(summary), encoding="utf-8")

    try:
        pose.load_calibration(path)
        raised = False
    except ValueError:
        raised = True
    assert raised
