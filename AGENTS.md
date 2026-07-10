# Chasecar Agent Notes

This file captures repo-specific execution guidance for coding agents.

## Global Agent Policy

Global policy: `D:/dev/canon/docs/ops/agent-guidance/global-working-agreement.md @ 2026-05-04-act-or-wait`.

Runtime mirror: `C:/Users/afutu/.codex/GLOBAL_WORKING_AGREEMENT.md`.

This file is the Chasecar repo overlay. Keep universal agent behavior in the
global policy; keep runtime, ROS, Docker, UAT, artifact, and safety rules here.

## Act-Or-Wait Discipline

During material work, an agent must always be in one of two states:

- Acting: inspecting, editing, validating, documenting, committing, pushing, or
  taking the next safe reversible step.
- Waiting: explicitly waiting on a running command, tool result, or required
  human decision, with the reason stated.

Do not idle silently. If a safe next step exists, take it. If a human decision is
required, ask for it and wait through the available tool when possible.

For notifications:
- Agent notifications and pings go through the Claude mobile app via the
  `PushNotification` tool.
- During live hardware work, immediately send a mobile notification whenever
  progress needs the operator's physical action, safety observation, or
  decision. State the exact requested action and do not rely on a chat-only
  message. Use the runtime's direct push tool when available; otherwise end the
  requesting turn so the terminal notification hook delivers the alert.
- Continue safe autonomous work between operator gates; notification is for a
  real attention requirement, not routine progress.
- The Telegram bridge is retired (2026-06-10); do not use `mcp__telegram__*`
  tools.
- Keep agent-authored start, milestone, blocker, and completion updates in chat
  plus repo handoff surfaces.

Before final handoff:
- Confirm no needed commands, tool waits, or background sessions are still
  running.
- Let the terminal notification hook provide the completion alert for material
  work.

## Operator Video Link Preference

When handing off UAT/demo evidence, prefer browser-watchable video links over
raw filesystem paths. If the dashboard is reachable over Tailscale, include the
Mobile UAT Package link and direct `/artifacts/session/.../*.mp4` links for key
videos. Lead with the onboard camera video, `raw_camera.mp4`, then include
`yolo_debug.mp4`, `topdown_telemetry.mp4`, and `world_stream.mp4` when present.
Keep raw artifact paths as secondary evidence for audit/replay.

If no Tailscale dashboard URL is already known, start or point the operator to a
dashboard bind that prints `DASHBOARD_TAILSCALE_URL`:
`powershell -ExecutionPolicy Bypass -File scripts/run_dashboard_service.ps1 -BindHost 0.0.0.0 -Port 8860`.

## Operator Visual Debugging

For each key fetch UAT or evidence run, inspect a sequence of frames throughout
the run rather than only the ending frame. Cover start/setup, pre-contact,
first contact, mid-push/coast, terminal arrival, and final rest when those
phases are present. Prefer onboard `raw_camera` frames first, then cross-check
with `topdown_telemetry`, `world_stream`, and telemetry keyframes. Treat any
telemetry pass that conflicts with the visual sequence as suspect until the
geometry, delivery metric, and artifact provenance are reconciled.

## Operator Physical Motion Assumption

For Chasebot/JetBot hardware threads, treat the operator's instruction as
physical motion clearance unless the operator says the setup is unsafe, asks to
stop, or current evidence contradicts the assumption. This removes repeated
physical-clearance prompts during active hardware work.

