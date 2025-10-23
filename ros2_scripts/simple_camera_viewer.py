#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class SimpleCameraViewer(Node):
    def __init__(self):
        super().__init__('simple_camera_viewer')
        
        self.bridge = CvBridge()
        
        # Subscribe to camera image
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        self.get_logger().info('Simple Camera Viewer started - press Q to quit')
        
    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Convert to HSV for analysis
            hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
            
            # Draw center crosshair
            height, width = cv_image.shape[:2]
            center_x, center_y = width // 2, height // 2
            cv2.line(cv_image, (center_x - 20, center_y), (center_x + 20, center_y), (0, 255, 0), 2)
            cv2.line(cv_image, (center_x, center_y - 20), (center_x, center_y + 20), (0, 255, 0), 2)
            
            # Get HSV value at center
            center_hsv = hsv[center_y, center_x]
            
            # Draw text with HSV values
            text = f"Center HSV: H={center_hsv[0]} S={center_hsv[1]} V={center_hsv[2]}"
            cv2.putText(cv_image, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(cv_image, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            
            # Create mask for green detection (current thresholds)
            green_lower = (35, 50, 50)
            green_upper = (85, 255, 255)
            mask = cv2.inRange(hsv, green_lower, green_upper)
            
            # Apply mask to show what's detected
            detected = cv2.bitwise_and(cv_image, cv_image, mask=mask)
            
            # Count green pixels
            green_pixels = cv2.countNonZero(mask)
            total_pixels = width * height
            percentage = (green_pixels / total_pixels) * 100
            
            text2 = f"Green pixels: {green_pixels} ({percentage:.1f}%)"
            cv2.putText(cv_image, text2, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(cv_image, text2, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            
            # Show images
            cv2.imshow('Camera View', cv_image)
            cv2.imshow('Green Detection', detected)
            cv2.imshow('Mask', mask)
            
            # Check for quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info('Shutting down...')
                rclpy.shutdown()
                cv2.destroyAllWindows()
                
        except Exception as e:
            self.get_logger().error(f'Error: {str(e)}')

def main(args=None):
    rclpy.init(args=args)
    viewer = SimpleCameraViewer()
    
    try:
        rclpy.spin(viewer)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        viewer.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
