# Active Workflow (Canonical)

## Scope
This file is the single source of truth for what to run for recovery, UAT, and GUI milestone demos.

## Canonical Stack Components
1. Simulation launch: `jetbot_gz_control_camera_test_v5.launch.py`
2. Detector: `ros2_yolo_detector_frisbee_quiet.py`
3. 3D extractor: `yolo_3d_position_extractor.py`
4. Nav bridge: `yolo_3d_to_nav2_bridge.py`

## Canonical Entry Scripts (Windows)
1. `scripts/sync_runtime_workspace.ps1`
2. `scripts/run_canonical_stack.ps1`
3. `scripts/run_coordinate_uat.ps1`
4. `scripts/run_orientation_uat.ps1`
5. `scripts/run_nav2_readiness_uat.ps1`
6. `scripts/run_autonomous_uat.ps1`
7. `scripts/run_milestone_demo.ps1 -Milestone <1|2|3>`

## Execution Policy (Current)
1. For active validation, run milestone scripts directly (`run_coordinate_uat.ps1`, `run_orientation_uat.ps1`, `run_nav2_readiness_uat.ps1`).
2. Treat `run_autonomous_uat.ps1` as experimental until wrapper soak handling is stabilized.
3. Before each long UAT run, reset stale WSL ROS/Gazebo state with `wsl --shutdown`.
4. If any run times out or appears stuck, stop it with `wsl --shutdown`, then rerun from a clean session.
5. For iterative UAT loops, use `scripts/sync_runtime_workspace.ps1 -SkipBuild` unless package metadata changed.

## Baseline Runtime
1. Primary execution baseline: `Ubuntu-24.04`
2. ROS distro resolution: `auto` (`jazzy` preferred, `humble` fallback)
3. Workspace default: `~/ros2_ws`

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

## Orientation UAT Output Contract
- `artifacts/orientation/<timestamp>/orientation_samples.csv`
- `artifacts/orientation/<timestamp>/orientation_summary.json`
- `artifacts/orientation/<timestamp>/snapshots/*.png`

## Nav2 Readiness Output Contract
- `artifacts/nav2/<timestamp>/nav_summary.json`
- required fields: `goal_accept_rate`, `goal_success_rate`, `cmd_vel_publish_stability`, `planner/controller_error_counts`, `tracking_continuity_score`, `pass`

## Session Manifest Contract
- `artifacts/session/<timestamp>/manifest.json`
- `artifacts/session/<timestamp>/readiness_report.json`

## Operator Sequence
1. Run Windows preflight: `scripts/windows_reinstall_preflight.ps1`
2. Sync runtime mirror to WSL ext4: `scripts/sync_runtime_workspace.ps1`
3. Bring up stack: `scripts/run_canonical_stack.ps1`
4. Run coordinate UAT: `scripts/run_coordinate_uat.ps1`
5. Run GUI milestone demos as needed.

## Notes
- Legacy and experimental launch/scripts remain in repo but are non-canonical.
- Canonical UAT pass/fail is always evaluated with `RuntimeTarget=robot_fidelity`.
- For heavy runs, prefer ext4 runtime source (`~/ros2_ws/src/chasecar_runtime`) over `/mnt/d/...` to avoid WSL I/O stalls.
- Latest known-good headless gates (UTC 2026-02-25):
  - Coordinate UAT pass: `/root/ros2_ws/src/chasecar_runtime/artifacts/uat/20260225T222740Z/summary.json`
  - Orientation UAT pass: `/root/ros2_ws/src/chasecar_runtime/artifacts/orientation/20260225T222650Z/orientation_summary.json`
  - Nav2 readiness pass: `/root/ros2_ws/src/chasecar_runtime/artifacts/nav2/20260225T223604Z/nav_summary.json`
