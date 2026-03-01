# Chasecar

Container-first ROS 2 stack for ball acquire/plan/track validation.

## Active Architecture (2026)

1. Gate lane (authoritative): ROS 2 `kilted` + Gazebo Jetty.
2. Fidelity lane (parallel): Isaac + Jazzy bridge sidecar.
3. Robot-fidelity target: `robot_fidelity_orin`.
4. Canonical inference backend: `tensorrt_int8`.

## First UAT (Operator Entry)

Run from Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 `
  -ExecutionLane container_kilted `
  -Distro Ubuntu-24.04 `
  -RuntimeTarget robot_fidelity_orin
```

Default behavior:

1. Cleans stale `chasecar_gate_*` compose projects.
2. Brings up gate lane with Nav2 disabled for coordinate truth stability.
3. Runs coordinate UAT in container lane (`sim_gate` execution context).
4. Runs Milestone 1 evidence capture when coordinate gate passes.
5. Tears down gate/UAT resources and writes session artifacts.

Required outputs:

1. `artifacts/session/<timestamp>/manifest.json`
2. `artifacts/session/<timestamp>/readiness_report.json`
3. `artifacts/uat/<timestamp>/summary.json` with `pass=true`
4. `artifacts/demos/milestone_1_<timestamp>/demo_summary.json` with `pass=true` (when visual enabled)

## Full Headless Replay (Coordinate + Orientation + Nav2)

```powershell
$proj = "chasecar_gate_replay_<timestamp>"
powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 `
  -Action up `
  -ProjectName $proj `
  -RuntimeTarget robot_fidelity_orin `
  -IncludeNav2Bringup $true `
  -IncludeBridge $false

powershell -ExecutionPolicy Bypass -File scripts/run_compose_uat.ps1 `
  -Action run `
  -ProjectName $proj `
  -RuntimeTarget robot_fidelity_orin `
  -UatMode full_replay `
  -UatExecutionContext sim_gate

powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 `
  -Action down `
  -ProjectName $proj `
  -RuntimeTarget robot_fidelity_orin `
  -IncludeNav2Bringup $true `
  -IncludeBridge $false

powershell -ExecutionPolicy Bypass -File scripts/run_compose_uat.ps1 `
  -Action down `
  -ProjectName $proj `
  -RuntimeTarget robot_fidelity_orin
```

Notes:

1. Coordinate and orientation run with deterministic target snapshots while robot remains stationary.
2. Nav2 stage uses managed bridge startup and deterministic target spawn before readiness monitoring.

## Pre-LLM Headless Push (Fast + Fidelity)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_headless_pre_llm.ps1 -Lane dual
```

This runs all low-level gates before high-level LLM wiring:

1. coordinate UAT
2. snapshot verification (`/d415/color/image_raw` vs `/yolo/debug_image`)
3. orientation UAT
4. nav2 readiness UAT
5. multi-target nav2 UAT

Verification notes:

1. Snapshot gate passes only when both feeds capture successfully, images are not byte-identical, mean diff meets threshold, and changed-pixel ratio meets threshold.
2. Nav2 readiness gate includes target-distance truth checks (improvement, retained progress, final distance, away ratio, and trend slope), not just goal status.

Lane modes:

1. `fast`: uses `workstation_max`, short timeouts, and fast-forward world `yolo_test_world_v6_clean_uat_fast.world`.
2. `fidelity`: uses `robot_fidelity_orin` on canonical world `yolo_test_world_v6_clean_uat.world`.
3. `dual`: runs `fast` then `fidelity`.

Lane-specific gate configs:

1. Fast Nav2 readiness: `ros2_config/config/nav2_readiness_fast.yaml`
2. Fidelity Nav2 readiness: `ros2_config/config/nav2_readiness_fidelity.yaml`
3. Fast multi-target: `ros2_config/config/multi_target_nav2_fast.yaml`
4. Fidelity multi-target: `ros2_config/config/multi_target_nav2_fidelity.yaml`
5. Fidelity soak multi-target: `ros2_config/config/multi_target_nav2_fidelity_soak.yaml`

Authoritative campaign command (3x dual + optional soak + RC package):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_campaign.ps1
```

