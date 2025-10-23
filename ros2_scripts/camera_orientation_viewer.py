#!/usr/bin/env python3
"""
Simple camera viewer to check D415 camera orientation
Shows the camera feed with colored ball positions labeled
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class CameraOrientationViewer(Node):
    def __init__(self):
        super().__init__('camera_orientation_viewer')
        
        # Subscribe to camera image
        self.image_sub = self.create_subscription(
            Image,
            '/d415/image_raw',
            self.image_callback,
            10
        )
        
        self.bridge = CvBridge()
        self.get_logger().info('Camera Orientation Viewer started')
        self.get_logger().info('Waiting for camera images on /d415/image_raw...')
        
        # Color definitions for ball detection
        self.ball_colors = {
            'RED (Forward)': {
                'lower': np.array([0, 120, 70]),
                'upper': np.array([10, 255, 255])
            },
            'BLUE (Left)': {
                'lower': np.array([100, 120, 70]),
                'upper': np.array([130, 255, 255])
            },
            'YELLOW (Right)': {
                'lower': np.array([20, 120, 70]),
                'upper': np.array([30, 255, 255])
            },
            'GREEN (Behind)': {
                'lower': np.array([40, 120, 70]),
                'upper': np.array([80, 255, 255])
            }
        }
        
    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            
            # Convert to HSV for color detection
            hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
            
            # Detect each colored ball
            for color_name, color_range in self.ball_colors.items():
                mask = cv2.inRange(hsv, color_range['lower'], color_range['upper'])
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Find largest contour (assumed to be the ball)
                    largest = max(contours, key=cv2.contourArea)
                    M = cv2.moments(largest)
                    
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        # Draw circle and label
                        cv2.circle(cv_image, (cx, cy), 20, (255, 255, 255), 3)
                        cv2.putText(cv_image, color_name, (cx - 50, cy - 25),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Add orientation guide
            cv2.putText(cv_image, "Camera Orientation Test", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(cv_image, "Red=Forward, Blue=Left, Yellow=Right, Green=Behind", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            # Add crosshair in center
            h, w = cv_image.shape[:2]
            cv2.line(cv_image, (w//2 - 20, h//2), (w//2 + 20, h//2), (0, 255, 0), 2)
            cv2.line(cv_image, (w//2, h//2 - 20), (w//2, h//2 + 20), (0, 255, 0), 2)
            
            # Display the image
            cv2.imshow('D415 Camera - Orientation Test', cv_image)
            cv2.waitKey(1)
            
        except Exception as e:
            self.get_logger().error('Failed to process image: {}'.format(str(e)))

def main(args=None):
    rclpy.init(args=args)
    viewer = CameraOrientationViewer()
    
    try:
        rclpy.spin(viewer)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        viewer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
