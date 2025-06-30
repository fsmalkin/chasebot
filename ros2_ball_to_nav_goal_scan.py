#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import LaserScan
import math

class BallToNavGoal(Node):
    """
    Converts laser scan detections to navigation goals for Nav2.
    """
    
    def __init__(self):
        super().__init__('ball_to_nav_goal')
        
        # Laser scan subscriber
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Navigation parameters
        self.approach_distance = 0.3  # How close to approach the ball (meters)
        self.goal_timeout = 30.0  # Navigation timeout
        self.min_detection_distance = 0.2  # Minimum distance for valid detection
        self.max_detection_distance = 3.0  # Maximum distance for valid detection
        
        # State tracking
        self.current_goal = None
        self.navigating = False
        self.last_goal_time = None
        self.goal_cooldown = 2.0  # Seconds between new goals
        
        # Wait for Nav2 to be ready
        self.get_logger().info('Waiting for Nav2 action server...')
        self.nav_client.wait_for_server()
        self.get_logger().info('Nav2 action server is ready!')
        
        self.get_logger().info('Ball to Nav Goal node initialized')
        
    def scan_callback(self, msg):
        """Process laser scan to find obstacles and send navigation goals."""
        try:
            if self.navigating:
                return
                
            # Find closest obstacle in scan
            min_distance = float('inf')
            min_angle = None
            
            for i, distance in enumerate(msg.ranges):
                if distance != float('inf') and \
                   self.min_detection_distance < distance < self.max_detection_distance:
                    if distance < min_distance:
                        min_distance = distance
                        min_angle = msg.angle_min + i * msg.angle_increment
            
            # If we found an obstacle
            if min_angle is not None:
                # Check cooldown
                current_time = self.get_clock().now()
                if self.last_goal_time is None or \
                   (current_time - self.last_goal_time).nanoseconds / 1e9 > self.goal_cooldown:
                    
                    self.get_logger().info(f'Obstacle detected at {min_distance:.2f}m, angle {math.degrees(min_angle):.1f}°')
                    
                    # Create navigation goal
                    goal_pose = self.create_nav_goal(min_distance, min_angle)
                    
                    if goal_pose:
                        # Send navigation goal
                        self.send_nav_goal(goal_pose)
                        self.last_goal_time = current_time
                        
        except Exception as e:
            self.get_logger().error(f'Error in scan callback: {str(e)}')
    
    def create_nav_goal(self, distance, angle):
        """Create navigation goal from obstacle detection."""
        try:
            # Calculate goal position (approach point, not obstacle center)
            # Subtract approach distance from the detected distance
            approach_distance = max(0.1, distance - self.approach_distance)
            
            # Convert polar to cartesian coordinates
            # X: forward, Y: left (ROS convention)
            goal_x = approach_distance * math.cos(angle)
            goal_y = approach_distance * math.sin(angle)
            
            # Create goal pose in odom frame
            # Since we're doing mapless navigation, we use odom as our global frame
            goal = PoseStamped()
            goal.header.frame_id = 'odom'
            goal.header.stamp = self.get_clock().now().to_msg()
            
            # Set position
            goal.pose.position.x = goal_x
            goal.pose.position.y = goal_y
            goal.pose.position.z = 0.0
            
            # Set orientation (face the obstacle)
            yaw = angle
            goal.pose.orientation.z = math.sin(yaw / 2.0)
            goal.pose.orientation.w = math.cos(yaw / 2.0)
            
            return goal
            
        except Exception as e:
            self.get_logger().error(f'Error creating nav goal: {str(e)}')
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
