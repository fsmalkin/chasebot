# Slice 2 UAT: Basic Gazebo + Robot Spawn + Static Transforms

## Overview
This is the second thin slice in our iterative launch file development. It builds on Slice 1 by adding explicit static transform publishers to fix the transform tree fragmentation issue discovered during previous testing.

## Purpose
- Maintain all Slice 1 functionality
- Add explicit static transform publishers
- Create complete transform chain: map → odom → base_link → camera_link → camera_optical_link
- Eliminate transform-related errors that block navigation

## What's New in Slice 2
- **3 Static Transform Publishers**:
  1. `map → odom` (0,0,0) - Required for Nav2
  2. `base_link → camera_link` (0.07,0,0.12) - Often missing from Gazebo
  3. `camera_link → camera_optical_link` (optical frame convention)

## Launch Command
```bash
# From Windows (with VcXsrv running)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_transforms.launch.py"
```

## UAT Success Criteria

### ✅ Primary Checks (Same as Slice 1)
1. **Gazebo Opens**: Window appears showing simulation world
2. **Robot Spawns**: JetBot appears at origin (0,0,0.05)
3. **Camera Visible**: Camera sensor mounted on robot front
4. **No Errors**: No RED error messages in terminal

### ✅ Slice 2 Specific - Transform Verification
1. **No Transform Warnings**: 
   - No "extrapolation into future" errors
   - No "transform timeout" warnings
   - No "unable to transform" messages

2. **Complete Transform Tree**:
   ```bash
   # Generate transform tree visualization (creates frames.pdf)
   wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run tf2_tools view_frames"
   
   # View the PDF (from Windows)
   wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && ls frames*.pdf"
   ```
   
   Expected: PDF shows complete chain with no disconnected nodes

3. **Verify Specific Transform**:
   ```bash
   # Test transform from map to camera
   wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run tf2_ros tf2_echo map camera_optical_link"
   ```
   
   Expected: Valid transform data with position and rotation

4. **Check Static Transforms**:
   ```bash
   # View published static transforms
   wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /tf_static --once"
   ```
   
   Expected: Should show all 3 static transforms being published

## Auto-Shutdown Features
- **5-minute timer**: Automatic cleanup after UAT
- **User controls**:
  - `Enter`: Confirm UAT success, shutdown immediately
  - `e` + `Enter`: Extend timer by 5 minutes
  - `q` + `Enter`: Quit immediately
- **Clean termination**: All processes properly killed

## What This Slice Does NOT Include
- ❌ YOLO detection
- ❌ Nav2 stack
- ❌ Golf ball spawning
- ❌ Any autonomous behavior
- ❌ Movement or navigation

## Common Issues

### Issue: "No module named 'tf2_ros'"
**Solution**: Install tf2_ros if missing
```bash
wsl -d Ubuntu-22.04 bash -c "sudo apt-get update && sudo apt-get install ros-humble-tf2-ros ros-humble-tf2-tools"
```

### Issue: Transform tree still shows disconnected nodes
**Solution**: Check that all 3 static publishers launched successfully. Look for these lines in terminal:
- "Publishing map → odom transform..."
- "Publishing base_link → camera_link transform..."
- "Publishing camera_link → camera_optical_link transform..."

### Issue: "Unable to open frames.pdf"
**Solution**: The PDF is created in the workspace root. Find it with:
```bash
wsl -d Ubuntu-22.04 bash -c "find ~/ros2_ws -name 'frames*.pdf' -type f"
```

## Success Indicators
✅ Robot spawns (same as Slice 1)
✅ No transform-related errors in terminal
✅ Transform tree visualization shows complete chain
✅ `tf2_echo` returns valid transform data
✅ System ready for YOLO/Nav2 integration

## Next Steps
Once this UAT passes:
- **Slice 3**: Add YOLO detection with proper time synchronization
- **Slice 4**: Add Nav2 minimal with the working transform tree
- **Slice 5**: Add bridge script to connect detections to navigation

## Key Improvements from Slice 1
- Explicit static transforms prevent Gazebo reliability issues
- Complete transform chain enables coordinate transformations
- Foundation ready for vision-based navigation
- No more "extrapolation into future" errors
