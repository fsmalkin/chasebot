# New Gazebo (Ignition Fortress) Migration Plan

## Date: January 5, 2025
## Status: STARTING MIGRATION
## Priority: TOP PRIORITY - Unblocks all 3D vision development

## Migration Rationale

### Gazebo Classic Issues Discovered
1. **Camera plugins don't publish ROS 2 topics** - Fundamental incompatibility
2. **EOL timing** - Gazebo Classic reaches end-of-life January 2025
3. **Limited ROS 2 support** - Known community issue with Humble integration
4. **Time sink** - Could spend weeks debugging unfixable issues

### New Gazebo Benefits
- **Native ROS 2 support** - Designed for modern robotics
- **Active development** - Future-proof choice
- **Better sensors** - Improved camera and depth sensor simulation
- **Modern architecture** - More efficient and stable

## Migration Strategy

### Phase 1: Installation (Day 1)

#### Step 1: Remove Gazebo Classic Conflicts
```bash
# Stop any running Gazebo processes
pkill -f gazebo

# Remove conflicting packages (optional, can coexist)
# sudo apt remove gazebo11 gazebo11-* (only if conflicts arise)
```

#### Step 2: Install Ignition Fortress
```bash
# Add Ignition repository
sudo wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

# Update and install
sudo apt update
sudo apt install ignition-fortress

# Install ROS 2 integration
sudo apt install ros-humble-ros-gz-bridge ros-humble-ros-gz-sim ros-humble-ros-gz-image
```

#### Step 3: Verify Installation
```bash
# Check Ignition version
ign gazebo --version

# Test launch
ign gazebo empty.sdf
```

### Phase 2: World File Conversion (Day 1)

#### Step 1: Convert SDF Format
Old Gazebo Classic world files need minor updates for New Gazebo:

**Example conversion for camera:**
```xml
<!-- Old Gazebo Classic -->
<plugin name="camera_controller" filename="libgazebo_ros_camera.so">
  ...
</plugin>

<!-- New Gazebo (Ignition) -->
<plugin filename="ignition-gazebo-sensors-system" name="ignition::gazebo::systems::Sensors">
  <render_engine>ogre2</render_engine>
</plugin>
```

#### Step 2: Create Test World
Create `test_ignition_camera.sdf`:
```xml
<?xml version="1.0"?>
<sdf version="1.8">
  <world name="camera_test">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    
    <plugin filename="ignition-gazebo-physics-system" name="ignition::gazebo::systems::Physics"></plugin>
    <plugin filename="ignition-gazebo-sensors-system" name="ignition::gazebo::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>1 1 1 1</diffuse>
      <specular>0.5 0.5 0.5 1</specular>
      <attenuation>
        <range>1000</range>
      </attenuation>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry>
            <plane>
              <normal>0 0 1</normal>
              <size>100 100</size>
            </plane>
          </geometry>
        </collision>
        <visual name="visual">
          <geometry>
            <plane>
              <normal>0 0 1</normal>
              <size>100 100</size>
            </plane>
          </geometry>
          <material>
            <ambient>0.8 0.8 0.8 1</ambient>
            <diffuse>0.8 0.8 0.8 1</diffuse>
            <specular>0.8 0.8 0.8 1</specular>
          </material>
        </visual>
      </link>
    </model>
    
    <!-- Test camera -->
    <model name="camera">
      <static>true</static>
      <pose>0 0 1 0 0 0</pose>
      <link name="camera_link">
        <sensor name="camera" type="camera">
          <camera>
            <horizontal_fov>1.047</horizontal_fov>
            <image>
              <width>640</width>
              <height>480</height>
            </image>
            <clip>
              <near>0.1</near>
              <far>100</far>
            </clip>
          </camera>
          <always_on>1</always_on>
          <update_rate>30</update_rate>
          <visualize>true</visualize>
          <topic>camera</topic>
        </sensor>
      </link>
    </model>
  </world>
</sdf>
```

### Phase 3: ROS 2 Integration (Day 1-2)

#### Step 1: Launch with ROS 2 Bridge
```bash
# Terminal 1: Launch Ignition
ign gazebo test_ignition_camera.sdf

# Terminal 2: Launch ROS 2 bridge for camera
ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@ignition.msgs.Image

# Terminal 3: Verify topics
ros2 topic list
ros2 topic echo /camera
```

#### Step 2: Create Launch File
`ignition_camera_test.launch.py`:
```python
from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Launch Ignition Gazebo
        ExecuteProcess(
            cmd=['ign', 'gazebo', 'test_ignition_camera.sdf'],
            output='screen'
        ),
        
        # Bridge camera topics
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            arguments=['/camera@sensor_msgs/msg/Image@ignition.msgs.Image'],
            output='screen'
        ),
    ])
```

### Phase 4: D415 Camera Integration (Day 2)

#### Step 1: Create D415 Model
Create accurate D415 depth camera model with RGB-D capabilities

#### Step 2: Test with YOLO
Integrate with yolov8_ros package for 3D detection

#### Step 3: Validate Performance
Ensure 30Hz publishing rate and accurate depth data

## Success Criteria

1. ✅ Camera topics visible in `ros2 topic list`
2. ✅ Image data publishing at 30Hz
3. ✅ Depth data available for 3D position calculation
4. ✅ Can visualize in RViz2
5. ✅ YOLO detection works with camera feed

## Timeline

- **Day 1**: Installation, basic camera test
- **Day 2**: D415 model, YOLO integration
- **Total**: 1-2 days to unblock 3D vision development

## Commands Reference

### Installation Check
```bash
# Version
ign gazebo --version

# Available topics in simulation
ign topic -l

# Echo camera data
ign topic -e -t /camera
```

### ROS 2 Bridge
```bash
# List available bridges
ros2 run ros_gz_bridge parameter_bridge --help

# Bridge multiple topics
ros2 run ros_gz_bridge parameter_bridge \
  /camera@sensor_msgs/msg/Image@ignition.msgs.Image \
  /camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo
```

## Rollback Plan

If issues arise:
1. New Gazebo can coexist with Gazebo Classic
2. Can continue using Classic for non-camera features
3. Alternative: Skip to hardware testing

## Next Steps

1. Start installation process
2. Create test camera world
3. Verify ROS 2 bridge functionality
4. Proceed with D415 integration

---

**Note**: This migration is critical to unblock all 3D vision work. Gazebo Classic has reached EOL and camera plugins are incompatible with ROS 2 Humble.
