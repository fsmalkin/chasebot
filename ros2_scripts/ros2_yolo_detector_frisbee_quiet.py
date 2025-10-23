#!/usr/bin/env python3
"""
ROS 2 YOLO Frisbee Detection Node - Quiet Version
Accepts frisbee detections (class 29) with reduced logging
Only logs summaries every 5 seconds instead of every detection
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

class YOLOFrisbeeDetectorNode(Node):
    def __init__(self):
        super().__init__('yolo_frisbee_detector')
        
        # Declare parameters
        self.declare_parameter('input_topic', '/d415/color/image_raw')
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('log_interval', 5.0)  # Log summary interval in seconds
        
        # Get parameters
        input_topic = self.get_parameter('input_topic').value
        self.CONFIDENCE_THRESHOLD = self.get_parameter('confidence_threshold').value
        self.log_interval = self.get_parameter('log_interval').value
        
        # Initialize CV Bridge
        self.bridge = CvBridge()
        
        # Load YOLO model
        model_path = os.path.expanduser('~/ros2_ws/yolov8m.pt')
        if not os.path.exists(model_path):
            model_path = os.path.expanduser('~/ros2_ws/src/chasebot_description/yolov8m.pt')
        if not os.path.exists(model_path):
            model_path = 'yolov8m.pt'
            
        self.get_logger().info(f'Loading YOLO model from: {model_path}')
        try:
            self.model = YOLO(model_path)
            self.get_logger().info('YOLO model loaded successfully')
        except Exception as e:
            self.get_logger().error(f'Failed to load YOLO model: {e}')
            return
        
        # COCO class for frisbee (our simulated balls appear as frisbees)
        self.FRISBEE_CLASS = 29
        
        # Publishers
        self.debug_image_pub = self.create_publisher(Image, '/yolo/debug_image', 10)
        self.detection_pub = self.create_publisher(Point, '/yolo/ball_position', 10)
        self.confidence_pub = self.create_publisher(Float32, '/yolo/confidence', 10)
        
        # Subscriber
        self.image_sub = self.create_subscription(
            Image,
            input_topic,
            self.image_callback,
            10
        )
        
        # Debug window
        self.window_name = 'YOLO Ball Detection (Frisbee) - Quiet'
        
        # Logging control variables
        self.last_log_time = time.time()
        self.frame_count = 0
        self.detection_count = 0
        self.frames_with_detection = 0
        self.last_confidence = 0.0
        self.confidence_change_threshold = 0.1  # Log if confidence changes by 10%
        self.max_confidence_seen = 0.0
        self.min_confidence_seen = 1.0
        
        self.get_logger().info('='*50)
        self.get_logger().info('YOLO Ball Detection Node Started (Quiet Mode)')
        self.get_logger().info(f'Subscribing to: {input_topic}')
        self.get_logger().info(f'Confidence threshold: {self.CONFIDENCE_THRESHOLD}')
        self.get_logger().info(f'Looking for: Frisbee (class {self.FRISBEE_CLASS})')
        self.get_logger().info(f'Summaries every {self.log_interval} seconds')
        self.get_logger().info('='*50)
        
    def image_callback(self, msg):
        try:
            self.frame_count += 1
            
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Run YOLO detection
            results = self.model(cv_image, verbose=False)
            
            # Process detections
            detected_balls = []
            
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get detection info
                        class_id = int(box.cls)
                        confidence = float(box.conf)
                        
                        # Check if detection is a frisbee with sufficient confidence
                        if class_id == self.FRISBEE_CLASS and confidence >= self.CONFIDENCE_THRESHOLD:
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
                            
                            # Update confidence statistics
                            self.max_confidence_seen = max(self.max_confidence_seen, confidence)
                            self.min_confidence_seen = min(self.min_confidence_seen, confidence)
            
            # Track frames with detections
            if detected_balls:
                self.frames_with_detection += 1
            
            # Draw debug image
            debug_image = cv_image.copy()
            
            # Draw detected balls
            for ball in detected_balls:
                x1, y1, x2, y2 = ball['bbox']
                confidence = ball['confidence']
                
                # Draw green rectangle with thicker lines
                cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
                # Draw center point
                center = (int(ball['center'][0]), int(ball['center'][1]))
                cv2.circle(debug_image, center, 5, (0, 0, 255), -1)
                
                # Add confidence text with background
                label = f'Ball (Frisbee): {confidence:.2f}'
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(debug_image, 
                             (x1, y1 - label_size[1] - 10),
                             (x1 + label_size[0], y1),
                             (0, 255, 0), -1)
                cv2.putText(debug_image, label, (x1, y1 - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            
            # Add status info
            status_color = (0, 255, 0) if detected_balls else (0, 0, 255)
            cv2.putText(debug_image, f'Frame: {self.frame_count}', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(debug_image, f'Balls Detected: {len(detected_balls)}', (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            cv2.putText(debug_image, f'Threshold: {self.CONFIDENCE_THRESHOLD}', (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(debug_image, 'Quiet mode - reduced logging', (10, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # Publish debug image
            debug_msg = self.bridge.cv2_to_imgmsg(debug_image, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_image_pub.publish(debug_msg)
            
            # Publish detection data for highest confidence ball
            if detected_balls:
                # Get highest confidence ball
                best_ball = max(detected_balls, key=lambda x: x['confidence'])
                
                # Publish normalized position (0-1 range)
                position_msg = Point()
                position_msg.x = best_ball['center'][0] / cv_image.shape[1]
                position_msg.y = best_ball['center'][1] / cv_image.shape[0]
                position_msg.z = 0.0
                self.detection_pub.publish(position_msg)
                
                # Publish confidence
                confidence_msg = Float32()
                confidence_msg.data = best_ball['confidence']
                self.confidence_pub.publish(confidence_msg)
                
                # Log significant confidence changes only
                current_confidence = best_ball['confidence']
                if abs(current_confidence - self.last_confidence) > self.confidence_change_threshold:
                    self.get_logger().info(
                        f'Confidence changed significantly: {current_confidence:.3f} '
                        f'(was {self.last_confidence:.3f})'
                    )
                    self.last_confidence = current_confidence
            
            # Show debug window
            cv2.imshow(self.window_name, debug_image)
            key = cv2.waitKey(1)
            
            # Allow threshold adjustment with keys
            if key == ord('+') or key == ord('='):
                self.CONFIDENCE_THRESHOLD = min(0.9, self.CONFIDENCE_THRESHOLD + 0.05)
                self.get_logger().info(f'Increased threshold to: {self.CONFIDENCE_THRESHOLD:.2f}')
            elif key == ord('-'):
                self.CONFIDENCE_THRESHOLD = max(0.1, self.CONFIDENCE_THRESHOLD - 0.05)
                self.get_logger().info(f'Decreased threshold to: {self.CONFIDENCE_THRESHOLD:.2f}')
            elif key == ord('q'):
                self.get_logger().info('User requested quit')
                rclpy.shutdown()
            
            # Periodic summary logging
            current_time = time.time()
            if current_time - self.last_log_time >= self.log_interval:
                if self.frame_count > 0:
                    detection_rate = (self.frames_with_detection / self.frame_count) * 100
                    avg_detections_per_frame = self.detection_count / self.frame_count
                    
                    self.get_logger().info('='*50)
                    self.get_logger().info(
                        f'📊 Detection Summary ({self.log_interval}s interval):'
                    )
                    self.get_logger().info(
                        f'   Frames processed: {self.frame_count}'
                    )
                    self.get_logger().info(
                        f'   Total detections: {self.detection_count} '
                        f'({avg_detections_per_frame:.1f} per frame)'
                    )
                    self.get_logger().info(
                        f'   Detection rate: {detection_rate:.1f}% of frames had detections'
                    )
                    if self.detection_count > 0:
                        self.get_logger().info(
                            f'   Confidence range: {self.min_confidence_seen:.3f} - {self.max_confidence_seen:.3f}'
                        )
                    self.get_logger().info('='*50)
                
                # Reset counters
                self.last_log_time = current_time
                self.frame_count = 0
                self.detection_count = 0
                self.frames_with_detection = 0
                self.max_confidence_seen = 0.0
                self.min_confidence_seen = 1.0
                
        except Exception as e:
            self.get_logger().error(f'Error in image callback: {e}')
            import traceback
            self.get_logger().error(traceback.format_exc())

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = YOLOFrisbeeDetectorNode()
        node.get_logger().info('Press +/- to adjust confidence threshold, Q to quit')
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
