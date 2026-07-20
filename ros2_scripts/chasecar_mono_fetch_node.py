#!/usr/bin/env python3
"""Mono RGB fetch node for sim-side JetBot Mini bringup.

The node is deliberately blind to depth, odometry, and Gazebo truth. It consumes
only the mono RGB camera plus CameraInfo, estimates target range from calibrated
apparent size, and publishes robot-relative TwistStamped commands.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from sensor_msgs.msg import Image

try:
    from rclpy.executors import ExternalShutdownException
except Exception:  # pragma: no cover - keeps unit-test stubs simple.
    class ExternalShutdownException(Exception):
        pass


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_mono_yolo_detect as mono_yolo  # noqa: E402
import chasecar_mono_color_detect as mono_color  # noqa: E402
from chasecar_bridge_object_pose_observation import estimate_object_pose  # noqa: E402
from chasecar_bridge_object_pose_observation import load_calibration  # noqa: E402
from chasecar_bridge_visual_fetch_controller import ACT_FORWARD  # noqa: E402
from chasecar_bridge_visual_fetch_controller import ACT_HOLD  # noqa: E402
from chasecar_bridge_visual_fetch_controller import ACT_STOP  # noqa: E402
from chasecar_bridge_visual_fetch_controller import ACT_TURN  # noqa: E402
from chasecar_bridge_visual_fetch_controller import decide_fetch_action  # noqa: E402
from chasecar_bridge_visual_fetch_controller import default_config  # noqa: E402


DEFAULT_IMAGE_TOPIC = "/d415/color/image_raw"
DEFAULT_CAMERA_INFO_TOPIC = "/d415/color/camera_info"
DEFAULT_CMD_VEL_TOPIC = "/jetbot_base_controller/cmd_vel"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "session" / "mono_fetch_node"
POSE_METRIC = "metric"
POSE_UNAVAILABLE = "unavailable"


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_fetch_config(calibration: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    cfg = default_config(
        k_px_m=float(calibration["k_px_m"]),
        size_key=str(calibration.get("size_key") or "equiv_diameter_px"),
    )
    cfg.update({key: value for key, value in overrides.items() if value is not None})
    return cfg


def build_controller_observation(
    detection: dict[str, Any] | None,
    *,
    size_key: str,
) -> dict[str, Any]:
    if not detection:
        return {"detected": False, size_key: 0.0, "center_error": 0.0, "confidence": 0.0}
    return {
        "detected": True,
        size_key: safe_float(detection.get(size_key), 0.0),
        "center_error": safe_float(detection.get("center_error"), 0.0),
        "confidence": safe_float(detection.get("confidence"), 0.0),
    }


def estimate_pose_for_detection(
    detection: dict[str, Any] | None,
    *,
    calibration: dict[str, Any],
    horizontal_fov_deg: float,
    sigma_d_max_m: float | None = None,
) -> dict[str, Any] | None:
    if not detection:
        return None
    size_key = str(calibration.get("size_key") or "equiv_diameter_px")
    return estimate_object_pose(
        safe_float(detection.get(size_key), 0.0),
        k_px_m=float(calibration["k_px_m"]),
        sigma_s_px=float(calibration["sigma_s_px"]),
        object_size_m=float(calibration["object_size_m"]),
        center_error=safe_float(detection.get("center_error"), 0.0),
        horizontal_fov_deg=float(horizontal_fov_deg),
        max_reliable_range_m=calibration.get("max_reliable_range_m"),
        sigma_d_max_m=sigma_d_max_m,
    )


def decide_mono_fetch(
    detection: dict[str, Any] | None,
    *,
    state: dict[str, Any],
    cfg: dict[str, Any],
    calibration: dict[str, Any],
    horizontal_fov_deg: float,
    sigma_d_max_m: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    obs = build_controller_observation(detection, size_key=str(cfg["size_key"]))
    pose = estimate_pose_for_detection(
        detection,
        calibration=calibration,
        horizontal_fov_deg=horizontal_fov_deg,
        sigma_d_max_m=sigma_d_max_m,
    )
    return obs, pose, decide_fetch_action(obs, state, cfg)


def apply_decision_to_state(
    state: dict[str, Any],
    *,
    obs: dict[str, Any],
    decision: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(state)
    updated["step"] = int(updated.get("step", 0)) + 1
    if decision.get("action") == ACT_FORWARD:
        updated["forward_steps"] = int(updated.get("forward_steps", 0)) + 1
    if "lost_count" in decision:
        updated["lost_count"] = int(decision.get("lost_count", 0) or 0)
    else:
        usable = (
            bool(obs.get("detected"))
            and safe_float(obs.get("confidence"), 0.0) >= float(cfg["min_confidence"])
            and safe_float(obs.get(cfg["size_key"]), 0.0) > 0.0
        )
        if usable:
            updated["lost_count"] = 0
    return updated


def apply_pose_status_motion_gate(
    decision: dict[str, Any],
    mono_pose: dict[str, Any] | None,
    *,
    require_metric_pose_for_forward: bool,
) -> dict[str, Any]:
    if not require_metric_pose_for_forward or decision.get("action") != ACT_FORWARD:
        return decision
    pose_status = str((mono_pose or {}).get("pose_status") or POSE_UNAVAILABLE)
    if pose_status == POSE_METRIC:
        return decision
    gated = dict(decision)
    gated.update(
        {
            "action": ACT_HOLD,
            "reason": "pose_not_metric",
            "pose_status": pose_status,
            "gated_action": ACT_FORWARD,
        }
    )
    gated.pop("linear_x", None)
    return gated


def _phase_state_defaults(phase_state: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(phase_state or {})
    state.setdefault("phase", "approach")
    state.setdefault("push_ticks", 0)
    state.setdefault("push_distance_m", 0.0)
    state.setdefault("terminal_reason", "")
    return state


def contact_push_phase_step(
    phase_state: dict[str, Any] | None,
    controller_decision: dict[str, Any],
    *,
    push_steps: int,
    push_linear_x: float,
    push_max_distance_m: float,
    publish_hz: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    state = _phase_state_defaults(phase_state)
    phase = str(state.get("phase") or "approach")
    transition: dict[str, Any] | None = None

    if phase == "approach":
        if controller_decision.get("action") == ACT_STOP:
            reason = str(controller_decision.get("reason") or "stop")
            next_phase = (
                "push"
                if reason == "standoff_reached"
                and int(push_steps) > 0
                and float(push_linear_x) > 0.0
                and float(push_max_distance_m) > 0.0
                else "hold"
            )
            state["phase"] = next_phase
            state["terminal_reason"] = reason
            transition = {"from": "approach", "to": next_phase, "reason": reason}
        return controller_decision, state, transition

    if phase == "push":
        step_distance_m = abs(float(push_linear_x)) / max(float(publish_hz), 1.0)
        push_ticks = int(state.get("push_ticks", 0) or 0)
        push_distance_m = float(state.get("push_distance_m", 0.0) or 0.0)
        stop_reason = ""
        if push_ticks >= int(push_steps):
            stop_reason = "push_steps_completed"
        elif push_distance_m + step_distance_m > float(push_max_distance_m):
            stop_reason = "push_max_distance_reached"
        if stop_reason:
            state["phase"] = "hold"
            state["terminal_reason"] = stop_reason
            transition = {"from": "push", "to": "hold", "reason": stop_reason}
            return {"action": ACT_STOP, "reason": stop_reason}, state, transition

        push_ticks += 1
        push_distance_m += step_distance_m
        state["push_ticks"] = push_ticks
        state["push_distance_m"] = round(push_distance_m, 6)
        return (
            {
                "action": ACT_FORWARD,
                "reason": "contact_push",
                "linear_x": float(push_linear_x),
                "push_tick": push_ticks,
                "push_steps": int(push_steps),
                "estimated_push_distance_m": round(push_distance_m, 6),
                "push_max_distance_m": float(push_max_distance_m),
            },
            state,
            None,
        )

    reason = str(state.get("terminal_reason") or "terminal_hold")
    return {"action": ACT_STOP, "reason": reason}, state, None


def action_to_twist_values(decision: dict[str, Any]) -> tuple[float, float]:
    action = str(decision.get("action") or "")
    if action == ACT_FORWARD:
        return safe_float(decision.get("linear_x"), 0.0), 0.0
    if action == ACT_TURN:
        return 0.0, safe_float(decision.get("angular_z"), 0.0)
    return 0.0, 0.0


class MonoFetchNode(Node):
    """ROS wrapper around the pure mono detector/pose/controller seam."""

    def __init__(self, cli_args: argparse.Namespace) -> None:
        super().__init__(
            "chasecar_mono_fetch_node",
            automatically_declare_parameters_from_overrides=True,
        )
        self._declare_parameters(cli_args)

        self.image_topic = str(self.get_parameter("image_topic").value)
        self.camera_info_topic = str(self.get_parameter("camera_info_topic").value)
        self.cmd_vel_topic = str(self.get_parameter("cmd_vel_topic").value)
        self.size_key = str(self.get_parameter("size_key").value)
        self.publish_hz = max(float(self.get_parameter("publish_hz").value), 20.0)
        self.sigma_d_max_m = self._optional_float_parameter("sigma_d_max_m")
        self.max_frame_age_s = max(float(self.get_parameter("max_frame_age_s").value), 0.0)
        self.push_steps = max(int(self.get_parameter("push_steps").value), 0)
        self.push_linear_x = max(float(self.get_parameter("push_linear_x").value), 0.0)
        self.push_max_distance_m = max(float(self.get_parameter("push_max_distance_m").value), 0.0)
        self.require_metric_pose_for_forward = bool(self.get_parameter("require_metric_pose_for_forward").value)
        self.use_sim_time = bool(self.get_parameter("use_sim_time").value)

        calibration_path = str(self.get_parameter("calibration").value)
        if not calibration_path:
            raise ValueError("calibration_path_required")
        self.calibration = load_calibration(calibration_path, size_key=self.size_key)
        self.cfg = build_fetch_config(
            self.calibration,
            standoff_m=float(self.get_parameter("standoff_m").value),
            center_deadband=float(self.get_parameter("center_deadband").value),
            forward_budget=int(self.get_parameter("forward_budget").value),
            lost_limit=int(self.get_parameter("lost_limit").value),
            min_confidence=float(self.get_parameter("min_confidence").value),
            max_steps=int(self.get_parameter("max_steps").value),
            turn_angular_z=float(self.get_parameter("turn_angular_z").value),
            approach_linear_x=float(self.get_parameter("approach_linear_x").value),
            size_key=self.size_key,
        )

        artifact_dir_raw = str(self.get_parameter("artifact_dir").value or "")
        self.artifact_dir = Path(artifact_dir_raw) if artifact_dir_raw else DEFAULT_ARTIFACT_DIR / utc_stamp()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.artifact_dir / "mono_fetch_node.jsonl"
        self._log_handle = self.log_path.open("a", encoding="utf-8")

        self.detector_kind = str(self.get_parameter("detector").value or "yolo").strip().lower()
        if self.detector_kind == "yolo":
            model_path = str(self.get_parameter("model_path").value)
            self.detector = mono_yolo.MonoYoloDetector(
                model_path or mono_yolo.DEFAULT_MODEL_PATH,
                target_class=str(self.get_parameter("target_class").value),
                confidence_threshold=float(self.get_parameter("confidence_threshold").value),
                iou_threshold=float(self.get_parameter("iou_threshold").value),
                input_size=int(self.get_parameter("input_size").value),
                min_area_ratio=float(self.get_parameter("target_min_area_ratio").value),
            )
        elif self.detector_kind == "color":
            self.detector = mono_color.MonoColorDetector(
                hsv_lower=(
                    int(self.get_parameter("color_hsv_lower_h").value),
                    int(self.get_parameter("color_hsv_lower_s").value),
                    int(self.get_parameter("color_hsv_lower_v").value),
                ),
                hsv_upper=(
                    int(self.get_parameter("color_hsv_upper_h").value),
                    int(self.get_parameter("color_hsv_upper_s").value),
                    int(self.get_parameter("color_hsv_upper_v").value),
                ),
                min_area_px=float(self.get_parameter("color_min_area_px").value),
                morph_kernel_size=int(self.get_parameter("color_morph_kernel_size").value),
            )
        else:
            raise ValueError("unsupported_detector:%s" % self.detector_kind)

        from cv_bridge import CvBridge  # Imported here so ROS-light tests can stub imports.

        self.bridge = CvBridge()
        self.latest_rgb = None
        self.latest_image_stamp = None
        self.latest_detection: dict[str, Any] | None = None
        self.camera_info: dict[str, Any] | None = None
        self.state: dict[str, Any] = {"step": 0, "forward_steps": 0, "lost_count": 0}
        self.phase_state: dict[str, Any] = _phase_state_defaults(None)
        self.tick_index = 0

        self.cmd_pub = self.create_publisher(TwistStamped, self.cmd_vel_topic, 10)
        from rclpy.qos import qos_profile_sensor_data

        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            qos_profile_sensor_data,
        )
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            qos_profile_sensor_data,
        )
        self.timer = self.create_timer(1.0 / self.publish_hz, self.timer_callback)
        clock_type = getattr(self.get_clock(), "clock_type", "")
        clock_type_name = getattr(clock_type, "name", str(clock_type))
        if self.use_sim_time and clock_type_name != "ROS_TIME":
            self.get_logger().warn(
                "clock_source_resolved use_sim_time=true clock_type=%s" % clock_type_name
            )
        else:
            self.get_logger().info(
                "clock_source_resolved use_sim_time=%s clock_type=%s"
                % (str(self.use_sim_time).lower(), clock_type_name)
            )
        self.get_logger().info(
            "mono fetch node active: detector=%s image=%s camera_info=%s cmd_vel=%s log=%s"
            % (
                self.detector_kind,
                self.image_topic,
                self.camera_info_topic,
                self.cmd_vel_topic,
                self.log_path,
            )
        )

    def _declare_parameter_if_needed(self, name: str, value: Any) -> None:
        has_parameter = False
        try:
            has_parameter = bool(self.has_parameter(name))
        except Exception:
            has_parameter = False
        if not has_parameter:
            self.declare_parameter(name, value)

    def _declare_parameters(self, cli_args: argparse.Namespace) -> None:
        self._declare_parameter_if_needed("calibration", cli_args.calibration or "")
        self._declare_parameter_if_needed("artifact_dir", cli_args.artifact_dir or "")
        self._declare_parameter_if_needed("model_path", cli_args.model or str(mono_yolo.DEFAULT_MODEL_PATH))
        self._declare_parameter_if_needed("detector", "yolo")
        self._declare_parameter_if_needed("image_topic", DEFAULT_IMAGE_TOPIC)
        self._declare_parameter_if_needed("camera_info_topic", DEFAULT_CAMERA_INFO_TOPIC)
        self._declare_parameter_if_needed("cmd_vel_topic", DEFAULT_CMD_VEL_TOPIC)
        self._declare_parameter_if_needed("use_sim_time", False)
        self._declare_parameter_if_needed("target_class", mono_yolo.DEFAULT_TARGET_CLASS)
        self._declare_parameter_if_needed("confidence_threshold", 0.25)
        self._declare_parameter_if_needed("target_min_area_ratio", 0.0)
        self._declare_parameter_if_needed("iou_threshold", 0.45)
        self._declare_parameter_if_needed("input_size", 640)
        self._declare_parameter_if_needed("color_hsv_lower_h", mono_color.DEFAULT_HSV_LOWER[0])
        self._declare_parameter_if_needed("color_hsv_lower_s", mono_color.DEFAULT_HSV_LOWER[1])
        self._declare_parameter_if_needed("color_hsv_lower_v", mono_color.DEFAULT_HSV_LOWER[2])
        self._declare_parameter_if_needed("color_hsv_upper_h", mono_color.DEFAULT_HSV_UPPER[0])
        self._declare_parameter_if_needed("color_hsv_upper_s", mono_color.DEFAULT_HSV_UPPER[1])
        self._declare_parameter_if_needed("color_hsv_upper_v", mono_color.DEFAULT_HSV_UPPER[2])
        self._declare_parameter_if_needed("color_min_area_px", mono_color.DEFAULT_MIN_AREA_PX)
        self._declare_parameter_if_needed("color_morph_kernel_size", 3)
        self._declare_parameter_if_needed("size_key", "equiv_diameter_px")
        self._declare_parameter_if_needed("publish_hz", 20.0)
        self._declare_parameter_if_needed("standoff_m", 0.40)
        self._declare_parameter_if_needed("center_deadband", 0.16)
        self._declare_parameter_if_needed("min_confidence", 0.25)
        self._declare_parameter_if_needed("forward_budget", 40)
        self._declare_parameter_if_needed("lost_limit", 4)
        self._declare_parameter_if_needed("max_steps", 120)
        self._declare_parameter_if_needed("turn_angular_z", 0.7)
        self._declare_parameter_if_needed("approach_linear_x", 0.04)
        self._declare_parameter_if_needed("sigma_d_max_m", 0.0)
        self._declare_parameter_if_needed("max_frame_age_s", 0.4)
        self._declare_parameter_if_needed("push_linear_x", 0.05)
        self._declare_parameter_if_needed("push_steps", 100)
        self._declare_parameter_if_needed("push_max_distance_m", 0.25)
        self._declare_parameter_if_needed("require_metric_pose_for_forward", True)

    def _optional_float_parameter(self, name: str) -> float | None:
        value = safe_float(self.get_parameter(name).value, 0.0)
        return value if value > 0.0 else None

    def image_callback(self, msg: Image) -> None:
        self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8")
        self.latest_image_stamp = getattr(getattr(msg, "header", None), "stamp", None)

    def camera_info_callback(self, msg: CameraInfo) -> None:
        if self.camera_info is not None:
            return
        k_field = getattr(msg, "k", None)
        k = list(k_field) if k_field is not None else []
        if len(k) < 6:
            self.get_logger().warn("camera_info_missing_k_matrix")
            return
        fx = safe_float(k[0], 0.0)
        cx = safe_float(k[2], 0.0)
        width = int(getattr(msg, "width", 0) or 0)
        height = int(getattr(msg, "height", 0) or 0)
        if fx <= 0.0 or width <= 0:
            self.get_logger().warn("camera_info_invalid_fx_or_width")
            return
        horizontal_fov_deg = math_degrees_hfov(width=width, fx=fx)
        self.camera_info = {
            "fx": fx,
            "fy": safe_float(k[4], 0.0),
            "cx": cx,
            "cy": safe_float(k[5], 0.0),
            "width": width,
            "height": height,
            "horizontal_fov_deg": horizontal_fov_deg,
        }
        self.get_logger().info("camera_info_loaded:%s" % json.dumps(self.camera_info, sort_keys=True))

    def timer_callback(self) -> None:
        self.tick_index += 1
        detection = None
        mono_pose = None
        issue = ""
        frame_age_s = self.latest_frame_age_s()
        pre_state = dict(self.state)
        pre_phase_state = dict(self.phase_state)
        phase_transition = None
        if str(self.phase_state.get("phase")) == "approach":
            if self.latest_rgb is None:
                issue = "image_missing"
            elif frame_age_s is not None and frame_age_s > self.max_frame_age_s:
                issue = "image_stale"
            elif self.camera_info is None:
                issue = "camera_info_missing"
            else:
                try:
                    detection = self.detector.detect(self.latest_rgb)
                    self.latest_detection = detection
                except Exception as exc:  # pragma: no cover - live dependency failures
                    issue = "detect_failed:%s" % exc
                    detection = None
            if self.camera_info is not None:
                obs, mono_pose, controller_decision = decide_mono_fetch(
                    detection,
                    state=self.state,
                    cfg=self.cfg,
                    calibration=self.calibration,
                    horizontal_fov_deg=float(self.camera_info["horizontal_fov_deg"]),
                    sigma_d_max_m=self.sigma_d_max_m,
                )
            else:
                obs = build_controller_observation(None, size_key=str(self.cfg["size_key"]))
                controller_decision = decide_fetch_action(obs, self.state, self.cfg)
            gated_decision = apply_pose_status_motion_gate(
                controller_decision,
                mono_pose,
                require_metric_pose_for_forward=self.require_metric_pose_for_forward,
            )
            decision, self.phase_state, phase_transition = contact_push_phase_step(
                self.phase_state,
                gated_decision,
                push_steps=self.push_steps,
                push_linear_x=self.push_linear_x,
                push_max_distance_m=self.push_max_distance_m,
                publish_hz=self.publish_hz,
            )
            self.state = apply_decision_to_state(self.state, obs=obs, decision=decision, cfg=self.cfg)
        else:
            obs = build_controller_observation(None, size_key=str(self.cfg["size_key"]))
            decision, self.phase_state, phase_transition = contact_push_phase_step(
                self.phase_state,
                {"action": ACT_STOP, "reason": "terminal_phase"},
                push_steps=self.push_steps,
                push_linear_x=self.push_linear_x,
                push_max_distance_m=self.push_max_distance_m,
                publish_hz=self.publish_hz,
            )
        published_cmd = self.publish_decision(decision)
        if phase_transition:
            self.get_logger().info("phase_transition:%s" % json.dumps(phase_transition, sort_keys=True))
        self.log_tick(
            {
                "tick": self.tick_index,
                "sim_time_s": self.get_clock().now().nanoseconds / 1.0e9,
                "wall_time_unix_s": time.time(),
                "clock_type": getattr(getattr(self.get_clock(), "clock_type", ""), "name", str(getattr(self.get_clock(), "clock_type", ""))),
                "use_sim_time": self.use_sim_time,
                "image_topic": self.image_topic,
                "camera_info_topic": self.camera_info_topic,
                "cmd_vel_topic": self.cmd_vel_topic,
                "detector": self.detector_kind,
                "issue": issue,
                "frame_age_s": round(frame_age_s, 6) if frame_age_s is not None and math.isfinite(frame_age_s) else frame_age_s,
                "camera_info": self.camera_info,
                "detection": detection,
                "mono_pose": mono_pose,
                "observation": obs,
                "action": decision,
                "state_before": pre_state,
                "state_after": dict(self.state),
                "phase": self.phase_state.get("phase"),
                "phase_state_before": pre_phase_state,
                "phase_state_after": dict(self.phase_state),
                "phase_transition": phase_transition,
                "published_cmd": published_cmd,
            }
        )

    def latest_frame_age_s(self) -> float | None:
        stamp = self.latest_image_stamp
        if stamp is None:
            return None
        sec = getattr(stamp, "sec", None)
        nanosec = getattr(stamp, "nanosec", getattr(stamp, "nsec", 0))
        if sec is None:
            return None
        stamp_s = float(sec) + (float(nanosec or 0) / 1.0e9)
        return (self.get_clock().now().nanoseconds / 1.0e9) - stamp_s

    def publish_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        linear_x, angular_z = action_to_twist_values(decision)
        msg = TwistStamped()
        stamp = self.get_clock().now()
        msg.header.stamp = stamp.to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = float(linear_x)
        msg.twist.linear.y = 0.0
        msg.twist.linear.z = 0.0
        msg.twist.angular.x = 0.0
        msg.twist.angular.y = 0.0
        msg.twist.angular.z = float(angular_z)
        self.cmd_pub.publish(msg)
        return {
            "linear_x": float(linear_x),
            "angular_z": float(angular_z),
            "stamp_s": stamp.nanoseconds / 1.0e9,
            "frame_id": msg.header.frame_id,
        }

    def log_tick(self, record: dict[str, Any]) -> None:
        self._log_handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._log_handle.flush()

    def close(self) -> None:
        try:
            self.publish_decision({"action": ACT_STOP, "reason": "node_close"})
        except Exception:
            pass
        try:
            self._log_handle.close()
        except Exception:
            pass


def math_degrees_hfov(*, width: int, fx: float) -> float:
    import math

    return math.degrees(2.0 * math.atan(float(width) / (2.0 * float(fx))))


def parse_cli(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", default="")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--model", default="")
    return parser.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    cli_args, ros_args = parse_cli(argv)
    rclpy.init(args=ros_args)
    node: MonoFetchNode | None = None
    try:
        node = MonoFetchNode(cli_args)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        return 0
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
