#!/usr/bin/env python3
"""
ROS 2 Forward Movement Test
Simple programmatic movement control for ChaseBot UAT validation
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import time


class ForwardMovementTest(Node):
    """Simple forward movement test for ROS 2 ChaseBot"""
    
    def __init__(self):
        super().__init__('forward_movement_test')
        
        # Create publisher for cmd_vel
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Movement parameters
        self.linear_speed = 0.2  # m/s
        self.movement_duration = 3.0  # seconds
        
        self.get_logger().info("Forward Movement Test initialized")
        self.get_logger().info(f"Will move forward at {self.linear_speed} m/s for {self.movement_duration} seconds")
        
    def execute_forward_movement(self):
        """Execute forward movement test"""
        try:
            # Create Twist message for forward movement
            move_cmd = Twist()
            move_cmd.linear.x = self.linear_speed
            move_cmd.angular.z = 0.0
            
            # Create stop command
            stop_cmd = Twist()
            stop_cmd.linear.x = 0.0
            stop_cmd.angular.z = 0.0
            
            self.get_logger().info("Starting forward movement...")
            
            # Record start time
            start_time = time.time()
            
            # Movement loop with safety timeout
            while time.time() - start_time < self.movement_duration:
                self.cmd_vel_pub.publish(move_cmd)
                time.sleep(0.1)  # 10Hz publishing rate
                
            # Stop the robot
            self.get_logger().info("Movement complete - stopping robot")
            for _ in range(10):  # Send stop commands for 1 second
                self.cmd_vel_pub.publish(stop_cmd)
                time.sleep(0.1)
                
            self.get_logger().info("Forward movement test completed successfully")
            
        except Exception as e:
            self.get_logger().error(f"Error during movement: {str(e)}")
            # Emergency stop
            stop_cmd = Twist()
            for _ in range(10):
                self.cmd_vel_pub.publish(stop_cmd)
                time.sleep(0.1)


def main(args=None):
    """Main function"""
    rclpy.init(args=args)
    
    try:
        # Create and run the test
        movement_test = ForwardMovementTest()
        
        # Wait for publishers to be ready
        time.sleep(1.0)
        
        # Execute the movement test
        movement_test.execute_forward_movement()
        
        # Keep node alive for a moment to ensure all messages are sent
        time.sleep(1.0)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Cleanup
        if 'movement_test' in locals():
            movement_test.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
