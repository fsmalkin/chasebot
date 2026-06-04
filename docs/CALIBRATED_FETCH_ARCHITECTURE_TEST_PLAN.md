# Calibrated Fetch Architecture Test Plan

This plan exists so architecture exploration does not collapse into tuning the
same control loop under different names. The active UAT baseline remains
`object_centric_fetch_policy_v1` on the calibrated golf-ball/turf lane, but the
research portfolio should deliberately test wider designs that may generalize
better, reduce telemetry fragility, or simplify eventual hardware transfer.

Next major milestone: Deliver Planner-Gated Generalized Fetch-To-Pose v1, a
no-shoot, robot-owned fetch behavior where an LLM/world-state planner selects
the route class, Nav2 owns as much real-time robot motion as the corrected
evidence supports, and a thin fetch adapter monitors corrected delivery
geometry, object progress, escape, stale state, and replanning triggers.
Custom contact routines and AI/model proposal layers remain fallback lanes that
earn live authority only from corrected, reproducible stage-gap evidence.

May 31, 2026 evidence reset: the delivery-marker geometry issue changed the
meaning of recent fetch metrics. A fetch result is architecture evidence only
when `geometry_consistency.pass=true`, the visible marker matches
`fetch_pose_world`, and same-session browser-watchable onboard plus context
video exists. Pre-fix or marker-mismatched passes are diagnostic implementation
evidence. The corrected reference package is
`artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`,
with geometry audit
`artifacts/session/fetch_geometry_evidence_audit_postfix_20260531/fetch_geometry_evidence_audit/scorecard.md`.
This reset moves the active comparison back to a corrected Nav2/LLM-first
baseline before expanding custom contact or AI control.

June 1, 2026 provenance reset: architecture evidence also requires calibrated
model provenance. Direct `fetch_to_pose` artifacts must record
`model_provenance_valid=true`, target model `calibrated_golf_ball`, target
radius `0.021336m`, and marker model `golf_ball_delivery_zone_marker`.
Commit `680e393 Use calibrated ball for fetch direct runs` is the direct-run
boundary. Older direct artifacts without explicit model provenance are
diagnostic until rerun. Use `scripts/fetch_model_provenance_audit.py` before
carrying prior direct repeatability results into a findings matrix.

June 1, 2026 contact-buffer handoff update: operator video review correctly
identified a real stop-short failure. Commit `02a4c12 Fix Nav2 contact-buffer
fetch handoff` tightens corridor-push goal checking, adds the missing depth scan
TF, and adds a monitored `contact_buffer_handoff` from Nav2 to the deterministic
first-contact servo. The one-run `zero` proof at
`artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`
passed `fetch_to_pose` with `0.179959m` closest delivery distance, Nav2 handoff
at `0.195671m` robot-ball separation, and `0.046811m` measured first-contact
ball motion. Treat this as the current staged local fetch baseline and as
one-run evidence only.

Later June 1 saved-anchor requalification: planner handoff passed `5/5`, and
the staged baseline passed `zero` plus `left05` one-run with corrected geometry
and model provenance. `right05` failed at `capture_entry_timeout`, and
`artifacts/session/audit_contact_buffer_right05_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
classifies it as a setup/capture blocker. The next evidence gate is a broad
stage-owner comparison before targeted repair. The comparison includes current
staged Nav2/contact-buffer behavior, May 27 object-centric fetch, Nav2
corridor-push, corrected direct `right05`, and prior acquisition or goal-side
setup evidence. Score by lifecycle stage before selecting a repair branch.

Later June 1 clip-review alignment: the follow-on
`ai_push_coast_servo_v1` guarded-live saved-anchor rebuild produced a clean
centerline pass and two off-axis failures:
`artifacts/session/audit_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
The videos and telemetry agree that `left05` and `right05` fail through
capture/handoff instability before terminal correction is a fair target. The
architecture contract is now the straightforward staged algorithm: compute the
ball-target delivery line, compute and reach the capture pose, gate standoff
plus lateral/yaw error, hand off a clean setup to Nav2 corridor push, then let
the monitor classify success, escape, stale state, action abort, timeout, or a
near-contract terminal miss.

