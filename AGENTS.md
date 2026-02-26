# Chasecar Agent Notes

This file captures repo-specific execution guidance for coding agents.

## Baseline

1. Runtime substrate: Docker-first (`docker compose` profiles).
2. Primary ROS distro: `kilted`.
3. Compatibility lane: `lyrical` (smoke + selected UAT).
4. Runtime workspace mirror: `~/ros2_ws/src/chasecar_runtime`.
5. Authoritative runtime target: `robot_fidelity_orin`.
6. Canonical inference backend: `tensorrt_int8`.

## First Steps Per Session

1. Check repo state: `git status --short`.
2. Ensure no stale compose projects are running on the same ROS domain:
   - `docker ps --format "table {{.Names}}\t{{.Status}}"`
   - Stop stale gate stacks before starting a new session.
3. Run host bootstrap checks:
   - `powershell -ExecutionPolicy Bypass -File scripts/bootstrap_docker_host.ps1 -ExpectedDistro Ubuntu-24.04`
4. Sync source into runtime mirror:
   - `powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro kilted`
5. Bring up gate lane:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -Action up -Build`

## Canonical Headless UAT Path

1. Start gate lane for deterministic perception checks (Nav2 disabled):
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -ProjectName chasecar_gate_nav2fix -Action up`
2. Coordinate UAT:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_coordinate_uat.ps1 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro kilted`
3. Orientation UAT:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_orientation_uat.ps1 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro kilted`
4. Recreate gate lane with Nav2 enabled for navigation readiness:
   - `$env:GATE_INCLUDE_NAV2_BRINGUP='true'`
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -ProjectName chasecar_gate_nav2fix -Action up`
5. Spawn deterministic target before Nav2 readiness run (if using raw runner).
6. Nav2 readiness UAT:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_nav2_readiness_uat.ps1 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro kilted`

## Compose Profiles

1. Gate lane:
   - `scripts/run_compose_gate.ps1`
2. Isaac lane:
   - `scripts/run_compose_isaac.ps1`
3. UAT orchestrator:
   - `scripts/run_compose_uat.ps1`

## Current Caution

1. Isaac runtime container requires NVIDIA Container Toolkit and valid image access.
2. `run_autonomous_uat.ps1` should be treated as orchestration glue; direct UAT scripts remain authoritative for triage.
3. If a long run appears stuck in WSL-hosted mode, stop with `wsl --shutdown` and rerun from a clean session.
4. `ros2 action list` includes clients and may show `/navigate_to_pose` even when no server is active. Use `ros2 action info /navigate_to_pose` and confirm `Action servers: 1` for readiness.
5. `scripts/run_compose_profile.ps1` now auto-resolves Docker Desktop CLI path (`C:\Program Files\Docker\Docker\resources\bin\docker.exe`) when `docker` is not on PATH.

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
4. Session packaging:
   - `artifacts/session/<timestamp>/manifest.json`
   - `artifacts/session/<timestamp>/readiness_report.json`
