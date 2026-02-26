# ChaseBot - Golf Ball Collection Robot

A ROS 2-based vision-guided autonomous robot for collecting golf balls, built on the JetBot Nano platform with the Robot Operating System. The project is transitioning to Intel RealSense D415 3D camera for professional depth-based perception, eliminating coordinate transformation complexities.

> **ðŸš€ Major Update (January 2025)**: Moving from problematic 2D vision to Intel RealSense D415 3D camera for direct world coordinate detection. See `docs/d415_implementation_plan.md` for details.

## 2026 Rebuild Track (Active)

The active rebuild path is now container-first and dual-lane:

1. Authoritative gate lane: ROS 2 Kilted + Gazebo Jetty (`jetty_gate`).
2. High-fidelity lane: Isaac + Jazzy bridge sidecar (`isaac_fidelity`).
3. Physical robot contract: Jetson Orin Nano 8GB.
4. Canonical inference backend: TensorRT INT8 (`tensorrt_int8`).

Primary workflow entrypoints:

1. `scripts/bootstrap_docker_host.ps1`
2. `scripts/run_compose_gate.ps1`
3. `scripts/run_compose_isaac.ps1`
4. `scripts/run_compose_uat.ps1`

See `docs/ACTIVE_WORKFLOW.md` for canonical commands and contracts.

## ðŸŽ¯ Project Overview

**Ultimate Goal**: Full-sized autonomous golf ball collection robot for driving ranges and golf courses.

**Current POC**: Mini proof-of-concept focused on core golf ball acquisition behaviors using a JetBot Nano platform with ROS navigation stack.

**Current Focus**: Intel RealSense D415 3D camera integration to provide direct depth measurement and eliminate pixel-to-world coordinate transformation issues.

**Next Milestone**: Autonomous ball following with accurate 3D position detection using D415 depth camera in Gazebo simulation.

## Current Folder Structure

```
/ros2_scripts     # ROS 2 nodes for vision, navigation, and control
/ros2_config      # Launch files, URDF models, Gazebo worlds, parameters
/docs             # Architecture, D415 implementation plan, development guides
/scripts          # Environment checks and local automation helpers
/archive          # Legacy code including old 2D vision attempts
  old_2d_vision   # Deprecated coordinate transformation approaches
```

## ðŸ“Œ Project Architecture Decisions

* **Robot platform:** JetBot Nano with Jetson Nano 4GB and Intel RealSense D415 3D camera
* **ROS 2 Humble:** Modern ROS 2 LTS with Nav2 navigation stack
* **3D Vision pipeline:** D415 depth camera provides direct world coordinates (no transforms!)
* **YOLO Detection:** Object detection on RGB stream, depth lookup for 3D position
* **Navigation:** Nav2 stack with direct 3D goal publishing (map-free approach)
* **Simulation:** Gazebo Classic with D415 depth camera plugin
* **Development:** Ubuntu 22.04 on WSL2 with full ROS 2 ecosystem
* **Key Innovation:** Elimination of error-prone pixel-to-world coordinate transforms

## ðŸ“ˆ Current Phase: 3D Camera Integration

**Objectives:**
- Replace broken 2D vision system with Intel RealSense D415
- Eliminate coordinate transformation bugs with direct depth measurement
- Maintain Nav2 navigation stack integration
- Achieve accurate ball approach with 3D position data

**Success Criteria:**
- D415 provides RGB + depth streams in Gazebo
- YOLO detection enhanced with depth lookup
- Direct 3D world coordinates (no transforms)
- Accurate autonomous ball following (Â±10cm approach)

## ðŸš— Target Hardware

- **Robot**: NVIDIA JetBot Nano with ROS 2 integration
- **Board**: Jetson Nano 4GB with JetPack 4.6+
- **Camera**: Intel RealSense D415 depth camera (RGB + Depth)
  - Range: 0.16m - 10m
  - Depth: 1280x720 @ 30fps
  - RGB: 1920x1080 @ 30fps
- **Actuators**: Differential drive motors via ROS 2 control
- **OS**: Ubuntu 20.04/22.04 with ROS 2 Humble
- **Power**: Portable battery pack with monitoring

## ðŸ› ï¸ Development Tools

