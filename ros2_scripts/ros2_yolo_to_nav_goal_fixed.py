#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Point
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Float32
from cv_bridge import CvBridge
import cv2
import numpy as np
import math
import tf2_ros
from tf2_ros import TransformException
from geometry_msgs.msg import TransformStamped
import tf2_geometry_msgs

class YoloToNavGoal(Node):
    """
    Converts YOLO detections to Nav2 navigation goals.
    Fixed version that subscribes to actual YOLO detector topics.
    """
    
    def __init__(self):
        super().__init__('yolo_to_nav_goal')
        
        # YOLO detection subscribers (fixed to match actual topics)
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
        
        # Camera info subscriber for intrinsics
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/camera/camera_info',
            self.camera_info_callback,
            10
        )
        
        # Image subscriber to get image dimensions
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            1  # Low queue to just get dimensions
        )
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # TF2 Buffer and Listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Camera parameters
        self.camera_info = None
        self.camera_height = 0.12  # Camera height from ground (meters) - adjusted for JetBot
        self.ball_diameter = 0.043  # Golf ball diameter in meters
        self.image_width = 640  # Default, will be updated from actual image
        self.image_height = 480  # Default, will be updated from actual image
        
        # Navigation parameters
        self.min_confidence = 0.5  # Minimum detection confidence
        self.approach_distance = 0.3  # How close to approach the ball (meters)
        self.goal_timeout = 30.0  # Navigation timeout
        
        # State tracking
        self.current_goal = None
        self.navigating = False
        self.last_detection_time = None
        self.detection_cooldown = 2.0  # Seconds between new goals
        self.last_position = None
        self.last_confidence = 0.0
        
        # Wait for Nav2 to be ready
        self.get_logger().info('Waiting for Nav2 action server...')
        self.nav_client.wait_for_server()
        self.get_logger().info('Nav2 action server is ready!')
        
        self.get_logger().info('YOLO to Nav Goal bridge initialized (fixed version)')
        self.get_logger().info('Subscribing to /yolo/ball_position and /yolo/confidence')
        
    def camera_info_callback(self, msg):
        """Store camera intrinsics."""
        self.camera_info = msg
        
    def image_callback(self, msg):
        """Update image dimensions from actual camera feed."""
        self.image_width = msg.width
        self.image_height = msg.height
        
    def confidence_callback(self, msg):
        """Store latest confidence value."""
        self.last_confidence = msg.data
        
    def position_callback(self, msg):
        """Process YOLO ball position and send navigation goals."""
        if self.navigating:
            return
            
        # Store position (normalized 0-1 coordinates)
        self.last_position = msg
        
        # Check if we have sufficient confidence
        if self.last_confidence < self.min_confidence:
            return
        
        # Check cooldown
        current_time = self.get_clock().now()
        if self.last_detection_time is None or \
           (current_time - self.last_detection_time).nanoseconds / 1e9 > self.detection_cooldown:
            
            # Convert detection to navigation goal
            goal_pose = self.detection_to_world_pose(msg, self.last_confidence)
            
            if goal_pose:
                # Send navigation goal
                self.send_nav_goal(goal_pose)
                self.last_detection_time = current_time
                
                # Convert normalized coordinates back to pixels for logging
                pixel_x = msg.x * self.image_width
                pixel_y = msg.y * self.image_height
                
                self.get_logger().info(
                    f'Ball detected: sports ball '
                    f'(confidence: {self.last_confidence:.2f}, '
                    f'pixel position: {pixel_x:.0f}, {pixel_y:.0f})'
                )
    
    def detection_to_world_pose(self, position_msg, confidence):
        """Convert YOLO detection to world pose for navigation."""
        try:
            # Get current time for all transforms
            current_time = self.get_clock().now()
            
            # Convert normalized coordinates to pixels
            pixel_x = position_msg.x * self.image_width
            pixel_y = position_msg.y * self.image_height
            
            # Estimate bounding box size from normalized position and confidence
            # Higher confidence typically means clearer/closer detection
            estimated_bbox_size = 50.0  # Base estimate, can be refined
            
            self.get_logger().info(
                f'Detection pixels: ({pixel_x:.0f}, {pixel_y:.0f}), '
                f'estimated bbox size: {estimated_bbox_size:.0f}'
            )
            
            # Estimate distance based on estimated bounding box size
            distance = self.estimate_distance_from_bbox(estimated_bbox_size, estimated_bbox_size)
            self.get_logger().info(f'Estimated distance: {distance:.2f}m')
            
            # Convert pixel to angle using camera FOV
            if self.camera_info:
                # Use camera intrinsics if available
                cx = self.camera_info.k[2]  # Principal point x
                cy = self.camera_info.k[5]  # Principal point y
                fx = self.camera_info.k[0]  # Focal length x
                
                # Calculate angle from optical center
                angle_x = math.atan2(pixel_x - cx, fx)
            else:
                # Fallback to FOV-based calculation
                camera_fov = 62.2 * math.pi / 180  # IMX219 horizontal FOV
                angle_x = (pixel_x - self.image_width/2) * camera_fov / self.image_width
            
            # Calculate ball position relative to camera
            ball_x = distance * math.cos(angle_x)
            ball_y = distance * math.sin(angle_x)
            
            self.get_logger().info(
                f'Ball position in camera frame: ({ball_x:.2f}, {ball_y:.2f})'
            )
            
            # Create pose in camera_link frame (not camera_optical_link)
            ball_pose = PoseStamped()
            ball_pose.header.frame_id = 'camera_link'
            ball_pose.header.stamp = current_time.to_msg()
            
            # Ball position (camera frame has X forward, Y left, Z up)
            ball_pose.pose.position.x = ball_x
            ball_pose.pose.position.y = ball_y
            ball_pose.pose.position.z = 0.0
            
            # Transform to base_link frame
            ball_in_base = self.tf_buffer.transform(
                ball_pose, 
                'base_link', 
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            
            # Calculate approach position (stop before the ball)
            distance_to_ball = math.sqrt(
                ball_in_base.pose.position.x**2 + 
                ball_in_base.pose.position.y**2
            )
            
            # Scale back the position to maintain approach distance
            if distance_to_ball > self.approach_distance:
                scale = (distance_to_ball - self.approach_distance) / distance_to_ball
                approach_x = ball_in_base.pose.position.x * scale
                approach_y = ball_in_base.pose.position.y * scale
            else:
                # Ball is too close, don't move
                self.get_logger().info('Ball is too close, not moving')
                return None
            
            # Create goal pose
            goal = PoseStamped()
            goal.header.frame_id = 'base_link'
            goal.header.stamp = current_time.to_msg()
            
            # Set approach position
            goal.pose.position.x = approach_x
            goal.pose.position.y = approach_y
            goal.pose.position.z = 0.0
            
            # Set orientation to face the ball
            yaw = math.atan2(ball_in_base.pose.position.y, ball_in_base.pose.position.x)
            goal.pose.orientation.z = math.sin(yaw / 2.0)
            goal.pose.orientation.w = math.cos(yaw / 2.0)
            
            self.get_logger().info(
                f'Approach position in base_link: ({approach_x:.2f}, {approach_y:.2f})'
            )
            
            # Transform to odom frame for navigation
            goal_odom = self.tf_buffer.transform(
                goal, 
                'odom', 
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            
            return goal_odom
            
        except (TransformException, tf2_ros.LookupException, tf2_ros.ConnectivityException, 
                tf2_ros.ExtrapolationException) as e:
            self.get_logger().error(f'Transform error: {str(e)}')
            
            # Try to provide more context about the transform failure
            try:
                # Check if base_link exists
                self.tf_buffer.lookup_transform('odom', 'base_link', 
                                                rclpy.time.Time(), 
                                                timeout=rclpy.duration.Duration(seconds=0.1))
                self.get_logger().info('Transform chain odom->base_link exists')
            except:
                self.get_logger().error('Transform chain odom->base_link is broken!')
                
            try:
                # Check if camera_link exists
                self.tf_buffer.lookup_transform('base_link', 'camera_link', 
                                                rclpy.time.Time(), 
                                                timeout=rclpy.duration.Duration(seconds=0.1))
                self.get_logger().info('Transform chain base_link->camera_link exists')
            except:
                self.get_logger().error('Transform chain base_link->camera_link is broken!')
                
            return None
    
    def estimate_distance_from_bbox(self, bbox_width, bbox_height):
        """Estimate distance to ball based on bounding box size."""
        # Use the larger dimension (ball should be roughly circular)
        bbox_size = max(bbox_width, bbox_height)
        
        # Camera parameters (adjust based on calibration)
        # At 1 meter, a 4.3cm golf ball might appear as ~40 pixels
        reference_pixels = 40.0
        reference_distance = 1.0
        
        # Simple inverse relationship
        distance = reference_distance * (reference_pixels / bbox_size)
        
        # Clamp to reasonable range
        return max(0.3, min(3.0, distance))
    
    def send_nav_goal(self, pose):
        """Send navigation goal to Nav2."""
        self.get_logger().info(
            f'Sending navigation goal to ({pose.pose.position.x:.2f}, '
            f'{pose.pose.position.y:.2f})'
        )
        
        # Create goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = pose
        
        # Send goal
        self.current_goal = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        
        self.current_goal.add_done_callback(self.goal_response_callback)
        self.navigating = True
    
    def goal_response_callback(self, future):
        """Handle goal response from Nav2."""
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().info('Goal rejected by Nav2')
            self.navigating = False
            return
        
        self.get_logger().info('Goal accepted by Nav2, navigating...')
        
        # Get result
        self.result_future = goal_handle.get_result_async()
        self.result_future.add_done_callback(self.get_result_callback)
    
    def get_result_callback(self, future):
        """Handle navigation result."""
        result = future.result().result
        status = future.result().status
        
        if status == 4:  # SUCCEEDED
            self.get_logger().info('Navigation succeeded! Reached the ball.')
        else:
            self.get_logger().info(f'Navigation finished with status: {status}')
        
        self.navigating = False
    
    def feedback_callback(self, feedback_msg):
        """Handle navigation feedback."""
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        
        # Log progress occasionally
        self.get_logger().debug(
            f'Navigation feedback - Position: '
            f'({current_pose.position.x:.2f}, {current_pose.position.y:.2f})'
        )


def main(args=None):
    rclpy.init(args=args)
    
    yolo_to_nav = YoloToNavGoal()
    
    try:
        rclpy.spin(yolo_to_nav)
    except KeyboardInterrupt:
        pass
    finally:
        yolo_to_nav.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
