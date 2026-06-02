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
the local fetch subsystem computes the intended ball path and capture geometry,
Nav2 owns the corridor push after measured push-readiness is proven, and a thin
fetch adapter monitors corrected ball/target geometry, success, escape, stale
state, and replanning triggers. The runtime sequence is: planner route
classification, ball-target delivery line, capture-pose setup, push-readiness
gate, Nav2 corridor push, monitor classification, and route-back-to-setup on
setup or contact failure. One bounded terminal correction remains available only
from a clean near-contract terminal miss. Custom contact routines and AI
push-coast prediction remain fallback lanes that earn live authority only after
corrected Nav2-first evidence exposes a reproducible stage gap.

Scope correction: this milestone proves the planner-to-subsystem handoff plus
the bounded local fetch skill. The planner first classifies scenes as
`fetch_ready_local`, `nav2_reposition_first`, `scan_or_perceive_first`,
`recovery_or_reaim`, or `ambiguous_or_unsafe_no_go`. Only planner-approved
`fetch_ready_local` cases should be handed to `fetch_to_pose` and scored as
local fetch evidence.

Milestone acceptance:

1. Evidence is valid only when `geometry_consistency.pass=true`, the visible
   delivery marker matches `fetch_pose_world`,
   `model_provenance_valid=true`, the target model is
   `calibrated_golf_ball`, the delivery marker is
   `golf_ball_delivery_zone_marker`, and the run has same-session
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
7. The push-readiness gate is the core invariant: the robot must be behind the
   ball on the intended ball-target line, inside standoff, lateral-error, yaw,
   freshness, and corridor-validity bounds before Nav2 is allowed to push.
   Failures before that gate return to setup/reacquire rather than terminal
   correction.

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
2. Compute the ball-target delivery line and desired capture pose before
   contact; the robot must be behind the ball, square to the delivery line, and
   inside standoff, lateral-error, and yaw-error gates before Nav2 pushes.
3. Let Nav2 own long-haul navigation, repositioning, corridor approach, and
   bounded push paths whenever corrected evidence shows the ball remains inside
   the local envelope.
4. Keep the custom fetch adapter focused on intent translation, corrected
   geometry monitoring, escape/stale/success classification, and replanning or
   cancellation.
5. Keep AI push-coast/contact-stability as the fallback lane for reproducible
   gaps such as setup instability, first-contact drift, terminal stop-short, or
   re-aim selection.
6. Keep large world-model or VLA ideas as high-level planning, teacher-label,
   or offboard scoring tools until a smaller `tensorrt_int8`-compatible onboard
   predictor has shadow evidence.

## June 1, 2026 Calibrated-Ball Provenance Reset

The follow-up video review exposed a second evidence floor issue: some direct
`fetch_to_pose` runs used the legacy `frisbee_target_ball.sdf` target model.
That model is a large red sphere with radius `0.05m`; the calibrated golf-ball
model is `calibrated_golf_ball.sdf` with radius `0.021336m` and the rolling
resistance plugin. Direct fetch evidence after commit
`680e393 Use calibrated ball for fetch direct runs` must carry model provenance
fields before it supports architecture or promotion claims.

Evidence reset rules:

1. Treat pre-`680e393` direct `fetch_to_pose` repeatability evidence as
   diagnostic unless the artifact explicitly records
   `model_provenance_valid=true`, target model
   `calibrated_golf_ball`, and marker model
   `golf_ball_delivery_zone_marker`.
2. Keep dashboard CTA evidence separate: runs that used the dedicated golf-ball
   demo runner remain reviewable when the artifact records calibrated model,
   corrected marker geometry, and same-session video.
3. Use `scripts/fetch_model_provenance_audit.py` to inventory old artifacts.
   Missing provenance means `needs_recheck_missing_model_provenance`; legacy or
   mismatched model fields mean `quarantine_invalid_model_provenance`.
