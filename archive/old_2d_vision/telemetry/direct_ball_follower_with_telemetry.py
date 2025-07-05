#!/usr/bin/env python3
"""
Direct Ball Follower with Telemetry
Simple approach that bypasses complex transformations
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from visualization_msgs.msg import Marker
from std_msgs.msg import ColorRGBA
import cv2
from cv_bridge import CvBridge
from ultralytics import YOLO
import numpy as np
import os
import time
from datetime import datetime


class DirectBallFollowerWithTelemetry(Node):
    def __init__(self):
        super().__init__('direct_ball_follower')
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.marker_pub = self.create_publisher(Marker, '/ball_marker', 10)
        
        # Subscriber
        self.image_sub = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 10)
        
        # YOLO setup
        model_path = os.path.expanduser('~/ros2_ws/yolov8m.pt')
        self.model = YOLO(model_path)
        self.bridge = CvBridge()
        
        # Control parameters
        self.linear_speed = 0.15  # m/s
        self.angular_speed = 0.4  # rad/s
        self.approach_distance = 0.5  # meters (estimated from image size)
        
        # Telemetry
        self.last_detection_time = None
        self.detection_count = 0
        self.frame_count = 0
        self.last_telemetry_time = time.time()
        
        self.get_logger().info('Direct Ball Follower with Telemetry initialized')
        self.get_logger().info('Using simple proportional control')

    def image_callback(self, msg):
        self.frame_count += 1
        
        # Convert ROS image to OpenCV
        cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        
        # Run YOLO detection
        results = self.model(cv_image, classes=[32], conf=0.6, verbose=False)
        
        # Process results
        cmd_vel = Twist()
        ball_detected = False
        
        if len(results) > 0 and len(results[0].boxes) > 0:
            # Get the first detection
            box = results[0].boxes[0]
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = box.conf[0].cpu().numpy()
            
            # Calculate center
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            
            # Normalize coordinates
            height, width = cv_image.shape[:2]
            nx = cx / width
            ny = cy / height
            
            # Calculate ball size as percentage of image
            ball_width = (x2 - x1) / width
            ball_height = (y2 - y1) / height
            ball_size = (ball_width + ball_height) / 2
            
            ball_detected = True
            self.detection_count += 1
            self.last_detection_time = time.time()
            
            # Simple control logic
            # If ball is too small (far away), move forward
            if ball_size < 0.15:  # Ball takes up less than 15% of image
                cmd_vel.linear.x = self.linear_speed
                status = "APPROACHING"
            else:
                cmd_vel.linear.x = 0.0
                status = "AT GOAL"
            
            # Turn to center ball
            center_error = nx - 0.5
            if abs(center_error) > 0.1:  # Dead zone
                cmd_vel.angular.z = -center_error * self.angular_speed * 2.0
                status = "CENTERING"
            
            # Publish marker
            self.publish_ball_marker(nx, ny, ball_size)
            
            # Print telemetry every second
            if time.time() - self.last_telemetry_time > 1.0:
                self.print_telemetry(nx, ny, ball_size, conf, cmd_vel, status)
                self.last_telemetry_time = time.time()
        
        else:
            # No ball detected - stop
            cmd_vel.linear.x = 0.0
            cmd_vel.angular.z = 0.0
            
            if time.time() - self.last_telemetry_time > 1.0:
                self.print_telemetry(0, 0, 0, 0, cmd_vel, "NO DETECTION")
                self.last_telemetry_time = time.time()
        
        # Publish velocity command
        self.cmd_vel_pub.publish(cmd_vel)

    def publish_ball_marker(self, nx, ny, size):
        """Publish a marker at the estimated ball position"""
        marker = Marker()
        marker.header.frame_id = "base_link"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "ball"
        marker.id = 0
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        
        # Estimate distance based on ball size
        # Assuming ball is 4.3cm diameter and camera FOV
        estimated_distance = 0.1 / size  # Rough estimate
        
        # Position in front of robot
        marker.pose.position.x = estimated_distance
        marker.pose.position.y = -(nx - 0.5) * estimated_distance
        marker.pose.position.z = 0.05
        
        marker.pose.orientation.w = 1.0
        
        # Size
        marker.scale.x = 0.043
        marker.scale.y = 0.043
        marker.scale.z = 0.043
        
        # Color (green)
        marker.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=1.0)
        
        self.marker_pub.publish(marker)

    def print_telemetry(self, nx, ny, size, conf, cmd_vel, status):
        """Print telemetry information"""
        os.system('clear')
        print("╔══════════════════════════════════════════════════════════════════════════════╗")
        print("║                    DIRECT BALL FOLLOWER TELEMETRY                            ║")
        print(f"║                        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                             ║")
        print("╠══════════════════════════════════════════════════════════════════════════════╣")
        
        if conf > 0:
            print(f"║ BALL DETECTION:                                                              ║")
            print(f"║   Position: ({nx:.3f}, {ny:.3f}) normalized                                     ║")
            print(f"║   Size: {size:.3f} (% of image)                                                ║")
            print(f"║   Confidence: {conf*100:.1f}%                                                      ║")
            print(f"║   Est. Distance: {0.1/size if size > 0 else 0:.2f}m                                             ║")
        else:
            print(f"║ BALL DETECTION: NOT DETECTED                                                 ║")
        
        print(f"║                                                                              ║")
        print(f"║ ROBOT CONTROL:                                                               ║")
        print(f"║   Linear Vel: {cmd_vel.linear.x:+.3f} m/s                                           ║")
        print(f"║   Angular Vel: {cmd_vel.angular.z:+.3f} rad/s                                        ║")
        print(f"║   Status: {status:<20}                                                 ║")
        
        print(f"║                                                                              ║")
        print(f"║ STATISTICS:                                                                  ║")
        print(f"║   Frames: {self.frame_count}                                                           ║")
        print(f"║   Detections: {self.detection_count}                                                       ║")
        print(f"║   Detection Rate: {self.detection_count/max(self.frame_count,1)*100:.1f}%                                          ║")
        
        print("╚══════════════════════════════════════════════════════════════════════════════╝")
        
        # Status indicators
        if conf > 0:
            print("🟢 Ball Detected  ", end='')
        else:
            print("🔴 No Ball  ", end='')
        
        if abs(cmd_vel.linear.x) > 0 or abs(cmd_vel.angular.z) > 0:
            print("🟢 Robot Moving")
        else:
            print("🔴 Robot Stopped")


def main(args=None):
    rclpy.init(args=args)
    node = DirectBallFollowerWithTelemetry()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
