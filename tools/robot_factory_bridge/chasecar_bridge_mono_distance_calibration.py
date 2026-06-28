#!/usr/bin/env python3
"""Monocular distance calibration for the factory-bridge camera.

This is the modern, calibrated descendant of the legacy 2D-vision estimator
(``ros2_scripts/ros2_ball_to_nav_goal.py``), which used a single hardcoded
anchor (40 px @ 1 m). Here we measure a target's apparent pixel size from the
production color-blob analyzer at operator-measured distances and fit the
apparent-size law

    s_px = K / d            with   K = f_px * object_size_m

then report the residual sigma and a distance-uncertainty model

    sigma_d(d) ~= (d**2 / K) * sigma_s_px

which surfaces the known monocular failure mode (error grows with d**2).

Observation only: this never enables motion. It reads ``/health`` and
``/camera.jpg`` and leaves the bridge exactly as found (expected locked,
``motion_enabled=false``). The pixel-size source is the color-blob analyzer
(robust on a small colored golf ball, and the same measurement the production
adapter consumes); YOLO is intentionally not required here.

Usage:
    # one capture per operator-measured distance (repeat for the sweep)
    python chasecar_bridge_mono_distance_calibration.py capture \
        --session-id bench01 --known-distance-m 0.30 --label d030 \
        --target-profile bright

    # fit once the sweep is captured
    python chasecar_bridge_mono_distance_calibration.py fit \
        --session-id bench01 --object-size-m 0.0427
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import chasecar_bridge_behavior_runner as behavior_runner
import chasecar_bridge_yolo_onnx_probe as yolo_probe

DEFAULT_BASE_URL = yolo_probe.DEFAULT_BASE_URL
DEFAULT_OBJECT_SIZE_M = 0.0427  # regulation golf ball diameter, metres
DATASET_NAME = "calibration_dataset.jsonl"
SUMMARY_NAME = "calibration_summary.json"
SIZE_KEYS = ("bbox_height_px", "equiv_diameter_px")


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


def session_dir(session_id: str) -> Path:
    return Path("artifacts") / "session" / ("mono_distance_calibration_%s" % session_id)


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if not Path(dataset_path).is_file():
        return samples
    for line in Path(dataset_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        samples.append(json.loads(line))
    return samples


def measure_frame(
    image_path: Path,
    *,
    target_profile: str,
    min_area_ratio: float,
    annotated_path: Path | None,
    min_luma: float | None = None,
    min_saturation: float | None = None,
    min_value: float | None = None,
) -> dict[str, Any]:
    """Measure the target blob's apparent size using the production analyzer.

    Threshold overrides (luma/saturation/value) are exposed so the operator can
    tune detection to the actual ball + lighting during the live sanity check
    before the calibration sweep, without editing code.
    """
    bargs = behavior_runner.build_parser().parse_args([])
    bargs.target_profile = target_profile
    bargs.target_min_area_ratio = float(min_area_ratio)
    if min_luma is not None:
        bargs.target_min_luma = float(min_luma)
    if min_saturation is not None:
        bargs.target_min_saturation = float(min_saturation)
    if min_value is not None:
        bargs.target_min_value = float(min_value)
    analysis = behavior_runner.analyze_target_image(
        Path(image_path), bargs, annotated_path=annotated_path
    )
    bbox = analysis.get("bbox") if isinstance(analysis.get("bbox"), dict) else {}
    detected = bool(analysis.get("detected", False))
    height_px = (float(bbox.get("y1", 0.0)) - float(bbox.get("y0", 0.0))) if bbox else 0.0
    width_px = (float(bbox.get("x1", 0.0)) - float(bbox.get("x0", 0.0))) if bbox else 0.0
    matched = float(analysis.get("matched_pixels", 0.0) or 0.0)
    equiv_diameter_px = 2.0 * math.sqrt(matched / math.pi) if matched > 0.0 else 0.0
    return {
        "detected": detected,
        "target_profile": analysis.get("target_profile"),
        "bbox": bbox,
        "bbox_height_px": round(height_px, 3),
        "bbox_width_px": round(width_px, 3),
        "bbox_area_px": round(height_px * width_px, 3),
        "matched_pixels": matched,
        "equiv_diameter_px": round(equiv_diameter_px, 3),
        "area_ratio": analysis.get("area_ratio"),
        "center_error": analysis.get("center_error"),
        "image_width": analysis.get("image_width"),
        "image_height": analysis.get("image_height"),
        "annotated_image_path": str(annotated_path) if annotated_path else "",
    }


def measure_frame_yolo(
    image_path: Path,
    *,
    model: str,
    target_class: str,
    confidence_threshold: float,
    iou_threshold: float,
    input_size: int,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Measure the target's apparent size from the committed YOLO ONNX probe.

    YOLO keys on learned shape, so it isolates the ball in dim / reflective scenes
    where color/brightness segmentation fails. Runs the proven probe on the saved
    frame (no re-fetch) and reads its best detection. ``equiv_diameter_px`` is the
    bbox geometric mean sqrt(w*h) — orientation-stable for a sphere.
    """
    yolo_script = Path(__file__).with_name("chasecar_bridge_yolo_onnx_probe.py")
    yolo_dir = ensure_dir(artifact_dir)
    command = [
        sys.executable,
        str(yolo_script),
        "--image",
        str(image_path),
        "--model",
        str(model),
        "--target-class",
        target_class,
        "--confidence-threshold",
        str(confidence_threshold),
        "--iou-threshold",
        str(iou_threshold),
        "--input-size",
        str(input_size),
        "--target-min-area-ratio",
        "0.0",
        "--artifact-dir",
        str(yolo_dir),
    ]
    completed = subprocess.run(
        command,
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=120.0,
    )
    summary_path = yolo_dir / "yolo_detection_summary.json"
    if not summary_path.is_file():
        return {
            "detected": False,
            "detector": "yolo",
            "issue": "yolo_summary_missing",
            "returncode": completed.returncode,
            "stderr": completed.stderr[-400:],
        }
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    best = summary.get("best_detection") if isinstance(summary.get("best_detection"), dict) else None
    if not summary.get("detected") or not best:
        return {
            "detected": False,
            "detector": "yolo",
            "class_name": target_class,
            "issues": summary.get("issues", []),
            "annotated_image_path": summary.get("annotated_image_path", ""),
        }
    bbox = best.get("bbox_xyxy") or []
    x0, y0, x1, y1 = [float(v) for v in bbox]
    height_px = max(0.0, y1 - y0)
    width_px = max(0.0, x1 - x0)
    equiv_diameter_px = math.sqrt(width_px * height_px) if (width_px > 0.0 and height_px > 0.0) else 0.0
    return {
        "detected": True,
        "detector": "yolo",
        "class_name": best.get("class_name"),
        "confidence": best.get("confidence"),
        "bbox": {"x0": round(x0, 3), "y0": round(y0, 3), "x1": round(x1, 3), "y1": round(y1, 3)},
        "bbox_height_px": round(height_px, 3),
        "bbox_width_px": round(width_px, 3),
        "equiv_diameter_px": round(equiv_diameter_px, 3),
        "area_ratio": best.get("area_ratio"),
        "center_error": best.get("center_error"),
        "annotated_image_path": summary.get("annotated_image_path", ""),
    }


