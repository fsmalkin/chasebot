from __future__ import annotations

import sys
from pathlib import Path

import pytest


cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


REPO_ROOT = Path(__file__).resolve().parents[1]
ROS2_SCRIPTS_DIR = REPO_ROOT / "ros2_scripts"
if str(ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ROS2_SCRIPTS_DIR))

import chasecar_mono_color_detect as mono_color  # noqa: E402


def _scene(*, center_x: int = 320, center_y: int = 240, radius: int = 40) -> np.ndarray:
    image = np.full((480, 640, 3), (50, 160, 70), dtype=np.uint8)
    cv2.circle(image, (center_x, center_y), radius, (242, 255, 46), -1)
    return image


def test_detects_centered_yellow_ball_with_calibrated_measurements():
    detector = mono_color.MonoColorDetector(min_area_px=100.0)

    detection = detector.detect(_scene())

    assert detection is not None
    assert abs(detection["equiv_diameter_px"] - 80.0) <= 2.0
    assert abs(detection["center_error"]) <= 0.005
    assert detection["confidence"] >= 0.85
    assert detection["image_width"] == 640
    assert detection["image_height"] == 480


def test_center_error_sign_matches_yolo_convention_for_offset_ball():
    detector = mono_color.MonoColorDetector(min_area_px=100.0)

    right_detection = detector.detect(_scene(center_x=400))
    left_detection = detector.detect(_scene(center_x=240))

    assert right_detection is not None
    assert left_detection is not None
    assert right_detection["center_error"] > 0.0
    assert left_detection["center_error"] < 0.0
