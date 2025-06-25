#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from cv_bridge import CvBridge
import cv2
import numpy as np
import math

class VisionToLaserScanHSV(Node):
    """
    Converts RGB camera images to laser scan data for Nav2 navigation.
    Uses HSV color detection to identify green golf balls as obstacles.
    """
    
    def __init__(self):
        super().__init__('vision_to_laserscan_hsv')
        
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
        
        # Parameters for HSV detection (green golf balls)
        self.declare_parameter('hsv_lower_h', 35)
        self.declare_parameter('hsv_upper_h', 85)
        self.declare_parameter('hsv_lower_s', 50)
        self.declare_parameter('hsv_upper_s', 255)
        self.declare_parameter('hsv_lower_v', 50)
        self.declare_parameter('hsv_upper_v', 255)
        
        # Laser scan parameters
        self.declare_parameter('scan_height_ratio', 0.5)
        self.declare_parameter('num_scan_samples', 360)
        self.declare_parameter('scan_range_max', 5.0)
        self.declare_parameter('scan_range_min', 0.1)
        self.declare_parameter('min_obstacle_width', 5)  # Minimum pixels for valid obstacle
        
        # Get parameters
        self.hsv_lower = np.array([
            self.get_parameter('hsv_lower_h').value,
            self.get_parameter('hsv_lower_s').value,
            self.get_parameter('hsv_lower_v').value
        ])
        self.hsv_upper = np.array([
            self.get_parameter('hsv_upper_h').value,
            self.get_parameter('hsv_upper_s').value,
            self.get_parameter('hsv_upper_v').value
        ])
        
        self.scan_height_ratio = self.get_parameter('scan_height_ratio').value
        self.num_scan_samples = self.get_parameter('num_scan_samples').value
        self.scan_range_max = self.get_parameter('scan_range_max').value
        self.scan_range_min = self.get_parameter('scan_range_min').value
        self.min_obstacle_width = self.get_parameter('min_obstacle_width').value
        
        # Camera parameters (typical for IMX219)
        self.horizontal_fov = 62.2 * math.pi / 180  # 62.2 degrees in radians
        
        self.get_logger().info('Vision to LaserScan HSV node initialized')
        self.get_logger().info(f'HSV range: [{self.hsv_lower}] to [{self.hsv_upper}]')
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
        Convert RGB image to laser scan by detecting green golf balls.
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
        
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create mask for green objects
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Extract scan line from mask
        scan_line = mask[scan_row, :]
        
        # Initialize ranges
        scan.ranges = []
        
        # Sample points across the image width
        for i in range(self.num_scan_samples):
            # Map scan index to image column
            col = int(i * width / self.num_scan_samples)
            
            # Check for obstacle in a small window around the column
            window_start = max(0, col - self.min_obstacle_width // 2)
            window_end = min(width, col + self.min_obstacle_width // 2)
            
            # Check if there's a green object in the window
            if np.any(scan_line[window_start:window_end] > 0):
                # Estimate distance based on position and size
                distance = self.estimate_distance_from_position(scan_row, height, col, width)
                scan.ranges.append(float(distance))
            else:
                # No obstacle detected
                scan.ranges.append(float('inf'))
        
        return scan
    
    def estimate_distance_from_position(self, row, image_height, col, image_width):
        """
        Estimate distance based on pixel position.
        For golf balls, we can use a more sophisticated model.
        """
        # Normalize row position (0 = top, 1 = bottom)
        normalized_row = row / image_height
        
        # For golf balls at ground level, use inverse relationship
        # Closer to bottom of image = closer distance
        if normalized_row > 0.8:
            distance = self.scan_range_min + 0.5
        elif normalized_row < 0.3:
            distance = self.scan_range_max
        else:
            # More realistic distance estimation for golf balls
            # Based on typical camera mounting and field of view
            distance = 3.0 - (normalized_row - 0.3) * 4.0
        
        # Also consider horizontal position (objects at edges appear further)
        normalized_col = abs(col - image_width/2) / (image_width/2)
        distance *= (1.0 + 0.2 * normalized_col)
        
        return max(self.scan_range_min, min(self.scan_range_max, distance))
    
    def create_debug_image(self, image):
        """
        Create debug visualization showing scan line and detected obstacles.
        """
        debug_image = image.copy()
        height, width = image.shape[:2]
        scan_row = int(height * self.scan_height_ratio)
        
        # Convert to HSV and create mask
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Draw scan line
        cv2.line(debug_image, (0, scan_row), (width, scan_row), (0, 255, 0), 2)
        
        # Extract scan line from mask
        scan_line = mask[scan_row, :]
        
        # Mark detected green objects
        for i in range(0, width, 5):  # Sample every 5 pixels for visualization
            if scan_line[i] > 0:
                # Draw green marker for detected golf ball
                cv2.circle(debug_image, (i, scan_row), 3, (0, 255, 0), -1)
        
        # Find contours in the mask to highlight golf balls
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Draw contours of detected golf balls
        cv2.drawContours(debug_image, contours, -1, (255, 0, 255), 2)
        
        # Add text
        cv2.putText(debug_image, "Vision to LaserScan HSV", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(debug_image, f"HSV: {self.hsv_lower[0]}-{self.hsv_upper[0]}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(debug_image, f"Scan line at {int(self.scan_height_ratio*100)}%", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return debug_image


def main(args=None):
    rclpy.init(args=args)
    
    vision_to_laserscan = VisionToLaserScanHSV()
    
    try:
        rclpy.spin(vision_to_laserscan)
    except KeyboardInterrupt:
        pass
    finally:
        vision_to_laserscan.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
