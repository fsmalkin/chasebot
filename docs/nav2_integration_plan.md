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

### IMX219 Camera Compatibility (Updated)
After research, we discovered that the **IMX219 is a monocular RGB camera** without native depth capabilities. This requires adjusting our approach since depthimage_to_laserscan requires depth images.

**IMX219 Characteristics:**
- ✅ Standard camera on JetBot hardware
- ✅ 8MP resolution, 1080p video capability
- ❌ No native depth information
- ❌ Incompatible with depthimage_to_laserscan without modification

**Recommended Approach: Vision-Based Obstacle Detection**
Instead of depth → laser scan conversion, we'll implement:
1. RGB camera feed → Computer vision obstacle detection
2. Obstacle positions → Simulated laser scan data
3. Simulated scan → Nav2 navigation
4. Ball detection → Navigation goals → Professional path planning

This approach provides:
- ✅ Professional Nav2 integration
- ✅ Hardware compatibility with IMX219
- ✅ Real obstacle avoidance capability
- ✅ Manageable implementation complexity

## Revised Implementation Plan

### Phase 1: Vision-Based Obstacle Detection
**Goal**: Convert RGB camera feed to laser scan for Nav2
- [x] Research IMX219 compatibility - monocular RGB only
- [x] Create vision-based obstacle detection node
- [x] Convert obstacle positions to laser scan format
- [x] Test simulated scan generation from RGB camera
- [x] Verify scan data publishing to /scan topic
- [x] Implement HSV-based detection for green golf balls
- [ ] Debug and optimize obstacle detection accuracy

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

## Current Status (2025-06-24 22:57)
- ✅ Nav2 packages installed successfully
- ✅ IMX219 camera compatibility resolved - using vision-based approach
- ✅ Vision to laser scan conversion implemented (both darkness and HSV versions)
- ✅ Laser scan topic publishing successfully
- ✅ Initial testing shows obstacle detection working (71 points detected)
- ✅ Launch files and nodes running without errors
- ✅ Fixed Windows line ending issue in ros2_ball_to_nav_goal.py
- ✅ **CONFIRMED**: Base autonomous ball following still works perfectly!
  - User validation: "wohoo it went to the first ball"
  - Direct cmd_vel control functioning as expected

### Implementation Progress
- **ros2_vision_to_laserscan_hsv.py**: Converting camera to laser scan using HSV detection
  - HSV range [35,50,50] to [85,255,255] for green detection
  - Publishing to /scan topic with 180 scan points
  - Debug visualization on /vision_to_laserscan/debug
- **ros2_ball_to_nav_goal.py**: Detects balls and sends Nav2 navigation goals
  - Waits for Nav2 action server
  - Converts ball positions to world coordinates
  - Sends NavigateToPose actions
- **nav2_params_simple.yaml**: Simplified Nav2 config without map requirement
  - Uses odom frame as global frame
  - Rolling window for global costmap
  - Basic obstacle avoidance from camera-based laser scan
- **jetbot_nav2_complete.launch.py**: Full Nav2 integration launch
  - Launches complete Nav2 stack
  - Includes all navigation components
- **test_nav2_vision.py**: Simple test script for incremental verification
  - Tests laser scan reception
  - Tests direct motor control
  - Prepares for Nav2 goal testing

### Next Steps
1. **Nav2 Launch Simplification**: Break down Nav2 launch into smaller components
2. **Transform Tree Verification**: Ensure all required transforms are published
3. **Nav2 Action Server**: Get basic Nav2 action server running with minimal config
4. **Integration Test**: Once Nav2 accepts goals, integrate with ball detection

### Key Insights
1. **Base System Works**: Direct cmd_vel control confirmed working perfectly
2. **Nav2 Resource Requirements**: Full Nav2 stack is very resource-intensive
   - Can cause system overheating on limited hardware
   - Requires significant CPU/RAM for planning, costmaps, behaviors
3. **Practical Approach**: Current direct control system is sufficient for basic ball following
   - Professional path planning can be added when more powerful hardware available
   - All Nav2 components are created and ready for future integration

### Recommendations
- **Continue with Direct Control**: The current autonomous ball following system works well
- **Nav2 for Future**: When deploying to more powerful hardware (Jetson Nano/Xavier)
- **Incremental Approach**: Could try just Nav2 controller without full planning stack
- **Alternative**: Consider lighter-weight planners like DWA-local-planner only
