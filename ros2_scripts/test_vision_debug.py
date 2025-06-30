#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class VisionDebugger(Node):
    def __init__(self):
        super().__init__('vision_debugger')
        
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        self.bridge = CvBridge()
        self.frame_count = 0
        
        self.get_logger().info('Vision Debugger started')
        
    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Convert to HSV
            hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
            
            # Only process every 30th frame
            self.frame_count += 1
            if self.frame_count % 30 != 0:
                return
                
            height, width = cv_image.shape[:2]
            center_y = height // 2
            center_x = width // 2
            
            # Sample colors from center region
            sample_region = hsv[center_y-50:center_y+50, center_x-50:center_x+50]
            
            # Calculate mean HSV values
            mean_hsv = np.mean(sample_region.reshape(-1, 3), axis=0)
            
            # Also check for any green-ish colors
            green_lower = np.array([35, 50, 50])
            green_upper = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, green_lower, green_upper)
            green_pixels = np.sum(mask > 0)
            
            self.get_logger().info(f'Center HSV: H={mean_hsv[0]:.1f}, S={mean_hsv[1]:.1f}, V={mean_hsv[2]:.1f}')
            self.get_logger().info(f'Green pixels detected: {green_pixels} / {width*height} total')
            
            # Check if there's any bright green in the image
            bright_green_lower = np.array([50, 100, 100])
            bright_green_upper = np.array([70, 255, 255])
            bright_mask = cv2.inRange(hsv, bright_green_lower, bright_green_upper)
            bright_green_pixels = np.sum(bright_mask > 0)
            
            if bright_green_pixels > 0:
                self.get_logger().info(f'Bright green pixels found: {bright_green_pixels}')
            
        except Exception as e:
            self.get_logger().error(f'Error: {str(e)}')

def main(args=None):
    rclpy.init(args=args)
    debugger = VisionDebugger()
    
    try:
        rclpy.spin(debugger)
    except KeyboardInterrupt:
        pass
    finally:
        debugger.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
