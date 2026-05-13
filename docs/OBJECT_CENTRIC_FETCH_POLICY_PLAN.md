# Object-Centric Fetch Policy Plan

## Status

This is the active research direction after the object-centric gather/place
pivot. Treat the emergent roll/launch behavior as the core fetch primitive. The
near-term target is `fetch_to_pose`; `fetch_to_person` comes later after target
pose delivery is repeatable and instrumented.

The previous gather/place objective remains useful as negative baseline
evidence, but success is no longer final stop in the corral. Success is
trajectory intersection with a delivery radius around the requested target pose.

## Thesis

Use long-range navigation only to set up the robot and ball. The object-centric
fetch policy owns short-horizon ball interaction as bounded
setup-launch-observe-recover cycles:

1. `setup`: reach a measured launch pocket behind the ball for the requested
   target pose.
2. `launch`: apply a bounded command sequence intended to roll the ball through
   the delivery radius.
3. `observe`: track ball trajectory, speed decay, target intersection, and miss
   vector.
4. `recover`: re-aim from the new ball state when budgets allow.
5. `done`: accept once the ball trajectory intersects the delivery radius.
6. `give_up`: stop with an explicit failure reason when budgets are exhausted.

The first policy family is:

`object_centric_fetch_policy_v1`

It may emit bounded `linear_x` / `angular_z` commands, short relative waypoints,
or launch scripts, but every proposal must pass deterministic guards before
execution.

## Success Definition

Primary success for `fetch_to_pose`:

- the ball trajectory intersects a configurable delivery radius around the
  target pose
- intersection is measured from fresh runtime state, not inferred from command
  intent
- the run records approach, launch, and post-launch ball state at enough
  resolution to replay the shot

Secondary metrics:

- closest approach distance to target pose
- first intersection timestamp
- ball speed at intersection
- final rest distance from target
- number of setup/launch/recover cycles
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

- no-launch / setup-only runs
- single-shot launches without recovery
- bounded multi-shot launches with recovery and re-aim

## Implementation Surface

Build the first `fetch_to_pose` lane inside the existing gather mission
infrastructure rather than adding a parallel runner.

Recommended surfaces:

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
  per-tick fetch visualization.

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
- setup pose, ball pose, and relative launch geometry
- launch command sequence and duration
- ball trajectory samples through observe
- intersection result, closest approach, rest point, and miss vector
- surface/friction calibration snapshot
- deterministic guard decisions
- counterfactual prediction made before launch

Required run fields:

- cycle count
- total elapsed time
- success/failure verdict
- give-up budget consumed
- failure replay pointers

## Milestone 2: Surface Calibration

Build a small calibration lane for launch behavior before broader mission gates.

Calibration cases:

- straight shots at multiple distances
- shallow left/right angle shots
- low, nominal, and high launch effort
- repeated shots from the same setup pose

Outputs:

- distance and lateral error distribution by command profile
- speed decay estimate
- miss-vector bias by surface/session
- launch effort bounds for safe fetch attempts

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

- choose a launch line from ball to target pose
- select a measured setup pocket behind the ball
- execute one bounded launch profile
- observe ball trajectory until success, rest, timeout, or unsafe drift
- recover and re-aim only when budgets allow

Guards:

- max launch effort
- max angular command
- ball drift before intended launch
- obstacle/person clearance
- target freshness
- cycle timeout
- stuck state
- give-up budget

## Milestone 4: Recovery And Counterfactuals

Use failed and partial shots to improve recovery without loosening guards.

Each launch should record a pre-shot counterfactual prediction:

- expected trajectory corridor
- expected closest approach
- expected rest point
- expected need for recovery

After observe, compare prediction to measured outcome and emit a replayable miss
class. Recovery may use the measured miss vector and calibrated surface bias to
choose the next setup pocket or launch effort.

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

1. Calibration smoke:
   - straight target pose, one launch, one run
   - record shot outcome and replay pointers
2. Fetch-to-pose smoke:
   - saved-layout `zero`, one run, no retries
   - saved-layout `plus45`, one run, no retries
3. Recovery smoke:
   - one allowed recovery cycle
   - explicit give-up when the second shot cannot be made safely
4. Repeatability:
   - saved-layout `zero --runs 3`, bounded recovery
   - saved-layout `plus45 --runs 3`, bounded recovery
5. Person target prototype:
   - only after pose-target gates are green

## Non-Goals

- Do not require final stop in the corral for fetch success.
- Do not begin with user detection before `fetch_to_pose` is repeatable.
- Do not loosen `/odom` or frozen runtime contracts.
- Do not allow unbounded re-aim or retry loops.
- Do not hide failed launches; every miss needs replayable evidence.
- Do not let learned components bypass deterministic guards.

## Stop Criteria

Retire or freeze a branch when:

- success depends on case-specific launch scripts
- give-up budgets must grow to hide unreliable shots
- fresh reruns flip after minor session/runtime changes
- failure replay cannot explain shot outcomes
- counterfactual predictions do not improve with calibration data
- safety guards must be loosened to show progress
