# CRITICAL: Wheel Axis Configuration Bug

**Date Discovered**: 2025-07-06  
**Severity**: CRITICAL - Blocks all robot movement  
**Status**: Identified, Fix pending

## Problem Description

When velocity commands are sent to the robot, the wheels spin around the wrong axis, behaving like casters instead of drive wheels. This makes proper differential drive movement impossible.

## Root Cause

In `ros2_config/urdf/jetbot_core_ignition.sdf`, there's a mismatch between wheel orientation and joint rotation axes:

### Current Configuration (BROKEN)
```xml
<!-- Wheel is rotated 90 degrees around X-axis -->
<link name="left_wheel">
  <pose>0 0.08 0.032 1.5708 0 0</pose>  <!-- 1.5708 rad = 90 degrees -->
  ...
</link>

<!-- But joint rotates around Y-axis! -->
<joint name="left_wheel_joint" type="revolute">
  <axis>
    <xyz>0 1 0</xyz>  <!-- WRONG AXIS! -->
  </axis>
</joint>
```

### What's Happening
1. The wheel cylinder is laying on its side (rotated 90° around X)
2. The joint is trying to spin it around the Y-axis
3. Result: Wheel spins like a caster, not rolling forward

### Visual Explanation
```
Current (BROKEN):
  Wheel orientation: ═══ (laying sideways)
  Rotation axis: ↑ (Y-axis)
  Result: Wheel spins around its length

Expected (CORRECT):
  Wheel orientation: ═══ (laying sideways)
  Rotation axis: ⊙ (Z-axis, into page)
  Result: Wheel rolls forward/backward
```

## Required Fix

Change the joint axis definition in both wheel joints:

```xml
<!-- Left Wheel Joint -->
<joint name="left_wheel_joint" type="revolute">
  <parent>base_link</parent>
  <child>left_wheel</child>
  <axis>
    <xyz>0 0 1</xyz>  <!-- Changed from 0 1 0 -->
    <dynamics>
      <damping>0.7</damping>
    </dynamics>
  </axis>
</joint>

<!-- Right Wheel Joint -->
<joint name="right_wheel_joint" type="revolute">
  <parent>base_link</parent>
  <child>right_wheel</child>
  <axis>
    <xyz>0 0 1</xyz>  <!-- Changed from 0 1 0 -->
    <dynamics>
      <damping>0.7</damping>
    </dynamics>
  </axis>
</joint>
```

## Testing the Fix

After applying the fix, use the existing test script:

```bash
# Launch robot with fixed model
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_ros2_control_gui.launch.py"

# Run movement test
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 src/chasebot_sim/ros2_scripts/test_gz_controller_movement.py"
```

Expected behavior after fix:
- Forward command → Both wheels rotate forward
- Rotation command → Left wheel backward, right wheel forward
- Robot moves properly instead of wheels spinning uselessly

## Impact

This bug completely blocks:
- Basic robot movement
- Navigation capabilities
- Autonomous ball following
- Any testing of control systems

## Priority

**HIGHEST PRIORITY** - No other development can proceed until this is fixed.

## Related Files

- `ros2_config/urdf/jetbot_core_ignition.sdf` - File requiring the fix
- `ros2_scripts/test_gz_controller_movement.py` - Test script to validate fix
- `memory-bank/activeContext.md` - Updated to reflect this as top priority