Robot-side technical gates still apply before every live-motion slice: bridge
reachability, tool-controlled motion lock, verified stop path, fresh camera,
coherent target/detector state, bounded command limits, and final motors zero
with the bridge locked.

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
| Goal-side matrix | `scripts/run_gather_goal_side_matrix.ps1 -GatherControlFamily baseline -MaxRetriesPerTarget 2` |
| Gather control portfolio | `python scripts/gather_control_portfolio.py --campaign-id <id> --branch helper=<summary> --branch short_horizon_v2=<summary> --baseline-branch helper` |
| Gather hard-case stress analyzer | `python scripts/gather_control_stress_analyzer.py --campaign-id <id> --branch helper=<summary> --branch short_horizon_v2=<summary>` |
| Gather control failure audit | `python scripts/gather_control_failure_audit.py --campaign-id <id> --branch region_funnel_v1=<matrix_summary> --branch nav2_reacquire_v1=<matrix_summary> --branch constrained_local_planner_v1=<matrix_summary> --branch docking_reacquire_v1=<matrix_summary> --branch handoff_yaw_servo_v1=<matrix_summary> --branch pre_stage_reacquire_fsm_v1=<matrix_summary> --branch pre_stage_path_tracker_v1=<matrix_summary> --branch pre_stage_trajectory_owner_v1=<matrix_summary> --branch nav2_follow_path_reacquire_v1=<matrix_summary> --branch nav2_mppi_follow_path_reacquire_v1=<matrix_summary>` |
| Gather FollowPath research analyzer | `python scripts/gather_follow_path_research_analyzer.py --campaign-id <id> --artifact may2=<summary> --artifact may3=<summary>` |
| Gather object-centric policy evaluator | `python scripts/gather_object_centric_policy_evaluator.py --campaign-id <id> --artifact mppi=<summary> --artifact object_policy=<summary>` |
| Gather pre-stage command authority audit | `python scripts/gather_pre_stage_command_authority_audit.py --campaign-id <id> --branch region_funnel_v1=<matrix_summary> --branch nav2_reacquire_v1=<matrix_summary> --branch constrained_local_planner_v1=<matrix_summary> --branch docking_reacquire_v1=<matrix_summary> --branch handoff_yaw_servo_v1=<matrix_summary> --branch pre_stage_reacquire_fsm_v1=<matrix_summary> --branch pre_stage_path_tracker_v1=<matrix_summary> --branch pre_stage_trajectory_owner_v1=<matrix_summary>` |
| Gather portfolio stress ingestion | `python scripts/gather_control_portfolio.py --campaign-id <id> --branch helper=<summary> --stress helper=artifacts/session/<id>/gather_control_portfolio/helper/stress_summary.json --baseline-branch helper` |
| Gather escape oracle | `scripts/run_gather_escape_oracle.ps1 -CampaignId <id>` |
| Gather escape sandbox | `scripts/run_gather_escape_sandbox.ps1 -CampaignId <id>` |
| Gather escape reference | `scripts/run_gather_escape_reference.ps1 -CampaignId <id>` |
| Gather escape feasibility audit | `scripts/run_gather_escape_feasibility_audit.ps1 -CampaignId <id>` |
| Gather escape divergence audit | `scripts/run_gather_escape_divergence_audit.ps1 -CampaignId <id>` |
| Gather turn realization audit | `scripts/run_gather_turn_realization_audit.ps1 -CampaignId <id>` |
| Gather helper turn-authority contract audit | `scripts/run_gather_helper_turn_authority_contract_audit.ps1 -CampaignId <id>` |
| Gather manual-drive sign parity audit | `scripts/run_gather_manual_drive_sign_parity_audit.ps1 -CampaignId <id>` |
| Probe odom/world sign chain | `scripts/run_probe_odom_world_sign_chain.ps1 -CampaignId <id>` |
| Gather manager helper (internal) | `scripts/gather_manager_helpers.py` |
| Gather short-horizon helper (internal) | `scripts/gather_short_horizon_helpers.py` |
| Gather docking reacquire helper (internal) | `scripts/gather_docking_reacquire_helpers.py` |
| Gather handoff yaw servo helper (internal) | `scripts/gather_handoff_yaw_servo_helpers.py` |
| Gather pre-stage reacquire FSM helper (internal) | `scripts/gather_pre_stage_reacquire_fsm_helpers.py` |
| Gather pre-stage path tracker helper (internal) | `scripts/gather_pre_stage_path_tracker_helpers.py` |
| Gather pre-stage trajectory owner helper (internal) | `scripts/gather_pre_stage_trajectory_owner_helpers.py` |
| Gather Nav2 FollowPath reacquire helper (internal) | `scripts/gather_nav2_follow_path_reacquire_helpers.py` |
| Gather control portfolio analyzer (internal) | `scripts/gather_control_portfolio.py` |
| Gather hard-case stress analyzer (internal) | `scripts/gather_control_stress_analyzer.py` |
| Gather control failure audit analyzer (internal) | `scripts/gather_control_failure_audit.py` |
| Gather FollowPath research analyzer (internal) | `scripts/gather_follow_path_research_analyzer.py` |
| Gather object-centric policy evaluator (internal) | `scripts/gather_object_centric_policy_evaluator.py` |
| Gather object-centric policy helper (internal) | `scripts/gather_object_centric_policy_helpers.py` |
| Gather pre-stage command authority audit analyzer (internal) | `scripts/gather_pre_stage_command_authority_audit.py` |
| Gather escape oracle helper (internal) | `scripts/gather_escape_oracle.py` |
| Gather escape sandbox helper (internal) | `scripts/gather_escape_sandbox.py` |
| Gather escape reference helper (internal) | `scripts/gather_escape_reference.py` |
| Gather escape feasibility audit helper (internal) | `scripts/gather_escape_feasibility_audit.py` |
| Gather escape divergence audit helper (internal) | `scripts/gather_escape_divergence_audit.py` |
| Gather turn realization audit helper (internal) | `scripts/gather_turn_realization_audit.py` |
| Gather helper turn-authority contract audit helper (internal) | `scripts/gather_helper_turn_authority_contract_audit.py` |
| Gather manual-drive sign parity audit helper (internal) | `scripts/gather_manual_drive_sign_parity_audit.py` |
| Probe odom/world sign-chain helper (internal) | `scripts/probe_odom_world_sign_chain.py` |
| Odom/world sign-chain runtime probe helper (internal) | `scripts/odom_world_sign_chain_runtime_probe.py` |
| Route-planning parallel soak | `scripts/run_route_planning_parallel_soak.ps1 -Workers 2 -RunsPerWorker 1` |
| Dashboard service | `scripts/run_dashboard_service.ps1` |
| Dashboard validation | `scripts/run_dashboard_validation.ps1` |

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
15. `visit_route_planning` dashboard runs are intentionally self-contained: each click queues a sim reset and starts a fresh session before the mission launches. For repeatability triage, compare the pre-click and post-click session IDs.
16. Route-planning campaign parallelism belongs in isolated non-interactive soak runners, not in the operator dashboard. Keep browser UAT serial; use unique dashboard ports / compose projects / sessions for parallel background workers.
17. `region_funnel_v1` is a failed experimental gather-control branch after the April 24, 2026 one-run goal-side smoke; do not add it to portfolio/stress comparison or promotion discussion until a repaired branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes.
18. `nav2_reacquire_v1` is a blocked experimental ROS-native pre-stage reacquire branch after the April 24, 2026 one-run goal-side smoke; do not add it to portfolio/stress comparison or promotion discussion until a repaired branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes.
19. `constrained_local_planner_v1` is a blocked experimental local-planner gather-control branch after the April 25, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison until a repaired branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes without pre-stage ball drift/contact.
20. `docking_reacquire_v1` is a blocked experimental deterministic docking-style pre-stage reacquire branch after the April 25, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison until a repaired branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes without pre-stage ball drift/contact.
21. Gather control failure audit is analyzer-only closeout evidence; it does not promote or refresh portfolio/stress evidence for any blocked branch, including `region_funnel_v1`, `nav2_reacquire_v1`, `constrained_local_planner_v1`, `docking_reacquire_v1`, `handoff_yaw_servo_v1`, `pre_stage_reacquire_fsm_v1`, `pre_stage_path_tracker_v1`, `pre_stage_trajectory_owner_v1`, `nav2_follow_path_reacquire_v1`, or `nav2_mppi_follow_path_reacquire_v1`.
22. `handoff_yaw_servo_v1` is a blocked experimental last-mile pre-stage yaw-alignment branch after the April 25/26, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison until a repaired branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes without pre-stage ball drift/contact.
23. `pre_stage_reacquire_fsm_v1` is a blocked experimental first-attempt pre-stage reacquire branch after the April 26, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison until a repaired branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes without pre-stage ball drift/contact.
24. `pre_stage_path_tracker_v1` is a blocked experimental first-attempt pre-stage branch after the April 26, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison until a larger repaired control-stack branch shows fresh-attempt `zero` and `plus45` pre-stage handoff passes without pre-stage ball drift/contact.
25. `pre_stage_trajectory_owner_v1` is a blocked experimental pre-stage trajectory-owner branch after the April 27, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison.
26. Gather pre-stage command authority audit is analyzer-only assumption-peel-back evidence. It reads existing matrix/state-history artifacts, does not rerun live sim, and does not promote or refresh portfolio/stress evidence for any blocked gather-control branch.
27. `nav2_follow_path_reacquire_v1` is a blocked experimental one-ball `pre_stage` Nav2 controller-server `FollowPath` / DWB branch after the April 27, 2026 one-run goal-side smoke; keep it out of portfolio/stress comparison.
28. `nav2_mppi_follow_path_reacquire_v1` is a blocked lower-stack one-ball `pre_stage` MPPI FollowPath branch. It dispatches `/follow_path` with `controller_id=MppiFollowPath`, sends a start-anchored dense odom-frame path with tangent headings through `escape_clear`, `corridor_approach`, `port`, and `handoff_yaw`, and accepts only measured pre-stage handoff dwell; the May 3, 2026 terminal-geometry patch removed the extra MPPI-only `handoff_align` detour without changing MPPI params, handoff acceptance, capture behavior, `/odom`, or frozen contracts.
29. Latest May 3, 2026 terminal-geometry evidence recovered primary pre-stage reproducibility: saved-layout `zero` passed measured handoff 1/1 and then 3/3, saved-layout `plus45` passed measured handoff 3/3, all with `STATUS_SUCCEEDED`, `0.0m` pre-stage ball motion, and no `handoff_align` path segment. Live audit: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_live_audit_20260503/gather_follow_path_research_analyzer/follow_path_research_summary.json`.
30. Keep `nav2_mppi_follow_path_reacquire_v1` out of portfolio/stress comparison because the branch is now blocked downstream: `zero` fails at `capture_entry_timeout`, while `plus45` reaches capture-entry and then fails around first-contact/release alignment (`missing_first_contact_alignment` / `release_roll_away`). The current capture-layer repair patch is still pending live requalification; it gives capture-entry bounded extra convergence time/forward authority and prevents far-from-zone generic capture from clamping into `capture_handoff_hold`, without adding another helper/manual-drive overlay or loosening pre-stage handoff.
31. Continued MPPI/capture threshold tuning is baseline-maintenance only. Treat MPPI FollowPath as baseline evidence for long-range/pre-stage behavior, not as the primary contact-rich manipulation path.
32. Current research direction has pivoted from gather/place into `object_centric_fetch_policy_v1`: a short-horizon fetch-to-pose policy on calibrated ball/surface physics. Treat earlier emergent launch/roll behavior as hypothesis-only until the physics lane is green; success is measured ball trajectory intersection with a delivery radius around a target pose, not final stop in a corral. The current small-robot UAT lane uses a calibrated golf ball and visible delivery circle before autonomous control promotion. The next control priority is stable pre-contact approach on the ball-target line, then bounded directional correction while pushing; classify lateral knock-away and over-rotation from robot pose/yaw telemetry before tuning. User/person detection comes later after `fetch_to_pose` is repeatable. Keep Nav2 reserved for long-range repositioning and do not change `/odom`, frozen contracts, or measured handoff acceptance.

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

Gather escape offline audit baseline:
- Feasibility audit: `artifacts/session/live_plus45_escape_feasibility_audit_20260420/gather_escape_feasibility_audit/feasibility_summary.json`
- Divergence audit: `artifacts/session/live_plus45_escape_divergence_audit_20260420/gather_escape_divergence_audit/divergence_summary.json`
- Turn realization audit: `artifacts/session/live_plus45_turn_realization_audit_20260420/gather_turn_realization_audit/turn_realization_summary.json`
- Helper turn-authority contract audit: `artifacts/session/live_plus45_helper_turn_authority_contract_audit_20260420/gather_helper_turn_authority_contract_audit/helper_turn_authority_contract_summary.json`
- Manual-drive sign parity audit: `artifacts/session/live_plus45_manual_drive_sign_parity_audit_20260420/gather_manual_drive_sign_parity_audit/manual_drive_sign_parity_summary.json`

Gather sign-chain runtime probe reference:
- Probe summary: `artifacts/session/live_plus45_probe_odom_world_sign_chain_20260421_provenance_rerun/probe_odom_world_sign_chain/odom_world_sign_chain_summary.json`
- Runtime probe payload: `artifacts/session/live_plus45_probe_odom_world_sign_chain_20260421_provenance_rerun/probe_odom_world_sign_chain/runtime_probe.json`
- Working odom witness for this probe branch: `/jetbot_base_controller/odom` only, without redefining the public `/odom` contract
- Current branch implementation: `scripts/run_probe_odom_world_sign_chain.ps1` now passes the fresh probe session's `visual/truth_state.json` path into `scripts/odom_world_sign_chain_runtime_probe.py`, which emits additive `world_truth` metrics in `runtime_probe.json`; `scripts/probe_odom_world_sign_chain.py` now prefers those metrics before falling back to `truth_timeline.json`, reconstructs source and fresh fixture-local command provenance inside the bundle, emits additive `source_alignment_assessment` / `source_fresh_fixture_window_comparison` surfaces, and fail-closes runtime `world_truth` back to `truth_timeline.json` when `source_session_id` does not match the expected probe session
- Current branch offline verification: `pytest tests/test_probe_odom_world_sign_chain.py -q`, `pytest tests/test_probe_odom_world_sign_chain_source_provenance.py -q`, `pytest tests/test_probe_odom_world_sign_chain_session_binding.py -q`, and `pytest tests/dashboard/test_world_stream_freshness.py -k "truth_ready or make_session_id" -q`
- Current closeout status after refreshing the saved April 21, 2026 provenance rerun bundle: `runtime_classification.diagnosis=sign_chain_aligned` and `source_alignment_assessment.diagnosis=source_fixture_command_sign_mismatch`; bounded source-vs-fresh windows still mismatch on `early_stall`, `mid_stall`, and `late_stall`, while `terminal_stall` remains the control match
- Next work: shift to source-artifact interpretation/documentation; reopen runtime-focused work only if a future fresh rerun materially changes that mismatch set

Gather region-funnel experimental branch status:
- Repair smoke: `artifacts/session/live_region_funnel_v1_zero_repair_20260424/gather_goal_side_matrix/campaign_summary.json`
- Result: `region_funnel_v1` remains blocked. The evidence hygiene fix now surfaces fresh-attempt goal-side pre-stage failures consistently, but fresh `zero` and `plus45` still fail pre-stage handoff in the matrix, so no portfolio/stress refresh was produced for this branch.

Gather ROS-native reacquire experimental branch status:
- Candidate: `nav2_reacquire_v1`
- Scope: one-ball `pre_stage` / behind-ball reacquisition only; bounded Nav2 waypoint first, then baseline `stage -> capture_entry -> capture` resumes.
- Smoke: `artifacts/session/live_nav2_reacquire_v1_matrix_smoke_20260424/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff, Nav2 accepted the reacquire goals but timed out, and no portfolio/stress refresh was produced for this branch.

