# ChaseBot Quick Reference - Robot Control

## 🎯 Current Status: FULLY OPERATIONAL

### Launch Simulation
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib && ros2 launch chasebot_sim jetbot_gz_control_v3.0.0.launch.py"
```

### Send Velocity Commands (MUST use TwistStamped!)
```bash
# Single command
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic pub --once /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped '{twist: {linear: {x: 0.2}, angular: {z: 0.5}}}'"

# Continuous (3 seconds)
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && timeout 3 ros2 topic pub /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped '{twist: {linear: {x: 0.2}, angular: {z: 0.5}}}' --rate 10"
```

### Key Discovery
- ❌ WRONG: `geometry_msgs/msg/Twist`
- ✅ RIGHT: `geometry_msgs/msg/TwistStamped`
- Topic: `/jetbot_base_controller/cmd_vel` (NOT `/cmd_vel`)

### Test Robot Movement
```bash
# Copy test script to WSL2
powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/test_gz_controller_movement.py ~/ros2_ws/src/chasebot_sim/ros2_scripts/'"

# Run test
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_sim/ros2_scripts/test_gz_controller_movement.py"
```

### Common Commands
```bash
# List topics
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Check topic type
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic info -v /jetbot_base_controller/cmd_vel"

# Monitor joint states
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic echo /joint_states --once"
```

### Required Environment Variables
- `DISPLAY=172.25.128.1:0.0` (or your Windows IP)
- `IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib`

### Package Name
- **Current**: `chasebot_sim` (NOT `chasebot_description`)
- This was changed to fix gz_ros2_control plugin loading issue

### Key Files
- Launch: `ros2_config/launch/jetbot_gz_control_v3.0.0.launch.py`
- Config: `ros2_config/config/jetbot_controllers.yaml`
- SDF: `ros2_config/urdf/jetbot_core_ignition.sdf`
- Test: `ros2_scripts/test_gz_controller_movement.py`

### Next Steps
1. Add camera to robot model
2. Integrate D415 depth camera
3. Configure 3D object detection
4. Implement vision-based following

---
**Remember**: gz_ros2_control is fully working! Use TwistStamped messages on `/jetbot_base_controller/cmd_vel`
