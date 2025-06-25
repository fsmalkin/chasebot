#!/usr/bin/env python3
"""
Direct test of Nav2 goal sending.
Tests if Nav2 will accept navigation goals after all fixes.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import time

class TestNav2Goal(Node):
    def __init__(self):
        super().__init__('test_nav2_goal')
        
        self.get_logger().info('=== NAV2 GOAL ACCEPTANCE TEST ===')
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Wait for Nav2
        self.get_logger().info('Waiting for Nav2 action server...')
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('❌ Nav2 action server NOT available!')
            self.get_logger().info('Make sure Nav2 is running with: ros2 launch nav2_bringup navigation_launch.py')
            return
            
        self.get_logger().info('✅ Nav2 action server is READY!')
        
        # Send test goal
        time.sleep(2.0)
        self.send_test_goal()
        
    def send_test_goal(self):
        """Send a test navigation goal."""
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = self.get_clock().now().to_msg()
        
        # Simple goal: 0.5 meters forward
        goal.pose.position.x = 0.5
        goal.pose.position.y = 0.0
        goal.pose.position.z = 0.0
        
        # No rotation
        goal.pose.orientation.x = 0.0
        goal.pose.orientation.y = 0.0
        goal.pose.orientation.z = 0.0
        goal.pose.orientation.w = 1.0
        
        self.get_logger().info('📍 Sending Nav2 goal to (0.5, 0.0)...')
        
        # Create goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal
        
        # Send goal
        self.future = self.nav_client.send_goal_async(goal_msg)
        self.future.add_done_callback(self.goal_response_callback)
        
    def goal_response_callback(self, future):
        """Handle goal response."""
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error('❌ FAIL: Nav2 goal REJECTED!')
            self.get_logger().info('This indicates Nav2 configuration issues remain.')
        else:
            self.get_logger().info('✅ SUCCESS: Nav2 goal ACCEPTED!')
            self.get_logger().info('🎉 Nav2 integration is working correctly!')
            self.get_logger().info('The robot would now navigate using professional path planning.')
            
        # Shutdown after test
        self.get_logger().info('=== TEST COMPLETE ===')
        time.sleep(2.0)
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    
    test_node = TestNav2Goal()
    
    try:
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        test_node.get_logger().error(f'Error: {str(e)}')
    finally:
        if rclpy.ok():
            test_node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
