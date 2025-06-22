# ChaseBot ROS Architecture

## System Overview

ChaseBot is designed as a modular, ROS-based autonomous robot system for golf ball collection. The architecture follows an **iterative development approach** - starting with simple topic-based nodes that can evolve into more sophisticated behavior coordination without throwaway work.

## Development Philosophy

### Pragmatic Iteration
- **Start Simple**: Basic topic/service nodes for immediate progress
- **Evolve Naturally**: Each simple node becomes a reusable primitive action
- **Zero Throwaway**: All code remains useful as system grows in complexity
- **Unblock Progress**: Focus on working robot behavior over architectural perfection

### Future LLM Integration Path
The architecture is designed to eventually support LLM-driven task decomposition:
```
"Collect Ball" → acquire_target + approach_object + engage_ball + push_to_location
```

Current simple nodes will become the primitive actions for this higher-level coordination.

## Current Architecture (Milestone: Navigate to Target)

### 1. Object Detection System (darknet_ros)
- **Package**: darknet_ros (2.3k GitHub stars) - industry-standard YOLO implementation
- **Input**: Camera feed via `/camera/image_raw` topic (sensor_msgs/Image)
- **Processing**: Pre-trained YOLO v2-tiny model detecting golf balls as "sports ball" class
- **Output**: Bounding boxes via `/darknet_ros/bounding_boxes` topic (darknet_ros_msgs/BoundingBoxes)
- **Visualization**: Detection results on `/darknet_ros/detection_image` topic

### 2. Target Selection Node (chasebot_navigation)
- **Node**: `target_selector_node` - simple custom node
- **Input**: `/darknet_ros/bounding_boxes` (darknet_ros_msgs/BoundingBoxes)
- **Processing**: Filter "sports ball" detections, select best target (closest/largest)
- **Output**: `/target_position` (geometry_msgs/PointStamped)
- **Logic**: Simple heuristics for target prioritization

### 3. Approach Controller Node (chasebot_navigation)
- **Node**: `approach_controller_node` - adapted from ball-chaser-bot pattern
- **Input**: `/target_position` (geometry_msgs/PointStamped)
- **Processing**: Proportional control algorithm for differential drive
- **Output**: `/cmd_vel` (geometry_msgs/Twist)
- **Implementation**: Based on proven gsotirchos/ball-chaser-bot approach

### 4. State Monitor Node (chasebot_navigation)
- **Node**: `state_monitor_node` - simple status tracking
- **Input**: `/target_position`, `/cmd_vel`
- **Processing**: Track system state for debugging and future coordination
- **Output**: `/approach_status` (std_msgs/String)
- **States**: "searching", "approaching", "reached", "lost_target"

## ROS Data Flow (Current Implementation)

```
/camera/image_raw → darknet_ros → /darknet_ros/bounding_boxes → target_selector_node → /target_position
     ↑                     ↓                                            ↓                        ↓
Camera Driver    /darknet_ros/detection_image              Target Selection Logic    approach_controller_node
     ↑                     ↓                                            ↓                        ↓
Hardware Layer    Visual Confirmation                     Best Target Position            /cmd_vel → Motor Control
                                                                   ↓
                                                          state_monitor_node → /approach_status
```

## ROS Topic Architecture

### Core Topics (Current Milestone)
- `/camera/image_raw` (sensor_msgs/Image) - Raw camera feed from robot
- `/darknet_ros/bounding_boxes` (darknet_ros_msgs/BoundingBoxes) - YOLO detection results
- `/darknet_ros/detection_image` (sensor_msgs/Image) - Visual detection overlay
- `/target_position` (geometry_msgs/PointStamped) - Selected target for approach
- `/cmd_vel` (geometry_msgs/Twist) - Motor control commands to robot
- `/approach_status` (std_msgs/String) - System state for monitoring

### Future Evolution Topics
- `/ball_detections` (chasebot_msgs/BallDetectionArray) - Rich detection format
- `/odom` (nav_msgs/Odometry) - Robot odometry for path planning
- `/move_base_simple/goal` (geometry_msgs/PoseStamped) - Navigation goals

## Evolution Path (No Throwaway Work)

### Phase 1: Simple Nodes (Current)
```python
# Each node is standalone and testable
target_selector_node      # → becomes "acquire_target" action
approach_controller_node  # → becomes "approach_object" action  
state_monitor_node       # → becomes behavior tree conditions
```

### Phase 2: Coordination Layer (When Needed)
Choose based on complexity:
- **Simple Growth**: Python coordinator script
- **Medium Complexity**: SMACH state machines
- **High Complexity**: BehaviorTree.CPP framework

### Phase 3: LLM Integration (Future)
```
LLM Task Planner
    ↓
Behavior Coordinator (Trees/States)
    ↓
Primitive Actions (Current Simple Nodes)
```

## Pre-Built Package Integration

### gsotirchos/ball-chaser-bot Integration
Our approach adapts the proven ball-chaser-bot pattern:
- **Service Architecture**: `drive_bot` + `process_image_opencv` pattern
- **OpenCV Replacement**: Use YOLO detections instead of OpenCV ball detection
- **Control Logic**: Proven proportional control algorithms
- **Clean Separation**: Vision processing separate from motor control

### Alternative Packages Evaluated
- **aravindh96/Turtlebot_Object_Follower**: Camera-based white ball following
- **53+ ball_chaser repositories**: Various ROS object following implementations
- **ROS 2 Migration Path**: Future upgrade options identified

## Platform Specifications

### Hardware Target
- **Robot**: JetBot Nano kit (Proof of Concept scope)
- **Compute**: Jetson Nano 4GB
- **Camera**: IMX219 CSI camera
- **Motors**: Differential drive with PWM control
- **Scope**: Golf ball sized objects, controlled environment

### Software Stack
- **OS**: Ubuntu 18.04 (JetPack) / WSL2 for development
- **ROS**: ROS Melodic (target platform compatibility)
- **Vision**: OpenCV 4.x + darknet_ros
- **Simulation**: Gazebo with JetBot URDF
- **Development**: VS Code with cross-platform workflow

## Key Design Decisions

### Simplicity First
- **Rationale**: Unblock current milestone without over-engineering
- **Implementation**: Topic-based nodes that can evolve
- **Benefits**: Immediate progress, clear interfaces, testable components

### Pre-Built Package Leverage
- **Rationale**: Proven solutions over custom implementation
- **Strategy**: Adapt gsotirchos/ball-chaser-bot for our detection pipeline
- **Benefits**: Faster development, battle-tested algorithms

### Modular Evolution
- **Current**: Simple standalone nodes
- **Near-term**: Coordination layer when complexity demands it
- **Long-term**: LLM-driven task decomposition using current nodes as primitives

### Vision-Only Navigation
- **Rationale**: Appropriate complexity for POC scope
- **Trade-offs**: Acceptable accuracy limitations for proof of concept
- **Future**: Can add sensors without changing core architecture

## Testing Strategy

### Development Workflow
- **Simulation First**: Test all logic in Gazebo before hardware
- **Component Testing**: Each node testable independently
- **Integration Testing**: Complete pipeline validation
- **Hardware Deployment**: Same code runs on JetBot

### Success Criteria
- **Basic Following**: Robot approaches detected golf balls
- **Visual Confirmation**: Can observe behavior in simulation
- **Modular Design**: Components can be tested/replaced independently
- **Evolution Ready**: Architecture supports future complexity growth

This architecture prioritizes immediate progress on the current milestone while maintaining a clear path for future sophistication without requiring throwaway work.
