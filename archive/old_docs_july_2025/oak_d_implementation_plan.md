# OAK-D Lite Implementation Plan (Accelerated Approach)

## Overview
This document outlines the accelerated implementation plan for integrating the OAK-D Lite 3D camera into ChaseBot, replacing both the problematic 2D vision system and the blocked RealSense D415 approach.

## Why OAK-D Lite?
1. **Onboard AI Processing**: Runs YOLO directly on camera (DepthAI)
2. **Better Simulation Support**: Synthetic data approach is standard practice
3. **Lower Power Consumption**: Critical for JetBot's limited battery
4. **Cost Effective**: ~$149 vs ~$250 for RealSense D415
5. **Proven ROS 2 Support**: depthai-ros package actively maintained

## Problem Statement
The current 2D vision system has a critical bug where YOLO's normalized pixel coordinates (0.0-1.0) are incorrectly treated as world coordinates in meters. Additionally, camera simulation in Ignition Gazebo requires rendering context that's problematic in our setup.

## Solution: OAK-D Lite + Synthetic Data for Simulation
The OAK-D Lite provides direct 3D world coordinates through onboard processing, eliminating coordinate transformation issues. For simulation, we'll use a synthetic data approach (standard practice for OAK cameras).

### Key Components:
1. **depthai-ros** - Official ROS 2 integration for OAK cameras
2. **Onboard YOLO** - Run detection directly on OAK-D's Myriad X VPU
3. **Synthetic Data Node** - Mock camera for simulation testing

## Implementation: Accelerated Thin Slices

### ✅ **FOUNDATION COMPLETE: Robot Control System** 
**Status**: ✅ **FULL SUCCESS** (January 6, 2025)
- gz_ros2_control working with differential drive
- Robot responds correctly to velocity commands
- Professional architecture ready for hardware deployment

### Slice 1: Create Synthetic OAK-D Node
**Single UAT**: Can we create a mock OAK-D that publishes synthetic data?

**Implementation**:
```python
# Create: oak_d_synthetic_publisher.py
import rclpy
from sensor_msgs.msg import Image, CameraInfo
from vision_msgs.msg import Detection3DArray, Detection3D
import numpy as np

class OakDSyntheticPublisher:
    def __init__(self):
        # Publish same topics as real OAK-D
        self.rgb_pub = self.create_publisher(Image, '/oak/rgb/image_raw', 10)
        self.depth_pub = self.create_publisher(Image, '/oak/depth/image_raw', 10)
        self.detection_pub = self.create_publisher(Detection3DArray, '/oak/detections', 10)
        
    def publish_synthetic_ball(self):
        # Create fake golf ball detection at known 3D position
        detection = Detection3D()
        detection.bbox.center.position.x = 2.0  # 2m forward
        detection.bbox.center.position.y = 0.0
        detection.bbox.center.position.z = 0.0
        detection.results[0].id = "golf_ball"
        detection.results[0].score = 0.95
```

**UAT Success Criteria**:
- ✓ Synthetic node publishes RGB/depth/detections
- ✓ Topics match real OAK-D format
- ✓ Can place balls at specific positions

---

### Slice 2: Install depthai-ros Package
**Single UAT**: Can we build the official OAK-D ROS 2 package?

**Implementation**:
```bash
# Install dependencies
sudo apt install ros-humble-depthai-ros
pip3 install depthai opencv-contrib-python

# Clone if needed for customization
cd ~/ros2_ws/src
git clone https://github.com/luxonis/depthai-ros.git
cd ~/ros2_ws
colcon build --packages-select depthai_ros_msgs depthai_bridge
```

**UAT Success Criteria**:
- ✓ Package builds without errors
- ✓ Example nodes available
- ✓ Documentation accessible

---

### Slice 3: Configure YOLO for Onboard Execution
**Single UAT**: Can we deploy YOLO to run on OAK-D's VPU?

**Implementation**:
```python
# Create: oak_d_yolo_golf_detector.py
import depthai as dai
import blobconverter

# Create pipeline
pipeline = dai.Pipeline()

# Configure YOLO for Myriad X
nn = pipeline.create(dai.node.YoloDetectionNetwork)
nn.setConfidenceThreshold(0.5)
nn.setNumClasses(1)  # Just golf balls
nn.setIouThreshold(0.5)

# Convert YOLO to blob format for VPU
blob_path = blobconverter.from_zoo(
    name="yolov8n_coco_640x352",  # Will customize for golf balls
    zoo_type="depthai"
)
nn.setBlobPath(blob_path)
```

