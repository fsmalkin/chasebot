# ChaseBot Active Context

## Current Focus (Jan 2025)
Successfully restored gz_ros2_control functionality with proper differential drive control.

### Latest Achievement
- **Date**: 2025-01-06
- **Status**: gz_ros2_control fully operational
- **Key Fix**: Set IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib environment variable
- **Result**: Robot responds correctly to velocity commands with proper kinematics

### Working Configuration
- **Launch File**: jetbot_gz_control_v3.0.0.launch.py
- **Controllers**: 
  - joint_state_broadcaster (active)
  - jetbot_base_controller (active)
- **Command Topic**: /jetbot_base_controller/cmd_vel
- **Message Type**: geometry_msgs/msg/TwistStamped (NOT Twist)

### Critical Commands
```bash
# Launch with working configuration
export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib
ros2 launch chasebot_sim jetbot_gz_control_v3.0.0.launch.py

# Send velocity commands
ros2 topic pub /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped '{twist: {linear: {x: 0.2}, angular: {z: 0.0}}}'
```

## Next Steps
1. Integrate D415 camera into robot model
2. Set up 3D vision with yolov8_ros package
3. Implement depth-based ball following using direct 3D coordinates
4. Test Nav2 integration with working control system

## Technical Context
- **Platform**: ROS 2 Humble on Ubuntu 22.04 (WSL2)
- **Simulation**: Ignition Gazebo (Fortress)
- **Control**: gz_ros2_control with diff_drive_controller
- **Vision Goal**: Use D415 depth camera for 3D object detection

## Recent Changes
- Restored working gz_ros2_control configuration
- Verified differential drive kinematics
- Confirmed visual wheel rotation is correct
- Environment variable IGN_GAZEBO_SYSTEM_PLUGIN_PATH is critical
