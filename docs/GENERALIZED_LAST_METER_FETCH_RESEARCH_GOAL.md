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

## Paths To Research

Evaluate these paths side by side:

1. Current object-centric fetch baseline.
2. Contact-aware geometric shooter.
3. Receding-horizon contact MPC or object servo.
4. ROS action-server or behavior-tree last-meter owner.
5. Nav2 reposition plus object-centric last meter.
6. Passive mechanical guide or funnel.
7. Learned residual or maneuver proposer behind deterministic guards.
8. Portfolio supervisor or switcher.
9. Perception-first target-pose fetch.

Use the existing object-centric baseline as the comparison reference, not as an
automatic winner. Use the geometric-shooter evidence as a promising shot
primitive until robot-owned contact is implemented and measured.

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

## Next Thread Prompt

```text
/goal Full Research: Generalized Last-Meter Fetch Architecture

Research all high-level last-meter fetch architecture paths documented in
Chasecar and return with findings, evidence gaps, and a recommended path
sequence. Compare current object-centric fetch, contact-aware geometric shooter,
receding-horizon contact MPC/object servo, ROS action/BT last-meter owner, Nav2
reposition plus local fetch, passive guide/funnel, learned residual/maneuver
proposer, portfolio supervisor/switcher, and perception-first target-pose fetch.

Do not jump straight into tuning one path. First ground in branch/docs/artifacts,
then evaluate each path against the calibrated fetch_to_pose contract,
saved-layout anchors, seeded random/generalization gate, robot-owned contact
requirement, hardware-transfer path, diagnosability, and implementation cost.
Come back with a findings matrix, a recommended primary path, fallback paths,
no-go paths, and the next focused spike/gate plan.
```
