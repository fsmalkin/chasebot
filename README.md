# ChaseBot - Golf Ball Collection Robot

A ROS-based vision-guided autonomous robot for collecting golf balls, built on the JetBot Nano platform with the Robot Operating System. This project follows a phase-based development approach, starting with ROS simulation and progressing to hardware deployment.

## 🎯 Project Overview

**Ultimate Goal**: Full-sized autonomous golf ball collection robot for driving ranges and golf courses.

**Current POC**: Mini proof-of-concept focused on core golf ball acquisition behaviors using a JetBot Nano platform with ROS navigation stack.

**Phase 1 Focus**: ROS + Gazebo simulation environment to develop and test vision + navigation logic before hardware deployment.

**First Milestone**: End-to-end ROS demo of detecting golf balls and autonomously navigating toward them using the navigation stack.

## ✅ Folder Structure

```
/hardware      # BOM, wiring diagrams, JetBot + JetPack setup notes
/software      # ROS packages (chasebot_vision, chasebot_navigation, chasebot_bringup)
/sim          # Gazebo simulation (JetBot URDF, worlds, launch files)
/docs         # Architecture, decisions, milestone plans, ROS setup guides
/legacy_sim   # Previous Webots work (preserved for reference and lessons learned)
```

## 📌 Project Architecture Decisions

* **Robot platform:** JetBot Nano with Jetson Nano 4GB, IMX219 camera, and JetPack 4.6+ with ROS Melodic
* **ROS-based navigation:** Leverage ROS Navigation Stack (`move_base`, `amcl`, `map_server`) instead of custom control
* **Vision pipeline:** ROS nodes publishing detected targets to `/ball_detections` topic
* **Hardware abstraction:** JetBot ROS packages handle motor control via `/cmd_vel` geometry_msgs/Twist
* **Simulation platform:** Gazebo with JetBot URDF model for physics-accurate simulation
* **Node architecture:** Modular ROS nodes (vision, navigation, behavior) communicating via topics/services
* **Reasoning layer:** High-level ROS action server for task coordination (`find_ball`, `approach_ball`, `return_home`)
* **Tool abstraction layer:** ROS services expose robot capabilities to reasoning layer
* **Training-free principle:** Classical computer vision + ROS navigation, optionally enhanced with pre-trained models

## 📈 Current Phase: ROS Setup & Migration

**Objectives:**
- Migrate from Webots to Gazebo + ROS simulation environment  
- Implement ROS node architecture for vision and navigation
- Leverage JetBot ROS packages for hardware abstraction
- Validate ROS navigation stack for golf ball collection task

**Success Criteria:**
- Gazebo simulation runs with JetBot URDF model
- ROS nodes communicate properly via topics and services
- Navigation stack can autonomously drive toward detected targets
- Same ROS nodes work in simulation and on hardware

## 🚗 Target Hardware

- **Robot**: NVIDIA JetBot Nano with ROS integration
- **Board**: Jetson Nano 4GB with JetPack 4.6+
- **OS**: Ubuntu 18.04 with ROS Melodic pre-installed
- **Camera**: IMX219 160-degree FOV camera module with CSI interface
- **Actuators**: Differential drive motors controlled via ROS
- **Sensors**: Optional IMU and wheel encoders for improved navigation
- **Power**: Portable battery pack with power management

## 🛠️ Development Tools

- **Development Environment**: VS Code with ROS extensions and GitHub sync
- **ROS Distribution**: ROS Melodic (compatible with JetPack 4.6)
- **Simulation**: Gazebo + ROS Gazebo integration packages
- **Vision**: OpenCV with cv_bridge for ROS integration
- **Navigation**: ROS Navigation Stack (move_base, amcl, map_server)
- **Build System**: Catkin workspace with package dependencies
- **Testing**: ROS testing framework + RViz for visualization
- **Deployment**: ROS launch files for coordinated node startup
- **Version Control**: Git with ROS package structure

## 📋 Next Steps

1. **Environment Setup**: Configure simulation environment with JetBot model
2. **Vision Pipeline**: Implement golf ball detection using color/shape recognition
3. **Navigation Loop**: Create basic approach behavior for target acquisition
4. **Integration Testing**: Validate complete detection → navigation → acquisition cycle

## 📚 Documentation

See `/docs` folder for detailed architecture decisions, milestone planning, and setup guides.

## ✅ Current Status

**Phase 1 Migration**: From Webots to ROS + Gazebo
- ✅ **Webots Foundation Complete**: Successful proof-of-concept with motor control and physics
- ✅ **ROS Architecture Designed**: Node-based approach with navigation stack integration
- 🔄 **Gazebo Environment Setup**: JetBot URDF model and simulation world
- 🔄 **ROS Package Structure**: chasebot_vision, chasebot_navigation, chasebot_bringup packages
- 🔄 **Navigation Stack Integration**: move_base configuration for differential drive

**Phase 2 Ready**: ROS-based vision and navigation
- ✅ **Movement Principles Proven**: Webots work validates navigation feasibility
- 🔄 **ROS Vision Node**: Golf ball detection publishing to `/ball_detections`
- 🔄 **ROS Navigation Integration**: `/cmd_vel` control via navigation stack
- 🔄 **Hardware Deployment**: JetBot + JetPack + ROS Melodic setup

## 🎓 Lessons Learned & ROS Migration Insights

### Webots Foundation (Preserved Knowledge)
- **Device Discovery**: Understanding hardware abstraction layer requirements
- **Physics Configuration**: Importance of proper robot modeling (mass, inertia, collision)
- **Velocity Scaling**: Real-world vs simulation velocity mapping principles
- **Position Tracking**: Value of ground truth for debugging navigation algorithms
- **Modular Testing**: Benefits of incremental testing and validation

### ROS Migration Benefits
- **Hardware Abstraction**: ROS handles device discovery and motor control complexity
- **Navigation Stack**: Professional-grade path planning and obstacle avoidance
- **Simulation Consistency**: Gazebo + ROS provides better sim-to-hardware transfer
- **Community Support**: Extensive JetBot ROS ecosystem and documentation
- **Debugging Tools**: RViz, rostopic, rosbag for advanced debugging capabilities

### Architecture Improvements
- **Topic-Based Communication**: Cleaner separation between vision, navigation, and control
- **Launch File Coordination**: Systematic startup and parameter management
- **Service-Based Tools**: Standardized interfaces for high-level reasoning layer
- **Configuration Management**: ROS parameter server for tuning and deployment
- **Hardware Independence**: Same nodes run on simulation and physical robot

### Development Workflow
- **Catkin Workspace**: Structured development environment with dependency management
- **Package Organization**: Logical separation of concerns (vision, navigation, behavior)
- **Testing Framework**: ROS testing tools and simulation validation
- **Deployment Pipeline**: Launch files enable consistent multi-node deployment
