#!/usr/bin/env python3
"""
Simple Nav2 Test - Launch simulation first, then Nav2
"""

import subprocess
import time
import sys

def run_test():
    print("=== Simple Nav2 Test ===")
    print("This test launches simulation first, then Nav2 components")
    
    # Launch simulation with robot
    print("\n[STEP 1] Launching simulation with JetBot...")
    sim_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && "
        "ros2 launch chasebot_description jetbot_gz_control_camera_test_v5.launch.py"
    ])
    
    print("[INFO] Waiting for simulation to start...")
    time.sleep(10)
    
    # Check if simulation is running
    print("\n[STEP 2] Checking topics...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && ros2 topic list | grep -E 'odom|cmd_vel|tf'"
    ])
    
    # Launch blank map publisher
    print("\n[STEP 3] Launching blank map publisher...")
    map_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py"
    ])
    
    time.sleep(3)
    
    # Launch controller server only
    print("\n[STEP 4] Launching controller_server...")
    controller_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "ros2 run nav2_controller controller_server --ros-args "
        "-p use_sim_time:=True "
        "--params-file ~/ros2_ws/src/chasebot_description/ros2_scripts/nav2_complete_params.yaml"
    ])
    
    time.sleep(5)
    
    # Check controller state
    print("\n[STEP 5] Checking controller server state...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && ros2 lifecycle get /controller_server"
    ])
    
    # Try to configure controller
    print("\n[STEP 6] Configuring controller_server...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && ros2 lifecycle set /controller_server configure"
    ])
    
    time.sleep(2)
    
    # Check state again
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && ros2 lifecycle get /controller_server"
    ])
    
    print("\n[INFO] Test complete. Nav2 controller_server is running.")
    print("Press Ctrl+C to stop all processes.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping all processes...")
        sim_process.terminate()
        map_process.terminate()
        controller_process.terminate()
        
        # Wait for clean shutdown
        sim_process.wait()
        map_process.wait()
        controller_process.wait()

if __name__ == "__main__":
    run_test()
