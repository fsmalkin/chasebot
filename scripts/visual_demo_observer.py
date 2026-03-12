#!/usr/bin/env python3
"""Record visual evidence and live dashboard frames from the authoritative ROS graph."""

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped, Twist, TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, QoSPresetProfiles, ReliabilityPolicy
from sensor_msgs.msg import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe ROS topics and emit recorded visual artifacts.")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execution-lane", default="container_kilted")
    parser.add_argument("--runtime-target", default="robot_fidelity_orin")
    parser.add_argument("--visual-mode", choices=("recorded", "browser_dashboard"), default="recorded")
    parser.add_argument("--phase", default="")
    parser.add_argument("--target-id", default="")
    parser.add_argument("--target-transition-active", action="store_true")
    parser.add_argument("--duration-s", type=float, default=120.0)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--raw-topic", default="/d415/color/image_raw")
    parser.add_argument("--debug-topic", default="/yolo/debug_image")
    parser.add_argument("--detection-topic", default="/yolo/ball_position_3d")
    parser.add_argument("--goal-topic", default="/chasecar/nav_goal_pose")
    parser.add_argument("--goal-fallback-topic", default="/goal_pose")
    parser.add_argument("--truth-state-path", default="")
    parser.add_argument("--odom-topic", default="/odom")
    parser.add_argument("--cmd-vel-topic-primary", default="/jetbot_base_controller/cmd_vel")
    parser.add_argument("--cmd-vel-topic-secondary", default="/cmd_vel")
    parser.add_argument("--target-visible-min-ratio", type=float, default=0.15)
    parser.add_argument("--overlay-min-changed-pixel-ratio", type=float, default=0.001)
    parser.add_argument("--overlay-min-mean-abs-diff", type=float, default=1.0)
    parser.add_argument("--motion-progress-min-m", type=float, default=0.20)
    parser.add_argument("--require-motion", action="store_true")
    parser.add_argument("--use-sim-time", action="store_true")
    return parser.parse_args()


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

    if msg.step > 0:
        row_bytes = int(msg.step)
        if raw.size >= msg.height * row_bytes:
            full = raw[: msg.height * row_bytes].reshape((msg.height, row_bytes))
            pixels_bytes = msg.width * 3
            if row_bytes >= pixels_bytes:
                arr = full[:, :pixels_bytes].reshape((msg.height, msg.width, 3))
                return arr

    raise ValueError(f"Unsupported image encoding: {msg.encoding}")


