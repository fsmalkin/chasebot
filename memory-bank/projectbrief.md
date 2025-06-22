# ChaseBot Project Brief

## Project Overview
ChaseBot is an autonomous golf ball collection robot built on the NVIDIA JetBot Nano platform using the Robot Operating System (ROS). The project demonstrates professional robotics development practices with a focus on simulation-to-hardware deployment.

## Core Goals
1. **Autonomous Ball Collection**: Create a robot that can detect, navigate to, and collect golf balls autonomously
2. **Professional Robotics Development**: Implement industry-standard ROS architecture and development practices
3. **Simulation-First Approach**: Develop and validate all functionality in simulation before hardware deployment
4. **Educational Value**: Serve as a comprehensive example of modern robotics development workflow

## Target Platform
- **Hardware**: NVIDIA JetBot Nano with Jetson Nano 4GB
- **Software**: ROS Melodic on Ubuntu 18.04 (JetPack 4.6+)
- **Simulation**: Gazebo with ROS integration
- **Camera**: IMX219 160-degree FOV camera module

## Project Scope
- **Phase 1**: ROS simulation environment setup with Gazebo
- **Phase 2**: Vision-to-action loop with ROS Navigation Stack
- **Phase 3**: High-level reasoning and tool abstraction
- **Phase 4**: Hardware deployment and real-world validation

## Success Criteria
- Robot autonomously detects and approaches golf balls in simulation
- Same codebase runs on both simulation and hardware
- Professional ROS architecture with proper node organization
- Comprehensive documentation and reproducible development environment

## Current Status
**Migration Phase**: Successfully completed Webots proof-of-concept and migrating to ROS-based architecture for improved scalability and hardware integration.
