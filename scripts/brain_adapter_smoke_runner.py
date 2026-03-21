#!/usr/bin/env python3
"""Deterministic pre-LLM brain adapter smoke runner.

This smoke validates that the frozen pre-LLM contract can be exercised
against the low-level stack without changing autonomy codepaths.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

import rclpy
from geometry_msgs.msg import PointStamped, Twist, TwistStamped
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSPresetProfiles
from std_msgs.msg import String


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run pre-LLM brain adapter smoke checks.")
    parser.add_argument(
        "--contract",
        default=str(repo_root / "runtime" / "contracts" / "llm_control_contract.yaml"),
        help="Path to frozen pre-LLM contract YAML.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSON summary.",
    )
    parser.add_argument(
        "--wait-timeout-s",
        type=float,
        default=25.0,
        help="Timeout for graph/message/action/service readiness checks.",
    )
    parser.add_argument(
        "--publish-interval-s",
        type=float,
        default=0.25,
        help="Delay between intent publish events.",
    )
    parser.add_argument(
        "--use-sim-time",
        action="store_true",
        default=True,
        help="Enable use_sim_time on the runner node (default: true).",
    )
    parser.add_argument(
        "--no-use-sim-time",
        dest="use_sim_time",
        action="store_false",
        help="Disable use_sim_time on the runner node.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_contract(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        raise ValueError("Contract YAML must deserialize to a mapping.")
    return data


def default_arg_value(arg_name: str):
    lowered = arg_name.lower()
    if "target_class" in lowered:
        return "ball"
    if "distance" in lowered:
        return 0.25
    if "timeout" in lowered:
        return 5.0
    if lowered.startswith("enable_"):
        return True
    return "default"


class BrainAdapterSmokeNode(Node):
    def __init__(self, use_sim_time: bool) -> None:
        super().__init__("brain_adapter_smoke_runner")
        if use_sim_time:
            self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])

        self.detection_count = 0
        self.odom_count = 0
        self.feedback_count = 0
        self.cmd_vel_count = 0

        self._subs = []

    def subscribe_topics(self, detection_topic: str, odom_topic: str, feedback_topic: str) -> None:
        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value
        self._subs.append(self.create_subscription(PointStamped, detection_topic, self._on_detection, sensor_qos))
        self._subs.append(self.create_subscription(Odometry, odom_topic, self._on_odom, sensor_qos))
        self._subs.append(self.create_subscription(String, feedback_topic, self._on_feedback, 20))

        for topic in ("/cmd_vel", "/cmd_vel_nav", "/jetbot_base_controller/cmd_vel"):
            self._subs.append(self.create_subscription(Twist, topic, self._on_cmd_vel, sensor_qos))
            self._subs.append(self.create_subscription(TwistStamped, topic, self._on_cmd_vel_stamped, sensor_qos))

    def _on_detection(self, _msg: PointStamped) -> None:
        self.detection_count += 1

    def _on_odom(self, _msg: Odometry) -> None:
        self.odom_count += 1

    def _on_feedback(self, _msg: String) -> None:
        self.feedback_count += 1

    def _on_cmd_vel(self, _msg: Twist) -> None:
        self.cmd_vel_count += 1

    def _on_cmd_vel_stamped(self, _msg: TwistStamped) -> None:
        self.cmd_vel_count += 1


def wait_for_topic_presence(node: Node, topics: List[str], timeout_s: float) -> Tuple[bool, Dict[str, bool], Dict[str, List[str]]]:
    deadline = time.monotonic() + max(timeout_s, 0.1)
    topic_present = {topic: False for topic in topics}
    topic_types: Dict[str, List[str]] = {topic: [] for topic in topics}
    while time.monotonic() < deadline and rclpy.ok():
        graph = dict(node.get_topic_names_and_types())
        for topic in topics:
            if topic in graph:
                topic_present[topic] = True
                topic_types[topic] = list(graph[topic])
        if all(topic_present.values()):
            return True, topic_present, topic_types
        rclpy.spin_once(node, timeout_sec=0.1)
    return all(topic_present.values()), topic_present, topic_types


def wait_for_data(node: BrainAdapterSmokeNode, timeout_s: float) -> Tuple[bool, bool]:
    deadline = time.monotonic() + max(timeout_s, 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        if node.detection_count > 0 and node.odom_count > 0:
            return True, True
        rclpy.spin_once(node, timeout_sec=0.1)
    return node.detection_count > 0, node.odom_count > 0


def collect_graph_snapshot(node: Node) -> Dict:
    topics = node.get_topic_names_and_types()
    services = node.get_service_names_and_types()
    actions = []
    try:
        proc = subprocess.run(
            ["ros2", "action", "list", "-t"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            for raw in proc.stdout.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if " [" in line and line.endswith("]"):
                    name, typ = line.split(" [", 1)
                    actions.append({"name": name.strip(), "types": [typ[:-1].strip()]})
                else:
                    actions.append({"name": line, "types": []})
    except Exception:
        actions = []
    return {
        "topics": [{"name": name, "types": list(types)} for name, types in sorted(topics)],
        "actions": actions,
        "services": [{"name": name, "types": list(types)} for name, types in sorted(services)],
    }


def main() -> int:
    args = parse_args()
    contract_path = Path(args.contract).resolve()
    output_path = Path(args.output).resolve()

    contract = load_contract(contract_path)
    contract_status = str(contract.get("contract_status", ""))
    intents = list(contract.get("intents", []))
    transport = dict(contract.get("transport", {}))
    boundary = dict(contract.get("low_level_boundary", {}))

    command_topic = str(transport.get("command_topic", "/chasecar/brain/intent"))
    feedback_topic = str(transport.get("feedback_topic", "/chasecar/brain/feedback"))
    topics_consumed = [str(t) for t in list(boundary.get("topics_consumed", []))]
    topics_published = [str(t) for t in list(boundary.get("topics_published", []))]
    actions_expected = [str(a) for a in list(boundary.get("actions", []))]
    services_expected = [str(s) for s in list(boundary.get("services", []))]

    required_intents = {"search_for_target", "acquire_target", "plan_to_target", "track_target", "abort", "safe_stop"}
    available_intents = {str(intent.get("name", "")) for intent in intents}
    required_intents_present = required_intents.issubset(available_intents)

    detection_topic = "/yolo/ball_position_3d"
    odom_topic = "/odom"
    for topic in topics_consumed:
        if topic.endswith("ball_position_3d"):
            detection_topic = topic
        if topic.endswith("/odom") or topic == "/odom":
            odom_topic = topic

    rclpy.init()
    node = BrainAdapterSmokeNode(use_sim_time=args.use_sim_time)
    node.subscribe_topics(detection_topic=detection_topic, odom_topic=odom_topic, feedback_topic=feedback_topic)

    intent_pub = node.create_publisher(String, command_topic, 20)
    nav2_client = ActionClient(node, NavigateToPose, "/navigate_to_pose")
    lifecycle_client = node.create_client(ManageLifecycleNodes, "/lifecycle_manager_navigation/manage_nodes")

    topic_check_targets = list(dict.fromkeys([detection_topic, odom_topic] + topics_published))
    graph_topics_ok, topic_presence, topic_types = wait_for_topic_presence(
        node, topics=topic_check_targets, timeout_s=args.wait_timeout_s
    )
    detection_seen, odom_seen = wait_for_data(node, timeout_s=args.wait_timeout_s)
    action_ready = bool(nav2_client.wait_for_server(timeout_sec=max(args.wait_timeout_s, 0.1)))
    service_ready = bool(lifecycle_client.wait_for_service(timeout_sec=max(args.wait_timeout_s, 0.1)))

    published_payloads = []
    for idx, intent in enumerate(intents, start=1):
        intent_name = str(intent.get("name", "")).strip()
        required_args = list(intent.get("required_args", []))
        payload = {
            "intent": intent_name,
            "seq": idx,
            "timestamp_utc": utc_now(),
            "args": {str(arg): default_arg_value(str(arg)) for arg in required_args},
        }
        msg = String()
        msg.data = json.dumps(payload, separators=(",", ":"))
        intent_pub.publish(msg)
        published_payloads.append(payload)
        spin_deadline = time.monotonic() + max(args.publish_interval_s, 0.05)
        while time.monotonic() < spin_deadline and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)

    graph_snapshot = collect_graph_snapshot(node)
    action_names_in_graph = {entry["name"] for entry in graph_snapshot["actions"]}
    service_names_in_graph = {entry["name"] for entry in graph_snapshot["services"]}

    actions_graph_ok = all(name in action_names_in_graph for name in actions_expected)
    services_graph_ok = all(name in service_names_in_graph for name in services_expected)

    cmd_vel_exact = topic_presence.get("/cmd_vel", False)
    cmd_vel_alias = (
        topic_presence.get("/cmd_vel_nav", False)
        or topic_presence.get("/jetbot_base_controller/cmd_vel", False)
    )
    cmd_vel_boundary_ok = bool(cmd_vel_exact or cmd_vel_alias)

    checks = {
        "contract_status_frozen": contract_status == "frozen_pre_llm",
        "required_intents_present": required_intents_present,
        "intents_published": len(published_payloads) == len(intents),
        "detection_topic_present": bool(topic_presence.get(detection_topic, False)),
        "odom_topic_present": bool(topic_presence.get(odom_topic, False)),
        "nav2_action_server_ready": action_ready,
        "lifecycle_service_ready": service_ready,
        "actions_graph_ok": actions_graph_ok,
        "services_graph_ok": services_graph_ok,
        "cmd_vel_boundary_ok": cmd_vel_boundary_ok,
    }

    warnings: List[str] = []
    if not cmd_vel_exact and cmd_vel_alias:
        warnings.append("cmd_vel exact topic missing; alias topic observed.")
    if node.feedback_count == 0:
        warnings.append("No feedback topic messages observed during smoke window.")

    passed = all(checks.values())

    summary = {
        "run_id": output_path.parent.name,
        "generated_utc": utc_now(),
        "type": "brain_adapter_smoke",
        "contract_path": str(contract_path),
        "contract_status": contract_status,
        "command_topic": command_topic,
        "feedback_topic": feedback_topic,
        "topics_consumed": topics_consumed,
        "topics_published": topics_published,
        "actions_expected": actions_expected,
        "services_expected": services_expected,
        "checks": checks,
        "message_counts": {
            "detection": node.detection_count,
            "odom": node.odom_count,
            "cmd_vel": node.cmd_vel_count,
            "feedback": node.feedback_count,
        },
        "stream_activity": {
            "detection_seen": detection_seen,
            "odom_seen": odom_seen,
        },
        "intent_publish_count": len(published_payloads),
        "intent_names": [str(intent.get("name", "")) for intent in intents],
        "published_payloads": published_payloads,
        "topic_presence": topic_presence,
        "topic_types": topic_types,
        "graph_snapshot": graph_snapshot,
        "warnings": warnings,
        "pass": passed,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"BRAIN_ADAPTER_SMOKE_REPORT={output_path}")
    print(f"BRAIN_ADAPTER_SMOKE_STATUS={'pass' if passed else 'fail'}")

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
