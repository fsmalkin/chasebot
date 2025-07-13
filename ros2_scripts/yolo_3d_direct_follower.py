#!/usr/bin/env python3
"""
YOLO 3D Direct Follower Node
Subscribes to 3D ball positions and directly controls the robot (bypasses Nav2)
Uses simple proportional control to approach detected balls
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped, TwistStamped
from std_msgs.msg import Header
import time
import math


class Yolo3DDirectFollower(Node):
    def __init__(self):
        super().__init__('yolo_3d_direct_follower')
        
        # Parameters
        self.declare_parameter('approach_distance', 0.15)  # 15cm approach distance
        self.declare_parameter('max_linear_speed', 0.2)   # 0.2 m/s max forward speed
        self.declare_parameter('max_angular_speed', 0.5)  # 0.5 rad/s max rotation
        self.declare_parameter('linear_gain', 0.5)        # Proportional gain for linear
        self.declare_parameter('angular_gain', 2.0)       # Proportional gain for angular
        self.declare_parameter('stop_threshold', 0.02)    # 2cm position error to stop
        
        self.approach_distance = self.get_parameter('approach_distance').value
        self.max_linear_speed = self.get_parameter('max_linear_speed').value
        self.max_angular_speed = self.get_parameter('max_angular_speed').value
        self.linear_gain = self.get_parameter('linear_gain').value
        self.angular_gain = self.get_parameter('angular_gain').value
        self.stop_threshold = self.get_parameter('stop_threshold').value
        
        # State tracking
        self.last_detection_time = 0
        self.detection_timeout = 2.0  # Stop if no detection for 2 seconds
        self.is_following = False
        
        # Publisher for robot control
        self.cmd_vel_pub = self.create_publisher(
            TwistStamped,
            '/jetbot_base_controller/cmd_vel',
            10
        )
        
        # Subscribe to 3D ball positions
        self.position_sub = self.create_subscription(
            PointStamped,
            '/yolo/ball_position_3d',
            self.position_callback,
            10
        )
        
        # Create timer for control loop (10 Hz)
        self.control_timer = self.create_timer(0.1, self.control_loop)
        
        self.get_logger().info('🤖 YOLO 3D Direct Follower Started (No Nav2!)')
        self.get_logger().info(f'📏 Approach distance: {self.approach_distance}m')
        self.get_logger().info(f'🚀 Max speeds: {self.max_linear_speed}m/s linear, {self.max_angular_speed}rad/s angular')
        self.get_logger().info(f'🎯 Control gains: {self.linear_gain} linear, {self.angular_gain} angular')
        self.get_logger().info('🎾 Waiting for ball detections...')
    
    def position_callback(self, msg):
        """Handle incoming 3D ball position."""
        # Update detection time
        self.last_detection_time = time.time()
        
        # Extract position
        self.ball_x = msg.point.x
        self.ball_y = msg.point.y
        self.ball_z = msg.point.z
        
        # Calculate distance
        self.distance_to_ball = math.sqrt(self.ball_x**2 + self.ball_y**2)
        
        # Log detection
        self.get_logger().info(
            f'🎾 Ball at: [{self.ball_x:.3f}, {self.ball_y:.3f}, {self.ball_z:.3f}]m, '
            f'Distance: {self.distance_to_ball:.3f}m'
        )
        
        # Start following if not already
        if not self.is_following:
            self.is_following = True
            self.get_logger().info('🏃 Starting to follow ball!')
    
    def control_loop(self):
        """Control loop that runs at 10Hz to send velocity commands."""
        current_time = time.time()
        
        # Check if we have a recent detection
        if (current_time - self.last_detection_time) > self.detection_timeout:
            if self.is_following:
                self.is_following = False
                self.stop_robot()
                self.get_logger().info('⏹️  No detection for 2s, stopping robot')
            return
        
        # Only control if we're following
        if not self.is_following:
            return
        
        # Check if we have ball position
        if not hasattr(self, 'ball_x'):
            return
        
        # Check if we're close enough
        if self.distance_to_ball < self.approach_distance:
            if abs(self.distance_to_ball - self.approach_distance) < self.stop_threshold:
                self.stop_robot()
                self.get_logger().info(f'✅ Reached approach distance! Stopping at {self.distance_to_ball:.3f}m')
                self.is_following = False
                return
        
        # Calculate control commands using proportional control
        # Linear velocity: proportional to distance error
        distance_error = self.distance_to_ball - self.approach_distance
        linear_vel = self.linear_gain * distance_error
        
        # Angular velocity: proportional to angle error
        angle_to_ball = math.atan2(self.ball_y, self.ball_x)
        angular_vel = self.angular_gain * angle_to_ball
        
        # Clamp velocities to max values
        linear_vel = max(-self.max_linear_speed, min(self.max_linear_speed, linear_vel))
        angular_vel = max(-self.max_angular_speed, min(self.max_angular_speed, angular_vel))
        
        # Create and publish TwistStamped message
        cmd_vel = TwistStamped()
        cmd_vel.header.stamp = self.get_clock().now().to_msg()
        cmd_vel.header.frame_id = ''  # Empty frame_id as per working example
        cmd_vel.twist.linear.x = linear_vel
        cmd_vel.twist.angular.z = angular_vel
        
        self.cmd_vel_pub.publish(cmd_vel)
        
        # Log control state occasionally
        if not hasattr(self, '_last_log_time') or (current_time - self._last_log_time) > 1.0:
            self._last_log_time = current_time
            self.get_logger().info(
                f'🎮 Control: linear={linear_vel:.3f}m/s, angular={angular_vel:.3f}rad/s, '
                f'distance={self.distance_to_ball:.3f}m, angle={math.degrees(angle_to_ball):.1f}°'
            )
    
    def stop_robot(self):
        """Send zero velocity to stop the robot."""
        cmd_vel = TwistStamped()
        cmd_vel.header.stamp = self.get_clock().now().to_msg()
        cmd_vel.header.frame_id = ''
        cmd_vel.twist.linear.x = 0.0
        cmd_vel.twist.angular.z = 0.0
        self.cmd_vel_pub.publish(cmd_vel)


def main(args=None):
    rclpy.init(args=args)
    
    follower = Yolo3DDirectFollower()
    
    try:
        follower.get_logger().info('🚀 YOLO 3D Direct Follower running...')
        follower.get_logger().info('🎾 Waiting for ball detections...')
        rclpy.spin(follower)
    except KeyboardInterrupt:
        follower.get_logger().info('🛑 Shutting down follower...')
    finally:
        # Make sure to stop the robot before exiting
        follower.stop_robot()
        follower.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
