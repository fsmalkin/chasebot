# Active Workflow (Canonical 2026 Rebuild)

## Scope

This is the single source of truth for the rebuilt stack bring-up, UAT execution, and GUI rehearsal sequencing.

## Canonical Runtime Contract

1. `runtime_target`: `robot_fidelity_orin|workstation_balanced|workstation_max`
2. `sim_lane`: `jetty_gate|isaac_fidelity`
3. `inference_backend`: `tensorrt_int8`

Legacy compatibility:

- `robot_fidelity` is accepted as an alias and resolves to `robot_fidelity_orin`.

## Docker Profiles

1. Gate lane (authoritative):
   - `docker compose --profile gate up`
2. Isaac lane (high-fidelity):
   - `docker compose --profile isaac up`
3. UAT orchestrator:
   - `docker compose --profile uat run uat-orchestrator`

Windows wrappers:

1. `scripts/run_compose_gate.ps1`
2. `scripts/run_compose_isaac.ps1`
3. `scripts/run_compose_uat.ps1`

Compose hygiene:

1. Before a new run, stop stale gate projects sharing the same ROS domain:
   - `docker ps --format "table {{.Names}}\t{{.Status}}"`
   - `docker compose -p <stale_project> down --remove-orphans`
2. First-UAT wrapper project naming pattern:
   - `chasecar_gate_firstuat_<timestamp>`
3. Preferred first operator entrypoint performs stale gate cleanup automatically:
   - `scripts/run_first_uat.ps1`

## First Operator Path

Use this as the default first run on a fresh/recovered machine:

1. `powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin`
2. Runbook details: `docs/FIRST_UAT_RUNBOOK.md`

Key options:

1. `-Distro Ubuntu-24.04`
2. `-ExecutionLane container_kilted|host_ros` (default `container_kilted`)
3. `-RosDistro <name>` (used only when `ExecutionLane=host_ros`)
4. `-RuntimeTarget robot_fidelity_orin`
5. `-ProjectName chasecar_gate_firstuat_manual`
6. `-IncludeVisual true|false` (default `true`)
7. `-StepTimeoutMinutes <n>`
8. `-UatExecutionContext sim_gate|gate_stack|uat_orchestrator` (default `sim_gate`)

First-UAT contract:

1. Coordinate UAT must pass (`summary.json` has `pass=true`).
2. If visual is enabled, milestone 1 evidence bundle must exist.
3. Session outputs are always written to:
   - `artifacts/session/<timestamp>/manifest.json`
   - `artifacts/session/<timestamp>/readiness_report.json`
4. Readiness includes deterministic lane/timeout metadata:
   - `execution_lane`
   - `failure_class`
   - `step_timeout_s`
   - `container_core_ros_distro`
   - `detected_host_ros_distros`

## UAT Orchestrator Modes

Use `scripts/run_compose_uat.ps1 -UatMode <mode>`:

1. `prepare`
2. `coordinate`
3. `orientation`
4. `nav2`
5. `first_uat`
6. `full_replay`

Machine-readable markers emitted by orchestrator:

1. `STEP_RESULT=<step>:<status>:<artifact>`
2. `ARTIFACT_DIR=<path>`
3. `READINESS_REPORT=<path>`

## Canonical Launch Surfaces

1. `launch/sim_gate.launch.py`
2. `launch/perception_stack.launch.py`
3. `launch/nav_acquire_plan_track.launch.py`
4. `launch/sim_isaac_bridge.launch.py`

## Canonical Detector Runtime

1. Detector script: `ros2_scripts/chasecar_tensorrt_detector.py`
2. Backend: TensorRT INT8 (`inference_backend=tensorrt_int8`)
3. Engine config:
   - `runtime/tensorrt/calibration/calibration_config.yaml`

## Headless UAT Sequence (Container Lane)

1. Host preflight:
   - `scripts/bootstrap_docker_host.ps1`
2. Runtime sync:
   - `scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -SkipBuild`
3. Start gate lane:
   - `scripts/run_compose_gate.ps1 -ProjectName chasecar_gate_replay_<timestamp> -Action up -RuntimeTarget robot_fidelity_orin -IncludeNav2Bringup $true -IncludeBridge $false`
4. Run full replay in one containerized session:
   - `scripts/run_compose_uat.ps1 -Action run -ProjectName chasecar_gate_replay_<timestamp> -RuntimeTarget robot_fidelity_orin -UatMode full_replay -UatExecutionContext sim_gate`
   - Full replay uses orchestrator-managed nav2 bridge startup plus deterministic nav2 target spawn during the nav2 stage.
5. Teardown:
   - `scripts/run_compose_gate.ps1 -Action down -ProjectName chasecar_gate_replay_<timestamp> -RuntimeTarget robot_fidelity_orin -IncludeNav2Bringup $true -IncludeBridge $false`
   - `scripts/run_compose_uat.ps1 -Action down -ProjectName chasecar_gate_replay_<timestamp> -RuntimeTarget robot_fidelity_orin`
