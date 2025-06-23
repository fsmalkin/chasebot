#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Twist
from simple_follower.msg import position as PositionMsg
from nav_msgs.msg import Odometry
import threading
import time

class RobotMovementDiagnostic:
    def __init__(self):
        rospy.init_node('robot_movement_diagnostic', anonymous=True)
        
        # Data storage
        self.position_msgs_received = 0
        self.cmd_vel_msgs_sent = 0
        self.last_position_msg = None
        self.last_cmd_vel_msg = None
        self.last_odom_msg = None
        
        # Subscribers
        self.position_sub = rospy.Subscriber('/object_tracker/current_position', PositionMsg, self.position_callback)
        self.cmd_vel_sub = rospy.Subscriber('/cmd_vel', Twist, self.cmd_vel_callback)
        self.odom_sub = rospy.Subscriber('/odom', Odometry, self.odom_callback)
        
        rospy.loginfo("Robot Movement Diagnostic started")
        rospy.loginfo("Monitoring topics for 30 seconds...")
        
        # Start diagnostic timer
        self.start_time = time.time()
        self.diagnostic_timer = threading.Timer(30.0, self.print_final_diagnosis)
        self.diagnostic_timer.start()
        
        # Print status every 5 seconds
        self.status_timer = rospy.Timer(rospy.Duration(5.0), self.print_status)
    
    def position_callback(self, msg):
        self.position_msgs_received += 1
        self.last_position_msg = msg
        rospy.loginfo("Position received: X={:.2f}deg, Y={:.2f}deg, Dist={:.2f}m (Total: {})".format(
            msg.angleX, msg.angleY, msg.distance, self.position_msgs_received))
    
    def cmd_vel_callback(self, msg):
        self.cmd_vel_msgs_sent += 1
        self.last_cmd_vel_msg = msg
        rospy.loginfo("CMD_VEL sent: Linear={:.3f}, Angular={:.3f} (Total: {})".format(
            msg.linear.x, msg.angular.z, self.cmd_vel_msgs_sent))
    
    def odom_callback(self, msg):
        self.last_odom_msg = msg
    
    def print_status(self, event):
        elapsed = time.time() - self.start_time
        rospy.loginfo("=== STATUS UPDATE ({}s elapsed) ===".format(int(elapsed)))
        rospy.loginfo("Position messages received: {}".format(self.position_msgs_received))
        rospy.loginfo("CMD_VEL messages sent: {}".format(self.cmd_vel_msgs_sent))
        
        if self.last_position_msg:
            rospy.loginfo("Latest position: X={:.2f}deg, Y={:.2f}deg".format(
                self.last_position_msg.angleX, self.last_position_msg.angleY))
        
        if self.last_cmd_vel_msg:
            rospy.loginfo("Latest cmd_vel: Linear={:.3f}, Angular={:.3f}".format(
                self.last_cmd_vel_msg.linear.x, self.last_cmd_vel_msg.angular.z))
        else:
            rospy.logwarn("NO cmd_vel messages received yet!")
            
        if self.last_odom_msg:
            pos = self.last_odom_msg.pose.pose.position
            rospy.loginfo("Robot position: X={:.3f}, Y={:.3f}".format(pos.x, pos.y))
        
        rospy.loginfo("===============================")
    
    def print_final_diagnosis(self):
        rospy.loginfo("=== FINAL DIAGNOSIS ===")
        rospy.loginfo("Total position messages: {}".format(self.position_msgs_received))
        rospy.loginfo("Total cmd_vel messages: {}".format(self.cmd_vel_msgs_sent))
        
        # Diagnosis logic
        if self.position_msgs_received == 0:
            rospy.logerr("PROBLEM: No position messages received!")
            rospy.logerr("Check if yolo_position_publisher is running and publishing to /object_tracker/current_position")
        elif self.cmd_vel_msgs_sent == 0:
            rospy.logerr("PROBLEM: Position messages received but NO cmd_vel messages sent!")
            rospy.logerr("The simple_follower node is not converting positions to movement commands")
            rospy.logerr("Check simple_follower configuration and topic subscriptions")
        elif self.cmd_vel_msgs_sent < self.position_msgs_received / 2:
            rospy.logwarn("WARNING: Few cmd_vel messages compared to position messages")
            rospy.logwarn("Follower may have restrictive conditions for movement")
        else:
            rospy.loginfo("SUCCESS: Both position and cmd_vel messages are flowing")
            rospy.loginfo("Robot should be moving - check Gazebo simulation")
        
        if self.last_position_msg and self.last_cmd_vel_msg:
            rospy.loginfo("Final position: X={:.2f}deg, Y={:.2f}deg".format(
                self.last_position_msg.angleX, self.last_position_msg.angleY))
            rospy.loginfo("Final cmd_vel: Linear={:.3f}, Angular={:.3f}".format(
                self.last_cmd_vel_msg.linear.x, self.last_cmd_vel_msg.angular.z))
        
        rospy.loginfo("=== DIAGNOSIS COMPLETE - SHUTTING DOWN ===")
        rospy.signal_shutdown("Diagnostic complete")

if __name__ == '__main__':
    try:
        diagnostic = RobotMovementDiagnostic()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo('Robot Movement Diagnostic stopped')
