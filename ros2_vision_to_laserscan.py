#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from cv_bridge import CvBridge
import cv2
import numpy as np
import math

class VisionToLaserScan(Node):
    """
    Converts RGB camera images to laser scan data for Nav2 navigation.
    Designed for IMX219 monocular cameras without depth information.
    """
    
    def __init__(self):
        super().__init__('vision_to_laserscan')
        
        # Publishers and Subscribers
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        self.scan_pub = self.create_publisher(
            LaserScan,
            '/scan',
            10
        )
        
        # Debug visualization publisher
        self.debug_pub = self.create_publisher(
            Image,
            '/vision_to_laserscan/debug',
            10
        )
        
        # CV Bridge
        self.bridge = CvBridge()
        
        # Parameters
        self.declare_parameter('scan_height_ratio', 0.5)  # Which height of image to scan
        self.declare_parameter('num_scan_samples', 360)   # Number of laser scan points
        self.declare_parameter('scan_range_max', 5.0)     # Maximum range in meters
        self.declare_parameter('scan_range_min', 0.1)     # Minimum range in meters
        self.declare_parameter('obstacle_threshold', 100)  # Darkness threshold for obstacles
        
        # Get parameters
        self.scan_height_ratio = self.get_parameter('scan_height_ratio').value
        self.num_scan_samples = self.get_parameter('num_scan_samples').value
        self.scan_range_max = self.get_parameter('scan_range_max').value
        self.scan_range_min = self.get_parameter('scan_range_min').value
        self.obstacle_threshold = self.get_parameter('obstacle_threshold').value
        
        # Camera parameters (typical for IMX219)
        self.horizontal_fov = 62.2 * math.pi / 180  # 62.2 degrees in radians
        
        self.get_logger().info('Vision to LaserScan node initialized')
        self.get_logger().info(f'Scanning at {self.scan_height_ratio*100}% of image height')
        
    def image_callback(self, msg):
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Create laser scan from image
            scan = self.create_scan_from_image(cv_image, msg.header)
            
            # Publish scan
            self.scan_pub.publish(scan)
            
            # Publish debug visualization
            debug_image = self.create_debug_image(cv_image)
            debug_msg = self.bridge.cv2_to_imgmsg(debug_image, "bgr8")
            debug_msg.header = msg.header
            self.debug_pub.publish(debug_msg)
            
        except Exception as e:
            self.get_logger().error(f'Error processing image: {str(e)}')
    
    def create_scan_from_image(self, image, header):
        """
        Convert RGB image to laser scan by detecting obstacles.
        Simple approach: darker pixels = obstacles
        """
        height, width = image.shape[:2]
        scan_row = int(height * self.scan_height_ratio)
        
        # Create laser scan message
        scan = LaserScan()
        scan.header = header
        scan.header.frame_id = 'camera_optical_link'
        
        # Configure scan parameters
        scan.angle_min = -self.horizontal_fov / 2
        scan.angle_max = self.horizontal_fov / 2
        scan.angle_increment = self.horizontal_fov / self.num_scan_samples
        scan.time_increment = 0.0
        scan.scan_time = 0.033  # 30 Hz
        scan.range_min = self.scan_range_min
        scan.range_max = self.scan_range_max
        
        # Convert to grayscale for obstacle detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Extract scan line
        scan_line = gray[scan_row, :]
        
        # Initialize ranges
        scan.ranges = []
        
        # Sample points across the image width
        for i in range(self.num_scan_samples):
            # Map scan index to image column
            col = int(i * width / self.num_scan_samples)
            
            # Get pixel value
            pixel_value = scan_line[col]
            
            # Simple obstacle detection: dark pixels are obstacles
            if pixel_value < self.obstacle_threshold:
                # Estimate distance based on vertical position in image
                # This is a simple heuristic - closer to bottom = closer distance
                distance = self.estimate_distance_from_pixel(scan_row, height)
                scan.ranges.append(float(distance))
            else:
                # No obstacle detected
                scan.ranges.append(float('inf'))
        
        return scan
    
    def estimate_distance_from_pixel(self, row, image_height):
        """
        Simple distance estimation based on pixel position.
        Assumes flat ground and camera mounted at fixed height.
        """
        # Normalize row position (0 = top, 1 = bottom)
        normalized_row = row / image_height
        
        # Simple inverse relationship: lower in image = closer
        # This is a rough approximation
        if normalized_row > 0.9:
            distance = self.scan_range_min
        elif normalized_row < 0.1:
            distance = self.scan_range_max
        else:
            # Linear interpolation
            distance = self.scan_range_max - (normalized_row * (self.scan_range_max - self.scan_range_min))
        
        return max(self.scan_range_min, min(self.scan_range_max, distance))
    
    def create_debug_image(self, image):
        """
        Create debug visualization showing scan line and detected obstacles.
        """
        debug_image = image.copy()
        height, width = image.shape[:2]
        scan_row = int(height * self.scan_height_ratio)
        
        # Draw scan line
        cv2.line(debug_image, (0, scan_row), (width, scan_row), (0, 255, 0), 2)
        
        # Convert to grayscale for obstacle detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scan_line = gray[scan_row, :]
        
        # Mark detected obstacles
        for i in range(0, width, 5):  # Sample every 5 pixels for visualization
            if scan_line[i] < self.obstacle_threshold:
                # Draw red marker for obstacle
                cv2.circle(debug_image, (i, scan_row), 3, (0, 0, 255), -1)
        
        # Add text
        cv2.putText(debug_image, "Vision to LaserScan Debug", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(debug_image, f"Threshold: {self.obstacle_threshold}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return debug_image


def main(args=None):
    rclpy.init(args=args)
    
    vision_to_laserscan = VisionToLaserScan()
    
    try:
        rclpy.spin(vision_to_laserscan)
    except KeyboardInterrupt:
        pass
    finally:
        vision_to_laserscan.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
