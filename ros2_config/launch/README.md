# ROS2 Launch Files Directory

## Overview
This directory contains all ROS2 launch files for the ChaseBot project. Launch files coordinate the startup of multiple nodes, configure parameters, and set up the simulation environment.

## File Inventory

### ✅ Active Launch Files

#### **jetbot_gz_control_camera_test_v3.launch.py**
- **Purpose**: Current primary launch file with Ignition Gazebo, camera, and control
- **Status**: ACTIVE - Use this for YOLO detection testing
- **Simulator**: Ignition Gazebo (Fortress)
- **Features**:
  - D415 camera with proper sensor plugin
  - gz_ros2_control for wheel control
  - Uses SDF model `jetbot_core_ignition_v1.3.0.sdf` ✅ **HAS WHEEL AXIS FIX**
  - World: `yolo_test_world_v4_white_forward.world`
- **Camera Topic**: `/d415/image_raw`
- **CRITICAL**: This launch file uses the FIXED SDF with proper wheel axis (Z-axis)

#### **jetbot_nav2_integration_complete.launch.py**
- **Purpose**: Full Nav2 stack integration with navigation
- **Status**: ACTIVE - Use for navigation testing
- **Features**:
  - Complete Nav2 stack
  - Map server with blank map
  - AMCL localization
  - Path planning
- **Note**: Requires separate vision nodes

#### **jetbot_gz_control_camera_test_v2.launch.py**
- **Purpose**: Previous version of camera test
- **Status**: ACTIVE - Still functional
- **Difference**: Uses older world configuration

### ❌ Deprecated Launch Files

#### **jetbot_with_yolo_clean_fixed.launch.py**
- **Purpose**: Old Classic Gazebo version with YOLO
- **Status**: DEPRECATED
- **Issue**: Uses Classic Gazebo (`gazebo` command), not Ignition
- **Historical Note**: This file previously detected green balls successfully

#### **jetbot_with_yolo_clean.launch.py**
- **Purpose**: Original YOLO integration attempt
- **Status**: DEPRECATED
- **Issue**: Various configuration problems

### 🧪 Experimental Launch Files

#### **camera_orientation_test.launch.py**
- **Purpose**: Test camera orientation fixes
- **Status**: EXPERIMENTAL

#### **jetbot_yolo_detection.launch.py**
- **Purpose**: Integrated YOLO detection launch
- **Status**: EXPERIMENTAL - Needs topic fix

## Launch File Categories

### Simulation Types
1. **Ignition Gazebo** (Current standard)
   - Files with `gz_` prefix
   - Use `ign gazebo` command
   - Better performance and features

2. **Classic Gazebo** (Legacy)
   - Older files without `gz_` prefix
   - Use `gazebo` command
   - Some may have better YOLO compatibility

### Feature Sets
1. **Basic Movement**: Simple spawning and control
2. **Camera Integration**: Includes D415 camera setup
3. **Navigation Stack**: Full Nav2 integration
4. **Vision Pipeline**: YOLO detection included

## Usage Examples

### Launch Simulation with Camera (Current Best)
```bash
export DISPLAY=172.25.128.1:0.0
ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py
```

### Launch with Navigation
```bash
ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py
```

### Test Camera Orientation
```bash
ros2 launch chasebot_sim camera_orientation_test.launch.py
```

## Common Parameters

### Robot Spawn Position
- Default: x=0.0, y=0.0, z=0.05
- Modify in spawn_entity node arguments

### World Files
- Location: `ros2_config/worlds/`
- Current: `yolo_test_world_v4_white_forward.world`

### Camera Configuration
- Topic: `/d415/image_raw`
- Frame: `jetbot/d415_camera_link/d415_rgb`
- Resolution: 640x480

## Changelog

### 2025-01-07
- Identified `jetbot_gz_control_camera_test_v3.launch.py` as primary
- Documented camera topic configuration
- Marked Classic Gazebo files as deprecated

### 2025-01-06
- Created v3 launch file with white ball world
- Fixed camera sensor plugin issues

### Previous
- Initial Ignition Gazebo migration
- Nav2 stack integration

## Troubleshooting

### No Camera Images
1. Check IGN_GAZEBO_SYSTEM_PLUGIN_PATH is set
2. Verify SDF has camera sensor plugin
3. Use `ros2 topic list | grep d415`

### Robot Not Moving
1. Check gz_ros2_control is loaded
2. Verify controller spawner succeeded
3. Test with: `ros2 topic pub /cmd_vel ...`

### YOLO Not Detecting
1. Ensure using Ignition-compatible launch file
2. Check camera topic matches YOLO subscription
3. Consider Classic Gazebo if texture issues persist

## Dependencies
- ROS2 Humble
- ros_gz_sim (Ignition-ROS bridge)
- gz_ros2_control
- Nav2 stack (for navigation launches)
