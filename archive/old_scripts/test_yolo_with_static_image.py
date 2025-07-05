#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class TestImagePublisher(Node):
    def __init__(self):
        super().__init__('test_image_publisher')
        
        # Create publisher for camera image
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)
        
        # Create a timer to publish at 5 Hz
        self.timer = self.create_timer(0.2, self.publish_test_image)
        
        # CV Bridge for image conversion
        self.bridge = CvBridge()
        
        # Create a simple test image with a green circle (simulating golf ball)
        self.test_image = self.create_test_image()
        
        self.get_logger().info('Test image publisher started - publishing green circle as golf ball')
        
    def create_test_image(self):
        """Create a test image with a green circle representing a golf ball"""
        # Create a 640x480 image with blue background (like sky/grass)
        img = np.ones((480, 640, 3), dtype=np.uint8) * 100
        img[:,:,0] = 150  # More blue
        img[:,:,1] = 180  # Some green
        
        # Add a white circle in the center (golf ball)
        center = (320, 240)
        radius = 30
        # Pure white golf ball
        cv2.circle(img, center, radius, (255, 255, 255), -1)
        
        # Add some shading for realism
        cv2.circle(img, (center[0]-10, center[1]-10), radius//3, (245, 245, 245), -1)
        
        return img
        
    def publish_test_image(self):
        """Publish the test image"""
        msg = self.bridge.cv2_to_imgmsg(self.test_image, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_optical_link'
        self.image_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = TestImagePublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
