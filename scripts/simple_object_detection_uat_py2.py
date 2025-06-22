#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ChaseBot Simple Object Detection UAT
Basic test: Can we detect ANY object in the camera feed?
Python 2.7 compatible version for ROS Melodic
"""

import rospy
import subprocess
import time
import signal
import sys
from geometry_msgs.msg import Point

class SimpleObjectDetectionUAT:
    def __init__(self):
        rospy.init_node('simple_object_detection_uat', anonymous=True)
        
        # Test parameters
        self.test_duration = 20.0  # Test for 20 seconds
        self.detection_required = 1  # Need at least 1 detection to pass
        
        # State tracking
        self.detections = []
        self.test_start_time = None
        
        # Subscriber to monitor detections
        self.detection_sub = rospy.Subscriber('/object_detection', Point, self.detection_callback)
        
        rospy.loginfo("Simple Object Detection UAT initialized")
        rospy.loginfo("Test duration: {:.1f}s, Required detections: {}".format(
            self.test_duration, self.detection_required))
    
    def detection_callback(self, msg):
        """Track object detections"""
        detection = {
            'time': rospy.Time.now(),
            'x': msg.x,
            'y': msg.y,
            'area': msg.z
        }
        self.detections.append(detection)
        
        rospy.loginfo("UAT: DETECTION #{}: Object at ({:.0f}, {:.0f}), area: {:.0f}".format(
            len(self.detections), msg.x, msg.y, msg.z))
    
    def run_test(self):
        """Execute the UAT test"""
        rospy.loginfo("\n" + "="*50)
        rospy.loginfo("STARTING SIMPLE OBJECT DETECTION UAT")
        rospy.loginfo("="*50)
        rospy.loginfo("Goal: Detect ANY object in camera feed")
        rospy.loginfo("Environment: Simple world with golf ball")
        rospy.loginfo("Detection system: OpenCV contour analysis")
        
        self.test_start_time = rospy.Time.now()
        
        # Wait for system to initialize
        rospy.loginfo("Waiting 5 seconds for system initialization...")
        time.sleep(5.0)
        
        # Run test
        rospy.loginfo("Running object detection test for {:.1f} seconds...".format(self.test_duration))
        
        rate = rospy.Rate(2)  # 2 Hz monitoring
        elapsed_time = 0.0
        
        while elapsed_time < self.test_duration and not rospy.is_shutdown():
            elapsed_time = (rospy.Time.now() - self.test_start_time).to_sec()
            
            # Progress update every 5 seconds
            if int(elapsed_time) % 5 == 0 and elapsed_time > 0:
                rospy.loginfo("UAT Progress: {:.1f}s elapsed, {} detections so far".format(
                    elapsed_time, len(self.detections)))
            
            rate.sleep()
        
        # Analyze results
        rospy.loginfo("\n" + "="*50)
        rospy.loginfo("UAT TEST RESULTS")
        rospy.loginfo("="*50)
        
        # Basic statistics
        total_detections = len(self.detections)
        rospy.loginfo("Total detections: {}".format(total_detections))
        rospy.loginfo("Test duration: {:.1f} seconds".format(elapsed_time))
        
        if total_detections > 0:
            # Show detection details
            rospy.loginfo("Detection details:")
            for i, detection in enumerate(self.detections[:5]):  # Show first 5
                rospy.loginfo("  #{}: Position ({:.0f}, {:.0f}), Area: {:.0f}".format(
                    i+1, detection['x'], detection['y'], detection['area']))
            
            if len(self.detections) > 5:
                rospy.loginfo("  ... and {} more detections".format(len(self.detections) - 5))
        
        # Success criteria
        rospy.loginfo("\n" + "="*50)
        if total_detections >= self.detection_required:
            rospy.loginfo("SUCCESS: UAT RESULT: SUCCESS!")
            rospy.loginfo("   [OK] Object detection is working")
            rospy.loginfo("   [OK] Found {} objects (required: {})".format(
                total_detections, self.detection_required))
            rospy.loginfo("   [OK] Camera feed is functional")
            rospy.loginfo("   [OK] OpenCV processing is working")
            return True
        else:
            rospy.loginfo("FAILED: UAT RESULT: FAILED")
            rospy.loginfo("   [X] Only {} detections (required: {})".format(
                total_detections, self.detection_required))
            rospy.loginfo("   Possible issues:")
            rospy.loginfo("      - Camera not working")
            rospy.loginfo("      - Object detector not running")
            rospy.loginfo("      - Golf ball not visible to camera")
            rospy.loginfo("      - Detection thresholds too strict")
            return False

def main():
    try:
        # Initialize UAT
        uat = SimpleObjectDetectionUAT()
        
        # Run the test
        success = uat.run_test()
        
        # Exit with appropriate code
        if success:
            rospy.loginfo("\nSUCCESS: Simple Object Detection UAT PASSED!")
            rospy.loginfo("Ready to proceed with navigation implementation")
            sys.exit(0)
        else:
            rospy.loginfo("\nFAILED: Simple Object Detection UAT FAILED")
            rospy.loginfo("Need to debug object detection system")
            sys.exit(1)
            
    except rospy.ROSInterruptException:
        rospy.loginfo("Simple Object Detection UAT interrupted")
        sys.exit(1)
    except Exception as e:
        rospy.logerr("Simple Object Detection UAT error: {}".format(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
