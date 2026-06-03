#!/usr/bin/env python3
"""Build a mobile-watchable fetch UAT evidence package."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
PACKAGE_KIND = "fetch_visual_uat_package"
VIDEO_MIN_BYTES = 1024
VIDEO_NAMES = (
    "raw_camera_browser.mp4",
    "yolo_debug_browser.mp4",
    "topdown_telemetry_browser.mp4",
    "world_stream.mp4",
    "yolo_debug.mp4",
    "raw_camera.mp4",
    "topdown_telemetry.mp4",
)
REQUIRED_MOBILE_VIDEO_NAMES = frozenset(
    {
        "raw_camera_browser.mp4",
        "world_stream.mp4",
        "topdown_telemetry_browser.mp4",
    }
)
ONBOARD_VIDEO_NAMES = frozenset({"raw_camera_browser.mp4", "raw_camera.mp4", "yolo_debug_browser.mp4", "yolo_debug.mp4"})
BROWSER_COMPATIBLE_VIDEO_NAMES = frozenset(
    {
        "raw_camera_browser.mp4",
        "yolo_debug_browser.mp4",
        "topdown_telemetry_browser.mp4",
        "world_stream.mp4",
    }
)
KEYFRAME_RECOVERY_MIN_FRAMES = 3
KEYFRAME_REVIEW_OUTPUT_NAME = "keyframe_review_contact_sheet.png"
KEYFRAME_REVIEW_MAX_FRAMES = 10
KEYFRAME_REVIEW_THUMBNAIL_SIZE = (220, 124)
KEYFRAME_REVIEW_LABEL_HEIGHT_PX = 22
KEYFRAME_REVIEW_GAP_PX = 6
KEYFRAME_VIDEO_RECOVERY_SPECS = (
    {
        "output_name": "raw_camera_browser.mp4",
        "frame_dir": "keyframes",
        "frame_glob": "*_raw.png",
        "source": "raw_keyframes",
    },
    {
        "output_name": "topdown_telemetry_browser.mp4",
        "frame_dir": "keyframes",
        "frame_glob": "*_topdown.png",
        "source": "topdown_keyframes",
    },
    {
        "output_name": "world_stream.mp4",
        "frame_dir": "world_stream_frames",
        "frame_glob": "*.jpg",
        "source": "world_stream_frames",
    },
)


def _select_evenly_spaced(items: list[Any], limit: int) -> list[Any]:
    if limit <= 0 or len(items) <= limit:
        return list(items)
    last_index = len(items) - 1
    selected_indexes = []
    for index in range(limit):
        selected = round(index * last_index / max(1, limit - 1))
        if selected not in selected_indexes:
            selected_indexes.append(selected)
    return [items[index] for index in selected_indexes]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def artifact_url(path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(SESSION_ROOT.resolve())
    except ValueError:
        return ""
    return "/artifacts/session/" + rel.as_posix()


def compact_validation_error(value: Any) -> str:
    return " ".join(str(value or "").strip().split())[:320]


def inspect_video_file(path: Path) -> dict[str, Any]:
    size_bytes = int(path.stat().st_size) if path.is_file() else 0
    result: dict[str, Any] = {
        "size_bytes": size_bytes,
        "ffprobe_valid": False,
        "browser_playable": False,
        "codec_name": "",
        "pix_fmt": "",
        "duration_s": 0.0,
        "validation_error": "",
    }
    if size_bytes < VIDEO_MIN_BYTES:
        result["validation_error"] = "video_missing_or_tiny"
        return result
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,pix_fmt,width,height",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except FileNotFoundError:
        result["validation_error"] = "ffprobe_not_found"
        return result
    except subprocess.TimeoutExpired:
        result["validation_error"] = "ffprobe_timeout"
        return result
    if completed.returncode != 0:
        result["validation_error"] = compact_validation_error(
            completed.stderr or completed.stdout or f"ffprobe_exit_{completed.returncode}"
        )
        return result
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        result["validation_error"] = "ffprobe_invalid_json"
        return result
    streams = payload.get("streams", [])
    stream = streams[0] if streams and isinstance(streams[0], dict) else {}
    if not stream:
        result["validation_error"] = "ffprobe_no_video_stream"
        return result
    codec = str(stream.get("codec_name", "") or "")
    pix_fmt = str(stream.get("pix_fmt", "") or "")
    try:
        duration_s = float((payload.get("format", {}) or {}).get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        duration_s = 0.0
    result.update(
        {
            "ffprobe_valid": duration_s > 0.0,
            "browser_playable": bool(codec == "h264" and pix_fmt == "yuv420p" and duration_s > 0.0),
            "codec_name": codec,
            "pix_fmt": pix_fmt,
            "duration_s": round(duration_s, 6),
        }
    )
    if not result["ffprobe_valid"]:
        result["validation_error"] = "ffprobe_invalid_duration"
    elif not result["browser_playable"]:
        result["validation_error"] = f"not_browser_h264_yuv420p:codec={codec}:pix_fmt={pix_fmt}"
    return result


def _write_ffconcat(frames: list[Path], list_path: Path, *, frame_duration_s: float = 0.2) -> None:
    lines = ["ffconcat version 1.0"]
    for frame in frames:
        safe_path = frame.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{safe_path}'")
        lines.append(f"duration {frame_duration_s:.6f}")
    if frames:
        safe_path = frames[-1].resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{safe_path}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _transcode_frame_sequence(
    *,
    frames: list[Path],
    output_path: Path,
    color_range_fix: bool,
) -> tuple[bool, str]:
    concat_path = output_path.with_suffix(f"{output_path.suffix}.ffconcat")
    _write_ffconcat(frames, concat_path)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
    ]
    if color_range_fix:
        command.extend(["-vf", "scale=in_range=pc:out_range=tv,format=yuv420p"])
    command.extend(
        [
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    except FileNotFoundError:
        return False, "ffmpeg_not_found"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg_timeout"
    finally:
        try:
            concat_path.unlink()
        except FileNotFoundError:
            pass
    if completed.returncode != 0:
        return False, compact_validation_error(completed.stderr or completed.stdout or f"ffmpeg_exit_{completed.returncode}")
    probe = inspect_video_file(output_path)
    if not probe.get("browser_playable", False):
        return False, str(probe.get("validation_error", "") or "browser_video_validation_failed")
    return True, ""


def recover_browser_videos(visual_dir: Path) -> list[dict[str, Any]]:
    """Recover browser-watchable videos from saved keyframes when recorders fail."""
    results: list[dict[str, Any]] = []
    if not visual_dir.is_dir():
        return results
    for spec in KEYFRAME_VIDEO_RECOVERY_SPECS:
        output_name = str(spec["output_name"])
        output_path = visual_dir / output_name
        current_probe = inspect_video_file(output_path)
        if current_probe.get("browser_playable", False):
            continue
        frame_dir = visual_dir / str(spec["frame_dir"])
        frames = sorted(frame_dir.glob(str(spec["frame_glob"]))) if frame_dir.is_dir() else []
        result = {
            "output_name": output_name,
            "path": artifact_display_path(output_path),
            "source": str(spec["source"]),
            "attempted": False,
            "ok": False,
            "frame_count": len(frames),
            "previous_validation_error": str(current_probe.get("validation_error", "") or ""),
            "error": "",
        }
        if len(frames) < KEYFRAME_RECOVERY_MIN_FRAMES:
            result["error"] = "insufficient_frames"
            results.append(result)
            continue
        result["attempted"] = True
        ok, error = _transcode_frame_sequence(
            frames=frames,
            output_path=output_path,
            color_range_fix=output_name == "world_stream.mp4",
        )
        result["ok"] = bool(ok)
        result["error"] = error
        results.append(result)
    return results


def _keyframe_prefix(path: Path, suffix: str) -> str:
    name = path.name
    return name[: -len(suffix)] if name.endswith(suffix) else path.stem


def build_keyframe_review(visual_dir: Path) -> dict[str, Any]:
    """Create a compact sequence review from onboard and topdown keyframes."""
    output_path = visual_dir / KEYFRAME_REVIEW_OUTPUT_NAME
    result: dict[str, Any] = {
        "output_name": KEYFRAME_REVIEW_OUTPUT_NAME,
        "session_id": session_id_for_path(visual_dir),
        "path": artifact_display_path(output_path),
        "url": "",
        "source": "raw_topdown_keyframes",
        "attempted": False,
        "ok": False,
        "raw_frame_count": 0,
        "topdown_frame_count": 0,
        "paired_frame_count": 0,
        "selected_count": 0,
        "selected_frame_ids": [],
        "error": "",
        "review_instruction": "inspect_onboard_and_topdown_sequence_not_only_end_frame",
    }
    keyframes_dir = visual_dir / "keyframes"
    if not keyframes_dir.is_dir():
        result["error"] = "missing_keyframes_dir"
        return result
    raw_frames = sorted(keyframes_dir.glob("*_raw.png"))
    topdown_by_prefix = {
        _keyframe_prefix(path, "_topdown.png"): path for path in sorted(keyframes_dir.glob("*_topdown.png"))
    }
    result["raw_frame_count"] = len(raw_frames)
    result["topdown_frame_count"] = len(topdown_by_prefix)
    pairs: list[tuple[str, Path, Path]] = []
    for raw_path in raw_frames:
        frame_id = _keyframe_prefix(raw_path, "_raw.png")
        topdown_path = topdown_by_prefix.get(frame_id)
        if topdown_path is not None:
            pairs.append((frame_id, raw_path, topdown_path))
    result["paired_frame_count"] = len(pairs)
    if len(pairs) < KEYFRAME_RECOVERY_MIN_FRAMES:
        result["error"] = "insufficient_paired_keyframes"
        return result

    result["attempted"] = True
    selected = _select_evenly_spaced(pairs, KEYFRAME_REVIEW_MAX_FRAMES)
    result["selected_count"] = len(selected)
    result["selected_frame_ids"] = [frame_id for frame_id, _, _ in selected]
    try:
        from PIL import Image, ImageDraw, ImageOps
    except Exception:
        result["error"] = "pillow_not_available"
        return result

    thumb_width, thumb_height = KEYFRAME_REVIEW_THUMBNAIL_SIZE
    label_height = KEYFRAME_REVIEW_LABEL_HEIGHT_PX
    gap = KEYFRAME_REVIEW_GAP_PX
    columns = max(1, len(selected))
    rows = 2
    sheet_width = columns * thumb_width + (columns + 1) * gap
    sheet_height = rows * (thumb_height + label_height) + (rows + 1) * gap
    sheet = Image.new("RGB", (sheet_width, sheet_height), (248, 248, 248))
    draw = ImageDraw.Draw(sheet)

    def paste_tile(source_path: Path, column: int, row: int, label: str) -> None:
        x = gap + column * (thumb_width + gap)
        y = gap + row * (thumb_height + label_height + gap)
        with Image.open(source_path) as image:
            image = ImageOps.contain(image.convert("RGB"), (thumb_width, thumb_height))
            tile = Image.new("RGB", (thumb_width, thumb_height), (28, 28, 28))
            tile.paste(image, ((thumb_width - image.width) // 2, (thumb_height - image.height) // 2))
        sheet.paste(tile, (x, y + label_height))
        draw.text((x + 4, y + 4), label, fill=(20, 20, 20))
        draw.rectangle((x, y + label_height, x + thumb_width - 1, y + label_height + thumb_height - 1), outline=(120, 120, 120))

    try:
        for column, (frame_id, raw_path, topdown_path) in enumerate(selected):
            paste_tile(raw_path, column, 0, f"{frame_id} raw")
            paste_tile(topdown_path, column, 1, f"{frame_id} topdown")
        ensure_dir(output_path.parent)
        sheet.save(output_path)
    except Exception as exc:
        result["error"] = compact_validation_error(exc)
        return result

    result["ok"] = output_path.is_file() and output_path.stat().st_size > 0
    result["url"] = artifact_url(output_path) if result["ok"] else ""
    if not result["ok"]:
        result["error"] = "contact_sheet_not_written"
    return result


def finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def geometry_pose(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    x_value = finite_float(value.get("x"))
    y_value = finite_float(value.get("y"))
    if x_value is None or y_value is None:
        return {}
    payload: dict[str, Any] = {"x": round(x_value, 6), "y": round(y_value, 6)}
    z_value = finite_float(value.get("z"))
    radius_value = finite_float(value.get("radius_m", value.get("radius")))
    if z_value is not None:
        payload["z"] = round(z_value, 6)
    if radius_value is not None:
        payload["radius_m"] = round(radius_value, 6)
    return payload


def infer_geometry_consistency(source: dict[str, Any]) -> dict[str, Any]:
    existing = source.get("geometry_consistency") if isinstance(source.get("geometry_consistency"), dict) else {}
    if existing:
        return dict(existing)
    fetch_pose = geometry_pose(source.get("fetch_pose_world", {}))
    marker_pose = geometry_pose(source.get("visible_delivery_marker_pose", source.get("zone_pose", {})))
    if not fetch_pose and isinstance(source.get("requested_fetch_pose_world"), dict):
        fetch_pose = geometry_pose(source.get("requested_fetch_pose_world", {}))
    if not fetch_pose or not marker_pose:
        return {}
    center_delta_m = math.hypot(float(fetch_pose["x"]) - float(marker_pose["x"]), float(fetch_pose["y"]) - float(marker_pose["y"]))
    fetch_radius = finite_float(fetch_pose.get("radius_m"))
    marker_radius = finite_float(marker_pose.get("radius_m"))
    radius_delta_m = abs(float(fetch_radius) - float(marker_radius)) if fetch_radius is not None and marker_radius is not None else None
    reason = "matched"
    if center_delta_m > 0.02:
        reason = "center_mismatch"
    elif radius_delta_m is None:
        reason = "missing_radius"
    elif radius_delta_m > 0.01:
        reason = "radius_mismatch"
    return {
        "pass": reason == "matched",
        "reason": reason,
        "center_delta_m": round(center_delta_m, 6),
        "radius_delta_m": round(float(radius_delta_m), 6) if radius_delta_m is not None else None,
        "fetch_pose_world": fetch_pose,
        "visible_delivery_marker_pose": marker_pose,
        "source": "fetch_visual_uat_package",
    }


def extract_model_provenance(source: dict[str, Any]) -> dict[str, Any]:
    existing = source.get("model_provenance") if isinstance(source.get("model_provenance"), dict) else {}
    if existing:
        payload = dict(existing)
    else:
        payload = {}
        for key in (
            "target_model_sdf",
            "zone_model_sdf",
            "target_model_radius_m",
            "target_model_classification",
            "zone_model_radius_m",
            "zone_model_classification",
            "model_provenance_valid",
            "model_provenance_reason",
            "model_provenance_required",
        ):
            if key in source:
                payload[key] = source.get(key)
    if not payload:
        return {
            "model_provenance_valid": False,
            "model_provenance_reason": "missing_model_provenance",
        }
    if "model_provenance_valid" not in payload:
        target_class = str(payload.get("target_model_classification", "") or "")
        zone_class = str(payload.get("zone_model_classification", "") or "")
        payload["model_provenance_valid"] = bool(
            target_class == "calibrated_golf_ball"
            and zone_class == "golf_ball_delivery_zone_marker"
        )
    if not str(payload.get("model_provenance_reason", "") or ""):
        payload["model_provenance_reason"] = (
            "calibrated_fetch_models"
            if bool(payload.get("model_provenance_valid", False))
            else "invalid_or_missing_model_provenance"
        )
    return payload


def session_id_for_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(SESSION_ROOT.resolve())
    except ValueError:
        return ""
    return rel.parts[0] if rel.parts else ""


def summarize_planner_gate(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {}
    candidates = payload.get("candidate_families", [])
    if isinstance(candidates, list) and candidates:
        candidate_results = [item for item in candidates if isinstance(item, dict)]
        one_run_results = [
            result
            for candidate in candidate_results
            for result in candidate.get("one_run_results", [])
            if isinstance(result, dict)
        ]
        pass_count = sum(1 for result in one_run_results if bool(result.get("pass", False)))
        fail_count = sum(1 for result in one_run_results if not bool(result.get("pass", False)))
        decision_green = any(
            bool(
                (
                    candidate.get("decision")
                    if isinstance(candidate.get("decision"), dict)
                    else {}
                ).get("one_run_green", candidate.get("one_run_green", False))
            )
            for candidate in candidate_results
        )
        route_counts = {
            str(result.get("layout_id", "") or result.get("campaign_id", "")): 1 if bool(result.get("pass", False)) else 0
            for result in one_run_results
        }
        return {
            "campaign_id": str(payload.get("campaign_id", "") or ""),
            "session_id": session_id_for_path(path),
            "path": artifact_display_path(path),
            "pass": bool(decision_green or (one_run_results and fail_count == 0)),
            "planner_mode": "calibrated_fetch_architecture_revisit",
            "scene_set": str(payload.get("screen_scope", "") or ""),
            "scene_source": str(payload.get("type", "") or ""),
            "pass_count": int(pass_count),
            "fail_count": int(fail_count),
            "total_count": int(len(one_run_results)),
            "fetch_dispatch_count": int(pass_count),
            "wrong_fetch_dispatch_count": 0,
            "route_counts": route_counts,
        }
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "session_id": session_id_for_path(path),
        "path": artifact_display_path(path),
        "pass": bool(payload.get("pass", False)),
        "planner_mode": str(payload.get("planner_mode", "") or ""),
        "scene_set": str(payload.get("scene_set", "") or ""),
        "scene_source": str(payload.get("scene_source", "") or ""),
        "pass_count": int(payload.get("pass_count", 0) or 0),
        "fail_count": int(payload.get("fail_count", 0) or 0),
        "total_count": int(payload.get("random_cases", 0) or 0),
        "fetch_dispatch_count": int(payload.get("fetch_dispatch_count", 0) or 0),
        "wrong_fetch_dispatch_count": int(payload.get("wrong_fetch_dispatch_count", 0) or 0),
        "route_counts": payload.get("route_counts", {}) if isinstance(payload.get("route_counts"), dict) else {},
    }


def summarize_seeded_evidence(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    seeded = payload.get("seeded_gate", payload.get("seeded_shadow_gate", {}))
    seeded = seeded if isinstance(seeded, dict) else {}
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "session_id": session_id_for_path(path),
        "path": artifact_display_path(path),
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
        "milestone_interpretation": str(payload.get("milestone_interpretation", "") or ""),
        "recommended_next_action": str(payload.get("recommended_next_action", "") or ""),
        "seeded_pass": bool(seeded.get("pass", False)),
        "seeded_pass_count": int(seeded.get("pass_count", 0) or 0),
        "seeded_fail_count": int(seeded.get("fail_count", 0) or 0),
        "guarded_live_candidate_count": int(seeded.get("guarded_live_candidate_count", 0) or 0),
        "non_repro_failure_count": int(seeded.get("non_repro_failure_count", 0) or 0),
        "reproduced_failure_count": int(seeded.get("reproduced_failure_count", 0) or 0),
        "model_provenance_valid": bool(seeded.get("model_provenance_valid", False)),
        "model_provenance_invalid_count": int(seeded.get("model_provenance_invalid_count", 0) or 0),
    }


def summarize_stage_quality(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    rows = payload.get("saved_anchors", []) if isinstance(payload.get("saved_anchors"), list) else []
    invalid_model_count = int(payload.get("invalid_model_provenance_count", 0) or 0)
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "session_id": session_id_for_path(path),
        "path": artifact_display_path(path),
        "green": bool(payload.get("stage_quality_green", False)) and invalid_model_count == 0,
        "overall_interpretation": str(payload.get("overall_interpretation", "") or ""),
        "pass_count": int(payload.get("stage_quality_pass_count", payload.get("pass_count", 0)) or 0),
        "total_count": int(payload.get("saved_anchor_count", len(rows)) or 0),
        "setup_contact_blocker_count": int(payload.get("setup_contact_blocker_count", 0) or 0),
        "setup_capture_blocker_count": int(payload.get("setup_capture_blocker_count", 0) or 0),
        "first_contact_blocker_count": int(payload.get("first_contact_blocker_count", 0) or 0),
        "push_coast_blocker_count": int(payload.get("push_coast_blocker_count", 0) or 0),
        "invalid_geometry_count": int(payload.get("invalid_geometry_count", 0) or 0),
        "invalid_model_provenance_count": invalid_model_count,
        "watch_count": int(payload.get("saved_anchor_pass_with_contact_watch_count", 0) or 0),
        "saved_anchors": [
            {
                "layout": str(row.get("layout", "") or ""),
                "pass": bool(row.get("pass", False)),
                "delivery_pass": bool(row.get("delivery_pass", False)),
                "quality_classification": str(row.get("quality_classification", "") or ""),
                "quality_flags": row.get("quality_flags", []) if isinstance(row.get("quality_flags"), list) else [],
                "model_provenance_valid": bool(row.get("model_provenance_valid", False)),
                "model_provenance_reason": str(row.get("model_provenance_reason", "") or ""),
                "pre_stage_yaw_travel_max_deg": row.get("pre_stage_yaw_travel_max_deg"),
                "capture_yaw_travel_max_deg": row.get("capture_yaw_travel_max_deg"),
                "capture_yaw_span_max_deg": row.get("capture_yaw_span_max_deg"),
                "capture_yaw_sign_crossing_max": row.get("capture_yaw_sign_crossing_max"),
                "capture_entry_time_max_s": row.get("capture_entry_time_max_s"),
            }
            for row in rows
            if isinstance(row, dict)
        ],
    }


def summarize_mission(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    runs = payload.get("runs", []) if isinstance(payload.get("runs"), list) else []
    first_run = runs[0] if runs and isinstance(runs[0], dict) else {}
    mission_verdict = payload.get("mission_verdict", {}) if isinstance(payload.get("mission_verdict"), dict) else {}
    if not mission_verdict and isinstance(first_run.get("mission_verdict"), dict):
        mission_verdict = first_run.get("mission_verdict", {})
    planner_route: dict[str, Any] = {}
    for candidate in (payload.get("planner_route"), mission_verdict.get("planner_route"), first_run.get("planner_route")):
        if isinstance(candidate, dict):
            planner_route.update(candidate)
    shot_outcome: dict[str, Any] = {}
    for candidate in (payload.get("shot_outcome"), mission_verdict.get("shot_outcome"), first_run.get("shot_outcome")):
        if isinstance(candidate, dict):
            shot_outcome.update(candidate)

    def pick_text(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    geometry_source: dict[str, Any] = {}
    for candidate in (payload, mission_verdict, first_run):
        if isinstance(candidate, dict):
            geometry_source.update(candidate)
    geometry_consistency = infer_geometry_consistency(geometry_source)
    geometry_ok = not geometry_consistency or bool(geometry_consistency.get("pass", False))
    model_provenance = extract_model_provenance(geometry_source)
    provenance_ok = bool(model_provenance.get("model_provenance_valid", False))
    pass_flag = bool(
        payload.get("pass", payload.get("promotion_gate_pass", mission_verdict.get("pass", first_run.get("mission_completed_pass", False))))
    )
    raw_fetch_pass = bool(
        payload.get("fetch_to_pose_pass_count", 0)
        or payload.get("fetch_to_pose_pass", False)
        or mission_verdict.get("fetch_to_pose_pass", False)
        or first_run.get("fetch_to_pose_pass", False)
    )
    fetch_pass = bool(raw_fetch_pass and geometry_ok and provenance_ok)
    session_id = str(
        mission_verdict.get("session_id", first_run.get("session_id", payload.get("session_id", session_id_for_path(path)))) or ""
    )
    route_label = pick_text(
        payload.get("planner_route_label"),
        mission_verdict.get("planner_route_label"),
        first_run.get("planner_route_label"),
        planner_route.get("planner_route_label"),
        planner_route.get("route_label"),
    )
    route_executor = pick_text(
        payload.get("route_executor"),
        mission_verdict.get("route_executor"),
        first_run.get("route_executor"),
        planner_route.get("route_executor"),
        planner_route.get("executor"),
    )
    closest_approach = payload.get(
        "closest_approach_distance_m",
        mission_verdict.get("closest_approach_distance_m", shot_outcome.get("closest_approach_distance_m")),
    )
    outcome_reason = pick_text(
        payload.get("reason"),
        mission_verdict.get("reason"),
        shot_outcome.get("reason"),
        payload.get("pass_reason"),
        mission_verdict.get("pass_reason"),
    )
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "session_id": session_id,
        "path": artifact_display_path(path),
        "planner_route_label": route_label,
        "route_executor": route_executor,
        "pass": bool(pass_flag and geometry_ok and provenance_ok),
        "fetch_to_pose_pass": fetch_pass,
        "raw_fetch_to_pose_pass": raw_fetch_pass,
        "fetch_to_pose_pass_count": int(payload.get("fetch_to_pose_pass_count", 1 if fetch_pass else 0) or 0) if fetch_pass else 0,
        "fetch_to_pose_fail_count": int(payload.get("fetch_to_pose_fail_count", 0 if fetch_pass else 1) or 0) if fetch_pass else 1,
        "ai_push_coast_mode": str(payload.get("ai_push_coast_mode", mission_verdict.get("ai_push_coast_mode", "")) or ""),
        "mission_objective": str(payload.get("mission_objective", mission_verdict.get("mission_objective", "")) or ""),
        "scenario_label": str(payload.get("scenario_label", mission_verdict.get("scenario_label", "")) or ""),
        "target_layout_json": str(payload.get("requested_target_layout_json", mission_verdict.get("target_layout_json", "")) or ""),
        "closest_approach_distance_m": closest_approach,
        "outcome_reason": outcome_reason,
        "failure_reasons": payload.get("fetch_to_pose_failure_reasons", mission_verdict.get("failure_reasons", [])),
        "geometry_consistency": geometry_consistency,
        "geometry_consistent": geometry_ok,
        "model_provenance": model_provenance,
        "model_provenance_valid": provenance_ok,
        "model_provenance_reason": str(model_provenance.get("model_provenance_reason", "") or ""),
        "target_model_sdf": str(model_provenance.get("target_model_sdf", "") or ""),
        "zone_model_sdf": str(model_provenance.get("zone_model_sdf", "") or ""),
        "target_model_radius_m": model_provenance.get("target_model_radius_m"),
        "target_model_classification": str(model_provenance.get("target_model_classification", "") or ""),
    }


def summarize_visual_dir(path: Path) -> dict[str, Any]:
    visual_summary = read_json(path / "visual_demo_summary.json")
    world_summary = read_json(path / "world_stream_summary.json")
    world_state = read_json(path / "world_stream_state.json")
    visual_state = read_json(path / "state.json")
    visual_pass = bool(visual_summary.get("pass", False))
    state_frame_count = int(world_state.get("frame_count", 0) or 0)
    summary_frame_count = int(world_summary.get("frame_count", 0) or 0)
    state_world_pass = bool(
        world_state.get("world_stream_ready", False)
        and world_state.get("world_stream_renderable", False)
        and world_state.get("same_session_partition", True)
    )
    world_source = world_summary
    if state_world_pass and state_frame_count >= summary_frame_count:
        world_source = {**world_summary, **world_state, "pass": True, "failure_class": ""}
    world_pass = bool(world_summary.get("pass", False) or state_world_pass)
    keyframes_dir = path / "keyframes"
    keyframe_counts = {
        "raw": len(list(keyframes_dir.glob("*_raw.png"))) if keyframes_dir.is_dir() else 0,
        "debug": len(list(keyframes_dir.glob("*_debug.png"))) if keyframes_dir.is_dir() else 0,
        "topdown": len(list(keyframes_dir.glob("*_topdown.png"))) if keyframes_dir.is_dir() else 0,
    }
    raw_frame_count = int(visual_summary.get("raw_frame_count", visual_state.get("raw_frame_count", 0)) or 0)
    telemetry_frame_count = int(
        visual_summary.get("telemetry_frame_count", visual_state.get("telemetry_frame_count", 0)) or 0
    )
    raw_nonblank = bool(visual_summary.get("raw_nonblank", visual_state.get("raw_nonblank", False)))
    debug_nonblank = bool(visual_summary.get("debug_nonblank", visual_state.get("debug_nonblank", False)))
    keyframe_recovery_pass = bool(
        not visual_pass
        and raw_nonblank
        and debug_nonblank
        and raw_frame_count >= KEYFRAME_RECOVERY_MIN_FRAMES
        and telemetry_frame_count >= KEYFRAME_RECOVERY_MIN_FRAMES
        and keyframe_counts["raw"] >= KEYFRAME_RECOVERY_MIN_FRAMES
        and keyframe_counts["topdown"] >= KEYFRAME_RECOVERY_MIN_FRAMES
        and bool(visual_state.get("true_target_seen", True))
        and bool(visual_state.get("truth_alignment_ok", True))
    )
    return {
        "session_id": session_id_for_path(path),
        "path": artifact_display_path(path),
        "visual_demo_pass": visual_pass,
        "world_stream_pass": world_pass,
        "visual_keyframe_recovery_pass": keyframe_recovery_pass,
        "visual_confirmation_pass": bool(visual_pass or world_pass or keyframe_recovery_pass),
        "visual_confirmation_source": (
            "visual_demo_summary" if visual_pass else "world_stream" if world_pass else "keyframe_recovery" if keyframe_recovery_pass else ""
        ),
        "raw_nonblank": raw_nonblank,
        "debug_nonblank": debug_nonblank,
        "target_persistence_ok": bool(visual_summary.get("target_persistence_ok", False)),
        "motion_progress_ok": bool(visual_summary.get("motion_progress_ok", False)),
        "target_visible_ratio": visual_summary.get("target_visible_ratio"),
        "raw_frame_count": raw_frame_count,
        "telemetry_frame_count": telemetry_frame_count,
        "keyframe_counts": keyframe_counts,
        "world_stream_degraded": bool(world_source.get("world_stream_degraded", False)),
        "world_stream_transport_healthy": bool(world_source.get("world_stream_transport_healthy", False)),
        "world_stream_failure_class": str(world_source.get("failure_class", "") or ""),
        "world_stream_frame_coverage_ratio": world_source.get("frame_coverage_ratio"),
        "world_stream_frame_count": int(world_source.get("frame_count", 0) or 0),
    }


def discover_videos(visual_dirs: list[Path]) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for visual_dir in visual_dirs:
        if not visual_dir.is_dir():
            continue
        for name in VIDEO_NAMES:
            path = (visual_dir / name).resolve()
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            probe = inspect_video_file(path)
            browser_compatible = name in BROWSER_COMPATIBLE_VIDEO_NAMES
            browser_playable = bool(browser_compatible and probe.get("browser_playable", False))
            videos.append(
                {
                    "name": name,
                    "role": "onboard_camera" if name in ONBOARD_VIDEO_NAMES else "external_context",
                    "browser_compatible": browser_compatible,
                    "browser_playable": browser_playable,
                    "ffprobe_valid": bool(probe.get("ffprobe_valid", False)),
                    "codec_name": str(probe.get("codec_name", "") or ""),
                    "pix_fmt": str(probe.get("pix_fmt", "") or ""),
                    "duration_s": probe.get("duration_s", 0.0),
                    "validation_error": str(probe.get("validation_error", "") or ""),
                    "path": artifact_display_path(path),
                    "url": artifact_url(path) if browser_playable else "",
                    "size_bytes": int(probe.get("size_bytes", path.stat().st_size) or 0),
                    "playable_candidate": browser_playable,
                }
            )
    return videos


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    planner_gates = [summarize_planner_gate(resolve_path(path)) for path in args.planner_summary]
    planner_gates = [item for item in planner_gates if item]
    seeded_evidence = [summarize_seeded_evidence(resolve_path(path)) for path in args.seeded_evidence_summary]
    seeded_evidence = [item for item in seeded_evidence if item]
    stage_quality_audits = [summarize_stage_quality(resolve_path(path)) for path in getattr(args, "stage_quality_summary", [])]
    stage_quality_audits = [item for item in stage_quality_audits if item]
    missions = [summarize_mission(resolve_path(path)) for path in args.mission_summary]
    missions = [item for item in missions if item]
    visual_dirs = [resolve_path(path) for path in args.visual_dir]
    video_recovery = [item for path in visual_dirs for item in recover_browser_videos(path)]
    keyframe_reviews = [build_keyframe_review(path) for path in visual_dirs if path.is_dir()]
    visual_summaries = [summarize_visual_dir(path) for path in visual_dirs if path.is_dir()]
    videos = discover_videos(visual_dirs)
    visual_by_session = {
        str(item.get("session_id", "") or ""): item
        for item in visual_summaries
        if str(item.get("session_id", "") or "")
    }

    planner_ok = bool(planner_gates) and all(
        gate.get("pass") and int(gate.get("wrong_fetch_dispatch_count", 0) or 0) == 0 for gate in planner_gates
    )
    raw_local_fetch_seen = any(mission.get("raw_fetch_to_pose_pass", mission.get("fetch_to_pose_pass")) for mission in missions)
    geometry_mismatch_seen = any(
        mission.get("raw_fetch_to_pose_pass", mission.get("fetch_to_pose_pass"))
        and not bool(mission.get("geometry_consistent", True))
        for mission in missions
    )
    model_provenance_invalid_seen = any(
        mission.get("raw_fetch_to_pose_pass", mission.get("fetch_to_pose_pass"))
        and not bool(mission.get("model_provenance_valid", False))
        for mission in missions
    )
    local_fetch_seen = any(mission.get("fetch_to_pose_pass") for mission in missions)
    visual_confirmation_seen = any(item.get("visual_confirmation_pass") for item in visual_summaries)
    local_fetch_visual_confirmed = any(
        mission.get("fetch_to_pose_pass")
        and visual_by_session.get(str(mission.get("session_id", "") or ""), {}).get("visual_confirmation_pass")
        for mission in missions
    )
    playable_core = {
        video["name"]
        for video in videos
        if video.get("url") and video.get("playable_candidate") and video.get("browser_compatible") and video.get("browser_playable")
    }
    onboard_camera_ok = "raw_camera_browser.mp4" in playable_core
    video_ok = REQUIRED_MOBILE_VIDEO_NAMES.issubset(playable_core)
    pass_flag = bool(planner_ok and local_fetch_seen and video_ok and local_fetch_visual_confirmed)
    warnings: list[str] = []
    if not planner_ok:
        warnings.append("planner_gate_not_green")
    if not local_fetch_seen:
        warnings.append("no_local_fetch_pass_seen")
    if geometry_mismatch_seen:
        warnings.append("fetch_marker_geometry_mismatch")
    if model_provenance_invalid_seen:
        warnings.append("fetch_model_provenance_invalid")
    if any(
        int(item.get("model_provenance_invalid_count", 0) or 0) > 0
        or (
            item.get("model_provenance_valid") is False
            and int(item.get("seeded_pass_count", 0) or 0) + int(item.get("seeded_fail_count", 0) or 0) > 0
        )
        for item in seeded_evidence
    ):
        warnings.append("seeded_model_provenance_invalid")
    if not video_ok:
        warnings.append("missing_or_tiny_required_mobile_video")
    if not onboard_camera_ok:
        warnings.append("missing_or_tiny_onboard_raw_camera_video")
    if not visual_confirmation_seen:
        warnings.append("no_healthy_visual_confirmation")
    if local_fetch_seen and not local_fetch_visual_confirmed:
        warnings.append("passing_local_fetch_lacks_same_session_visual_confirmation")
    if any(item.get("visual_keyframe_recovery_pass") for item in visual_summaries):
        warnings.append("visual_confirmation_keyframe_recovery")
    stage_quality_green = bool(stage_quality_audits and all(item.get("green", False) for item in stage_quality_audits))
    stage_quality_blocker_seen = any(
        int(item.get("setup_contact_blocker_count", 0) or 0) > 0
        or int(item.get("setup_capture_blocker_count", 0) or 0) > 0
        or int(item.get("first_contact_blocker_count", 0) or 0) > 0
        or int(item.get("push_coast_blocker_count", 0) or 0) > 0
        or int(item.get("invalid_geometry_count", 0) or 0) > 0
        or int(item.get("invalid_model_provenance_count", 0) or 0) > 0
        for item in stage_quality_audits
    )
    stage_quality_watch_seen = any(int(item.get("watch_count", 0) or 0) > 0 for item in stage_quality_audits)
    if stage_quality_blocker_seen:
        warnings.append("stage_quality_blocker")
    elif stage_quality_watch_seen:
        warnings.append("stage_quality_watch")

    return {
        "type": PACKAGE_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "pass": pass_flag,
        "mobile_watchable": video_ok,
        "onboard_camera_watchable": onboard_camera_ok,
        "visual_confirmation_seen": visual_confirmation_seen,
        "local_fetch_visual_confirmed": local_fetch_visual_confirmed,
        "planner_gate_green": planner_ok,
        "local_fetch_pass_seen": local_fetch_seen,
        "raw_local_fetch_pass_seen": raw_local_fetch_seen,
        "fetch_marker_geometry_mismatch_seen": geometry_mismatch_seen,
        "fetch_model_provenance_invalid_seen": model_provenance_invalid_seen,
        "stage_quality_green": stage_quality_green,
        "stage_quality_status": (
            "blocker" if stage_quality_blocker_seen else "watch" if stage_quality_watch_seen else "green" if stage_quality_green else ""
        ),
        "promotion_evidence": False,
        "milestone_interpretation": (
            "mobile_visual_uat_ready_not_promotion" if pass_flag else "mobile_visual_uat_incomplete"
        ),
        "warnings": warnings,
        "planner_gates": planner_gates,
        "seeded_evidence": seeded_evidence,
        "stage_quality_audits": stage_quality_audits,
        "video_recovery": video_recovery,
        "keyframe_reviews": keyframe_reviews,
        "missions": missions,
        "visual_summaries": visual_summaries,
        "videos": videos,
        "scorecard_path": "",
    }


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Visual UAT Package",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- mobile_watchable: `{summary.get('mobile_watchable', False)}`",
        f"- onboard_camera_watchable: `{summary.get('onboard_camera_watchable', False)}`",
        f"- visual_confirmation_seen: `{summary.get('visual_confirmation_seen', False)}`",
        f"- local_fetch_visual_confirmed: `{summary.get('local_fetch_visual_confirmed', False)}`",
        f"- planner_gate_green: `{summary.get('planner_gate_green', False)}`",
        f"- local_fetch_pass_seen: `{summary.get('local_fetch_pass_seen', False)}`",
        f"- raw_local_fetch_pass_seen: `{summary.get('raw_local_fetch_pass_seen', False)}`",
        f"- fetch_marker_geometry_mismatch_seen: `{summary.get('fetch_marker_geometry_mismatch_seen', False)}`",
        f"- fetch_model_provenance_invalid_seen: `{summary.get('fetch_model_provenance_invalid_seen', False)}`",
        f"- stage_quality_green: `{summary.get('stage_quality_green', False)}`",
        f"- stage_quality_status: `{summary.get('stage_quality_status', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        "",
        "## Videos",
    ]
    videos = summary.get("videos", []) if isinstance(summary.get("videos"), list) else []
    if videos:
        onboard = [
            video
            for video in videos
            if video.get("role") == "onboard_camera" and video.get("browser_compatible") and video.get("browser_playable")
        ]
        external = [
            video
            for video in videos
            if video.get("role") != "onboard_camera" and video.get("browser_compatible") and video.get("browser_playable")
        ]
        if onboard:
            lines.append("")
            lines.append("### Browser-Safe Onboard Camera")
            for video in onboard:
                name = str(video.get("name", "") or "")
                url = str(video.get("url", "") or "")
                lines.append(f"- [{name}]({url})" if url else f"- `{name}`")
        if external:
            lines.append("")
            lines.append("### Browser-Safe Context Views")
            for video in external:
                name = str(video.get("name", "") or "")
                url = str(video.get("url", "") or "")
                lines.append(f"- [{name}]({url})" if url else f"- `{name}`")
    else:
        lines.append("- none")
    lines.extend(["", "## All Video Artifacts"])
    if videos:
        for video in videos:
            name = str(video.get("name", "") or "")
            url = str(video.get("url", "") or "")
            validation = str(video.get("validation_error", "") or "")
            if url:
                lines.append(f"- [{name}]({url})")
            elif validation:
                lines.append(f"- `{name}` validation=`{validation}`")
            else:
                lines.append(f"- `{name}`")
    else:
        lines.append("- none")
    recovery_rows = summary.get("video_recovery", []) if isinstance(summary.get("video_recovery"), list) else []
    lines.extend(["", "## Video Recovery"])
    if recovery_rows:
        for item in recovery_rows:
            lines.append(
                f"- `{item.get('output_name', '')}` source=`{item.get('source', '')}` "
                f"ok=`{item.get('ok', False)}` frames=`{item.get('frame_count', 0)}` "
                f"previous=`{item.get('previous_validation_error', '')}` "
                f"error=`{item.get('error', '')}`"
            )
    else:
        lines.append("- none")
    review_rows = summary.get("keyframe_reviews", []) if isinstance(summary.get("keyframe_reviews"), list) else []
    lines.extend(["", "## Visual Keyframe Reviews"])
    if review_rows:
        for item in review_rows:
            name = str(item.get("output_name", "") or "")
            url = str(item.get("url", "") or "")
            label = f"[{name}]({url})" if url else f"`{name}`"
            lines.append(
                f"- {label} session=`{item.get('session_id', '')}` ok=`{item.get('ok', False)}` "
                f"selected=`{item.get('selected_count', 0)}` paired=`{item.get('paired_frame_count', 0)}` "
                f"source=`{item.get('source', '')}` error=`{item.get('error', '')}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Planner Gates"])
    for gate in summary.get("planner_gates", []) if isinstance(summary.get("planner_gates"), list) else []:
        lines.append(
            f"- `{gate.get('campaign_id', '')}` pass=`{gate.get('pass', False)}` "
            f"routes=`{gate.get('pass_count', 0)}/{gate.get('total_count', 0)}` "
            f"wrong_fetch=`{gate.get('wrong_fetch_dispatch_count', 0)}`"
        )
    lines.extend(["", "## Seeded Evidence"])
    seeded_rows = summary.get("seeded_evidence", []) if isinstance(summary.get("seeded_evidence"), list) else []
    if seeded_rows:
        for seeded in seeded_rows:
            lines.append(
                f"- `{seeded.get('campaign_id', '')}` "
                f"pass=`{seeded.get('seeded_pass_count', 0)}/{seeded.get('seeded_fail_count', 0)}` "
                f"model=`{seeded.get('model_provenance_valid', False)}` "
                f"invalid_model_provenance=`{seeded.get('model_provenance_invalid_count', 0)}` "
                f"interpretation=`{seeded.get('milestone_interpretation', '')}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Stage Quality"])
    stage_audits = summary.get("stage_quality_audits", []) if isinstance(summary.get("stage_quality_audits"), list) else []
    if stage_audits:
        for audit in stage_audits:
            lines.append(
                f"- `{audit.get('campaign_id', '')}` green=`{audit.get('green', False)}` "
                f"pass=`{audit.get('pass_count', 0)}/{audit.get('total_count', 0)}` "
                f"blockers=`{audit.get('setup_contact_blocker_count', 0)}` "
                f"invalid_model_provenance=`{audit.get('invalid_model_provenance_count', 0)}` "
                f"watch=`{audit.get('watch_count', 0)}` "
                f"interpretation=`{audit.get('overall_interpretation', '')}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Missions"])
    for mission in summary.get("missions", []) if isinstance(summary.get("missions"), list) else []:
        geometry = mission.get("geometry_consistency", {}) if isinstance(mission.get("geometry_consistency"), dict) else {}
        route_label = str(mission.get("planner_route_label", "") or mission.get("scenario_label", "") or mission.get("campaign_id", "") or "")
        session_id = str(mission.get("session_id", "") or "")
        closest = mission.get("closest_approach_distance_m")
        closest_text = ""
        if isinstance(closest, (int, float)) and math.isfinite(float(closest)):
            closest_text = f" closest=`{float(closest):.3f}m`"
        summary_path = str(mission.get("path", "") or "")
        summary_link = f" [summary](/{summary_path})" if summary_path.startswith("artifacts/session/") else ""
        lines.append(
            f"- route=`{route_label}` "
            f"session=`{session_id}` "
            f"fetch_to_pose=`{mission.get('fetch_to_pose_pass', False)}` "
            f"raw_fetch_to_pose=`{mission.get('raw_fetch_to_pose_pass', mission.get('fetch_to_pose_pass', False))}` "
            f"executor=`{mission.get('route_executor', '')}` "
            f"reason=`{mission.get('outcome_reason', '')}`"
            f"{closest_text} "
            f"geometry=`{geometry.get('pass', 'unknown')}` "
            f"geometry_reason=`{geometry.get('reason', '')}` "
            f"model_provenance=`{mission.get('model_provenance_valid', False)}` "
            f"target_model=`{mission.get('target_model_classification', '')}` "
            f"ai_mode=`{mission.get('ai_push_coast_mode', '')}`"
            f"{summary_link}"
        )
    lines.extend(["", "## Visual Evidence"])
    for visual in summary.get("visual_summaries", []) if isinstance(summary.get("visual_summaries"), list) else []:
        lines.append(
            f"- `{visual.get('path', '')}` confirmation=`{visual.get('visual_confirmation_pass', False)}` "
            f"visual_demo=`{visual.get('visual_demo_pass', False)}` "
            f"world_stream=`{visual.get('world_stream_pass', False)}` "
            f"target_persistence=`{visual.get('target_persistence_ok', False)}` "
            f"world_degraded=`{visual.get('world_stream_degraded', False)}` "
            f"world_failure=`{visual.get('world_stream_failure_class', '')}`"
        )
    warnings = summary.get("warnings", []) if isinstance(summary.get("warnings"), list) else []
    lines.extend(["", "## Warnings"])
    lines.extend([f"- `{item}`" for item in warnings] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mobile fetch visual UAT package.")
    parser.add_argument("--campaign-id", default=f"live_fetch_visual_uat_package_{current_utc_stamp()}")
    parser.add_argument("--planner-summary", action="append", default=[])
    parser.add_argument("--seeded-evidence-summary", action="append", default=[])
    parser.add_argument("--stage-quality-summary", action="append", default=[])
    parser.add_argument("--mission-summary", action="append", default=[])
    parser.add_argument("--visual-dir", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / PACKAGE_KIND)
    summary = build_summary(args)
    summary_path = root / "package_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_VISUAL_UAT_PACKAGE_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
