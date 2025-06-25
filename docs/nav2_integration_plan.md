# Nav2 Integration Plan

## Objective
Upgrade ChaseBot from direct motor control to professional navigation using ROS 2 Navigation Stack (Nav2).

**UAT Goal**: "Robot navigates to ball using professional path planning with obstacle avoidance"

## Current Capabilities
- ✅ Autonomous ball following using direct `/cmd_vel` commands
- ✅ HSV-based golf ball detection working perfectly
- ✅ Multi-ball detection and sequential targeting achieved
- ✅ ROS 2 Humble environment stable and operational

## Implementation Plan

### Slice 1: Nav2 Installation & Basic Configuration
**Goal**: Install Nav2 packages and verify basic functionality
- [x] Install ros-humble-navigation2
- [x] Install ros-humble-nav2-bringup
- [x] Verify Nav2 packages are accessible
- [ ] Create basic Nav2 configuration files

### Slice 2: Robot Configuration for Nav2
**Goal**: Configure JetBot for Nav2 compatibility
- [ ] Add required sensors (laser scan simulation)
- [ ] Configure robot_localization for odometry
- [ ] Set up transform tree (map → odom → base_link)
- [ ] Create Nav2 parameter files for JetBot

### Slice 3: Coordinate Transformation System
**Goal**: Transform camera ball detections to navigation goals
- [ ] Create ball position to world coordinate transformer
- [ ] Test coordinate accuracy in simulation
- [ ] Publish navigation goals from ball positions
- [ ] Validate goal reaching behavior

### Slice 4: Navigation Integration & UAT
**Goal**: Replace direct control with Nav2 navigation
- [ ] Modify ball follower to use Nav2 action client
- [ ] Add obstacle to test world
- [ ] Test path planning around obstacles
- [ ] Complete UAT demonstration

## Technical Requirements

### Nav2 Dependencies
- navigation2 (meta-package)
- nav2_bringup
- nav2_bt_navigator
- nav2_planner
- nav2_controller
- nav2_recoveries
- nav2_waypoint_follower

### Sensor Requirements
- Simulated laser scanner for obstacle detection
- Proper odometry from differential drive
- Transform publishers for coordinate frames

### Configuration Files
- nav2_params.yaml - Navigation stack parameters
- costmap_params.yaml - Costmap configuration
- planner_params.yaml - Path planning parameters
- controller_params.yaml - Path following parameters

## Success Criteria
1. Nav2 packages installed and launching without errors
2. Robot can receive and navigate to goal poses
3. Path planning avoids obstacles
4. Ball detection integrates with navigation goals
5. System more robust than direct motor control

## Research Findings

### Discovered Solution: depthimage_to_laserscan
After researching existing solutions for camera-only Nav2 navigation, we discovered the perfect standard solution:
- **Package**: ros-perception/depthimage_to_laserscan (272 GitHub stars)
- **Purpose**: Converts a depth image to a laser scan for use with navigation and localization
- **Benefit**: Allows camera-only robots to use standard laser-based Nav2 navigation

### Camera → Nav2 Pipeline
1. Camera feed → Depth estimation
2. Depth image → depthimage_to_laserscan → Simulated laser scan
3. Laser scan → Nav2 navigation (standard approach)
4. Ball detection → Navigation goals → Professional path planning

## Revised Implementation Plan

### Phase 1: depthimage_to_laserscan Integration
**Goal**: Convert camera feed to laser scan for Nav2
- [ ] Install depthimage_to_laserscan package for ROS 2
- [ ] Configure depth camera simulation
- [ ] Test laser scan generation from camera
- [ ] Verify scan data in RViz

### Phase 2: Basic Nav2 with Camera-based Laser
**Goal**: Nav2 navigation using camera-generated laser scans
- [ ] Configure Nav2 with camera-based laser scan
- [ ] Test basic navigation to goal poses
- [ ] Validate obstacle avoidance from camera data
- [ ] Compare performance with direct motor control

### Phase 3: Ball Detection to Navigation Goals
**Goal**: Transform ball positions to Nav2 goals
- [ ] Create coordinate transformation node
- [ ] Convert pixel positions to world coordinates
- [ ] Send navigation goals to Nav2
- [ ] Test autonomous ball following with Nav2

### Phase 4: Complete Integration & UAT
**Goal**: Full camera-based Nav2 navigation system
- [ ] Integrate all components
- [ ] Add obstacles to test world
- [ ] Demonstrate path planning around obstacles
- [ ] Complete UAT with professional navigation

## Current Status
- ✅ Nav2 packages installed successfully
- ✅ Research completed - found depthimage_to_laserscan solution
- 🎯 Next: Install and configure depthimage_to_laserscan
