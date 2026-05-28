# Object-Centric Fetch Policy Plan

## Status

This is the active research direction after the object-centric gather/place
pivot. The May 2026 direction is now physics-first: treat the earlier
launch/roll behavior as a hypothesis until the ball and surface model pass
calibrated roll and contact-rich UAT gates. The near-term target is a
small-robot golf-ball `fetch_to_pose` demo into a visible delivery circle;
`fetch_to_person` comes later after target pose delivery is repeatable and
instrumented.

Latest physics status: Live Gate 0 is green on May 26, 2026. The production
`calibrated_golf_ball.sdf` now carries a built Gazebo rolling-resistance system
with `linear_decel_mps2=0.72`; a 3-run direct-velocity passive roll gate stopped
at `0.679778m` from a configured `1.0m/s` launch in all runs, inside the
`0.45-0.90m` calibrated turf band.

The previous gather/place objective remains useful as negative baseline
evidence, but success is no longer final stop in the corral. Success is
trajectory intersection with a delivery radius around the requested target pose.

Latest green UAT:

- Dashboard scenario: `golf_ball_circle_delivery_uat`
- World: `yolo_test_world_v6_calibrated_golf_turf.world`
- Ball model: `ros2_config/calibrated_golf_ball.sdf`
- Delivery marker: `ros2_config/golf_ball_delivery_zone_marker.sdf`
- Latest evidence branch/input commit:
  `physics-calibrated-golf-fetch-v1` / `904c265`
- Dashboard session:
  `artifacts/session/20260526T175235537805Z/golf_ball_circle_delivery/20260526T175246191783Z`
- Verdict: `mission_completed_pass=true`, `fetch_to_pose_pass=true`,
  `fetch_to_pose_pass_count=1`, `fetch_to_pose_fail_count=0`
- Closest approach: `0.183896m` inside a `0.300m` delivery radius
- Approach telemetry: `stable_contact_approach_pass=true`,
  `robot_yaw_error_sign_changes_pre_contact=0`,
  `max_abs_robot_lateral_error_pre_contact_m=0.0`,
  `max_abs_robot_yaw_error_pre_contact_deg=0.000003`
- Direct demo repeatability: `3/3` pass under
  `artifacts/session/20260526T175235537805Z/golf_ball_circle_delivery_checkpoint_repeatability`,
  with worst closest approach `0.167477m` and stable approach in all runs.
- Actual object-centric policy clean-start probes: `2/2` pass at
  `artifacts/session/20260526T180015557889Z/gather_mission_calibrated_golf_policy_probe/20260526T180039Z`
  and
  `artifacts/session/20260526T180402943809Z/gather_mission_calibrated_golf_policy_probe/20260526T180439Z`.
  The second probe was borderline at `0.298832m` inside the `0.300m`
  delivery radius, so the next move is pressure testing rather than path
  redesign.
- Off-axis smoke: `live_calibrated_golf_fetch_off_axis_smoke_20260527`
  passed `left05` and `right05` one-run policy probes with no retries. The
  `left05` closest approach was `0.270262m`; the `right05` closest approach was
  `0.299554m`, so off-axis behavior is green but still near the threshold on
  the right side.
- Formal centerline repeatability:
  `live_calibrated_golf_fetch_centerline_repeatability_rerun_20260527`
  passed both gates. The dashboard CTA passed `3/3` with worst closest approach
  `0.194764m`; the actual object-centric policy passed `3/3` with worst closest
  approach `0.292869m` and max first-contact push alignment `0.835258deg`.
- Demo-readiness saved-layout gate:
  `live_calibrated_golf_fetch_uat_readiness_rerun_20260527` passed all four
  sub-gates with no retries and a `0.300m` delivery radius. The dashboard CTA
  centerline passed `3/3` with worst closest approach `0.235981m`. The actual
  object-centric policy passed saved-layout `zero` `3/3` with worst closest
  approach `0.280497m`, `left05` `3/3` with worst closest approach `0.287996m`,
  and `right05` `3/3` with worst closest approach `0.293705m`. Every run has
  `mission_completed_pass=true` and `fetch_to_pose_pass=true`.
