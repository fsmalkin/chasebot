# First UAT Runbook

## Purpose

Run the first deterministic operator UAT on a rebuilt machine and produce a session package with clear pass/fail gates.

## Preconditions

1. Repo branch is `recovery/uat-full-robot-2026-02`.
2. Docker Desktop is running and Linux engine is reachable.
3. WSL distro exists and starts:
   - `wsl -d Ubuntu-24.04 -- bash -lc "echo ok"`
4. Host ROS install is optional for default first-UAT lane.
   - Canonical runtime is `kilted` inside containers.
   - Host ROS is only used when `-ExecutionLane host_ros`.
5. Runtime source mirror is synced if you use `~/ros2_ws/src/chasecar_runtime`.

## First UAT Command

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 `
  -ExecutionLane container_kilted `
  -Distro Ubuntu-24.04 `
  -RuntimeTarget robot_fidelity_orin `
  -UatExecutionContext sim_gate
```

Optional:

```powershell
# disable visual milestone 1 for headless-only triage
powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 `
  -ExecutionLane container_kilted `
  -Distro Ubuntu-24.04 `
  -RuntimeTarget robot_fidelity_orin `
  -IncludeVisual false

# fallback lane (host ROS)
powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 `
  -ExecutionLane host_ros `
  -Distro Ubuntu-24.04 `
  -RosDistro jazzy `
  -RuntimeTarget robot_fidelity_orin
```

## What The Script Does

1. Scans stale `chasecar_gate_*` compose projects and cleans them.
2. Brings up gate lane with Nav2 bringup disabled.
3. Runs coordinate UAT through compose UAT mode (`scripts/run_compose_uat.ps1 -UatMode coordinate`) for default lane.
   - Default execution context is `sim_gate` for stable world service access.
4. If coordinate pass is green and visual enabled, runs Milestone 1 demo with evidence capture.
5. Tears down both gate and UAT compose resources.
6. Writes session artifacts.

## Required Outputs

1. `artifacts/session/<timestamp>/manifest.json`
2. `artifacts/session/<timestamp>/readiness_report.json`
3. If visual enabled:
   - `artifacts/demos/milestone_1_<timestamp>/operator_checklist.json`
   - `artifacts/demos/milestone_1_<timestamp>/demo_summary.json`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/d415_color.png`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/yolo_debug.png`

## Pass/Fail Interpretation

1. `first_uat_complete=true` in `readiness_report.json` means the first UAT promotion gate passed.
2. Step-level status is in `readiness_report.json -> steps[]`.
3. Readiness includes:
   - `execution_lane`
   - `failure_class`
   - `step_timeout_s`
   - `container_core_ros_distro`
   - `detected_host_ros_distros`
4. Coordinate gate is authoritative:
   - Must produce `summary.json` with `pass=true`.
5. Visual gate is required when `-IncludeVisual true`:
   - Evidence bundle must exist and `demo_summary.json` should report `pass=true`.

## Common Recovery Steps

1. Docker daemon unavailable:
   - Start Docker Desktop.
   - Verify: `powershell -ExecutionPolicy Bypass -File scripts/bootstrap_docker_host.ps1 -ExpectedDistro Ubuntu-24.04`
   - Re-run `run_first_uat.ps1`.
2. Host ROS distro mismatch:
   - Stay on `-ExecutionLane container_kilted` unless actively triaging host lane behavior.
   - Keep `kilted` as canonical container target in release gates.
   - Keep `-UatExecutionContext sim_gate` for canonical first-UAT runs.
3. Stale compose contamination:
   - Wrapper handles this automatically, but manual fallback is:
   - `scripts/run_compose_gate.ps1 -Action down -ProjectName <stale_project>`
   - `scripts/run_compose_uat.ps1 -Action down -ProjectName <stale_project>`
4. Visual run leaves processes alive:
   - `run_milestone_demo.ps1 -MaxRunSeconds <n>` enforces budgeted auto-stop.
   - Manual fallback: use `demo_pids.json` and kill listed WSL PIDs.
5. Visual Milestone 1 shows empty world or duplicate targets:
   - Use canonical command with deterministic target handling:
   - `scripts/run_milestone_demo.ps1 -Milestone 1 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 90`
6. Visual raw and debug images look identical:
   - Check `demo_summary.json` fields:
   - `capture.detection_seen`
   - `capture.detection_confidence`
   - `capture.detection_above_threshold`
   - `capture.overlay_distinct`
   - If confidence gate is false, reposition camera/target and rerun.
7. Visual run shows Gazebo but no feed windows:
   - Check `demo_summary.json -> viewers.feed_viewer_status`.
   - If `rqt_image_view_missing`, install `rqt_image_view` for active ROS distro.

## Milestone 3 Motion Triage (Headless-Compatible)

Use `artifacts/demos/milestone_3_<timestamp>/demo_summary.json`:

1. `nav2.action_server_ready=false`
   - Nav2 stack is not fully ready.
   - Check `logs/nav2.log` and verify `/navigate_to_pose` server availability.
2. `motion.cmd_vel_message_count=0`
   - Bridge/goal flow did not generate drive commands.
   - Check `logs/bridge.log` and `logs/cmd_vel_relay.log`.
3. `motion.odom_seen=false`
   - Odometry topic bridging is missing.
   - Validate `/odom` and `/model/jetbot/odometry` availability in the launch stack.
4. `motion.odom_displacement_m < motion.min_distance_m`
   - Robot moved insufficiently for pass gate.
   - Increase run duration or investigate controller/planner instability before lowering threshold.
