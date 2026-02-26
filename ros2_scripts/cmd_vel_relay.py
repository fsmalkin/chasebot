#!/usr/bin/env python3
"""Bridge Nav2 cmd_vel outputs to robot controller cmd_vel input."""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
class CmdVelRelay(Node):
    def __init__(self):
        super().__init__('cmd_vel_relay')

        self.declare_parameter('input_topic_primary', '/cmd_vel_nav')
        self.declare_parameter('input_topic_secondary', '/cmd_vel')

        input_topic_primary = str(self.get_parameter('input_topic_primary').value)
        input_topic_secondary = str(self.get_parameter('input_topic_secondary').value)
        
        # Subscribe to both Twist and TwistStamped variants because Nav2 stacks
        # can publish either type on these topics.
        self.cmd_vel_primary_twist_sub = self.create_subscription(
            Twist,
            input_topic_primary,
            self.cmd_vel_twist_callback,
            10
        )
        self.cmd_vel_secondary_twist_sub = self.create_subscription(
            Twist,
            input_topic_secondary,
            self.cmd_vel_twist_callback,
            10
        )
        self.cmd_vel_primary_stamped_sub = self.create_subscription(
            TwistStamped,
            input_topic_primary,
            self.cmd_vel_stamped_callback,
            10
        )
        self.cmd_vel_secondary_stamped_sub = self.create_subscription(
            TwistStamped,
            input_topic_secondary,
            self.cmd_vel_stamped_callback,
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
            '-> /jetbot_base_controller/cmd_vel (TwistStamped, supports Twist/TwistStamped input)'
        )
        
        # Message counter for debugging
        self.msg_count = 0
    
    def cmd_vel_twist_callback(self, msg: Twist):
        """Convert Twist to TwistStamped and relay to the robot topic."""
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

    def cmd_vel_stamped_callback(self, msg: TwistStamped):
        """Relay TwistStamped directly while refreshing timestamp."""
        twist_stamped = TwistStamped()
        twist_stamped.header.stamp = self.get_clock().now().to_msg()
        twist_stamped.header.frame_id = msg.header.frame_id or ''
        twist_stamped.twist = msg.twist

        self.robot_cmd_vel_pub.publish(twist_stamped)
        self.msg_count += 1

        if self.msg_count % 10 == 0:
            self.get_logger().info(
                f'Relayed {self.msg_count} messages. Latest: '
                f'linear.x={msg.twist.linear.x:.3f}, angular.z={msg.twist.angular.z:.3f}'
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
