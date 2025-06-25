#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
import time

class TestDirectThenNav2(Node):
    """
    Test direct control first, then try Nav2.
    This helps debug if the issue is with movement or Nav2.
    """
    
    def __init__(self):
        super().__init__('test_direct_then_nav2')
        
        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Nav2 action client (will test later)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # State
        self.phase = 0
        self.nav2_available = False
        
        # Timer for test sequence
        self.timer = self.create_timer(2.0, self.timer_callback)
        
        self.get_logger().info('Test Direct Then Nav2 initialized')
        self.get_logger().info('Phase 1: Testing direct cmd_vel control...')
    
    def timer_callback(self):
        if self.phase == 0:
            # Test forward movement
            cmd = Twist()
            cmd.linear.x = 0.2
            self.cmd_pub.publish(cmd)
            self.get_logger().info('Sending forward command (0.2 m/s)...')
            self.phase = 1
            
        elif self.phase == 1:
            # Stop
            cmd = Twist()
            self.cmd_pub.publish(cmd)
            self.get_logger().info('Stopping...')
            self.phase = 2
            
        elif self.phase == 2:
            # Test rotation
            cmd = Twist()
            cmd.angular.z = 0.5
            self.cmd_pub.publish(cmd)
            self.get_logger().info('Rotating (0.5 rad/s)...')
            self.phase = 3
            
        elif self.phase == 3:
            # Stop
            cmd = Twist()
            self.cmd_pub.publish(cmd)
            self.get_logger().info('Stopping...')
            self.get_logger().info('Direct control test complete!')
            self.get_logger().info('If robot moved, basic control is working.')
            
            # Check Nav2
            self.get_logger().info('\nPhase 2: Checking Nav2 availability...')
            if self.nav_client.wait_for_server(timeout_sec=2.0):
                self.nav2_available = True
                self.get_logger().info('Nav2 is available! Sending test goal...')
                self.phase = 4
            else:
                self.get_logger().warn('Nav2 not available. Need to launch Nav2 stack.')
                self.get_logger().info('Try: ros2 launch nav2_bringup navigation_launch.py')
                self.timer.cancel()
                
        elif self.phase == 4 and self.nav2_available:
            # Send simple Nav2 goal
            goal = PoseStamped()
            goal.header.frame_id = 'odom'
            goal.header.stamp = self.get_clock().now().to_msg()
            
            # Simple forward goal
            goal.pose.position.x = 0.5
            goal.pose.position.y = 0.0
            goal.pose.orientation.w = 1.0
            
            self.send_nav_goal(goal)
            self.timer.cancel()
    
    def send_nav_goal(self, pose):
        """Send navigation goal to Nav2."""
        self.get_logger().info(f'Sending Nav2 goal to ({pose.pose.position.x:.2f}, '
                              f'{pose.pose.position.y:.2f})')
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = pose
        
        future = self.nav_client.send_goal_async(goal_msg)
        future.add_done_callback(self.goal_response_callback)
    
    def goal_response_callback(self, future):
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected by Nav2!')
        else:
            self.get_logger().info('Goal accepted by Nav2! Robot should navigate.')


def main(args=None):
    rclpy.init(args=args)
    
    test_node = TestDirectThenNav2()
    
    try:
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    finally:
        test_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
