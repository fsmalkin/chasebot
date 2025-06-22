# ChaseBot System Patterns

## System Architecture
### ROS Node Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Camera Node   │───▶│  Vision Node    │───▶│ Behavior Node   │
│ /camera/image_* │    │ /ball_detections│    │ Coordination    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Motor Control  │◀───│ Navigation Stack │◀───│ Goal Publisher  │
│    Hardware     │    │   move_base     │    │ /move_base_goal │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Design Patterns
1. **Publisher-Subscriber**: Vision detection results published to behavior nodes
2. **Service-Oriented**: High-level behaviors exposed as ROS services
3. **Action-Based**: Long-running operations (navigation) use actionlib
4. **Parameter-Driven**: Runtime configuration via ROS parameter server

## Component Relationships
### Vision System
- **Input**: Raw camera stream (`/camera/image_raw`)
- **Processing**: OpenCV detection pipeline with cv_bridge
- **Output**: Ball detection messages (`/ball_detections`)
- **Configuration**: Dynamic reconfigure for detection parameters

### Navigation System
- **Input**: Goal positions from behavior coordination
- **Processing**: ROS Navigation Stack (move_base, local/global planners)
- **Output**: Velocity commands (`/cmd_vel`) to motor controllers
- **Safety**: Collision avoidance and velocity constraints

### Behavior Coordination
- **Input**: Detection results and user commands
- **Processing**: State machine for task sequencing
- **Output**: Navigation goals and system status
- **Interface**: ROS services for high-level tool abstraction

## Critical Implementation Paths
### Simulation-to-Hardware Transfer
1. **URDF Modeling**: Identical robot model in Gazebo and hardware
2. **Parameter Abstraction**: Hardware-specific configs via parameter server
3. **Topic Consistency**: Same message types and topic names
4. **Launch File Modes**: Simulation vs hardware launch configurations

### Safety and Diagnostics
1. **Emergency Stop**: Immediate `/cmd_vel` override capability
2. **Health Monitoring**: Diagnostic publishers for all major components
3. **Timeout Handling**: Graceful degradation when components fail
4. **Logging**: Comprehensive ROS logging for debugging and analysis

## Proven Patterns from Webots Foundation
### Motor Control
- **Velocity Scaling**: Understanding of simulation vs real-world velocity mapping
- **Differential Drive**: Left/right motor coordination for movement and turning
- **Physics Integration**: Proper robot mass and inertia configuration
- **Position Tracking**: Ground truth validation for navigation accuracy

### Vision Processing
- **Detection Pipeline**: HSV color masking with contour analysis
- **Target Selection**: Prioritization logic for multiple detections
- **Coordinate Conversion**: Pixel to world coordinate transformation
- **Parameter Optimization**: Empirically validated detection thresholds

### System Integration
- **Modular Testing**: Component isolation for debugging
- **External Control**: Benefits of external process control vs embedded
- **Diagnostic Tools**: Device discovery and validation frameworks
- **Performance Monitoring**: Real-time system performance tracking

## Architectural Decisions
### ROS over Custom Control
- **Rationale**: Industry standard, hardware abstraction, community support
- **Trade-offs**: Learning curve vs long-term maintainability
- **Implementation**: Gradual migration preserving proven algorithms

### Gazebo over Webots
- **Rationale**: Better ROS integration, hardware compatibility
- **Trade-offs**: Migration effort vs professional tooling benefits
- **Implementation**: Port validated physics and environment models

### Navigation Stack Integration
- **Rationale**: Professional path planning vs custom reactive control
- **Trade-offs**: Complexity vs robustness and safety
- **Implementation**: Configure for differential drive golf ball collection task
