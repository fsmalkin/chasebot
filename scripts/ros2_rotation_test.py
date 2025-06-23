#!/usr/bin/env python3
"""
ROS 2 Rotation Test
Programmatic rotation control for ChaseBot UAT validation
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import math


class RotationTest(Node):
    """Rotation test for ROS 2 ChaseBot"""
    
    def __init__(self):
        super().__init__('rotation_test')
        
        # Create publisher for cmd_vel
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Rotation parameters
        self.angular_speed = 0.5  # rad/s
        self.target_angle = 2 * math.pi  # 360 degrees in radians
        self.rotation_duration = self.target_angle / self.angular_speed  # calculated duration
        
        self.get_logger().info("Rotation Test initialized")
        self.get_logger().info(f"Will rotate 360° at {self.angular_speed} rad/s for {self.rotation_duration:.1f} seconds")
        
    def execute_clockwise_rotation(self):
        """Execute clockwise rotation test"""
        self._execute_rotation(-self.angular_speed, "clockwise")
        
    def execute_counterclockwise_rotation(self):
        """Execute counter-clockwise rotation test"""
        self._execute_rotation(self.angular_speed, "counter-clockwise")
        
    def _execute_rotation(self, angular_velocity, direction):
        """Execute rotation with given angular velocity"""
        try:
            # Create Twist message for rotation
            rotate_cmd = Twist()
            rotate_cmd.linear.x = 0.0
            rotate_cmd.angular.z = angular_velocity
            
            # Create stop command
            stop_cmd = Twist()
            stop_cmd.linear.x = 0.0
            stop_cmd.angular.z = 0.0
            
            self.get_logger().info(f"Starting {direction} rotation...")
            
            # Record start time
            start_time = time.time()
            
            # Rotation loop with safety timeout
            while time.time() - start_time < self.rotation_duration:
                self.cmd_vel_pub.publish(rotate_cmd)
                time.sleep(0.1)  # 10Hz publishing rate
                
            # Stop the robot
            self.get_logger().info(f"{direction.capitalize()} rotation complete - stopping robot")
            for _ in range(10):  # Send stop commands for 1 second
                self.cmd_vel_pub.publish(stop_cmd)
                time.sleep(0.1)
                
            self.get_logger().info(f"{direction.capitalize()} rotation test completed successfully")
            
        except Exception as e:
            self.get_logger().error(f"Error during rotation: {str(e)}")
            # Emergency stop
            stop_cmd = Twist()
            for _ in range(10):
                self.cmd_vel_pub.publish(stop_cmd)
                time.sleep(0.1)
                
    def execute_full_rotation_test(self):
        """Execute complete rotation test sequence"""
        self.get_logger().info("Starting complete rotation test sequence")
        
        # Test clockwise rotation
        self.execute_clockwise_rotation()
        time.sleep(2.0)  # Pause between tests
        
        # Test counter-clockwise rotation
        self.execute_counterclockwise_rotation()
        
        self.get_logger().info("Complete rotation test sequence finished")


def main(args=None):
    """Main function"""
    rclpy.init(args=args)
    
    try:
        # Create and run the test
        rotation_test = RotationTest()
        
        # Wait for publishers to be ready
        time.sleep(1.0)
        
        # Execute the rotation test sequence
        rotation_test.execute_full_rotation_test()
        
        # Keep node alive for a moment to ensure all messages are sent
        time.sleep(1.0)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Cleanup
        if 'rotation_test' in locals():
            rotation_test.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
