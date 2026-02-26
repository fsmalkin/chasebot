# Robot Hardware Contract: Orin Nano 8GB

This document defines the physical target constraints used by `robot_fidelity_orin`.

## Canonical Source

- `docs/ROBOT_HARDWARE_CONTRACT_ORIN_NANO.yaml`
- `ros2_config/config/robot_hardware_constraints.yaml`

## Contract Summary

1. Compute target:
   - Jetson Orin Nano 8GB
   - TensorRT INT8 runtime required for canonical inference path
2. Sensor target:
   - Intel RealSense D415
   - RGB + Depth at 640x480 @ 30 FPS
3. Motion constraints:
   - max linear velocity: 0.6 m/s
   - max angular velocity: 2.5 rad/s
   - cmd_vel timeout: 0.5 s
4. Control constraints:
   - controller update rate: 100 Hz
5. Safety constraints:
   - deadman timeout: 0.5 s
   - stale detection timeout: 2.0 s

## Usage

All authoritative UAT pass/fail decisions must run with:

- `runtime_target=robot_fidelity_orin`
- `sim_lane=jetty_gate`
- `inference_backend=tensorrt_int8`
