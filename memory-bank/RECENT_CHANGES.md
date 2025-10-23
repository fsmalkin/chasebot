# Recent Changes - ChaseBot Project

## 2025-07-12 Session: Nav2 Integration Progress

### Major Achievements:
1. **Breakthrough with Nav2** - Bypassed lifecycle_manager to get controller/planner working
   - Discovered Nav2 publishes to `/cmd_vel_nav` (Twist)
   - Robot expects `/jetbot_base_controller/cmd_vel` (TwistStamped)
   - Created `cmd_vel_relay_v2.0.0.py` to bridge the gap
   
2. **Identified Missing Odometry**
   - Nav2 expects `/odom` but has 0 publishers
   - Gazebo publishes to `/model/jetbot/odometry`
   - Need odometry relay for complete Nav2 functionality

3. **Successfully Tested Nav2 Components**
   - Controller server configured and activated with DWB critics
   - Planner server working with NavFn planner
   - Path computation successful (computed path to 1m goal)
   - Command relay verified (793 messages relayed before stopping)

### Files Created:
- `test_nav2_simple.py` - Bypasses lifecycle_manager for direct control
- `test_nav2_v2.0.0.py` - Includes cmd_vel relay integration
- `test_nav2_minimal_v1.0.0.py` - Minimal Nav2 configuration
- `cmd_vel_relay_v2.0.0.py` - Converts Twist to TwistStamped with logging
- `nav2_minimal_params_v2.yaml` - Nav2 params without critics (failed)
- `nav2_minimal_params_v3.yaml` - Nav2 params with proper DWB critics (working)

### Key Discoveries:
- Nav2 stops sending commands after ~2 seconds without odometry feedback
- DWB local planner requires critics to be defined
- Manual lifecycle management bypasses bt_navigator issues
- Topic type mismatches are common in ROS 2 integrations

---

## 2025-01-12 Session: Direct Follower Implementation & Coordinate Issue

### Major Achievements:
1. **Implemented Direct Follower** - Bypassed Nav2 to achieve autonomous ball following
   - Created `yolo_3d_direct_follower.py` with proportional control
   - Robot successfully tracks and moves toward detected balls
   - Complete end-to-end pipeline working

2. **Discovered Coordinate Transformation Bug**
   - Robot moves backwards instead of forwards
   - Turns continuously in one direction
   - Root cause: Camera frame vs Robot frame mismatch

3. **Created Debugging Solutions for Nav2**
   - Complete parameter file with bond_timeout=0
   - Manual launch script bypassing lifecycle_manager
   - Lifecycle debug script for manual state transitions
   - Minimal controller test

### Files Created:
- `yolo_3d_direct_follower.py` - Direct proportional control follower
- `yolo_3d_direct_follower_v2.py` - Attempted coordinate fix (still backwards)
- `test_direct_follower.py` - Complete test script (LAST KNOWN GOOD)
- `test_direct_follower_v2.py` - Test for v2 with coordinate transform
- `test_direct_follower_tuning.py` - Parameter tuning tool
- `nav2_complete_params.yaml` - Full Nav2 parameters with fixes
- `test_nav2_manual_launch.py` - Manual Nav2 launch without lifecycle
- `test_nav2_lifecycle_manual.py` - Manual lifecycle transitions
- `test_controller_server_only.py` - Minimal controller test

### Key Discovery:
Robot moves backwards because camera coordinates are being used directly without proper transformation to robot frame. The attempted fix in v2 (robot_x = camera_z, robot_y = -camera_x) was still incorrect.

---

## 2025-01-10 Session Summary

### Vision System Decision Finalized
- Selected YOLO + Depth pipeline as primary approach
- ros2_vision_inference evaluated but doesn't detect golf balls
- Created comprehensive comparison test

### Files Created/Modified:
- `test_yolo_vs_vision_inference_comparison.py` - Side-by-side comparison
- `vision_architecture.md` - Detailed analysis of both approaches
- Updated `docs/README.md` with final decision

---

## 2025-01-09 Session Summary

### 3D Vision Pipeline Success
- Implemented 3D position extraction from YOLO + depth
- Created headless detector for WSL2 compatibility
- Verified complete pipeline working end-to-end

### Key Files:
- `ros2_yolo_detector_headless.py` - No display required
- `yolo_3d_position_extractor.py` - 2D to 3D conversion
- `test_3d_position_extraction.py` - Integration test

---

## 2025-01-07 Session Summary

### YOLO Detection Breakthrough
- Discovered simulated balls appear as "frisbee" (class 29)
- Created frisbee-specific detectors
- Achieved reliable ball detection

### Key Files:
- `ros2_yolo_detector_frisbee.py` - Accepts frisbee class
- `ros2_yolo_detector_frisbee_quiet.py` - Production version
- `test_sports_ball_detection_uat.py` - Complete demo

---

## 2025-01-06 Session Summary

### Initial Setup
- ROS 2 Humble + Gazebo Ignition working
- JetBot URDF with diff drive control
- D415 camera integrated and publishing

### Foundation Files:
- Basic simulation environment
- Camera integration complete
- Initial YOLO detector attempts
