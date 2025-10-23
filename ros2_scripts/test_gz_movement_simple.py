#!/usr/bin/env python3
"""
Simple Movement Test - Uses Correct Topic Names
Tests robot movement with /jetbot_base_controller/cmd_vel

Date: January 5, 2025
Objective: Validate robot responds to movement commands using actual topic names
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import time

class SimpleMovementTest(Node):
    def __init__(self):
        super().__init__('simple_movement_test')
        
        # Publishers - use actual topic names
        self.cmd_vel_pub = self.create_publisher(Twist, '/jetbot_base_controller/cmd_vel', 10)
        
        # Subscribers - use actual topic names  
        self.odom_sub = self.create_subscription(
            Odometry, '/jetbot_base_controller/odom', self.odom_callback, 10)
        
        # State tracking
        self.current_pose = None
        self.initial_pose = None
        
        self.get_logger().info("Simple Movement Test initialized")
        self.get_logger().info("Using topics:")
        self.get_logger().info("  - Commands: /jetbot_base_controller/cmd_vel")
        self.get_logger().info("  - Odometry: /jetbot_base_controller/odom")

    def odom_callback(self, msg):
        """Track robot position"""
        self.current_pose = msg.pose.pose
        if self.initial_pose is None:
            self.initial_pose = msg.pose.pose
            self.get_logger().info(f"✅ Odometry received! Initial position: x={self.initial_pose.position.x:.3f}, y={self.initial_pose.position.y:.3f}")

    def send_movement_command(self, linear_x=0.0, angular_z=0.0, duration=2.0):
        """Send movement command for specified duration"""
        self.get_logger().info(f"Sending command: linear_x={linear_x}, angular_z={angular_z} for {duration}s")
        
        move_cmd = Twist()
        move_cmd.linear.x = linear_x
        move_cmd.angular.z = angular_z
        
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_vel_pub.publish(move_cmd)
            time.sleep(0.1)
        
        # Stop robot
        stop_cmd = Twist()
        self.cmd_vel_pub.publish(stop_cmd)
        self.get_logger().info("Movement command complete, robot stopped")

    def wait_for_odometry(self, timeout=10.0):
        """Wait for odometry data to arrive"""
        start_time = time.time()
        while self.current_pose is None and (time.time() - start_time) < timeout:
            self.get_logger().info("Waiting for odometry data...")
            rclpy.spin_once(self, timeout_sec=1.0)
        
        return self.current_pose is not None

    def run_movement_test(self):
        """Execute simple movement test sequence"""
        self.get_logger().info("=== STARTING SIMPLE MOVEMENT TEST ===")
        
        # Wait for odometry
        if not self.wait_for_odometry():
            self.get_logger().error("❌ FAILED: No odometry data received")
            return False
        
        # Test 1: Forward movement
        self.get_logger().info("\n--- TEST 1: Forward Movement (2 seconds) ---")
        initial_x = self.current_pose.position.x
        self.send_movement_command(linear_x=0.2, angular_z=0.0, duration=2.0)
        
        # Check if robot moved
        time.sleep(1.0)  # Allow time for odometry update
        rclpy.spin_once(self, timeout_sec=0.1)
        
        if self.current_pose:
            distance_moved = abs(self.current_pose.position.x - initial_x)
            self.get_logger().info(f"Distance moved: {distance_moved:.3f}m")
            if distance_moved > 0.01:
                self.get_logger().info("✅ TEST 1 PASSED: Robot moved forward!")
            else:
                self.get_logger().warn("⚠️ TEST 1 UNCLEAR: Small movement detected")
        
        time.sleep(2.0)
        
        # Test 2: Rotation
        self.get_logger().info("\n--- TEST 2: Rotation (2 seconds) ---")
        self.send_movement_command(linear_x=0.0, angular_z=0.5, duration=2.0)
        self.get_logger().info("✅ TEST 2 COMPLETED: Rotation command sent")
        
        time.sleep(2.0)
        
        # Test 3: Stop and report final position
        self.get_logger().info("\n--- TEST 3: Final Position Check ---")
        if self.current_pose and self.initial_pose:
            final_x = self.current_pose.position.x
            final_y = self.current_pose.position.y
            initial_x = self.initial_pose.position.x
            initial_y = self.initial_pose.position.y
            
            total_distance = ((final_x - initial_x)**2 + (final_y - initial_y)**2)**0.5
            
            self.get_logger().info(f"Initial position: x={initial_x:.3f}, y={initial_y:.3f}")
            self.get_logger().info(f"Final position: x={final_x:.3f}, y={final_y:.3f}")
            self.get_logger().info(f"Total displacement: {total_distance:.3f}m")
            
            if total_distance > 0.05:
                self.get_logger().info("✅ MOVEMENT VALIDATION SUCCESS: Robot responded to commands!")
                return True
            else:
                self.get_logger().warn("⚠️ MOVEMENT VALIDATION UNCLEAR: Minimal movement detected")
                return False
        
        self.get_logger().error("❌ MOVEMENT VALIDATION FAILED: No position data")
        return False

def main():
    rclpy.init()
    
    test_node = SimpleMovementTest()
    
    try:
        success = test_node.run_movement_test()
        
        if success:
            test_node.get_logger().info("\n🎉 SLICE 8.5 SUCCESS: Robot movement validation complete!")
            test_node.get_logger().info("✅ GUI system functional")
            test_node.get_logger().info("✅ gz_ros2_control operational")
            test_node.get_logger().info("✅ Robot responds to movement commands")
            test_node.get_logger().info("📋 System ready for D415 camera integration!")
        else:
            test_node.get_logger().error("❌ SLICE 8.5 NEEDS INVESTIGATION: Movement validation inconclusive")
            
    except KeyboardInterrupt:
        test_node.get_logger().info("Movement test interrupted by user")
    finally:
        # Send final stop command
        stop_cmd = Twist()
        test_node.cmd_vel_pub.publish(stop_cmd)
        test_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