- Approach readout for the demo-readiness gate: every policy run has
  `fresh_attempt_approach.pass=true`, `approach_side_pass=true`, no
  `approach_failure_reason`, no goal-side entry before capture, and no
  pre-contact yaw-error sign changes in the sampled state histories. Off-axis
  final ball lateral magnitude moved toward the target line on all six runs,
  so there is no lateral knock-away evidence. The tightest margin remains
  `right05` run 2 at `0.293705m`; centerline run 2 also showed a larger
  `first_contact_push_alignment_deg=12.826061` while still passing, so treat
  first-contact alignment as a watch item rather than a reason for a policy
  change on this green gate.
- Opposite-side dashboard observation, May 27, 2026: placing robot and ball on
  opposite sides of the delivery target produced qualitatively different
  behavior from the saved centerline/off-axis gates. The robot could get near
  the ball, but then turned into a side knock-away / overshoot instead of
  owning the ball-target line. Treat this as a generalization failure signal,
  not as a reason to discard the calibrated physics lane. The lesson is that
  saved-layout success currently proves the known geometry; it does not yet
  prove target-relative side selection, pre-contact reorientation, or bounded
  first-contact energy across novel layouts.

## Architecture Revisit Conclusion

Preserve the calibrated golf-ball/turf lane and object-centric fetch architecture
as the UAT baseline. The May 27, 2026 demo-readiness gate is the current
comparison package:
`artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`.

This is not a broad pivot away from object-centric fetch. Alternative
architectures may be evaluated only through a targeted calibrated
`fetch_to_pose` requalification gate that keeps the same ball model, turf world,
delivery radius, saved layouts, no-retry policy runs, approach telemetry, and
deterministic guards. The requalification must compare directly against the May
27 gate and explain any regression in closest approach, first-contact alignment,
or lateral/goal-side behavior.

Historical pre-stage-only branches remain blocked and out of portfolio/stress
promotion unless they produce fresh calibrated fetch-to-pose evidence. MPPI
FollowPath is classified separately: May 3 terminal-geometry evidence recovered
primary pre-stage handoff, but downstream capture/contact behavior remained
contaminated, so it is retained as baseline evidence rather than a fetch
architecture candidate.

Latest architecture-revisit spike:
`artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`.
The spike reran `nav2_mppi_follow_path_reacquire_v1` as a setup/pre-stage
candidate under the calibrated golf-ball `fetch_to_pose` objective on saved
layouts `zero`, `left05`, and `right05`, one run each, no retries. All three
failed before contact with `nav2_follow_path_path_clearance_guard` /
`pre_stage_pose_not_reached`; no `shot_outcome.closest_approach_distance_m` was
produced. Recommendation: do not develop this alternative for calibrated fetch.

Important scope correction: the MPPI revisit and the runnable legacy
`--gather-control-family` screens are control-family evidence inside the current
mission shell. They do not exhaust the broader architecture space. The wider
architecture portfolio and gate ladder now live in
[CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md](CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md).
That plan explicitly separates control variants from architecture spikes and
adds coverage for contact-aware geometric shooting, receding-horizon contact
MPC/object servo, ROS action-server or behavior-tree last-meter ownership,
Nav2-reposition/object-centric last-meter hybrids, passive mechanical guides,
learned residuals or maneuver proposers, portfolio switching, and
perception-first target-pose fetch.

Next architecture exploration should be wide but staged:

1. keep the May 27 object-centric fetch gate as the comparison baseline
2. use accelerated/offline screens only for cheap negative evidence
3. rerun any green or surprising screen in the canonical `real_time_factor=1.0`
   calibrated golf turf world before counting it
4. promote a new branch only if it passes the saved-layout `zero`, `left05`,
   and `right05` gates and provides a clear benefit in margin, stability,
   simplicity, diagnosability, runtime cost, or hardware-transfer path

## Current Control Pivot

The next fetch-control work remains approach-stability and recovery first, not
harder contact tuning. The May 27 gate added enough approach telemetry to keep
lateral knock-away, pre-contact oscillation, and first-contact alignment as
explicit watch items before any policy or architecture change.

Current goal: build a generalized object-centric `fetch_to_pose` policy that
can start from either side of the target, choose the correct side of the ball,
settle onto the ball-target line, make low-yaw/low-lateral-error first contact,
and bound the ball trajectory so it intersects the delivery circle without a
side knock-away or uncontrolled overshoot. This is the goal to pursue before
user/person targeting or broad Nav2/MPPI contact work.