def fit_apparent_size(
    samples: list[dict[str, Any]],
    *,
    size_key: str,
    object_size_m: float,
) -> dict[str, Any]:
    """Least-squares fit of s_px = K / d through the origin in (1/d, s_px).

    Pure function (no I/O) so it is unit-testable without a bridge or images.
    """
    used = [
        s
        for s in samples
        if bool(s.get("detected"))
        and float(s.get("known_distance_m", 0.0) or 0.0) > 0.0
        and float(s.get(size_key, 0.0) or 0.0) > 0.0
    ]
    if len(used) < 2:
        return {
            "pass": False,
            "size_key": size_key,
            "n_used": len(used),
            "issues": ["need_at_least_two_detected_samples"],
        }

    xs = [1.0 / float(s["known_distance_m"]) for s in used]
    ss = [float(s[size_key]) for s in used]
    sxx = sum(x * x for x in xs)
    sxs = sum(x * sv for x, sv in zip(xs, ss))
    if sxx <= 0.0:
        return {"pass": False, "size_key": size_key, "n_used": len(used), "issues": ["degenerate_distances"]}
    k_const = sxs / sxx
    residuals = [sv - k_const * x for x, sv in zip(xs, ss)]
    n = len(used)
    sigma_s = math.sqrt(sum(r * r for r in residuals) / (n - 1)) if n > 1 else 0.0

    per_sample: list[dict[str, Any]] = []
    for sample, x, sv, r in zip(used, xs, ss, residuals):
        d = float(sample["known_distance_m"])
        d_hat = k_const / sv if sv > 0.0 else 0.0
        per_sample.append(
            {
                "label": sample.get("label"),
                "known_distance_m": d,
                "size_px": round(sv, 3),
                "d_hat_m": round(d_hat, 4),
                "abs_err_m": round(abs(d_hat - d), 4),
                "residual_px": round(r, 3),
                "sigma_d_m": round((d * d / k_const) * sigma_s, 4) if k_const > 0.0 else None,
            }
        )

    implied_focal_px = (k_const / object_size_m) if object_size_m > 0.0 else None
    max_range = max(float(s["known_distance_m"]) for s in used)
    return {
        "pass": True,
        "size_key": size_key,
        "n_used": n,
        "K_px_m": round(k_const, 4),
        "object_size_m": float(object_size_m),
        "implied_focal_px": round(implied_focal_px, 3) if implied_focal_px else None,
        "sigma_s_px": round(sigma_s, 4),
        "max_calibrated_range_m": round(max_range, 3),
        "sigma_d_model": "sigma_d(d) = (d^2 / K_px_m) * sigma_s_px",
        "per_sample": per_sample,
        "issues": [],
    }


