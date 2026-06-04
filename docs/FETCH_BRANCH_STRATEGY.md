# Calibrated Golf Fetch Branch Strategy

This document owns branch-role decisions for calibrated golf fetch work. Use the
roadmap for priority, `ACTIVE_WORKFLOW.md` for gates and commands, and the
`OBJECT_CENTRIC_*` docs for research details.

Next major milestone: Deliver Planner-Gated Generalized Fetch-To-Pose v1, a
no-shoot, robot-owned fetch behavior where an LLM/world-state planner selects
the route class, Nav2 owns as much real-time robot motion as the corrected
evidence supports, and a thin fetch adapter monitors delivery geometry, object
progress, escape, stale state, and replanning triggers.

Scope correction: this branch strategy covers both the planner handoff lane and
the bounded local fetch subsystem. Major unknowns and arbitrary random scenes
require planner classification before fetch execution. The LLM/world-state
planner should classify scenes as `fetch_ready_local`, `nav2_reposition_first`,
`scan_or_perceive_first`, `recovery_or_reaim`, or
`ambiguous_or_unsafe_no_go`; only `fetch_ready_local` cases count against the
local fetch branch. Custom contact routines and AI push-coast proposals remain
fallback lanes that earn live authority only from corrected reproducible
stage-gap evidence.

## Recommended Branch Roles

1. Stable demo/UAT branch:
   - Keep `physics-calibrated-golf-fetch-v1` as the integration branch for the
     calibrated golf ball, object-centric fetch policy, surface-calibrated
     fetch-to-pose demo, UAT fixes, and operator-facing evidence.
   - Merge only focused changes that preserve the active fetch gates and
     protected route-planning floor.
   - After green UAT, snapshot releases from this branch as
     `release/golf-fetch-uat-YYYYMMDD`; do not do new development on release
     snapshots.
2. Evidence-only archived experimental architecture branches:
   - Treat `nav2_mppi_follow_path_reacquire_v1` as baseline/evidence for
     long-range and pre-stage behavior, not as the active manipulation branch.
   - Keep `region_funnel_v1`, `nav2_reacquire_v1`,
     `constrained_local_planner_v1`, `docking_reacquire_v1`,
     `handoff_yaw_servo_v1`, `pre_stage_reacquire_fsm_v1`,
     `pre_stage_path_tracker_v1`, `pre_stage_trajectory_owner_v1`,
     `nav2_follow_path_reacquire_v1`, and
     `nav2_mppi_follow_path_reacquire_v1` out of portfolio, stress, release, and
     promotion discussion unless a repaired branch first produces fresh
     saved-layout `zero` and `plus45` pre-stage handoff passes with no pre-stage
     ball drift/contact and records the artifact paths here and in
     `ACTIVE_WORKFLOW.md`.
   - Use those branches for evidence lookup only; do not revive them as hidden
     sidecars under the fetch branch.
3. Short-lived spike or requalification branches:
   - Branch from `physics-calibrated-golf-fetch-v1` for one narrow hypothesis and
     delete, merge, or archive after the named gate.
   - Naming examples: `spike/fetch-shot-outcome-schema`,
     `spike/fetch-plus45-recovery-requal`,
     `spike/nav2-mppi-terminal-geometry-revisit`,
     `spike/fetch-arch-ai-push-coast-servo-YYYYMMDD`, and
     `spike/architecture-revisit-object-centric-fetch-2026Q3`.
   - Each spike must state its hypothesis, artifact target, expected gate, and
     expiry condition in its PR or handoff notes.
   - For AI-assisted fetch spikes, "expected gate" must include shadow-mode
     prediction/proposal scoring before any learned output is allowed to drive.
4. Release and PR hygiene:
   - Keep one behavioral theme per PR: implementation, evidence replay, doc-only
     recommendation, or UAT release cleanup.
   - PRs should identify their branch role and cite the newest gate artifacts.
   - Do not mix archived-architecture resurrection with stable demo fixes in the
     same PR.
   - Before release, rebase or merge current stable demo work into
     `physics-calibrated-golf-fetch-v1`, run the documented fetch gates, then cut
   the release snapshot.

## Architecture Evidence Classification

Use this table when deciding whether better calibrated physics justifies
reopening an older architecture. Most blocked branches failed before intended
ball contact, so old ball/turf physics does not explain the primary failure.

