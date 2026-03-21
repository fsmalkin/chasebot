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
   - modes: `prepare|coordinate|snapshot|orientation|nav2|multi_target|first_uat|full_replay|pre_llm`

## Pre-LLM Headless Push

1. Preferred command:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_headless_pre_llm.ps1 -Lane dual`
2. Full campaign command (3 dual runs + soak + RC package):
   - `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_campaign.ps1`
   - Default now includes same-session GUI rehearsal + parity checks for each dual run (`-IncludeGuiParity true`).
3. Brain adapter smoke (post-campaign, pre-GUI):
   - `powershell -ExecutionPolicy Bypass -File scripts/run_brain_adapter_smoke.ps1 -RuntimeTarget robot_fidelity_orin`
4. Deterministic planner shell smoke (first post-freeze integration step):
   - `powershell -ExecutionPolicy Bypass -File scripts/run_brain_intent_shell.ps1 -RuntimeTarget robot_fidelity_orin`
5. Adversarial must-fail suite:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_adversarial.ps1 -RuntimeTarget robot_fidelity_orin`
6. Final GUI rehearsal wrapper:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_pre_llm_gui_rehearsal.ps1 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -OpenFeedViewers false -VisualSurface browser_dashboard`
7. Visual/headless parity comparator:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_visual_parity_check.ps1 -SessionId <session_id> -HeadlessSummaryPath artifacts/session/<session_id>/pre_llm_headless_summary.json -GuiSummaryPath artifacts/session/<session_id>/pre_llm_gui_rehearsal_summary.json`
8. Recorded visual evidence wrapper:
   - `powershell -ExecutionPolicy Bypass -File scripts/run_recorded_visual_demo.ps1 -Milestone 3 -RuntimeTarget robot_fidelity_orin -SessionId <session_id>`
2. Lane behavior:
   - `fast`: shorter timeouts + fast-forward world (`yolo_test_world_v6_clean_uat_fast.world`)
   - `fidelity`: authoritative `robot_fidelity_orin` replay on canonical world
   - `dual`: fast first, fidelity second
3. Stage order in `pre_llm`:
   - `coordinate -> snapshot -> orientation -> nav2 -> multi_target`
   - Snapshot gate is two-signal: mean diff + changed-pixel ratio (not byte-identity alone).
   - Nav2 gate requires target-distance progress truth checks (trend, away-ratio, retained progress, final distance).
4. Lane-specific config defaults:
   - fast nav2: `ros2_config/config/nav2_readiness_fast.yaml`
   - fidelity nav2: `ros2_config/config/nav2_readiness_fidelity.yaml`
   - fast multi-target: `ros2_config/config/multi_target_nav2_fast.yaml`
   - fidelity multi-target: `ros2_config/config/multi_target_nav2_fidelity.yaml`
   - fidelity soak multi-target: `ros2_config/config/multi_target_nav2_fidelity_soak.yaml`
5. Latest frozen campaign + soak + smoke package:
   - campaign summary: `artifacts/session/20260309T063355Z/campaign_run_summary.json`
   - campaign trend: `artifacts/session/20260309T063355Z/pre_llm_campaign_trend.json`
   - soak summary: `artifacts/session/20260309T073224Z/pre_llm_headless_summary.json`
   - rc readiness: `artifacts/session/20260309T063355Z/rc/readiness_report.json`
   - adversarial summary: `artifacts/session/20260303T061055Z/adversarial_headless_summary.json`
   - brain adapter smoke: `artifacts/session/20260312T001204Z/brain_adapter_smoke_summary.json`
   - deterministic planner shell: `artifacts/session/20260312T001244Z/brain_intent_shell_summary.json`
   - latest same-session headless: `artifacts/session/20260312T013442Z/pre_llm_headless_summary.json`
   - latest same-session recorded visual: `artifacts/session/20260312T013442Z/visual/visual_demo_summary_recorded.json`
   - latest same-session GUI rehearsal: `artifacts/session/20260312T013442Z/pre_llm_gui_rehearsal_summary.json`
   - latest same-session parity: `artifacts/session/20260312T013442Z/parity_summary.json`

