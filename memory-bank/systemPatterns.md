# System Patterns - ChaseBot Architecture

## Overview
This document captures architectural patterns, design decisions, and system-level insights discovered during ChaseBot development.

## Core Architecture

### Vision Pipeline Architecture (VERIFIED WORKING)
```
D415 Camera → YOLO Detector → 3D Position Extractor → Direct Follower → Robot Control
     ↓              ↓                    ↓                   ↓              ↓
/d415/color/   /yolo/ball_   /yolo/ball_position_3d   Control Logic   /jetbot_base_
 image_raw      position                                               controller/cmd_vel
```

### Component Breakdown
1. **D415 Camera**: Publishes RGB and depth images
2. **YOLO Detector**: Detects balls (as frisbees) in 2D
3. **3D Position Extractor**: Converts 2D + depth to 3D coordinates
4. **Direct Follower**: Proportional control to approach ball
5. **Robot Control**: Executes movement commands

## Coordinate Frame Issues (CRITICAL)

### The Problem
Robot moves backwards because camera coordinates are used directly without proper transformation.

### Frame Definitions
- **Camera Frame (D415)**:
  - X: Right (positive = right of camera)
  - Y: Down (positive = below camera) 
  - Z: Forward (positive = away from camera)
  - Origin: Camera optical center

- **Robot Frame (JetBot)**:
  - X: Forward (positive = robot front)
  - Y: Left (positive = robot left)
  - Z: Up (positive = above robot)
  - Origin: Robot base center

### Current Bug
Direct use of camera coordinates causes:
- Ball ahead (camera +Z) → Robot backwards (negative linear velocity)
- Ball right (camera +X) → Robot turns wrong direction

### Attempted Fix (v2)
```python
# Attempted transformation
robot_x = camera_z  # Camera forward → Robot forward
robot_y = -camera_x # Camera right → Robot left (negated)
```
**Result**: Still backwards - transformation incomplete or incorrect

### Correct Transformation (Theory)
Need full rotation matrix considering:
1. Camera mounted angle relative to robot
2. Proper axis mapping
3. Sign conventions

## Direct Follower Pattern

### Proportional Control Implementation
```python
# Calculate errors
distance_error = distance_to_ball - approach_distance
angle_error = math.atan2(ball_y, ball_x)

# Apply proportional gains
linear_vel = linear_gain * distance_error
angular_vel = angular_gain * angle_error

# Apply limits
linear_vel = max(-max_linear, min(max_linear, linear_vel))
angular_vel = max(-max_angular, min(max_angular, angular_vel))
```

### Parameters That Work
- Approach Distance: 0.15m (15cm)
- Max Linear Speed: 0.2 m/s
- Max Angular Speed: 0.5 rad/s
- Linear Gain: 0.5
- Angular Gain: 2.0

## Nav2 Integration Challenges

### Lifecycle Manager Hanging
- **Symptom**: Hangs waiting for bt_navigator/get_state
- **Root Cause**: Missing behavior tree XML files or service timeout
- **Solutions Attempted**:
  1. Set bond_timeout to 0
  2. Manual component launch
  3. Direct lifecycle transitions
  4. Minimal controller testing

### Direct Follower as Alternative
Bypassed Nav2 complexity with direct proportional control:
- Simpler implementation
- Immediate results
- No lifecycle management
- Direct topic publishing

## Testing Patterns

### Successful Test Architecture
```python
# 1. Launch simulation with display
subprocess.Popen(["ros2", "launch", ...])

# 2. Start components in sequence
detector_proc = subprocess.Popen(["python3", "ros2_yolo_detector_headless.py"])
extractor_proc = subprocess.Popen(["python3", "yolo_3d_position_extractor.py"]) 
follower_proc = subprocess.Popen(["python3", "yolo_3d_direct_follower.py"])

# 3. Monitor and clean up
time.sleep(test_duration)
cleanup_all_processes()
```

### Display Configuration for WSL2
```python
# Auto-detect Windows host IP
result = subprocess.run(['powershell.exe', '-Command', 
    'Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*WSL*"} | Select-Object -First 1 -ExpandProperty IPAddress'],
    capture_output=True, text=True)
host_ip = result.stdout.strip()
env['DISPLAY'] = f"{host_ip}:0.0"
```

## Vision System Decisions

### YOLO vs ros2_vision_inference
**Selected**: YOLO + Custom Pipeline
- **Pros**: Full control, works immediately, easy to debug
- **Cons**: More code to maintain

**Alternative**: ros2_vision_inference
- **Pros**: Professional package, many features
- **Cons**: Model doesn't detect golf balls

### Headless Operation
Created headless versions by:
1. Removing cv2.imshow() calls
2. Removing cv2.waitKey() 
3. Keeping all detection logic
4. Perfect for WSL2 environments

## File Versioning Pattern
Adopted semantic versioning for all iterations:
- v1.0.0 - Initial implementation
- v1.1.0 - Minor improvements
- v2.0.0 - Major changes (coordinate fix attempt)

Never use ambiguous names like "fixed" or "corrected".

## Key Discoveries

### Simulation Quirks
1. Golf balls appear as "frisbee" (class 29) in YOLO
2. D415 camera topics use /d415/ prefix, not /camera/
3. Robot control topic is /jetbot_base_controller/cmd_vel

### Performance Insights
- YOLO detection: ~30 FPS
- 3D extraction: Negligible overhead
- Direct follower: Real-time response
- Complete pipeline: <50ms latency

### Debugging Tools
Essential diagnostic commands:
```bash
# Check detection
ros2 topic echo /yolo/ball_position

# Monitor 3D positions
ros2 topic echo /yolo/ball_position_3d

# Verify robot commands
ros2 topic echo /jetbot_base_controller/cmd_vel

# Camera data flow
ros2 topic hz /d415/color/image_raw
```

## Lessons Learned

### What Works
1. Direct control bypassing complex navigation stacks
2. Headless operation for development
3. Proportional control for smooth following
4. Thin slice development approach

### What Doesn't Work (Yet)
1. Direct camera coordinate usage (backwards motion)
2. Nav2 lifecycle management in simulation
3. ros2_vision_inference for golf balls

### Future Improvements
1. Fix coordinate transformation properly
2. Train YOLO specifically on golf balls
3. Debug Nav2 for advanced behaviors
4. Add obstacle avoidance
