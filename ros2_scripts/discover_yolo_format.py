#!/usr/bin/env python3
"""
Slice 2.1: Detection Format Discovery
Subscribes to YOLO detection topics and logs the message format and content
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import Float32
from sensor_msgs.msg import Image
import time

class YOLOFormatDiscoveryNode(Node):
    def __init__(self):
        super().__init__('yolo_format_discovery')
        
        self.get_logger().info('='*60)
        self.get_logger().info('YOLO Detection Format Discovery Node')
        self.get_logger().info('='*60)
        self.get_logger().info('This node will discover what YOLO is publishing')
        self.get_logger().info('')
        
        # Track what we've received
        self.position_received = False
        self.confidence_received = False
        self.debug_image_received = False
        self.start_time = time.time()
        
        # Subscribe to YOLO topics
        self.position_sub = self.create_subscription(
            Point,
            '/yolo/ball_position',
            self.position_callback,
            10
        )
        
        self.confidence_sub = self.create_subscription(
            Float32,
            '/yolo/confidence',
            self.confidence_callback,
            10
        )
        
        self.debug_image_sub = self.create_subscription(
            Image,
            '/yolo/debug_image',
            self.debug_image_callback,
            10
        )
        
        self.get_logger().info('Subscribed to:')
        self.get_logger().info('  - /yolo/ball_position (geometry_msgs/Point)')
        self.get_logger().info('  - /yolo/confidence (std_msgs/Float32)')
        self.get_logger().info('  - /yolo/debug_image (sensor_msgs/Image)')
        self.get_logger().info('')
        self.get_logger().info('Waiting for YOLO detections...')
        self.get_logger().info('-'*60)
        
        # Timer to check topic availability
        self.timer = self.create_timer(5.0, self.check_topics)
        
    def position_callback(self, msg):
        if not self.position_received:
            self.position_received = True
            self.get_logger().info('')
            self.get_logger().info('🎯 POSITION MESSAGE RECEIVED!')
            self.get_logger().info(f'Topic: /yolo/ball_position')
            self.get_logger().info(f'Message Type: {type(msg).__module__}.{type(msg).__name__}')
            self.get_logger().info('Message Fields:')
            self.get_logger().info(f'  - x: {msg.x:.4f} (normalized 0-1)')
            self.get_logger().info(f'  - y: {msg.y:.4f} (normalized 0-1)')
            self.get_logger().info(f'  - z: {msg.z:.4f}')
            self.get_logger().info('')
            self.get_logger().info('NOTE: x,y are normalized image coordinates (0-1 range)')
            self.get_logger().info('      To get pixel coordinates, multiply by image width/height')
            self.get_logger().info('-'*60)
        else:
            # Log periodic updates
            elapsed = time.time() - self.start_time
            if int(elapsed) % 10 == 0:  # Every 10 seconds
                self.get_logger().info(f'Latest position: x={msg.x:.3f}, y={msg.y:.3f}')
    
    def confidence_callback(self, msg):
        if not self.confidence_received:
            self.confidence_received = True
            self.get_logger().info('')
            self.get_logger().info('💯 CONFIDENCE MESSAGE RECEIVED!')
            self.get_logger().info(f'Topic: /yolo/confidence')
            self.get_logger().info(f'Message Type: {type(msg).__module__}.{type(msg).__name__}')
            self.get_logger().info(f'Confidence Value: {msg.data:.4f}')
            self.get_logger().info('-'*60)
        else:
            # Log when confidence changes significantly
            pass
    
    def debug_image_callback(self, msg):
        if not self.debug_image_received:
            self.debug_image_received = True
            self.get_logger().info('')
            self.get_logger().info('📷 DEBUG IMAGE RECEIVED!')
            self.get_logger().info(f'Topic: /yolo/debug_image')
            self.get_logger().info(f'Message Type: {type(msg).__module__}.{type(msg).__name__}')
            self.get_logger().info(f'Image Size: {msg.width}x{msg.height}')
            self.get_logger().info(f'Encoding: {msg.encoding}')
            self.get_logger().info(f'Step: {msg.step} bytes per row')
            self.get_logger().info('-'*60)
    
    def check_topics(self):
        """Check available topics and provide status update"""
        topic_list = self.get_topic_names_and_types()
        
        # Look for vision_msgs topics
        vision_topics = [t for t in topic_list if 'vision_msgs' in str(t[1])]
        if vision_topics:
            self.get_logger().info('')
            self.get_logger().info('🔍 Found vision_msgs topics:')
            for topic, types in vision_topics:
                self.get_logger().info(f'  - {topic}: {types}')
            self.get_logger().info('')
        
        # Status summary
        self.get_logger().info('')
        self.get_logger().info('📊 DISCOVERY STATUS:')
        self.get_logger().info(f'  Position messages: {"✅ Received" if self.position_received else "❌ Not received"}')
        self.get_logger().info(f'  Confidence messages: {"✅ Received" if self.confidence_received else "❌ Not received"}')
        self.get_logger().info(f'  Debug images: {"✅ Received" if self.debug_image_received else "❌ Not received"}')
        
        if not self.position_received:
            self.get_logger().info('')
            self.get_logger().info('⚠️  No detections received yet. Make sure:')
            self.get_logger().info('  1. Simulation is running with camera')
            self.get_logger().info('  2. YOLO detector is running')
            self.get_logger().info('  3. There are objects to detect in view')
        else:
            self.get_logger().info('')
            self.get_logger().info('✅ YOLO detection format discovered!')
            self.get_logger().info('')
            self.get_logger().info('SUMMARY:')
            self.get_logger().info('  - YOLO publishes normalized (0-1) position coordinates')
            self.get_logger().info('  - Position is 2D only (z=0)')
            self.get_logger().info('  - Confidence is published separately')
            self.get_logger().info('  - No 3D information in current implementation')
            self.get_logger().info('')
            self.get_logger().info('Next step: Create bridge to convert this to Nav2 goals')
        
        self.get_logger().info('-'*60)

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = YOLOFormatDiscoveryNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('\nShutting down discovery node...')
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
