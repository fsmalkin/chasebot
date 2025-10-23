#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point
from std_msgs.msg import Float32
import math

class PositionDiagnostics(Node):
    def __init__(self):
        super().__init__('position_diagnostics')
        
        # Subscriptions
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )
        
        self.ball_position_sub = self.create_subscription(
            Point,
            '/yolo/ball_position',
            self.ball_position_callback,
            10
        )
        
        self.confidence_sub = self.create_subscription(
            Float32,
            '/yolo/confidence',
            self.confidence_callback,
            10
        )
        
        # Current positions
        self.robot_position = None
        self.ball_world_position = None
        self.ball_confidence = 0.0
        
        # Create timer for periodic reporting
        self.timer = self.create_timer(2.0, self.report_positions)
        
        self.get_logger().info("Position Diagnostics Node Started")
        self.get_logger().info("Monitoring robot position and ball detections...")

    def odom_callback(self, msg):
        """Update robot position from odometry"""
        self.robot_position = msg.pose.pose.position
        
    def ball_position_callback(self, msg):
        """Update ball position (this is relative position from camera)"""
        # Store the ball position - this might be in camera frame
        self.ball_world_position = msg
        
    def confidence_callback(self, msg):
        """Update ball detection confidence"""
        self.ball_confidence = msg.data

    def calculate_distance(self, pos1, pos2):
        """Calculate 2D distance between two positions"""
        if pos1 is None or pos2 is None:
            return None
        
        dx = pos1.x - pos2.x
        dy = pos1.y - pos2.y
        return math.sqrt(dx*dx + dy*dy)

    def report_positions(self):
        """Report current positions and distances"""
        self.get_logger().info("=" * 60)
        
        # Robot position
        if self.robot_position:
            self.get_logger().info(f"🤖 ROBOT Position: ({self.robot_position.x:.3f}, {self.robot_position.y:.3f}, {self.robot_position.z:.3f})")
        else:
            self.get_logger().info("🤖 ROBOT Position: No odometry data")
            
        # Ball detection
        if self.ball_world_position and self.ball_confidence > 0.5:
            self.get_logger().info(f"⚽ BALL Position: ({self.ball_world_position.x:.3f}, {self.ball_world_position.y:.3f}, {self.ball_world_position.z:.3f})")
            self.get_logger().info(f"⚽ BALL Confidence: {self.ball_confidence:.2f}")
            
            # Calculate distance if both positions available
            if self.robot_position:
                distance = self.calculate_distance(self.robot_position, self.ball_world_position)
                if distance is not None:
                    self.get_logger().info(f"📏 DISTANCE: {distance:.3f}m")
                    
                    # Check against approach distance thresholds
                    if distance <= 0.05:
                        self.get_logger().info("✅ Within 0.05m approach distance")
                    elif distance <= 0.10:
                        self.get_logger().info("⚠️  Within 0.10m but beyond 0.05m")
                    elif distance <= 0.25:
                        self.get_logger().info("⚠️  Within 0.25m but beyond 0.10m")
                    else:
                        self.get_logger().info("❌ MUCH TOO FAR! Beyond reasonable approach distance")
        else:
            self.get_logger().info("⚽ BALL: No detection or low confidence")
            
        self.get_logger().info("=" * 60)

def main(args=None):
    rclpy.init(args=args)
    
    diagnostics = PositionDiagnostics()
    
    try:
        rclpy.spin(diagnostics)
    except KeyboardInterrupt:
        pass
    finally:
        diagnostics.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
