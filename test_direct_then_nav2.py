#!/usr/bin/env python3
"""
Test script that first moves the robot with direct cmd_vel, 
then attempts a Nav2 goal to verify both systems work.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import LaserScan
import time
import math

class DirectThenNav2Test(Node):
    def __init__(self):
        super().__init__('direct_then_nav2_test')
        
        # Publishers and subscribers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # State tracking
        self.scan_received = False
        self.phase = "starting"
        
        # Start test sequence
        self.create_timer(1.0, self.test_sequence)
        
    def scan_callback(self, msg):
        """Track if we're receiving laser scans."""
        if not self.scan_received:
            self.scan_received = True
            valid_ranges = sum(1 for r in msg.ranges if not math.isinf(r))
            self.get_logger().info(f'✅ Laser scan received! {valid_ranges} valid points out of {len(msg.ranges)}')
    
    def test_sequence(self):
        """Execute test sequence."""
        if self.phase == "starting":
            self.get_logger().info('=== STARTING NAV2 INTEGRATION TEST ===')
            self.phase = "check_scan"
            
        elif self.phase == "check_scan":
            if self.scan_received:
                self.get_logger().info('✅ Vision-to-laserscan working')
                self.phase = "test_direct_control"
            else:
                self.get_logger().info('⏳ Waiting for laser scan data...')
                
        elif self.phase == "test_direct_control":
            self.get_logger().info('📍 Testing direct cmd_vel control (forward 0.1 m/s for 2 seconds)...')
            
            # Send forward command
            twist = Twist()
            twist.linear.x = 0.1
            twist.angular.z = 0.0
            self.cmd_vel_pub.publish(twist)
            
            # Schedule stop
            self.create_timer(2.0, self.stop_direct_movement, run_once=True)
            self.phase = "waiting_direct"
            
        elif self.phase == "check_nav2":
            self.get_logger().info('🔍 Checking Nav2 availability...')
            
            if self.nav_client.wait_for_server(timeout_sec=5.0):
                self.get_logger().info('✅ Nav2 action server is ready!')
                self.phase = "test_nav2_goal"
            else:
                self.get_logger().error('❌ Nav2 action server not available!')
                self.phase = "done"
                
        elif self.phase == "test_nav2_goal":
            self.get_logger().info('🎯 Sending Nav2 goal (1 meter forward)...')
            self.send_nav2_goal()
            self.phase = "waiting_nav2"
            
        elif self.phase == "done":
            self.get_logger().info('=== TEST COMPLETE ===')
            # Keep spinning to see results
            
    def stop_direct_movement(self):
        """Stop direct movement and move to Nav2 test."""
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        self.cmd_vel_pub.publish(twist)
        
        self.get_logger().info('✅ Direct control test complete')
        time.sleep(1.0)
        self.phase = "check_nav2"
        
    def send_nav2_goal(self):
        """Send a simple Nav2 goal."""
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = self.get_clock().now().to_msg()
        
        # Goal: 1 meter forward from current position
        goal.pose.position.x = 1.0
        goal.pose.position.y = 0.0
        goal.pose.position.z = 0.0
        
        # No rotation
        goal.pose.orientation.w = 1.0
        
        # Create and send goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal
        
        self.future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.nav2_feedback_callback
        )
        
        self.future.add_done_callback(self.nav2_goal_response_callback)
        
    def nav2_goal_response_callback(self, future):
        """Handle Nav2 goal response."""
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error('❌ Nav2 goal REJECTED!')
            self.get_logger().info('Check Nav2 logs for rejection reason')
        else:
            self.get_logger().info('✅ Nav2 goal ACCEPTED!')
            self.get_logger().info('🚀 Robot navigating with professional path planning!')
            
            # Get result
            self.result_future = goal_handle.get_result_async()
            self.result_future.add_done_callback(self.nav2_result_callback)
            
        self.phase = "done"
        
    def nav2_result_callback(self, future):
        """Handle navigation result."""
        result = future.result().result
        status = future.result().status
        
        if status == 4:  # SUCCEEDED
            self.get_logger().info('🎉 Nav2 Navigation SUCCEEDED!')
        else:
            self.get_logger().info(f'Nav2 Navigation finished with status: {status}')
            
    def nav2_feedback_callback(self, feedback_msg):
        """Handle Nav2 feedback."""
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        
        self.get_logger().info(f'📍 Nav2 position: ({current_pose.position.x:.2f}, {current_pose.position.y:.2f})')


def main(args=None):
    rclpy.init(args=args)
    
    test_node = DirectThenNav2Test()
    
    try:
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    finally:
        test_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
