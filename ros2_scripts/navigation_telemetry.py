#!/usr/bin/env python3
"""
Navigation Telemetry - Real-time monitoring of robot navigation state
Shows robot position, ball detection, navigation goals, and system status
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point, PoseStamped, Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32
from nav2_msgs.action import NavigateToPose
from sensor_msgs.msg import LaserScan
import math
from datetime import datetime

class NavigationTelemetry(Node):
    def __init__(self):
        super().__init__('navigation_telemetry')
        
        # Robot state
        self.robot_position = None
        self.robot_velocity = None
        
        # Ball detection state
        self.ball_pixel_position = None
        self.ball_confidence = 0.0
        self.last_detection_time = None
        
        # Navigation state
        self.current_nav_goal = None
        self.nav_status = "IDLE"
        self.last_goal_time = None
        
        # Subscriptions
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        
        self.ball_pos_sub = self.create_subscription(
            Point, '/yolo/ball_position', self.ball_position_callback, 10)
        
        self.confidence_sub = self.create_subscription(
            Float32, '/yolo/confidence', self.confidence_callback, 10)
        
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        
        self.goal_sub = self.create_subscription(
            PoseStamped, '/goal_pose', self.goal_callback, 10)
        
        # Create timer for telemetry display
        self.timer = self.create_timer(5.0, self.display_telemetry)
        
        self.get_logger().info("Navigation Telemetry Started - Updates every 5 seconds")
        self.get_logger().info("="*80)

    def odom_callback(self, msg):
        """Update robot position from odometry"""
        self.robot_position = msg.pose.pose.position
        self.robot_velocity = msg.twist.twist

    def ball_position_callback(self, msg):
        """Update ball detection position"""
        self.ball_pixel_position = msg
        self.last_detection_time = self.get_clock().now()

    def confidence_callback(self, msg):
        """Update detection confidence"""
        self.ball_confidence = msg.data

    def cmd_vel_callback(self, msg):
        """Monitor commanded velocities"""
        if abs(msg.linear.x) > 0.01 or abs(msg.angular.z) > 0.01:
            self.nav_status = "MOVING"
        else:
            if self.nav_status == "MOVING":
                self.nav_status = "STOPPED"

    def goal_callback(self, msg):
        """Track navigation goals"""
        self.current_nav_goal = msg.pose.position
        self.last_goal_time = self.get_clock().now()
        self.nav_status = "GOAL_RECEIVED"

    def display_telemetry(self):
        """Display comprehensive telemetry data"""
        print("\033[2J\033[H")  # Clear screen and move cursor to top
        print("╔" + "═"*78 + "╗")
        print("║" + " CHASEBOT NAVIGATION TELEMETRY ".center(78) + "║")
        print("║" + f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ".center(78) + "║")
        print("╠" + "═"*78 + "╣")
        
        # Robot State
        print("║ ROBOT STATE:".ljust(79) + "║")
        if self.robot_position:
            print(f"║   Position: X={self.robot_position.x:6.3f}m  Y={self.robot_position.y:6.3f}m  Z={self.robot_position.z:6.3f}m".ljust(79) + "║")
            if self.robot_velocity:
                print(f"║   Velocity: Linear={self.robot_velocity.linear.x:5.3f}m/s  Angular={self.robot_velocity.angular.z:5.3f}rad/s".ljust(79) + "║")
        else:
            print("║   Position: Not available".ljust(79) + "║")
        print("║" + " "*78 + "║")
        
        # Ball Detection
        print("║ BALL DETECTION:".ljust(79) + "║")
        if self.ball_pixel_position and self.ball_confidence > 0:
            print(f"║   Pixel Position: ({self.ball_pixel_position.x:.3f}, {self.ball_pixel_position.y:.3f}) normalized".ljust(79) + "║")
            print(f"║   Confidence: {self.ball_confidence:.1%}".ljust(79) + "║")
            
            if self.last_detection_time:
                age = (self.get_clock().now() - self.last_detection_time).nanoseconds / 1e9
                print(f"║   Detection Age: {age:.1f}s ago".ljust(79) + "║")
        else:
            print("║   No ball detected".ljust(79) + "║")
        print("║" + " "*78 + "║")
        
        # Navigation State
        print("║ NAVIGATION:".ljust(79) + "║")
        print(f"║   Status: {self.nav_status}".ljust(79) + "║")
        if self.current_nav_goal:
            print(f"║   Goal: X={self.current_nav_goal.x:6.3f}m  Y={self.current_nav_goal.y:6.3f}m".ljust(79) + "║")
            
            if self.robot_position:
                dx = self.current_nav_goal.x - self.robot_position.x
                dy = self.current_nav_goal.y - self.robot_position.y
                distance = math.sqrt(dx*dx + dy*dy)
                print(f"║   Distance to Goal: {distance:.3f}m".ljust(79) + "║")
            
            if self.last_goal_time:
                age = (self.get_clock().now() - self.last_goal_time).nanoseconds / 1e9
                print(f"║   Goal Age: {age:.1f}s".ljust(79) + "║")
        else:
            print("║   No active goal".ljust(79) + "║")
        
        print("╚" + "═"*78 + "╝")
        
        # Quick status indicators
        if self.ball_confidence > 0.6:
            print("🟢 Ball Detected", end="  ")
        else:
            print("🔴 No Ball", end="  ")
            
        if self.nav_status == "MOVING":
            print("🟢 Robot Moving", end="  ")
        elif self.nav_status == "GOAL_RECEIVED":
            print("🟡 Goal Received", end="  ")
        else:
            print("🔴 Robot Idle", end="  ")
        
        print()  # New line

def main(args=None):
    rclpy.init(args=args)
    node = NavigationTelemetry()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
