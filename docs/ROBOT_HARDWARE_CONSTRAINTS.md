# Robot Hardware Constraints

## Physical Robot Target
- Platform: Chasecar (JetBot-derived differential drive)
- Onboard compute: Jetson Orin Nano 8GB
- Camera: Intel RealSense D415

This is the binding fidelity target for UAT gating.

## Control and Kinematic Limits
- Wheel separation: `0.16 m`
- Wheel radius: `0.032 m`
- Max linear velocity: `0.6 m/s`
- Max angular velocity: `2.5 rad/s`
- `cmd_vel` timeout: `0.5 s`
- Controller update rate: `100 Hz`

## Camera Envelope
- RGB baseline: `640x480 @ 30 Hz`
- Depth baseline: `640x480 @ 30 Hz`
- Depth valid range: `0.165 m` to `10.0 m`

## Where Constraints Are Defined
- `ros2_config/config/robot_hardware_constraints.yaml`
- `docs/ROBOT_HARDWARE_CONTRACT_ORIN_NANO.yaml`
- `ros2_config/config/jetbot_diff_drive_v1.0.0.yaml`
- `ros2_config/urdf/jetbot_core_ignition_v1.6.0.sdf`

## Enforcement Rules
1. `robot_fidelity_orin` runtime must enforce physical limits.
2. Coordinate UAT pass/fail is valid only under `robot_fidelity_orin`.
3. Workstation profiles may exceed robot compute capacity for iteration speed, but cannot redefine robot-fidelity thresholds.
