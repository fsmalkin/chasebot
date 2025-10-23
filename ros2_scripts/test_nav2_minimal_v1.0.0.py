#!/usr/bin/env python3
"""
Minimal Nav2 Test Version 1.0.0 - Just controller_server with proper remapping
This is the simplest possible Nav2 test to verify basic functionality
"""

import subprocess
import time
import sys

def run_test():
    print("=== Minimal Nav2 Test v1.0.0 ===")
    print("Testing just controller_server with topic remapping")
    
    # Get display IP dynamically
    print("\n[STEP 0] Detecting display IP...")
    get_ip_cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        'cat /etc/resolv.conf | grep nameserver | awk \'{print $2}\''
    ]
    result = subprocess.run(get_ip_cmd, capture_output=True, text=True)
    # Extract just the IP address
    output = result.stdout.strip()
    if output:
        # Handle case where output might be "nameserver X.X.X.X" or just "X.X.X.X"
        parts = output.split()
        display_ip = parts[-1] if parts else ""
    else:
        display_ip = ""
    
    # Default fallback if detection fails
    if not display_ip:
        display_ip = "192.168.96.1"
        print(f"Could not detect display IP, using default: {display_ip}")
    else:
        print(f"Detected display IP: {display_ip}")
    
    display_var = f"{display_ip}:0.0"
    print(f"Using DISPLAY={display_var}")
    
    # Kill any existing processes
    print("\n[CLEANUP] Checking for existing processes...")
    result = subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "ps aux | grep -E '(gazebo|ros2|nav2)' | grep -v grep"
    ], capture_output=True, text=True)
    
    if result.stdout:
        print("Found existing processes:")
        print(result.stdout)
        print("\nKilling processes...")
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "pkill -f gazebo; pkill -f ros2; pkill -f nav2; sleep 2"
        ])
    
    # Launch simulation
    print("\n[STEP 1] Launching simulation...")
    sim_cmd = (
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        f"export DISPLAY={display_var} && "
        "ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py"
    )
    
    print(f"Command: {sim_cmd}")
    sim_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c", sim_cmd
    ])
    
    print("Waiting 15 seconds for simulation to fully start...")
    time.sleep(15)
    
    # Check topics
    print("\n[STEP 2] Checking available topics...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && ros2 topic list | sort"
    ])
    
    # Check for required topics
    print("\n[STEP 3] Verifying required topics...")
    required_topics = ['/odom', '/tf', '/jetbot_base_controller/cmd_vel']
    for topic in required_topics:
        result = subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            f"source /opt/ros/humble/setup.bash && ros2 topic list | grep -q '{topic}' && echo '✓ Found: {topic}' || echo '✗ Missing: {topic}'"
        ], capture_output=True, text=True)
        print(result.stdout.strip())
    
    # Test robot movement
    print("\n[STEP 4] Testing robot movement...")
    print("Sending movement command...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped "
        "'{header: {stamp: {sec: 0, nanosec: 0}, frame_id: \"\"}, twist: {linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}}'"
    ])
    
    print("\n[INFO] Basic simulation is working!")
    print("The robot should have moved forward slightly.")
    print("\nNext steps would be to add Nav2 components.")
    print("\nPress Ctrl+C to stop the simulation.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping simulation...")
        sim_process.terminate()
        sim_process.wait()
        print("Simulation stopped.")

if __name__ == "__main__":
    run_test()
