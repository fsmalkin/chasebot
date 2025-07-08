#!/usr/bin/env python3
"""
Simple script to test camera topic and verify images are being published
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import time

class CameraTopicTester(Node):
    def __init__(self):
        super().__init__('camera_topic_tester')
        
        self.get_logger().info('Starting camera topic tester...')
        
        # Check both possible topics
        self.topics_to_check = ['/d415/image_raw', '/camera/image_raw']
        self.subscribers = {}
        self.message_counts = {}
        self.last_message_time = {}
        
        # Create subscribers for each topic
        for topic in self.topics_to_check:
            self.message_counts[topic] = 0
            self.last_message_time[topic] = None
            self.subscribers[topic] = self.create_subscription(
                Image,
                topic,
                lambda msg, t=topic: self.image_callback(msg, t),
                10
            )
            self.get_logger().info(f'Subscribed to: {topic}')
        
        # Create timer for periodic status reports
        self.timer = self.create_timer(2.0, self.status_report)
        
    def image_callback(self, msg, topic):
        self.message_counts[topic] += 1
        self.last_message_time[topic] = time.time()
        
        # Log first message details
        if self.message_counts[topic] == 1:
            self.get_logger().info(f'First message received on {topic}!')
            self.get_logger().info(f'  - Width: {msg.width}')
            self.get_logger().info(f'  - Height: {msg.height}')
            self.get_logger().info(f'  - Encoding: {msg.encoding}')
            self.get_logger().info(f'  - Frame ID: {msg.header.frame_id}')
    
    def status_report(self):
        self.get_logger().info('=== Camera Topic Status ===')
        current_time = time.time()
        
        for topic in self.topics_to_check:
            count = self.message_counts[topic]
            if count > 0:
                last_time = self.last_message_time[topic]
                time_since_last = current_time - last_time if last_time else 0
                self.get_logger().info(f'{topic}: {count} messages received (last: {time_since_last:.1f}s ago)')
            else:
                self.get_logger().info(f'{topic}: No messages received')

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = CameraTopicTester()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
