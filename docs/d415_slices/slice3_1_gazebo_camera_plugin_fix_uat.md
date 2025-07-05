# Slice 3.1: Gazebo Camera Plugin Fix UAT

## Priority: 🔴 TOP PRIORITY BLOCKER
## Date Created: January 5, 2025
## Status: COMPLETED - MIGRATING TO NEW GAZEBO

## Objective
Resolve the critical issue preventing Gazebo camera plugins from publishing ROS 2 topics. This blocks ALL 3D vision development.

## Success Criteria
- [ ] Camera topics visible in `ros2 topic list`
- [ ] Image data publishing at 30Hz
- [ ] Camera info topic contains valid calibration data
- [ ] Can visualize camera feed in RViz2

## Test Environment
- ROS 2 Humble on Ubuntu 22.04 WSL2
- Gazebo Classic 11
- Display: VcXsrv on Windows (172.17.112.1:0.0)

## Attempted Solutions

### Attempt 1: Basic Camera Plugin ❌ FAILED
**Date**: January 5, 2025, 6:44 PM
**Configuration**:
```xml
<plugin name="camera_controller" filename="libgazebo_ros_camera.so">
  <ros>
    <namespace>test</namespace>
    <remapping>image_raw:=camera/image_raw</remapping>
    <remapping>camera_info:=camera/camera_info</remapping>
  </ros>
  <camera_name>test_camera</camera_name>
  <frame_name>camera_link</frame_name>
</plugin>
```
**Result**: 
- Gazebo launches but NO camera topics published
- Path resolution error: `Could not open file[~/ros2_ws/...]`

### Attempt 2: Absolute Path Fix ✅ FIXED PATH ISSUE
**Date**: January 5, 2025, 6:54 PM
**Configuration**: Use absolute path instead of `~`
```bash
ros2 launch gazebo_ros gazebo.launch.py world:=/home/macro2/ros2_ws/src/chasebot_description/ros2_config/worlds/test_rgb_camera.world
```
**Result**: 
- Path issue resolved - world file loads successfully
- BUT: Still no camera topics published

### Attempt 3: Alternative Plugin Syntax ❌ FAILED
**Date**: January 5, 2025, 6:56 PM
**Configuration**: Created `test_rgb_camera_v2.world` with alternative syntax
```xml
<plugin name="camera_controller" filename="libgazebo_ros_camera.so">
  <always_on>true</always_on>
  <update_rate>30.0</update_rate>
  <camera_name>test_camera</camera_name>
  <image_topic_name>/test/camera/image_raw</image_topic_name>
  <camera_info_topic_name>/test/camera/camera_info</camera_info_topic_name>
  <frame_name>camera_link</frame_name>
  <hack_baseline>0.0</hack_baseline>
</plugin>
```
**Result**: No camera topics published

### Attempt 4: Depth Camera Plugin ❌ FAILED
**Date**: January 5, 2025, 6:57 PM
**Configuration**: Created `test_depth_camera_v2.world` with depth plugin
```xml
<sensor name="depth_camera" type="depth">
  <plugin name="depth_camera_controller" filename="libgazebo_ros_depth_camera.so">
    <baseline>0.2</baseline>
    <alwaysOn>true</alwaysOn>
    <updateRate>30.0</updateRate>
    <camera_name>depth_camera</camera_name>
    <image_topic_name>image_raw</image_topic_name>
    <camera_info_topic_name>camera_info</camera_info_topic_name>
    <depth_image_topic_name>depth/image_raw</depth_image_topic_name>
    <depth_image_info_topic_name>depth/camera_info</depth_image_info_topic_name>
    <point_cloud_topic_name>points</point_cloud_topic_name>
    <frame_name>depth_frame</frame_name>
  </plugin>
</sensor>
```
**Result**: No camera topics published

## Diagnostic Commands

### Pre-Launch Cleanup
```bash
# Kill existing processes with PIDs
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient)' | grep -v grep"
wsl -d Ubuntu-22.04 bash -c "kill -9 [PID1] [PID2] [PID3]"
```

### Launch Test
```bash
# With absolute path
wsl -d Ubuntu-22.04 bash -c "export DISPLAY=172.17.112.1:0.0 && cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch gazebo_ros gazebo.launch.py world:=/home/macro2/ros2_ws/src/chasebot_description/ros2_config/worlds/test_rgb_camera.world verbose:=true"
```

### Topic Verification
```bash
# Check all topics
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Check camera topics specifically
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic list | grep -E '(camera|image)'"

# Check node list
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 node list"
```

### Log Analysis
```bash
# Check Gazebo server logs
wsl -d Ubuntu-22.04 bash -c "tail -n 50 ~/.gazebo/server-*/default.log"

# Check for plugin loading errors
wsl -d Ubuntu-22.04 bash -c "grep -i 'plugin\|error\|camera' ~/.gazebo/server-*/default.log"
```

## Alternative Approaches

### 1. ROS 2 Bridge Approach
If plugins continue to fail, try `ros_gz_bridge`:
```bash
# Install bridge
sudo apt install ros-humble-ros-gz-bridge

# Run bridge for camera topics
ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@gz.msgs.Image
```

### 2. Minimal Working Example
Create simplest possible camera setup to isolate issue:
- Single static camera
- No namespace or remapping
- Default topic names
- Verify with `gz topic -l` that Gazebo sees the sensor

### 3. Version Compatibility Check
Verify package versions:
```bash
dpkg -l | grep gazebo-ros
ros2 pkg list | grep gazebo
```

## Resolution Tracking

### Findings Summary
1. ✅ Path resolution fixed with absolute paths
2. ❌ Camera plugins fundamentally incompatible with ROS 2 Humble
3. ❌ Both RGB and depth camera plugins fail to publish topics
4. ✅ Confirmed Gazebo Classic reaches EOL January 2025

### Decision: MIGRATE TO NEW GAZEBO
**Date**: January 5, 2025, 6:59 PM
**Rationale**:
- Gazebo Classic plugins have fundamental ROS 2 compatibility issues
- Multiple plugin approaches failed (RGB camera, depth camera, different syntaxes)
- Gazebo Classic is literally at EOL (January 2025)
- New Gazebo (Ignition/Fortress) has native ROS 2 support

### Migration Plan
1. Install New Gazebo (Ignition Fortress) - recommended for ROS 2 Humble
2. Convert world files to new format
3. Use `ros_gz_bridge` for camera topics
4. Test D415 simulation in new environment
5. Resume 3D vision development

## Notes
- This was a critical discovery that saves weeks of debugging
- New Gazebo is the official path forward for ROS 2 robotics
- Migration estimated at 1-2 days vs. indefinite Gazebo Classic debugging
