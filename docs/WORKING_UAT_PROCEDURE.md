# ChaseBot Working UAT Procedure

**PROVEN WORKING SEQUENCE - 2025-06-29**

This document captures the exact procedure that successfully demonstrates ChaseBot's autonomous navigation capabilities. This is based on actual working execution, not theoretical approaches.

## Quick Start

**Single Command Demo:**
```bash
./run_chasebot_demo.sh
```

## Prerequisites

### Required Setup
1. **VcXsrv Running**: Windows X Server must be active in system tray
2. **WSL2 Ubuntu-22.04**: Must be running with ROS 2 Humble installed
3. **Files Synced**: Latest files copied from Windows to WSL2

### Verification Commands
```bash
# Check WSL2 status
wsl --list --verbose

# Verify VcXsrv connection
wsl -d Ubuntu-22.04 bash -c "DISPLAY=\$(ip route show default | awk '{print \$3}'):0 && xset q"

# Verify ROS 2
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"
```

## Manual Step-by-Step Procedure

### Step 1: Display Environment Setup
```bash
# Auto-detect and set display
wsl -d Ubuntu-22.04 bash -c "
    DISPLAY_IP=\$(ip route show default | awk '{print \$3}')
    export DISPLAY=\${DISPLAY_IP}:0
    export LIBGL_ALWAYS_INDIRECT=1
    export MESA_GL_VERSION_OVERRIDE=3.3
    echo 'DISPLAY set to: '\$DISPLAY
"
```

### Step 2: File Synchronization
```bash
# Copy latest files from Windows to WSL2
wsl -d Ubuntu-22.04 bash -c "
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/nav2_complete_uat.launch.py ~/ros2_ws/src/chasebot_description/launch/
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_vision_to_laserscan_hsv.py ~/ros2_ws/src/chasebot_description/scripts/
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_ball_to_nav_goal.py ~/ros2_ws/src/chasebot_description/scripts/
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/autonomous_golf_ball_world.world ~/ros2_ws/src/chasebot_description/worlds/
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_jetbot.urdf ~/ros2_ws/src/chasebot_description/urdf/
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/nav2_params_simple.yaml ~/ros2_ws/src/chasebot_description/
    chmod +x ~/ros2_ws/src/chasebot_description/scripts/*.py
"
```

### Step 3: Workspace Rebuild
```bash
# Rebuild the ROS 2 workspace
wsl -d Ubuntu-22.04 bash -c "
    cd ~/ros2_ws
    source /opt/ros/humble/setup.bash
    colcon build --packages-select chasebot_description
"
```

### Step 4: Process Cleanup
```bash
# Clean up any existing processes using PID-based method
wsl -d Ubuntu-22.04 bash -c "
    PIDS=\$(ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep | awk '{print \$2}' | tr '\n' ' ')
    if [ ! -z '\$PIDS' ]; then
        kill -9 \$PIDS 2>/dev/null || true
        sleep 2
    fi
"
```

### Step 5: Launch Components in Sequence

#### 5.1 Launch Gazebo with Golf Ball World
```bash
wsl -d Ubuntu-22.04 bash -c "
    DISPLAY_IP=\$(ip route show default | awk '{print \$3}')
    export DISPLAY=\${DISPLAY_IP}:0
    export LIBGL_ALWAYS_INDIRECT=1
    export MESA_GL_VERSION_OVERRIDE=3.3
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 launch gazebo_ros gazebo.launch.py world:=~/ros2_ws/src/chasebot_description/worlds/autonomous_golf_ball_world.world
" &
```

**Expected Output:**
- Gazebo GUI opens showing world with green golf ball
- Console shows "Gazebo multi-robot simulator" messages
- ALSA audio warnings are normal and can be ignored

**Wait:** 10 seconds for Gazebo to fully initialize

#### 5.2 Spawn Golf Balls (CRITICAL STEP)
```bash
# Copy golf ball SDF file and spawn all 3 golf balls manually
wsl -d Ubuntu-22.04 bash -c "
    cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/green_golf_ball.sdf ~/ros2_ws/
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/green_golf_ball.sdf -entity golf_ball_1 -x 1.0 -y 0.0 -z 0.025
    ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/green_golf_ball.sdf -entity golf_ball_2 -x 2.5 -y 1.0 -z 0.025
    ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/green_golf_ball.sdf -entity golf_ball_3 -x 1.5 -y -1.5 -z 0.025
"
```

**Expected Output:**
```
SpawnEntity: Successfully spawned entity [golf_ball_1]
SpawnEntity: Successfully spawned entity [golf_ball_2]
SpawnEntity: Successfully spawned entity [golf_ball_3]
```

**Critical Note**: The world file golf balls do NOT spawn automatically. Manual spawning is required.

**Wait:** 2 seconds for golf balls to settle

