# Roadmap 2026 H2

## Near-Term (First UAT to Full Visual UAT)

Current status as of February 27, 2026:

1. First-UAT promotion gate is green (`session 20260227T230314Z`).
2. Full headless replay gate is green (`session 20260227T231443Z`).
3. Visual milestone evidence runs are green for M1/M2/M3 (latest M2 `20260227T232250Z`, M3 `20260227T232745Z`).
4. Next promotion focus is repeatability and soak cycles for the same gates.

1. Keep `scripts/run_first_uat.ps1` as the default operator entrypoint on `ExecutionLane=container_kilted`.
2. Keep gate-critical first-UAT steps container-native (no host `/opt/ros/kilted` dependency).
3. Achieve first-UAT green on canonical target:
   - coordinate summary `pass=true`
   - milestone 1 evidence bundle present
4. Run headless replay gates in sequence:
   - coordinate
   - snapshot verification
   - orientation
   - Nav2 readiness
   - multi-target Nav2
5. Run visual milestone progression:
   - milestone 1 (perception)
   - milestone 2 (3D estimate coherence)
   - milestone 3 (autonomous approach)
6. Freeze operator docs only after one green first-UAT cycle and one green full headless replay cycle.
7. Keep `scripts/run_headless_pre_llm.ps1` as the default developer push path with `Lane=dual` until LLM integration starts.

Status update as of February 28, 2026:

1. Pre-LLM dual-lane campaign achieved `3/3` green:
   - `artifacts/session/20260228T155850Z/pre_llm_headless_summary.json`
   - `artifacts/session/20260228T160643Z/pre_llm_headless_summary.json`
   - `artifacts/session/20260228T161425Z/pre_llm_headless_summary.json`
2. Fidelity soak gate is green:
   - `artifacts/session/20260228T162201Z/pre_llm_headless_summary.json`
   - includes Nav2 duration `1200s` and 12-goal multi-target sequence.
3. Campaign trend report and RC package generated:
   - `artifacts/session/20260228T164623Z/pre_llm_campaign_trend.json`
   - `artifacts/session/20260228T164654Z/readiness_report.json` (`pass=true`)
4. Pre-LLM contract freeze applied:
   - `runtime/contracts/llm_control_contract.yaml` (`contract_status: frozen_pre_llm`)

## Mid-Term (Dual-Lane Regression Hardening)

1. Keep Jetty gate lane as authoritative release lane.
2. Maintain Isaac lane as parity/cross-validation lane behind bridge contract.
3. Add weekly dual-lane regression policy:
   - Jetty full headless gate replay weekly
   - Isaac subset parity replay weekly
4. Enforce per-session isolation:
   - unique compose project naming
   - stale project cleanup before each run
   - explicit ROS domain strategy per session

## Pre-LLM Integration Gate Checklist

1. Acquire/plan/track low-level interfaces are frozen and documented.
2. Safety contracts are frozen:
   - stale detection timeout
   - navigation timeout
   - safe stop behavior
3. Required artifact set is green in one release candidate cycle:
   - coordinate summary
   - orientation summary
   - nav readiness summary
   - milestone evidence bundle(s)
4. Unresolved failure signatures are tracked in session readiness reports.
5. Final GUI rehearsal aligns with headless gate outcomes before LLM handoff.

## Post-Freeze Bounded LLM Promotion Path

Once the frozen pre-LLM boundary is in place, the next roadmap step is not open-ended autonomy. It is a bounded promotion ladder:

1. headless LLM proof over the frozen intent contract (complete)
2. repeatability gate on the authoritative `container_kilted` lane (complete)
3. simple browser UAT demo for the same proof path (complete)
4. bounded supervisor reuse across the visible-ball M3 scenario family (complete)
   - `visit_m3_positions` scenario validates center, left, right targets using the same policy
5. target prior contract for multi-target scenarios (complete)
   - executor receives expected target position from the mission layer, not from sim ground truth
   - prior-based lock gating and prior-based track approach implemented and tested
   - `visit_single_ball_proof` and `visit_three_ball_sequence` passing
   - sim truth probe is a validation oracle (test-time only), not an executor runtime dependency
   - this makes the executor's target discrimination portable to hardware
6. provider benchmarking infrastructure for a future on-machine model path on Orin Nano (complete)
   - provider abstraction (`DecisionProvider` protocol) and replay comparison tool exist
   - `LocalModelProvider` placeholder ready for Orin Nano integration
   - benchmarking is not a prerequisite for the current promotion ladder

Status update as of April 3, 2026:

1. All six promotion ladder steps are complete.
2. Target prior contract validated: `visit_three_ball_sequence` 3/3, `visit_m3_positions` 3/3.
3. Escalation rules formalized with table and 19 policy tests.
4. Browser UAT surface meets acceptance criteria (Watch/Drive/Inspect tabs).
5. Provider benchmarking infrastructure in place (replay comparison tool, local provider placeholder).

Status update as of April 4, 2026:

1. Direct intent dispatch implemented: file-based inbox replaces docker-exec-per-intent.
2. Intent dispatch latency reduced from ~13s to <1s.
3. Zombie dashboard prevention: startup kills stale processes, `allow_reuse_address` enabled.
4. Dashboard URL fix: client-facing URL uses `127.0.0.1` when binding `0.0.0.0` (Windows).

### Intended Outcomes

1. prove that the LLM can supervise high-level bounded decisions without owning low-level loops
2. keep deterministic policy/gating as the safety and contract layer
3. give operators a browser demo that is simple enough to trust and understand
4. keep the control architecture compatible with both:
   - Wi-Fi/cloud inference
   - smaller local-model inference later
5. ensure multi-target discrimination is solved in sim before hardware POC:
   - executor target verification uses mission-provided priors, not sim-only ground truth
   - the same mechanism works on hardware with operator-provided or observation-derived priors

### Explicit Non-Goals For This Roadmap Slice

1. freeform browser prompt control
2. open-ended task decomposition
3. end-to-end VLA action generation
4. autonomous environment lifecycle management by the LLM
5. pivoting the roadmap slice to end-to-end VLA control
6. replacing deterministic perception, planning, or execution loops with model-generated low-level action

## Next Roadmap Slice: Gather Generalization Slice, Goal-Side Matrix And Geometry Sweeps

