# Ubuntu 24.04/22.04 Compatibility Checklist

## Purpose
Track parity between immediate execution baseline (`Ubuntu-24.04`) and compatibility lanes.

## Toolchain
- [ ] ROS distro installed (`kilted` primary, `lyrical` compatibility, optional `jazzy` bridge sidecar)
- [ ] `ros_gz_sim` available
- [ ] Nav2 packages available
- [ ] Colcon build succeeds for workspace
- [ ] `ros2 pkg list` includes canonical package path (`chasebot_description`) and `launch/*.launch.py` wrappers are reachable

## Canonical Scripts
- [ ] `scripts/windows_reinstall_preflight.ps1` passes
- [ ] `scripts/run_canonical_stack.ps1 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8` launches without manual edits
- [ ] `scripts/run_coordinate_uat.ps1 -RuntimeTarget robot_fidelity_orin` emits `detections.csv` and `summary.json`
- [ ] `scripts/run_orientation_uat.ps1 -RuntimeTarget robot_fidelity_orin` emits snapshot bundle
- [ ] `scripts/run_nav2_readiness_uat.ps1 -RuntimeTarget robot_fidelity_orin` emits `nav_summary.json`
- [ ] `scripts/run_autonomous_uat.ps1` emits session manifest and readiness report

## UAT Contracts
- [ ] Coordinate thresholds hold (`>=90%` success, mean/p95 within limits)
- [ ] Orientation thresholds hold (side/frame/snapshot thresholds)
- [ ] Nav2 readiness thresholds hold
- [ ] Failure classes populated (`no_detection`, `invalid_depth`, `stale_topic`, `transform_failure`)

## Notes
- 2026-02-26 rebuild state: Docker-first migration in progress; host + container prerequisites must be validated together.
