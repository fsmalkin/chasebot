# ChaseBot ROS Architecture

## System Overview

ChaseBot is designed as a modular, ROS-based autonomous robot system for golf ball collection. The architecture leverages the Robot Operating System (ROS) for standardized communication, navigation, and hardware abstraction, enabling seamless development from simulation to hardware deployment.

## Core ROS Components

### 1. Professional Object Detection System (darknet_ros package)
- **Package**: darknet_ros (2.3k GitHub stars) - industry-standard YOLO implementation
- **Input**: Camera feed via `/camera/image_raw` topic (sensor_msgs/Image)
- **Processing**: Pre-trained YOLO v2-tiny model with 80 object classes
- **Detection**: Golf ball detected as "sports ball" class (43-60% confidence)
- **Output**: Bounding boxes via `/darknet_ros/bounding_boxes` topic (darknet_ros_msgs/BoundingBoxes)
- **Visualization**: Detection results on `/darknet_ros/detection_image` topic

### 2. Proven Navigation System (ros_simple_follower package)
- **Package**: ros_simple_follower (56 GitHub stars) - proven object following solution
- **Input**: Object position via `/object_tracker/current_position` topic (geometry_msgs/PointStamped)
- **Output**: Motor commands via `/cmd_vel` topic (geometry_msgs/Twist)
- **Implementation**: Tested differential drive control with proportional steering
- **Architecture**: Clean separation between detection and navigation
- **Benefits**: No custom navigation code required - leverages proven solution

### 3. YOLO-to-Position Bridge (chasebot_vision package)
- **Purpose**: Convert YOLO bounding boxes to 3D position estimates
- **Node**: `yolo_position_publisher.py` - minimal custom code
- **Input**: `/darknet_ros/bounding_boxes` (darknet_ros_msgs/BoundingBoxes)
- **Processing**: Filter "sports ball" detections, calculate position from bounding box center
- **Output**: `/object_tracker/current_position` (geometry_msgs/PointStamped)
- **Scope**: Thin interface layer between proven systems

### 4. System Integration (chasebot_bringup package)
- **Purpose**: Launch file coordination and parameter management
- **Components**: Integrated launch files combining all subsystems
- **Simulation**: Gazebo integration with JetBot URDF model and ChaseBot world
- **Architecture**: Modular design enabling independent testing of components
- **Configuration**: Parameter files for simulation vs hardware deployment

## ROS Data Flow

```
/camera/image_raw → darknet_ros → /darknet_ros/bounding_boxes → yolo_position_publisher → /object_tracker/current_position
     ↑                     ↓                                            ↓                            ↓
Camera Driver    /darknet_ros/detection_image                Bridge Node Processing           ros_simple_follower
     ↑                     ↓                                            ↓                            ↓
Hardware Layer    Visual Confirmation                      Position Calculation              /cmd_vel → Motor Control
```

## ROS Topic Architecture

### Core Topics (New Architecture)
- `/camera/image_raw` (sensor_msgs/Image) - Raw camera feed from robot
- `/darknet_ros/bounding_boxes` (darknet_ros_msgs/BoundingBoxes) - YOLO detection results
- `/darknet_ros/detection_image` (sensor_msgs/Image) - Visual detection overlay
- `/object_tracker/current_position` (geometry_msgs/PointStamped) - Target position for follower
- `/cmd_vel` (geometry_msgs/Twist) - Motor control commands to robot

### Legacy Topics (For Reference)
- `/camera/camera_info` (sensor_msgs/CameraInfo) - Camera calibration
- `/ball_detections` (chasebot_msgs/BallDetectionArray) - Custom detection format (future)
- `/odom` (nav_msgs/Odometry) - Robot odometry (future)
- `/move_base_simple/goal` (geometry_msgs/PoseStamped) - Navigation goals (future)

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
