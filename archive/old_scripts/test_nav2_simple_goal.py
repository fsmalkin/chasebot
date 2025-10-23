#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import math

class SimpleNav2GoalSender(Node):
    """
    Simple Nav2 goal sender for UAT testing.
    Sends robot to a fixed position where a golf ball should be located.
    """
    
    def __init__(self):
        super().__init__('simple_nav2_goal_sender')
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Wait for Nav2 to be ready
        self.get_logger().info('Waiting for Nav2 action server...')
        self.nav_client.wait_for_server()
        self.get_logger().info('Nav2 action server is ready!')
        
        # Create timer to send goal after startup
        self.timer = self.create_timer(3.0, self.send_goal_to_ball)
        
    def send_goal_to_ball(self):
        """Send navigation goal to ball position for UAT testing."""
        self.timer.cancel()  # Only send one goal
        
        # Create goal pose - go to where the ball should be
        # In simple_golf_ball_world.world, ball is typically at (2, 1, 0.1)
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'odom'
        goal_pose.header.stamp = self.get_clock().now().to_msg()
        
        # Position: approach the ball from 0.5m away
        goal_pose.pose.position.x = 1.5  # Approach position
        goal_pose.pose.position.y = 1.0  # Same Y as ball
        goal_pose.pose.position.z = 0.0
        
        # Orientation: face the ball
        # Calculate yaw to face the ball at (2, 1)
        dx = 2.0 - 1.5  # Ball X - approach X
        dy = 1.0 - 1.0  # Ball Y - approach Y
        yaw = math.atan2(dy, dx)
        
        goal_pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_pose.pose.orientation.w = math.cos(yaw / 2.0)
        
        # Create goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info(f'Sending Nav2 goal to ({goal_pose.pose.position.x:.2f}, '
                              f'{goal_pose.pose.position.y:.2f}) - approaching ball position')
        
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
            self.get_logger().error('❌ Goal rejected by Nav2! Check Nav2 configuration.')
            return
        
        self.get_logger().info('✅ Goal accepted by Nav2! Robot is navigating...')
        
        # Get result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_callback)
    
    def get_result_callback(self, future):
        """Handle navigation result."""
        result = future.result().result
        status = future.result().status
        
        if status == 4:  # SUCCEEDED
            self.get_logger().info('🎉 SUCCESS! Robot reached the goal using Nav2 navigation!')
            self.get_logger().info('UAT PASSED: Nav2 professional navigation is working!')
        else:
            self.get_logger().warn(f'Navigation finished with status: {status}')
            if status == 6:  # ABORTED
                self.get_logger().error('Navigation was aborted - check for obstacles or configuration issues')
            elif status == 5:  # CANCELED
                self.get_logger().info('Navigation was canceled')
    
    def feedback_callback(self, feedback_msg):
        """Handle navigation feedback."""
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        
        # Log progress
        self.get_logger().info(f'Navigation progress - Position: '
                               f'({current_pose.position.x:.2f}, {current_pose.position.y:.2f})')


def main(args=None):
    rclpy.init(args=args)
    
    goal_sender = SimpleNav2GoalSender()
    
    try:
        rclpy.spin(goal_sender)
    except KeyboardInterrupt:
        goal_sender.get_logger().info('Goal sender stopped by user')
    finally:
        goal_sender.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
