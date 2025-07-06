# Slice 7: Joint Velocity Controller Implementation Plan

**Date**: January 5, 2025, 8:05 PM  
**Status**: 🎯 TOP PRIORITY - Core Movement Solution  
**Next**: Replace differential drive plugin with joint velocity controllers

## Overview

Replace the problematic differential drive plugin with a robust joint velocity controller solution that maintains full Nav2 compatibility.

## Implementation Strategy

### **Phase 1: Robot Model Updates**

#### 1.1 Remove Differential Drive Plugin
- Remove current `gz-sim-diff-drive-system` plugin from SDF
- Keep existing joint definitions (left_wheel_joint, right_wheel_joint)
- Maintain wheel physics and collision properties

#### 1.2 Add Joint Velocity Controllers
```xml
<!-- Left Wheel Velocity Controller -->
<plugin filename="gz-sim-joint-controller-system" name="gz::sim::systems::JointController">
  <joint_name>left_wheel_joint</joint_name>
  <topic>/left_wheel_cmd</topic>
  <p_gain>1000</p_gain>
  <i_gain>100</i_gain>
  <d_gain>10</d_gain>
</plugin>

<!-- Right Wheel Velocity Controller -->
<plugin filename="gz-sim-joint-controller-system" name="gz::sim::systems::JointController">
  <joint_name>right_wheel_joint</joint_name>
  <topic>/right_wheel_cmd</topic>
  <p_gain>1000</p_gain>
  <i_gain>100</i_gain>
  <d_gain>10</d_gain>
</plugin>
```

#### 1.3 Add Joint State Publisher
```xml
<plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">
  <joint_name>left_wheel_joint</joint_name>
  <joint_name>right_wheel_joint</joint_name>
</plugin>
```

### **Phase 2: ROS 2 Bridge Nodes**

#### 2.1 Cmd_Vel to Joint Velocities Converter
**File**: `ros2_scripts/cmd_vel_to_joints.py`

**Function**: Convert geometry_msgs/Twist to individual wheel velocities
```python
# Differential drive kinematics
wheel_separation = 0.16  # meters
wheel_radius = 0.032     # meters

# Convert twist to wheel speeds
v = twist.linear.x
w = twist.angular.z

left_wheel_velocity = (v - w * wheel_separation / 2) / wheel_radius
right_wheel_velocity = (v + w * wheel_separation / 2) / wheel_radius
```

**Topics**:
- **Subscribe**: `/cmd_vel` (geometry_msgs/Twist)
- **Publish**: 
  - `/left_wheel_cmd` (std_msgs/Float64)
  - `/right_wheel_cmd` (std_msgs/Float64)

#### 2.2 Joint States to Odometry Calculator
**File**: `ros2_scripts/joint_state_to_odom.py`

**Function**: Calculate robot odometry from wheel joint states
```python
# Read joint velocities from /joint_states
# Calculate robot velocity using differential drive kinematics
# Integrate position and orientation over time
# Publish odometry and transform
```

**Topics**:
- **Subscribe**: `/joint_states` (sensor_msgs/JointState)
- **Publish**: 
  - `/odom` (nav_msgs/Odometry)
  - `odom → base_link` transform

### **Phase 3: Launch File Integration**

#### 3.1 Updated Launch Configuration
```python
# Launch joint velocity controller nodes
Node(
    package='chasebot_description',
    executable='cmd_vel_to_joints.py',
    name='cmd_vel_to_joints'
),
Node(
    package='chasebot_description',
    executable='joint_state_to_odom.py',
    name='joint_state_to_odom'
),
```

#### 3.2 ROS-Gazebo Bridge Updates
```python
# Remove odom bridge (now handled by joint_state_to_odom)
# Keep cmd_vel bridge for Nav2 input
# Add joint command bridges
Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=['/left_wheel_cmd@std_msgs/msg/Float64@gz.msgs.Double'],
),
Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=['/right_wheel_cmd@std_msgs/msg/Float64@gz.msgs.Double'],
),
```

## Implementation Steps

### **Step 1: Update Robot Model** (30 min)
1. Modify `jetbot_core_ignition.sdf`
2. Replace differential drive plugin with joint controllers
3. Add joint state publisher plugin
4. Test robot spawning

### **Step 2: Implement Bridge Nodes** (60 min)
1. Create `cmd_vel_to_joints.py`
2. Create `joint_state_to_odom.py`
3. Test individual node functionality
4. Verify differential drive mathematics

### **Step 3: Integration Testing** (30 min)
1. Update launch file
2. Test complete movement pipeline
3. Verify Nav2 topic compatibility
4. Validate odometry accuracy

### **Step 4: UAT Validation** (15 min)
1. Run automated movement tests
2. Verify `/cmd_vel` → movement response
3. Confirm `/odom` data publication
4. Test Nav2 goal navigation

## Success Criteria

### ✅ **Movement Functionality**
- [ ] Robot responds to `/cmd_vel` commands
- [ ] Accurate differential drive kinematics
- [ ] Smooth acceleration and deceleration
- [ ] Proper turning behavior

### ✅ **Nav2 Integration**
- [ ] `/odom` topic publishes correctly
- [ ] `odom → base_link` transform available
- [ ] Nav2 can plan and execute paths
- [ ] Goal navigation works end-to-end

### ✅ **System Reliability**
- [ ] No plugin loading errors
- [ ] Stable long-running operation
- [ ] Proper error handling
- [ ] Clean simulation shutdown

## Advantages Over Differential Drive Plugin

1. **Reliability**: Joint controllers are proven and stable
2. **Control**: Complete control over implementation details
3. **Debugging**: Easy to troubleshoot and modify
4. **Real-world**: Mirrors actual robot driver architecture
5. **Nav2**: Guaranteed compatibility with navigation stack

## Next Phase Priorities

After completing robot movement:
1. **🎯 Priority 1**: 3D Vision System (D415 camera integration)
2. **🎯 Priority 2**: Object Detection (YOLO 3D integration)
3. **🎯 Priority 3**: Navigation to Target (autonomous ball following)

## Related Documentation

> **📎 Current Issue**: [`docs/d415_slices/slice6_differential_drive_fix_uat.md`](slice6_differential_drive_fix_uat.md)  
> **🔧 Foundation**: Ignition Fortress migration complete

> **📎 Implementation Files**:
> - `ros2_config/urdf/jetbot_core_ignition.sdf` (model updates)
> - `ros2_scripts/cmd_vel_to_joints.py` (to be created)
> - `ros2_scripts/joint_state_to_odom.py` (to be created)

## Timeline

**Estimated Completion**: 2-3 hours for full implementation and testing
**Next UAT**: Complete robot movement with Nav2 integration validation
