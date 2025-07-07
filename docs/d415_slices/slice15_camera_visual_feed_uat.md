# D415 Camera Visual Feed UAT

## Objective
Validate that the D415 camera sensor is working correctly by displaying the visual feed with golf ball detection overlays.

## Prerequisites
- ROS 2 Humble environment
- D415 camera integrated (v1.2.0 model)
- Display configured (X11 forwarding)
- Ignition Gazebo plugin path set

## Test Procedure

### Step 1: Prepare Environment
```bash
# Set up display
export DISPLAY=172.17.112.1:0.0

# Set up Ignition plugin path
export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib

# Source ROS 2
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
source install/setup.bash
```

### Step 2: Launch Simulation with Camera
```bash
# Terminal 1: Launch simulation
ros2 launch chasebot_sim jetbot_gz_control_camera_test.launch.py
```

Wait for:
- "Loaded system plugin" messages
- "[spawner-6] Configured and activated jetbot_base_controller"
- Test movement command execution

### Step 3: Verify Camera Topics
```bash
# Terminal 2: Check camera topics are available
ros2 topic list | grep d415

# Expected output:
# /d415/camera_info
# /d415/image_raw
```

### Step 4: Launch Camera Viewer
```bash
# Terminal 2: Run the D415 vision display
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/d415_vision_display.py
```

## Expected Results

### Success Criteria
1. ✅ Camera window opens showing "D415 Vision - Golf Ball Detection"
2. ✅ Live camera feed from robot's perspective is visible
3. ✅ Frame counter increments in top-left corner
4. ✅ When golf ball is in view:
   - Green bounding box appears around ball
   - "GOLF BALL" label shown
   - Area value displayed
   - Red center dot marks detection center
5. ✅ Terminal shows periodic frame processing logs (every 60 frames)
6. ✅ Pressing 'Q' cleanly closes the window and exits

### Visual Indicators
- **Frame Counter**: Shows continuous updates (top-left)
- **Detection Counter**: Increments when balls detected
- **Bounding Boxes**: Green rectangles around detected balls
- **Center Markers**: Red dots at ball centers
- **Area Values**: Pixel area shown below each detection

## Troubleshooting

### No Window Appears
- Check DISPLAY environment variable is set
- Verify X11 server (VcXsrv) is running on Windows
- Try: `export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0`

### Black/Empty Window
- Check if camera topics are being published: `ros2 topic hz /d415/image_raw`
- Verify simulation is running and robot spawned
- Check for camera sensor errors in simulation terminal

### No Ball Detection
- Move robot closer to golf ball (optimal: 1-3 meters)
- Check Gazebo lighting conditions
- Verify golf ball is white/bright in appearance
- Adjust detection thresholds if needed

### Window Freezes
- Check CPU usage - vision processing can be intensive
- Reduce camera update rate if needed
- Press 'Q' and restart viewer

## Quick Test Commands

```bash
# All-in-one test sequence (run in WSL2)
cd ~/ros2_ws && \
export DISPLAY=172.17.112.1:0.0 && \
export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib && \
source /opt/ros/humble/setup.bash && \
source install/setup.bash && \
echo "Starting simulation..." && \
ros2 launch chasebot_sim jetbot_gz_control_camera_test.launch.py &

# Wait 10 seconds for simulation to start
sleep 10

# Launch vision display
echo "Starting camera viewer..." && \
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/d415_vision_display.py
```

## Notes
- This uses HSV-based detection as a placeholder
- Will be replaced with YOLO detection when yolov8_ros is integrated
- Current detection works best with white golf balls under good lighting
- Camera resolution: 640x480 @ 30fps (D415 specs)
