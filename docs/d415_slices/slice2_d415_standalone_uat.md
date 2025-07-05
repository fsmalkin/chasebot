# Slice 2: D415 Standalone Test UAT

## Objective
Launch RealSense D415 node in simulation mode and verify camera topics are publishing.

## Pre-conditions
- Slice 1 completed (RealSense packages installed)
- Terminal with ROS 2 environment sourced

## Test Steps

### Step 1: Launch RealSense Node (Simulation Mode)
```bash
# Terminal 1: Launch camera
ros2 launch realsense2_camera rs_launch.py \
    enable_depth:=true \
    enable_color:=true \
    enable_infra:=false \
    initial_reset:=false \
    allow_no_texture_points:=true
```

Note: Without actual hardware, the node may show warnings but should still create topics.

### Step 2: Check Topics in New Terminal
```bash
# Terminal 2: List camera topics
ros2 topic list | grep camera

# Expected topics:
# /camera/color/camera_info
# /camera/color/image_raw
# /camera/depth/camera_info  
# /camera/depth/image_rect_raw
# /camera/aligned_depth_to_color/camera_info
# /camera/aligned_depth_to_color/image_raw
```

### Step 3: Verify Topic Publishing Rate
```bash
# Check RGB stream
ros2 topic hz /camera/color/image_raw

# Check depth stream  
ros2 topic hz /camera/depth/image_rect_raw

# Expected: Topics should show they exist (even if 0 Hz without hardware)
```

### Step 4: Check Message Types
```bash
# Verify correct message types
ros2 topic info /camera/color/image_raw
# Expected: Type: sensor_msgs/msg/Image

ros2 topic info /camera/depth/image_rect_raw  
# Expected: Type: sensor_msgs/msg/Image
```

## Success Criteria
- ✅ Camera node launches (warnings about no device OK)
- ✅ RGB topic `/camera/color/image_raw` exists
- ✅ Depth topic `/camera/depth/image_rect_raw` exists
- ✅ Topics are correct message type (sensor_msgs/msg/Image)

## Troubleshooting

### If node won't launch:
```bash
# Check for missing dependencies
ros2 doctor --report | grep realsense

# Try minimal launch
ros2 run realsense2_camera realsense2_camera_node
```

### If no topics appear:
```bash
# Source ROS 2 environment
source /opt/ros/humble/setup.bash

# Check node is running
ros2 node list | grep camera
```

## Notes
- In simulation mode, topics will exist but may not publish data
- This validates the RealSense ROS 2 integration is working
- Actual data will come when we add Gazebo depth plugin (Slice 3)

## Next Slice
Slice 3: Gazebo Depth Camera Plugin - Create depth camera in simulation
