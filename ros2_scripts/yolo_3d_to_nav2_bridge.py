#!/usr/bin/env python3
"""
YOLO 3D to Nav2 Bridge Node
Subscribes to 3D ball positions and sends Nav2 goals
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, PointStamped
from std_msgs.msg import Header
import time
import math


class Yolo3DToNav2Bridge(Node):
    def __init__(self):
        super().__init__('yolo_3d_to_nav2_bridge')
        
        # Parameters
        self.declare_parameter('approach_distance', 0.15)  # 15cm approach distance
        self.declare_parameter('confidence_threshold', 0.4)
        self.declare_parameter('goal_tolerance', 0.05)  # 5cm tolerance
        self.declare_parameter('cooldown_time', 5.0)  # Seconds between goals
        self.declare_parameter('action_server_wait_s', 30.0)
        self.declare_parameter('goal_frame', 'odom')
        
        self.approach_distance = self.get_parameter('approach_distance').value
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        self.goal_tolerance = self.get_parameter('goal_tolerance').value
        self.cooldown_time = self.get_parameter('cooldown_time').value
        self.action_server_wait_s = float(self.get_parameter('action_server_wait_s').value)
        self.goal_frame = str(self.get_parameter('goal_frame').value)
        
        # State tracking
        self.last_goal_time = 0
        self.current_goal_handle = None
        self.goal_in_progress = False
        self._last_server_warn_time = 0.0
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Subscribe to 3D ball positions
        self.position_sub = self.create_subscription(
            PointStamped,
            '/yolo/ball_position_3d',
            self.position_callback,
            10
        )
        
        self.get_logger().info('🤖 YOLO 3D to Nav2 Bridge Started')
        self.get_logger().info(f'📏 Approach distance: {self.approach_distance}m')
        self.get_logger().info(f'🎯 Goal tolerance: {self.goal_tolerance}m')
        self.get_logger().info(f'⏱️  Cooldown time: {self.cooldown_time}s')
        
        # Wait for Nav2
        self.get_logger().info('⏳ Waiting for Nav2 action server...')
        if self.nav_client.wait_for_server(timeout_sec=self.action_server_wait_s):
            self.get_logger().info('✅ Nav2 action server ready!')
        else:
            self.get_logger().error('❌ Nav2 action server not available!')
    
    def position_callback(self, msg):
        """Handle incoming 3D ball position."""
        if not rclpy.ok():
            return

        # Check if we should send a new goal
        current_time = time.time()
        if self.goal_in_progress:
            return  # Already navigating
            
        if (current_time - self.last_goal_time) < self.cooldown_time:
            return  # Still in cooldown

        try:
            if not self.nav_client.server_is_ready():
                if not self.nav_client.wait_for_server(timeout_sec=0.2):
                    if (current_time - self._last_server_warn_time) > 2.0:
                        self.get_logger().warn('Nav2 action server still unavailable; skipping this detection.')
                        self._last_server_warn_time = current_time
                    return
                self.get_logger().info('Nav2 action server became ready.')
        except Exception as exc:
            self.get_logger().warn(f'Action server check failed during shutdown/teardown: {exc}')
            return
        
        # Extract position
        ball_x = float(msg.point.z)    # forward range in camera frame
        ball_y = float(-msg.point.x)   # base_link +y (left) from camera +x (right)
        ball_z = float(msg.point.y)    # vertical component (unused for planning)
        
        self.get_logger().info(f'🎾 Ball detected at: [{ball_x:.3f}, {ball_y:.3f}, {ball_z:.3f}]m')
        
        # Calculate approach position (stop before the ball)
        # We approach from the robot's current position toward the ball
        # The ball position is relative to the camera/robot
        distance_to_ball = math.sqrt(ball_x**2 + ball_y**2)
        
        if distance_to_ball < self.approach_distance:
            self.get_logger().info(f'✅ Already within approach distance ({distance_to_ball:.3f}m)')
            return
        
        # Calculate unit vector toward ball
        unit_x = ball_x / distance_to_ball
        unit_y = ball_y / distance_to_ball
        
        # Calculate goal position (approach_distance before the ball)
        goal_distance = distance_to_ball - self.approach_distance
        goal_x = unit_x * goal_distance
        goal_y = unit_y * goal_distance
        
        self.get_logger().info(f'🎯 Calculated approach goal: [{goal_x:.3f}, {goal_y:.3f}]m')
        self.get_logger().info(f'📐 Distance to ball: {distance_to_ball:.3f}m, Goal distance: {goal_distance:.3f}m')
        
        # Send navigation goal
        self.send_nav_goal(goal_x, goal_y)
        self.last_goal_time = current_time
    
    def send_nav_goal(self, x, y):
        """Send a navigation goal to Nav2."""
        # Create goal pose
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = self.goal_frame
        goal_pose.header.stamp = self.get_clock().now().to_msg()
        
        goal_pose.pose.position.x = x
        goal_pose.pose.position.y = y
        goal_pose.pose.position.z = 0.0
        
        # Calculate orientation to face the ball
        yaw = math.atan2(y, x)
        goal_pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_pose.pose.orientation.w = math.cos(yaw / 2.0)
        
        # Create Nav2 goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        # Set behavior tree (optional)
        goal_msg.behavior_tree = ''
        
        self.get_logger().info(f'📍 Sending Nav2 goal: ({x:.2f}, {y:.2f}) in {goal_pose.header.frame_id} frame')
        
        # Send goal asynchronously
        self.goal_in_progress = True
        send_goal_future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)
    
    def goal_response_callback(self, future):
        """Handle goal response from Nav2."""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('❌ Goal rejected by Nav2!')
            self.goal_in_progress = False
            return
        
        self.get_logger().info('✅ Goal accepted by Nav2! Robot navigating...')
        self.current_goal_handle = goal_handle
        
        # Get result asynchronously
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.get_result_callback)
    
    def feedback_callback(self, feedback_msg):
        """Handle navigation feedback."""
        feedback = feedback_msg.feedback
        # Log progress occasionally
        current_pose = feedback.current_pose.pose
        distance_remaining = feedback.distance_remaining
        
        if hasattr(self, '_last_feedback_time'):
            if time.time() - self._last_feedback_time < 2.0:
                return
        
        self._last_feedback_time = time.time()
        self.get_logger().info(f'🏃 Navigation progress: {distance_remaining:.2f}m remaining')
    
    def get_result_callback(self, future):
        """Handle navigation result."""
        result = future.result().result
        status = future.result().status
        
        if status == 4:  # SUCCEEDED
            self.get_logger().info('🎉 Navigation goal reached successfully!')
            self.get_logger().info(f'✅ Robot is now within {self.approach_distance}m of the ball')
        elif status == 6:  # CANCELED
            self.get_logger().warn('⚠️  Navigation goal was canceled')
        else:
            self.get_logger().error(f'❌ Navigation failed with status: {status}')
        
        self.goal_in_progress = False
        self.current_goal_handle = None


def main(args=None):
    rclpy.init(args=args)
    
    bridge = Yolo3DToNav2Bridge()
    
    try:
        bridge.get_logger().info('🚀 YOLO 3D to Nav2 bridge running...')
        bridge.get_logger().info('🎾 Waiting for ball detections...')
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        bridge.get_logger().info('🛑 Shutting down bridge...')
    finally:
        bridge.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
