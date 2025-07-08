# ROS2 URDF/SDF Directory

## Overview
This directory contains robot model descriptions in SDF format for Ignition Gazebo simulation.

## CRITICAL: Wheel Axis Fix Status

### ✅ FIXED Files (Use these!)
- **`jetbot_core_ignition_v1.3.0.sdf`** - LATEST VERSION WITH ALL FIXES
  - Wheel axis: Z-axis (0 0 1) ✅ CORRECT
  - D415 camera with sensor plugin ✅
  - gz_ros2_control integration ✅
  
- **`jetbot_core_ignition.sdf`** - Base version with wheel fix
  - Wheel axis: Z-axis (0 0 1) ✅ CORRECT

### ❌ BROKEN Files (Do NOT use)
- **`jetbot_core_ignition_v1.0.0.sdf`** - Wheel axis bug (0 1 0)
- **`jetbot_core_ignition_v1.1.0.sdf`** - Wheel axis bug (0 1 0)  
- **`jetbot_core_ignition_v1.2.0.sdf`** - Wheel axis bug (0 1 0)

## The Wheel Axis Bug

### Problem
When wheel joints use Y-axis (0 1 0), wheels spin like casters instead of rolling forward/backward.

### Solution
Wheel joints must use Z-axis (0 0 1) for proper differential drive:
```xml
<axis>
  <xyz>0 0 1</xyz>  <!-- CORRECT -->
</axis>
```

## Recommended Usage

**Always use `jetbot_core_ignition_v1.3.0.sdf`** - it has:
- ✅ Wheel axis fix (wheels roll properly)
- ✅ D415 camera integration
- ✅ Camera sensor plugin for Ignition
- ✅ gz_ros2_control for motor control

## Launch File Integration

Current launch files using the correct SDF:
- `jetbot_gz_control_camera_test_v3.launch.py` - Uses v1.3.0 ✅

## Version History

- **v1.3.0** (Jan 8, 2025) - FIXED wheel axis from Y to Z
- **v1.2.0** - Added camera sensor (but has wheel bug)
- **v1.1.0** - Added D415 visual (but has wheel bug)
- **v1.0.0** - Initial version (has wheel bug)

## Testing the Fix

After launching with a fixed SDF file, test movement:
```bash
# Forward movement - both wheels should roll forward
ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped '{twist: {linear: {x: 0.5}}}'

# Rotation - left wheel backward, right wheel forward  
ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped '{twist: {angular: {z: 1.0}}}'
```

With the fix, the robot moves properly instead of wheels spinning uselessly.
