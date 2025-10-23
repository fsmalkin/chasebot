#!/usr/bin/env python3
"""
YOLO to Nav2 Goal Bridge - Version 2.0.0
Major changes:
- v2.0.0: Complete rewrite using camera intrinsics for proper coordinate conversion
- v1.2.0: Direct position calculation (incorrectly treated pixels as meters)
- v1.1.0: Used transforms with hardcoded distance estimation
- v1.0.0: Initial implementation
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Point, PoseStamped, TransformStamped
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Float32
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformListener
import tf2_geometry_msgs
import math
import numpy as np

class YoloToNavGoalV2(Node):
    def __init__(self):
        super().__init__('yolo_to_nav_goal_v2')
        
        # Action client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # TF2 for coordinate transformations
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Camera parameters
        self.camera_info = None
        self.camera_frame = 'camera_link'
        self.robot_frame = 'base_link'
        self.world_frame = 'odom'
        self.image_width = None
        self.image_height = None
        
        # Camera info subscription
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/camera/camera_info',
            self.camera_info_callback,
            10
        )
        
        # Image subscription (just for dimensions)
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        # Ball position and confidence subscriptions
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
        
        # Parameters
        self.min_confidence = 0.6
        self.approach_distance = 0.15  # 15cm approach distance
        self.detection_cooldown = 2.0  # Reduced to 2 seconds for faster response
        self.min_detection_distance = 0.3  # Minimum distance to trigger navigation (30cm)
        self.max_detection_distance = 2.0  # Maximum distance to consider ball (2m)
        self.ground_height = 0.02  # Assume ball is 2cm above ground (ball radius)
        
        # State tracking
        self.current_ball_position = None
        self.current_confidence = 0.0
        self.last_navigation_time = 0.0
        self.navigating = False
        
        # Wait for Nav2
        self.get_logger().info("Waiting for Nav2 action server...")
        self.nav_client.wait_for_server()
        self.get_logger().info("Nav2 action server ready!")
        
        self.get_logger().info("YOLO to Nav Goal Bridge v2.0.0 initialized")
        self.get_logger().info("Using camera intrinsics for proper coordinate conversion")
        self.get_logger().info(f"Approach distance: {self.approach_distance}m")
        self.get_logger().info(f"Min confidence: {self.min_confidence}")

    def camera_info_callback(self, msg):
        """Store camera calibration info"""
        self.camera_info = msg
        if self.image_width is None or self.image_height is None:
            self.image_width = msg.width
            self.image_height = msg.height
            self.get_logger().info(f"Camera info received: {msg.width}x{msg.height}")

    def image_callback(self, msg):
        """Store image dimensions"""
        if self.image_width is None or self.image_height is None:
            self.image_width = msg.width
            self.image_height = msg.height

    def ball_position_callback(self, msg):
        """Update ball position (normalized pixel coordinates)"""
        self.current_ball_position = msg
        self.process_detection()

    def confidence_callback(self, msg):
        """Update detection confidence"""
        self.current_confidence = msg.data
        self.process_detection()

    def process_detection(self):
        """Process ball detection and send navigation goal if appropriate"""
        self.get_logger().debug(f"Processing detection - Confidence: {self.current_confidence:.2f}")
        
        if not self.should_navigate():
            return
        
        # Convert pixel coordinates to world coordinates
        world_position = self.pixel_to_world_coords()
        if world_position is None:
            self.get_logger().warn("Failed to convert pixel to world coordinates")
            return
        
        # Calculate approach goal
        goal_pose = self.calculate_approach_goal(world_position)
        if goal_pose is None:
            return
        
        # Send navigation goal
        self.send_navigation_goal(goal_pose)

    def should_navigate(self):
        """Check if we should send a new navigation goal"""
        # Need camera info
        if self.camera_info is None:
            if not hasattr(self, '_warned_camera_info'):
                self.get_logger().warn("Waiting for camera info...")
                self._warned_camera_info = True
            return False
        
        # Need both position and confidence
        if self.current_ball_position is None or self.current_confidence == 0.0:
            self.get_logger().debug("No ball position or confidence")
            return False
        
        # Check confidence threshold
        if self.current_confidence < self.min_confidence:
            self.get_logger().debug(f"Confidence too low: {self.current_confidence:.2f} < {self.min_confidence}")
            return False
        
        # Check cooldown period
        current_time = self.get_clock().now().nanoseconds / 1e9
        time_since_last = current_time - self.last_navigation_time
        if time_since_last < self.detection_cooldown:
            self.get_logger().debug(f"In cooldown: {time_since_last:.1f}s < {self.detection_cooldown}s")
            return False
        
        # Don't send new goals while navigating
        if self.navigating:
            self.get_logger().debug("Already navigating")
            return False
        
        self.get_logger().info("✅ All navigation checks passed!")
        return True

    def pixel_to_world_coords(self):
        """Convert normalized pixel coordinates to world coordinates"""
        # Get pixel coordinates from normalized values
        pixel_x = self.current_ball_position.x * self.image_width
        pixel_y = self.current_ball_position.y * self.image_height
        
        self.get_logger().info(f"Ball detected at pixel ({pixel_x:.0f}, {pixel_y:.0f})")
        
        # Get camera intrinsic matrix
        K = np.array(self.camera_info.k).reshape(3, 3)
        fx = K[0, 0]
        fy = K[1, 1]
        cx = K[0, 2]
        cy = K[1, 2]
        
        # Convert pixel to camera ray (normalized)
        # Camera coordinate system: X-right, Y-down, Z-forward
        ray_x = (pixel_x - cx) / fx
        ray_y = (pixel_y - cy) / fy
        ray_z = 1.0
        
        # Normalize the ray
        ray_length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
        ray_x /= ray_length
        ray_y /= ray_length
        ray_z /= ray_length
        
        # Get camera transform
        try:
            # Get transform from camera to odom
            transform = self.tf_buffer.lookup_transform(
                self.world_frame,
                self.camera_frame,
                rclpy.time.Time()
            )
        except Exception as e:
            self.get_logger().error(f"Failed to get transform: {e}")
            return None
        
        # Camera position in world
        cam_x = transform.transform.translation.x
        cam_y = transform.transform.translation.y
        cam_z = transform.transform.translation.z
        
        # Apply rotation to ray (simplified - assuming camera is roughly horizontal)
        # For JetBot, camera typically points forward and slightly down
        # We'll intersect the ray with the ground plane (z = ground_height)
        
        # If ray points up, ball is not visible on ground
        if ray_y <= 0:  # Remember Y is down in camera coords
            self.get_logger().warn("Ball ray points upward, cannot intersect with ground")
            return None
        
        # Calculate intersection with ground plane
        # Assuming camera is roughly horizontal, ray_y corresponds to vertical component
        t = (cam_z - self.ground_height) / ray_y  # Distance along ray to ground
        
        if t < 0:
            self.get_logger().warn("Ball appears to be behind camera")
            return None
        
        # Calculate world position
        # Note: This is simplified - assumes camera is level
        # In camera frame: X-right, Y-down, Z-forward
        # In world frame: X-forward, Y-left, Z-up
        world_x = cam_x + t * ray_z  # Forward
        world_y = cam_y - t * ray_x  # Left (negative of camera right)
        world_z = self.ground_height
        
        self.get_logger().info(f"Ball world position: ({world_x:.3f}, {world_y:.3f}, {world_z:.3f})")
        
        return (world_x, world_y, world_z)

    def calculate_approach_goal(self, world_position):
        """Calculate approach goal from world position"""
        ball_x, ball_y, _ = world_position
        
        # Get robot position
        try:
            transform = self.tf_buffer.lookup_transform(
                self.world_frame,
                self.robot_frame,
                rclpy.time.Time()
            )
            robot_x = transform.transform.translation.x
            robot_y = transform.transform.translation.y
        except Exception as e:
            self.get_logger().error(f"Failed to get robot transform: {e}")
            robot_x = 0.0
            robot_y = 0.0
        
        # Calculate distance from robot to ball
        dx = ball_x - robot_x
        dy = ball_y - robot_y
        distance_to_ball = math.sqrt(dx*dx + dy*dy)
        
        self.get_logger().info(f"📍 Ball at ({ball_x:.2f}, {ball_y:.2f}), Robot at ({robot_x:.2f}, {robot_y:.2f})")
        self.get_logger().info(f"📏 Distance to ball: {distance_to_ball:.3f}m")
        
        # Check if ball is too close already
        if distance_to_ball <= self.approach_distance:
            self.get_logger().info("✅ Ball is already within approach distance!")
            return None
        
        # Check if ball is within valid detection range
        if distance_to_ball < self.min_detection_distance:
            self.get_logger().info(f"⚠️ Ball too close for navigation: {distance_to_ball:.3f}m < {self.min_detection_distance}m")
            return None
            
        if distance_to_ball > self.max_detection_distance:
            self.get_logger().warn(f"⚠️ Ball too far: {distance_to_ball:.3f}m > {self.max_detection_distance}m")
            return None
        
        # Calculate approach point
        scale = (distance_to_ball - self.approach_distance) / distance_to_ball
        approach_x = robot_x + dx * scale
        approach_y = robot_y + dy * scale
        
        # Create goal pose
        goal = PoseStamped()
        goal.header.frame_id = self.world_frame
        goal.header.stamp = self.get_clock().now().to_msg()
        
        goal.pose.position.x = approach_x
        goal.pose.position.y = approach_y
        goal.pose.position.z = 0.0
        
        # Orient towards the ball
        yaw = math.atan2(dy, dx)
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        
        self.get_logger().info(f"🎯 Approach goal: ({approach_x:.3f}, {approach_y:.3f})")
        self.get_logger().info(f"📐 Approach will stop {self.approach_distance:.3f}m from ball")
        self.get_logger().info(f"🧭 Yaw angle to ball: {math.degrees(yaw):.1f}°")
        
        return goal

    def send_navigation_goal(self, goal_pose):
        """Send navigation goal to Nav2"""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info("="*60)
        self.get_logger().info(f"🚀 SENDING NAVIGATION GOAL!")
        self.get_logger().info(f"📍 Target: ({goal_pose.pose.position.x:.3f}, {goal_pose.pose.position.y:.3f})")
        self.get_logger().info("="*60)
        
        # Send goal
        future = self.nav_client.send_goal_async(goal_msg)
        future.add_done_callback(self.goal_response_callback)
        
        # Update state
        self.navigating = True
        self.last_navigation_time = self.get_clock().now().nanoseconds / 1e9

    def goal_response_callback(self, future):
        """Handle goal response from Nav2"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Navigation goal rejected!')
            self.navigating = False
            return
        
        self.get_logger().info('Navigation goal accepted, robot moving...')
        
        # Wait for result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_result_callback)

    def goal_result_callback(self, future):
        """Handle navigation result"""
        result = future.result().result
        self.navigating = False
        
        if result:
            self.get_logger().info("✅ Navigation completed! Robot should be near the ball.")
        else:
            self.get_logger().error("❌ Navigation failed!")

def main(args=None):
    rclpy.init(args=args)
    
    node = YoloToNavGoalV2()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
