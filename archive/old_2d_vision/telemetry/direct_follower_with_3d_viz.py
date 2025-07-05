#!/usr/bin/env python3
"""
Direct Ball Follower with 3D Visualization
Shows robot view and ball detection in real-time
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist, PointStamped
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import ColorRGBA, Header
import cv2
from cv_bridge import CvBridge
from ultralytics import YOLO
import numpy as np
import os
import time
from datetime import datetime


class DirectFollowerWith3DViz(Node):
    def __init__(self):
        super().__init__('direct_follower_3d_viz')
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.marker_pub = self.create_publisher(MarkerArray, '/visualization_markers', 10)
        self.debug_image_pub = self.create_publisher(Image, '/debug/image_with_overlay', 10)
        
        # Subscriber
        self.image_sub = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 10)
        
        # YOLO setup
        model_path = os.path.expanduser('~/ros2_ws/yolov8m.pt')
        if not os.path.exists(model_path):
            self.get_logger().error(f'YOLO model not found at {model_path}')
        self.model = YOLO(model_path)
        self.bridge = CvBridge()
        
        # Control parameters
        self.linear_speed = 0.15  # m/s
        self.angular_speed = 0.4  # rad/s
        
        # Status tracking
        self.last_detection_time = None
        self.frame_count = 0
        self.status = "STARTING"
        self.ball_detected = False
        
        # Timer for telemetry
        self.create_timer(1.0, self.print_telemetry)
        
        self.get_logger().info('Direct Follower with 3D Visualization started')

    def image_callback(self, msg):
        self.frame_count += 1
        
        # Convert ROS image to OpenCV
        cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        height, width = cv_image.shape[:2]
        
        # Run YOLO detection
        results = self.model(cv_image, classes=[32], conf=0.6, verbose=False)
        
        # Initialize command
        cmd_vel = Twist()
        
        # Process detections
        if len(results) > 0 and len(results[0].boxes) > 0:
            # Get the first detection
            box = results[0].boxes[0]
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = box.conf[0].cpu().numpy()
            
            # Calculate center
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            
            # Normalize coordinates
            nx = cx / width
            ny = cy / height
            
            # Calculate ball size
            ball_width = (x2 - x1) / width
            ball_height = (y2 - y1) / height
            ball_size = (ball_width + ball_height) / 2
            
            self.ball_detected = True
            self.last_detection_time = self.get_clock().now()
            
            # Draw on image
            cv2.rectangle(cv_image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.circle(cv_image, (int(cx), int(cy)), 5, (255, 0, 0), -1)
            cv2.putText(cv_image, f"Ball: {conf:.2f}", (int(x1), int(y1)-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Control logic
            if ball_size < 0.15:  # Ball is far
                cmd_vel.linear.x = self.linear_speed
                self.status = "APPROACHING"
            else:
                cmd_vel.linear.x = 0.0
                self.status = "AT GOAL"
            
            # Center the ball
            center_error = nx - 0.5
            if abs(center_error) > 0.1:
                cmd_vel.angular.z = -center_error * self.angular_speed * 2.0
                self.status = "CENTERING"
            
            # Publish 3D markers
            self.publish_3d_markers(nx, ny, ball_size, conf)
            
        else:
            self.ball_detected = False
            self.status = "SEARCHING"
            cmd_vel.linear.x = 0.0
            cmd_vel.angular.z = 0.0
            
            cv2.putText(cv_image, "NO BALL DETECTED", (width//2-100, height//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # Add status overlay
        cv2.putText(cv_image, f"Status: {self.status}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(cv_image, f"Vel: {cmd_vel.linear.x:.2f}, {cmd_vel.angular.z:.2f}", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # Publish debug image
        debug_msg = self.bridge.cv2_to_imgmsg(cv_image, 'bgr8')
        self.debug_image_pub.publish(debug_msg)
        
        # Publish velocity command
        self.cmd_vel_pub.publish(cmd_vel)

    def publish_3d_markers(self, nx, ny, size, conf):
        """Publish visualization markers for RViz"""
        marker_array = MarkerArray()
        
        # Ball marker
        ball_marker = Marker()
        ball_marker.header.frame_id = "base_link"
        ball_marker.header.stamp = self.get_clock().now().to_msg()
        ball_marker.ns = "ball"
        ball_marker.id = 0
        ball_marker.type = Marker.SPHERE
        ball_marker.action = Marker.ADD
        
        # Estimate distance
        estimated_distance = 0.1 / size if size > 0 else 5.0
        
        # Position
        ball_marker.pose.position.x = estimated_distance
        ball_marker.pose.position.y = -(nx - 0.5) * estimated_distance
        ball_marker.pose.position.z = 0.05
        ball_marker.pose.orientation.w = 1.0
        
        # Size
        ball_marker.scale.x = 0.043
        ball_marker.scale.y = 0.043
        ball_marker.scale.z = 0.043
        
        # Color (green)
        ball_marker.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=1.0)
        
        marker_array.markers.append(ball_marker)
        
        # Confidence text
        text_marker = Marker()
        text_marker.header = ball_marker.header
        text_marker.ns = "text"
        text_marker.id = 1
        text_marker.type = Marker.TEXT_VIEW_FACING
        text_marker.action = Marker.ADD
        text_marker.pose.position.x = estimated_distance
        text_marker.pose.position.y = -(nx - 0.5) * estimated_distance
        text_marker.pose.position.z = 0.2
        text_marker.pose.orientation.w = 1.0
        text_marker.scale.z = 0.1
        text_marker.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)
        text_marker.text = f"Ball {conf*100:.0f}%\n{estimated_distance:.1f}m"
        
        marker_array.markers.append(text_marker)
        
        # Camera FOV lines
        fov_marker = Marker()
        fov_marker.header = ball_marker.header
        fov_marker.ns = "fov"
        fov_marker.id = 2
        fov_marker.type = Marker.LINE_LIST
        fov_marker.action = Marker.ADD
        fov_marker.scale.x = 0.01
        fov_marker.color = ColorRGBA(r=0.5, g=0.5, b=0.5, a=0.5)
        
        # FOV angle (approximate)
        fov_angle = 1.047  # 60 degrees
        max_dist = 5.0
        
        # Center line
        fov_marker.points.append(PointStamped().point)
        p = PointStamped().point
        p.x = max_dist
        fov_marker.points.append(p)
        
        self.marker_pub.publish(marker_array)

    def print_telemetry(self):
        """Print status telemetry"""
        os.system('clear')
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                 DIRECT FOLLOWER WITH 3D VISUALIZATION                        ║")
        print(f"║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                             ║")
        print("╠══════════════════════════════════════════════════════════════════════════════╣")
        print(f"║ STATUS: {self.status:<20}                                              ║")
        print(f"║ FRAMES: {self.frame_count:<10}                                                    ║")
        print(f"║ BALL: {'DETECTED' if self.ball_detected else 'NOT FOUND':<15}                                           ║")
        print("╠══════════════════════════════════════════════════════════════════════════════╣")
        print("║ DEBUG:                                                                       ║")
        print("║  - Check /debug/image_with_overlay topic for annotated camera view          ║")
        print("║  - Check /visualization_markers in RViz for 3D visualization                ║")
        print("║  - Ball detection runs on class 32 (sports ball) with conf > 0.6            ║")
        print("╚══════════════════════════════════════════════════════════════════════════════╝")


def main(args=None):
    rclpy.init(args=args)
    node = DirectFollowerWith3DViz()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
