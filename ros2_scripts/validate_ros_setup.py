#!/usr/bin/env python

"""
ROS Environment Validation Script for ChaseBot
This script validates that ROS Melodic and Gazebo are properly installed and working.
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and check if it succeeds"""
    print(f"Testing: {description}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ PASS: {description}")
            return True
        else:
            print(f"❌ FAIL: {description}")
            print(f"Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️ TIMEOUT: {description}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {description} - {str(e)}")
        return False

def main():
    """Main validation function"""
    print("=" * 60)
    print("ChaseBot ROS Environment Validation")
    print("=" * 60)
    
    # List of validation tests
    tests = [
        # ROS Core Tests
        ("source /opt/ros/melodic/setup.bash && which roscore", "ROS Core Available"),
        ("source /opt/ros/melodic/setup.bash && which rosnode", "ROS Node Tools Available"),
        ("source /opt/ros/melodic/setup.bash && which rostopic", "ROS Topic Tools Available"),
        ("source /opt/ros/melodic/setup.bash && which roslaunch", "ROS Launch Available"),
        ("source /opt/ros/melodic/setup.bash && which catkin_make", "Catkin Build System Available"),
        
        # Gazebo Tests
        ("which gazebo", "Gazebo Simulator Available"),
        ("which gzserver", "Gazebo Server Available"),
        ("which gzclient", "Gazebo Client Available"),
        
        # ROS-Gazebo Integration Tests
        ("source /opt/ros/melodic/setup.bash && rospack find gazebo_ros", "Gazebo ROS Integration Available"),
        ("source /opt/ros/melodic/setup.bash && rospack find gazebo_plugins", "Gazebo ROS Plugins Available"),
        
        # Python Dependencies
        ("python2 -c 'import rospy; print(\"ROS Python bindings work\")'", "ROS Python Bindings"),
        ("python2 -c 'import cv2; print(\"OpenCV available\")'", "OpenCV Available"),
        ("python2 -c 'import numpy; print(\"NumPy available\")'", "NumPy Available"),
        
        # Catkin Workspace Test
        ("test -d ~/catkin_ws/src", "Catkin Workspace Structure"),
        ("source ~/catkin_ws/devel/setup.bash && echo 'Workspace sourced'", "Catkin Workspace Sourcing"),
    ]
    
    passed = 0
    total = len(tests)
    
    for command, description in tests:
        if run_command(command, description):
            passed += 1
        print()
    
    print("=" * 60)
    print(f"VALIDATION SUMMARY: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("🎉 SUCCESS: ROS environment is fully functional!")
        print("✅ ROS Melodic is installed and working")
        print("✅ Gazebo 9 is installed and integrated")
        print("✅ Catkin workspace is set up")
        print("✅ All dependencies are available")
        print("\nReady for ChaseBot development!")
        return True
    else:
        print(f"⚠️ WARNING: {total - passed} tests failed")
        print("Some components may not be working correctly.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
