# ChaseBot Core Project Rules

## Project Overview
ChaseBot is a ROS-based autonomous golf ball collection robot built on the JetBot Nano platform. The project emphasizes professional robotics development practices, hardware abstraction, and seamless simulation-to-hardware deployment.

## Core Principles

### 1. ROS-First Development
- All functionality must be implemented as ROS nodes with proper topic/service interfaces
- Use standard ROS message types when possible (geometry_msgs, sensor_msgs, nav_msgs)
- Leverage ROS Navigation Stack instead of custom motor control
- Implement proper ROS launch files for system coordination

### 2. Documentation-Driven Development
- Update documentation BEFORE implementing changes
- Keep docs/milestone_progress.md current with latest status
- Maintain architecture decisions in docs/architecture.md
- Document all ROS topics, services, and parameters

### 3. Hardware Abstraction
- Same ROS nodes must work in both Gazebo simulation and on JetBot hardware
- Use ROS parameter server for hardware-specific configurations
- Implement proper hardware safety constraints and emergency stops
- Validate all changes in simulation before hardware deployment

### 4. Professional Standards
- Follow ROS naming conventions for nodes, topics, and parameters
- Use catkin workspace structure with proper package organization
- Implement proper error handling and diagnostics
- Add comprehensive logging for debugging

## Development Workflow
1. **Plan** - Always understand the requirement and approach before coding
2. **Simulate** - Test in Gazebo simulation first
3. **Document** - Update relevant documentation
4. **Validate** - Ensure ROS integration works properly
5. **Commit** - Use descriptive commit messages with proper scope

## Key Technologies
- ROS Melodic (target platform: JetPack 4.6+)
- Gazebo simulation environment
- OpenCV for computer vision (with cv_bridge)
- Navigation Stack (move_base, amcl)
- JetBot hardware platform with Jetson Nano
