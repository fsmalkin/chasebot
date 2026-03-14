#!/usr/bin/env python3
"""Deterministic planner-shell runner for the frozen pre-LLM contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped, Twist, TwistStamped
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
    parser = argparse.ArgumentParser(description="Run deterministic planner-shell contract checks.")
    parser.add_argument(
        "--contract",
        default=str(repo_root / "runtime" / "contracts" / "llm_control_contract.yaml"),
        help="Path to frozen pre-LLM contract YAML.",
    )
    parser.add_argument("--output", required=True, help="Path to output JSON summary.")
    parser.add_argument("--wait-timeout-s", type=float, default=25.0, help="Boundary readiness timeout.")
    parser.add_argument("--step-timeout-s", type=float, default=1.0, help="Observation window after each intent publish.")
    parser.add_argument("--publish-interval-s", type=float, default=0.25, help="Delay between intent publishes.")
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


def load_contract(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        raise ValueError("Contract YAML must deserialize to a mapping.")
    return data


def default_arg_value(arg_name: str) -> Any:
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


class BrainIntentShellNode(Node):
    def __init__(self, use_sim_time: bool) -> None:
        super().__init__("brain_intent_shell_runner")
        if use_sim_time:
            self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])

        self.detection_count = 0
        self.odom_count = 0
        self.feedback_count = 0
        self.cmd_vel_count = 0
        self.nav_goal_count = 0
        self.feedback_samples: List[str] = []
        self._subs = []

    def subscribe_topics(
        self,
        detection_topic: str,
        odom_topic: str,
        feedback_topic: str,
        nav_goal_topic: str,
    ) -> None:
        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value
        self._subs.append(self.create_subscription(PointStamped, detection_topic, self._on_detection, sensor_qos))
        self._subs.append(self.create_subscription(Odometry, odom_topic, self._on_odom, sensor_qos))
        self._subs.append(self.create_subscription(String, feedback_topic, self._on_feedback, 20))
        self._subs.append(self.create_subscription(PoseStamped, nav_goal_topic, self._on_nav_goal, 20))

        for topic in ("/cmd_vel", "/cmd_vel_nav", "/jetbot_base_controller/cmd_vel"):
            self._subs.append(self.create_subscription(Twist, topic, self._on_cmd_vel, sensor_qos))
            self._subs.append(self.create_subscription(TwistStamped, topic, self._on_cmd_vel_stamped, sensor_qos))

    def snapshot_counts(self) -> Dict[str, int]:
        return {
            "detection": self.detection_count,
            "odom": self.odom_count,
            "feedback": self.feedback_count,
            "cmd_vel": self.cmd_vel_count,
            "nav_goal": self.nav_goal_count,
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


def wait_for_data(node: BrainIntentShellNode, timeout_s: float) -> Tuple[bool, bool]:
    deadline = time.monotonic() + max(timeout_s, 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        if node.detection_count > 0 and node.odom_count > 0:
            return True, True
        rclpy.spin_once(node, timeout_sec=0.1)
    return node.detection_count > 0, node.odom_count > 0


def collect_graph_snapshot(node: Node) -> Dict[str, Any]:
    topics = node.get_topic_names_and_types()
    services = node.get_service_names_and_types()
    actions: List[Dict[str, Any]] = []
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


def observe_after_publish(node: BrainIntentShellNode, publisher, payload: Dict[str, Any], settle_s: float) -> Dict[str, Any]:
    before = node.snapshot_counts()
    msg = String()
    msg.data = json.dumps(payload, separators=(",", ":"))
    publisher.publish(msg)
    deadline = time.monotonic() + max(settle_s, 0.05)
    while time.monotonic() < deadline and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.05)
    after = node.snapshot_counts()
    deltas = {key: after[key] - before[key] for key in after}
    return {
        "intent": payload["intent"],
        "payload": payload,
        "counts_before": before,
        "counts_after": after,
        "count_deltas": deltas,
        "feedback_seen": deltas["feedback"] > 0,
        "nav_goal_activity": deltas["nav_goal"] > 0,
        "cmd_vel_activity": deltas["cmd_vel"] > 0,
        "boundary_activity_seen": (deltas["feedback"] > 0 or deltas["nav_goal"] > 0 or deltas["cmd_vel"] > 0),
    }


def main() -> int:
    args = parse_args()
    contract_path = Path(args.contract).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    contract = load_contract(contract_path)
    contract_status = str(contract.get("contract_status", ""))
    intents = list(contract.get("intents", []))
    transport = dict(contract.get("transport", {}))
    boundary = dict(contract.get("low_level_boundary", {}))
    freeze_basis = dict(contract.get("freeze_basis", {}))

    required_sequence = ["search_for_target", "acquire_target", "plan_to_target", "track_target", "safe_stop"]
    intents_by_name = {str(intent.get("name", "")): intent for intent in intents}
    required_intents_present = all(name in intents_by_name for name in required_sequence)

    command_topic = str(transport.get("command_topic", "/chasecar/brain/intent"))
    feedback_topic = str(transport.get("feedback_topic", "/chasecar/brain/feedback"))
    topics_consumed = [str(t) for t in list(boundary.get("topics_consumed", []))]
    topics_published = [str(t) for t in list(boundary.get("topics_published", []))]
    actions_expected = [str(a) for a in list(boundary.get("actions", []))]
    services_expected = [str(s) for s in list(boundary.get("services", []))]

    detection_topic = "/yolo/ball_position_3d"
    odom_topic = "/odom"
    nav_goal_topic = "/chasecar/nav_goal_pose"
    for topic in topics_consumed:
        if topic.endswith("ball_position_3d"):
            detection_topic = topic
        if topic.endswith("/odom") or topic == "/odom":
            odom_topic = topic

    rclpy.init()
    node = BrainIntentShellNode(use_sim_time=args.use_sim_time)
    node.subscribe_topics(
        detection_topic=detection_topic,
        odom_topic=odom_topic,
        feedback_topic=feedback_topic,
        nav_goal_topic=nav_goal_topic,
    )

    intent_pub = node.create_publisher(String, command_topic, 20)
    nav2_client = ActionClient(node, NavigateToPose, "/navigate_to_pose")
    lifecycle_client = node.create_client(ManageLifecycleNodes, "/lifecycle_manager_navigation/manage_nodes")

    topic_targets = list(dict.fromkeys([detection_topic, odom_topic, feedback_topic] + topics_published))
    graph_topics_ok, topic_presence, topic_types = wait_for_topic_presence(node, topics=topic_targets, timeout_s=args.wait_timeout_s)
    detection_seen, odom_seen = wait_for_data(node, timeout_s=args.wait_timeout_s)
    action_ready = bool(nav2_client.wait_for_server(timeout_sec=max(args.wait_timeout_s, 0.1)))
    service_ready = bool(lifecycle_client.wait_for_service(timeout_sec=max(args.wait_timeout_s, 0.1)))

    sequence_results: List[Dict[str, Any]] = []
    for idx, intent_name in enumerate(required_sequence, start=1):
        intent_spec = intents_by_name.get(intent_name, {})
        required_args = list(intent_spec.get("required_args", []))
        payload = {
            "intent": intent_name,
            "seq": idx,
            "planner": "deterministic_shell",
            "timestamp_utc": utc_now(),
            "args": {str(arg): default_arg_value(str(arg)) for arg in required_args},
        }
        sequence_results.append(observe_after_publish(node, intent_pub, payload, args.step_timeout_s))
        settle_deadline = time.monotonic() + max(args.publish_interval_s, 0.05)
        while time.monotonic() < settle_deadline and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)

    graph_snapshot = collect_graph_snapshot(node)
    action_names_in_graph = {entry["name"] for entry in graph_snapshot["actions"]}
    service_names_in_graph = {entry["name"] for entry in graph_snapshot["services"]}
    actions_graph_ok = all(name in action_names_in_graph for name in actions_expected)
    services_graph_ok = all(name in service_names_in_graph for name in services_expected)

    checks = {
        "contract_status_frozen": contract_status == "frozen_pre_llm",
        "required_intents_present": required_intents_present,
        "graph_topics_ok": graph_topics_ok,
        "detection_topic_present": bool(topic_presence.get(detection_topic, False)),
        "odom_topic_present": bool(topic_presence.get(odom_topic, False)),
        "nav2_action_server_ready": action_ready,
        "lifecycle_service_ready": service_ready,
        "actions_graph_ok": actions_graph_ok,
        "services_graph_ok": services_graph_ok,
        "sequence_emitted": len(sequence_results) == len(required_sequence),
    }

    warnings: List[str] = []
    if not detection_seen:
        warnings.append("No detection samples observed during planner-shell readiness window.")
    if not odom_seen:
        warnings.append("No odom samples observed during planner-shell readiness window.")
    if node.feedback_count == 0:
        warnings.append("No brain feedback messages observed during deterministic shell run.")
    if not any(item["boundary_activity_seen"] for item in sequence_results):
        warnings.append("Intent publishes caused no observable feedback/nav_goal/cmd_vel deltas.")

    summary = {
        "run_id": output_path.parent.name,
        "generated_utc": utc_now(),
        "type": "brain_intent_shell",
        "contract_path": str(contract_path),
        "contract_status": contract_status,
        "freeze_basis": freeze_basis,
        "command_topic": command_topic,
        "feedback_topic": feedback_topic,
        "nav_goal_topic": nav_goal_topic,
        "topics_consumed": topics_consumed,
        "topics_published": topics_published,
        "actions_expected": actions_expected,
        "services_expected": services_expected,
        "checks": checks,
        "sequence": required_sequence,
        "sequence_results": sequence_results,
        "message_counts": node.snapshot_counts(),
        "stream_activity": {
            "detection_seen": detection_seen,
            "odom_seen": odom_seen,
            "feedback_seen": node.feedback_count > 0,
        },
        "feedback_samples": node.feedback_samples,
        "topic_presence": topic_presence,
        "topic_types": topic_types,
        "graph_snapshot": graph_snapshot,
        "warnings": warnings,
    }
    summary["pass"] = all(checks.values())

    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

    print(f"BRAIN_INTENT_SHELL_SUMMARY={output_path}")
    print(f"BRAIN_INTENT_SHELL_PASS={summary['pass']}")
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
