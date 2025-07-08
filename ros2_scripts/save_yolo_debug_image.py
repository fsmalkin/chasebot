#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class DebugImageSaver(Node):
    def __init__(self):
        super().__init__('debug_image_saver')
        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            Image,
            '/yolo/dbg_image',
            self.image_callback,
            10)
        self.image_saved = False
        self.get_logger().info('Waiting for YOLO debug image...')

    def image_callback(self, msg):
        if not self.image_saved:
            try:
                cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
                cv2.imwrite('/tmp/yolo_debug_view.png', cv_image)
                self.get_logger().info('Debug image saved to /tmp/yolo_debug_view.png')
                self.image_saved = True
                rclpy.shutdown()
            except Exception as e:
                self.get_logger().error(f'Error saving image: {str(e)}')

def main(args=None):
    rclpy.init(args=args)
    node = DebugImageSaver()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
