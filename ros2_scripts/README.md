# ROS2 Scripts Directory

## Overview
This directory contains all ROS2 Python scripts for the ChaseBot project, including vision processing, robot control, navigation utilities, and testing tools.

## File Inventory

### ✅ Active Vision Scripts

#### **ros2_yolo_detector_fixed.py** 
- **Purpose**: Fixed YOLO object detection node with correct camera topic subscription
- **Status**: ACTIVE - Primary detection node
- **Key Fix**: Subscribes to `/d415/image_raw` instead of `/camera/image_raw`
- **Dependencies**: ROS2 Humble, OpenCV, ultralytics (YOLO), cv_bridge
- **Usage**: `python3 ros2_yolo_detector_fixed.py`
- **Notes**: Detects objects but classifies balls as "frisbee" (class 29)

#### **test_camera_topic.py**
- **Purpose**: Diagnostic tool to verify camera topics and message rates
- **Status**: ACTIVE - Essential debugging tool
- **Dependencies**: ROS2 Humble
- **Usage**: `python3 test_camera_topic.py`
- **Output**: Shows message counts for both `/d415/image_raw` and `/camera/image_raw`

#### **monitor_yolo_detections.py**
- **Purpose**: Monitor YOLO detection output in real-time
- **Status**: ACTIVE
- **Dependencies**: ROS2 Humble
- **Topics**: Subscribes to `/yolo/detections`

#### **analyze_yolo_raw_detections.py**
- **Purpose**: Detailed analysis of YOLO raw detection data
- **Status**: ACTIVE
- **Dependencies**: ROS2 Humble

### ❌ Deprecated Vision Scripts

#### **ros2_yolo_detector.py**
- **Purpose**: Original YOLO detector (BROKEN - wrong topic)
- **Status**: DEPRECATED
- **Issue**: Subscribes to wrong topic `/camera/image_raw`
- **Replaced by**: `ros2_yolo_detector_fixed.py`

#### **ros2_yolo_detector_quiet.py** / **ros2_yolo_detector_silent.py**
- **Purpose**: Variants with reduced logging
- **Status**: DEPRECATED
- **Issue**: All have the same wrong topic subscription

### ✅ Active Navigation Scripts

#### **ros2_simple_movement_test.py**
- **Purpose**: Test basic robot movement commands
- **Status**: ACTIVE
- **Usage**: Tests cmd_vel publishing

#### **simple_odom_publisher.py**
- **Purpose**: Publish odometry data for testing
- **Status**: ACTIVE

### ✅ Active Utility Scripts

#### **kill_chasebot_processes.py**
- **Purpose**: Clean shutdown of all ChaseBot ROS processes
- **Status**: ACTIVE
- **Usage**: Emergency cleanup tool

#### **cleanup_before_launch.py**
- **Purpose**: Pre-launch cleanup of stale processes
- **Status**: ACTIVE

#### **shutdown_manager.py**
- **Purpose**: Automatic shutdown after timeout
- **Status**: ACTIVE
- **Notes**: Used in launch files for auto-cleanup

### 🧪 Experimental/Test Scripts

#### **d415_vision_display.py**
- **Purpose**: Display D415 camera feed with GUI
- **Status**: EXPERIMENTAL
- **Dependencies**: Requires X11 display

#### **headless_vision_analyzer.py**
- **Purpose**: Analyze vision without GUI
- **Status**: EXPERIMENTAL

## Changelog

### 2025-01-07
- **BREAKTHROUGH**: Fixed YOLO topic mismatch in `ros2_yolo_detector_fixed.py`
- Created `test_camera_topic.py` for camera diagnostics
- Discovered YOLO detects simulated balls as "frisbee" (class 29)

### 2025-01-06
- Initial YOLO integration attempts
- Created monitoring and analysis tools

### Previous
- Navigation test scripts
- Basic movement validation tools

## Usage Examples

### Test Camera Topics
```bash
# Verify camera is publishing
python3 test_camera_topic.py
# Expected: Messages on /d415/image_raw, none on /camera/image_raw
```

### Run Fixed YOLO Detector
```bash
# With display for debug window
export DISPLAY=172.25.128.1:0.0
python3 ros2_yolo_detector_fixed.py
```

### Monitor Detections
```bash
# In separate terminal
python3 monitor_yolo_detections.py
```

## Common Issues

### No Detections
1. Check camera topic with `test_camera_topic.py`
2. Ensure using `ros2_yolo_detector_fixed.py` (not the original)
3. Lower confidence threshold if needed

### Wrong Classification
- Simulated balls detected as "frisbee" (class 29)
- Solution: Accept both frisbee and sports ball classes

## Dependencies
- ROS2 Humble
- OpenCV (`python3-opencv`)
- ultralytics (`pip install ultralytics`)
- cv_bridge
- numpy
