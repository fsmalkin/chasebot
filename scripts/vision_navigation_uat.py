#!/usr/bin/env python
"""
ChaseBot Vision Navigation UAT Test
Automated test for vision-based ball detection and navigation
"""

import rospy
import time
import subprocess
import signal
import sys
from geometry_msgs.msg import Point, Twist
from std_msgs.msg import String
from nav_msgs.msg import Odometry
import math

class VisionNavigationUAT:
    def __init__(self):
        rospy.init_node('vision_navigation_uat', anonymous=True)
        
        # Test parameters
        self.test_duration = 30.0  # Maximum test time (seconds)
        self.success_area_threshold = 1000  # Ball area indicating close proximity
        self.movement_threshold = 0.5  # Minimum distance moved to indicate navigation
        
        # State tracking
        self.test_start_time = None
        self.ball_detections = []
        self.robot_positions = []
        self.cmd_vel_commands = []
        self.status_messages = []
        
        # Subscribers for monitoring
        self.ball_sub = rospy.Subscriber('/ball_detection', Point, self.ball_callback)
        self.odom_sub = rospy.Subscriber('/odom', Odometry, self.odom_callback)
        self.cmd_vel_sub = rospy.Subscriber('/cmd_vel', Twist, self.cmd_vel_callback)
        self.status_sub = rospy.Subscriber('/chasebot/status', String, self.status_callback)
        
        rospy.loginfo("Vision Navigation UAT initialized")
        rospy.loginfo("Test duration: {:.1f}s, Success threshold: {} pixels".format(
            self.test_duration, self.success_area_threshold))
    
    def ball_callback(self, msg):
        """Track ball detections"""
        detection = {
            'time': rospy.Time.now(),
            'center_x': msg.x,
            'center_y': msg.y,
            'area': msg.z
        }
        self.ball_detections.append(detection)
        rospy.loginfo("UAT: Ball detected at ({:.0f}, {:.0f}), area: {:.0f}".format(
            msg.x, msg.y, msg.z))
    
    def odom_callback(self, msg):
        """Track robot position"""
        position = {
            'time': rospy.Time.now(),
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y,
            'z': msg.pose.pose.position.z
        }
        self.robot_positions.append(position)
    
    def cmd_vel_callback(self, msg):
        """Track movement commands"""
        command = {
            'time': rospy.Time.now(),
            'linear_x': msg.linear.x,
            'angular_z': msg.angular.z
        }
        self.cmd_vel_commands.append(command)
    
    def status_callback(self, msg):
        """Track status messages"""
        status = {
            'time': rospy.Time.now(),
            'message': msg.data
        }
        self.status_messages.append(status)
        rospy.loginfo("UAT Status: {}".format(msg.data))
    
    def calculate_distance_moved(self):
        """Calculate total distance robot has moved"""
        if len(self.robot_positions) < 2:
            return 0.0
        
        start_pos = self.robot_positions[0]
        end_pos = self.robot_positions[-1]
        
        dx = end_pos['x'] - start_pos['x']
        dy = end_pos['y'] - start_pos['y']
        distance = math.sqrt(dx*dx + dy*dy)
        
        return distance
    
    def analyze_ball_approach(self):
        """Analyze if robot successfully approached the ball"""
        if not self.ball_detections:
            return False, "No ball detections recorded"
        
        # Check if ball area increased over time (getting closer)
        first_detection = self.ball_detections[0]
        last_detection = self.ball_detections[-1]
        
        area_increase = last_detection['area'] - first_detection['area']
        max_area = max(d['area'] for d in self.ball_detections)
        
        rospy.loginfo("UAT Analysis: First area: {:.0f}, Last area: {:.0f}, Max area: {:.0f}".format(
            first_detection['area'], last_detection['area'], max_area))
        
        # Success criteria
        if max_area >= self.success_area_threshold:
            return True, "Ball reached (max area: {:.0f} >= {:.0f})".format(
                max_area, self.success_area_threshold)
        elif area_increase > 200:
            return True, "Clear approach progress (area increased by {:.0f})".format(area_increase)
        else:
            return False, "Insufficient approach progress (max area: {:.0f}, increase: {:.0f})".format(
                max_area, area_increase)
    
    def analyze_navigation_behavior(self):
        """Analyze navigation behavior"""
        results = []
        
        # Check if robot moved significantly
        distance_moved = self.calculate_distance_moved()
        if distance_moved >= self.movement_threshold:
            results.append("✅ Robot moved {:.2f}m (>= {:.2f}m threshold)".format(
                distance_moved, self.movement_threshold))
        else:
            results.append("❌ Robot only moved {:.2f}m (< {:.2f}m threshold)".format(
                distance_moved, self.movement_threshold))
        
        # Check for movement commands
        if len(self.cmd_vel_commands) > 0:
            has_forward = any(cmd['linear_x'] > 0.05 for cmd in self.cmd_vel_commands)
            has_turning = any(abs(cmd['angular_z']) > 0.1 for cmd in self.cmd_vel_commands)
            
            if has_forward:
                results.append("✅ Forward movement commands detected")
            else:
                results.append("❌ No forward movement commands")
                
            if has_turning:
                results.append("✅ Turning commands detected (navigation/search)")
            else:
                results.append("❌ No turning commands")
        else:
            results.append("❌ No movement commands recorded")
        
        # Check for status updates
        if len(self.status_messages) > 0:
            latest_status = self.status_messages[-1]['message']
            results.append("📊 Latest status: {}".format(latest_status))
        else:
            results.append("❌ No status messages received")
        
        return results
    
    def run_test(self):
        """Execute the UAT test"""
        rospy.loginfo("\n" + "="*60)
        rospy.loginfo("STARTING VISION NAVIGATION UAT")
        rospy.loginfo("="*60)
        
        self.test_start_time = rospy.Time.now()
        
        # Wait for system to initialize
        rospy.loginfo("Waiting 3 seconds for system initialization...")
        time.sleep(3.0)
        
        # Run test for specified duration
        rospy.loginfo("Running vision navigation test for {:.1f} seconds...".format(self.test_duration))
        
        rate = rospy.Rate(2)  # 2 Hz monitoring
        elapsed_time = 0.0
        
        while elapsed_time < self.test_duration and not rospy.is_shutdown():
            elapsed_time = (rospy.Time.now() - self.test_start_time).to_sec()
            
            # Progress update every 5 seconds
            if int(elapsed_time) % 5 == 0 and elapsed_time > 0:
                rospy.loginfo("UAT Progress: {:.1f}s elapsed, {} detections, {} positions".format(
                    elapsed_time, len(self.ball_detections), len(self.robot_positions)))
            
            rate.sleep()
        
        # Analyze results
        rospy.loginfo("\n" + "="*60)
        rospy.loginfo("UAT TEST ANALYSIS")
        rospy.loginfo("="*60)
        
        # Ball approach analysis
        approach_success, approach_msg = self.analyze_ball_approach()
        rospy.loginfo("Ball Approach: {}".format(approach_msg))
        
        # Navigation behavior analysis
        nav_results = self.analyze_navigation_behavior()
        rospy.loginfo("Navigation Behavior:")
        for result in nav_results:
            rospy.loginfo("  {}".format(result))
        
        # Summary statistics
        rospy.loginfo("\nTest Statistics:")
        rospy.loginfo("  - Test duration: {:.1f} seconds".format(elapsed_time))
        rospy.loginfo("  - Ball detections: {}".format(len(self.ball_detections)))
        rospy.loginfo("  - Robot positions recorded: {}".format(len(self.robot_positions)))
        rospy.loginfo("  - Movement commands: {}".format(len(self.cmd_vel_commands)))
        rospy.loginfo("  - Status messages: {}".format(len(self.status_messages)))
        rospy.loginfo("  - Distance moved: {:.2f}m".format(self.calculate_distance_moved()))
        
        # Overall result
        rospy.loginfo("\n" + "="*60)
        if approach_success:
            rospy.loginfo("🎉 UAT RESULT: SUCCESS - Vision navigation working!")
            rospy.loginfo("   Robot successfully detected and approached the golf ball")
            return True
        else:
            rospy.loginfo("❌ UAT RESULT: NEEDS IMPROVEMENT")
            rospy.loginfo("   Vision navigation needs tuning or debugging")
            return False

def main():
    try:
        # Initialize UAT
        uat = VisionNavigationUAT()
        
        # Run the test
        success = uat.run_test()
        
        # Exit with appropriate code
        if success:
            rospy.loginfo("Vision Navigation UAT completed successfully")
            sys.exit(0)
        else:
            rospy.loginfo("Vision Navigation UAT failed - check logs for details")
            sys.exit(1)
            
    except rospy.ROSInterruptException:
        rospy.loginfo("Vision Navigation UAT interrupted")
        sys.exit(1)
    except Exception as e:
        rospy.logerr("Vision Navigation UAT error: {}".format(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
