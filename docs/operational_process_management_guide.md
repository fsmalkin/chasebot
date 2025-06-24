# Operational Process Management Guide

**Purpose**: Prevent system freezing and ensure clean process management during ChaseBot development

## 🚨 Critical Process Management Commands

### Emergency Cleanup (When System Freezes)
```bash
# Aggressive process termination
sudo pkill -9 -f gazebo
sudo pkill -9 -f gzserver  
sudo pkill -9 -f gzclient
sudo pkill -9 -f ros

# Wait and verify cleanup
sleep 3
ps aux | grep -E '(gazebo|ros)' | grep -v grep || echo "All processes cleaned"
```

### Preventive Cleanup (Before Each Launch)
```bash
# Gentle cleanup first
pkill -f gazebo
pkill -f ros
sleep 2

# Verify no conflicts
netstat -tulpn | grep 11345 || echo "Gazebo port available"
```

### Process Monitoring
```bash
# Check active ROS/Gazebo processes
ps aux | grep -E '(gazebo|ros)' | grep -v grep

# Monitor system resources
top -p $(pgrep -d, -f "gazebo|ros")
```

## 📊 Data Streaming Optimization

### High-Frequency Logging Issues

**Problem**: Excessive logging causes system freezing
```
[python3-5] [INFO] [timestamp] [golf_ball_follower]: Following ball at (285, 380) area=4570.0
[python3-5] [INFO] [timestamp] [golf_ball_follower]: Following ball at (284, 381) area=4582.0
[python3-5] [INFO] [timestamp] [golf_ball_follower]: Following ball at (284, 381) area=4590.0
```

**Solution**: Reduce logging frequency in ball follower

### Gazebo Queue Warnings
```
[gazebo-1] [Wrn] [Publisher.cc:135] Queue limit reached for topic /gazebo/autonomous_golf_ball_world/pose/local/info
[gazebo-1] [Wrn] [Publisher.cc:135] Queue limit reached for topic /gazebo/autonomous_golf_ball_world/physics/contacts
```

**Action Required**: Implement logging throttling and queue management

### Optimized Logging Pattern
```python
# Instead of every detection:
self.get_logger().info(f'Following ball at ({x}, {y}) area={area}')

# Use throttled logging:
if self.log_counter % 10 == 0:  # Log every 10th detection
    self.get_logger().info(f'Following ball at ({x}, {y}) area={area}')
self.log_counter += 1
```

## 🛠️ Launch Protocol Best Practices

### Pre-Launch Checklist
1. **✅ Clean Environment**: Run preventive cleanup
2. **✅ Check Resources**: Verify system memory and CPU
3. **✅ Port Availability**: Ensure Gazebo ports are free
4. **✅ Workspace Sourced**: Source ROS 2 environment

### During Operation
1. **Monitor Logs**: Watch for queue warnings
2. **Track Performance**: Monitor system resource usage
3. **Early Termination**: Stop before system overload

### Post-Operation Cleanup
1. **Graceful Shutdown**: Use Ctrl+C first
2. **Wait Period**: Allow 5 seconds for cleanup
3. **Force Cleanup**: Use emergency commands if needed
4. **Verification**: Confirm all processes terminated

## 🎯 Performance Optimization Guidelines

### Logging Frequency Limits
- **Ball Detection**: Log every 10th detection (not every frame)
- **Movement Commands**: Log only on significant changes
- **System Status**: Log every 30 seconds maximum
- **Debug Info**: Disable in production runs

### Gazebo Resource Management
- **Physics Rate**: Standard 1000Hz (don't increase)
- **GUI Rendering**: Disable unnecessary visual effects
- **Contact Detection**: Limit to essential surfaces only
- **Sensor Publishing**: Reduce camera frame rate if needed

### ROS 2 Queue Management
```python
# Use appropriate QoS settings
qos_profile = QoSProfile(
    reliability=QoSReliabilityPolicy.RELIABLE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10  # Limit queue depth
)
```

## 🔄 Session Management Workflow

### Starting a Session
```bash
# 1. Clean slate
./scripts/emergency_cleanup.sh

# 2. Verify environment
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"

# 3. Source workspace
cd ~/ros2_ws && source install/setup.bash

# 4. Launch with monitoring
ros2 launch chasebot_description jetbot_autonomous_ball_following.launch.py
```

### Ending a Session
```bash
# 1. Graceful shutdown (Ctrl+C)
# 2. Wait for cleanup
sleep 5
# 3. Force cleanup if needed
sudo pkill -9 -f gazebo
# 4. Verify clean state
ps aux | grep -E '(gazebo|ros)' | grep -v grep
```

## 📋 Troubleshooting Common Issues

### "Address already in use" Error
```bash
# Find process using Gazebo port
sudo lsof -i :11345
# Kill specific process
sudo kill -9 <PID>
```

### System Freezing During Operation
```bash
# From another terminal
sudo pkill -9 -f gazebo
sudo pkill -9 -f ros
# May require system restart in severe cases
```

### Excessive Memory Usage
```bash
# Monitor memory usage
free -h
# Check specific processes
ps aux --sort=-%mem | head
```

### GUI Responsiveness Issues
```bash
# Launch headless mode
ros2 launch chasebot_description jetbot_autonomous_ball_following.launch.py headless:=true
```

## 🎯 Operational Success Patterns

### Working Session Example (December 24, 2025)
- **Duration**: ~20 minutes of autonomous operation
- **Behavior**: Multi-ball detection and sequential targeting
- **Termination**: System freeze during shutdown (expected)
- **Resolution**: Emergency cleanup successful

### Resource Usage Monitoring
- **Normal Operation**: Expect high CPU during vision processing
- **Warning Signs**: Queue limit warnings, memory exhaustion
- **Action Triggers**: System responsiveness degradation

## 📝 Session Documentation Template

```markdown
## Session Report: [Date]
**Duration**: [Start] - [End]
**Behavior Tested**: [Description]
**System Performance**: [CPU/Memory usage]
**Issues Encountered**: [List]
**Resolution**: [Actions taken]
**Lessons Learned**: [Key insights]
```

## 🔧 Automation Scripts

### Emergency Cleanup Script
Create `scripts/emergency_cleanup.sh`:
```bash
#!/bin/bash
echo "Emergency cleanup starting..."
sudo pkill -9 -f gazebo
sudo pkill -9 -f ros
sleep 3
echo "Processes cleaned. Verifying..."
ps aux | grep -E '(gazebo|ros)' | grep -v grep || echo "✅ All clean"
```

### Pre-Launch Check Script
Create `scripts/pre_launch_check.sh`:
```bash
#!/bin/bash
echo "Pre-launch environment check..."
# Check WSL status
wsl --list --verbose | grep Ubuntu-22.04
# Check ROS availability
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help" >/dev/null && echo "✅ ROS 2 available"
# Check port availability
netstat -tulpn | grep 11345 || echo "✅ Gazebo port available"
echo "Pre-launch check complete"
```

This operational guide should prevent the system freezing issues and make our development sessions much more reliable and efficient.
