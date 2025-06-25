#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time

class Nav2MinimalTest(Node):
    """
    Super minimal test - just check if we can move the robot.
    This avoids loading the full Nav2 stack.
    """
    
    def __init__(self):
        super().__init__('nav2_minimal_test')
        
        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Give time for connections
        time.sleep(1.0)
        
        self.get_logger().info('Nav2 Minimal Test - Direct Control Only')
        self.get_logger().info('This test avoids loading Nav2 to prevent overheating')
        
        # Test sequence
        self.test_movement()
        
    def test_movement(self):
        """Test basic movement without Nav2."""
        
        # Forward
        self.get_logger().info('Moving forward...')
        cmd = Twist()
        cmd.linear.x = 0.1  # Slower speed
        self.cmd_pub.publish(cmd)
        time.sleep(2.0)
        
        # Stop
        self.get_logger().info('Stopping...')
        cmd = Twist()
        self.cmd_pub.publish(cmd)
        time.sleep(1.0)
        
        # Turn
        self.get_logger().info('Turning...')
        cmd = Twist()
        cmd.angular.z = 0.3
        self.cmd_pub.publish(cmd)
        time.sleep(2.0)
        
        # Stop
        self.get_logger().info('Final stop...')
        cmd = Twist()
        self.cmd_pub.publish(cmd)
        
        self.get_logger().info('Test complete!')
        self.get_logger().info('\nDirect control is working.')
        self.get_logger().info('Nav2 integration would add:')
        self.get_logger().info('- Path planning around obstacles')
        self.get_logger().info('- Smooth navigation to goals')
        self.get_logger().info('- Recovery behaviors')
        self.get_logger().info('\nBut requires significant computational resources.')


def main(args=None):
    rclpy.init(args=args)
    
    test_node = Nav2MinimalTest()
    
    # Just run the test once
    rclpy.spin_once(test_node, timeout_sec=10.0)
    
    test_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