6. Optional raw sequence (triage mode):
   - `scripts/run_compose_gate.ps1 -Action up -ProjectName <name> -IncludeNav2Bringup $true -IncludeBridge $false`
   - `scripts/run_compose_uat.ps1 -Action run -ProjectName <name> -UatMode coordinate`
   - `scripts/run_compose_uat.ps1 -Action run -ProjectName <name> -UatMode orientation`
   - `scripts/run_compose_uat.ps1 -Action run -ProjectName <name> -UatMode nav2`

Fallback lane (`host_ros`) is non-canonical and for troubleshooting only.

## Visual UAT Sequence

Run only after headless gates are green:

1. `scripts/run_milestone_demo.ps1 -Milestone 1 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 90`
2. `scripts/run_milestone_demo.ps1 -Milestone 2 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 120`
3. `scripts/run_milestone_demo.ps1 -Milestone 3 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 150`

Milestone 1 pass criteria include:

1. deterministic target spawn succeeded
2. debug image capture succeeded
3. confidence sample from `/yolo/confidence` met threshold (`>= 0.50` default)
4. `/world/<name>/create` service became available before spawn
5. debug image differs from raw image evidence when confidence gate is met
6. non-headless feed viewers are alive when `-OpenFeedViewers $true`

## Artifact Contracts

1. Coordinate:
   - `artifacts/uat/<timestamp>/detections.csv`
   - `artifacts/uat/<timestamp>/summary.json`
2. Orientation:
   - `artifacts/orientation/<timestamp>/orientation_samples.csv`
   - `artifacts/orientation/<timestamp>/orientation_summary.json`
   - `artifacts/orientation/<timestamp>/snapshots/*.png`
3. Nav2:
   - `artifacts/nav2/<timestamp>/nav_summary.json`
4. Session:
   - `artifacts/session/<timestamp>/manifest.json`
   - `artifacts/session/<timestamp>/readiness_report.json`
5. Milestone 1 visual evidence:
   - `artifacts/demos/milestone_1_<timestamp>/operator_checklist.json`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/*.png`
   - `artifacts/demos/milestone_1_<timestamp>/demo_summary.json`
   - `demo_summary.json` includes `capture.detection_confidence*` and `demo_target.*`

## Failure Triage Path

1. `S0` fail in first-UAT:
   - Validate Docker daemon and rerun.
2. `S1` fail:
   - Inspect `artifacts/session/<ts>/logs/run_first_uat.log` for compose bring-up failures.
3. `S2` fail with `threshold_failed`:
   - Review `artifacts/uat/<ts>/summary.json` for gate metrics.
4. `S2` fail with `service_unavailable`:
   - Check `/world/<world>/create` readiness in coordinate logs and rerun from a clean project.
5. `S2` fail with `timeout`:
   - Increase `-StepTimeoutMinutes` and rerun from a clean compose project.
6. `S3` blocked:
   - Expected when coordinate gate fails.
7. `S4` fail:
   - Run both down commands manually for the project (`run_compose_gate.ps1` and `run_compose_uat.ps1`).
8. Visual demo shows duplicate balls:
   - Use clean UAT world with `-EnsureDemoTarget`; avoid manual ad-hoc spawns.
9. Visual demo raw/debug windows look identical:
   - Check `demo_summary.json -> capture.detection_above_threshold`; if false, detector has no valid target yet.
10. Visual demo shows sim only with no camera windows:
   - Keep `-OpenFeedViewers $true` and check `demo_summary.json -> viewers.feed_viewer_status`.
   - If status is `rqt_image_view_missing`, install `rqt_image_view` in the active ROS distro.

## Interface Contracts

1. Isaac bridge allowlist:
   - `runtime/contracts/isaac_bridge_allowlist.yaml`
2. Message schema manifest:
   - `runtime/contracts/message_schema_manifest.yaml`
3. LLM pre-integration control contract:
   - `runtime/contracts/llm_control_contract.yaml`

## Compatibility Entry Points

Preferred:

1. `scripts/run_chasecar_stack.ps1`
2. `scripts/run_chasecar_coordinate_uat.ps1`

Compatibility wrappers:

1. `scripts/run_chasebot_stack_compat.ps1`
2. `scripts/run_chasebot_coordinate_uat_compat.ps1`

## Notes

1. Gazebo Classic is non-canonical and not used in rebuilt promotion gates.
2. Kilted is primary; Lyrical compatibility runs in CI.
3. Isaac runs behind a Jazzy bridge sidecar contract until native Kilted support is validated.
4. `ros2 action list` includes action clients; validate server availability with `ros2 action info /navigate_to_pose` and check `Action servers: 1`.
