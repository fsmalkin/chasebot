#!/usr/bin/env python3
"""Record and validate a same-session Gazebo world stream from an observer camera topic."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import Image


WORLD_STREAM_RECENT_WINDOW_S = 5.0
WORLD_STREAM_TRANSPORT_MIN_FRAMES = 3
WORLD_STREAM_TRANSPORT_MAX_AGE_S = 2.5
WORLD_STREAM_RENDERABLE_MAX_AGE_S = 10.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a streamed Gazebo world pane from a sensor topic.")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--world-name", default="yolo_test_world")
    parser.add_argument("--image-topic", default="/observer_world/image_raw")
    parser.add_argument("--truth-state-path", default="")
    parser.add_argument("--public-url", default="")
    parser.add_argument("--camera-profile", default="overview_fixed")
    parser.add_argument("--duration-s", type=float, default=180.0)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--require-target-visible", action="store_true")
    parser.add_argument("--robot-min-area-px", type=float, default=140.0)
    parser.add_argument("--target-min-area-px", type=float, default=90.0)
    parser.add_argument("--scene-std-min", type=float, default=12.0)
    parser.add_argument("--scene-sat-min", type=float, default=30.0)
    parser.add_argument("--healthy-stale-seconds", type=float, default=2.5)
    return parser.parse_args()


def image_msg_to_bgr(msg: Image) -> np.ndarray:
    if msg.height <= 0 or msg.width <= 0:
        raise ValueError("invalid image dimensions")

    raw = np.frombuffer(msg.data, dtype=np.uint8)
    encoding = (msg.encoding or "").lower()

    if encoding in ("bgr8", "rgb8"):
        expected = msg.height * msg.width * 3
        if raw.size < expected:
            raise ValueError("rgb payload too small")
        arr = raw[:expected].reshape((msg.height, msg.width, 3))
        if encoding == "rgb8":
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return arr

    if encoding in ("bgra8", "rgba8"):
        expected = msg.height * msg.width * 4
        if raw.size < expected:
            raise ValueError("rgba payload too small")
        arr = raw[:expected].reshape((msg.height, msg.width, 4))
        if encoding == "rgba8":
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

    if encoding in ("mono8", "8uc1"):
        expected = msg.height * msg.width
        if raw.size < expected:
            raise ValueError("mono payload too small")
        gray = raw[:expected].reshape((msg.height, msg.width))
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    if msg.step > 0:
        row_bytes = int(msg.step)
        if raw.size >= msg.height * row_bytes:
            full = raw[: msg.height * row_bytes].reshape((msg.height, row_bytes))
            pixels_bytes = msg.width * 3
            if row_bytes >= pixels_bytes:
                arr = full[:, :pixels_bytes].reshape((msg.height, msg.width, 3))
                return arr

    raise ValueError(f"unsupported image encoding: {msg.encoding}")


def placeholder_frame(width: int, height: int, label: str) -> np.ndarray:
    frame = np.full((height, width, 3), 200, dtype=np.uint8)
    cv2.putText(frame, label, (30, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2, cv2.LINE_AA)
    return frame


def image_is_nonblank(frame: np.ndarray) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sat_mean = float(np.mean(hsv[:, :, 1]))
    if np.std(gray) >= 2.5 or sat_mean >= 10.0:
        return True
    return False


def largest_mask_area(mask: np.ndarray) -> float:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0
    return float(max(cv2.contourArea(contour) for contour in contours))


def scene_has_content(frame: np.ndarray, scene_std_min: float, scene_sat_min: float) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sat_mean = float(np.mean(hsv[:, :, 1]))
    if np.std(gray) >= scene_std_min and sat_mean >= scene_sat_min:
        return True

    green_mask = cv2.inRange(hsv, (35, 60, 40), (90, 255, 255))
    blue_mask = cv2.inRange(hsv, (95, 60, 35), (128, 255, 220))
    red_mask_1 = cv2.inRange(hsv, (0, 90, 45), (12, 255, 255))
    red_mask_2 = cv2.inRange(hsv, (168, 90, 45), (180, 255, 255))
    red_mask = cv2.bitwise_or(red_mask_1, red_mask_2)

    green_ratio = float(np.mean(green_mask > 0))
    blue_ratio = float(np.mean(blue_mask > 0))
    red_ratio = float(np.mean(red_mask > 0))
    return bool(sat_mean >= scene_sat_min and (green_ratio >= 0.05 or blue_ratio >= 0.001 or red_ratio >= 0.0005))


def robot_blue_area(frame: np.ndarray) -> float:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Target the darker saturated JetBot body, not the pale blue sky.
    mask = cv2.inRange(hsv, (95, 60, 35), (128, 255, 220))
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return largest_mask_area(mask)


def target_red_area(frame: np.ndarray) -> float:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (0, 90, 45), (12, 255, 255))
    mask2 = cv2.inRange(hsv, (168, 90, 45), (180, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return largest_mask_area(mask)


def truth_state_matches(path: Optional[Path], session_id: str) -> tuple[bool, bool]:
    if path is None or not path.exists():
        return True, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False, False
    matches = str(payload.get("session_id", "")).strip() == session_id
    target_seen = bool(payload.get("true_target_seen", False))
    return matches, target_seen


class WorldStreamObserver(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("chasecar_world_stream_observer")
        self.args = args
        self.latest_frame: Optional[np.ndarray] = None
        self.last_frame_wall_s = 0.0
        self.image_error = ""
        self.received_frame_count = 0
        self.rendered_frame_count = 0
        self.latest_received_frame_seq = 0
        self.last_rendered_frame_seq = 0
        self.recent_frame_wall_times: deque[float] = deque()
        self.nonblank_count = 0
        self.scene_content_count = 0
        self.robot_visible_count = 0
        self.target_visible_count = 0
        self.robot_max_area = 0.0
        self.target_max_area = 0.0
        self.started_monotonic_s = time.monotonic()

        self.output_dir = Path(args.output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.live_dir = self.output_dir / "live"
        self.live_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_path = self.live_dir / "world_stream.jpg"
        self.video_path = self.output_dir / "world_stream.mp4"
        self.state_path = self.output_dir / "world_stream_state.json"
        self.summary_path = self.output_dir / "world_stream_summary.json"
        self.placeholder = placeholder_frame(960, 540, "waiting for Gazebo observer camera")
        cv2.imwrite(str(self.screenshot_path), self.placeholder)
        self.writer: Optional[cv2.VideoWriter] = None
        self.writer_size: Optional[tuple[int, int]] = None

        qos = QoSPresetProfiles.SENSOR_DATA.value
        self.create_subscription(Image, args.image_topic, self._on_image, qos)

    def _on_image(self, msg: Image) -> None:
        try:
            frame = image_msg_to_bgr(msg)
            self.latest_frame = frame
            self.last_frame_wall_s = time.time()
            self.received_frame_count += 1
            self.latest_received_frame_seq = self.received_frame_count
            self.recent_frame_wall_times.append(self.last_frame_wall_s)
            latest_nonblank = image_is_nonblank(frame)
            latest_scene = scene_has_content(frame, self.args.scene_std_min, self.args.scene_sat_min)
            latest_robot_area = robot_blue_area(frame)
            latest_target_area = target_red_area(frame)
            latest_robot = latest_robot_area >= self.args.robot_min_area_px
            latest_target = latest_target_area >= self.args.target_min_area_px
            if latest_nonblank:
                self.nonblank_count += 1
            if latest_scene:
                self.scene_content_count += 1
            if latest_robot:
                self.robot_visible_count += 1
            if latest_target:
                self.target_visible_count += 1
            self.robot_max_area = max(self.robot_max_area, latest_robot_area)
            self.target_max_area = max(self.target_max_area, latest_target_area)
            self.image_error = ""
        except Exception as exc:  # pragma: no cover - defensive path
            self.image_error = str(exc)

    def _prune_recent_frames(self, now: float) -> None:
        cutoff = now - WORLD_STREAM_RECENT_WINDOW_S
        while self.recent_frame_wall_times and self.recent_frame_wall_times[0] < cutoff:
            self.recent_frame_wall_times.popleft()

    def _recent_frame_count(self, now: float) -> int:
        self._prune_recent_frames(now)
        return len(self.recent_frame_wall_times)

    def _ensure_writer(self, frame: np.ndarray) -> None:
        if self.writer is not None:
            return
        size = (frame.shape[1], frame.shape[0])
        self.writer_size = size
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(str(self.video_path), fourcc, max(self.args.fps, 1.0), size)

    def update(self) -> dict[str, object]:
        now = time.time()
        truth_matches, truth_target_seen = truth_state_matches(
            Path(self.args.truth_state_path).resolve() if self.args.truth_state_path else None,
            self.args.session_id,
        )
        partition = (
            os.environ.get("GAZEBO_PARTITION", "").strip()
            or os.environ.get("GZ_PARTITION", "").strip()
            or os.environ.get("IGN_PARTITION", "").strip()
        )
        same_session_partition = bool(partition) and partition == self.args.session_id and truth_matches
        latest_nonblank = False
        latest_scene = False
        latest_robot = False
        latest_target = False
        latest_robot_area = 0.0
        latest_target_area = 0.0

        if self.latest_frame is not None:
            frame = self.latest_frame.copy()
            latest_nonblank = image_is_nonblank(frame)
            latest_scene = scene_has_content(frame, self.args.scene_std_min, self.args.scene_sat_min)
            latest_robot_area = robot_blue_area(frame)
            latest_target_area = target_red_area(frame)
            latest_robot = latest_robot_area >= self.args.robot_min_area_px
            latest_target = latest_target_area >= self.args.target_min_area_px

        new_frame_ready = self.latest_frame is not None and self.latest_received_frame_seq > self.last_rendered_frame_seq

        if new_frame_ready:
            self.rendered_frame_count += 1
            self._ensure_writer(frame)
            if self.writer is not None:
                self.writer.write(frame)
            cv2.imwrite(str(self.screenshot_path), frame)
            self.last_rendered_frame_seq = self.latest_received_frame_seq

        min_frames = 3
        target_required = self.args.require_target_visible and (truth_target_seen or not self.args.truth_state_path)
        observed_frames = max(self.received_frame_count, 1)
        nonblank_ratio = float(self.nonblank_count / observed_frames)
        scene_ratio = float(self.scene_content_count / observed_frames)
        robot_ratio = float(self.robot_visible_count / observed_frames)
        target_ratio = float(self.target_visible_count / observed_frames)
        recent_frame_count = self._recent_frame_count(now)
        elapsed_s = max(time.monotonic() - self.started_monotonic_s, 1e-6)
        expected_recent_frames = max(WORLD_STREAM_RECENT_WINDOW_S * max(self.args.fps, 1.0), 1.0)
        frame_coverage_ratio = float(recent_frame_count / expected_recent_frames)
        latest_frame_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_frame_wall_s)) if self.last_frame_wall_s > 0 else ""
        latest_frame_age_s = max(now - self.last_frame_wall_s, 0.0) if self.last_frame_wall_s > 0 else None
        screenshot_exists = self.screenshot_path.exists()
        world_stream_transport_healthy = bool(
            same_session_partition
            and recent_frame_count >= WORLD_STREAM_TRANSPORT_MIN_FRAMES
            and latest_frame_age_s is not None
            and latest_frame_age_s <= WORLD_STREAM_TRANSPORT_MAX_AGE_S
            and not self.image_error
        )
        world_stream_renderable = bool(
            same_session_partition
            and self.rendered_frame_count >= 1
            and screenshot_exists
            and latest_frame_age_s is not None
            and latest_frame_age_s <= WORLD_STREAM_RENDERABLE_MAX_AGE_S
        )
        frames_stale = bool(
            self.received_frame_count >= 1
            and latest_frame_age_s is not None
            and latest_frame_age_s > max(self.args.healthy_stale_seconds, 0.1)
        )
        world_stream_nonblank = self.received_frame_count >= min_frames and nonblank_ratio >= 0.60
        scene_content_ok = self.received_frame_count >= min_frames and scene_ratio >= 0.60
        robot_visible_ok = self.received_frame_count >= min_frames and robot_ratio >= 0.50
        target_visible_ok = (not target_required) or (self.received_frame_count >= min_frames and target_ratio >= 0.50)

        failure_class = ""
        if not same_session_partition:
            failure_class = "world_stream_partition_mismatch"
        elif self.image_error:
            failure_class = "world_stream_image_decode_error"
        elif latest_frame_age_s is None or recent_frame_count == 0 or latest_frame_age_s > WORLD_STREAM_RENDERABLE_MAX_AGE_S:
            failure_class = "world_stream_no_recent_frames"
        elif not world_stream_transport_healthy:
            failure_class = "world_stream_receive_rate_low"
        elif not world_stream_nonblank:
            failure_class = "world_stream_blank"
        elif not scene_content_ok:
            failure_class = "world_stream_scene_missing"
        elif not robot_visible_ok:
            failure_class = "world_stream_robot_not_visible"
        elif not target_visible_ok:
            failure_class = "world_stream_target_not_visible"

        world_stream_ready = not failure_class
        world_stream_degraded = bool(world_stream_renderable and (not world_stream_transport_healthy or not world_stream_ready))
        state = {
            "session_id": self.args.session_id,
            "partition": partition,
            "world_surface": "streamed_sim",
            "world_stream_url": "",
            "world_stream_ready": world_stream_ready,
            "world_stream_renderable": world_stream_renderable,
            "world_stream_transport_healthy": world_stream_transport_healthy,
            "world_stream_degraded": world_stream_degraded,
            "world_stream_nonblank": world_stream_nonblank,
            "world_stream_interactive": False,
            "same_session_partition": same_session_partition,
            "viewer_process_healthy": world_stream_transport_healthy,
            "viewer_client_mode": "gazebo_sensor_camera",
            "camera_profile": self.args.camera_profile,
            "render_backend": "gazebo_sensor_camera:ogre2",
            "software_render_only": False,
            "display_server": "none",
            "gpu_available": True,
            "scene_content_ok": scene_content_ok,
            "robot_visible_ok": robot_visible_ok,
            "target_visible_ok": target_visible_ok,
            "failure_class": failure_class,
            "image_topic": self.args.image_topic,
            "frame_count": self.received_frame_count,
            "received_frame_count": self.received_frame_count,
            "rendered_frame_count": self.rendered_frame_count,
            "latest_frame_wall_s": round(self.last_frame_wall_s, 6) if self.last_frame_wall_s > 0 else None,
            "latest_frame_utc": latest_frame_utc,
            "latest_frame_age_s": round(latest_frame_age_s, 3) if latest_frame_age_s is not None else None,
            "frames_stale": frames_stale,
            "healthy_stale_seconds": round(max(self.args.healthy_stale_seconds, 0.1), 3),
            "elapsed_s": round(elapsed_s, 3),
            "frame_coverage_ratio": round(frame_coverage_ratio, 6),
            "recent_frame_count_5s": recent_frame_count,
            "recent_frame_window_s": WORLD_STREAM_RECENT_WINDOW_S,
            "nonblank_ratio": round(nonblank_ratio, 6),
            "scene_content_ratio": round(scene_ratio, 6),
            "robot_visible_ratio": round(robot_ratio, 6),
            "target_visible_ratio": round(target_ratio, 6),
            "robot_max_area_px": round(self.robot_max_area, 3),
            "target_max_area_px": round(self.target_max_area, 3),
            "latest_robot_area_px": round(latest_robot_area, 3),
            "latest_target_area_px": round(latest_target_area, 3),
            "latest_frame_error": self.image_error,
            "truth_target_seen": truth_target_seen,
            "screenshot_path": str(self.screenshot_path),
            "video_path": str(self.video_path),
        }
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return state

    def finalize(self, last_state: dict[str, object]) -> None:
        if self.writer is not None:
            self.writer.release()
        video_ok = self.video_path.exists() and self.video_path.stat().st_size > 0
        summary = dict(last_state)
        summary.update(
            {
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pass": bool(last_state.get("world_stream_ready")) and video_ok,
                "summary_path": str(self.summary_path),
                "state_path": str(self.state_path),
                "video_ok": video_ok,
            }
        )
        self.summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    rclpy.init()
    node = WorldStreamObserver(args)
    stop_requested = False

    def request_stop(*_args: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    started = time.monotonic()
    tick_period = 1.0 / max(args.fps, 1.0)
    last_tick = 0.0
    last_state: dict[str, object] = {
        "session_id": args.session_id,
        "world_stream_ready": False,
        "world_stream_renderable": False,
        "world_stream_transport_healthy": False,
        "world_stream_degraded": False,
        "failure_class": "world_stream_no_recent_frames",
        "world_stream_nonblank": False,
        "world_stream_interactive": False,
        "same_session_partition": False,
        "viewer_process_healthy": False,
        "viewer_client_mode": "gazebo_sensor_camera",
        "camera_profile": args.camera_profile,
        "render_backend": "gazebo_sensor_camera:ogre2",
        "software_render_only": False,
        "display_server": "none",
        "gpu_available": True,
        "scene_content_ok": False,
        "robot_visible_ok": False,
        "target_visible_ok": False,
        "received_frame_count": 0,
        "rendered_frame_count": 0,
        "latest_frame_wall_s": None,
        "latest_frame_utc": "",
        "latest_frame_age_s": None,
        "frames_stale": False,
        "healthy_stale_seconds": round(max(args.healthy_stale_seconds, 0.1), 3),
        "recent_frame_count_5s": 0,
        "recent_frame_window_s": WORLD_STREAM_RECENT_WINDOW_S,
        "screenshot_path": str(node.screenshot_path),
        "video_path": str(node.video_path),
    }

    try:
        while not stop_requested and (time.monotonic() - started) < max(args.duration_s, 1.0):
            rclpy.spin_once(node, timeout_sec=0.1)
            now = time.monotonic()
            if (now - last_tick) >= tick_period:
                last_tick = now
                last_state = node.update()
    finally:
        node.finalize(last_state)
        node.destroy_node()
        rclpy.shutdown()

    print(f"WORLD_STREAM_STATE={node.state_path}")
    print(f"WORLD_STREAM_SUMMARY={node.summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