May 29, 2026 update: keep the runtime architecture no-shoot. The
`nav2_followpath_corridor_push_v1` spike showed Nav2 can own useful real-time
`FollowPath` corridor tracking, but not the full contact outcome by itself.
Contact-ready `zero`/`left05`/`right05` passed, the full saved-layout one-run
matrix passed, and `3/3` repeatability passed `zero` and `left05`; `right05`
failed one promotion run because the ball stopped short after Nav2 returned
`STATUS_SUCCEEDED` (`0.451645m` closest approach against the `0.300m`
contract). This was saved-anchor evidence only, not seeded random
generalization. The next active architecture lane is a hybrid fetch stage
supervisor: Nav2 remains the stage owner for long-haul, coarse setup, and
corridor tracking when the ball stays bounded; deterministic homebrew routines
own fine pre-capture alignment, first contact, terminal re-push/coast, and
recentering; the AI/model layer starts in shadow mode as the handoff and
maneuver-class proposer. Contact-aware geometric-shooter artifacts remain
valuable physics probes, but they are not the preferred runtime architecture
until they are reframed as robot-owned bounded push/coast evidence.

The next-thread research charter lives in
[GENERALIZED_LAST_METER_FETCH_RESEARCH_GOAL.md](GENERALIZED_LAST_METER_FETCH_RESEARCH_GOAL.md).
Use it when the goal is to compare the full architecture space and return with
findings before tuning a single path.

## Coverage Rule

Treat these as different levels of evidence:

0. Evidence validity floor:
   - corrected delivery marker geometry matches `fetch_pose_world`
   - calibrated model provenance records `model_provenance_valid=true`
   - same-session browser-watchable onboard and context video exists
   - pre-fix, marker-mismatched, legacy-model, or missing-provenance results are
     labeled diagnostic
1. Control-family screen:
   - same mission shell and fetch objective, different `--gather-control-family`
     implementation
   - useful for cheap regression checks and branch resurrection decisions
   - not sufficient to claim broad architecture coverage
2. Architecture spike:
   - changes who owns the last-meter behavior, the state machine boundary, the
     prediction model, or the actuation/contact strategy
   - must keep the same calibrated ball, turf, delivery radius, saved layouts,
     no-retry rule, and approach telemetry
3. Promotion candidate:
   - passes canonical fidelity gates and shows a generalization or product
     benefit beyond matching the current baseline

Accelerated time is allowed only for screening. Any green or surprising
accelerated result must be rerun in the canonical
`yolo_test_world_v6_calibrated_golf_turf.world` lane before it counts as UAT or
branch-promotion evidence.

Current acceleration policy: the documented calibrated fast-screen world is
`yolo_test_world_v6_calibrated_golf_turf_fast.world` at
`real_time_factor=2.0` with `max_step_size=0.001`. This 2.0x lane is the normal
cheap-rejection screen. A 3.0x or 4.0x world may be created only as a
non-authoritative speed sweep after checking `/clock`, Nav2 tracking, contact
telemetry, and ball escape/success monitor behavior. Do not treat any pass above
`real_time_factor=1.0` as promotion evidence; higher-than-2.0x contact-rich
results are especially useful for finding failures, not for proving success.

Novel-layout failures are first-class evidence. The May 27, 2026 opposite-side
dashboard observation showed that a policy can pass saved centerline/off-axis
layouts while still failing when robot, target, and ball ordering changes. Use
that as a reminder that saved-layout gates measure regression stability; they
do not by themselves prove target-relative side selection or generalization.
The June 2, 2026 opposite-side rerun added a concrete regression rule: direct
`fetch_to_pose` setup must use the requested delivery pose as the active control
target, while the legacy corral zone remains reporting context. The fixed layout
`ros2_config/target_layouts/golf_ball_circle_delivery_opposite_side_01.json`
passed `1/1` after that correction:
`artifacts/session/live_fetch_opposite_side_probe_fetch_zone_fix_20260602/gather_mission_repeatability/campaign_run_summary.json`.
This expands direct subsystem coverage; planner-gated broad UAT still requires
an executable `nav2_reposition_first` handoff path.

Planner handoff is a separate evidence layer. Random scenes that are outside the
local fetch envelope should not be handed directly to `fetch_to_pose` and scored
as subsystem failures. The planner layer must first classify each scene as one
of: `fetch_ready_local`, `nav2_reposition_first`, `scan_or_perceive_first`,
`recovery_or_reaim`, or `ambiguous_or_unsafe_no_go`. A local fetch failure is
only subsystem evidence after a correct `fetch_ready_local` handoff. A correct
abstain, scan, reposition, or no-go on an out-of-envelope scene is planner
success, not missing fetch capability.