Evidence reset rule after May 31, 2026: any fetch pass/fail claim is promotion
eligible only when the artifact records `geometry_consistency.pass=true`, the
visible delivery marker matches `fetch_pose_world`, and same-session
browser-watchable onboard plus context video exists. Pre-fix or
marker-mismatched fetch passes become diagnostic implementation evidence. The
post-fix reference package is
`artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`,
and the post-fix geometry audit is
`artifacts/session/fetch_geometry_evidence_audit_postfix_20260531/fetch_geometry_evidence_audit/scorecard.md`.

Provenance reset rule after June 1, 2026: direct fetch evidence also needs
`model_provenance_valid=true` with target model `calibrated_golf_ball`, target
radius `0.021336m`, and marker model `golf_ball_delivery_zone_marker`. Commit
`680e393 Use calibrated ball for fetch direct runs` is the direct-run boundary.
Older direct repeatability artifacts without explicit calibrated model fields
remain diagnostic until rerun. Inventory them with
`scripts/fetch_model_provenance_audit.py`.

| Candidate | Key evidence | Classification | Branch decision |
| --- | --- | --- | --- |
| `helper` / `short_horizon_v2` manual-drive lane | `artifacts/session/live_plus45_helper_turn_authority_contract_audit_20260420/gather_helper_turn_authority_contract_audit/helper_turn_authority_contract_summary.json`; `artifacts/session/live_plus45_probe_odom_world_sign_chain_20260421_provenance_rerun/probe_odom_world_sign_chain/odom_world_sign_chain_summary.json` | Physics-independent pre-stage / command-authority evidence | Baseline evidence only. |
| `region_funnel_v1` | `artifacts/session/live_region_funnel_v1_zero_repair_20260424/gather_goal_side_matrix/campaign_summary.json` | Fresh-attempt pre-stage blocked | Archive current branch. |
| `nav2_reacquire_v1` | `artifacts/session/live_nav2_reacquire_v1_matrix_smoke_20260424/gather_goal_side_matrix/campaign_summary.json` | Physics-independent pre-stage timeout | Archive current branch. |
| `constrained_local_planner_v1` | `artifacts/session/live_constrained_local_planner_v1_matrix_smoke_20260425/gather_goal_side_matrix/campaign_summary.json` | Primary gate pre-stage blocked; later contact symptoms non-promotional | Archive current branch. |
| `docking_reacquire_v1` | `artifacts/session/live_docking_reacquire_v1_release_fix_matrix_smoke_20260425/gather_goal_side_matrix/campaign_summary.json` | Physics-independent handoff/yaw timeout | Archive current branch. |
| `handoff_yaw_servo_v1` | `artifacts/session/live_handoff_yaw_servo_v1_matrix_smoke_20260426/gather_goal_side_matrix/campaign_summary.json` | Required fresh `zero` / `plus45` gate stayed pre-stage blocked | Archive current branch; reuse only as a new fetch approach-stability idea. |
| `pre_stage_reacquire_fsm_v1` | `artifacts/session/live_pre_stage_reacquire_fsm_v1_matrix_smoke_20260426/gather_goal_side_matrix/campaign_summary.json` | Physics-independent pre-stage blocked | Archive current branch. |
| `pre_stage_path_tracker_v1` | `artifacts/session/live_pre_stage_path_tracker_v1_matrix_smoke_20260426/gather_goal_side_matrix/campaign_summary.json` | Physics-independent escape / waypoint progress failure | Archive current branch. |
| `pre_stage_trajectory_owner_v1` | `artifacts/session/live_pre_stage_trajectory_owner_v1_matrix_smoke_20260427/gather_goal_side_matrix/campaign_summary.json` | Physics-independent trajectory stall / clearance guard before contact | Archive as architecture-review evidence. |
| `nav2_follow_path_reacquire_v1` | `artifacts/session/live_nav2_follow_path_reacquire_v1_matrix_smoke_20260427/gather_goal_side_matrix/campaign_summary.json` | Physics-independent lower-stack DWB FollowPath abort | Negative baseline evidence only. |
| `nav2_mppi_follow_path_reacquire_v1` | `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_live_audit_20260503/gather_follow_path_research_analyzer/follow_path_research_summary.json`; `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_zero_3run_20260503/gather_mission_repeatability/campaign_run_summary.json`; `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_plus45_3run_20260503/gather_mission_repeatability/campaign_run_summary.json` | Recovered pre-stage, downstream contact-contaminated | Preserve as long-range/pre-stage baseline evidence only. |
| legacy corral/place one-ball baseline | `artifacts/session/20260413T054235Z/gather_mission_repeatability/campaign_run_summary.json`; later mixed evidence such as `artifacts/session/20260416T184447Z/gather_mission_repeatability/campaign_run_summary.json` | Old gather/place contact evidence, physics-contaminated | Historical practical baseline, not evidence against calibrated fetch. |
| `object_centric_gather_policy_v1` | `docs/OBJECT_CENTRIC_GATHER_POLICY_RESEARCH_PLAN.md` | Superseded gather/place plan | Do not reopen as a gather/place promotion path. |
| `object_centric_fetch_policy_v1` | `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`; `artifacts/session/live_passive_golf_roll_built_resistance_repeatability_20260526/passive_ball_roll_calibration/campaign_summary.json` | Active calibrated baseline | Organize new alternatives around this gate and telemetry. |
| `contact_aware_geometric_shooter` | `artifacts/session/live_fetch_geometric_shooter_screen_20260527/fetch_geometric_shooter_screen/geometric_shooter_summary.json`; `artifacts/session/live_fetch_geometric_shooter_probe_zero_20260527/fetch_geometric_shooter_probe/geometric_shooter_probe_summary.json` plus `left05` / `right05` one-run probes | Direct-velocity physics probe, not robot-owned runtime evidence | Keep as roll-window/coast-geometry evidence; do not promote as the primary runtime path. |
| `nav2_followpath_corridor_push_v1` | `artifacts/session/live_nav2_corridor_push_contact_ready_rerun3_20260529/calibrated_fetch_architecture_revisit/scorecard.md`; `artifacts/session/live_nav2_corridor_push_full_saved_layout_20260529/calibrated_fetch_architecture_revisit/scorecard.md` | Evidence branch; not standalone promotion candidate | Contact-ready and full saved-layout one-run gates passed, but saved-layout `3/3` failed on `right05` stop-short after Nav2 `STATUS_SUCCEEDED`. Preserve as corridor-tracking baseline and AI training/eval data. |
| corrected Nav2/LLM-first baseline | `artifacts/session/20260531T204154158382Z/gather_mission/20260531T204255Z/mission_verdict.json`; `artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md` | Preferred immediate requalification lane | Rerun saved layouts and planner-approved local random cases with corrected geometry and same-session video before expanding custom contact or learned control. |
| calibrated-ball direct fetch reset | `artifacts/session/20260601T000718616964Z/visual/raw_camera_browser.mp4`; `artifacts/session/20260601T000718616964Z/visual/topdown_telemetry_browser.mp4`; `artifacts/session/20260601T000718616964Z/visual/world_stream.mp4` | Current model-provenance reference | Rebuild saved-layout direct evidence from commit `680e393` onward with `model_provenance_valid=true`; quarantine missing-provenance or legacy-ball direct summaries. |
| Nav2 contact-buffer handoff baseline | `artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`; `artifacts/session/uat_contact_buffer_monitor_servo_zero_probe_20260601/fetch_visual_uat_package/scorecard.md` | Preferred local fetch implementation baseline; one-run proof only | Commit `02a4c12` uses tight corridor goal checking, fixes the depth scan TF, and hands off from Nav2 to a deterministic contact servo at a close/aligned no-object-motion contact buffer. Rebuild saved-layout one-run and `3/3` before promotion. |
| `ai_push_coast_servo_v1` | `artifacts/session/live_fetch_setup_contact_repair_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`; `artifacts/session/live_fetch_case01_near_margin_gate_v1_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`; `artifacts/session/live_fetch_case04_relaxed_standoff_v1_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`; `artifacts/session/live_fetch_near_margin_case04_repeat_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`; `artifacts/session/live_fetch_guarded_live_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`; `artifacts/session/live_fetch_guarded_live_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`; `artifacts/session/evidence_fetch_guarded_live_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`; `artifacts/session/uat_fetch_guarded_live_seeded_case04_20260602/fetch_visual_uat_package/scorecard.md` | Active milestone branch; contract evidence promotion-ready and UAT package ready | Saved anchors passed `3/3`; case01 near-margin passed `3/3`; case04 targeted delivery passed `3/3`; clean shadow seeded gate passed `6/6`; guarded-live saved anchors passed `3/3`; guarded-live seeded random passed `6/6` with `promotion_evidence=True`; browser-watchable UAT package passes. Continue with operator clip review, then select contact-quality polish or broader planner-routed coverage. |
| `ai_push_coast_servo` umbrella | corrected Nav2-first gaps plus saved/random traces | Model/proposer direction | Train or prototype local handoff/maneuver-class predictor from calibrated simulation, score in shadow mode on saved anchors and seeded random layouts, then allow it to select only deterministic guarded routines after shadow scoring proves a benefit. |

