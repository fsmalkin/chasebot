# Slice 1: RealSense Package Installation UAT

## Objective
Install and verify Intel RealSense ROS 2 packages for D415 camera support.

## Pre-conditions
- Ubuntu 22.04 with ROS 2 Humble installed
- WSL2 environment operational
- Internet connection for package download

## Test Steps

### Step 1: Install RealSense Packages
```bash
# In WSL2 Ubuntu-22.04
sudo apt update
sudo apt install ros-humble-realsense2-camera
sudo apt install ros-humble-realsense2-description
```

### Step 2: Verify Installation
```bash
# Check if packages are installed
ros2 pkg list | grep realsense2

# Expected output:
# realsense2_camera
# realsense2_camera_msgs
# realsense2_description
```

### Step 3: Check Package Executables
```bash
# Verify launch files exist
ls /opt/ros/humble/share/realsense2_camera/launch/

# Should see:
# - rs_launch.py
# - rs_multi_camera_launch.py
# - etc.
```

## Success Criteria
- ✅ Both realsense2_camera and realsense2_description packages appear in package list
- ✅ No installation errors or warnings
- ✅ Launch files are present in the correct location

## Troubleshooting

### If packages not found:
```bash
# Add ROS 2 apt repository if missing
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update
```

### If dependency errors:
```bash
# Install missing dependencies
sudo apt install ros-humble-image-transport
sudo apt install ros-humble-diagnostic-updater
```

## Notes
- These packages provide ROS 2 wrappers for Intel RealSense cameras
- Works with both real hardware and simulated cameras
- No actual D415 hardware needed for this slice

## Next Slice
Slice 2: D415 Standalone Test - Launch camera node and verify topics

## Related Documentation

> **📎 Implementation Plan**: [`docs/d415_implementation_plan.md`](../../docs/d415_implementation_plan.md)  
> **🔧 Maintenance**: If slice order changes, update:
> - Implementation plan (Slice 1 description)
> - Progress tracking checklist

> **📎 Next Slice**: [`slice2_d415_standalone_uat.md`](./slice2_d415_standalone_uat.md)  
> **🔧 Maintenance**: Update link if file renamed

> **📎 Progress Tracking**: [`memory-bank/progress.md`](../../memory-bank/progress.md)  
> **🔧 Maintenance**: Mark Slice 1 complete when UAT passes
