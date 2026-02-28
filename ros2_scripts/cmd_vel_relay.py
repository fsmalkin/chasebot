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

        # Subscribe defensively: DDS disallows mixed message types on one topic.
        # Some stacks publish Twist, others TwistStamped.
        self._relay_subs = []
        self._relay_subs.append(
            self._try_create_subscription(
                Twist, input_topic_primary, self.cmd_vel_twist_callback, 'primary_twist'
            )
        )
        self._relay_subs.append(
            self._try_create_subscription(
                TwistStamped,
                input_topic_primary,
                self.cmd_vel_stamped_callback,
                'primary_stamped',
            )
        )
        self._relay_subs.append(
            self._try_create_subscription(
                Twist, input_topic_secondary, self.cmd_vel_twist_callback, 'secondary_twist'
            )
        )
        self._relay_subs.append(
            self._try_create_subscription(
                TwistStamped,
                input_topic_secondary,
                self.cmd_vel_stamped_callback,
                'secondary_stamped',
            )
        )
        self._relay_subs = [sub for sub in self._relay_subs if sub is not None]
        
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
        if not self._relay_subs:
            self.get_logger().error(
                'No compatible cmd_vel subscriptions were created. Check topic types.'
            )
        
        # Message counter for debugging
        self.msg_count = 0

    def _try_create_subscription(self, msg_type, topic, callback, label):
        try:
            return self.create_subscription(msg_type, topic, callback, 10)
        except Exception as exc:
            self.get_logger().warn(
                f'Skipping {label} subscription on {topic}: {exc}'
            )
            return None
    
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
