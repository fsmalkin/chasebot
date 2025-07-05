# Task 2 UAT Procedure: YOLO-to-Nav2 Bridge

## Prerequisites
1. **VcXsrv Running**: Ensure VcXsrv is active in system tray with access control disabled
2. **WSL2 Active**: Ubuntu-22.04 instance running

## Launch Command
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}'):0.0 && ros2 launch ~/ros2_ws/src/chasebot_description/launch/jetbot_yolo_nav2_complete.launch.py"
```

## Expected Behavior Timeline

### T+0s: Launch
- Gazebo GUI opens with simple_golf_ball_world
- Golf balls visible in simulation

### T+5s: Robot Spawn
- JetBot robot appears at origin (0,0)
- Camera sensor active

### T+8s: Nav2 Stack
- Nav2 navigation stack initializes
- "Lifecycle nodes are active" message appears

### T+10s: YOLO Detection
- YOLO nodes start processing camera feed
- "sports ball" detections begin appearing in logs

### T+12s: Bridge Active
- "YOLO to Nav Goal bridge initialized" message
- "Waiting for Nav2 action server..." followed by "Nav2 action server is ready!"

### T+15s: Autonomous Behavior
- **UAT SUCCESS CRITERIA**:
  1. "Ball detected: sports ball" message with confidence >0.5
  2. "Sending navigation goal to (X.XX, Y.YY)" message
  3. "Goal accepted by Nav2, navigating..." message
  4. Robot physically moves toward golf ball in Gazebo
  5. Robot stops approximately 0.3m from ball
  6. "Navigation succeeded! Reached the ball." message

## Visual Verification (Optional)
```bash
# In a new terminal, view YOLO detections with bounding boxes:
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}'):0.0 && ros2 run rqt_image_view rqt_image_view"
# Select /yolo/debug_image to see bounding boxes
```

## Success Indicators
- ✅ YOLO detects golf balls as "sports ball"
- ✅ Detection converted to navigation goal
- ✅ Nav2 accepts and executes goal
- ✅ Robot autonomously approaches ball
- ✅ Robot stops at approach distance

## Failure Indicators
- ❌ "Transform error" messages
- ❌ "Goal rejected by Nav2"
- ❌ Robot doesn't move after detection
- ❌ Robot oscillates or exhibits unstable behavior

## Task 2 Complete When:
Robot successfully detects a golf ball via YOLO and autonomously navigates to within 0.3m of it.
