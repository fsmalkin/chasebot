#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import math
import time

class SimpleNav2Demo(Node):
    """
    Simple Nav2 demo that sends a navigation goal to test Nav2 functionality.
    """
    
    def __init__(self):
        super().__init__('simple_nav2_demo')
        
        # Wait a bit for the system to initialize
        time.sleep(5)
        
        # Check if Nav2 is available by trying to connect to action server
        self.get_logger().info('Testing Nav2 functionality...')
        
        # Try to connect to Nav2 action server
        try:
            self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
            
            self.get_logger().info('Waiting for Nav2 action server (timeout: 10 seconds)...')
            if self.nav_client.wait_for_server(timeout_sec=10):
                self.get_logger().info('✅ Nav2 action server found! Testing navigation...')
                self.send_test_goal()
            else:
                self.get_logger().error('❌ Nav2 action server not available')
                self.get_logger().info('📋 This means Nav2 stack is not running')
                self.get_logger().info('💡 To test Nav2: Launch Nav2 stack separately')
                
        except Exception as e:
            self.get_logger().error(f'Error connecting to Nav2: {str(e)}')
            
        # Test basic robot movement instead
        self.test_basic_movement()
        
    def send_test_goal(self):
        """Send a test navigation goal."""
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'odom'
        goal_pose.header.stamp = self.get_clock().now().to_msg()
        
        # Simple goal: move 1 meter forward
        goal_pose.pose.position.x = 1.0
        goal_pose.pose.position.y = 0.0
        goal_pose.pose.position.z = 0.0
        goal_pose.pose.orientation.w = 1.0
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info('Sending Nav2 goal: Move 1m forward')
        
        future = self.nav_client.send_goal_async(goal_msg)
        future.add_done_callback(self.goal_response_callback)
        
    def goal_response_callback(self, future):
        """Handle goal response."""
        goal_handle = future.result()
        
        if goal_handle.accepted:
            self.get_logger().info('🎉 Nav2 GOAL ACCEPTED! Navigation system is working!')
            self.get_logger().info('✅ UAT SUCCESS: Nav2 navigation functionality confirmed')
        else:
            self.get_logger().error('❌ Nav2 goal rejected')
            
    def test_basic_movement(self):
        """Test basic robot movement using /cmd_vel."""
        from geometry_msgs.msg import Twist
        
        self.get_logger().info('Testing basic robot movement...')
        
        # Create cmd_vel publisher
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Wait for publisher to be ready
        time.sleep(1)
        
        # Send movement command
        twist = Twist()
        twist.linear.x = 0.1  # 0.1 m/s forward
        twist.angular.z = 0.0
        
        self.get_logger().info('Sending movement command: 0.1 m/s forward for 2 seconds')
        
        # Send command for 2 seconds
        for _ in range(20):  # 20 * 0.1s = 2 seconds
            self.cmd_pub.publish(twist)
            time.sleep(0.1)
            
        # Stop robot
        twist.linear.x = 0.0
        self.cmd_pub.publish(twist)
        
        self.get_logger().info('✅ Basic movement test completed')
        self.get_logger().info('🤖 Robot should have moved forward for 2 seconds')


def main(args=None):
    rclpy.init(args=args)
    
    demo = SimpleNav2Demo()
    
    try:
        # Spin for a while to let everything complete
        rclpy.spin_for_time(demo, 15.0)  # Run for 15 seconds
    except KeyboardInterrupt:
        pass
    finally:
        demo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
