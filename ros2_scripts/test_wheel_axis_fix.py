#!/usr/bin/env python3
"""
Test script to demonstrate wheel axis fix in Ignition Gazebo
Shows that wheels now rotate correctly around Z-axis instead of Y-axis
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time

class WheelAxisTester(Node):
    def __init__(self):
        super().__init__('wheel_axis_tester')
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.get_logger().info('Wheel Axis Test Starting...')
        
    def test_forward_motion(self):
        """Test forward motion - wheels should roll forward"""
        msg = Twist()
        msg.linear.x = 0.2  # Forward velocity
        msg.angular.z = 0.0
        
        self.get_logger().info('Testing FORWARD motion - wheels should ROLL forward')
        self.get_logger().info('If wheels spin sideways like casters, the axis bug is NOT fixed')
        self.get_logger().info('If wheels roll forward/backward, the fix is WORKING')
        
        # Publish for 3 seconds
        start_time = time.time()
        while time.time() - start_time < 3.0:
            self.publisher.publish(msg)
            time.sleep(0.1)
            
    def test_rotation(self):
        """Test rotation - differential drive"""
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.5  # Rotate
        
        self.get_logger().info('\nTesting ROTATION - differential drive')
        self.get_logger().info('Left wheel should go backward, right wheel forward')
        
        # Publish for 3 seconds
        start_time = time.time()
        while time.time() - start_time < 3.0:
            self.publisher.publish(msg)
            time.sleep(0.1)
            
    def stop(self):
        """Stop the robot"""
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.publisher.publish(msg)
        self.get_logger().info('Stopped')

def main():
    rclpy.init()
    tester = WheelAxisTester()
    
    # Give time for everything to initialize
    time.sleep(2.0)
    
    # Run tests
    tester.test_forward_motion()
    tester.stop()
    time.sleep(1.0)
    
    tester.test_rotation()
    tester.stop()
    
    tester.get_logger().info('\nTest complete! Check visual results:')
    tester.get_logger().info('✅ FIXED: Wheels roll forward/backward properly')
    tester.get_logger().info('❌ BROKEN: Wheels spin sideways like casters')
    
    rclpy.shutdown()

if __name__ == '__main__':
    main()
