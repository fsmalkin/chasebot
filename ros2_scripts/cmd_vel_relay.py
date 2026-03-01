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

        # Track one subscription per topic and adapt type if publishers indicate a mismatch.
        self._topic_map = {
            'primary': input_topic_primary,
            'secondary': input_topic_secondary,
        }
        self._relay_subs = {}
        self._relay_sub_types = {}
        
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
        self._refresh_subscriptions(force=True)
        self._refresh_timer = self.create_timer(1.0, self._refresh_subscriptions)
        
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

    def _detect_topic_kind(self, topic: str):
        topic_types = set()
        try:
            infos = self.get_publishers_info_by_topic(topic)
            for info in infos:
                if info.topic_type:
                    topic_types.add(info.topic_type)
        except Exception:
            pass
        if not topic_types:
            try:
                for known_topic, known_types in self.get_topic_names_and_types():
                    if known_topic == topic:
                        topic_types.update(known_types)
                        break
            except Exception:
                pass

        if 'geometry_msgs/msg/TwistStamped' in topic_types:
            return 'stamped'
        if 'geometry_msgs/msg/Twist' in topic_types:
            return 'twist'
        return None

    def _refresh_subscriptions(self, force: bool = False):
        for label, topic in self._topic_map.items():
            detected_kind = self._detect_topic_kind(topic)
            desired_kind = detected_kind if detected_kind in ('twist', 'stamped') else 'twist'
            current_kind = self._relay_sub_types.get(label)

            if (not force) and current_kind == desired_kind and label in self._relay_subs:
                continue

            current_sub = self._relay_subs.get(label)
            if current_sub is not None:
                try:
                    self.destroy_subscription(current_sub)
                except Exception:
                    pass
                self._relay_subs.pop(label, None)

            if desired_kind == 'stamped':
                sub = self._try_create_subscription(
                    TwistStamped,
                    topic,
                    self.cmd_vel_stamped_callback,
                    f'{label}_stamped',
                )
            else:
                sub = self._try_create_subscription(
                    Twist,
                    topic,
                    self.cmd_vel_twist_callback,
                    f'{label}_twist',
                )

            if sub is not None:
                self._relay_subs[label] = sub
                self._relay_sub_types[label] = desired_kind
                if force or current_kind != desired_kind:
                    self.get_logger().info(
                        f'Using {desired_kind} subscription for {label} topic {topic}'
                    )
    
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