Gather constrained-local planner experimental branch status:
- Candidate: `constrained_local_planner_v1`
- Scope: one-ball `pre_stage` / behind-ball reacquisition only; bounded local rollout candidates reject predicted ball contact and release back to baseline pre-stage/stage control.
- Smoke: `artifacts/session/live_constrained_local_planner_v1_matrix_smoke_20260425/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff, so no portfolio/stress refresh was produced for this branch.

Gather docking-style reacquire experimental branch status:
- Candidate: `docking_reacquire_v1`
- Scope: one-ball `pre_stage` / behind-ball reacquisition only; deterministic local docking pocket selection and bounded pose-servo commands release back to baseline only after measured handoff geometry is safe.
- Smoke: `artifacts/session/live_docking_reacquire_v1_release_fix_matrix_smoke_20260425/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff; the branch can reach near behind-ball geometry without observed pre-stage ball motion, but it still times out on yaw/handoff alignment, so no portfolio/stress refresh was produced for this branch.

Gather handoff-yaw-servo experimental branch status:
- Candidate: `handoff_yaw_servo_v1`
- Scope: one-ball `pre_stage` / behind-ball last-mile handoff only; yaw-only local servo activates only after measured geometry is safe except yaw.
- Smoke: `artifacts/session/live_handoff_yaw_servo_v1_matrix_smoke_20260426/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff, so no portfolio/stress refresh was produced for this branch.

Gather pre-stage reacquire FSM experimental branch status:
- Candidate: `pre_stage_reacquire_fsm_v1`
- Scope: one-ball first-attempt `pre_stage` reacquisition only; explicit measured-state phases cover goal-side escape, safe docking entry, dock-port convergence, yaw-only final alignment, and baseline release.
- Smoke: `artifacts/session/live_pre_stage_reacquire_fsm_v1_matrix_smoke_20260426/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff without clearing the matrix gate, so no portfolio/stress refresh was produced for this branch.