## Latest Revisit Result

The May 27, 2026 targeted MPPI revisit did not justify developing the old
`nav2_mppi_follow_path_reacquire_v1` alternative:

- artifact:
  `artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`
- command shape:
  `python scripts/calibrated_fetch_architecture_revisit.py --candidate-family nav2_mppi_follow_path_reacquire_v1 --runs 1 --promote-on-green --promote-runs 3`
- result: saved-layout `zero`, `left05`, and `right05` each failed one-run
  calibrated `fetch_to_pose` before contact
- failure class: `pre_stage_path_clearance_guard`
- artifact reasons: `nav2_follow_path_path_clearance_guard` and
  `pre_stage_pose_not_reached`
- branch decision: keep MPPI as long-range/pre-stage baseline evidence only; do
  not create a development branch for this alternative

This does not close the new `nav2_followpath_corridor_push_v1` hypothesis. The
new spike is a fresh contact-ready/corridor-push test under calibrated physics,
not a revival of the blocked MPPI pre-stage branch.

## Latest Nav2 Corridor-Push Result

The May 29, 2026 Nav2 corridor-push spike produced useful bounded-contact
evidence, but it does not promote as the standalone contact architecture:

- branch: `spike/fetch-arch-nav2-corridor-push-20260528`
- implementation/evidence commit: `03c0aaf`
- contact-ready artifact:
  `artifacts/session/live_nav2_corridor_push_contact_ready_rerun3_20260529/calibrated_fetch_architecture_revisit/scorecard.md`
