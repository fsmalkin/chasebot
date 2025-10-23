# Slice 1 UAT: Basic Gazebo + Robot Spawn

## Overview
This is the first thin slice in our iterative launch file development. It establishes the foundation by spawning the JetBot in Gazebo with a working camera sensor.

## Purpose
- Verify basic Gazebo + robot integration
- Confirm camera sensor is publishing data
- Establish clean auto-shutdown pattern
- No navigation or detection - just basic spawn

## Launch Command
```bash
# From Windows (with VcXsrv running)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_basic_spawn.launch.py"
```

## UAT Success Criteria

### ✅ Primary Checks
1. **Gazebo Opens**: Window appears showing simulation world
2. **Robot Spawns**: JetBot appears at origin (0,0,0.05)
3. **Camera Visible**: Camera sensor mounted on robot front
4. **No Errors**: No RED error messages in terminal

### ✅ Secondary Verification
To verify camera is publishing:
```bash
# In a new terminal
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /camera/image_raw --once"
```

Expected output: Image message with data array (non-empty)

## Auto-Shutdown Features
- **5-minute timer**: Automatic cleanup after UAT
- **User controls**:
  - `Enter`: Confirm UAT success, shutdown immediately
  - `e` + `Enter`: Extend timer by 5 minutes
  - `q` + `Enter`: Quit immediately
- **Clean termination**: All processes properly killed

## What This Slice Does NOT Include
- ❌ Static transform publishers
- ❌ YOLO detection
- ❌ Nav2 stack
- ❌ Golf ball spawning
- ❌ Any autonomous behavior

## Common Issues

### Issue: "No module named 'chasebot_description'"
**Solution**: Rebuild workspace
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && colcon build --packages-select chasebot_description"
```

### Issue: "executable 'shutdown_manager.py' not found"
**Solution**: Make script executable
```bash
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/shutdown_manager.py"
```

### Issue: Gazebo window doesn't appear
**Solution**: Check VcXsrv is running with "Disable access control" checked

## Next Steps
Once this UAT passes:
- Slice 2: Add static transforms to fix transform tree
- Slice 3: Add YOLO detection
- Slice 4: Add Nav2 minimal
- Slice 5: Add bridge script

## Key Learnings
- Minimal foundation works without complex dependencies
- Auto-shutdown prevents process accumulation
- Clear UAT criteria enable quick validation
- Each slice builds confidence in the system