The route-planning baseline remains the protected regression floor, and the
single-ball corral path now has an explicit dual-radius scoring model on
realistic soccer-practice surfaces. Using the committed shorter spur geometry,
the current one-ball flow is acceptable enough as the working development
baseline. The next gather milestone is no longer framed as "clear
`capture_entry` and green the named matrix cases." The latest April 18, 2026
`plus45` evidence progressed from `pre_stage` failures to `stage`, then to
`capture_entry_ready`, yet still failed after the handoff, which now points to
brittle cross-phase transitions rather than a single remaining threshold bug.
Fresh-only April 19, 2026 `plus45` evidence then stayed red `5/5` in
`pre_stage_timeout` even after retry-oriented escape fixes, which shows the
current controller can satisfy local branch objectives while still failing the
global behind-ball objective. The goal-side matrix remains the first offline
coverage harness, and the next gate extends beyond those named cases into
nearby geometry sweeps and controller-family comparisons. The deeper April 19,
2026 truth-state escape oracle then still produced `0/5` stable goal-side
clears on the representative fresh-only `plus45` fixtures, which means the
next move should be a richer offline escape sandbox rather than another live
controller-family promotion attempt.

Surface and ball fidelity remain an open realism question, and the calibration
harness remains useful, but that thread no longer blocks the roadmap. The
dashboard UAT story stays honest: route-planning is protected, and gather UAT
does not move until the redesigned control path proves generalization across
the harness.

The important product outcome stays explicit: we care about the ball ending up
retrieved and stopped in the corral area, not whether it stayed perfectly
centered under the spur. The outer retrieval ring remains a 5-foot diameter
circle (`0.762 m` radius), while the inner `0.20 m` control ring stays in
place for release and correction heuristics. In the later multi-ball
milestone, already retrieved balls helping arrest later balls through
collisions is a valid assist, not an anti-goal.

```mermaid
flowchart LR
    A[Route-planning baseline] --> B[Operator-acceptable one-ball retrieval baseline]
    B --> C[Deterministic gather-control family comparison]
    C --> D[Goal-side matrix plus geometry sweeps]
    D --> E[Three-ball gather promotion]
    E --> F[Corral accel and decel optimization]
    F --> G[Onboard planner evaluation]
    B -.-> H[Surface and ball fidelity follow-up if needed]
```

### Step 1: Route-Planning Baseline - Complete

Goal: keep the current visit-and-avoid stack as the regression floor while new
gather behavior lands above it.

Validated evidence:

1. authoritative serial dashboard gate: `artifacts/session/20260412T170306Z/route_planning_serial_gate/campaign_summary.json`
2. serial operator scorecard: `artifacts/session/20260412T170306Z/route_planning_serial_gate/scorecard.md`
3. isolated parallel soak baseline: `artifacts/session/20260412T054630Z/route_planning_parallel_soak/campaign_summary.json`

What this means:

1. `visit_route_planning` is now a one-click self-contained dashboard proof
2. already-visited balls are avoided on later legs instead of being driven through
3. serial dashboard UAT remains the trust surface
4. parallel soak remains the throughput surface

Exit criterion for this step:

1. keep the route-planning serial gate green while corral/place work is added

### Step 2: Single-Ball Corral / Place Through Dashboard UAT - Complete

Goal: the robot keeps one ball controlled at the front of the robot and places
it into a designated area, then proves that behavior through the browser
dashboard before the operator-facing primary action changes.

Assumptions for this proof:

1. operating surface is smooth, like a soccer field or similar practice surface
2. the robot gets a simulated front-mounted catcher shaped like a spur with a U opening outward
3. the catcher sits below the ball midline so the ball can roll into a stable push envelope while the robot advances
4. success is measured by zone entry and control, not just contact

Work:

1. keep `visit_route_planning` green as the regression baseline while catcher/corral work lands
2. hold the single-ball corral/place proof green offline and headless before dashboard handoff
3. keep `corral_single_ball_place` integrated in the dashboard control plane without promoting the primary button yet
4. stabilize repeated operator-visible dashboard UAT on the one-ball flow until it is green `3/3`
5. repoint and relabel the old `Run LLM Route Plan` primary button only after the dashboard proof is green

Validated evidence:

1. single-ball headless `5/5`: `artifacts/session/20260413T054235Z/gather_mission_repeatability/campaign_run_summary.json`
2. clean browser/dashboard `3/3`: `artifacts/session/20260413T_CORRAL_DASHBOARD_UAT_GATE2/dashboard_uat_summary.json`
3. milestone promotion commit: `98ca4a2`

Acceptance:

1. single-ball dashboard UAT passes `3/3`
2. the ball is kept controlled and placed into the zone without ricochet dependence
3. the old primary route-planning button is replaced by the new single-ball corral action only after that proof
4. route-planning regression evidence remains green

Operator-facing promotion rule:

1. before dashboard UAT passes, `corral_single_ball_place` may exist as a scenario but does not replace the primary route-planning action
2. after dashboard UAT passes, the existing `Run LLM Route Plan` primary button is repointed or relabelled to the single-ball corral flow
3. that button replacement is the promotion signal for this milestone

Interfaces held constant in this slice:

1. active UAT scenario: `corral_single_ball_place`
2. protected regression scenario: `visit_route_planning`
3. deferred later scenario: `gather_three_ball_zone`
4. deferred provider seam: `plan_collection_route(...)`
5. no frozen-contract changes in this slice

### Step 3: Surface-Aware Single-Ball Corral Refinement - Infrastructure Complete

Goal: simulate the real practice surfaces we care about, then tune one-ball
corral placement so surface friction helps the ball settle inside the zone
instead of rolling through and overshooting.

Why this mattered:

1. fresh UAT showed the ball can still overshoot after it exits the catcher
2. real turf and grass surfaces add friction that should arrest the ball earlier than the current sim surface does
3. it is better to get one-ball place-and-settle behavior right before adding multi-ball gather complexity

Completed work:

1. research how to simulate turf-like and grass-like practice surfaces in the active Gazebo/SDF stack
2. choose one canonical friction preset for short turf and one for short grass, then make them repeatable in sim
3. rerun the one-ball corral proof on those surfaces and measure zone overshoot and settle distance
4. tune the corral placement behavior so friction works to our advantage once the ball leaves the catcher
5. keep `visit_route_planning` green while the surface and corral changes land

Historical evidence under the earlier tighter settle bar:

1. route-planning regression pass: `artifacts/session/20260413T135805491949Z/visit_mission/20260413T135817Z/mission_verdict.json`
2. canonical short-turf headless `5/5`: `artifacts/session/20260413T135949Z/gather_mission_repeatability/campaign_run_summary.json`
3. secondary short-grass headless `3/3`: `artifacts/session/20260413T140714Z/gather_mission_repeatability/campaign_run_summary.json`
4. dashboard UAT `3/3` on calibrated short turf: `artifacts/session/20260412T_CORRAL_DASHBOARD_UAT/dashboard_uat_summary.json`

Checkpoint truth after the 5-foot retrieval-corral promotion:

1. the surface presets and contact seams still exist and remain the right structure
2. the strict sim-only one-ball gate became mixed again after the scoring bar changed
3. fresh mixed checkpoints include failing conservative-lane runs:
   - `artifacts/session/20260416T023444Z/gather_mission_repeatability/campaign_run_summary.json`
   - `artifacts/session/20260416T023035Z/gather_mission_repeatability/campaign_run_summary.json`

Acceptance for this step now means infrastructure only:

1. at least one turf-like surface preset and one grass-like surface preset are reproducible in sim
2. the surface-comparison seam exists even though the canonical calibrated lane is now reopened
3. route-planning regression evidence remains green

What this means:

1. `short_turf` remains the intended default one-ball comparison surface
2. `short_grass` is credible as a secondary comparison surface and fallback candidate
3. gather artifacts now carry settle metrics (`surface_profile`, `final_settle_distance_m`, `max_overshoot_distance_m`, `settle_time_s`, `release_recontact_count`)
4. future multi-ball and speed work will build on this surface structure, but the canonical lane decision remains an open calibration task

### Step 4: 5-Foot Practical Retrieval Baseline - Accepted Checkpoint

Goal: lock the one-ball outcome bar around what a player would call retrieved:
the ball finishes inside the 5-foot corral area, comes to rest there, and does
not meaningfully roll away after the final release or handoff.

Why this checkpoint matters:

1. it defines the product outcome in operator terms rather than overfitting to perfect spur retention
2. it gives later multi-ball work a practical retrieval footprint instead of a too-tight center-only target
3. it keeps the inner `0.20 m` control ring as a robot heuristic without making that tighter ring the product pass bar

Implemented checkpoint:

1. outer retrieval corral fixed at `5 ft` diameter (`0.762 m` radius)
2. inner control ring remains `0.20 m`
3. artifacts and dashboard state carry `final_inside_retrieval_corral`, `ball_stopped_in_corral`, and `rolled_away_after_release`
4. visible corral marker shows both rings
5. the committed shorter spur geometry is restored as the baseline geometry

Checkpoint truth:

1. route-planning regression remains green after the latest corral/contact tuning:
   - `artifacts/session/20260416T023747Z/visit_mission_repeatability/campaign_run_summary.json`
2. operator review now considers the current one-ball behavior acceptable enough to continue development from here
3. strict conservative-lane `short_turf` evidence is still mixed, so this checkpoint should be treated as a practical baseline rather than an exact surface-fidelity proof

Acceptance for this checkpoint:

1. route-planning regression evidence remains green
2. the promoted one-ball flow remains acceptable as the practical retrieval baseline
3. `final_center_inside_zone` and clean spur retention remain visible in artifacts, but they are diagnostic rather than gating
4. no claim is made yet that the simulation exactly matches real grass or turf behavior

### Step 5: Generalizable Gather Control Redesign

Goal: extend the accepted one-ball practical-retrieval baseline into
`gather_three_ball_zone` by replacing brittle phase-specific threshold tuning
with a more general deterministic gather-control design. The active problem is
cross-phase stability across `pre_stage`, `stage`, `capture_entry`, and the
post-`capture_entry_ready` handoff.

Why this is the next slice:

1. the one-ball flow is already acceptable enough to serve as a mechanical baseline
2. multi-ball gather is the next product milestone that actually exercises sequencing and already-placed-ball interactions
3. the latest April 18 `plus45` evidence shows failures migrating across phases, which means single-threshold tuning is no longer the right framing
4. acceleration and deceleration tuning should optimize a multi-ball behavior we trust, not a controller whose handoffs are still brittle
5. exact surface fidelity is still open, but it no longer blocks this next milestone
6. the goal-side matrix plus nearby geometry sweeps are the offline coverage harness for this slice
7. dashboard UAT stays blocked until that harness shows robust cross-phase behavior

Work:

1. keep `gather_three_ball_zone` in the dashboard as a secondary gather scenario, but only behind the offline generalization gate
2. keep the 5-foot diameter retrieval corral (`0.762 m` radius) and `0.20 m` inner control ring fixed
3. preserve the current practical-retrieval pass bar:
   - ball center finishes inside the outer corral
   - ball stops there
   - ball does not meaningfully roll away
4. redesign the shared gather path around stable cross-phase invariants instead of named-case thresholds
5. treat the current 10-foot multi-ball arc matrix as the first coverage and regression harness:
   - radius: `3.048 m` from corral center
   - cases: `+45`, `0`, `-45`
   - `180` backside guard case retained in the matrix
6. extend the harness with small spawn jitter or geometry perturbation sweeps so promotion is not based only on four fixed placements
7. keep `visit_route_planning` green while multi-ball gather work lands
8. keep non-push travel intentionally fast so the robot moves on quickly once a ball is practically retrieved
9. keep surface and ball fidelity calibration available as a realism follow-up rather than the blocking lane
10. compare candidate designs on shared metrics:
   - terminal failure stage
   - `pre_stage_pose_reached`
   - `staging_pose_reached`
   - `capture_entry_reached`
   - successful handoff after `capture_entry_ready`
   - mission pass / practical retrieval pass

Current truth:

1. the one-ball practical-retrieval baseline is accepted enough to keep moving, but fresh strict `short_turf` reruns are still mixed:
   - `artifacts/session/20260416T184447Z/gather_mission_repeatability/campaign_run_summary.json`
2. `visit_route_planning` remains green and protected:
   - `artifacts/session/20260416T184326Z/visit_mission_repeatability/campaign_run_summary.json`
3. the 5-foot diameter corral model is already implemented and operator-visible
4. `gather_three_ball_zone` is now wired into the dashboard as a secondary gather scenario on `short_turf`, but dashboard UAT is blocked until the generalization gate is green
5. the final multi-ball corral audit fields are implemented and emitted in live artifacts:
   - `final_corral_audit`
   - `final_all_targets_inside_retrieval_corral`
   - `final_all_targets_stopped`
   - `final_three_ball_corral_pass`
   - `retrieved_count`
