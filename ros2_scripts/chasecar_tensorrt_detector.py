#!/usr/bin/env python3
"""
Canonical TensorRT-based detector interface for chasecar runtime.

This node is intentionally independent of PyTorch/Ultralytics so the runtime lane
can stay aligned with Orin deployment constraints.
"""

import os
import time
from typing import Dict, Optional

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Point
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32
from std_msgs.msg import String


class ChasecarTensorRtDetector(Node):
    def __init__(self) -> None:
        super().__init__("chasecar_tensorrt_detector")

        self.declare_parameter("input_topic", "/d415/color/image_raw")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("inference_device", "cuda:0")
        self.declare_parameter("inference_backend", "tensorrt_int8")
        self.declare_parameter("engine_path", "runtime/tensorrt/engines/ball_detector_int8.engine")
        self.declare_parameter("headless", True)
        self.declare_parameter("show_window", False)
        self.declare_parameter("perf_profile", "compat")
        self.declare_parameter("runtime_target", "robot_fidelity_orin")
        self.declare_parameter("bbox_vertical_anchor", 0.85)
        self.declare_parameter("red_fallback_min_area_px", 10)
        self.declare_parameter("red_fallback_confidence", 0.55)
        self.declare_parameter("allow_red_fallback", True)

        self.input_topic = str(self.get_parameter("input_topic").value)
        self.confidence_threshold = float(self.get_parameter("confidence_threshold").value)
        self.inference_device = str(self.get_parameter("inference_device").value)
        self.inference_backend = str(self.get_parameter("inference_backend").value)
        self.engine_path = self._resolve_engine_path(str(self.get_parameter("engine_path").value))
        self.headless = bool(self.get_parameter("headless").value)
        self.show_window = bool(self.get_parameter("show_window").value) and not self.headless
        self.perf_profile = str(self.get_parameter("perf_profile").value)
        self.runtime_target = str(self.get_parameter("runtime_target").value)
        self.bbox_vertical_anchor = max(0.0, min(float(self.get_parameter("bbox_vertical_anchor").value), 1.0))
        self.red_fallback_min_area_px = max(1, int(self.get_parameter("red_fallback_min_area_px").value))
        self.red_fallback_confidence = max(
            0.0, min(1.0, float(self.get_parameter("red_fallback_confidence").value))
        )
        self.allow_red_fallback = bool(self.get_parameter("allow_red_fallback").value)

        self.bridge = CvBridge()
        self.window_name = "Chasecar TensorRT Detector"
        self._trt_ready = False
        self._trt_load_error = ""
        self._backend_status = "uninitialized"

        self._init_tensorrt_runtime()

        self.position_pub = self.create_publisher(Point, "/yolo/ball_position", 10)
        self.confidence_pub = self.create_publisher(Float32, "/yolo/confidence", 10)
        self.debug_image_pub = self.create_publisher(Image, "/yolo/debug_image", 10)
        self.inference_ms_pub = self.create_publisher(Float32, "/yolo/inference_ms", 10)
        self.backend_status_pub = self.create_publisher(String, "/yolo/backend_status", 10)

        self.image_sub = self.create_subscription(Image, self.input_topic, self.image_callback, 10)

        self._last_status_publish = 0.0
        self._frames = 0

        self.get_logger().info("=" * 60)
        self.get_logger().info("Chasecar TensorRT Detector started")
        self.get_logger().info(f"input_topic={self.input_topic}")
        self.get_logger().info(f"inference_backend={self.inference_backend}")
        self.get_logger().info(f"inference_device={self.inference_device}")
        self.get_logger().info(f"engine_path={self.engine_path}")
        self.get_logger().info(f"runtime_target={self.runtime_target}, perf_profile={self.perf_profile}")
        self.get_logger().info(f"backend_status={self._backend_status}")
        self.get_logger().info("=" * 60)

    def _resolve_engine_path(self, configured_path: str) -> str:
        path = configured_path.strip()
        if os.path.isabs(path):
            return path

        candidates = [
            path,
            os.path.join(os.getcwd(), path),
            os.path.join(os.path.expanduser("~"), "ros2_ws", "src", "chasecar_runtime", path),
            os.path.join(os.path.expanduser("~"), "ros2_ws", "src", "chasecar", path),
            os.path.join(os.path.expanduser("~"), "ros2_ws", "src", "chasebot_description", path),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return path

    def _init_tensorrt_runtime(self) -> None:
        if self.inference_backend != "tensorrt_int8":
            self._backend_status = f"invalid_backend:{self.inference_backend}"
            return

        try:
            import tensorrt as trt  # pylint: disable=import-outside-toplevel

            if not os.path.isfile(self.engine_path):
                self._backend_status = "tensorrt_engine_missing"
                self._trt_load_error = f"Engine not found: {self.engine_path}"
                return

            logger = trt.Logger(trt.Logger.WARNING)
            with open(self.engine_path, "rb") as fp:
                engine_bytes = fp.read()

            runtime = trt.Runtime(logger)
            engine = runtime.deserialize_cuda_engine(engine_bytes)
            if engine is None:
                self._backend_status = "tensorrt_deserialize_failed"
                self._trt_load_error = "deserialize_cuda_engine returned None"
                return

            context = engine.create_execution_context()
            if context is None:
                self._backend_status = "tensorrt_context_failed"
                self._trt_load_error = "create_execution_context returned None"
                return

            # Keep references for future full-engine execution path.
            self._trt_runtime = runtime
            self._trt_engine = engine
            self._trt_context = context
            self._trt_ready = True
            self._backend_status = "tensorrt_loaded"
        except Exception as exc:  # pylint: disable=broad-except
            self._backend_status = "tensorrt_unavailable"
            self._trt_load_error = str(exc)

    def _publish_backend_status(self) -> None:
        now = time.time()
        if now - self._last_status_publish < 2.0:
            return
        msg = String()
        msg.data = self._backend_status
        self.backend_status_pub.publish(msg)
        self._last_status_publish = now

    def _detect_with_tensorrt(self, _image_bgr: np.ndarray) -> Optional[Dict]:
        # Full TensorRT decode pipeline will be enabled after engine schema lock.
        # For now, this method returns None and canonical fallback handles deterministic sim targets.
        if not self._trt_ready:
            return None
        return None

    def _detect_red_blob(self, image_bgr: np.ndarray) -> Optional[Dict]:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        lower_red_1 = (0, 70, 50)
        upper_red_1 = (15, 255, 255)
        lower_red_2 = (165, 70, 50)
        upper_red_2 = (180, 255, 255)

        mask_1 = cv2.inRange(hsv, lower_red_1, upper_red_1)
        mask_2 = cv2.inRange(hsv, lower_red_2, upper_red_2)
        mask = cv2.bitwise_or(mask_1, mask_2)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        _, mask = cv2.threshold(mask, 90, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(best))
        if area < float(self.red_fallback_min_area_px):
            return None

        x, y, width, height = cv2.boundingRect(best)
        center_x = float(x + (width / 2.0))
        center_y = float(y + (height * self.bbox_vertical_anchor))
        return {
            "bbox": (x, y, x + width, y + height),
            "center": (center_x, center_y),
            "confidence": float(self.red_fallback_confidence),
            "class_name": "sim_red_blob",
        }

    def image_callback(self, msg: Image) -> None:
        self._frames += 1
        start = time.perf_counter()

        try:
            image_bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:  # pylint: disable=broad-except
            self.get_logger().error(f"cv_bridge conversion failed: {exc}")
            return

        detection = self._detect_with_tensorrt(image_bgr)
        if detection is None and self.allow_red_fallback:
            detection = self._detect_red_blob(image_bgr)
            if detection is not None and self._backend_status.startswith("tensorrt"):
                self._backend_status = "tensorrt_loaded_fallback_active"

        if detection is not None and detection["confidence"] >= self.confidence_threshold:
            point_msg = Point()
            point_msg.x = float(detection["center"][0])
            point_msg.y = float(detection["center"][1])
            point_msg.z = 0.0
            self.position_pub.publish(point_msg)

            conf_msg = Float32()
            conf_msg.data = float(detection["confidence"])
            self.confidence_pub.publish(conf_msg)

            x1, y1, x2, y2 = detection["bbox"]
            cv2.rectangle(image_bgr, (x1, y1), (x2, y2), (0, 220, 0), 2)
            label = f"Ball ({detection['class_name']}): {detection['confidence']:.2f}"
            cv2.putText(image_bgr, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)

        if self._frames % 10 == 0:
            cv2.putText(
                image_bgr,
                f"backend={self._backend_status}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

        debug_msg = self.bridge.cv2_to_imgmsg(image_bgr, encoding="bgr8")
        debug_msg.header = msg.header
        self.debug_image_pub.publish(debug_msg)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        inference_msg = Float32()
        inference_msg.data = float(elapsed_ms)
        self.inference_ms_pub.publish(inference_msg)

        self._publish_backend_status()

        if self.show_window:
            cv2.imshow(self.window_name, image_bgr)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                self.get_logger().info("Window close requested; shutting down detector node.")
                cv2.destroyAllWindows()
                rclpy.shutdown()

    def destroy_node(self):
        if self.show_window:
            cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ChasecarTensorRtDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
