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

1. Start gate lane:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -ProjectName chasecar_gate_replay_<ts> -Action up -RuntimeTarget robot_fidelity_orin -IncludeNav2Bringup $true -IncludeBridge $false`
2. Run full replay in one session:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_uat.ps1 -Action run -ProjectName chasecar_gate_replay_<ts> -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -CoreRosDistro kilted -UatMode full_replay -UatExecutionContext sim_gate`
3. Teardown:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -ProjectName chasecar_gate_replay_<ts> -Action down -RuntimeTarget robot_fidelity_orin -IncludeNav2Bringup $true -IncludeBridge $false`
   - `powershell -ExecutionPolicy Bypass -File scripts/run_compose_uat.ps1 -ProjectName chasecar_gate_replay_<ts> -Action down -RuntimeTarget robot_fidelity_orin`
4. Triage mode (individual phases):
   - `-UatMode coordinate|orientation|nav2`

## First Operator UAT Path

Preferred operator entrypoint for first promotion gate:

1. `powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin`

Behavior:

1. Scans and cleans stale `chasecar_gate_*` compose projects before bring-up.
2. Uses compose project naming pattern `chasecar_gate_firstuat_<timestamp>` unless `-ProjectName` is supplied.
3. Runs coordinate UAT first and blocks milestone 1 visual run if coordinate gate fails.
   - Uses `-UatExecutionContext sim_gate` by default for deterministic create/remove service access.
4. Writes session package:
   - `artifacts/session/<timestamp>/manifest.json`
   - `artifacts/session/<timestamp>/readiness_report.json`
5. Uses `-ExecutionLane host_ros` only for fallback troubleshooting.

## Compose Profiles

1. Gate lane:
   - `scripts/run_compose_gate.ps1`
2. Isaac lane:
   - `scripts/run_compose_isaac.ps1`
3. UAT orchestrator:
   - `scripts/run_compose_uat.ps1`
   - modes: `prepare|coordinate|orientation|nav2|first_uat|full_replay`

## Current Caution

1. Isaac runtime container requires NVIDIA Container Toolkit and valid image access.
2. `run_autonomous_uat.ps1` should be treated as orchestration glue; direct UAT scripts remain authoritative for triage.
3. If a long run appears stuck in WSL-hosted mode, stop with `wsl --shutdown` and rerun from a clean session.
4. `ros2 action list` includes clients and may show `/navigate_to_pose` even when no server is active. Use `ros2 action info /navigate_to_pose` and confirm `Action servers: 1` for readiness.
5. `scripts/run_compose_profile.ps1` now auto-resolves Docker Desktop CLI path (`C:\Program Files\Docker\Docker\resources\bin\docker.exe`) when `docker` is not on PATH.
6. For full replay, keep launch bridge disabled (`-IncludeBridge $false`) and rely on orchestrator-managed bridge startup during nav2 stage.
7. For GUI milestones, keep `-OpenFeedViewers $true` unless intentionally running screenshot-only mode; inspect `demo_summary.json -> viewers.feed_viewer_status` when feeds are not visible.

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
5. Milestone 1 visual evidence (when enabled):
   - `artifacts/demos/milestone_1_<timestamp>/operator_checklist.json`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/d415_color.png`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/yolo_debug.png`
   - `artifacts/demos/milestone_1_<timestamp>/demo_summary.json`