6. the first fresh three-ball sanity run populated those fields, but it still failed on the first-ball release/settle path before any full three-ball proof:
   - `artifacts/session/20260416T184739Z/gather_mission_repeatability/campaign_run_summary.json`
7. the calibration harness exists, but it did not lock a canonical surface yet:
   - `artifacts/session/pre_tune_surface_calibration/corral_surface_calibration/campaign_summary.json`
   - `artifacts/session/halfstep_probe_surface_calibration/corral_surface_calibration/campaign_summary.json`
8. that unresolved fidelity question is now treated as a known follow-up, not the gate in front of multi-ball gather
9. the active three-ball checkpoint now uses the 10-foot multi-ball arc layout and faster non-push transit
10. the protected regression floor stayed green after the faster transit tuning:
   - `artifacts/session/20260417T040105820076Z/visit_mission/20260417T040503Z/mission_verdict.json`
11. the earlier delay before starting the second ball is materially improved in the latest live trace:
   - `ball_b` completed at `04:02:20.475Z`
   - `ball_a` visit attempt started at `04:02:21.599Z`
   - gap: about `1.1 s`
   - trace: `artifacts/session/20260417T040105820076Z/gather_mission/20260417T040116Z/gather_sequence.jsonl`
12. the freshest `plus45` live evidence now reaches `capture_entry_ready` and still fails after the handoff, which is the clearest current sign that the shared gather transitions need redesign:
   - `artifacts/session/live_plus45_captureentry_0625_20260418/gather_mission_repeatability/campaign_run_summary.json`
   - `artifacts/session/20260418T212252235403Z/gather_mission/20260418T212303Z/state_history.jsonl`
13. fresh failing three-ball checkpoint evidence still exists:
   - `artifacts/session/20260417T040027Z/gather_mission_repeatability/campaign_run_summary.json`
14. the deeper truth-state escape oracle still reports `0/5` stable clears and only `near_clear` evidence on the primary fresh-only `plus45` fixtures:
   - `artifacts/session/live_plus45_escape_oracle_deep_20260419/gather_escape_oracle/oracle_summary.json`
   - `artifacts/session/live_plus45_escape_oracle_deep_20260419/gather_escape_oracle/scorecard.md`

Acceptance:

1. route-planning regression evidence remains green
2. the goal-side matrix passes across `+45`, `0`, `-45`, and `180 backside`
3. nearby spawn jitter or geometry perturbation sweeps do not reopen cross-phase failures
4. the promoted path succeeds after `capture_entry_ready`, not only up to it
5. `gather_three_ball_zone` reaches `placed_count == 3` and `retrieved_count == 3`
6. `final_all_targets_inside_retrieval_corral == true`, `final_all_targets_stopped == true`, and `final_three_ball_corral_pass == true`
7. `post_visit_revisit_count == 0` in the promotion bundle
8. already retrieved balls remain in the world and behave as normal obstacles or passive stopping aids
9. one-ball baseline behavior is not regressed while multi-ball gather lands

### Step 6: Gather-Control Alternatives Portfolio

Goal: find the best bounded gather-control approach for the single-ball corral
task without assuming the final design must contain a separate "recovery
strategy." The known wrong-side and stall fixtures are required stress tests,
but the primary comparison is end-to-end task performance.

Why this comes next:

1. the deeper oracle and sandbox already showed that the current simplified escape formulation is still not enough to prove stable goal-side exit
2. the April 20, 2026 audit stack says the strongest current preserved safe-control signal is still `strategy_authority_limited`, but the helper turn-authority / turn-profile lane is now preserved as a comparison baseline after `helper_turn_authority_contract_audit` returned `stop_and_branch` with blocking_reason=`sign_parity`, and the follow-on `manual_drive_sign_parity_audit` now points the runtime-check branch at the concrete `scripts/run_probe_odom_world_sign_chain.ps1 -CampaignId <id>` follow-on
3. the escape fixtures should be treated as hard-case evidence, not as proof that the winning architecture must expose a named recovery mode
4. a candidate can win by avoiding the bad geometry earlier, by handling it when it happens, or by safely switching away before it becomes a stall
5. serial dashboard proof should remain the trust surface while this broader alternatives portfolio competes offline and in shadow first
6. this portfolio is local to the gather-control layer; it does not replace the later onboard high-level visit-and-gather planner evaluation

Work:

1. keep one safe control:
   - preserve the helper turn-authority / turn-profile / manual-drive contract lane as the deterministic comparison baseline informed by the April 20 audit stack, not as the next direct promotion path while `sign_parity` remains the blocking reason
2. open broader alternative paths as co-equal exploration branches:
   - deterministic gather-controller branch:
     - `region_funnel_v1`: region or funnel targets that avoid brittle exact `pre_stage` points
     - explicit scripted maneuvers such as back up, arc around, and re-approach when needed
   - ROS-native local-planner branch:
     - `nav2_reacquire_v1`: direct bounded `NavigateToPose` pre-stage reacquisition before handing back to baseline staging
     - docking-style local staging / recovery
     - MPPI-style local recovery
   - learned maneuver selector branch:
     - rule-labeled maneuver-family choice in shadow mode
   - learned bounded-action backend branch:
     - small bounded local action proposals in shadow mode
   - learned switch / abstain backend branch:
     - stall detection, backend selection, or fallback gating in shadow mode
3. compare candidates through a shared gather-control adapter that can start at the current manual `pre_stage` seam, but does not require every candidate to model itself as "recovery"
4. keep every branch bounded by the same downstream safety contract:
   - deterministic translation remains authoritative
   - `gather_motion_bridge.py` remains the runtime clamp surface
   - controller and hardware caps remain authoritative
5. judge every branch on the same two-layer harness:
   - end-to-end gather score: mission pass, practical retrieval placement, phase reached, post-handoff success, time-to-place, and protected-baseline regressions
   - hard-case stress score: April 19, 2026 fixtures, nearby geometry jitter, behind-ball progress, stall duration, and whether the candidate avoids or survives the known bad geometries
   - April 19, 2026 canonical `live_plus45_short_horizon_v2_20260419` corpus
   - five representative fixtures
   - nearby geometry jitter
   - neighboring-case expansion only after a branch earns it
   - fresh shadow-sim comparison before any live consideration
