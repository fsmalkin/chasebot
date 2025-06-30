#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

class LaserScanChecker(Node):
    def __init__(self):
        super().__init__('laser_scan_checker')
        self.subscription = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )
        self.get_logger().info('LaserScan checker started')
        
    def scan_callback(self, msg):
        ranges = msg.ranges
        non_inf_count = sum(1 for r in ranges if r != float('inf'))
        
        if non_inf_count > 0:
            # Find all non-inf indices
            non_inf_indices = [i for i, r in enumerate(ranges) if r != float('inf')]
            self.get_logger().info(f'Found {non_inf_count} non-inf values at indices: {non_inf_indices[:10]}...')
            
            # Check specific indices
            if len(ranges) > 180:
                self.get_logger().info(f'Range at index 179: {ranges[179]}')
                self.get_logger().info(f'Range at index 180: {ranges[180]}')
            
            # Find closest obstacle
            min_range = min(r for r in ranges if r != float('inf'))
            self.get_logger().info(f'Closest obstacle at: {min_range:.2f}m')
        else:
            self.get_logger().info('All ranges are infinity!')
            
        # Shutdown after first message
        self.destroy_node()
        rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)
    checker = LaserScanChecker()
    rclpy.spin(checker)

if __name__ == '__main__':
    main()
