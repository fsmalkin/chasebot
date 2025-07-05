# Slice 4 UAT: Nav2 Minimal Integration

## Overview
This slice adds the Nav2 navigation stack to our existing YOLO detection system, enabling autonomous ball following behavior. The robot will detect golf balls and autonomously navigate to them.

## Purpose
- Maintain all Slice 1, 2, and 3.5 functionality
- Add Nav2 navigation stack components
- Enable autonomous navigation to detected balls
- Test complete end-to-end system

## What's New in Slice 4
- **Nav2 Stack**: Controller, Planner, Behavior Server, BT Navigator
- **Robot State Publisher**: For URDF broadcasting
- **YOLO to Nav2 Bridge**: Converts detections to navigation goals
- **Lifecycle Manager**: Coordinates Nav2 component startup
- **Autonomous Behavior**: Complete detection → navigation pipeline

## Launch Command
```bash
# From Windows (with VcXsrv running)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_nav2_minimal.launch.py"
```

## UAT Success Criteria

### ✅ Foundation Checks (From Previous Slices)
1. **Gazebo Opens**: Window appears showing simulation world
2. **Robot Spawns**: JetBot appears at origin (0,0,0.05)
3. **Golf Ball Visible**: Green golf ball visible at position (2.0, 1.0)
4. **YOLO Detection**: OpenCV window shows bounding box around ball
5. **Clean Logging**: Periodic summaries without spam

### 🎯 Slice 4 Specific - Nav2 Integration

#### 1. Nav2 Stack Startup
Expected console messages:
```
[controller_server-X] [INFO] Creating controller server
[planner_server-X] [INFO] Creating planner server
[behavior_server-X] [INFO] Creating behavior server
[bt_navigator-X] [INFO] Creating BT navigator
[lifecycle_manager-X] [INFO] Starting lifecycle nodes...
[lifecycle_manager-X] [INFO] Managed nodes are active
```

#### 2. Bridge Script Activation
```
[yolo_to_nav_goal-X] [INFO] Waiting for Nav2 action server...
[yolo_to_nav_goal-X] [INFO] Nav2 action server is ready!
[yolo_to_nav_goal-X] [INFO] YOLO to Nav Goal bridge initialized
```

#### 3. Autonomous Navigation Behavior
When the robot detects a ball:
```
[yolo_to_nav_goal-X] [INFO] Ball detected: sports ball (confidence: 0.XX, bbox center: XXX, XXX)
[yolo_to_nav_goal-X] [INFO] Detection pixels: (XXX, XXX), bbox size: XXxXX
[yolo_to_nav_goal-X] [INFO] Estimated distance: X.XXm
[yolo_to_nav_goal-X] [INFO] Ball position in camera frame: (X.XX, X.XX)
[yolo_to_nav_goal-X] [INFO] Approach position in base_link: (X.XX, X.XX)
[yolo_to_nav_goal-X] [INFO] Sending navigation goal to (X.XX, X.XX)
[yolo_to_nav_goal-X] [INFO] Goal accepted by Nav2, navigating...
```

#### 4. Robot Movement
- **Visual**: Robot turns toward the ball and moves forward
- **Path Planning**: Robot avoids obstacles (if any)
- **Goal Achievement**: Robot stops approximately 0.3m from the ball
- **Success Message**: `[yolo_to_nav_goal-X] [INFO] Navigation succeeded! Reached the ball.`

### 📊 Testing Options

#### Manual Goal Testing (Optional)
Test Nav2 without YOLO by publishing manual goals:
```bash
# In a separate terminal
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic pub /goal_pose geometry_msgs/PoseStamped '{header: {frame_id: \"odom\"}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}'"
```

#### Check Nav2 Topics
```bash
# Verify Nav2 topics are active
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list | grep -E '(cmd_vel|goal_pose|plan|controller)'"

# Expected topics:
/cmd_vel
/goal_pose
/controller_server/transition_event
/planner_server/transition_event
/behavior_server/transition_event
/bt_navigator/transition_event
```

## Key Improvements from Slice 3.5
- **Full Autonomy**: Complete detection → navigation pipeline
- **Professional Navigation**: Nav2 path planning and obstacle avoidance
- **Behavior Recovery**: Automatic recovery from stuck situations
- **Standards Compliance**: Using industry-standard Nav2 stack

## Launch Sequence Timeline
- 0s: Gazebo starts
- 5s: Robot spawns
- 8s: Robot State Publisher starts
- 9s: Transform publishers start
- 12s: YOLO detector starts
- 15s: Nav2 components start
- 16s: Lifecycle manager activates Nav2
- 20s: Bridge script connects YOLO to Nav2
- 21s+: Autonomous behavior active

## Auto-Shutdown Features
- **5-minute timer**: Automatic cleanup after UAT
- **User controls**:
  - `Enter`: Confirm UAT success, shutdown immediately
  - `e` + `Enter`: Extend timer by 5 minutes
  - `q` + `Enter`: Quit immediately

## Success Indicators
✅ Nav2 stack launches without errors
✅ YOLO detections trigger navigation goals
✅ Robot autonomously approaches the ball
✅ Robot stops at appropriate distance (~0.3m)
✅ Professional path planning visible
✅ Complete autonomous behavior loop works

## Next Steps
If this UAT passes, the core autonomous ball following system is complete! 
Potential enhancements (not required for success):
- Fine-tune approach distance
- Add multiple ball handling
- Implement collection behavior
- Add obstacle avoidance improvements

## Common Issues

### Issue: "Nav2 action server not found"
**Solution**: Wait for full 20 seconds for Nav2 to initialize, check lifecycle manager output

### Issue: Robot doesn't move after detection
**Solution**: Check transform chain is complete, verify /cmd_vel is being published

### Issue: "Transform error" in bridge script
**Solution**: Ensure all transform publishers are running, check `ros2 run tf2_tools view_frames`

### Issue: Robot moves but misses the ball
**Solution**: This is expected - approach distance tuning can be done later

## 🎯 UAT COMPLETE when:
1. Robot spawns successfully
2. YOLO detects the golf ball
3. Nav2 stack initializes without errors
4. Robot autonomously navigates toward the ball
5. Robot stops approximately 0.3m from the ball

This demonstrates a complete autonomous golf ball following system using professional ROS 2 components!
