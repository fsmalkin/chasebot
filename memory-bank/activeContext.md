# Active Context - ChaseBot ROS 2 Development

## Current Session (2025-01-02)

### Transform Tree Side Quest - CRITICAL LESSONS LEARNED

**Major Discovery**: Our ROS 2 system has fundamental transform tree and timing issues that were breaking navigation.

#### Key Problems Identified:
1. **Broken Transform Tree**: Gazebo doesn't reliably publish URDF-defined camera transforms
   - Missing link: `base_link → camera_link → camera_optical_link`
   - Results in "not part of the same tree" errors
   
2. **Simulation Time Sync**: Nodes using wall time vs sim time
   - YOLO: Unix timestamps (1751434165)
   - Simulation: ROS time (881 seconds)
   - Causes "extrapolation into future" errors

3. **Ball Detection Issues**:
   - Ball must be spawned at y=0.0 (directly ahead)
   - Green balls detect better than white
   - Distance matters: 0.5-1.0m optimal

#### Solution Pattern Discovered:
1. Explicitly publish ALL static transforms (don't trust Gazebo)
2. Every node needs `use_sim_time:=true` parameter
3. Strict launch order: Gazebo → Robot → Transforms → Nav2 → YOLO → Debug → Bridge → Ball
4. ALWAYS open camera debugger before spawning ball

**Documentation Created**: `docs/lessons_learned_transform_issues.md`

### Next Immediate Steps - Simple Iterative Approach

#### Step 1: Create Robust Launch File
Build a single launch file that:
- Spawns robot and world
- Publishes ALL static transforms explicitly
- Launches Nav2 with proper delays
- Starts YOLO with sim time
- Opens debug viewers automatically
- Prompts user when to spawn ball

#### Step 2: Test Transform Chain
Before any navigation:
- Verify complete TF tree: `map → odom → base_link → camera_link → camera_optical_link`
- Check no timing errors in console
- Confirm YOLO debug shows camera feed

#### Step 3: Iterative Ball Detection
- Start with green ball at 0.5m directly ahead
- Verify detection in debug viewer
- Check bridge receives detections
- Only then expect navigation

### Critical Process Changes
1. **Visual First**: Always verify detection visually before expecting navigation
2. **Ball Last**: Spawn ball as final step - it's the "test begins" indicator
3. **PID Management**: Use specific PIDs for cleanup, not generic pkill
4. **Debug Always**: Camera debugger is not optional - it's required

### Session Status
- Cleaned up all running processes
- Documented critical lessons learned
- Identified robust solution pattern
- Ready to implement proper launch file in next session

## Previous Sessions Summary

### ROS 2 Migration Progress
- Core simulation environment working (Gazebo + JetBot)
- YOLO detection system integrated
- Nav2 stack functional
- **NEW**: Transform tree issues identified and solution documented

### Outstanding Work
- Task 2.1: Implement robust launch file with all transforms
- Task 2.2: Test and validate single ball navigation
- Task 3: Implement precise 3-inch approach
- Task 4: Create production launch file

### Key Technical Decisions
- Must explicitly publish all static transforms
- All nodes require use_sim_time parameter
- Visual debugging is mandatory, not optional
- Launch order is critical for success
