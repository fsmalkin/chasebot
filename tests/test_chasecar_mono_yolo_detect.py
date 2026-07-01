from __future__ import annotations

import math
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROS2_SCRIPTS_DIR = REPO_ROOT / "ros2_scripts"
if str(ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ROS2_SCRIPTS_DIR))

import chasecar_mono_yolo_detect as mono_yolo  # noqa: E402


def test_detection_measurement_matches_calibration_convention():
    detection = {
        "class_id": mono_yolo.SPORTS_BALL_CLASS_ID,
        "class_name": "sports ball",
        "confidence": 0.91,
        "bbox_xyxy": [288.0, 100.0, 368.0, 140.0],
    }

    measured = mono_yolo.detection_with_calibrated_size(
        detection,
        image_width=640,
        image_height=480,
    )

    assert measured["bbox_width_px"] == 80.0
    assert measured["bbox_height_px"] == 40.0
    assert measured["equiv_diameter_px"] == round(math.sqrt(80.0 * 40.0), 3)
    assert measured["center_error"] == round(((328.0 - 320.0) / 320.0), 6)
    assert measured["area_ratio"] == round((80.0 * 40.0) / (640.0 * 480.0), 6)


def test_best_detection_selection_prefers_confidence_then_area():
    detections = [
        {"confidence": 0.40, "area_ratio": 0.10, "bbox_xyxy": [0, 0, 10, 10]},
        {"confidence": 0.80, "area_ratio": 0.01, "bbox_xyxy": [0, 0, 8, 8]},
        {"confidence": 0.80, "area_ratio": 0.03, "bbox_xyxy": [0, 0, 12, 12]},
    ]

    best = mono_yolo.select_best_detection(detections, min_area_ratio=0.0)

    assert best is detections[2]