- **Development Environment**: VS Code on Windows + WSL2 Ubuntu 22.04
- **ROS Distribution**: ROS 2 Humble LTS (supported through 2027)
- **Simulation**: Gazebo Classic with depth camera plugins
- **Vision**: YOLO v8 + Intel RealSense SDK 2.0
- **Navigation**: Nav2 navigation stack (map-free approach)
- **Build System**: Colcon workspace with ament_cmake
- **Visualization**: RViz2 for 3D debugging
- **Hardware**: NVIDIA GTX 1660 SUPER + 28GB RAM dev system

## ðŸ“‹ Next Steps

1. **D415 Simulation**: Add RealSense D415 to Gazebo with depth plugin
2. **3D YOLO Integration**: Enhance detector with depth lookup for 3D positions
3. **Navigation Bridge**: Simple 3D position to Nav2 goal converter
4. **System Validation**: Test accurate ball approach with real depth data

## ðŸ“š Documentation

See `/docs` folder for detailed architecture decisions, milestone planning, and setup guides.

## âœ… Current Status

**Completed**:
- âœ… **ROS 2 Environment**: Humble on Ubuntu 22.04 WSL2
- âœ… **Nav2 Integration**: Professional navigation stack working
- âœ… **YOLO Detection**: Reliable ball detection on RGB images
- âœ… **Simulation**: Gazebo with JetBot model operational

**In Progress (January 2025)**:
- ðŸ”„ **D415 Integration**: Adding 3D camera to eliminate coordinate bugs
- ðŸ”„ **3D Detection**: YOLO + depth for world coordinates
- ðŸ”„ **Simplified Bridge**: Direct 3D to Nav2 goals

**Deprecated**:
- âŒ **2D Coordinate Transforms**: Fundamentally flawed approach
- âŒ **Pixel-to-World Conversion**: Replaced by direct depth measurement

## ðŸŽ“ Key Lessons Learned

### Critical Discovery: 2D Vision Limitations
- **Coordinate Bug**: 2D system treated normalized pixels (0-1) as world coordinates (meters)
- **Transform Complexity**: Multiple frame conversions introduced cumulative errors
- **Distance Estimation**: Pixel-based depth estimation fundamentally unreliable
- **Solution**: 3D camera provides direct world coordinates - no transforms needed!

### Why D415 3D Camera
- **Direct Depth**: Each pixel has real-world distance measurement
- **No Transforms**: Eliminates entire class of coordinate conversion bugs
- **Professional Solution**: Industry-standard approach for robotics
- **Simplified Code**: Hundreds of lines of transform code â†’ simple depth lookup

### Architecture Benefits (ROS 2 + 3D Vision)
- **Modern Stack**: ROS 2 Humble with Nav2 professional navigation
- **Clean Data Flow**: RGB â†’ YOLO â†’ Depth Lookup â†’ 3D Position â†’ Nav2
- **Simulation Fidelity**: Gazebo depth camera plugin matches real D415
- **Maintainability**: Dramatically simplified codebase

### Development Best Practices
- Simulation first: test everything in Gazebo before hardware
- Thin slicing: make small, testable increments with clear success criteria
- Keep setup and launch docs current with each workflow change
- Preserve known-good launch paths while iterating

## Repo Level Set (February 25, 2026)

- Latest commit on `main`: `fe9410b` (2025-10-22)
- Secondary remote branch: `origin/dev-branch` at `8f151d0` (2025-06-25)
- Local machine checkout/fetch happened on 2026-02-24 after Windows reinstall
- Current recovery focus:
  - Reproducible bring-up scripts for WSL2/ROS 2 Humble
  - Gradual transition from `chasebot_*` naming toward `chasecar`
  - Reduction of archive-only runtime dependencies

## Recovery Quick Start (2026)

- Canonical workflow: `docs/ACTIVE_WORKFLOW.md`
- Hardware constraints: `docs/ROBOT_HARDWARE_CONSTRAINTS.md`
- Sim fidelity matrix: `docs/SIM_FIDELITY_MATRIX.md`

Windows entrypoints:
1. `scripts/windows_reinstall_preflight.ps1`
2. `scripts/run_canonical_stack.ps1`
3. `scripts/run_coordinate_uat.ps1`
4. `scripts/run_milestone_demo.ps1 -Milestone 1`

Coordinate UAT config:
- `ros2_config/config/uat_coordinates.yaml`

Expected UAT outputs:
- `artifacts/uat/<timestamp>/detections.csv`
- `artifacts/uat/<timestamp>/summary.json`
