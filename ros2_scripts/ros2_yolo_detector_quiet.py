#!/usr/bin/env python3
"""
ROS 2 YOLO Object Detection Node for Golf Ball Detection - Quiet Version
Part of Slice 3.5: Clean YOLO Integration with reduced logging
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from cv_bridge import CvBridge
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import os
from std_msgs.msg import Header, Float32
import time

class YOLODetectorNode(Node):
    def __init__(self):
        super().__init__('yolo_detector_node')
        
        # Initialize CV Bridge
        self.bridge = CvBridge()
        
        # Load YOLO model
        model_path = os.path.expanduser('~/ros2_ws/yolov8m.pt')
        self.get_logger().info(f'Loading YOLO model from: {model_path}')
        try:
            self.model = YOLO(model_path)
            self.get_logger().info('YOLO model loaded successfully')
        except Exception as e:
            self.get_logger().error(f'Failed to load YOLO model: {e}')
            return
        
        # COCO class names (sports ball is class 32)
        self.SPORTS_BALL_CLASS = 32
        self.CONFIDENCE_THRESHOLD = 0.6
        
        # Publishers
        self.debug_image_pub = self.create_publisher(Image, '/yolo/debug_image', 10)
        self.detection_pub = self.create_publisher(Point, '/yolo/ball_position', 10)
        self.confidence_pub = self.create_publisher(Float32, '/yolo/confidence', 10)
        
        # Subscriber
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        # Debug window flag
        self.show_debug_window = True
        self.window_name = 'YOLO Golf Ball Detection'
        
        # Logging control variables
        self.last_log_time = time.time()
        self.log_interval = 5.0  # Log summary every 5 seconds
        self.last_confidence = 0.0
        self.confidence_change_threshold = 0.1  # Log if confidence changes by 10%
        self.detection_count = 0
        self.frame_count = 0
        
        self.get_logger().info('YOLO detection node started (quiet mode)')
        self.get_logger().info(f'Detecting sports balls with confidence > {self.CONFIDENCE_THRESHOLD}')
        self.get_logger().info('Detection summaries will be logged every 5 seconds')
        
    def image_callback(self, msg):
        try:
            self.frame_count += 1
            
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Run YOLO detection
            results = self.model(cv_image)
            
            # Process detections
            detected_balls = []
            
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Check if detection is a sports ball
                        class_id = int(box.cls)
                        confidence = float(box.conf)
                        
                        if class_id == self.SPORTS_BALL_CLASS and confidence > self.CONFIDENCE_THRESHOLD:
                            # Get bounding box coordinates
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            
                            # Calculate center point
                            center_x = (x1 + x2) / 2
                            center_y = (y1 + y2) / 2
                            
                            detected_balls.append({
                                'bbox': (int(x1), int(y1), int(x2), int(y2)),
                                'center': (center_x, center_y),
                                'confidence': confidence
                            })
                            
                            self.detection_count += 1
            
            # Draw bounding boxes on debug image
            debug_image = cv_image.copy()
            for ball in detected_balls:
                x1, y1, x2, y2 = ball['bbox']
                confidence = ball['confidence']
                
                # Draw green rectangle
                cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Add confidence text
                label = f'Golf Ball: {confidence:.2f}'
                cv2.putText(debug_image, label, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Publish debug image
            debug_msg = self.bridge.cv2_to_imgmsg(debug_image, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_image_pub.publish(debug_msg)
            
            # Publish detection data for closest ball
            if detected_balls:
                # Get closest ball (highest confidence)
                closest_ball = max(detected_balls, key=lambda x: x['confidence'])
                
                # Publish position (normalized coordinates)
                position_msg = Point()
                position_msg.x = closest_ball['center'][0] / cv_image.shape[1]  # Normalize to 0-1
                position_msg.y = closest_ball['center'][1] / cv_image.shape[0]  # Normalize to 0-1
                position_msg.z = 0.0
                self.detection_pub.publish(position_msg)
                
                # Publish confidence
                confidence_msg = Float32()
                confidence_msg.data = closest_ball['confidence']
                self.confidence_pub.publish(confidence_msg)
                
                # Log significant confidence changes
                current_confidence = closest_ball['confidence']
                if abs(current_confidence - self.last_confidence) > self.confidence_change_threshold:
                    self.get_logger().info(
                        f'Detection confidence changed: {current_confidence:.2f} '
                        f'(was {self.last_confidence:.2f})'
                    )
                    self.last_confidence = current_confidence
            
            # Show debug window if enabled
            if self.show_debug_window:
                cv2.imshow(self.window_name, debug_image)
                cv2.waitKey(1)
            
            # Periodic summary logging
            current_time = time.time()
            if current_time - self.last_log_time >= self.log_interval:
                avg_detections_per_frame = self.detection_count / max(self.frame_count, 1)
                self.get_logger().info(
                    f'Detection summary: {self.detection_count} detections in '
                    f'{self.frame_count} frames ({avg_detections_per_frame:.2f} per frame)'
                )
                
                # Reset counters
                self.last_log_time = current_time
                self.detection_count = 0
                self.frame_count = 0
                
        except Exception as e:
            self.get_logger().error(f'Error in image callback: {e}')

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = YOLODetectorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
