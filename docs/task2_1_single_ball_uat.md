# Task 2.1 UAT Procedure: Transform Timing Fix with Single Ball Test

## Overview
This UAT validates the fix for transform timing errors while maintaining successful navigation to a single golf ball.

## Prerequisites
1. **VcXsrv Running**: Launch VcXsrv with "Disable access control" checked
2. **WSL2 Active**: Ubuntu-22.04 instance running
3. **Working Directory**: `/mnt/c/workspaces/chasebot/`

## Test Execution

### Step 1: Copy Updated Files to WSL2
```bash
# Copy the updated scripts and configs
wsl -d Ubuntu-22.04 bash -c "cp -r /mnt/c/workspaces/chasebot/ros2_scripts/* ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 bash -c "cp -r /mnt/c/workspaces/chasebot/ros2_config/* ~/ros2_ws/src/chasebot_description/ros2_config/"
```

### Step 2: Make Scripts Executable
```bash
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/*.py"
```

### Step 3: Run Single Ball Test
```bash
# From Windows PowerShell/CMD in the ChaseBot directory:
python ros2_scripts/run_single_ball_test.py
```

## Expected Timeline & Behavior

### T+0s: Process Cleanup
- "ChaseBot Process Killer" message
- "✓ No ChaseBot processes found" or list of killed processes

### T+2s: VcXsrv Check
- "✅ VcXsrv is running"

### T+5s: Gazebo Launch
- Gazebo window opens with empty world (gray ground plane)
- Red message box visible at top saying "SINGLE BALL TEST"

### T+10s: Robot Spawn
- JetBot robot appears at origin (0,0)
- Camera visible on robot

### T+18s: SLAM Initialization
- SLAM_toolbox starts: "Using solver plugin solver_plugins::CeresSolver"
- **CRITICAL**: Wait for map frame creation before Nav2
- May show initial transform warnings - this is normal

### T+23s: Nav2 Stack Launch
- **IMPORTANT**: Only start after SLAM is ready
- Terminal shows "Managed nodes are active"
- "Creating bond timer..." message
- If you see "Invalid frame ID 'map'" errors, SLAM wasn't ready yet

### T+28s: YOLO Ready
- "YOLOv8m summary" with model details
- CPU usage increases

### T+28s: ⛳ GOLF BALL SPAWNS
- **VISUAL CUE**: White golf ball appears at position (2.0, 0.5)
- "SPAWNING GOLF BALL - TESTING SHOULD BEGIN NOW!" message
- This is when the actual test begins

### T+30s: Visual Debug Window
- **YOLO Debug Window Opens**: Shows camera view with labeled bounding boxes
- Golf ball should have "sports ball" label with confidence score
- Bounding box should be drawn around the ball
- This confirms YOLO is detecting objects correctly

### T+32s: Bridge Active
- "YOLO to Nav Goal bridge initialized" message
- "Nav2 action server is ready!" message

### T+34s: Detection & Navigation
- **SUCCESS CRITERIA**:
  1. ✅ NO transform timing errors (no "extrapolation" messages)
  2. ✅ "Ball detected: sports ball" message with confidence
  3. ✅ "Detection pixels: (X, Y)" with bbox size
  4. ✅ "Estimated distance: X.XXm" 
  5. ✅ "Ball position in camera frame: (X.XX, Y.YY)"
  6. ✅ "Approach position in base_link: (X.XX, Y.YY)"
  7. ✅ "Sending navigation goal to (X.XX, Y.YY)"
  8. ✅ "Goal accepted by Nav2, navigating..."
  9. ✅ Robot physically moves toward ball in Gazebo
  10. ✅ Robot stops approximately 0.3m from ball
  11. ✅ "Navigation succeeded! Reached the ball."

## UAT Success Indicators

### Primary Success (Transform Fix)
- ✅ **NO TRANSFORM ERRORS** in logs
- ✅ Clean detection-to-navigation pipeline
- ✅ Robot successfully navigates to ball

### Secondary Success (System Health)
- ✅ Process management works cleanly
- ✅ Clear visual timing (ball spawns when ready)
- ✅ Detailed logging shows coordinate transformations
- ✅ Navigation completes without errors

## UAT Failure Indicators
- ❌ "Transform error: extrapolation" messages
- ❌ "Transform chain odom->base_link is broken!"
- ❌ Robot doesn't move after ball spawns
- ❌ Navigation goals sent to wrong coordinates

## Common Issues & Solutions

### Issue: "Invalid frame ID 'map'" Errors
**Cause**: Nav2 launched before SLAM created the map frame
**Solution**: 
1. Kill all processes
2. Restart with proper sequence:
   - Launch Gazebo + Robot
   - Launch SLAM_toolbox and wait for initialization
   - Move robot manually to help SLAM build initial map
   - THEN launch Nav2
   - Finally launch YOLO and bridge

### Issue: YOLO Shows Empty Detections
**Cause**: Golf ball not visible to camera or model not detecting
**Solution**:
1. Check camera view with `ros2 run image_tools showimage image:=/camera/image_raw`
2. Ensure golf ball is in front of robot
3. Verify YOLO model includes "sports ball" class

### Issue: Robot Not Moving
**Cause**: Nav2 not fully initialized or goal rejected
**Solution**:
1. Check Nav2 status: All lifecycle nodes should be "Active"
2. Verify map frame exists: `ros2 run tf2_tools view_frames`
3. Check for navigation feedback in terminal

## Debugging Information
If issues occur, check:
1. **Transform Chain**: Look for "Transform chain odom->base_link exists" message
2. **Detection Details**: Pixel coordinates and bbox size logged
3. **Distance Estimation**: "Estimated distance" should be reasonable (0.3-3.0m)
4. **Coordinate Transformation**: Camera frame → base_link → odom positions logged
5. **SLAM Status**: Map frame should exist before Nav2 launches

## Test Cleanup
Press `Ctrl+C` in the test runner window to:
- Stop all processes gracefully
- Run automatic cleanup
- See "✅ Test complete and cleaned up" message

## Task 2.1 Complete When:
1. Robot detects and navigates to single golf ball
2. **NO transform timing errors** appear in logs
3. Detailed coordinate logging shows transformation pipeline
4. Navigation succeeds with robot stopping ~0.3m from ball

## Next Steps
Once this UAT passes:
- Task 2.2: Improve distance estimation accuracy
- Task 3: Implement precise 3-inch (0.0762m) approach
- Task 4: Create unified launch file for production use
