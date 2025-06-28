# ChaseBot Technical Context

## Core Technologies
### ROS 1 Baseline (Stable - Reference)
- **ROS Distribution**: ROS Melodic (LTS compatibility with JetPack 4.6+)
- **Simulation Platform**: Gazebo 9 with ROS integration
- **Operating System**: Ubuntu 18.04 LTS (WSL2 - ROS Melodic)
- **Programming Language**: Python 2.7/3.6+ (ROS Melodic compatibility)
- **Computer Vision**: darknet_ros YOLO v2-tiny (42-48% confidence golf ball detection)
- **Status**: ✅ **COMPLETE AUTONOMOUS BALL FOLLOWING** (preserved as reference)

### ROS 2 Target (✅ OPERATIONAL - New Hardware 2025-06-28)
- **ROS Distribution**: ROS 2 Humble LTS (5+ year support through 2027)
- **Advanced Stack**: Ready for NVIDIA Isaac ROS GPU-accelerated perception
- **Simulation Platform**: Gazebo Classic (CPU-compatible) + Isaac ROS integration ready
- **Operating System**: Ubuntu 22.04.5 LTS (WSL2 - Fresh Installation)
- **Build System**: colcon for ROS 2 package building (installed and operational)
- **Computer Vision**: Ready for Isaac ROS YOLOv8/RT-DETR (target >5 FPS performance)
- **Hardware Platform**: NVIDIA JetBot Nano with Jetson Nano 4GB (target deployment)

## Hardware Specifications

### Development Environment (✅ NEW SYSTEM 2025-06-28)
- **Host System**: Windows 11 on powerful desktop workstation
- **Processor**: AMD processor (~3801 MHz)
- **GPU**: NVIDIA GeForce GTX 1660 SUPER (full GPU acceleration available)
- **Memory**: 28GB RAM (excellent for simulation and development)
- **Storage**: High-performance SSD with ample space
- **Network**: High-speed internet connectivity
- **Performance**: Excellent capability for ROS 2 + Gazebo + Nav2 simulation

### Target JetBot Platform (Deployment Target)
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

## ROS Package Architecture
### Core Packages
- **chasebot_description**: Robot URDF models, launch files, and Nav2 configurations
- **chasebot_vision**: Ball detection and computer vision processing (planned)
- **chasebot_navigation**: Advanced Nav2 integration and behaviors (planned)
- **chasebot_behavior**: High-level behavior coordination and state machines (planned)
- **chasebot_msgs**: Custom message and service definitions (planned)

### Key ROS Dependencies (Installed and Ready)
- **Navigation Stack**: navigation2, nav2_bringup, nav2_*
- **SLAM**: slam_toolbox for mapping capabilities
- **Sensors**: sensor_msgs, cv_bridge, image_transport
- **Control**: geometry_msgs, action interfaces
- **Diagnostics**: diagnostic_msgs, rosbag2
- **Build System**: ament_cmake, colcon

## Development Environment

### WSL2 + ROS 2 Setup (✅ OPERATIONAL)
- **WSL Version**: WSL2 on Windows 11
- **Distribution**: Ubuntu-22.04 (22.04.5 LTS)
- **ROS Environment**: Auto-sourcing in ~/.bashrc
- **Workspace**: ~/ros2_ws/ with proper colcon structure
- **Build System**: colcon with all extensions installed
- **Package Status**: chasebot_description builds successfully

### Development Tools (✅ READY)
- **IDE**: VS Code with ROS extensions (host system)
- **Build System**: colcon for ROS 2 package building
- **Visualization**: RViz2 for real-time system visualization
- **Debugging**: ros2 CLI tools, topic monitoring, parameter server
- **Version Control**: Git with proper ROS package structure

### Testing Framework (Ready for Implementation)
- **Unit Testing**: Python unittest with ROS integration
- **Integration Testing**: ROS testing framework for node communication
- **Simulation Testing**: Automated Gazebo scenarios with Nav2
- **Hardware Testing**: Controlled real-world validation (future)

