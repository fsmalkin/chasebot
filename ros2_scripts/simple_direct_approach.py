#!/usr/bin/env python3
"""
Simple Direct Approach - Fallback Solution
Uses YOLO detections directly without complex coordinate transformations
Assumes ball is roughly at a fixed distance when detected
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Point, PoseStamped
from std_msgs.msg import Float32
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import math

class SimpleDirectApproach(Node):
    def __init__(self):
        super().__init__('simple_direct_approach')
        
        # Action client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Robot state
        self.robot_pose = None
        
        # Detection state
        self.ball_position = None
        self.confidence = 0.0
        
        # Parameters - SIMPLIFIED APPROACH
        self.assumed_ball_distance = 1.0  # Assume ball is 1m away when detected
        self.approach_distance = 0.15  # Stop 15cm from ball
        self.min_confidence = 0.6
        self.detection_cooldown = 3.0
        self.camera_fov_horizontal = 60.0  # degrees
        
        # State tracking
        self.last_navigation_time = 0.0
        self.navigating = False
        
        # Subscriptions
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        
        self.ball_pos_sub = self.create_subscription(
            Point, '/yolo/ball_position', self.ball_position_callback, 10)
        
        self.confidence_sub = self.create_subscription(
            Float32, '/yolo/confidence', self.confidence_callback, 10)
        
        # Wait for Nav2
        self.get_logger().info("Waiting for Nav2 action server...")
        self.nav_client.wait_for_server()
        
        self.get_logger().info("="*60)
        self.get_logger().info("SIMPLE DIRECT APPROACH - Fallback Solution")
        self.get_logger().info("="*60)
        self.get_logger().info(f"Assumed ball distance: {self.assumed_ball_distance}m")
        self.get_logger().info(f"Approach distance: {self.approach_distance}m")
        self.get_logger().info(f"Camera FOV: {self.camera_fov_horizontal}°")
        self.get_logger().info("Using simplified navigation without coordinate transforms")
        self.get_logger().info("="*60)

    def odom_callback(self, msg):
        """Update robot pose from odometry"""
        self.robot_pose = msg.pose.pose

    def ball_position_callback(self, msg):
        """Update ball position (normalized)"""
        self.ball_position = msg
        self.process_detection()

    def confidence_callback(self, msg):
        """Update detection confidence"""
        self.confidence = msg.data
        self.process_detection()

    def process_detection(self):
        """Process ball detection with simplified approach"""
        if not self.should_navigate():
            return
        
        # Calculate ball position using simplified approach
        ball_world_pos = self.calculate_simple_ball_position()
        if ball_world_pos is None:
            return
        
        # Calculate approach goal
        goal_pose = self.calculate_approach_goal(ball_world_pos)
        if goal_pose is None:
            return
        
        # Send navigation goal
        self.send_navigation_goal(goal_pose)

    def should_navigate(self):
        """Check if we should send a new navigation goal"""
        if self.robot_pose is None:
            self.get_logger().warn("No robot pose available")
            return False
        
        if self.ball_position is None or self.confidence == 0.0:
            return False
        
        if self.confidence < self.min_confidence:
            return False
        
        # Check cooldown
        current_time = self.get_clock().now().nanoseconds / 1e9
        if current_time - self.last_navigation_time < self.detection_cooldown:
            return False
        
        if self.navigating:
            return False
        
        return True

    def calculate_simple_ball_position(self):
        """Calculate ball position using simplified assumptions"""
        # Get robot position and orientation
        robot_x = self.robot_pose.position.x
        robot_y = self.robot_pose.position.y
        
        # Calculate robot yaw from quaternion
        q = self.robot_pose.orientation
        robot_yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 
                               1 - 2 * (q.y * q.y + q.z * q.z))
        
        # Calculate angle to ball based on normalized X position
        # ball_position.x: 0 = left edge, 0.5 = center, 1 = right edge
        normalized_x = self.ball_position.x - 0.5  # Center is 0
        angle_to_ball = normalized_x * math.radians(self.camera_fov_horizontal)
        
        # Calculate ball position relative to robot
        ball_angle = robot_yaw + angle_to_ball
        ball_x = robot_x + self.assumed_ball_distance * math.cos(ball_angle)
        ball_y = robot_y + self.assumed_ball_distance * math.sin(ball_angle)
        
        self.get_logger().info("="*60)
        self.get_logger().info("SIMPLE BALL POSITION CALCULATION:")
        self.get_logger().info(f"  Robot position: ({robot_x:.2f}, {robot_y:.2f})")
        self.get_logger().info(f"  Robot yaw: {math.degrees(robot_yaw):.1f}°")
        self.get_logger().info(f"  Ball normalized X: {self.ball_position.x:.3f}")
        self.get_logger().info(f"  Angle offset from center: {math.degrees(angle_to_ball):.1f}°")
        self.get_logger().info(f"  Assumed distance: {self.assumed_ball_distance}m")
        self.get_logger().info(f"  Ball world position: ({ball_x:.2f}, {ball_y:.2f})")
        self.get_logger().info("="*60)
        
        return (ball_x, ball_y)

    def calculate_approach_goal(self, ball_pos):
        """Calculate approach goal position"""
        ball_x, ball_y = ball_pos
        robot_x = self.robot_pose.position.x
        robot_y = self.robot_pose.position.y
        
        # Calculate distance to ball
        dx = ball_x - robot_x
        dy = ball_y - robot_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance <= self.approach_distance:
            self.get_logger().info("Already within approach distance")
            return None
        
        # Calculate approach point
        scale = (distance - self.approach_distance) / distance
        approach_x = robot_x + dx * scale
        approach_y = robot_y + dy * scale
        
        # Create goal pose
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = self.get_clock().now().to_msg()
        
        goal.pose.position.x = approach_x
        goal.pose.position.y = approach_y
        goal.pose.position.z = 0.0
        
        # Orient towards the ball
        yaw = math.atan2(dy, dx)
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        
        self.get_logger().info(f"Approach goal: ({approach_x:.2f}, {approach_y:.2f})")
        
        return goal

    def send_navigation_goal(self, goal_pose):
        """Send navigation goal to Nav2"""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info("🚀 SENDING SIMPLE NAVIGATION GOAL!")
        
        # Send goal
        future = self.nav_client.send_goal_async(goal_msg)
        future.add_done_callback(self.goal_response_callback)
        
        # Update state
        self.navigating = True
        self.last_navigation_time = self.get_clock().now().nanoseconds / 1e9

    def goal_response_callback(self, future):
        """Handle goal response from Nav2"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Navigation goal rejected!')
            self.navigating = False
            return
        
        self.get_logger().info('Navigation goal accepted')
        
        # Wait for result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_result_callback)

    def goal_result_callback(self, future):
        """Handle navigation result"""
        result = future.result().result
        self.navigating = False
        
        if result:
            self.get_logger().info("✅ Navigation completed!")
        else:
            self.get_logger().error("❌ Navigation failed!")

def main(args=None):
    rclpy.init(args=args)
    node = SimpleDirectApproach()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
