# Active Workflow (Canonical)

## Scope
This file is the single source of truth for what to run for recovery, UAT, and GUI milestone demos.

## Canonical Stack Components
1. Simulation launch: `jetbot_gz_control_camera_test_v5.launch.py`
2. Detector: `ros2_yolo_detector_frisbee_quiet.py`
3. 3D extractor: `yolo_3d_position_extractor.py`
4. Nav bridge: `yolo_3d_to_nav2_bridge.py`

## Canonical Entry Scripts (Windows)
1. `scripts/run_canonical_stack.ps1`
2. `scripts/run_coordinate_uat.ps1`
3. `scripts/run_milestone_demo.ps1 -Milestone <1|2|3>`

## Runtime Targets
1. `robot_fidelity`
2. `workstation_balanced`
3. `workstation_max`

Defaults are defined in:
- `ros2_config/config/hardware_profiles.yaml`
- `ros2_config/config/robot_hardware_constraints.yaml`

## Required Topics
- `/d415/color/image_raw`
- `/d415/depth/image_raw`
- `/d415/depth/camera_info`
- `/yolo/ball_position`
- `/yolo/confidence`
- `/yolo/ball_position_3d`
- `/odom`

## Expected Node Graph (Minimum)
- `parameter_bridge` (ros_gz_bridge)
- `robot_state_publisher`
- `controller_manager` + `jetbot_base_controller`
- `yolo_frisbee_detector`
- `yolo_3d_position_extractor`
- `yolo_3d_to_nav2_bridge` (milestone 3 / nav UAT)

## Known-Good Parameters
- `inference_device`: `auto|cuda:0|cpu`
- `perf_profile`: `compat|balanced|max`
- `headless`: `true|false`
- Detector input topic: `/d415/color/image_raw`
- UAT scenarios: `ros2_config/config/uat_coordinates.yaml`

## Coordinate UAT Output Contract
- `artifacts/uat/<timestamp>/detections.csv`
- `artifacts/uat/<timestamp>/summary.json`

`summary.json` includes:
- detection success rate
- mean and p95 XY error
- timeout and failure class counters
- pass/fail boolean

## Operator Sequence
1. Run Windows preflight: `scripts/windows_reinstall_preflight.ps1`
2. Bring up stack: `scripts/run_canonical_stack.ps1`
3. Run coordinate UAT: `scripts/run_coordinate_uat.ps1`
4. Run GUI milestone demos as needed.

## Notes
- Legacy and experimental launch/scripts remain in repo but are non-canonical.
- Canonical UAT pass/fail is always evaluated with `RuntimeTarget=robot_fidelity`.
