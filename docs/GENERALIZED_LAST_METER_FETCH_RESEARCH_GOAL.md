# Generalized Last-Meter Fetch Research Goal

Date: May 28, 2026

## Goal

Run a full architecture research pass for generalized last-meter
`fetch_to_pose`. The result should be a findings package, not an immediate
tuning branch: compare the plausible architecture paths against the same
calibrated ball/turf contract, identify which paths deserve focused spikes,
which should remain fallback or evidence-only, and which should be treated as
no-go until assumptions change.

The target capability is a robot-owned last-meter architecture that can deliver
the ball to a requested target pose from varied robot, ball, and target geometry,
not only the current saved layouts.

## May 28, 2026 Direction

The research pass selected a no-shoot runtime direction. The target
architecture is a robot-owned bounded push-and-coast local policy:
approach the correct side of the ball, make low-error contact, add only bounded
energy, stop pushing when the measured or predicted trajectory intersects the
delivery circle, then observe and re-aim within a small budget.

AI is part of the direction, but it is layered:

1. LM or robot-foundation-model supervision may reason over task mode, failure
   interpretation, and known maneuver choices.
2. A learned local predictor/proposer should be trained from many calibrated
   simulations to estimate roll outcome, miss vector, push duration, coast
   timing, and recovery side.
3. Deterministic guards remain authoritative over command limits, target
   freshness, ball drift, retry budget, safe stop, and promotion gates.
4. Direct high-frequency LM-owned `/cmd_vel` remains out of scope.

Use contact-aware geometric-shooter evidence as a physics and trajectory probe
only. It is not the preferred runtime architecture because it currently proves a
direct ball-velocity impulse, not robot-owned bounded pushing.

Immediate update: before building the learned contact controller, test whether
the calibrated world physics keeps the ball inside Nav2's natural operating
envelope. The next hypothesis spike is `nav2_followpath_corridor_push_v1`:
Nav2 owns real-time `FollowPath` tracking through the ball-target corridor,
while a fetch monitor only cancels on measured success, ball escape, stale
state, unsafe drift, timeout, or action abort. This is distinct from the old
`nav2_mppi_follow_path_reacquire_v1` pre-stage evidence branch; it is a fresh
corridor-push test. If the ball escapes or Nav2 contact motion is unstable, the
AI learned local contact policy remains the next/fallback lane.

## Paths To Research

Evaluate these paths side by side:

1. Current object-centric fetch baseline.
2. Contact-aware geometric shooter as physics-probe evidence only.
3. Receding-horizon contact MPC or object servo.
4. ROS action-server or behavior-tree last-meter owner.
5. Nav2 FollowPath corridor-push contact owner.
6. Nav2 reposition plus object-centric last meter.
7. Passive mechanical guide or funnel.
8. Learned local predictor, residual, or maneuver proposer behind deterministic
   guards.
9. Portfolio supervisor or switcher.
10. Perception-first target-pose fetch.

Use the existing object-centric baseline as the comparison reference, not as an
automatic winner. The preferred next spike is not a shooter spike; it is
`spike/fetch-arch-nav2-corridor-push-20260528`, a physics-first Nav2
FollowPath corridor-push test with ball-escape monitoring. The AI-assisted
bounded push-and-coast object-servo lane remains the next/fallback path if Nav2
cannot keep contact stable under calibrated physics.

## Research Questions

For each path, answer:

1. What owns the last meter: mission loop, action server, local controller,
   learned proposer, passive mechanism, or supervisor?
2. What changes relative to the current implementation: ownership boundary,
   prediction model, state-machine boundary, contact strategy, recovery
   strategy, hardware shape, or perception assumption?
3. Which generalization failures should it fix: side selection, pre-contact
   reorientation, first-contact alignment, lateral knock-away, overshoot,
   recovery failure, shot infeasible, or perception mismatch?
4. What is the cheapest honest evidence gate that can reject it?
5. What evidence is required before it can be called robot-owned UAT rather than
   offline, accelerated, direct-ball, or probe-only evidence?
6. What is the hardware-transfer story for the Jetbot-sized robot and calibrated
   golf-ball/turf lane?
7. What makes the path diagnosable when it fails?
8. If AI is involved, what layer owns it: LM/VLA supervisor, local learned
   predictor, maneuver proposer, residual controller, perception source, or
   low-level policy? What deterministic guard can veto it?

## Evidence Ladder

Use the ladder in
[CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md](CALIBRATED_FETCH_ARCHITECTURE_TEST_PLAN.md)
as the common comparison frame:

1. Desk check.
2. Offline or accelerated screen.
3. Canonical saved-layout `zero` one-run probe.
4. Canonical saved-layout matrix: `zero`, `left05`, `right05`.
5. `3/3` repeatability on each saved layout.
6. Seeded random/generalization suite.
7. Promotion package with explicit failure interpretation.

Promotion evidence must use the canonical calibrated golf-ball/turf world,
`0.300m` delivery radius, no retries, fresh runtime traces, and the same
`fetch_to_pose` success contract. Offline, accelerated, direct-ball, or
dashboard-observation results may guide research but cannot promote a
robot-owned architecture.

AI-assisted candidates add two pre-promotion requirements:

1. shadow-mode evaluation against saved anchors and seeded random layouts before
   learned proposals can execute
2. an onboard-inference plan compatible with the canonical
   `tensorrt_int8` backend before hardware-transfer claims

## Definition Of Done For The Research Thread

The research thread is done when it returns a concise findings package that:

1. Grounds itself in current docs, branches, stashes, and artifacts before
   proposing a path.
2. Summarizes every listed architecture path with promise, blockers,
   implementation effort, safety/evidence gaps, likely failure classes, and
   first honest gate.
3. Identifies immediate paths, later/fallback paths, and no-go paths.
4. Recommends one primary path and a short fallback sequence.
5. Defines the next focused spike branch and gate without tuning code first.
6. Explains how saved-layout anchors, seeded random layouts, and frozen
   reproducible failures will be used.
7. Keeps branch strategy and high-level plans propagated to `main`; runnable
   experiments stay on focused spike branches.
8. Separates no-shoot bounded push/coast control from direct impulse or
   geometric-shooter probe evidence.

## Next Thread Prompt

```text
/goal Full Research: Generalized Last-Meter Fetch Architecture

Research all high-level last-meter fetch architecture paths documented in
Chasecar and return with findings, evidence gaps, and a recommended path
sequence. Compare current object-centric fetch, contact-aware geometric shooter
as physics-probe evidence, receding-horizon contact MPC/object servo, ROS
action/BT last-meter owner, Nav2 reposition plus local fetch, passive
guide/funnel, learned local predictor/residual/maneuver proposer, portfolio
supervisor/switcher, and perception-first target-pose fetch.

Do not jump straight into tuning one path. First ground in branch/docs/artifacts,
then evaluate each path against the calibrated fetch_to_pose contract,
saved-layout anchors, seeded random/generalization gate, robot-owned contact
requirement, hardware-transfer path, diagnosability, and implementation cost.
Come back with a findings matrix, a recommended primary path, fallback paths,
no-go paths, and the next focused spike/gate plan.
```
