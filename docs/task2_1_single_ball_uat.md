# Task 2.1 UAT Procedure: Transform Timing Fix with Single Ball Test

## Overview
This UAT validates the fix for transform timing errors while maintaining successful navigation to a single golf ball using **vision-based, map-free navigation**.

## Navigation Architecture
**CRITICAL**: ChaseBot uses direct vision-to-navigation without SLAM or mapping:
- YOLO detections are transformed directly to navigation goals
- No persistent maps are built or required
- Nav2 uses local costmaps for obstacle avoidance
- This approach is simpler and more robust for dynamic environments

## Prerequisites
1. **VcXsrv Running**: Launch VcXsrv with "Disable access control" checked
2. **WSL2 Active**: Ubuntu-22.04 instance running
3. **Working Directory**: `/mnt/c/workspaces/chasebot/`

## Important Note
**⚠️ AUTOMATED SCRIPT ISSUE**: The automated test runner (`run_single_ball_test.py`) has quote escaping issues when running from Windows. Use the manual steps below instead.

## Manual Test Execution Steps

### Step 1: Clean Any Existing Processes
```bash
# In Terminal 1
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws/src/chasebot_description && python3 ros2_scripts/kill_chasebot_processes.py"
```

### Step 2: Launch Gazebo with Empty World
```bash
# In Terminal 2
wsl -d Ubuntu-22.04
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
ros2 launch gazebo_ros gazebo.launch.py world:=~/ros2_ws/src/chasebot_description/ros2_config/worlds/single_ball_test.world
```
Wait for Gazebo to fully load (5-10 seconds)

### Step 3: Spawn the Robot
```bash
# In Terminal 3
wsl -d Ubuntu-22.04
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/src/chasebot_description/ros2_config/urdf/ros2_jetbot.urdf -entity jetbot -x 0 -y 0 -z 0.05
```
Verify robot appears in Gazebo

### Step 4: Static Transform Publisher (Optional - if Nav2 requires map frame)
```bash
# In Terminal 4
wsl -d Ubuntu-22.04
source /opt/ros/humble/setup.bash
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom
```
**Note**: Only needed if Nav2 complains about missing map frame. Creates identity transform map→odom.

### Step 5: Launch Nav2 Stack
```bash
# In Terminal 5
wsl -d Ubuntu-22.04
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true
```
Wait for "Managed nodes are active" message

### Step 6: Launch YOLO Detection
```bash
# In Terminal 6
wsl -d Ubuntu-22.04
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
ros2 launch yolov8_bringup yolov8.launch.py model:=yolov8m.pt input_image_topic:=/camera/image_raw device:=cpu
```
Wait for "YOLOv8m summary" message

### Step 7: Spawn Golf Ball (Visual Test Indicator)
```bash
# In Terminal 7
wsl -d Ubuntu-22.04
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0

# CRITICAL: Ball must be directly in front of robot for camera to see it!
# Create golf ball SDF
cat > /tmp/golf_ball.sdf << 'EOF'
<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="golf_ball">
    <pose>2.0 0.0 0.021 0 0 0</pose>
    <link name="link">
      <inertial>
        <mass>0.045</mass>
        <inertia>
          <ixx>1.5e-05</ixx>
          <iyy>1.5e-05</iyy>
          <izz>1.5e-05</izz>
        </inertia>
      </inertial>
      <collision name="collision">
        <geometry>
          <sphere>
            <radius>0.021</radius>
          </sphere>
        </geometry>
      </collision>
      <visual name="visual">
        <geometry>
          <sphere>
            <radius>0.021</radius>
          </sphere>
        </geometry>
        <material>
          <ambient>0.9 0.9 0.9 1</ambient>
          <diffuse>0.9 0.9 0.9 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>
EOF

# Spawn the ball DIRECTLY IN FRONT of robot (y=0.0 is critical!)
ros2 run gazebo_ros spawn_entity.py -file /tmp/golf_ball.sdf -entity golf_ball -x 2.0 -y 0.0 -z 0.021
```
**⛳ Golf ball appears = Testing begins!**

### Step 8: Launch YOLO-to-Nav2 Bridge
```bash
# In Terminal 8
wsl -d Ubuntu-22.04
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal.py
```

## Expected Timeline & Behavior

### Detection & Navigation
Within seconds of launching the bridge, you should see:
1. ✅ "Ball detected: sports ball" message with confidence
2. ✅ "Detection pixels: (X, Y)" with bbox size
3. ✅ "Estimated distance: X.XXm" 
4. ✅ "Ball position in camera frame: (X.XX, Y.YY)"
5. ✅ "Approach position in base_link: (X.XX, Y.YY)"
6. ✅ "Sending navigation goal to (X.XX, Y.YY)"
7. ✅ "Goal accepted by Nav2, navigating..."
8. ✅ Robot physically moves toward ball in Gazebo
9. ✅ Robot stops approximately 0.3m from ball
10. ✅ "Navigation succeeded! Reached the ball."

## UAT Success Indicators

### Primary Success (Transform Fix)
- ✅ **NO TRANSFORM ERRORS** in logs
- ✅ No "extrapolation" or timing-related errors
- ✅ Clean detection-to-navigation pipeline
- ✅ Robot successfully navigates to ball

### Secondary Success (System Health)
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
**Cause**: Nav2 requires a map frame but we're not using SLAM
**Solution**: 
1. Add the static transform publisher (Step 4) if not already running
2. Ensure the static publisher is running before launching Nav2
3. The static transform creates map→odom identity transform

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

## Test Cleanup
To stop all processes:
```bash
# Press Ctrl+C in each terminal, then run:
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws/src/chasebot_description && python3 ros2_scripts/kill_chasebot_processes.py"
```

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
