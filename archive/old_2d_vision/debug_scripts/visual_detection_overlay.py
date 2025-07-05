#!/usr/bin/env python3
"""
Visual Detection Overlay
Overlays detection information on camera feed for debugging
Shows ball detection boxes, confidence, and calculated positions
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from geometry_msgs.msg import Point
from std_msgs.msg import Float32
from cv_bridge import CvBridge
import cv2
import numpy as np

class VisualDetectionOverlay(Node):
    def __init__(self):
        super().__init__('visual_detection_overlay')
        
        # OpenCV bridge
        self.bridge = CvBridge()
        
        # Detection data
        self.ball_position = None
        self.confidence = 0.0
        self.last_detection_time = None
        
        # Image dimensions
        self.image_width = None
        self.image_height = None
        
        # Subscriptions
        self.image_sub = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 10)
        
        self.ball_pos_sub = self.create_subscription(
            Point, '/yolo/ball_position', self.ball_position_callback, 10)
        
        self.confidence_sub = self.create_subscription(
            Float32, '/yolo/confidence', self.confidence_callback, 10)
        
        # Publisher for annotated image
        self.overlay_pub = self.create_publisher(
            Image, '/detection/overlay', 10)
        
        self.compressed_pub = self.create_publisher(
            CompressedImage, '/detection/overlay/compressed', 10)
        
        self.get_logger().info("Visual Detection Overlay Started")
        self.get_logger().info("Publishing to /detection/overlay and /detection/overlay/compressed")

    def ball_position_callback(self, msg):
        """Update ball position"""
        self.ball_position = msg
        self.last_detection_time = self.get_clock().now()

    def confidence_callback(self, msg):
        """Update detection confidence"""
        self.confidence = msg.data

    def image_callback(self, msg):
        """Process image and add overlay"""
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            self.image_height, self.image_width = cv_image.shape[:2]
            
            # Create overlay
            overlay = cv_image.copy()
            
            # Add grid lines for reference (every 10%)
            self.draw_grid(overlay)
            
            # Add detection information
            if self.ball_position and self.confidence > 0:
                self.draw_detection(overlay)
            
            # Add info panel
            self.draw_info_panel(overlay)
            
            # Publish annotated image
            overlay_msg = self.bridge.cv2_to_imgmsg(overlay, "bgr8")
            overlay_msg.header = msg.header
            self.overlay_pub.publish(overlay_msg)
            
            # Also publish compressed version
            _, buffer = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
            compressed_msg = CompressedImage()
            compressed_msg.header = msg.header
            compressed_msg.format = "jpeg"
            compressed_msg.data = buffer.tobytes()
            self.compressed_pub.publish(compressed_msg)
            
        except Exception as e:
            self.get_logger().error(f"Failed to process image: {e}")

    def draw_grid(self, image):
        """Draw reference grid on image"""
        # Vertical lines every 10%
        for i in range(1, 10):
            x = int(self.image_width * i / 10)
            cv2.line(image, (x, 0), (x, self.image_height), (128, 128, 128), 1)
            if i == 5:  # Center line
                cv2.line(image, (x, 0), (x, self.image_height), (255, 255, 0), 2)
        
        # Horizontal lines every 10%
        for i in range(1, 10):
            y = int(self.image_height * i / 10)
            cv2.line(image, (0, y), (self.image_width, y), (128, 128, 128), 1)
            if i == 5:  # Center line
                cv2.line(image, (0, y), (self.image_width, y), (255, 255, 0), 2)

    def draw_detection(self, image):
        """Draw ball detection overlay"""
        if self.ball_position is None:
            return
        
        # Convert normalized coordinates to pixels
        px = int(self.ball_position.x * self.image_width)
        py = int(self.ball_position.y * self.image_height)
        
        # Detection age
        if self.last_detection_time:
            age = (self.get_clock().now() - self.last_detection_time).nanoseconds / 1e9
            if age > 1.0:  # Stale detection
                return
        
        # Choose color based on confidence
        if self.confidence > 0.8:
            color = (0, 255, 0)  # Green - high confidence
        elif self.confidence > 0.6:
            color = (0, 165, 255)  # Orange - medium confidence
        else:
            color = (0, 0, 255)  # Red - low confidence
        
        # Draw crosshair at detection center
        cv2.drawMarker(image, (px, py), color, cv2.MARKER_CROSS, 20, 2)
        
        # Draw bounding box (estimated from typical YOLO detection)
        box_size = 40  # Approximate box size
        cv2.rectangle(image, 
                     (px - box_size, py - box_size),
                     (px + box_size, py + box_size),
                     color, 2)
        
        # Add confidence label
        label = f"Ball: {self.confidence:.1%}"
        cv2.putText(image, label, (px - box_size, py - box_size - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Add coordinate info
        coord_text = f"({self.ball_position.x:.3f}, {self.ball_position.y:.3f})"
        cv2.putText(image, coord_text, (px - box_size, py + box_size + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    def draw_info_panel(self, image):
        """Draw information panel"""
        # Create semi-transparent overlay for info panel
        panel_height = 100
        panel = np.zeros((panel_height, self.image_width, 3), dtype=np.uint8)
        panel.fill(40)  # Dark gray background
        
        # Add to top of image with transparency
        y_offset = 0
        image[y_offset:y_offset+panel_height] = cv2.addWeighted(
            image[y_offset:y_offset+panel_height], 0.7, panel, 0.3, 0)
        
        # Add text information
        text_color = (255, 255, 255)
        y_pos = 20
        
        # Title
        cv2.putText(image, "YOLO Detection Debug Overlay", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        
        # Detection status
        y_pos += 25
        if self.ball_position and self.confidence > 0:
            status = f"Detection: ACTIVE | Confidence: {self.confidence:.1%}"
            cv2.putText(image, status, (10, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Position info
            y_pos += 20
            pos_text = f"Normalized: ({self.ball_position.x:.3f}, {self.ball_position.y:.3f}) | "
            pos_text += f"Pixels: ({int(self.ball_position.x * self.image_width)}, "
            pos_text += f"{int(self.ball_position.y * self.image_height)})"
            cv2.putText(image, pos_text, (10, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, 1)
        else:
            cv2.putText(image, "Detection: NO BALL DETECTED", (10, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Image info
        y_pos += 20
        img_info = f"Image: {self.image_width}x{self.image_height} | Grid: 10% intervals"
        cv2.putText(image, img_info, (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, 1)

def main(args=None):
    rclpy.init(args=args)
    node = VisualDetectionOverlay()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