4. Rebuild the saved-layout ladder from the corrected runner:
   `zero`/`left05`/`right05` one-run, then `3/3`, then the seeded
   `6 x 1` gate, then a visual UAT package with browser-watchable onboard and
   context videos.

Corrected reference after the model fix:

- Fix commit: `680e393 Use calibrated ball for fetch direct runs`.
- Reference campaign: `live_calibrated_ball_right05_one_run_20260601`.
- Reference session: `20260601T000718616964Z`.
- Result: `fetch_to_pose_pass=true`, `geometry_consistency.pass=true`,
  `closest_approach_distance_m=0.136176`, and calibrated yellow ball visual
  evidence.

## June 1, 2026 Contact-Buffer Handoff Validation

The operator video review exposed a real stop-short behavior in the current
Nav2-first path. The fix-forward result keeps the architecture staged instead
of treating Nav2 as the sole contact owner.

Root causes and fixes:

1. The first-contact probe used `general_goal_checker` with a `0.25m`
   tolerance, so Nav2 could report success before measured ball contact. Commit
   `02a4c12 Fix Nav2 contact-buffer fetch handoff` adds a
   `corridor_push_goal_checker` with `0.035m` XY tolerance for corridor-push and
   contact-probe paths.
2. Commit `02a4c12` adds a static TF:
   `base_link -> jetbot/d415_camera_link/d415_depth`. This resolves the
   collision-monitor invalid-source stop in the failing run.
3. Fresh live evidence showed Nav2 can approach the ball-target corridor and
   then stop at a legitimate contact buffer. The adapter now treats a close,
   laterally aligned, no-object-motion Nav2 stop as
   `monitor_contact_buffer_handoff`, then starts the bounded deterministic
   first-contact servo.

Validated one-run evidence:

- Commit: `02a4c12 Fix Nav2 contact-buffer fetch handoff`.
- Campaign:
  `artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`.
- Session: `20260601T042808225875Z`.
- Visual UAT package:
  `artifacts/session/uat_contact_buffer_monitor_servo_zero_probe_20260601/fetch_visual_uat_package/scorecard.md`.
- Result: `fetch_to_pose_pass=true`, `geometry_consistency.pass=true`,
  `model_provenance_valid=true`, closest delivery distance `0.179959m` against
  the `0.300m` contract.
- Stage telemetry: Nav2 handed off at `robot_ball_distance_m=0.195671`; the
  deterministic contact servo confirmed `0.046811m` ball motion; the later
  corridor push ended with `monitor_success`.
- Browser-watchable videos:
  `artifacts/session/20260601T042808225875Z/visual/raw_camera_browser.mp4`,
  `artifacts/session/20260601T042808225875Z/visual/topdown_telemetry_browser.mp4`,
  and `artifacts/session/20260601T042808225875Z/visual/world_stream.mp4`.

Architecture update:

1. The planner classifies the scene and dispatches only `fetch_ready_local`
   cases to local fetch.
2. Nav2 owns corridor approach until the contact-buffer monitor fires or motion
   evidence is observed.
3. The deterministic contact servo owns first-contact confirmation after a
   close/aligned Nav2 stop.
4. Nav2 corridor push plus the fetch adapter own the delivery monitor, success,
   escape, stale-state, and unsafe-drift classification.
5. The AI/model lane remains a shadow handoff and maneuver-class proposer until
   saved-anchor and seeded-random scoring shows a reproducible benefit.

Evidence meaning: this is a valid one-run proof of the staged local fetch
sequence on `zero`. It repairs the specific "robot stops halfway" behavior.
Promotion still requires corrected `zero`/`left05`/`right05` one-run,
saved-layout `3/3`, the seeded `6 x 1` generalization gate, and a healthy
visual UAT package. The current package is watchable and operator-reviewed. The
visual observer summary reports incomplete health, so future UAT packages should
make the observer confirmation green alongside browser-watchable videos.

Saved-anchor requalification result, later June 1:

- Planner-handoff gate:
  `artifacts/session/live_planner_handoff_mixed_fetch_20260601/fetch_planner_handoff_gate/gate_summary.json`
  passed `5/5`; only the `fetch_ready_local` scene dispatches local fetch.
- LLM-shadow planner gate:
  `artifacts/session/live_planner_handoff_mixed_fetch_llm_shadow_20260601/fetch_planner_handoff_gate/gate_summary.json`
  recorded provider requests and used deterministic fallback because
  `OPENAI_API_KEY` was absent.
- `zero` one-run:
  `artifacts/session/live_contact_buffer_saved_anchor_zero_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  passed with `closest=0.152567m`.
- `left05` one-run:
  `artifacts/session/live_contact_buffer_saved_anchor_left05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  passed with `closest=0.266102m` and a `capture_entry_time_watch`.
- `right05` one-run:
  `artifacts/session/live_contact_buffer_saved_anchor_right05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  failed at `capture_entry_timeout` after pre-stage handoff.
- Stage audit:
  `artifacts/session/audit_contact_buffer_right05_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
  classifies the failure as `setup_capture_blocker` with next action
  `repair_setup_contact_before_guarded_live`.
- Browser UAT packages:
  `artifacts/session/uat_contact_buffer_saved_anchor_zero_one_run_20260601/fetch_visual_uat_package/scorecard.md`,
  `artifacts/session/uat_contact_buffer_saved_anchor_left05_one_run_20260601/fetch_visual_uat_package/scorecard.md`,
  and
  `artifacts/session/uat_contact_buffer_saved_anchor_right05_one_run_20260601/fetch_visual_uat_package/scorecard.md`.

Evidence meaning: the staged baseline clears centerline and left-offset one-run
anchors, while the right-offset setup/capture failure blocks saved-layout
promotion. The next milestone step is a broad stage-owner comparison before
targeted `right05` repair. Compare current staged Nav2/contact-buffer behavior
against the May 27 object-centric saved-anchor package, the corrected direct
`right05` reference, Nav2 corridor-push evidence, and prior acquisition or
goal-side setup evidence. Score setup/pre-capture, capture entry, first
contact, push/coast stability, terminal delivery, and visual clarity
separately. A targeted `right05` repair starts after the scorecard identifies
the lifecycle stage and prior behavior to reuse, restore, or replace.

## June 1, 2026 Clip-Review Algorithm Alignment

Operator clip review and telemetry agree on the current boundary. The centerline
case works because the robot starts with clean capture geometry: the ball stays
centered, the push line matches the target, and the ball reaches the delivery
circle. The off-axis `left05` and `right05` clips fail before terminal correction
is the main problem. Both show capture/handoff instability; `left05` pushes the
ball laterally out of the corridor, while `right05` under-moves the ball after an
unstable approach.

Evidence:

- Audit:
  `artifacts/session/audit_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
- Visual package:
  `artifacts/session/uat_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_visual_uat_package/scorecard.md`.
- Result: `zero` passed with `0.190334m` closest approach; `left05` failed at
  `0.656077m` with large lateral escape and capture yaw churn; `right05` failed
  at `0.461005m` with small ball motion and capture yaw churn.

Current algorithm:

1. Planner or LLM classifies whether the scene belongs to local fetch.
2. The local fetch planner computes the intended ball path: current ball pose to
   target circle.
3. The setup stage computes a capture pose behind the ball on that line and
   gets the robot there with Nav2 or a bounded deterministic local routine.
4. A geometry gate checks standoff, lateral offset, yaw error, target freshness,
   and ball-target corridor validity before contact.
5. Nav2 owns the corridor push after the handoff is clean.
6. The monitor classifies success, ball escape, stale state, unsafe drift,
   action abort, timeout, and near-contract terminal miss.
7. Terminal correction runs only when object motion already happened and the
   miss is small; setup/capture failures go back to capture planning.

Next engineering focus: implement and prove the setup/capture path as a first
class stage. Terminal correction remains useful, but it follows clean capture
geometry in the sequence.

## June 1, 2026 Simplified Stage-Boundary Update

The latest `ai_push_coast_servo_v1` full saved-layout one-run gate confirms the
architecture issue is stage ownership. Terminal correction follows clean setup;
an unstable push handoff routes back to setup/reacquire.
The correct high-level algorithm is straightforward:

1. The planner selects a feasible ball-target corridor or routes the scene to
   reposition, perceive, recover, or no-go.
2. The setup owner reaches a measured push-ready pose behind the ball.
3. The push-readiness gate proves standoff, lateral error, yaw error, target
   freshness, and corridor validity.
4. Nav2 owns the real-time corridor push.
5. The monitor classifies delivery, escape, stale state, unsafe drift, timeout,
   or action abort and reports the result back to the planner.

The missing invariant is push-readiness before contact. The current code became
too complex because it allowed unstable setup/capture states to leak into
contact and push logic, then added guards around downstream symptoms. The next
implementation step should reduce that complexity by routing every failed
push-readiness check back to setup/reacquire.

Latest evidence:

- Fix commit: `7c2b244 Guard fetch contact handoff geometry`.
- Full saved-layout gate:
  `artifacts/session/live_ai_push_coast_forward_contact_guard_saved_layout_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`.
- Stage audit:
  `artifacts/session/audit_ai_push_coast_forward_contact_guard_saved_layout_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
- Visual package:
  `artifacts/session/uat_ai_push_coast_forward_contact_guard_saved_layout_one_run_20260601/fetch_visual_uat_package/scorecard.md`.
- Result: `zero` passed with `0.230116m` closest approach. `left05` failed on
  `capture_entry_timeout`. `right05` failed as a setup/contact blocker with
  `0.557965m` closest approach, large capture yaw travel, and first-contact
  alignment watch flags.
- Targeted `right05` diagnostic:
  `artifacts/session/live_ai_push_coast_forward_contact_guard_right05_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`
  passed with `0.196206m` closest approach after forward-contact validation.

Evidence meaning: the guard fixes are useful, but the saved-anchor gate remains
blocked by setup/capture repeatability. Terminal correction resumes after
push-readiness is clean across `zero`, `left05`, and `right05`.

## June 1, 2026 Push-Readiness Gate Evidence

The push-readiness gate is now implemented as an explicit pre-dispatch
contract. Nav2 corridor push starts only after measured geometry proves the
robot is behind the ball on the ball-target line and inside standoff, lateral
error, yaw error, target freshness, and corridor-validity bounds.

Latest implementation and evidence:

- Gate commit: `d3d1550 Add fetch push-readiness gate`.
- Saved-anchor gate:
  `artifacts/session/live_push_readiness_gate_saved_anchor_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`.
- Corrected stage audit:
  `artifacts/session/audit_push_readiness_gate_saved_anchor_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
- Visual UAT package:
  `artifacts/session/uat_push_readiness_gate_saved_anchor_one_run_20260601/fetch_visual_uat_package/scorecard.md`.
- Result: `zero`, `left05`, and `right05` all failed the one-run saved-anchor
  gate under corrected geometry and calibrated model provenance.
- `zero` failed before Nav2 dispatch because standoff was too close:
  `0.114858m` against the current `0.120m` minimum.
- `left05` passed push-readiness narrowly with `19.612223deg` yaw error against
  the current `20.0deg` limit, then failed during Nav2 corridor push with a
  timeout and capture-yaw churn.
- `right05` failed before Nav2 dispatch because yaw error was out of bounds:
  `36.13447deg` against the current `20.0deg` limit.

Evidence meaning: the latest gate corrected the interpretation. The current
blocker is setup and first-contact readiness, with zero guarded-live terminal
correction candidates. The next engineering step is a setup/reacquire repair
that intentionally reaches a clean push-ready pose before dispatch. Threshold
tuning is allowed only after video and telemetry show the gate contract itself
matches the desired physical setup.

Implementation update: the runner now includes one bounded push-readiness setup
window before Nav2 corridor-push dispatch. The setup command uses the same
ball-target-line geometry as the gate, corrects toward a conservative
`0.24m` standoff, and caps local correction at `0.08m/s` linear and
`0.45rad/s` angular. A no-retry mission still gets only one setup window; if
the gate remains red, the run fails as setup/contact evidence. The next live
gate is the same saved-anchor one-run matrix, scored on whether `zero`,
`left05`, and `right05` reach push-readiness before Nav2 owns the corridor
push.

Live follow-up after the setup slice:

- Implementation commits: `0828b33 Add bounded push-readiness setup` and
  `3d5c73c Refine push-readiness backoff alignment`.
- Full saved-anchor gate:
  `artifacts/session/live_push_readiness_setup_backoff_saved_anchor_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`.
- Stage audit:
  `artifacts/session/audit_push_readiness_setup_backoff_saved_anchor_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