def placeholder_frame(width: int, height: int, label: str) -> np.ndarray:
    frame = np.full((height, width, 3), 42, dtype=np.uint8)
    cv2.putText(frame, label, (24, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (220, 230, 255), 2, cv2.LINE_AA)
    return frame


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def is_nonblank(frame: np.ndarray) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return bool(np.std(gray) >= 5.0 and np.mean(gray) >= 5.0)


def red_blob_ratio(frame: np.ndarray) -> float:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (0, 80, 40), (12, 255, 255))
    mask2 = cv2.inRange(hsv, (165, 80, 40), (180, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)
    return float(np.mean(mask > 0))


def compute_image_diff(left: np.ndarray, right: np.ndarray) -> tuple[float, float]:
    if left.shape != right.shape:
        right = cv2.resize(right, (left.shape[1], left.shape[0]), interpolation=cv2.INTER_LINEAR)
    diff = cv2.absdiff(left, right)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    return float(np.mean(diff)), float(np.mean(gray > 0))


@dataclass
class Pose2D:
    x: float
    y: float
    yaw: float


class VisualDemoObserver(Node):
    def __init__(self, args: argparse.Namespace, run_id: str, visual_dir: Path):
        super().__init__("visual_demo_observer")
        self.args = args
        self.run_id = run_id
        self.visual_dir = visual_dir
        self.live_dir = visual_dir / "live"
        self.keyframes_dir = visual_dir / "keyframes"
        self.truth_state_path = Path(args.truth_state_path).resolve() if args.truth_state_path else None
        self.live_dir.mkdir(parents=True, exist_ok=True)
        self.keyframes_dir.mkdir(parents=True, exist_ok=True)

        if args.use_sim_time:
            self.set_parameters(
                [rclpy.parameter.Parameter("use_sim_time", rclpy.Parameter.Type.BOOL, True)]
            )

        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value
        default_qos = QoSPresetProfiles.SYSTEM_DEFAULT.value
        reliable_image_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.create_subscription(Image, args.raw_topic, self._on_raw, sensor_qos)
        # The detector publishes the debug image with RELIABLE QoS; mirror that here.
        self.create_subscription(Image, args.debug_topic, self._on_debug, reliable_image_qos)
        self.create_subscription(PointStamped, args.detection_topic, self._on_detection, default_qos)
        self.create_subscription(PoseStamped, args.goal_topic, self._on_goal, default_qos)
        if args.goal_fallback_topic and args.goal_fallback_topic != args.goal_topic:
            self.create_subscription(PoseStamped, args.goal_fallback_topic, self._on_goal, default_qos)
        self.create_subscription(Odometry, args.odom_topic, self._on_odom, sensor_qos)
        self.create_subscription(Odometry, "/model/jetbot/odometry", self._on_odom, sensor_qos)
        self.create_subscription(Odometry, "/jetbot_base_controller/odom", self._on_odom, sensor_qos)
        self.create_subscription(TwistStamped, args.cmd_vel_topic_primary, self._on_cmd_vel_stamped, default_qos)
        self.create_subscription(Twist, args.cmd_vel_topic_secondary, self._on_cmd_vel, default_qos)
        self.create_subscription(Twist, "/cmd_vel_nav", self._on_cmd_vel, default_qos)

        self.latest_raw_msg: Optional[Image] = None
        self.latest_debug_msg: Optional[Image] = None
        self.latest_odom: Optional[Odometry] = None
        self.latest_detection_local: Optional[PointStamped] = None
        self.latest_goal: Optional[PoseStamped] = None
        self.latest_goal_source: str = ""
        self.cmd_vel_count = 0

        self.raw_frame_count = 0
        self.debug_frame_count = 0
        self.telemetry_frame_count = 0
        self.raw_msg_count = 0
        self.debug_msg_count = 0
        self.raw_nonblank_count = 0
        self.debug_nonblank_count = 0
        self.target_visible_count = 0
        self.overlay_diff_positive_count = 0
        self.max_overlay_changed_pixel_ratio = 0.0
        self.max_overlay_mean_abs_diff = 0.0
        self.first_pose: Optional[Pose2D] = None
        self.latest_pose: Optional[Pose2D] = None
        self.timeline: list[dict[str, object]] = []
        self.distance_history: list[tuple[float, float]] = []
        self.detection_world_history: list[tuple[float, float]] = []
        self.vision_truth_deltas: list[float] = []
        self.waypoint_truth_deltas: list[float] = []
        self.waypoint_vision_deltas: list[float] = []
        self.started_monotonic = time.monotonic()
        self.last_keyframe_written = 0.0
        self.finalized = False

        self.raw_video_path = visual_dir / "raw_camera.mp4"
        self.debug_video_path = visual_dir / "yolo_debug.mp4"
        self.topdown_video_path = visual_dir / "topdown_telemetry.mp4"
        self.timeline_path = visual_dir / "timeline.json"
        self.summary_path = visual_dir / "visual_demo_summary.json"
        self.state_path = visual_dir / "state.json"

        self.raw_writer: Optional[cv2.VideoWriter] = None
        self.debug_writer: Optional[cv2.VideoWriter] = None
        self.topdown_writer: Optional[cv2.VideoWriter] = None
        self.raw_size: Optional[tuple[int, int]] = None
        self.debug_size: Optional[tuple[int, int]] = None
        self.topdown_size = (960, 540)

        self.tick_period_s = 1.0 / max(args.fps, 1.0)
        self.create_timer(self.tick_period_s, self._tick)

    def _on_raw(self, msg: Image) -> None:
        self.latest_raw_msg = msg
        self.raw_msg_count += 1

    def _on_debug(self, msg: Image) -> None:
        self.latest_debug_msg = msg
        self.debug_msg_count += 1

    def _on_detection(self, msg: PointStamped) -> None:
        self.latest_detection_local = msg

    def _on_goal(self, msg: PoseStamped) -> None:
        self.latest_goal = msg
        self.latest_goal_source = msg.header.frame_id or "goal_topic"

    def _on_odom(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def _on_cmd_vel_stamped(self, msg: TwistStamped) -> None:
        _ = msg
        self.cmd_vel_count += 1

    def _on_cmd_vel(self, msg: Twist) -> None:
        _ = msg
        self.cmd_vel_count += 1

    def _pose_from_odom(self) -> Optional[Pose2D]:
        if self.latest_odom is None:
            return None
        pose = self.latest_odom.pose.pose
        yaw = quaternion_to_yaw(
            float(pose.orientation.x),
            float(pose.orientation.y),
            float(pose.orientation.z),
            float(pose.orientation.w),
        )
        return Pose2D(float(pose.position.x), float(pose.position.y), yaw)

    def _transform_detection_world(self) -> Optional[tuple[float, float]]:
        pose = self._pose_from_odom()
        if pose is None or self.latest_detection_local is None:
            return None
        ball_x = float(self.latest_detection_local.point.z)
        ball_y = float(-self.latest_detection_local.point.x)
        world_x = pose.x + (math.cos(pose.yaw) * ball_x) - (math.sin(pose.yaw) * ball_y)
        world_y = pose.y + (math.sin(pose.yaw) * ball_x) + (math.cos(pose.yaw) * ball_y)
        return (world_x, world_y)

    def _load_truth_state(self) -> Optional[dict[str, object]]:
        if self.truth_state_path is None or not self.truth_state_path.exists():
            return None
        try:
            return json.loads(self.truth_state_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _truth_target_world(self) -> Optional[tuple[float, float]]:
        state = self._load_truth_state()
        if not state:
            return None
        target_pose = state.get("true_target_pose")
        if not isinstance(target_pose, dict):
            return None
        try:
            position = target_pose["position"]
            return (float(position.get("x", 0.0)), float(position.get("y", 0.0)))
        except Exception:
            return None

    def _ensure_writer(
        self,
        writer: Optional[cv2.VideoWriter],
        path: Path,
        size: tuple[int, int],
    ) -> cv2.VideoWriter:
        if writer is not None:
            return writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(str(path), fourcc, max(self.args.fps, 1.0), size)
        return video_writer

    def _write_image(self, path: Path, frame: np.ndarray) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), frame)

    def _render_topdown(self) -> np.ndarray:
        width, height = self.topdown_size
        frame = np.full((height, width, 3), 250, dtype=np.uint8)
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), (205, 210, 220), 2)

        pose = self._pose_from_odom()
        detection_world = self._transform_detection_world()
        goal = self.latest_goal
        truth_target = self._truth_target_world()

        world_points: list[tuple[float, float]] = []
        if pose:
            world_points.append((pose.x, pose.y))
        if detection_world:
            world_points.append(detection_world)
        if goal:
            world_points.append((float(goal.pose.position.x), float(goal.pose.position.y)))
        if truth_target:
            world_points.append(truth_target)
        if self.first_pose:
            world_points.append((self.first_pose.x, self.first_pose.y))

        if world_points:
            xs = [p[0] for p in world_points]
            ys = [p[1] for p in world_points]
            pad = 0.8
            min_x = min(xs) - pad
            max_x = max(xs) + pad
            min_y = min(ys) - pad
            max_y = max(ys) + pad
        else:
            min_x, max_x, min_y, max_y = -2.5, 2.5, -2.0, 2.0

        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)

        def world_to_px(wx: float, wy: float) -> tuple[int, int]:
            px = int(((wx - min_x) / span_x) * (width - 80) + 40)
            py = int(((max_y - wy) / span_y) * (height - 120) + 40)
            return px, py

        grid_step = 0.5
        gx = math.floor(min_x / grid_step) * grid_step
        while gx <= max_x:
            p1 = world_to_px(gx, min_y)
            p2 = world_to_px(gx, max_y)
            cv2.line(frame, p1, p2, (230, 233, 238), 1)
            gx += grid_step
        gy = math.floor(min_y / grid_step) * grid_step
        while gy <= max_y:
            p1 = world_to_px(min_x, gy)
            p2 = world_to_px(max_x, gy)
            cv2.line(frame, p1, p2, (230, 233, 238), 1)
            gy += grid_step

        if self.first_pose:
            px, py = world_to_px(self.first_pose.x, self.first_pose.y)
            cv2.circle(frame, (px, py), 8, (120, 120, 120), 2)
            cv2.putText(frame, "start", (px + 10, py - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 90, 90), 1, cv2.LINE_AA)

        if truth_target:
            tx_px, ty_px = world_to_px(*truth_target)
            cv2.circle(frame, (tx_px, ty_px), 10, (20, 20, 20), 2)
            cv2.circle(frame, (tx_px, ty_px), 6, (45, 150, 225), -1)
            cv2.putText(frame, "true target", (tx_px + 10, ty_px - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (35, 95, 150), 2, cv2.LINE_AA)

        if detection_world:
            dx_px, dy_px = world_to_px(*detection_world)
            cv2.circle(frame, (dx_px, dy_px), 8, (30, 30, 210), -1)
            cv2.putText(frame, "vision target", (dx_px + 10, dy_px + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (25, 25, 120), 2, cv2.LINE_AA)

        if goal:
            gx_px, gy_px = world_to_px(float(goal.pose.position.x), float(goal.pose.position.y))
            cv2.circle(frame, (gx_px, gy_px), 10, (210, 110, 30), -1)
            cv2.putText(frame, "nav waypoint", (gx_px + 10, gy_px - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (110, 70, 25), 2, cv2.LINE_AA)

        if pose:
            rx, ry = world_to_px(pose.x, pose.y)
            cv2.circle(frame, (rx, ry), 12, (30, 120, 30), -1)
            tip = (
                int(rx + math.cos(pose.yaw) * 22.0),
                int(ry - math.sin(pose.yaw) * 22.0),
            )
            cv2.arrowedLine(frame, (rx, ry), tip, (20, 90, 20), 3, tipLength=0.35)
            cv2.putText(frame, "robot", (rx + 12, ry - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 80, 20), 2, cv2.LINE_AA)
            if goal:
                gx_px, gy_px = world_to_px(float(goal.pose.position.x), float(goal.pose.position.y))
                cv2.line(frame, (rx, ry), (gx_px, gy_px), (40, 120, 200), 2)
            elif detection_world:
                dx_px, dy_px = world_to_px(*detection_world)
                cv2.line(frame, (rx, ry), (dx_px, dy_px), (80, 80, 200), 2)

        panel_y = height - 86
        cv2.rectangle(frame, (20, panel_y), (width - 20, height - 20), (245, 247, 250), -1)
        cv2.rectangle(frame, (20, panel_y), (width - 20, height - 20), (210, 214, 220), 1)
        pose_text = "Robot=waiting_for_odom"
        if pose:
            pose_text = f"Robot=({pose.x:.2f},{pose.y:.2f}) yaw={pose.yaw:.2f}"
        truth_text = "TrueTarget=none"
        if truth_target:
            truth_text = f"TrueTarget=({truth_target[0]:.2f},{truth_target[1]:.2f})"
        goal_text = "NavWaypoint=none"
        if goal:
            goal_text = f"NavWaypoint=({float(goal.pose.position.x):.2f},{float(goal.pose.position.y):.2f})"
        det_text = "VisionTarget=none"
        if detection_world:
            det_text = f"VisionTarget=({detection_world[0]:.2f},{detection_world[1]:.2f})"
        cv2.putText(frame, f"{pose_text}  {truth_text}  {goal_text}", (32, panel_y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (60, 65, 75), 1, cv2.LINE_AA)
        cv2.putText(frame, det_text, (32, panel_y + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (60, 65, 75), 1, cv2.LINE_AA)

        if len(self.distance_history) >= 2:
            chart = self.distance_history[-60:]
            xs = [p[0] for p in chart]
            ys = [p[1] for p in chart]
            min_t = min(xs)
            max_t = max(xs)
            min_d = min(ys)
            max_d = max(ys)
            span_t = max(max_t - min_t, 1e-6)
            span_d = max(max_d - min_d, 0.25)
            base_x0, base_y0 = width - 300, panel_y + 10
            chart_w, chart_h = 250, 45
            cv2.rectangle(frame, (base_x0, base_y0), (base_x0 + chart_w, base_y0 + chart_h), (230, 234, 240), 1)
            points = []
            for t_val, d_val in chart:
                px = int(base_x0 + ((t_val - min_t) / span_t) * chart_w)
                py = int(base_y0 + chart_h - ((d_val - min_d) / span_d) * chart_h)
                points.append((px, py))
            if len(points) >= 2:
                cv2.polylines(frame, [np.array(points, dtype=np.int32)], False, (40, 90, 210), 2)
            cv2.putText(frame, "distance trend", (base_x0, base_y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 85, 90), 1, cv2.LINE_AA)

        cv2.putText(
            frame,
            f"session={self.run_id} mode={self.args.visual_mode} raw={self.raw_frame_count} debug={self.debug_frame_count} telem={self.telemetry_frame_count}",
            (24, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (70, 74, 82),
            2,
            cv2.LINE_AA,
        )
        return frame

    def _sample_distance(self) -> Optional[float]:
        pose = self._pose_from_odom()
        if pose is None:
            return None
        truth_target = self._truth_target_world()
        if truth_target is not None:
            tx, ty = truth_target
        elif self.latest_goal is not None:
            tx = float(self.latest_goal.pose.position.x)
            ty = float(self.latest_goal.pose.position.y)
        else:
            detection_world = self._transform_detection_world()
            if detection_world is None:
                return None
            tx, ty = detection_world
        return math.hypot(pose.x - tx, pose.y - ty)

    def _tick(self) -> None:
        elapsed = time.monotonic() - self.started_monotonic
        pose = self._pose_from_odom()
        if pose and self.first_pose is None:
            self.first_pose = pose
        if pose:
            self.latest_pose = pose

        raw_frame: np.ndarray
        debug_frame: np.ndarray
        raw_real = False
        debug_real = False

        if self.latest_raw_msg is not None:
            try:
                raw_frame = image_msg_to_bgr(self.latest_raw_msg)
                raw_real = True
            except Exception:
                raw_frame = placeholder_frame(640, 480, "raw_decode_error")
        else:
            raw_frame = placeholder_frame(640, 480, "waiting_raw")

        if self.latest_debug_msg is not None:
            try:
                debug_frame = image_msg_to_bgr(self.latest_debug_msg)
                debug_real = True
            except Exception:
                debug_frame = placeholder_frame(640, 480, "debug_decode_error")
        else:
            debug_frame = placeholder_frame(640, 480, "waiting_debug")

        if self.raw_size is None:
            self.raw_size = (int(raw_frame.shape[1]), int(raw_frame.shape[0]))
            self.raw_writer = self._ensure_writer(self.raw_writer, self.raw_video_path, self.raw_size)
        if self.debug_size is None:
            self.debug_size = (int(debug_frame.shape[1]), int(debug_frame.shape[0]))
            self.debug_writer = self._ensure_writer(self.debug_writer, self.debug_video_path, self.debug_size)
        if self.topdown_writer is None:
            self.topdown_writer = self._ensure_writer(self.topdown_writer, self.topdown_video_path, self.topdown_size)

        if self.raw_size and (raw_frame.shape[1], raw_frame.shape[0]) != self.raw_size:
            raw_frame = cv2.resize(raw_frame, self.raw_size, interpolation=cv2.INTER_LINEAR)
        if self.debug_size and (debug_frame.shape[1], debug_frame.shape[0]) != self.debug_size:
            debug_frame = cv2.resize(debug_frame, self.debug_size, interpolation=cv2.INTER_LINEAR)

        raw_nonblank = raw_real and is_nonblank(raw_frame)
        debug_nonblank = debug_real and is_nonblank(debug_frame)
        target_visible = raw_real and red_blob_ratio(raw_frame) >= 0.0005
        mean_abs_diff, changed_pixel_ratio = compute_image_diff(raw_frame, debug_frame)
        overlay_diff_positive = (
            mean_abs_diff >= self.args.overlay_min_mean_abs_diff
            and changed_pixel_ratio >= self.args.overlay_min_changed_pixel_ratio
        )

        self.raw_frame_count += 1
        self.debug_frame_count += 1
        if raw_nonblank:
            self.raw_nonblank_count += 1
        if debug_nonblank:
            self.debug_nonblank_count += 1
        if target_visible:
            self.target_visible_count += 1
        if overlay_diff_positive:
            self.overlay_diff_positive_count += 1
        self.max_overlay_mean_abs_diff = max(self.max_overlay_mean_abs_diff, mean_abs_diff)
        self.max_overlay_changed_pixel_ratio = max(self.max_overlay_changed_pixel_ratio, changed_pixel_ratio)

        if self.raw_writer and self.raw_writer.isOpened():
            self.raw_writer.write(raw_frame)
        if self.debug_writer and self.debug_writer.isOpened():
            self.debug_writer.write(debug_frame)

        topdown_frame = self._render_topdown()
        if self.topdown_writer and self.topdown_writer.isOpened():
            self.topdown_writer.write(topdown_frame)
        self.telemetry_frame_count += 1

        self._write_image(self.live_dir / "raw_camera.jpg", raw_frame)
        self._write_image(self.live_dir / "yolo_debug.jpg", debug_frame)
        self._write_image(self.live_dir / "topdown_telemetry.jpg", topdown_frame)

        detection_world = self._transform_detection_world()
        truth_target = self._truth_target_world()
        if detection_world is not None:
            self.detection_world_history.append(detection_world)
        distance = self._sample_distance()
        if distance is not None:
            self.distance_history.append((elapsed, distance))
        vision_truth_delta = None
        waypoint_truth_delta = None
        waypoint_vision_delta = None
        if truth_target is not None and detection_world is not None:
            vision_truth_delta = math.hypot(detection_world[0] - truth_target[0], detection_world[1] - truth_target[1])
            self.vision_truth_deltas.append(vision_truth_delta)
        if truth_target is not None and self.latest_goal is not None:
            waypoint_truth_delta = math.hypot(float(self.latest_goal.pose.position.x) - truth_target[0], float(self.latest_goal.pose.position.y) - truth_target[1])
            self.waypoint_truth_deltas.append(waypoint_truth_delta)
        if detection_world is not None and self.latest_goal is not None:
            waypoint_vision_delta = math.hypot(float(self.latest_goal.pose.position.x) - detection_world[0], float(self.latest_goal.pose.position.y) - detection_world[1])
            self.waypoint_vision_deltas.append(waypoint_vision_delta)

        if elapsed - self.last_keyframe_written >= 2.0:
            stamp = int(elapsed * 1000.0)
            self._write_image(self.keyframes_dir / f"{stamp:08d}_raw.png", raw_frame)
            self._write_image(self.keyframes_dir / f"{stamp:08d}_debug.png", debug_frame)
            self._write_image(self.keyframes_dir / f"{stamp:08d}_topdown.png", topdown_frame)
            self.last_keyframe_written = elapsed

        record = {
            "t_s": round(elapsed, 3),
            "phase": self.args.phase or "",
            "target_id": self.args.target_id or "",
            "target_transition_active": bool(self.args.target_transition_active),
            "raw_nonblank": raw_nonblank,
            "debug_nonblank": debug_nonblank,
            "target_visible": target_visible,
            "overlay_mean_abs_diff": round(mean_abs_diff, 6),
            "overlay_changed_pixel_ratio": round(changed_pixel_ratio, 6),
            "cmd_vel_count": self.cmd_vel_count,
            "robot_pose": None,
            "goal_pose": None,
            "detection_world": None,
            "truth_target_world": None,
            "target_distance_m": None if distance is None else round(distance, 6),
            "vision_vs_truth_m": None if vision_truth_delta is None else round(vision_truth_delta, 6),
            "waypoint_vs_truth_m": None if waypoint_truth_delta is None else round(waypoint_truth_delta, 6),
            "waypoint_vs_vision_m": None if waypoint_vision_delta is None else round(waypoint_vision_delta, 6),
        }
        if pose:
            record["robot_pose"] = {"x": round(pose.x, 6), "y": round(pose.y, 6), "yaw": round(pose.yaw, 6)}
        if self.latest_goal is not None:
            record["goal_pose"] = {
                "x": round(float(self.latest_goal.pose.position.x), 6),
                "y": round(float(self.latest_goal.pose.position.y), 6),
                "frame_id": self.latest_goal.header.frame_id or self.latest_goal_source,
            }
        if detection_world is not None:
            record["detection_world"] = {"x": round(detection_world[0], 6), "y": round(detection_world[1], 6)}
        if truth_target is not None:
            record["truth_target_world"] = {"x": round(truth_target[0], 6), "y": round(truth_target[1], 6)}
        self.timeline.append(record)
        self._write_state_json()

        if elapsed >= max(self.args.duration_s, 1.0):
            self.finalize()
            raise SystemExit(0)

    def _write_state_json(self) -> None:
        target_visible_ratio = float(self.target_visible_count / max(self.raw_frame_count, 1))
        truth_target = self._truth_target_world()
        latest_vision_truth = self.vision_truth_deltas[-1] if self.vision_truth_deltas else None
        latest_waypoint_truth = self.waypoint_truth_deltas[-1] if self.waypoint_truth_deltas else None
        latest_waypoint_vision = self.waypoint_vision_deltas[-1] if self.waypoint_vision_deltas else None
        truth_alignment_ok = True
        truth_failure_class = ""
        if self.vision_truth_deltas and float(np.median(self.vision_truth_deltas)) > 0.50:
            truth_alignment_ok = False
            truth_failure_class = "vision_truth_diverged"
        elif self.waypoint_vision_deltas and float(np.median(self.waypoint_vision_deltas)) > 0.50:
            truth_alignment_ok = False
            truth_failure_class = "waypoint_vision_diverged"
        payload = {
            "session_id": self.run_id,
            "visual_mode": self.args.visual_mode,
            "execution_lane": self.args.execution_lane,
            "runtime_target": self.args.runtime_target,
            "phase": self.args.phase or "",
            "target_id": self.args.target_id or "",
            "target_transition_active": bool(self.args.target_transition_active),
            "raw_frame_count": self.raw_frame_count,
            "debug_frame_count": self.debug_frame_count,
            "telemetry_frame_count": self.telemetry_frame_count,
            "raw_msg_count": self.raw_msg_count,
            "debug_msg_count": self.debug_msg_count,
            "viewer_frame_counts": {
                "raw": self.raw_frame_count,
                "debug": self.debug_frame_count,
                "telemetry": self.telemetry_frame_count,
            },
            "raw_nonblank": self.raw_nonblank_count > 0,
            "debug_nonblank": self.debug_nonblank_count > 0,
            "target_visible_ratio": round(target_visible_ratio, 6),
            "overlay_difference_ok": bool(
                self.max_overlay_mean_abs_diff >= self.args.overlay_min_mean_abs_diff
                and self.max_overlay_changed_pixel_ratio >= self.args.overlay_min_changed_pixel_ratio
            ),
            "max_overlay_mean_abs_diff": round(self.max_overlay_mean_abs_diff, 6),
            "max_overlay_changed_pixel_ratio": round(self.max_overlay_changed_pixel_ratio, 6),
            "cmd_vel_count": self.cmd_vel_count,
            "goal_topic_seen": self.latest_goal is not None,
            "detection_topic_seen": self.latest_detection_local is not None,
            "true_target_seen": truth_target is not None,
            "truth_alignment_ok": truth_alignment_ok,
            "truth_failure_class": truth_failure_class,
            "vision_vs_truth_m": None if latest_vision_truth is None else round(latest_vision_truth, 6),
            "waypoint_vs_truth_m": None if latest_waypoint_truth is None else round(latest_waypoint_truth, 6),
            "waypoint_vs_vision_m": None if latest_waypoint_vision is None else round(latest_waypoint_vision, 6),
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def finalize(self) -> None:
        if self.finalized:
            return
        self.finalized = True

        for writer in (self.raw_writer, self.debug_writer, self.topdown_writer):
            if writer is not None:
                writer.release()

        self.timeline_path.write_text(json.dumps(self.timeline, indent=2), encoding="utf-8")

        target_visible_ratio = float(self.target_visible_count / max(self.raw_frame_count, 1))
        overlay_difference_ok = bool(
            self.max_overlay_mean_abs_diff >= self.args.overlay_min_mean_abs_diff
            and self.max_overlay_changed_pixel_ratio >= self.args.overlay_min_changed_pixel_ratio
        )
        target_persistence_ok = bool(target_visible_ratio >= self.args.target_visible_min_ratio)
        truth_target = self._truth_target_world()
        truth_alignment_ok = True
        truth_failure_class = ""
        if self.vision_truth_deltas and float(np.median(self.vision_truth_deltas)) > 0.50:
            truth_alignment_ok = False
            truth_failure_class = "vision_truth_diverged"
        elif self.waypoint_vision_deltas and float(np.median(self.waypoint_vision_deltas)) > 0.50:
            truth_alignment_ok = False
            truth_failure_class = "waypoint_vision_diverged"

        motion_progress_m = 0.0
        motion_progress_ok = False
        if len(self.distance_history) >= 2:
            motion_progress_m = float(self.distance_history[0][1] - self.distance_history[-1][1])
            motion_progress_ok = motion_progress_m >= self.args.motion_progress_min_m

        summary = {
            "session_id": self.run_id,
            "execution_lane": self.args.execution_lane,
            "runtime_target": self.args.runtime_target,
            "visual_mode": self.args.visual_mode,
            "phase": self.args.phase or "",
            "target_id": self.args.target_id or "",
            "target_transition_active": bool(self.args.target_transition_active),
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "raw_nonblank": self.raw_nonblank_count > 0,
            "debug_nonblank": self.debug_nonblank_count > 0,
            "overlay_difference_ok": overlay_difference_ok,
            "target_persistence_ok": target_persistence_ok,
            "motion_progress_ok": motion_progress_ok,
            "pass": (
                self.raw_nonblank_count > 0
                and self.debug_nonblank_count > 0
                and overlay_difference_ok
                and target_persistence_ok
                and truth_alignment_ok
                and (motion_progress_ok if self.args.require_motion else True)
            ),
            "raw_frame_count": self.raw_frame_count,
            "debug_frame_count": self.debug_frame_count,
            "telemetry_frame_count": self.telemetry_frame_count,
            "raw_msg_count": self.raw_msg_count,
            "debug_msg_count": self.debug_msg_count,
            "target_visible_ratio": round(target_visible_ratio, 6),
            "cmd_vel_count": self.cmd_vel_count,
            "max_overlay_mean_abs_diff": round(self.max_overlay_mean_abs_diff, 6),
            "max_overlay_changed_pixel_ratio": round(self.max_overlay_changed_pixel_ratio, 6),
            "motion_progress_m": round(motion_progress_m, 6),
            "true_target_seen": truth_target is not None,
            "truth_alignment_ok": truth_alignment_ok,
            "truth_failure_class": truth_failure_class,
            "vision_vs_truth_m_median": round(float(np.median(self.vision_truth_deltas)), 6) if self.vision_truth_deltas else None,
            "waypoint_vs_truth_m_median": round(float(np.median(self.waypoint_truth_deltas)), 6) if self.waypoint_truth_deltas else None,
            "waypoint_vs_vision_m_median": round(float(np.median(self.waypoint_vision_deltas)), 6) if self.waypoint_vision_deltas else None,
            "raw_video": str(self.raw_video_path),
            "debug_video": str(self.debug_video_path),
            "topdown_video": str(self.topdown_video_path),
            "keyframes_dir": str(self.keyframes_dir),
            "timeline_path": str(self.timeline_path),
            "state_path": str(self.state_path),
            "goal_topic_seen": self.latest_goal is not None,
            "detection_topic_seen": self.latest_detection_local is not None,
        }
        self.summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self._write_state_json()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.session_id
    rclpy.init()
    node = VisualDemoObserver(args, run_id, output_dir)

    stop_requested = {"value": False}

    def request_stop(*_args) -> None:
        stop_requested["value"] = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        while rclpy.ok() and not stop_requested["value"]:
            rclpy.spin_once(node, timeout_sec=0.1)
    except SystemExit:
        pass
    finally:
        node.finalize()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    print(f"VISUAL_SUMMARY={node.summary_path}")
    print(f"VISUAL_TIMELINE={node.timeline_path}")
    print(f"VISUAL_STATE={node.state_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
