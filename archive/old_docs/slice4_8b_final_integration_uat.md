# Slice 4.8b UAT: Final Nav2 Integration with Odometry Publisher

## Test Objective
Complete the autonomous ball following system by integrating the proven odometry publisher into the Nav2 launch file, enabling actual robot movement toward detected golf balls.

## Prerequisites
- ROS 2 Humble installed in WSL2 (Ubuntu-22.04)
- Display forwarding configured (export DISPLAY=:0)
- All previous slices validated (YOLO detection, Nav2 stack, odometry publisher)
- ChaseBot workspace built

## Files to Deploy
Copy these files to WSL2:
```bash
# From Windows PowerShell in the project directory:
# Copy the new complete launch file
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_nav2_integration_complete.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/

# Ensure the odometry publisher is executable
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/simple_odom_publisher.py

# Rebuild the workspace
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && colcon build --packages-select chasebot_description"
```

## UAT Test Procedure

### Step 1: Clean Environment
```bash
# Terminate any existing processes
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2|yolo)' | grep -v grep"
# Note the PIDs and kill them: kill -9 [PID1] [PID2] etc.

# Source ROS 2
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash"
```

### Step 2: Launch Complete System
```bash
# Launch the complete autonomous system
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py"
```

### Step 3: System Startup Sequence Verification
Watch the console for these key milestones:
1. **0s**: Gazebo starts, robot spawns, ball placed at (2, 2)
2. **5s**: Static transforms established
3. **7s**: YOLO detector starts (detection window appears)
4. **8s**: Robot State Publisher starts
5. **10s**: Odometry Publisher starts ✨ KEY ADDITION
6. **15s**: Nav2 components start
7. **16s**: Lifecycle manager activates Nav2
8. **20s**: YOLO-to-Nav2 bridge starts

### Step 4: Verify Component Status
In a new terminal:
```bash
# Check all transforms are present (including odom->base_link)
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 run tf2_ros tf2_echo odom base_link"

# Verify Nav2 is receiving goals
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic echo /navigate_to_pose/goal --once"

# Monitor cmd_vel for movement commands
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic echo /cmd_vel"
```

### Step 5: Autonomous Ball Following Test

#### Expected Behavior:
1. **Ball Detection**: YOLO window shows green bounding box around ball
2. **Console Output**: "Ball detected at X=... Y=... (confidence: ...%)"
3. **Navigation Goal**: "Sending navigation goal to position..."
4. **Movement**: Robot should physically move toward the ball
5. **Continuous Following**: As robot approaches, new goals sent

#### Visual Confirmation in Gazebo:
- Robot starts at origin (0, 0)
- Ball is visible at (2, 2)
- Robot rotates to face ball
- Robot moves forward toward ball
- Robot stops near ball (within approach distance)

### Step 6: Manual Movement Test (Fallback)
If autonomous movement doesn't start:
```bash
# Send manual nav goal to verify Nav2 stack
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic pub --once /navigate_to_pose/goal geometry_msgs/PoseStamped '{header: {frame_id: odom}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}'"

# Send direct velocity command
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{linear: {x: 0.1}, angular: {z: 0.0}}'"
```

## Success Criteria
- [ ] All components launch without errors
- [ ] YOLO detects golf ball (bounding box visible)
- [ ] odom→base_link transform is publishing
- [ ] Navigation goals are sent to Nav2
- [ ] Robot physically moves in Gazebo
- [ ] Robot approaches the golf ball autonomously

## Troubleshooting
1. **No movement but goals sent**: Check `ros2 topic echo /cmd_vel` for velocity commands
2. **Transform errors**: Verify odometry publisher is running and publishing
3. **Nav2 not ready**: Wait full 20 seconds for all components to initialize
4. **YOLO not detecting**: Ensure ball is visible in camera view

## Result Documentation
```
Test Date: _______________
Tester: _________________
Result: [ ] PASS  [ ] FAIL

Observations:
- YOLO Detection Rate: _____%
- Navigation Goals Sent: Yes/No
- Robot Movement: Yes/No
- Approach Success: Yes/No

Notes:
_________________________________
_________________________________
_________________________________
```

## Next Steps on Success
- Document complete autonomous behavior
- Update memory bank with achievement
- Prepare for hardware deployment testing
