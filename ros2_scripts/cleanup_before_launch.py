#!/usr/bin/env python3
"""
Pre-launch cleanup script to ensure no conflicting processes are running
"""

import subprocess
import sys
import time

def kill_processes():
    """Kill any existing Gazebo and ROS processes"""
    print("=== Pre-launch Cleanup ===")
    print("Checking for existing processes...")
    
    # Define process patterns to check
    process_patterns = [
        'gazebo',
        'gzserver',
        'gzclient',
        'ros2',
        'robot_state_publisher',
        'joint_state_publisher',
        'spawn_entity'
    ]
    
    # Check each pattern
    processes_found = False
    for pattern in process_patterns:
        try:
            # Check if process exists
            result = subprocess.run(['pgrep', '-f', pattern], 
                                  capture_output=True, 
                                  text=True)
            
            if result.stdout.strip():
                processes_found = True
                print(f"Found {pattern} processes: {result.stdout.strip()}")
                # Kill the processes
                subprocess.run(['pkill', '-f', pattern], check=False)
                
        except Exception as e:
            print(f"Error checking {pattern}: {e}")
    
    if processes_found:
        print("Waiting for processes to terminate...")
        time.sleep(2)  # Give processes time to shut down
        print("Cleanup complete!")
    else:
        print("No conflicting processes found.")
    
    print("=== Ready to launch ===\n")

if __name__ == '__main__':
    kill_processes()
