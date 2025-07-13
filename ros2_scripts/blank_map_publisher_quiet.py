#!/usr/bin/env python3
"""
Quiet Blank Map Publisher for Nav2
Publishes a minimal occupancy grid without flooding logs
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Header


class QuietBlankMapPublisher(Node):
    def __init__(self):
        super().__init__('blank_map_publisher')
        
        # Create publisher
        self.map_publisher = self.create_publisher(OccupancyGrid, '/map', 10)
        
        # Create a simple blank map
        self.map_msg = OccupancyGrid()
        self.map_msg.header.frame_id = 'map'
        self.map_msg.info.resolution = 0.05  # 5cm per pixel
        self.map_msg.info.width = 200
        self.map_msg.info.height = 200
        self.map_msg.info.origin.position.x = -5.0
        self.map_msg.info.origin.position.y = -5.0
        self.map_msg.info.origin.position.z = 0.0
        self.map_msg.info.origin.orientation.w = 1.0
        
        # Initialize map data (0 = free space)
        self.map_msg.data = [0] * (self.map_msg.info.width * self.map_msg.info.height)
        
        # Publish once at startup
        self.get_logger().info('Publishing blank map (200x200 at 0.05m/pixel)')
        self.publish_map()
        
        # Then publish at lower frequency (1 Hz instead of 10 Hz)
        self.timer = self.create_timer(1.0, self.publish_map_silent)
        
    def publish_map(self):
        """Publish map with logging"""
        self.map_msg.header.stamp = self.get_clock().now().to_msg()
        self.map_publisher.publish(self.map_msg)
        
    def publish_map_silent(self):
        """Publish map without logging"""
        self.map_msg.header.stamp = self.get_clock().now().to_msg()
        self.map_publisher.publish(self.map_msg)


def main(args=None):
    rclpy.init(args=args)
    node = QuietBlankMapPublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
