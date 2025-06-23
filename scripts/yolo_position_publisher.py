#!/usr/bin/env python

import rospy
from darknet_ros_msgs.msg import BoundingBoxes
from simple_follower.msg import position as PositionMsg
import math

class YoloPositionPublisher:
    def __init__(self):
        rospy.init_node('yolo_position_publisher', anonymous=True)
        
        # Publishers and subscribers
        self.position_pub = rospy.Publisher('/object_tracker/current_position', PositionMsg, queue_size=10)
        self.bbox_sub = rospy.Subscriber('/darknet_ros/bounding_boxes', BoundingBoxes, self.bbox_callback)
        
        # Parameters for position calculation
        self.camera_fov_horizontal = 62.2  # IMX219 camera horizontal FOV in degrees
        self.assumed_ball_distance = 1.0   # Assume golf ball is 1 meter away for simplicity
        self.image_width = 640             # Camera image width in pixels
        self.image_height = 480            # Camera image height in pixels
        
        # Target class to follow
        self.target_class = 'sports ball'
        self.min_confidence = 0.3
        
        rospy.loginfo('YOLO Position Publisher initialized')
        rospy.loginfo('Target class: {} (min confidence: {})'.format(self.target_class, self.min_confidence))
        rospy.loginfo('Publishing to: /object_tracker/current_position')
        
    def bbox_callback(self, msg):
        """Convert YOLO bounding boxes to position estimates"""
        
        # Find all sports ball detections
        sports_balls = []
        for bbox in msg.bounding_boxes:
            if bbox.Class == self.target_class and bbox.probability >= self.min_confidence:
                sports_balls.append(bbox)
        
        if not sports_balls:
            # No valid detections - no position to publish
            return
            
        # Use the detection with highest confidence
        best_detection = max(sports_balls, key=lambda x: x.probability)
        
        # Calculate bounding box center
        center_x = (best_detection.xmin + best_detection.xmax) / 2.0
        center_y = (best_detection.ymin + best_detection.ymax) / 2.0
        
        # Convert pixel coordinates to angular offsets from camera center
        pixel_offset_x = center_x - (self.image_width / 2.0)
        pixel_offset_y = center_y - (self.image_height / 2.0)
        
        # Convert to angles (in degrees as expected by simple_follower)
        angle_per_pixel = self.camera_fov_horizontal / self.image_width
        angle_x_degrees = pixel_offset_x * angle_per_pixel
        angle_y_degrees = pixel_offset_y * angle_per_pixel  # Vertical angle
        
        # Create and publish simple_follower position message
        position_msg = PositionMsg()
        position_msg.angleX = angle_x_degrees  # Horizontal angle in degrees
        position_msg.angleY = angle_y_degrees  # Vertical angle in degrees  
        position_msg.distance = self.assumed_ball_distance  # Distance in meters
        
        self.position_pub.publish(position_msg)
        
        rospy.loginfo('Sports ball detected! Confidence: {:.1f}%, Angles: X={:.2f} deg, Y={:.2f} deg, Distance={:.2f}m'.format(
            best_detection.probability * 100, angle_x_degrees, angle_y_degrees, self.assumed_ball_distance))

if __name__ == '__main__':
    try:
        publisher = YoloPositionPublisher()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo('YOLO Position Publisher stopped')
        pass