- Visual UAT package:
  `artifacts/session/uat_push_readiness_setup_backoff_saved_anchor_one_run_20260601/fetch_visual_uat_package/scorecard.md`.
- Result: `zero` passed at `0.110841m`; `right05` passed at `0.105228m`
  with capture-quality watch flags; `left05` failed before push-readiness on
  `capture_entry_timeout`.

Evidence meaning: the setup slice recovered centerline and right-offset
delivery, while left-offset capture-entry remains the saved-anchor blocker.
The next repair target is `left05` capture-entry convergence, measured before
Nav2 dispatch. Terminal correction and seeded random promotion remain paused.

June 2, 2026 update: the left-offset blocker is resolved at the stage-boundary
level. Capture-entry now has a fetch-specific handoff: once the robot satisfies
world-frame push-readiness on the ball-target line, with a tighter `0.55m`
capture-entry standoff cap, the runner holds and returns `handoff_kind =
fetch_push_ready`. The caller then starts `fetch_to_pose` corridor push directly
from capture-entry. This aligns the intermediate gate with the actual no-shoot
fetch contract and keeps the older ball-frame capture-entry band intact for
non-fetch capture flows.

Latest live evidence:

- Implementation: fetch push-readiness capture-entry handoff and corrected
  visual-package architecture-summary parsing.
- Targeted `left05` proof:
  `artifacts/session/live_fetch_push_ready_handoff_left05_one_run_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
- Full saved-anchor one-run:
  `artifacts/session/live_fetch_push_ready_handoff_saved_anchor_one_run_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
- Mobile visual UAT package:
  `artifacts/session/uat_fetch_push_ready_handoff_saved_anchor_one_run_20260602/fetch_visual_uat_package/scorecard.md`.
- Result: saved-anchor one-run is `3/3`. `zero` passed at `0.200915m` with
  `secure_capture`; `left05` passed at `0.148471m` with `fetch_push_ready`;
  `right05` passed at `0.169160m` with `fetch_push_ready`.
- Evidence status: approach rollups are clean for all three layouts, calibrated
  model provenance is valid, and the package is mobile-watchable. The package
  supports one-run UAT screening; promotion still requires saved-layout `3/3`
  and seeded random evidence.

June 2, 2026 repeatability update: the fetch-ready handoff plus setup/contact
repair cleared saved-layout repeatability. The first seeded random gate exposed
setup/capture generalization; the bounded setup repair then shifted the active
blocker to first-contact/release stability on case01.

Latest repeatability evidence:

- Corrected saved-layout `3/3` gate:
  `artifacts/session/live_fetch_setup_contact_repair_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
- Setup/contact audit:
  `artifacts/session/audit_fetch_setup_contact_repair_saved_anchor_3x_20260602/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
- Result: `zero`, `left05`, and `right05` passed promotion `3/3` with worst
  closest approaches `0.201194m`, `0.169541m`, and `0.136046m`.
