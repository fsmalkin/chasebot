#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
import time

class TimedBallApproach:
    def __init__(self):
        rospy.init_node('timed_ball_approach', anonymous=True)
        
        # Publisher for robot movement
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # Movement parameters
        self.linear_speed = 0.2  # m/s forward speed
        self.movement_time = 5.0  # Move for 5 seconds (0.2 m/s * 5s = 1.0m)
        
        # Create movement command
        self.move_cmd = Twist()
        self.move_cmd.linear.x = self.linear_speed
        self.move_cmd.angular.z = 0.0
        
        # Stop command
        self.stop_cmd = Twist()
        self.stop_cmd.linear.x = 0.0
        self.stop_cmd.angular.z = 0.0
        
        rospy.loginfo("Timed Ball Approach initialized. Moving toward golf ball for {} seconds...".format(self.movement_time))
        
    def navigate(self):
        """Simple time-based navigation"""
        rate = rospy.Rate(10)  # 10 Hz
        
        # Wait a moment for system to be ready
        rospy.sleep(1.0)
        
        rospy.loginfo("Starting movement toward golf ball...")
        start_time = time.time()
        
        # Move forward for specified time
        while not rospy.is_shutdown():
            elapsed_time = time.time() - start_time
            
            if elapsed_time >= self.movement_time:
                rospy.loginfo("SUCCESS: Completed {:.1f}s movement. Should have reached golf ball!".format(elapsed_time))
                break
                
            # Move forward
            self.cmd_vel_pub.publish(self.move_cmd)
            
            # Log progress
            if int(elapsed_time) % 1 == 0 and elapsed_time > 0:
                rospy.loginfo("Moving... {:.1f}s / {:.1f}s".format(elapsed_time, self.movement_time))
            
            rate.sleep()
            
        # Stop the robot
        for _ in range(5):  # Send stop command multiple times to ensure it stops
            self.cmd_vel_pub.publish(self.stop_cmd)
            rate.sleep()
            
        rospy.loginfo("Robot stopped after {:.1f}s movement".format(elapsed_time))

if __name__ == '__main__':
    try:
        navigator = TimedBallApproach()
        navigator.navigate()
    except rospy.ROSInterruptException:
        rospy.loginfo("Navigation interrupted")
        pass