## Architecture Portfolio

| Family | Why test it | First evidence gate | Promotion question |
| --- | --- | --- | --- |
| Corrected Nav2/LLM-first staged fetch baseline | Tests the simplest reusable architecture after the geometry reset: planner route selection, explicit ball-path/capture setup, Nav2-first execution, and a thin geometry monitor/adapter | Capture-geometry one-run rebuild on corrected saved-layout `zero`/`left05`/`right05` with same-session video | How much of fetch stays inside planner, capture-geometry, and Nav2-owned subsystem behavior before custom contact code is justified? |
| Nav2 contact-buffer handoff baseline | Keeps Nav2 in the stages it can own while giving first contact to a bounded deterministic servo after a monitored close/aligned stop | Prior `zero` and `left05` one-runs are green; latest off-axis clips show setup/capture instability; next gate is capture-geometry repair | Does explicit capture setup remove off-axis churn without adding broad custom control or hiding setup/capture failures? |
| Current object-centric fetch baseline | Known implementation and reference telemetry; corrected rerun required for post-reset claims | Rerun against the May 31 evidence floor | Does any new design beat its margin, stability, or simplicity under corrected metrics? |
| Runnable legacy control-family screen | Checks whether old branches become viable under calibrated physics | `scripts/calibrated_fetch_architecture_revisit.py --screen-scope runnable_control_family_screen --fast-screen --short-circuit-on-failure` | Did any old implementation clear `zero` cheaply enough to justify canonical rerun? |
| Contact-aware geometric shooter | Physics-probe evidence for roll windows, delivery margins, and feasible coast geometry; not the preferred runtime path | Offline shot-model replay or direct-velocity probe only | Does it teach useful push/coast targets without becoming non-robot-owned control? |
| Nav2 FollowPath corridor-push | Tests whether calibrated physics keeps the ball inside Nav2's natural real-time path-tracking envelope | Completed contact-ready and saved-layout one-run gates; failed `right05` saved-layout `3/3` promotion short of delivery | Use as corridor-tracking baseline and data source, not as standalone promotion candidate. |
| Hybrid fetch stage supervisor with AI handoff/proposal | Keeps Nav2 as owner where corrected evidence shows it works, then uses deterministic contact routines and shadow AI for proven object-outcome gaps | Shadow prediction/proposal over corrected Nav2-first failure traces, saved anchors, and seeded-random layouts, then guarded canonical `zero` one-run | Does the supervisor choose better stage handoffs and terminal correction while preserving guard acceptance and Nav2 margins? |
| Receding-horizon contact MPC/object servo | Owns robot-ball-target state and optimizes bounded commands directly | Fast screen on `zero`, then canonical `zero`/`left05`/`right05` one-run | Does it avoid lateral knock-away while recovering from small offsets? |
| ROS action-server or behavior-tree last-meter owner | Moves setup, contact, re-aim, abort, and telemetry out of ad hoc mission-loop phases | Dry-run/action-contract test, then canonical one-run `zero` | Does explicit ownership make failures easier to classify and recover? |
| Nav2 reposition plus object-centric last meter | Uses Nav2 for long-range approach only, with a clean handoff to object-centric contact | Pre-contact approach telemetry and handoff dwell on varied starts | Does it generalize to farther starts without contaminating contact control? |
| Passive mechanical guide/funnel | Tests whether a wider physical interaction envelope is simpler than software-only precision | Sim model smoke plus calibrated `zero`/off-axis one-run | Does it improve robustness without hiding unstable approach telemetry? |
| Learned residual or maneuver proposer | Learns residual corrections or proposes setup pocket, handoff, push duration, coast timing, and recovery side behind deterministic gates | Offline replay/shadow evaluation before live control | Does it add measurable margin while abstaining on out-of-distribution states? |
| LM/VLA high-level supervisor | Uses language or robot-foundation-model reasoning for task mode, failure interpretation, and maneuver choice without owning fast control | Contract/dry-run prompt replay over frozen state digests | Does it improve recover/give-up decisions while leaving local contact to guarded controllers? |
| Planner-gated fetch handoff | Tests whether the LLM/world-state planner recognizes when local fetch is applicable versus when to scan, reposition, recover, or no-go | `scripts/fetch_planner_handoff_gate.py --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json` | Does it avoid dispatching local fetch outside its envelope while still choosing fetch on valid local cases? |
| Portfolio supervisor/switcher | Chooses push, coast, re-aim, hold, or give-up from measured uncertainty | Offline counterfactual replay, then live A/B on hard layouts | Does switching reduce tail failures without adding opaque behavior? |
| Perception-first target-pose fetch | Replaces truth-state assumptions with sensed ball/target pose once pose delivery is stable | Shadow perception parity against truth-state UAT traces | Does it preserve success when truth-state shortcuts are removed? |

