# ChaseBot Milestone Plan

## Project Phases Overview

ChaseBot development follows a structured phase-based approach, progressing from simulation to hardware deployment with clear success criteria at each stage.

## Phase 1: Simulation Setup
**Timeline**: Weeks 1-2  
**Goal**: Establish simulation environment and basic vision-to-action loop

### Milestone 1.1: Environment Setup
**Deliverables:**
- [ ] Choose simulation platform (Webots vs Gazebo evaluation)
- [ ] Install and configure simulation environment
- [ ] Import or create JetBot model with camera and differential drive
- [ ] Create simple test world with golf balls scattered on flat surface

**Success Criteria:**
- Simulation launches without errors
- JetBot model loads and responds to basic movement commands
- Camera feed displays properly in simulation
- Golf balls are visible and distinguishable in camera view

### Milestone 1.2: Basic Vision Pipeline
**Deliverables:**
- [ ] Implement golf ball detection using OpenCV
- [ ] Color-based or shape-based recognition system
- [ ] Camera image preprocessing and filtering
- [ ] Target position calculation relative to robot

**Success Criteria:**
- System reliably detects golf balls in simulated camera feed
- False positive rate < 20% in test scenarios
- Target position accuracy within reasonable bounds
- Processing runs at >10 FPS in simulation

### Milestone 1.3: Navigation Commands
**Deliverables:**
- [ ] Abstract movement interface (`turn()`, `move_forward()`, `stop()`)
- [ ] Differential drive control in simulation
- [ ] Basic approach behavior toward detected targets
- [ ] Safety constraints (speed limits, collision detection)

**Success Criteria:**
- Robot moves accurately in response to navigation commands
- Approach behavior successfully reaches golf ball location
- Robot stops appropriately when target is reached
- No collisions or unstable movement patterns

## Phase 2: Vision-to-Action Loop
**Timeline**: Weeks 3-4  
**Goal**: Complete autonomous ball acquisition cycle

### Milestone 2.1: Integrated Detection and Navigation
**Deliverables:**
- [ ] Combined vision + navigation control loop
- [ ] Real-time target tracking during movement
- [ ] Reactive planning for target approach
- [ ] Error handling for lost targets

**Success Criteria:**
- Robot autonomously detects and approaches golf balls
- Success rate >80% for balls within 2 meters
- Approach accuracy within 10cm of target
- Graceful handling of target loss scenarios

### Milestone 2.2: Multi-Target Scenarios
**Deliverables:**
- [ ] Multiple golf ball detection and prioritization
- [ ] Target selection strategy (nearest, largest, etc.)
- [ ] Sequential target acquisition
- [ ] Return-to-start behavior

**Success Criteria:**
- System handles multiple targets without confusion
- Logical target prioritization and selection
- Successfully acquires 3+ targets in sequence
- Robot returns to starting position after collection

### Milestone 2.3: Performance Optimization
**Deliverables:**
- [ ] Vision processing optimization
- [ ] Navigation efficiency improvements
- [ ] Behavior tuning and parameter optimization
- [ ] Performance metrics collection

**Success Criteria:**
- Vision processing maintains >15 FPS
- Average target acquisition time < 30 seconds
- Navigation path efficiency >70% of optimal
- Consistent performance across different scenarios

## Phase 3: Target Reasoning Layer
**Timeline**: Weeks 5-6  
**Goal**: Add high-level decision making and tool abstraction

### Milestone 3.1: Tool Abstraction Interface
**Deliverables:**
- [ ] High-level command interface (`find_ball`, `approach_ball`, `return_home`)
- [ ] Tool-based architecture for reasoning layer
- [ ] State management and task coordination
- [ ] Abstract goal representation

**Success Criteria:**
- Clean separation between reasoning and navigation layers
- Tool commands execute reliably
- State tracking accurately reflects robot status
- Goals can be expressed in high-level terms

### Milestone 3.2: Reasoning Engine Integration
**Deliverables:**
- [ ] LLM or scripted planner integration
- [ ] Natural language task specification
- [ ] Multi-step plan generation and execution
- [ ] Error recovery and replanning

**Success Criteria:**
- System accepts high-level task descriptions
- Generates appropriate action sequences
- Handles plan failures with recovery strategies
- Completes complex multi-ball collection scenarios

## Phase 4: Hardware Integration
**Timeline**: Weeks 7-8  
**Goal**: Transition from simulation to physical JetBot

### Milestone 4.1: Hardware Preparation
**Deliverables:**
- [ ] JetBot assembly and configuration
- [ ] JetPack installation and setup
- [ ] Camera calibration and testing
- [ ] Motor control validation

**Success Criteria:**
- JetBot hardware fully operational
- Camera produces clear, stable images
- Motors respond accurately to control commands
- All sensors and actuators function correctly

### Milestone 4.2: Code Deployment
**Deliverables:**
- [ ] Port simulation code to JetBot hardware
- [ ] Hardware-specific adaptations and tuning
- [ ] Real-world performance validation
- [ ] Safety and error handling verification

**Success Criteria:**
- Same codebase runs on both simulation and hardware
- Real-world detection accuracy >60%
- Safe operation in controlled environment
- Successful golf ball acquisition in physical world

### Milestone 4.3: Performance Validation
**Deliverables:**
- [ ] Comprehensive testing in various conditions
- [ ] Performance comparison: simulation vs hardware
- [ ] Error analysis and system improvements
- [ ] Documentation and deployment guide

**Success Criteria:**
- Consistent performance across different lighting conditions
- Hardware performance within 80% of simulation results
- Documented setup and deployment procedures
- System ready for demonstration and further development

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