**UAT Success Criteria**:
- ✓ YOLO model converts to blob format
- ✓ Deploys to OAK-D pipeline
- ✓ Runs at >10 FPS on VPU

---

### Slice 4: Create ROS 2 Bridge for OAK-D Pipeline
**Single UAT**: Can we publish OAK-D detections to ROS 2?

**Implementation**:
```python
# Create: oak_d_ros2_bridge.py
from depthai_ros_msgs.msg import SpatialDetectionArray
from geometry_msgs.msg import PoseStamped

class OakDROS2Bridge:
    def __init__(self):
        self.detection_sub = self.create_subscription(
            SpatialDetectionArray,
            '/oak/yolo/spatial_detections',
            self.detection_callback,
            10
        )
        self.goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        
    def detection_callback(self, msg):
        if msg.detections:
            # Get 3D position directly from OAK-D
            ball = msg.detections[0]
            goal = PoseStamped()
            goal.pose.position.x = ball.position.x
            goal.pose.position.y = ball.position.y
            goal.pose.position.z = ball.position.z
            self.goal_pub.publish(goal)
```

**UAT Success Criteria**:
- ✓ Bridge receives spatial detections
- ✓ Converts to Nav2 goals
- ✓ No coordinate transformation needed

---

### Slice 5: Test with Synthetic Data
**Single UAT**: Does the complete pipeline work with synthetic data?

**Implementation**:
```bash
# Terminal 1: Launch robot simulation
ros2 launch chasebot_sim jetbot_gz_control_gui.launch.py

# Terminal 2: Launch synthetic OAK-D
ros2 run chasebot_sim oak_d_synthetic_publisher.py

# Terminal 3: Launch detection bridge
ros2 run chasebot_sim oak_d_ros2_bridge.py

# Terminal 4: Verify robot moves toward synthetic ball
ros2 topic echo /goal_pose
```

**UAT Success Criteria**:
- ✓ Synthetic ball detected
- ✓ Goal published to Nav2
- ✓ Robot moves toward ball

---

### Slice 6: Implement Approach Distance Control
**Single UAT**: Can robot stop 15cm from ball?

**Implementation**:
```python
# In bridge, calculate approach point:
def calculate_approach_goal(self, ball_position):
    # Get robot position from TF
    robot_pos = self.get_robot_position()
    
    # Calculate approach vector
    dx = ball_position.x - robot_pos.x
    dy = ball_position.y - robot_pos.y
    distance = sqrt(dx*dx + dy*dy)
    
    # Stop 15cm before ball
    approach_distance = 0.15
    scale = (distance - approach_distance) / distance
    
    goal = PoseStamped()
    goal.pose.position.x = robot_pos.x + dx * scale
    goal.pose.position.y = robot_pos.y + dy * scale
    return goal
```

**UAT Success Criteria**:
- ✓ Robot stops 15cm from ball
- ✓ Works at various distances
- ✓ Handles edge cases

---

### Slice 7: Multi-Ball Detection Logic
**Single UAT**: Can system handle multiple balls?

**Implementation**:
```python
# Add ball selection strategy
def select_nearest_ball(self, detections):
    """Select closest ball based on 3D distance"""
    robot_pos = self.get_robot_position()
    
    nearest_ball = None
    min_distance = float('inf')
    
    for detection in detections:
        dist = self.calculate_3d_distance(robot_pos, detection.position)
        if dist < min_distance:
            min_distance = dist
            nearest_ball = detection
            
    return nearest_ball
```

**UAT Success Criteria**:
- ✓ Detects multiple balls
- ✓ Selects nearest
- ✓ Ignores collected balls

---

### Slice 8: Create Hardware Launch Configuration
**Single UAT**: Can we prepare for real OAK-D hardware?

