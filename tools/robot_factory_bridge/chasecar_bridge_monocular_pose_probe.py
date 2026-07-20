#!/usr/bin/env python3
"""Probe factory-bridge YOLO detections for metric object-pose readiness."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import chasecar_bridge_yolo_onnx_probe as yolo_probe


DEFAULT_ARTIFACT_STEM = "factory_bridge_monocular_pose_probe"


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_dir(path: Path | str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_artifact_dir() -> Path:
    return Path("artifacts") / "session" / ("%s_%s" % (DEFAULT_ARTIFACT_STEM, utc_stamp()))


def focal_from_fov(width_px: float, height_px: float, horizontal_fov_deg: float, vertical_fov_deg: float) -> dict[str, float]:
    if horizontal_fov_deg <= 0.0 or horizontal_fov_deg >= 179.0:
        raise ValueError("horizontal_fov_deg_out_of_range")
    if vertical_fov_deg <= 0.0 or vertical_fov_deg >= 179.0:
        raise ValueError("vertical_fov_deg_out_of_range")
    fx = (width_px / 2.0) / math.tan(math.radians(horizontal_fov_deg) / 2.0)
    fy = (height_px / 2.0) / math.tan(math.radians(vertical_fov_deg) / 2.0)
    return {
        "fx_px": fx,
        "fy_px": fy,
        "cx_px": width_px / 2.0,
        "cy_px": height_px / 2.0,
        "source": "field_of_view",
    }


def estimate_pose_from_bbox(
    detection: dict[str, Any],
    *,
    image_width: int,
    image_height: int,
    object_height_m: float,
    fx_px: float,
    fy_px: float,
    cx_px: float,
    cy_px: float,
) -> dict[str, Any]:
    bbox = detection.get("bbox_xyxy") if isinstance(detection.get("bbox_xyxy"), list) else []
    if len(bbox) != 4:
        raise ValueError("bbox_xyxy_required")
    x0, y0, x1, y1 = [float(value) for value in bbox]
    bbox_height_px = max(0.0, y1 - y0)
    bbox_width_px = max(0.0, x1 - x0)
    if bbox_height_px <= 1.0:
        raise ValueError("bbox_height_too_small")
    if object_height_m <= 0.0:
        raise ValueError("object_height_m_required")
    if fx_px <= 0.0 or fy_px <= 0.0:
        raise ValueError("positive_focal_lengths_required")
    center_x = float(detection.get("center_x_px", (x0 + x1) / 2.0))
    center_y = float(detection.get("center_y_px", (y0 + y1) / 2.0))
    z_m = object_height_m * fy_px / bbox_height_px
    x_m = (center_x - cx_px) * z_m / fx_px
    y_m = (center_y - cy_px) * z_m / fy_px
    bearing_rad = math.atan2(x_m, z_m)
    return {
        "frame": "factory_bridge_camera_optical_estimated",
        "x_m_right": round(x_m, 6),
        "y_m_down": round(y_m, 6),
        "z_m_forward": round(z_m, 6),
        "bearing_rad_right_positive": round(bearing_rad, 6),
        "bbox_width_px": round(bbox_width_px, 3),
        "bbox_height_px": round(bbox_height_px, 3),
        "image_width": int(image_width),
        "image_height": int(image_height),
        "method": "monocular_known_object_height_pinhole",
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_dir = ensure_dir(args.artifact_dir or default_artifact_dir())
    summary: dict[str, Any] = {
        "type": "factory_bridge_monocular_pose_probe",
        "generated_utc": utc_now(),
        "artifact_dir": str(artifact_dir),
        "base_url": args.base_url,
        "issues": [],
        "pass": False,
    }
    yolo_dir = artifact_dir / "yolo"
    yolo_script = Path(__file__).with_name("chasecar_bridge_yolo_onnx_probe.py")
    command = [
        sys.executable,
        str(yolo_script),
        "--base-url",
        args.base_url,
        "--artifact-dir",
        str(yolo_dir),
        "--model",
        args.model,
        "--confidence-threshold",
        str(args.confidence_threshold),
        "--target-min-area-ratio",
        str(args.target_min_area_ratio),
        "--iou-threshold",
        str(args.iou_threshold),
        "--input-size",
        str(args.input_size),
        "--timeout-s",
        str(args.timeout_s),
    ]
    if args.image:
        command.extend(["--image", args.image])
    for target_class in args.target_class or ["bottle"]:
        command.extend(["--target-class", target_class])
    completed = subprocess.run(command, cwd=str(Path(__file__).resolve().parents[2]), capture_output=True, text=True, timeout=max(20.0, float(args.timeout_s) + 15.0))
    summary["yolo_command"] = command
    summary["yolo_returncode"] = completed.returncode
    summary["yolo_stdout"] = completed.stdout
    summary["yolo_stderr"] = completed.stderr
    summary["yolo_summary_path"] = str(yolo_dir / "yolo_detection_summary.json")
    if not (yolo_dir / "yolo_detection_summary.json").is_file():
        summary["issues"].append("yolo_summary_missing")
        write_json(artifact_dir / "monocular_pose_summary.json", summary)
        return summary
    yolo_summary = json.loads((yolo_dir / "yolo_detection_summary.json").read_text(encoding="utf-8-sig"))
    summary["yolo"] = {
        "pass": bool(yolo_summary.get("pass", False)),
        "issues": list(yolo_summary.get("issues", [])) if isinstance(yolo_summary.get("issues"), list) else [],
        "detected": bool(yolo_summary.get("detected", False)),
        "best_detection": yolo_summary.get("best_detection", {}),
        "snapshot": yolo_summary.get("snapshot", {}),
        "annotated_image_path": yolo_summary.get("annotated_image_path", ""),
    }
    if not bool(yolo_summary.get("pass", False)):
        summary["issues"].append("yolo_probe_not_passed")
        write_json(artifact_dir / "monocular_pose_summary.json", summary)
        return summary

    detection = yolo_summary.get("best_detection") if isinstance(yolo_summary.get("best_detection"), dict) else {}
    image_path = Path(str(yolo_summary.get("snapshot", {}).get("path", "")))
    image_width = 0
    image_height = 0
    if image_path.is_file():
        import_error = yolo_probe.load_detector_dependencies(require_onnx=False)
        if import_error:
            summary["issues"].append("image_dependency_unavailable:%s" % import_error)
        else:
            image = yolo_probe.Image.open(image_path)
            image_width, image_height = image.size
            image.close()
    if image_width <= 0 or image_height <= 0:
        summary["issues"].append("snapshot_dimensions_unavailable")
        write_json(artifact_dir / "monocular_pose_summary.json", summary)
        return summary

    center_error = float(detection.get("center_error", 0.0) or 0.0)
    area_ratio = float(detection.get("area_ratio", 0.0) or 0.0)
    summary["bearing_area_observation"] = {
        "class_name": detection.get("class_name", ""),
        "confidence": detection.get("confidence"),
        "area_ratio": round(area_ratio, 6),
        "center_error": round(center_error, 6),
        "bearing_status": "available_nonmetric",
    }

    intrinsics: dict[str, Any] = {}
    if args.fx_px > 0.0 and args.fy_px > 0.0:
        intrinsics = {
            "fx_px": float(args.fx_px),
            "fy_px": float(args.fy_px),
            "cx_px": float(args.cx_px if args.cx_px > 0.0 else image_width / 2.0),
            "cy_px": float(args.cy_px if args.cy_px > 0.0 else image_height / 2.0),
            "source": "explicit",
        }
    elif args.horizontal_fov_deg > 0.0 and args.vertical_fov_deg > 0.0:
        intrinsics = focal_from_fov(
            float(image_width),
            float(image_height),
            float(args.horizontal_fov_deg),
            float(args.vertical_fov_deg),
        )
    summary["intrinsics"] = intrinsics

    if not intrinsics or float(args.object_height_m) <= 0.0:
        summary["metric_pose_status"] = "blocked"
        summary["blocker"] = (
            "metric_pose_requires_depth_or_calibrated_intrinsics_and_target_size"
        )
        summary["issues"].append(summary["blocker"])
        write_json(artifact_dir / "monocular_pose_summary.json", summary)
        return summary

    pose = estimate_pose_from_bbox(
        detection,
        image_width=image_width,
        image_height=image_height,
        object_height_m=float(args.object_height_m),
        fx_px=float(intrinsics["fx_px"]),
        fy_px=float(intrinsics["fy_px"]),
        cx_px=float(intrinsics["cx_px"]),
        cy_px=float(intrinsics["cy_px"]),
    )
    summary["metric_pose_status"] = "estimated"
    summary["metric_pose"] = pose
    summary["object_height_m"] = float(args.object_height_m)
    summary["pass"] = True
    write_json(artifact_dir / "monocular_pose_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe whether bridge YOLO detections can produce metric object pose.")
    parser.add_argument("--base-url", default=yolo_probe.DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--image", default="")
    parser.add_argument("--model", default="runtime/yolo/yolov5s.onnx")
    parser.add_argument("--target-class", action="append", default=[])
    parser.add_argument("--confidence-threshold", type=float, default=0.10)
    parser.add_argument("--target-min-area-ratio", type=float, default=0.03)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--object-height-m", type=float, default=0.0)
    parser.add_argument("--fx-px", type=float, default=0.0)
    parser.add_argument("--fy-px", type=float, default=0.0)
    parser.add_argument("--cx-px", type=float, default=0.0)
    parser.add_argument("--cy-px", type=float, default=0.0)
    parser.add_argument("--horizontal-fov-deg", type=float, default=0.0)
    parser.add_argument("--vertical-fov-deg", type=float, default=0.0)
    parser.add_argument("--pretty", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass", False) or summary.get("metric_pose_status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
