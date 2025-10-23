#!/usr/bin/env python3
"""
YOLO to Nav2 Goal Bridge - Version 3.0.0
Major changes:
- v3.0.0: Direct 3D position input from yolo_3d_position_extractor (uses depth camera)
- v2.0.0: Complete rewrite using camera intrinsics for proper coordinate conversion
- v1.2.0: Direct position calculation (incorrectly treated pixels as meters)
- v1.1.0: Used transforms with hardcoded distance estimation
- v1.0.0: Initial implementation
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PointStamped, PoseStamped
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformListener
import tf2_geometry_msgs
import math
import numpy as np
import time

class YoloToNavGoalV3(Node):
    def __init__(self):
        super().__init__('yolo_to_nav_goal_v3')
        
        # Action client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 3D ball position subscription
        self.ball_position_3d_sub = self.create_subscription(
            PointStamped,
            '/yolo/ball_position_3d',
            self.ball_position_3d_callback,
            10
        )
        
        # Parameters
        self.declare_parameter('approach_distance', 0.15)  # 15cm approach distance
        self.declare_parameter('cooldown_time', 5.0)  # Seconds between goals
        self.declare_parameter('min_detection_distance', 0.3)  # Minimum distance to trigger navigation
        self.declare_parameter('max_detection_distance', 3.0)  # Maximum distance to consider ball
        
        self.approach_distance = self.get_parameter('approach_distance').value
        self.cooldown_time = self.get_parameter('cooldown_time').value
        self.min_detection_distance = self.get_parameter('min_detection_distance').value
        self.max_detection_distance = self.get_parameter('max_detection_distance').value
        
        # State tracking
        self.last_goal_time = 0
        self.goal_in_progress = False
        
        # Wait for Nav2
        self.get_logger().info("Waiting for Nav2 action server...")
        self.nav_client.wait_for_server()
        self.get_logger().info("Nav2 action server ready!")
        
        self.get_logger().info("🤖 YOLO to Nav Goal Bridge v3.0.0 initialized")
        self.get_logger().info("📍 Using direct 3D positions from depth camera")
        self.get_logger().info(f"📏 Approach distance: {self.approach_distance}m")
        self.get_logger().info(f"⏱️  Cooldown time: {self.cooldown_time}s")

    def ball_position_3d_callback(self, msg):
        """Handle incoming 3D ball position"""
        # Check cooldown
        current_time = time.time()
        if self.goal_in_progress:
            return  # Already navigating
            
        if (current_time - self.last_goal_time) < self.cooldown_time:
            return  # Still in cooldown
        
        # Extract 3D position (already in camera frame coordinates)
        ball_x = msg.point.x
        ball_y = msg.point.y
        ball_z = msg.point.z
        
        self.get_logger().info(f"🎾 Ball detected at: [{ball_x:.3f}, {ball_y:.3f}, {ball_z:.3f}]m")
        
        # Process the detection
        self.process_3d_detection(ball_x, ball_y, ball_z)

    def process_3d_detection(self, ball_x, ball_y, ball_z):
        """Process 3D ball detection and send navigation goal"""
        # Calculate distance to ball (in camera frame)
        # For JetBot camera: X-right, Y-down, Z-forward
        # So horizontal distance is sqrt(x^2 + z^2) since z is forward
        distance_to_ball = math.sqrt(ball_x**2 + ball_z**2)
        
        self.get_logger().info(f"📏 Distance to ball: {distance_to_ball:.3f}m")
        
        # Check if ball is within valid range
        if distance_to_ball < self.min_detection_distance:
            self.get_logger().info(f"⚠️ Ball too close: {distance_to_ball:.3f}m < {self.min_detection_distance}m")
            return
            
        if distance_to_ball > self.max_detection_distance:
            self.get_logger().warn(f"⚠️ Ball too far: {distance_to_ball:.3f}m > {self.max_detection_distance}m")
            return
        
        # Check if already within approach distance
        if distance_to_ball <= self.approach_distance:
            self.get_logger().info(f"✅ Already within approach distance ({distance_to_ball:.3f}m)")
            return
        
        # Calculate approach goal in camera frame
        # We want to stop approach_distance before the ball
        scale = (distance_to_ball - self.approach_distance) / distance_to_ball
        goal_x = ball_x * scale
        goal_z = ball_z * scale  # z is forward in camera frame
        
        # Convert to base_link frame
        # For JetBot: camera is mounted on top, facing forward
        # Assuming camera frame aligned with base_link (x-forward, y-left)
        # Camera: X-right, Y-down, Z-forward
        # Base: X-forward, Y-left, Z-up
        goal_base_x = goal_z  # Camera Z -> Base X (forward)
        goal_base_y = -goal_x  # Camera -X -> Base Y (left)
        
        # Create goal pose
        goal = PoseStamped()
        goal.header.frame_id = 'base_link'  # Goals relative to robot
        goal.header.stamp = self.get_clock().now().to_msg()
        
        goal.pose.position.x = goal_base_x
        goal.pose.position.y = goal_base_y
        goal.pose.position.z = 0.0
        
        # Orient towards the ball
        yaw = math.atan2(goal_base_y, goal_base_x)
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        
        self.get_logger().info(f"🎯 Approach goal in base_link: ({goal_base_x:.3f}, {goal_base_y:.3f})")
        self.get_logger().info(f"📐 Will stop {self.approach_distance:.3f}m from ball")
        
        # Send navigation goal
        self.send_navigation_goal(goal)
        

    def send_navigation_goal(self, goal_pose):
        """Send navigation goal to Nav2"""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info("="*60)
        self.get_logger().info(f"🚀 SENDING NAVIGATION GOAL!")
        self.get_logger().info(f"📍 Target: ({goal_pose.pose.position.x:.3f}, {goal_pose.pose.position.y:.3f})")
        self.get_logger().info("="*60)
        
        # Send goal asynchronously
        self.goal_in_progress = True
        self.last_goal_time = time.time()
        
        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        """Handle goal response from Nav2"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Navigation goal rejected!')
            self.goal_in_progress = False
            return
        
        self.get_logger().info('Navigation goal accepted, robot moving...')
        
        # Wait for result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_result_callback)

    def goal_result_callback(self, future):
        """Handle navigation result"""
        result = future.result().result
        self.goal_in_progress = False
        
        if result:
            self.get_logger().info("✅ Navigation completed! Robot should be near the ball.")
        else:
            self.get_logger().error("❌ Navigation failed!")

def main(args=None):
    rclpy.init(args=args)
    
    node = YoloToNavGoalV3()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