## Current Caution

1. Isaac runtime container requires NVIDIA Container Toolkit and valid image access.
2. `run_autonomous_uat.ps1` should be treated as orchestration glue; direct UAT scripts remain authoritative for triage.
3. If a long run appears stuck in WSL-hosted mode, stop with `wsl --shutdown` and rerun from a clean session.
4. `ros2 action list` includes clients and may show `/navigate_to_pose` even when no server is active. Use `ros2 action info /navigate_to_pose` and confirm `Action servers: 1` for readiness.
5. `scripts/run_compose_profile.ps1` now auto-resolves Docker Desktop CLI path (`C:\Program Files\Docker\Docker\resources\bin\docker.exe`) when `docker` is not on PATH.
6. For full replay, keep launch bridge disabled (`-IncludeBridge $false`) and rely on orchestrator-managed bridge startup during nav2 stage.
7. For GUI parity campaigns, require at least one viewer-enabled rehearsal (`-OpenFeedViewers $true`) per cycle; if viewer plumbing fails, the run must fail closed (`failure_class=feed_viewer_unavailable`).
8. For headless milestone promotion, run M2 then M3 with `robot_fidelity_orin`; M3 pass requires motion evidence (`nav2.action_server_ready`, `motion.odom_displacement_m`, `motion.target_progress_ok`, `motion.pass`).
9. `run_compose_gate.ps1` supports `-WorldFile`, `-GatePerfProfile`, and `-InferenceDevice`; use these for fast-lane acceleration while keeping fidelity lanes on canonical defaults.
10. `run_milestone_demo.ps1` and `run_pre_llm_gui_rehearsal.ps1` now sweep stale viewer/sim/nav processes before each run attempt.
11. `run_pre_llm_gui_rehearsal.ps1` defaults to cleanup-on-exit; set `-KeepWindowsOpen true` only when an operator is actively watching.
12. GUI parity truth is authoritative only on `container_kilted`; `host_ros` is debug-only and non-authoritative.
13. Operator-facing GUI (`-OpenFeedViewers true`) is blocked by default unless the latest `parity_summary.json` is green.
14. Container-lane live feed viewers are currently strict-gated: if `-OpenFeedViewers true` is requested but viewer plumbing is unavailable, milestone runs fail with `failure_class=feed_viewer_unavailable` instead of reporting a false visual pass.
15. Native Windows X11 / Gazebo windows are `debug_only` and non-promoting. Authoritative visual review is now:
   - recorded bundle under `artifacts/session/<session_id>/visual/`
   - streamed-sim browser dashboard via `-VisualSurface browser_dashboard -WorldSurface streamed_sim`
   - the browser world pane comes from the Gazebo world camera sensor topic `/observer_world/image_raw`, not the old noVNC/X11 path
16. Browser-dashboard and recorded visual review must stay on the same `container_kilted` session ID as the headless run. Promotion requires same-session visual bundle + dashboard + parity pass.
17. World-stream promotion requires `world_stream_ready=true`, `scene_content_ok=true`, `robot_visible_ok=true`, `target_visible_ok=true`, and `same_session_partition=true`.
18. Diff-drive sign parity is now fixed in:
   - `ros2_config/config/jetbot_diff_drive_v1.0.0.yaml`
   - `ros2_config/config/jetbot_controllers.yaml`
   Both use negative wheel radius multipliers so Gazebo world motion and ROS odom agree. If the robot appears to drive backward again, compare `/jetbot_base_controller/odom` against `/world/<world>/dynamic_pose/info` before trusting nav results.
19. Operator visual signoff sequence is:
   - single-target M3 browser run first (`phase=M3`, `target_id=single_target`)
   - multi-target GUI rehearsal second (`phase=multi_target_rehearsal`)
   - do not use the full rehearsal wrapper as the first human-facing demo.
