# JetBot Nano Simulation & Deployment

This repository contains code and configurations for simulating and deploying an AI-powered JetBot Nano robot. The goal is to prototype, test, and refine control and perception logic in a virtual environment before deploying to physical hardware.

## 🧠 Project Objectives

- Simulate JetBot Nano behavior including vision, motion, and environment interaction
- Build a portable codebase that can run both in simulation and on hardware with minimal change
- Use Codex/GitHub Copilot to accelerate development with meaningful inline and contextual suggestions

## 🚗 Target Hardware

- **Robot**: NVIDIA JetBot Nano
- **Board**: Jetson Nano 4GB
- **Sensors**: Onboard camera, ultrasonic sensor (optional)
- **Actuators**: Differential drive motors

## 🧪 Simulation Goals

- Run JetBot control logic in Gazebo or Isaac Sim
- Emulate camera input for CV models
- Emulate motor controls and obstacle detection
- Allow rapid iteration in Jupyter or script mode

## 📦 Project Structure

```
jetbot-sim/
├── README.md                # Overview and setup instructions
├── requirements.txt         # Python dependencies
├── sim_env/                 # Simulation environment (URDFs, Gazebo world, Isaac config)
│   ├── world/
│   └── robot/
├── scripts/                 # Control and training scripts
├── notebooks/               # Jupyter notebooks for interactive exploration
├── deploy/                  # Real JetBot deployment logic
└── utils/                   # Helper functions, data processing
```

## 💻 Tools

- Python 3.8+
- JupyterLab
- OpenCV
- Gazebo (or NVIDIA Isaac Sim)
- ROS 2 (if using Gazebo)
- Docker (optional, for consistent environments)

## 🔁 Simulation vs Deployment

- Code will be modularized for reuse across simulated and real environments
- Deployment will handle Jetson-specific hardware APIs

## 🧱 Roadmap

- [ ] Set up simulation environment with basic world and robot model
- [ ] Create a control loop script using simulated camera input
- [ ] Integrate object detection or line following logic
- [ ] Validate control policies in sim, then deploy to JetBot
