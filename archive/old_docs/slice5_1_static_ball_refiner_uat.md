# Slice 5.1: Static Ball Refiner UAT

## Overview
**Minislice 1**: Enhanced static ball approach with periodic goal refinement and improved approach distance.

## Baseline vs Enhanced Comparison

### Previous System (Slice 4.9)
- **Approach Distance**: 0.3m (user feedback: "stopped way short")
- **Goal Strategy**: One-shot detection → single goal → navigate
- **Refinement**: None during navigation
- **Success**: Basic autonomous ball following achieved

### Enhanced System (Slice 5.1)
- **Approach Distance**: 0.25m (reduced by 5cm)
- **Goal Strategy**: Initial goal → periodic refinement every 3 seconds
- **Refinement**: Position-based updates during navigation
- **Enhancement**: Smoother, more accurate approach

## Key Improvements

### 1. Closer Approach Distance
- **Change**: Reduced from 0.3m to 0.25m
- **Benefit**: Robot gets closer to ball for better collection positioning
- **Parameter**: `self.approach_distance = 0.25`

### 2. Periodic Goal Refinement
- **Feature**: Re-evaluates ball position every 3 seconds during navigation
- **Threshold**: Only updates if position changes by >5cm
- **Limit**: Stops refining when within 0.5m of goal
- **Benefit**: Corrects for small detection variations and improves accuracy

### 3. Smart Update Logic
- **Position Change Check**: Prevents unnecessary goal updates
- **Distance Limiting**: Avoids refinement during final approach
- **Cooldown**: Prevents goal thrashing with 3-second intervals

## Test Environment Setup

### Manual File Sync (Required)
**NOTE**: Batch file sync approach abandoned due to reliability issues. Manual sync required.

**CRITICAL ISSUE DISCOVERED**: WSL path mapping from Git Bash doesn't work correctly. The commands below may fail with "No such file or directory" errors when run from Git Bash.

**WORKAROUND**: Use Command Prompt (cmd.exe) or PowerShell instead of Git Bash for WSL file operations.

```bash
# Method 1: Use Command Prompt (RECOMMENDED)
# Open Command Prompt and run:
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_static_ball_refiner.py ~/ros2_ws/src/chasebot_description/ros2_scripts/

wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_nav2_refined_approach.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/

# Method 2: Alternative - Direct WSL session
# Open WSL terminal directly and run:
cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_static_ball_refiner.py ~/ros2_ws/src/chasebot_description/ros2_scripts/
cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_nav2_refined_approach.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/

# Fix line endings and make executable
sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_static_ball_refiner.py
chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_static_ball_refiner.py

# Build workspace
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description
```

**PATH ISSUE SYMPTOMS**:
- Error: "cannot stat 'C:/Program Files/Git/mnt/c/..." 
- Error: "No such file or directory"
- Git Bash incorrectly prefixes paths with Git installation directory

**SOLUTION**: Always use Command Prompt, PowerShell, or direct WSL terminal for file operations.

### Launch Commands
```bash
# Terminal 1: Main system with enhanced refiner
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
ros2 launch chasebot_description jetbot_nav2_refined_approach.launch.py

# Terminal 2: Map publisher (if not auto-launching)
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash
sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py
```

### Prerequisites
- ✅ WSL2 Ubuntu-22.04 running
- ✅ VcXsrv running with proper display configuration
- ✅ All processes from previous tests terminated
- ✅ Fresh Gazebo environment
- ✅ **Manual file sync completed** (batch files unreliable)

## UAT Test Procedures

### Test 1: Basic Approach Distance Improvement
**Objective**: Verify robot approaches closer to ball than previous 0.3m distance.

**Procedure**:
1. Launch enhanced system with new refiner
2. Wait for "Started Static Ball Refiner" message
3. Place ball at coordinates (1.0, 0.0)
4. Observe robot approach behavior
5. Measure final stopping distance

**Success Criteria**:
- ✅ Robot stops at approximately 0.25m ± 0.05m from ball
- ✅ Final distance is noticeably closer than previous 0.3m
- ✅ Robot orientation faces the ball
- ✅ Navigation reports success

**Expected Log Messages**:
```
[static_ball_refiner]: Static Ball Refiner initialized
[static_ball_refiner]: Enhanced with 3.0s refinement interval
[static_ball_refiner]: Approach distance: 0.25m
[static_ball_refiner]: Initial ball detection: sports ball (confidence: 0.63, pixel position: XXX, XXX)
[static_ball_refiner]: Sending navigation goal to (X.XX, X.XX)
[static_ball_refiner]: Navigation succeeded! Reached the ball.
```

