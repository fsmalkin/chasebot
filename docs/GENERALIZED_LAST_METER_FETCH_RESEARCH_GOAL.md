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

## Next Major Milestone

Deliver Generalized Fetch-To-Pose v1: a no-shoot, robot-owned local fetch
behavior that combines Nav2 stage ownership, deterministic homebrew contact
routines, and a guarded AI/model handoff-and-maneuver proposer, proven on saved
layouts and the first seeded random generalization gate.

Scope correction: this milestone proves the bounded local fetch subsystem, not
open-world planner competence. The broader product milestone is Planner-Gated
Generalized Fetch: an LLM/world-state planner first decides whether a scene is
fetch-ready, requires scan/perception, requires Nav2 repositioning, requires a
different recovery/subroutine, or should abort/no-go. Only fetch-ready local
cases should be handed to `fetch_to_pose` and scored as fetch subsystem
evidence.

Milestone acceptance:

1. Saved-layout `zero`, `left05`, and `right05` pass `3/3` in the canonical
   calibrated golf-ball/turf lane with no retries and `0.300m` delivery radius.
2. The first seeded random `fetch_generalization_gate` set runs; reproducible
   failures are frozen into named saved layouts before tuning.
3. The AI/model layer first passes shadow scoring on saved anchors, Nav2
   stop-short evidence, and seeded layouts as a handoff and maneuver-class
   proposer, not as a direct motor controller.
4. Learned execution, when enabled, remains inside deterministic guards for
   command bounds, target freshness, ball drift, retry budget, safe stop, and
   `/odom`/contract preservation.
5. A separate planner-handoff gate exists before any "truly random" claim:
   mixed scenarios are scored on correct route selection (`fetch_ready_local`,
   `nav2_reposition_first`, `scan_or_perceive_first`, `recovery_or_reaim`,
   `ambiguous_or_unsafe_no_go`) before subsystem execution is judged.

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
   simulations to estimate stage handoffs, roll outcome, miss vector, terminal
   re-push need, coast timing, and recovery side.
3. Deterministic guards remain authoritative over command limits, target
   freshness, ball drift, retry budget, safe stop, and promotion gates.
4. Direct high-frequency LM-owned `/cmd_vel` remains out of scope.

Use contact-aware geometric-shooter evidence as a physics and trajectory probe
only. It is not the preferred runtime architecture because it currently proves a
direct ball-velocity impulse, not robot-owned bounded pushing.

May 29, 2026 evidence update: the Nav2 corridor-push spike answered the cheap
physics/controller question but did not promote as the sole contact controller.
The spike was saved-layout evidence only; the seeded random/generalization gate
has not run.

- Contact-ready `zero`, `left05`, and `right05` all passed with Nav2 owning
  real-time `FollowPath` tracking through the ball-target corridor.
- Full saved-layout one-run `zero`, `left05`, and `right05` all passed.
- Saved-layout `3/3` repeatability passed `zero` and `left05`, but `right05`
  failed one promotion run with
  `missed_delivery_radius_after_fetch_to_pose_ball_stopped_short`; Nav2
  returned `STATUS_SUCCEEDED`, the ball moved only about `0.121m`, and the
  closest approach was `0.451645m` against the `0.300m` contract.

Interpretation: Nav2 can provide useful real-time corridor tracking and bounded
contact, but path completion is not the same as object delivery. The `right05`
miss is close enough to be a constructive boundary case, not a reason to
replace Nav2 wholesale. Do not promote `nav2_followpath_corridor_push_v1` as a
standalone contact owner. Freeze the right05 stop-short artifact and move the
next focused lane to a hybrid fetch stage supervisor: Nav2 owns long-haul,
coarse setup, and corridor tracking where it is strong; deterministic homebrew
routines own fine pre-capture alignment, first contact, terminal re-push/coast,
and recentering; the AI/model layer starts in shadow mode as the handoff and
maneuver-class proposer. This remains distinct from the old
`nav2_mppi_follow_path_reacquire_v1` pre-stage evidence branch.