#### 5.3 Spawn JetBot Robot
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/src/chasebot_description/urdf/ros2_jetbot.urdf -entity jetbot -x 0 -y 0 -z 0.1
"
```

**Expected Output:**
```
SpawnEntity: Successfully spawned entity [jetbot]
Publishing camera info to [/camera/camera_info]
Subscribed to [/cmd_vel]
Advertise odometry on [/odom]
Publishing odom transforms between [odom] and [base_link]
```

**Wait:** 3 seconds for robot controllers to initialize

#### 5.3 Launch Nav2 Navigation Stack
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 launch nav2_bringup navigation_launch.py params_file:=/home/macro2/ros2_ws/src/chasebot_description/nav2_params_simple.yaml use_sim_time:=true
" &
```

**Expected Output:**
```
Creating bond (waitForServer)
Managed nodes are active
Nav2 is active. Lifecycle node bringup complete
```

**Wait:** 8 seconds for Nav2 stack to fully initialize

#### 5.4 Start Vision to LaserScan Converter
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    python3 ~/ros2_ws/src/chasebot_description/scripts/ros2_vision_to_laserscan_hsv.py
" &
```

**Expected Output:**
```
Vision to LaserScan HSV node initialized
HSV range: [[35 50 50]] to [[ 85 255 255]]
Scanning at 50.0% of image height
```

**Wait:** 3 seconds for vision processing to start

#### 5.5 Start Ball to Nav Goal Converter
```bash
wsl -d Ubuntu-22.04 bash -c "
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    python3 ~/ros2_ws/src/chasebot_description/scripts/ros2_ball_to_nav_goal.py
" &
```

**Expected Behavior:**
- Robot begins detecting green golf ball
- Navigation goals sent to Nav2 stack
- Robot autonomously moves toward ball

## Success Criteria

### Visual Confirmation (Gazebo GUI)
- ✅ Gazebo window opens and remains stable
- ✅ Green golf ball visible in the world
- ✅ Blue JetBot robot spawned at origin
- ✅ Robot rotates to face the ball
- ✅ Robot moves autonomously toward the ball
- ✅ Path planning visible (if Nav2 visualization enabled)

### Console Output Validation
- ✅ No "Unable to create CameraSensor" errors
- ✅ Camera info publishing successfully
- ✅ Nav2 stack reports "Managed nodes are active"
- ✅ Vision processing detects ball coordinates
- ✅ Navigation goals being published
- ✅ Robot movement commands sent to `/cmd_vel`

### Technical Architecture Validated
- ✅ **Simulation Layer**: Gazebo + ROS 2 integration
- ✅ **Robot Layer**: JetBot URDF with sensors
- ✅ **Navigation Layer**: Nav2 with path planning
- ✅ **Vision Layer**: HSV detection → LaserScan conversion
- ✅ **Integration Layer**: Ball detection → Nav2 goals

## Troubleshooting

### GUI Issues
**Problem**: Gazebo doesn't open
**Solution**: 
1. Verify VcXsrv is running: Check system tray
2. Test X11: `wsl -d Ubuntu-22.04 bash -c "DISPLAY=\$(ip route show default | awk '{print \$3}'):0 && xset q"`
3. Check Windows Firewall: Allow VcXsrv

### Process Management Issues
**Problem**: "Address already in use" errors
**Solution**: Use PID-based cleanup:
```bash
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep"
# Then kill specific PIDs: kill -9 [PID1] [PID2] [PID3]
```

### Package Installation Issues
**Problem**: "libexec directory does not exist"
**Solution**: 
1. Sync files from Windows: `cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/...`
2. Rebuild workspace: `colcon build --packages-select chasebot_description`
3. Use manual component launching instead of launch files

### Robot Not Moving
**Problem**: Robot doesn't approach ball
**Check**:
1. Vision detection: `ros2 topic echo /ball_detected`
2. Navigation goals: `ros2 topic echo /goal_pose` 
3. Movement commands: `ros2 topic echo /cmd_vel`
4. Nav2 status: Look for "Managed nodes are active"

## Key Insights

### Why Manual Component Launching Works
1. **Bypasses Package Installation Issues**: Direct script execution avoids CMakeLists.txt dependencies
2. **Proper Timing**: Controlled delays between component startup
3. **Clean Process Management**: PID-based cleanup prevents conflicts
4. **Environment Isolation**: Each component gets fresh environment setup

### Why Automated Launch Files Fail
1. **Package Installation Dependencies**: Scripts not properly installed in libexec
2. **Timing Issues**: Components start too quickly without proper delays
3. **Environment Variables**: Display variables not propagated correctly

### Critical Success Factors
1. **VcXsrv Must Be Running**: GUI absolutely requires Windows X server
2. **File Synchronization**: Latest files must be copied from Windows to WSL2
3. **Workspace Rebuild**: `colcon build` required after file changes
4. **PID-Based Cleanup**: Generic `pkill` commands are unreliable
5. **Sequential Launching**: Proper delays between components essential

## Architecture Overview

```
Windows (Development) → WSL2 (Execution)
    ↓
File Sync → Workspace Rebuild → Component Launch
    ↓
Gazebo (GUI) → Robot Spawn → Nav2 Stack → Vision Processing
    ↓
Autonomous Ball Following with Professional Path Planning
```

This procedure represents a working, validated approach to ChaseBot autonomous navigation. The success has been confirmed through multiple UAT sessions and should be the standard approach for demonstration and development.
