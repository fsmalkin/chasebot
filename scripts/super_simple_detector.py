#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ChaseBot Super Simple Object Detector
Detects ANY objects/contours in camera feed - for basic UAT validation
"""

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from cv_bridge import CvBridge, CvBridgeError

class SuperSimpleDetector:
    def __init__(self):
        rospy.init_node('super_simple_detector', anonymous=True)
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Very permissive detection parameters
        self.min_area = 10  # Detect anything larger than 10 pixels
        self.detection_count = 0
        
        # Publishers
        self.detection_pub = rospy.Publisher('/object_detection', Point, queue_size=10)
        
        # Subscribers
        self.image_sub = rospy.Subscriber('/camera/image_raw', Image, self.image_callback)
        
        rospy.loginfo("Super Simple Detector initialized - will detect ANYTHING!")
    
    def detect_anything(self, image):
        """Detect ANY objects using very simple thresholding"""
        if image is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Simple binary threshold (detect anything not background)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Also try inverted threshold 
        _, thresh_inv = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours in both images
        result1 = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result2 = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Handle OpenCV version compatibility
        if len(result1) == 3:
            _, contours1, _ = result1
            _, contours2, _ = result2
        else:
            contours1, _ = result1
            contours2, _ = result2
        
        # Combine all contours
        all_contours = contours1 + contours2
        
        detections = []
        for i, contour in enumerate(all_contours):
            area = cv2.contourArea(contour)
            
            # Accept ANY contour larger than minimum area
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
                
                rospy.loginfo("Found object #{}: area={:.0f}, center=({}, {})".format(
                    i, area, center_x, center_y))
        
        return detections
    
    def image_callback(self, msg):
        """Process incoming camera image"""
        try:
            # Convert ROS image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            rospy.loginfo("Received image: {}x{} pixels".format(cv_image.shape[1], cv_image.shape[0]))
            
        except CvBridgeError as e:
            rospy.logerr("CV Bridge error: {}".format(e))
            return
        
        # Detect anything
        detections = self.detect_anything(cv_image)
        
        if detections:
            self.detection_count += 1
            
            # Publish the largest detection
            best_detection = max(detections, key=lambda x: x['area'])
            
            detection_msg = Point()
            detection_msg.x = best_detection['center'][0]
            detection_msg.y = best_detection['center'][1]
            detection_msg.z = best_detection['area']
            self.detection_pub.publish(detection_msg)
            
            rospy.loginfo("DETECTION #{}: Published object at ({}, {}) with area {:.0f}".format(
                self.detection_count, 
                best_detection['center'][0], 
                best_detection['center'][1], 
                best_detection['area']))
        else:
            rospy.loginfo("No objects detected in this frame")
    
    def run(self):
        """Main execution loop"""
        rospy.loginfo("Super Simple Detector running - looking for ANYTHING!")
        rospy.spin()

if __name__ == '__main__':
    try:
        detector = SuperSimpleDetector()
        detector.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("Super Simple Detector terminated")
