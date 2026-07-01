#!/usr/bin/env python3
"""HSV color/shape detector for mono fetch sim validation.

This adapter matches the ``MonoYoloDetector.detect`` output convention while
using only the RGB image. It is intended for synthetic sim balls whose color is
more reliable than YOLO's sports-ball prior.
"""

from __future__ import annotations

import math
from typing import Any

from chasecar_mono_yolo_detect import detection_with_calibrated_size


# White (emissive) sim golf ball: low saturation, very high value. The sky is
# bright too but more saturated (S ~= 46), so the S<=40 cap excludes it.
DEFAULT_HSV_LOWER = (0, 0, 205)
DEFAULT_HSV_UPPER = (179, 40, 255)
DEFAULT_MIN_AREA_PX = 30.0


def _load_cv_dependencies() -> tuple[Any, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised by ROS-light import tests.
        raise RuntimeError("mono_color_dependency_import_failed:%s" % exc) from exc
    return cv2, np


def _as_rgb_uint8_ndarray(rgb_ndarray: Any, np: Any) -> Any:
    if rgb_ndarray is None:
        raise ValueError("rgb_ndarray_required")
    array = np.asarray(rgb_ndarray)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("expected_rgb_ndarray_hwc3_got:%s" % (list(array.shape),))
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return array


def _hsv_triplet(values: Any, *, name: str) -> tuple[int, int, int]:
    try:
        triplet = tuple(int(value) for value in values)
    except TypeError as exc:
        raise ValueError("%s_must_be_hsv_triplet" % name) from exc
    if len(triplet) != 3:
        raise ValueError("%s_must_be_hsv_triplet" % name)
    h, s, v = triplet
    if not (0 <= h <= 179 and 0 <= s <= 255 and 0 <= v <= 255):
        raise ValueError("%s_out_of_hsv_range:%s" % (name, list(triplet)))
    return h, s, v


def _build_hsv_mask(
    hsv: Any,
    lower: tuple[int, int, int],
    upper: tuple[int, int, int],
    *,
    cv2: Any,
    np: Any,
) -> Any:
    lower_array = np.array(lower, dtype=np.uint8)
    upper_array = np.array(upper, dtype=np.uint8)
    if lower[0] <= upper[0]:
        return cv2.inRange(hsv, lower_array, upper_array)
    lower_wrap = np.array([0, lower[1], lower[2]], dtype=np.uint8)
    upper_wrap = np.array([179, upper[1], upper[2]], dtype=np.uint8)
    return cv2.bitwise_or(
        cv2.inRange(hsv, lower_array, upper_wrap),
        cv2.inRange(hsv, lower_wrap, upper_array),
    )


def _blob_confidence(contour: Any, *, cv2: Any) -> float:
    area = float(cv2.contourArea(contour))
    perimeter = float(cv2.arcLength(contour, True))
    if area <= 0.0 or perimeter <= 0.0:
        return 0.0
    circularity = max(0.0, min((4.0 * math.pi * area) / (perimeter * perimeter), 1.0))
    (_x, _y), radius = cv2.minEnclosingCircle(contour)
    enclosing_area = math.pi * float(radius) * float(radius)
    fill_ratio = max(0.0, min(area / enclosing_area, 1.0)) if enclosing_area > 0.0 else 0.0
    return max(0.0, min(math.sqrt(circularity * fill_ratio), 1.0))


class MonoColorDetector:
    """Detect the sim yellow/gold ball from an RGB image via HSV contours."""

    def __init__(
        self,
        *,
        hsv_lower: tuple[int, int, int] = DEFAULT_HSV_LOWER,
        hsv_upper: tuple[int, int, int] = DEFAULT_HSV_UPPER,
        min_area_px: float = DEFAULT_MIN_AREA_PX,
        morph_kernel_size: int = 3,
    ) -> None:
        self.hsv_lower = _hsv_triplet(hsv_lower, name="hsv_lower")
        self.hsv_upper = _hsv_triplet(hsv_upper, name="hsv_upper")
        self.min_area_px = max(float(min_area_px), 0.0)
        self.morph_kernel_size = max(int(morph_kernel_size), 0)

    def detect(self, rgb_ndarray: Any) -> dict[str, Any] | None:
        """Return the largest qualifying yellow/gold blob from an RGB HWC ndarray."""
        cv2, np = _load_cv_dependencies()
        array = _as_rgb_uint8_ndarray(rgb_ndarray, np)
        height, width = int(array.shape[0]), int(array.shape[1])
        hsv = cv2.cvtColor(array, cv2.COLOR_RGB2HSV)
        mask = _build_hsv_mask(hsv, self.hsv_lower, self.hsv_upper, cv2=cv2, np=np)
        if self.morph_kernel_size > 1:
            kernel = np.ones((self.morph_kernel_size, self.morph_kernel_size), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = [
            contour
            for contour in contours
            if float(cv2.contourArea(contour)) >= self.min_area_px
        ]
        if not candidates:
            return None

        contour = max(candidates, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(contour)
        confidence = _blob_confidence(contour, cv2=cv2)
        if confidence <= 0.0:
            return None
        return detection_with_calibrated_size(
            {
                "bbox_xyxy": [float(x), float(y), float(x + w), float(y + h)],
                "confidence": round(confidence, 6),
            },
            image_width=width,
            image_height=height,
        )


__all__ = [
    "DEFAULT_HSV_LOWER",
    "DEFAULT_HSV_UPPER",
    "DEFAULT_MIN_AREA_PX",
    "MonoColorDetector",
]
