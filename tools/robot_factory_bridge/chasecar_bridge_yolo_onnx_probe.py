#!/usr/bin/env python3
"""Run a YOLO ONNX detector against a live factory-bridge camera frame.

This is a laptop-side probe: it leaves the robot bridge locked, fetches one
JPEG from /camera.jpg, runs ONNX Runtime locally, and writes JSON plus an
annotated image for review.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

np = None
Image = None
ImageDraw = None
ImageFont = None
ort = None
DETECTOR_IMPORT_ERROR = ""


DEFAULT_BASE_URL = "http://192.168.1.11:8765"
DEFAULT_MODEL_URL = "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx"

COCO_CLASSES = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def json_dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_detector_dependencies(*, require_onnx: bool = True) -> str:
    global DETECTOR_IMPORT_ERROR, Image, ImageDraw, ImageFont, np, ort
    if DETECTOR_IMPORT_ERROR:
        return DETECTOR_IMPORT_ERROR
    try:
        if np is None:
            import numpy as numpy_module

            np = numpy_module
        if Image is None or ImageDraw is None or ImageFont is None:
            from PIL import Image as pil_image
            from PIL import ImageDraw as pil_image_draw
            from PIL import ImageFont as pil_image_font

            Image = pil_image
            ImageDraw = pil_image_draw
            ImageFont = pil_image_font
        if require_onnx and ort is None:
            import onnxruntime as onnxruntime_module

            ort = onnxruntime_module
    except Exception as exc:  # pragma: no cover - exercised in live setup
        DETECTOR_IMPORT_ERROR = str(exc)
    return DETECTOR_IMPORT_ERROR


def fetch_json(url: str, timeout_s: float) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return int(response.status), json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str, timeout_s: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return int(response.status), response.read()


def fetch_camera_bytes(base_url: str, timeout_s: float) -> tuple[int, bytes, str, str]:
    try:
        status, payload = fetch_bytes(base_url.rstrip("/") + "/camera.jpg", timeout_s)
        return status, payload, "camera.jpg", ""
    except Exception as exc:  # pylint: disable=broad-except
        jpg_error = repr(exc)
    status, payload = fetch_json(base_url.rstrip("/") + "/camera.json", timeout_s)
    if not bool(payload.get("ok", False)):
        raise RuntimeError("camera_json_not_ok:%s after camera_jpg_failed:%s" % (payload, jpg_error))
    encoded = payload.get("image_base64", "")
    if not encoded:
        raise RuntimeError("camera_json_missing_image_base64 after camera_jpg_failed:%s" % jpg_error)
    return status, base64.b64decode(encoded), "camera.json", jpg_error


def download_file(url: str, path: Path, timeout_s: float) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".download")
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            data = response.read()
            tmp.write_bytes(data)
            tmp.replace(path)
            return {"ok": True, "url": url, "path": str(path), "bytes": len(data), "http_status": int(response.status)}
    except urllib.error.URLError as exc:
        return {"ok": False, "url": url, "path": str(path), "error": str(exc)}


def letterbox(image: Image.Image, size: int, *, dtype=None) -> tuple[np.ndarray, float, tuple[int, int]]:
    if dtype is None:
        dtype = np.float32
    width, height = image.size
    scale = min(size / float(width), size / float(height))
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))
    resized = image.resize((new_width, new_height), Image.BILINEAR)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    pad_x = (size - new_width) // 2
    pad_y = (size - new_height) // 2
    canvas.paste(resized, (pad_x, pad_y))
    array = np.asarray(canvas, dtype=np.float32) / 255.0
    array = np.transpose(array, (2, 0, 1))[None, ...]
    return array.astype(dtype), scale, (pad_x, pad_y)


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    converted = np.zeros_like(boxes, dtype=np.float32)
    converted[:, 0] = boxes[:, 0] - boxes[:, 2] / 2.0
    converted[:, 1] = boxes[:, 1] - boxes[:, 3] / 2.0
    converted[:, 2] = boxes[:, 0] + boxes[:, 2] / 2.0
    converted[:, 3] = boxes[:, 1] + boxes[:, 3] / 2.0
    return converted


def unletterbox(boxes: np.ndarray, scale: float, pad: tuple[int, int], width: int, height: int) -> np.ndarray:
    pad_x, pad_y = pad
    converted = boxes.copy().astype(np.float32)
    converted[:, [0, 2]] = (converted[:, [0, 2]] - pad_x) / scale
    converted[:, [1, 3]] = (converted[:, [1, 3]] - pad_y) / scale
    converted[:, [0, 2]] = np.clip(converted[:, [0, 2]], 0, width - 1)
    converted[:, [1, 3]] = np.clip(converted[:, [1, 3]], 0, height - 1)
    return converted


def box_iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    box_area = max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))
    boxes_area = np.maximum(0.0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0.0, boxes[:, 3] - boxes[:, 1])
    return inter / np.maximum(box_area + boxes_area - inter, 1e-6)


def nms(detections: list[dict], iou_threshold: float) -> list[dict]:
    if not detections:
        return []
    ordered = sorted(detections, key=lambda item: float(item["confidence"]), reverse=True)
    kept: list[dict] = []
    while ordered:
        current = ordered.pop(0)
        kept.append(current)
        if not ordered:
            break
        current_box = np.array(current["bbox_xyxy"], dtype=np.float32)
        remaining_boxes = np.array([item["bbox_xyxy"] for item in ordered], dtype=np.float32)
        overlaps = box_iou(current_box, remaining_boxes)
        ordered = [item for item, overlap in zip(ordered, overlaps) if overlap <= iou_threshold]
    return kept


def decode_yolov5_output(
    output: np.ndarray,
    *,
    width: int,
    height: int,
    scale: float,
    pad: tuple[int, int],
    confidence_threshold: float,
    class_names: set[str],
    iou_threshold: float,
) -> list[dict]:
    predictions = np.squeeze(output)
    if predictions.ndim != 2 or predictions.shape[1] < 85:
        raise RuntimeError("unsupported_yolo_output_shape:%s" % (list(output.shape),))

    boxes_xywh = predictions[:, 0:4]
    objectness = predictions[:, 4]
    class_scores = predictions[:, 5:]
    class_ids = np.argmax(class_scores, axis=1)
    class_conf = class_scores[np.arange(class_scores.shape[0]), class_ids]
    scores = objectness * class_conf
    keep = scores >= confidence_threshold
    if not np.any(keep):
        return []

    boxes = xywh_to_xyxy(boxes_xywh[keep])
    boxes = unletterbox(boxes, scale, pad, width, height)
    kept_scores = scores[keep]
    kept_class_ids = class_ids[keep]

    detections: list[dict] = []
    for box, score, class_id in zip(boxes, kept_scores, kept_class_ids):
        class_name = COCO_CLASSES[int(class_id)] if int(class_id) < len(COCO_CLASSES) else "class_%s" % int(class_id)
        if class_names and class_name not in class_names:
            continue
        x0, y0, x1, y1 = [float(v) for v in box.tolist()]
        detections.append(
            {
                "class_id": int(class_id),
                "class_name": class_name,
                "confidence": round(float(score), 6),
                "bbox_xyxy": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
                "center_x_px": round((x0 + x1) / 2.0, 3),
                "center_y_px": round((y0 + y1) / 2.0, 3),
                "area_ratio": round(max(0.0, (x1 - x0) * (y1 - y0)) / float(width * height), 6),
                "center_error": round(((x0 + x1) / 2.0 - (width / 2.0)) / (width / 2.0), 6),
            }
        )
    return nms(detections, iou_threshold)


def annotate(image: Image.Image, detections: list[dict], path: Path) -> None:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    for det in detections:
        x0, y0, x1, y1 = [int(round(v)) for v in det["bbox_xyxy"]]
        label = "%s %.2f" % (det["class_name"], float(det["confidence"]))
        draw.rectangle((x0, y0, x1, y1), outline=(0, 220, 0), width=3)
        text_bbox = draw.textbbox((x0, y0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        draw.rectangle((x0, max(0, y0 - text_h - 6), x0 + text_w + 6, y0), fill=(0, 220, 0))
        draw.text((x0 + 3, max(0, y0 - text_h - 4)), label, fill=(0, 0, 0), font=font)
        draw.ellipse(
            (
                float(det["center_x_px"]) - 3,
                float(det["center_y_px"]) - 3,
                float(det["center_x_px"]) + 3,
                float(det["center_y_px"]) + 3,
            ),
            fill=(220, 0, 0),
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    output.save(path, quality=90)


def select_best_detection(detections: list[dict], *, min_area_ratio: float = 0.0) -> dict | None:
    candidates = [
        det
        for det in detections
        if float(det.get("area_ratio", 0.0) or 0.0) >= float(min_area_ratio)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda det: (
            float(det.get("confidence", 0.0) or 0.0),
            float(det.get("area_ratio", 0.0) or 0.0),
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO ONNX detector probe for factory bridge camera frames.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--image", default="", help="Use an existing image instead of fetching /camera.jpg.")
    parser.add_argument("--model", default="runtime/yolo/yolov5s.onnx")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--model-url", default=DEFAULT_MODEL_URL)
    parser.add_argument("--target-class", action="append", default=[], help="COCO class to keep; repeatable.")
    parser.add_argument("--all-classes", action="store_true", help="Keep all COCO classes for diagnostics.")
    parser.add_argument("--confidence-threshold", type=float, default=0.25)
    parser.add_argument("--target-min-area-ratio", type=float, default=0.0)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--timeout-s", type=float, default=6.0)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else Path("artifacts") / "session" / ("yolo_onnx_probe_%s" % utc_stamp())
    artifact_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "type": "factory_bridge_yolo_onnx_probe",
        "base_url": args.base_url.rstrip("/"),
        "artifact_dir": str(artifact_dir),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": str(Path(args.model)),
        "target_classes": "all" if args.all_classes else list(args.target_class or ["bottle"]),
        "confidence_threshold": float(args.confidence_threshold),
        "iou_threshold": float(args.iou_threshold),
        "issues": [],
    }

    model_path = Path(args.model)
    if not model_path.is_file() and args.download_model:
        summary["model_download"] = download_file(args.model_url, model_path, args.timeout_s)
    if not model_path.is_file():
        summary["issues"].append("model_file_missing")
        summary["pass"] = False
        json_dump(artifact_dir / "yolo_detection_summary.json", summary)
        print(json.dumps(summary, indent=2 if args.pretty else None))
        return 2

    detector_import_error = load_detector_dependencies(require_onnx=True)
    if detector_import_error:
        summary["issues"].append("detector_dependency_import_failed")
        summary["detector_dependency_import_error"] = detector_import_error
        summary["pass"] = False
        json_dump(artifact_dir / "yolo_detection_summary.json", summary)
        print(json.dumps(summary, indent=2 if args.pretty else None))
        return 2

    try:
        if args.image:
            image_path = Path(args.image)
            image = Image.open(image_path).convert("RGB")
            summary["snapshot"] = {"source": "file", "path": str(image_path), "bytes": image_path.stat().st_size}
        else:
            health_status, health = fetch_json(args.base_url.rstrip("/") + "/health", args.timeout_s)
            summary["health"] = {"http_status": health_status, "response": health}
            camera = health.get("camera", {}) if isinstance(health, dict) else {}
            if not bool(health.get("ok", False)):
                summary["issues"].append("bridge_health_not_ok")
            if bool(health.get("motion_enabled", False)):
                summary["issues"].append("bridge_motion_enabled")
            if not bool(camera.get("enabled", False)):
                summary["issues"].append("camera_not_enabled")
            snapshot_status, snapshot_bytes, snapshot_source, snapshot_fallback = fetch_camera_bytes(args.base_url, args.timeout_s)
            image_path = artifact_dir / "camera.jpg"
            image_path.write_bytes(snapshot_bytes)
            image = Image.open(image_path).convert("RGB")
            summary["snapshot"] = {
                "source": "bridge",
                "bridge_endpoint": snapshot_source,
                "http_status": snapshot_status,
                "path": str(image_path),
                "bytes": len(snapshot_bytes),
            }
            if snapshot_fallback:
                summary["snapshot"]["camera_jpg_error"] = snapshot_fallback
    except Exception as exc:  # pylint: disable=broad-except
        summary["issues"].append("snapshot_or_health_failed:%s" % exc)
        summary["pass"] = False
        json_dump(artifact_dir / "yolo_detection_summary.json", summary)
        print(json.dumps(summary, indent=2 if args.pretty else None))
        return 1

    try:
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        model_input = session.get_inputs()[0]
        input_name = model_input.name
        input_dtype = np.float16 if "float16" in str(model_input.type).lower() else np.float32
        input_tensor, scale, pad = letterbox(image, int(args.input_size), dtype=input_dtype)
        outputs = session.run(None, {input_name: input_tensor})
        detections = decode_yolov5_output(
            outputs[0],
            width=image.size[0],
            height=image.size[1],
            scale=scale,
            pad=pad,
            confidence_threshold=float(args.confidence_threshold),
            class_names=set() if args.all_classes else set(args.target_class or ["bottle"]),
            iou_threshold=float(args.iou_threshold),
        )
        annotated_path = artifact_dir / "yolo_detection_annotated.jpg"
        annotate(image, detections, annotated_path)
        best_detection = select_best_detection(detections, min_area_ratio=float(args.target_min_area_ratio))
        summary["detections"] = detections
        summary["detected"] = bool(best_detection)
        summary["best_detection"] = best_detection
        summary["annotated_image_path"] = str(annotated_path)
        summary["model"] = str(model_path)
        summary["input_size"] = int(args.input_size)
        summary["model_input"] = {"name": input_name, "type": str(model_input.type), "shape": list(model_input.shape)}
        summary["pass"] = bool(best_detection) and not any(issue == "bridge_motion_enabled" for issue in summary["issues"])
        if not best_detection:
            summary["issues"].append("target_class_not_detected")
    except Exception as exc:  # pylint: disable=broad-except
        summary["issues"].append("onnx_inference_failed:%s" % exc)
        summary["pass"] = False

    json_dump(artifact_dir / "yolo_detection_summary.json", summary)
    print(json.dumps(summary, indent=2 if args.pretty else None))
    return 0 if summary.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
