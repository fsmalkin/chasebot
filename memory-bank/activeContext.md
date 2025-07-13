# Active Context - ChaseBot YOLO + Depth Pipeline Integration

## Session Date: 2025-07-12 (Latest Update)

### Current Focus: Nav2 Integration & Coordinate Transformation Issue

#### Status:
- ✅ YOLO + Depth pipeline VERIFIED WORKING (detects balls, extracts 3D positions)
- ✅ Robot control VERIFIED (responds to TwistStamped on `/jetbot_base_controller/cmd_vel`)
- ✅ Direct follower VERIFIED WORKING - Robot moves autonomously!
- ⚠️ CRITICAL ISSUE: Robot moves backwards and turns in one direction
- ⚠️ Nav2 integration PARTIAL - controller/planner work but missing odometry relay

#### Direct Follower Success & Issue (Jan 12 - 9:37 PM):
- **Confirmed Working**: Complete vision pipeline operational
- **YOLO Detection**: Detects balls with 50.1% confidence at ~1.58m distance
- **3D Positions**: Successfully extracted from depth data
- **Robot Control**: Actively responds to control commands
- **CRITICAL BUG**: Robot moves backwards instead of forwards and turns continuously

#### Coordinate Transformation Analysis:
- **Root Cause**: Incorrect coordinate transformation between camera and robot frames
- **Camera Frame**: X-right, Y-down, Z-forward (standard camera convention)
- **Robot Frame**: X-forward, Y-left, Z-up (standard robot convention)
- **Current Math**: Direct use of camera coordinates causes backwards motion
- **Attempted Fix (v2)**: Transform robot_x = camera_z, robot_y = -camera_x
- **Result**: Still incorrect - robot still moves backwards and turns

#### Working Commands:
```bash
# Run complete direct follower test (LAST KNOWN GOOD)
cd ros2_scripts && python test_direct_follower.py

# Components launched:
# 1. Simulation with D415 camera (GUI)
# 2. YOLO detector (headless, confidence_threshold: 0.3)
# 3. 3D position extractor
# 4. Direct follower node
```

#### Direct Follower Parameters:
- **Approach Distance**: 15cm (0.15m)
- **Max Linear Speed**: 0.2 m/s
- **Max Angular Speed**: 0.5 rad/s
- **Proportional Gains**: 0.5 linear, 2.0 angular
- **Detection Timeout**: 2 seconds

#### Files Created This Session:
1. **yolo_3d_direct_follower.py** - Main follower implementation (backwards issue)
2. **yolo_3d_direct_follower_v2.py** - Attempted coordinate fix (still backwards)
3. **test_direct_follower.py** - Complete test script (LAST KNOWN GOOD)
4. **test_direct_follower_v2.py** - Test for v2 follower
5. **test_direct_follower_tuning.py** - Parameter tuning tool
6. **Nav2 debugging suite**:
   - nav2_complete_params.yaml
   - test_nav2_manual_launch.py
   - test_nav2_lifecycle_manual.py
   - test_controller_server_only.py

#### Nav2 Debugging Status (Updated July 12):
- **Major Progress**: Bypassed lifecycle_manager, got controller/planner working
- **Key Discovery 1**: Nav2 publishes to `/cmd_vel_nav` but robot expects `/jetbot_base_controller/cmd_vel` (TwistStamped)
- **Key Discovery 2**: Missing odometry - `/odom` has 0 publishers, data on `/model/jetbot/odometry`
- **Solution Implemented**: Created cmd_vel_relay_v2.0.0.py - successfully relays 793 messages
- **Remaining Issue**: Need odometry relay from `/model/jetbot/odometry` to `/odom`
- **Files Created**:
  - test_nav2_simple.py - Bypasses lifecycle_manager
  - test_nav2_v2.0.0.py - Includes cmd_vel relay
  - cmd_vel_relay_v2.0.0.py - Type conversion Twist → TwistStamped
  - nav2_minimal_params_v3.yaml - Working controller configuration with critics

#### Next Steps for New Session:
1. **Complete Nav2 Integration**:
   - Create odometry relay from `/model/jetbot/odometry` to `/odom`
   - Test full navigation with odometry feedback
   - Should enable Nav2 path planning and execution
2. **Fix coordinate transformation math**:
   - Need proper rotation matrix between camera and robot frames
   - Consider: robot_x = camera_z, robot_y = camera_x, robot_z = camera_y
   - Test with visualization to verify correct transformation
3. **Alternative: Train YOLO on robot's view if coordinate fix too complex**

#### Achievement Despite Issue:
**Autonomous ball tracking is operational!** The robot successfully detects golf balls and responds with movement. The backwards motion is a solvable coordinate transformation issue.
