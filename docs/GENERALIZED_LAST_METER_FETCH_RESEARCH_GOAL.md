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

Deliver Planner-Gated Generalized Fetch-To-Pose v1: a no-shoot, robot-owned
fetch behavior where an LLM/world-state planner chooses the right bounded route,
Nav2 owns as much real-time robot motion as it can safely own, and a thin
fetch adapter monitors corrected ball/target geometry, success, escape, stale
state, and replanning triggers. Custom contact routines and AI push-coast
prediction remain fallback lanes that earn live authority only after corrected
Nav2-first evidence exposes a reproducible stage gap.

Scope correction: this milestone proves the planner-to-subsystem handoff plus
the bounded local fetch skill. The planner first classifies scenes as
`fetch_ready_local`, `nav2_reposition_first`, `scan_or_perceive_first`,
`recovery_or_reaim`, or `ambiguous_or_unsafe_no_go`. Only planner-approved
`fetch_ready_local` cases should be handed to `fetch_to_pose` and scored as
local fetch evidence.

Milestone acceptance:

1. Evidence is valid only when `geometry_consistency.pass=true`, the visible
   delivery marker matches `fetch_pose_world`, and the run has same-session
   browser-watchable onboard plus context video.
2. Pre-fix or marker-mismatched fetch passes are reclassified as diagnostic
   implementation evidence. Architecture and promotion claims require the
   corrected marker and video floor.
3. The planner-handoff gate passes before broad random UAT: mixed scenarios are
   scored on correct route selection (`fetch_ready_local`,
   `nav2_reposition_first`, `scan_or_perceive_first`, `recovery_or_reaim`,
   `ambiguous_or_unsafe_no_go`) before subsystem execution is judged.
4. Saved-layout `zero`, `left05`, and `right05` pass `3/3` in the canonical
   calibrated golf-ball/turf lane with no retries and `0.300m` delivery radius.
5. The first seeded random `fetch_generalization_gate` set runs; reproducible
   failures are frozen into named saved layouts before tuning.
6. Custom contact routines and AI/model proposals are added only where the
   corrected Nav2/adapter baseline shows a reproducible stage gap. AI starts in
   shadow mode and may execute only by selecting deterministic guarded routines.

## May 31, 2026 Evidence And Architecture Reset

The delivery-marker geometry issue invalidated a meaningful share of recent
fetch-result interpretation. Preserve the code, dashboards, analyzers, videos,
and guardrails that exposed the issue. Reclassify pre-fix result claims unless
the artifact proves corrected marker geometry and same-session visual evidence.

Fresh corrected evidence:

- Geometry fix commit: `7bb2719 Fix fetch delivery marker geometry validation`.
- Invalidated-evidence audit:
  `artifacts/session/fetch_geometry_evidence_audit_20260531/fetch_geometry_evidence_audit/scorecard.md`.
- Corrected UAT run:
  `artifacts/session/20260531T204154158382Z/gather_mission/20260531T204255Z/mission_verdict.json`.
- Corrected visual UAT package:
  `artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`.
- Corrected geometry audit:
  `artifacts/session/fetch_geometry_evidence_audit_postfix_20260531/fetch_geometry_evidence_audit/scorecard.md`.

The corrected saved-zero run proves the metric path: `fetch_to_pose_pass=true`,
`geometry_consistency.pass=true`, marker center `(0.95, 0.0)`, marker radius
`0.300m`, and truth telemetry showing the ball reached about `0.158m` from the
target center. This is valid local fetch evidence and a visual UAT reference.
Broad-generalization claims still require saved-layout repeatability and the
seeded gate.

Architecture reset:

1. Default to `LLM/world-state planner -> Nav2/BT action owner -> thin fetch
   adapter and geometry monitor -> robot`.
2. Let Nav2 own long-haul navigation, repositioning, corridor approach, and
   bounded push paths whenever corrected evidence shows the ball remains inside
   the local envelope.
