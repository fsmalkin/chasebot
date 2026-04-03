# ChaseBot 3D Vision Pipeline: yolo_ros Integration Plan

## Overview
This document details the integration of mgonzs13/yolo_ros package for 3D object detection in ChaseBot. Following our "Search Existing Solutions First" principle, we're adopting this proven package (739 stars) instead of building custom solutions.

## Package Selection Rationale

### Why mgonzs13/yolo_ros?
- **3D Detection Built-in**: Already supports RGB-D cameras for 3D object positions
- **Active Development**: Last update 17 days ago, regular releases
- **ROS 2 Humble Support**: Compatible with our environment
- **Standard Messages**: Uses vision_msgs for interoperability
- **Lifecycle Nodes**: Efficient resource management
- **Community**: 739 stars, 167 forks, multiple contributors

### Alternative Packages Considered
- andreasHovaldt/yolov8_ros2: Specific to RealSense but less features
- TensorRT_YOLO_ROS2: More complex, requires TensorRT
- detect_3d_object: Limited documentation

## Implementation Plan: 7 Thin Slices

### Slice 1: Package Installation & Basic Validation
**Objective**: Get yolo_ros installed and verify basic functionality

**Steps**:
```bash
# Clone package
cd ~/ros2_ws/src
git clone https://github.com/mgonzs13/yolo_ros.git

# Install Python dependencies
pip3 install -r yolo_ros/requirements.txt

# Build
cd ~/ros2_ws
colcon build --packages-select yolo_msgs yolo_ros yolo_bringup
```

**UAT Criteria**:
- Package builds without errors
- Can run: `ros2 launch yolo_bringup yolo.launch.py`
- Node starts and waits for images

**Isolation Test**: Launch with dummy model to verify node lifecycle

---

### Slice 2: Connect to D415 Camera (2D Only)
**Objective**: Connect yolo_ros to our D415 RGB stream

**Configuration**:
```python
# Launch parameters
'input_image_topic': '/d415/image_raw',
'model': 'yolov8m.pt',  # Same model we already have
'threshold': 0.5,
'device': 'cpu',  # Start with CPU
'use_3d': False,  # 2D only first
```

**UAT Criteria**:
- yolo_ros receives D415 images
- `/yolo/detections` topic publishes data
- `/yolo/debug_image` shows bounding boxes
- Golf balls detected (class 32: sports ball)

**Verification Command**:
```bash
ros2 topic echo /yolo/detections --once
```

---

### Slice 3: Enable 3D Detection with Depth
**Objective**: Add depth processing for 3D positions

**Configuration Changes**:
```python
'use_3d': True,
'input_depth_topic': '/d415/depth/image_raw',
'input_depth_info_topic': '/d415/depth/camera_info',
'target_frame': 'base_link',
'depth_image_units_divisor': 1000,  # mm to meters
```

**UAT Criteria**:
- `/yolo/detections_3d` topic active
- 3D positions not NaN
- Positions in base_link frame
- Z-coordinate reasonable (>0, <10m)

**Debug Tool** (if needed):
```python
# Simple 3D position logger
def callback(msg):
    for det in msg.detections:
        pos = det.bbox.center.position
        print(f"Ball at: x={pos.x:.2f}, y={pos.y:.2f}, z={pos.z:.2f}")
```

---

### Slice 4: Validate 3D Accuracy
**Objective**: Ensure 3D positions match reality

**Test Setup**:
- Place ball at known position (3m forward)
- Robot stationary at origin
- Compare detected vs actual position

**UAT Criteria**:
- Ball at 3m detected within ±10cm
- Position updates as robot moves
- Consistent detection across frames

**Validation Script**:
```python
# Compare detected position to ground truth
expected = {'x': 3.0, 'y': 0.0, 'z': 0.02}
tolerance = 0.1  # 10cm
```

---

### Slice 5: Navigation Bridge (Minimal)
**Objective**: Send detected ball to Nav2

**Bridge Implementation**:
```python
#!/usr/bin/env python3
"""Minimal bridge from yolo_ros to Nav2"""

class YoloToNav2Bridge:
    def __init__(self):
        # Subscribe to 3D detections
        self.sub = self.create_subscription(
            Detection3DArray,
            '/yolo/detections_3d',
            self.detection_callback,
            10
        )
        
        # Publish navigation goals
        self.nav_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose'
        )
    
    def detection_callback(self, msg):
        if msg.detections:
            # Get closest ball
            ball = msg.detections[0]
            self.send_nav_goal(ball)
```

**UAT Criteria**:
- Nav2 receives goal
- Robot starts moving
- Movement toward ball

---

### Slice 6: Approach Distance Tuning
**Objective**: Stop 3 inches (7.62cm) from ball

**Approach Calculation**:
```python
APPROACH_DISTANCE = 0.0762  # 3 inches

# Calculate approach position
direction = np.array([ball.x, ball.y]) 
direction = direction / np.linalg.norm(direction)
approach_pos = ball_pos - direction * APPROACH_DISTANCE
```

**UAT Criteria**:
- Robot stops 7.62cm ± 1cm from ball
- Consistent across 5 runs
- No collision with ball

**Measurement Method**:
- Use simulation ruler tool
- Log final distance in each run

---

### Slice 7: System Integration
**Objective**: Complete autonomous system

**Unified Launch File**:
```xml
<launch>
  <!-- Simulation -->
  <include file="jetbot_gz_control_camera_test_v2.launch.py"/>
  
  <!-- YOLO 3D Detection -->
  <include file="yolo.launch.py">
    <arg name="model" value="yolov8m.pt"/>
    <arg name="use_3d" value="true"/>
    <arg name="input_image_topic" value="/d415/image_raw"/>
    <arg name="input_depth_topic" value="/d415/depth/image_raw"/>
  </include>
  
  <!-- Navigation Bridge -->
  <node name="yolo_nav_bridge" pkg="chasebot_behavior" 
        executable="yolo_to_nav2_bridge.py"/>
</launch>
```

**UAT Criteria**:
- Single command launches everything
- Autonomous ball detection and approach
- System runs at >5 Hz
- Graceful handling of no-ball scenarios

---

## Risk Mitigation

### Potential Issues & Solutions

1. **Package Compatibility**
   - Risk: yolo_ros might not work with our setup
   - Mitigation: Thin slices allow early detection
   - Fallback: Use package as reference, implement minimal version

2. **Performance**
   - Risk: 3D processing too slow
   - Mitigation: Start with CPU, measure, then try GPU
   - Fallback: Reduce image size or detection rate

3. **Coordinate Frames**
   - Risk: Transform issues (we've seen this before)
   - Mitigation: Validate at Slice 4 with known positions
   - Tool: Transform visualizer if needed

## Success Metrics

- **Time to Complete**: 2-3 hours (vs days for custom)
- **Detection Rate**: >95% for visible balls
- **Approach Accuracy**: 3 inches ± 0.5 inch
- **System Frequency**: >5 Hz
- **Code Reuse**: >80% existing components

## Lessons from Previous Work

1. **Coordinate Transforms**: We fixed a 57cm error before - validate early
2. **Thin Slices Work**: D415 integration succeeded with incremental approach
3. **Display Issues**: Already solved - use DISPLAY=172.25.128.1:0.0
4. **File Sync**: Use PowerShell commands, not .bat files

## Next Steps

1. Update memory bank with this plan ✅
2. Begin Slice 1: Package installation
3. Report results after each slice
4. Adjust plan based on findings

This approach maximizes our chances of success while minimizing development time and risk.