June 3 route-owner UAT update: planner-gated fetch handoff now has a corrected
fresh-session replay harness. The seed `20260608` six-scene analyzer passed two
`fetch_ready_local`, two `nav2_reposition_first`, and two `recovery_or_reaim`
layouts with same-session browser-watchable packages:
`artifacts/session/route_uat_seed20260608_six_fresh_sessions_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
Use this as broad visual UAT and route-owner evidence. Promotion still requires
the canonical saved-layout and seeded-random gates, because all six runs carry
contact-quality watches around pre-contact lateral/yaw posture.

June 3 route-quality scorer update: planner-gated fetch handoff now emits a
route-quality score and first-contact risk before execution, and the route UAT
analyzer preserves predicted-vs-actual contact quality. The roughest live
executable replay from seed `20260613` passed `3/3` across recovery, Nav2
reposition, and fetch-ready route owners:
`artifacts/session/live_route_quality_roughest_fresh_replay_20260603/fetch_planner_route_replay_batch/scorecard.md`.
The analyzer
`artifacts/session/route_uat_route_quality_roughest_live_20260603/fetch_planner_route_uat_analyzer/scorecard.md`
classifies the result as visual UAT green with `promotion_evidence=false`.
Treat the high-risk recovery case as the next contact-smoothing target; treat
the clean-first-contact Nav2 run as supporting evidence for Nav2 setup
ownership inside the broader planner-routed architecture.

June 4 readyfix evidence strengthens the planner-gated candidate. Planner child
`live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_planner`
passed `30/30`; mission replay
`live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_replay`
passed `6/6` and included a Nav2-first abort that left the ball unmoved before
bounded local recovery delivered at `0.197m`. Browser-visual replay
`live_planner_seeded_generalization_gate_visual_recheck_20260604` passed `4/4`
with same-session browser-watchable packages and reviewed keyframe sheets.
Classify this as route-owner UAT green. The canonical parent seeded gate still
owns promotion evidence.

June 4 seed `20260629` boundary repairs: the planner child passed `30/30` with
`0` wrong fetch-ready dispatches, then the first live `nav2_reposition_first`
row aborted before fetch with no first-contact trace. The clean abort moved the
ball `0.0m`, so it classifies as a setup-owner resilience gap. The fallback gate
now admits otherwise-safe clean pre-contact Nav2 aborts out to `1.300m`
robot-ball separation while preserving ball-motion, lateral, yaw, and
ball-target bounds. The exact row passed in
`live_seed20260629_scene01_nav2_abort_fallback_repro_20260604`, with closest
approach `0.195562m`, clean first-contact flags, stable contact approach, and
browser-watchable visual proof. The resumed parent gate then exposed
`seed20260629_scene05_recovery_or_reaim`: high setup debt consumed about a
minute before first contact, leaving too little push time. The longer bounded
recovery window repaired that row while preserving delivery-stop behavior. The
final parent gate
`artifacts/session/live_planner_seeded_generalization_gate_seed20260629_boundary_repair_full_visual_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`
is promotion-green with `30/30` planner routing, `6/6` live missions, `6/6`
visual packages, clean analyzer status, and `0` first-contact blockers.

June 4 mixed-family route-owner evidence now covers two rough seeds. Seed
`20260633` and seed `20260632` each passed the two-live-samples-per-route UAT
surface across `fetch_ready_local`, `nav2_reposition_first`,
`recovery_or_reaim`, `scan_or_perceive_first`, and
`ambiguous_or_unsafe_no_go`. The latest analyzer is
`artifacts/session/analysis_mixed_route_family_2per_route_seed20260632_20260604/fetch_planner_route_uat_analyzer/scorecard.md`:
route contracts `10/10`, visual packages `10/10`, executable deliveries `6/6`,
route-only proofs `4/4`, clean analyzer status, and first-contact blockers
`0`. Treat this as route-family visual UAT. The next gate should deliberately
stress hard geometry and planner refusal boundaries before additional contact
controller work.

June 4 hard mixed-scenario route-owner evidence now closes that next gate.
`hard_mixed_fetch_planner_v1` is the named two-per-route pressure matrix for
wide-angle local fetch, opposite-side Nav2-first setup, large-angle
recovery/re-aim, scan/defer, and safe no-go. The live replay analyzer is
`artifacts/session/analysis_hard_mixed_route_family_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
It passed route contracts `10/10`, visual packages `10/10`, executable
deliveries `6/6`, route-only proofs `4/4`, clean analyzer status, and
first-contact blockers `0`, with executable closest approaches in
`0.194m..0.197m`. Treat this as hard route-family visual UAT and architecture
support. Promotion still requires the canonical saved-layout and seeded-gate
ladder for any changed executor.

