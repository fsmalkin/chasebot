# ChaseBot Architecture

## System Overview

ChaseBot is designed as a modular, vision-based autonomous robot system for golf ball collection. The architecture emphasizes abstraction layers to enable both simulation development and hardware deployment.

## Core Components

### 1. Vision System
- **Input**: Monocular camera feed (IMX219 160° FOV)
- **Processing**: OpenCV-based computer vision pipeline
- **Detection**: Golf ball identification using shape/color recognition
- **Output**: Target positions and confidence scores

### 2. Navigation Subsystem
- **Interface**: Abstract movement commands (`turn(angle)`, `move_forward(distance)`, `acquire_target()`)
- **Implementation**: Differential drive motor control
- **Planning**: Reactive navigation toward detected targets
- **Feedback**: Vision-based position estimation

### 3. Reasoning Layer (Future)
- **Purpose**: High-level decision making and task coordination
- **Interface**: Tool-based abstraction (`find_ball`, `approach_ball`, `return_home`)
- **Implementation**: LLM or scripted planner
- **Scope**: Strategic planning, not micro-coordination

## Data Flow

```
Camera Feed → Vision Processing → Target Detection → Navigation Commands → Motor Control
     ↑                                      ↓
     └────── Shared Feed ←────────── Reasoning Layer
```

## Key Design Decisions

### Vision-Only Navigation
- **Rationale**: Simplicity and cost-effectiveness for POC
- **Trade-offs**: Limited accuracy vs. sensor complexity
- **Future**: May add encoders or IMU for improved positioning

### Training-Free Approach
- **Rationale**: Avoid model training overhead and data requirements
- **Implementation**: Classical CV + heuristic planning
- **Alternative**: Leverage pre-trained models (YOLOv8, SAM)

### Modular Abstraction
- **Benefit**: Clean separation between simulation and hardware
- **Implementation**: Interface-based design with mode switching
- **Testing**: Identical logic runs in sim and on hardware

## Platform Specifications

### Hardware Target
- **Robot**: JetBot Nano kit
- **Compute**: Jetson Nano 4GB
- **Camera**: IMX219 CSI camera
- **Motors**: Differential drive with PWM control
- **Power**: Portable battery pack

### Software Stack
- **OS**: Ubuntu 18.04 (JetPack)
- **Runtime**: Python 3.6+
- **Vision**: OpenCV 4.x
- **Simulation**: Webots or Gazebo
- **Development**: Jupyter notebooks + VS Code

## Simulation Strategy

### Environment
- **Platform**: Webots (preferred) or Gazebo
- **World**: Simple flat surface with scattered golf balls
- **Robot Model**: JetBot with camera and differential drive
- **Physics**: Basic collision and dynamics

### Validation Approach
- **Development**: Iterate in simulation first
- **Testing**: Identical code runs in sim and hardware
- **Metrics**: Success rate, approach accuracy, cycle time

## Security & Safety

### Safety Considerations
- **Speed Limits**: Maximum velocity constraints
- **Collision Avoidance**: Basic obstacle detection
- **Manual Override**: Emergency stop capability
- **Power Management**: Battery monitoring and shutdown

### Deployment Safety
- **Environment**: Controlled indoor/outdoor spaces
- **Supervision**: Human oversight during testing
- **Fail-safes**: Automatic stop on vision loss or errors
