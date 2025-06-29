# ChaseBot ROS 2 Autonomous Ball Following - UAT Steps

**Updated UAT Order of Operations for Nav2 Integration Testing**

## Prerequisites
- WSL2 Ubuntu-22.04 environment with ROS 2 Humble
- GUI environment configured for Gazebo visual feedback
- All processes terminated using PID-based cleanup

## UAT Order of Operations

### Step 1: Start GUI
Launch Gazebo with GUI environment:
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && gazebo ~/ros2_ws/src/chasebot_description/worlds/simple_uat_world.world"
```

**Expected Result:**
- Gazebo GUI window opens
- Empty world with ground plane visible
- No console spam or transform warnings

### Step 2: Spawn Ball
Add green golf ball target to the simulation:
```bash
# (Ball spawning command to be added - requires GUI environment)
```

**Expected Result:**
- Green golf ball appears in the world
- Ball positioned for robot detection and following

### Step 3: Spawn Bot
Launch JetBot robot in the simulation:
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run gazebo_ros spawn_entity.py -entity jetbot -file ~/ros2_ws/src/chasebot_description/urdf/ros2_jetbot.urdf -x 0 -y 0 -z 0.05"
```

**Expected Result:**
- Blue JetBot robot appears in Gazebo
- Robot properly spawned with physics enabled
- Camera sensor functional (requires GUI)

### Step 4: Boot NAV
Start Nav2 navigation stack and autonomous behavior:
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ~/ros2_ws/src/chasebot_description/launch/nav2_complete_uat.launch.py"
```

**Expected Result:**
- Nav2 stack launches without transform cache warnings
- Vision-to-laserscan conversion active
- Ball-to-navigation-goal conversion running
- Robot begins autonomous ball following behavior

## Success Criteria

### ✅ PASS Conditions:
1. **GUI Stability**: Gazebo opens and remains stable
2. **Clean Logging**: No transform cache warning spam
3. **Ball Detection**: HSV color detection identifies green golf ball
4. **Navigation Goals**: Ball position converted to Nav2 navigation targets
5. **Autonomous Movement**: Robot moves toward and approaches golf ball
6. **Visual Confirmation**: All behavior visible in Gazebo GUI

### ❌ FAIL Conditions:
- GUI fails to open or crashes
- Transform cache warnings flood the logs
- Robot doesn't detect or approach the ball
- Navigation stack fails to initialize
- Camera sensor errors prevent vision processing

## Troubleshooting

### Process Management
Always use PID-based cleanup between tests:
```bash
# List processes
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep"

# Kill specific PIDs (replace with actual PIDs)
wsl -d Ubuntu-22.04 bash -c "kill -9 [PID1] [PID2] [PID3]"

# Verify cleanup
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep"
```

### Known Issues
- **"Unable to create CameraSensor"**: Camera requires GUI environment
- **Qt platform plugin errors**: Expected in headless mode, resolved with GUI
- **Transform cache warnings**: Fixed by using 'base_link' frame for laser scans

## Recent Fixes Applied

### Transform Cache Warning Elimination
- **Issue**: Nav2 costmaps generated warnings for every camera frame
- **Root Cause**: LaserScan messages used 'camera_optical_link' frame_id
- **Solution**: Changed frame_id to 'base_link' in ros2_vision_to_laserscan_hsv.py
- **Result**: Clean logs without flooding, preserved functionality

This UAT order ensures proper sequence of GUI → Ball → Bot → Nav for comprehensive autonomous behavior validation.
