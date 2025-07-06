# D415 Camera Integration - Step 4: RGBD Camera for Depth

## Overview
Upgrading the basic RGB camera to full RGBD (RGB + Depth) sensor to enable 3D position detection.

## Goal
Add depth sensing capability to match Intel RealSense D415 specifications, providing both color and depth images for 3D coordinate calculation.

## Implementation Plan

### 1. Update Sensor Type
- Change from `camera` to `rgbd_camera` sensor type
- Add depth camera configuration
- Configure proper depth range (0.16m - 10m for D415)

### 2. Key D415 Specifications
- **Depth Technology**: Active IR Stereo
- **Depth FOV**: 69.4° × 42.5° × 77° (H × V × D)
- **Depth Output Resolution**: 1280 × 720
- **Depth Range**: 0.16m - 10m
- **RGB Resolution**: 1920 × 1080 (we'll use 640×480 for performance)

### 3. Expected Topics
After upgrade:
- `/d415/image_raw` - RGB image (existing)
- `/d415/camera_info` - RGB camera info (existing)
- `/d415/depth/image_raw` - Depth image (NEW)
- `/d415/depth/camera_info` - Depth camera info (NEW)
- `/d415/points` - Point cloud (NEW, optional)

## Test Procedure

### 1. Model Update
Update `jetbot_core_ignition_v1.2.0.sdf` → `v2.0.0.sdf` (major change: sensor type)

### 2. Launch File Update
Add depth topic bridges:
- `/d415/depth/image_raw`
- `/d415/depth/camera_info`
- `/d415/points` (if needed)

### 3. Verification
```bash
# Check all camera topics
ros2 topic list | grep d415

# Expected output:
# /d415/camera_info
# /d415/image_raw
# /d415/depth/camera_info
# /d415/depth/image_raw
# /d415/points (optional)
```

## Success Criteria
- [ ] Robot spawns with RGBD sensor
- [ ] All 4 camera topics present (2 RGB + 2 depth)
- [ ] No sensor-related errors
- [ ] Optional: Point cloud topic available

## Benefits
- Direct 3D coordinates from depth data
- No complex coordinate transformations needed
- Compatible with yolov8_ros 3D detection
- Matches real D415 capabilities

## Next Steps
Once RGBD is working:
1. Test with yolov8_ros package
2. Configure for ball detection with depth
3. Get 3D positions directly from YOLO
