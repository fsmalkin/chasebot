#!/usr/bin/env python3
"""
Test script to validate gz_ros2_control differential drive controller
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import JointState
import time

class ControllerTestNode(Node):
    def __init__(self):
        super().__init__('controller_test_node')
        
        # Publisher for velocity commands
        self.cmd_vel_pub = self.create_publisher(
            TwistStamped, 
            '/jetbot_base_controller/cmd_vel', 
            10
        )
        
        # Subscriber for joint states
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )
        
        self.initial_positions = None
        self.current_positions = None
        
        # Give time for connections
        time.sleep(1.0)
        
        self.get_logger().info('Starting controller movement test...')
        
    def joint_state_callback(self, msg):
        """Store joint positions"""
        if self.initial_positions is None:
            self.initial_positions = dict(zip(msg.name, msg.position))
            self.get_logger().info(f'Initial positions: {self.initial_positions}')
        
        self.current_positions = dict(zip(msg.name, msg.position))
        
    def send_velocity_command(self, linear_x=0.0, angular_z=0.0):
        """Send velocity command to robot"""
        msg = TwistStamped()
        msg.twist.linear.x = linear_x
        msg.twist.angular.z = angular_z
        self.cmd_vel_pub.publish(msg)
        
    def test_forward_movement(self):
        """Test forward movement"""
        self.get_logger().info('Testing forward movement (0.2 m/s for 2 seconds)...')
        
        # Send forward command
        start_time = time.time()
        while time.time() - start_time < 2.0:
            self.send_velocity_command(linear_x=0.2)
            rclpy.spin_once(self, timeout_sec=0.1)
            
        # Stop
        self.send_velocity_command()
        time.sleep(0.5)
        
        # Check movement
        if self.current_positions and self.initial_positions:
            left_delta = self.current_positions.get('left_wheel_joint', 0) - self.initial_positions.get('left_wheel_joint', 0)
            right_delta = self.current_positions.get('right_wheel_joint', 0) - self.initial_positions.get('right_wheel_joint', 0)
            self.get_logger().info(f'Forward test - Left wheel delta: {left_delta:.3f} rad, Right wheel delta: {right_delta:.3f} rad')
            
            # Both wheels should have moved forward (positive rotation)
            if left_delta > 0.1 and right_delta > 0.1:
                self.get_logger().info('✓ Forward movement test PASSED')
                return True
            else:
                self.get_logger().error('✗ Forward movement test FAILED')
                return False
                
    def test_rotation_movement(self):
        """Test rotation movement"""
        self.get_logger().info('Testing rotation movement (0.5 rad/s for 2 seconds)...')
        
        # Reset initial positions
        self.initial_positions = self.current_positions.copy() if self.current_positions else None
        
        # Send rotation command
        start_time = time.time()
        while time.time() - start_time < 2.0:
            self.send_velocity_command(angular_z=0.5)
            rclpy.spin_once(self, timeout_sec=0.1)
            
        # Stop
        self.send_velocity_command()
        time.sleep(0.5)
        
        # Check movement
        if self.current_positions and self.initial_positions:
            left_delta = self.current_positions.get('left_wheel_joint', 0) - self.initial_positions.get('left_wheel_joint', 0)
            right_delta = self.current_positions.get('right_wheel_joint', 0) - self.initial_positions.get('right_wheel_joint', 0)
            self.get_logger().info(f'Rotation test - Left wheel delta: {left_delta:.3f} rad, Right wheel delta: {right_delta:.3f} rad')
            
            # For positive rotation, left wheel should go backward (negative) and right forward (positive)
            if left_delta < -0.1 and right_delta > 0.1:
                self.get_logger().info('✓ Rotation movement test PASSED')
                return True
            else:
                self.get_logger().error('✗ Rotation movement test FAILED')
                return False

def main(args=None):
    rclpy.init(args=args)
    node = ControllerTestNode()
    
    try:
        # Wait for initial joint state
        for _ in range(10):
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.initial_positions:
                break
        
        # Run tests
        forward_passed = node.test_forward_movement()
        rotation_passed = node.test_rotation_movement()
        
        # Summary
        node.get_logger().info('=' * 50)
        if forward_passed and rotation_passed:
            node.get_logger().info('✓ ALL TESTS PASSED - gz_ros2_control is working correctly!')
        else:
            node.get_logger().error('✗ SOME TESTS FAILED - Check controller configuration')
        node.get_logger().info('=' * 50)
        
    except Exception as e:
        node.get_logger().error(f'Test failed with error: {e}')
    finally:
        # Ensure robot stops
        node.send_velocity_command()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
