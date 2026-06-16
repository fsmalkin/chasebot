#!/usr/bin/env python3
"""Camera-gated behavior runner for the Chasecar factory bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import time

import chasecar_bridge_client as bridge_client


DEFAULT_TINY_TURN_PLAN = {
    "name": "tiny_turn_v1",
    "description": "One in-place Chasecar-style cmd_vel turn pulse.",
    "steps": [
        {
            "label": "in_place_turn_left",
            "linear_x": 0.0,
            "angular_z": 2.5,
            "duration_s": 0.30,
            "settle_s": 0.25,
        }
    ],
}


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def ensure_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, payload):
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def camera_diag_args(args, output_dir):
    return SimpleNamespace(
        frames=args.camera_frames,
        interval_s=args.camera_interval_s,
        output_dir=str(output_dir),
        min_fps=args.min_camera_fps,
        max_frame_age_s=args.max_frame_age_s,
        min_frame_bytes=args.min_frame_bytes,
    )


def camera_ready(diagnostics):
    return bool(diagnostics.get("pass", False)) and not diagnostics.get("issues")


def camera_block(health):
    if isinstance(health, dict) and isinstance(health.get("camera"), dict):
        return health["camera"]
    return {}


def default_artifact_dir(mode):
    return Path("artifacts") / "session" / ("factory_bridge_%s_%s" % (mode.replace("-", "_"), utc_stamp()))


def normalized_step(raw_step, index):
    step = dict(raw_step)
    step.setdefault("label", "step_%02d" % (index + 1))
    step["linear_x"] = float(step.get("linear_x", 0.0))
    step["angular_z"] = float(step.get("angular_z", 0.0))
    step["duration_s"] = float(step.get("duration_s", 0.0))
    step["settle_s"] = max(0.0, float(step.get("settle_s", 0.0)))
    return step


def load_plan(args):
    if args.plan_file:
        payload = load_json(args.plan_file)
    else:
        payload = DEFAULT_TINY_TURN_PLAN
    if not isinstance(payload, dict):
        raise ValueError("plan_json_must_be_object")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan_steps_required")
    plan = dict(payload)
    plan["steps"] = [normalized_step(step, index) for index, step in enumerate(steps)]
    return plan


def validate_plan(plan, args):
    issues = []
    for step in plan["steps"]:
        label = step["label"]
        if abs(step["linear_x"]) > float(args.max_abs_linear_x):
            issues.append("step_linear_x_above_limit:%s" % label)
        if abs(step["angular_z"]) > float(args.max_abs_angular_z):
            issues.append("step_angular_z_above_limit:%s" % label)
        if step["duration_s"] <= 0:
            issues.append("step_duration_missing:%s" % label)
        if step["duration_s"] > float(args.max_step_duration_s):
            issues.append("step_duration_above_limit:%s" % label)
    return issues


def save_snapshot(client, output_path):
    status, image = client.snapshot()
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    output_path.write_bytes(image)
    return {
        "http_status": status,
        "output": str(output_path),
        "bytes": len(image),
        "sha256": sha256_file(output_path),
    }


def maybe_make_contact_sheet(paths, labels, output_path):
    try:
        from PIL import Image, ImageChops, ImageDraw
    except Exception as exc:
        return {
            "available": False,
            "error": repr(exc),
        }

    try:
        thumbs = []
        for path, label in zip(paths, labels):
            image = Image.open(path).convert("RGB")
            image.thumbnail((320, 240))
            tile = Image.new("RGB", (320, 270), "white")
            tile.paste(image, ((320 - image.width) // 2, 24))
            draw = ImageDraw.Draw(tile)
            draw.text((8, 6), label, fill=(0, 0, 0))
            thumbs.append(tile)

        columns = min(3, max(1, len(thumbs)))
        rows = (len(thumbs) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * 320, rows * 270), (245, 246, 248))
        for index, tile in enumerate(thumbs):
            sheet.paste(tile, ((index % columns) * 320, (index // columns) * 270))
        output_path = Path(output_path)
        ensure_dir(output_path.parent)
        sheet.save(output_path, quality=90)

        metrics = {}
        if len(paths) >= 2:
            base = Image.open(paths[0]).convert("RGB")
            for index, path in enumerate(paths[1:], start=1):
                compare = Image.open(path).convert("RGB")
                if compare.size != base.size:
                    compare = compare.resize(base.size)
                diff = ImageChops.difference(base, compare)
                pixels = list(diff.getdata())
                channel_count = max(len(pixels) * 3, 1)
                abs_sum = sum(red + green + blue for red, green, blue in pixels)
                metrics["before_vs_%s" % labels[index].replace(" ", "_")] = {
                    "mean_abs_diff": abs_sum / channel_count,
                    "max_abs_diff": max(max(pixel) for pixel in pixels) if pixels else 0,
                    "strong_changed_pixel_ratio": (
                        sum(1 for pixel in pixels if max(pixel) >= 16) / max(len(pixels), 1)
                    ),
                }
        return {
            "available": True,
            "output": str(output_path),
            "metrics": metrics,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": repr(exc),
        }


def build_summary(args, artifact_dir):
    return {
        "generated_utc": utc_now(),
        "mode": args.mode,
        "base_url": bridge_client.normalize_base_url(args.base_url),
        "artifact_dir": str(artifact_dir),
        "dry_run": bool(args.dry_run),
        "execute_motion": bool(args.execute_motion),
        "operator_ready": bool(args.confirm_operator_ready),
        "pass": False,
        "issues": [],
        "readiness": {},
        "plan": None,
        "steps": [],
        "artifacts": {},
    }


def append_issue(summary, issue):
    summary.setdefault("issues", []).append(issue)


def run_readiness_gate(client, args, artifact_dir, summary):
    health_status, health = client.health()
    summary["readiness"]["initial_health_status"] = health_status
    summary["readiness"]["initial_health"] = health
    diagnostics = bridge_client.run_camera_diagnostics(
        client,
        camera_diag_args(args, artifact_dir / "camera_gate"),
    )
    summary["readiness"]["camera_diagnostics"] = diagnostics
    if health_status != 200 or not bool(health.get("ok", False)):
        append_issue(summary, "bridge_health_not_ok")
    if not camera_ready(diagnostics):
        append_issue(summary, "camera_diagnostics_not_pass")
    return health


def run_no_motion_command(client, args, summary):
    try:
        status, payload = client.cmd_vel(
            args.refusal_linear_x,
            args.refusal_angular_z,
            args.refusal_duration_s,
            "factory_behavior_runner:no_motion_refusal",
        )
        summary["steps"].append(
            {
                "label": "no_motion_refusal",
                "http_status": status,
                "response": payload,
            }
        )
        append_issue(summary, "expected_motion_refusal_but_command_succeeded")
    except bridge_client.BridgeHttpError as exc:
        summary["steps"].append(
            {
                "label": "no_motion_refusal",
                "http_status": exc.status_code,
                "response": exc.payload,
                "expected_refusal": exc.status_code == 423,
            }
        )
        if exc.status_code != 423:
            append_issue(summary, "motion_refusal_status_unexpected:%s" % exc.status_code)


def execute_motion_plan(client, args, artifact_dir, summary, initial_health):
    if not args.execute_motion:
        append_issue(summary, "execute_motion_required")
        return
    if not args.confirm_operator_ready:
        append_issue(summary, "operator_ready_confirmation_required")
        return
    if not bool(initial_health.get("motion_enabled", False)):
        append_issue(summary, "bridge_motion_not_enabled")
        return

    plan = load_plan(args)
    plan_issues = validate_plan(plan, args)
    summary["plan"] = plan
    summary["plan_limits"] = {
        "max_abs_linear_x": float(args.max_abs_linear_x),
        "max_abs_angular_z": float(args.max_abs_angular_z),
        "max_step_duration_s": float(args.max_step_duration_s),
    }
    summary["issues"].extend(plan_issues)
    if plan_issues:
        return

    before = save_snapshot(client, artifact_dir / "before.jpg")
    summary["artifacts"]["before_snapshot"] = before
    after_paths = []
    motion_started = False
    try:
        for step in plan["steps"]:
            status, payload = client.cmd_vel(
                step["linear_x"],
                step["angular_z"],
                step["duration_s"],
                "factory_behavior_runner:%s" % step["label"],
            )
            motion_started = True
            summary["steps"].append(
                {
                    "label": step["label"],
                    "request": {
                        "linear_x": step["linear_x"],
                        "angular_z": step["angular_z"],
                        "duration_s": step["duration_s"],
                    },
                    "http_status": status,
                    "response": payload,
                }
            )
            if step["settle_s"] > 0:
                time.sleep(step["settle_s"])
        diagnostics = bridge_client.run_camera_diagnostics(
            client,
            camera_diag_args(args, artifact_dir / "after_frames"),
        )
        summary["artifacts"]["after_camera_diagnostics"] = diagnostics
        after_paths = [frame["output"] for frame in diagnostics.get("frames", [])]
        if not camera_ready(diagnostics):
            append_issue(summary, "post_motion_camera_diagnostics_not_pass")
    finally:
        if motion_started:
            try:
                status, payload = client.stop("factory_behavior_runner:finally_stop")
                summary["artifacts"]["finally_stop"] = {
                    "http_status": status,
                    "response": payload,
                }
            except Exception as exc:  # pragma: no cover - defensive hardware cleanup
                append_issue(summary, "finally_stop_failed:%r" % (exc,))

    if after_paths:
        labels = ["before"] + ["after %02d" % (index + 1) for index in range(len(after_paths))]
        contact_sheet = maybe_make_contact_sheet(
            [before["output"]] + after_paths,
            labels,
            artifact_dir / "camera_contact_sheet.jpg",
        )
        summary["artifacts"]["contact_sheet"] = contact_sheet


def run(args):
    artifact_dir = ensure_dir(args.artifact_dir or default_artifact_dir(args.mode))
    summary = build_summary(args, artifact_dir)
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    if args.dry_run:
        summary["pass"] = True
        summary["dry_run_plan"] = load_plan(args) if args.mode == "tiny-turn" else None
        write_json(artifact_dir / "behavior_summary.json", summary)
        return summary

    initial_health = run_readiness_gate(client, args, artifact_dir, summary)
    if args.mode == "readiness":
        pass
    elif args.mode == "no-motion-command":
        if not summary["issues"]:
            run_no_motion_command(client, args, summary)
    elif args.mode == "tiny-turn":
        if not summary["issues"]:
            execute_motion_plan(client, args, artifact_dir, summary, initial_health)
    else:
        append_issue(summary, "unsupported_mode:%s" % args.mode)

    try:
        final_status, final_health = client.health()
        summary["readiness"]["final_health_status"] = final_status
        summary["readiness"]["final_health"] = final_health
        if final_status != 200 or not bool(final_health.get("ok", False)):
            append_issue(summary, "final_health_not_ok")
        if abs(float(final_health.get("left_motor", 0.0))) > 0.0001:
            append_issue(summary, "final_left_motor_nonzero")
        if abs(float(final_health.get("right_motor", 0.0))) > 0.0001:
            append_issue(summary, "final_right_motor_nonzero")
    except Exception as exc:
        append_issue(summary, "final_health_failed:%r" % (exc,))

    summary["pass"] = not summary["issues"]
    summary_path = artifact_dir / "behavior_summary.json"
    summary["summary_path"] = str(summary_path)
    write_json(summary_path, summary)
    return summary


def build_parser():
    parser = argparse.ArgumentParser(description="Run a camera-gated behavior through the factory bridge.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CHASECAR_FACTORY_BRIDGE_URL", bridge_client.DEFAULT_BASE_URL),
    )
    parser.add_argument("--timeout-s", type=float, default=bridge_client.DEFAULT_TIMEOUT_S)
    parser.add_argument("--mode", choices=("readiness", "no-motion-command", "tiny-turn"), default="readiness")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    parser.add_argument("--camera-frames", type=int, default=8)
    parser.add_argument("--camera-interval-s", type=float, default=0.2)
    parser.add_argument("--min-camera-fps", type=float, default=2.0)
    parser.add_argument("--max-frame-age-s", type=float, default=1.0)
    parser.add_argument("--min-frame-bytes", type=int, default=100)

    parser.add_argument("--refusal-linear-x", type=float, default=0.05)
    parser.add_argument("--refusal-angular-z", type=float, default=0.0)
    parser.add_argument("--refusal-duration-s", type=float, default=0.1)

    parser.add_argument("--plan-file", default="")
    parser.add_argument("--execute-motion", action="store_true")
    parser.add_argument("--confirm-operator-ready", action="store_true")
    parser.add_argument("--max-abs-linear-x", type=float, default=0.05)
    parser.add_argument("--max-abs-angular-z", type=float, default=2.5)
    parser.add_argument("--max-step-duration-s", type=float, default=0.5)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        summary = run(args)
    except Exception as exc:
        summary = {
            "generated_utc": utc_now(),
            "mode": getattr(args, "mode", ""),
            "pass": False,
            "issues": ["runner_exception:%r" % (exc,)],
        }
        artifact_dir = ensure_dir(getattr(args, "artifact_dir", "") or default_artifact_dir(getattr(args, "mode", "error")))
        summary["summary_path"] = str(artifact_dir / "behavior_summary.json")
        write_json(summary["summary_path"], summary)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass") else 1


if __name__ == "__main__":
    sys.exit(main())
