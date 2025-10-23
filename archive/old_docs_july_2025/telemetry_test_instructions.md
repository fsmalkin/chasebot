# ChaseBot Telemetry Test Instructions

## Issue Identified
The navigation telemetry is showing ball detection but the robot remains idle. This suggests the direct follower scripts aren't controlling the robot.

## Created Telemetry Tools

### 1. Direct Ball Follower with Telemetry
**File**: `ros2_scripts/direct_ball_follower_with_telemetry.py`
- Simple proportional control for ball following
- Real-time telemetry display showing:
  - Ball detection status
  - Robot velocity commands
  - Detection statistics

### 2. Direct Follower with 3D Visualization
**File**: `ros2_scripts/direct_follower_with_3d_viz.py`
- Same control logic with additional debug features:
  - Annotated camera view on `/debug/image_with_overlay`
  - 3D markers on `/visualization_markers`
  - Terminal telemetry

### 3. Navigation Telemetry (Monitoring Only)
**File**: `ros2_scripts/navigation_telemetry.py`
- Monitors system state but doesn't control robot
- Shows what's happening but doesn't make robot move

## Test Scripts Created

### Option 1: test_3d_follower.sh (RECOMMENDED)
```bash
./test_3d_follower.sh
```
This script:
- Kills ALL existing ROS processes
- Spawns basic robot without navigation stack
- Manually spawns golf ball
- Runs ONLY the direct follower with 3D visualization

### Option 2: Manual Testing
If the scripts aren't working, try manual testing:

```bash
# Terminal 1 - Kill everything first
wsl -d Ubuntu-22.04 bash -c "pkill -9 -f ros2; pkill -9 -f gazebo; pkill -9 -f navigation_telemetry"

# Terminal 2 - Basic robot spawn
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_basic_spawn.launch.py"

# Wait 15 seconds

# Terminal 3 - Spawn ball
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && ros2 run gazebo_ros spawn_entity.py -entity golf_ball -database golf_ball -x 3.0 -y 0.0 -z 0.05"

# Terminal 4 - Run direct follower
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_follower_with_3d_viz.py"
```

## Debugging Steps

1. **Check what's running**:
   ```bash
   wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(navigation_telemetry|yolo|ros2)'"
   ```

2. **Check topics**:
   ```bash
   wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"
   ```

3. **Monitor cmd_vel**:
   ```bash
   wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic echo /cmd_vel"
   ```

4. **View debug image** (in separate terminal):
   ```bash
   wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 run rqt_image_view rqt_image_view"
   ```
   Select `/debug/image_with_overlay` topic

## Key Points

1. **Navigation telemetry is monitoring only** - it shows ball detection but doesn't move robot
2. **Direct follower scripts control movement** - they detect ball AND send velocity commands
3. **Kill navigation_telemetry** if it's running - it might be started by a launch file
4. **Use basic_spawn** launch file - avoids Nav2 stack complexity

## Expected Behavior

When working correctly, you should see:
1. Terminal showing telemetry with status changing (APPROACHING, CENTERING, AT GOAL)
2. Robot moving toward the ball in Gazebo
3. Debug image showing bounding box around ball
4. Velocity commands being published to /cmd_vel

## If Robot Still Won't Move

1. Check if something else is publishing to /cmd_vel:
   ```bash
   wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic info /cmd_vel -v"
   ```

2. Try manual velocity command:
   ```bash
   wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic pub /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.2}}' --once"
   ```

3. Check robot controller status:
   ```bash
   wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 control list_controllers"
