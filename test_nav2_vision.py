#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import time

class Nav2VisionTester(Node):
    def __init__(self):
        super().__init__('nav2_vision_tester')
        
        # Publisher for movement commands
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Subscriber for laser scan
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )
        
        # Timer for periodic movement
        self.timer = self.create_timer(3.0, self.timer_callback)
        self.state = 0
        
        self.get_logger().info('Nav2 Vision Tester started')
        
    def scan_callback(self, msg):
        # Count non-infinite ranges (obstacles detected)
        obstacles = sum(1 for r in msg.ranges if r != float('inf') and r < msg.range_max)
        
        if obstacles > 0:
            self.get_logger().info(f'Detected {obstacles} obstacle points in laser scan')
            # Log some details about detected obstacles
            min_range = min(r for r in msg.ranges if r != float('inf'))
            self.get_logger().info(f'Closest obstacle at {min_range:.2f} meters')
    
    def timer_callback(self):
        """Rotate robot slowly to scan environment"""
        cmd = Twist()
        
        if self.state == 0:
            # Rotate slowly
            cmd.angular.z = 0.3
            self.get_logger().info('Rotating to scan for obstacles...')
            self.state = 1
        else:
            # Stop
            cmd.angular.z = 0.0
            self.get_logger().info('Stopping rotation')
            self.state = 0
            
        self.cmd_vel_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    
    tester = Nav2VisionTester()
    
    try:
        rclpy.spin(tester)
    except KeyboardInterrupt:
        pass
    finally:
        # Stop the robot
        stop_cmd = Twist()
        tester.cmd_vel_pub.publish(stop_cmd)
        tester.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
