#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import time

def test_movement():
    """Quick test to verify JetBot movement with physics fixes"""
    rospy.init_node('simple_movement_test', anonymous=True)
    
    # Create publisher for movement commands
    cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
    
    # Wait for connections
    rospy.sleep(2)
    
    print("Testing JetBot Physics Fixes...")
    print("Sending forward movement command...")
    
    # Test forward movement
    twist = Twist()
    twist.linear.x = 0.2  # Move forward at 0.2 m/s
    twist.angular.z = 0.0
    
    # Send commands for 3 seconds
    for i in range(30):
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.linear.x = 0.0
    cmd_pub.publish(twist)
    
    print("Forward movement test complete!")
    
    # Test rotation
    print("Testing rotation...")
    twist.angular.z = 0.5  # Rotate at 0.5 rad/s
    
    # Send rotation commands for 2 seconds
    for i in range(20):
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.angular.z = 0.0
    cmd_pub.publish(twist)
    
    print("Rotation test complete!")
    print("Physics test finished - check Gazebo for robot movement")

if __name__ == '__main__':
    try:
        test_movement()
    except rospy.ROSInterruptException:
        print("Test interrupted")
    except Exception as e:
        print("Test failed: {}".format(e))
