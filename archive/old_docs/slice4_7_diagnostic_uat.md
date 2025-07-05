# Slice 4.7 UAT: Nav2 Movement Diagnostics

## Overview
Diagnostic tool to identify why Nav2 accepts navigation goals but doesn't send cmd_vel commands to move the robot.

## What We Built
- **debug_nav2_movement.py**: Comprehensive Nav2 diagnostic tool that:
  - Monitors cmd_vel publishing
  - Checks odometry availability
  - Verifies transform chain completeness
  - Tests manual navigation goals
  - Provides clear status indicators

## Test Procedure

### Step 1: Deploy Files
```bash
sync_slice4_7_to_wsl.bat
```

### Step 2: Launch Nav2 Integration
In Terminal 1:
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.22.96.1:0.0 && ros2 launch chasebot_description jetbot_nav2_integration.launch.py"
```

Wait for:
- Gazebo to open with robot and golf ball
- "Managed nodes are active" message
- YOLO detection messages

### Step 3: Run Diagnostic Tool
In Terminal 2:
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run chasebot_description debug_nav2_movement.py"
```

## Expected Diagnostics

### Every 1 second, you should see:
```
=== Status Check ===
❌ CMD_VEL: Never received            # Problem indicator
✅ ODOM: Active (0.1s ago)           # Should be green
❌ TF map→odom: Could not find...    # Missing transform
❌ TF odom→base_link: Could not find # Critical missing link
✅ TF base_link→camera_link: OK      # Static transforms working
⚪ Navigation Goal: None active
```

### Every 5 seconds:
```
Sending test navigation goal: 0.5m forward in base_link frame
Test goal accepted!
```

## Key Diagnostic Insights

### 🔴 Critical Issues to Look For:
1. **No CMD_VEL**: If never received, Nav2 controller isn't publishing
2. **Missing TF odom→base_link**: This is likely the root cause
3. **Old transforms**: Timestamps > 1s indicate publishing issues

### 🟢 What Should Work:
1. ODOM topic should be active (from Gazebo)
2. Static transforms (base_link→camera_link) should be OK
3. Navigation goals should be accepted

## Next Steps Based on Results

### If odom→base_link transform is missing:
- **Root Cause**: No component is publishing this critical transform
- **Solution**: Add odometry publisher (Step 2 of implementation plan)

### If CMD_VEL never appears despite goals:
- **Root Cause**: Controller can't compute path without transforms
- **Solution**: Fix transform chain first

### If transforms are OK but no movement:
- **Root Cause**: Nav2 configuration issue
- **Solution**: Simplify Nav2 params (Step 3 of implementation plan)

## UAT Success Criteria

✅ **Diagnostic Success** when we can clearly identify:
1. Which transforms are missing
2. Whether cmd_vel is being published
3. Whether navigation goals are accepted
4. The specific point of failure in the Nav2 chain

This diagnostic step provides the data needed to implement the correct fix in the next step.

## Sample Output Analysis

```
❌ CMD_VEL: Never received
└─> Controller not publishing velocities

❌ TF odom→base_link: "base_link" passed to lookupTransform argument target_frame does not exist
└─> Critical transform missing - Nav2 can't track robot position

✅ Navigation Goal: ACTIVE
└─> Nav2 stack is trying to work but blocked by transform issues
