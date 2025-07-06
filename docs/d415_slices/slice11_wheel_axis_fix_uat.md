# Slice 11: Wheel Axis Fix UAT

**Date**: 2025-07-06  
**Status**: Fixed, Ready for UAT  
**Priority**: CRITICAL - Blocks all movement

## Issue Summary
Wheels were spinning around the wrong axis (like casters) due to joint axis mismatch with wheel orientation in Ignition Gazebo.

## Fix Applied
Changed wheel joint axes from Y-axis `<xyz>0 1 0</xyz>` to Z-axis `<xyz>0 0 1</xyz>` in both:
- `left_wheel_joint`
- `right_wheel_joint`

## Files Modified
- `ros2_config/urdf/jetbot_core_ignition.sdf` - Fixed wheel joint axes
- `ros2_config/urdf/jetbot_core_ignition_v1.0.0.sdf` - Backup of broken version

## UAT Test Procedure

### Prerequisites
- Ensure display is configured: `export DISPLAY=172.25.128.1:0.0`
- Kill any existing Gazebo processes

### Launch Robot
```bash
# Launch with GUI
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_ros2_control_gui.launch.py"
```

### Test Movement
In a separate terminal:
```bash
# Run movement test script
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 src/chasebot_sim/ros2_scripts/test_gz_controller_movement.py"
```

## Expected Results

### Before Fix (Broken)
- Wheels spin around their length (like casters)
- Robot cannot move forward/backward
- Robot spins in place when trying to move

### After Fix (Working)
- Forward command → Both wheels rotate forward around Z-axis
- Robot moves forward in a straight line
- Rotation command → Differential drive works correctly
- Robot can navigate properly

## Visual Indicators
Watch for:
1. **Wheel Rotation**: Should roll forward/backward, not spin sideways
2. **Robot Movement**: Should translate forward/backward smoothly
3. **Turning**: Should execute proper differential drive turns

## Success Criteria
- [ ] Wheels rotate correctly around Z-axis (rolling motion)
- [ ] Robot moves forward when commanded
- [ ] Robot rotates properly with differential drive
- [ ] No caster-like spinning behavior

## Rollback Instructions
If issues occur:
```bash
# Restore original broken version
cp ros2_config/urdf/jetbot_core_ignition_v1.0.0.sdf ros2_config/urdf/jetbot_core_ignition.sdf
```

## Next Steps After UAT Success
1. Add camera sensor for vision capabilities
2. Test object detection with fixed movement
3. Implement autonomous ball following
