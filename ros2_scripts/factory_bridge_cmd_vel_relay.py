#!/usr/bin/env python3
"""Forward Chasecar ROS velocity commands to the factory robot bridge."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
import time
from typing import Any

import rclpy
from geometry_msgs.msg import Twist, TwistStamped
from rclpy.node import Node


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_client as bridge_client  # noqa: E402


DEFAULT_BASE_URL = "http://192.168.1.11:8765"
DEFAULT_SUMMARY_PATH = REPO_ROOT / "artifacts" / "session" / "factory_bridge_cmd_vel_relay" / "relay_summary.json"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def split_topics(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


@dataclass(frozen=True)
class RelayConfig:
    linear_scale: float = 3.0
    angular_scale: float = 3.0
    max_bridge_linear_x: float = 0.36
    max_bridge_angular_z: float = 1.0
    command_duration_s: float = 0.20
    post_rate_hz: float = 5.0
    stale_stop_s: float = 0.45
    source_prefix: str = "factory_bridge_cmd_vel_relay"


@dataclass(frozen=True)
class RelayInput:
    topic: str
    message_type: str
    raw_linear_x: float
    raw_angular_z: float
    bridge_linear_x: float
    bridge_angular_z: float
    received_monotonic_s: float
    received_utc: str


@dataclass(frozen=True)
class RelayAction:
    action: str
    payload: dict[str, Any]
    reason: str


class RelayCore:
    def __init__(self, config: RelayConfig) -> None:
        self.config = config
        self.last_input: RelayInput | None = None
        self.last_action_monotonic_s: float | None = None
        self.active_command_posted = False
        self.stale_stop_sent = False
        self.counters: dict[str, int] = {
            "messages_received": 0,
            "cmd_vel_posts": 0,
            "stop_posts": 0,
            "http_refusals": 0,
            "http_errors": 0,
            "dry_run_actions": 0,
        }
        self.events: list[dict[str, Any]] = []

    def _scaled(self, linear_x: float, angular_z: float) -> tuple[float, float]:
        scaled_linear = clamp(
            float(linear_x) * float(self.config.linear_scale),
            -float(self.config.max_bridge_linear_x),
            float(self.config.max_bridge_linear_x),
        )
        scaled_angular = clamp(
            float(angular_z) * float(self.config.angular_scale),
            -float(self.config.max_bridge_angular_z),
            float(self.config.max_bridge_angular_z),
        )
        return round(scaled_linear, 6), round(scaled_angular, 6)

    @staticmethod
    def _nonzero(linear_x: float, angular_z: float) -> bool:
        return abs(float(linear_x)) > 1.0e-6 or abs(float(angular_z)) > 1.0e-6

    def update_command(
        self,
        *,
        topic: str,
        message_type: str,
        linear_x: float,
        angular_z: float,
        now_monotonic_s: float | None = None,
    ) -> RelayInput:
        now = time.monotonic() if now_monotonic_s is None else float(now_monotonic_s)
        bridge_linear, bridge_angular = self._scaled(linear_x, angular_z)
        self.last_input = RelayInput(
            topic=str(topic),
            message_type=str(message_type),
            raw_linear_x=float(linear_x),
            raw_angular_z=float(angular_z),
            bridge_linear_x=bridge_linear,
            bridge_angular_z=bridge_angular,
            received_monotonic_s=now,
            received_utc=utc_now(),
        )
        self.stale_stop_sent = False
        self.counters["messages_received"] += 1
        return self.last_input

    def next_action(self, now_monotonic_s: float | None = None) -> RelayAction | None:
        now = time.monotonic() if now_monotonic_s is None else float(now_monotonic_s)
        latest = self.last_input
        if latest is None:
            return None

        age_s = now - latest.received_monotonic_s
        if age_s > float(self.config.stale_stop_s):
            if self.active_command_posted and not self.stale_stop_sent:
                return RelayAction(
                    action="stop",
                    payload={"source": f"{self.config.source_prefix}:stale_stop"},
                    reason="input_stale",
                )
            return None

        min_interval_s = 1.0 / max(float(self.config.post_rate_hz), 0.1)
        if self.last_action_monotonic_s is not None and (now - self.last_action_monotonic_s) < min_interval_s:
            return None

        return RelayAction(
            action="cmd_vel",
            payload={
                "linear_x": latest.bridge_linear_x,
                "angular_z": latest.bridge_angular_z,
                "duration_s": float(self.config.command_duration_s),
                "source": f"{self.config.source_prefix}:{latest.topic}",
                "raw": {
                    "linear_x": latest.raw_linear_x,
                    "angular_z": latest.raw_angular_z,
                    "message_type": latest.message_type,
                },
            },
            reason="fresh_input",
        )

    def record_action_result(
        self,
        action: RelayAction,
        *,
        now_monotonic_s: float | None = None,
        http_status: int | None = None,
        response: dict[str, Any] | None = None,
        error: str = "",
        dry_run: bool = False,
    ) -> None:
        now = time.monotonic() if now_monotonic_s is None else float(now_monotonic_s)
        self.last_action_monotonic_s = now
        if action.action == "cmd_vel":
            self.counters["cmd_vel_posts"] += 1
            self.active_command_posted = self._nonzero(
                float(action.payload.get("linear_x", 0.0) or 0.0),
                float(action.payload.get("angular_z", 0.0) or 0.0),
            )
        elif action.action == "stop":
            self.counters["stop_posts"] += 1
            self.active_command_posted = False
            self.stale_stop_sent = True
        if dry_run:
            self.counters["dry_run_actions"] += 1
        if http_status == 423:
            self.counters["http_refusals"] += 1
        if error:
            self.counters["http_errors"] += 1
        self.events.append(
            {
                "at_utc": utc_now(),
                "action": action.action,
                "reason": action.reason,
                "payload": action.payload,
                "http_status": http_status,
                "response": response or {},
                "error": error,
                "dry_run": bool(dry_run),
            }
        )
        self.events = self.events[-200:]

    def summary(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "counters": dict(self.counters),
            "last_input": asdict(self.last_input) if self.last_input is not None else {},
            "active_command_posted": bool(self.active_command_posted),
            "stale_stop_sent": bool(self.stale_stop_sent),
            "events": list(self.events),
        }


class FactoryBridgeCmdVelRelay(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("factory_bridge_cmd_vel_relay")
        self.args = args
        self.summary_path = Path(args.summary_path).resolve()
        self.summary: dict[str, Any] = {
            "type": "factory_bridge_cmd_vel_relay",
            "started_at_utc": utc_now(),
            "base_url": args.base_url,
            "dry_run": bool(args.dry_run),
            "twist_topics": split_topics(args.twist_topics),
            "twist_stamped_topics": split_topics(args.twist_stamped_topics),
            "bridge_health": {},
            "issues": [],
        }
        self.core = RelayCore(
            RelayConfig(
                linear_scale=float(args.linear_scale),
                angular_scale=float(args.angular_scale),
                max_bridge_linear_x=float(args.max_bridge_linear_x),
                max_bridge_angular_z=float(args.max_bridge_angular_z),
                command_duration_s=float(args.command_duration_s),
                post_rate_hz=float(args.post_rate_hz),
                stale_stop_s=float(args.stale_stop_s),
            )
        )
        self.client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
        self._check_bridge_health()
        self._create_subscriptions()
        self.create_timer(1.0 / max(float(args.post_rate_hz), 0.1), self._on_timer)
        self._write_summary()

    def _check_bridge_health(self) -> None:
        if self.args.dry_run:
            return
        try:
            status, payload = self.client.health()
            self.summary["bridge_health"] = {"http_status": status, "response": payload}
            if bool(self.args.require_motion_enabled) and not bool(payload.get("motion_enabled", False)):
                self.summary["issues"].append("bridge_motion_not_enabled")
                self.get_logger().warn("Factory bridge motion is not enabled; live commands will be refused.")
        except Exception as exc:
            self.summary["issues"].append(f"bridge_health_failed:{exc!r}")
            self.get_logger().warn(f"Factory bridge health check failed: {exc!r}")

    def _create_subscriptions(self) -> None:
        for topic in split_topics(self.args.twist_topics):
            self.create_subscription(Twist, topic, self._twist_callback(topic), 10)
            self.get_logger().info(f"Subscribing to {topic} as Twist")
        for topic in split_topics(self.args.twist_stamped_topics):
            self.create_subscription(TwistStamped, topic, self._twist_stamped_callback(topic), 10)
            self.get_logger().info(f"Subscribing to {topic} as TwistStamped")

    def _twist_callback(self, topic: str):
        def callback(msg: Twist) -> None:
            self.core.update_command(
                topic=topic,
                message_type="geometry_msgs/msg/Twist",
                linear_x=float(msg.linear.x),
                angular_z=float(msg.angular.z),
            )

        return callback

    def _twist_stamped_callback(self, topic: str):
        def callback(msg: TwistStamped) -> None:
            self.core.update_command(
                topic=topic,
                message_type="geometry_msgs/msg/TwistStamped",
                linear_x=float(msg.twist.linear.x),
                angular_z=float(msg.twist.angular.z),
            )

        return callback

    def _on_timer(self) -> None:
        action = self.core.next_action()
        if action is None:
            return
        if self.args.dry_run:
            self.core.record_action_result(action, dry_run=True)
            self._write_summary()
            return
        try:
            if action.action == "cmd_vel":
                payload = action.payload
                status, response = self.client.cmd_vel(
                    payload["linear_x"],
                    payload["angular_z"],
                    payload["duration_s"],
                    payload["source"],
                )
            elif action.action == "stop":
                status, response = self.client.stop(action.payload["source"])
            else:
                return
            self.core.record_action_result(action, http_status=status, response=response)
        except bridge_client.BridgeHttpError as exc:
            response = exc.payload if isinstance(exc.payload, dict) else {}
            self.core.record_action_result(action, http_status=exc.status_code, response=response, error=str(exc))
            if exc.status_code != 423:
                self.get_logger().warn(f"Factory bridge HTTP error: {exc.status_code} {response}")
        except Exception as exc:
            self.core.record_action_result(action, error=repr(exc))
            self.get_logger().warn(f"Factory bridge command failed: {exc!r}")
        self._write_summary()

    def _write_summary(self) -> None:
        payload = dict(self.summary)
        payload["updated_at_utc"] = utc_now()
        payload["relay"] = self.core.summary()
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def close(self) -> None:
        if not self.args.dry_run:
            try:
                self.client.stop("factory_bridge_cmd_vel_relay:shutdown_stop")
            except Exception as exc:
                self.summary["issues"].append(f"shutdown_stop_failed:{exc!r}")
        self._write_summary()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forward Chasecar ROS cmd_vel topics to the factory robot bridge.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=1.0)
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--twist-topics", default="/cmd_vel,/cmd_vel_nav")
    parser.add_argument("--twist-stamped-topics", default="/jetbot_base_controller/cmd_vel")
    parser.add_argument("--linear-scale", type=float, default=3.0)
    parser.add_argument("--angular-scale", type=float, default=3.0)
    parser.add_argument("--max-bridge-linear-x", type=float, default=0.36)
    parser.add_argument("--max-bridge-angular-z", type=float, default=1.0)
    parser.add_argument("--command-duration-s", type=float, default=0.20)
    parser.add_argument("--post-rate-hz", type=float, default=5.0)
    parser.add_argument("--stale-stop-s", type=float, default=0.45)
    parser.add_argument("--require-motion-enabled", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    args, ros_args = build_parser().parse_known_args(argv)
    args.ros_args = ros_args
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rclpy.init(args=getattr(args, "ros_args", None))
    node = FactoryBridgeCmdVelRelay(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down factory bridge cmd_vel relay...")
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
