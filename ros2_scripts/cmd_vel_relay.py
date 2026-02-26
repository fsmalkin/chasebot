#!/usr/bin/env python3
"""
CMD_VEL Relay Node
Subscribes to /cmd_vel and publishes to /jetbot_base_controller/cmd_vel
This bridges Nav2's output to the robot's expected input topic
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from std_msgs.msg import Header


class CmdVelRelay(Node):
    def __init__(self):
        super().__init__('cmd_vel_relay')

        self.declare_parameter('input_topic_primary', '/cmd_vel_nav')
        self.declare_parameter('input_topic_secondary', '/cmd_vel')

        input_topic_primary = str(self.get_parameter('input_topic_primary').value)
        input_topic_secondary = str(self.get_parameter('input_topic_secondary').value)
        
        # Create subscriber(s) to Nav2 cmd_vel topics.
        self.cmd_vel_primary_sub = self.create_subscription(
            Twist,
            input_topic_primary,
            self.cmd_vel_callback,
            10
        )
        self.cmd_vel_secondary_sub = self.create_subscription(
            Twist,
            input_topic_secondary,
            self.cmd_vel_callback,
            10
        )
        
        # Create publisher to robot's cmd_vel (as TwistStamped)
        self.robot_cmd_vel_pub = self.create_publisher(
            TwistStamped,
            '/jetbot_base_controller/cmd_vel',
            10
        )
        
        self.get_logger().info('CMD_VEL Relay started')
        self.get_logger().info(
            f'Relaying {input_topic_primary} and {input_topic_secondary} '
            '-> /jetbot_base_controller/cmd_vel (TwistStamped)'
        )
        
        # Message counter for debugging
        self.msg_count = 0
    
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
        
        # Log every 10th message to avoid flooding
        if self.msg_count % 10 == 0:
            self.get_logger().info(
                f'Relayed {self.msg_count} messages. Latest: '
                f'linear.x={msg.linear.x:.3f}, angular.z={msg.angular.z:.3f}'
            )


def main(args=None):
    rclpy.init(args=args)
    
    relay = CmdVelRelay()
    
    try:
        rclpy.spin(relay)
    except KeyboardInterrupt:
        relay.get_logger().info('Shutting down CMD_VEL relay...')
    finally:
        relay.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
