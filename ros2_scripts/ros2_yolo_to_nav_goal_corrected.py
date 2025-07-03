#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Point, PoseStamped
from std_msgs.msg import Float32
from nav2_msgs.action import NavigateToPose
import math

class YoloToNavGoalCorrected(Node):
    def __init__(self):
        super().__init__('yolo_to_nav_goal_corrected')
        
        # Action client for Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Subscriptions
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
        self.detection_cooldown = 3.0  # Seconds between navigation goals
        
        # State tracking
        self.current_ball_position = None
        self.current_confidence = 0.0
        self.last_navigation_time = 0.0
        self.navigating = False
        
        # Wait for Nav2
        self.get_logger().info("Waiting for Nav2 action server...")
        self.nav_client.wait_for_server()
        self.get_logger().info("Nav2 action server ready!")
        
        self.get_logger().info("CORRECTED YOLO to Nav Goal bridge initialized")
        self.get_logger().info(f"Approach distance: {self.approach_distance}m")
        self.get_logger().info(f"Min confidence: {self.min_confidence}")

    def ball_position_callback(self, msg):
        """Update ball position"""
        self.current_ball_position = msg
        self.process_detection()

    def confidence_callback(self, msg):
        """Update detection confidence"""
        self.current_confidence = msg.data
        self.process_detection()

    def process_detection(self):
        """Process ball detection and send navigation goal if appropriate"""
        if not self.should_navigate():
            return
            
        # Calculate approach goal directly from ball position
        goal_pose = self.calculate_approach_goal()
        if goal_pose is None:
            return
            
        # Send navigation goal
        self.send_navigation_goal(goal_pose)

    def should_navigate(self):
        """Check if we should send a new navigation goal"""
        # Need both position and confidence
        if self.current_ball_position is None or self.current_confidence == 0.0:
            return False
            
        # Check confidence threshold
        if self.current_confidence < self.min_confidence:
            return False
            
        # Check cooldown period
        current_time = self.get_clock().now().nanoseconds / 1e9
        if current_time - self.last_navigation_time < self.detection_cooldown:
            return False
            
        # Don't send new goals while navigating
        if self.navigating:
            return False
            
        return True

    def calculate_approach_goal(self):
        """Calculate approach goal from ball position"""
        ball_x = self.current_ball_position.x
        ball_y = self.current_ball_position.y
        
        # Calculate distance to ball from robot origin (0,0)
        distance_to_ball = math.sqrt(ball_x*ball_x + ball_y*ball_y)
        
        self.get_logger().info(f"Ball at ({ball_x:.3f}, {ball_y:.3f}), distance: {distance_to_ball:.3f}m")
        
        # Check if ball is too close already
        if distance_to_ball <= self.approach_distance:
            self.get_logger().info("Ball is already within approach distance!")
            return None
            
        # Calculate approach point: move towards ball but stop at approach_distance
        scale = (distance_to_ball - self.approach_distance) / distance_to_ball
        approach_x = ball_x * scale
        approach_y = ball_y * scale
        
        # Create goal pose
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.header.stamp = self.get_clock().now().to_msg()
        
        goal.pose.position.x = approach_x
        goal.pose.position.y = approach_y
        goal.pose.position.z = 0.0
        
        # Orient towards the ball
        yaw = math.atan2(ball_y, ball_x)
        goal.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.orientation.w = math.cos(yaw / 2.0)
        
        self.get_logger().info(f"Approach goal: ({approach_x:.3f}, {approach_y:.3f})")
        self.get_logger().info(f"Expected final distance to ball: {self.approach_distance:.3f}m")
        
        return goal

    def send_navigation_goal(self, goal_pose):
        """Send navigation goal to Nav2"""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info(f"Sending navigation goal to ({goal_pose.pose.position.x:.3f}, {goal_pose.pose.position.y:.3f})")
        
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
    
    node = YoloToNavGoalCorrected()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