Gather pre-stage path tracker experimental branch status:
- Candidate: `pre_stage_path_tracker_v1`
- Scope: one-ball first-attempt `pre_stage` reacquisition only; explicit waypoint path tracker covers escape, off-axis approach, port, and final yaw-align waypoints before baseline handoff.
- Smoke: `artifacts/session/live_pre_stage_path_tracker_v1_matrix_smoke_20260426/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff; path-tracker debug showed no pre-stage ball motion/contact, but both primary cases stayed on the `escape` waypoint until timeout, so no portfolio/stress refresh was produced for this branch.

Gather pre-stage trajectory owner experimental branch status:
- Candidate: `pre_stage_trajectory_owner_v1`
- Scope: one-ball first-attempt `pre_stage` only; in-process measured trajectory owner through `escape_clear`, `corridor_approach`, `port`, and `handoff_yaw`, with one alternate-side replan and strict measured handoff release.
- Smoke: `artifacts/session/live_pre_stage_trajectory_owner_v1_matrix_smoke_20260427/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff with no pre-stage ball motion/contact; the branch mostly stopped on `trajectory_progress_stalled`, with `plus45` also showing a latest-retry `trajectory_clearance_guard`, so no portfolio/stress refresh was produced for this branch.

Gather Nav2 FollowPath reacquire experimental branch status:
- Candidate: `nav2_follow_path_reacquire_v1`
- Scope: one-ball `pre_stage` only; builds an explicit odom-frame path through `escape_clear`, `corridor_approach`, `port`, and `handoff_yaw`, dispatches `/follow_path` with DWB, disables manual drive while Nav2 owns the path, and accepts only measured pre-stage handoff dwell.
- Smoke: `artifacts/session/live_nav2_follow_path_reacquire_v1_matrix_smoke_20260427/gather_goal_side_matrix/campaign_summary.json`
- Result: blocked. Fresh `zero` and `plus45` both failed pre-stage handoff; `/follow_path` goals were accepted but immediately aborted with `status_code=6`, no pre-stage ball motion/contact, and no measured handoff, so no portfolio/stress refresh was produced for this branch.