def run_capture(args: argparse.Namespace) -> dict[str, Any]:
    sdir = ensure_dir(session_dir(args.session_id))
    dataset_path = sdir / DATASET_NAME
    sample: dict[str, Any] = {
        "type": "mono_distance_calibration_sample",
        "label": args.label,
        "known_distance_m": float(args.known_distance_m),
        "generated_utc": utc_now(),
        "base_url": args.base_url.rstrip("/"),
        "issues": [],
    }

    try:
        _, health = yolo_probe.fetch_json(args.base_url.rstrip("/") + "/health", args.timeout_s)
    except Exception as exc:  # pylint: disable=broad-except
        sample["issues"].append("health_fetch_failed:%s" % exc)
        _append_sample(dataset_path, sample)
        return sample
    camera = health.get("camera", {}) if isinstance(health, dict) else {}
    sample["bridge_motion_enabled"] = bool(health.get("motion_enabled", True))
    sample["camera_fps"] = camera.get("cached_fps")
    sample["frame_age_s"] = camera.get("frame_age_s")
    sample["camera_backend"] = camera.get("backend")
    if sample["bridge_motion_enabled"]:
        sample["issues"].append("bridge_motion_enabled_unexpected")
    if not bool(camera.get("enabled", False)):
        sample["issues"].append("camera_not_enabled")

    try:
        status, frame_bytes, source, fallback = yolo_probe.fetch_camera_bytes(args.base_url, args.timeout_s)
    except Exception as exc:  # pylint: disable=broad-except
        sample["issues"].append("camera_fetch_failed:%s" % exc)
        _append_sample(dataset_path, sample)
        return sample
    frame_path = sdir / ("frame_%s_%s.jpg" % (args.label, utc_stamp()))
    frame_path.write_bytes(frame_bytes)
    annotated_path = sdir / ("frame_%s_annotated.jpg" % args.label)
    sample["frame_path"] = str(frame_path)
    sample["camera_endpoint"] = source
    sample["camera_http_status"] = status
    if fallback:
        sample["camera_jpg_error"] = fallback

    try:
        if args.detector == "yolo":
            measurement = measure_frame_yolo(
                frame_path,
                model=args.model,
                target_class=args.target_class,
                confidence_threshold=args.confidence_threshold,
                iou_threshold=args.iou_threshold,
                input_size=args.input_size,
                artifact_dir=sdir / ("yolo_%s" % args.label),
            )
        else:
            measurement = measure_frame(
                frame_path,
                target_profile=args.target_profile,
                min_area_ratio=args.target_min_area_ratio,
                annotated_path=annotated_path,
                min_luma=args.target_min_luma,
                min_saturation=args.target_min_saturation,
                min_value=args.target_min_value,
            )
    except Exception as exc:  # pylint: disable=broad-except
        sample["issues"].append("measure_failed:%s" % exc)
        _append_sample(dataset_path, sample)
        return sample

    sample["detector"] = measurement.get("detector", args.detector)
    sample["detected"] = bool(measurement.get("detected"))
    sample["class_name"] = measurement.get("class_name")
    sample["confidence"] = measurement.get("confidence")
    sample["bbox_height_px"] = measurement.get("bbox_height_px")
    sample["equiv_diameter_px"] = measurement.get("equiv_diameter_px")
    sample["bbox_width_px"] = measurement.get("bbox_width_px")
    sample["matched_pixels"] = measurement.get("matched_pixels")
    sample["center_error"] = measurement.get("center_error")
    sample["measurement"] = measurement
    if not sample["detected"]:
        sample["issues"].append("target_not_detected")
    _append_sample(dataset_path, sample)
    return sample


