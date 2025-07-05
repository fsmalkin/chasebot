#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Odometry
from action_msgs.msg import GoalStatusArray
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from tf2_ros import TransformBroadcaster, Buffer, TransformListener, TransformException
import tf2_geometry_msgs
import time

class Nav2MovementDebugger(Node):
    def __init__(self):
        super().__init__('nav2_movement_debugger')
        
        self.get_logger().info('=== Nav2 Movement Debugger Started ===')
        
        # Subscribers
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        self.goal_status_sub = self.create_subscription(
            GoalStatusArray, '/navigate_to_pose/_action/status',
            self.goal_status_callback, 10)
        
        # TF Buffer
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Action client for navigation
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Monitoring variables
        self.last_cmd_vel = None
        self.last_cmd_vel_time = None
        self.last_odom = None
        self.last_odom_time = None
        self.goal_active = False
        
        # Create timers
        self.create_timer(1.0, self.check_status)
        self.create_timer(5.0, self.test_manual_navigation)
        
        self.get_logger().info('Monitoring /cmd_vel, /odom, and navigation status...')
        
    def cmd_vel_callback(self, msg):
        self.last_cmd_vel = msg
        self.last_cmd_vel_time = self.get_clock().now()
        self.get_logger().info(f'CMD_VEL received: linear.x={msg.linear.x:.3f}, angular.z={msg.angular.z:.3f}')
        
    def odom_callback(self, msg):
        self.last_odom = msg
        self.last_odom_time = self.get_clock().now()
        
    def goal_status_callback(self, msg):
        if msg.status_list:
            status = msg.status_list[0].status
            self.goal_active = (status == 1 or status == 2)  # ACCEPTED or EXECUTING
            self.get_logger().debug(f'Goal status: {status}')
            
    def check_status(self):
        self.get_logger().info('=== Status Check ===')
        
        # Check cmd_vel
        if self.last_cmd_vel_time:
            time_since_cmd = (self.get_clock().now() - self.last_cmd_vel_time).nanoseconds / 1e9
            if time_since_cmd < 2.0:
                self.get_logger().info(f'✅ CMD_VEL: Active ({time_since_cmd:.1f}s ago)')
            else:
                self.get_logger().warn(f'❌ CMD_VEL: Stale ({time_since_cmd:.1f}s ago)')
        else:
            self.get_logger().warn('❌ CMD_VEL: Never received')
            
        # Check odometry
        if self.last_odom_time:
            time_since_odom = (self.get_clock().now() - self.last_odom_time).nanoseconds / 1e9
            if time_since_odom < 1.0:
                self.get_logger().info(f'✅ ODOM: Active ({time_since_odom:.1f}s ago)')
            else:
                self.get_logger().warn(f'❌ ODOM: Stale ({time_since_odom:.1f}s ago)')
        else:
            self.get_logger().warn('❌ ODOM: Never received')
            
        # Check transforms
        self.check_transforms()
        
        # Check goal status
        if self.goal_active:
            self.get_logger().info('✅ Navigation Goal: ACTIVE')
        else:
            self.get_logger().info('⚪ Navigation Goal: None active')
            
    def check_transforms(self):
        transform_pairs = [
            ('map', 'odom'),
            ('odom', 'base_link'),
            ('base_link', 'camera_link'),
            ('map', 'base_link')  # Full chain
        ]
        
        for parent, child in transform_pairs:
            try:
                transform = self.tf_buffer.lookup_transform(
                    parent, child, rclpy.time.Time(), timeout=rclpy.duration.Duration(seconds=0.1))
                age = (self.get_clock().now() - transform.header.stamp).nanoseconds / 1e9
                if age < 1.0:
                    self.get_logger().info(f'✅ TF {parent}→{child}: OK (age: {age:.3f}s)')
                else:
                    self.get_logger().warn(f'⚠️  TF {parent}→{child}: Old (age: {age:.3f}s)')
            except TransformException as e:
                self.get_logger().error(f'❌ TF {parent}→{child}: {str(e)}')
                
    def test_manual_navigation(self):
        """Send a test navigation goal every 5 seconds"""
        if not self.nav_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().warn('Navigation action server not available')
            return
            
        # Only send if no goal is active
        if self.goal_active:
            self.get_logger().info('Skipping test goal - navigation already active')
            return
            
        # Send a simple forward goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'base_link'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = 0.5  # 50cm forward
        goal_msg.pose.pose.position.y = 0.0
        goal_msg.pose.pose.position.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0
        
        self.get_logger().info('Sending test navigation goal: 0.5m forward in base_link frame')
        future = self.nav_client.send_goal_async(goal_msg)
        future.add_done_callback(self.goal_response_callback)
        
    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Test goal rejected!')
        else:
            self.get_logger().info('Test goal accepted!')
            
def main(args=None):
    rclpy.init(args=args)
    
    debugger = Nav2MovementDebugger()
    
    try:
        rclpy.spin(debugger)
    except KeyboardInterrupt:
        pass
    finally:
        debugger.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
