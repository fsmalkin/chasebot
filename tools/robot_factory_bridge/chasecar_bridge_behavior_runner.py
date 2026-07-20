#!/usr/bin/env python3
"""Camera-gated behavior runner for the Chasecar factory bridge."""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
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

DEFAULT_VISUAL_SCAN_PROFILES = ("yellow", "orange", "red", "green", "blue", "bright", "any-saturated")


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


def parse_visual_scan_profiles(raw_profiles):
    allowed = set(DEFAULT_VISUAL_SCAN_PROFILES)
    profiles = []
    for raw_profile in str(raw_profiles or "").split(","):
        profile = raw_profile.strip()
        if not profile:
            continue
        if profile not in allowed:
            raise ValueError("unsupported_visual_scan_profile:%s" % profile)
        if profile not in profiles:
            profiles.append(profile)
    return profiles or list(DEFAULT_VISUAL_SCAN_PROFILES)


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
    status, image = bridge_client.snapshot_with_retries(client)
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
                diff_bytes = diff.tobytes()
                channel_count = max(len(diff_bytes), 1)
                pixel_count = max(len(diff_bytes) // 3, 1)
                abs_sum = sum(diff_bytes)
                metrics["before_vs_%s" % labels[index].replace(" ", "_")] = {
                    "mean_abs_diff": abs_sum / channel_count,
                    "max_abs_diff": max(diff_bytes) if diff_bytes else 0,
                    "strong_changed_pixel_ratio": (
                        sum(
                            1
                            for offset in range(0, len(diff_bytes), 3)
                            if max(diff_bytes[offset : offset + 3]) >= 16
                        )
                        / pixel_count
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


def image_edge_profile(image_path, sample_width=160, sample_height=120):
    from PIL import Image, ImageFilter

    image_path = Path(image_path)
    image = (
        Image.open(image_path)
        .convert("L")
        .filter(ImageFilter.GaussianBlur(radius=2.0))
        .resize((sample_width, sample_height))
    )
    pixels = image.load()
    y_start = int(sample_height * 0.15)
    y_end = int(sample_height * 0.88)
    profile = []
    for x_coord in range(sample_width - 1):
        total = 0.0
        count = 0
        for y_coord in range(y_start, y_end):
            total += abs(pixels[x_coord + 1, y_coord] - pixels[x_coord, y_coord])
            count += 1
        profile.append(total / max(count, 1))
    mean = sum(profile) / max(len(profile), 1)
    profile = [value - mean for value in profile]
    norm = math.sqrt(sum(value * value for value in profile))
    if norm <= 0.0:
        return []
    return [value / norm for value in profile]


def shifted_profile_score(base_profile, compare_profile, shift):
    if shift < 0:
        base_window = base_profile[-shift:]
        compare_window = compare_profile[: len(base_window)]
    elif shift > 0:
        base_window = base_profile[:-shift]
        compare_window = compare_profile[shift:]
    else:
        base_window = base_profile
        compare_window = compare_profile
    if not base_window or not compare_window:
        return -1.0
    dot = sum(base_value * compare_value for base_value, compare_value in zip(base_window, compare_window))
    base_norm = math.sqrt(sum(value * value for value in base_window))
    compare_norm = math.sqrt(sum(value * value for value in compare_window))
    return dot / ((base_norm * compare_norm) + 1e-9)


def analyze_visual_motion(before_path, after_paths, labels, args):
    try:
        from PIL import Image
    except Exception as exc:
        return {
            "available": False,
            "movement_detected": False,
            "issues": ["pillow_unavailable:%r" % (exc,)],
        }

    before_path = Path(before_path)
    after_paths = [Path(path) for path in after_paths]
    labels = list(labels)
    if not after_paths:
        return {
            "available": True,
            "movement_detected": False,
            "issues": ["after_frames_missing"],
            "frames": [],
        }

    before_width = Image.open(before_path).size[0]
    base_profile = image_edge_profile(before_path)
    if not base_profile:
        return {
            "available": True,
            "movement_detected": False,
            "issues": ["visual_motion_texture_insufficient"],
            "before_path": str(before_path),
            "frames": [],
        }
    sample_scale = before_width / max(len(base_profile) + 1, 1)
    max_shift = max(1, min(80, len(base_profile) - 1))
    frames = []
    for index, after_path in enumerate(after_paths):
        compare_profile = image_edge_profile(after_path)
        if not compare_profile:
            frames.append(
                {
                    "label": labels[index] if index < len(labels) else "after_%02d" % (index + 1),
                    "path": str(after_path),
                    "movement_detected": False,
                    "issues": ["visual_motion_texture_insufficient"],
                }
            )
            continue
        zero_shift_score = shifted_profile_score(base_profile, compare_profile, 0)
        best_shift, best_score = max(
            (
                (shift, shifted_profile_score(base_profile, compare_profile, shift))
                for shift in range(-max_shift, max_shift + 1)
            ),
            key=lambda item: item[1],
        )
        best_shift_px = best_shift * sample_scale
        shift_detected = (
            abs(best_shift_px) >= float(args.min_visual_shift_px)
            and best_score >= zero_shift_score + float(args.min_visual_shift_score_gain)
        )
        scene_change_detected = zero_shift_score <= float(args.max_static_visual_similarity)
        frames.append(
            {
                "label": labels[index] if index < len(labels) else "after_%02d" % (index + 1),
                "path": str(after_path),
                "zero_shift_similarity": zero_shift_score,
                "best_shift_similarity": best_score,
                "best_shift_px": best_shift_px,
                "shift_detected": bool(shift_detected),
                "scene_change_detected": bool(scene_change_detected),
                "movement_detected": bool(shift_detected or scene_change_detected),
            }
        )

    movement_detected = any(frame["movement_detected"] for frame in frames)
    issues = [] if movement_detected else ["visual_motion_not_confirmed"]
    return {
        "available": True,
        "movement_detected": bool(movement_detected),
        "issues": issues,
        "before_path": str(before_path),
        "thresholds": {
            "min_visual_shift_px": float(args.min_visual_shift_px),
            "min_visual_shift_score_gain": float(args.min_visual_shift_score_gain),
            "max_static_visual_similarity": float(args.max_static_visual_similarity),
        },
        "frames": frames,
    }


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def target_pixel_match(red, green, blue, profile, args):
    red_unit = red / 255.0
    green_unit = green / 255.0
    blue_unit = blue / 255.0
    hue, saturation, value = colorsys.rgb_to_hsv(red_unit, green_unit, blue_unit)
    hue_degrees = hue * 360.0
    luma = (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)
    if profile == "bright":
        return luma >= args.target_min_luma
    if profile == "any-saturated":
        return saturation >= args.target_min_saturation and value >= args.target_min_value
    if profile == "yellow":
        return 35.0 <= hue_degrees <= 75.0 and saturation >= args.target_min_saturation and value >= args.target_min_value
    if profile == "orange":
        return 10.0 <= hue_degrees <= 40.0 and saturation >= args.target_min_saturation and value >= args.target_min_value
    if profile == "green":
        return 75.0 <= hue_degrees <= 165.0 and saturation >= args.target_min_saturation and value >= args.target_min_value
    if profile == "blue":
        return 180.0 <= hue_degrees <= 260.0 and saturation >= args.target_min_saturation and value >= args.target_min_value
    if profile == "red":
        red_hue = hue_degrees <= 20.0 or hue_degrees >= 335.0
        return red_hue and saturation >= args.target_min_saturation and value >= args.target_min_value
    return False


def component_summary(area, sum_x, sum_y, min_x, min_y, max_x, max_y, width, height, border_margin_ratio=0.0):
    centroid_x = sum_x / max(area, 1)
    centroid_y = sum_y / max(area, 1)
    margin_x = max(0, int(round(width * float(border_margin_ratio))))
    margin_y = max(0, int(round(height * float(border_margin_ratio))))
    touches_border = bool(
        area
        and (
            min_x <= margin_x
            or min_y <= margin_y
            or max_x >= (width - 1 - margin_x)
            or max_y >= (height - 1 - margin_y)
        )
    )
    return {
        "matched_pixels": area,
        "area_ratio": area / max(width * height, 1),
        "bbox_width_ratio": ((max_x - min_x + 1) / width) if area else 0.0,
        "bbox_height_ratio": ((max_y - min_y + 1) / height) if area else 0.0,
        "bbox_aspect_ratio": ((max_x - min_x + 1) / max((max_y - min_y + 1), 1)) if area else 0.0,
        "centroid": {"x": centroid_x, "y": centroid_y} if area else None,
        "centroid_y_ratio": (centroid_y / height) if area else None,
        "bbox": {"x0": min_x, "y0": min_y, "x1": max_x, "y1": max_y} if area else None,
        "bbox_center_y_ratio": (((min_y + max_y) / 2.0) / height) if area else None,
        "bbox_bottom_ratio": (max_y / height) if area else None,
        "center_error": ((centroid_x - (width / 2.0)) / (width / 2.0)) if area else None,
        "touches_border": touches_border,
    }


def find_target_components(image, args):
    width, height = image.size
    pixels = image.load()
    border_margin_ratio = float(args.target_border_margin_ratio)
    mask = []
    total_matched = 0
    aggregate = {"area": 0, "sum_x": 0.0, "sum_y": 0.0, "min_x": width, "min_y": height, "max_x": -1, "max_y": -1}
    for y_coord in range(height):
        row = bytearray(width)
        for x_coord in range(width):
            red, green, blue = pixels[x_coord, y_coord]
            if target_pixel_match(red, green, blue, args.target_profile, args):
                row[x_coord] = 1
                total_matched += 1
                aggregate["area"] += 1
                aggregate["sum_x"] += x_coord
                aggregate["sum_y"] += y_coord
                aggregate["min_x"] = min(aggregate["min_x"], x_coord)
                aggregate["min_y"] = min(aggregate["min_y"], y_coord)
                aggregate["max_x"] = max(aggregate["max_x"], x_coord)
                aggregate["max_y"] = max(aggregate["max_y"], y_coord)
        mask.append(row)

    seen = [bytearray(width) for _ in range(height)]
    components = []
    for y_coord in range(height):
        for x_coord in range(width):
            if not mask[y_coord][x_coord] or seen[y_coord][x_coord]:
                continue
            stack = [(x_coord, y_coord)]
            seen[y_coord][x_coord] = 1
            area = 0
            sum_x = 0.0
            sum_y = 0.0
            min_x = width
            min_y = height
            max_x = -1
            max_y = -1
            while stack:
                x_current, y_current = stack.pop()
                area += 1
                sum_x += x_current
                sum_y += y_current
                min_x = min(min_x, x_current)
                min_y = min(min_y, y_current)
                max_x = max(max_x, x_current)
                max_y = max(max_y, y_current)
                for x_next, y_next in (
                    (x_current + 1, y_current),
                    (x_current - 1, y_current),
                    (x_current, y_current + 1),
                    (x_current, y_current - 1),
                ):
                    if (
                        0 <= x_next < width
                        and 0 <= y_next < height
                        and mask[y_next][x_next]
                        and not seen[y_next][x_next]
                    ):
                        seen[y_next][x_next] = 1
                        stack.append((x_next, y_next))
            summary = component_summary(
                area,
                sum_x,
                sum_y,
                min_x,
                min_y,
                max_x,
                max_y,
                width,
                height,
                border_margin_ratio,
            )
            summary["issues"] = component_issues(summary, args)
            components.append(summary)

    components.sort(
        key=lambda component: (
            bool(component.get("issues")),
            -float(component.get("area_ratio", 0.0) or 0.0),
            abs(float(component.get("center_error", 999.0) or 999.0)),
        )
    )
    aggregate_summary = component_summary(
        aggregate["area"],
        aggregate["sum_x"],
        aggregate["sum_y"],
        aggregate["min_x"],
        aggregate["min_y"],
        aggregate["max_x"],
        aggregate["max_y"],
        width,
        height,
        border_margin_ratio,
    )
    aggregate_summary["issues"] = component_issues(aggregate_summary, args)
    return total_matched, aggregate_summary, components


def component_issues(summary, args):
    issues = []
    matched = int(summary.get("matched_pixels", 0) or 0)
    area_ratio = float(summary.get("area_ratio", 0.0) or 0.0)
    bbox_width_ratio = float(summary.get("bbox_width_ratio", 0.0) or 0.0)
    bbox_height_ratio = float(summary.get("bbox_height_ratio", 0.0) or 0.0)
    bbox_aspect_ratio = float(summary.get("bbox_aspect_ratio", 0.0) or 0.0)
    centroid_y_ratio = summary.get("centroid_y_ratio")
    min_centroid_y_ratio = float(getattr(args, "target_min_centroid_y_ratio", 0.0) or 0.0)
    max_centroid_y_ratio = float(getattr(args, "target_max_centroid_y_ratio", 1.0) or 1.0)
    if matched <= 0:
        issues.append("target_not_detected")
    if area_ratio < args.target_min_area_ratio:
        issues.append("target_area_below_threshold")
    if area_ratio > args.target_max_area_ratio:
        issues.append("target_area_above_threshold")
    if bbox_width_ratio > args.target_max_bbox_width_ratio:
        issues.append("target_bbox_width_above_threshold")
    if bbox_height_ratio > args.target_max_bbox_height_ratio:
        issues.append("target_bbox_height_above_threshold")
    if float(args.target_border_margin_ratio) > 0.0 and bool(summary.get("touches_border", False)):
        issues.append("target_touches_image_border")
    if bbox_aspect_ratio < float(args.target_min_bbox_aspect_ratio):
        issues.append("target_bbox_aspect_below_threshold")
    if float(args.target_max_bbox_aspect_ratio) > 0.0 and bbox_aspect_ratio > float(args.target_max_bbox_aspect_ratio):
        issues.append("target_bbox_aspect_above_threshold")
    if centroid_y_ratio is not None and centroid_y_ratio < min_centroid_y_ratio:
        issues.append("target_centroid_y_below_threshold")
    if centroid_y_ratio is not None and centroid_y_ratio > max_centroid_y_ratio:
        issues.append("target_centroid_y_above_threshold")
    return issues


def analyze_target_image(image_path, args, annotated_path=None):
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        return {
            "detected": False,
            "issues": ["pillow_unavailable:%r" % (exc,)],
            "image_path": str(image_path),
        }

    image_path = Path(image_path)
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    total_matched, aggregate, components = find_target_components(image, args)
    valid_components = [component for component in components if not component.get("issues")]
    target = valid_components[0] if valid_components else aggregate
    issues = [] if valid_components else list(aggregate.get("issues", []))
    if total_matched > 0 and not valid_components and "target_component_not_detected" not in issues:
        issues.append("target_component_not_detected")

    matched = int(target.get("matched_pixels", 0) or 0)
    area_ratio = float(target.get("area_ratio", 0.0) or 0.0)
    bbox_width_ratio = float(target.get("bbox_width_ratio", 0.0) or 0.0)
    bbox_height_ratio = float(target.get("bbox_height_ratio", 0.0) or 0.0)
    bbox_aspect_ratio = float(target.get("bbox_aspect_ratio", 0.0) or 0.0)
    centroid = target.get("centroid")
    bbox = target.get("bbox")
    detected = bool(valid_components)
    centroid_x = centroid.get("x") if centroid else None
    centroid_y = centroid.get("y") if centroid else None
    center_error = target.get("center_error")
    centered = abs(center_error or 0.0) <= args.visual_center_deadband
    angular_z = 0.0
    linear_x = 0.0
    if detected and center_error is not None:
        angular_z = clamp(
            -float(args.visual_turn_sign) * center_error * float(args.visual_angular_gain),
            -float(args.max_visual_angular_z),
            float(args.max_visual_angular_z),
        )
        if args.allow_forward and centered and area_ratio < args.forward_stop_area_ratio:
            linear_x = clamp(float(args.visual_forward_x), 0.0, float(args.max_visual_linear_x))

    annotated = ""
    if annotated_path:
        annotated_path = Path(annotated_path)
        ensure_dir(annotated_path.parent)
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        if bbox:
            outline = (0, 255, 0) if detected else (255, 0, 0)
            draw.rectangle((bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]), outline=outline, width=3)
            draw.line((width / 2, 0, width / 2, height), fill=(255, 255, 255), width=1)
            if centroid_x is not None and centroid_y is not None:
                draw.ellipse((centroid_x - 5, centroid_y - 5, centroid_x + 5, centroid_y + 5), outline=outline, width=2)
        annotated_image.save(annotated_path, quality=90)
        annotated = str(annotated_path)

    return {
        "detected": bool(detected),
        "issues": issues,
        "image_path": str(image_path),
        "annotated_image_path": annotated,
        "target_profile": args.target_profile,
        "image_width": width,
        "image_height": height,
        "matched_pixels": matched,
        "total_matched_pixels": total_matched,
        "area_ratio": area_ratio,
        "bbox_width_ratio": bbox_width_ratio,
        "bbox_height_ratio": bbox_height_ratio,
        "bbox_aspect_ratio": bbox_aspect_ratio,
        "centroid": {"x": centroid_x, "y": centroid_y} if centroid_x is not None else None,
        "bbox": bbox,
        "component_count": len(components),
        "component_candidates": components[:8],
        "center_error": center_error,
        "centered": bool(centered and detected),
        "recommendation": {
            "linear_x": linear_x,
            "angular_z": angular_z,
            "duration_s": float(args.visual_command_duration_s),
            "source": "factory_behavior_runner:visual_advisor",
        },
    }


def visual_scan_sort_key(analysis):
    detected_rank = 0 if analysis.get("detected", False) else 1
    profile_rank = int(analysis.get("profile_rank", 999))
    area_ratio = float(analysis.get("area_ratio", 0.0) or 0.0)
    center_error = analysis.get("center_error")
    center_rank = abs(float(center_error)) if center_error is not None else 999.0
    return (detected_rank, profile_rank, -area_ratio, center_rank)


def analyze_visual_scan(image_path, args, artifact_dir):
    results = []
    profiles = parse_visual_scan_profiles(args.visual_scan_profiles)
    for profile_rank, profile in enumerate(profiles):
        profile_args = SimpleNamespace(**vars(args))
        profile_args.target_profile = profile
        annotated_path = artifact_dir / ("visual_scan_%s.jpg" % profile.replace("-", "_"))
        analysis = analyze_target_image(image_path, profile_args, annotated_path=annotated_path)
        analysis["profile_rank"] = profile_rank
        recommendation = dict(analysis.get("recommendation", {}))
        recommendation["source"] = "factory_behavior_runner:visual_scan:%s" % profile
        analysis["recommendation"] = recommendation
        results.append(analysis)

    ranked = sorted(results, key=visual_scan_sort_key)
    detected = [analysis for analysis in ranked if analysis.get("detected", False)]
    return {
        "profiles": profiles,
        "ranked_profiles": [analysis.get("target_profile") for analysis in ranked],
        "detected_profiles": [analysis.get("target_profile") for analysis in detected],
        "best_candidate": detected[0] if detected else None,
        "results": ranked,
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


def run_plan_refusal_check(client, args, summary, initial_health):
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
    if bool(initial_health.get("motion_enabled", False)):
        summary["steps"].append(
            {
                "label": "plan_refusal_skipped",
                "reason": "bridge_motion_enabled",
            }
        )
        append_issue(summary, "bridge_motion_enabled_for_plan_refusal")
        return

    for step in plan["steps"]:
        try:
            status, payload = client.cmd_vel(
                step["linear_x"],
                step["angular_z"],
                step["duration_s"],
                "factory_behavior_runner:plan_refusal:%s" % step["label"],
            )
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
                    "expected_refusal": False,
                }
            )
            append_issue(summary, "plan_refusal_unexpected_success:%s" % step["label"])
        except bridge_client.BridgeHttpError as exc:
            expected = exc.status_code == 423
            summary["steps"].append(
                {
                    "label": step["label"],
                    "request": {
                        "linear_x": step["linear_x"],
                        "angular_z": step["angular_z"],
                        "duration_s": step["duration_s"],
                    },
                    "http_status": exc.status_code,
                    "response": exc.payload,
                    "expected_refusal": expected,
                }
            )
            if not expected:
                append_issue(summary, "plan_refusal_status_unexpected:%s:%s" % (step["label"], exc.status_code))


def run_visual_scan(client, args, artifact_dir, summary):
    snapshot = save_snapshot(client, artifact_dir / "visual_scan_frame.jpg")
    scan = analyze_visual_scan(snapshot["output"], args, artifact_dir)
    best = scan.get("best_candidate")
    summary["artifacts"]["visual_scan_snapshot"] = snapshot
    summary["artifacts"]["visual_scan"] = scan
    if best:
        summary["steps"].append(
            {
                "label": "visual_scan_best_candidate",
                "target_profile": best.get("target_profile"),
                "recommendation": best.get("recommendation", {}),
                "center_error": best.get("center_error"),
                "area_ratio": best.get("area_ratio"),
                "annotated_image_path": best.get("annotated_image_path", ""),
            }
        )
        return
    summary["steps"].append(
        {
            "label": "visual_scan_noop",
            "reason": "visual_target_not_detected",
            "detected_profiles": scan.get("detected_profiles", []),
            "ranked_profiles": scan.get("ranked_profiles", []),
        }
    )
    if args.require_target:
        append_issue(summary, "visual_target_not_detected")


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
        motion_evidence = analyze_visual_motion(before["output"], after_paths, labels[1:], args)
        summary["artifacts"]["visual_motion_evidence"] = motion_evidence
        if args.require_visual_motion and not motion_evidence.get("movement_detected", False):
            append_issue(summary, "visual_motion_not_confirmed")


def run_visual_advisor(client, args, artifact_dir, summary, initial_health):
    snapshot = save_snapshot(client, artifact_dir / "visual_advisor_frame.jpg")
    analysis = analyze_target_image(
        snapshot["output"],
        args,
        annotated_path=artifact_dir / "visual_advisor_annotated.jpg",
    )
    summary["artifacts"]["visual_advisor_snapshot"] = snapshot
    summary["artifacts"]["visual_advisor_analysis"] = analysis
    if not analysis.get("detected", False):
        summary["steps"].append(
            {
                "label": "visual_advisor_noop",
                "reason": "visual_target_not_detected",
                "analysis_issues": analysis.get("issues", []),
                "recommendation": analysis.get("recommendation", {}),
            }
        )
        if args.require_target:
            append_issue(summary, "visual_target_not_detected")
        return
    if not args.execute_motion:
        return
    if not args.confirm_operator_ready:
        append_issue(summary, "operator_ready_confirmation_required")
        return
    if not bool(initial_health.get("motion_enabled", False)):
        append_issue(summary, "bridge_motion_not_enabled")
        return
    recommendation = analysis.get("recommendation", {})
    linear_x = float(recommendation.get("linear_x", 0.0))
    angular_z = float(recommendation.get("angular_z", 0.0))
    duration_s = float(recommendation.get("duration_s", args.visual_command_duration_s))
    if abs(linear_x) > float(args.max_visual_linear_x):
        append_issue(summary, "visual_linear_x_above_limit")
        return
    if abs(angular_z) > float(args.max_visual_angular_z):
        append_issue(summary, "visual_angular_z_above_limit")
        return
    if duration_s > float(args.max_step_duration_s):
        append_issue(summary, "visual_duration_above_limit")
        return
    motion_started = False
    try:
        status, payload = client.cmd_vel(
            linear_x,
            angular_z,
            duration_s,
            recommendation.get("source", "factory_behavior_runner:visual_advisor"),
        )
        motion_started = True
        summary["steps"].append(
            {
                "label": "visual_advisor_cmd_vel",
                "request": {
                    "linear_x": linear_x,
                    "angular_z": angular_z,
                    "duration_s": duration_s,
                },
                "http_status": status,
                "response": payload,
            }
        )
        if args.visual_post_settle_s > 0:
            time.sleep(args.visual_post_settle_s)
        diagnostics = bridge_client.run_camera_diagnostics(
            client,
            camera_diag_args(args, artifact_dir / "visual_advisor_after_frames"),
        )
        summary["artifacts"]["visual_advisor_after_camera_diagnostics"] = diagnostics
        if not camera_ready(diagnostics):
            append_issue(summary, "visual_advisor_post_camera_diagnostics_not_pass")
    finally:
        if motion_started:
            try:
                status, payload = client.stop("factory_behavior_runner:visual_advisor_finally_stop")
                summary["artifacts"]["visual_advisor_finally_stop"] = {
                    "http_status": status,
                    "response": payload,
                }
            except Exception as exc:  # pragma: no cover - defensive hardware cleanup
                append_issue(summary, "visual_advisor_finally_stop_failed:%r" % (exc,))


def run(args):
    artifact_dir = ensure_dir(args.artifact_dir or default_artifact_dir(args.mode))
    summary = build_summary(args, artifact_dir)
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    if args.dry_run:
        summary["pass"] = True
        summary["dry_run_plan"] = load_plan(args) if args.mode in ("tiny-turn", "plan-refusal") else None
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
    elif args.mode == "plan-refusal":
        if not summary["issues"]:
            run_plan_refusal_check(client, args, summary, initial_health)
    elif args.mode == "visual-scan":
        if not summary["issues"]:
            run_visual_scan(client, args, artifact_dir, summary)
    elif args.mode == "visual-advisor":
        if not summary["issues"]:
            run_visual_advisor(client, args, artifact_dir, summary, initial_health)
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
    parser.add_argument(
        "--mode",
        choices=("readiness", "no-motion-command", "tiny-turn", "plan-refusal", "visual-scan", "visual-advisor"),
        default="readiness",
    )
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
    parser.add_argument("--require-visual-motion", action="store_true")
    parser.add_argument("--min-visual-shift-px", type=float, default=12.0)
    parser.add_argument("--min-visual-shift-score-gain", type=float, default=0.03)
    parser.add_argument("--max-static-visual-similarity", type=float, default=0.82)

    parser.add_argument(
        "--target-profile",
        choices=("bright", "any-saturated", "yellow", "orange", "red", "green", "blue"),
        default="yellow",
    )
    parser.add_argument("--target-min-luma", type=float, default=180.0)
    parser.add_argument("--target-min-saturation", type=float, default=0.35)
    parser.add_argument("--target-min-value", type=float, default=0.35)
    parser.add_argument("--target-min-area-ratio", type=float, default=0.0008)
    parser.add_argument("--target-max-area-ratio", type=float, default=0.20)
    parser.add_argument("--target-max-bbox-width-ratio", type=float, default=0.70)
    parser.add_argument("--target-max-bbox-height-ratio", type=float, default=0.70)
    parser.add_argument("--target-border-margin-ratio", type=float, default=0.0)
    parser.add_argument("--target-min-bbox-aspect-ratio", type=float, default=0.0)
    parser.add_argument("--target-max-bbox-aspect-ratio", type=float, default=0.0)
    parser.add_argument("--target-min-centroid-y-ratio", type=float, default=0.0)
    parser.add_argument("--target-max-centroid-y-ratio", type=float, default=1.0)
    parser.add_argument("--visual-scan-profiles", default=",".join(DEFAULT_VISUAL_SCAN_PROFILES))
    parser.add_argument("--require-target", action="store_true")
    parser.add_argument("--visual-center-deadband", type=float, default=0.16)
    parser.add_argument("--visual-turn-sign", type=float, default=1.0)
    parser.add_argument("--visual-angular-gain", type=float, default=0.8)
    parser.add_argument("--max-visual-angular-z", type=float, default=0.45)
    parser.add_argument("--allow-forward", action="store_true")
    parser.add_argument("--visual-forward-x", type=float, default=0.03)
    parser.add_argument("--max-visual-linear-x", type=float, default=0.04)
    parser.add_argument("--forward-stop-area-ratio", type=float, default=0.08)
    parser.add_argument("--visual-command-duration-s", type=float, default=0.20)
    parser.add_argument("--visual-post-settle-s", type=float, default=0.30)
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
