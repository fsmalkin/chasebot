#!/usr/bin/env python3
"""Persistent YOLOv5 ONNX detector for mono fetch.

This adapter keeps the probe's decode and measurement conventions intact while
removing the calibration probe's disk/subprocess loop:

* letterbox/decode/NMS/best-detection selection come from the committed probe
* ``equiv_diameter_px`` is ``sqrt(bbox_w * bbox_h)``
* ``center_error`` is ``(bbox_cx - W/2) / (W/2)``
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_yolo_onnx_probe as yolo_probe  # noqa: E402


DEFAULT_MODEL_PATH = REPO_ROOT / "runtime" / "yolo" / "yolov5m.onnx"
DEFAULT_TARGET_CLASS = "sports ball"
SPORTS_BALL_CLASS_ID = 32

# Export the lifted probe helpers for tests and callers that need identical
# preprocessing/decode behavior without importing the factory-bridge probe.
decode_yolov5_output = yolo_probe.decode_yolov5_output
nms = yolo_probe.nms
select_best_detection = yolo_probe.select_best_detection


def _load_detector_dependencies(*, require_onnx: bool) -> None:
    error = yolo_probe.load_detector_dependencies(require_onnx=require_onnx)
    if error:
        raise RuntimeError("mono_yolo_dependency_import_failed:%s" % error)


def _as_rgb_uint8_ndarray(rgb_ndarray: Any) -> Any:
    _load_detector_dependencies(require_onnx=False)
    np = yolo_probe.np
    if rgb_ndarray is None:
        raise ValueError("rgb_ndarray_required")
    array = np.asarray(rgb_ndarray)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("expected_rgb_ndarray_hwc3_got:%s" % (list(array.shape),))
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return array


def rgb_ndarray_to_pil(rgb_ndarray: Any) -> Any:
    """Convert an RGB ndarray into the exact PIL input expected by the probe."""
    _load_detector_dependencies(require_onnx=False)
    array = _as_rgb_uint8_ndarray(rgb_ndarray)
    return yolo_probe.Image.fromarray(array, mode="RGB")


def letterbox(rgb_ndarray: Any, size: int, *, dtype: Any = None) -> tuple[Any, float, tuple[int, int]]:
    """Probe-compatible letterbox that accepts an RGB ndarray."""
    image = rgb_ndarray_to_pil(rgb_ndarray)
    return yolo_probe.letterbox(image, int(size), dtype=dtype)


def detection_with_calibrated_size(
    detection: dict[str, Any],
    *,
    image_width: int,
    image_height: int,
) -> dict[str, Any]:
    """Add calibration-coupled size fields to one YOLO detection.

    The math mirrors ``measure_frame_yolo`` in
    ``chasecar_bridge_mono_distance_calibration.py``.
    """
    bbox = detection.get("bbox_xyxy") or []
    if len(bbox) != 4:
        raise ValueError("bbox_xyxy_required")
    x0, y0, x1, y1 = [float(value) for value in bbox]
    bbox_width_px = max(0.0, x1 - x0)
    bbox_height_px = max(0.0, y1 - y0)
    bbox_cx = (x0 + x1) / 2.0
    equiv_diameter_px = (
        math.sqrt(bbox_width_px * bbox_height_px)
        if bbox_width_px > 0.0 and bbox_height_px > 0.0
        else 0.0
    )
    width = max(float(image_width), 1.0)
    height = max(float(image_height), 1.0)
    enriched = dict(detection)
    enriched.update(
        {
            "bbox_xyxy": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
            "bbox_width_px": round(bbox_width_px, 3),
            "bbox_height_px": round(bbox_height_px, 3),
            "equiv_diameter_px": round(equiv_diameter_px, 3),
            "center_x_px": round(bbox_cx, 3),
            "center_y_px": round((y0 + y1) / 2.0, 3),
            "center_error": round((bbox_cx - (width / 2.0)) / (width / 2.0), 6),
            "area_ratio": round((bbox_width_px * bbox_height_px) / (width * height), 6),
            "image_width": int(image_width),
            "image_height": int(image_height),
        }
    )
    return enriched


class MonoYoloDetector:
    """Reusable mono YOLOv5 detector with a persistent ONNX Runtime session."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        *,
        target_class: str = DEFAULT_TARGET_CLASS,
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        input_size: int = 640,
        min_area_ratio: float = 0.0,
        providers: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        _load_detector_dependencies(require_onnx=True)
        self.model_path = Path(model_path)
        self.target_class = str(target_class)
        self.confidence_threshold = float(confidence_threshold)
        self.iou_threshold = float(iou_threshold)
        self.input_size = int(input_size)
        self.min_area_ratio = float(min_area_ratio)
        if not self.model_path.is_file():
            raise FileNotFoundError(str(self.model_path))
        self._session = yolo_probe.ort.InferenceSession(
            str(self.model_path),
            providers=list(providers or ["CPUExecutionProvider"]),
        )
        model_input = self._session.get_inputs()[0]
        self.input_name = model_input.name
        input_type = str(model_input.type).lower()
        self.input_dtype = (
            yolo_probe.np.float16 if "float16" in input_type else yolo_probe.np.float32
        )
        self.model_input = {
            "name": model_input.name,
            "type": str(model_input.type),
            "shape": list(model_input.shape),
        }

    def detect(self, rgb_ndarray: Any) -> dict[str, Any] | None:
        """Return the best target detection from an RGB HWC ndarray."""
        array = _as_rgb_uint8_ndarray(rgb_ndarray)
        height, width = int(array.shape[0]), int(array.shape[1])
        input_tensor, scale, pad = letterbox(array, self.input_size, dtype=self.input_dtype)
        outputs = self._session.run(None, {self.input_name: input_tensor})
        detections = decode_yolov5_output(
            outputs[0],
            width=width,
            height=height,
            scale=scale,
            pad=pad,
            confidence_threshold=self.confidence_threshold,
            class_names={self.target_class},
            iou_threshold=self.iou_threshold,
        )
        best = select_best_detection(detections, min_area_ratio=self.min_area_ratio)
        if not best:
            return None
        return detection_with_calibrated_size(best, image_width=width, image_height=height)


__all__ = [
    "DEFAULT_MODEL_PATH",
    "DEFAULT_TARGET_CLASS",
    "SPORTS_BALL_CLASS_ID",
    "MonoYoloDetector",
    "decode_yolov5_output",
    "detection_with_calibrated_size",
    "letterbox",
    "nms",
    "rgb_ndarray_to_pil",
    "select_best_detection",
]
