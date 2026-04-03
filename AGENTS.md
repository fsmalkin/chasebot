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

## Key Commands

Full workflow details are in [docs/ACTIVE_WORKFLOW.md](docs/ACTIVE_WORKFLOW.md). Quick reference:

| Task | Command |
|------|---------|
| First UAT | `scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin` |
| Full replay | `scripts/run_compose_uat.ps1 -Action run -ProjectName <name> -RuntimeTarget robot_fidelity_orin -UatMode full_replay -UatExecutionContext sim_gate` |
| Pre-LLM dual | `scripts/run_headless_pre_llm.ps1 -Lane dual` |
| Campaign | `scripts/run_pre_llm_campaign.ps1` |
| Brain adapter smoke | `scripts/run_brain_adapter_smoke.ps1 -RuntimeTarget robot_fidelity_orin` |
| Planner shell smoke | `scripts/run_brain_intent_shell.ps1 -RuntimeTarget robot_fidelity_orin` |
| Adversarial must-fail | `scripts/run_pre_llm_adversarial.ps1 -RuntimeTarget robot_fidelity_orin` |
| GUI rehearsal | `scripts/run_pre_llm_gui_rehearsal.ps1 -ExecutionLane container_kilted -CoreRosDistro kilted -RuntimeTarget robot_fidelity_orin -OpenFeedViewers false -VisualSurface browser_dashboard` |
| Visual parity check | `scripts/run_visual_parity_check.ps1 -SessionId <id> -HeadlessSummaryPath <path> -GuiSummaryPath <path>` |
| Recorded visual demo | `scripts/run_recorded_visual_demo.ps1 -Milestone 3 -RuntimeTarget robot_fidelity_orin -SessionId <id>` |

## Compose Profiles

| Profile | Script |
|---------|--------|
| Gate lane | `scripts/run_compose_gate.ps1` |
| Isaac lane | `scripts/run_compose_isaac.ps1` |
| UAT orchestrator | `scripts/run_compose_uat.ps1` |

UAT modes: `prepare`, `coordinate`, `snapshot`, `orientation`, `nav2`, `multi_target`, `first_uat`, `full_replay`, `pre_llm`

## Lane Behavior

- `fast`: `workstation_max`, short timeouts, fast-forward world
- `fidelity`: `robot_fidelity_orin`, canonical world, strict timing
- `dual`: fast then fidelity

Lane-specific configs:
- `ros2_config/config/nav2_readiness_fast.yaml` / `nav2_readiness_fidelity.yaml`
- `ros2_config/config/multi_target_nav2_fast.yaml` / `multi_target_nav2_fidelity.yaml` / `multi_target_nav2_fidelity_soak.yaml`

## Current Caution

1. Isaac runtime container requires NVIDIA Container Toolkit and valid image access.
2. `run_autonomous_uat.ps1` is orchestration glue; direct UAT scripts are authoritative for triage.
3. If a long run appears stuck in WSL-hosted mode, stop with `wsl --shutdown` and rerun from a clean session.
4. `ros2 action list` includes clients; use `ros2 action info /navigate_to_pose` and confirm `Action servers: 1` for readiness.
5. `scripts/run_compose_profile.ps1` auto-resolves Docker Desktop CLI path when `docker` is not on PATH.
6. For full replay, keep launch bridge disabled (`-IncludeBridge $false`).
7. GUI parity is authoritative only on `container_kilted`; `host_ros` is debug-only.
8. Operator live view (`-OpenFeedViewers true`) is blocked unless latest `parity_summary.json` is green.
9. Container-lane live viewers are strict-gated: unavailable viewers fail with `failure_class=feed_viewer_unavailable`.
10. Native X11/Gazebo windows are debug-only. Authoritative visual is recorded bundles + browser dashboard + Xpra.
11. Browser/recorded visual must use the same `container_kilted` session ID as headless.
12. Diff-drive sign parity is in `ros2_config/config/jetbot_diff_drive_v1.0.0.yaml` and `jetbot_controllers.yaml`. If robot drives backward, compare odom to world pose before trusting nav results.
13. Operator visual signoff: single-target M3 first, multi-target rehearsal second.
14. Dashboard status chips surface `phase`, `target_id`, `target_transition_active`.

## Latest Validated Artifacts

Campaign + soak + smoke package:
- Campaign: `artifacts/session/20260309T063355Z/campaign_run_summary.json`
- Soak: `artifacts/session/20260309T073224Z/pre_llm_headless_summary.json`
- RC readiness: `artifacts/session/20260309T063355Z/rc/readiness_report.json`
- Adversarial: `artifacts/session/20260303T061055Z/adversarial_headless_summary.json`
- Brain adapter: `artifacts/session/20260312T001204Z/brain_adapter_smoke_summary.json`
- Planner shell: `artifacts/session/20260312T001244Z/brain_intent_shell_summary.json`

Same-session visual baseline:
- `artifacts/session/20260312T013442Z/pre_llm_headless_summary.json`
- `artifacts/session/20260312T013442Z/visual/visual_demo_summary_recorded.json`
- `artifacts/session/20260312T013442Z/pre_llm_gui_rehearsal_summary.json`
- `artifacts/session/20260312T013442Z/parity_summary.json`
