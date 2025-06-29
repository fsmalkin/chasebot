# ChaseBot Manual Steps - PROVEN WORKING PROCEDURE

**IMPORTANT**: Use these EXACT manual steps. Do NOT use scripts - they have proven unreliable.

**Date**: 2025-06-29  
**Status**: ✅ VALIDATED - Manual steps work reliably

## Critical Notes

1. **NO SCRIPTS**: The `run_chasebot_demo.sh` script approach has failed repeatedly. Use manual steps only.
2. **ONE BALL ONLY**: We spawn just one golf ball for simplicity and reliability.
3. **EXACT COMMANDS**: Copy and paste these commands exactly as shown.
4. **SEQUENTIAL EXECUTION**: Wait for each step to complete before proceeding to the next.

## Prerequisites

- VcXsrv running on Windows (check system tray)
- WSL2 Ubuntu-22.04 with ROS 2 Humble installed
- All files synced from Windows to WSL2

## Step-by-Step Manual Procedure

### Step 1: File Sync and Workspace Build
```bash
# Copy all necessary files
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/green_golf_ball.sdf ~/ros2_ws/ && cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_vision_to_laserscan_hsv.py ~/ros2_ws/src/chasebot_description/scripts/ && cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_ball_to_nav_goal.py ~/ros2_ws/src/chasebot_description/scripts/ && cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_jetbot.urdf ~/ros2_ws/src/chasebot_description/urdf/ && cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/nav2_params_simple.yaml ~/ros2_ws/src/chasebot_description/ && chmod +x ~/ros2_ws/src/chasebot_description/scripts/*.py"

# Build workspace
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"
```

### Step 2: Launch Gazebo
```bash
wsl -d Ubuntu-22.04 bash -c "export DISPLAY=172.19.144.1:0 && source /opt/ros/humble/setup.bash && cd ~/ros2_ws && source install/setup.bash && ros2 launch gazebo_ros gazebo.launch.py"
```
**WAIT**: 10 seconds for Gazebo to fully load

### Step 3: Spawn ONE Golf Ball (Critical!)
```bash
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && cd ~/ros2_ws && source install/setup.bash && ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/green_golf_ball.sdf -entity golf_ball_1 -x 1.0 -y 0.0 -z 0.025"
```
**VERIFY**: Green golf ball appears directly in front of robot spawn position

### Step 4: Spawn JetBot Robot
```bash
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && cd ~/ros2_ws && source install/setup.bash && ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/src/chasebot_description/urdf/ros2_jetbot.urdf -entity jetbot -x 0 -y 0 -z 0.1"
```
**WAIT**: 3 seconds for robot controllers to initialize

### Step 5: Launch Nav2
```bash
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && cd ~/ros2_ws && source install/setup.bash && ros2 launch nav2_bringup navigation_launch.py params_file:=/home/macro2/ros2_ws/src/chasebot_description/nav2_params_simple.yaml use_sim_time:=true"
```
**WAIT**: 8 seconds for Nav2 to report "Managed nodes are active"

### Step 6: Start Vision to LaserScan
```bash
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && cd ~/ros2_ws && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/scripts/ros2_vision_to_laserscan_hsv.py"
```
**WAIT**: 3 seconds for initialization

### Step 7: Start Ball to Nav Goal
```bash
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && cd ~/ros2_ws && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/scripts/ros2_ball_to_nav_goal.py"
```

## Expected Result

1. Gazebo GUI shows robot and ONE green golf ball
2. Robot detects the ball and begins moving toward it
3. Navigation is handled by Nav2 with path planning

## Process Cleanup

When done, kill all processes:
```bash
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep | awk '{print \$2}' | xargs -r kill -9 2>/dev/null"
```

## Why Manual Steps Work

1. **Timing Control**: Manual execution allows proper wait times between components
2. **Environment Isolation**: Each command gets fresh environment setup
3. **Error Visibility**: You can see exactly where issues occur
4. **No Script Complexity**: Avoids shell script parsing and execution issues

## Common Issues

- **DISPLAY not set**: The display IP may change. Run `wsl -d Ubuntu-22.04 bash -c "ip route show default | awk '{print \$3}'"` to get current IP
- **Golf ball not visible**: World file balls don't spawn - manual spawning is REQUIRED
- **Robot not moving**: Check all components launched successfully in sequence

Remember: These manual steps have been proven to work. Follow them exactly in order.
