# ChaseBot Technical Context

## Core Technologies
- **ROS Distribution**: ROS Melodic (LTS compatibility with JetPack 4.6+)
- **Simulation Platform**: Gazebo 9 with ROS integration
- **Operating System**: Ubuntu 18.04 LTS (JetPack target)
- **Programming Language**: Python 3.6+ (ROS Melodic compatibility)
- **Computer Vision**: OpenCV 4.x with cv_bridge integration
- **Hardware Platform**: NVIDIA JetBot Nano with Jetson Nano 4GB

## ROS Package Architecture
### Core Packages
- **chasebot_vision**: Ball detection and computer vision processing
- **chasebot_navigation**: Integration with ROS Navigation Stack
- **chasebot_behavior**: High-level behavior coordination and state machines
- **chasebot_bringup**: Launch files and system coordination
- **chasebot_msgs**: Custom message and service definitions

### Key ROS Dependencies
- **Navigation Stack**: move_base, amcl, map_server
- **Sensors**: sensor_msgs, cv_bridge, image_transport
- **Control**: geometry_msgs, actionlib
- **Diagnostics**: diagnostic_msgs, rosbag

## Hardware Specifications
### JetBot Platform
- **Compute**: Jetson Nano 4GB with GPU acceleration
- **Camera**: IMX219 CSI camera (160° FOV, 224x224 default resolution)
- **Motors**: Differential drive with PWM control via ROS
- **Power**: Portable battery pack with monitoring
- **Connectivity**: WiFi for remote development and monitoring

### Simulation Hardware Modeling
- **Robot Mass**: 2.5kg (validated in Webots, transferring to Gazebo)
- **Wheel Configuration**: Differential drive with realistic physics
- **Camera Modeling**: Matches IMX219 specifications in simulation
- **Golf Ball Physics**: 46g mass, 42mm diameter (regulation specifications)

## Development Environment
### Build System
- **Catkin Workspace**: Standard ROS build system
- **Dependencies**: rosdep for automated dependency management
- **CI/CD**: Automated building and testing pipeline

### Development Tools
- **IDE**: VS Code with ROS extensions
- **Visualization**: RViz for real-time system visualization
- **Debugging**: rostopic, rosbag, rqt tools
- **Version Control**: Git with proper ROS package structure

### Testing Framework
- **Unit Testing**: Python unittest with ROS integration
- **Integration Testing**: rostest framework for node communication
- **Simulation Testing**: Automated Gazebo scenarios
- **Hardware Testing**: Controlled real-world validation

## Technical Constraints
### Performance Targets
- **Vision Processing**: >10 Hz detection rate
- **Navigation Planning**: <500ms for typical goals
- **System Latency**: End-to-end detection to motion <2 seconds

### Resource Constraints
- **Memory**: Efficient operation within Jetson Nano 4GB
- **Processing**: GPU acceleration for computer vision when possible
- **Power**: Battery-efficient operation for extended missions
- **Network**: Reliable WiFi for development and monitoring

## Migration Status
### Webots Foundation (Completed)
- Established physics modeling and simulation principles
- Validated differential drive control algorithms
- Proven computer vision detection pipeline
- Comprehensive debugging and diagnostic methodologies

### ROS Migration (Current)
- Transitioning to Gazebo + ROS simulation environment
- Converting direct motor control to ROS Navigation Stack
- Implementing proper ROS node architecture and communication
- Establishing professional robotics development workflow