3. Keep the custom fetch adapter focused on intent translation, corrected
   geometry monitoring, escape/stale/success classification, and replanning or
   cancellation.
4. Keep AI push-coast/contact-stability as the fallback lane for reproducible
   gaps such as setup instability, first-contact drift, terminal stop-short, or
   re-aim selection.
5. Keep large world-model or VLA ideas as high-level planning, teacher-label,
   or offboard scoring tools until a smaller `tensorrt_int8`-compatible onboard
   predictor has shadow evidence.

## May 28, 2026 Direction

The research pass selected a no-shoot runtime direction. After the May 31
evidence reset, the preferred runtime shape is planner-gated and Nav2-first:
the planner chooses the route class, Nav2 owns robot motion where it has a
clear contract, and the fetch adapter verifies object outcome against corrected
geometry. Bounded push-and-coast routines remain available for contact-rich
subroutines outside Nav2's clean local-control contract.

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
physics/controller question and left sole-contact promotion blocked by
repeatability. The spike was saved-layout evidence only; the seeded
random/generalization gate remains pending.

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

Use the existing object-centric and AI push-coast work as implementation
infrastructure, with the corrected Nav2/LLM-first baseline as the immediate
center of gravity:

1. rerun saved-layout `zero`, `left05`, and `right05` under the corrected
   geometry/video evidence floor
2. run the planner-handoff gate before broad random or visually surprising
   scenarios
3. dispatch local `fetch_to_pose` only for planner-approved
   `fetch_ready_local` scenes
4. let the AI push-coast lane score stage gaps in shadow mode from corrected
   Nav2-first failures

The current `spike/fetch-arch-ai-push-coast-servo-20260529` branch remains a
valid place to preserve the analyzer, guard, and fallback code. Its live-control
authority should stay narrow until corrected Nav2-first evidence proves the
specific subroutine that needs custom or learned help.

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

0. Evidence validity check: corrected delivery marker geometry plus same-session
   browser-watchable onboard and context video.
1. Desk check.
2. Offline or accelerated screen.
3. Planner-handoff gate for mixed or broad random scenes.
4. Canonical saved-layout `zero` one-run probe.
5. Canonical saved-layout matrix: `zero`, `left05`, `right05`.
6. `3/3` repeatability on each saved layout.
7. Seeded random/generalization suite inside the local fetch envelope.
8. Promotion package with explicit failure interpretation.

Promotion evidence must use the canonical calibrated golf-ball/turf world,
`0.300m` delivery radius, no retries, fresh runtime traces, corrected
`fetch_to_pose` marker geometry, same-session visual confirmation, and the same
success contract. Offline, accelerated, direct-ball, pre-fix marker-mismatched,
or dashboard-observation results may guide research only.

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
sequence. Start from the May 31 corrected evidence floor: geometry-consistent
delivery marker, same-session onboard/topdown/world-stream video, no retries,
and `0.300m` delivery radius. Compare corrected Nav2/LLM-first fetch, current
object-centric fetch, contact-aware geometric shooter as physics-probe
evidence, receding-horizon contact MPC/object servo, ROS action/BT last-meter
owner, Nav2 reposition plus local fetch, passive guide/funnel, learned local
predictor/residual/maneuver proposer, portfolio supervisor/switcher, and
perception-first target-pose fetch.

Do not jump straight into tuning one path. First ground in branch/docs/artifacts,
then evaluate each path against the corrected calibrated fetch_to_pose contract,
planner-handoff route labels, saved-layout anchors, seeded random/generalization
gate, robot-owned contact requirement, hardware-transfer path, diagnosability,
and implementation cost. Prefer Nav2 and LLM-planner reuse before custom
contact development; make AI push-coast a fallback only when corrected evidence
proves a reproducible stage gap. Come back with a findings matrix, a recommended
primary path, fallback paths, no-go paths, and the next focused spike/gate plan.
```
