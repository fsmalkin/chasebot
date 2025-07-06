# Slice 8: gz_ros2_control Controller Plugin Investigation

## Overview
This slice focused on investigating why the gz_ros2_control plugin was unable to find and load the ROS 2 controller plugins (joint_state_broadcaster, diff_drive_controller) within the Ignition Gazebo environment.

## Current Status: BLOCKED ⚠️
- GUI display working ✅
- gz_ros2_control plugin loads and initializes ✅
- Controller manager inside Gazebo cannot find controller plugins ❌
- Controllers fail to spawn with "Loader not found" errors ❌

## Root Cause Analysis

### Issue Discovered
The gz_ros2_control plugin successfully:
1. Loads the URDF with ros2_control tags
2. Initializes the hardware interface
3. Creates a controller_manager instance

However, the controller_manager cannot find the controller plugins:
```
[ERROR] Loader for controller 'joint_state_broadcaster' (type 'joint_state_broadcaster/JointStateBroadcaster') not found.
Available classes:
  controller_manager/test_controller
  controller_manager/test_controller_failed_init
  controller_manager/test_controller_with_interfaces
  diff_drive_controller/DiffDriveController
  controller_manager/test_chainable_controller
```

Note: `diff_drive_controller` appears in the list but `joint_state_broadcaster` does not.

### Environment Verification
All required packages are installed:
```bash
# Verified installed packages:
ros-humble-gz-ros2-control
ros-humble-joint-state-broadcaster
ros-humble-diff-drive-controller
ros-humble-ros2-controllers
```

The plugin libraries exist:
```
/opt/ros/humble/lib/libjoint_state_broadcaster.so
/opt/ros/humble/lib/libdiff_drive_controller.so
```

## Files Created/Modified

### 1. `ros2_config/launch/jetbot_gz_control_simple.launch.py`
Simplified launch file that:
- Removes separate ros2_control_node (let Gazebo handle it)
- Includes ros2_control tags in the URDF
- Uses proven display configuration
- Spawns controllers after delays

### 2. `ros2_scripts/test_minimal_gz_control.py`
Test script to validate controller loading and send velocity commands

### 3. `ros2_config/config/jetbot_diff_drive.yaml`
Controller configuration for diff_drive_controller with proper parameters

## Key Discoveries

1. **Separate controller_manager conflict**: The original launch file was starting a separate `ros2_control_node` which couldn't find the `gz_ros2_control/GazeboSimSystem` plugin
2. **URDF requirements**: The URDF must include ros2_control tags for gz_ros2_control to activate
3. **Plugin path issues**: Despite setting `IGN_GAZEBO_SYSTEM_PLUGIN_PATH`, the controller plugins aren't being found by the Gazebo-internal controller_manager

## Next Steps for Resolution

1. **Investigate plugin loading mechanism**:
   - Check if gz_ros2_control is using a different pluginlib instance
   - Verify if controller plugins need special registration for Ignition Gazebo

2. **Try alternative approaches**:
   - Use the external controller_manager approach with proper hardware interface
   - Check gz_ros2_control examples for working configurations
   - Investigate if there's a specific controller plugin path environment variable

3. **Potential workarounds**:
   - Create a custom controller that's directly linked
   - Use Ignition's native diff_drive system instead of ros2_control
   - Bridge velocity commands directly without ros2_control

## Commands for Testing

```bash
# Launch the system
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib && ros2 launch chasebot_description jetbot_gz_control_simple.launch.py"

# In another terminal, check controller status
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 control list_controllers"

# Try to load controller manually
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 control load_controller jetbot_base_controller"
```

## Related Documentation
- Previous: [Slice 7 - gz_ros2_control Basic Integration](./slice7_gz_ros2_control_uat_complete.md)
- Related: [GUI Display Fix](./slice8_gui_display_fix_uat_complete.md)
- Next: Consider alternative approaches or deeper plugin investigation
