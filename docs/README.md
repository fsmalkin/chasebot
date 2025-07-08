# ChaseBot Documentation Index & Project Status

## Project Overview
ChaseBot is a ROS2-based autonomous golf ball collection robot that uses computer vision (YOLO) for ball detection and Nav2 for navigation. The system runs in Ignition Gazebo simulation and will eventually deploy to JetBot hardware.

## Current Status: YOLO Detection Working! (January 7, 2025)

### 🎯 Latest Breakthrough
- **Issue**: YOLO wasn't detecting balls due to topic mismatch
- **Root Cause**: YOLO subscribed to `/camera/image_raw` but camera publishes to `/d415/image_raw`
- **Solution**: Created `ros2_yolo_detector_fixed.py` with correct topic subscription
- **Result**: YOLO now detects objects (currently classifying as "frisbee" - class 29)
- **Next**: Add multi-class support for both frisbee and sports ball detection

## Project Milestones

### Phase 1: Foundation ✅ COMPLETED
- ROS2 Humble on Ubuntu 22.04 WSL2
- Ignition Gazebo (Fortress) integration
- Basic robot spawning and control
- gz_ros2_control for motor control

### Phase 2: Navigation ✅ COMPLETED
- Nav2 stack integration
- Path planning and obstacle avoidance
- Coordinate transformation fix (15cm accuracy)
- Autonomous navigation to goals

### Phase 3: Vision System 🚧 IN PROGRESS
- ✅ D415 camera integration (producing images at 18Hz)
- ✅ Camera topic mapping fixed
- ✅ YOLO detection working (detects objects)
- 🚧 Multi-class detection (frisbee + sports ball)
- ⏳ 3D depth integration for better positioning

### Phase 4: Autonomous Ball Following ⏳ PENDING
- Integrate vision with navigation
- Continuous ball tracking
- Collection mechanism simulation

## Component Status

### Vision Components (`ros2_scripts/`)
| File | Status | Purpose |
|------|--------|---------|
| `ros2_yolo_detector_fixed.py` | ✅ ACTIVE | Fixed YOLO detector with correct topic |
| `test_camera_topic.py` | ✅ ACTIVE | Camera topic verification tool |
| `ros2_yolo_detector.py` | ❌ DEPRECATED | Original with wrong topic subscription |
| `monitor_yolo_detections.py` | ✅ ACTIVE | Detection monitoring tool |

### Launch Files (`ros2_config/launch/`)
| File | Status | Purpose |
|------|--------|---------|
| `jetbot_gz_control_camera_test_v3.launch.py` | ✅ ACTIVE | Current working launch with camera |
| `jetbot_with_yolo_clean_fixed.launch.py` | ❌ DEPRECATED | Old Classic Gazebo version |
| `jetbot_nav2_integration_complete.launch.py` | ✅ ACTIVE | Full Nav2 integration |

### Navigation Components
| Component | Status | Notes |
|-----------|--------|-------|
| Nav2 Stack | ✅ COMPLETED | Fully integrated and working |
| Coordinate Fix | ✅ COMPLETED | 15cm approach accuracy achieved |
| 3D Navigation | ⏳ PENDING | Waiting on vision completion |

## Quick Start Commands

### Launch Simulation with Camera
```bash
wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py"
```

### Run Fixed YOLO Detector
```bash
wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_fixed.py"
```

### Test Camera Topics
```bash
wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/test_camera_topic.py"
```

## Directory Documentation

### Core Directories
- [`ros2_scripts/`](../ros2_scripts/README.md) - All ROS2 Python scripts and nodes
- [`ros2_config/`](../ros2_config/README.md) - Configuration files, launch files, worlds
- [`memory-bank/`](../memory-bank/README.md) - Session context and project memory
- [`archive/`](../archive/README.md) - Old implementations and documentation

### Configuration Subdirectories
- [`ros2_config/launch/`](../ros2_config/launch/README.md) - Launch file descriptions
- [`ros2_config/worlds/`](../ros2_config/worlds/README.md) - Gazebo world files
- [`ros2_config/urdf/`](../ros2_config/urdf/README.md) - Robot models and descriptions

## Known Issues & Solutions

### Issue: YOLO Detection Shows "Frisbee" Instead of "Sports Ball"
- **Cause**: Pre-trained YOLO models classify simulated balls differently
- **Impact**: Detection works but with wrong class label
- **Solution**: Accept both class 29 (frisbee) and class 32 (sports ball)

### Issue: Wheel Axis Bug ✅ FIXED (January 8, 2025)
- **Status**: Fixed in SDF file `jetbot_core_ignition_v1.3.0.sdf`
- **Solution**: Changed wheel joint axis from Y-axis (0 1 0) to Z-axis (0 0 1)
- **Result**: Wheels now rotate properly for forward/backward movement instead of spinning like casters

## Next Steps
1. Create multi-class YOLO detector (accept frisbee + sports ball)
2. Test complete autonomous ball following pipeline
3. Add 3D depth information for better positioning
4. Document working configuration in memory bank
