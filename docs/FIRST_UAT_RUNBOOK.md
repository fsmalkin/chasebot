# First UAT Runbook

## Purpose

Run the first deterministic operator UAT on a rebuilt machine and produce a session package with clear pass/fail gates.

For the browser-dashboard operator flow, use [Dashboard Operator Guide](./DASHBOARD_OPERATOR_GUIDE.md). The dashboard remains the control/status plane, while Xpra is the recommended live operator view. This runbook stays focused on orchestration, gating, and artifact interpretation.

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
    - Do not treat native Gazebo/X11 as authoritative.
    - Prefer recorded-first review:
    - `powershell -ExecutionPolicy Bypass -File scripts/run_recorded_visual_demo.ps1 -Milestone 3 -RuntimeTarget robot_fidelity_orin -SessionId <session_id>`
    - For live review, prefer the dashboard's `Open Xpra` link and keep the browser-dashboard rehearsal path as validation tooling:
    - `powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 2 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -Headless true -VisualSurface browser_dashboard -WorldSurface streamed_sim -OpenFeedViewers true -AutoOpenVisualSurface true -RequireParityGreenForOperatorView false`

## Milestone 3 Motion Triage (Headless-Compatible)

Use `artifacts/demos/milestone_3_<timestamp>/demo_summary.json`:

1. `nav2.action_server_ready=false`
   - Nav2 stack is not fully ready.
   - Check `logs/nav2.log` and verify `/navigate_to_pose` server availability.
2. `motion.cmd_vel_message_count=0`
   - Treat as diagnostic unless displacement/progress checks also fail.
   - Check `logs/bridge.log` and `logs/cmd_vel_relay.log`.
3. `motion.odom_seen=false`
   - Odometry topic bridging is missing.
   - Validate `/odom` and `/model/jetbot/odometry` availability in the launch stack.
4. `motion.odom_displacement_m < motion.min_distance_m`
   - Robot moved insufficiently for pass gate.
   - Increase run duration or investigate controller/planner instability before lowering threshold.
5. Robot appears to drive backward in the streamed sim world:
   - Treat this as a hard trust failure, not a cosmetic issue.
   - Compare `/jetbot_base_controller/odom` against `/world/<world>/dynamic_pose/info`.
   - Confirm negative wheel radius multipliers are still present in:
   - `ros2_config/config/jetbot_diff_drive_v1.0.0.yaml`
   - `ros2_config/config/jetbot_controllers.yaml`

## LLM-Ready Handoff Checklist

Run this only after first-UAT promotion is already green:

1. `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_campaign.ps1`
   - Default includes same-session GUI rehearsal + parity checks (`-IncludeGuiParity true`).
2. `powershell -ExecutionPolicy Bypass -File scripts/run_brain_adapter_smoke.ps1 -RuntimeTarget robot_fidelity_orin`
3. `powershell -ExecutionPolicy Bypass -File scripts/run_brain_intent_shell.ps1 -RuntimeTarget robot_fidelity_orin`

Required handoff artifacts:

1. `artifacts/session/<timestamp>/pre_llm_campaign_trend.json`
2. `artifacts/session/<timestamp>/campaign_run_summary.json`
3. `artifacts/session/<timestamp>/rc/manifest.json`
4. `artifacts/session/<timestamp>/rc/readiness_report.json`
5. `runtime/contracts/llm_control_contract.yaml`
6. `artifacts/session/<timestamp>/brain_adapter_smoke_summary.json`
7. `artifacts/session/<timestamp>/brain_intent_shell_summary.json`

Current full campaign baseline (post world-stream recovery):

1. `artifacts/session/20260309T063355Z/pre_llm_campaign_trend.json`
2. `artifacts/session/20260309T063355Z/campaign_run_summary.json`
3. `artifacts/session/20260309T063355Z/rc/manifest.json`
4. `artifacts/session/20260309T063355Z/rc/readiness_report.json`
5. `artifacts/session/20260309T073224Z/pre_llm_headless_summary.json` (soak)
6. `artifacts/session/20260312T001204Z/brain_adapter_smoke_summary.json` (adapter smoke)
7. `artifacts/session/20260312T001244Z/brain_intent_shell_summary.json` (deterministic planner shell)

