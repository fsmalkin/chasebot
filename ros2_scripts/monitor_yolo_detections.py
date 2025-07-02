#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from yolo_msgs.msg import DetectionArray

class YoloMonitor(Node):
    def __init__(self):
        super().__init__('yolo_monitor')
        
        self.detection_sub = self.create_subscription(
            DetectionArray,
            '/yolo/detections',
            self.detection_callback,
            10
        )
        
        self.get_logger().info('Monitoring YOLO detections on /yolo/detections...')
        
    def detection_callback(self, msg):
        if msg.detections:
            self.get_logger().info(f'=== YOLO Detections: {len(msg.detections)} objects ===')
            for i, detection in enumerate(msg.detections):
                self.get_logger().info(
                    f'  [{i}] {detection.class_name} (ID: {detection.class_id}) '
                    f'conf: {detection.score:.2f} '
                    f'bbox: ({detection.bbox.center.position.x:.0f}, {detection.bbox.center.position.y:.0f})'
                )
                if detection.class_id == 32 or 'ball' in detection.class_name.lower():
                    self.get_logger().info('  ✅ SPORTS BALL DETECTED!')
        else:
            self.get_logger().debug('No detections')

def main(args=None):
    rclpy.init(args=args)
    monitor = YoloMonitor()
    
    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
