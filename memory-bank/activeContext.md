# Active Context - ChaseBot Development

## Current Session: January 6, 2025

### Session Focus: OAK-D Lite Camera Integration 
**Status**: 🟢 NEW DIRECTION - Pivoting from blocked D415 to OAK-D Lite

#### Strategic Pivot (January 6, 2025):
After confirming the Ignition Gazebo camera rendering blocker, we're switching to OAK-D Lite which offers:
1. **Onboard AI Processing**: Runs YOLO directly on camera's Myriad X VPU
2. **Synthetic Data Support**: Standard practice for OAK cameras in simulation
3. **Lower Power**: Critical for JetBot's battery life
4. **Cost Effective**: ~$149 vs ~$250 for D415

#### Key Findings from D415 Investigation:
1. **GUI Display Working**: Successfully connected via VcXsrv with `DISPLAY=172.25.128.1:0.0`
2. **Robot Control Operational**: JetBot spawns with full control system in Ignition Gazebo v6.17.0
3. **Camera Rendering Blocked**: Ignition requires GPU context for camera sensors
4. **Topics Without Data**: Bridge configured but no images generated

#### New Technical Approach:
- **Camera**: OAK-D Lite with DepthAI
- **Simulation**: Synthetic data publisher (avoids rendering issues)
- **Processing**: YOLO runs on camera VPU (not Jetson)
- **Integration**: depthai-ros package for ROS 2

### OAK-D Implementation Strategy
1. Create synthetic OAK-D publisher for simulation
2. Deploy YOLO to camera's VPU using blob format
3. Bridge spatial detections directly to Nav2 goals
4. No coordinate transformation needed (3D world coords provided)

This approach eliminates both the rendering blocker and coordinate transformation complexity.

### Alternative Approaches to Consider:

#### Option 1: Return to 2D System with Better Coordinates
- The 2D YOLO system was working with corrected coordinate transformation
- Could refine the 2D approach further instead of requiring 3D
- Faster path to working solution

#### Option 2: Hardware-First Development
- Skip simulation for camera development
- Test D415 integration directly on physical JetBot
- Use recorded bag files for development

#### Option 3: Different Simulation Platform
- Migrate to Isaac Sim or Unity with better camera support
- Significant effort but guaranteed camera functionality

#### Option 4: Synthetic Camera Data
- Create node that publishes fake depth images for testing
- Allows YOLO 3D integration development to proceed
- Replace with real camera later

### Recommended Next Step:
Given the time spent on this blocker, recommend **Option 1**: Return to refining the 2D system that was already working. The coordinate transformation fix proved the 2D approach can achieve the required accuracy (15cm approach distance).

### Recent Command History:
```bash
# Working display configuration
export DISPLAY=172.25.128.1:0.0

# Launch with camera (topics created but no data)
ros2 launch chasebot_sim jetbot_gz_control_camera_test.launch.py

# Confirmed no data flowing
ros2 topic hz /d415/image_raw  # Hangs waiting for data
```

### Key Decisions Needed:
1. Continue fighting the camera rendering issue?
2. Pivot back to 2D system refinement?
3. Try alternative simulation platform?
4. Move to hardware-only development?

The core functionality (navigation, control, YOLO detection) is proven. Only the camera data generation in simulation remains blocked.