Latest validated same-session visual package:

1. `artifacts/session/20260312T013442Z/pre_llm_headless_summary.json`
2. `artifacts/session/20260312T013442Z/visual/visual_demo_summary_recorded.json`
3. `artifacts/session/20260312T013442Z/pre_llm_gui_rehearsal_summary.json`
4. `artifacts/session/20260312T013442Z/parity_summary.json`

Operator visual signoff order:

1. Single-target M3 browser run first:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 3 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -Headless true -VisualSurface browser_dashboard -WorldSurface streamed_sim -OpenFeedViewers true -AutoOpenVisualSurface true -RequireParityGreenForOperatorView false -OperatorPhase M3 -TargetId single_target -DemoTargetRelative false -DemoTargetX 1.10 -DemoTargetY 0.00 -DemoTargetZ 0.05 -MaxRunSeconds 150`
2. Multi-target GUI rehearsal second:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_gui_rehearsal.ps1 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -SessionId <session_id> -HeadlessSummaryPath artifacts/session/<session_id>/pre_llm_headless_summary.json -OpenFeedViewers false -VisualSurface browser_dashboard -WorldSurface streamed_sim`
   - This browser-dashboard wrapper remains unchanged validation tooling in v1.
3. Dashboard now shows:
   - `phase`
   - `target_id`
   - `target_transition_active`
   Use these fields to explain target resets during multi-target rehearsal.

Parity-first GUI readiness (required before operator live view):

1. Run headless session:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_headless_pre_llm.ps1 -Lane fidelity`
2. Rehearse GUI on the same session:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_gui_rehearsal.ps1 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -SessionId <session_id> -HeadlessSummaryPath artifacts/session/<session_id>/pre_llm_headless_summary.json -OpenFeedViewers false -VisualSurface browser_dashboard -WorldSurface streamed_sim`
3. Verify parity:
   - `artifacts/session/<session_id>/parity_summary.json` with `pass=true`
4. Only then run operator view:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_gui_rehearsal.ps1 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -SessionId <session_id> -HeadlessSummaryPath artifacts/session/<session_id>/pre_llm_headless_summary.json -OpenFeedViewers true -VisualSurface browser_dashboard -WorldSurface streamed_sim -AutoOpenVisualSurface true`
   - The browser world pane remains available for validation, but the recommended live operator view is Xpra from the dashboard's `Open Xpra` link.
5. Current validated same-session baseline:
   - `artifacts/session/20260312T013442Z/pre_llm_headless_summary.json`
   - `artifacts/session/20260312T013442Z/visual/visual_demo_summary_recorded.json`
   - `artifacts/session/20260312T013442Z/pre_llm_gui_rehearsal_summary.json`
   - `artifacts/session/20260312T013442Z/parity_summary.json`

Required pass criteria:

1. Campaign report `campaign.all_green=true` for the 3 dual runs.
2. Fidelity soak is green with Nav2 duration `>= 1200s`.
3. Fidelity soak multi-target run has `goal_count >= 10`.
4. RC readiness report has `pass=true`.
5. `llm_control_contract.yaml` remains in `contract_status: frozen_pre_llm`.
6. Brain adapter smoke report has `pass=true`.

Known limitations before full LLM wiring:

1. High-level behavior planning is not implemented in this phase.
2. GUI milestone replay is still required before final operator handoff.
3. Isaac lane remains parity-only and does not replace Jetty gate authority.

Visual parity triage failure classes:

1. `rgb_stream_timeout`
2. `debug_stream_timeout`
3. `odom_timeout`
4. `nav2_action_unavailable`
5. `target_distance_not_improving`
6. `lane_mismatch`
7. `feed_viewer_unavailable`
8. `visual_bundle_missing`
9. `world_stream_client_crash`
10. `world_stream_blank`
11. `world_stream_scene_missing`
12. `world_stream_robot_not_visible`
13. `world_stream_target_not_visible`
14. `world_stream_partition_mismatch`
