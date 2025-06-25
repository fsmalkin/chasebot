#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import math
import tf2_ros
from tf2_ros import TransformException
from geometry_msgs.msg import TransformStamped
import tf2_geometry_msgs

class BallToNavGoal(Node):
    """
    Detects golf balls and sends navigation goals to Nav2.
    Bridges ball detection to professional navigation.
    """
    
    def __init__(self):
        super().__init__('ball_to_nav_goal')
        
        # Camera subscriber
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # CV Bridge
        self.bridge = CvBridge()
        
        # TF2 Buffer and Listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # HSV parameters (same as our working detection)
        self.hsv_lower = np.array([35, 50, 50])
        self.hsv_upper = np.array([85, 255, 255])
        
        # Camera parameters
        self.camera_fov = 62.2 * math.pi / 180  # IMX219 FOV in radians
        self.camera_height = 0.1  # Camera height from ground (meters)
        self.camera_tilt = 0.0  # Camera tilt angle (radians)
        
        # Navigation parameters
        self.min_ball_area = 100  # Minimum pixels for valid detection
        self.approach_distance = 0.3  # How close to approach the ball (meters)
        self.goal_timeout = 30.0  # Navigation timeout
        
        # State tracking
        self.current_goal = None
        self.navigating = False
        self.last_detection_time = None
        self.detection_cooldown = 2.0  # Seconds between new goals
        
        # Wait for Nav2 to be ready
        self.get_logger().info('Waiting for Nav2 action server...')
        self.nav_client.wait_for_server()
        self.get_logger().info('Nav2 action server is ready!')
        
        self.get_logger().info('Ball to Nav Goal node initialized')
        
    def image_callback(self, msg):
        """Process image to detect balls and send navigation goals."""
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Detect golf balls
            ball_info = self.detect_golf_ball(cv_image)
            
            if ball_info and not self.navigating:
                # Check cooldown
                current_time = self.get_clock().now()
                if self.last_detection_time is None or \
                   (current_time - self.last_detection_time).nanoseconds / 1e9 > self.detection_cooldown:
                    
                    # Convert ball position to navigation goal
                    goal_pose = self.ball_to_world_pose(ball_info, msg.header)
                    
                    if goal_pose:
                        # Send navigation goal
                        self.send_nav_goal(goal_pose)
                        self.last_detection_time = current_time
                        
        except Exception as e:
            self.get_logger().error(f'Error in image callback: {str(e)}')
    
    def detect_golf_ball(self, image):
        """Detect green golf ball using HSV."""
        height, width = image.shape[:2]
        
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create mask
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        if area < self.min_ball_area:
            return None
        
        # Get ball center
        M = cv2.moments(largest_contour)
        if M["m00"] == 0:
            return None
            
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        # Calculate angle from center
        angle_from_center = (cx - width/2) * self.camera_fov / width
        
        # Estimate distance based on ball size
        # This is a simple approximation - adjust based on your setup
        ball_diameter_pixels = 2 * math.sqrt(area / math.pi)
        distance = self.estimate_distance(ball_diameter_pixels, width)
        
        self.get_logger().info(f'Ball detected at ({cx}, {cy}), area: {area}, '
                              f'angle: {math.degrees(angle_from_center):.1f}°, '
                              f'distance: {distance:.2f}m')
        
        return {
            'x': cx,
            'y': cy,
            'area': area,
            'angle': angle_from_center,
            'distance': distance
        }
    
    def estimate_distance(self, ball_pixels, image_width):
        """Estimate distance to ball based on its pixel size."""
        # Golf ball is approximately 4.3cm diameter
        # This is a simplified model - adjust based on calibration
        
        # At 1 meter, a golf ball might appear as ~40 pixels (example)
        # This needs calibration for your specific camera
        reference_pixels = 40.0
        reference_distance = 1.0
        
        # Simple inverse relationship
        distance = reference_distance * (reference_pixels / ball_pixels)
        
        # Clamp to reasonable range
        return max(0.3, min(3.0, distance))
    
    def ball_to_world_pose(self, ball_info, header):
        """Convert ball detection to world pose for navigation."""
        try:
            # Get transform from camera to base_link
            transform = self.tf_buffer.lookup_transform(
                'base_link',
                header.frame_id,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            
            # Calculate ball position relative to robot
            # X: forward, Y: left (ROS convention)
            ball_x = ball_info['distance'] * math.cos(ball_info['angle'])
            ball_y = ball_info['distance'] * math.sin(ball_info['angle'])
            
            # Adjust for approach distance
            approach_x = ball_x - self.approach_distance
            
            # Create goal pose
            goal = PoseStamped()
            goal.header.frame_id = 'base_link'
            goal.header.stamp = self.get_clock().now().to_msg()
            
            # Set position (approach point, not ball center)
            goal.pose.position.x = approach_x
            goal.pose.position.y = ball_y
            goal.pose.position.z = 0.0
            
            # Set orientation (face the ball)
            yaw = math.atan2(ball_y, ball_x)
            goal.pose.orientation.z = math.sin(yaw / 2.0)
            goal.pose.orientation.w = math.cos(yaw / 2.0)
            
            # Transform to map frame
            goal_map = self.tf_buffer.transform(goal, 'map', timeout=rclpy.duration.Duration(seconds=1.0))
            
            return goal_map
            
        except (TransformException, tf2_ros.LookupException, tf2_ros.ConnectivityException, 
                tf2_ros.ExtrapolationException) as e:
            self.get_logger().error(f'Transform error: {str(e)}')
            return None
    
    def send_nav_goal(self, pose):
        """Send navigation goal to Nav2."""
        self.get_logger().info(f'Sending navigation goal to ({pose.pose.position.x:.2f}, '
                              f'{pose.pose.position.y:.2f})')
        
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
        self.get_logger().debug(f'Navigation feedback - Position: '
                               f'({current_pose.position.x:.2f}, {current_pose.position.y:.2f})')


def main(args=None):
    rclpy.init(args=args)
    
    ball_to_nav = BallToNavGoal()
    
    try:
        rclpy.spin(ball_to_nav)
    except KeyboardInterrupt:
        pass
    finally:
        ball_to_nav.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
