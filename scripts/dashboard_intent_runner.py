#!/usr/bin/env python3
"""Publish one frozen dashboard intent inside the authoritative ROS graph."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped, Twist, TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSPresetProfiles
from std_msgs.msg import String


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Publish one frozen dashboard intent and capture feedback.")
    parser.add_argument(
        "--contract",
        default=str(repo_root / "runtime" / "contracts" / "llm_control_contract.yaml"),
        help="Path to the frozen LLM control contract.",
    )
    parser.add_argument("--intent", required=True, help="Frozen intent name.")
    parser.add_argument("--args-json", default="{}", help="JSON object with intent args.")
    parser.add_argument("--output", required=True, help="Output JSON summary path.")
    parser.add_argument("--seq", type=int, default=0, help="Optional fixed sequence number for the published payload.")
    parser.add_argument("--planner", default="dashboard_service", help="Planner label to embed in the published payload.")
    parser.add_argument("--timestamp-utc", default="", help="Optional fixed UTC timestamp for the published payload.")
    parser.add_argument("--wait-timeout-s", type=float, default=12.0, help="Readiness timeout in seconds.")
    parser.add_argument("--observe-time-s", type=float, default=3.0, help="Observation window after publish.")
    parser.add_argument(
        "--use-sim-time",
        action="store_true",
        default=True,
        help="Enable use_sim_time on this runner node (default: true).",
    )
    parser.add_argument(
        "--no-use-sim-time",
        dest="use_sim_time",
        action="store_false",
        help="Disable use_sim_time on this runner node.",
    )
    return parser.parse_args()


def load_contract(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        payload = yaml.safe_load(fp) or {}
    if not isinstance(payload, dict):
        raise ValueError("Contract YAML must deserialize to a mapping.")
    return payload


class IntentProbeNode(Node):
    def __init__(self, use_sim_time: bool) -> None:
        super().__init__("dashboard_intent_runner")
        if use_sim_time:
            self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])

        self.feedback_samples: List[str] = []
        self.feedback_count = 0
        self.detection_count = 0
        self.odom_count = 0
        self.nav_goal_count = 0
        self.cmd_vel_count = 0
        self._subs = []

    def subscribe(self, detection_topic: str, odom_topic: str, feedback_topic: str) -> None:
        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value
        self._subs.append(self.create_subscription(PointStamped, detection_topic, self._on_detection, sensor_qos))
        self._subs.append(self.create_subscription(Odometry, odom_topic, self._on_odom, sensor_qos))
        self._subs.append(self.create_subscription(String, feedback_topic, self._on_feedback, 20))
        self._subs.append(self.create_subscription(PoseStamped, "/chasecar/nav_goal_pose", self._on_nav_goal, 20))
        for topic in ("/cmd_vel", "/cmd_vel_nav", "/jetbot_base_controller/cmd_vel"):
            self._subs.append(self.create_subscription(Twist, topic, self._on_cmd_vel, sensor_qos))
            self._subs.append(self.create_subscription(TwistStamped, topic, self._on_cmd_vel_stamped, sensor_qos))

    def snapshot_counts(self) -> Dict[str, int]:
        return {
            "feedback": self.feedback_count,
            "detection": self.detection_count,
            "odom": self.odom_count,
            "nav_goal": self.nav_goal_count,
            "cmd_vel": self.cmd_vel_count,
        }

    def _on_detection(self, _msg: PointStamped) -> None:
        self.detection_count += 1

    def _on_odom(self, _msg: Odometry) -> None:
        self.odom_count += 1

    def _on_feedback(self, msg: String) -> None:
        self.feedback_count += 1
        if len(self.feedback_samples) < 10:
            self.feedback_samples.append(msg.data)

    def _on_nav_goal(self, _msg: PoseStamped) -> None:
        self.nav_goal_count += 1

    def _on_cmd_vel(self, _msg: Twist) -> None:
        self.cmd_vel_count += 1

    def _on_cmd_vel_stamped(self, _msg: TwistStamped) -> None:
        self.cmd_vel_count += 1


def wait_for_data(node: IntentProbeNode, intent_name: str, timeout_s: float) -> Dict[str, bool]:
    deadline = time.monotonic() + max(timeout_s, 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        if intent_name == "search_for_target":
            if node.odom_count > 0:
                break
        elif intent_name in {"abort", "safe_stop"}:
            break
        elif node.detection_count > 0 and node.odom_count > 0:
            break
        rclpy.spin_once(node, timeout_sec=0.1)
    return {
        "detection_seen": node.detection_count > 0,
        "odom_seen": node.odom_count > 0,
    }


def main() -> int:
    args = parse_args()
    contract_path = Path(args.contract).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    contract = load_contract(contract_path)
    intents = list(contract.get("intents", []))
    intent_spec = None
    for candidate in intents:
        if str(candidate.get("name", "")).strip() == args.intent:
            intent_spec = dict(candidate)
            break
    if intent_spec is None:
        raise ValueError(f"Unsupported frozen intent: {args.intent}")

    transport = dict(contract.get("transport", {}))
    boundary = dict(contract.get("low_level_boundary", {}))
    required_args = [str(value) for value in list(intent_spec.get("required_args", []))]
    allowed_args = set(required_args)
    provided_args = json.loads(args.args_json)
    if not isinstance(provided_args, dict):
        raise ValueError("args-json must decode to a JSON object.")

    missing_args = [name for name in required_args if name not in provided_args]
    extra_args = sorted(name for name in provided_args.keys() if str(name) not in allowed_args)
    if missing_args:
        raise ValueError(f"Missing required args for {args.intent}: {', '.join(missing_args)}")
    if extra_args:
        raise ValueError(f"Unexpected args for {args.intent}: {', '.join(extra_args)}")

    command_topic = str(transport.get("command_topic", "/chasecar/brain/intent"))
    feedback_topic = str(transport.get("feedback_topic", "/chasecar/brain/feedback"))
    topics_consumed = [str(value) for value in list(boundary.get("topics_consumed", []))]

    detection_topic = "/yolo/ball_position_3d"
    odom_topic = "/odom"
    for topic in topics_consumed:
        if topic.endswith("ball_position_3d"):
            detection_topic = topic
        if topic == "/odom" or topic.endswith("/odom"):
            odom_topic = topic

    rclpy.init()
    node = IntentProbeNode(use_sim_time=args.use_sim_time)
    node.subscribe(detection_topic=detection_topic, odom_topic=odom_topic, feedback_topic=feedback_topic)
    readiness = wait_for_data(node, args.intent, timeout_s=args.wait_timeout_s)

    publisher = node.create_publisher(String, command_topic, 20)
    payload = {
        "intent": args.intent,
        "seq": int(args.seq or int(time.time() * 1000)),
        "planner": str(args.planner or "dashboard_service"),
        "timestamp_utc": str(args.timestamp_utc or utc_now()),
        "args": provided_args,
    }

    before = node.snapshot_counts()
    msg = String()
    msg.data = json.dumps(payload, separators=(",", ":"))
    publisher.publish(msg)

    deadline = time.monotonic() + max(args.observe_time_s, 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.05)

    after = node.snapshot_counts()
    count_deltas = {name: after[name] - before.get(name, 0) for name in after}
    feedback_seen = count_deltas["feedback"] > 0
    nav_goal_activity = count_deltas["nav_goal"] > 0
    cmd_vel_activity = count_deltas["cmd_vel"] > 0

    summary = {
        "generated_utc": utc_now(),
        "type": "dashboard_intent",
        "contract_path": str(contract_path),
        "contract_status": str(contract.get("contract_status", "")),
        "intent": args.intent,
        "payload": payload,
        "required_args": required_args,
        "command_topic": command_topic,
        "feedback_topic": feedback_topic,
        "readiness": readiness,
        "counts_before": before,
        "counts_after": after,
        "count_deltas": count_deltas,
        "feedback_seen": feedback_seen,
        "feedback_samples": node.feedback_samples,
        "nav_goal_activity": nav_goal_activity,
        "cmd_vel_activity": cmd_vel_activity,
        "boundary_activity_seen": bool(feedback_seen or nav_goal_activity or cmd_vel_activity),
        "pass": bool(feedback_seen or nav_goal_activity or cmd_vel_activity),
    }
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

    print(f"DASHBOARD_INTENT_SUMMARY={output_path}")
    print(f"DASHBOARD_INTENT_PASS={summary['pass']}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
