# Ubuntu 24.04/22.04 Compatibility Checklist

## Purpose
Track parity between the immediate execution baseline (`Ubuntu-24.04`) and fallback parity target (`Ubuntu-22.04`).

## Toolchain
- [ ] ROS distro installed (`jazzy` on 24.04, `humble` on 22.04)
- [ ] `ros_gz_sim` available
- [ ] Nav2 packages available
- [ ] Colcon build succeeds for workspace
- [ ] `ros2 pkg list` includes canonical package path (`chasebot_description` and/or `chasebot_sim`)

## Canonical Scripts
- [ ] `scripts/windows_reinstall_preflight.ps1` passes
- [ ] `scripts/run_canonical_stack.ps1 -RuntimeTarget robot_fidelity` launches without manual edits
- [ ] `scripts/run_coordinate_uat.ps1 -RuntimeTarget robot_fidelity` emits `detections.csv` and `summary.json`
- [ ] `scripts/run_orientation_uat.ps1 -RuntimeTarget robot_fidelity` emits snapshot bundle
- [ ] `scripts/run_nav2_readiness_uat.ps1 -RuntimeTarget robot_fidelity` emits `nav_summary.json`
- [ ] `scripts/run_autonomous_uat.ps1` emits session manifest and readiness report

## UAT Contracts
- [ ] Coordinate thresholds hold (`>=90%` success, mean/p95 within limits)
- [ ] Orientation thresholds hold (side/frame/snapshot thresholds)
- [ ] Nav2 readiness thresholds hold
- [ ] Failure classes populated (`no_detection`, `invalid_depth`, `stale_topic`, `transform_failure`)

## Notes
- 2026-02-25 current state on `Ubuntu-24.04`: blocked at M0 because ROS and workspace are not installed.
