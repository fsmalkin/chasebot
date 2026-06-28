from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_monocular_pose_probe as probe  # noqa: E402


def test_estimate_pose_from_bbox_uses_known_height_and_intrinsics():
    detection = {
        "bbox_xyxy": [140.0, 60.0, 180.0, 160.0],
        "center_x_px": 160.0,
        "center_y_px": 110.0,
    }

    pose = probe.estimate_pose_from_bbox(
        detection,
        image_width=320,
        image_height=240,
        object_height_m=0.20,
        fx_px=260.0,
        fy_px=260.0,
        cx_px=160.0,
        cy_px=120.0,
    )

    assert pose["z_m_forward"] == 0.52
    assert pose["x_m_right"] == 0.0
    assert pose["y_m_down"] < 0.0
    assert pose["method"] == "monocular_known_object_height_pinhole"


def test_focal_from_fov_returns_centered_intrinsics():
    intrinsics = probe.focal_from_fov(320, 240, 60.0, 45.0)

    assert intrinsics["fx_px"] > 0.0
    assert intrinsics["fy_px"] > 0.0
    assert intrinsics["cx_px"] == 160.0
    assert intrinsics["cy_px"] == 120.0
    assert intrinsics["source"] == "field_of_view"

