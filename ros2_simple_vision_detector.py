#!/usr/bin/env python3
"""
ChaseBot ROS 2 Simple Vision Detector
Phase 3, Step 3.2 - Basic Vision Integration
Thin Slice 1: Minimal vision node for camera feed validation
"""

import rclpy
from rclpy.node import Node
import cv2
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from cv_bridge import CvBridge, CvBridgeError

class SimpleVisionDetector(Node):
    def __init__(self):
        super().__init__('simple_vision_detector')
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Detection parameters
        self.min_area = 100  # Minimum object area in pixels
        self.detection_count = 0
        self.frame_count = 0
        
        # Publishers
        self.detection_pub = self.create_publisher(Point, '/ball_detections', 10)
        
        # Subscribers
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        self.get_logger().info("Simple Vision Detector initialized - subscribing to /camera/image_raw")
        self.get_logger().info("Will detect white/bright objects as golf balls")
    
    def detect_golf_balls(self, image):
        """Detect white/bright golf balls using HSV color filtering"""
        if image is None:
            return []
        
        # Convert to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Define HSV range for white/bright objects (golf balls)
        # White objects have high value, low saturation
        lower_white = np.array([0, 0, 200])    # Low saturation, high value
        upper_white = np.array([180, 30, 255]) # Any hue, low saturation, max value
        
        # Create binary mask
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            # Filter by minimum area
            if area > self.min_area:
                x, y, w, h = cv2.boundingRect(contour)
                center_x = x + w // 2
                center_y = y + h // 2
                
                detection = {
                    'center': (center_x, center_y),
                    'area': area,
                    'bbox': (x, y, w, h)
                }
                detections.append(detection)
                
                self.get_logger().info("Found golf ball candidate #{}: area={:.0f}, center=({}, {})".format(
                    i, area, center_x, center_y))
        
        return detections
    
    def image_callback(self, msg):
        """Process incoming camera image"""
        self.frame_count += 1
        
        try:
            # Convert ROS image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Log every 30 frames to avoid spam (roughly once per second at 30 Hz)
            if self.frame_count % 30 == 0:
                self.get_logger().info("Received image #{}: {}x{} pixels".format(
                    self.frame_count, cv_image.shape[1], cv_image.shape[0]))
            
        except CvBridgeError as e:
            self.get_logger().error("CV Bridge error: {}".format(e))
            return
        
        # Detect golf balls
        detections = self.detect_golf_balls(cv_image)
        
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
        else:
            # Log only occasionally when no detections to avoid spam
            if self.frame_count % 60 == 0:  # Every 2 seconds
                self.get_logger().info("No golf balls detected in recent frames")

def main(args=None):
    rclpy.init(args=args)
    
    detector = SimpleVisionDetector()
    
    try:
        rclpy.spin(detector)
    except KeyboardInterrupt:
        detector.get_logger().info("Vision detector shutting down...")
    finally:
        detector.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
