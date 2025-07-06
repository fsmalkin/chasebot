#!/usr/bin/env python3
"""
Minimal test for gz_ros2_control movement validation
Tests if the diff_drive_controller can be loaded and commanded
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from controller_manager_msgs.srv import ListControllers
import time

class MinimalControlTest(Node):
    def __init__(self):
        super().__init__('minimal_control_test')
        
        # Create publisher for velocity commands
        self.cmd_vel_pub = self.create_publisher(
            Twist, 
            '/jetbot_base_controller/cmd_vel', 
            10
        )
        
        # Create service client to check controller status
        self.list_controllers_client = self.create_client(
            ListControllers,
            '/controller_manager/list_controllers'
        )
        
        self.get_logger().info("Waiting for controller_manager service...")
        if not self.list_controllers_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error("Controller manager service not available!")
            return
            
        self.timer = self.create_timer(2.0, self.test_sequence)
        self.test_step = 0
        
    def test_sequence(self):
        if self.test_step == 0:
            self.get_logger().info("Step 1: Checking available controllers...")
            self.check_controllers()
            
        elif self.test_step == 1:
            self.get_logger().info("Step 2: Sending forward command...")
            self.send_velocity(0.1, 0.0)
            
        elif self.test_step == 2:
            self.get_logger().info("Step 3: Stopping...")
            self.send_velocity(0.0, 0.0)
            
        elif self.test_step == 3:
            self.get_logger().info("Step 4: Rotating...")
            self.send_velocity(0.0, 0.5)
            
        elif self.test_step == 4:
            self.get_logger().info("Step 5: Final stop...")
            self.send_velocity(0.0, 0.0)
            self.get_logger().info("Test complete!")
            self.timer.cancel()
            
        self.test_step += 1
        
    def check_controllers(self):
        req = ListControllers.Request()
        future = self.list_controllers_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        
        if future.result() is not None:
            self.get_logger().info("Available controllers:")
            for controller in future.result().controller:
                self.get_logger().info(f"  - {controller.name} [{controller.state}]")
        else:
            self.get_logger().error("Failed to get controller list")
            
    def send_velocity(self, linear, angular):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.cmd_vel_pub.publish(msg)
        self.get_logger().info(f"Sent velocity: linear={linear}, angular={angular}")

def main(args=None):
    rclpy.init(args=args)
    node = MinimalControlTest()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