- full-layout artifact:
  `artifacts/session/live_nav2_corridor_push_full_saved_layout_20260529/calibrated_fetch_architecture_revisit/scorecard.md`
- result:
  contact-ready `zero`/`left05`/`right05` passed; full saved-layout one-run
  `zero`/`left05`/`right05` passed; saved-layout repeatability passed `zero`
  and `left05` `3/3` but failed `right05` `2/3`
- failing class:
  `missed_delivery_radius_after_fetch_to_pose_ball_stopped_short`; Nav2
  returned `STATUS_SUCCEEDED`, the ball moved only about `0.121m`, and closest
  approach was `0.451645m` against the `0.300m` delivery radius
- branch decision:
  preserve Nav2 corridor-push as a baseline path-tracking/contact-data branch.
  Standalone promotion requires corrected repeatability evidence. Start the
  hybrid stage-supervisor spike from this evidence: Nav2 owns the stages it
  handles well, deterministic routines own fine contact and terminal
  correction, and the model starts as a shadow handoff/maneuver proposer.

Seeded random/generalization remains pending for this branch.
Generalized-behavior claims require saved-anchor repeatability followed by the
reusable `fetch_generalization_gate`.

## Latest Nav2 Contact-Buffer Handoff Result

The June 1, 2026 fix-forward pass validates the staged local fetch sequence that
the branch strategy now prefers:

- branch: `spike/fetch-arch-ai-push-coast-servo-20260529`
- implementation/evidence commit: `02a4c12`
- campaign:
  `artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`
- visual package:
  `artifacts/session/uat_contact_buffer_monitor_servo_zero_probe_20260601/fetch_visual_uat_package/scorecard.md`
- result:
  `zero` passed one-run `fetch_to_pose` with `0.179959m` closest delivery
  distance, `geometry_consistency.pass=true`, and calibrated model provenance
- handoff telemetry:
  Nav2 canceled at `monitor_contact_buffer_handoff` with
  `robot_ball_distance_m=0.195671`; the deterministic contact servo confirmed
  `0.046811m` ball motion; the later corridor push ended with
  `monitor_success`