## Technical Constraints
### Performance Targets
- **Vision Processing**: >10 Hz detection rate (GPU acceleration available)
- **Navigation Planning**: <500ms for typical goals (Nav2 professional stack)
- **System Latency**: End-to-end detection to motion <2 seconds

### Resource Constraints
- **Development Memory**: 28GB available (excellent for development)
- **Development Processing**: AMD + GTX 1660 SUPER (excellent performance)
- **Target Memory**: Efficient operation within Jetson Nano 4GB
- **Target Processing**: GPU acceleration for computer vision when possible
- **Power**: Battery-efficient operation for extended missions
- **Network**: Reliable WiFi for development and monitoring

## Migration Status
### Webots Foundation (Completed ✅)
- Established physics modeling and simulation principles
- Validated differential drive control algorithms
- Proven computer vision detection pipeline
- Comprehensive debugging and diagnostic methodologies

### ROS 1 Achievement (Completed ✅)
- **Autonomous Ball Following**: Complete working system operational
- **Professional Architecture**: ROS-native design with proper patterns
- **YOLO Vision Pipeline**: darknet_ros with 42-48% confidence detection
- **Launch Command**: `roslaunch chasebot_description autonomous_ball_following.launch`
- **Status**: Preserved as stable baseline and architectural reference

### ROS 2 Environment Setup (✅ COMPLETE - 2025-06-28)
- **Decision**: Fresh Ubuntu 22.04 + ROS 2 environment on powerful hardware
- **Achievement**: Complete ROS 2 Humble + Nav2 installation successful
- **Approach**: Clean installation following proven patterns
- **Target**: ROS 2 + Nav2 + advanced capabilities operational
- **Timeline**: Environment setup complete, ready for Nav2 UAT
- **Benefits**: Stable foundation + GPU acceleration + professional Nav2 stack

### Nav2 Integration (✅ TECHNICALLY COMPLETE - Ready for UAT)
- **Architecture**: Camera → Ball Detection → Nav2 Goal → Path Planning → Navigation
- **Components**: Ball-to-goal converter, vision-to-laserscan, Nav2 config, launch files
- **Status**: Technical development complete from previous work
- **Current Issue**: Package installation needs debugging (minor CMakeLists.txt issue)
- **Ready for**: User Acceptance Testing of Nav2 autonomous ball following

## Current Development Infrastructure

### File Locations (ROS 2)
- **Workspace**: `~/ros2_ws/src/chasebot_description/`
- **URDF Models**: `urdf/ros2_jetbot.urdf`
- **Launch Files**: `launch/jetbot_nav2_*.launch.py`
- **Nav2 Config**: `nav2_params_simple.yaml`
- **Source Backup**: `/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/`

### Build Commands
```bash
# Environment Setup
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
source install/setup.bash

# Build Package
colcon build --packages-select chasebot_description

# Launch (when package installation fixed)
ros2 launch chasebot_description jetbot_nav2_complete.launch.py
```

### Professional Architecture Achieved ✅
- **Standard Interfaces**: Using Nav2 professional navigation messages
- **Proper Physics**: Realistic mass, inertia, and friction configured
- **Professional Logging**: ROS 2 logging for debugging and monitoring
- **Modular Design**: Each component independently testable and upgradeable
- **Safety Systems**: Comprehensive timeout and navigation safety

## Success Definition (Current State)
- ✅ **Powerful Development Environment**: GTX 1660 SUPER + 28GB RAM operational
- ✅ **Complete ROS 2 + Nav2 Stack**: Professional navigation framework ready
- ✅ **Package Structure**: chasebot_description properly organized and building
- ✅ **Nav2 Integration**: Technical development complete, ready for UAT
- ✅ **Professional Development**: Industry-standard tools and practices
- ✅ **Hardware Deployment Path**: Clear migration strategy to Jetson Nano

**Current Priority**: Fix package installation issue → Nav2 UAT testing → Advanced features development on powerful new hardware platform.
