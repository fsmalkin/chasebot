#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Header

class BlankMapPublisher(Node):
    def __init__(self):
        super().__init__('blank_map_publisher')
        
        # Create map publisher with transient local QoS for Nav2
        self.map_pub = self.create_publisher(
            OccupancyGrid, 
            '/map',
            rclpy.qos.QoSProfile(
                depth=1,
                durability=rclpy.qos.DurabilityPolicy.TRANSIENT_LOCAL,
                reliability=rclpy.qos.ReliabilityPolicy.RELIABLE
            )
        )
        
        # Create a blank map
        self.map_msg = OccupancyGrid()
        
        # Header
        self.map_msg.header = Header()
        self.map_msg.header.frame_id = 'map'
        
        # Map metadata
        self.map_msg.info.resolution = 0.05  # 5cm per pixel
        self.map_msg.info.width = 200  # 10m wide
        self.map_msg.info.height = 200  # 10m tall
        
        # Origin at center
        self.map_msg.info.origin.position.x = -5.0
        self.map_msg.info.origin.position.y = -5.0
        self.map_msg.info.origin.position.z = 0.0
        self.map_msg.info.origin.orientation.w = 1.0
        
        # Fill with unknown (-1) or free space (0)
        # Using 0 (free space) for the entire map
        self.map_msg.data = [0] * (self.map_msg.info.width * self.map_msg.info.height)
        
        # Publish once and keep alive
        self.timer = self.create_timer(5.0, self.publish_map)
        self.publish_map()  # Publish immediately
        
        self.get_logger().info('Blank map publisher started')
        self.get_logger().info(f'Map size: {self.map_msg.info.width}x{self.map_msg.info.height} at {self.map_msg.info.resolution}m/pixel')
        
    def publish_map(self):
        self.map_msg.header.stamp = self.get_clock().now().to_msg()
        self.map_pub.publish(self.map_msg)
        self.get_logger().debug('Published blank map')

def main(args=None):
    rclpy.init(args=args)
    node = BlankMapPublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