- branch decision:
  make this the immediate local fetch implementation baseline. Nav2 owns
  corridor approach, the adapter owns contact-buffer classification, the
  deterministic servo owns first-contact confirmation, and Nav2 plus the
  monitor own delivery. The next branch work is saved-layout requalification;
  broader learned control remains queued behind evidence.

Promotion remains blocked until corrected `zero`/`left05`/`right05` one-run,
saved-layout `3/3`, seeded `6 x 1`, and a healthy browser-watchable visual UAT
package are green.

Planner-routed moonshot update, June 2:

- branch:
  `spike/fetch-arch-planner-routed-forward-only-moonshot-20260602`
- purpose:
  test the full-stack route contract before another narrow controller fix
- executable lanes:
  `fetch_ready_local`, `nav2_reposition_first`, and `recovery_or_reaim`
  dispatch the forward-only golf delivery runner with route metadata and a
  pre-contact forward-motion guard; `nav2_reposition_first` uses real Nav2
  setup before local fetch; `recovery_or_reaim` uses the bounded local re-aim
  routine from the generated robot pose; `ambiguous_or_unsafe_no_go` records
  an executed safe no-go; `scan_or_perceive_first` records a planner-owned
  refresh/abstain outcome
- current recovery evidence:
  the exact recovery layout that stalled without contact at `0.739814m` closest
  (`20260603T040615017369Z`) now passes at `0.196169m` closest
  (`20260603T042159429741Z`) after `recovery_line_acquire` was added. Package:
  `artifacts/session/uat_recovery_line_acquire_fix_seed20260606_20260603/fetch_visual_uat_package/scorecard.md`
- broad frozen route evidence:
  the mixed planner handoff gate passed `5/5` with zero wrong fetch dispatches:
  `artifacts/session/live_broad_frozen_planner_routed_gate_20260603/fetch_planner_handoff_gate/gate_summary.json`.
  Same-session executable route UAT passed for `fetch_ready_local`
  (`20260603T043331724833Z`, closest `0.196023m`),
  `nav2_reposition_first` (`20260603T043525704923Z`, closest `0.193737m`),
  and `recovery_or_reaim` (`20260603T043728550735Z`, closest `0.197799m`).
  `scan_or_perceive_first` and `ambiguous_or_unsafe_no_go` selected the correct
  planner-owned non-fetch actions. Combined package:
  `artifacts/session/uat_broad_frozen_planner_routes_20260603/fetch_visual_uat_package/scorecard.md`
- randomized route-owner evidence:
  generated planner handoff passed `15/15` with zero wrong fetch dispatches:
  `artifacts/session/live_random_planner_routed_gate_seed20260607_15case_20260603/fetch_planner_handoff_gate/gate_summary.json`.
  Executable route UAT passed `6/6`, with two live runs each for
  `fetch_ready_local`, `nav2_reposition_first`, and `recovery_or_reaim`.
  Closest approach ranged from `0.193687m` to `0.247356m`, inside the
  `0.300m` delivery contract. Contact quality is a watch item because
  pre-contact lateral/yaw flags appeared in all six runs, while first-contact
  flags stayed clean.
  Combined package:
  `artifacts/session/uat_random_planner_routes_seed20260607_exec6_20260603/fetch_visual_uat_package/scorecard.md`
  Route UAT analyzer:
  `artifacts/session/route_uat_random_seed20260607_exec6_analyzer_20260603/fetch_planner_route_uat_analyzer/scorecard.md`
- June 4 recovery/re-aim boundary evidence:
  the exact seed `20260627` recovery row that previously failed before contact
  passed after `recovery_or_reaim` stopped invoking real Nav2 pre-fetch setup.
  The run used the generated robot pose, `nav2_reposition_before_fetch=false`,
  clean first-contact quality, stable contact approach, and closest approach
  `0.193732m`.
  Replay batch:
  `artifacts/session/live_recovery_reaim_local_setup_scene04_20260604/fetch_planner_route_replay_batch/scorecard.md`.
  Visual package:
  `artifacts/session/live_recovery_reaim_local_setup_scene04_20260604_seed20260627_scene04_recovery_or_reaim/fetch_visual_uat_package/scorecard.md`.
