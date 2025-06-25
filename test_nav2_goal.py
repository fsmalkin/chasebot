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

class TestNav2Goal(Node):
    """
    Test Nav2 by sending manual navigation goals.
    This will verify Nav2 is working before integrating ball detection.
    """
    
    def __init__(self):
        super().__init__('test_nav2_goal')
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Camera subscriber to detect balls (but not send goals yet)
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        
        # CV Bridge
        self.bridge = CvBridge()
        
        # HSV parameters for ball detection
        self.hsv_lower = np.array([35, 50, 50])
        self.hsv_upper = np.array([85, 255, 255])
        
        # State
        self.ball_detected = False
        self.ball_position = None
        self.goal_sent = False
        self.test_phase = 0
        
        # Timer for test sequence
        self.timer = self.create_timer(3.0, self.timer_callback)
        
        self.get_logger().info('Test Nav2 Goal node initialized')
        self.get_logger().info('Waiting for Nav2 action server...')
        
        # Check if Nav2 is available
        if self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().info('Nav2 action server is ready!')
        else:
            self.get_logger().error('Nav2 action server not available!')
    
    def image_callback(self, msg):
        """Detect ball position but don't send goals automatically."""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Convert to HSV
            hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
            
            # Create mask
            mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find largest contour
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)
                
                if area > 100:  # Minimum area threshold
                    M = cv2.moments(largest_contour)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        if not self.ball_detected:
                            self.ball_detected = True
                            self.ball_position = (cx, cy)
                            self.get_logger().info(f'Ball detected at ({cx}, {cy})')
                        
        except Exception as e:
            self.get_logger().error(f'Error in image callback: {str(e)}')
    
    def timer_callback(self):
        """Test sequence for Nav2."""
        if self.test_phase == 0:
            self.get_logger().info('Phase 1: Sending simple forward goal...')
            
            # Send a goal 0.5m forward in odom frame
            goal = PoseStamped()
            goal.header.frame_id = 'odom'
            goal.header.stamp = self.get_clock().now().to_msg()
            
            # 0.5m forward from origin
            goal.pose.position.x = 0.5
            goal.pose.position.y = 0.0
            goal.pose.position.z = 0.0
            
            # Face forward
            goal.pose.orientation.x = 0.0
            goal.pose.orientation.y = 0.0
            goal.pose.orientation.z = 0.0
            goal.pose.orientation.w = 1.0
            
            self.send_nav_goal(goal)
            self.test_phase = 1
            
        elif self.test_phase == 1 and self.ball_detected and not self.goal_sent:
            self.get_logger().info('Phase 2: Ball detected! Sending goal near ball...')
            
            # For now, just send a goal slightly to the right
            goal = PoseStamped()
            goal.header.frame_id = 'odom'
            goal.header.stamp = self.get_clock().now().to_msg()
            
            # Goal to the right side
            goal.pose.position.x = 0.3
            goal.pose.position.y = -0.3
            goal.pose.position.z = 0.0
            
            # Face toward origin
            angle = math.atan2(0.0 - (-0.3), 0.0 - 0.3)
            goal.pose.orientation.z = math.sin(angle / 2.0)
            goal.pose.orientation.w = math.cos(angle / 2.0)
            
            self.send_nav_goal(goal)
            self.goal_sent = True
            self.timer.cancel()
    
    def send_nav_goal(self, pose):
        """Send navigation goal to Nav2."""
        self.get_logger().info(f'Sending Nav2 goal to ({pose.pose.position.x:.2f}, '
                              f'{pose.pose.position.y:.2f})')
        
        # Create goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = pose
        
        # Send goal
        future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        
        future.add_done_callback(self.goal_response_callback)
    
    def goal_response_callback(self, future):
        """Handle goal response from Nav2."""
        goal_handle = future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected by Nav2!')
            return
        
        self.get_logger().info('Goal accepted by Nav2!')
        
        # Get result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_callback)
    
    def get_result_callback(self, future):
        """Handle navigation result."""
        result = future.result().result
        status = future.result().status
        
        if status == 4:  # SUCCEEDED
            self.get_logger().info('Navigation succeeded!')
        else:
            self.get_logger().info(f'Navigation finished with status: {status}')
    
    def feedback_callback(self, feedback_msg):
        """Handle navigation feedback."""
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        
        # Log progress
        self.get_logger().info(f'Nav2 position: ({current_pose.position.x:.2f}, '
                              f'{current_pose.position.y:.2f})')


def main(args=None):
    rclpy.init(args=args)
    
    test_nav = TestNav2Goal()
    
    try:
        rclpy.spin(test_nav)
    except KeyboardInterrupt:
        pass
    finally:
        test_nav.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
