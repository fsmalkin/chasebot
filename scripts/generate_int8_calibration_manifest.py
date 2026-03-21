#!/usr/bin/env python3
"""Create a deterministic image manifest for TensorRT INT8 calibration."""

import argparse
import json
import pathlib
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate INT8 calibration manifest.")
    parser.add_argument("--images", required=True, help="Directory containing calibration images.")
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of images.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_dir = pathlib.Path(args.images).expanduser().resolve()
    if not image_dir.is_dir():
        print(f"[ERROR] image directory not found: {image_dir}", file=sys.stderr)
        return 2

    candidates = []
    for pattern in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        candidates.extend(image_dir.glob(pattern))
    candidates = sorted({path.resolve() for path in candidates})

    if args.limit > 0:
        candidates = candidates[: args.limit]

    manifest = {
        "dataset_root": str(image_dir),
        "count": len(candidates),
        "images": [str(path) for path in candidates],
    }

    out = pathlib.Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2)

    print("INT8_MANIFEST_OK=1")
    print(f"INT8_MANIFEST_PATH={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
