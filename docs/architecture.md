# ChaseBot ROS Architecture

## System Overview

ChaseBot is designed as a modular, ROS-based autonomous robot system for golf ball collection. The architecture leverages the Robot Operating System (ROS) for standardized communication, navigation, and hardware abstraction, enabling seamless development from simulation to hardware deployment.

## Core ROS Components

### 1. Vision System (chasebot_vision package)
- **Input**: Camera feed via `/camera/image_raw` topic (sensor_msgs/Image)
- **Processing**: OpenCV-based computer vision with cv_bridge integration
- **Detection**: Golf ball identification using shape/color recognition
- **Output**: Target detections published to `/ball_detections` topic (custom message type)
- **Node**: `ball_detector_node` with configurable parameters

### 2. Navigation Subsystem (chasebot_navigation package)
- **Interface**: ROS Navigation Stack integration (move_base)
- **Input**: Target goals from `/ball_detections` and `/move_base_simple/goal`
- **Output**: Motor commands via `/cmd_vel` topic (geometry_msgs/Twist) 
- **Implementation**: Differential drive base controller with obstacle avoidance
- **Planning**: Global and local path planning via ROS navigation stack
- **Feedback**: Odometry and localization through AMCL or wheel encoders

### 3. Behavior Coordination (chasebot_behavior package)
- **Purpose**: High-level task coordination and decision making
- **Interface**: ROS action servers for tool abstraction (`FindBall.action`, `ApproachBall.action`, `ReturnHome.action`)
- **Implementation**: State machine or behavior tree for task sequencing
- **Integration**: Coordinates vision and navigation subsystems
- **Scope**: Strategic planning and mission-level coordination

### 4. Hardware Interface (chasebot_bringup package)
- **Purpose**: Hardware abstraction and system startup
- **Components**: Launch files, configuration files, and hardware drivers
- **Simulation**: Gazebo integration with JetBot URDF model
- **Hardware**: JetBot motor control and camera interface via ROS

## ROS Data Flow

```
/camera/image_raw → Vision Node → /ball_detections → Behavior Node → /move_base_simple/goal
     ↑                    ↓                             ↓                        ↓
Camera Driver    /camera/camera_info          Action Feedback        Navigation Stack
     ↑                    ↓                             ↓                        ↓
Hardware Layer   Vision Diagnostics       /behavior_status         /cmd_vel → Motor Control
```

## ROS Topic Architecture

### Core Topics
- `/camera/image_raw` (sensor_msgs/Image) - Raw camera feed
- `/camera/camera_info` (sensor_msgs/CameraInfo) - Camera calibration
- `/ball_detections` (chasebot_msgs/BallDetectionArray) - Detected golf balls
- `/cmd_vel` (geometry_msgs/Twist) - Motor control commands
- `/odom` (nav_msgs/Odometry) - Robot odometry
- `/move_base_simple/goal` (geometry_msgs/PoseStamped) - Navigation goals

### Diagnostic Topics
- `/behavior_status` (chasebot_msgs/BehaviorStatus) - Current behavior state
- `/vision_diagnostics` (diagnostic_msgs/DiagnosticArray) - Vision system health
- `/navigation_diagnostics` (diagnostic_msgs/DiagnosticArray) - Navigation status

## ROS Service Architecture

### Behavior Services
- `/find_ball` (chasebot_srvs/FindBall) - Initiate ball search behavior
- `/approach_ball` (chasebot_srvs/ApproachBall) - Navigate to specific ball
- `/return_home` (chasebot_srvs/ReturnHome) - Return to starting position
- `/emergency_stop` (std_srvs/Trigger) - Immediate stop command

### Configuration Services
- `/set_vision_params` (dynamic_reconfigure) - Adjust detection parameters
- `/set_nav_params` (dynamic_reconfigure) - Tune navigation behavior
- `/calibrate_camera` (chasebot_srvs/CalibrateCamera) - Camera calibration routine

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
- **OS**: Ubuntu 18.04 (JetPack) for hardware deployment
- **Runtime**: Python 3.6+
- **Vision**: OpenCV 4.x
- **Simulation**: Webots or Gazebo
- **Development**: VS Code with GitHub sync for all development
- **Testing**: Local Python scripts + Jupyter notebooks for analysis

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
