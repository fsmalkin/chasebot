# ChaseBot ROS Milestone Plan

## Project Phases Overview

ChaseBot development follows a structured phase-based approach, progressing from ROS simulation to hardware deployment with clear success criteria at each stage.

## Phase 1: ROS Simulation Setup
**Timeline**: Weeks 1-2  
**Goal**: Establish ROS + Gazebo simulation environment and basic vision-to-navigation loop

### Milestone 1.1: ROS Environment Setup
**Deliverables:**
- [x] **Choose simulation platform** (Gazebo + ROS vs Webots evaluation)
  - ✅ Selected Gazebo with ROS integration for better hardware transfer
- [ ] **Install and configure ROS + Gazebo environment**
  - Install ROS Melodic and Gazebo 9
  - Set up catkin workspace structure
  - Configure JetBot ROS packages
- [ ] **Create JetBot URDF model with camera and differential drive**
  - Integrate or adapt existing JetBot URDF
  - Configure camera sensor and motor controllers
  - Set up Gazebo plugins for hardware simulation
- [ ] **Create simple test world with golf balls scattered on flat surface**
  - Design Gazebo world file with arena
  - Place golf ball objects with realistic physics
  - Configure lighting and textures

**Success Criteria:**
- ROS master and Gazebo simulation launch without errors
- JetBot URDF loads and publishes `/cmd_vel` topic control
- Camera publishes to `/camera/image_raw` and `/camera/camera_info`
- Golf balls are visible in camera feed and distinguishable
- RViz displays robot model, camera feed, and world correctly

### Milestone 1.2: ROS Vision Pipeline
**Deliverables:**
- [ ] **Implement ROS vision node** (`ball_detector_node`)
  - Create chasebot_vision package with catkin structure
  - Implement OpenCV golf ball detection with cv_bridge
  - Subscribe to `/camera/image_raw` and `/camera/camera_info`
  - Publish detections to `/ball_detections` topic
- [ ] **Color-based and shape recognition system**
  - HSV color masking for golf ball detection
  - Contour analysis and filtering for circular objects
  - Multi-stage detection pipeline with validation
- [ ] **Camera calibration and preprocessing**
  - Integrate camera calibration from `/camera/camera_info`
  - Image preprocessing for lighting and contrast
  - Noise reduction and filtering
- [ ] **Target position calculation in camera frame**
  - Convert pixel coordinates to relative positions
  - Publish target bearing and estimated distance
  - Handle multiple detections with confidence scoring

**Success Criteria:**
- Vision node runs stably and publishes detections at >10 Hz
- System reliably detects golf balls in Gazebo camera feed
- False positive rate < 20% in test scenarios with multiple objects
- Target position accuracy sufficient for navigation (< 10° bearing error)
- ROS parameter server allows runtime tuning of detection parameters

### Milestone 1.3: ROS Navigation Integration
**Deliverables:**
- [ ] **Configure ROS Navigation Stack**
  - Install and configure `move_base` package for path planning
  - Set up `amcl` for localization or simple odometry
  - Configure `base_local_planner` for differential drive
  - Create navigation parameter files
- [ ] **Implement behavior coordination node**
  - Create `ball_chase_node` that bridges vision and navigation
  - Subscribe to `/ball_detections` and publish `/move_base_simple/goal`
  - Implement basic approach behavior toward detected targets
  - Handle goal completion and target loss scenarios
- [ ] **Safety and constraint system**
  - Configure velocity limits and acceleration constraints
  - Implement emergency stop via `/cmd_vel` override
  - Add collision avoidance through navigation stack
  - Set up safety monitoring and diagnostics
- [ ] **Testing and validation framework**
  - Create ROS launch files for complete system startup
  - Implement automated testing with `rostest`
  - Add RViz configuration for visualization and debugging

**Success Criteria:**
- Navigation stack launches and runs without errors
- Robot responds to `/move_base_simple/goal` messages accurately
- Ball chase behavior successfully navigates toward detected targets
- Safety constraints prevent collisions and limit velocities
- RViz shows planned paths, robot pose, and goal states
- System handles goal preemption and re-planning gracefully

## Phase 2: ROS Vision-to-Action Loop
**Timeline**: Weeks 3-4  
**Goal**: Complete autonomous ball acquisition cycle with ROS integration

### Milestone 2.1: Integrated ROS Detection and Navigation
**Deliverables:**
- [ ] **Complete ROS system integration**
  - Launch file for full system startup (Gazebo + all nodes)
  - Coordinate vision, navigation, and behavior nodes
  - Implement proper ROS node lifecycle management
  - Add system health monitoring and diagnostics
- [ ] **Real-time target tracking during movement**
  - Dynamic goal updating based on ball movement
  - Handle target occlusion and re-acquisition
  - Implement visual servoing for fine-tuned approach
  - Add target loss detection and recovery behaviors
