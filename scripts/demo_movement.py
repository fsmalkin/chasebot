#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
import time

def demo_movement():
    """Demonstrate visible JetBot movement"""
    rospy.init_node('demo_movement', anonymous=True)
    
    # Create publisher for movement commands
    cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
    
    # Wait for connections
    rospy.sleep(2)
    
    print("Starting movement demonstration...")
    
    # Create movement command
    twist = Twist()
    
    # Move forward at higher speed for longer duration
    print("Moving forward at 0.5 m/s for 3 seconds...")
    twist.linear.x = 0.5
    twist.angular.z = 0.0
    
    for i in range(30):  # 3 seconds at 10Hz
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.linear.x = 0.0
    cmd_pub.publish(twist)
    rospy.sleep(1)
    
    # Rotate at higher speed
    print("Rotating at 1.0 rad/s for 3 seconds...")
    twist.linear.x = 0.0
    twist.angular.z = 1.0
    
    for i in range(30):  # 3 seconds at 10Hz
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.angular.z = 0.0
    cmd_pub.publish(twist)
    rospy.sleep(1)
    
    # Circle movement
    print("Moving in a circle for 5 seconds...")
    twist.linear.x = 0.3
    twist.angular.z = 0.5
    
    for i in range(50):  # 5 seconds at 10Hz
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.linear.x = 0.0
    twist.angular.z = 0.0
    cmd_pub.publish(twist)
    
    print("Movement demonstration complete!")

if __name__ == '__main__':
    try:
        demo_movement()
    except rospy.ROSInterruptException:
        print("Demo interrupted")
    except Exception as e:
        print("Demo failed with error: {}".format(e))
