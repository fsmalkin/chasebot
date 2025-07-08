#!/usr/bin/env python3
"""
ROS 2 YOLO Object Detection Node for Golf Ball Detection - Fixed Version
Corrects topic subscription and lowers confidence threshold
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

class YOLODetectorNode(Node):
    def __init__(self):
        super().__init__('yolo_detector_node')
        
        # Declare parameters
        self.declare_parameter('input_topic', '/d415/image_raw')  # Fixed: correct camera topic
        self.declare_parameter('confidence_threshold', 0.01)  # Lower threshold for debugging
        self.declare_parameter('debug_all_classes', True)  # Debug option to see all detections
        
        # Get parameters
        input_topic = self.get_parameter('input_topic').value
        self.CONFIDENCE_THRESHOLD = self.get_parameter('confidence_threshold').value
        self.debug_all_classes = self.get_parameter('debug_all_classes').value
        
        # Initialize CV Bridge
        self.bridge = CvBridge()
        
        # Load YOLO model
        model_path = os.path.expanduser('~/ros2_ws/yolov8m.pt')
        if not os.path.exists(model_path):
            # Try alternative path
            model_path = os.path.expanduser('~/ros2_ws/src/chasebot_description/yolov8m.pt')
        if not os.path.exists(model_path):
            # Try current directory
            model_path = 'yolov8m.pt'
            
        self.get_logger().info(f'Loading YOLO model from: {model_path}')
        try:
            self.model = YOLO(model_path)
            self.get_logger().info('YOLO model loaded successfully')
        except Exception as e:
            self.get_logger().error(f'Failed to load YOLO model: {e}')
            return
        
        # COCO class names (sports ball is class 32)
        self.SPORTS_BALL_CLASS = 32
        
        # Publishers
        self.debug_image_pub = self.create_publisher(Image, '/yolo/debug_image', 10)
        self.detection_pub = self.create_publisher(Point, '/yolo/ball_position', 10)
        self.confidence_pub = self.create_publisher(Float32, '/yolo/confidence', 10)
        
        # Subscriber - Fixed to use correct topic
        self.image_sub = self.create_subscription(
            Image,
            input_topic,
            self.image_callback,
            10
        )
        
        # Debug window flag
        self.show_debug_window = True
        self.window_name = 'YOLO Golf Ball Detection'
        
        # Frame counter for periodic logging
        self.frame_count = 0
        
        self.get_logger().info('YOLO detection node started')
        self.get_logger().info(f'Subscribing to: {input_topic}')
        self.get_logger().info(f'Detecting sports balls with confidence > {self.CONFIDENCE_THRESHOLD}')
        self.get_logger().info(f'Debug all classes: {self.debug_all_classes}')
        
    def image_callback(self, msg):
        try:
            self.frame_count += 1
            
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Log every 30 frames
            if self.frame_count % 30 == 0:
                self.get_logger().info(f'Processing frame {self.frame_count}, image shape: {cv_image.shape}')
            
            # Run YOLO detection
            results = self.model(cv_image)
            
            # Process detections
            detected_balls = []
            all_detections = []
            
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get detection info
                        class_id = int(box.cls)
                        confidence = float(box.conf)
                        
                        # Get bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        
                        # Store all detections if debug mode
                        if self.debug_all_classes and confidence > self.CONFIDENCE_THRESHOLD:
                            all_detections.append({
                                'class_id': class_id,
                                'class_name': self.model.names[class_id],
                                'confidence': confidence,
                                'bbox': (int(x1), int(y1), int(x2), int(y2))
                            })
                        
                        # Check if detection is a sports ball
                        if class_id == self.SPORTS_BALL_CLASS and confidence > self.CONFIDENCE_THRESHOLD:
                            # Calculate center point
                            center_x = (x1 + x2) / 2
                            center_y = (y1 + y2) / 2
                            
                            detected_balls.append({
                                'bbox': (int(x1), int(y1), int(x2), int(y2)),
                                'center': (center_x, center_y),
                                'confidence': confidence
                            })
                            
                            # Log detection
                            self.get_logger().info(
                                f'Golf ball detected! Confidence: {confidence:.2f}, '
                                f'Center: ({center_x:.0f}, {center_y:.0f})'
                            )
            
            # Log all detections in debug mode
            if self.debug_all_classes and all_detections and self.frame_count % 30 == 0:
                self.get_logger().info(f'All detections in frame {self.frame_count}:')
                for det in all_detections:
                    self.get_logger().info(f'  - {det["class_name"]} (ID: {det["class_id"]}): confidence {det["confidence"]:.3f}')
            
            # Draw bounding boxes on debug image
            debug_image = cv_image.copy()
            
            # Draw all detections in debug mode
            if self.debug_all_classes:
                for det in all_detections:
                    x1, y1, x2, y2 = det['bbox']
                    # Draw in blue for non-ball objects
                    cv2.rectangle(debug_image, (x1, y1), (x2, y2), (255, 0, 0), 1)
                    label = f'{det["class_name"]}: {det["confidence"]:.2f}'
                    cv2.putText(debug_image, label, (x1, y1 - 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
            
            # Draw detected balls
            for ball in detected_balls:
                x1, y1, x2, y2 = ball['bbox']
                confidence = ball['confidence']
                
                # Draw green rectangle
                cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Add confidence text
                label = f'Golf Ball: {confidence:.2f}'
                cv2.putText(debug_image, label, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Add frame info
            cv2.putText(debug_image, f'Frame: {self.frame_count}', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(debug_image, f'Detections: {len(all_detections)}', (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
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
            
            # Show debug window if enabled
            if self.show_debug_window:
                cv2.imshow(self.window_name, debug_image)
                cv2.waitKey(1)
                
        except Exception as e:
            self.get_logger().error(f'Error in image callback: {e}')
            import traceback
            self.get_logger().error(traceback.format_exc())

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
