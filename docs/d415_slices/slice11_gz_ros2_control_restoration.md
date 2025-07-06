# Slice 11: gz_ros2_control Restoration

## Objective
Restore the working gz_ros2_control functionality that was operational the previous night but failing to load.

## Background
The gz_ros2_control plugin was failing with "couldn't find shared library" error, preventing the differential drive controller from working.

## Solution
The critical fix was setting the `IGN_GAZEBO_SYSTEM_PLUGIN_PATH` environment variable to `/opt/ros/humble/lib`.

## Implementation

### Working Launch Command
```bash
export DISPLAY=172.25.128.1:0.0
export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib
ros2 launch chasebot_sim jetbot_gz_control_v3.0.0.launch.py
```

### Key Configuration Files
- **Launch File**: `jetbot_gz_control_v3.0.0.launch.py`
- **Controller Config**: `jetbot_diff_drive_v1.0.0.yaml`
- **Robot Model**: Uses minimal URDF with ros2_control tags

### Velocity Commands
```bash
# Must use TwistStamped (not Twist)
ros2 topic pub /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped \
  '{twist: {linear: {x: 0.2}, angular: {z: 0.0}}}'
```

## Test Results

### Controller Test Output
```
[INFO] Starting controller movement test...
[INFO] Testing forward movement (0.2 m/s for 2 seconds)...
[INFO] Forward test - Left wheel delta: 8.531 rad, Right wheel delta: 8.531 rad
[INFO] ✓ Forward movement test PASSED
[INFO] Testing rotation movement (0.5 rad/s for 2 seconds)...
[INFO] Rotation test - Left wheel delta: -1.019 rad, Right wheel delta: 2.331 rad
[INFO] ✓ Rotation movement test PASSED
[INFO] ✓ ALL TESTS PASSED - gz_ros2_control is working correctly!
```

### Visual Confirmation
- Robot moves forward with both wheels rotating equally
- Robot rotates with proper differential drive behavior
- Wheels visually rotate correctly (not spinning sideways)

## Key Insights

1. **Environment Variable Critical**: The `IGN_GAZEBO_SYSTEM_PLUGIN_PATH` must be set for gz_ros2_control to load
2. **Message Type**: Controller expects `TwistStamped`, not `Twist`
3. **Launch Configuration**: The v3.0.0 launch file includes all necessary components
4. **Visual Validation**: Wheels rotate properly around correct axis

## Next Steps
With the control system fully operational, we can proceed to:
1. Integrate D415 depth camera into robot model
2. Set up 3D vision pipeline with yolov8_ros
3. Implement depth-based ball following
4. Connect to Nav2 for advanced navigation

## Status: ✅ COMPLETE
The gz_ros2_control system is fully restored and operational. The robot responds correctly to velocity commands with proper differential drive kinematics.