def _append_sample(dataset_path: Path, sample: dict[str, Any]) -> None:
    ensure_dir(Path(dataset_path).parent)
    with open(dataset_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, sort_keys=True) + "\n")


def run_fit(args: argparse.Namespace) -> dict[str, Any]:
    sdir = session_dir(args.session_id)
    dataset_path = sdir / DATASET_NAME
    samples = load_dataset(dataset_path)
    summary: dict[str, Any] = {
        "type": "mono_distance_calibration_summary",
        "generated_utc": utc_now(),
        "session_id": args.session_id,
        "dataset_path": str(dataset_path),
        "n_samples": len(samples),
        "n_detected": sum(1 for s in samples if bool(s.get("detected"))),
        "object_size_m": float(args.object_size_m),
        "fits": {},
        "issues": [],
    }
    if not samples:
        summary["issues"].append("dataset_empty")
        summary["pass"] = False
        write_json(sdir / SUMMARY_NAME, summary)
        return summary
    for size_key in SIZE_KEYS:
        summary["fits"][size_key] = fit_apparent_size(
            samples, size_key=size_key, object_size_m=float(args.object_size_m)
        )
    summary["recommended_size_key"] = "equiv_diameter_px"
    summary["pass"] = bool(summary["fits"].get("equiv_diameter_px", {}).get("pass"))
    write_json(sdir / SUMMARY_NAME, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="Capture one known-distance frame + measurement.")
    cap.add_argument("--session-id", required=True)
    cap.add_argument("--known-distance-m", type=float, required=True)
    cap.add_argument("--label", required=True)
    cap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    cap.add_argument("--timeout-s", type=float, default=6.0)
    cap.add_argument("--detector", default="yolo", choices=("yolo", "color"))
    cap.add_argument("--model", default="runtime/yolo/yolov5m.onnx")
    cap.add_argument("--target-class", default="sports ball")
    cap.add_argument("--confidence-threshold", type=float, default=0.25)
    cap.add_argument("--iou-threshold", type=float, default=0.45)
    cap.add_argument("--input-size", type=int, default=640)
    cap.add_argument(
        "--target-profile",
        default="bright",
        choices=("bright", "any-saturated", "yellow", "orange", "red", "green", "blue"),
    )
    cap.add_argument("--target-min-area-ratio", type=float, default=0.0008)
    cap.add_argument("--target-min-luma", type=float, default=180.0)
    cap.add_argument("--target-min-saturation", type=float, default=0.35)
    cap.add_argument("--target-min-value", type=float, default=0.35)
    cap.add_argument("--pretty", action="store_true")

    fit = sub.add_parser("fit", help="Fit the apparent-size law over a captured sweep.")
    fit.add_argument("--session-id", required=True)
    fit.add_argument("--object-size-m", type=float, default=DEFAULT_OBJECT_SIZE_M)
    fit.add_argument("--pretty", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _print_capture(sample: dict[str, Any]) -> None:
    print(
        "d=%.3fm label=%s detector=%s detected=%s class=%s conf=%s diam_px=%s height_px=%s center_err=%s%s"
        % (
            sample.get("known_distance_m", 0.0),
            sample.get("label"),
            sample.get("detector"),
            sample.get("detected"),
            sample.get("class_name"),
            sample.get("confidence"),
            sample.get("equiv_diameter_px"),
            sample.get("bbox_height_px"),
            sample.get("center_error"),
            (" issues=%s" % sample["issues"]) if sample.get("issues") else "",
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "capture":
        sample = run_capture(args)
        _print_capture(sample)
        if args.pretty:
            print(json.dumps(sample, indent=2, sort_keys=True))
        return 0 if sample.get("detected") and not sample.get("issues") else 1
    summary = run_fit(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