20. Browser dashboard status chips now surface:
   - `phase`
   - `target_id`
   - `target_transition_active`
   Use these to distinguish real target resets from faults during multi-target rehearsal.

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
   - `artifacts/nav2/<timestamp>/distance_samples.csv`
4. Snapshot verification:
   - `artifacts/snapshots/<timestamp>/d415_color.png`
   - `artifacts/snapshots/<timestamp>/yolo_debug.png`
   - `artifacts/snapshots/<timestamp>/image_diff.json`
   - `artifacts/snapshots/<timestamp>/snapshot_summary.json`
5. Multi-target Nav2:
   - `artifacts/nav2_multi/<timestamp>/multi_target_samples.csv`
   - `artifacts/nav2_multi/<timestamp>/multi_target_summary.json`
6. Session packaging:
   - `artifacts/session/<timestamp>/manifest.json`
   - `artifacts/session/<timestamp>/readiness_report.json`
7. Headless pre-LLM summary:
   - `artifacts/session/<timestamp>/pre_llm_headless_summary.json`
8. Campaign and RC packaging:
   - `artifacts/session/<timestamp>/pre_llm_campaign_trend.json`
   - `artifacts/session/<timestamp>/campaign_run_summary.json`
   - `artifacts/session/<timestamp>/rc/manifest.json`
   - `artifacts/session/<timestamp>/rc/readiness_report.json`
9. Milestone 1 visual evidence (when enabled):
   - `artifacts/demos/milestone_1_<timestamp>/operator_checklist.json`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/d415_color.png`
   - `artifacts/demos/milestone_1_<timestamp>/screenshots/yolo_debug.png`
   - `artifacts/demos/milestone_1_<timestamp>/demo_summary.json`
10. Brain adapter smoke:
   - `artifacts/session/<timestamp>/brain_adapter_smoke_summary.json`
11. Deterministic planner shell:
   - `artifacts/session/<timestamp>/brain_intent_shell_summary.json`
12. GUI rehearsal + parity:
   - `artifacts/session/<timestamp>/pre_llm_gui_rehearsal_summary.json`
   - `artifacts/session/<timestamp>/parity_summary.json`
13. Recorded/browser visual bundle:
   - `artifacts/session/<timestamp>/visual/raw_camera.mp4`
   - `artifacts/session/<timestamp>/visual/raw_camera_recorded.mp4`
   - `artifacts/session/<timestamp>/visual/raw_camera_browser_dashboard.mp4`
   - `artifacts/session/<timestamp>/visual/yolo_debug.mp4`
   - `artifacts/session/<timestamp>/visual/yolo_debug_recorded.mp4`
   - `artifacts/session/<timestamp>/visual/yolo_debug_browser_dashboard.mp4`
   - `artifacts/session/<timestamp>/visual/topdown_telemetry.mp4`
   - `artifacts/session/<timestamp>/visual/topdown_telemetry_recorded.mp4`
   - `artifacts/session/<timestamp>/visual/topdown_telemetry_browser_dashboard.mp4`
   - `artifacts/session/<timestamp>/visual/world_stream.mp4`
   - `artifacts/session/<timestamp>/visual/world_stream_recorded.mp4`
   - `artifacts/session/<timestamp>/visual/world_stream_browser_dashboard.mp4`
   - `artifacts/session/<timestamp>/visual/world_stream_summary.json`
   - `artifacts/session/<timestamp>/visual/world_stream_summary_recorded.json`
   - `artifacts/session/<timestamp>/visual/world_stream_summary_browser_dashboard.json`
   - `artifacts/session/<timestamp>/visual/keyframes/*.png`
   - `artifacts/session/<timestamp>/visual/timeline.json`
   - `artifacts/session/<timestamp>/visual/state.json`
   - `artifacts/session/<timestamp>/visual/visual_demo_summary.json`
   - `artifacts/session/<timestamp>/visual/visual_demo_summary_recorded.json`
   - `artifacts/session/<timestamp>/visual/visual_demo_summary_browser_dashboard.json`
