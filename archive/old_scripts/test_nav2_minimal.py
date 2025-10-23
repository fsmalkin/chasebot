#!/usr/bin/env python3
"""
Minimal Nav2 test script to verify goal acceptance.
Tests sending a simple navigation goal to Nav2.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import time

class Nav2MinimalTest(Node):
    def __init__(self):
        super().__init__('nav2_minimal_test')
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        self.get_logger().info('Waiting for Nav2 action server...')
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Nav2 action server not available!')
            return
            
        self.get_logger().info('Nav2 action server is ready!')
        
        # Wait a bit for everything to stabilize
        time.sleep(2.0)
        
        # Send a simple test goal
        self.send_test_goal()
        
    def send_test_goal(self):
        """Send a simple navigation goal 1 meter forward."""
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = self.get_clock().now().to_msg()
        
        # Simple goal: 1 meter forward from origin
        goal.pose.position.x = 1.0
        goal.pose.position.y = 0.0
        goal.pose.position.z = 0.0
        
        # Face forward (no rotation)
        goal.pose.orientation.x = 0.0
        goal.pose.orientation.y = 0.0
        goal.pose.orientation.z = 0.0
        goal.pose.orientation.w = 1.0
        
        self.get_logger().info(f'Sending test goal to (1.0, 0.0)')
        
        # Create goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal
        
        # Send goal
        self.future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        
        self.future.add_done_callback(self.goal_response_callback)
        
    def goal_response_callback(self, future):
        """Handle goal response."""
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error('❌ Goal REJECTED by Nav2!')
            self.get_logger().info('This means Nav2 configuration still needs adjustment.')
        else:
            self.get_logger().info('✅ Goal ACCEPTED by Nav2!')
            self.get_logger().info('Nav2 is working correctly!')
            
            # Get result
            self.result_future = goal_handle.get_result_async()
            self.result_future.add_done_callback(self.result_callback)
            
    def result_callback(self, future):
        """Handle navigation result."""
        result = future.result().result
        status = future.result().status
        
        if status == 4:  # SUCCEEDED
            self.get_logger().info('✅ Navigation SUCCEEDED!')
        else:
            self.get_logger().info(f'Navigation completed with status: {status}')
            
    def feedback_callback(self, feedback_msg):
        """Handle navigation feedback."""
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        
        self.get_logger().info(f'Robot at: ({current_pose.position.x:.2f}, {current_pose.position.y:.2f})')


def main(args=None):
    rclpy.init(args=args)
    
    test_node = Nav2MinimalTest()
    
    try:
        # Spin for a while to see results
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    finally:
        test_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
