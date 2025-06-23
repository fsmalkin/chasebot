#!/usr/bin/env python3
"""
ROS 2 Square Pattern Test
Programmatic square movement pattern for ChaseBot UAT validation
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import math


class SquarePatternTest(Node):
    """Square pattern movement test for ROS 2 ChaseBot"""
    
    def __init__(self):
        super().__init__('square_pattern_test')
        
        # Create publisher for cmd_vel
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Movement parameters
        self.linear_speed = 0.2  # m/s
        self.angular_speed = 0.5  # rad/s
        self.side_length = 1.0  # meters
        self.turn_angle = math.pi / 2  # 90 degrees in radians
        
        # Calculated durations
        self.forward_duration = self.side_length / self.linear_speed
        self.turn_duration = self.turn_angle / self.angular_speed
        
        self.get_logger().info("Square Pattern Test initialized")
        self.get_logger().info(f"Square: {self.side_length}m sides, forward {self.forward_duration:.1f}s, turn {self.turn_duration:.1f}s")
        
    def move_forward(self):
        """Move forward for one side of the square"""
        try:
            move_cmd = Twist()
            move_cmd.linear.x = self.linear_speed
            move_cmd.angular.z = 0.0
            
            self.get_logger().info(f"Moving forward {self.side_length}m...")
            
            start_time = time.time()
            while time.time() - start_time < self.forward_duration:
                self.cmd_vel_pub.publish(move_cmd)
                time.sleep(0.1)
                
            self.get_logger().info("Forward movement complete")
            
        except Exception as e:
            self.get_logger().error(f"Error during forward movement: {str(e)}")
            self._emergency_stop()
            
    def turn_left(self):
        """Turn left 90 degrees"""
        try:
            turn_cmd = Twist()
            turn_cmd.linear.x = 0.0
            turn_cmd.angular.z = self.angular_speed  # Positive for counter-clockwise
            
            self.get_logger().info("Turning left 90°...")
            
            start_time = time.time()
            while time.time() - start_time < self.turn_duration:
                self.cmd_vel_pub.publish(turn_cmd)
                time.sleep(0.1)
                
            self.get_logger().info("Left turn complete")
            
        except Exception as e:
            self.get_logger().error(f"Error during turn: {str(e)}")
            self._emergency_stop()
            
    def _emergency_stop(self):
        """Emergency stop the robot"""
        stop_cmd = Twist()
        stop_cmd.linear.x = 0.0
        stop_cmd.angular.z = 0.0
        
        for _ in range(10):
            self.cmd_vel_pub.publish(stop_cmd)
            time.sleep(0.1)
            
    def stop_robot(self):
        """Stop the robot cleanly"""
        stop_cmd = Twist()
        stop_cmd.linear.x = 0.0
        stop_cmd.angular.z = 0.0
        
        self.get_logger().info("Stopping robot...")
        for _ in range(10):
            self.cmd_vel_pub.publish(stop_cmd)
            time.sleep(0.1)
            
    def execute_square_pattern(self):
        """Execute complete square pattern"""
        try:
            self.get_logger().info("Starting square pattern execution...")
            
            # Execute 4 sides of the square
            for side in range(4):
                self.get_logger().info(f"Executing side {side + 1}/4")
                
                # Move forward for one side
                self.move_forward()
                
                # Brief pause
                time.sleep(0.5)
                
                # Turn left 90 degrees (except after the last side)
                if side < 3:  # Don't turn after the 4th side
                    self.turn_left()
                    time.sleep(0.5)  # Brief pause after turn
                    
            # Final stop
            self.stop_robot()
            self.get_logger().info("Square pattern completed successfully!")
            
        except Exception as e:
            self.get_logger().error(f"Error during square pattern: {str(e)}")
            self._emergency_stop()


def main(args=None):
    """Main function"""
    rclpy.init(args=args)
    
    try:
        # Create and run the test
        square_test = SquarePatternTest()
        
        # Wait for publishers to be ready
        time.sleep(1.0)
        
        # Execute the square pattern
        square_test.execute_square_pattern()
        
        # Keep node alive for a moment to ensure all messages are sent
        time.sleep(1.0)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Cleanup
        if 'square_test' in locals():
            square_test.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
