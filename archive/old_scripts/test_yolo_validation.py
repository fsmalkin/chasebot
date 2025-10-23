#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from yolo_msgs.msg import DetectionArray
import time

class YoloValidationTest(Node):
    def __init__(self):
        super().__init__('yolo_validation_test')
        
        # Subscribe to YOLO detections
        self.detection_sub = self.create_subscription(
            DetectionArray,
            '/yolo/detections',
            self.detection_callback,
            10
        )
        
        self.detections_received = False
        self.sports_ball_detected = False
        self.start_time = time.time()
        
        self.get_logger().info('YOLO Validation Test Started - Listening for detections...')
        
        # Create a timer to check status
        self.timer = self.create_timer(2.0, self.check_status)
        
    def detection_callback(self, msg):
        """Process YOLO detections"""
        self.detections_received = True
        
        if msg.detections:
            self.get_logger().info(f'Received {len(msg.detections)} detections!')
            
            for detection in msg.detections:
                self.get_logger().info(f'  - Class: {detection.class_name} (ID: {detection.class_id}), Confidence: {detection.score:.2f}')
                
                # Check if sports ball detected
                if detection.class_id == 32 or 'ball' in detection.class_name.lower():
                    self.sports_ball_detected = True
                    self.get_logger().info('✅ SPORTS BALL DETECTED! Task 1 UAT Success!')
        
    def check_status(self):
        """Periodic status check"""
        elapsed = time.time() - self.start_time
        
        if not self.detections_received:
            self.get_logger().info(f'Waiting for detections... ({elapsed:.0f}s)')
        elif self.sports_ball_detected:
            self.get_logger().info('✅ Task 1 Complete: YOLO is detecting sports balls!')
            rclpy.shutdown()
        else:
            self.get_logger().info('Detections received but no sports ball found yet...')

def main(args=None):
    rclpy.init(args=args)
    node = YoloValidationTest()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.sports_ball_detected:
            print('\n✅ TASK 1 UAT PASSED: YOLO detection validated!')
        else:
            print('\n❌ No sports ball detected during test')
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
