# ChaseBot Operational Guide

This consolidated guide combines all operational procedures for ChaseBot development and testing.

## Quick Start Commands

### YOLO Detection Demo (Recommended)
```bash
# 1. Start VcXsrv with access control disabled
# 2. Launch complete YOLO system
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}'):0.0 && ros2 launch ~/ros2_ws/jetbot_yolo_complete.launch.py"

# 3. View detections with bounding boxes
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}'):0.0 && ros2 run rqt_image_view rqt_image_view"
# Select /yolo/debug_image in the dropdown
```

### Environment Check
```bash
# Check WSL2 status
wsl --list --verbose

# Verify ROS 2
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"

# Test X11 display
wsl -d Ubuntu-22.04 bash -c "DISPLAY=\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}'):0.0 && xeyes"
```

## Session Initialization

### Prerequisites
1. **VcXsrv Running**: Windows X Server must be active in system tray
2. **WSL2 Ubuntu-22.04**: Running with ROS 2 Humble installed
3. **Files Synced**: Latest files copied from Windows to WSL2

### Standard Initialization Sequence
1. Check WSL2 status: `wsl --list --verbose`
2. Start WSL2 if stopped: `wsl -d Ubuntu-22.04`
3. Kill existing processes (PID-based method)
4. Copy updated files from Windows to WSL2
5. Source ROS environment
6. Launch fresh simulation

### Process Cleanup (CRITICAL: Use PIDs)
```bash
# List processes
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep"

# Kill specific PIDs (NEVER use generic pkill)
wsl -d Ubuntu-22.04 bash -c "kill -9 [PID1] [PID2] [PID3]"

# Verify cleanup
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep"
```

## Simplified UAT Order of Operations

### Order: GUI → Ball → Bot → Nav
This sequence ensures proper component initialization:

1. **Start GUI**: Launch Gazebo with world
2. **Spawn Ball**: Add golf ball targets
3. **Spawn Bot**: Launch JetBot robot
4. **Boot NAV**: Start Nav2 and autonomous behavior

### Success Criteria
- ✅ Gazebo GUI stable and visible
- ✅ Robot detects green golf ball
- ✅ Navigation goals published to Nav2
- ✅ Robot autonomously approaches ball
- ✅ Clean logs without transform warnings

## File Synchronization

### Standard File Copy Commands
```bash
# Copy launch files
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/*.launch.py ~/ros2_ws/src/chasebot_description/launch/"

# Copy scripts
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/*.py ~/ros2_ws/src/chasebot_description/scripts/ && chmod +x ~/ros2_ws/src/chasebot_description/scripts/*.py"

# Copy worlds
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/*.world ~/ros2_ws/src/chasebot_description/worlds/"

# Copy URDF
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/*.urdf ~/ros2_ws/src/chasebot_description/urdf/"

# Copy config files
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/*.yaml ~/ros2_ws/src/chasebot_description/"
```

### Workspace Rebuild
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"
```

## Manual Component Launch Sequence

### 1. Launch Gazebo with World
```bash
wsl -d Ubuntu-22.04 bash -c "
    DISPLAY_IP=\$(ip route show default | awk '{print \$3}')
    export DISPLAY=\${DISPLAY_IP}:0
    export LIBGL_ALWAYS_INDIRECT=1
    export MESA_GL_VERSION_OVERRIDE=3.3
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws && source install/setup.bash
    ros2 launch gazebo_ros gazebo.launch.py world:=~/ros2_ws/src/chasebot_description/worlds/autonomous_golf_ball_world.world
" &
```
**Wait**: 10 seconds for Gazebo initialization

### 2. Spawn Golf Balls (Manual Required)
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws && source install/setup.bash
    ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/green_golf_ball.sdf -entity golf_ball_1 -x 1.0 -y 0.0 -z 0.025
"
```
**Note**: World file golf balls do NOT spawn automatically

### 3. Spawn JetBot Robot
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws && source install/setup.bash
    ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/src/chasebot_description/urdf/ros2_jetbot.urdf -entity jetbot -x 0 -y 0 -z 0.1
"
```
**Wait**: 3 seconds for controllers to initialize

### 4. Launch Nav2 Stack
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws && source install/setup.bash
    ros2 launch nav2_bringup navigation_launch.py params_file:=/home/macro2/ros2_ws/src/chasebot_description/nav2_params_simple.yaml use_sim_time:=true
" &
```
**Wait**: 8 seconds for Nav2 initialization

### 5. Start Vision Processing
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws && source install/setup.bash
    python3 ~/ros2_ws/src/chasebot_description/scripts/ros2_vision_to_laserscan_hsv.py
" &
```

### 6. Start Ball-to-Nav Goal Converter
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws && source install/setup.bash
    python3 ~/ros2_ws/src/chasebot_description/scripts/ros2_ball_to_nav_goal.py
" &
```

## Common Issues & Solutions

### GUI Issues
- **Problem**: Gazebo doesn't open
- **Solution**: Verify VcXsrv running, test X11 connection, check firewall

### Process Conflicts
- **Problem**: "Address already in use" errors
- **Solution**: Use PID-based cleanup (NEVER generic pkill)

### Transform Warnings
- **Problem**: Nav2 costmap transform cache warnings
- **Solution**: Use 'base_link' frame_id in laser scan messages

### Package Installation
- **Problem**: "libexec directory does not exist"
- **Solution**: Use manual script execution instead of launch files

## Architecture Overview

```
Windows Development → WSL2 Execution
    ↓
File Sync → Workspace Build → Component Launch
    ↓
Gazebo GUI → Robot Spawn → Nav2 Stack → Vision Processing
    ↓
Autonomous Ball Following with Professional Navigation
```

## Key Success Factors

1. **VcXsrv Must Be Running**: GUI requires Windows X server
2. **PID-Based Process Management**: Generic pkill unreliable
3. **Sequential Component Launch**: Proper timing essential
4. **File Synchronization**: Latest files must be in WSL2
5. **Workspace Rebuild**: Required after file changes

This operational guide represents proven, working procedures validated through multiple UAT sessions.
