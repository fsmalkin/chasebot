# Slice 3: YOLO Detection Regression Investigation

## Issue Summary
YOLO detection that previously worked with green balls on plain backgrounds is now failing to detect any balls in simulation, despite multiple attempts to improve detection conditions.

## Test Configuration

### Environment
- **Simulation**: Ignition Gazebo with D415 camera
- **Camera**: 640x480 @ ~18Hz, working correctly
- **YOLO Model**: yolov8m.pt (pre-trained)
- **Confidence Threshold**: Lowered to 0.01 (from default 0.25)

### Test Scenarios Attempted

#### 1. Multi-colored balls (original test)
- **World**: `yolo_test_world_v2_colored.world`
- **Setup**: Red, blue, yellow, green balls at 1m distance
- **Result**: 0 detections

#### 2. White ball with contrasting background
- **World**: `yolo_test_world_v4_white_forward.world`
- **Setup**: 
  - White ball forward (1m distance)
  - Green grass ground
  - Blue sky background
  - Larger ball size (0.05m radius)
- **Result**: 0 detections

### Files Used

#### Launch File
- `jetbot_gz_control_camera_test_v3.launch.py`
- Based on working v2 launch file
- Uses SDF model `jetbot_core_ignition_v1.3.0.sdf`

#### Detection Scripts
- `ros2_yolo_detector.py` - Main YOLO detection node
- `monitor_yolo_detections.py` - Detection monitoring
- `analyze_yolo_raw_detections.py` - Raw detection analysis

#### World Files
- `yolo_test_world_v2_colored.world` - Multi-colored balls
- `yolo_test_world_v4_white_forward.world` - White ball with green/blue background

## Key Observations

### What's Working
- ✅ Camera feed active and publishing at 640x480
- ✅ YOLO model loads successfully
- ✅ ROS topics properly connected
- ✅ Image data flowing through pipeline
- ✅ Robot spawning and control working

### What's Not Working
- ❌ Zero detections despite clear ball visibility
- ❌ No detections even with 0.01 confidence threshold
- ❌ Multiple ball colors and backgrounds all fail

## Regression Analysis

### 🔴 IMPORTANT: Old Working Configuration Found
**The following launch configuration was reported to successfully detect green balls:**
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_description jetbot_with_yolo_clean_fixed.launch.py"
```
- **Package**: `chasebot_description` (not `chasebot_sim`)
- **Launch file**: `jetbot_with_yolo_clean_fixed.launch.py`
- **This configuration detected green balls on plain backgrounds**

### Historical Context
According to user feedback, YOLO previously had "no problem detecting green balls on a plain background" in the older Gazebo setup. This suggests a fundamental change in either:

1. **Image Pipeline**: Something in the image format/encoding between old and new Gazebo
2. **Camera Simulation**: Ignition Gazebo may render images differently
3. **Model Compatibility**: Pre-trained YOLO models may expect different image characteristics
4. **Missing Configuration**: Some critical parameter from the old setup

## Next Steps for Deep Debugging

### 1. Image Analysis
- Save raw camera images from simulation to disk
- Compare with images from working historical setup
- Check image encoding, color space, bit depth

### 2. YOLO Model Investigation
- Test YOLO with saved real-world ball images
- Verify model expects sports ball class (class 32)
- Try different YOLO model versions (yolov8s, yolov8n)

### 3. Historical Comparison
- **PRIORITY**: Analyze `jetbot_with_yolo_clean_fixed.launch.py` from `chasebot_description`
- Compare with current `jetbot_gz_control_camera_test_v3.launch.py`
- Check for differences in:
  - Camera configuration
  - YOLO wrapper/implementation
  - Simulator version (Classic vs Ignition)
  - Image pipeline setup

### 4. Online Research Required
- Ignition Gazebo camera rendering differences
- YOLO compatibility with simulated images
- Known issues with pre-trained models on synthetic data

### 5. Alternative Approaches
- Test with custom-trained YOLO on simulated balls
- Try classical CV detection (color/shape based)
- Use different object detection framework

## Commands for Reference

```bash
# Launch simulation with new world
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py"

# Run YOLO detector
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_sim/scripts/ros2_yolo_detector.py"

# Monitor detections
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/monitor_yolo_detections.py"
```

## Resolution (January 9, 2025)

### Root Cause Discovered: Topic Mismatch
The YOLO detection regression was caused by a topic name change in the v5 configuration:
- **Old Topic**: `/d415/image_raw` (v3/v4 configurations)
- **New Topic**: `/d415/color/image_raw` (v5 configuration with separated sensors)

### The Fix
Pass the correct topic parameter to YOLO detectors:
```bash
python3 ros2_yolo_detector_frisbee.py --ros-args -p input_topic:=/d415/color/image_raw
```

### Why It Failed
- YOLO detectors were still subscribing to `/d415/image_raw`
- v5 configuration separated RGB and depth into different sensors
- RGB data now publishes to `/d415/color/image_raw`
- YOLO was receiving no images, hence zero detections

### Verification
After fixing the topic parameter:
- **Detection Rate**: ~100% for visible balls
- **Confidence**: 0.77 (detecting as "frisbee" class 29)
- **Performance**: Real-time at 18Hz

### Key Lesson
Always verify topic names when upgrading sensor configurations. The v5 separation of RGB and depth sensors fundamentally changed the topic structure, requiring explicit topic parameters for all vision nodes.

## Original Conclusion

This appeared to be a deeper compatibility issue between pre-trained YOLO models and Ignition Gazebo's image rendering, but was actually a simple topic configuration issue. The detection capability was always there - YOLO just wasn't receiving any images due to the topic mismatch.

**Lesson Learned**: Before investigating complex compatibility issues, always verify basic connectivity - check that data is actually flowing between nodes using the correct topic names.
