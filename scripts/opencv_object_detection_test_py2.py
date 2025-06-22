#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ChaseBot OpenCV Object Detection Test
Uses OpenCV contour analysis to detect round objects
Python 2.7 compatible version for ROS Melodic
"""

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from cv_bridge import CvBridge, CvBridgeError

class OpenCVObjectDetector:
    def __init__(self):
        rospy.init_node('opencv_object_detector', anonymous=True)
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Detection parameters
        self.confidence_threshold = 0.5
        self.min_area = 100
        self.max_area = 10000
        
        # State tracking
        self.detection_count = 0
        self.sports_ball_detections = 0
        
        # Publishers
        self.detection_pub = rospy.Publisher('/object_detection', Point, queue_size=10)
        
        # Subscribers
        self.image_sub = rospy.Subscriber('/camera/image_raw', Image, self.image_callback)
        
        rospy.loginfo("OpenCV Object Detector initialized")
        rospy.loginfo("Looking for round objects that could be balls...")
    
    def detect_objects_basic(self, image):
        """Basic object detection using contours and shape analysis"""
        if image is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Use adaptive thresholding to find objects
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        # Find contours (handle OpenCV 3.x vs 4.x compatibility)
        result = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(result) == 3:
            # OpenCV 3.x returns (image, contours, hierarchy)
            _, contours, _ = result
        else:
            # OpenCV 4.x returns (contours, hierarchy)
            contours, _ = result
        
        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area (reasonable object size)
            if self.min_area < area < self.max_area:
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check if roughly circular (could be a ball)
                aspect_ratio = float(w) / h if h > 0 else 0
                if 0.7 <= aspect_ratio <= 1.3:  # Nearly square/circular
                    # Calculate circularity
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        
                        if circularity > 0.4:  # Reasonably circular
                            center_x = x + w // 2
                            center_y = y + h // 2
                            
                            detection = {
                                'class': 'round_object',
                                'confidence': min(0.9, circularity),
                                'bbox': (x, y, w, h),
                                'center': (center_x, center_y),
                                'area': area
                            }
                            detections.append(detection)
        
        return detections
    
    def image_callback(self, msg):
        """Process incoming camera image"""
        try:
            # Convert ROS image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
        except CvBridgeError as e:
            rospy.logerr("CV Bridge error: {}".format(e))
            return
        
        # Detect objects
        detections = self.detect_objects_basic(cv_image)
        
        # Process detections
        if detections:
            self.detection_count += 1
            
            # Find best detection (highest confidence or largest area)
            best_detection = max(detections, key=lambda x: x.get('confidence', 0) + x['area']/10000.0)
            
            # Check if it could be a sports ball
            if best_detection['class'] in ['round_object', 'sports ball']:
                self.sports_ball_detections += 1
                
                # Publish detection
                detection_msg = Point()
                detection_msg.x = best_detection['center'][0]
                detection_msg.y = best_detection['center'][1]
                detection_msg.z = best_detection['area']
                self.detection_pub.publish(detection_msg)
                
                rospy.loginfo("OBJECT DETECTED: {} at ({}, {}) with confidence {:.2f}, area: {:.0f}".format(
                    best_detection['class'],
                    best_detection['center'][0],
                    best_detection['center'][1],
                    best_detection.get('confidence', 0),
                    best_detection['area']
                ))
            
            rospy.loginfo("Detection #{}: Found {} objects, {} potential balls".format(
                self.detection_count, len(detections), self.sports_ball_detections))
        
        else:
            rospy.logdebug("No objects detected in current frame")
    
    def run(self):
        """Main execution loop"""
        rospy.loginfo("OpenCV Object Detector running...")
        rospy.loginfo("Looking for round objects that could be balls...")
        rospy.loginfo("Publishing detections to /object_detection topic")
        rospy.spin()

if __name__ == '__main__':
    try:
        detector = OpenCVObjectDetector()
        detector.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("OpenCV Object Detector terminated")
