#!/usr/bin/env python3
"""
ROS 2 Movement Test Suite
Comprehensive automated movement testing for ChaseBot UAT validation
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time
import math
import sys


class MovementTestSuite(Node):
    """Comprehensive movement test suite for ROS 2 ChaseBot"""
    
    def __init__(self):
        super().__init__('movement_test_suite')
        
        # Create publisher for cmd_vel
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Test parameters
        self.linear_speed = 0.2  # m/s
        self.angular_speed = 0.5  # rad/s
        self.test_pause = 3.0  # seconds between tests
        
        self.get_logger().info("Movement Test Suite initialized")
        self.get_logger().info("Will execute: Forward → Rotation → Square Pattern")
        
    def _publish_command(self, linear_x=0.0, angular_z=0.0, duration=1.0):
        """Publish movement command for specified duration"""
        cmd = Twist()
        cmd.linear.x = linear_x
        cmd.angular.z = angular_z
        
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_vel_pub.publish(cmd)
            time.sleep(0.1)
            
    def _stop_robot(self, duration=1.0):
        """Stop the robot for specified duration"""
        self.get_logger().info("Stopping robot...")
        self._publish_command(0.0, 0.0, duration)
        
    def test_forward_movement(self):
        """Test 1: Forward movement"""
        self.get_logger().info("=== TEST 1: FORWARD MOVEMENT ===")
        self.get_logger().info("Moving forward 3 seconds at 0.2 m/s")
        
        self._publish_command(self.linear_speed, 0.0, 3.0)
        self._stop_robot()
        
        self.get_logger().info("Forward movement test completed")
        
    def test_rotation(self):
        """Test 2: Rotation test"""
        self.get_logger().info("=== TEST 2: ROTATION TEST ===")
        
        # Calculate duration for 360-degree rotation
        rotation_duration = (2 * math.pi) / self.angular_speed
        
        # Clockwise rotation
        self.get_logger().info(f"Rotating clockwise 360° in {rotation_duration:.1f} seconds")
        self._publish_command(0.0, -self.angular_speed, rotation_duration)
        self._stop_robot()
        
        time.sleep(2.0)  # Pause between rotations
        
        # Counter-clockwise rotation
        self.get_logger().info(f"Rotating counter-clockwise 360° in {rotation_duration:.1f} seconds")
        self._publish_command(0.0, self.angular_speed, rotation_duration)
        self._stop_robot()
        
        self.get_logger().info("Rotation test completed")
        
    def test_square_pattern(self):
        """Test 3: Square pattern"""
        self.get_logger().info("=== TEST 3: SQUARE PATTERN ===")
        
        side_length = 1.0  # meters
        forward_duration = side_length / self.linear_speed
        turn_duration = (math.pi / 2) / self.angular_speed  # 90 degrees
        
        self.get_logger().info(f"Executing 1m x 1m square pattern")
        
        for side in range(4):
            self.get_logger().info(f"Side {side + 1}/4: Moving forward {side_length}m")
            self._publish_command(self.linear_speed, 0.0, forward_duration)
            
            time.sleep(0.5)  # Brief pause
            
            if side < 3:  # Don't turn after the last side
                self.get_logger().info(f"Turning left 90°")
                self._publish_command(0.0, self.angular_speed, turn_duration)
                time.sleep(0.5)
                
        self._stop_robot()
        self.get_logger().info("Square pattern test completed")
        
    def run_complete_test_suite(self):
        """Execute complete test suite"""
        try:
            self.get_logger().info("Starting ChaseBot Movement Test Suite...")
            self.get_logger().info("Total estimated time: ~60 seconds")
            
            # Test 1: Forward Movement
            self.test_forward_movement()
            time.sleep(self.test_pause)
            
            # Test 2: Rotation
            self.test_rotation()
            time.sleep(self.test_pause)
            
            # Test 3: Square Pattern
            self.test_square_pattern()
            
            # Final summary
            self.get_logger().info("=== TEST SUITE COMPLETE ===")
            self.get_logger().info("All movement tests executed successfully!")
            self.get_logger().info("UAT validation: Observe robot movement in Gazebo simulation")
            
        except Exception as e:
            self.get_logger().error(f"Test suite failed: {str(e)}")
            self._stop_robot(2.0)  # Emergency stop
            
    def run_single_test(self, test_name):
        """Run a single test by name"""
        test_map = {
            'forward': self.test_forward_movement,
            'rotation': self.test_rotation,
            'square': self.test_square_pattern
        }
        
        if test_name in test_map:
            self.get_logger().info(f"Running single test: {test_name}")
            test_map[test_name]()
        else:
            self.get_logger().error(f"Unknown test: {test_name}")
            self.get_logger().info("Available tests: forward, rotation, square")


def main(args=None):
    """Main function"""
    rclpy.init(args=args)
    
    try:
        # Create test suite
        test_suite = MovementTestSuite()
        
        # Wait for publishers to be ready
        time.sleep(1.0)
        
        # Check for command line arguments
        if len(sys.argv) > 1:
            test_name = sys.argv[1].lower()
            test_suite.run_single_test(test_name)
        else:
            # Run complete test suite
            test_suite.run_complete_test_suite()
        
        # Keep node alive briefly
        time.sleep(1.0)
        
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
    except Exception as e:
        print(f"Test suite failed: {e}")
    finally:
        # Cleanup
        if 'test_suite' in locals():
            test_suite.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
