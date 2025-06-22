#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
from gazebo_msgs.msg import ContactsState
import sys

class BallNavigator:
    def __init__(self):
        rospy.init_node('ball_navigator', anonymous=True)
        
        # Publisher for robot movement
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # Subscriber for collision detection
        self.contact_sub = rospy.Subscriber('/bumper_states', ContactsState, self.contact_callback)
        
        # Movement parameters
        self.linear_speed = 0.2  # m/s forward speed
        self.contact_detected = False
        
        # Create movement command
        self.move_cmd = Twist()
        self.move_cmd.linear.x = self.linear_speed
        self.move_cmd.angular.z = 0.0
        
        # Stop command
        self.stop_cmd = Twist()
        self.stop_cmd.linear.x = 0.0
        self.stop_cmd.angular.z = 0.0
        
        rospy.loginfo("Ball Navigator initialized. Moving toward golf ball...")
        
    def contact_callback(self, data):
        """Callback for collision detection"""
        if len(data.states) > 0:
            self.contact_detected = True
            rospy.loginfo("Contact detected! Stopping robot.")
            
    def navigate(self):
        """Main navigation loop"""
        rate = rospy.Rate(10)  # 10 Hz
        start_time = rospy.Time.now()
        timeout = 30.0  # 30 second timeout
        
        while not rospy.is_shutdown() and not self.contact_detected:
            # Check for timeout
            if (rospy.Time.now() - start_time).to_sec() > timeout:
                rospy.logwarn("Navigation timeout reached. Stopping.")
                break
                
            # Move forward
            self.cmd_vel_pub.publish(self.move_cmd)
            rate.sleep()
            
        # Stop the robot
        self.cmd_vel_pub.publish(self.stop_cmd)
        
        if self.contact_detected:
            rospy.loginfo("SUCCESS: Robot reached the golf ball!")
        else:
            rospy.loginfo("Navigation completed (timeout or shutdown)")

if __name__ == '__main__':
    try:
        navigator = BallNavigator()
        navigator.navigate()
    except rospy.ROSInterruptException:
        rospy.loginfo("Navigation interrupted")
        pass
