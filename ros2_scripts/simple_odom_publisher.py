#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster

class SimpleOdomPublisher(Node):
    def __init__(self):
        super().__init__('simple_odom_publisher')
        
        # Subscribe to Gazebo's odometry
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )
        
        # Create transform broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)
        
        self.get_logger().info('Simple odometry publisher started')
        self.get_logger().info('Broadcasting odom->base_link transform from Gazebo odometry')
        
    def odom_callback(self, msg):
        # Create transform from odometry message
        transform = TransformStamped()
        
        # Set header
        transform.header.stamp = msg.header.stamp
        transform.header.frame_id = 'odom'
        transform.child_frame_id = 'base_link'
        
        # Copy position
        transform.transform.translation.x = msg.pose.pose.position.x
        transform.transform.translation.y = msg.pose.pose.position.y
        transform.transform.translation.z = msg.pose.pose.position.z
        
        # Copy orientation
        transform.transform.rotation = msg.pose.pose.orientation
        
        # Broadcast the transform
        self.tf_broadcaster.sendTransform(transform)
        
def main(args=None):
    rclpy.init(args=args)
    
    node = SimpleOdomPublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
