# ChaseBot Documentation

## Project Status Tracker

### Current Phase: Vision System Finalized
**Date**: 2025-01-10
**Status**: YOLO + Depth Pipeline Selected as Primary Approach

---

## Project Overview
ChaseBot is an autonomous golf ball collection robot built on the JetBot Nano platform, running in ROS 2 simulation with advanced 3D vision capabilities.

## Current Vision System Status

### 🟢 Selected Approach: YOLO + Depth Pipeline 
**Decision Date**: 2025-01-10
- **Status**: ✅ FULLY OPERATIONAL - Selected as primary vision approach
- **Detection Rate**: 100% when ball in view
- **3D Position**: Successfully extracts world coordinates using depth
- **Performance**: ~30 FPS processing
- **Key Files**:
  - `ros2_yolo_detector_headless.py` - Production detector (no display)
  - `yolo_3d_position_extractor.py` - Converts 2D→3D using depth
  - `test_yolo_vs_vision_inference_comparison.py` - Comparison test
- **Next Steps**: Finalize Nav2 integration for autonomous following

### 📋 Alternative Evaluated: ros2_vision_inference
- **Status**: ❌ Not suitable for golf balls
- **Test Result**: Processes images but produces no detections
- **Root Cause**: Model not trained on golf balls
- **Decision**: Keep as future enhancement when golf ball models available
- **Details**: See [`vision_architecture.md`](./vision_architecture.md)

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

### ✅ Phase 3: Vision Detection (COMPLETE)
- Selected YOLO + Depth pipeline as primary approach
- 3D position extraction working accurately
- ros2_vision_inference evaluated and documented as future option

### 🚧 Phase 4: Nav2 Integration (IN PROGRESS)
**Latest Update**: 2025-01-10
- ✅ 3D position extraction from YOLO detections working
- ✅ Nav2 bridge implementation complete (`ros2_yolo_to_nav_goal_v3.0.0.py`)
- 🔧 Nav2 basic connectivity test revealed integration issues:
  - **Missing Map Frame**: Nav2 requires a "map" frame that doesn't exist
  - **Topic Mismatch**: Robot uses `/jetbot_base_controller/cmd_vel` but Nav2 expects `/cmd_vel`
  - **Goal Rejection**: Navigation goals rejected due to incomplete Nav2 activation
- **Next Steps**: 
  - Add blank map publisher to provide map frame
  - Configure topic remapping for cmd_vel and odom
  - Complete thin slice testing approach

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

## Nav2 Integration Challenges

### Issue 1: Missing Map Frame
**Problem**: Nav2 global costmap waiting for transform from `base_link` to `map`
**Error**: `Invalid frame ID "map" passed to canTransform argument target_frame - frame does not exist`
**Solution**: Need to provide a map frame, either through:
- SLAM (Simultaneous Localization and Mapping)
- Static map server
- Blank map publisher for testing

### Issue 2: Topic Remapping
**Problem**: Topic namespace mismatch
- Robot publishes: `/jetbot_base_controller/cmd_vel` and `/jetbot_base_controller/odom`
- Nav2 expects: `/cmd_vel` and `/odom`
**Solution**: Configure remapping in Nav2 launch file or robot controller

### Issue 3: Nav2 Activation Sequence
**Problem**: Nav2 lifecycle nodes fail to activate without proper map
**Solution**: Ensure all dependencies are met before Nav2 startup:
1. Provide map frame
2. Ensure transforms are available
3. Verify topic connections

### Thin Slice Testing Approach
To address these issues systematically:
- **Slice 1**: ✅ Basic connectivity test (revealed issues)
- **Slice 1.5**: Add blank map publisher
- **Slice 2**: Fix topic remapping
- **Slice 3**: Verify basic navigation
- **Slice 4**: Integrate 3D vision pipeline
- **Slice 5**: Complete autonomous ball following

---

## Next Actions

### Primary Path Forward
1. Finalize Nav2 bridge integration (`ros2_yolo_to_nav_goal_v3.0.0.py`)
2. Test complete autonomous ball following
3. Optimize performance if needed
4. Consider custom YOLO training for better golf ball detection

### Future Enhancement Opportunities
1. Monitor ros2_vision_inference for golf ball-compatible models
2. Train custom YOLO model specifically on golf balls
3. Implement multi-ball tracking and prioritization

---

## Known Issues & Solutions

| Issue | Solution | Status |
|-------|----------|--------|
| YOLO detects balls as "frisbee" | Accept class 29 detections | ✅ Solved |
| GUI scripts fail in WSL2 | Created headless versions | ✅ Solved |
| ros2_vision_inference no detections | Model not trained on golf balls | 📋 Documented as limitation |
| Some scripts need Windows | Document in FILE_REGISTRY | ✅ Documented |
| Nav2 missing map frame | Add blank map publisher | 🔧 In Progress |
| Nav2 topic mismatch | Configure remapping for cmd_vel/odom | 🔧 In Progress |
| Nav2 goal rejection | Fix map frame and remapping first | 🔧 In Progress |

---

## References

- [ros2_vision_inference GitHub](https://github.com/Ikhyeon-Cho/ros2_vision_inference)
- [Nav2 Documentation](https://navigation.ros.org/)
- [ChaseBot Memory Bank](../memory-bank/)
- [ROS2 Scripts Registry](../ros2_scripts/FILE_REGISTRY.yaml)