- video recovery:
  `fetch_visual_uat_package.py` now rebuilds browser-safe onboard, top-down, and
  world-stream clips from saved frame sequences when recorder MP4s are missing,
  empty, or invalid. Scorecards list those recoveries explicitly.
- next branch decision:
  keep this branch disposable while using the seven-seed executable regression
  manifest and the seed `20260633` mixed route-family proof as the current UAT
  baseline. The non-fetch proof is
  `artifacts/session/live_planner_only_route_proof_seed20260633_20260604/fetch_planner_route_replay_batch/scorecard.md`:
  one `scan_or_perceive_first` row and one `ambiguous_or_unsafe_no_go` row
  passed with local fetch withheld, browser-watchable packages, `59` samples
  each, and measured robot/ball motion `0.000m`. The mixed proof is
  `artifacts/session/analysis_mixed_route_family_uat_seed20260633_20260604/fetch_planner_route_uat_analyzer/scorecard.md`:
  one live row per route family, route contracts `5/5`, visual packages `5/5`,
  executable deliveries `3/3`, route-only proofs `2/2`, and first-contact
  blockers `0`. The scaled mixed proof is
  `artifacts/session/analysis_mixed_route_family_2per_route_seed20260633_20260604/fetch_planner_route_uat_analyzer/scorecard.md`:
  two live rows per route family, route contracts `10/10`, visual packages
  `10/10`, executable deliveries `6/6`, route-only proofs `4/4`, and
  first-contact blockers `0`. The next patch should repeat mixed-family breadth
  on a second rough seed or package the stack for hardware-transfer review
  before contact-quality tuning.
- second rough mixed-family confirmation:
  seed `20260632` repeated the full two-live-samples-per-route package at
  `artifacts/session/analysis_mixed_route_family_2per_route_seed20260632_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
  The replay used fresh packages for all `10` rows and passed route contracts
  `10/10`, visual packages `10/10`, executable deliveries `6/6`, route-only
  proofs `4/4`, clean analyzer status, and first-contact blockers `0`.
  Branch decision: keep
  `spike/fetch-arch-planner-routed-forward-only-moonshot-20260602` active as
  the planner-routed UAT harness. The next branch work is a harder mixed
  scenario matrix plus hardware-transfer packaging. Alternative architectures
  remain reserve lanes for reproduced stage gaps in that harder matrix.
- frozen planner-layout replay fix:
  fresh seed `seed20260608_scene24_fetch_ready_local` first failed as a manual
  target-layout replay because the runner used the old constant-push defaults
  and default robot pose. The branch now applies planner route execution
  defaults from frozen layouts, including route metadata, planned robot pose for
  `fetch_ready_local`, current-robot pose normalization for setup-first route
  replays, long-horizon line servo, delivery stop, and forward-only
  contact guard. Patched rerun `20260603T120817888242Z` passed at `0.196327m`.
  Diagnostic package:
  `artifacts/session/uat_planner_route_replay_fix_seed20260608_scene24_20260603/fetch_visual_uat_package/scorecard.md`
- frozen executable-route coverage:
  seed `20260608` now has one browser-watchable replay for each executable
  route owner: `fetch_ready_local`, `nav2_reposition_first`, and
  `recovery_or_reaim`. Combined analyzer:
  `artifacts/session/route_uat_frozen_seed20260608_three_route_replays_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
  Result is visual-UAT green with contact-quality watch, `0` first-contact
  blockers, and no promotion claim. The next branch work should improve
  pre-contact lateral/yaw posture while preserving the route-owner split.
- corrected fresh-session route replay:
  `scripts/fetch_planner_route_replay_batch.py` now owns balanced executable
  route replay and can start a fresh dashboard session per row. Each mission
  receives `--expected-session-id`, the sim is stopped before visual packaging,
  and `fetch_visual_uat_package.py` writes the keyframe review sheet inside the
  package, isolating sequence-review evidence per row.
