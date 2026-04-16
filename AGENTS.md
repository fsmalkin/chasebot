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
| LLM recommend | `scripts/run_brain_llm_recommend.ps1 -RuntimeTarget robot_fidelity_orin` |
| Turn-then-go proof | `scripts/run_llm_turn_then_go_proof.ps1` |
| Turn-then-go repeat | `scripts/run_llm_turn_then_go_repeatability.ps1` |
| Visible ball campaign | `scripts/run_llm_visible_ball_campaign.ps1` |
| Visit mission repeat | `scripts/run_visit_mission_repeatability.ps1` |
| Corral surface calibration | `scripts/run_corral_surface_calibration.ps1 -RunsPerLane 3` |
| Route-planning parallel soak | `scripts/run_route_planning_parallel_soak.ps1 -Workers 2 -RunsPerWorker 1` |
| Dashboard service | `scripts/run_dashboard_service.ps1` |
| Dashboard validation | `scripts/run_dashboard_validation.ps1` |
| Telegram preflight | `scripts/telegram_preflight.ps1 -CheckBot` |
| Telegram daemon | `scripts/run_telegram_wait_daemon.ps1 -Action up -Build` |
| Telegram MCP register | `scripts/register_telegram_mcp.ps1` |

## Compose Profiles

| Profile | Script |
|---------|--------|
| Gate lane | `scripts/run_compose_gate.ps1` |
| Isaac lane | `scripts/run_compose_isaac.ps1` |
| UAT orchestrator | `scripts/run_compose_uat.ps1` |
| Telegram wait bridge | `scripts/run_telegram_wait_daemon.ps1` |

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
15. `visit_route_planning` dashboard runs are intentionally self-contained: each click queues a sim reset and starts a fresh session before the mission launches. For repeatability triage, compare the pre-click and post-click session IDs.
16. Route-planning campaign parallelism belongs in isolated non-interactive soak runners, not in the operator dashboard. Keep browser UAT serial; use unique dashboard ports / compose projects / sessions for parallel background workers.

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

Route-planning obstacle-avoidance validation:
- Fresh-session pass: `artifacts/session/20260412T021011Z/visit_mission/20260412T021044Z/mission_verdict.json`
- Fresh-session pass: `artifacts/session/20260412T022002Z/visit_mission/20260412T022019Z/mission_verdict.json`
- Clearance trace: `artifacts/session/20260412T021011Z/route_clearance_monitor_persistent_obstacles.jsonl`
- Clearance trace: `artifacts/session/20260412T022002Z/route_clearance_monitor_fresh2.jsonl`

Route-planning self-contained rerun validation:
- One-click rerun pass: `artifacts/session/20260412T033747Z/visit_mission/20260412T033759Z/mission_verdict.json`
- One-click rerun pass: `artifacts/session/20260412T033934Z/visit_mission/20260412T033947Z/mission_verdict.json`

Route-planning parallel soak validation:
- Isolated 2-worker soak pass: `artifacts/session/20260412T054630Z/route_planning_parallel_soak/campaign_summary.json`

## Testing

### Verification levels

Changes must pass **both** tiers before being considered verified:

| Tier | What | When | Command |
|------|------|------|---------|
| **Unit** | Offline pytest (mocks, no sim) | Every commit | `pytest tests/test_brain_intent_executor.py tests/test_visit_mission_runner.py tests/dashboard/` |
| **Live sim** | Dashboard UAT in running sim | Every behavior change | Click scenario in dashboard, observe robot behavior, check event log |

**Unit tests alone are NOT sufficient verification for behavior changes.** They mock ROS, Nav2, and perception — they prove wiring, not that the robot actually moves correctly. Any commit that changes executor behavior, visit lifecycle, navigation, or perception must be verified with a live sim run before being declared working.

### Live sim verification checklist

For route-planning / visit lifecycle changes, run the "LLM Route Plan" scenario from the dashboard and confirm:

1. All balls spawn and persist throughout the mission
2. Robot navigates (drives) toward each target — not spinning in place
3. Robot acquires target visually when near, approaches, and reports visited
4. Event log shows: `route_planned` -> `route_step` -> `target_visited` x N -> `mission_passed`
5. Top-down telemetry shows robot path to each ball
6. For repeatability changes, click the scenario twice without a manual env restart and confirm each click creates a fresh session ID and still ends in `mission_passed`

If any step fails, the change is not verified regardless of unit test results.

### Live sim integration tests

```
pytest tests/dashboard/test_dashboard_api.py --run-live
```

These require a running simulation environment (Docker + Gazebo + ROS2) and are skipped by default.

### Unit test modules

Run the unit test suite before committing changes:

```
pytest tests/
```

Key test modules and what they cover:

