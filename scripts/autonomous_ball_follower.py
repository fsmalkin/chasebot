#!/usr/bin/env python

import rospy
import numpy as np
from geometry_msgs.msg import Twist, Vector3
from simple_follower.msg import position as PositionMsg

class AutonomousBallFollower:
    def __init__(self):
        rospy.init_node('autonomous_ball_follower', anonymous=True)
        
        # Get parameters
        self.max_speed = rospy.get_param('~maxSpeed', 0.2)
        self.target_distance = rospy.get_param('~targetDist', 0.5)
        
        # PID parameters for [angular, linear] control
        PID_param = rospy.get_param('~PID_controller', {'P': [1.0, 1.0], 'I': [0.0, 0.0], 'D': [0.1, 0.1]})
        
        # Initialize PID controller
        self.PID_controller = SimplePID([0, self.target_distance], PID_param['P'], PID_param['I'], PID_param['D'])
        
        # Publishers and subscribers
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=3)
        self.position_sub = rospy.Subscriber('/object_tracker/current_position', PositionMsg, self.position_callback)
        
        rospy.loginfo('Autonomous Ball Follower initialized')
        rospy.loginfo('Max speed: {:.2f}, Target distance: {:.2f}'.format(self.max_speed, self.target_distance))
        rospy.loginfo('PID parameters - P:{}, I:{}, D:{}'.format(PID_param['P'], PID_param['I'], PID_param['D']))
        
        # Safety timer - stop if no position updates for 2 seconds
        self.last_position_time = rospy.Time.now()
        self.safety_timer = rospy.Timer(rospy.Duration(0.5), self.safety_check)
    
    def position_callback(self, position):
        """Process position updates and generate movement commands"""
        self.last_position_time = rospy.Time.now()
        
        angle_x = position.angleX  # Horizontal angle in degrees
        distance = position.distance  # Distance in meters
        
        rospy.loginfo('Ball position - Angle: {:.2f}deg, Distance: {:.2f}m'.format(angle_x, distance))
        
        # Update PID controller
        try:
            [uncliped_ang_speed, uncliped_lin_speed] = self.PID_controller.update([angle_x, distance])
            
            # Clip speeds to maximum
            angular_speed = np.clip(-uncliped_ang_speed, -self.max_speed, self.max_speed)
            linear_speed = np.clip(-uncliped_lin_speed, -self.max_speed, self.max_speed)
            
            # Create and publish movement command
            cmd_vel = Twist()
            cmd_vel.linear = Vector3(linear_speed, 0, 0)
            cmd_vel.angular = Vector3(0, 0, angular_speed)
            
            self.cmd_vel_pub.publish(cmd_vel)
            
            rospy.loginfo('Movement command - Linear: {:.3f}, Angular: {:.3f}'.format(linear_speed, angular_speed))
            
        except Exception as e:
            rospy.logerr('Error in PID controller: {}'.format(e))
            self.stop_robot()
    
    def safety_check(self, event):
        """Stop robot if no position updates received recently"""
        time_since_last_position = rospy.Time.now() - self.last_position_time
        if time_since_last_position.to_sec() > 2.0:
            self.stop_robot()
            rospy.logwarn('No position updates for {:.1f}s - stopping robot'.format(time_since_last_position.to_sec()))
    
    def stop_robot(self):
        """Send stop command to robot"""
        cmd_vel = Twist()
        cmd_vel.linear = Vector3(0, 0, 0)
        cmd_vel.angular = Vector3(0, 0, 0)
        self.cmd_vel_pub.publish(cmd_vel)

class SimplePID:
    """Simple discrete PID controller"""
    def __init__(self, target, P, I, D):
        self.Kp = np.array(P)
        self.Ki = np.array(I) 
        self.Kd = np.array(D)
        self.setPoint = np.array(target)
        
        self.last_error = 0
        self.integrator = 0
        self.timeOfLastCall = None
        
        rospy.loginfo('PID initialized with P:{}, I:{}, D:{}'.format(P, I, D))
    
    def update(self, current_value):
        """Update PID controller and return control signal"""
        current_value = np.array(current_value)
        
        if self.timeOfLastCall is None:
            # First call - no delta time yet
            self.timeOfLastCall = rospy.Time.now()
            return np.zeros(np.size(current_value))
        
        error = self.setPoint - current_value
        P = error
        
        current_time = rospy.Time.now()
        delta_t = (current_time - self.timeOfLastCall).to_sec()
        
        if delta_t <= 0:
            # Avoid division by zero
            return np.zeros(np.size(current_value))
        
        # Integral term
        self.integrator = self.integrator + (error * delta_t)
        I = self.integrator
        
        # Derivative term
        D = (error - self.last_error) / delta_t
        
        self.last_error = error
        self.timeOfLastCall = current_time
        
        # Return control signal
        return self.Kp * P + self.Ki * I + self.Kd * D

if __name__ == '__main__':
    try:
        follower = AutonomousBallFollower()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo('Autonomous Ball Follower stopped')