- corrected six-scene evidence:
  the first shared-session six-run replay exposed one detached visual package
  and one `nav2_reposition_first` miss that cleared under clean session
  binding. Fresh-session reruns passed all six executable frozen layouts from
  seed `20260608`: two
  `fetch_ready_local`, two `nav2_reposition_first`, and two
  `recovery_or_reaim`. Combined analyzer:
  `artifacts/session/route_uat_seed20260608_six_fresh_sessions_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
  Result is route-owner UAT green with `promotion_evidence=false`, contact
  quality `watch`, first-contact blockers `0`, and closest approaches
  `0.194811m..0.197835m`.
- branch decision:
  keep the moonshot branch active as the route-owner UAT harness. The next
  branch work is a route-quality scorer and pre-contact smoothing, especially
  lateral/yaw setup quality and recovery first-contact alignment. Preserve the
  LLM/world-state planner split and continue using Nav2 for reposition/corridor
  stages where the fresh evidence stays green.
- route-quality scorer evidence:
  `scripts/fetch_planner_handoff_gate.py` now records route-quality score,
  predicted contact quality, first-contact risk, route-quality flags, and
  recommendations. `scripts/fetch_planner_route_replay_batch.py` can select
  `--quality-order roughest` for stress UAT. Seed `20260613` roughest live
  replay passed all three executable route owners with same-session packages:
  `artifacts/session/live_route_quality_roughest_fresh_replay_20260603/fetch_planner_route_replay_batch/scorecard.md`.
  Combined analyzer:
  `artifacts/session/route_uat_route_quality_roughest_live_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
  Result is route-owner UAT green with `promotion_evidence=false`, contact
  quality `watch`, first-contact blockers `0`, and closest approaches
  `0.193026m..0.197752m`.
- branch decision update:
  keep the planner-routed moonshot branch active. The next controller slice is
  recovery first-contact smoothing, because the high-risk recovery case still
  shows visible off-axis contact while Nav2 reposition produced clean first
  contact under the same roughest-selector harness.
- readyfix update, June 4:
  seed `20260627` now has a green representative route-owner UAT package and
  stronger mission-only gate evidence. Planner child
  `live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_planner`
  passed `30/30`; mission-only replay passed `6/6` and proved the
  Nav2-abort-to-local-recovery boundary; visual replay
  `live_planner_seeded_generalization_gate_visual_recheck_20260604` passed
  `4/4` with browser-watchable packages across recovery, fetch-ready, and
  Nav2-first rows. Keep this branch as the active planner-gated route-owner
  lane, and keep promotion pending until the parent seeded gate carries the
  canonical live visual package with `promotion_evidence=true`.
- harness update:
  stale-model cleanup timeouts now return recorded timeout status instead of
  killing the delivery runner before mission dispatch.
- seed `20260629` boundary repairs, June 4:
  seed `20260629` kept the planner handoff green at `30/30` with
  `0` wrong fetch-ready dispatches, then stopped on the first live
  `nav2_reposition_first` row after Nav2 aborted before fetch with no ball
  motion and no first-contact trace. The exact row
  `seed20260629_scene01_nav2_reposition_first` now passes in
  `live_seed20260629_scene01_nav2_abort_fallback_repro_20260604`, with closest
  approach `0.195562m`, clean first-contact flags, stable contact approach, and
  browser-watchable onboard/topdown/world proof. The clean pre-contact abort
  fallback now admits otherwise-safe rows out to `1.300m` robot-ball separation,
  preserving the ball-motion, lateral, yaw, and ball-target gates. The resumed
  parent gate then exposed and repaired a second boundary:
  `seed20260629_scene05_recovery_or_reaim` reached clean first contact after
  about a minute, so the old recovery window left too little push time. The
  longer bounded recovery window repaired scene05 while preserving
  delivery-stop behavior. The final parent gate is green at
  `artifacts/session/live_planner_seeded_generalization_gate_seed20260629_boundary_repair_full_visual_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`
  with `30/30` planner routing, `6/6` live missions, `6/6` visual packages,
  clean analyzer status, and `promotion_evidence=true`. This branch now has
  three randomized promotion-green seeds: `20260627`, `20260628`, and
  `20260629`.
- regression manifest update, June 4:
  `scripts/fetch_moonshot_regression_manifest.py` now makes the branch's
  preservation bar explicit. The green manifest at
  `artifacts/session/analysis_planner_moonshot_regression_set_20260604/fetch_moonshot_regression_manifest/scorecard.md`
  verifies saved-anchor repeatability, the setup/contact audit, the three
  promoted seeded gates, and the two seed `20260629` boundary rows. Use this
  analyzer as the branch-local regression gate before route-owner swaps,
  executor moonshots, recovery-window changes, visual-packaging changes, or
  hardware-transfer claims.

