# ChaseBot Current Experiments Reference Guide

## Overview
This document provides clear instructions to reproduce all current experiments and highlights key issues discovered.

## Working Baseline Configuration (2D System)

### Last Fully Working Setup
This configuration achieved autonomous ball following with 15cm accuracy:

```bash
# Terminal 1: Launch simulation with Nav2
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py"

# Terminal 2: Launch corrected coordinate bridge
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py --ros-args -p use_sim_time:=true"
```

**Key Features:**
- Single ball at 3.0m distance
- Wheel axis properly configured
- YOLO detection working (with textured balls)
- Accurate navigation to target

## Current 3D Vision Experiments

### Experiment 1: Camera Feed Verification ✅

**Purpose:** Verify D415 camera is producing images and oriented correctly

```bash
# Terminal 1: Launch with camera orientation test world (4 colored balls)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_description jetbot_gz_control_camera_test_v2.launch.py"

# Terminal 2: View camera feed
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 run rqt_image_view rqt_image_view"
# Select /d415/image_raw from dropdown

# Terminal 3: Check camera data rate
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic hz /d415/image_raw"
```

**Results:**
- Camera producing 640x480 images at ~18Hz
- Camera facing forward (can see colored balls)
- ⚠️ **ISSUE**: Wheel axis bug present in this configuration

### Experiment 2: YOLO Integration Test ❌

**Purpose:** Test YOLO detection on simulated balls

```bash
# Terminal 1: Launch integrated YOLO test
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_description jetbot_yolo_d415_test.launch.py"

# Terminal 2: Monitor YOLO detections
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/monitor_yolo_detections.py"

# Terminal 3: View what YOLO sees (optional)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 run rqt_image_view rqt_image_view"
# Try /yolo/dbg_image (may be blank)
```

**Results:**
- YOLO nodes running correctly
- 0 detections despite visible balls
- Pre-trained model expects textured sports balls

### Experiment 3: Manual YOLO Launch

**Purpose:** Test YOLO with different parameters

```bash
# Terminal 1: Keep simulation running from Experiment 1

# Terminal 2: Launch YOLO separately
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch yolo_bringup yolo.launch.py model:=yolov8m.pt input_image_topic:=/d415/image_raw device:=cpu"

# Terminal 3: Analyze raw detections
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/analyze_yolo_raw_detections.py"
```

## Key Issues Discovered

### 1. Detection Problem 🔴
**Issue:** YOLO doesn't detect uniform-colored simulation balls
- Pre-trained models expect realistic textures
- Simulated balls are perfect spheres with solid colors
- No seams, panels, or surface variations

**Impact:** Cannot proceed with 3D vision pipeline

### 2. Wheel Axis Regression ⚠️
**Issue:** Wheel axis bug reappeared in multi-ball world
- Was fixed in `jetbot_nav2_integration_complete.launch.py`
- Not fixed in `jetbot_gz_control_camera_test_v2.launch.py`
- Causes robot to spin instead of moving forward

**Impact:** Movement testing difficult in some configurations

## Diagnostic Tools Created

### 1. YOLO Detection Monitor
```bash
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/monitor_yolo_detections.py
```
Shows:
- Camera feed status
- Detection count
- Ball detection count (class 32)

### 2. YOLO Raw Analyzer
```bash
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/analyze_yolo_raw_detections.py
```
Shows:
- All detections (any class)
- Confidence scores
- Bounding box coordinates

### 3. Camera Viewer
```bash
ros2 run rqt_image_view rqt_image_view
```
Topics to check:
- `/d415/image_raw` - Raw camera feed
- `/yolo/dbg_image` - YOLO debug view (currently blank)

## Next Steps Priority

### 1. Isolate Detection Solution
**Options in order of feasibility:**

a) **Color-based detector** (1-2 hours)
   - Use HSV filtering for specific colors
   - Circle detection with OpenCV
   - Quick to implement

b) **Add ball textures** (2-4 hours)
   - Modify SDF models
   - Add soccer/tennis ball textures
   - May work with existing YOLO

c) **Custom YOLO training** (1-2 days)
   - Generate simulated dataset
   - Train on uniform balls
   - Most robust but time-consuming

d) **Alternative detector** (2-3 hours)
   - Use blob detection
   - Hough circle transform
   - Color + shape combination

### 2. Fix Wheel Axis Consistency
Compare these files:
- `jetbot_nav2_integration_complete.launch.py` (working)
- `jetbot_gz_control_camera_test_v2.launch.py` (broken)

Look for differences in:
- Controller configuration
- Wheel joint parameters
- Robot model loading

### 3. Port Solution to Main Sim
Once detection works:
1. Integrate with existing Nav2 setup
2. Add depth processing for 3D position
3. Test full autonomous following

## File Sync Commands

Always sync files from Windows to WSL before testing:

```bash
# Sync scripts
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/* ~/ros2_ws/src/chasebot_description/ros2_scripts/'"

# Sync launch files
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/* ~/ros2_ws/src/chasebot_description/ros2_config/launch/'"

# Rebuild if needed
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description'"
```

## Process Management

Kill stuck processes before relaunching:
```bash
# Check processes
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|ros2|yolo)' | grep -v grep"

# Kill by PID (use actual PIDs from above)
wsl -d Ubuntu-22.04 bash -c "kill -9 PID1 PID2 PID3"
