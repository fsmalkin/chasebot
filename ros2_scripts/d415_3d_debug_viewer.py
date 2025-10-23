#!/usr/bin/env python3
"""
D415 3D Debug Viewer
Shows RGB camera with YOLO detections and depth image side-by-side
Subscribes to YOLO detection topics and 3D position extraction
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import Point, PointStamped
from std_msgs.msg import Float32
from cv_bridge import CvBridge
import cv2
import numpy as np
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy


class D4153DDebugViewer(Node):
    def __init__(self):
        super().__init__('d415_3d_debug_viewer')
        
        # CV Bridge
        self.bridge = CvBridge()
        
        # Latest data
        self.latest_rgb = None
        self.latest_depth = None
        self.latest_yolo_position = None
        self.latest_yolo_confidence = 0.0
        self.latest_3d_position = None
        
        # Frame counters
        self.rgb_frame_count = 0
        self.depth_frame_count = 0
        self.yolo_detection_count = 0
        self.position_3d_count = 0
        
        # FPS tracking
        self.last_time = self.get_clock().now()
        self.fps = 0.0
        
        # QoS profile for sensor data
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE
        )
        
        # Subscribers
        self.rgb_sub = self.create_subscription(
            Image,
            '/d415/color/image_raw',
            self.rgb_callback,
            sensor_qos
        )
        
        self.depth_sub = self.create_subscription(
            Image,
            '/d415/depth/image_raw',
            self.depth_callback,
            sensor_qos
        )
        
        self.yolo_position_sub = self.create_subscription(
            Point,
            '/yolo/ball_position',
            self.yolo_position_callback,
            10
        )
        
        self.yolo_confidence_sub = self.create_subscription(
            Float32,
            '/yolo/confidence',
            self.yolo_confidence_callback,
            10
        )
        
        self.position_3d_sub = self.create_subscription(
            PointStamped,
            '/yolo/ball_position_3d',
            self.position_3d_callback,
            10
        )
        
        # Timer for display update (30 Hz)
        self.display_timer = self.create_timer(0.033, self.update_display)
        
        self.get_logger().info('D415 3D Debug Viewer initialized')
        self.get_logger().info('Subscribing to:')
        self.get_logger().info('  - /d415/color/image_raw')
        self.get_logger().info('  - /d415/depth/image_raw')
        self.get_logger().info('  - /yolo/ball_position')
        self.get_logger().info('  - /yolo/confidence')
        self.get_logger().info('  - /yolo/ball_position_3d')
        self.get_logger().info('Press Q to quit')
    
    def rgb_callback(self, msg):
        """Handle RGB image"""
        try:
            self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.rgb_frame_count += 1
        except Exception as e:
            self.get_logger().error(f'Error converting RGB image: {str(e)}')
    
    def depth_callback(self, msg):
        """Handle depth image"""
        try:
            if msg.encoding == '16UC1':
                depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='16UC1')
                # Convert to float meters
                self.latest_depth = depth_image.astype(np.float32) * 0.001
            elif msg.encoding == '32FC1':
                self.latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='32FC1')
            else:
                self.get_logger().warn(f'Unsupported depth encoding: {msg.encoding}')
            
            self.depth_frame_count += 1
        except Exception as e:
            self.get_logger().error(f'Error converting depth image: {str(e)}')
    
    def yolo_position_callback(self, msg):
        """Handle YOLO detection position (normalized coordinates)"""
        self.latest_yolo_position = msg
        self.yolo_detection_count += 1
        self.get_logger().info(f'YOLO detection #{self.yolo_detection_count}: ({msg.x:.3f}, {msg.y:.3f})')
    
    def yolo_confidence_callback(self, msg):
        """Handle YOLO detection confidence"""
        self.latest_yolo_confidence = msg.data
    
    def position_3d_callback(self, msg):
        """Handle 3D position"""
        self.latest_3d_position = msg
        self.position_3d_count += 1
        self.get_logger().info(
            f'3D Position #{self.position_3d_count}: '
            f'[{msg.point.x:.3f}, {msg.point.y:.3f}, {msg.point.z:.3f}]m'
        )
    
    def colorize_depth(self, depth_image):
        """Convert depth image to colorized version for visualization"""
        if depth_image is None:
            return None
        
        # Get valid depth values (ignore 0s)
        valid_depths = depth_image[depth_image > 0]
        
        if len(valid_depths) == 0:
            return np.zeros((depth_image.shape[0], depth_image.shape[1], 3), dtype=np.uint8)
        
        # Calculate min/max for normalization
        min_depth = np.percentile(valid_depths, 5)
        max_depth = np.percentile(valid_depths, 95)
        
        # Normalize to 0-255
        depth_normalized = np.clip((depth_image - min_depth) / (max_depth - min_depth), 0, 1)
        depth_normalized = (depth_normalized * 255).astype(np.uint8)
        
        # Apply colormap
        depth_colorized = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
        
        # Make invalid pixels black
        depth_colorized[depth_image <= 0] = [0, 0, 0]
        
        return depth_colorized
    
    def update_display(self):
        """Update the visualization display"""
        # Calculate FPS
        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        if dt > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)
        self.last_time = current_time
        
        # Create display image
        if self.latest_rgb is not None:
            rgb_display = self.latest_rgb.copy()
            
            # Draw YOLO detection if available
            if self.latest_yolo_position is not None:
                h, w = rgb_display.shape[:2]
                x = int(self.latest_yolo_position.x * w)
                y = int(self.latest_yolo_position.y * h)
                
                # Draw detection box (approximate size)
                box_size = 40
                cv2.rectangle(rgb_display, 
                            (x - box_size, y - box_size),
                            (x + box_size, y + box_size),
                            (0, 255, 0), 2)
                
                # Draw center point
                cv2.circle(rgb_display, (x, y), 5, (0, 0, 255), -1)
                
                # Add confidence text
                conf_text = f'Conf: {self.latest_yolo_confidence:.2f}'
                cv2.putText(rgb_display, conf_text, (x - 40, y - 45),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            rgb_display = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(rgb_display, 'Waiting for RGB...', (200, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Create depth display
        if self.latest_depth is not None:
            depth_display = self.colorize_depth(self.latest_depth)
            
            # If we have a YOLO detection, mark it on depth too
            if self.latest_yolo_position is not None:
                h, w = depth_display.shape[:2]
                x = int(self.latest_yolo_position.x * w)
                y = int(self.latest_yolo_position.y * h)
                
                # Draw crosshair
                cv2.line(depth_display, (x - 10, y), (x + 10, y), (255, 255, 255), 2)
                cv2.line(depth_display, (x, y - 10), (x, y + 10), (255, 255, 255), 2)
                
                # Show depth value at that point
                if 0 <= y < self.latest_depth.shape[0] and 0 <= x < self.latest_depth.shape[1]:
                    depth_value = self.latest_depth[y, x]
                    depth_text = f'{depth_value:.2f}m'
                    cv2.putText(depth_display, depth_text, (x + 15, y - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        else:
            depth_display = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(depth_display, 'Waiting for Depth...', (200, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Ensure both images have the same height
        if rgb_display.shape[0] != depth_display.shape[0]:
            target_height = max(rgb_display.shape[0], depth_display.shape[0])
            if rgb_display.shape[0] < target_height:
                rgb_display = cv2.resize(rgb_display, (rgb_display.shape[1], target_height))
            else:
                depth_display = cv2.resize(depth_display, (depth_display.shape[1], target_height))
        
        # Combine images side by side
        combined = np.hstack([rgb_display, depth_display])
        
        # Add info panel at bottom
        info_height = 80
        info_panel = np.zeros((info_height, combined.shape[1], 3), dtype=np.uint8)
        
        # Add text to info panel
        info_y = 20
        cv2.putText(info_panel, f'FPS: {self.fps:.1f}', (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(info_panel, f'RGB: {self.rgb_frame_count}', (120, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(info_panel, f'Depth: {self.depth_frame_count}', (250, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(info_panel, f'YOLO: {self.yolo_detection_count}', (400, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(info_panel, f'3D Pos: {self.position_3d_count}', (530, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        info_y = 50
        if self.latest_3d_position is not None:
            pos_text = (f'3D Position: X={self.latest_3d_position.point.x:.3f}m, '
                       f'Y={self.latest_3d_position.point.y:.3f}m, '
                       f'Z={self.latest_3d_position.point.z:.3f}m')
            cv2.putText(info_panel, pos_text, (10, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        
        # Stack info panel below main display
        final_display = np.vstack([combined, info_panel])
        
        # Add title bar
        cv2.putText(final_display, 'RGB + YOLO', (160, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(final_display, 'Depth Map', (rgb_display.shape[1] + 160, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Show the combined display
        cv2.imshow('D415 3D Debug Viewer', final_display)
        
        # Check for quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'):
            self.get_logger().info('User requested quit')
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = D4153DDebugViewer()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
