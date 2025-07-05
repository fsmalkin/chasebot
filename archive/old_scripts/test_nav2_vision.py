#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from sensor_msgs.msg import LaserScan
import time

class TestNav2Vision(Node):
    """
    Simple test node to verify Nav2 integration.
    Publishes manual cmd_vel commands and monitors laser scan.
    """
    
    def __init__(self):
        super().__init__('test_nav2_vision')
        
        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Subscribers
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )
        
        # Timer for periodic commands
        self.timer = self.create_timer(2.0, self.timer_callback)
        
        # State
        self.scan_received = False
        self.test_phase = 0
        self.phase_start_time = self.get_clock().now()
        
        self.get_logger().info('Test Nav2 Vision node initialized')
        self.get_logger().info('Phase 1: Checking laser scan data...')
    
    def scan_callback(self, msg):
        if not self.scan_received:
            self.scan_received = True
            self.get_logger().info(f'Laser scan received! {len(msg.ranges)} points')
            
            # Count valid readings
            valid_readings = sum(1 for r in msg.ranges if r != float('inf'))
            self.get_logger().info(f'Valid readings: {valid_readings}/{len(msg.ranges)}')
            
            # Find closest obstacle
            finite_ranges = [r for r in msg.ranges if r != float('inf')]
            if finite_ranges:
                min_range = min(finite_ranges)
                self.get_logger().info(f'Closest obstacle: {min_range:.2f}m')
    
    def timer_callback(self):
        current_time = self.get_clock().now()
        phase_duration = (current_time - self.phase_start_time).nanoseconds / 1e9
        
        if self.test_phase == 0:
            # Phase 1: Just monitor laser scan
            if phase_duration > 3.0 and self.scan_received:
                self.test_phase = 1
                self.phase_start_time = current_time
                self.get_logger().info('Phase 2: Testing direct motor control...')
        
        elif self.test_phase == 1:
            # Phase 2: Test direct motor control
            if phase_duration < 2.0:
                # Move forward
                cmd = Twist()
                cmd.linear.x = 0.1
                cmd.angular.z = 0.0
                self.cmd_pub.publish(cmd)
                self.get_logger().info('Moving forward...')
            elif phase_duration < 4.0:
                # Turn
                cmd = Twist()
                cmd.linear.x = 0.0
                cmd.angular.z = 0.3
                self.cmd_pub.publish(cmd)
                self.get_logger().info('Turning...')
            else:
                # Stop
                cmd = Twist()
                cmd.linear.x = 0.0
                cmd.angular.z = 0.0
                self.cmd_pub.publish(cmd)
                self.test_phase = 2
                self.phase_start_time = current_time
                self.get_logger().info('Phase 3: Complete. Robot should have moved.')
        
        elif self.test_phase == 2:
            # Phase 3: Test complete
            if phase_duration > 2.0:
                self.get_logger().info('Test complete!')
                self.get_logger().info('Results:')
                self.get_logger().info(f'- Laser scan: {"WORKING" if self.scan_received else "NOT WORKING"}')
                self.get_logger().info('- Check if robot moved in Gazebo')
                self.get_logger().info('- If robot moved, basic systems are working')
                self.get_logger().info('- Next step: Add Nav2 goal sending')
                
                # Cancel timer
                self.timer.cancel()


def main(args=None):
    rclpy.init(args=args)
    
    test_node = TestNav2Vision()
    
    try:
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    finally:
        test_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