Control order:

1. Stabilize the pre-contact approach on the ball-target line.
2. Make first contact with low lateral error and low yaw error.
3. Keep pushing toward the target while applying bounded directional correction.
4. Use a wider attachment/funnel as an allowed mechanical robustness path, but
   do not let width hide unstable approach telemetry.

Approach-quality evidence must record:

- per-tick robot pose/yaw and ball pose
- signed robot lateral error to the ball-target line
- robot yaw error to the intended push line
- yaw-error sign changes before first contact
- first-contact pose, lateral error, yaw error, and ball displacement
- ball lateral displacement and contact trajectory angle after first contact

Promotion rule: a run can pass the delivery circle and still be classified as
control-quality suspect when approach telemetry shows lateral knock-away,
pre-contact oscillation, or high first-contact yaw/lateral error.

## Experiment Policy

Use deterministic and randomized experiments for different jobs:

1. Saved layouts are regression anchors. Keep `zero`, `left05`, and `right05`
   as the first comparison gate for every policy or architecture branch because
   they make margins, traces, and regressions comparable across time.
2. Novel and randomized layouts are brittleness discovery. After a candidate is
   green on the saved layouts, sample target-relative start side, robot yaw,
   lateral offset, ball-target distance, and modest surface variation. Freeze
   any reproduced failure seed into a named saved layout before tuning against
   it.
3. Rerun selectively, not blindly. Rerun when the scenario class changes, when
   physics or contact code changes, when an accelerated/offline result is green
   or surprising, or before promotion. Do not rerun every obsolete blocked
   branch unless it has a fresh hypothesis and a calibrated fetch gate.
4. Count only canonical evidence for promotion. Offline, accelerated, and
   dashboard-observation results can direct the next experiment, but promotion
   evidence must come from the canonical calibrated world with fresh runtime
   traces and the same no-retry delivery-radius contract.

## Trajectory Limiter Direction

Avoid actuated ball-handling hardware until the software/contact lane has been
exhausted. The first limiter should be a measured-state policy envelope, not a
target-seeking trick:

- pre-contact gate: do not enter push mode unless robot lateral error, yaw error,
  and yaw-error sign changes are inside thresholds
- energy gate: cap push speed, push duration, and angular command; release/coast
  as soon as the measured ball trajectory is projected to intersect the delivery
  circle
- corridor guard: define a ball-target-line corridor and stop forward pushing if
  the ball exits it; recover by re-aiming instead of chasing laterally while in
  contact
- escape guard: if ball speed, lateral displacement, or predicted miss exceeds
  bounds, cut contact effort and classify the run before tuning

This keeps the ball from escaping by limiting injected energy and lateral error
at the contact layer. Passive fixed geometry, such as a wider non-actuated guide
or funnel, remains an allowed robustness option, but promotion evidence must
still show stable approach telemetry without relying on hidden mechanical rescue.

## Thesis

Use long-range navigation only to set up the robot and ball. The object-centric
fetch policy owns short-horizon ball interaction as bounded
setup-contact-observe-recover cycles:

1. `setup`: reach a measured contact pocket behind the ball for the requested
   target pose.
2. `contact`: apply a bounded command sequence intended to roll the ball through
   the delivery radius.
3. `observe`: track ball trajectory, speed decay, target intersection, and miss
   vector.
4. `recover`: re-aim from the new ball state when budgets allow.
5. `done`: accept once the ball trajectory intersects the delivery radius.
6. `give_up`: stop with an explicit failure reason when budgets are exhausted.

The first policy family is:

`object_centric_fetch_policy_v1`

It may emit bounded `linear_x` / `angular_z` commands, short relative waypoints,
or contact profiles, but every proposal must pass deterministic guards before
execution.

## Success Definition

Primary success for `fetch_to_pose`:

- the ball trajectory intersects a configurable delivery radius around the
  target pose
- intersection is measured from fresh runtime state, not inferred from command
  intent
- the run records approach, contact, and post-contact ball state at enough
  resolution to replay the shot

Secondary metrics:

- closest approach distance to target pose
- first intersection timestamp
- ball speed at intersection
- final rest distance from target
- number of setup/contact/recover cycles
- give-up reason, when not successful

`fetch_to_person` is intentionally deferred. User detection should later produce
the same target-pose contract plus confidence and freshness metadata; it should
not change the fetch policy's core success metric.

## Baselines

Keep these as evidence branches, not active promotion targets:

- `nav2_mppi_follow_path_reacquire_v1`: recovered pre-stage / downstream
  contact-contaminated baseline evidence. The May 3 terminal-geometry package
  recovered saved-layout `zero` and `plus45` pre-stage handoff, while full
  missions still failed downstream around capture-entry, first contact, or
  release:
  `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_live_audit_20260503/gather_follow_path_research_analyzer/follow_path_research_summary.json`.
- April pre-stage-only experimental branches remain blocked unless refreshed
  through the calibrated fetch-to-pose gate; do not reuse old pre-stage smokes
  as architecture evidence.
- `object_centric_gather_policy_v1`: frozen gather/place concept superseded by
  fetch-to-pose.

Fetch evidence should compare against:

- no-contact / setup-only runs
- single-contact shots without recovery
- bounded multi-contact attempts with recovery and re-aim

## Implementation Surface

Build the first `fetch_to_pose` lane from two surfaces:

1. A calibrated golf-ball UAT lane that exercises real sim contact and produces
   dashboard-visible evidence.
2. The existing gather mission infrastructure, after the ball/surface model is
   locked, for autonomous setup and recovery.

Current surfaces:

- `scripts/golf_ball_circle_delivery_demo_runner.py`: dashboard-owned
  golf-ball circle-delivery UAT. It spawns the calibrated ball and delivery
  circle, drives the robot through `/jetbot_base_controller/cmd_vel`, samples
  fresh Gazebo truth, and writes `mission_verdict.json`, `summary.json`,
  `target_results.json`, `scorecard.md`, `ball_trace.jsonl`,
  `contact_trace.jsonl`, and `approach_metrics.json`.
- `scripts/passive_ball_roll_calibration_helpers.py` and
  `scripts/passive_ball_roll_calibration_runner.py`: passive roll calibration
  scaffolding. The calibration lane now has a `direct_velocity` launch method
  that spawns a temporary ball SDF with a one-shot initial-velocity system:
  requested linear velocity plus matching rolling angular velocity
  (`omega = v / r`). Ramp and gravity-impulse modes remain debug fallbacks, not
  the promotional friction gate. Optional temporary rolling-resistance injection
  remains available for parameter sweeps, but promotional evidence now uses the
  built plugin carried by `ros2_config/calibrated_golf_ball.sdf`.
- `src/golf_ball_rolling_resistance_system.cc`: Gazebo system plugin for the
  calibrated golf-ball SDF. It observes post-update ball motion and passively
  reduces planar speed along the current motion direction; it does not steer
  toward the target.
- `ros2_config/calibrated_golf_ball.sdf`: canonical golf-ball dimensions and
  mass for the small-robot lane, plus the built rolling-resistance plugin.
  Calibrated-golf UAT requires `chasebot_description` to be built in
  `/root/ros2_ws` so the SDF can load the installed plugin library.
- `ros2_config/worlds/yolo_test_world_v6_calibrated_golf_turf.world`: calibrated
  golf-turf UAT world.
- `ros2_config/golf_ball_delivery_zone_marker.sdf`: visible delivery-circle
  marker for operator UAT.
- `ros2_config/target_layouts/golf_ball_circle_delivery_zero.json`: current
  zero-angle golf-ball target layout.
- `scripts/dashboard_service.py`: exposes the `golf_ball_circle_delivery_uat`
  scenario and records the latest `fetch_to_pose` result in dashboard state.

Next autonomous surfaces:

- `scripts/gather_mission_runner.py`: add a bounded `fetch_to_pose` phase after
  successful capture/setup and before any legacy place/release path. Preserve
  existing approach, capture-entry, capture, retry, and verdict bookkeeping.
- `scripts/gather_object_centric_policy_helpers.py`: add `phase="fetch_to_pose"`
  support and keep diagnostics compatible with existing `object_centric_policy`
  rows.
