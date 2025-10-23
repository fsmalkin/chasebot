# Slice 3 UAT: Basic Gazebo + Robot Spawn + Static Transforms + YOLO Detection

## Overview
This is the third thin slice in our iterative launch file development. It builds on Slice 2 by adding YOLO-based golf ball detection with visual feedback.

## Purpose
- Maintain all Slice 1 & 2 functionality
- Add YOLO-based object detection for golf balls
- Display camera view with bounding boxes
- Publish detection data to ROS topics

## What's New in Slice 3
- **YOLO Detection Node**: YOLOv8 model for sports ball detection
- **Golf Ball in World**: Green golf ball at position (2.0, 1.0, 0.02)
- **Debug Visualization**: OpenCV window showing camera feed with bounding boxes
- **Detection Topics**: 
  - `/yolo/ball_position` - Normalized ball position
  - `/yolo/confidence` - Detection confidence
  - `/yolo/debug_image` - Annotated camera image

## Launch Command
```bash
# From Windows (with VcXsrv running)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_yolo.launch.py"
```

## UAT Success Criteria

### ✅ Foundation Checks (From Slices 1 & 2)
1. **Gazebo Opens**: Window appears showing simulation world
2. **Robot Spawns**: JetBot appears at origin (0,0,0.05)
3. **Golf Ball Visible**: Green golf ball visible at position (2.0, 1.0)
4. **Transforms Working**: No transform errors in console

### 🎯 Slice 3 Specific - YOLO Detection
1. **YOLO Loads Successfully**:
   - Look for: "Loading YOLO model from: /home/*/ros2_ws/yolov8m.pt"
   - Look for: "YOLO model loaded successfully"
   - Look for: "YOLO detection node started"

2. **Detection Window Opens**:
   - OpenCV window titled "YOLO Golf Ball Detection" appears
   - Shows camera view from robot's perspective
   - Golf ball visible in camera frame

3. **Bounding Box Display**:
   - Green rectangle drawn around detected golf ball
   - Confidence score displayed above box (should be >60%)
   - Example: "Golf Ball: 0.85"

4. **Console Detection Logs**:
   ```
   [yolo_detector-X] [INFO] Golf ball detected! Confidence: 0.85, Center: (320, 240)
   ```

5. **ROS Topics Publishing**:
   ```bash
   # Check detection position
   wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /yolo/ball_position --once"
   
   # Check confidence
   wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /yolo/confidence --once"
   ```

## Auto-Shutdown Features
- **5-minute timer**: Automatic cleanup after UAT
- **User controls**:
  - `Enter`: Confirm UAT success, shutdown immediately
  - `e` + `Enter`: Extend timer by 5 minutes
  - `q` + `Enter`: Quit immediately
- **Clean termination**: All processes properly killed

## What This Slice Does NOT Include
- ❌ Nav2 stack
- ❌ Autonomous navigation to ball
- ❌ Multiple ball detection
- ❌ Real ball pickup behavior

## Common Issues

### Issue: "No module named 'ultralytics'"
**Solution**: Install YOLO dependencies
```bash
wsl -d Ubuntu-22.04 bash -c "pip3 install ultralytics opencv-python torch torchvision"
```

### Issue: "Failed to load YOLO model"
**Solution**: Ensure yolov8m.pt exists in workspace
```bash
# Copy from Windows to WSL
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/"
```

### Issue: OpenCV window doesn't appear
**Solution**: Check display configuration
```bash
# Test X11 forwarding
wsl -d Ubuntu-22.04 bash -c "echo $DISPLAY && xclock"
```

### Issue: No detections (0% confidence)
**Solution**: 
- Verify golf ball is in camera view (adjust robot position if needed)
- Check lighting in simulation (sun angle affects detection)
- Ensure camera sensor is properly configured in URDF

## Success Indicators
✅ Robot and golf ball spawn correctly
✅ YOLO model loads without errors
✅ OpenCV window shows camera feed
✅ Green bounding box appears around golf ball
✅ Console shows detection confidence >60%
✅ ROS topics publish detection data

## Next Steps
Once this UAT passes:
- **Slice 4**: Add Nav2 minimal with manual goal testing
- **Slice 5**: Add bridge script to connect YOLO detections to Nav2 goals

## Key Improvements from Slice 2
- Real-time object detection with industry-standard YOLO
- Visual feedback through debug window
- Professional detection data publishing
- Foundation for vision-based navigation
