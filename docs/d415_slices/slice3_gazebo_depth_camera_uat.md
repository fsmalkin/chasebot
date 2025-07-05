# Slice 3: Gazebo Depth Camera Plugin UAT

## Objective
Create and test a simple depth camera in Gazebo to validate depth plugin functionality.

## Pre-conditions
- ROS 2 Humble and Gazebo installed
- Display configured (VcXsrv or similar for WSL2)

## Test Steps

### Step 1: Create Minimal Depth Camera Test World
```xml
<!-- File: test_depth_camera.world -->
<?xml version="1.0"?>
<sdf version="1.6">
  <world name="depth_test">
    <include>
      <uri>model://ground_plane</uri>
    </include>
    
    <include>
      <uri>model://sun</uri>
    </include>
    
    <!-- Test box at known distance -->
    <model name="test_box">
      <pose>3 0 0.5 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <geometry>
            <box>
              <size>1 1 1</size>
            </box>
          </geometry>
        </collision>
        <visual name="visual">
          <geometry>
            <box>
              <size>1 1 1</size>
            </box>
          </geometry>
        </visual>
      </link>
    </model>
    
    <!-- Static depth camera -->
    <model name="depth_camera">
      <static>true</static>
      <pose>0 0 1 0 0 0</pose>
      <link name="link">
        <sensor name="depth_camera" type="depth">
          <camera>
            <horizontal_fov>1.047</horizontal_fov>
            <image>
              <width>640</width>
              <height>480</height>
            </image>
            <clip>
              <near>0.1</near>
              <far>10</far>
            </clip>
          </camera>
          <plugin name="camera_plugin" filename="libgazebo_ros_camera.so">
            <ros>
              <namespace>/test</namespace>
              <remapping>~/image_raw:=depth/image_raw</remapping>
              <remapping>~/camera_info:=depth/camera_info</remapping>
            </ros>
            <camera_name>depth_camera</camera_name>
            <frame_name>depth_frame</frame_name>
          </plugin>
        </sensor>
      </link>
    </model>
  </world>
</sdf>
```

### Step 2: Launch Gazebo with Test World
```bash
# Terminal 1: Launch Gazebo
gazebo test_depth_camera.world --verbose
```

### Step 3: Verify Depth Topics
```bash
# Terminal 2: Check topics
ros2 topic list | grep test

# Expected:
# /test/depth/camera_info
# /test/depth/image_raw
```

### Step 4: Visualize in RViz2
```bash
# Terminal 3: Launch RViz2
rviz2

# In RViz2:
# 1. Add Image display
# 2. Set topic to /test/depth/image_raw
# 3. Should see depth gradient (darker = closer)
```

### Step 5: Echo Depth Values
```bash
# Simple Python script to check depth values
python3 -c "
import rclpy
from sensor_msgs.msg import Image
import numpy as np

def callback(msg):
    # Convert to numpy array
    depth = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)
    center = depth[msg.height//2, msg.width//2]
    print(f'Center depth: {center:.2f}m')

rclpy.init()
node = rclpy.create_node('depth_test')
sub = node.create_subscription(Image, '/test/depth/image_raw', callback, 10)
rclpy.spin_once(node, timeout_sec=1.0)
"
```

## Success Criteria
- ✅ Gazebo launches without errors
- ✅ Depth camera topics appear
- ✅ Depth image visible in RViz2
- ✅ Box at 3m shows ~3m depth value at center
- ✅ Depth values change across image (not uniform)

## Troubleshooting

### If Gazebo won't launch:
```bash
# Kill any existing Gazebo processes
pkill -9 gazebo
pkill -9 gzserver
pkill -9 gzclient

# Check display
echo $DISPLAY
export DISPLAY=:0
```

### If no depth data:
```bash
# Check Gazebo plugin is loaded
gz topic -l | grep depth

# Try different plugin
# Change libgazebo_ros_camera.so to libgazebo_ros_depth_camera.so
```

## Notes
- This validates Gazebo depth camera functionality
- Depth values should correspond to actual distances
- The plugin provides both RGB and depth from same sensor

## Next Slice
Slice 4: D415 in Robot URDF - Add D415 model to JetBot
