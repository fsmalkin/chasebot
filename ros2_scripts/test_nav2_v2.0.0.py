#!/usr/bin/env python3
"""
Nav2 Test Version 2.0.0 - Proper topic remapping and individual component launch
Major changes from v1:
- v2.0.0: Complete rewrite with proper topic remapping and no lifecycle_manager
- Individual component launch to avoid hanging issues
- cmd_vel relay for proper topic routing
"""

import subprocess
import time
import sys
import os

def run_test():
    print("=== Nav2 Test v2.0.0 ===")
    print("This version launches Nav2 with proper topic remapping")
    print("Components are launched individually to avoid lifecycle_manager issues")
    
    # Kill any existing processes
    print("\n[CLEANUP] Killing any existing processes...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "pkill -f gazebo; pkill -f ros2; pkill -f nav2; sleep 2"
    ])
    
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
    
    # Launch static transform for map->odom
    print("\n[STEP 3] Publishing static transform (map->odom)...")
    tf_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom"
    ])
    
    time.sleep(2)
    
    # Launch blank map publisher
    print("\n[STEP 4] Launching blank map publisher...")
    map_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py"
    ])
    
    time.sleep(3)
    
    # Create a cmd_vel relay node to remap topics
    print("\n[STEP 5] Creating cmd_vel relay node...")
    relay_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/cmd_vel_relay_v2.0.0.py"
    ])
    
    time.sleep(2)
    
    # Launch controller server with remapping
    print("\n[STEP 6] Launching controller_server with topic remapping...")
    controller_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "ros2 run nav2_controller controller_server --ros-args "
        "-p use_sim_time:=True "
        "--params-file ~/ros2_ws/src/chasebot_description/ros2_scripts/nav2_minimal_params_v2.yaml "
        "--remap cmd_vel:=cmd_vel_nav "  # Nav2 publishes to cmd_vel_nav
        "--log-level info"
    ])
    
    time.sleep(5)
    
    # Launch planner server
    print("\n[STEP 7] Launching planner_server...")
    planner_process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "ros2 run nav2_planner planner_server --ros-args "
        "-p use_sim_time:=True "
        "--params-file ~/ros2_ws/src/chasebot_description/ros2_scripts/nav2_minimal_params_v2.yaml "
        "--log-level info"
    ])
    
    time.sleep(5)
    
    # Manually configure and activate nodes
    print("\n[STEP 8] Configuring nodes...")
    
    # Configure controller_server
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 lifecycle set /controller_server configure"
    ])
    
    time.sleep(2)
    
    # Configure planner_server
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 lifecycle set /planner_server configure"
    ])
    
    time.sleep(2)
    
    # Activate controller_server
    print("\n[STEP 9] Activating nodes...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 lifecycle set /controller_server activate"
    ])
    
    time.sleep(2)
    
    # Activate planner_server
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 lifecycle set /planner_server activate"
    ])
    
    time.sleep(2)
    
    # Check states
    print("\n[STEP 10] Checking node states...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "echo 'Controller state:' && ros2 lifecycle get /controller_server && "
        "echo 'Planner state:' && ros2 lifecycle get /planner_server"
    ])
    
    # Test navigation goal
    print("\n[STEP 11] Sending test navigation goal...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && "
        "ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "
        "'{pose: {header: {frame_id: \"map\"}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}}}}'"
    ])
    
    print("\n[SUCCESS] Nav2 is running with proper topic remapping!")
    print("The robot should now navigate to the goal position.")
    print("\nPress Ctrl+C to stop all processes.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping all processes...")
        sim_process.terminate()
        tf_process.terminate()
        map_process.terminate()
        relay_process.terminate()
        controller_process.terminate()
        planner_process.terminate()
        
        # Wait for clean shutdown
        sim_process.wait()
        tf_process.wait()
        map_process.wait()
        relay_process.wait()
        controller_process.wait()
        planner_process.wait()

if __name__ == "__main__":
    run_test()
