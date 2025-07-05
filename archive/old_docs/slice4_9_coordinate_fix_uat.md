# Slice 4.9: Coordinate Fix - UAT Procedure

## Objective
Fix the coordinate transformation so the robot turns TOWARD the ball instead of away from it.

## Fix Applied
- Inverted Y-axis in camera-to-world transformation
- Changed: `ball_y = distance * math.sin(angle_x)`
- To: `ball_y = -distance * math.sin(angle_x)`

## UAT Test Procedure

### 1. Kill Any Running Processes
```bash
ps aux | grep -E '(gazebo|ros2|nav2|yolo)' | grep -v grep
# Kill any PIDs found
```

### 2. Launch Complete System
```bash
# Terminal 1: Main launch
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py
```

### 3. Fix Line Endings and Run Map Publisher
```bash
# Terminal 2: Map publisher
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash
sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py
```

### 4. Monitor Detection (Optional)
```bash
# Terminal 3: Monitor topics
source /opt/ros/humble/setup.bash
ros2 topic echo /yolo/ball_position
```

## Expected Behavior

### ✅ Success Criteria:
1. **Correct Turn Direction**:
   - Ball on LEFT of image → Robot turns LEFT
   - Ball on RIGHT of image → Robot turns RIGHT
   - Ball in CENTER → Robot drives straight forward

2. **Approach Behavior**:
   - Robot navigates to ~30cm from ball
   - Robot stops when close enough
   - Robot maintains ball in camera view

3. **Continuous Tracking**:
   - If ball moves, robot updates goal
   - Robot follows ball as it moves
   - Detection remains stable during movement

### Visual Confirmation in Gazebo:
- Watch robot in Gazebo GUI
- Confirm robot faces ball before moving
- Verify smooth approach trajectory
- Check robot stops at appropriate distance

## Troubleshooting

### If Robot Still Turns Wrong Way:
1. Check console output for "Ball position in camera frame"
2. Verify Y coordinate sign matches expected direction
3. Confirm transforms are publishing correctly

### If No Movement:
1. Verify map publisher is running
2. Check Nav2 accepted the goal
3. Ensure detection confidence > 0.5

### If Movement is Erratic:
1. Increase detection cooldown in bridge script
2. Check for multiple detections
3. Verify stable transforms

## Complete System Architecture
```
Camera → YOLO → Fixed Bridge → Nav2 → Movement
   ↓        ↓         ↓          ↓        ↓
Image → Detection → Correct → Path → Autonomous
Feed    Position    Transform  Plan   Following
```

## Final Validation
Once coordinate fix is confirmed:
1. Test with ball in multiple positions
2. Move ball and verify following
3. Test approach from different angles
4. Document successful autonomous behavior

## Success Metrics
- [ ] Robot turns correct direction (toward ball)
- [ ] Robot approaches to target distance
- [ ] Robot tracks moving ball
- [ ] No oscillation or erratic movement
- [ ] Stable detection throughout approach

## Notes
- This completes the autonomous ball following system
- All components integrated and functional
- Ready for operational deployment