### Test 2: Periodic Goal Refinement
**Objective**: Verify goal refinement occurs during navigation for distant balls.

**Procedure**:
1. Launch enhanced system
2. Place ball at coordinates (2.0, 0.0) - further distance for longer navigation
3. Monitor terminal logs for refinement messages
4. Observe if multiple goals are sent during approach

**Success Criteria**:
- ✅ Initial goal sent immediately upon detection
- ✅ 1-2 refinement goals sent during navigation (every 3 seconds)
- ✅ Refinement stops when robot is within 0.5m of goal
- ✅ Robot successfully reaches ball

**Expected Log Messages**:
```
[static_ball_refiner]: Initial ball detection: sports ball (confidence: 0.XX, pixel position: XXX, XXX)
[static_ball_refiner]: Sending navigation goal to (X.XX, X.XX)
[static_ball_refiner]: Goal accepted by Nav2, navigating...
[static_ball_refiner]: Refining navigation goal (position change: 0.XXXm)
[static_ball_refiner]: Canceling current navigation goal
[static_ball_refiner]: Refined goal sent to (X.XX, X.XX)
[static_ball_refiner]: Navigation succeeded! Reached the ball.
```

### Test 3: No Oscillation Verification
**Objective**: Ensure refinement doesn't cause back-and-forth movement.

**Procedure**:
1. Launch enhanced system
2. Place ball at coordinates (1.5, 0.5) - angled position
3. Watch robot movement in Gazebo GUI
4. Verify smooth, direct approach path

**Success Criteria**:
- ✅ Robot follows smooth path toward ball
- ✅ No back-and-forth or oscillating movement
- ✅ Path updates are gradual and logical
- ✅ Final approach is direct and stable

**Expected Behavior**:
- Robot starts moving toward ball
- Any path corrections are smooth and minimal
- No rapid direction changes or stopping/starting
- Final approach is confident and direct

### Test 4: Position Change Threshold
**Objective**: Verify refinement only occurs for significant position changes.

**Procedure**:
1. Launch enhanced system
2. Place ball at coordinates (1.0, 0.0)
3. Monitor logs for position change messages
4. Observe if small detection variations trigger refinement

**Success Criteria**:
- ✅ Small position changes (<5cm) don't trigger refinement
- ✅ Log shows "Position change too small" debug messages
- ✅ Only significant changes trigger goal updates
- ✅ System is stable and doesn't over-refine

**Expected Log Messages**:
```
[static_ball_refiner]: Position change too small (0.02m), not refining
```

## Performance Metrics

### Quantitative Measures
- **Approach Distance**: Target 0.25m ± 0.05m
- **Refinement Frequency**: 1-2 updates per 2-meter approach
- **Success Rate**: 100% for static balls in open space
- **Navigation Time**: <30 seconds for 2-meter approach

### Qualitative Measures
- **Smoothness**: No oscillation or erratic movement
- **Precision**: Consistent final positioning
- **Reliability**: Repeatable behavior across multiple tests
- **Responsiveness**: Appropriate refinement timing

## Troubleshooting

### Common Issues
1. **No Refinement Occurring**: Check refinement timer and distance limits
2. **Excessive Refinement**: Verify position change threshold
3. **Navigation Failures**: Check Nav2 stack and transform tree
4. **Distance Measurement**: Verify final approach distance measurement

### Debug Commands
```bash
# Monitor refinement logic
ros2 topic echo /static_ball_refiner/parameter_events

# Check navigation feedback
ros2 topic echo /navigate_to_pose/_action/feedback

# Verify YOLO detections
ros2 topic echo /yolo/ball_position
ros2 topic echo /yolo/confidence
```

## Success Definition
**Minislice 1 Complete** when:
- ✅ Robot approaches ball to 0.25m (improvement from 0.3m)
- ✅ Periodic goal refinement works every 3 seconds
- ✅ No oscillation or erratic movement observed
- ✅ Position change threshold prevents over-refinement
- ✅ Navigation success rate remains 100% for static balls

## Next Steps
Upon successful UAT completion:
1. **Document Results**: Record actual vs expected measurements
2. **Update Memory Bank**: Capture refinement system lessons learned
3. **Prepare Minislice 2**: Visual servoing for final approach enhancement
4. **Consider Parameter Tuning**: Optimize refinement intervals based on performance
