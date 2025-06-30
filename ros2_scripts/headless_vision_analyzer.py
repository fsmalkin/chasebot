#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class HeadlessVisionAnalyzer(Node):
    def __init__(self):
        super().__init__('headless_vision_analyzer')
        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10)
        
        # Current HSV thresholds (from vision_to_laserscan_hsv.py)
        self.lower_green = np.array([35, 100, 50])
        self.upper_green = np.array([85, 255, 255])
        
        self.frame_count = 0
        self.detection_count = 0
        self.last_log_time = self.get_clock().now()
        
        self.get_logger().info('Headless Vision Analyzer started - analyzing camera feed...')

    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
            
            self.frame_count += 1
            
            # Create mask for current thresholds
            mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
            green_pixels = np.sum(mask > 0)
            
            # Every 30 frames (about 1 second), analyze and report
            if self.frame_count % 30 == 0:
                self.analyze_frame_hsv(hsv, cv_image)
                
                # Report detection status
                if green_pixels > 0:
                    self.detection_count += 1
                    self.get_logger().info(f'Green pixels detected: {green_pixels} pixels')
                else:
                    self.get_logger().warn('No green pixels detected with current thresholds')
                
        except Exception as e:
            self.get_logger().error(f'Error processing image: {e}')

    def analyze_frame_hsv(self, hsv, bgr_image):
        """Analyze the HSV values in the frame to find potential golf ball colors"""
        height, width = hsv.shape[:2]
        
        # Sample center region (where ball is likely to be)
        center_x = width // 2
        center_y = height // 2
        sample_size = 50
        
        # Get center region
        x1 = max(0, center_x - sample_size)
        x2 = min(width, center_x + sample_size)
        y1 = max(0, center_y - sample_size)
        y2 = min(height, center_y + sample_size)
        
        center_region_hsv = hsv[y1:y2, x1:x2]
        center_region_bgr = bgr_image[y1:y2, x1:x2]
        
        # Calculate statistics for the center region
        h_mean = np.mean(center_region_hsv[:,:,0])
        s_mean = np.mean(center_region_hsv[:,:,1])
        v_mean = np.mean(center_region_hsv[:,:,2])
        
        # Find pixels that might be green/golf ball colored
        # Look for high saturation and value (bright colors)
        bright_mask = (center_region_hsv[:,:,1] > 50) & (center_region_hsv[:,:,2] > 50)
        
        if np.any(bright_mask):
            bright_pixels_hsv = center_region_hsv[bright_mask]
            h_bright = bright_pixels_hsv[:,0]
            
            # Find the most common hue values for bright pixels
            if len(h_bright) > 0:
                h_min = np.min(h_bright)
                h_max = np.max(h_bright)
                h_median = np.median(h_bright)
                
                self.get_logger().info(f'Center region HSV stats: H={h_mean:.1f}, S={s_mean:.1f}, V={v_mean:.1f}')
                self.get_logger().info(f'Bright pixels hue range: {h_min}-{h_max}, median={h_median:.1f}')
                
                # Check if we're detecting anything in green range
                green_range_pixels = np.sum((h_bright >= 35) & (h_bright <= 85))
                if green_range_pixels > 0:
                    self.get_logger().info(f'Found {green_range_pixels} bright pixels in green hue range (35-85)')
                else:
                    # Suggest what range might work
                    self.get_logger().warn(f'No bright pixels in green range. Try hue range: {h_min}-{h_max}')
        else:
            self.get_logger().warn('No bright pixels found in center region - ball might not be visible')
            
        # Also analyze the full frame for any bright green-ish areas
        full_bright_mask = (hsv[:,:,1] > 100) & (hsv[:,:,2] > 100)
        bright_green_mask = full_bright_mask & (hsv[:,:,0] >= 20) & (hsv[:,:,0] <= 100)
        
        bright_green_count = np.sum(bright_green_mask)
        if bright_green_count > 0:
            bright_green_hsv = hsv[bright_green_mask]
            h_values = bright_green_hsv[:,0]
            self.get_logger().info(f'Found {bright_green_count} bright green-ish pixels in full frame')
            self.get_logger().info(f'Their hue range: {np.min(h_values)}-{np.max(h_values)}')

def main(args=None):
    rclpy.init(args=args)
    analyzer = HeadlessVisionAnalyzer()
    
    try:
        rclpy.spin(analyzer)
    except KeyboardInterrupt:
        pass
    finally:
        analyzer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
