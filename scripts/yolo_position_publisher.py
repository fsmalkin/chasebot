#!/usr/bin/env python

import rospy
from darknet_ros_msgs.msg import BoundingBoxes
from geometry_msgs.msg import PointStamped
import math

class YoloPositionPublisher:
    def __init__(self):
        rospy.init_node('yolo_position_publisher', anonymous=True)
        
        # Publishers and subscribers
        self.position_pub = rospy.Publisher('/object_tracker/current_position', PointStamped, queue_size=10)
        self.bbox_sub = rospy.Subscriber('/darknet_ros/bounding_boxes', BoundingBoxes, self.bbox_callback)
        
        # Parameters for position calculation
        self.camera_fov_horizontal = 62.2  # IMX219 camera horizontal FOV in degrees
        self.assumed_ball_distance = 1.0   # Assume golf ball is 1 meter away for simplicity
        self.image_width = 640             # Camera image width in pixels
        self.image_height = 480            # Camera image height in pixels
        
        # Target class to follow
        self.target_class = "sports ball"
        self.min_confidence = 0.3
        
        rospy.loginfo("YOLO Position Publisher initialized")
        rospy.loginfo("Target class: {} (min confidence: {})".format(self.target_class, self.min_confidence))
        rospy.loginfo("Publishing to: /object_tracker/current_position")
        
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
        
        # Convert to angles (simplified perspective projection)
        angle_per_pixel = self.camera_fov_horizontal / self.image_width
        angle_x = pixel_offset_x * angle_per_pixel * (math.pi / 180.0)  # Convert to radians
        
        # Calculate 3D position assuming object is at fixed distance
        # In robot frame: x=forward, y=left, z=up
        pos_x = self.assumed_ball_distance * math.cos(angle_x)  # Forward distance
        pos_y = self.assumed_ball_distance * math.sin(angle_x)  # Left/right offset
        pos_z = 0.0  # Assume ball is on ground level
        
        # Create and publish position message
        position_msg = PointStamped()
        position_msg.header.stamp = rospy.Time.now()
        position_msg.header.frame_id = "base_link"  # Robot coordinate frame
        position_msg.point.x = pos_x
        position_msg.point.y = pos_y
        position_msg.point.z = pos_z
        
        self.position_pub.publish(position_msg)
        
        rospy.loginfo("Sports ball detected! Confidence: {:.1f}%, Position: x={:.2f}, y={:.2f}, z={:.2f}".format(
            best_detection.probability * 100, pos_x, pos_y, pos_z))

if __name__ == '__main__':
    try:
        publisher = YoloPositionPublisher()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("YOLO Position Publisher stopped")
        pass
