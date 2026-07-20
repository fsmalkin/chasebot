from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_object_pose_adapter as adapter  # noqa: E402


def _write_calibration(tmp_path, *, k=9.62, sigma=1.7, obj=0.0427, max_range=0.914):
    summary = {
        "object_size_m": obj,
        "fits": {
            "equiv_diameter_px": {
                "pass": True,
                "K_px_m": k,
                "sigma_s_px": sigma,
                "max_calibrated_range_m": max_range,
                "object_size_m": obj,
            }
        },
    }
    path = tmp_path / "calibration_summary.json"
    path.write_text(json.dumps(summary), encoding="utf-8")
    return path


def _common(**over):
    base = dict(
        model="m",
        target_class="sports ball",
        confidence_threshold=0.1,
        iou_threshold=0.45,
        input_size=640,
        size_key="equiv_diameter_px",
        image_width=320,
    )
    base.update(over)
    return base


def test_hfov_deg_from_focal():
    # f=225 px over a 320 px frame -> ~71 deg
    h = adapter.hfov_deg_from_focal(225.0, 320)
    assert 68.0 < h < 74.0
    assert adapter.hfov_deg_from_focal(0.0, 320) == 0.0


def test_build_observation_metric(tmp_path, monkeypatch):
    cal = _write_calibration(tmp_path)
    monkeypatch.setattr(
        adapter.calib,
        "measure_frame_yolo",
        lambda *a, **k: {
            "detected": True,
            "detector": "yolo",
            "class_name": "sports ball",
            "confidence": 0.67,
            "bbox": {"x0": 154, "y0": 139, "x1": 172, "y1": 154},
            "equiv_diameter_px": 32.0,
            "bbox_height_px": 33.0,
            "center_error": 0.0,
        },
    )
    obs = adapter.build_observation(
        Path("x.jpg"), cal, artifact_dir=tmp_path / "y", **_common()
    )

    assert obs["detected"] is True
    assert obs["pose"]["pose_status"] == adapter.pose.POSE_METRIC
    assert abs(obs["pose"]["z_m_forward"] - 9.62 / 32.0) < 1e-3
    assert obs["delivery_target"]["status"] == "pending_design"
    assert obs["freshness"]["stale"] is False


def test_build_observation_unavailable(tmp_path, monkeypatch):
    cal = _write_calibration(tmp_path)
    monkeypatch.setattr(
        adapter.calib,
        "measure_frame_yolo",
        lambda *a, **k: {"detected": False, "issues": ["target_not_detected"]},
    )
    obs = adapter.build_observation(
        Path("x.jpg"), cal, artifact_dir=tmp_path / "y", **_common()
    )

    assert obs["detected"] is False
    assert obs["pose"]["pose_status"] == adapter.pose.POSE_UNAVAILABLE


def test_build_observation_stale_downgrades_to_bearing_only(tmp_path, monkeypatch):
    cal = _write_calibration(tmp_path)
    monkeypatch.setattr(
        adapter.calib,
        "measure_frame_yolo",
        lambda *a, **k: {
            "detected": True,
            "class_name": "sports ball",
            "confidence": 0.7,
            "bbox": {},
            "equiv_diameter_px": 32.0,
            "center_error": 0.0,
        },
    )
    obs = adapter.build_observation(
        Path("x.jpg"), cal, artifact_dir=tmp_path / "y",
        frame_age_s=5.0, max_frame_age_s=2.0, **_common()
    )

    assert obs["freshness"]["stale"] is True
    assert obs["pose"]["pose_status"] == adapter.pose.POSE_BEARING_ONLY
    assert obs["pose"].get("stale_downgrade") is True