| Module | Covers |
|--------|--------|
| `tests/test_brain_supervisor.py` | Supervisor loop observe-choose-dispatch cycle |
| `tests/test_brain_supervisor_policy.py` | Deterministic policy and escalation rules |
| `tests/test_brain_intent_executor.py` | Intent executor dispatch, visit lifecycle, scenario tests |
| `tests/test_brain_llm_recommender.py` | LLM recommender provider integration |
| `tests/test_llm_demo_campaign_helpers.py` | Campaign aggregation and trend helpers |
| `tests/test_llm_turn_then_go_proof_runner.py` | Turn-then-go proof runner logic |
| `tests/test_visit_mission_runner.py` | Visit mission sequencing and route planning |
| `tests/test_visit_mission_campaign_helpers.py` | Visit mission campaign helpers |
| `tests/dashboard/test_dashboard_api.py` | Dashboard HTTP API (requires `--run-live`) |
| `tests/dashboard/test_world_stream_freshness.py` | World stream liveness checks |

Dashboard end-to-end validation uses Playwright:

```
cd dashboard_validation && npx playwright test
```

## Frozen Contracts

Files under `runtime/contracts/` are versioned and may carry a freeze status:

| Contract | File |
|----------|------|
| LLM control contract | `runtime/contracts/llm_control_contract.yaml` |
| Message schema manifest | `runtime/contracts/message_schema_manifest.yaml` |
| Isaac bridge allowlist | `runtime/contracts/isaac_bridge_allowlist.yaml` |

Rules:

1. If `contract_status` is `frozen_pre_llm` or any `frozen_*` value, do **not** modify the contract without bumping the `version` field and documenting the rationale.
2. Adding new intents or removing existing ones from the LLM control contract changes the safety boundary between the LLM layer and low-level execution — treat this as a breaking change.
3. The `freeze_basis` block in `llm_control_contract.yaml` records which validated artifacts justified the freeze. Do not alter it retroactively.

## LLM Brain Layer

The LLM supervisor stack sits above the frozen contract boundary:

- **State digest**: `scripts/brain_state_digest.py` — compact fixed-shape state for LLM consumption.
- **Recommender**: `scripts/brain_llm_recommender.py` — calls a provider to choose the next intent.
- **Providers**: `scripts/llm_provider_base.py`, `llm_provider_local.py`, `llm_provider_openai.py`, `llm_provider_replay_compare.py`.
- **Supervisor loop**: `scripts/brain_supervisor_loop.py` — observe → recommend → validate → dispatch.
- **Policy gate**: `scripts/brain_supervisor_policy.py` — deterministic validation between LLM output and executor.
- **Executor**: `scripts/brain_intent_executor.py` — dispatches validated intents to ROS subsystems.

Architecture details: [docs/LLM_CONTROL_ARCHITECTURE.md](docs/LLM_CONTROL_ARCHITECTURE.md).

Key constraint: the LLM never bypasses deterministic gating. All recommended intents pass through the policy gate before reaching the executor.

## Dashboard

The browser dashboard is part of the operator control plane:

- **Service**: `scripts/dashboard_service.py` (start via `scripts/run_dashboard_service.ps1`).
- **Frontend**: `runtime/dashboard/browser_dashboard.html` + `browser_dashboard.js`.
- **Runtime state**: `runtime/dashboard/dashboard_service_state.json`, `llm_supervisor_state.json`.
- **Validation**: `dashboard_validation/` (Playwright tests via `scripts/run_dashboard_validation.ps1`).

The dashboard surfaces `phase`, `target_id`, and `target_transition_active` status chips during multi-target operation. Parity checks require the dashboard to be ready.

## Documentation Update Policy

When making changes that affect the items below, update the relevant docs **in the same commit**:

1. **Adding or removing a script** in `scripts/` → update the Key Commands table in this file and the relevant section in `docs/ACTIVE_WORKFLOW.md`.
2. **Adding or removing a UAT mode** → update the UAT Orchestrator Modes list in `docs/ACTIVE_WORKFLOW.md` and the mode list in this file.
3. **Changing artifact output paths or adding new artifact types** → update Artifact Contracts in `docs/ACTIVE_WORKFLOW.md`.
4. **Adding or removing an intent** in the LLM control contract → update the LLM Brain Layer section in this file and `docs/LLM_CONTROL_ARCHITECTURE.md`.
5. **Adding or removing a launch file** → update Canonical Launch Surfaces in `docs/ACTIVE_WORKFLOW.md`.
6. **Changing contract schema or version** → update the Frozen Contracts section in this file.

If you are unsure whether a doc needs updating, check this file and `docs/ACTIVE_WORKFLOW.md` for references to the changed path or name.
