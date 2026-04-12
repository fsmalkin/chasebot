#!/usr/bin/env python3
"""Publish visited target positions as persistent Nav2 obstacle points."""

from __future__ import annotations

import json
import math
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header


def _default_runtime_path() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return str((repo_root / "runtime" / "dashboard" / "visit_mission_runtime.json").resolve())


def _load_runtime(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class VisitedTargetObstacleCloud(Node):
    def __init__(self) -> None:
        super().__init__("visited_target_obstacle_cloud")

        self.declare_parameter("runtime_path", _default_runtime_path())
        self.declare_parameter("cloud_topic", "/visited_target_obstacles")
        self.declare_parameter("frame_id", "odom")
        self.declare_parameter("publish_hz", 5.0)
        self.declare_parameter("point_z_m", 0.05)
        self.declare_parameter("obstacle_radius_m", 0.14)
        self.declare_parameter("inner_ring_radius_m", 0.07)
        self.declare_parameter("ring_points", 12)

        self.runtime_path = Path(str(self.get_parameter("runtime_path").value)).resolve()
        cloud_topic = str(self.get_parameter("cloud_topic").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.point_z_m = float(self.get_parameter("point_z_m").value)
        self.obstacle_radius_m = float(self.get_parameter("obstacle_radius_m").value)
        self.inner_ring_radius_m = float(self.get_parameter("inner_ring_radius_m").value)
        self.ring_points = max(int(self.get_parameter("ring_points").value), 4)

        publish_hz = max(float(self.get_parameter("publish_hz").value), 1.0)
        self.publisher = self.create_publisher(PointCloud2, cloud_topic, 10)
        self.create_timer(1.0 / publish_hz, self._publish_cloud)

        self.last_signature = ""
        self.get_logger().info(f"Visited target obstacle cloud runtime: {self.runtime_path}")
        self.get_logger().info(f"Visited target obstacle cloud topic: {cloud_topic}")

    def _publish_cloud(self) -> None:
        runtime = _load_runtime(self.runtime_path)
        visited_targets = runtime.get("visited_targets") if isinstance(runtime.get("visited_targets"), list) else []
        target_positions = runtime.get("target_positions") if isinstance(runtime.get("target_positions"), dict) else {}

        points: list[tuple[float, float, float]] = []
        active_positions: list[tuple[str, float, float]] = []
        for target_id in visited_targets:
            if not isinstance(target_id, str):
                continue
            pose = target_positions.get(target_id)
            if not isinstance(pose, dict):
                continue
            try:
                center_x = float(pose["x"])
                center_y = float(pose["y"])
            except (KeyError, TypeError, ValueError):
                continue
            active_positions.append((target_id, center_x, center_y))
            points.extend(self._disc_points(center_x, center_y))

        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = self.frame_id
        cloud = point_cloud2.create_cloud_xyz32(header, points)
        self.publisher.publish(cloud)

        signature = json.dumps(active_positions, separators=(",", ":"), sort_keys=False)
        if signature != self.last_signature:
            self.last_signature = signature
            self.get_logger().info(f"Publishing {len(active_positions)} visited target obstacle(s)")

    def _disc_points(self, center_x: float, center_y: float) -> list[tuple[float, float, float]]:
        points = [(center_x, center_y, self.point_z_m)]
        for radius in (self.inner_ring_radius_m, self.obstacle_radius_m):
            if radius <= 0.0:
                continue
            for idx in range(self.ring_points):
                theta = (2.0 * math.pi * float(idx)) / float(self.ring_points)
                points.append(
                    (
                        center_x + (radius * math.cos(theta)),
                        center_y + (radius * math.sin(theta)),
                        self.point_z_m,
                    )
                )
        return points


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VisitedTargetObstacleCloud()
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
