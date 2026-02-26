# Chasecar Agent Notes

This file captures repo-specific execution guidance for coding agents.

## Baseline

1. Primary runtime distro: `Ubuntu-24.04` on WSL2.
2. ROS distro: `jazzy` (auto-resolve supported by scripts).
3. Runtime workspace mirror: `~/ros2_ws/src/chasecar_runtime`.

## First Steps Per Session

1. Check repo state: `git status --short`.
2. Reset stale WSL processes before long runs: `wsl --shutdown`.
3. Sync source into runtime mirror:
   - `powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro jazzy`

## Canonical Headless UAT Path

1. Coordinate UAT:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_coordinate_uat.ps1 -RuntimeTarget robot_fidelity -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro jazzy`
2. Orientation UAT:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_orientation_uat.ps1 -RuntimeTarget robot_fidelity -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro jazzy`
3. Nav2 readiness UAT:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_nav2_readiness_uat.ps1 -RuntimeTarget robot_fidelity -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro jazzy`

## Current Caution

1. `scripts/run_autonomous_uat.ps1` is not the preferred execution path yet and may stall during soak handling.
2. Use direct milestone scripts for reliable progress and artifact generation.
3. If a run appears stuck, stop immediately with `wsl --shutdown` and rerun from a clean session.

## Artifact Contracts

1. Coordinate:
   - `artifacts/uat/<timestamp>/detections.csv`
   - `artifacts/uat/<timestamp>/summary.json`
2. Orientation:
   - `artifacts/orientation/<timestamp>/orientation_samples.csv`
   - `artifacts/orientation/<timestamp>/orientation_summary.json`
   - `artifacts/orientation/<timestamp>/snapshots/*.png`
3. Nav2 readiness:
   - `artifacts/nav2/<timestamp>/nav_summary.json`
