#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
import time

def test_jetbot_movement():
    """Test JetBot movement and camera functionality"""
    rospy.init_node('test_jetbot_movement', anonymous=True)
    
    # Create publisher for movement commands
    cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
    
    # Wait for connections
    rospy.sleep(2)
    
    print("Testing JetBot movement...")
    
    # Test forward movement
    twist = Twist()
    twist.linear.x = 0.2  # Move forward at 0.2 m/s
    twist.angular.z = 0.0
    
    print("Moving forward...")
    for i in range(20):  # Send commands for 2 seconds
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.linear.x = 0.0
    cmd_pub.publish(twist)
    rospy.sleep(1)
    
    # Test rotation
    twist.linear.x = 0.0
    twist.angular.z = 0.5  # Rotate at 0.5 rad/s
    
    print("Rotating...")
    for i in range(20):  # Send commands for 2 seconds
        cmd_pub.publish(twist)
        rospy.sleep(0.1)
    
    # Stop
    twist.angular.z = 0.0
    cmd_pub.publish(twist)
    
    print("Movement test complete!")

def camera_callback(msg):
    """Callback to confirm camera data is being received"""
    print("Camera image received: {}x{} pixels, encoding: {}".format(
        msg.width, msg.height, msg.encoding))

def test_camera():
    """Test camera functionality"""
    rospy.init_node('test_jetbot_camera', anonymous=True)
    
    print("Testing camera feed...")
    
    # Subscribe to camera topic
    rospy.Subscriber('/camera/image_raw', Image, camera_callback)
    
    # Wait for a few seconds to receive messages
    rospy.sleep(5)
    
    print("Camera test complete!")

if __name__ == '__main__':
    try:
        # Test movement first
        test_jetbot_movement()
        
        # Test camera
        test_camera()
        
    except rospy.ROSInterruptException:
        print("Test interrupted")
    except Exception as e:
        print("Test failed with error: {}".format(e))
