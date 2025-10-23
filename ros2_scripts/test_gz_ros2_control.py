#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
import time
import math

class GzRos2ControlTester(Node):
    """Test script for gz_ros2_control integration"""
    
    def __init__(self):
        super().__init__('gz_ros2_control_tester')
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Subscribers
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self.joint_state_callback, 10)
        
        # State tracking
        self.odom_received = False
        self.joint_states_received = False
        self.latest_odom = None
        self.latest_joint_states = None
        
        self.get_logger().info("gz_ros2_control tester initialized")
        self.get_logger().info("Waiting for topics...")
        
        # Start the test sequence
        self.test_timer = self.create_timer(1.0, self.run_test_sequence)
        self.test_step = 0
        self.test_start_time = time.time()
        
    def odom_callback(self, msg):
        """Handle odometry messages"""
        self.odom_received = True
        self.latest_odom = msg
        if not hasattr(self, 'odom_logged'):
            self.get_logger().info("✓ Odometry topic active")
            self.odom_logged = True
    
    def joint_state_callback(self, msg):
        """Handle joint state messages"""
        self.joint_states_received = True
        self.latest_joint_states = msg
        if not hasattr(self, 'joint_states_logged'):
            self.get_logger().info("✓ Joint states topic active")
            self.get_logger().info(f"  Joints: {msg.name}")
            self.joint_states_logged = True
    
    def run_test_sequence(self):
        """Run the test sequence"""
        elapsed = time.time() - self.test_start_time
        
        if self.test_step == 0:
            # Step 0: Wait for topics (first 5 seconds)
            if elapsed < 5.0:
                return
            
            if not self.odom_received:
                self.get_logger().error("✗ No odometry received after 5 seconds")
                return
            
            if not self.joint_states_received:
                self.get_logger().error("✗ No joint states received after 5 seconds")
                return
                
            self.get_logger().info("=== Starting movement tests ===")
            self.test_step = 1
            self.test_start_time = time.time()
        
        elif self.test_step == 1:
            # Step 1: Forward movement test (5 seconds)
            if elapsed < 5.0:
                twist = Twist()
                twist.linear.x = 0.1  # 0.1 m/s forward
                self.cmd_vel_pub.publish(twist)
                
                if elapsed == 1.0:  # Log once
                    self.get_logger().info("→ Testing forward movement (0.1 m/s)")
                return
            
            # Stop and proceed to next test
            self.stop_robot()
            self.get_logger().info("✓ Forward movement test complete")
            self.test_step = 2
            self.test_start_time = time.time()
        
        elif self.test_step == 2:
            # Step 2: Rotation test (5 seconds)
            if elapsed < 5.0:
                twist = Twist()
                twist.angular.z = 0.5  # 0.5 rad/s rotation
                self.cmd_vel_pub.publish(twist)
                
                if elapsed == 1.0:  # Log once
                    self.get_logger().info("↻ Testing rotation (0.5 rad/s)")
                return
            
            # Stop and proceed to next test
            self.stop_robot()
            self.get_logger().info("✓ Rotation test complete")
            self.test_step = 3
            self.test_start_time = time.time()
        
        elif self.test_step == 3:
            # Step 3: Combined movement test (5 seconds)
            if elapsed < 5.0:
                twist = Twist()
                twist.linear.x = 0.05  # Slow forward
                twist.angular.z = 0.3  # Slow turn
                self.cmd_vel_pub.publish(twist)
                
                if elapsed == 1.0:  # Log once
                    self.get_logger().info("↗ Testing combined movement")
                return
            
            # Stop and complete tests
            self.stop_robot()
            self.get_logger().info("✓ Combined movement test complete")
            self.test_step = 4
        
        elif self.test_step == 4:
            # Step 4: Final status report
            self.report_final_status()
            self.test_step = 5  # Done
        
        elif self.test_step == 5:
            # Keep publishing stop commands
            self.stop_robot()
    
    def stop_robot(self):
        """Send stop command"""
        twist = Twist()  # All zeros
        self.cmd_vel_pub.publish(twist)
    
    def report_final_status(self):
        """Report final test status"""
        self.get_logger().info("=== Test Results ===")
        self.get_logger().info(f"✓ Odometry active: {self.odom_received}")
        self.get_logger().info(f"✓ Joint states active: {self.joint_states_received}")
        
        if self.latest_odom:
            pos = self.latest_odom.pose.pose.position
            self.get_logger().info(f"✓ Final position: x={pos.x:.3f}, y={pos.y:.3f}")
        
        if self.latest_joint_states:
            if 'left_wheel_joint' in self.latest_joint_states.name:
                left_idx = self.latest_joint_states.name.index('left_wheel_joint')
                left_vel = self.latest_joint_states.velocity[left_idx]
                self.get_logger().info(f"✓ Left wheel velocity: {left_vel:.3f} rad/s")
            
            if 'right_wheel_joint' in self.latest_joint_states.name:
                right_idx = self.latest_joint_states.name.index('right_wheel_joint')
                right_vel = self.latest_joint_states.velocity[right_idx]
                self.get_logger().info(f"✓ Right wheel velocity: {right_vel:.3f} rad/s")
        
        self.get_logger().info("=== gz_ros2_control integration test COMPLETE ===")
        self.get_logger().info("If you see movement in Gazebo, the integration is working!")

def main(args=None):
    rclpy.init(args=args)
    
    tester = GzRos2ControlTester()
    
    try:
        rclpy.spin(tester)
    except KeyboardInterrupt:
        tester.get_logger().info("Test interrupted by user")
    finally:
        # Send final stop command
        tester.stop_robot()
        tester.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
