#!/usr/bin/env python3
"""
File: yolo_3d_position_extractor.py
Status: ACTIVE
Version: 1.0.0
Last Updated: 2025-01-09
Purpose: Extracts 3D positions from YOLO detections + depth data
Dependencies: ROS2 Humble, numpy
Working Status: VERIFIED
Notes: Core component of 3D vision pipeline
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point, PointStamped
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Float32
from cv_bridge import CvBridge
import numpy as np
import message_filters
import time
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy


class YOLO3DPositionExtractor(Node):
    def __init__(self):
        super().__init__('yolo_3d_position_extractor')
        
        # Parameters
        self.declare_parameter('confidence_threshold', 0.1)
        self.declare_parameter('detection_stale_timeout_s', 0.5)
        self.declare_parameter('depth_sample_radius_px', 3)
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        self.detection_stale_timeout_s = float(
            self.get_parameter('detection_stale_timeout_s').value
        )
        self.depth_sample_radius_px = int(self.get_parameter('depth_sample_radius_px').value)
        
        # CV Bridge for image conversion
        self.bridge = CvBridge()
        
        # Camera intrinsics (will be updated from camera_info)
        self.fx = None
        self.fy = None
        self.cx = None
        self.cy = None
        self.camera_frame = 'd415_camera_link'
        
        # Latest detection data
        self.latest_position_2d = None
        self.latest_confidence = 0.0
        self.latest_position_mono = 0.0
        self.latest_confidence_mono = 0.0
        
        # QoS profile for sensor data
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )
        
        # Subscribers
        self.position_sub = self.create_subscription(
            Point,
            '/yolo/ball_position',
            self.position_callback,
            10
        )
        
        self.confidence_sub = self.create_subscription(
            Float32,
            '/yolo/confidence',
            self.confidence_callback,
            10
        )
        
        self.depth_sub = self.create_subscription(
            Image,
            '/d415/depth/image_raw',
            self.depth_callback,
            sensor_qos
        )
        
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/d415/depth/camera_info',
            self.camera_info_callback,
            sensor_qos
        )
        
        # Publishers
        self.position_3d_pub = self.create_publisher(
            PointStamped,
            '/yolo/ball_position_3d',
            10
        )
        
        self.get_logger().info('3D Position Extractor initialized')
        self.get_logger().info(f'Confidence threshold: {self.confidence_threshold}')
        self.get_logger().info(f'Detection stale timeout: {self.detection_stale_timeout_s:.2f}s')
        self.get_logger().info(f'Depth sample radius: {self.depth_sample_radius_px}px')
        self.get_logger().info('Waiting for camera info and detections...')
        
        # Debug counters
        self.position_received_count = 0
        self.confidence_received_count = 0
        self.depth_received_count = 0
    
    def camera_info_callback(self, msg):
        """Extract camera intrinsics from camera info"""
        if self.fx is None:
            self.fx = msg.k[0]  # Focal length x
            self.fy = msg.k[4]  # Focal length y
            self.cx = msg.k[2]  # Principal point x
            self.cy = msg.k[5]  # Principal point y
            self.camera_frame = msg.header.frame_id
            
            self.get_logger().info(f'Camera intrinsics received:')
            self.get_logger().info(f'  fx: {self.fx:.2f}, fy: {self.fy:.2f}')
            self.get_logger().info(f'  cx: {self.cx:.2f}, cy: {self.cy:.2f}')
            self.get_logger().info(f'  frame: {self.camera_frame}')
    
    def position_callback(self, msg):
        """Store latest 2D position (normalized coordinates)"""
        self.latest_position_2d = msg
        self.latest_position_mono = time.monotonic()
        self.position_received_count += 1
        if self.position_received_count % 10 == 1:  # Log every 10th
            self.get_logger().info(f'Position received #{self.position_received_count}: ({msg.x:.3f}, {msg.y:.3f})')
    
    def confidence_callback(self, msg):
        """Store latest confidence"""
        self.latest_confidence = msg.data
        self.latest_confidence_mono = time.monotonic()
        self.confidence_received_count += 1
        if self.confidence_received_count % 10 == 1:  # Log every 10th
            self.get_logger().info(f'Confidence received #{self.confidence_received_count}: {msg.data:.3f}')
    
    def depth_callback(self, msg):
        """Process depth image and extract 3D position if detection is available"""
        self.depth_received_count += 1
        
        # Check if we have all required data
        if self.fx is None:
            if self.depth_received_count % 30 == 1:
                self.get_logger().warn('Waiting for camera intrinsics...')
            return
        
        if self.latest_position_2d is None:
            if self.depth_received_count % 30 == 1:
                self.get_logger().info('Waiting for YOLO position...')
            return

        now_mono = time.monotonic()
        if (
            now_mono - self.latest_position_mono > self.detection_stale_timeout_s
            or now_mono - self.latest_confidence_mono > self.detection_stale_timeout_s
        ):
            if self.depth_received_count % 30 == 1:
                self.get_logger().info('Skipping stale YOLO detection sample')
            return
        
        if self.latest_confidence < self.confidence_threshold:
            if self.depth_received_count % 30 == 1:
                self.get_logger().info(f'Confidence {self.latest_confidence:.3f} < threshold {self.confidence_threshold:.3f}')
            return
        
        try:
            # Convert depth image to numpy array
            if msg.encoding == '16UC1':
                depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='16UC1')
                depth_scale = 0.001  # D415 default: depth in mm, convert to meters
            elif msg.encoding == '32FC1':
                depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='32FC1')
                depth_scale = 1.0  # Already in meters
            else:
                self.get_logger().error(f'Unsupported depth encoding: {msg.encoding}')
                return
            
            # Convert normalized coordinates to pixel coordinates
            height, width = depth_image.shape
            pixel_x = int(self.latest_position_2d.x * width)
            pixel_y = int(self.latest_position_2d.y * height)
            
            # Ensure pixel coordinates are within bounds
            pixel_x = max(0, min(pixel_x, width - 1))
            pixel_y = max(0, min(pixel_y, height - 1))
            
            # Use a small depth window median for robustness near edges/horizon.
            radius = max(0, self.depth_sample_radius_px)
            y0 = max(0, pixel_y - radius)
            y1 = min(height - 1, pixel_y + radius)
            x0 = max(0, pixel_x - radius)
            x1 = min(width - 1, pixel_x + radius)
            depth_window = depth_image[y0:y1 + 1, x0:x1 + 1]
            valid_window = depth_window[np.isfinite(depth_window) & (depth_window > 0)]
            if valid_window.size > 0:
                depth_value = float(np.median(valid_window) * depth_scale)
            else:
                depth_value = float(depth_image[pixel_y, pixel_x] * depth_scale)
            
            # Get depth statistics for debugging
            valid_depths = depth_image[depth_image > 0]
            if len(valid_depths) > 0:
                min_depth = np.min(valid_depths) * depth_scale
                max_depth = np.max(valid_depths) * depth_scale
                mean_depth = np.mean(valid_depths) * depth_scale
                
                # Log depth stats every 30 frames
                if self.depth_received_count % 30 == 0:
                    self.get_logger().info(
                        f'Depth stats: min={min_depth:.2f}m, max={max_depth:.2f}m, '
                        f'mean={mean_depth:.2f}m, valid_pixels={len(valid_depths)}'
                    )
            
            # Skip if depth is invalid (0 or very large)
            if depth_value <= 0.01 or depth_value > 10.0:
                self.get_logger().warn(
                    f'Invalid depth at ({pixel_x}, {pixel_y}): {depth_value:.3f}m '
                    f'(encoding: {msg.encoding}, scale: {depth_scale})'
                )
                return
            
            # Convert pixel + depth to 3D point using camera intrinsics
            # Camera coordinate system: X-right, Y-down, Z-forward
            z = depth_value
            x = (pixel_x - self.cx) * z / self.fx
            y = (pixel_y - self.cy) * z / self.fy
            
            # Create and publish 3D position
            position_3d = PointStamped()
            position_3d.header.stamp = msg.header.stamp
            position_3d.header.frame_id = self.camera_frame
            position_3d.point.x = x
            position_3d.point.y = y
            position_3d.point.z = z
            
            self.position_3d_pub.publish(position_3d)
            
            self.get_logger().info(
                f'3D Position: [{x:.3f}, {y:.3f}, {z:.3f}]m '
                f'(from pixel [{pixel_x}, {pixel_y}], '
                f'confidence: {self.latest_confidence:.3f})'
            )
            
        except Exception as e:
            self.get_logger().error(f'Error processing depth: {str(e)}')


def main(args=None):
    rclpy.init(args=args)
    node = YOLO3DPositionExtractor()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
