#!/usr/bin/env python3
"""Capture one ROS image message from a topic and write it as PNG."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture one ROS Image topic sample.")
    parser.add_argument("--topic", required=True, help="Image topic, e.g. /d415/color/image_raw")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--timeout-s", type=float, default=10.0, help="Max wait for one message")
    parser.add_argument(
        "--placeholder-label",
        default="missing_topic",
        help="Text label used if no image is received before timeout",
    )
    parser.add_argument(
        "--use-sim-time",
        action="store_true",
        help="Set use_sim_time on the capture node.",
    )
    parser.add_argument(
        "--qos-profile",
        choices=("default", "sensor_data"),
        default="sensor_data",
        help="QoS profile used for image subscription.",
    )
    parser.add_argument(
        "--min-frames",
        type=int,
        default=1,
        help="Number of frames that must be observed before capture succeeds.",
    )
    return parser.parse_args()


def placeholder_image(label: str) -> np.ndarray:
    canvas = np.full((360, 640, 3), 48, dtype=np.uint8)
    cv2.putText(
        canvas,
        f"capture: {label}",
        (24, 180),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (200, 220, 255),
        2,
        cv2.LINE_AA,
    )
    return canvas


def image_msg_to_bgr(msg: Image) -> np.ndarray:
    if msg.height <= 0 or msg.width <= 0:
        raise ValueError("Invalid image dimensions")

    raw = np.frombuffer(msg.data, dtype=np.uint8)
    encoding = (msg.encoding or "").lower()

    if encoding in ("bgr8", "rgb8"):
        expected = msg.height * msg.width * 3
        if raw.size < expected:
            raise ValueError("RGB/BGR payload too small")
        arr = raw[:expected].reshape((msg.height, msg.width, 3))
        if encoding == "rgb8":
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return arr

    if encoding in ("bgra8", "rgba8"):
        expected = msg.height * msg.width * 4
        if raw.size < expected:
            raise ValueError("RGBA/BGRA payload too small")
        arr = raw[:expected].reshape((msg.height, msg.width, 4))
        if encoding == "rgba8":
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

    if encoding in ("mono8", "8uc1"):
        expected = msg.height * msg.width
        if raw.size < expected:
            raise ValueError("Mono payload too small")
        gray = raw[:expected].reshape((msg.height, msg.width))
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Fallback: infer shape using step (bytes per row).
    if msg.step > 0:
        row_bytes = int(msg.step)
        if raw.size >= msg.height * row_bytes:
            full = raw[: msg.height * row_bytes].reshape((msg.height, row_bytes))
            # Use first width*3 bytes as BGR when available.
            pixels_bytes = msg.width * 3
            if row_bytes >= pixels_bytes:
                arr = full[:, :pixels_bytes].reshape((msg.height, msg.width, 3))
                return arr

    raise ValueError(f"Unsupported image encoding: {msg.encoding}")


class OneShotImageCapture(Node):
    def __init__(self, topic: str, use_sim_time: bool, qos_profile_name: str):
        super().__init__("capture_topic_image")
        if use_sim_time:
            self.set_parameters(
                [rclpy.parameter.Parameter("use_sim_time", rclpy.Parameter.Type.BOOL, True)]
            )
        self._latest_msg: Image | None = None
        self._frames_seen = 0
        self._topic_seen = False
        qos_profile = (
            QoSPresetProfiles.SENSOR_DATA.value
            if qos_profile_name == "sensor_data"
            else QoSPresetProfiles.SYSTEM_DEFAULT.value
        )
        self._sub = self.create_subscription(Image, topic, self._on_image, qos_profile)

    def _on_image(self, msg: Image) -> None:
        self._topic_seen = True
        self._frames_seen += 1
        self._latest_msg = msg

    @property
    def message(self) -> Image | None:
        return self._latest_msg

    @property
    def frames_seen(self) -> int:
        return self._frames_seen

    @property
    def topic_seen(self) -> bool:
        return self._topic_seen


def main() -> int:
    args = parse_args()
    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    min_frames = max(int(args.min_frames), 1)
    node = OneShotImageCapture(
        topic=args.topic,
        use_sim_time=args.use_sim_time,
        qos_profile_name=args.qos_profile,
    )

    deadline = time.monotonic() + max(args.timeout_s, 0.1)
    captured = False
    capture_error = "none"

    while time.monotonic() < deadline and rclpy.ok() and node.frames_seen < min_frames:
        rclpy.spin_once(node, timeout_sec=0.1)

    try:
        if node.message is not None and node.frames_seen >= min_frames:
            try:
                img = image_msg_to_bgr(node.message)
                captured = True
            except Exception:
                capture_error = "decode_error"
                img = placeholder_image("decode_error")
        else:
            if node.topic_seen:
                capture_error = "timeout_min_frames"
            else:
                capture_error = "timeout_no_messages"
            img = placeholder_image(args.placeholder_label)
        ok = cv2.imwrite(str(out_path), img)
        if not ok:
            print(f"Failed to write image: {out_path}", file=sys.stderr)
            print("CAPTURED=false")
            print(f"OUTPUT={out_path}")
            print(f"TOPIC_SEEN={'true' if node.topic_seen else 'false'}")
            print(f"FRAMES_SEEN={node.frames_seen}")
            print("CAPTURE_ERROR=imwrite_failed")
            return 2
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    print(f"CAPTURED={'true' if captured else 'false'}")
    print(f"OUTPUT={out_path}")
    print(f"TOPIC_SEEN={'true' if node.topic_seen else 'false'}")
    print(f"FRAMES_SEEN={node.frames_seen}")
    print(f"CAPTURE_ERROR={capture_error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
