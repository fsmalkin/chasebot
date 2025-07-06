# Active Context - ChaseBot Project (2025-07-06)

## 🔴 CRITICAL ISSUE: Wheel Axis Configuration Bug

### Top Priority Problem Discovered
**The robot's wheels are spinning like casters instead of rolling forward!** When movement commands are issued, the wheels rotate around the wrong axis, preventing proper differential drive movement.

### Root Cause Analysis
The issue is in `ros2_config/urdf/jetbot_core_ignition.sdf`:
1. **Wheel Orientation**: Wheels are rotated 90 degrees (1.5708 radians) around X-axis
   - Left wheel: `<pose>0 0.08 0.032 1.5708 0 0</pose>`
   - Right wheel: `<pose>0 -0.08 0.032 1.5708 0 0</pose>`
2. **Joint Axis Mismatch**: Joints rotate around Y-axis `<axis><xyz>0 1 0</xyz></axis>`
3. **Result**: Wheels spin around their length instead of rolling forward

### Required Fix
Change wheel joint axes from `<xyz>0 1 0</xyz>` to `<xyz>0 0 1</xyz>` in both:
- `left_wheel_joint`
- `right_wheel_joint`

### Impact
- **BLOCKS**: All movement and navigation capabilities
- **AFFECTS**: Entire autonomous ball following system
- **PRIORITY**: Must be fixed before any other development

---

## Previous Status: gz_ros2_control Working (But Movement Broken)

### What Was Achieved
- gz_ros2_control plugin loads successfully
- Controllers activate and accept commands
- Robot receives velocity commands via `TwistStamped`

### What's Actually Broken
- Wheels rotate around wrong axis (caster-like behavior)
- Robot cannot move forward/backward properly
- Differential drive kinematics impossible with current configuration

## Environment Status
- ROS 2 Humble on Ubuntu 22.04 (WSL2)
- Ignition Gazebo Fortress (version 6.17.0)
- Display working: `export DISPLAY=172.25.128.1:0.0`
- Package name: `chasebot_sim`

## Next Steps After Wheel Fix
1. **Immediate**: Fix wheel joint axes in SDF model
2. **Validate**: Test proper forward/backward movement
3. **Then**: Resume camera integration for vision system

## Technical Context
The robot model was migrated from classic Gazebo to Ignition, but the wheel joint axes weren't properly adjusted for the wheel orientation. This fundamental mechanical issue must be resolved before any control or navigation work can proceed.

## Files Requiring Update
- `ros2_config/urdf/jetbot_core_ignition.sdf` - Fix wheel joint axes
- Create versioned backup of current SDF before modification
- Update test scripts to validate proper wheel rotation
