#!/usr/bin/env python
"""
ChaseBot Ball Detector Node
Detects golf balls in camera feed using HSV color masking
Adapted from proven Webots implementation
"""

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from std_msgs.msg import Header
from cv_bridge import CvBridge, CvBridgeError

# Simple message for ball detection (using Point for now)
# Later we can create custom message type

class BallDetector:
    def __init__(self):
        rospy.init_node('ball_detector', anonymous=True)
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Parameters (can be made configurable via ROS params)
        self.hsv_lower = np.array([0, 0, 150])    # Lower HSV threshold for white
        self.hsv_upper = np.array([180, 50, 255])  # Upper HSV threshold for white
        self.min_area = 20                         # Minimum contour area
        self.max_area = 10000                      # Maximum contour area
        self.min_aspect_ratio = 0.3                # Minimum aspect ratio for circular objects
        self.max_aspect_ratio = 4.0                # Maximum aspect ratio for circular objects
        
        # Publishers
        self.ball_pub = rospy.Publisher('/ball_detection', Point, queue_size=10)
        self.debug_pub = rospy.Publisher('/ball_detection_debug', Image, queue_size=1)
        
        # Subscribers
        self.image_sub = rospy.Subscriber('/camera/image_raw', Image, self.image_callback)
        
        rospy.loginfo("Ball Detector Node initialized")
        rospy.loginfo("HSV Range: {} to {}".format(self.hsv_lower, self.hsv_upper))
        rospy.loginfo("Area Range: {} to {}".format(self.min_area, self.max_area))
    
    def image_callback(self, msg):
        """Process incoming camera image"""
        try:
            # Convert ROS image to OpenCV format
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            rospy.logdebug("Received image: {}x{} pixels".format(cv_image.shape[1], cv_image.shape[0]))
            
        except CvBridgeError as e:
            rospy.logerr("CV Bridge error: {}".format(e))
            return
        
        # Detect golf balls
        detections = self.detect_golf_balls(cv_image)
        
        # Publish best detection (largest area)
        if detections:
            best_ball = max(detections, key=lambda x: x['area'])
            
            # Create Point message with pixel coordinates and area as z
            ball_point = Point()
            ball_point.x = best_ball['center'][0]
            ball_point.y = best_ball['center'][1] 
            ball_point.z = best_ball['area']  # Store area in z coordinate
            
            self.ball_pub.publish(ball_point)
            
            rospy.loginfo("Ball detected at pixel ({:.0f}, {:.0f}) with area {:.0f}".format(
                ball_point.x, ball_point.y, ball_point.z))
        else:
            rospy.logdebug("No balls detected")
        
        # Publish debug image if we have subscribers
        if self.debug_pub.get_num_connections() > 0:
            debug_image = self.create_debug_image(cv_image, detections)
            try:
                debug_msg = self.bridge.cv2_to_imgmsg(debug_image, "bgr8")
                self.debug_pub.publish(debug_msg)
            except CvBridgeError as e:
                rospy.logerr("Debug image conversion error: {}".format(e))
    
    def detect_golf_balls(self, image):
        """Detect golf balls using HSV color masking and contour analysis"""
        if image is None:
            return []
        
        # Convert to HSV color space
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create mask for white objects (golf balls)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Count white pixels for debugging
        white_pixels = cv2.countNonZero(mask)
        rospy.logdebug("White pixels found: {}".format(white_pixels))
        
        # Apply morphological operations to clean up mask
        kernel = np.ones((3,3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rospy.logdebug("Found {} contours".format(len(contours)))
        
        golf_balls = []
        for i, contour in enumerate(contours):
            # Filter by area
            area = cv2.contourArea(contour)
            rospy.logdebug("Contour {}: area={}".format(i, area))
            
            if self.min_area <= area <= self.max_area:
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check if shape is roughly circular
                aspect_ratio = float(w) / h if h > 0 else 0
                rospy.logdebug("Contour {}: bbox=({},{},{},{}), aspect_ratio={:.2f}".format(
                    i, x, y, w, h, aspect_ratio))
                
                if self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    golf_balls.append({
                        'center': (center_x, center_y),
                        'area': area,
                        'bbox': (x, y, w, h),
                        'contour': contour
                    })
                    rospy.logdebug("FOUND golf ball: center=({},{}), area={}".format(
                        center_x, center_y, area))
                else:
                    rospy.logdebug("REJECT: aspect ratio {:.2f} not circular".format(aspect_ratio))
            else:
                rospy.logdebug("REJECT: area {} out of range [{}, {}]".format(
                    area, self.min_area, self.max_area))
        
        rospy.logdebug("Total golf balls detected: {}".format(len(golf_balls)))
        return golf_balls
    
    def create_debug_image(self, original_image, detections):
        """Create debug visualization showing detections"""
        debug_image = original_image.copy()
        
        # Draw detections
        for detection in detections:
            center = detection['center']
            bbox = detection['bbox']
            area = detection['area']
            
            # Draw bounding box
            x, y, w, h = bbox
            cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Draw center point
            cv2.circle(debug_image, center, 5, (0, 0, 255), -1)
            
            # Add text with area
            text = "Area: {:.0f}".format(area)
            cv2.putText(debug_image, text, (x, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Add status text
        status = "Balls: {}".format(len(detections))
        cv2.putText(debug_image, status, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return debug_image
    
    def run(self):
        """Main execution loop"""
        rospy.loginfo("Ball Detector running...")
        rospy.spin()

if __name__ == '__main__':
    try:
        detector = BallDetector()
        detector.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("Ball Detector node terminated")