- [ ] **Advanced navigation behaviors**
  - Obstacle avoidance during ball approach
  - Dynamic path replanning when targets move
  - Implement "collection zone" behavior for final approach
  - Add timeout and failure recovery mechanisms

**Success Criteria:**
- Complete ROS system launches and runs stably for >5 minutes
- Robot autonomously detects and approaches golf balls via ROS topics
- Success rate >80% for balls within 2 meters in Gazebo simulation
- Approach accuracy within 10cm of target using navigation stack
- Graceful handling of target loss with automatic re-search behavior
- RViz displays show proper goal planning and execution

### Milestone 2.2: Multi-Target ROS Scenarios
**Deliverables:**
- [ ] **Enhanced multi-ball detection system**
  - Improve `/ball_detections` message to handle multiple targets
  - Implement confidence scoring and target persistence
  - Add detection filtering to reduce false positives
  - Create target database with unique identification
- [ ] **Intelligent target selection strategy**
  - Implement priority-based selection (nearest, largest, accessibility)
  - Add target selection as ROS service (`/select_target`)
  - Consider navigation cost in target prioritization
  - Handle dynamic target addition/removal during operation
- [ ] **Sequential acquisition coordination**
  - State machine for multi-target collection workflow
  - Progress tracking and mission completion detection
  - Return-to-home behavior after collection cycle
  - Mission abort and recovery capabilities

**Success Criteria:**
- System handles 3+ simultaneous targets without confusion
- Logical target prioritization and selection via ROS services
- Successfully acquires 3+ targets in sequence in Gazebo
- Robot returns to starting position after collection cycle
- Mission state tracked and published to `/mission_status` topic
- System recovers gracefully from individual target failures

### Milestone 2.3: ROS Performance Optimization
**Deliverables:**
- [ ] **Vision processing optimization**
  - GPU acceleration using CUDA for OpenCV operations
  - Multi-threaded vision pipeline for improved throughput
  - Dynamic parameter tuning via ROS parameter server
  - Vision processing profiling and bottleneck identification
- [ ] **Navigation stack tuning**
  - Optimize planner parameters for golf ball collection task
  - Tune velocity profiles for smooth and efficient movement
  - Configure recovery behaviors for navigation failures
  - Implement custom cost functions for ball approach
- [ ] **System-wide performance monitoring**
  - ROS node resource usage monitoring
  - Performance metrics collection via ROS topics
  - Automated performance regression testing
  - System benchmarking tools and reporting

**Success Criteria:**
- Vision processing maintains >15 Hz publication rate
- Navigation planning completes within 500ms for typical goals
- Average target acquisition time < 30 seconds from detection
- Navigation path efficiency >70% of theoretical optimal
- System resource usage remains stable during extended operation
- Performance metrics dashboard shows consistent behavior

## Phase 3: ROS Reasoning Layer & Tool Abstraction
**Timeline**: Weeks 5-6  
**Goal**: Add high-level decision making and tool abstraction using ROS action servers

### Milestone 3.1: ROS Tool Abstraction Interface
**Deliverables:**
- [ ] **ROS action server implementation**
  - Create chasebot_behavior package with action definitions
  - Implement `FindBall.action`, `ApproachBall.action`, `ReturnHome.action`
  - Add action server nodes for each high-level behavior
  - Create action client interfaces for reasoning layer integration
- [ ] **State machine architecture**
  - Implement behavior state machine using `smach` or similar
  - Add mission state tracking and coordination
  - Implement task queuing and prioritization system
  - Add failure recovery and retry mechanisms
- [ ] **Abstract goal representation**
  - Define high-level goal message types
  - Implement goal validation and feasibility checking
  - Add goal progress tracking and feedback
  - Create goal completion and success metrics

**Success Criteria:**
- ROS action servers launch and accept action goals correctly
- Clean separation between reasoning and navigation layers via ROS topics
- Tool commands execute reliably with proper feedback
- State machine accurately tracks robot status and publishes to `/robot_state`
- Goals can be expressed in high-level terms via ROS services
- Action preemption and cancellation work correctly

### Milestone 3.2: Advanced Reasoning Engine Integration
**Deliverables:**
- [ ] **Decision making framework**
  - Implement hierarchical task planning for multi-ball scenarios
  - Add dynamic replanning based on environmental changes
  - Integrate cost-based decision making for target selection
  - Implement timeout and fallback strategies
- [ ] **Mission coordination system**
  - Create mission definition and execution framework
  - Add mission progress monitoring and reporting
  - Implement complex multi-step collection scenarios
  - Add mission abort and recovery capabilities
- [ ] **Optional: LLM integration preparatory work**
  - Define natural language command interface
  - Create structured command parsing and validation
  - Add safety constraints for LLM-generated commands
  - Implement command explanation and confirmation dialog