Saved-anchor requalification update, later June 1:

- planner gate:
  `artifacts/session/live_planner_handoff_mixed_fetch_20260601/fetch_planner_handoff_gate/gate_summary.json`
  passed `5/5`
- one-run saved anchors:
  `zero` passed at
  `artifacts/session/live_contact_buffer_saved_anchor_zero_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`;
  `left05` passed at
  `artifacts/session/live_contact_buffer_saved_anchor_left05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`;
  `right05` failed at
  `artifacts/session/live_contact_buffer_saved_anchor_right05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
- audit:
  `artifacts/session/audit_contact_buffer_right05_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
  classifies `right05` as `setup_capture_blocker`
- branch decision:
  keep the staged Nav2/contact-buffer baseline as a candidate, insert a broad
  stage-owner comparison before right-offset repair, and compare current staged
  behavior against May 27 object-centric saved-anchor evidence, Nav2
  corridor-push, corrected direct `right05`, and prior acquisition or goal-side
  setup evidence. Repeatability, seeded gate, and guarded-live terminal
  correction wait for the comparison result.

## Wider Architecture Portfolio

Treat the runnable legacy `--gather-control-family` list as a control-family
screen inside one mission shell. The wider architecture portfolio is tracked in
[CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md](CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md)
and includes distinct ownership and interaction models:

- contact-aware geometric shooter as physics-probe evidence
- hybrid fetch stage supervisor with AI handoff/proposal
- receding-horizon contact MPC / object servo
- ROS action-server or behavior-tree last-meter owner
- Nav2 reposition plus object-centric last-meter handoff
- passive mechanical guide or funnel
- learned residual or maneuver proposer behind deterministic guards
- LM/VLA high-level supervisor over known maneuver choices
- portfolio supervisor / switcher
- perception-first target-pose fetch

Branching rule for wide tests:

1. put shared harnesses, analyzers, and docs on `physics-calibrated-golf-fetch-v1`
2. create `spike/fetch-arch-<family>-YYYYMMDD` for one architecture hypothesis
3. use accelerated/offline screens only for cheap rejection; never use them as
   UAT evidence. The current calibrated accelerated lane is 2.0x
   (`yolo_test_world_v6_calibrated_golf_turf_fast.world`); 3.0x/4.0x worlds are
   experimental speed sweeps and must be labeled that way.
4. require AI-assisted lanes to pass shadow-mode saved-anchor and seeded-random
   scoring before learned proposals execute live
5. promote to `candidate/fetch-arch-<family>` only after canonical saved-layout
   `zero`, `left05`, and `right05` one-run evidence is green and the candidate
   benefit is written down
6. require `3/3` saved-layout repeatability before release or demo discussion

## Decision Rule

Branch decisions live here. A future architecture revisit should start as a
short-lived spike from `physics-calibrated-golf-fetch-v1`, not by promoting a
blocked branch in place. A blocked branch becomes a candidate again only after
fresh `zero` and `plus45` pre-stage proof is recorded with artifact paths and an
explicit update to this document.

Current preferred branch decision: use the current fetch spike to score a broad
stage-owner comparison before adding broader live custom control. The immediate
hypothesis is staged rather than Nav2-only: planner-approved local cases should
use Nav2 for corridor approach, a monitored contact-buffer handoff for
close/aligned no-object-motion stops, deterministic first-contact confirmation,
and Nav2 corridor push plus delivery monitoring. The next runnable branch work
should compare this staged behavior against the May 27 object-centric package,
Nav2 corridor-push, corrected direct `right05`, and prior acquisition or
goal-side setup evidence before selecting a targeted repair.

Keep `spike/fetch-arch-ai-push-coast-servo-20260529` available for analyzers,
guards, shadow scoring, and narrow fallback routines. Learned local output may
execute only by selecting deterministic guarded routines after corrected
saved-anchor and seeded-random scoring proves a reproducible gap and a measured
benefit. LM/VLA components may supervise mode choice and failure interpretation
through deterministic contracts. Large V-JEPA-style world models remain
offboard teacher or research baselines; onboard inference should be smaller and
`tensorrt_int8`-compatible.
