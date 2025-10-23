#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from yolo_msgs.msg import DetectionArray
import json

class YOLOAnalyzer(Node):
    def __init__(self):
        super().__init__('yolo_analyzer')
        self.subscription = self.create_subscription(
            DetectionArray,
            '/yolo/detections',
            self.detection_callback,
            10)
        self.detection_count = 0
        self.get_logger().info('YOLO Analyzer started - analyzing all detections...')

    def detection_callback(self, msg):
        self.detection_count += 1
        
        if msg.detections:
            self.get_logger().info(f'Frame {self.detection_count}: {len(msg.detections)} detections')
            for i, det in enumerate(msg.detections):
                self.get_logger().info(f'  Detection {i}: class={det.class_id}, '
                                     f'name={det.class_name}, confidence={det.score:.3f}, '
                                     f'bbox=[{det.bbox.center.position.x:.3f}, '
                                     f'{det.bbox.center.position.y:.3f}]')
        else:
            if self.detection_count % 10 == 0:  # Log every 10th frame to avoid spam
                self.get_logger().info(f'Frame {self.detection_count}: No detections')

def main(args=None):
    rclpy.init(args=args)
    node = YOLOAnalyzer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