6. keep the protected floors unchanged:
   - `visit_route_planning` remains the regression floor
   - the accepted one-ball baseline remains protected
   - no live promotion is unlocked by this roadmap update alone
7. avoid declaring whole categories dead from one early weak result:
   - one weak formulation is branch-specific signal
   - it is not by itself proof that the whole deterministic, ROS-native, or learned category should be retired
8. keep LLM-owned real-time gather steering out of scope while allowing shadow learned backends inside the bounded Layer 3 evaluation surface

Shared evidence contract:

1. v1 portfolio analyzer bundle:
   - `artifacts/session/<campaign_id>/gather_control_portfolio/portfolio_summary.json`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/scorecard.md`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/branch_summary.json`
2. Branch 1 hard-case stress analyzer bundle:
   - `artifacts/session/<campaign_id>/gather_control_portfolio/stress_summary.json`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/stress_scorecard.md`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/stress_summary.json`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/fixtures/<fixture_label>.json`
   - fixture evidence remains analyzer-only and feeds portfolio readiness through explicit `--stress <branch>=<stress_summary.json>` inputs; it does not change runtime control or unlock live promotion by itself
3. future per-branch shadow bundle:
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/counterfactual_replay_summary.json`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/shadow_summary.json`
4. learned-branch extras:
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/teacher_dataset_summary.json`
   - `artifacts/session/<campaign_id>/gather_control_portfolio/<branch_name>/holdout_eval_summary.json`
5. readiness rule:
   - hard-case stress evidence blocks live promotion unless every required fixture is present, complete, and passing, even when a branch is the best observed end-to-end performer

Acceptance:

1. the portfolio is evaluated as a shared comparison program rather than a single mainline plus token sidecars
2. the protected route-planning floor and one-ball baseline remain untouched while the portfolio work lands
3. no branch is considered live-promotion ready until it improves end-to-end gather behavior and survives the hard-case stress slice plus fresh shadow-sim comparison
4. the later onboard model step remains a distinct high-level planning milestone rather than being merged into this local gather-control comparison work

Current direction update:

Next major milestone: Deliver Planner-Gated Generalized Fetch-To-Pose v1, a
no-shoot, robot-owned fetch behavior where an LLM/world-state planner selects
the correct route class, Nav2 owns as much real-time robot motion as the
corrected evidence supports, and a thin fetch adapter monitors delivery
geometry, object progress, escape, stale state, and replanning triggers.
Custom contact routines and AI/model proposal layers remain fallback lanes that
earn live authority only from corrected, reproducible stage-gap evidence.

Planner-gating correction: this milestone proves the planner-to-subsystem
handoff plus the bounded local fetch skill. The planner first classifies each
scene as `fetch_ready_local`, `nav2_reposition_first`,
`scan_or_perceive_first`, `recovery_or_reaim`, or
`ambiguous_or_unsafe_no_go`. Only `fetch_ready_local` cases are handed to the
fetch subsystem and scored as local fetch evidence.

May 31, 2026 evidence reset: the delivery-marker geometry issue means prior
fetch pass/fail claims require reclassification unless the artifact proves
`geometry_consistency.pass=true`, the visible delivery marker matches
`fetch_pose_world`, and the run has same-session browser-watchable onboard plus
context video. The corrected reference run is
`artifacts/session/20260531T204154158382Z/gather_mission/20260531T204255Z/mission_verdict.json`;
the corrected visual package is
`artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`;
the corrected geometry audit is
`artifacts/session/fetch_geometry_evidence_audit_postfix_20260531/fetch_geometry_evidence_audit/scorecard.md`.
That run passed `fetch_to_pose` with matched marker geometry and truth telemetry
showing the ball reached about `0.158m` from the target center inside the
`0.300m` contract. Treat it as the first valid post-fix UAT reference. Broad
generalization still requires saved-layout repeatability and the seeded gate.

June 1, 2026 calibrated-ball provenance reset: direct `fetch_to_pose` evidence
now requires explicit model provenance in addition to marker geometry and video.
Commit `680e393 Use calibrated ball for fetch direct runs` changed direct fetch
defaults from the legacy `frisbee_target_ball.sdf` to
`calibrated_golf_ball.sdf`. Pre-boundary direct repeatability artifacts that do
not record `model_provenance_valid=true`, target model `calibrated_golf_ball`,
and marker model `golf_ball_delivery_zone_marker` are diagnostic. Rebuild the
evidence ladder from corrected direct runs: saved `zero`/`left05`/`right05`
one-run, saved `3/3`, seeded `6 x 1`, then browser-watchable visual UAT.

June 1, 2026 corrected saved-anchor one-run rebuild: the provenance and marker
path is functioning, and the current blocker is setup/contact reliability.
`right05` passed with `0.143206m` closest approach, `zero` failed on
first-contact no-object-motion, and `left05` failed on `capture_entry_timeout`.
The stage audit is
`artifacts/session/live_corrected_fetch_saved_anchor_one_run_audit_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
The next milestone step is repair setup/contact behavior before saved-layout
`3/3`, seeded gate, or guarded-live promotion.

June 1, 2026 contact-buffer handoff validation: the operator-visible stop-short
behavior was real, and the staged fix passed the `zero` one-run proof. Commit
`02a4c12 Fix Nav2 contact-buffer fetch handoff` adds the tight corridor goal
checker, the missing depth scan TF, and a monitored handoff from Nav2 to the
deterministic contact servo when the robot reaches a close/aligned
no-object-motion contact buffer. Campaign
`artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`
passed `fetch_to_pose` with `0.179959m` closest delivery distance. Nav2 handed
off at `robot_ball_distance_m=0.195671`, the servo confirmed `0.046811m` ball
motion, and the corridor push completed with `monitor_success`. The roadmap
baseline is now staged local fetch: planner-approved local case, Nav2 corridor
approach, contact-buffer monitor, deterministic first-contact servo, Nav2
corridor push, delivery monitor. The next milestone step is a broad stage-owner
comparison, then the selected targeted repair and corrected
`zero`/`left05`/`right05` one-run.

Later June 1 saved-anchor requalification refined that sequence. The planner
handoff gate
`artifacts/session/live_planner_handoff_mixed_fetch_20260601/fetch_planner_handoff_gate/gate_summary.json`
passed `5/5`. `zero` and `left05` passed one-run under the staged baseline:
`artifacts/session/live_contact_buffer_saved_anchor_zero_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
and
`artifacts/session/live_contact_buffer_saved_anchor_left05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`.
`right05` failed at `capture_entry_timeout`:
`artifacts/session/live_contact_buffer_saved_anchor_right05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`.
The audit
`artifacts/session/audit_contact_buffer_right05_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
classifies this as setup/capture. The roadmap now inserts a broad stage-owner
comparison before right-offset repair: current staged Nav2/contact-buffer
behavior, May 27 object-centric fetch, Nav2 corridor-push, corrected direct
`right05`, and prior acquisition or goal-side setup evidence. Repeatability,
seeded generalization, and guarded-live terminal correction wait for that
comparison.

The later June 1 setup/capture gap-fill probe requalified the front half of the
staged local fetch path. `scripts/fetch_setup_capture_gap_fill_probe.py`
compared current `ai_push_coast_servo_v1`, Nav2 corridor-push, and
object-centric behavior on `right05`:
`artifacts/session/live_fetch_setup_capture_gap_fill_20260601/fetch_setup_capture_gap_fill_probe/scorecard.md`.
The current staged path passed once at `0.271919m`; object-centric passed once
at `0.29623m`; Nav2 corridor-push missed terminal arrival at `0.572189m`.
The follow-on saved-anchor rebuild
`artifacts/session/live_ai_push_coast_saved_anchor_gapfill_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`
passed `zero` and `left05`, while `right05` reached capture-entry and failed
terminal arrival at `0.520765m`. The refreshed stage-quality audit
`artifacts/session/audit_ai_push_coast_gapfill_saved_anchor_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
classified the blocker as terminal arrival at that point and suggested narrow
terminal-arrival correction before the later clip review refined the priority.

