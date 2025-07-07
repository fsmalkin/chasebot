#!/usr/bin/env python3
"""
ChaseBot D415 Camera Vision Display
Based on ros2_vision_with_display.py but adapted for D415 camera topic
Shows camera feed with golf ball detection and bounding boxes
"""

import rclpy
from rclpy.node import Node
import cv2
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from cv_bridge import CvBridge, CvBridgeError

class D415VisionDisplay(Node):
    def __init__(self):
        super().__init__('d415_vision_display')
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Detection parameters
        self.min_area = 200  # Minimum golf ball area in pixels
        self.detection_count = 0
        self.frame_count = 0
        
        # Publishers
        self.detection_pub = self.create_publisher(Point, '/ball_detections', 10)
        
        # Subscribers - CHANGED to D415 topic
        self.image_sub = self.create_subscription(
            Image,
            '/d415/image_raw',  # Changed from /camera/image_raw
            self.image_callback,
            10
        )
        
        self.get_logger().info("D415 Vision Display initialized - subscribing to /d415/image_raw")
        self.get_logger().info("Will show visual window with golf ball detection overlays")
        self.get_logger().info("Press 'Q' to quit")
    
    def detect_golf_balls(self, image):
        """Detect white/bright golf balls using HSV color filtering"""
        if image is None:
            return [], image
        
        # Convert to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Define HSV range for white/bright objects (golf balls)
        # White objects have high value, low saturation
        lower_white = np.array([0, 0, 180])    # Lowered threshold for more sensitivity
        upper_white = np.array([180, 50, 255]) # Slightly higher saturation tolerance
        
        # Create binary mask
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Apply morphological operations to clean up the mask
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Create display image with detection overlays
        display_image = image.copy()
        detections = []
        
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            # Filter by minimum area
            if area > self.min_area:
                # Calculate bounding box and center
                x, y, w, h = cv2.boundingRect(contour)
                center_x = x + w // 2
                center_y = y + h // 2
                
                # Filter by aspect ratio (golf balls should be roughly circular)
                aspect_ratio = float(w) / h
                if 0.5 < aspect_ratio < 2.0:  # Allow some tolerance for perspective
                    detection = {
                        'center': (center_x, center_y),
                        'area': area,
                        'bbox': (x, y, w, h)
                    }
                    detections.append(detection)
                    
                    # Draw detection overlay on display image
                    cv2.rectangle(display_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.circle(display_image, (center_x, center_y), 5, (0, 0, 255), -1)
                    cv2.putText(display_image, 'GOLF BALL', (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(display_image, f'Area: {int(area)}', (x, y + h + 20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    self.get_logger().info("Found golf ball #{}: area={:.0f}, center=({}, {})".format(
                        i, area, center_x, center_y))
        
        # Add info overlay to the display image
        cv2.putText(display_image, f'Frame: {self.frame_count}', (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display_image, f'Detections: {len(detections)}', (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display_image, 'D415 Camera Feed - Press Q to quit', (10, display_image.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return detections, display_image
    
    def image_callback(self, msg):
        """Process incoming camera image"""
        self.frame_count += 1
        
        try:
            # Convert ROS image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Log every 60 frames to avoid spam
            if self.frame_count % 60 == 0:
                self.get_logger().info("Processing frame #{}: {}x{} pixels".format(
                    self.frame_count, cv_image.shape[1], cv_image.shape[0]))
            
        except CvBridgeError as e:
            self.get_logger().error("CV Bridge error: {}".format(e))
            return
        
        # Detect golf balls and create display image
        detections, display_image = self.detect_golf_balls(cv_image)
        
        # Show the image with detection overlays
        cv2.imshow('D415 Vision - Golf Ball Detection', display_image)
        
        # Process keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'):
            self.get_logger().info("User requested quit via 'Q' key")
            cv2.destroyAllWindows()
            rclpy.shutdown()
        
        # Publish detections
        if detections:
            self.detection_count += 1
            
            # Publish the largest detection (most likely golf ball)
            best_detection = max(detections, key=lambda x: x['area'])
            
            detection_msg = Point()
            detection_msg.x = float(best_detection['center'][0])  # Pixel X coordinate
            detection_msg.y = float(best_detection['center'][1])  # Pixel Y coordinate
            detection_msg.z = float(best_detection['area'])       # Detection confidence (area)
            self.detection_pub.publish(detection_msg)
            
            self.get_logger().info("GOLF BALL DETECTION #{}: Published at pixel ({}, {}) with area {:.0f}".format(
                self.detection_count, 
                best_detection['center'][0], 
                best_detection['center'][1], 
                best_detection['area']))

def main(args=None):
    rclpy.init(args=args)
    
    detector = D415VisionDisplay()
    
    try:
        rclpy.spin(detector)
    except KeyboardInterrupt:
        detector.get_logger().info("Vision detector shutting down...")
    finally:
        cv2.destroyAllWindows()
        detector.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
