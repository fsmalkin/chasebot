# Calibrated Golf Fetch Branch Strategy

This document owns branch-role decisions for calibrated golf fetch work. Use the
roadmap for priority, `ACTIVE_WORKFLOW.md` for gates and commands, and the
`OBJECT_CENTRIC_*` docs for research details.

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
     `spike/nav2-mppi-terminal-geometry-revisit`, and
     `spike/architecture-revisit-object-centric-fetch-2026Q3`.
   - Each spike must state its hypothesis, artifact target, expected gate, and
     expiry condition in its PR or handoff notes.
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

## Latest Revisit Result

The May 27, 2026 targeted MPPI revisit did not justify developing an alternative
architecture:

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

## Wider Architecture Portfolio

Do not treat the runnable legacy `--gather-control-family` list as full
architecture coverage. Those families mostly vary pre-stage/contact control
inside the same mission shell. The wider portfolio is tracked in
[CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md](CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md)
and includes distinct ownership and interaction models:

- contact-aware geometric shooter
- receding-horizon contact MPC / object servo
- ROS action-server or behavior-tree last-meter owner
- Nav2 reposition plus object-centric last-meter handoff
- passive mechanical guide or funnel
- learned residual or maneuver proposer behind deterministic guards
- portfolio supervisor / switcher
- perception-first target-pose fetch

Branching rule for wide tests:

1. put shared harnesses, analyzers, and docs on `physics-calibrated-golf-fetch-v1`
2. create `spike/fetch-arch-<family>-YYYYMMDD` for one architecture hypothesis
3. use accelerated/offline screens only for cheap rejection; never use them as
   UAT evidence
4. promote to `candidate/fetch-arch-<family>` only after canonical saved-layout
   `zero`, `left05`, and `right05` one-run evidence is green and the candidate
   benefit is written down
5. require `3/3` saved-layout repeatability before release or demo discussion

## Decision Rule

Branch decisions live here. A future architecture revisit should start as a
short-lived spike from `physics-calibrated-golf-fetch-v1`, not by promoting a
blocked branch in place. A blocked branch becomes a candidate again only after
fresh `zero` and `plus45` pre-stage proof is recorded with artifact paths and an
explicit update to this document.
