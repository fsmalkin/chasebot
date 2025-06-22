# ChaseBot Core Project Rules

## Project Overview
ChaseBot is a ROS-based autonomous golf ball collection robot built on the JetBot Nano platform. The project emphasizes professional robotics development practices, hardware abstraction, and seamless simulation-to-hardware deployment.

## Core Principles

### 1. Search Existing Solutions First
- **ALWAYS search for existing ROS packages before building custom solutions**
- Prioritize proven, well-maintained packages with active communities (check GitHub stars, commits)
- Look for packages that solve 80% of the problem rather than building from scratch
- Examples: darknet_ros for object detection, move_base for navigation, opencv_apps for vision
- Custom development should only fill gaps that existing packages don't address
- Document why existing solutions were chosen over custom implementation

### 2. ROS-First Development
- All functionality must be implemented as ROS nodes with proper topic/service interfaces
- Use standard ROS message types when possible (geometry_msgs, sensor_msgs, nav_msgs)
- Leverage ROS Navigation Stack instead of custom motor control
- Implement proper ROS launch files for system coordination

### 3. Documentation-Driven Development
- Update documentation BEFORE implementing changes
- Keep docs/milestone_progress.md current with latest status
- Maintain architecture decisions in docs/architecture.md
- Document all ROS topics, services, and parameters

### 4. Hardware Abstraction
- Same ROS nodes must work in both Gazebo simulation and on JetBot hardware
- Use ROS parameter server for hardware-specific configurations
- Implement proper hardware safety constraints and emergency stops
- Validate all changes in simulation before hardware deployment

### 5. Thin Slice Development
- **Break down complex problems into very small, testable pieces**
- Each iteration should have a single, clear UAT success criterion
- Avoid building multiple features simultaneously - focus on one working piece at a time
- Examples: Test package installation → Test basic launch → Test with camera → Test detection
- Each slice should be independently demonstrable and valuable
- Build incrementally: working foundation before adding complexity

### 6. Professional Standards
- Follow ROS naming conventions for nodes, topics, and parameters
- Use catkin workspace structure with proper package organization
- Implement proper error handling and diagnostics
- Add comprehensive logging for debugging

## Development Workflow
1. **Plan** - Always understand the requirement and approach before coding
2. **Slice** - Break the work into thin, testable slices with clear UAT criteria
3. **Simulate** - Test in Gazebo simulation first
4. **Document** - Update relevant documentation
5. **Validate** - Ensure ROS integration works properly
6. **UAT** - Nothing is considered complete until User Acceptance Testing confirms it works as expected
7. **Commit** - Use descriptive commit messages with proper scope

## Definition of Done
- **Code Complete**: Implementation finished and internally tested
- **Documentation Updated**: All relevant docs reflect changes
- **Simulation Validated**: Functionality proven in Gazebo environment
- **UAT Passed**: User has tested and confirmed the feature works as expected
- **Repository Updated**: Changes committed with proper documentation

**CRITICAL**: No work item is considered "done" or "complete" until the user has performed User Acceptance Testing and confirmed it meets requirements.

## Key Technologies
- ROS Melodic (target platform: JetPack 4.6+)
- Gazebo simulation environment
- OpenCV for computer vision (with cv_bridge)
- Navigation Stack (move_base, amcl)
- JetBot hardware platform with Jetson Nano
