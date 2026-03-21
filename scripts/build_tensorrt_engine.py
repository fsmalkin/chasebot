#!/usr/bin/env python3
"""Deterministic TensorRT engine build helper using trtexec."""

import argparse
import json
import os
import pathlib
import subprocess
import sys
from typing import Dict

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TensorRT engine from ONNX.")
    parser.add_argument("--config", required=True, help="Path to calibration config YAML.")
    parser.add_argument("--onnx", required=True, help="Path to ONNX model.")
    parser.add_argument("--engine-out", default="", help="Override output engine path.")
    parser.add_argument("--dry-run", action="store_true", help="Print command without execution.")
    return parser.parse_args()


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    precision = (cfg.get("precision") or {}).get("target", "int8").lower()
    flags = cfg.get("build_flags") or {}
    workspace_mb = int(flags.get("workspace_mb", 4096))
    timing_cache = flags.get("timing_cache", "")

    onnx_path = pathlib.Path(args.onnx).expanduser().resolve()
    if not onnx_path.is_file():
        print(f"[ERROR] ONNX file not found: {onnx_path}", file=sys.stderr)
        return 2

    engine_out = args.engine_out or cfg.get("engine_output", "runtime/tensorrt/engines/ball_detector_int8.engine")
    engine_path = pathlib.Path(engine_out).expanduser().resolve()
    engine_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "trtexec",
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
        f"--workspace={workspace_mb}",
        "--builderOptimizationLevel=5",
        "--skipInference",
        "--verbose",
    ]

    if precision == "int8":
        cmd.append("--int8")
        calibration_cache = (cfg.get("cache_file") or "").strip()
        if calibration_cache:
            cache_path = pathlib.Path(calibration_cache).expanduser().resolve()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cmd.append(f"--calib={cache_path}")
    elif precision == "fp16":
        cmd.append("--fp16")

    if timing_cache:
        timing_path = pathlib.Path(timing_cache).expanduser().resolve()
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.append(f"--timingCacheFile={timing_path}")

    print("TRTEXEC_COMMAND=" + " ".join(cmd))
    if args.dry_run:
        return 0

    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        print("[ERROR] trtexec not found on PATH.", file=sys.stderr)
        return 3

    build_log = {
        "command": cmd,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout.splitlines()[-80:],
        "stderr_tail": completed.stderr.splitlines()[-80:],
    }
    log_path = engine_path.with_suffix(engine_path.suffix + ".buildlog.json")
    with open(log_path, "w", encoding="utf-8") as fp:
        json.dump(build_log, fp, indent=2)

    if completed.returncode != 0:
        print(f"[ERROR] trtexec failed. Log: {log_path}", file=sys.stderr)
        return completed.returncode

    print("TRT_ENGINE_BUILD_OK=1")
    print(f"TRT_ENGINE_PATH={engine_path}")
    print(f"TRT_ENGINE_LOG={log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