June 4 LLM-shadow hard-matrix evidence adds high-level planner support:
`artifacts/session/shadow_llm_hard_mixed_fetch_planner_v1_20260604/fetch_planner_handoff_gate/scorecard.md`.
The real provider matched the deterministic guard `10/10`, provider status was
`ok` on all ten rows, wrong fetch-ready dispatches were `0`, and
`llm_shadow_ready=True`. Treat this as shadow-only route-selection evidence.
The next calibrated architecture work repeats shadow comparison on rough mixed
seeds and the seven-seed manifest while hardware-transfer packaging starts.

The first rough-seed LLM-shadow rollup is green:
`artifacts/session/analysis_llm_shadow_hard_plus_rough_mixed_20260604/fetch_planner_llm_shadow_evidence/scorecard.md`.
It aggregates the hard matrix and rough mixed seeds `20260632` / `20260633`,
with `70/70` provider-ok classifications, `70/70` guard agreement, route
pass/fail `70/0`, and wrong fetch-ready dispatches `0`. The remaining
calibrated planner work is seven-seed shadow expansion plus hardware-transfer
packaging.

The full hard-plus-seven-seed LLM-shadow manifest is green at
`artifacts/session/analysis_llm_shadow_hard_plus_seven_seed_manifest_20260604/fetch_planner_llm_shadow_evidence/scorecard.md`.
It covers eight gates and `220` total scenes, with provider `ok` on `220/220`,
guard agreement `220/220`, route pass/fail `220/0`, and wrong fetch-ready
dispatches `0`. Seed `20260630` required a longer-timeout rerun after one
transient provider read timeout. Treat this as shadow route-selection evidence;
live authority still requires a supervised threshold and fallback policy.

## Research Thread Output

Before starting another implementation spike, produce a findings matrix across
the full portfolio. Each row should state ownership boundary, expected
generalization benefit, first honest rejection gate, robot-owned evidence gap,
hardware-transfer risk, diagnosability, likely failure classes, and recommended
status: immediate, fallback/later, or no-go.

The recommended path should include one focused spike branch and one fallback
sequence. Runnable experiments stay on spike branches; high-level decisions and
branch strategy changes are propagated back to `main`.

## Gate Ladder

1. Desk check:
   - define the ownership boundary and why this is not merely parameter tuning
   - state expected benefit: margin, speed, robustness, simplicity, hardware
     transfer, data collection, or diagnosability
   - list new failure modes and safety guards
   - state whether the candidate is planner-owned, Nav2-owned, monitor-only,
     custom deterministic control, or learned proposal
2. Offline or accelerated screen:
   - use recorded traces, dry-run contract tests, or the 2.0x calibrated fast
     world for cheap negatives
   - keep 2.0x as the default accelerated lane; label 3.0x/4.0x runs as
     experimental speed sweeps if used
   - accept accelerated failures as screening evidence
   - never accept accelerated passes as UAT evidence
   - for AI-assisted lanes, run shadow prediction/proposal first: compare the
     learned model's predicted trajectory, miss vector, and proposed maneuver
     against measured outcomes without allowing execution
3. Evidence validity check:
   - require `geometry_consistency.pass=true`
   - require the visible delivery marker to match `fetch_pose_world`
   - require same-session browser-watchable onboard and context videos for UAT
   - classify old marker-mismatched passes as diagnostic
4. Planner-handoff gate:
   - score mixed scenes before local fetch dispatch
   - require correct routing across `fetch_ready_local`,
     `nav2_reposition_first`, `scan_or_perceive_first`, `recovery_or_reaim`,
     and `ambiguous_or_unsafe_no_go`
   - dispatch local fetch only for planner-approved `fetch_ready_local` cases
