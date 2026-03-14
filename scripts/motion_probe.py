#!/usr/bin/env python3
"""Collect simple motion evidence from cmd_vel + odom topics."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Optional, Set, Tuple

import rclpy
from geometry_msgs.msg import Twist, TwistStamped
from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles


def yaw_from_quaternion(q) -> float:
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def normalize_angle(value: float) -> float:
    while value > math.pi:
        value -= 2.0 * math.pi
    while value < -math.pi:
        value += 2.0 * math.pi
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture cmd_vel and odom motion evidence.")
    parser.add_argument("--duration-s", type=float, default=90.0, help="Sampling window in seconds.")
    parser.add_argument("--cmd-vel-topic-primary", default="/jetbot_base_controller/cmd_vel")
    parser.add_argument("--cmd-vel-topic-secondary", default="/cmd_vel")
    parser.add_argument("--odom-topic", default="/odom")
    parser.add_argument("--detection-topic", default="/yolo/ball_position_3d")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    parser.add_argument("--use-sim-time", action="store_true")
    return parser.parse_args()


class MotionProbe(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("chasecar_motion_probe")
        if args.use_sim_time:
            self.set_parameters(
                [rclpy.parameter.Parameter("use_sim_time", rclpy.Parameter.Type.BOOL, True)]
            )

        self.cmd_vel_count = 0
        self.odom_count = 0
        self.detection_count = 0
        self.odom_start: Optional[Tuple[float, float, float]] = None
        self.odom_end: Optional[Tuple[float, float, float]] = None
        self.odom_start_yaw: Optional[float] = None
        self.odom_end_yaw: Optional[float] = None
        self._last_yaw: Optional[float] = None
        self.cumulative_yaw_change_rad = 0.0

        qos = QoSPresetProfiles.SENSOR_DATA.value
        self._probe_subs = []
        cmd_vel_topics = []
        for topic in (
            args.cmd_vel_topic_primary,
            args.cmd_vel_topic_secondary,
            "/cmd_vel_nav",
        ):
            if topic and topic not in cmd_vel_topics:
                cmd_vel_topics.append(topic)
        for topic in cmd_vel_topics:
            self._subscribe_cmd_vel_topic(topic, qos)
        odom_candidates = []
        for topic in (
            args.odom_topic,
            "/odom",
            "/model/jetbot/odometry",
            "/jetbot_base_controller/odom",
        ):
            if topic and topic not in odom_candidates:
                odom_candidates.append(topic)
        for topic in odom_candidates:
            self._try_subscribe(Odometry, topic, self._on_odom, qos)

        self._subscribe_detection_topic(args.detection_topic, qos)

    def _topic_types(self, topic: str) -> Set[str]:
        topic_types: Set[str] = set()
        try:
            for info in self.get_publishers_info_by_topic(topic):
                if info.topic_type:
                    topic_types.add(info.topic_type)
        except Exception:
            pass
        if topic_types:
            return topic_types
        try:
            for known_topic, known_types in self.get_topic_names_and_types():
                if known_topic == topic:
                    topic_types.update(known_types)
                    break
        except Exception:
            pass
        return topic_types

    def _subscribe_cmd_vel_topic(self, topic: str, qos) -> None:
        topic_types = self._topic_types(topic)
        if "geometry_msgs/msg/TwistStamped" in topic_types:
            self._try_subscribe(TwistStamped, topic, self._on_twist_stamped, qos)
            return
        if "geometry_msgs/msg/Twist" in topic_types:
            self._try_subscribe(Twist, topic, self._on_twist, qos)
            return

        # If type is not discoverable yet, use a deterministic default per topic family.
        if topic.endswith("_nav"):
            self._try_subscribe(TwistStamped, topic, self._on_twist_stamped, qos)
        else:
            self._try_subscribe(Twist, topic, self._on_twist, qos)

    def _subscribe_detection_topic(self, topic: str, qos) -> None:
        topic_types = self._topic_types(topic)
        if "geometry_msgs/msg/PointStamped" in topic_types:
            self._try_subscribe(PointStamped, topic, self._on_detection_stamped, qos)
            return
        # Canonical detection contract is PointStamped.
        self._try_subscribe(PointStamped, topic, self._on_detection_stamped, qos)

    def _try_subscribe(self, msg_type, topic: str, callback, qos) -> None:
        try:
            sub = self.create_subscription(msg_type, topic, callback, qos)
            self._probe_subs.append(sub)
        except Exception as exc:
            self.get_logger().warn(f"Skipping subscription {msg_type.__name__} on {topic}: {exc}")

    def _on_twist(self, _msg: Twist) -> None:
        self.cmd_vel_count += 1

    def _on_twist_stamped(self, _msg: TwistStamped) -> None:
        self.cmd_vel_count += 1

    def _on_odom(self, msg: Odometry) -> None:
        p = msg.pose.pose.position
        pose = (float(p.x), float(p.y), float(p.z))
        yaw = yaw_from_quaternion(msg.pose.pose.orientation)
        if self.odom_start is None:
            self.odom_start = pose
            self.odom_start_yaw = yaw
        if self._last_yaw is not None:
            self.cumulative_yaw_change_rad += abs(normalize_angle(yaw - self._last_yaw))
        self._last_yaw = yaw
        self.odom_end = pose
        self.odom_end_yaw = yaw
        self.odom_count += 1

    def _on_detection_stamped(self, _msg: PointStamped) -> None:
        self.detection_count += 1


def main() -> int:
    args = parse_args()
    duration_s = max(args.duration_s, 1.0)

    rclpy.init()
    node = MotionProbe(args)

    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)

    odom_seen = node.odom_start is not None and node.odom_end is not None
    displacement = 0.0
    if odom_seen:
        sx, sy, sz = node.odom_start  # type: ignore[misc]
        ex, ey, ez = node.odom_end  # type: ignore[misc]
        displacement = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2 + (ez - sz) ** 2)

    result = {
        "cmd_vel_message_count": int(node.cmd_vel_count),
        "odom_seen": bool(odom_seen),
        "odom_count": int(node.odom_count),
        "odom_start": {
            "x": float(node.odom_start[0]) if node.odom_start else 0.0,
            "y": float(node.odom_start[1]) if node.odom_start else 0.0,
            "z": float(node.odom_start[2]) if node.odom_start else 0.0,
        },
        "odom_start_yaw_rad": float(node.odom_start_yaw) if node.odom_start_yaw is not None else 0.0,
        "odom_end": {
            "x": float(node.odom_end[0]) if node.odom_end else 0.0,
            "y": float(node.odom_end[1]) if node.odom_end else 0.0,
            "z": float(node.odom_end[2]) if node.odom_end else 0.0,
        },
        "odom_end_yaw_rad": float(node.odom_end_yaw) if node.odom_end_yaw is not None else 0.0,
        "cumulative_yaw_change_rad": float(node.cumulative_yaw_change_rad),
        "odom_displacement_m": float(displacement),
        "detection_message_count": int(node.detection_count),
    }

    if args.json_out:
        out_path = Path(args.json_out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"CMD_VEL_MESSAGE_COUNT={result['cmd_vel_message_count']}")
    print(f"ODOM_SEEN={'true' if result['odom_seen'] else 'false'}")
    print(f"ODOM_COUNT={result['odom_count']}")
    print(f"ODOM_START_X={result['odom_start']['x']:.6f}")
    print(f"ODOM_START_Y={result['odom_start']['y']:.6f}")
    print(f"ODOM_START_Z={result['odom_start']['z']:.6f}")
    print(f"ODOM_END_X={result['odom_end']['x']:.6f}")
    print(f"ODOM_END_Y={result['odom_end']['y']:.6f}")
    print(f"ODOM_END_Z={result['odom_end']['z']:.6f}")
    print(f"ODOM_START_YAW_RAD={result['odom_start_yaw_rad']:.6f}")
    print(f"ODOM_END_YAW_RAD={result['odom_end_yaw_rad']:.6f}")
    print(f"CUMULATIVE_YAW_CHANGE_RAD={result['cumulative_yaw_change_rad']:.6f}")
    print(f"ODOM_DISPLACEMENT_M={result['odom_displacement_m']:.6f}")
    print(f"DETECTION_MESSAGE_COUNT={result['detection_message_count']}")

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
