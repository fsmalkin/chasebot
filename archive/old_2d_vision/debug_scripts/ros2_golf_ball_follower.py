#!/usr/bin/env python3

"""
ROS 2 Golf Ball Following Node
Professional object following behavior for ChaseBot
Integrates vision detection with differential drive control
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, Point
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge
import numpy as np
import math

class GolfBallFollower(Node):
    def __init__(self):
        super().__init__('golf_ball_follower')
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Publishers and subscribers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.image_sub = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        
        # Control parameters
        self.image_width = 640
        self.image_height = 480
        self.center_x = self.image_width // 2
        self.center_y = self.image_height // 2
        
        # Following behavior parameters
        self.linear_speed = 0.2  # m/s
        self.angular_speed = 0.5  # rad/s
        self.min_area = 100  # Much lower threshold for small golf balls
        self.target_area = 8000  # Target area for optimal distance
        self.max_area = 15000  # Maximum area - too close
        
        # Tolerance zones
        self.center_tolerance = 50  # pixels
        self.area_tolerance = 1000  # area units
        
        # Safety limits
        self.max_linear_speed = 0.3
        self.max_angular_speed = 1.0
        
        # Detection state
        self.last_detection_time = self.get_clock().now()
        self.detection_timeout = 2.0  # seconds
        
        # Logging throttle
        self.log_counter = 0
        self.log_frequency = 30  # Log every 30th detection (approx 1Hz at 30fps)
        
        self.get_logger().info('Golf Ball Follower initialized')
        self.get_logger().info(f'Target center: ({self.center_x}, {self.center_y})')
        self.get_logger().info(f'Linear speed: {self.linear_speed} m/s, Angular speed: {self.angular_speed} rad/s')
    
    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            
            # Detect golf balls (white objects)
            detection = self.detect_golf_ball(cv_image)
            
            if detection:
                ball_x, ball_y, ball_area = detection
                self.last_detection_time = self.get_clock().now()
                
                # Generate movement command
                twist = self.generate_movement_command(ball_x, ball_y, ball_area)
                self.cmd_vel_pub.publish(twist)
                
                # Throttled logging
                self.log_counter += 1
                if self.log_counter % self.log_frequency == 0:
                    self.get_logger().info(f'Following ball at ({ball_x}, {ball_y}) area={ball_area}')
            else:
                # Check for detection timeout
                current_time = self.get_clock().now()
                time_since_detection = (current_time - self.last_detection_time).nanoseconds / 1e9
                
                if time_since_detection > self.detection_timeout:
                    # Stop robot if no detection for too long
                    twist = Twist()
                    self.cmd_vel_pub.publish(twist)
                    # Only warn once per second about no detection
                    if int(time_since_detection) > int(time_since_detection - 0.033):  # Roughly once per second
                        self.get_logger().warn(f'No ball detected for {time_since_detection:.1f}s - stopping')
                
        except Exception as e:
            self.get_logger().error(f'Image processing error: {e}')
    
    def detect_golf_ball(self, image):
        """
        Detect green golf balls using HSV color filtering
        Returns: (center_x, center_y, area) or None if no detection
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Green color range in HSV (very permissive for any green)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        # Create mask
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Apply morphological operations to clean up
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find largest contour (assuming it's the golf ball)
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        # Check minimum area threshold
        if area < self.min_area:
            return None
        
        # Calculate center
        M = cv2.moments(largest_contour)
        if M['m00'] != 0:
            center_x = int(M['m10'] / M['m00'])
            center_y = int(M['m01'] / M['m00'])
            return (center_x, center_y, area)
        
        return None
    
    def generate_movement_command(self, ball_x, ball_y, ball_area):
        """
        Generate Twist command based on ball position and size
        """
        twist = Twist()
        
        # Calculate horizontal error (for angular velocity)
        x_error = ball_x - self.center_x
        
        # Calculate distance error (for linear velocity)
        area_error = ball_area - self.target_area
        
        # Angular velocity - turn toward ball
        if abs(x_error) > self.center_tolerance:
            # Proportional control for turning
            angular_vel = -float(x_error) / self.center_x * self.angular_speed
            # Clamp to maximum
            angular_vel = max(-self.max_angular_speed, min(self.max_angular_speed, angular_vel))
            twist.angular.z = angular_vel
        else:
            twist.angular.z = 0.0
        
        # Linear velocity - approach or back away from ball
        if ball_area > self.max_area:
            # Too close - back away
            twist.linear.x = -self.linear_speed * 0.5
            # Only log state changes
            if hasattr(self, '_last_state') and self._last_state != 'too_close':
                self.get_logger().info('Too close - backing away')
                self._last_state = 'too_close'
        elif ball_area < (self.target_area - self.area_tolerance):
            # Too far - approach
            # Reduce speed when turning
            speed_factor = 1.0 - abs(twist.angular.z) / self.max_angular_speed * 0.5
            twist.linear.x = self.linear_speed * speed_factor
            if hasattr(self, '_last_state') and self._last_state != 'approaching':
                self.get_logger().info('Approaching ball')
                self._last_state = 'approaching'
        else:
            # At good distance - just rotate to center
            twist.linear.x = 0.0
            if hasattr(self, '_last_state') and self._last_state != 'optimal':
                self.get_logger().info('At optimal distance - centering')
                self._last_state = 'optimal'
        
        # Clamp linear velocity
        twist.linear.x = max(-self.max_linear_speed, min(self.max_linear_speed, twist.linear.x))
        
        return twist

def main():
    rclpy.init()
    
    follower = GolfBallFollower()
    
    try:
        rclpy.spin(follower)
    except KeyboardInterrupt:
        pass
    finally:
        # Send stop command
        twist = Twist()
        follower.cmd_vel_pub.publish(twist)
        follower.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