Gather Nav2 MPPI FollowPath reacquire experimental branch status:
- Candidate: `nav2_mppi_follow_path_reacquire_v1`
- Scope: one-ball `pre_stage` only; dispatches `/follow_path` with the Nav2 MPPI `MppiFollowPath` controller, sends a start-anchored dense odom-frame path with tangent headings through `escape_clear`, `corridor_approach`, `port`, and `handoff_yaw`, disables manual drive while Nav2 owns the path, and accepts only measured pre-stage handoff dwell.
- Recovery matrix: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_entry_diag_20260502/gather_goal_side_matrix/campaign_summary.json`
- Recovery audit: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_entry_diag_20260502_failure_audit/gather_control_failure_audit/failure_audit_summary.json`
- Latest clean rerun: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_diag_rerun_20260503/gather_goal_side_matrix/campaign_summary.json`
- Latest clean audit: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_diag_rerun_20260503_failure_audit/gather_control_failure_audit/failure_audit_summary.json`
- Targeted saved-layout `zero` repro: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_prestage_repro_zero_20260503/gather_mission_repeatability/campaign_run_summary.json`
- Targeted saved-layout `plus45` repro: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_prestage_repro_plus45_20260503/gather_mission_repeatability/campaign_run_summary.json`
- Research reset summary: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_research_reset_20260503/research_reset_summary.json`
- Terminal-geometry live audit: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_live_audit_20260503/gather_follow_path_research_analyzer/follow_path_research_summary.json`
- Result: blocked downstream after pre-stage recovery and now treated as baseline evidence rather than the primary research path. The May 3 research reset showed both `8dfe93b` and the recovery commit `eafdc59` fail saved-layout `zero`; loaded runtime MPPI params match `nav2_params_simple.yaml`; the first near-goal critic/pruning patch worsened progress and was reverted. The follow-up terminal-geometry patch removed the extra MPPI-only `handoff_align` waypoint and recovered saved-layout primary pre-stage handoff: `zero` passed 1/1 and then 3/3, `plus45` passed 3/3, all with `STATUS_SUCCEEDED`, `0.0m` pre-stage ball motion, and no `handoff_align` path segment. No portfolio/stress refresh was produced because full missions still fail downstream (`zero` at `capture_entry_timeout`; `plus45` after capture-entry around first-contact/release alignment). The next research branch should be `object_centric_gather_policy_v1`, not more broad MPPI/capture threshold tuning.

