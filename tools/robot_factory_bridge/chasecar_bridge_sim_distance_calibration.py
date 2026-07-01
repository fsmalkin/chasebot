#!/usr/bin/env python3
"""Fit sim mono apparent-size calibration from saved RGB frames.

Input is a directory of captured frames plus a JSON map of
``{frame_filename: known_forward_range_z_m}``. Detection uses the persistent
mono YOLO adapter, then the existing apparent-size fit is reused for both
``equiv_diameter_px`` and ``bbox_height_px``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
ROS2_SCRIPTS_DIR = REPO_ROOT / "ros2_scripts"
if str(ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ROS2_SCRIPTS_DIR))

import chasecar_mono_yolo_detect as mono_yolo  # noqa: E402
from chasecar_bridge_mono_distance_calibration import DEFAULT_OBJECT_SIZE_M  # noqa: E402
from chasecar_bridge_mono_distance_calibration import SIZE_KEYS  # noqa: E402
from chasecar_bridge_mono_distance_calibration import fit_apparent_size  # noqa: E402


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_range_map(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and isinstance(payload.get("frames"), dict):
        payload = payload["frames"]
    if not isinstance(payload, dict):
        raise ValueError("range_map_must_be_json_object")
    result: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            raw_range = value.get("known_forward_range_z_m", value.get("known_distance_m"))
        else:
            raw_range = value
        result[str(key)] = float(raw_range)
    return result


def resolve_frame_path(frames_dir: Path, filename: str) -> Path:
    candidate = Path(filename)
    if candidate.is_file():
        return candidate
    return frames_dir / filename


def load_rgb_frame(path: Path) -> Any:
    mono_yolo._load_detector_dependencies(require_onnx=False)  # pylint: disable=protected-access
    image = mono_yolo.yolo_probe.Image.open(path).convert("RGB")
    return mono_yolo.yolo_probe.np.asarray(image, dtype=mono_yolo.yolo_probe.np.uint8)


def build_samples(args: argparse.Namespace) -> list[dict[str, Any]]:
    frames_dir = Path(args.frames_dir)
    range_map = load_range_map(Path(args.range_map))
    detector = mono_yolo.MonoYoloDetector(
        args.model,
        target_class=args.target_class,
        confidence_threshold=args.confidence_threshold,
        iou_threshold=args.iou_threshold,
        input_size=args.input_size,
        min_area_ratio=args.target_min_area_ratio,
    )
    samples: list[dict[str, Any]] = []
    for frame_name, known_range_m in sorted(range_map.items()):
        frame_path = resolve_frame_path(frames_dir, frame_name)
        sample: dict[str, Any] = {
            "type": "sim_mono_distance_calibration_sample",
            "frame_filename": frame_name,
            "frame_path": str(frame_path),
            "known_forward_range_z_m": float(known_range_m),
            "known_distance_m": float(known_range_m),
            "detector": "yolo",
            "class_name": args.target_class,
            "issues": [],
        }
        if not frame_path.is_file():
            sample.update({"detected": False})
            sample["issues"].append("frame_missing")
            samples.append(sample)
            continue
        if frame_path.suffix.lower() not in IMAGE_SUFFIXES:
            sample.update({"detected": False})
            sample["issues"].append("unsupported_image_suffix")
            samples.append(sample)
            continue
        try:
            detection = detector.detect(load_rgb_frame(frame_path))
        except Exception as exc:  # pragma: no cover - live dependency failures
            sample.update({"detected": False})
            sample["issues"].append("detect_failed:%s" % exc)
            samples.append(sample)
            continue
        if not detection:
            sample.update({"detected": False})
            sample["issues"].append("target_not_detected")
            samples.append(sample)
            continue
        sample.update(
            {
                "detected": True,
                "confidence": detection.get("confidence"),
                "bbox_xyxy": detection.get("bbox_xyxy"),
                "bbox_height_px": detection.get("bbox_height_px"),
                "bbox_width_px": detection.get("bbox_width_px"),
                "equiv_diameter_px": detection.get("equiv_diameter_px"),
                "area_ratio": detection.get("area_ratio"),
                "center_error": detection.get("center_error"),
                "measurement": detection,
            }
        )
        samples.append(sample)
    return samples


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    samples = build_samples(args)
    object_size_m = float(args.object_size_m)
    summary: dict[str, Any] = {
        "type": "mono_distance_calibration_summary",
        "source": "sim_saved_frames_yolo",
        "generated_utc": utc_now(),
        "frames_dir": str(Path(args.frames_dir)),
        "range_map_path": str(Path(args.range_map)),
        "model": str(Path(args.model)),
        "target_class": args.target_class,
        "confidence_threshold": float(args.confidence_threshold),
        "iou_threshold": float(args.iou_threshold),
        "input_size": int(args.input_size),
        "object_size_m": object_size_m,
        "n_samples": len(samples),
        "n_detected": sum(1 for sample in samples if bool(sample.get("detected"))),
        "samples": samples,
        "fits": {},
        "issues": [],
    }
    if not samples:
        summary["issues"].append("range_map_empty")
    for size_key in SIZE_KEYS:
        summary["fits"][size_key] = fit_apparent_size(
            samples,
            size_key=size_key,
            object_size_m=object_size_m,
        )
    summary["recommended_size_key"] = "equiv_diameter_px"
    summary["pass"] = bool(summary["fits"].get("equiv_diameter_px", {}).get("pass"))
    if not summary["pass"]:
        summary["issues"].append("recommended_fit_failed")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--range-map", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--model", default=str(mono_yolo.DEFAULT_MODEL_PATH))
    parser.add_argument("--target-class", default=mono_yolo.DEFAULT_TARGET_CLASS)
    parser.add_argument("--confidence-threshold", type=float, default=0.25)
    parser.add_argument("--target-min-area-ratio", type=float, default=0.0)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--object-size-m", type=float, default=DEFAULT_OBJECT_SIZE_M)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_summary(args)
    output = Path(args.output) if args.output else Path(args.frames_dir) / "calibration_summary.json"
    write_json(output, summary)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
