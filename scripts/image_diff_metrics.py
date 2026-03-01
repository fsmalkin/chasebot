#!/usr/bin/env python3
"""Compute simple image-difference metrics for visual UAT evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two image files.")
    parser.add_argument("--left", required=True, help="Path to left/reference PNG")
    parser.add_argument("--right", required=True, help="Path to right/compare PNG")
    parser.add_argument("--json-out", default="", help="Optional JSON output path")
    return parser.parse_args()


def sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_image(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def main() -> int:
    args = parse_args()
    left_path = Path(args.left).resolve()
    right_path = Path(args.right).resolve()

    left_exists = left_path.exists()
    right_exists = right_path.exists()
    left_hash = sha256_bytes(left_path) if left_exists else ""
    right_hash = sha256_bytes(right_path) if right_exists else ""
    byte_identical = bool(left_hash and right_hash and left_hash == right_hash)

    mean_abs_diff = 0.0
    max_abs_diff = 0.0
    changed_pixel_ratio = 0.0
    strong_changed_pixel_ratio = 0.0
    shape_match = False

    left_img = load_image(left_path)
    right_img = load_image(right_path)
    if left_img is not None and right_img is not None:
        shape_match = left_img.shape == right_img.shape
        if shape_match:
            diff = cv2.absdiff(left_img, right_img)
            mean_abs_diff = float(np.mean(diff))
            max_abs_diff = float(np.max(diff))
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            changed_pixel_ratio = float(np.mean(gray_diff > 0))
            strong_changed_pixel_ratio = float(np.mean(gray_diff >= 16))

    result = {
        "left_path": str(left_path),
        "right_path": str(right_path),
        "left_exists": left_exists,
        "right_exists": right_exists,
        "left_sha256": left_hash,
        "right_sha256": right_hash,
        "byte_identical": byte_identical,
        "shape_match": shape_match,
        "mean_abs_diff": mean_abs_diff,
        "max_abs_diff": max_abs_diff,
        "changed_pixel_ratio": changed_pixel_ratio,
        "strong_changed_pixel_ratio": strong_changed_pixel_ratio,
    }

    if args.json_out:
        out = Path(args.json_out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"LEFT_EXISTS={'true' if left_exists else 'false'}")
    print(f"RIGHT_EXISTS={'true' if right_exists else 'false'}")
    print(f"BYTE_IDENTICAL={'true' if byte_identical else 'false'}")
    print(f"SHAPE_MATCH={'true' if shape_match else 'false'}")
    print(f"MEAN_ABS_DIFF={mean_abs_diff:.6f}")
    print(f"MAX_ABS_DIFF={max_abs_diff:.6f}")
    print(f"CHANGED_PIXEL_RATIO={changed_pixel_ratio:.6f}")
    print(f"STRONG_CHANGED_PIXEL_RATIO={strong_changed_pixel_ratio:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