- `scripts/gather_mission_repeatability_runner.py`: preserve fetch verdict and
  shot-outcome fields in campaign summaries.
- `scripts/gather_object_centric_policy_evaluator.py`: add fetch outcome metrics
  beside the existing pre-stage/capture/zone metrics.
- `scripts/dashboard_service.py`: expose fetch only after the runner has a
  first-class scenario or CLI mode; final verdict display is enough before live
  per-tick fetch visualization. The dedicated golf-ball UAT scenario is already
  available for operator signoff.

State-history rows should carry the detailed shot evidence because
`state_history.jsonl` is per-tick. Keep `gather_sequence.jsonl` focused on
milestones and result events.

Planned per-tick fields:

- `phase: "fetch_to_pose"`
- `event_type`: `fetch_to_pose_tick`, `fetch_to_pose_result`, or `shot_outcome`
- `target_id`, `attempt`, and `attempt_kind`
- `robot_pose`, `ball_pose`, and `fetch_pose_world`
- `approach_contact_metrics`: signed lateral error, yaw error, first-contact
  state, ball lateral displacement, and oscillation counters
- `fetch_to_pose`: pass/reached/time/failure/distance/yaw fields
- `selected_command`
- `object_centric_policy.objective_name: "fetch_to_pose_object_state"`

Planned verdict fields:

- `fetch_to_pose_reached`
- `fetch_to_pose_time_s`
- `fetch_to_pose_failure_reason`
- `fetch_pose_world`
- `shot_outcome`

## Milestone 1: Fetch Outcome Schema

Define an artifact shape for shot-level and run-level evidence before tuning the
policy.

Required shot fields:

- target pose and delivery radius
- setup pose, ball pose, and relative contact geometry
- contact command sequence and duration
- ball trajectory samples through observe
- intersection result, closest approach, rest point, and miss vector
- surface/friction calibration snapshot
- deterministic guard decisions
- counterfactual prediction made before contact

Required run fields:

- cycle count
- total elapsed time
- success/failure verdict
- give-up budget consumed
- failure replay pointers

## Milestone 2: Surface Calibration

Build a small calibration lane for roll/contact behavior before broader mission
gates.

Calibration cases:

- straight shots at multiple distances
- shallow left/right angle shots
- low, nominal, and high contact effort
- repeated shots from the same setup pose

Outputs:

- distance and lateral error distribution by command profile
- speed decay estimate
- miss-vector bias by surface/session
- contact effort bounds for safe fetch attempts

Current calibration contract:

- Small-robot lane uses a golf ball with official-size model constants
  (`mass=0.04593kg`, `radius=0.021336m`).
- Surface tuning must make robot-scale golf-ball roll distance believable before
  the autonomous policy is promoted.
- Passive roll gates should be repaired into a repeatable excitation method, but
  the promotional path is now direct initial velocity, not robot contact, ramp,
  or gravity fixture acceleration. The first green UAT evidence is still the
  dashboard-owned real-contact circle delivery demo.

## Milestone 3: Structured Fetch Baseline

Start with an interpretable object-centric policy, not RL.

Inputs:

- robot pose
- ball pose
- target pose
- relative robot-ball vector
- relative ball-target vector
- recent robot and ball deltas
- previous selected command
- surface calibration summary

Behavior:

- choose a contact line from ball to target pose
- select a measured setup pocket behind the ball
- settle yaw and lateral error before first contact
- execute one bounded contact profile
- apply bounded directional correction while pushing, after stable contact
- observe ball trajectory until success, rest, timeout, or unsafe drift
- recover and re-aim only when budgets allow

Guards:

- max contact effort
- max angular command
- ball drift before intended contact
- max pre-contact lateral error
- max pre-contact yaw error
- max pre-contact yaw-error sign changes
- max ball lateral displacement during initial contact
- obstacle/person clearance
- target freshness
- cycle timeout
- stuck state
- give-up budget

## Milestone 4: Recovery And Counterfactuals

Use failed and partial shots to improve recovery without loosening guards.

Each contact attempt should record a pre-shot counterfactual prediction:

- expected trajectory corridor
- expected closest approach
- expected rest point
- expected need for recovery