Later operator clip review refined that sequence again. The
`ai_push_coast_servo_v1` guarded-live saved-anchor clips in
`artifacts/session/uat_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_visual_uat_package/scorecard.md`
and
`artifacts/session/audit_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
show one clean centerline pass and two off-axis setup/capture/handoff failures:
`left05` escapes laterally, and `right05` under-moves after unstable capture.
The roadmap sequence is now capture-geometry setup first, then saved-anchor
one-run rebuild, then terminal correction only for clean near-contract misses.
The intended algorithm is straightforward: route classification, ball-target
delivery line, capture pose behind the ball, geometry-gated setup handoff, Nav2
corridor push, delivery monitor, and bounded correction only from a clean
terminal state.

June 2 saved-anchor repeatability repair cleared the current setup/contact
blocker for the saved anchors. The corrected gate
`artifacts/session/live_fetch_setup_contact_repair_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`
passed `zero`, `left05`, and `right05` promotion `3/3` with worst closest
approaches `0.201194m`, `0.169541m`, and `0.136046m`. The stage audit
`artifacts/session/audit_fetch_setup_contact_repair_saved_anchor_3x_20260602/fetch_saved_anchor_setup_contact_audit/scorecard.md`
is `stage_quality_green=true`, with one `left05` `capture_entry_time_watch`.
The roadmap resumes seeded random generalization next; guarded-live terminal
correction follows only if reproduced random evidence shows a clean
near-contract terminal-arrival gap.

1. the first sandbox result remains a valid stop signal against another blind live controller-family tweak:
   - `artifacts/session/live_plus45_escape_sandbox_20260419/gather_escape_sandbox/sandbox_summary.json`
   - `artifacts/session/live_plus45_escape_sandbox_20260419/gather_escape_sandbox/scorecard.md`
2. the next milestone is no longer "build `short_horizon_v3`"; it is "compare multiple bounded gather-control alternatives on end-to-end task performance plus the known hard-case stress slice"
3. the project should now search more aggressively for a better bounded gather-control approach rather than assuming the next result must come from one helper-only branch or one named recovery strategy
4. `region_funnel_v1` is now a failed experimental formulation, not a portfolio candidate:
   - repair smoke `artifacts/session/live_region_funnel_v1_zero_repair_20260424/gather_goal_side_matrix/campaign_summary.json` kept fresh `zero` and `plus45` blocked at pre-stage handoff
   - do not feed `region_funnel_v1` into portfolio stress ingestion until a repaired branch first clears fresh-attempt `zero` and `plus45` pre-stage handoff
5. `nav2_reacquire_v1` is implemented but blocked as the first narrow ROS-native candidate:
   - smoke `artifacts/session/live_nav2_reacquire_v1_matrix_smoke_20260424/gather_goal_side_matrix/campaign_summary.json` kept fresh `zero` and `plus45` blocked at pre-stage handoff
   - accepted Nav2 goals timed out instead of reaching the handoff pose, so no portfolio/stress ingestion was produced
   - keep the branch available as evidence, but repair/requalify it before any promotion discussion
6. `nav2_follow_path_reacquire_v1` and `nav2_mppi_follow_path_reacquire_v1` are blocked lower-stack controller-server probes:
   - DWB FollowPath smoke `artifacts/session/live_nav2_follow_path_reacquire_v1_matrix_smoke_20260427/gather_goal_side_matrix/campaign_summary.json` accepted `/follow_path` goals but immediately aborted with `status_code=6` in fresh `zero` and `plus45`
   - MPPI matrix smoke `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_matrix_smoke_20260429_rerun/gather_goal_side_matrix/campaign_summary.json` accepted `/follow_path` goals and moved the robot with no pre-stage ball motion, but `zero`, `plus45`, and `minus45` still timed out before handoff and `backside180` tripped the path-clearance guard
   - tangent-heading `plus45` recheck `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_plus45_tangent_20260429/gather_mission_repeatability/campaign_run_summary.json` still failed with `nav2_follow_path_timeout`; at that point the next work was MPPI/controller convergence repair rather than portfolio ingestion
   - May 3 research reset `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_research_reset_20260503/research_reset_summary.json` showed the recovery commit `eafdc59` also fails saved-layout `zero`, loaded runtime MPPI params match `nav2_params_simple.yaml`, and the first near-goal critic/pruning patch worsened progress before being reverted
   - May 3 terminal-geometry repair removed the extra MPPI-only `handoff_align` waypoint while leaving MPPI params, measured handoff acceptance, capture behavior, `/odom`, and frozen contracts unchanged
   - latest live audit `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_live_audit_20260503/gather_follow_path_research_analyzer/follow_path_research_summary.json` recovered saved-layout primary pre-stage reproducibility: `zero` passed measured handoff 1/1 and then 3/3, `plus45` passed 3/3, all with `STATUS_SUCCEEDED`, `0.0m` pre-stage ball motion, and no `handoff_align` path segment
   - do not feed MPPI into portfolio/stress ingestion yet: full missions remain blocked downstream, with `zero` failing at `capture_entry_timeout` and `plus45` reaching capture-entry before first-contact/release alignment failure; the current capture-layer repair patch is offline-green only until fresh live `zero`/`plus45` repair gates pass
   - preserve MPPI as baseline evidence, not the main research path; the historical follow-on gather branch was `object_centric_gather_policy_v1`, documented in [OBJECT_CENTRIC_GATHER_POLICY_RESEARCH_PLAN.md](OBJECT_CENTRIC_GATHER_POLICY_RESEARCH_PLAN.md), and it has now been superseded by calibrated fetch-to-pose
7. `object_centric_gather_policy_v1` is historical gather/place context:
   - use Nav2/MPPI for long-range repositioning and obstacle-aware path following only
   - own ball interaction as a short-horizon object-centric manipulation policy over robot pose, ball pose, zone pose, recent robot/ball deltas, previous command, and capture/contact flags
   - start with an offline evaluator over the MPPI evidence set, then a structured object-servo baseline
   - for calibrated fetch, add a learned local handoff/maneuver proposer in
     shadow mode earlier than live learned control; execution still waits for
     deterministic guard acceptance and saved/seeded evidence
   - keep deterministic safety gates around every command or waypoint proposal
   - prohibit direct high-frequency LLM motor control, `/odom` changes, frozen-contract changes, and handoff-gate loosening
   - first live gate was saved-layout `zero` and `plus45`, one run each, no retries; future alternatives must instead requalify through the calibrated fetch gate
8. the preserved helper contract lane is still not the next promotion path:
   - `helper_turn_authority_contract_audit` returned `stop_and_branch` with blocking_reason=`sign_parity`
   - `manual_drive_sign_parity_audit` now points to the `probe_odom_world_sign_chain` runtime probe wrapper (`scripts/run_probe_odom_world_sign_chain.ps1`)
   - the refreshed April 21, 2026 provenance rerun now lands in `artifacts/session/live_plus45_probe_odom_world_sign_chain_20260421_provenance_rerun/probe_odom_world_sign_chain/odom_world_sign_chain_summary.json`
   - treat `/jetbot_base_controller/odom` as the working odom witness for this probe branch only; do not redefine the public `/odom` contract based on this rerun
   - that refreshed bundle preserves `runtime_classification.diagnosis=sign_chain_aligned` plus `source_alignment_assessment.diagnosis=source_fixture_command_sign_mismatch`
   - the bounded source-vs-fresh fixture windows still mismatch on `early_stall`, `mid_stall`, and `late_stall`, while `terminal_stall` remains the control match; see [PROBE_ODOM_WORLD_SIGN_CHAIN_CLOSEOUT_2026-04-21.md](PROBE_ODOM_WORLD_SIGN_CHAIN_CLOSEOUT_2026-04-21.md)
   - the next work is no longer another runtime sign-chain patch; it is source-artifact interpretation plus end-to-end gather-control comparison with hard-case stress tests
   - the helper turn-authority lane stays a comparison baseline rather than the next promotion path
   - focused offline verification on the current branch remains green on `tests/test_probe_odom_world_sign_chain.py -q`, `tests/test_probe_odom_world_sign_chain_source_provenance.py -q`, `tests/test_probe_odom_world_sign_chain_session_binding.py -q`, and `tests/dashboard/test_world_stream_freshness.py -k "truth_ready or make_session_id" -q`
9. calibrated golf fetch branch decisions now live in [FETCH_BRANCH_STRATEGY.md](FETCH_BRANCH_STRATEGY.md):
   - keep `physics-calibrated-golf-fetch-v1` as the stable demo/UAT integration branch
   - preserve blocked architecture branches, including `nav2_mppi_follow_path_reacquire_v1`, as evidence unless a short-lived requalification spike produces fresh `zero` and `plus45` pre-stage proof
   - use `spike/...` branches for targeted architecture revisits and `release/golf-fetch-uat-YYYYMMDD` snapshots for green demo releases
   - current calibrated comparison package: `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`
   - latest targeted MPPI revisit:
     `artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`
   - result: all three one-run calibrated layouts failed before contact with
     `pre_stage_path_clearance_guard`, so the roadmap stays with the current
     object-centric fetch baseline rather than an MPPI alternative branch
10. May 28-31, 2026 Nav2 corridor-push, evidence reset, and AI fallback:
   - next major milestone:
     Deliver Planner-Gated Generalized Fetch-To-Pose v1 with LLM/world-state
     route selection, Nav2-first execution where feasible, corrected
     geometry/video evidence, saved-layout proof, and the first seeded random
     gate inside the local fetch envelope
   - keep the runtime fetch architecture as robot-owned bounded push-and-coast,
     not intentional shooting or direct ball impulse
   - use contact-aware geometric-shooter artifacts as calibrated roll/coast
     physics probes only
   - test a physics-first Nav2 hypothesis before building the learned local
     contact controller; the May 29 evidence now answers this as useful but
     insufficient for standalone promotion
   - treat the old `nav2_mppi_follow_path_reacquire_v1` calibrated revisit as
     prior negative pre-stage evidence, not as this new corridor-push contact
     hypothesis
   - keep AI as a fallback handoff/proposal lane: train/prototype from large
     calibrated simulation batches, score in shadow mode on corrected Nav2-first
     saved anchors, seeded random layouts, and frozen failures, then allow
     learned output only to select deterministic guarded routines
   - treat V-JEPA-style world models as offboard teachers or research baselines
     for candidate-action scoring; onboard control should use a smaller
     structured or distilled `tensorrt_int8`-compatible model
   - allow LM/VLA-style models to supervise task mode, failure interpretation,
     and known maneuver choices only through deterministic contracts
   - add a planner-handoff gate before any "truly random" claim: mixed scene
     descriptors must be scored on correct routing (`fetch_ready_local`,
     `nav2_reposition_first`, `scan_or_perceive_first`, `recovery_or_reaim`,
     `ambiguous_or_unsafe_no_go`) before subsystem success is judged
   - implementation note:
     `scripts/fetch_planner_handoff_gate.py` is the first planner-handoff
     evidence surface; it can replay
     `ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json`, and
     dashboard planner-gated random runs skip local fetch unless the route is
     `fetch_ready_local`
   - keep deterministic guards authoritative over command bounds, target
     freshness, ball drift, retry budget, safe stop, `/odom`, and frozen
     contracts
   - previous spike:
     `spike/fetch-arch-nav2-corridor-push-20260528`
   - May 29, 2026 evidence update:
     `nav2_followpath_corridor_push_v1` answered the cheap contact-envelope
     question but did not promote as the sole controller. Contact-ready
     `zero`/`left05`/`right05` passed, full saved-layout one-run
     `zero`/`left05`/`right05` passed, and saved-layout `3/3` repeatability
     passed `zero` and `left05`; `right05` failed one promotion run with
     `missed_delivery_radius_after_fetch_to_pose_ball_stopped_short` after
     Nav2 returned `STATUS_SUCCEEDED` (`0.451645m` closest approach, about
     `0.121m` ball displacement)
   - seeded random/generalization was not run for Nav2 corridor-push; do not
     claim generalized behavior from saved anchors
   - dashboard random visual UAT is now profile-scoped: the green CTA uses
     `local_visual_v1` for broader bounded visual stress, while
     `corridor_contact_v1` preserves the narrow contact-ready diagnostic draw;
     neither replaces the seeded `fetch_generalization_gate`
   - May 30 scoring step:
     close `local_visual_v1` runs with
     `scripts/dashboard_random_fetch_uat_analyzer.py`; delivery passes with
     contact flags become stage-supervisor backlog/training evidence, not
     milestone promotion evidence
   - seeded evidence step:
     score `fetch_generalization_gate` output with
     `scripts/fetch_seeded_gate_evidence_analyzer.py`; non-repro random
     failures become watchlist cases, while reproduced failures must be frozen
     before tuning
   - updated next spike:
     corrected Nav2/contact-buffer requalification on the current fetch spike,
     with `spike/fetch-arch-ai-push-coast-servo-20260529` retained for fallback
     analyzers, guards, and AI shadow scoring
   - updated interpretation:
     prefer Nav2 and planner-owned reuse where the contract is clean, then use
     deterministic contact-buffer and first-contact routines for the measured
     object-outcome gap. Add broader learned proposal layers only when corrected
     saved-anchor and seeded evidence show a reproducible benefit.
11. architecture exploration should widen, but stay staged:
   - do not treat the legacy `--gather-control-family` list as exhaustive
     architecture coverage; it is a runnable control-family screen inside the
     existing mission shell
   - use [CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md](CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md)
     for the wider portfolio
   - include contact-aware geometric shooting as physics-probe evidence,
     Nav2 FollowPath corridor-push contact ownership, AI-assisted bounded
     push-coast object servo, receding-horizon contact MPC/object servo, ROS
     action-server or behavior-tree last-meter ownership, Nav2 reposition plus
     object-centric last-meter handoff, passive mechanical guide/funnel, learned
     residual or maneuver proposer, LM/VLA high-level supervision, portfolio
     switching, and perception-first target-pose fetch
   - accelerated/offline results can reject a candidate early, but canonical
     `real_time_factor=1.0` saved-layout evidence is required before promotion
   - a candidate must offer more than equal pass rate: require better margin,
     stability, simplicity, diagnosability, runtime cost, or hardware-transfer
     path before moving it beyond a spike

### Step 7: Corral Time Optimization

Goal: reduce time-to-place only after the promoted deterministic gather-control family
and multi-ball practical retrieval behavior are stable enough to trust.

Why it comes later:

1. faster push profiles are only useful once the multi-ball gather mechanic already works
2. acceleration and deceleration tuning should optimize practical retrieval, not mask a release or roll-away problem
3. multi-ball mechanics are the higher-value product milestone right now

Work:

1. add explicit acceleration and deceleration shaping to the corral approach and push phases
2. compare mission time against the multi-ball practical retrieval baseline
3. keep contained stop behavior and no-roll-away placement intact while reducing time

Acceptance:

1. mission time improves on the canonical multi-ball practical-retrieval baseline
2. placement still finishes inside the practical retrieval corral without reintroducing roll-through or roll-away
3. route-planning regression evidence remains green

### Step 8: Surface and Ball Fidelity Follow-Up

Goal: revisit simulation realism after multi-ball mechanics are in place if the
current conservative one-ball and multi-ball behavior still appears materially
different from likely field behavior.

Why this comes later:

1. the product team is willing to move forward on the practical baseline now
2. the calibration harness already exists and can be reused when realism becomes the limiting factor again
3. this keeps the current milestone focused on task completion and throughput instead of reopening the same one-ball debate

Work:

1. compare the active red ball contact model across:
   - `baseline`
   - `short_turf`
   - `short_grass`
2. use `scripts/run_corral_surface_calibration.ps1` as the repeatable comparison harness
3. decide whether `short_turf` remains the intended default or whether `short_grass` should become the promoted calibrated lane
4. rerun one-ball and multi-ball checks after any realism change

Acceptance:

1. the sim-fidelity docs clearly state what is exact, what is approximated, and what is still an inference
2. the team has a clearer answer on whether the active lane is realistic or conservative
3. route-planning and gather baselines remain green after any realism change

### Step 9: Onboard Model for Visit + Gather Planning

Goal: determine whether a local model on the Orin can take over high-level visit
and gather planning after the promoted deterministic gather-control family and the task
surface are stable enough to benchmark fairly.

Why this comes after multi-ball gather:

1. route planning alone is now too small a target; the more useful benchmark is the full visit-and-gather loop
2. gather introduces richer tradeoffs: which ball next, when to place, when to recover a lost ball, and how to sequence the corral zone efficiently
3. evaluating local models after the deterministic gather-control family and generalization evidence stabilize gives a more meaningful promotion decision

Work:

1. record decision traces from the visit-and-gather scenarios using the current GPT planner as the baseline
2. replay those traces through candidate onboard providers with `llm_provider_replay_compare.py`
3. compare validity, agreement, latency, and gather-quality metrics
4. run the best local candidate in shadow mode first, then in live sim if it holds up
5. promote the onboard planner only if it matches the safety and task-completion bar; otherwise document the gap and keep cloud planning as the baseline

Acceptance:

1. replay comparison report for candidate onboard models against visit-and-gather traces
2. shadow-lane evidence that the top local model makes comparable high-level decisions
3. live end-to-end gather proof with the promoted local planner, or a documented decision to stay cloud-backed for this milestone
