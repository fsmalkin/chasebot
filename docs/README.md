# ChaseBot Documentation

## Project Status Tracker

### Current Phase: Vision System Evaluation
**Date**: 2025-01-09
**Status**: Evaluating Two Paths for 3D Vision

---

## Project Overview
ChaseBot is an autonomous golf ball collection robot built on the JetBot Nano platform, running in ROS 2 simulation with advanced 3D vision capabilities.

## Current Vision System Status

### 🟢 Path 1: Our Custom YOLO Detector (WORKING)
- **Status**: ✅ FULLY OPERATIONAL
- **Detection Rate**: Successfully detects golf balls as "frisbee" (class 29)
- **Latest Test**: Ball detected at (0.499, 0.547) with 50.5% confidence
- **Files**:
  - `ros2_yolo_detector_headless.py` - No display required (WSL2 compatible)
  - `ros2_yolo_detector_frisbee_quiet.py` - Reduced logging version
  - `ros2_yolo_detector_frisbee.py` - Verbose version for debugging
- **Next Step**: Add 3D position extraction using depth data

### 🟡 Path 2: ros2_vision_inference Package (PARTIAL)
- **Status**: ⚠️ RUNS BUT NO DETECTIONS
- **Issue**: Model not trained on golf balls (despite having sports ball class)
- **Behavior**: 
  - Node starts successfully
  - Subscribes to camera topics correctly
  - Camera data flows at 3-4 Hz
  - Publishes only empty MarkerArray on `/mono3d/bbox`
- **Model**: `mono3d_yolox_576_768.onnx`
- **Note**: Package advertised sports ball detection but doesn't detect our golf balls

---

## Phase Status Overview

### ✅ Phase 1: Core Foundation (COMPLETE)
- ROS 2 Humble + Gazebo Ignition working
- JetBot URDF with diff drive control
- Basic simulation environment

### ✅ Phase 2: Camera Integration (COMPLETE)
- Intel RealSense D415 camera integrated
- Publishing RGB and depth images
- Camera positioned for optimal ball detection

### 🔄 Phase 3: Vision Detection (IN PROGRESS)
- **Option A**: Use our working YOLO detector ✅
- **Option B**: Debug ros2_vision_inference package ⚠️

### ⏳ Phase 4: 3D Position & Navigation (PENDING)
- Convert 2D detections to 3D world coordinates
- Bridge to Nav2 navigation stack
- Handle multiple ball detections

### ⏳ Phase 5: Full Integration Test (PENDING)
- Complete autonomous ball following
- Performance optimization
- Multi-ball handling

---

## Quick Start Commands

### Using Our Working YOLO Detector
```bash
# Terminal 1: Launch simulation
ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py

# Terminal 2: Launch YOLO detector (headless)
python3 ros2_scripts/ros2_yolo_detector_headless.py

# Terminal 3: Monitor detections
ros2 topic echo /yolo/ball_position
ros2 topic echo /yolo/confidence
```

### Testing ros2_vision_inference (for debugging)
```bash
# Terminal 1: Launch simulation
ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py

# Terminal 2: Launch vision inference
ros2 launch ros2_vision_inference detect_seg_depth.launch.xml \
  mono3d_flag:=true \
  mono3d_ckpt_file:=/home/macro2/ros2_ws/models/mono3d_yolox_576_768.onnx \
  seg_flag:=false \
  monodepth_flag:=false \
  camera_topic:=/d415/color/image_raw \
  camera_param:=/d415/color/camera_info

# Terminal 3: Monitor (will show empty arrays)
ros2 topic echo /mono3d/bbox
```

---

## Working Components Summary

### ✅ Verified Working
- Gazebo simulation with JetBot robot
- D415 camera publishing RGB and depth
- Custom YOLO detector (detects balls as frisbees)
- Camera data flow at proper rates
- Topic publishing infrastructure

### ⚠️ Partially Working
- ros2_vision_inference package (runs but no detections)

### ❌ Not Working
- Golf ball detection in ros2_vision_inference
- Detection3DArray messages (not published at all)

---

## File Organization

```
chasebot/
├── docs/
│   ├── README.md (this file - project status)
│   ├── development_patterns.md (coding standards)
│   ├── vision_system_working.md (YOLO success details)
│   ├── slice_3_vision_inference_*.md (debugging logs)
│   └── vision_strategy_pivot.md (decision rationale)
├── ros2_scripts/
│   ├── FILE_REGISTRY.yaml (complete file inventory)
│   ├── README.md (auto-generated from registry)
│   ├── ros2_yolo_detector_*.py (our detectors)
│   └── test_*.py (test scripts)
└── memory-bank/
    └── activeContext.md (session memory)
```

---

## Development Patterns

See [`docs/development_patterns.md`](./development_patterns.md) for:
- File versioning standards
- Testing patterns
- Documentation requirements
- Clear status reporting

---

## Next Actions

### Option 1: Continue with Our YOLO Detector (Recommended)
1. Implement 3D position extraction using depth data
2. Create Nav2 bridge for navigation goals
3. Test complete autonomous ball following

### Option 2: Debug ros2_vision_inference
1. Investigate why sports ball class doesn't detect golf balls
2. Check model training classes and confidence thresholds
3. Consider retraining model or modifying detection parameters

---

## Known Issues & Solutions

| Issue | Solution | Status |
|-------|----------|--------|
| YOLO detects balls as "frisbee" | Accept class 29 detections | ✅ Solved |
| GUI scripts fail in WSL2 | Created headless versions | ✅ Solved |
| ros2_vision_inference no detections | Model not trained on golf balls | 🔍 Investigating |
| Some scripts need Windows | Document in FILE_REGISTRY | ✅ Documented |

---

## References

- [ros2_vision_inference GitHub](https://github.com/Ikhyeon-Cho/ros2_vision_inference)
- [Nav2 Documentation](https://navigation.ros.org/)
- [ChaseBot Memory Bank](../memory-bank/)
- [ROS2 Scripts Registry](../ros2_scripts/FILE_REGISTRY.yaml)
