#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math

class SimpleBallApproach:
    def __init__(self):
        rospy.init_node('simple_ball_approach', anonymous=True)
        
        # Publisher for robot movement
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # Subscriber for robot position
        self.odom_sub = rospy.Subscriber('/odom', Odometry, self.odom_callback)
        
        # Movement parameters
        self.linear_speed = 0.2  # m/s forward speed
        self.target_distance = 0.8  # Stop when 0.8m traveled (ball is at 1.0m, robot radius ~0.2m)
        
        # Robot state
        self.start_position = None
        self.current_position = None
        self.distance_traveled = 0.0
        
        # Create movement command
        self.move_cmd = Twist()
        self.move_cmd.linear.x = self.linear_speed
        self.move_cmd.angular.z = 0.0
        
        # Stop command
        self.stop_cmd = Twist()
        self.stop_cmd.linear.x = 0.0
        self.stop_cmd.angular.z = 0.0
        
        rospy.loginfo("Simple Ball Approach initialized. Moving toward golf ball...")
        
    def odom_callback(self, data):
        """Callback for odometry data"""
        self.current_position = data.pose.pose.position
        
        # Set start position on first callback
        if self.start_position is None:
            self.start_position = self.current_position
            rospy.loginfo("Start position set: x={:.3f}, y={:.3f}".format(
                self.start_position.x, self.start_position.y))
        
        # Calculate distance traveled
        if self.start_position is not None:
            dx = self.current_position.x - self.start_position.x
            dy = self.current_position.y - self.start_position.y
            self.distance_traveled = math.sqrt(dx*dx + dy*dy)
            
    def navigate(self):
        """Main navigation loop"""
        rate = rospy.Rate(10)  # 10 Hz
        start_time = rospy.Time.now()
        timeout = 20.0  # 20 second timeout
        
        # Wait for first odometry reading
        while self.start_position is None and not rospy.is_shutdown():
            rospy.loginfo("Waiting for odometry data...")
            rate.sleep()
        
        rospy.loginfo("Starting navigation. Target distance: {:.1f}m".format(self.target_distance))
        
        while not rospy.is_shutdown():
            # Check for timeout
            if (rospy.Time.now() - start_time).to_sec() > timeout:
                rospy.logwarn("Navigation timeout reached. Stopping.")
                break
                
            # Check if we've reached the target distance
            if self.distance_traveled >= self.target_distance:
                rospy.loginfo("SUCCESS: Reached target distance {:.3f}m. Golf ball should be contacted!".format(
                    self.distance_traveled))
                break
                
            # Move forward
            self.cmd_vel_pub.publish(self.move_cmd)
            
            # Log progress every 2 seconds
            if int((rospy.Time.now() - start_time).to_sec()) % 2 == 0:
                rospy.loginfo("Distance traveled: {:.3f}m / {:.1f}m target".format(
                    self.distance_traveled, self.target_distance))
            
            rate.sleep()
            
        # Stop the robot
        self.cmd_vel_pub.publish(self.stop_cmd)
        rospy.loginfo("Robot stopped. Final distance: {:.3f}m".format(self.distance_traveled))

if __name__ == '__main__':
    try:
        navigator = SimpleBallApproach()
        navigator.navigate()
    except rospy.ROSInterruptException:
        rospy.loginfo("Navigation interrupted")
        pass
