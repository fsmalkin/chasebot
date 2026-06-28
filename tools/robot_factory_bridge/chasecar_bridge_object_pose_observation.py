#!/usr/bin/env python3
"""Object-pose observation core for the factory-bridge mono camera.

Runtime estimator for the ``yolo_object_pose_observation_adapter`` gate. It
converts a detected target's apparent pixel size into a metric forward distance
plus bearing using the calibrated apparent-size law fitted by
``chasecar_bridge_mono_distance_calibration.py``:

    z       = K / size_px
    sigma_d = (z**2 / K) * sigma_s_px          # monocular z**2 error growth
    bearing = atan(center_error * tan(hfov/2))
    x_right = z * tan(bearing)

Every estimate carries an explicit ``pose_status`` limitation field
(``metric`` / ``bearing_only`` / ``unavailable``) so the policy never treats an
out-of-calibrated-range or high-variance monocular range as trustworthy. This is
the safety-critical honesty boundary for any downstream fetch-to-pose claim.

This module is pure estimation (no bridge I/O); the full observation adapter
wraps it with detection + freshness once a live calibration ``K`` exists.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

POSE_METRIC = "metric"
POSE_BEARING_ONLY = "bearing_only"
POSE_UNAVAILABLE = "unavailable"


def estimate_object_pose(
    size_px: float,
    *,
    k_px_m: float,
    sigma_s_px: float,
    object_size_m: float,
    center_error: float,
    horizontal_fov_deg: float,
    max_reliable_range_m: float | None = None,
    sigma_d_max_m: float | None = None,
) -> dict[str, Any]:
    """Estimate metric pose from one detection's apparent pixel size.

    ``size_px`` is the calibrated size metric (e.g. equivalent-diameter px).
    ``center_error`` is the normalized horizontal offset in [-1, 1]
    ((cx - w/2) / (w/2)); positive is right of center.
    """
    bearing_rad = math.atan(
        float(center_error) * math.tan(math.radians(float(horizontal_fov_deg)) / 2.0)
    )
    base: dict[str, Any] = {
        "frame": "factory_bridge_camera_optical_estimated",
        "method": "monocular_calibrated_apparent_size",
        "bearing_rad_right_positive": round(bearing_rad, 6),
        "center_error": round(float(center_error), 6),
        "size_px": round(float(size_px), 3),
        "k_px_m": float(k_px_m),
        "object_size_m": float(object_size_m),
    }
    if float(size_px) <= 0.0 or float(k_px_m) <= 0.0:
        base.update(
            {
                "pose_status": POSE_UNAVAILABLE,
                "z_m_forward": None,
                "x_m_right": None,
                "sigma_d_m": None,
                "limitation": "no_target_size_or_uncalibrated",
            }
        )
        return base

    z_m = float(k_px_m) / float(size_px)
    sigma_d_m = (z_m * z_m / float(k_px_m)) * float(sigma_s_px)
    x_m_right = z_m * math.tan(bearing_rad)
    range_exceeded = max_reliable_range_m is not None and z_m > float(max_reliable_range_m)
    sigma_exceeded = sigma_d_max_m is not None and sigma_d_m > float(sigma_d_max_m)
    status = POSE_BEARING_ONLY if (range_exceeded or sigma_exceeded) else POSE_METRIC
    base.update(
        {
            "pose_status": status,
            "z_m_forward": round(z_m, 6),
            "x_m_right": round(x_m_right, 6),
            "sigma_d_m": round(sigma_d_m, 6),
            "range_exceeded": bool(range_exceeded),
            "sigma_exceeded": bool(sigma_exceeded),
            "max_reliable_range_m": float(max_reliable_range_m)
            if max_reliable_range_m is not None
            else None,
        }
    )
    return base


def load_calibration(summary_path: Path | str, *, size_key: str = "equiv_diameter_px") -> dict[str, Any]:
    """Load a passed calibration fit from a calibration_summary.json."""
    data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    fit = (data.get("fits") or {}).get(size_key) or {}
    if not fit.get("pass"):
        raise ValueError("calibration_fit_not_passed:%s" % size_key)
    max_range = fit.get("max_calibrated_range_m")
    return {
        "k_px_m": float(fit["K_px_m"]),
        "sigma_s_px": float(fit["sigma_s_px"]),
        "object_size_m": float(fit.get("object_size_m", data.get("object_size_m", 0.0))),
        "max_reliable_range_m": float(max_range) if max_range is not None else None,
        "size_key": size_key,
    }