After observe, compare prediction to measured outcome and emit a replayable miss
class. Recovery may use the measured miss vector and calibrated surface bias to
choose the next setup pocket or contact effort.

## Milestone 5: Fetch To Person

Add user/person delivery only after `fetch_to_pose` is green.

Detection contract:

- target pose
- detection confidence
- freshness timestamp
- optional person motion estimate
- delivery radius

The fetch policy should treat this as a dynamic target-pose source. If the
target becomes stale or low confidence, enter recover/re-aim or give up through
the same bounded budgets.

## Live Gates

0. Passive physics calibration:
   - status: green on May 26, 2026
   - artifact:
     `artifacts/session/live_passive_golf_roll_built_resistance_repeatability_20260526/passive_ball_roll_calibration/campaign_summary.json`
   - result: `pass=true`, `pass_count=3`, `fail_count=0`,
     `avg_roll_distance_m=0.679778`,
     `avg_effective_decel_mps2=0.735534`
   - launch with `--launch-method direct_velocity`
   - seed a calibrated golf ball at `1.0m/s` plus rolling angular velocity
   - require stop distance to land inside the standards-derived
     `calibrated_golf_turf` band (`0.45-0.90m` at `1.0m/s`) before treating the
     world as physics-locked
   - reject ramp/gravity fixture artifacts as promotional evidence
1. Golf-ball circle-delivery dashboard UAT:
   - status: green on May 26, 2026
   - artifact:
     `artifacts/session/20260526T175235537805Z/golf_ball_circle_delivery/20260526T175246191783Z/mission_verdict.json`
   - acceptance: visible calibrated golf ball enters a `0.300m` delivery circle
     through real robot contact
2. Approach-stability instrumentation gate:
   - status: green on May 26, 2026
   - artifact:
     `artifacts/session/20260526T175235537805Z/golf_ball_circle_delivery/20260526T175246191783Z/approach_metrics.json`
   - same dashboard scenario
   - require per-tick robot pose/yaw plus ball pose in `contact_trace.jsonl`
   - require `approach_metrics.stable_contact_approach_pass=true`
   - classify lateral knock-away or pre-contact oscillation before tuning
3. Golf-ball circle-delivery repeatability:
   - status: formal centerline gate green on May 27, 2026
   - artifact:
     `artifacts/session/live_calibrated_golf_fetch_centerline_repeatability_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`
   - same dashboard scenario, at least 3 runs, no code changes during the gate
   - require `fetch_to_pose_pass_count=3`, `fetch_to_pose_fail_count=0`, and
     every `shot_outcome.closest_approach_distance_m <= 0.300`
4. Autonomous fetch-to-pose smoke on calibrated golf turf:
   - status: superseded by the May 27, 2026 demo-readiness saved-layout gate.
     Earlier centerline clean-start policy smoke was `2/2` green, and off-axis
     `left05/right05` smoke was `2/2` green. Two passes were borderline
     (`0.298832m` centerline and `0.299554m` right05), which led to the
     no-retry repeatability gate below rather than a policy redesign.
   - artifact:
     `artifacts/session/live_calibrated_golf_fetch_off_axis_smoke_20260527/calibrated_golf_fetch_gate/gate_summary.json`
   - saved-layout `golf_ball_circle_delivery_zero`, 3 runs, no retries
   - saved-layout `golf_ball_circle_delivery_left05`, one run, no retries
   - saved-layout `golf_ball_circle_delivery_right05`, one run, no retries
   - run with:
     `python scripts/calibrated_golf_fetch_gate.py --suite centerline`
     followed by
     `python scripts/calibrated_golf_fetch_gate.py --suite off_axis`
5. Autonomous recovery smoke:
   - one allowed recovery cycle
   - explicit give-up when the second contact cannot be made safely
