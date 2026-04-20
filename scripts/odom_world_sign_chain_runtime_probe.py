#!/usr/bin/env python3
"""Collect per-topic cmd_vel and odom sign evidence during a live gather probe."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable

import rclpy
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles


CMD_TOPIC_PRIMARY = "/jetbot_base_controller/cmd_vel"
CMD_TOPIC_SECONDARY = "/cmd_vel"
CMD_TOPIC_NAV = "/cmd_vel_nav"
ODOM_TOPIC_PRIMARY = "/odom"
ODOM_TOPIC_MODEL = "/model/jetbot/odometry"
ODOM_TOPIC_CONTROLLER = "/jetbot_base_controller/odom"
MIN_COMMAND_RADPS = 0.05
MIN_YAW_RAD = 0.05


def yaw_from_quaternion(quaternion: Any) -> float:
    siny_cosp = 2.0 * (quaternion.w * quaternion.z + quaternion.x * quaternion.y)
    cosy_cosp = 1.0 - 2.0 * (quaternion.y * quaternion.y + quaternion.z * quaternion.z)
    return math.atan2(siny_cosp, cosy_cosp)


def normalize_angle(value: float) -> float:
    while value > math.pi:
        value -= 2.0 * math.pi
    while value < -math.pi:
        value += 2.0 * math.pi
    return value


def sign(value: float, *, eps: float) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture per-topic sign evidence across cmd_vel and odom surfaces."
    )
    parser.add_argument("--duration-s", type=float, default=45.0)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--use-sim-time", action="store_true")
    return parser.parse_args()


@dataclass
class CommandTopicStats:
    topic: str
    message_count: int = 0
    nonzero_message_count: int = 0
    peak_abs_angular_z_radps: float = 0.0
    net_angular_integral_rad: float = 0.0
    first_nonzero_sign: int = 0
    last_nonzero_sign: int = 0
    last_sample_time_s: float | None = None

    def add(self, angular_z: float, sample_time_s: float) -> None:
        current_value = float(angular_z)
        if self.last_sample_time_s is not None:
            dt_s = max(sample_time_s - self.last_sample_time_s, 0.0)
            self.net_angular_integral_rad += current_value * min(dt_s, 1.0)
        self.last_sample_time_s = sample_time_s
        self.message_count += 1
        self.peak_abs_angular_z_radps = max(self.peak_abs_angular_z_radps, abs(current_value))
        current_sign = sign(current_value, eps=MIN_COMMAND_RADPS)
        if current_sign != 0:
            self.nonzero_message_count += 1
            if self.first_nonzero_sign == 0:
                self.first_nonzero_sign = current_sign
            self.last_nonzero_sign = current_sign

    def dominant_sign(self) -> int:
        resolved_sign = sign(self.net_angular_integral_rad, eps=MIN_COMMAND_RADPS)
        if resolved_sign == 0 and self.first_nonzero_sign != 0 and self.first_nonzero_sign == self.last_nonzero_sign:
            return self.first_nonzero_sign
        return resolved_sign

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "message_count": int(self.message_count),
            "nonzero_message_count": int(self.nonzero_message_count),
            "peak_abs_angular_z_radps": round(self.peak_abs_angular_z_radps, 6),
            "net_angular_integral_rad": round(self.net_angular_integral_rad, 6),
            "first_nonzero_sign": int(self.first_nonzero_sign),
            "last_nonzero_sign": int(self.last_nonzero_sign),
            "dominant_angular_sign": int(self.dominant_sign()),
        }


@dataclass
class OdomTopicStats:
    topic: str
    message_count: int = 0
    nonzero_step_count: int = 0
    peak_abs_yaw_step_rad: float = 0.0
    net_yaw_change_rad: float = 0.0
    cumulative_abs_yaw_change_rad: float = 0.0
    first_nonzero_sign: int = 0
    last_nonzero_sign: int = 0
    start_yaw_rad: float | None = None
    end_yaw_rad: float | None = None
    _last_yaw_rad: float | None = None

    def add(self, yaw_rad: float) -> None:
        current_yaw = float(yaw_rad)
        if self.start_yaw_rad is None:
            self.start_yaw_rad = current_yaw
        if self._last_yaw_rad is not None:
            yaw_delta = normalize_angle(current_yaw - self._last_yaw_rad)
            self.peak_abs_yaw_step_rad = max(self.peak_abs_yaw_step_rad, abs(yaw_delta))
            self.net_yaw_change_rad += yaw_delta
            self.cumulative_abs_yaw_change_rad += abs(yaw_delta)
            current_sign = sign(yaw_delta, eps=MIN_YAW_RAD)
            if current_sign != 0:
                self.nonzero_step_count += 1
                if self.first_nonzero_sign == 0:
                    self.first_nonzero_sign = current_sign
                self.last_nonzero_sign = current_sign
        self._last_yaw_rad = current_yaw
        self.end_yaw_rad = current_yaw
        self.message_count += 1

    def dominant_sign(self) -> int:
        resolved_sign = sign(self.net_yaw_change_rad, eps=MIN_YAW_RAD)
        if resolved_sign == 0 and self.first_nonzero_sign != 0 and self.first_nonzero_sign == self.last_nonzero_sign:
            return self.first_nonzero_sign
        return resolved_sign

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "message_count": int(self.message_count),
            "nonzero_step_count": int(self.nonzero_step_count),
            "peak_abs_yaw_step_rad": round(self.peak_abs_yaw_step_rad, 6),
            "net_yaw_change_rad": round(self.net_yaw_change_rad, 6),
            "cumulative_abs_yaw_change_rad": round(self.cumulative_abs_yaw_change_rad, 6),
            "first_nonzero_sign": int(self.first_nonzero_sign),
            "last_nonzero_sign": int(self.last_nonzero_sign),
            "dominant_yaw_sign": int(self.dominant_sign()),
            "start_yaw_rad": round(self.start_yaw_rad, 6) if self.start_yaw_rad is not None else None,
            "end_yaw_rad": round(self.end_yaw_rad, 6) if self.end_yaw_rad is not None else None,
        }


class OdomWorldSignChainRuntimeProbe(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("odom_world_sign_chain_runtime_probe")
        if args.use_sim_time:
            self.set_parameters(
                [rclpy.parameter.Parameter("use_sim_time", rclpy.Parameter.Type.BOOL, True)]
            )
        self.command_stats = {
            topic: CommandTopicStats(topic=topic)
            for topic in (CMD_TOPIC_PRIMARY, CMD_TOPIC_SECONDARY, CMD_TOPIC_NAV)
        }
        self.odom_stats = {
            topic: OdomTopicStats(topic=topic)
            for topic in (ODOM_TOPIC_MODEL, ODOM_TOPIC_PRIMARY, ODOM_TOPIC_CONTROLLER)
        }
        self._probe_subs = []
        qos = QoSPresetProfiles.SENSOR_DATA.value
        for topic in self.command_stats:
            self._subscribe_cmd_vel_topic(topic, qos)
        for topic in self.odom_stats:
            self._try_subscribe(
                Odometry,
                topic,
                self._odom_callback(topic),
                qos,
            )

    def _clock_time_s(self) -> float:
        return float(self.get_clock().now().nanoseconds) / 1.0e9

    def _topic_types(self, topic: str) -> set[str]:
        topic_types: set[str] = set()
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

    def _try_subscribe(self, msg_type: Any, topic: str, callback: Callable[[Any], None], qos: Any) -> None:
        try:
            sub = self.create_subscription(msg_type, topic, callback, qos)
            self._probe_subs.append(sub)
        except Exception as exc:
            self.get_logger().warn(f"Skipping subscription {msg_type.__name__} on {topic}: {exc}")

    def _subscribe_cmd_vel_topic(self, topic: str, qos: Any) -> None:
        topic_types = self._topic_types(topic)
        if "geometry_msgs/msg/TwistStamped" in topic_types:
            self._try_subscribe(TwistStamped, topic, self._twist_stamped_callback(topic), qos)
            return
        if "geometry_msgs/msg/Twist" in topic_types:
            self._try_subscribe(Twist, topic, self._twist_callback(topic), qos)
            return
        if topic.endswith("_nav"):
            self._try_subscribe(TwistStamped, topic, self._twist_stamped_callback(topic), qos)
        else:
            self._try_subscribe(Twist, topic, self._twist_callback(topic), qos)

    def _twist_callback(self, topic: str) -> Callable[[Twist], None]:
        def _callback(msg: Twist) -> None:
            self.command_stats[topic].add(float(msg.angular.z), self._clock_time_s())

        return _callback

    def _twist_stamped_callback(self, topic: str) -> Callable[[TwistStamped], None]:
        def _callback(msg: TwistStamped) -> None:
            self.command_stats[topic].add(float(msg.twist.angular.z), self._clock_time_s())

        return _callback

    def _odom_callback(self, topic: str) -> Callable[[Odometry], None]:
        def _callback(msg: Odometry) -> None:
            yaw_rad = yaw_from_quaternion(msg.pose.pose.orientation)
            self.odom_stats[topic].add(yaw_rad)

        return _callback

    def to_dict(self, *, duration_s: float) -> dict[str, Any]:
        return {
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "probe_type": "odom_world_sign_chain_runtime_probe",
            "duration_s": round(float(duration_s), 6),
            "cmd_vel_topics": {
                topic: stats.to_dict()
                for topic, stats in self.command_stats.items()
            },
            "odom_topics": {
                topic: stats.to_dict()
                for topic, stats in self.odom_stats.items()
            },
        }


def main() -> int:
    args = parse_args()
    duration_s = max(float(args.duration_s), 5.0)
    output_path = Path(args.json_out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    node = OdomWorldSignChainRuntimeProbe(args)
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)

    result = node.to_dict(duration_s=duration_s)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"ODOM_WORLD_SIGN_CHAIN_RUNTIME_PROBE_JSON={output_path}")
    print(
        json.dumps(
            {
                "cmd_topics": {
                    topic: payload.get("dominant_angular_sign", 0)
                    for topic, payload in result["cmd_vel_topics"].items()
                },
                "odom_topics": {
                    topic: payload.get("dominant_yaw_sign", 0)
                    for topic, payload in result["odom_topics"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