5. Canonical one-run probe:
   - `zero`, no retries, `0.300m` delivery radius, canonical calibrated world
   - require `mission_completed_pass=true`, `fetch_to_pose_pass=true`, and
     corrected delivery marker geometry
6. Canonical saved-layout matrix:
   - `zero`, `left05`, `right05`, one run each, no retries
   - compare closest-approach margin, first-contact alignment, yaw sign changes,
     lateral knock-away, and runtime/failure clarity against the corrected
     post-fix baseline
7. Repeatability promotion:
   - `zero`, `left05`, and `right05` `3/3` each
   - every run must pass mission and fetch gates
   - any candidate with only equal pass rate must still justify itself through
     better margin, simpler architecture, lower latency, cleaner telemetry, or
     better transfer path
8. Generalization suite:
   - wider lateral offsets, farther starts, start yaw variation, target-distance
     variation, opposite-side target-relative starts, and at least one
     secondary surface check
   - first harness: `scripts/fetch_generalization_gate.py`
   - keep this suite inside the local fetch envelope; out-of-envelope random
     scenes belong in the planner-handoff gate instead
   - include hard-case layouts only after the candidate clears the saved-layout
     gate, so hard cases do not distract from primary repeatability
   - run seeded random samples after deterministic anchors are green; any
     reproducible failure seed becomes a named saved layout before branch-level
     tuning
   - compare randomized failures by failure class and geometry, not just pass
     rate, so a single novel case can reveal a missing ownership boundary
   - the first no-shoot comparison set should include the current
     object-centric baseline and any AI-assisted push/coast shadow candidate;
     geometric-shooter probes may be cited as physics evidence, but should not
     be treated as the runtime comparison baseline
9. Promotion package:
   - include saved-layout repeatability, at least one seeded-random
     generalization set, and an explicit explanation of any observed
     novel-layout failure or recovery behavior
   - include planner-handoff evidence before making claims about major unknowns
     or truly random scenes
   - include model-card style notes for learned components: training data
     distribution, holdout geometry, abstention/guard rate, runtime latency, and
     TensorRT INT8 deployment plan

## Branching

- Keep `physics-calibrated-golf-fetch-v1` as the UAT integration branch.
- Put shared harnesses, analyzers, and docs there after review.
- Use `spike/fetch-arch-<family>-YYYYMMDD` for a single architecture hypothesis.
- The completed Nav2 corridor-push spike remains
  `spike/fetch-arch-nav2-corridor-push-20260528`; do not tune it as a standalone
  contact-promotion candidate after the `right05` stop-short promotion failure.
- The immediate requalification target is corrected Nav2/LLM-first evidence:
  planner-approved local fetch cases, Nav2-first execution where feasible, and
  same-session video plus corrected geometry. Keep
  `spike/fetch-arch-ai-push-coast-servo-20260529` for fallback analyzers,
  guards, shadow scoring, and narrow guarded-live routines.
- Keep the AI-assisted lane shadow-first: learned outputs may select a handoff
  or guarded maneuver class only after saved-anchor and seeded-random shadow
  scoring is green and deterministic guards accept the class.
- Promote to `candidate/fetch-arch-<family>` only after the canonical saved-layout
  matrix is green and the benefit is written down.
- Do not resurrect blocked gather-control branches in place. If an old idea is
  worth retesting, wrap it as a new architecture spike with a fresh hypothesis.

## Current Evidence Notes

- Contact-aware geometric shooter offline screen:
  `artifacts/session/live_fetch_geometric_shooter_screen_20260527/fetch_geometric_shooter_screen/geometric_shooter_summary.json`.
  It read the May 27 calibrated gate traces across CTA centerline and policy
  `centerline`/`left05`/`right05`, found `12/12` offline model passes, no
  missing trace inputs, max required delivery-entry speed `0.626061m/s`, max
  target-center stop speed `0.907718m/s`, and minimum aim half-angle
  `31.621299deg`. This is `offline_only_not_uat`; after the no-shoot pivot,
  treat it as roll-window and coast-geometry evidence rather than the primary
  runtime architecture.
- Contact-aware geometric shooter canonical `zero` probe:
  `artifacts/session/live_fetch_geometric_shooter_probe_zero_20260527/fetch_geometric_shooter_probe/geometric_shooter_probe_summary.json`.
  The bounded direct-velocity shot impulse passed one canonical calibrated
  `zero` run with no retries: initial speed `0.90598m/s`, heading `0.0deg`,
  `fetch_to_pose_pass=true`, closest/final distance `0.011837m`, and 65 ball
  trace samples. This advances the spike to a saved-layout
  `zero`/`left05`/`right05` one-run matrix, but it is still probe evidence, not
  repeatability, robot-owned contact, or promotion evidence.
