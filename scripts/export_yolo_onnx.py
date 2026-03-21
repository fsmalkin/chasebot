#!/usr/bin/env python3
"""Export a YOLO model to ONNX for TensorRT build pipeline."""

import argparse
import os
import pathlib
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Ultralytics YOLO weights to ONNX.")
    parser.add_argument("--model", default="yolov8m.pt", help="Path to source YOLO weights.")
    parser.add_argument("--output", required=True, help="Output ONNX file path.")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size.")
    parser.add_argument("--opset", type=int, default=13, help="ONNX opset version.")
    parser.add_argument("--simplify", action="store_true", help="Run ONNX simplification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from ultralytics import YOLO  # pylint: disable=import-outside-toplevel
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[ERROR] ultralytics import failed: {exc}", file=sys.stderr)
        return 2

    model_path = os.path.expanduser(args.model)
    output_path = pathlib.Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_path)
    result = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        simplify=args.simplify,
    )

    exported_path = pathlib.Path(str(result)).expanduser().resolve()
    if exported_path != output_path:
        output_path.write_bytes(exported_path.read_bytes())

    print(f"ONNX_EXPORT_OK=1")
    print(f"ONNX_EXPORT_PATH={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
