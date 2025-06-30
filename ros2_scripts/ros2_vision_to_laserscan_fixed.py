#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from cv_bridge import CvBridge
import cv2
import numpy as np
import math

class VisionToLaserScanImproved(Node):
    """
    Improved version that scans a vertical region instead of just a single line.
    Fixed array indexing for proper laser scan data.
    """
    
    def __init__(self):
        super().__init__('vision_to_laserscan_improved')
        
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
        
        # HSV parameters for green golf balls (matching our working detection)
        self.hsv_lower = np.array([35, 50, 50])
        self.hsv_upper = np.array([85, 255, 255])
        
        # Laser scan parameters
        self.scan_region_top = 0.3  # Start scanning at 30% of image height
        self.scan_region_bottom = 0.8  # End scanning at 80% of image height
        self.num_scan_samples = 360
        self.scan_range_max = 5.0
        self.scan_range_min = 0.1
        self.min_obstacle_pixels = 10  # Minimum pixels for valid obstacle
        
        # Camera parameters
        self.horizontal_fov = 62.2 * math.pi / 180  # 62.2 degrees in radians
        
        self.get_logger().info('Improved Vision to LaserScan node initialized')
        self.get_logger().info(f'HSV range: {self.hsv_lower} to {self.hsv_upper}')
        self.get_logger().info(f'Scanning region: {self.scan_region_top*100}% to {self.scan_region_bottom*100}% of image height')
        
        self.frame_count = 0
        
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
            
            self.frame_count += 1
            
        except Exception as e:
            self.get_logger().error(f'Error processing image: {str(e)}')
    
    def create_scan_from_image(self, image, header):
        """
        Convert RGB image to laser scan by detecting green golf balls in a vertical region.
        """
        height, width = image.shape[:2]
        scan_top = int(height * self.scan_region_top)
        scan_bottom = int(height * self.scan_region_bottom)
        
        # Create laser scan message
        scan = LaserScan()
        scan.header = header
        scan.header.frame_id = 'base_link'
        
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
        
        # Extract scan region from mask
        scan_region = mask[scan_top:scan_bottom, :]
        
        # Initialize ranges with infinity (no obstacle)
        scan.ranges = [float('inf')] * self.num_scan_samples
        
        # Log detection info periodically
        total_green_pixels = np.sum(mask > 0)
        if self.frame_count % 150 == 0:  # Every 5 seconds at 30Hz
            self.get_logger().info(f'Total green pixels in image: {total_green_pixels}')
        
        # Process each column in the image
        obstacles_found = 0
        closest_distance = float('inf')
        
        for col in range(width):
            # Check for obstacle in the vertical region at this column
            column_slice = scan_region[:, col]
            green_pixel_count = np.sum(column_slice > 0)
            
            # If we have enough green pixels in this column, there's an obstacle
            if green_pixel_count >= self.min_obstacle_pixels:
                # Find the lowest (closest) green pixel
                green_indices = np.where(column_slice > 0)[0]
                if len(green_indices) > 0:
                    lowest_pixel = np.max(green_indices)  # Max because bottom is higher index
                    # Convert to full image coordinates
                    pixel_row = scan_top + lowest_pixel
                    
                    # Estimate distance based on position
                    distance = self.estimate_distance_from_position(pixel_row, height, col, width)
                    
                    # Calculate the angle for this column
                    # Column 0 = left edge = angle_min
                    # Column width-1 = right edge = angle_max
                    normalized_col = col / (width - 1)
                    angle = scan.angle_min + normalized_col * (scan.angle_max - scan.angle_min)
                    
                    # Calculate the laser scan index for this angle
                    scan_index = int((angle - scan.angle_min) / scan.angle_increment)
                    
                    # Ensure index is within bounds
                    if 0 <= scan_index < self.num_scan_samples:
                        # Only update if this is closer than existing reading
                        if distance < scan.ranges[scan_index]:
                            scan.ranges[scan_index] = float(distance)
                            obstacles_found += 1
                            closest_distance = min(closest_distance, distance)
        
        # Log detection results periodically
        if obstacles_found > 0 and self.frame_count % 150 == 0:
            self.get_logger().info(f'Detected obstacles in {obstacles_found} laser scan points')
            self.get_logger().info(f'Closest obstacle at: {closest_distance:.2f}m')
            
            # Debug: show some non-inf values
            non_inf_indices = [i for i, r in enumerate(scan.ranges) if r != float('inf')]
            if len(non_inf_indices) > 0:
                sample_indices = non_inf_indices[:5]  # Show first 5
                self.get_logger().info(f'Sample scan indices with obstacles: {sample_indices}')
                sample_values = [scan.ranges[i] for i in sample_indices]
                self.get_logger().info(f'Sample distances: {[f"{v:.2f}" for v in sample_values]}')
        
        return scan
    
    def estimate_distance_from_position(self, row, image_height, col, image_width):
        """
        Estimate distance based on pixel position.
        Golf ball at bottom of image = closer
        """
        # Normalize row position (0 = top, 1 = bottom)
        normalized_row = row / image_height
        
        # Simple linear model for now
        # Bottom of scan region (0.8) = 0.5m
        # Top of scan region (0.3) = 3.0m
        if normalized_row >= 0.8:
            distance = 0.5
        elif normalized_row <= 0.3:
            distance = 3.0
        else:
            # Linear interpolation
            distance = 3.0 - (normalized_row - 0.3) * (2.5 / 0.5)
        
        # Clamp to valid range
        return max(self.scan_range_min, min(self.scan_range_max, distance))
    
    def create_debug_image(self, image):
        """
        Create debug visualization showing scan region and detected obstacles.
        """
        debug_image = image.copy()
        height, width = image.shape[:2]
        scan_top = int(height * self.scan_region_top)
        scan_bottom = int(height * self.scan_region_bottom)
        
        # Convert to HSV and create mask
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Draw scan region boundaries
        cv2.line(debug_image, (0, scan_top), (width, scan_top), (0, 255, 0), 2)
        cv2.line(debug_image, (0, scan_bottom), (width, scan_bottom), (0, 255, 0), 2)
        
        # Highlight detected green areas in scan region
        scan_region_mask = np.zeros_like(mask)
        scan_region_mask[scan_top:scan_bottom, :] = mask[scan_top:scan_bottom, :]
        
        # Find contours in the scan region
        contours, _ = cv2.findContours(scan_region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Draw contours
        cv2.drawContours(debug_image, contours, -1, (255, 0, 255), 2)
        
        # Mark detected columns with vertical lines
        for i in range(0, width, 10):  # Sample every 10 pixels for visualization
            column_slice = scan_region_mask[scan_top:scan_bottom, i]
            if np.sum(column_slice > 0) >= self.min_obstacle_pixels:
                cv2.line(debug_image, (i, scan_top), (i, scan_bottom), (0, 255, 255), 1)
        
        # Add text
        cv2.putText(debug_image, "Vision to LaserScan (Fixed)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(debug_image, f"Green pixels: {np.sum(mask > 0)}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(debug_image, f"Scan region: {int(self.scan_region_top*100)}%-{int(self.scan_region_bottom*100)}%", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return debug_image


def main(args=None):
    rclpy.init(args=args)
    
    vision_to_laserscan = VisionToLaserScanImproved()
    
    try:
        rclpy.spin(vision_to_laserscan)
    except KeyboardInterrupt:
        pass
    finally:
        vision_to_laserscan.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
