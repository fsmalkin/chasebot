#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from gazebo_msgs.msg import ModelStates
import time
import math

class JetBotPhysicsDiagnostic:
    def __init__(self):
        rospy.init_node('jetbot_physics_diagnostic', anonymous=True)
        
        # Publishers and subscribers
        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # Diagnostic data storage
        self.odom_data = None
        self.joint_data = None
        self.model_data = None
        
        # Subscribe to diagnostic topics
        rospy.Subscriber('/odom', Odometry, self.odom_callback)
        rospy.Subscriber('/joint_states', JointState, self.joint_callback)
        rospy.Subscriber('/gazebo/model_states', ModelStates, self.model_callback)
        
        # Wait for connections
        rospy.sleep(2)
        print("JetBot Physics Diagnostic Started")
        print("=" * 50)
    
    def odom_callback(self, msg):
        self.odom_data = msg
    
    def joint_callback(self, msg):
        self.joint_data = msg
    
    def model_callback(self, msg):
        self.model_data = msg
    
    def print_current_state(self, test_name=""):
        print(f"\n--- {test_name} ---")
        
        # Odometry data
        if self.odom_data:
            pos = self.odom_data.pose.pose.position
            vel = self.odom_data.twist.twist
            print(f"Odom Position: x={pos.x:.4f}, y={pos.y:.4f}, z={pos.z:.4f}")
            print(f"Odom Velocity: linear={vel.linear.x:.4f}, angular={vel.angular.z:.4f}")
        else:
            print("Odom: No data received")
        
        # Model states (Gazebo)
        if self.model_data and 'jetbot' in self.model_data.name:
            idx = self.model_data.name.index('jetbot')
            pos = self.model_data.pose[idx].position
            vel = self.model_data.twist[idx]
            print(f"Gazebo Position: x={pos.x:.4f}, y={pos.y:.4f}, z={pos.z:.4f}")
            print(f"Gazebo Velocity: linear={vel.linear.x:.4f}, angular={vel.angular.z:.4f}")
        else:
            print("Gazebo: No jetbot model data")
        
        # Joint states
        if self.joint_data:
            for i, name in enumerate(self.joint_data.name):
                if 'wheel' in name:
                    pos = self.joint_data.position[i] if i < len(self.joint_data.position) else 0
                    vel = self.joint_data.velocity[i] if i < len(self.joint_data.velocity) else 0
                    print(f"Joint {name}: pos={pos:.4f}, vel={vel:.4f}")
        else:
            print("Joints: No data received")
        
        print("-" * 30)
    
    def send_command(self, linear=0.0, angular=0.0, duration=2.0):
        """Send movement command for specified duration"""
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        
        print(f"Sending command: linear={linear}, angular={angular} for {duration}s")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            self.cmd_pub.publish(twist)
            rospy.sleep(0.1)
        
        # Stop
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        self.cmd_pub.publish(twist)
        rospy.sleep(0.5)
    
    def run_diagnostic(self):
        """Run comprehensive physics diagnostic"""
        
        print("Starting JetBot Physics Diagnostic...")
        
        # Initial state
        rospy.sleep(1.0)  # Let data settle
        self.print_current_state("Initial State")
        
        # Test 1: Forward movement
        print("\n" + "="*50)
        print("TEST 1: Forward Movement (0.2 m/s)")
        print("="*50)
        self.send_command(linear=0.2, angular=0.0, duration=3.0)
        self.print_current_state("After Forward Movement")
        
        # Test 2: Backward movement
        print("\n" + "="*50)
        print("TEST 2: Backward Movement (-0.2 m/s)")
        print("="*50)
        self.send_command(linear=-0.2, angular=0.0, duration=3.0)
        self.print_current_state("After Backward Movement")
        
        # Test 3: Rotation
        print("\n" + "="*50)
        print("TEST 3: Rotation (0.5 rad/s)")
        print("="*50)
        self.send_command(linear=0.0, angular=0.5, duration=3.0)
        self.print_current_state("After Rotation")
        
        # Test 4: Combined movement
        print("\n" + "="*50)
        print("TEST 4: Combined Movement (forward + rotation)")
        print("="*50)
        self.send_command(linear=0.1, angular=0.3, duration=3.0)
        self.print_current_state("After Combined Movement")
        
        # Final state
        rospy.sleep(2.0)
        self.print_current_state("Final State")
        
        print("\n" + "="*50)
        print("DIAGNOSTIC COMPLETE")
        print("="*50)
        
        # Analysis
        print("\nANALYSIS:")
        print("- Check if position values change during movement")
        print("- Verify velocity values are not 'nan' or zero during commands")
        print("- Confirm joint velocities show wheel rotation")
        print("- Look for consistent odom vs gazebo position data")
        
        if self.odom_data and self.model_data:
            print(f"\nFinal position moved from origin: {abs(self.odom_data.pose.pose.position.x) > 0.01 or abs(self.odom_data.pose.pose.position.y) > 0.01}")

if __name__ == '__main__':
    try:
        diagnostic = JetBotPhysicsDiagnostic()
        diagnostic.run_diagnostic()
    except rospy.ROSInterruptException:
        print("Diagnostic interrupted")
    except Exception as e:
        print(f"Diagnostic failed: {e}")
