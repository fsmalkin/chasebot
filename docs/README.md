# ChaseBot Documentation

## 🚨 CRITICAL DEVELOPMENT RULE

**ALWAYS COPY WORKING FILES BEFORE EDITING!**
```bash
# Before ANY changes:
cp working_file.py working_file_backup_$(date +%Y%m%d_%H%M%S).py
```
See [Operational Guide](./operational_guide.md) for detailed file management practices.

## Project Status Tracker

### Current Phase: Nav2 Integration Progress
**Date**: 2025-07-12
**Status**: Nav2 controller/planner working, needs odometry relay

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

### ✅ Phase 4: Direct Follower Implementation (WORKING WITH ISSUE)
**Latest Update**: 2025-01-12
- ✅ Direct follower implementation bypassing Nav2 complexity
- ✅ Autonomous ball following achieved!
- ✅ Robot successfully tracks and moves toward detected balls
- ⚠️ **Critical Issue**: Robot moves backwards and turns continuously
  - **Root Cause**: Coordinate frame mismatch between camera and robot
  - **Camera Frame**: X-right, Y-down, Z-forward
  - **Robot Frame**: X-forward, Y-left, Z-up
  - **Attempted Fix**: Transform in v2 (robot_x = camera_z, robot_y = -camera_x) - still backwards
- **Working Command**: `cd ros2_scripts && python test_direct_follower.py`

### 🚧 Phase 4.5: Nav2 Integration (PARTIAL SUCCESS)
**Latest Update**: 2025-07-12
- ✅ **Breakthrough**: Bypassed lifecycle_manager, got controller/planner working
- ✅ **cmd_vel relay created**: Successfully converts Twist → TwistStamped
- ✅ **Nav2 sends commands**: Verified 793 messages sent during path following
- ⚠️ **Odometry missing**: Need relay from `/model/jetbot/odometry` to `/odom`
- **Key Discovery**: Nav2 publishes to `/cmd_vel_nav`, robot expects `/jetbot_base_controller/cmd_vel`
- **Next Step**: Create odometry relay to complete Nav2 integration

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

## Nav2 Integration Progress (July 12)

### ✅ Solved Issues

#### Issue 1: Lifecycle Manager Hanging
**Problem**: lifecycle_manager stuck on bt_navigator/get_state
**Solution**: Bypass lifecycle_manager, launch controller/planner directly
**Status**: ✅ Working - nodes activate successfully

#### Issue 2: Command Velocity Type Mismatch
**Problem**: 
- Nav2 publishes: `/cmd_vel_nav` (geometry_msgs/Twist)
- Robot expects: `/jetbot_base_controller/cmd_vel` (geometry_msgs/TwistStamped)
**Solution**: Created `cmd_vel_relay_v2.0.0.py`
**Status**: ✅ Working - successfully relays 793 messages

#### Issue 3: Missing Map Frame
**Problem**: Nav2 needs map frame for navigation
**Solution**: Created `blank_map_publisher.py`
**Status**: ✅ Working - provides required map frame

### ⚠️ Remaining Issue

#### Odometry Topic Mismatch
**Problem**:
- Nav2 expects: `/odom` (0 publishers)
- Gazebo publishes: `/model/jetbot/odometry` (1 publisher)
**Solution Needed**: Create odometry relay similar to cmd_vel relay
**Impact**: Nav2 stops sending commands after ~2 seconds without position feedback

### Working Nav2 Commands
```bash
# Terminal 1: Launch simulation
ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py

# Terminal 2: Run Nav2 test with relays
python ros2_scripts/test_nav2_v2.0.0.py

# Terminal 3: Monitor command relay
ros2 topic echo /cmd_vel_nav  # See Nav2 commands
ros2 topic echo /jetbot_base_controller/cmd_vel  # See relayed commands
```

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
| Nav2 missing map frame | Add blank map publisher | ✅ Solved |
| Nav2 cmd_vel type mismatch | Created cmd_vel_relay_v2.0.0.py | ✅ Solved |
| Nav2 missing odometry | Need odometry relay | 🔧 In Progress |
| Robot moves backwards | Coordinate transformation issue | 🔧 Needs Fix |

---

## References

- [ros2_vision_inference GitHub](https://github.com/Ikhyeon-Cho/ros2_vision_inference)
- [Nav2 Documentation](https://navigation.ros.org/)
- [ChaseBot Memory Bank](../memory-bank/)
- [ROS2 Scripts Registry](../ros2_scripts/FILE_REGISTRY.yaml)
