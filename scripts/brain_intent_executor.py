#!/usr/bin/env python3
"""Bounded executor for frozen brain intents."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rclpy
from geometry_msgs.msg import PointStamped
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSPresetProfiles
from std_msgs.msg import String


REPO_ROOT = Path(__file__).resolve().parents[1]
ROS2_SCRIPTS = REPO_ROOT / "ros2_scripts"
if str(ROS2_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ROS2_SCRIPTS))

from nav_goal_planner import build_goal_pose  # noqa: E402
from nav_goal_planner import plan_approach_from_detection  # noqa: E402
from nav_goal_planner import pose_to_robot_pose  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_angle(value: float) -> float:
    while value > math.pi:
        value -= 2.0 * math.pi
    while value < -math.pi:
        value += 2.0 * math.pi
    return value


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run the bounded frozen brain-intent executor.")
    parser.add_argument("--intent-topic", default="/chasecar/brain/intent")
    parser.add_argument("--feedback-topic", default="/chasecar/brain/feedback")
    parser.add_argument("--detection-topic", default="/yolo/ball_position_3d")
    parser.add_argument("--goal-topic", default="/chasecar/nav_goal_pose")
    parser.add_argument("--cmd-vel-topic", default="/cmd_vel")
    parser.add_argument("--goal-frame", default="odom")
    parser.add_argument("--odom-topic", default="/odom")
    parser.add_argument("--odom-topics", default="")
    parser.add_argument("--approach-distance-m", type=float, default=0.25)
    parser.add_argument("--search-turn-speed-radps", type=float, default=0.3)
    parser.add_argument("--search-max-rotation-rad", type=float, default=6.6)
    parser.add_argument("--search-timeout-s", type=float, default=28.0)
    parser.add_argument("--search-detection-burst", type=int, default=2)
    parser.add_argument("--detection-stale-after-s", type=float, default=1.5)
    parser.add_argument("--track-replan-cooldown-s", type=float, default=1.5)
    parser.add_argument("--state-json", default=str(repo_root / "runtime" / "dashboard" / "brain_executor_state.json"))
    parser.add_argument("--feedback-jsonl", default="")
    parser.add_argument(
        "--use-sim-time",
        action="store_true",
        default=True,
        help="Enable use_sim_time on this node (default: true).",
    )
    parser.add_argument(
        "--no-use-sim-time",
        dest="use_sim_time",
        action="store_false",
        help="Disable use_sim_time on this node.",
    )
    return parser.parse_args()


class BrainIntentExecutor(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("brain_intent_executor")
        self.args = args
        if args.use_sim_time:
            self.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])

        self.state_path = Path(args.state_json).resolve() if args.state_json else None
        self.feedback_history_path = Path(args.feedback_jsonl).resolve() if args.feedback_jsonl else None
        if self.state_path is not None:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if self.feedback_history_path is not None:
            self.feedback_history_path.parent.mkdir(parents=True, exist_ok=True)

        self.latest_detection: PointStamped | None = None
        self.last_detection_monotonic = 0.0
        self.detection_burst_count = 0
        self.latest_pose = None
        self.latest_pose_stamp = ""
        self.latest_goal_pose: PoseStamped | None = None
        self.last_goal_dispatched_monotonic = 0.0
        self.last_goal_dispatched_utc = ""

        self.feedback_count = 0
        self.last_feedback_text = ""
        self.last_feedback_utc = ""

        self.last_intent = ""
        self.last_intent_args: dict[str, Any] = {}

        self.search_active = False
        self.search_state = "idle"
        self.search_started_monotonic = 0.0
        self.search_rotation_accum_rad = 0.0
        self.search_last_yaw: float | None = None
        self.search_target_class = ""

        self.target_locked = False
        self.target_locked_class = ""
        self.target_locked_utc = ""

        self.track_active = False
        self.track_needs_replan = False

        self.goal_in_progress = False
        self.current_goal_handle = None
        self.pending_cancel_reason = ""
        self.last_state_write_monotonic = 0.0

        default_qos = QoSPresetProfiles.SENSOR_DATA.value
        self.feedback_pub = self.create_publisher(String, args.feedback_topic, 20)
        self.cmd_vel_pub = self.create_publisher(Twist, args.cmd_vel_topic, 20)
        self.robot_cmd_vel_pub = self.create_publisher(TwistStamped, "/jetbot_base_controller/cmd_vel", 20)
        self.goal_pose_pub = self.create_publisher(PoseStamped, args.goal_topic, 20)
        self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

        self.create_subscription(String, args.intent_topic, self._on_intent, 20)
        self.create_subscription(PointStamped, args.detection_topic, self._on_detection, default_qos)
        for topic in self._odom_topic_candidates():
            self.create_subscription(Odometry, topic, self._on_odom, default_qos)
        self.timer = self.create_timer(0.1, self._on_timer)
        self._write_state(force=True)

    def _odom_topic_candidates(self) -> list[str]:
        topics: list[str] = []
        raw = [self.args.odom_topic]
        if self.args.odom_topics.strip():
            raw.extend([item.strip() for item in self.args.odom_topics.split(",") if item.strip()])
        raw.extend(["/odom", "/model/jetbot/odometry", "/jetbot_base_controller/odom"])
        for topic in raw:
            if topic and topic not in topics:
                topics.append(topic)
        return topics

    def _target_visible_recent(self) -> bool:
        return self.latest_detection is not None and (time.monotonic() - self.last_detection_monotonic) <= max(self.args.detection_stale_after_s, 0.1)

    def _publish_feedback(self, text: str, *, status: str, extra: dict[str, Any] | None = None) -> None:
        msg = String()
        msg.data = text
        self.feedback_pub.publish(msg)
        self.feedback_count += 1
        self.last_feedback_text = text
        self.last_feedback_utc = utc_now()
        if self.feedback_history_path is not None:
            payload = {
                "generated_utc": self.last_feedback_utc,
                "status": status,
                "text": text,
                "last_intent": self.last_intent,
                "last_intent_args": dict(self.last_intent_args),
                "search_state": self.search_state,
                "target_locked": self.target_locked,
                "goal_in_progress": self.goal_in_progress,
            }
            if extra:
                payload.update(extra)
            with self.feedback_history_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        self._write_state(force=True)

    def _publish_twist(self, twist: Twist) -> None:
        self.cmd_vel_pub.publish(twist)
        stamped = TwistStamped()
        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.header.frame_id = ""
        stamped.twist = twist
        self.robot_cmd_vel_pub.publish(stamped)

    def _publish_stop(self) -> None:
        self._publish_twist(Twist())

    def _cancel_goal(self, reason: str) -> None:
        if self.current_goal_handle is None:
            self.goal_in_progress = False
            return
        try:
            self.pending_cancel_reason = reason
            self.current_goal_handle.cancel_goal_async()
        except Exception as exc:
            self.get_logger().warn(f"Goal cancel failed: {exc}")
        self.current_goal_handle = None
        self.goal_in_progress = False

    def _clear_motion_state(self) -> None:
        self.search_active = False
        self.search_state = "idle"
        self.search_started_monotonic = 0.0
        self.search_rotation_accum_rad = 0.0
        self.search_last_yaw = None
        self.track_active = False
        self.track_needs_replan = False

    def _lock_target(self, target_class: str, source: str) -> None:
        self.target_locked = True
        self.target_locked_class = target_class
        self.target_locked_utc = utc_now()
        if self.search_active:
            self.search_active = False
            self.search_state = "locked"
            self._publish_stop()
        self._publish_feedback(
            f"{source}: target locked for {target_class}",
            status="locked",
            extra={"target_class": target_class},
        )

    def _dispatch_nav_goal(self, *, reason: str, approach_distance_m: float) -> bool:
        if self.latest_detection is None or not self._target_visible_recent():
            self._publish_feedback(
                f"{reason}: blocked because target is not visible",
                status="blocked",
            )
            return False
        if self.latest_pose is None:
            self._publish_feedback(
                f"{reason}: blocked because odom is unavailable",
                status="blocked",
            )
            return False
        if not self.nav_client.server_is_ready():
            if not self.nav_client.wait_for_server(timeout_sec=0.5):
                self._publish_feedback(
                    f"{reason}: blocked because Nav2 is unavailable",
                    status="blocked",
                )
                return False

        plan = plan_approach_from_detection(
            robot_pose=self.latest_pose,
            detection=self.latest_detection,
            approach_distance_m=approach_distance_m,
        )
        if plan is None:
            self._publish_feedback(
                f"{reason}: already within approach distance",
                status="noop",
            )
            return False

        if self.goal_in_progress:
            self._cancel_goal(f"{reason}: replacing active goal")

        goal_pose = build_goal_pose(
            goal_frame=self.args.goal_frame,
            goal_x_world=plan.goal_x_world,
            goal_y_world=plan.goal_y_world,
            face_x_world=plan.ball_x_world,
            face_y_world=plan.ball_y_world,
            stamp=self.get_clock().now().to_msg(),
        )
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        goal_msg.behavior_tree = ""

        self.latest_goal_pose = goal_pose
        self.goal_pose_pub.publish(goal_pose)
        self.goal_in_progress = True
        self.last_goal_dispatched_monotonic = time.monotonic()
        self.last_goal_dispatched_utc = utc_now()
        send_goal_future = self.nav_client.send_goal_async(goal_msg, feedback_callback=self._on_nav_feedback)
        send_goal_future.add_done_callback(self._on_goal_response)
        self._publish_feedback(
            f"{reason}: nav goal dispatched to ({plan.goal_x_world:.2f}, {plan.goal_y_world:.2f})",
            status="goal_dispatched",
            extra={
                "goal_x_world": round(plan.goal_x_world, 4),
                "goal_y_world": round(plan.goal_y_world, 4),
                "distance_to_ball_m": round(plan.distance_to_ball_m, 4),
            },
        )
        return True

    def _on_goal_response(self, future) -> None:
        try:
            goal_handle = future.result()
        except Exception as exc:
            self.goal_in_progress = False
            self._publish_feedback(f"nav goal rejected: {exc}", status="goal_rejected")
            return
        if not goal_handle.accepted:
            self.goal_in_progress = False
            self.current_goal_handle = None
            self._publish_feedback("nav goal rejected by Nav2", status="goal_rejected")
            return
        self.current_goal_handle = goal_handle
        self._publish_feedback("nav goal accepted by Nav2", status="goal_accepted")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_goal_result)

    def _on_nav_feedback(self, _feedback_msg) -> None:
        self._write_state(force=False)

    def _on_goal_result(self, future) -> None:
        self.goal_in_progress = False
        self.current_goal_handle = None
        try:
            result = future.result()
            status = int(result.status)
        except Exception as exc:
            self._publish_feedback(f"nav goal result failed: {exc}", status="goal_error")
            return
        if status == 4:
            self._publish_feedback("nav goal reached successfully", status="goal_succeeded")
        elif status == 5:
            reason = self.pending_cancel_reason or "nav goal canceled"
            self._publish_feedback(reason, status="goal_canceled")
        elif status == 6:
            self._publish_feedback("nav goal aborted by Nav2", status="goal_aborted")
        else:
            self._publish_feedback(f"nav goal finished with status {status}", status="goal_finished")
        self.pending_cancel_reason = ""
        if self.track_active:
            self.track_needs_replan = self._target_visible_recent()

    def _on_detection(self, msg: PointStamped) -> None:
        now = time.monotonic()
        if now - self.last_detection_monotonic <= 0.75:
            self.detection_burst_count += 1
        else:
            self.detection_burst_count = 1
        self.latest_detection = msg
        self.last_detection_monotonic = now
        if self.search_active and self.detection_burst_count >= max(self.args.search_detection_burst, 1):
            self._lock_target(self.search_target_class or "ball", "search_for_target")
            self.track_needs_replan = False
        elif self.track_active and not self.goal_in_progress:
            self.track_needs_replan = True
        self._write_state(force=False)

    def _on_odom(self, msg: Odometry) -> None:
        pose = pose_to_robot_pose(msg.pose.pose)
        if self.search_active and self.search_last_yaw is not None:
            delta = normalize_angle(pose.yaw - self.search_last_yaw)
            self.search_rotation_accum_rad += abs(delta)
        if self.search_active:
            self.search_last_yaw = pose.yaw
        self.latest_pose = pose
        self.latest_pose_stamp = utc_now()
        self._write_state(force=False)

    def _handle_search_intent(self, args_payload: dict[str, Any]) -> None:
        target_class = str(args_payload.get("target_class", "")).strip() or "ball"
        self._cancel_goal("search_for_target preempted active goal")
        self.track_active = False
        self.track_needs_replan = False
        self.target_locked = False
        self.target_locked_class = ""
        if self._target_visible_recent():
            self._lock_target(target_class, "search_for_target")
            return
        if self.latest_pose is None:
            self._publish_feedback("search_for_target: blocked because odom is unavailable", status="blocked")
            return
        self.search_active = True
        self.search_state = "rotating"
        self.search_started_monotonic = time.monotonic()
        self.search_rotation_accum_rad = 0.0
        self.search_last_yaw = self.latest_pose.yaw
        self.search_target_class = target_class
        self._publish_feedback(
            f"search_for_target: rotating to find {target_class}",
            status="search_active",
            extra={"target_class": target_class},
        )

    def _handle_acquire_intent(self, args_payload: dict[str, Any]) -> None:
        target_class = str(args_payload.get("target_class", "")).strip() or "ball"
        if not self._target_visible_recent():
            self._publish_feedback("acquire_target: blocked because target is not visible", status="blocked")
            return
        self._lock_target(target_class, "acquire_target")

    def _handle_plan_intent(self, args_payload: dict[str, Any]) -> None:
        approach_distance_m = float(args_payload.get("approach_distance_m", self.args.approach_distance_m))
        if not self.target_locked and self._target_visible_recent():
            self._lock_target("ball", "plan_to_target")
        self.track_active = False
        self.track_needs_replan = False
        self._dispatch_nav_goal(reason="plan_to_target", approach_distance_m=approach_distance_m)

    def _handle_track_intent(self) -> None:
        self.track_active = True
        self.track_needs_replan = True
        self._publish_feedback("track_target: tracking enabled", status="track_active")

    def _handle_abort_intent(self) -> None:
        self._clear_motion_state()
        self._cancel_goal("abort: canceled active behavior")
        self._publish_stop()
        self._publish_feedback("abort: active behavior canceled", status="aborted")

    def _handle_safe_stop_intent(self) -> None:
        self._clear_motion_state()
        self._cancel_goal("safe_stop: canceled active behavior")
        self._publish_stop()
        self._publish_feedback("safe_stop: robot stopped", status="stopped")

    def _on_intent(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self._publish_feedback(f"invalid intent payload: {exc}", status="invalid")
            return
        if not isinstance(payload, dict):
            self._publish_feedback("invalid intent payload: expected object", status="invalid")
            return
        intent_name = str(payload.get("intent", "")).strip()
        args_payload = payload.get("args", {})
        if not isinstance(args_payload, dict):
            args_payload = {}
        self.last_intent = intent_name
        self.last_intent_args = dict(args_payload)
        if intent_name == "search_for_target":
            self._handle_search_intent(dict(args_payload))
        elif intent_name == "acquire_target":
            self._handle_acquire_intent(dict(args_payload))
        elif intent_name == "plan_to_target":
            self._handle_plan_intent(dict(args_payload))
        elif intent_name == "track_target":
            self._handle_track_intent()
        elif intent_name == "abort":
            self._handle_abort_intent()
        elif intent_name == "safe_stop":
            self._handle_safe_stop_intent()
        else:
            self._publish_feedback(f"unsupported intent: {intent_name}", status="unsupported")

    def _on_timer(self) -> None:
        if self.search_active:
            elapsed = time.monotonic() - self.search_started_monotonic
            if self._target_visible_recent() and self.detection_burst_count >= max(self.args.search_detection_burst, 1):
                self._lock_target(self.search_target_class or "ball", "search_for_target")
            elif (
                self.search_rotation_accum_rad >= max(self.args.search_max_rotation_rad, 0.1)
                or elapsed >= max(self.args.search_timeout_s, 0.5)
            ):
                self.search_active = False
                self.search_state = "failed"
                self._publish_stop()
                self._publish_feedback("search_for_target: full scan completed without target lock", status="search_failed")
            else:
                twist = Twist()
                twist.angular.z = float(self.args.search_turn_speed_radps)
                self._publish_twist(twist)

        if (
            self.track_active
            and self.track_needs_replan
            and not self.search_active
            and not self.goal_in_progress
            and (time.monotonic() - self.last_goal_dispatched_monotonic) >= max(self.args.track_replan_cooldown_s, 0.2)
        ):
            dispatched = self._dispatch_nav_goal(reason="track_target", approach_distance_m=float(self.args.approach_distance_m))
            self.track_needs_replan = not dispatched and self._target_visible_recent()

        self._write_state(force=False)

    def _write_state(self, *, force: bool) -> None:
        if self.state_path is None:
            return
        now = time.monotonic()
        if not force and (now - self.last_state_write_monotonic) < 0.2:
            return
        payload: dict[str, Any] = {
            "generated_utc": utc_now(),
            "search_active": self.search_active,
            "search_state": self.search_state,
            "search_rotation_accum_rad": round(self.search_rotation_accum_rad, 6),
            "target_visible_recent": self._target_visible_recent(),
            "target_locked": self.target_locked,
            "target_locked_class": self.target_locked_class,
            "target_locked_utc": self.target_locked_utc,
            "track_active": self.track_active,
            "track_needs_replan": self.track_needs_replan,
            "goal_in_progress": self.goal_in_progress,
            "last_goal_dispatched_utc": self.last_goal_dispatched_utc,
            "last_intent": self.last_intent,
            "last_intent_args": self.last_intent_args,
            "last_feedback_text": self.last_feedback_text,
            "last_feedback_utc": self.last_feedback_utc,
            "feedback_count": self.feedback_count,
            "detection_burst_count": self.detection_burst_count,
            "latest_pose_stamp_utc": self.latest_pose_stamp,
        }
        if self.latest_pose is not None:
            payload["latest_robot_pose"] = asdict(self.latest_pose)
        if self.latest_goal_pose is not None:
            payload["latest_goal_pose"] = {
                "x": round(float(self.latest_goal_pose.pose.position.x), 6),
                "y": round(float(self.latest_goal_pose.pose.position.y), 6),
                "frame_id": self.latest_goal_pose.header.frame_id,
            }
        if self.latest_detection is not None:
            payload["latest_detection_local"] = {
                "x": round(float(self.latest_detection.point.x), 6),
                "y": round(float(self.latest_detection.point.y), 6),
                "z": round(float(self.latest_detection.point.z), 6),
            }
            if self.latest_pose is not None:
                plan = plan_approach_from_detection(
                    robot_pose=self.latest_pose,
                    detection=self.latest_detection,
                    approach_distance_m=float(self.args.approach_distance_m),
                )
                if plan is not None:
                    payload["latest_target_distance_m"] = round(float(plan.distance_to_ball_m), 6)
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.last_state_write_monotonic = now


def main() -> int:
    args = parse_args()
    rclpy.init()
    node = BrainIntentExecutor(args)
    try:
        node.get_logger().info("Brain intent executor running.")
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Brain intent executor interrupted.")
    finally:
        node._publish_stop()
        node._write_state(force=True)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
