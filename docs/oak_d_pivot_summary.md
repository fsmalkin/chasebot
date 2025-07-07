# OAK-D Lite Pivot Summary

## Date: January 6, 2025
## Status: New Direction for 3D Vision

## Executive Summary
After encountering a fundamental blocker with camera rendering in Ignition Gazebo, we've pivoted from Intel RealSense D415 to OAK-D Lite camera. This decision provides multiple advantages and a clearer path to implementation.

## The Camera Rendering Blocker
- **Issue**: Ignition Gazebo requires GPU/rendering context for camera sensors
- **Impact**: No camera data in our WSL2 environment despite correct configuration
- **Attempts**: Multiple approaches tried (display settings, bridges, launch configs)
- **Root Cause**: Architectural limitation of Ignition's camera implementation

## Why OAK-D Lite?
1. **Onboard AI Processing**
   - YOLO runs directly on camera's Myriad X VPU
   - 60-70% reduction in Jetson Nano CPU usage
   - No need for separate detection node

2. **Synthetic Data Support**
   - Industry standard approach for OAK cameras
   - Bypasses rendering requirements entirely
   - Easy transition from sim to hardware

3. **Better System Fit**
   - Lower power consumption (critical for battery life)
   - Single device for RGB + Depth + AI
   - Cost effective (~$149)

4. **Direct 3D Coordinates**
   - No coordinate transformation needed
   - Spatial detections in world coordinates
   - Eliminates source of previous bugs

## Implementation Strategy

### Simulation Approach
```python
# Synthetic OAK-D publisher mimics real camera
class OakDSyntheticPublisher:
    - Publishes RGB images (synthetic)
    - Publishes depth maps (synthetic)
    - Publishes 3D detections of golf balls
    - Same topic structure as real OAK-D
```

### Hardware Integration
- Use depthai-ros package
- Deploy YOLO as blob on VPU
- Direct spatial detection output
- Seamless swap from synthetic to real

## Benefits Over Previous Approaches

### vs 2D System
- True 3D positions (no transformation errors)
- Depth-based obstacle avoidance
- More accurate distance measurements

### vs RealSense D415
- Onboard processing (reduced CPU load)
- Better simulation support
- Lower power consumption
- Integrated AI pipeline

## Timeline Impact
- **Original D415 timeline**: 4 weeks (blocked)
- **OAK-D timeline**: 5 days to working system
- **Net gain**: Unblocked progress + better solution

## Key Technical Details
- **Camera**: OAK-D Lite
- **AI Chip**: Intel Myriad X VPU
- **ROS 2 Package**: depthai-ros
- **Detection**: YOLO running on VPU
- **Output**: Direct 3D world coordinates

## Next Steps
1. Create synthetic OAK-D publisher
2. Install depthai-ros packages
3. Convert YOLO to blob format
4. Test detection pipeline
5. Implement approach logic

## Lessons Learned
- Camera simulation in modern Gazebo has limitations
- Synthetic data approaches can bypass complex issues
- Onboard AI processing provides system-level benefits
- Sometimes a pivot leads to a better solution

## References
- [OAK-D Implementation Plan](oak_d_implementation_plan.md)
- [Camera Blocker Documentation](CRITICAL_GAZEBO_CAMERA_PLUGIN_BLOCKER.md)
- [depthai-ros GitHub](https://github.com/luxonis/depthai-ros)