**Success Criteria:**
- System executes complex multi-ball collection missions autonomously
- Decision making handles dynamic scenarios (balls moving, new balls appearing)
- Mission success rate >90% for 5+ ball scenarios in simulation
- Failure recovery strategies work without human intervention
- System handles plan failures with appropriate replanning
- Command interface (if implemented) safely processes natural language requests

## Phase 4: JetBot Hardware Integration with ROS
**Timeline**: Weeks 7-8  
**Goal**: Deploy ROS-based system to physical JetBot hardware

### Milestone 4.1: JetBot ROS Hardware Setup
**Deliverables:**
- [ ] **JetBot hardware preparation**
  - Assemble JetBot with all sensors and actuators
  - Install JetPack 4.6+ with ROS Melodic support
  - Configure GPIO and hardware interfaces
  - Set up networking and remote development environment
- [ ] **ROS hardware integration**
  - Install and configure JetBot ROS packages
  - Set up camera drivers and calibration
  - Configure motor control through ROS
  - Test basic hardware functionality via ROS topics
- [ ] **Hardware-specific parameter tuning**
  - Calibrate camera intrinsics and distortion
  - Tune motor control parameters for differential drive
  - Configure hardware-specific navigation parameters
  - Set up hardware safety limits and emergency stops

**Success Criteria:**
- JetBot hardware fully operational with ROS integration
- Camera publishes calibrated images to ROS topics
- Motors respond accurately to `/cmd_vel` commands
- Hardware safety systems function correctly
- ROS nodes can be launched remotely and run stably
- Hardware diagnostic information available via ROS topics

### Milestone 4.2: ROS System Hardware Deployment
**Deliverables:**
- [ ] **Direct deployment of simulation ROS nodes**
  - Deploy same catkin packages from simulation to hardware
  - Configure launch files for hardware vs simulation modes
  - Implement hardware-specific parameter overrides
  - Test full system integration on physical robot
- [ ] **Real-world performance validation**
  - Test ball detection in various lighting conditions
  - Validate navigation stack performance on real surfaces
  - Measure and optimize system performance on Jetson Nano
  - Implement power management and battery monitoring
- [ ] **Safety and robustness verification**
  - Test emergency stop and collision avoidance
  - Validate system behavior at hardware limits
  - Implement watchdog timers and health monitoring
  - Add logging and diagnostics for debugging

**Success Criteria:**
- Same ROS codebase runs on both simulation and hardware
- Real-world ball detection accuracy >60% in varied conditions
- Navigation stack successfully navigates real environments
- Safe operation in controlled environment without supervision
- System demonstrates successful golf ball acquisition on physical robot
- Hardware resource usage remains within acceptable limits

### Milestone 4.3: Real-World Performance Validation
**Deliverables:**
- [ ] **Comprehensive testing protocol**
  - Test system in various lighting and surface conditions
  - Validate performance with different ball arrangements
  - Measure success rates and completion times
  - Conduct reliability and endurance testing
- [ ] **Performance analysis and optimization**
  - Compare simulation vs hardware performance metrics
  - Identify and address performance bottlenecks
  - Optimize parameters for real-world conditions
  - Document performance characteristics and limitations
- [ ] **Deployment documentation and guides**
  - Create comprehensive setup and installation guide
  - Document hardware configuration and calibration procedures
  - Add troubleshooting guide for common issues
  - Prepare demonstration materials and videos

**Success Criteria:**
- Consistent performance across different environmental conditions
- Hardware performance within 80% of simulation results for key metrics
- System reliability >95% for standard collection scenarios
- Complete documentation enables independent system setup
- System ready for demonstration and further development
- Performance benchmarks established for future improvements

## Success Metrics

### Quantitative Metrics
- **Detection Accuracy**: % of golf balls correctly identified
- **Approach Precision**: Average distance from target when stopped
- **Completion Rate**: % of successful ball acquisitions
- **Cycle Time**: Average time per ball collection
- **Processing Speed**: Vision pipeline frame rate

### Qualitative Metrics
- **Robustness**: Performance consistency across scenarios
- **Reliability**: System uptime and error frequency
- **Safety**: Incident-free operation record
- **Maintainability**: Code clarity and documentation quality

## Risk Mitigation

### Technical Risks
- **Simulation Gap**: Validation through progressive hardware testing
- **Vision Robustness**: Multiple detection approaches and fallbacks
- **Hardware Limitations**: Conservative performance expectations
- **Integration Complexity**: Modular design with clear interfaces

### Timeline Risks
- **Scope Creep**: Strict milestone-based development
- **Technical Blockers**: Early prototyping and proof-of-concept validation
- **Hardware Delays**: Parallel simulation development while awaiting hardware