Campaign outputs:

1. `artifacts/session/<timestamp>/pre_llm_campaign_trend.json`
2. `artifacts/session/<timestamp>/campaign_run_summary.json`
3. `artifacts/session/<timestamp>/rc/manifest.json` (when soak enabled)
4. `artifacts/session/<timestamp>/rc/readiness_report.json` (when soak enabled)

Latest frozen pre-LLM package (post-green campaign):

1. `artifacts/session/20260301T014018Z/pre_llm_campaign_trend.json`
2. `artifacts/session/20260301T015545Z/pre_llm_headless_summary.json`
3. `artifacts/session/20260301T014018Z/rc/manifest.json`
4. `artifacts/session/20260301T014018Z/rc/readiness_report.json`

Pre-LLM brain adapter smoke (no LLM planner yet):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_brain_adapter_smoke.ps1 -RuntimeTarget robot_fidelity_orin
```

Adapter smoke output:

1. `artifacts/session/<timestamp>/brain_adapter_smoke_summary.json`
2. Latest validated smoke: `artifacts/session/20260301T022219Z/brain_adapter_smoke_summary.json`

## Visual Milestones

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 1 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 90
powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 2 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 120
powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 3 -RuntimeTarget workstation_balanced -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -OpenFeedViewers $true -MaxRunSeconds 150
```

Headless milestone progression (current development default):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 2 -RuntimeTarget robot_fidelity_orin -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -MaxRunSeconds 90
powershell -ExecutionPolicy Bypass -File scripts/run_milestone_demo.ps1 -Milestone 3 -RuntimeTarget robot_fidelity_orin -WorldFile yolo_test_world_v6_clean_uat.world -WorldName yolo_test_world -EnsureDemoTarget -MaxRunSeconds 150
```

Milestone 1 now enforces deterministic target acquisition:

1. removes duplicate legacy ball models in-world
2. spawns one canonical red target (`frisbee_target_ball.sdf`) with bounded timeout/retries
3. requires `/yolo/confidence >= 0.50` to pass
4. requires debug overlay to differ from raw RGB evidence when confidence gate passes
5. in non-headless mode, verifies both feed viewers are running (`/d415/color/image_raw` and `/yolo/debug_image`)

Milestone 3 now enforces measurable motion:

1. `nav2.action_server_ready=true`
2. `motion.cmd_vel_message_count > 0`
3. `motion.odom_displacement_m >= MotionMinDistanceMeters` (default `0.40`)

## Artifact Contracts

1. Coordinate: `artifacts/uat/<timestamp>/{detections.csv,summary.json}`
2. Orientation: `artifacts/orientation/<timestamp>/{orientation_samples.csv,orientation_summary.json,snapshots/*.png}`
3. Snapshot verification: `artifacts/snapshots/<timestamp>/{d415_color.png,yolo_debug.png,image_diff.json,snapshot_summary.json}`
4. Nav2: `artifacts/nav2/<timestamp>/nav_summary.json`
5. Nav2 distance series: `artifacts/nav2/<timestamp>/distance_samples.csv`
6. Multi-target Nav2: `artifacts/nav2_multi/<timestamp>/{multi_target_samples.csv,multi_target_summary.json}`
7. Session: `artifacts/session/<timestamp>/{manifest.json,readiness_report.json,pre_llm_headless_summary.json}`
8. Milestone 1 evidence: `artifacts/demos/milestone_1_<timestamp>/{operator_checklist.json,demo_summary.json,screenshots/*.png}`

## Reference Docs

1. `docs/ACTIVE_WORKFLOW.md`
2. `docs/FIRST_UAT_RUNBOOK.md`
3. `docs/LEVEL_SET_2026-02-26.md`
4. `AGENTS.md`
