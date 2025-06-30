#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection3DArray
from chasebot_msgs.msg import BallDetectionArray
from cv_bridge import CvBridge
import cv2
import numpy as np

class VisionComparisonNode(Node):
    def __init__(self):
        super().__init__('vision_comparison_display')
        
        # Initialize CV bridge
        self.bridge = CvBridge()
        
        # Subscribers
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        self.hsv_detection_sub = self.create_subscription(
            BallDetectionArray,
            '/ball_detections',
            self.hsv_detection_callback,
            10
        )
        
        self.professional_detection_sub = self.create_subscription(
            Detection3DArray,
            '/professional_ball_detections',
            self.professional_detection_callback,
            10
        )
        
        # Publishers
        self.comparison_image_pub = self.create_publisher(
            Image,
            '/vision_comparison_display',
            10
        )
        
        # State variables
        self.latest_image = None
        self.hsv_detections = []
        self.professional_detections = []
        
        self.get_logger().info('Vision Comparison Node started - comparing HSV vs Professional 3D detection')
    
    def image_callback(self, msg):
        """Store latest image for processing"""
        self.latest_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        self.create_comparison_display()
    
    def hsv_detection_callback(self, msg):
        """Handle HSV detection results"""
        self.hsv_detections = msg.detections
        self.get_logger().info(f'HSV detected {len(self.hsv_detections)} balls')
    
    def professional_detection_callback(self, msg):
        """Handle professional 3D detection results"""
        # Filter for sports balls (class_id might vary, check documentation)
        sports_balls = []
        for detection in msg.detections:
            # Look for sports ball detections
            for result in detection.results:
                if hasattr(result, 'hypothesis') and len(result.hypothesis) > 0:
                    # Check if this is a sports ball detection
                    class_id = result.hypothesis[0].class_id
                    score = result.hypothesis[0].score
                    if score > 0.3:  # Confidence threshold
                        sports_balls.append(detection)
                        break
        
        self.professional_detections = sports_balls
        self.get_logger().info(f'Professional detected {len(self.professional_detections)} balls with >30% confidence')
    
    def create_comparison_display(self):
        """Create side-by-side comparison image"""
        if self.latest_image is None:
            return
        
        # Create two copies of the image
        hsv_image = self.latest_image.copy()
        professional_image = self.latest_image.copy()
        
        # Draw HSV detections on left image
        for detection in self.hsv_detections:
            x, y = int(detection.center_x), int(detection.center_y)
            area = int(detection.area)
            
            # Draw circle for detected ball
            cv2.circle(hsv_image, (x, y), 20, (0, 255, 0), 2)
            cv2.putText(hsv_image, f'HSV: Area={area}', (x-50, y-30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Draw professional detections on right image
        for detection in self.professional_detections:
            # Get 2D bounding box from 3D detection
            bbox = detection.bbox
            center_x = int(bbox.center.position.x)
            center_y = int(bbox.center.position.y)
            
            # Get confidence score
            confidence = 0.0
            for result in detection.results:
                if hasattr(result, 'hypothesis') and len(result.hypothesis) > 0:
                    confidence = result.hypothesis[0].score
                    break
            
            # Draw bounding box
            width = int(bbox.size.x)
            height = int(bbox.size.y)
            top_left = (center_x - width//2, center_y - height//2)
            bottom_right = (center_x + width//2, center_y + height//2)
            
            cv2.rectangle(professional_image, top_left, bottom_right, (255, 0, 0), 2)
            cv2.putText(professional_image, f'3D: {confidence:.2f}', 
                       (center_x-40, center_y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # Create side-by-side comparison
        height, width = self.latest_image.shape[:2]
        comparison = np.zeros((height, width * 2, 3), dtype=np.uint8)
        
        # Place images side by side
        comparison[:, :width] = hsv_image
        comparison[:, width:] = professional_image
        
        # Add labels
        cv2.putText(comparison, 'HSV Detection (Green)', (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(comparison, 'Professional 3D Detection (Blue)', (width + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        
        # Add statistics
        cv2.putText(comparison, f'HSV Balls: {len(self.hsv_detections)}', (10, height - 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(comparison, f'3D Balls: {len(self.professional_detections)}', (width + 10, height - 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        # Publish comparison image
        comparison_msg = self.bridge.cv2_to_imgmsg(comparison, 'bgr8')
        self.comparison_image_pub.publish(comparison_msg)


def main(args=None):
    rclpy.init(args=args)
    node = VisionComparisonNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
