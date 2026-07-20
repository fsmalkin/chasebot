#!/usr/bin/env python3
"""Object-pose observation adapter — the ``yolo_object_pose_observation_adapter`` gate.

Turns one factory-bridge mono camera frame into the object-pose observation the
sim-stack policy consumes:

  - target class + confidence + 2D bbox           (YOLO ONNX, robust where color fails)
  - calibrated metric distance + bearing          (apparent-size law, calibrated K)
  - sigma_d uncertainty + pose_status limitation  (metric / bearing_only / unavailable)
  - freshness (frame age + stale flag)

Detection is YOLO; distance is the calibrated apparent-size law fitted by
``chasecar_bridge_mono_distance_calibration.py``. Delivery-target geometry (D3)
and the base_link frame transform (D4) are emitted as explicit pending fields
until that design lands. Observation only — the bridge stays locked.

Live:    --base-url http://192.168.1.11:8765 --calibration <summary.json>
Offline: --image <frame.jpg> --calibration <summary.json>
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import chasecar_bridge_mono_distance_calibration as calib
import chasecar_bridge_object_pose_observation as pose
import chasecar_bridge_yolo_onnx_probe as yolo_probe

DEFAULT_BASE_URL = yolo_probe.DEFAULT_BASE_URL


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def hfov_deg_from_focal(focal_px: float, image_width: int) -> float:
    if focal_px <= 0.0 or image_width <= 0:
        return 0.0
    return math.degrees(2.0 * math.atan((image_width / 2.0) / focal_px))


def build_observation(
    frame_path: Path,
    calibration_summary: Path | str,
    *,
    model: str,
    target_class: str,
    confidence_threshold: float,
    iou_threshold: float,
    input_size: int,
    size_key: str,
    artifact_dir: Path,
    image_width: int,
    frame_age_s: float | None = None,
    max_frame_age_s: float = 2.0,
) -> dict[str, Any]:
    cal = pose.load_calibration(calibration_summary, size_key=size_key)
    focal_px = cal["k_px_m"] / cal["object_size_m"] if cal["object_size_m"] > 0.0 else 0.0
    measurement = calib.measure_frame_yolo(
        Path(frame_path),
        model=model,
        target_class=target_class,
        confidence_threshold=confidence_threshold,
        iou_threshold=iou_threshold,
        input_size=input_size,
        artifact_dir=Path(artifact_dir),
    )
    stale = (frame_age_s is not None) and (float(frame_age_s) > float(max_frame_age_s))
    observation: dict[str, Any] = {
        "type": "factory_bridge_object_pose_observation",
        "generated_utc": utc_now(),
        "detector": "yolo_onnx",
        "target_class": target_class,
        "calibration": {
            "ref": str(calibration_summary),
            "k_px_m": cal["k_px_m"],
            "implied_focal_px": round(focal_px, 3),
            "object_size_m": cal["object_size_m"],
            "sigma_s_px": cal["sigma_s_px"],
            "max_reliable_range_m": cal["max_reliable_range_m"],
            "size_key": size_key,
        },
        "freshness": {
            "frame_age_s": frame_age_s,
            "max_frame_age_s": float(max_frame_age_s),
            "stale": bool(stale),
        },
        "delivery_target": {
            "status": "pending_design",
            "limitation": "D3_delivery_geometry_not_yet_defined",
        },
        "frame_note": "camera_optical_frame; base_link transform (D4) pending extrinsics",
        "detected": bool(measurement.get("detected")),
        "confidence": measurement.get("confidence"),
        "bbox": measurement.get("bbox"),
        "center_error": measurement.get("center_error"),
        "size_px": measurement.get(size_key),
    }
    if not measurement.get("detected"):
        observation["pose"] = {
            "pose_status": pose.POSE_UNAVAILABLE,
            "z_m_forward": None,
            "limitation": "target_not_detected",
        }
        observation["detection_issues"] = measurement.get("issues") or measurement.get("issue")
        return observation

    estimate = pose.estimate_object_pose(
        float(measurement.get(size_key) or 0.0),
        k_px_m=cal["k_px_m"],
        sigma_s_px=cal["sigma_s_px"],
        object_size_m=cal["object_size_m"],
        center_error=float(measurement.get("center_error") or 0.0),
        horizontal_fov_deg=hfov_deg_from_focal(focal_px, image_width),
        max_reliable_range_m=cal["max_reliable_range_m"],
    )
    if stale:
        # A stale frame cannot back a trustworthy metric range, regardless of fit.
        estimate["pose_status"] = pose.POSE_BEARING_ONLY
        estimate["stale_downgrade"] = True
    observation["pose"] = estimate
    return observation


def _fetch_live(base_url: str, timeout_s: float, artifact_dir: Path) -> tuple[Path, float | None, dict[str, Any]]:
    _, health = yolo_probe.fetch_json(base_url.rstrip("/") + "/health", timeout_s)
    camera = health.get("camera", {}) if isinstance(health, dict) else {}
    frame_age_s = camera.get("frame_age_s")
    _, frame_bytes, _, _ = yolo_probe.fetch_camera_bytes(base_url, timeout_s)
    frame_path = Path(artifact_dir) / "frame.jpg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.write_bytes(frame_bytes)
    health_brief = {
        "motion_enabled": health.get("motion_enabled"),
        "left_motor": health.get("left_motor"),
        "right_motor": health.get("right_motor"),
        "camera_backend": camera.get("backend"),
        "camera_width": camera.get("width"),
    }
    return frame_path, frame_age_s, health_brief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--calibration", required=True, help="calibration_summary.json from the distance calibration.")
    parser.add_argument("--image", default="", help="Use a saved frame instead of fetching live.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=6.0)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--model", default="runtime/yolo/yolov5m.onnx")
    parser.add_argument("--target-class", default="sports ball")
    parser.add_argument("--confidence-threshold", type=float, default=0.10)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--size-key", default="equiv_diameter_px", choices=("equiv_diameter_px", "bbox_height_px"))
    parser.add_argument("--image-width", type=int, default=320, help="Bridge camera output width (px).")
    parser.add_argument("--max-frame-age-s", type=float, default=2.0)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else (
        Path("artifacts") / "session" / ("object_pose_adapter_%s" % time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)

    frame_age_s: float | None = None
    health_brief: dict[str, Any] = {}
    if args.image:
        frame_path = Path(args.image)
    else:
        frame_path, frame_age_s, health_brief = _fetch_live(args.base_url, args.timeout_s, artifact_dir)

    observation = build_observation(
        frame_path,
        args.calibration,
        model=args.model,
        target_class=args.target_class,
        confidence_threshold=args.confidence_threshold,
        iou_threshold=args.iou_threshold,
        input_size=args.input_size,
        size_key=args.size_key,
        artifact_dir=artifact_dir / "yolo",
        image_width=args.image_width,
        frame_age_s=frame_age_s,
        max_frame_age_s=args.max_frame_age_s,
    )
    observation["source"] = {"image": str(frame_path), "live_health": health_brief}
    out_path = artifact_dir / "object_pose_observation.json"
    out_path.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(observation, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if observation.get("detected") else 1


if __name__ == "__main__":
    raise SystemExit(main())
