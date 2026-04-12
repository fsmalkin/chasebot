#!/usr/bin/env python3

import math

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image, LaserScan


class VisionToLaserScanHSV(Node):
    """
    Converts RGB detections of the red target balls into a LaserScan for Nav2.

    The original node estimated obstacle distance from pixel position only, which
    made the costmap inconsistent. This version keeps the HSV mask but measures
    range from the D415 depth image when available, so the scan lands in the
    correct frame with real obstacle distances.
    """

    def __init__(self):
        super().__init__("vision_to_laserscan_hsv")

        self.declare_parameter("image_topic", "/d415/color/image_raw")
        self.declare_parameter("depth_topic", "/d415/depth/image_raw")
        self.declare_parameter("camera_info_topic", "/d415/depth/camera_info")

        image_topic = str(self.get_parameter("image_topic").value)
        depth_topic = str(self.get_parameter("depth_topic").value)
        camera_info_topic = str(self.get_parameter("camera_info_topic").value)

        self.image_sub = self.create_subscription(Image, image_topic, self.image_callback, 10)
        self.depth_sub = self.create_subscription(Image, depth_topic, self.depth_callback, 10)
        self.camera_info_sub = self.create_subscription(CameraInfo, camera_info_topic, self.camera_info_callback, 10)

        self.scan_pub = self.create_publisher(LaserScan, "/scan", 10)
        self.debug_pub = self.create_publisher(Image, "/vision_to_laserscan/debug", 10)

        self.bridge = CvBridge()

        self.declare_parameter("hsv_lower_h", 0)
        self.declare_parameter("hsv_upper_h", 10)
        self.declare_parameter("hsv_lower_s", 100)
        self.declare_parameter("hsv_upper_s", 255)
        self.declare_parameter("hsv_lower_v", 100)
        self.declare_parameter("hsv_upper_v", 255)

        self.declare_parameter("num_scan_samples", 360)
        self.declare_parameter("scan_range_max", 5.0)
        self.declare_parameter("scan_range_min", 0.1)
        self.declare_parameter("depth_max_age_s", 0.25)
        self.declare_parameter("min_contour_area_px", 60.0)
        self.declare_parameter("mask_open_kernel_px", 5)
        self.declare_parameter("mask_close_kernel_px", 9)

        self.hsv_lower = np.array(
            [
                self.get_parameter("hsv_lower_h").value,
                self.get_parameter("hsv_lower_s").value,
                self.get_parameter("hsv_lower_v").value,
            ],
            dtype=np.uint8,
        )
        self.hsv_upper = np.array(
            [
                self.get_parameter("hsv_upper_h").value,
                self.get_parameter("hsv_upper_s").value,
                self.get_parameter("hsv_upper_v").value,
            ],
            dtype=np.uint8,
        )

        self.num_scan_samples = int(self.get_parameter("num_scan_samples").value)
        self.scan_range_max = float(self.get_parameter("scan_range_max").value)
        self.scan_range_min = float(self.get_parameter("scan_range_min").value)
        self.depth_max_age_s = float(self.get_parameter("depth_max_age_s").value)
        self.min_contour_area_px = float(self.get_parameter("min_contour_area_px").value)
        self.mask_open_kernel_px = int(self.get_parameter("mask_open_kernel_px").value)
        self.mask_close_kernel_px = int(self.get_parameter("mask_close_kernel_px").value)

        self.horizontal_fov = 62.2 * math.pi / 180.0
        self.camera_fx = 0.0
        self.camera_cx = 0.0
        self.latest_depth_image = None
        self.latest_depth_header = None
        self.latest_depth_stamp_s = 0.0
        self.frame_counter = 0
        self.depth_warning_counter = 0

        self.get_logger().info("Vision to LaserScan HSV node initialized")
        self.get_logger().info(f"RGB topic: {image_topic}")
        self.get_logger().info(f"Depth topic: {depth_topic}")
        self.get_logger().info(f"Camera info topic: {camera_info_topic}")
        self.get_logger().info(f"HSV range: [{self.hsv_lower}] to [{self.hsv_upper}]")

    def camera_info_callback(self, msg: CameraInfo):
        if len(msg.k) >= 6 and float(msg.k[0]) > 0.0:
            self.camera_fx = float(msg.k[0])
            self.camera_cx = float(msg.k[2])

    def depth_callback(self, msg: Image):
        try:
            depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        except Exception as exc:
            self.get_logger().error(f"Error converting depth image: {exc}")
            return

        if msg.encoding == "16UC1":
            depth_m = depth_image.astype(np.float32) * 0.001
        elif msg.encoding == "32FC1":
            depth_m = depth_image.astype(np.float32)
        else:
            self.get_logger().warn(f"Unsupported depth encoding: {msg.encoding}")
            return

        self.latest_depth_image = depth_m
        self.latest_depth_header = msg.header
        self.latest_depth_stamp_s = self._stamp_to_seconds(msg.header.stamp)

    def image_callback(self, msg: Image):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            mask = self._build_mask(cv_image)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            scan = self.create_scan_from_mask(mask, contours, msg.header)
            self.scan_pub.publish(scan)

            debug_image = self.create_debug_image(cv_image, mask, contours)
            debug_msg = self.bridge.cv2_to_imgmsg(debug_image, "bgr8")
            debug_msg.header = msg.header
            self.debug_pub.publish(debug_msg)
        except Exception as exc:
            self.get_logger().error(f"Error processing image: {exc}")

    def create_scan_from_mask(self, mask, contours, color_header):
        height, width = mask.shape[:2]
        angle_min, angle_max = self._scan_angle_limits(width)
        angle_increment = (angle_max - angle_min) / max(self.num_scan_samples - 1, 1)

        scan = LaserScan()
        scan.header.stamp = color_header.stamp
        scan.header.frame_id = color_header.frame_id
        if self._depth_ready(color_header):
            scan.header.stamp = self.latest_depth_header.stamp
            scan.header.frame_id = self.latest_depth_header.frame_id
        scan.angle_min = angle_min
        scan.angle_max = angle_max
        scan.angle_increment = angle_increment
        scan.time_increment = 0.0
        scan.scan_time = 0.033
        scan.range_min = self.scan_range_min
        scan.range_max = self.scan_range_max
        scan.ranges = [float("inf")] * self.num_scan_samples

        valid_contours = []
        for contour in contours:
            if cv2.contourArea(contour) < self.min_contour_area_px:
                continue
            valid_contours.append(contour)

            x, y, w, h = cv2.boundingRect(contour)
            distance_m = self._estimate_contour_distance(contour, mask.shape)
            if distance_m is None:
                distance_m = self.estimate_distance_from_position(y + h, height, x + (w / 2.0), width)
            if distance_m is None:
                continue

            start_angle = self._column_to_angle(float(x), width)
            end_angle = self._column_to_angle(float(x + w - 1), width)
            if start_angle > end_angle:
                start_angle, end_angle = end_angle, start_angle
            start_idx = max(0, min(self.num_scan_samples - 1, int((start_angle - angle_min) / angle_increment)))
            end_idx = max(0, min(self.num_scan_samples - 1, int((end_angle - angle_min) / angle_increment)))
            for idx in range(start_idx, end_idx + 1):
                scan.ranges[idx] = min(scan.ranges[idx], float(distance_m))

        self.frame_counter += 1
        if self.frame_counter % 90 == 0:
            mode = "depth" if self._depth_ready(color_header) else "fallback"
            self.get_logger().info(
                f"Published scan with {len(valid_contours)} contours using {mode} ranges; frame={scan.header.frame_id}"
            )

        return scan

    def estimate_distance_from_position(self, row, image_height, col, image_width):
        normalized_row = float(row) / max(float(image_height), 1.0)
        if normalized_row > 0.8:
            distance = self.scan_range_min + 0.5
        elif normalized_row < 0.3:
            distance = self.scan_range_max
        else:
            distance = 3.0 - (normalized_row - 0.3) * 4.0

        normalized_col = abs(float(col) - (image_width / 2.0)) / max((image_width / 2.0), 1.0)
        distance *= 1.0 + 0.2 * normalized_col
        return max(self.scan_range_min, min(self.scan_range_max, distance))

    def create_debug_image(self, image, mask, contours):
        debug_image = image.copy()
        depth_ready = self._depth_ready()

        for contour in contours:
            if cv2.contourArea(contour) < self.min_contour_area_px:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(debug_image, (x, y), (x + w, y + h), (255, 0, 255), 2)
            distance_m = self._estimate_contour_distance(contour, mask.shape)
            label = "depth"
            if distance_m is None:
                distance_m = self.estimate_distance_from_position(y + h, image.shape[0], x + (w / 2.0), image.shape[1])
                label = "fallback"
            cv2.putText(
                debug_image,
                f"{distance_m:.2f}m {label}",
                (x, max(y - 8, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        debug_image[mask > 0] = (0.5 * debug_image[mask > 0] + np.array([0, 0, 180])).astype(np.uint8)
        cv2.putText(
            debug_image,
            "Vision to LaserScan HSV",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            debug_image,
            f"range source: {'depth' if depth_ready else 'fallback'}",
            (10, 54),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            debug_image,
            f"HSV: {int(self.hsv_lower[0])}-{int(self.hsv_upper[0])}",
            (10, 74),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return debug_image

    def _build_mask(self, image):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)

        if self.mask_open_kernel_px > 1:
            kernel = np.ones((self.mask_open_kernel_px, self.mask_open_kernel_px), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        if self.mask_close_kernel_px > 1:
            kernel = np.ones((self.mask_close_kernel_px, self.mask_close_kernel_px), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return mask

    def _estimate_contour_distance(self, contour, mask_shape):
        if self.latest_depth_image is None:
            return None

        depth_image = self.latest_depth_image
        mask_height, mask_width = mask_shape[:2]
        depth_height, depth_width = depth_image.shape[:2]

        contour_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
        if (depth_width, depth_height) != (mask_width, mask_height):
            contour_mask = cv2.resize(contour_mask, (depth_width, depth_height), interpolation=cv2.INTER_NEAREST)

        valid = depth_image[
            (contour_mask > 0)
            & np.isfinite(depth_image)
            & (depth_image >= self.scan_range_min)
            & (depth_image <= self.scan_range_max)
        ]
        if valid.size == 0:
            return None

        return float(np.median(valid))

    def _scan_angle_limits(self, image_width):
        if self.camera_fx > 0.0:
            angle_min = math.atan2(-self.camera_cx, self.camera_fx)
            angle_max = math.atan2((image_width - 1) - self.camera_cx, self.camera_fx)
            if angle_min < angle_max:
                return angle_min, angle_max
        half_fov = self.horizontal_fov / 2.0
        return -half_fov, half_fov

    def _column_to_angle(self, col, image_width):
        if self.camera_fx > 0.0:
            return math.atan2(col - self.camera_cx, self.camera_fx)
        normalized = (float(col) / max(float(image_width - 1), 1.0)) - 0.5
        return normalized * self.horizontal_fov

    def _depth_ready(self, header=None):
        if self.latest_depth_image is None or self.latest_depth_header is None:
            return False
        if header is None:
            return True
        age_s = abs(self._stamp_to_seconds(header.stamp) - self.latest_depth_stamp_s)
        if age_s <= self.depth_max_age_s:
            return True
        self.depth_warning_counter += 1
        if self.depth_warning_counter % 60 == 1:
            self.get_logger().warn(
                f"Depth image age {age_s:.3f}s exceeds limit {self.depth_max_age_s:.3f}s; using fallback range estimate."
            )
        return False

    @staticmethod
    def _stamp_to_seconds(stamp):
        return float(stamp.sec) + (float(stamp.nanosec) / 1_000_000_000.0)


def main(args=None):
    rclpy.init(args=args)
    
    vision_to_laserscan = VisionToLaserScanHSV()
    
    try:
        rclpy.spin(vision_to_laserscan)
    except KeyboardInterrupt:
        pass
    finally:
        vision_to_laserscan.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