- Handoff semantics: fetch mode now treats ball-frame capture-entry as a
  diagnostic signal and requires `fetch_push_readiness` before corridor-push
  dispatch. The capture-entry standoff cap is `0.58m`, tighter than the general
  corridor-push dispatch cap.
- Audit status: `stage_quality_green=true`; setup/contact blockers,
  setup/capture blockers, invalid geometry, and invalid model provenance are
  all `0`. `left05` keeps a `capture_entry_time_watch` because one run took
  `4.093s` to reach the gate.

Seeded evidence:

- Initial gate:
  `artifacts/session/live_fetch_setup_contact_repair_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
- Initial analyzer:
  `artifacts/session/evidence_fetch_setup_contact_repair_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
- Initial result: `ai_push_coast_servo_v1` shadow mode passed `4/6`. `case01`
  (`f0.627`, `l-0.121`) and `case06` (`f0.502`, `l-0.174`) reproduced
  `capture_entry_timeout` before corridor-push handoff.
- Frozen layouts:
  `artifacts/session/live_fetch_setup_contact_repair_seeded_gate_20260602/fetch_generalization_gate/frozen_failure_layouts`.
- Bounded setup repair: large lateral setup error now selects a bounded
  recenter arc, uses a closer lateral setup standoff, and extends
  capture-entry time only while `fetch_push_readiness` score improves.
- Frozen repair proof: targeted one-run gates for `case01` and `case06` both
  passed with `handoff_kind=fetch_push_ready`.
  - `case01`: `artifacts/session/live_fetch_frozen_case01_setup_capture_bounded_setup_v2_20260602/gather_mission_repeatability/campaign_run_summary.json`
  - `case06`: `artifacts/session/live_fetch_frozen_case06_setup_capture_bounded_setup_v2_20260602/gather_mission_repeatability/campaign_run_summary.json`
- Clean seeded rerun:
  `artifacts/session/live_fetch_setup_capture_bounded_setup_v2_seeded_gate_clean_20260602/fetch_generalization_gate/gate_summary.json`.
- Clean seeded analyzer:
  `artifacts/session/evidence_fetch_setup_capture_bounded_setup_v2_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
- Current result: `5/6` initial pass, with `0` reproduced failures. `case01`
  failed once after `fetch_push_ready` with
  `missed_delivery_radius_after_push_readiness_gate_failed`; its repro passed.
  The analyzer marks this as a non-repro watchlist and a guarded-live terminal
  candidate.
- Case01 repeatability probe:
  `artifacts/session/live_fetch_case01_bounded_setup_v2_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
  Result: `2/3` passed. The remaining failure is
  `missing_first_contact_alignment` / `release_roll_away`.

Interpretation: setup/capture is no longer the primary blocker for the first
seeded gate. The active blocker is first-contact/release stability on the
high-forward left-lateral case. Terminal correction remains a candidate, but
the next repair should first stabilize first-contact alignment and release
before promotion.

Next sequence: freeze the new case01 first-contact/release failure as a named
watchlist case, repair first-contact alignment and release stability, rerun
case01 `3/3`, then rerun seeded random `6 x 1`.

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

Use the existing object-centric and AI push-coast work as implementation
infrastructure, with the corrected Nav2/LLM-first baseline as the immediate
center of gravity:

1. keep the planner-handoff gate green before local fetch scoring
2. build a stage-owner comparison scorecard across current staged
   Nav2/contact-buffer behavior, May 27 object-centric fetch, Nav2
   corridor-push, corrected direct `right05`, and prior acquisition or
   goal-side setup evidence
3. make setup/capture geometry explicit: delivery line, capture pose, standoff,
   lateral error, yaw error, and handoff gate
4. run missing canonical one-run probes only to fill comparison gaps
5. dispatch local `fetch_to_pose` only for planner-approved
   `fetch_ready_local` scenes
6. select the next targeted fix by stage-owner evidence, then repair the chosen
   lifecycle stage
7. let the AI push-coast lane score stage gaps in shadow mode from corrected
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