**Implementation**:
```xml
<!-- oak_d_hardware.launch.py -->
<launch>
  <!-- OAK-D Camera Node -->
  <include file="$(find depthai_ros)/launch/camera.launch.py">
    <arg name="camera_model" value="OAK-D-LITE"/>
    <arg name="base_frame" value="oak_frame"/>
    <arg name="parent_frame" value="base_link"/>
    <arg name="cam_pos_x" value="0.1"/>  <!-- 10cm forward of base -->
  </include>
  
  <!-- YOLO Golf Ball Detector -->
  <node name="golf_detector" pkg="chasebot_sim" exec="oak_d_yolo_golf_detector.py">
    <param name="blob_path" value="$(find chasebot_sim)/models/golf_ball_yolov8.blob"/>
  </node>
  
  <!-- Detection to Nav2 Bridge -->
  <node name="oak_bridge" pkg="chasebot_sim" exec="oak_d_ros2_bridge.py"/>
</launch>
```

**UAT Success Criteria**:
- ✓ Launch file prepared
- ✓ Parameters configurable
- ✓ Ready for hardware test

---

### Slice 9: Complete System Integration Test
**Single UAT**: Does full system work end-to-end?

**Implementation**:
```bash
# Single launch for complete system
ros2 launch chasebot_sim oak_d_ball_following_sim.launch.py

# Should include:
# - Robot simulation
# - Synthetic OAK-D (or real in hardware mode)
# - Detection pipeline
# - Nav2 integration
```

**UAT Success Criteria**:
- ✓ Single command launch
- ✓ Autonomous ball following
- ✓ Smooth transitions sim/hardware

---

### Slice 10: Documentation and Deployment Prep
**Single UAT**: Is system ready for real-world deployment?

**Implementation**:
1. Create operation manual
2. Document synthetic/real switch
3. Prepare hardware checklist
4. Archive old 2D/D415 code

**UAT Success Criteria**:
- ✓ Clear setup instructions
- ✓ Hardware requirements documented
- ✓ Troubleshooting guide ready

## File Structure

```
ros2_scripts/
├── oak_d_synthetic_publisher.py      # Simulation mock camera
├── oak_d_yolo_golf_detector.py      # Onboard YOLO deployment
├── oak_d_ros2_bridge.py             # Detection to Nav2 bridge
└── oak_d_hardware_test.py           # Hardware validation

ros2_config/
├── models/
│   └── golf_ball_yolov8.blob       # VPU-optimized model
└── launch/
    ├── oak_d_ball_following_sim.launch.py   # Simulation
    └── oak_d_ball_following_hw.launch.py    # Hardware

archive/
└── old_cameras/
    ├── d415_attempts/               # RealSense attempts
    └── 2d_vision/                   # Original 2D system
```

## Dependencies

### System Packages
```bash
# OAK-D Support
sudo apt install ros-humble-depthai-ros
sudo apt install ros-humble-depthai-ros-msgs
sudo apt install ros-humble-vision-msgs

# Python packages
pip3 install depthai
pip3 install opencv-contrib-python
pip3 install blobconverter
```

### Key Differences from D415
1. **No coordinate transformation** - OAK-D provides world coordinates directly
2. **Onboard processing** - Reduces Jetson Nano load by 60-70%
3. **Synthetic simulation** - Standard practice for OAK cameras
4. **Single device solution** - RGB + Depth + AI in one package

## Success Metrics

1. **Processing Efficiency**: >60% reduction in Jetson CPU usage
2. **Detection Accuracy**: 3D positions within ±5cm
3. **Approach Precision**: Robot stops within 15cm ±5cm
4. **System Reliability**: >95% successful approaches
5. **Frame Rate**: >15 FPS with onboard processing
6. **Power Consumption**: <3W total (vs 4.5W for D415 + Jetson processing)

## Timeline

- **Day 1**: Synthetic publisher and basic pipeline
- **Day 2**: YOLO deployment to VPU
- **Day 3**: ROS 2 integration and testing
- **Day 4**: Multi-ball logic and refinement
- **Day 5**: Hardware prep and documentation

**Total: 5 days to working system**

## Conclusion

The OAK-D Lite solves multiple problems at once:
- Eliminates coordinate transformation complexity
- Reduces computational load on Jetson Nano
- Provides a clear simulation strategy
- Offers future expansion (onboard AI for other tasks)

The synthetic data approach for simulation is industry-standard for OAK cameras and avoids the rendering issues we encountered with Ignition Gazebo cameras.
