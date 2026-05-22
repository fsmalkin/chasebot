# Object-Centric Fetch Policy Plan

## Status

This is the active research direction after the object-centric gather/place
pivot. The May 2026 direction is now physics-first: treat the earlier
launch/roll behavior as a hypothesis until the ball and surface model pass
calibrated roll and contact-rich UAT gates. The near-term target is a
small-robot golf-ball `fetch_to_pose` demo into a visible delivery circle;
`fetch_to_person` comes later after target pose delivery is repeatable and
instrumented.

The previous gather/place objective remains useful as negative baseline
evidence, but success is no longer final stop in the corral. Success is
trajectory intersection with a delivery radius around the requested target pose.

Latest green UAT:

- Dashboard scenario: `golf_ball_circle_delivery_uat`
- World: `yolo_test_world_v6_calibrated_golf_turf.world`
- Ball model: `ros2_config/calibrated_golf_ball.sdf`
- Delivery marker: `ros2_config/golf_ball_delivery_zone_marker.sdf`
- Session: `artifacts/session/20260522T055454253626Z/golf_ball_circle_delivery/20260522T055504453763Z`
- Verdict: `mission_completed_pass=true`, `fetch_to_pose_pass=true`,
  `fetch_to_pose_pass_count=1`, `fetch_to_pose_fail_count=0`
- Closest approach: `0.051999m` inside a `0.300m` delivery radius

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

- `nav2_mppi_follow_path_reacquire_v1`: baseline for long-range/pre-stage
  geometry and failure modes in contact-rich capture.
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
  `target_results.json`, `scorecard.md`, and `ball_trace.jsonl`.
- `scripts/passive_ball_roll_calibration_helpers.py` and
  `scripts/passive_ball_roll_calibration_runner.py`: passive roll calibration
  scaffolding. The current live sim does not expose a reliable ball impulse or
  wrench service, and ramp-start probes showed fixture artifacts, so this lane
  is instrumentation scaffolding until the excitation method is repaired.
- `ros2_config/calibrated_golf_ball.sdf`: canonical golf-ball dimensions and
  mass for the small-robot lane.
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
  the first green UAT evidence is the dashboard-owned real-contact circle
  delivery demo.

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
- execute one bounded contact profile
- observe ball trajectory until success, rest, timeout, or unsafe drift
- recover and re-aim only when budgets allow

Guards:

- max contact effort
- max angular command
- ball drift before intended contact
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

0. Passive physics calibration scaffolding:
   - status: instrumented, not promotional yet
   - repair or replace the excitation method so measured stop distance is a
     property of the ball/surface model rather than the fixture
1. Golf-ball circle-delivery dashboard UAT:
   - status: green on May 22, 2026
   - artifact:
     `artifacts/session/20260522T055454253626Z/golf_ball_circle_delivery/20260522T055504453763Z/mission_verdict.json`
   - acceptance: visible calibrated golf ball enters a `0.300m` delivery circle
     through real robot contact
2. Golf-ball circle-delivery repeatability:
   - same dashboard scenario, at least 3 runs, no code changes during the gate
   - require `fetch_to_pose_pass_count=3`, `fetch_to_pose_fail_count=0`, and
     every `shot_outcome.closest_approach_distance_m <= 0.300`
3. Autonomous fetch-to-pose smoke on calibrated golf turf:
   - saved-layout `zero`, one run, no retries
   - saved-layout `plus45`, one run, no retries
4. Autonomous recovery smoke:
   - one allowed recovery cycle
   - explicit give-up when the second contact cannot be made safely
5. Autonomous repeatability:
   - saved-layout `zero --runs 3`, bounded recovery
   - saved-layout `plus45 --runs 3`, bounded recovery
6. Person target prototype:
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

## Stop Criteria

Retire or freeze a branch when:

- success depends on case-specific contact scripts
- give-up budgets must grow to hide unreliable shots
- fresh reruns flip after minor session/runtime changes
- failure replay cannot explain shot outcomes
- counterfactual predictions do not improve with calibration data
- safety guards must be loosened to show progress
