#!/usr/bin/env python3

"""
Golf Ball Detection Test for ChaseBot
Tests vision system detection without movement commands
Shows what camera sees and logs detection results
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge
import numpy as np

class DetectionTest(Node):
    def __init__(self):
        super().__init__('detection_test')
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Subscribe to camera
        self.image_sub = self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        
        # Detection parameters
        self.image_width = 640
        self.image_height = 480
        self.center_x = self.image_width // 2
        self.center_y = self.image_height // 2
        self.min_area = 100  # Much lower threshold for small golf balls
        
        # Frame counter for reduced logging
        self.frame_count = 0
        self.log_every_n_frames = 30  # Log every 30 frames (about 1 per second)
        
        self.get_logger().info('Detection Test Started')
        self.get_logger().info('Looking for green golf balls...')
        self.get_logger().info('Close the camera window with Q key to exit')
    
    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            
            # Detect golf balls
            detection = self.detect_golf_ball(cv_image)
            
            # Create display image with detection overlay
            display_image = cv_image.copy()
            
            if detection:
                ball_x, ball_y, ball_area = detection
                
                # Draw detection info on image
                cv2.circle(display_image, (ball_x, ball_y), 10, (0, 255, 0), 3)  # Green center point
                cv2.putText(display_image, f'Ball: ({ball_x}, {ball_y}) Area: {int(ball_area)}', 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Log detection every N frames
                if self.frame_count % self.log_every_n_frames == 0:
                    x_error = ball_x - self.center_x
                    self.get_logger().info(f'BALL DETECTED: pos=({ball_x}, {ball_y}) area={int(ball_area)} x_error={x_error}')
            else:
                # Log no detection less frequently
                if self.frame_count % (self.log_every_n_frames * 3) == 0:
                    self.get_logger().warn('No ball detected')
            
            # Draw center crosshair
            cv2.line(display_image, (self.center_x - 20, self.center_y), 
                    (self.center_x + 20, self.center_y), (255, 0, 0), 2)
            cv2.line(display_image, (self.center_x, self.center_y - 20), 
                    (self.center_x, self.center_y + 20), (255, 0, 0), 2)
            
            # Add frame info
            cv2.putText(display_image, f'Frame: {self.frame_count}', 
                       (10, display_image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Show image
            cv2.imshow('Golf Ball Detection Test', display_image)
            
            # Exit on 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info('Q key pressed - shutting down')
                rclpy.shutdown()
            
            self.frame_count += 1
                
        except Exception as e:
            self.get_logger().error(f'Image processing error: {e}')
    
    def detect_golf_ball(self, image):
        """
        Detect green golf balls using HSV color filtering
        Returns: (center_x, center_y, area) or None if no detection
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Green color range in HSV (very permissive for any green)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        # Create mask
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Apply morphological operations to clean up
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find largest contour (assuming it's the golf ball)
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        # Check minimum area threshold
        if area < self.min_area:
            return None
        
        # Calculate center
        M = cv2.moments(largest_contour)
        if M['m00'] != 0:
            center_x = int(M['m10'] / M['m00'])
            center_y = int(M['m01'] / M['m00'])
            return (center_x, center_y, area)
        
        return None

def main():
    rclpy.init()
    
    test_node = DetectionTest()
    
    try:
        rclpy.spin(test_node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        test_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
