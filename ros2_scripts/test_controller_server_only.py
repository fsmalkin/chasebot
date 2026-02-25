#!/usr/bin/env python3
"""
Test Controller Server Only
Minimal test to debug controller_server issues
"""

import subprocess
import time
import sys
from pathlib import Path


def to_wsl_path(path: Path) -> str:
    """Convert a Windows path to /mnt/<drive>/... for WSL."""
    as_posix = path.resolve().as_posix()
    if len(as_posix) >= 3 and as_posix[1] == ":":
        return f"/mnt/{as_posix[0].lower()}{as_posix[2:]}"
    return as_posix

def run_test():
    print("=== Testing Controller Server Only ===")
    print("This test launches just the controller_server with minimal config")
    
    # First, ensure we have the necessary topics
    print("\n[STEP 1] Checking required topics...")
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "source /opt/ros/humble/setup.bash && ros2 topic list | grep -E '(odom|cmd_vel|tf)'"
    ])
    
    # Create minimal params file
    print("\n[STEP 2] Creating minimal controller params...")
    minimal_params = """controller_server:
  ros__parameters:
    use_sim_time: True
    controller_frequency: 20.0
    min_x_velocity_threshold: 0.001
    min_y_velocity_threshold: 0.5
    min_theta_velocity_threshold: 0.001
    failure_tolerance: 0.3
    progress_checker_plugin: "progress_checker"
    goal_checker_plugins: ["general_goal_checker"]
    controller_plugins: ["FollowPath"]
    
    progress_checker:
      plugin: "nav2_controller::SimpleProgressChecker"
      required_movement_radius: 0.5
      movement_time_allowance: 10.0
    
    general_goal_checker:
      stateful: True
      plugin: "nav2_controller::SimpleGoalChecker"
      xy_goal_tolerance: 0.25
      yaw_goal_tolerance: 0.25
    
    FollowPath:
      plugin: "dwb_core::DWBLocalPlanner"
      min_vel_x: -0.2
      max_vel_x: 0.2
      max_vel_theta: 0.5
      min_speed_theta: -0.5
      acc_lim_x: 1.0
      acc_lim_theta: 2.0
      decel_lim_x: -1.0
      decel_lim_theta: -2.0
      transform_tolerance: 0.2

local_costmap:
  local_costmap:
    ros__parameters:
      update_frequency: 5.0
      publish_frequency: 2.0
      global_frame: odom
      robot_base_frame: base_link
      use_sim_time: True
      rolling_window: true
      width: 3
      height: 3
      resolution: 0.05
      robot_radius: 0.22
      plugins: ["static_layer", "inflation_layer"]
      static_layer:
        plugin: "nav2_costmap_2d::StaticLayer"
        map_subscribe_transient_local: True
      inflation_layer:
        plugin: "nav2_costmap_2d::InflationLayer"
        cost_scaling_factor: 3.0
        inflation_radius: 0.55
      always_send_full_costmap: True
"""
    
    # Write params file
    with open("controller_minimal_params.yaml", "w", encoding="utf-8") as f:
        f.write(minimal_params)

    local_params_wsl = to_wsl_path(Path("controller_minimal_params.yaml"))
    
    # Copy to WSL
    subprocess.run([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        f"cp '{local_params_wsl}' ~/ros2_ws/src/chasebot_description/ros2_scripts/controller_minimal_params.yaml"
    ])
    
    # Launch controller_server
    print("\n[STEP 3] Launching controller_server...")
    print("Watch for errors in the output below:")
    print("-" * 50)
    
    process = subprocess.Popen([
        "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
        "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && "
        "ros2 run nav2_controller controller_server --ros-args "
        "-p use_sim_time:=True "
        "--params-file ~/ros2_ws/src/chasebot_description/ros2_scripts/controller_minimal_params.yaml "
        "--log-level debug"
    ])
    
    # Wait a bit
    time.sleep(5)
    
    # Check if it's still running
    if process.poll() is None:
        print("\n[SUCCESS] Controller server is running!")
        
        # Check lifecycle state
        print("\n[STEP 4] Checking lifecycle state...")
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle get /controller_server"
        ])
        
        print("\n[INFO] Controller server is running. Press Ctrl+C to stop.")
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n[INFO] Stopping controller server...")
            process.terminate()
    else:
        print("\n[ERROR] Controller server crashed! Check the output above for errors.")
        return process.returncode

if __name__ == "__main__":
    sys.exit(run_test())
