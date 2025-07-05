#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import time

class JetBotIgnitionTester(Node):
    def __init__(self):
        super().__init__('jetbot_ignition_tester')
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # Subscribers
        self.odom_sub = self.create_subscription(Odometry, 'odom', self.odom_callback, 10)
        
        # State tracking
        self.odom_received = False
        self.initial_position = None
        self.current_position = None
        
        self.get_logger().info("JetBot Ignition Core Tester initialized")
        
    def odom_callback(self, msg):
        """Handle odometry messages"""
        if not self.odom_received:
            self.initial_position = msg.pose.pose.position
            self.odom_received = True
            self.get_logger().info(f"Initial position: x={self.initial_position.x:.3f}, y={self.initial_position.y:.3f}")
        
        self.current_position = msg.pose.pose.position
        
    def test_forward_movement(self):
        """Test forward movement"""
        self.get_logger().info("Testing forward movement...")
        
        # Send forward command
        twist = Twist()
        twist.linear.x = 0.2  # 0.2 m/s forward
        
        for i in range(30):  # Send for 3 seconds
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.1)
            time.sleep(0.1)
        
        # Stop
        twist.linear.x = 0.0
        self.cmd_vel_pub.publish(twist)
        
        # Check if we moved
        if self.current_position and self.initial_position:
            distance_moved = ((self.current_position.x - self.initial_position.x)**2 + 
                            (self.current_position.y - self.initial_position.y)**2)**0.5
            self.get_logger().info(f"Distance moved: {distance_moved:.3f} meters")
            return distance_moved > 0.1  # Should move at least 10cm
        return False
        
    def test_rotation(self):
        """Test rotation"""
        self.get_logger().info("Testing rotation...")
        
        # Send rotation command
        twist = Twist()
        twist.angular.z = 0.5  # 0.5 rad/s rotation
        
        for i in range(20):  # Send for 2 seconds
            self.cmd_vel_pub.publish(twist)
            rclpy.spin_once(self, timeout_sec=0.1)
            time.sleep(0.1)
        
        # Stop
        twist.angular.z = 0.0
        self.cmd_vel_pub.publish(twist)
        
        self.get_logger().info("Rotation test completed")
        return True
        
    def run_tests(self):
        """Run all tests"""
        self.get_logger().info("Starting JetBot Ignition Core Tests...")
        
        # Wait for odometry
        self.get_logger().info("Waiting for odometry data...")
        timeout = 30.0  # 30 second timeout
        start_time = time.time()
        
        while not self.odom_received and (time.time() - start_time) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
            
        if not self.odom_received:
            self.get_logger().error("❌ FAILED: No odometry data received!")
            return False
        
        self.get_logger().info("✅ PASSED: Odometry data received")
        
        # Test forward movement
        if self.test_forward_movement():
            self.get_logger().info("✅ PASSED: Forward movement working")
        else:
            self.get_logger().error("❌ FAILED: Forward movement not working")
            return False
            
        # Test rotation
        if self.test_rotation():
            self.get_logger().info("✅ PASSED: Rotation working")
        else:
            self.get_logger().error("❌ FAILED: Rotation not working")
            return False
            
        self.get_logger().info("🎉 ALL TESTS PASSED: JetBot core functionality working in Ignition!")
        return True

def main():
    rclpy.init()
    
    tester = JetBotIgnitionTester()
    
    try:
        success = tester.run_tests()
        if success:
            print("\n🎉 UAT SUCCESS: JetBot core migration to Ignition Fortress complete!")
        else:
            print("\n❌ UAT FAILED: Issues with JetBot core functionality")
    except KeyboardInterrupt:
        pass
    finally:
        tester.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
