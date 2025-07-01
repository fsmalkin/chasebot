#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import urllib.request
import os

class RealImagePublisher(Node):
    def __init__(self):
        super().__init__('real_image_publisher')
        
        # Create publisher for camera image
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)
        
        # Create a timer to publish at 2 Hz
        self.timer = self.create_timer(0.5, self.publish_test_image)
        
        # CV Bridge for image conversion
        self.bridge = CvBridge()
        
        # Create a realistic golf ball scene
        self.test_image = self.create_golf_ball_scene()
        
        self.get_logger().info('Publishing realistic golf ball scene for YOLO testing')
        
    def create_golf_ball_scene(self):
        """Create a realistic scene with a golf ball"""
        # Create a green grass background
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Make grass green with some variation
        img[:,:,1] = 80 + np.random.randint(-20, 20, (480, 640))  # Green channel
        img[:,:,0] = 40 + np.random.randint(-10, 10, (480, 640))  # Blue channel
        img[:,:,2] = 30 + np.random.randint(-10, 10, (480, 640))  # Red channel
        
        # Add a realistic white golf ball with texture
        center = (320, 350)  # Lower in frame like on ground
        radius = 25
        
        # Create golf ball with realistic shading
        for y in range(center[1] - radius, center[1] + radius):
            for x in range(center[0] - radius, center[0] + radius):
                dist = np.sqrt((x - center[0])**2 + (y - center[1])**2)
                if dist < radius:
                    # Calculate brightness based on distance from center
                    brightness = 255 - int((dist / radius) * 50)
                    # Add slight dimple pattern
                    if (x + y) % 4 == 0:
                        brightness -= 10
                    img[y, x] = (brightness, brightness, brightness)
        
        # Add shadow
        shadow_center = (center[0] + 5, center[1] + 3)
        cv2.ellipse(img, shadow_center, (radius, radius//3), 0, 0, 360, (20, 40, 20), -1)
        
        # Redraw ball on top of shadow
        for y in range(center[1] - radius, center[1] + radius):
            for x in range(center[0] - radius, center[0] + radius):
                dist = np.sqrt((x - center[0])**2 + (y - center[1])**2)
                if dist < radius:
                    brightness = 255 - int((dist / radius) * 50)
                    if (x + y) % 4 == 0:
                        brightness -= 10
                    img[y, x] = (brightness, brightness, brightness)
        
        return img
        
    def publish_test_image(self):
        """Publish the test image"""
        msg = self.bridge.cv2_to_imgmsg(self.test_image, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_optical_link'
        self.image_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = RealImagePublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
