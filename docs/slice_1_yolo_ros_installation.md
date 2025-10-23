# Slice 1: yolo_ros Package Installation

## Objective
Install and validate mgonzs13/yolo_ros package for 3D object detection

## Prerequisites
- ROS 2 Humble environment ready
- Python 3.8+ installed
- Git configured

## Installation Steps

### 1. Clone the Repository
```bash
# From Windows PowerShell
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws/src && git clone https://github.com/mgonzs13/yolo_ros.git'"
```

### 2. Install Python Dependencies
```bash
# Install required Python packages
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws/src/yolo_ros && pip3 install -r requirements.txt'"
```

### 3. Build the Package
```bash
# Build yolo_ros and its dependencies
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select yolo_msgs yolo_ros yolo_bringup'"
```

### 4. Copy Our Existing YOLO Model
```bash
# We already have yolov8m.pt, copy it to the right location
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/'"
```

## Validation Commands

### Test 1: Basic Launch
```bash
# Launch yolo_ros with default settings
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch yolo_bringup yolo.launch.py'"
```

**Expected**: Node starts and waits for images (will show "waiting for images" or similar)

### Test 2: Check Topics
```bash
# In another terminal, check available topics
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'source /opt/ros/humble/setup.bash && ros2 topic list | grep yolo'"
```

**Expected Output**:
```
/yolo/detections
/yolo/tracking
/yolo/debug_image
```

### Test 3: Node Info
```bash
# Check node is running
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'source /opt/ros/humble/setup.bash && ros2 node list | grep yolo'"
```

## UAT Criteria
- [ ] Package builds without errors
- [ ] `ros2 launch yolo_bringup yolo.launch.py` starts successfully
- [ ] YOLO topics are visible
- [ ] No Python import errors
- [ ] Node waits for image input (expected behavior without camera)

## Troubleshooting

### Common Issues

1. **ultralytics not found**
   ```bash
   pip3 install ultralytics
   ```

2. **Build errors**
   - Check Python version: `python3 --version` (should be 3.8+)
   - Ensure all dependencies installed: `rosdep install --from-paths src --ignore-src -r -y`

3. **Model not found**
   - Verify model path in launch file
   - Ensure yolov8m.pt is accessible

## Next Steps
Once this slice passes UAT:
- Proceed to Slice 2: Connect to D415 Camera
- Do NOT modify any configurations yet
- Keep using default launch parameters

## Notes
- The package supports lifecycle nodes (efficient resource usage)
- Default model is YOLOv8
- GPU support available but we'll start with CPU
- Package is actively maintained (important for long-term support)
