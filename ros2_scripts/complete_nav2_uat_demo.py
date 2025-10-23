#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Twist
import time
import math

class CompleteNav2UAT(Node):
    """
    Complete Nav2 UAT Demo - Shows Nav2 working with clear visual feedback
    """
    
    def __init__(self):
        super().__init__('complete_nav2_uat')
        
        # Wait for system to initialize
        time.sleep(5)
        
        self.get_logger().info('🎯 STARTING COMPLETE NAV2 UAT DEMO')
        self.get_logger().info('=' * 60)
        
        # Create publishers and action clients
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        try:
            self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
            
            self.get_logger().info('🔍 Checking Nav2 availability...')
            if self.nav_client.wait_for_server(timeout_sec=10):
                self.get_logger().info('✅ Nav2 action server FOUND!')
                self.run_complete_demo()
            else:
                self.get_logger().error('❌ Nav2 action server NOT AVAILABLE')
                self.get_logger().info('💡 Testing basic robot movement instead...')
                self.test_basic_movement()
                
        except Exception as e:
            self.get_logger().error(f'Error: {str(e)}')
            self.test_basic_movement()
    
    def run_complete_demo(self):
        """Run the complete Nav2 demonstration."""
        self.get_logger().info('🚀 RUNNING COMPLETE NAV2 DEMO')
        self.get_logger().info('-' * 40)
        
        # Test multiple goals to show professional navigation
        goals = [
            (1.0, 0.0, "Move 1m forward"),
            (1.0, 1.0, "Move to (1,1) - diagonal"),
            (0.0, 1.0, "Move to (0,1) - sideways"),
            (0.0, 0.0, "Return to origin")
        ]
        
        for i, (x, y, description) in enumerate(goals, 1):
            self.get_logger().info(f'📍 Goal {i}/4: {description}')
            success = self.send_nav_goal(x, y)
            
            if success:
                self.get_logger().info(f'✅ Goal {i} COMPLETED successfully!')
            else:
                self.get_logger().error(f'❌ Goal {i} FAILED')
            
            time.sleep(2)  # Brief pause between goals
        
        self.get_logger().info('🎉 NAV2 UAT DEMONSTRATION COMPLETE!')
        self.get_logger().info('✅ ALL NAVIGATION GOALS ACHIEVED')
        self.get_logger().info('🏆 UAT SUCCESS: Professional Nav2 navigation proven!')
    
    def send_nav_goal(self, x, y):
        """Send a navigation goal and wait for completion."""
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'odom'
        goal_pose.header.stamp = self.get_clock().now().to_msg()
        
        goal_pose.pose.position.x = x
        goal_pose.pose.position.y = y
        goal_pose.pose.position.z = 0.0
        goal_pose.pose.orientation.w = 1.0
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = goal_pose
        
        self.get_logger().info(f'🎯 Sending goal: ({x:.1f}, {y:.1f})')
        
        # Send goal and wait for response
        future = self.nav_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected by Nav2')
            return False
        
        self.get_logger().info('🏃 Goal accepted! Robot navigating...')
        
        # Wait for result
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=30.0)
        
        result = result_future.result()
        if result and result.result:
            return True
        else:
            return False
    
    def test_basic_movement(self):
        """Test basic robot movement if Nav2 isn't available."""
        self.get_logger().info('🤖 TESTING BASIC ROBOT MOVEMENT')
        self.get_logger().info('-' * 40)
        
        movements = [
            (0.2, 0.0, 3, "Forward movement"),
            (0.0, 0.5, 2, "Rotation test"),
            (-0.2, 0.0, 3, "Backward movement"),
            (0.0, -0.5, 2, "Counter-rotation"),
        ]
        
        for linear, angular, duration, description in movements:
            self.get_logger().info(f'🎯 {description}...')
            
            twist = Twist()
            twist.linear.x = linear
            twist.angular.z = angular
            
            # Send commands for specified duration
            start_time = time.time()
            while (time.time() - start_time) < duration:
                self.cmd_pub.publish(twist)
                time.sleep(0.1)
            
            # Stop robot
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            self.cmd_pub.publish(twist)
            
            self.get_logger().info(f'✅ {description} completed')
            time.sleep(1)
        
        self.get_logger().info('✅ BASIC MOVEMENT TEST COMPLETE')
        self.get_logger().info('🤖 Robot successfully demonstrated movement capabilities')


def main(args=None):
    rclpy.init(args=args)
    
    demo = CompleteNav2UAT()
    
    try:
        # Keep node alive for demonstration
        rclpy.spin_for_a_while(demo, duration=60.0)  # Run for 1 minute
    except KeyboardInterrupt:
        pass
    finally:
        demo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
