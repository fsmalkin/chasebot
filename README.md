# ChaseBot - Golf Ball Collection Robot

A vision-based autonomous robot for collecting golf balls, built on the JetBot Nano platform. This project follows a phase-based development approach, starting with simulation and progressing to hardware implementation.

## 🎯 Project Overview

**Ultimate Goal**: Full-sized autonomous golf ball collection robot for driving ranges and golf courses.

**Current POC**: Mini proof-of-concept focused on core golf ball acquisition behaviors using a JetBot Nano platform.

**Phase 1 Focus**: Simulation environment setup to develop and test vision + control logic before hardware deployment.

**First Milestone**: End-to-end demo of acquiring a golf ball in view and navigating toward it.

## ✅ Folder Structure

```
/hardware      # BOM, wiring diagrams, JetBot setup notes
/software      # Core control code (vision, navigation, reasoning)
/sim           # Sim environment (JetBot models, Gazebo/Webots, etc.)
/docs          # Architecture, decisions, milestone plans, setup guides
```

## 📌 Project Architecture Decisions

* **Robot platform:** JetBot Mini with Jetson Nano 4GB and pre-mounted IMX219 camera
* **Vision-only navigation:** No lidar, sonar, or encoders for now; rely on monocular visual input
* **Navigation subsystem:** Exposes abstract commands like `turn(angle)`, `move_forward(distance)`, `acquire_target()`
* **Reasoning layer:** Long-term vision to integrate an LLM or lightweight agent that issues structured commands (e.g., "navigate to ball and return to origin")
* **Tool abstraction layer:** The reasoning layer will not micromanage coordinates; it will call general tools like `find_ball`, `approach_ball`, `return_home`
* **Sensor input routing:** Shared vision feed accessible to both navigation system and higher-level controller
* **Training-free principle:** Avoid model training; use lightweight CV + planning modules and optionally open-source models (YOLOv8, SAM, etc.)

## 📈 Current Phase: Simulation Setup

**Objectives:**
- Choose simulation environment (Webots, Gazebo, or JetBot Collab sim)
- Implement basic simulated vision + mobility
- Prove that vision loop can locate golf ball in frame and issue move commands

**Success Criteria:**
- Simulated JetBot can detect golf ball in camera view
- Navigation system can generate movement commands toward target
- Complete vision-to-action loop demonstrates ball acquisition behavior

## 🚗 Target Hardware

- **Robot**: NVIDIA JetBot Nano
- **Board**: Jetson Nano 4GB
- **Camera**: IMX219 160-degree FOV camera module
- **Actuators**: Differential drive motors
- **Power**: Portable battery pack

## 🛠️ Development Tools

- **Simulation**: Webots/Gazebo + Python control scripts
- **Vision**: OpenCV + lightweight object detection
- **Control**: Python-based navigation and planning modules
- **Development**: Jupyter notebooks for interactive testing
- **Deployment**: Direct Python scripts for hardware

## 📋 Next Steps

1. **Environment Setup**: Configure simulation environment with JetBot model
2. **Vision Pipeline**: Implement golf ball detection using color/shape recognition
3. **Navigation Loop**: Create basic approach behavior for target acquisition
4. **Integration Testing**: Validate complete detection → navigation → acquisition cycle

## 📚 Documentation

See `/docs` folder for detailed architecture decisions, milestone planning, and setup guides.