- Contact-aware geometric shooter saved-layout one-run matrix:
  `zero`, `left05`, and `right05` each passed one bounded direct-velocity probe:
  `live_fetch_geometric_shooter_probe_zero_20260527`,
  `live_fetch_geometric_shooter_probe_left05_20260527`, and
  `live_fetch_geometric_shooter_probe_right05_20260527`. Closest/final
  distances were `0.011837m`, `0.011898m`, and `0.011898m` respectively. This
  validates the calibrated roll model enough to inform bounded push/coast
  targets, but still does not prove a robot-owned contact policy or promotion
  readiness.
- AI-assisted hybrid stage-supervisor direction:
  no live model evidence exists yet. The first honest gate is a shadow-mode
  handoff/maneuver proposer over the saved anchors plus seeded random layouts
  emitted by `scripts/fetch_generalization_gate.py`, followed by a canonical
  `zero` robot-owned run only after deterministic guards accept the proposed
  maneuver class. V-JEPA-style world models may inform offboard teacher labels
  or candidate-action scoring, but onboard inference should be a smaller
  structured or distilled model compatible with `tensorrt_int8`.
- MPPI FollowPath calibrated revisit:
  `artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`.
  It failed `zero`, `left05`, and `right05` before contact and remains
  evidence-only. This is not the new `nav2_followpath_corridor_push_v1`
  hypothesis, which starts from a fresh corridor-push contact test.
- Nav2 corridor-push evidence:
  `artifacts/session/live_nav2_corridor_push_contact_ready_rerun3_20260529/calibrated_fetch_architecture_revisit/scorecard.md`
  passed contact-ready `zero`, `left05`, and `right05`.
  `artifacts/session/live_nav2_corridor_push_full_saved_layout_20260529/calibrated_fetch_architecture_revisit/scorecard.md`
  passed full saved-layout `zero`/`left05`/`right05` one-run, then failed
  saved-layout repeatability because `right05` promotion run 1 stopped short:
  `missed_delivery_radius_after_fetch_to_pose_ball_stopped_short`,
  `STATUS_SUCCEEDED`, `0.451645m` closest approach, and about `0.121m` ball
  displacement. Treat this as evidence that Nav2 can keep the ball bounded but
  cannot be promoted as the sole contact owner.
- Corrected May 31 geometry/video reference:
  `artifacts/session/20260531T204154158382Z/gather_mission/20260531T204255Z/mission_verdict.json`
  passed saved `zero` with `fetch_to_pose_pass=true`,
  `geometry_consistency.pass=true`, marker center `(0.95, 0.0)`, marker radius
  `0.300m`, and truth telemetry showing the ball reached about `0.158m` from
  target center. The package
  `artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`
  confirms browser-watchable onboard, topdown, and world-stream video. Treat
  this as the post-fix UAT reference for the metric path and as the starting
  point for corrected saved-layout requalification.
- Push-readiness gate requalification:
  `artifacts/session/live_push_readiness_gate_saved_anchor_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`
  failed saved-anchor `zero`, `left05`, and `right05` one-run requalification.
  The corrected audit
  `artifacts/session/audit_push_readiness_gate_saved_anchor_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
  reports `0` guarded-live terminal candidates. `zero` and `right05` failed
  before Nav2 dispatch on measured push-readiness; `left05` passed readiness
  and then failed during corridor push. Treat this as setup/contact evidence
  that pauses terminal correction and routes the next work to setup/reacquire.
- Seeded random/generalization status:
  not yet run for Nav2 corridor-push. Do not claim generalized behavior until
  the next candidate clears saved-anchor repeatability and then runs
  `scripts/fetch_generalization_gate.py`.
- A partial accelerated control-family screen on May 27, 2026 produced
  `artifacts/session/live_calibrated_fetch_architecture_revisit_legacy_fast_short_screen_20260527_region-funnel_zero_one_run/gather_mission_repeatability/campaign_run_summary.json`.
  `region_funnel_v1` failed `zero` after pre-stage handoff because the ball
  stopped short of the delivery radius. Treat this as screening-only context,
  not a completed architecture matrix.
