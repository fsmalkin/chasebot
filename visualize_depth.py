#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class DepthVisualizer(Node):
    """
    Simple node to visualize depth camera data.
    Shows both RGB and depth images side by side.
    """
    
    def __init__(self):
        super().__init__('depth_visualizer')
        
        # CV Bridge for image conversion
        self.bridge = CvBridge()
        
        # Subscribers
        self.rgb_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.rgb_callback,
            10
        )
        
        self.depth_sub = self.create_subscription(
            Image,
            '/camera/depth/image_raw',
            self.depth_callback,
            10
        )
        
        # Storage for latest images
        self.latest_rgb = None
        self.latest_depth = None
        
        # Create timer for display updates
        self.timer = self.create_timer(0.1, self.display_images)  # 10 Hz
        
        self.get_logger().info('Depth Visualizer started')
        self.get_logger().info('Subscribing to:')
        self.get_logger().info('  RGB: /camera/image_raw')
        self.get_logger().info('  Depth: /camera/depth/image_raw')
        
    def rgb_callback(self, msg):
        """Store latest RGB image."""
        try:
            self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f'RGB conversion error: {str(e)}')
    
    def depth_callback(self, msg):
        """Store latest depth image and log depth info."""
        try:
            # Convert depth image (usually 32FC1 format)
            depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            
            # Log depth statistics
            if depth_image is not None:
                valid_depths = depth_image[depth_image > 0]  # Remove invalid (0) depths
                if len(valid_depths) > 0:
                    min_depth = np.min(valid_depths)
                    max_depth = np.max(valid_depths)
                    mean_depth = np.mean(valid_depths)
                    
                    # Log center pixel depth
                    h, w = depth_image.shape
                    center_depth = depth_image[h//2, w//2]
                    
                    self.get_logger().info(f'Depth stats - Min: {min_depth:.2f}m, Max: {max_depth:.2f}m, '
                                          f'Mean: {mean_depth:.2f}m, Center: {center_depth:.2f}m')
            
            # Convert to 8-bit for visualization
            # Normalize depth to 0-255 range for display
            if depth_image.dtype == np.float32:
                # Clip extreme values and normalize
                depth_clipped = np.clip(depth_image, 0, 10.0)  # Clip to 10m max
                depth_normalized = (depth_clipped / 10.0 * 255).astype(np.uint8)
            else:
                depth_normalized = depth_image
            
            # Apply colormap for better visualization
            self.latest_depth = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
            
        except Exception as e:
            self.get_logger().error(f'Depth conversion error: {str(e)}')
    
    def display_images(self):
        """Display RGB and depth images side by side."""
        if self.latest_rgb is not None and self.latest_depth is not None:
            try:
                # Resize images to same height for side-by-side display
                h = min(self.latest_rgb.shape[0], self.latest_depth.shape[0])
                rgb_resized = cv2.resize(self.latest_rgb, (int(self.latest_rgb.shape[1] * h / self.latest_rgb.shape[0]), h))
                depth_resized = cv2.resize(self.latest_depth, (int(self.latest_depth.shape[1] * h / self.latest_depth.shape[0]), h))
                
                # Combine images horizontally
                combined = np.hstack((rgb_resized, depth_resized))
                
                # Add labels
                cv2.putText(combined, 'RGB Camera', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(combined, 'Depth Camera (Colorized)', (rgb_resized.shape[1] + 10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                # Display
                cv2.imshow('RGB and Depth Camera Feed', combined)
                cv2.waitKey(1)
                
            except Exception as e:
                self.get_logger().error(f'Display error: {str(e)}')
        
        elif self.latest_rgb is not None:
            # Show only RGB if depth not available yet
            cv2.imshow('RGB Camera Only', self.latest_rgb)
            cv2.waitKey(1)
            
        elif self.latest_depth is not None:
            # Show only depth if RGB not available yet
            cv2.imshow('Depth Camera Only', self.latest_depth)
            cv2.waitKey(1)


def main(args=None):
    rclpy.init(args=args)
    
    visualizer = DepthVisualizer()
    
    try:
        rclpy.spin(visualizer)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        visualizer.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
