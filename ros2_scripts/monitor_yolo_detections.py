#!/usr/bin/env python3
"""
Monitor YOLO detections from yolo_ros package
Part of Slice 2: Verify 2D detection is working
"""

import rclpy
from rclpy.node import Node
from yolo_msgs.msg import Detection, DetectionArray
from sensor_msgs.msg import Image


class YoloDetectionMonitor(Node):
    def __init__(self):
        super().__init__('yolo_detection_monitor')
        
        # Subscribe to YOLO detections
        self.detection_sub = self.create_subscription(
            DetectionArray,
            '/yolo/detections',
            self.detection_callback,
            10
        )
        
        # Subscribe to image to check if camera is working
        self.image_sub = self.create_subscription(
            Image,
            '/d415/image_raw',
            self.image_callback,
            1
        )
        
        # Stats tracking
        self.image_received = False
        self.detection_count = 0
        self.ball_detections = []
        
        # Create timer for status updates
        self.timer = self.create_timer(2.0, self.status_update)
        
        self.get_logger().info("YOLO Detection Monitor started")
        self.get_logger().info("Waiting for camera feed on /d415/image_raw...")
        self.get_logger().info("Monitoring detections on /yolo/detections...")
        
    def image_callback(self, msg):
        """Confirm camera feed is working"""
        if not self.image_received:
            self.image_received = True
            self.get_logger().info(f"✅ Camera feed active! Image size: {msg.width}x{msg.height}")
    
    def detection_callback(self, msg):
        """Process YOLO detections"""
        self.detection_count += 1
        
        # Look for sports ball (class 32) detections
        for detection in msg.detections:
            class_name = detection.class_name
            class_id = detection.class_id
            confidence = detection.confidence
            
            # YOLO class 32 is 'sports ball'
            if class_id == 32 or class_name.lower() in ['sports ball', 'ball', 'golf ball']:
                self.ball_detections.append({
                    'class_name': class_name,
                    'class_id': class_id,
                    'confidence': confidence,
                    'bbox': detection.bbox2d
                })
                
                self.get_logger().info(
                    f"⚽ BALL DETECTED! Class: {class_name} (ID: {class_id}), "
                    f"Confidence: {confidence:.2f}, "
                    f"BBox: [{detection.bbox2d.x}, {detection.bbox2d.y}, "
                    f"{detection.bbox2d.width}, {detection.bbox2d.height}]"
                )
    
    def status_update(self):
        """Periodic status update"""
        if not self.image_received:
            self.get_logger().warn("⚠️  No camera feed received yet...")
            return
            
        if self.detection_count == 0:
            self.get_logger().info("📷 Camera active, waiting for detections...")
        else:
            self.get_logger().info(
                f"📊 Status: {self.detection_count} detection messages, "
                f"{len(self.ball_detections)} ball detections"
            )
            
            # Summary of recent ball detections
            if self.ball_detections:
                recent = self.ball_detections[-5:]  # Last 5 detections
                avg_confidence = sum(d['confidence'] for d in recent) / len(recent)
                self.get_logger().info(
                    f"   Recent avg confidence: {avg_confidence:.2f}"
                )


def main(args=None):
    rclpy.init(args=args)
    monitor = YoloDetectionMonitor()
    
    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        monitor.get_logger().info("Shutting down detection monitor...")
    finally:
        # Print final summary
        if monitor.ball_detections:
            monitor.get_logger().info(
                f"\n✅ SLICE 2 SUCCESS: Total ball detections: {len(monitor.ball_detections)}"
            )
        else:
            monitor.get_logger().warn(
                f"\n❌ No ball detections found. Total messages: {monitor.detection_count}"
            )
        
        monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
