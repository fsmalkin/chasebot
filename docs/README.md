# ChaseBot Project Documentation

## Project Status (January 8, 2025)

### 🚧 Current Development: 3D Vision Integration
**Active Work**: Extracting 3D positions from YOLO detections for autonomous navigation

**Files Currently Under Development:**
- `ros2_scripts/discover_yolo_format.py` - YOLO output format analyzer
- `ros2_scripts/test_slice_2_1_discovery.py` - Format discovery test
- `ros2_scripts/yolo_3d_position_extractor.py` - 3D position extraction node
- `ros2_scripts/test_3d_position_extraction.py` - Integration test

### ✅ Recent Achievements
1. **YOLO Detection Fixed** - Topic mismatch resolved
2. **Wheel Axis Bug Fixed** - Proper differential drive working
3. **Documentation Restructured** - Clear README in each directory

## Quick Start - Working Detection Demo

```bash
# Run this to see YOLO detection working:
python ros2_scripts/test_sports_ball_detection_uat.py
```

## System Architecture

### Vision Pipeline Status
```
D415 Camera → YOLO Detection → 3D Position → Nav2 Goals
    ✅             ✅             🚧            ⏳
```

### Key Components
- **Camera**: D415 publishing to `/d415/image_raw` at 18Hz
- **Detection**: YOLO v8 detecting balls as "frisbee" (class 29)
- **Navigation**: Nav2 stack ready for integration
- **Robot**: JetBot with fixed wheel axis (v1.3.0 SDF)

## Critical Files Reference

### Working Detection Files
- `ros2_scripts/ros2_yolo_detector_fixed.py` - Fixed topic subscription ✅
- `ros2_scripts/ros2_yolo_detector_frisbee.py` - Accepts frisbee class ✅
- `ros2_scripts/test_sports_ball_detection_uat.py` - Complete test ✅

### Fixed Robot Definition
- `ros2_config/urdf/jetbot_core_ignition_v1.3.0.sdf` - Wheel axis fixed ✅
- `ros2_config/urdf/jetbot_core_ignition.sdf` - Latest version ✅

### Launch Files
- `ros2_config/launch/jetbot_gz_control_camera_test_v3.launch.py` - Current test
- `ros2_config/launch/jetbot_nav2_integration_complete.launch.py` - Full Nav2

## Development Workflow

### Current Testing Command
```bash
# Terminal 1: Launch simulation
wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py"

# Terminal 2: Run YOLO detector
wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_frisbee.py"
```

## Known Issues & Solutions

### Issue: YOLO Detects Balls as "Frisbee"
- **Cause**: Pre-trained model misclassifies simulated objects
- **Solution**: Accept frisbee (class 29) detections
- **Status**: Working with frisbee detection ✅

### Issue: cv2.imshow Crashes Without Display
- **Cause**: YOLO detector tries to show windows
- **Impact**: Affects headless operation
- **Solution**: Create headless version (in progress) 🚧

### Issue: Missing Depth Topics
- **Need**: Depth data for 3D position calculation
- **Expected**: `/d415/depth/*` topics
- **Status**: Investigating availability 🚧

## Project Milestones

### Completed ✅
- [x] ROS 2 Humble environment setup
- [x] Gazebo Ignition integration
- [x] Robot movement control
- [x] Camera integration (D415)
- [x] YOLO detection working
- [x] Wheel axis bug fixed
- [x] Documentation structure

### In Progress 🚧
- [ ] 3D position extraction from detections
- [ ] Headless YOLO operation
- [ ] Depth topic verification

### Planned ⏳
- [ ] YOLO → Nav2 integration
- [ ] Multi-class detection (frisbee + sports ball)
- [ ] Complete autonomous ball following
- [ ] Hardware deployment preparation

## Directory Structure

```
chasebot/
├── ros2_scripts/          # All Python scripts (50+ files)
│   ├── *_fixed.py        # Fixed/working versions
│   ├── *_frisbee.py      # Frisbee-specific detectors
│   └── test_*.py         # Test scripts
├── ros2_config/          # ROS 2 configuration
│   ├── launch/           # Launch files (30+)
│   ├── urdf/             # Robot definitions (check README for fixed versions)
│   └── worlds/           # Simulation worlds
├── memory-bank/          # Project context & progress
├── docs/                 # This documentation
└── archive/              # Old/deprecated files
```

## Next Steps

1. **Complete 3D Position Extraction**
   - Debug depth topic availability
   - Fix headless operation
   - Test position calculations

2. **Integration Testing**
   - Connect YOLO to Nav2
   - Test autonomous navigation
   - Validate approach accuracy

3. **Documentation & Cleanup**
   - Archive deprecated files
   - Create operational guide
   - Update hardware prep docs

---

For detailed progress tracking, see `memory-bank/progress.md`
For current work context, see `memory-bank/activeContext.md`
