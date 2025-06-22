#!/usr/bin/env python
"""
ChaseBot Vision-Based Ball Approach Node
Subscribes to ball detections and controls robot movement
Includes stubbed multimodal LLM integration for object classification
"""

import rospy
import time
from geometry_msgs.msg import Twist, Point
from std_msgs.msg import String

class VisionBallApproach:
    def __init__(self):
        rospy.init_node('vision_ball_approach', anonymous=True)
        
        # Control parameters
        self.image_width = 224  # From URDF camera config
        self.image_height = 224
        self.image_center_x = self.image_width // 2
        
        # Movement parameters
        self.forward_speed = 0.15        # Base forward speed (m/s)
        self.turn_gain = 0.8             # Proportional control gain for turning
        self.search_turn_speed = 0.3     # Turn speed when searching (rad/s)
        self.approach_area_threshold = 1500  # Ball area when close enough to stop
        self.detection_timeout = 2.0     # Seconds without detection before searching
        
        # State tracking
        self.last_detection_time = None
        self.current_ball = None
        self.object_classification = "unknown"  # Stubbed LLM classification
        
        # Publishers
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.status_pub = rospy.Publisher('/chasebot/status', String, queue_size=1)
        
        # Subscribers
        self.ball_sub = rospy.Subscriber('/ball_detection', Point, self.ball_callback)
        
        rospy.loginfo("Vision Ball Approach Node initialized")
        rospy.loginfo("Image size: {}x{}, center: {}".format(
            self.image_width, self.image_height, self.image_center_x))
        rospy.loginfo("Forward speed: {:.2f} m/s, Turn gain: {:.2f}".format(
            self.forward_speed, self.turn_gain))
        rospy.loginfo("Approach threshold: {} pixels, Detection timeout: {:.1f}s".format(
            self.approach_area_threshold, self.detection_timeout))
    
    def ball_callback(self, msg):
        """Handle incoming ball detection"""
        self.last_detection_time = rospy.Time.now()
        self.current_ball = {
            'center_x': int(msg.x),
            'center_y': int(msg.y), 
            'area': msg.z
        }
        
        # Stub multimodal LLM classification
        self.object_classification = self.classify_object_stub(msg)
        
        rospy.loginfo("Ball detected: center=({}, {}), area={:.0f}, class={}".format(
            self.current_ball['center_x'], self.current_ball['center_y'], 
            self.current_ball['area'], self.object_classification))
    
    def classify_object_stub(self, detection):
        """
        Stubbed multimodal LLM object classification
        In production, this would send camera image + detection to vision LLM
        For now, we assume it's a golf ball since that's what we're targeting
        """
        # Stub classification logic based on detection properties
        area = detection.z
        
        if area > 100 and area < 5000:
            # Size range consistent with golf ball at various distances
            confidence = min(0.95, area / 2000.0)  # Higher confidence for larger (closer) balls
            return "golf_ball (confidence: {:.2f})".format(confidence)
        elif area >= 5000:
            return "large_white_object (possibly golf ball very close)"
        else:
            return "small_white_object (possibly golf ball far away)"
    
    def calculate_movement_command(self):
        """Calculate movement command based on current state"""
        cmd = Twist()
        status = ""
        
        # Check if we have recent detection
        if (self.last_detection_time is None or 
            (rospy.Time.now() - self.last_detection_time).to_sec() > self.detection_timeout):
            # No recent detections - search behavior
            cmd.angular.z = self.search_turn_speed
            cmd.linear.x = 0.0
            status = "SEARCHING - No ball detected"
            rospy.loginfo_throttle(1.0, "Searching for ball (no recent detections)")
            
        elif self.current_ball is None:
            # Safety check
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            status = "STOPPED - No ball data"
            
        else:
            # We have a ball detection - approach behavior
            center_x = self.current_ball['center_x']
            area = self.current_ball['area']
            
            # Check if ball is close enough
            if area >= self.approach_area_threshold:
                # Ball is close - stop
                cmd.linear.x = 0.0
                cmd.angular.z = 0.0
                status = "REACHED - Ball is close (area: {:.0f})".format(area)
                rospy.loginfo("Ball reached! Area: {:.0f} >= {:.0f}".format(
                    area, self.approach_area_threshold))
                
            else:
                # Calculate steering based on ball position
                position_error = center_x - self.image_center_x
                normalized_error = position_error / float(self.image_center_x)
                
                # Proportional control
                turn_command = -normalized_error * self.turn_gain  # Negative for correct direction
                
                # Set movement commands
                cmd.linear.x = self.forward_speed
                cmd.angular.z = turn_command
                
                status = "APPROACHING - Ball at ({}, area: {:.0f}), turn: {:.2f}".format(
                    center_x, area, turn_command)
                
                rospy.loginfo_throttle(0.5, 
                    "Approaching ball: pos_error={:.0f}, normalized={:.2f}, turn={:.2f}".format(
                        position_error, normalized_error, turn_command))
        
        return cmd, status
    
    def publish_status(self, status_msg):
        """Publish status message"""
        status = String()
        status.data = status_msg
        self.status_pub.publish(status)
    
    def run(self):
        """Main control loop"""
        rospy.loginfo("Vision Ball Approach running...")
        
        rate = rospy.Rate(10)  # 10 Hz control loop
        
        while not rospy.is_shutdown():
            # Calculate movement command
            cmd_vel, status = self.calculate_movement_command()
            
            # Publish commands
            self.cmd_vel_pub.publish(cmd_vel)
            self.publish_status(status)
            
            # Sleep to maintain loop rate
            rate.sleep()

if __name__ == '__main__':
    try:
        navigator = VisionBallApproach()
        navigator.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("Vision Ball Approach node terminated")
