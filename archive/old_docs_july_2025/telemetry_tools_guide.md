# ChaseBot Telemetry Tools Guide

## Overview
These telemetry tools were created to help debug the coordinate transformation issue and provide visibility into what's happening during autonomous ball following. They also include a fallback solution that uses simplified navigation.

## Available Telemetry Tools

### 1. Navigation Telemetry (`navigation_telemetry.py`)
**Purpose**: Real-time monitoring dashboard for overall system state

**What it shows**:
- Robot position and velocity
- Ball detection status and confidence
- Navigation goals and status
- Distance to current goal
- Visual status indicators (🟢/🔴)

**Usage**:
```bash
# Run in separate terminal after launching main system
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/navigation_telemetry.py"
```

**Expected Output**:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                     CHASEBOT NAVIGATION TELEMETRY                            ║
║                        2025-07-04 23:15:00                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ROBOT STATE:                                                                 ║
║   Position: X= 0.000m  Y= 0.000m  Z= 0.000m                                ║
║   Velocity: Linear=0.000m/s  Angular=0.000rad/s                            ║
║                                                                              ║
║ BALL DETECTION:                                                              ║
║   Pixel Position: (0.500, 0.650) normalized                                 ║
║   Confidence: 85.0%                                                         ║
║   Detection Age: 0.1s ago                                                   ║
║                                                                              ║
║ NAVIGATION:                                                                  ║
║   Status: MOVING                                                            ║
║   Goal: X= 2.850m  Y= 0.000m                                              ║
║   Distance to Goal: 2.850m                                                  ║
║   Goal Age: 1.2s                                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
🟢 Ball Detected  🟢 Robot Moving
```

### 2. Coordinate Transformation Debugger (`coordinate_transformation_debug.py`)
**Purpose**: Step-by-step debugging of pixel-to-world coordinate conversion

**What it shows**:
- Normalized coordinates → Pixel coordinates conversion
- Camera intrinsics (focal length, principal point)
- Pixel → Camera ray calculation
- Transform lookups (camera and robot positions)
- Ground plane intersection calculation
- Final world position and navigation goal

**Usage**:
```bash
# Run after main system is launched
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/coordinate_transformation_debug.py"
```

**Expected Output**:
```
================================================================================
COORDINATE TRANSFORMATION DEBUG
================================================================================

1. NORMALIZED → PIXEL COORDINATES:
   Input (normalized): (0.5000, 0.6500)
   Image dimensions: 640 x 480
   Output (pixels): (320.0, 312.0)

2. CAMERA INTRINSICS:
   Focal length: fx=554.3, fy=554.3
   Principal point: cx=320.0, cy=240.0

3. PIXEL → CAMERA RAY:
   Unnormalized ray: (0.0000, 0.1299, 1.0000)
   Normalized ray: (0.0000, 0.1292, 0.9916)

4. TRANSFORM LOOKUP:
   Camera position in world: (0.100, 0.000, 0.120)
   Camera rotation: pitch=-10.0°, yaw=0.0°

5. GROUND PLANE INTERSECTION:
   Ground height: 0.020m
   Camera height: 0.120m
   Ray parameter t: 0.774m

6. WORLD POSITION CALCULATION:
   Ball world position: (0.867, 0.000, 0.020)

7. DISTANCE CALCULATIONS:
   Robot position: (0.000, 0.000)
   Distance to ball: 0.867m

8. NAVIGATION GOAL:
   Approach distance: 0.150m
   Goal position: (0.717, 0.000)
   Expected final distance: 0.150m

================================================================================
```

### 3. Visual Detection Overlay (`visual_detection_overlay.py`)
**Purpose**: Visual debugging overlay on camera feed

**What it shows**:
- Grid overlay (10% intervals) for reference
- Detection box around ball with confidence
- Normalized and pixel coordinates
- Color-coded confidence (Green >80%, Orange >60%, Red <60%)
- Info panel with detection status

**Usage**:
```bash
# Run after main system is launched
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/visual_detection_overlay.py"
```

**Output**: 
- Publishes annotated images to `/detection/overlay`
- Compressed images to `/detection/overlay/compressed`
- View in RViz2 or with `ros2 run rqt_image_view rqt_image_view`

### 4. Simple Direct Approach (`simple_direct_approach.py`)
**Purpose**: Fallback solution using simplified navigation

**Key Differences**:
- Assumes ball is at fixed distance (1.0m) when detected
- No complex coordinate transformations
- Uses only horizontal angle from camera center
- Direct calculation based on camera FOV

**Usage**:
```bash
# Use INSTEAD of the v2.0.0 bridge as a fallback
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/simple_direct_approach.py --ros-args -p use_sim_time:=true"
```

## Debugging Workflow

### 1. Initial System Launch
Launch the main system with the v2.0.0 bridge:
```bash
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py"
```

### 2. Start Telemetry Tools
In separate terminals:
```bash
# Terminal 1: Navigation telemetry
python3 navigation_telemetry.py

# Terminal 2: Coordinate debugger  
python3 coordinate_transformation_debug.py

# Terminal 3: Visual overlay (optional)
python3 visual_detection_overlay.py
```

### 3. What to Look For

**If coordinate transformation is working correctly**:
- Navigation telemetry shows reasonable goal positions
- Coordinate debugger shows ball position matching world file (3.0m)
- Robot navigates toward ball and stops at 0.15m

**If coordinate transformation has issues**:
- Ball world position doesn't match expected location
- Navigation goals are sent to wrong positions
- Robot moves but not toward ball

### 4. Fallback Solution
If v2.0.0 bridge has issues, try the simple approach:
```bash
# Kill the v2.0.0 bridge first
# Then launch simple approach
python3 simple_direct_approach.py --ros-args -p use_sim_time:=true
```

## Key Insights from Telemetry

### Navigation Telemetry Reveals:
- Whether YOLO is detecting the ball
- If navigation goals are being sent
- Robot's current state and movement
- How far robot thinks it is from goal

### Coordinate Debugger Reveals:
- Exact transformation steps
- Where calculations might go wrong
- Camera intrinsics being used
- Transform lookup success/failure

### Visual Overlay Reveals:
- Where in the image the ball is detected
- Detection consistency and confidence
- Whether detection position makes sense

## Potential Issues to Watch For

1. **Wrong Camera Intrinsics**: Check focal length values
2. **Transform Failures**: Camera or robot transform not available
3. **Ray Direction**: Ray pointing up instead of down
4. **Distance Calculation**: Ball appearing at wrong distance
5. **Navigation Rejection**: Goals being rejected by Nav2

## Next Steps
When you return:
1. Launch the system with telemetry tools
2. Observe the coordinate transformation process
3. Identify where the issue occurs
4. Try the fallback solution if needed
5. Consider switching to 3D camera if issues persist

The telemetry tools will give you complete visibility into what's happening, making it much easier to identify and fix the coordinate transformation issue.