Object-centric fetch policy research direction:
- Candidate: `object_centric_fetch_policy_v1`
- Active planning doc: `docs/OBJECT_CENTRIC_FETCH_POLICY_PLAN.md`
- Historical gather/place doc: `docs/OBJECT_CENTRIC_GATHER_POLICY_RESEARCH_PLAN.md`
- Scope: fetch-to-pose first on calibrated ball/surface physics. The current small-robot lane uses a golf ball and visible delivery circle; previous launch-only evidence is non-promotional until the physics lane is documented and repeatable. Overshoot is acceptable when the trajectory intersects the delivery radius.
- Runtime boundary: Nav2/MPPI remains available for long-range repositioning. The fetch policy owns short-horizon ball interaction and must be wrapped in deterministic guards for command bounds, pre-contact ball drift, clearance, target freshness, timeout, stuck state, recovery budget, and give-up.
- Current implementation direction: keep `golf_ball_circle_delivery_uat` as the dashboard-visible physics/contact UAT lane, instrument it with per-tick robot pose/yaw plus ball pose, then add autonomous `fetch_to_pose` inside the existing gather mission runner after successful capture/setup and before legacy place/release behavior; extend `scripts/gather_object_centric_policy_helpers.py` with `phase="fetch_to_pose"` while preserving existing diagnostics; propagate shot outcome fields through `state_history.jsonl`, `mission_verdict.json`, repeatability summaries, and evaluator outputs.
- Data rule: every contact attempt should record setup geometry, command sequence, robot lateral/yaw error to the ball-target line, first-contact state, ball trajectory, closest approach to target, success/intersection status, miss class, surface/friction snapshot, and predicted-vs-actual outcome.
- Latest physics/contact UAT: dashboard scenario `golf_ball_circle_delivery_uat` passed on May 22, 2026 in `artifacts/session/20260522T130431721734Z/golf_ball_circle_delivery/20260522T130442256465Z/mission_verdict.json` with `fetch_to_pose_pass=true`, `shot_outcome.closest_approach_distance_m=0.049893` inside a `0.300m` delivery radius, and `approach_contact_metrics.stable_contact_approach_pass=true` with zero pre-contact yaw sign changes.
- Promotion rule: no portfolio/stress ingestion until `fetch_to_pose` has schema evidence, calibrated physics/contact UAT, approach-stability telemetry, repeatability evidence, saved-layout `zero` and `plus45` autonomous pose-delivery smoke, and bounded recovery smoke. User/person detection is explicitly deferred.

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

## Owner-facing docs & dashboards: serve via the docs-hub (cross-project rule)
The owner reads on MOBILE over Tailscale. NEVER share a repo-relative `.md` path as the
only pointer — it doesn't render on a phone. Publish, then share the full URL.
- **The hub (always-on, independent of every dev server):** `node D:\services\docs-hub\hub-server.js`
  — port **8123**, binds 0.0.0.0, root-jailed static server over `D:\services\docs-hub\site\<project>\...`.
  If `http://127.0.0.1:8123/` is down (e.g. after reboot), restart it via a `run_in_background` shell call.
- **Publish a doc:** copy the `.md` into `D:\services\docs-hub\site\<project>\docs\` and add an entry to
  the `INDEX` array in `site\<project>\docs\index.html` (the mobile markdown renderer — copy
  `site\factr\docs\index.html` to bootstrap a new project). Share:
  `http://100.112.221.6:8123/<project>/docs/?doc=<file-stem>`
- **Dashboards:** publish to `site\<project>\` (e.g. `plan-progress.html`) → share
  `http://100.112.221.6:8123/<project>/<file>`.
- Lead with the Tailscale URL (`100.112.221.6` — stable); the repo path may follow in parentheses.
