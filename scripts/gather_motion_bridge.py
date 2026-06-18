#!/usr/bin/env python3
"""Publish direct gather motion commands from a shared runtime JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node

try:
    from rclpy.executors import ExternalShutdownException
except Exception:  # pragma: no cover - keeps non-ROS unit stubs importable.
    class ExternalShutdownException(Exception):
        pass


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Publish gather motion commands from a runtime JSON file.")
    parser.add_argument(
        "--runtime-json",
        default=str((repo_root / "runtime" / "dashboard" / "gather_mission_runtime.json").resolve()),
    )
    parser.add_argument("--cmd-vel-topic", default="/cmd_vel")
    parser.add_argument("--robot-cmd-vel-topic", default="/jetbot_base_controller/cmd_vel")
    parser.add_argument("--loop-rate-hz", type=float, default=10.0)
    parser.add_argument("--max-linear-x", type=float, default=0.30)
    parser.add_argument("--max-angular-z", type=float, default=1.20)
    parser.add_argument("--use-sim-time", action="store_true", default=True)
    parser.add_argument("--no-use-sim-time", dest="use_sim_time", action="store_false")
    return parser.parse_args()


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def load_runtime(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class GatherMotionBridge(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("gather_motion_bridge")
        self.runtime_path = Path(args.runtime_json).resolve()
        self.max_linear_x = max(float(args.max_linear_x), 0.0)
        self.max_angular_z = max(float(args.max_angular_z), 0.0)
        self.cmd_vel_pub = self.create_publisher(Twist, args.cmd_vel_topic, 20)
        self.robot_cmd_vel_pub = self.create_publisher(TwistStamped, args.robot_cmd_vel_topic, 20)
        self.stop_published = False
        self.last_signature = ""
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", rclpy.parameter.Parameter.Type.BOOL, bool(args.use_sim_time))])
        loop_rate_hz = max(float(args.loop_rate_hz), 2.0)
        self.create_timer(1.0 / loop_rate_hz, self._on_timer)
        self.get_logger().info(f"Gather motion bridge runtime: {self.runtime_path}")

    def _publish_twist(self, linear_x: float, angular_z: float) -> None:
        twist = Twist()
        twist.linear.x = clamp(float(linear_x), -self.max_linear_x, self.max_linear_x)
        twist.angular.z = clamp(float(angular_z), -self.max_angular_z, self.max_angular_z)
        self.cmd_vel_pub.publish(twist)

        stamped = TwistStamped()
        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.header.frame_id = "base_link"
        stamped.twist = twist
        self.robot_cmd_vel_pub.publish(stamped)

    def _on_timer(self) -> None:
        runtime = load_runtime(self.runtime_path)
        manual_drive = runtime.get("manual_drive") if isinstance(runtime.get("manual_drive"), dict) else {}
        enabled = bool(manual_drive.get("enabled", False))
        command = manual_drive.get("command") if isinstance(manual_drive.get("command"), dict) else {}
        signature = json.dumps(
            {
                "enabled": enabled,
                "linear_x": float(command.get("linear_x", 0.0) or 0.0),
                "angular_z": float(command.get("angular_z", 0.0) or 0.0),
                "sequence": int(manual_drive.get("sequence", 0) or 0),
            },
            sort_keys=True,
        )
        if enabled:
            self._publish_twist(
                float(command.get("linear_x", 0.0) or 0.0),
                float(command.get("angular_z", 0.0) or 0.0),
            )
            self.stop_published = False
        elif not self.stop_published:
            self._publish_twist(0.0, 0.0)
            self.stop_published = True
        if signature != self.last_signature:
            self.last_signature = signature
            self.get_logger().info(f"Gather motion command updated: {signature}")


def main() -> int:
    args = parse_args()
    rclpy.init()
    node = GatherMotionBridge(args)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            try:
                node._publish_twist(0.0, 0.0)
            except Exception as exc:
                node.get_logger().warn(f"Unable to publish shutdown stop: {exc!r}")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
