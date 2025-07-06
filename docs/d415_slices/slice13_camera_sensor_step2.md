# D415 Camera Integration - Step 2: Basic RGB Camera Sensor

## Overview
Adding basic RGB camera sensor to the D415 camera link to start capturing images.

## Implementation Details

### Model Changes
- **File**: `jetbot_core_ignition_v1.2.0.sdf`
- **Changes**: Added camera sensor element to d415_camera_link
- **Sensor Type**: Basic camera (RGB only, no depth yet)
- **Configuration**:
  - Update rate: 30Hz
  - Resolution: 640x480
  - FOV: 1.211 radians (69.4 degrees)
  - Topic: `/d415/image_raw`

### Key Design Decisions
1. **Versioning**: v1.1.0 → v1.2.0 (minor feature addition)
2. **Sensor Name**: `d415_rgb` to distinguish from future depth sensor
3. **Noise Model**: Added Gaussian noise for realism
4. **Visualization**: Enabled for debugging

## Test Procedure

### 1. Sync Files to WSL2
```powershell
# Sync the new model
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/jetbot_core_ignition_v1.2.0.sdf ~/ros2_ws/src/chasebot_sim/ros2_config/urdf/'"

# Sync the updated launch file
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_gz_control_camera_test.launch.py ~/ros2_ws/src/chasebot_sim/ros2_config/launch/'"

# Build workspace
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_sim'"
```

### 2. Launch Test
```bash
# Launch with camera sensor
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib && ros2 launch chasebot_sim jetbot_gz_control_camera_test.launch.py"
```

### 3. Verify Camera Topics
```bash
# In separate terminal, check camera topics
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list | grep d415"

# Check image publishing rate
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic hz /d415/image_raw"

# Echo camera info
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /d415/camera_info --once"
```

### 4. Test Camera Data
```bash
# Save a sample image
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /d415/image_raw --once > camera_test.txt"
```

## Success Criteria
- [ ] Robot spawns successfully with camera sensor
- [ ] `/d415/image_raw` topic appears in topic list
- [ ] `/d415/camera_info` topic appears in topic list
- [ ] Image topic publishes at ~30Hz
- [ ] Camera info contains proper intrinsics
- [ ] No errors related to camera sensor

## Expected Topics
After successful launch:
- `/d415/image_raw` - Raw RGB image (sensor_msgs/Image)
- `/d415/camera_info` - Camera calibration (sensor_msgs/CameraInfo)

## Troubleshooting
- **No camera topics**: Check sensor definition in SDF
- **Bridge errors**: Verify topic names in launch file match SDF
- **Low frame rate**: Reduce resolution or update rate
- **Black images**: Check camera pose and world lighting

## Next Steps
Once this UAT passes:
1. Visualize RGB in RViz2 (Step 3)
2. Upgrade to RGBD sensor for depth (Step 4)
3. Test depth measurements

## Related Files
- Model: `ros2_config/urdf/jetbot_core_ignition_v1.2.0.sdf`
- Launch: `ros2_config/launch/jetbot_gz_control_camera_test.launch.py`
- Previous: `jetbot_core_ignition_v1.1.0.sdf` (camera link only)