6. Autonomous repeatability:
   - status: green on May 27, 2026 for no-retry demo readiness
   - artifact:
     `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`
   - dashboard CTA centerline:
     `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527_cta_centerline/gather_mission_repeatability/campaign_run_summary.json`,
     `3/3`, worst closest approach `0.235981m`
   - saved-layout `golf_ball_circle_delivery_zero`:
     `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527_policy_centerline/gather_mission_repeatability/campaign_run_summary.json`,
     `3/3`, worst closest approach `0.280497m`
   - saved-layout `golf_ball_circle_delivery_left05`:
     `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527_policy_left05/gather_mission_repeatability/campaign_run_summary.json`,
     `3/3`, worst closest approach `0.287996m`
   - saved-layout `golf_ball_circle_delivery_right05`:
     `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527_policy_right05/gather_mission_repeatability/campaign_run_summary.json`,
     `3/3`, worst closest approach `0.293705m`
   - all runs used `--max-retries-per-target 0`, `mission_completed_pass=true`,
     `fetch_to_pose_pass=true`, and
     `shot_outcome.closest_approach_distance_m <= 0.300`
   - approach telemetry showed no lateral knock-away and no pre-contact
     oscillation regression; keep first-contact alignment under observation
     because one green centerline run reached `12.826061deg`
7. Targeted alternative-architecture requalification:
   - status: red for the MPPI setup/pre-stage revisit on May 27, 2026
   - artifact:
     `artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`
   - result: `nav2_mppi_follow_path_reacquire_v1` failed `zero`, `left05`, and
     `right05` one-run probes before contact with
     `nav2_follow_path_path_clearance_guard`; no promotion rerun was attempted
   - compare only against the calibrated May 27, 2026 demo-readiness package:
     `artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`
   - same calibrated golf ball, calibrated turf world, `0.300m` delivery radius,
     saved layouts, no retries, approach telemetry, and deterministic guards
   - pass the same dashboard CTA centerline and policy `zero`, `left05`, and
     `right05` gates before discussing promotion
   - classify regressions in closest approach, first-contact alignment,
     pre-contact yaw sign changes, lateral knock-away, or goal-side entry before
     any broader architecture pivot
8. Contact-aware geometric shooter spike:
   - status: offline screen green; canonical saved-layout `zero`/`left05`/
     `right05` one-shot matrix green; repeatability/recovery design not yet run
   - artifact:
     `artifacts/session/live_fetch_geometric_shooter_screen_20260527/fetch_geometric_shooter_screen/geometric_shooter_summary.json`
   - result: `12/12` offline model passes over the May 27 calibrated CTA/policy
     traces with no missing trace inputs
   - model requirement: max delivery-entry speed `0.626061m/s`, max target-center
     stop speed `0.907718m/s`, minimum aim half-angle `31.621299deg`
   - canonical `zero` probe:
     `artifacts/session/live_fetch_geometric_shooter_probe_zero_20260527/fetch_geometric_shooter_probe/geometric_shooter_probe_summary.json`
   - probe result: bounded direct-velocity shot impulse passed with initial
     speed `0.90598m/s`, heading `0.0deg`, closest/final distance `0.011837m`,
     and 65 ball trace samples
   - saved-layout matrix result:
     `live_fetch_geometric_shooter_probe_zero_20260527`,
     `live_fetch_geometric_shooter_probe_left05_20260527`, and
     `live_fetch_geometric_shooter_probe_right05_20260527` all passed one-run
     probes with closest/final distances `0.011837m`, `0.011898m`, and
     `0.011898m`
   - interpretation: the shot impulse is physically plausible enough to justify
     repeatability/recovery design; do not count the offline screen or one-run
     impulse matrix as robot-policy UAT evidence
9. Person target prototype:
   - only after pose-target gates are green

## Non-Goals

- Do not require final stop in the corral for fetch success.
- Do not promote previous launch-only evidence until the calibrated physics lane
  is green and documented.
- Do not begin with user detection before `fetch_to_pose` is repeatable.
- Do not loosen `/odom` or frozen runtime contracts.
- Do not allow unbounded re-aim or retry loops.
- Do not hide failed contact attempts; every miss needs replayable evidence.
- Do not let learned components bypass deterministic guards.
- Do not reopen old pre-stage-only branches or MPPI contact tuning as broad
  replacements for the calibrated fetch-to-pose baseline.

## Stop Criteria

Retire or freeze a branch when:

- success depends on case-specific contact scripts
- give-up budgets must grow to hide unreliable shots
- fresh reruns flip after minor session/runtime changes
- failure replay cannot explain shot outcomes
- counterfactual predictions do not improve with calibration data
- safety guards must be loosened to show progress