May 29, 2026 dashboard UAT refinement: dashboard random golf-fetch runs now
separate visual stress from evidence gates. `corridor_contact_v1` preserves the
narrow contact-ready random draw for contact diagnostics. `local_visual_v1` is
the green dashboard CTA default and samples a wider bounded ball-target and
robot setup geometry for visual UAT. These wide CTA failures should be
classified as controller-stage backlog evidence, not as architecture promotion
failures. Promotion still requires saved-layout gates and the seeded
`fetch_generalization_gate`.

May 30, 2026 evidence workflow update: close out `local_visual_v1` with a
scorecard before widening again. Use
`scripts/dashboard_random_fetch_uat_analyzer.py` to report seed, profile,
geometry, closest approach, pass/fail reason, contact-quality flags, and stage
labels. The first three live green-CTA runs passed delivery but carried contact
quality flags, so they support the hybrid stage-supervisor direction rather
than standalone promotion. The next ladder step is seeded `fetch_generalization_gate`
dry-run plus a `6 x 1` shadow/evidence pass with `ai_push_coast_servo_v1`.
Guarded live execution should start only with one terminal correction for
stop-short or near-contract misses after shadow scoring is useful.

May 30, 2026 guarded-live refinement: score seeded gates with
`scripts/fetch_seeded_gate_evidence_analyzer.py` before promotion or tuning.
The first guarded-live executor remains terminal-only: one deterministic
re-push/re-aim cycle may run only after Nav2/fetch has produced measured object
motion and the miss is near-contract. Setup, capture-entry, first-contact,
push/coast quality, ball-escape, stale-state, broad lateral/yaw, and non-repro
random failures stay in shadow/watchlist evidence until reproduced.

May 30, 2026 planner-gated randomization refinement: do not interpret arbitrary
or visually surprising random starts as direct fetch failures unless the scene is
inside the documented local fetch envelope. "Truly random" testing belongs in a
planner-handoff suite first. The planner/LLM should classify major unknowns and
choose a bounded route: scan, reposition, re-aim, recover, abstain/no-go, or
only then dispatch local `fetch_to_pose`. This keeps subsystem gates honest:
the fetch gate proves control inside its envelope; the planner gate proves that
the system can recognize when that envelope does not apply.

Implementation update: `scripts/fetch_planner_handoff_gate.py` now replays the
frozen `ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json` scene
set or generates mixed scene descriptors and scores route labels before local
fetch dispatch.
The dashboard has a planner-gated random path that writes planner artifacts and
skips local fetch for non-`fetch_ready_local` scenes. The initial deterministic
dry-run artifact is
`artifacts/session/dev_fetch_planner_handoff_gate_frozen_replay_20260531/fetch_planner_handoff_gate/scorecard.md`.

May 29, 2026 model-planning refinement: V-JEPA-style world models are relevant
as an architectural pattern for scoring candidate actions against predicted
physical outcomes, but full video world models are not the onboard control
target for the Jetbot/Orin lane. Treat large world models as offboard teachers,
labelers, or research baselines. The onboard path is a smaller structured model
or distilled predictor compatible with `tensorrt_int8`, operating on robot pose,
ball pose, target pose, Nav2 progress, and recent contact telemetry.

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
automatic winner. The preferred next spike is no longer a shooter spike or a
standalone Nav2 tuning pass. It is
`spike/fetch-arch-ai-push-coast-servo-20260529`: a shadow-first hybrid stage
supervisor spike. It should use the Nav2 corridor-push stop-short evidence plus
object-centric baseline traces to decide when to stay with Nav2, hand off to a
deterministic terminal re-push/coast routine, recenter left/right, abort, or
re-stage. Nav2 remains a first-class stage owner; the learned lane should rank
handoffs and maneuver classes, remain behind deterministic guards, and avoid
direct high-frequency `/cmd_vel`.

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

Acceleration note: the current calibrated fast-screen lane is
`real_time_factor=2.0` in
`yolo_test_world_v6_calibrated_golf_turf_fast.world`. Treat 2.0x as the normal
cheap-rejection speedup. Treat any 3.0x/4.0x run as an explicitly experimental
speed sweep, useful for finding obvious instability but not for proving
contact-rich success.

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
