# D415 Camera Integration - Step 1: Camera Link

## Overview
Adding visual camera link to JetBot model without sensor functionality to verify basic integration.

## Implementation Details

### Model Changes
- **File**: `jetbot_core_ignition_v1.1.0.sdf`
- **Changes**: Added D415 camera link with proper dimensions and positioning
- **Position**: 7.5cm forward from center, 10cm up from ground
- **Mass**: 72g (actual D415 weight)
- **Dimensions**: 99mm x 20mm x 23mm (actual D415 size)

### Key Design Decisions
1. **Versioning**: Following standards, incremented to v1.1.0 (minor change)
2. **Joint Type**: Fixed joint to base_link
3. **Visual**: Black box to represent camera
4. **No Sensor**: This step only adds visual representation

## Test Procedure

### 1. Sync Files to WSL2
```powershell
# Sync the new model
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/jetbot_core_ignition_v1.1.0.sdf ~/ros2_ws/src/chasebot_sim/ros2_config/urdf/'"

# Sync the launch file
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_camera_step1_test.launch.py ~/ros2_ws/src/chasebot_sim/ros2_config/launch/'"

# Build workspace
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_sim'"
```

### 2. Launch Test
```bash
# Launch with camera link
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib && ros2 launch chasebot_sim jetbot_camera_step1_test.launch.py"
```

### 3. Verify Topics
```bash
# In separate terminal, check control is still working
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list"

# Test movement
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped '{twist: {linear: {x: 0.2}, angular: {z: 0.5}}}'"
```

## Success Criteria
- [ ] Robot spawns successfully in Gazebo
- [ ] Black camera box visible at front of robot
- [ ] Robot still moves correctly with velocity commands
- [ ] No errors in terminal
- [ ] Controllers remain active

## Visual Verification
In Gazebo, you should see:
- Blue robot chassis
- Black camera box at front (above chassis)
- Two gray wheels
- Two caster spheres

## Next Steps
Once this UAT passes:
1. Add basic camera sensor (Step 2)
2. Verify image topic publishing
3. Progress to RGBD sensor for depth

## Troubleshooting
- **Robot doesn't spawn**: Check SDF syntax, especially joint definitions
- **No camera visible**: Verify pose and visual geometry
- **Movement broken**: Ensure controller config path is correct
- **Plugin errors**: Verify IGN_GAZEBO_SYSTEM_PLUGIN_PATH is set

## Related Files
- Model: `ros2_config/urdf/jetbot_core_ignition_v1.1.0.sdf`
- Launch: `ros2_config/launch/jetbot_camera_step1_test.launch.py`
- Previous: `jetbot_core_ignition_v1.0.0.sdf` (working baseline)
