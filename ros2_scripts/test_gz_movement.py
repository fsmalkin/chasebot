#!/usr/bin/env python3
"""
Slice 8.5: Movement Validation Test Script
Tests robot movement in GUI environment with gz_ros2_control

Date: January 5, 2025
Objective: Validate robot responds to /cmd_vel commands in GUI simulation
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import time
import math

class MovementValidator(Node):
    def __init__(self):
        super().__init__('movement_validator')
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Subscribers
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        
        # State tracking
        self.current_pose = None
        self.initial_pose = None
        self.test_active = False
        
        self.get_logger().info("Movement Validator initialized")
        self.get_logger().info("Waiting for odometry data...")

    def odom_callback(self, msg):
        """Track robot position for movement validation"""
        self.current_pose = msg.pose.pose
        if self.initial_pose is None:
            self.initial_pose = msg.pose.pose
            self.get_logger().info(f"Initial position recorded: x={self.initial_pose.position.x:.3f}, y={self.initial_pose.position.y:.3f}")

    def stop_robot(self):
        """Send stop command"""
        stop_cmd = Twist()
        self.cmd_vel_pub.publish(stop_cmd)
        self.get_logger().info("Stop command sent")

    def move_forward(self, distance=0.5, speed=0.2):
        """Move robot forward for specified distance"""
        self.get_logger().info(f"Testing forward movement: {distance}m at {speed}m/s")
        
        if self.current_pose is None:
            self.get_logger().error("No odometry data available!")
            return False
            
        start_x = self.current_pose.position.x
        target_distance = distance
        
        # Create forward movement command
        move_cmd = Twist()
        move_cmd.linear.x = speed
        
        # Move until target distance reached
        start_time = time.time()
        timeout = 10.0  # 10 second timeout
        
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                self.get_logger().error("Movement timeout!")
                self.stop_robot()
                return False
            
            # Publish movement command
            self.cmd_vel_pub.publish(move_cmd)
            
            # Check if we've reached target
            if self.current_pose is not None:
                current_distance = abs(self.current_pose.position.x - start_x)
                if current_distance >= target_distance:
                    self.stop_robot()
                    self.get_logger().info(f"Forward movement complete: moved {current_distance:.3f}m")
                    return True
            
            # Sleep for control loop
            time.sleep(0.1)

    def rotate_robot(self, angle_degrees=90, angular_speed=0.5):
        """Rotate robot by specified angle"""
        self.get_logger().info(f"Testing rotation: {angle_degrees}° at {angular_speed}rad/s")
        
        if self.current_pose is None:
            self.get_logger().error("No odometry data available!")
            return False
        
        # Convert to radians
        target_angle = math.radians(angle_degrees)
        
        # Create rotation command
        rotate_cmd = Twist()
        rotate_cmd.angular.z = angular_speed if angle_degrees > 0 else -angular_speed
        
        # Rotate for calculated time
        rotation_time = abs(target_angle / angular_speed)
        start_time = time.time()
        
        while time.time() - start_time < rotation_time:
            self.cmd_vel_pub.publish(rotate_cmd)
            time.sleep(0.1)
        
        self.stop_robot()
        self.get_logger().info(f"Rotation complete: {angle_degrees}°")
        return True

    def test_square_pattern(self, side_length=0.3):
        """Test robot movement in square pattern"""
        self.get_logger().info(f"Testing square pattern: {side_length}m sides")
        
        for i in range(4):
            self.get_logger().info(f"Square side {i+1}/4")
            
            # Move forward
            if not self.move_forward(distance=side_length, speed=0.15):
                return False
                
            time.sleep(1.0)  # Pause between movements
            
            # Rotate 90 degrees
            if not self.rotate_robot(angle_degrees=90, angular_speed=0.3):
                return False
                
            time.sleep(1.0)  # Pause between movements
        
        self.get_logger().info("Square pattern test complete!")
        return True

    def run_movement_tests(self):
        """Execute comprehensive movement test sequence"""
        self.get_logger().info("=== STARTING MOVEMENT VALIDATION TESTS ===")
        
        # Wait for odometry
        while self.current_pose is None:
            self.get_logger().info("Waiting for odometry data...")
            rclpy.spin_once(self, timeout_sec=1.0)
        
        # Test 1: Simple forward movement
        self.get_logger().info("\n--- TEST 1: Forward Movement ---")
        if not self.move_forward(distance=0.3, speed=0.2):
            self.get_logger().error("TEST 1 FAILED: Forward movement")
            return False
        
        time.sleep(2.0)
        
        # Test 2: Rotation
        self.get_logger().info("\n--- TEST 2: Rotation ---")
        if not self.rotate_robot(angle_degrees=180, angular_speed=0.4):
            self.get_logger().error("TEST 2 FAILED: Rotation")
            return False
        
        time.sleep(2.0)
        
        # Test 3: Return to start
        self.get_logger().info("\n--- TEST 3: Return Movement ---")
        if not self.move_forward(distance=0.3, speed=0.2):
            self.get_logger().error("TEST 3 FAILED: Return movement")
            return False
        
        time.sleep(2.0)
        
        # Test 4: Square pattern
        self.get_logger().info("\n--- TEST 4: Square Pattern ---")
        if not self.test_square_pattern(side_length=0.2):
            self.get_logger().error("TEST 4 FAILED: Square pattern")
            return False
        
        # Final position report
        if self.current_pose and self.initial_pose:
            final_x = self.current_pose.position.x
            final_y = self.current_pose.position.y
            initial_x = self.initial_pose.position.x
            initial_y = self.initial_pose.position.y
            
            distance_moved = math.sqrt(
                (final_x - initial_x)**2 + (final_y - initial_y)**2
            )
            
            self.get_logger().info(f"\n=== MOVEMENT TEST RESULTS ===")
            self.get_logger().info(f"Initial position: x={initial_x:.3f}, y={initial_y:.3f}")
            self.get_logger().info(f"Final position: x={final_x:.3f}, y={final_y:.3f}")
            self.get_logger().info(f"Total distance from start: {distance_moved:.3f}m")
        
        self.get_logger().info("=== ALL MOVEMENT TESTS PASSED! ===")
        return True

def main():
    rclpy.init()
    
    validator = MovementValidator()
    
    try:
        # Run movement validation tests
        success = validator.run_movement_tests()
        
        if success:
            validator.get_logger().info("✅ MOVEMENT VALIDATION SUCCESS: Robot control confirmed!")
            validator.get_logger().info("System ready for D415 camera integration.")
        else:
            validator.get_logger().error("❌ MOVEMENT VALIDATION FAILED: Check robot control system")
            
    except KeyboardInterrupt:
        validator.get_logger().info("Movement test interrupted")
    finally:
        validator.stop_robot()
        validator.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
