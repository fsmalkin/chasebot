#!/usr/bin/env python3

"""
Simple Movement Test for ChaseBot
Tests basic differential drive functionality without vision
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time

class SimpleMovementTest(Node):
    def __init__(self):
        super().__init__('simple_movement_test')
        
        # Publisher for movement commands
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Wait for publisher to be ready
        time.sleep(1.0)
        
        self.get_logger().info('Simple Movement Test - Starting in 2 seconds...')
        time.sleep(2.0)
        
        # Run movement test sequence
        self.run_movement_test()
    
    def run_movement_test(self):
        """Run a simple movement test sequence"""
        
        # Test 1: Move forward
        self.get_logger().info('TEST 1: Moving forward for 3 seconds')
        twist = Twist()
        twist.linear.x = 0.2  # 0.2 m/s forward
        twist.angular.z = 0.0
        
        start_time = time.time()
        while time.time() - start_time < 3.0:
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)
        
        # Stop
        self.get_logger().info('TEST 1: Stopping')
        self.stop_robot()
        time.sleep(1.0)
        
        # Test 2: Turn left
        self.get_logger().info('TEST 2: Turning left for 2 seconds')
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.5  # 0.5 rad/s left turn
        
        start_time = time.time()
        while time.time() - start_time < 2.0:
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)
        
        # Stop
        self.get_logger().info('TEST 2: Stopping')
        self.stop_robot()
        time.sleep(1.0)
        
        # Test 3: Move backward
        self.get_logger().info('TEST 3: Moving backward for 2 seconds')
        twist = Twist()
        twist.linear.x = -0.1  # -0.1 m/s backward
        twist.angular.z = 0.0
        
        start_time = time.time()
        while time.time() - start_time < 2.0:
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)
        
        # Stop
        self.get_logger().info('TEST 3: Stopping')
        self.stop_robot()
        time.sleep(1.0)
        
        # Test 4: Turn right
        self.get_logger().info('TEST 4: Turning right for 2 seconds')
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = -0.5  # -0.5 rad/s right turn
        
        start_time = time.time()
        while time.time() - start_time < 2.0:
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)
        
        # Final stop
        self.get_logger().info('TEST 4: Stopping')
        self.stop_robot()
        
        self.get_logger().info('Movement test sequence complete!')
        self.get_logger().info('If you saw the robot move, differential drive is working!')
        self.get_logger().info('If no movement, check physics/URDF configuration.')
    
    def stop_robot(self):
        """Send stop command"""
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        
        # Send stop command multiple times to ensure it's received
        for _ in range(5):
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)

def main():
    rclpy.init()
    
    test_node = SimpleMovementTest()
    
    try:
        # Keep node alive for a bit after test
        time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        # Final stop
        twist = Twist()
        test_node.cmd_vel_pub.publish(twist)
        test_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
