#!/usr/bin/env python3
"""
CMD_VEL Relay Node - Version 2.0.0
Subscribes to /cmd_vel_nav (from Nav2) and publishes to /jetbot_base_controller/cmd_vel
Major changes:
- v2.0.0: Subscribe to /cmd_vel_nav instead of /cmd_vel for proper Nav2 remapping
- Added better logging and status reporting
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from std_msgs.msg import Header


class CmdVelRelay(Node):
    def __init__(self):
        super().__init__('cmd_vel_relay_v2')
        
        # Create subscriber to Nav2's remapped cmd_vel
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            '/cmd_vel_nav',  # Nav2 publishes here with remapping
            self.cmd_vel_callback,
            10
        )
        
        # Create publisher to robot's cmd_vel (as TwistStamped)
        self.robot_cmd_vel_pub = self.create_publisher(
            TwistStamped,
            '/jetbot_base_controller/cmd_vel',
            10
        )
        
        self.get_logger().info('CMD_VEL Relay v2.0.0 started')
        self.get_logger().info('Relaying /cmd_vel_nav (Twist) -> /jetbot_base_controller/cmd_vel (TwistStamped)')
        
        # Message counter for debugging
        self.msg_count = 0
        
        # Timer for status reporting
        self.status_timer = self.create_timer(5.0, self.status_callback)
    
    def cmd_vel_callback(self, msg):
        """Convert Twist to TwistStamped and relay to the robot's topic"""
        # Create TwistStamped message
        twist_stamped = TwistStamped()
        twist_stamped.header.stamp = self.get_clock().now().to_msg()
        twist_stamped.header.frame_id = ''  # Empty frame_id as in the working example
        twist_stamped.twist = msg  # Copy the twist data
        
        # Publish the stamped message
        self.robot_cmd_vel_pub.publish(twist_stamped)
        self.msg_count += 1
        
        # Log significant commands (non-zero)
        if abs(msg.linear.x) > 0.01 or abs(msg.angular.z) > 0.01:
            self.get_logger().info(
                f'Relaying command: linear.x={msg.linear.x:.3f}, angular.z={msg.angular.z:.3f}'
            )
    
    def status_callback(self):
        """Report relay status periodically"""
        self.get_logger().info(f'Relay status: {self.msg_count} messages relayed')
        if self.msg_count == 0:
            self.get_logger().warn('No messages received yet on /cmd_vel_nav - check Nav2 remapping')


def main(args=None):
    rclpy.init(args=args)
    
    relay = CmdVelRelay()
    
    try:
        rclpy.spin(relay)
    except KeyboardInterrupt:
        relay.get_logger().info('Shutting down CMD_VEL relay v2.0.0...')
    finally:
        relay.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
