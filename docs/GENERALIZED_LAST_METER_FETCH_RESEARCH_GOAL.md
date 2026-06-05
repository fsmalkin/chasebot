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
repair cleared saved-layout repeatability. Seeded random gates exposed
setup/capture and near-margin readiness gaps; bounded setup, near-margin
readiness, and contact-buffer standoff repairs now clear the first seeded
generalization gate in guarded-live mode.

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
- Bounded setup rerun result: `5/6` initial pass, with `0` reproduced
  failures. `case01` failed once after `fetch_push_ready`; its repro passed.
- Case01 near-margin repair: `ball_already_at_delivery_margin` is now a
  non-blocking readiness note when setup geometry is otherwise ready, and the
  contact-buffer standoff floor is `0.10m` for short re-push geometry.
- Case01 repeatability proof:
  `artifacts/session/live_fetch_case01_near_margin_gate_v1_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
  Result: `3/3` passed with `handoff_kind=fetch_push_ready`.
- Latest seeded gate after near-margin and standoff repairs:
  `artifacts/session/live_fetch_relaxed_standoff_v1_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
- Latest seeded analyzer:
  `artifacts/session/evidence_fetch_relaxed_standoff_v1_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
  Earlier result: `5/6` initial pass, `1` non-repro failure, `0` reproduced
  failures. `case04` failed once, then passed repro.
- Case04 targeted repeatability:
  `artifacts/session/live_fetch_case04_relaxed_standoff_v1_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
  Result: delivery passed `3/3`; approach-quality diagnostics still reported
  `missing_first_contact_alignment` in `2/3`, so this remains a contact-quality
  backlog item rather than a delivery blocker.
- Clean shadow seeded gate:
  `artifacts/session/live_fetch_near_margin_case04_repeat_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
- Clean shadow seeded analyzer:
  `artifacts/session/evidence_fetch_near_margin_case04_repeat_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
  Result: `6/6`, `0` reproduced failures.
- Guarded-live `right05` terminal probe:
  `artifacts/session/live_fetch_guarded_live_terminal_right05_probe_20260602/gather_mission_repeatability/campaign_run_summary.json`.
  Result: `1/1` delivery pass with clean approach-side diagnostics.
- Guarded-live saved-layout `3/3` gate:
  `artifacts/session/live_fetch_guarded_live_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
  Result: `zero`, `left05`, and `right05` all passed promotion `3/3`.
- Guarded-live seeded gate:
  `artifacts/session/live_fetch_guarded_live_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
- Guarded-live seeded analyzer:
  `artifacts/session/evidence_fetch_guarded_live_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
  Result: `6/6`, `0` reproduced failures,
  `milestone_interpretation=guarded_live_seeded_gate_promotion_ready`, and
  `promotion_evidence=True`.
- Browser-watchable UAT package:
  `artifacts/session/uat_fetch_guarded_live_seeded_case04_20260602/fetch_visual_uat_package/scorecard.md`.
  Result: package pass `True`, mobile-watchable `True`, onboard-camera
  watchable `True`, and same-session local fetch visual confirmation `True`.
- Superseded case01 probe:
  `artifacts/session/live_fetch_case01_bounded_setup_v2_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
  Earlier result: `2/3`; this drove the near-margin repair above.

Interpretation: Generalized Fetch-To-Pose v1 is promotion-ready at the
contract-evidence level: saved anchors are green, guarded-live seeded random is
green, calibrated model provenance is valid, and the dashboard reports status
`ok`. Case04 and case01 contact-quality flags stay in the backlog for smoother
capture/contact, but they no longer block the delivery contract.

Next sequence: use operator clip review on the browser-watchable UAT package,
then decide whether the next engineering slice is smoother contact quality or
broader planner-routed scenario coverage.

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

June 3, 2026 fresh-session route-owner evidence update: the planner-routed
moonshot now has a corrected mixed-scene UAT harness. The first shared-session
six-run replay showed why visual evidence must be isolated per row: one mission
detached from the dashboard visual session, and one `nav2_reposition_first`
miss cleared when rerun with clean evidence binding. The fixed batch
runner starts a fresh calibrated dashboard session per selected scene, passes an
`--expected-session-id` into the mission runner, stops the sim before packaging,
and stores package-local keyframe review sheets.

Corrected evidence:

- six-scene analyzer:
  `artifacts/session/route_uat_seed20260608_six_fresh_sessions_20260603/fetch_planner_route_uat_analyzer/scorecard.md`
- covered executable route owners:
  two `fetch_ready_local`, two `nav2_reposition_first`, and two
  `recovery_or_reaim` scenes from seed `20260608`
- result:
  all six deliveries passed with same-session browser-watchable visual packages;
  closest approach ranged from `0.194811m` to `0.197835m` against the
  `0.300m` contract
- interpretation:
  route-owner UAT is green, `promotion_evidence=false`, and contact quality is
  still a `watch` item. Sequence-based visual review agrees with the geometry:
  the ball reaches the circle, while pre-contact lateral/yaw posture and
  recovery first-contact alignment need smoothing.

Next focused slice: keep the planner/LLM route split intact, keep Nav2 as the
setup/reposition owner where fresh evidence supports it, and add route-quality
scoring plus pre-contact smoothing before another broad randomized batch. Treat
AI/local learned control as a proposer for reproducible stage gaps, especially
where route-quality scoring shows deterministic setup or recovery reaching
first contact outside the clean envelope.

June 3, 2026 route-quality scorer update: the planner-routed moonshot now
scores route quality before execution and validates predicted quality after
execution. The dry planner gate
`artifacts/session/dev_route_quality_gate_seed20260613_20260603/fetch_planner_handoff_gate/gate_summary.json`
produced route-quality scores across all five route labels. The roughest live
executable replay
`artifacts/session/live_route_quality_roughest_fresh_replay_20260603/fetch_planner_route_replay_batch/scorecard.md`
selected `recovery_or_reaim` risk `high`, `nav2_reposition_first` risk
`medium`, and `fetch_ready_local` risk `low`. All three delivered inside the
`0.300m` contract with same-session visual packages. The combined analyzer
`artifacts/session/route_uat_route_quality_roughest_live_20260603/fetch_planner_route_uat_analyzer/scorecard.md`
keeps contact quality at `watch`, first-contact blockers at `0`, and promotion
evidence at `false`.

Research interpretation: route ownership now has supporting evidence across
bounded local-random executable cases. The first June 3 roughest selector exposed
recovery and fetch-ready first-contact smoothness as the immediate control gaps;
final-reaim repairs then cleared first-contact flags across the roughest
executable trio for seed `20260613`. A second planner seed, `20260614`, routed
`15/15` correctly and passed the roughest executable trio with no first-contact
flags:
`artifacts/session/route_uat_contact_final_reaim_seed20260614_roughest_trio_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
Treat this as breadth-oriented visual UAT with `promotion_evidence=false`;
canonical saved layouts and seeded-random gates remain the milestone proof.

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

June 4, 2026 saved-anchor route-owner update: the planner-routed moonshot now
has a corrected one-run saved-anchor visual proof. The saved-anchor handoff
gate passed `3/3` after the planner guard stopped treating exact `0.0`
lateral/yaw values as missing:
`artifacts/session/dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604/fetch_planner_handoff_gate/scorecard.md`.
The live replay passed `3/3` with browser-watchable visual packages:
`artifacts/session/live_planner_saved_anchor_replay_zero_numeric_fix_8881_20260604/fetch_planner_route_replay_batch/scorecard.md`.
Use this as current route-owner UAT evidence: `zero` is `fetch_ready_local`;
`left05` and `right05` are `recovery_or_reaim`; all three delivered inside the
`0.300m` contract with sequence-reviewed onboard/topdown proof.

June 4, 2026 saved-anchor repeatability update: the planner-routed stack passed
the saved-anchor `3/3` rung with nine fresh-dashboard runs:
`artifacts/session/analysis_planner_saved_anchor_repeat3x_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The analyzer reports `saved_anchor_repeatability_green`, `9/9` live mission
passes, `9/9` mobile/onboard visual packages, `0` first-contact blockers, clean
setup/contact quality, and closest approaches from `0.194m` to `0.198m`. The
visual review montage is
`artifacts/session/analysis_planner_saved_anchor_repeat3x_20260604/fetch_planner_route_uat_analyzer/saved_anchor_repeat3x_contact_sheet_montage.png`.
The seeded random gate is now the remaining promotion-grade proof for the
planner-routed architecture.

June 4, 2026 seed `20260627` randomized route-owner update: the planner-routed
stack passed a fresh mixed random handoff gate with `30/30` route decisions and
`0` wrong fetch-ready dispatches:
`artifacts/session/dev_route_quality_gate_seed20260627_post_repeatability_30case_20260604/fetch_planner_handoff_gate/scorecard.md`.
The executable replay slice passed `6/6` with fresh dashboard sessions: two
`fetch_ready_local`, two `nav2_reposition_first`, and two `recovery_or_reaim`
rows all delivered inside the `0.300m` contract:
`artifacts/session/analysis_route_quality_seed20260627_exec6_post_repeatability_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
Execution, setup, and contact quality were clean; first-contact blockers were
`0`; closest approaches ranged from `0.194m` to `0.196m`. Sequence review is
captured in:
`artifacts/session/analysis_route_quality_seed20260627_exec6_post_repeatability_20260604/fetch_planner_route_uat_analyzer/seed20260627_exec6_keyframe_montage.png`.
Use this as green randomized route-owner visual UAT. Promotion remains pending
until the planner-routed seeded generalization gate carries canonical `6 x 1`
semantics.

June 4, 2026 planner-routed seeded gate surface update:
`scripts/fetch_planner_seeded_generalization_gate.py` now provides the parent
gate for the next promotion rung. It runs the mixed planner handoff gate,
materializes the executable route replay batch, runs the route UAT analyzer
after live mission/visual artifacts exist, and sets `promotion_evidence=true`
only when the live surface is clean. Dry-run
`dev_planner_seeded_generalization_gate_dry_run_20260604` passed with `30/30`
planner decisions and six selected executable rows:
`artifacts/session/dev_planner_seeded_generalization_gate_dry_run_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The next evidence step is the same wrapper in live fresh-dashboard mode.

Live wrapper attempt
`live_planner_seeded_generalization_gate_seed20260627_20260604` reached the
promotion gate surface and failed before mission execution:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260627_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner child passed `30/30`; replay stopped on
`fresh_dashboard_session_start_failed` while the first fresh session remained in
`environment_starting`. Classify this as infrastructure evidence; fetch-control
scoring remains unattempted. The architecture decision remains unchanged until
the same gate runs through live mission and visual packages.

June 4, 2026 visual-evidence startup fix and promotion-green rerun:
`allow_operator_view_degraded` previously set `operator_view_required=false`,
and the dashboard interpreted that as permission to skip every visual surface.
Replay batches now request `visual_evidence_required=true` whenever visual
packages are enabled, so optional/degraded Xpra no longer disables
`world_stream_controller.py` or `visual_demo_observer.py`. The fixed live parent
gate
`artifacts/session/live_planner_seeded_generalization_gate_full_visual_fix_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`
passed with `promotion_evidence=true`. Planner routing was `30/30` with `0`
wrong fetch-ready dispatches; live replay was `6/6` missions and `6/6`
browser-watchable visual packages across two `fetch_ready_local`, two
`nav2_reposition_first`, and two `recovery_or_reaim` rows; the analyzer reported
clean execution/setup/contact quality and `0` first-contact blockers. The six
raw/topdown keyframe sheets were reviewed across setup, contact, push, and
terminal arrival and agree with telemetry. This is the current promotion-grade
sim evidence for the planner-routed architecture. The next research step is
seed breadth and hardware-transfer planning.

June 4, 2026 second-seed breadth update: seed `20260628` now gives the same
planner-routed parent gate a second promotion-green randomized result:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
Planner routing passed `30/30` with `0` wrong fetch-ready dispatches across
`fetch_ready_local`, `nav2_reposition_first`, `recovery_or_reaim`,
`scan_or_perceive_first`, and `ambiguous_or_unsafe_no_go`. The live replay
passed `6/6` executable rows and `6/6` browser-watchable visual packages across
two local fetch, two Nav2-first, and two recovery/re-aim cases:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604_replay/fetch_planner_route_replay_batch/scorecard.md`.
The analyzer is clean for execution, setup, and contact quality with `0`
first-contact blockers:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604_analysis/fetch_planner_route_uat_analyzer/scorecard.md`.
The first seed `20260628` attempt failed before mission launch because Docker
bridge subnet space was exhausted; cleanup removed unused Chasecar dashboard and
gate networks, and the rerun is the behavior evidence. The visual package now
writes contact sheets beside each visual session, which keeps Windows package
paths short and sequence review browser-linkable.

June 4, 2026 recovery/re-aim route-boundary update: the same seed `20260627`
later exposed a cleaner architecture lesson. A `recovery_or_reaim` route should
use the local bounded recovery routine from the generated robot pose, while
`nav2_reposition_first` remains the owner for real Nav2 setup before local
fetch. The exact `seed20260627_scene04_recovery_or_reaim` row passed after the
boundary correction:
`artifacts/session/live_recovery_reaim_local_setup_scene04_20260604/fetch_planner_route_replay_batch/scorecard.md`.
Visual UAT package:
`artifacts/session/live_recovery_reaim_local_setup_scene04_20260604_seed20260627_scene04_recovery_or_reaim/fetch_visual_uat_package/scorecard.md`.
The run delivered inside the `0.300m` contract at `0.193732m`, with clean
first-contact quality, stable contact approach, and
`nav2_reposition_before_fetch=false`. Treat this as targeted proof for the
stage boundary, then rerun the full planner-routed seeded gate for promotion
evidence.

June 4, 2026 readyfix evidence update: the same route-owner architecture now
has a clean representative visual package and a separate mission-only fallback
proof. Planner gate
`live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_planner`
passed `30/30` with `0` wrong fetch-ready dispatches. Mission replay
`live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_replay`
passed `6/6`; it included a Nav2-first row where Nav2 aborted before contact,
ball motion stayed `0.0m`, bounded local recovery took over, and delivery
finished at `0.197m`. Visual replay
`live_planner_seeded_generalization_gate_visual_recheck_20260604` passed `4/4`
with browser-watchable packages and frame-sequence review across recovery,
fetch-ready, and Nav2-first rows. This supports the planner-gated stack and
the Nav2/local handoff boundary. It remains UAT evidence because the parent
seeded gate still needs a canonical live visual run with `promotion_evidence=true`.

The same readyfix hardened stale-model cleanup so a Gazebo remove-service
timeout records `rc=124` instead of terminating the fetch runner before mission
dispatch.

June 4, 2026 infrastructure note: two failed live attempts on stale dashboard
ports reproduced truth-probe startup failures before mission dispatch. The
route replay harness now preserves those as dashboard-start failures and returns
fast on `environment_state=error`; the dashboard truth probe allows cold Gazebo
starts before declaring failure. Future truth/visual startup failures belong to
evidence-collection infrastructure triage before fetch-control interpretation.

June 4, 2026 third-seed and regression-manifest update: seed `20260629`
converted the next research question from architecture selection to regression
preservation. The seed first exposed a clean pre-contact Nav2 setup abort on
`seed20260629_scene01_nav2_reposition_first`; the repaired fallback then
delivered that row inside the contract. The same seed exposed a high-debt
`recovery_or_reaim` duration boundary on `seed20260629_scene05_recovery_or_reaim`;
the longer bounded recovery window repaired that row while preserving the
delivery stop. The final parent gate is green at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260629_boundary_repair_full_visual_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The regression manifest is green at
`artifacts/session/analysis_planner_moonshot_regression_set_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
It verifies saved anchors, seeds `20260627`, `20260628`, and `20260629`, and
the two repaired boundary rows. The recommended architecture remains
planner-routed route ownership with Nav2, bounded local recovery/fetch, and
visual keyframe review as a gate; alternatives stay alive as fallback lanes
when this manifest or broader UAT exposes a reproducible stage gap.

June 4, 2026 broad-UAT recovery repair update: the breadth queue selected seed
`20260630` as the next rough randomized route-owner package after the regression
manifest:
`artifacts/session/analysis_planner_moonshot_breadth_queue_20260604/fetch_moonshot_breadth_queue/scorecard.md`.
The first live row, `seed20260630_scene28_recovery_or_reaim`, failed for a
true setup/first-contact reason: the robot entered recovery yaw-hold, first
contact was missing, the ball start/end poses matched, and visual keyframe
review agreed with telemetry. The repair added a narrow recovery line-acquire
yaw crawl, preserving the staged architecture and direct visual review. The
targeted repair replay passed at
`artifacts/session/live_seed20260630_scene28_recovery_crawl_repair_20260604/fetch_planner_route_replay_batch/scorecard.md`;
the mission delivered to `0.198m` closest approach with clean first-contact
flags and browser-watchable onboard/topdown proof. The full seed `20260630`
breadth rerun passed at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260630_recovery_crawl_full_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
It delivered `30/30` planner routing, `wrong_fetch=0`, `6/6` executable
missions, `6/6` visual packages, clean analyzer status, and live closest
approach from `0.194m` to `0.198m`. The next evidence step is another rough
seed or a hardware-transfer packaging pass, while the regression manifest stays
the preservation bar.

June 4, 2026 second rough-seed breadth update: seed `20260631` passed the same
post-repair route-owner gate at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260631_breadth_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
It delivered `30/30` planner routing, `wrong_fetch=0`, `6/6` executable
missions, `6/6` visual packages, clean analyzer status, and closest approach
from `0.194m` to `0.197m`. Visual keyframe review checked both high-risk
recovery rows, both Nav2-first rows, and a fetch-ready row.

June 4, 2026 five-seed preservation update: the regression manifest now
includes seeds `20260627` through `20260631` by default:
`artifacts/session/analysis_planner_moonshot_regression_set_five_seed_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
It is green with `5/5` seeded gates, `30/30` live seeded missions, `30/30`
visual packages, and the repaired `20260629` boundary rows preserved. Continue
the moonshot from this broader preservation bar.

June 4, 2026 six-seed architecture checkpoint: seed `20260632` passed the next
rough breadth gate at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260632_breadth_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
It delivered `30/30` planner routing, `wrong_fetch=0`, `6/6` executable
missions, `6/6` visual packages, clean analyzer status, first-contact blockers
`0`, and closest approach from `0.194m` to `0.198m`. Visual keyframe review
checked the six selected executable rows and matched the telemetry.

The current architecture decision is to continue planner-routed route ownership.
The strongest current path is
`scenario planner -> route family -> forward-only setup/recovery/local fetch ->
Nav2 where useful -> visual and telemetry evidence`. Pure Nav2 remains a
reposition/corridor owner, learned local control remains a later fallback for
reproducible contact instability, and larger LLM/VLA/world-model work remains a
planner, teacher-label, or scoring layer until an onboard-safe executor earns
authority. The six-seed manifest is the current preservation bar:
`artifacts/session/analysis_planner_moonshot_regression_set_six_seed_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
It is green with seeds `20260627` through `20260632`, seeded gates `6/6`, live
seeded missions `36/36`, and visual packages `36/36`.

June 4, 2026 seven-seed breadth update: seed `20260633` passed the next rough
breadth gate at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260633_breadth_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
It delivered `30/30` planner routing, `wrong_fetch=0`, `6/6` executable
missions, `6/6` visual packages, clean analyzer status, first-contact blockers
`0`, and closest approach from `0.193m` to `0.196m`. This seed is useful
because the planner saw `10` no-go classifications and `4` scan/perception
classifications while the six selected executable rows were all predicted as
contact-quality watches and then cleared live execution.

The seven-seed manifest is now the current preservation bar:
`artifacts/session/analysis_planner_moonshot_regression_set_seven_seed_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
It is green with seeds `20260627` through `20260633`, seeded gates `7/7`, live
seeded missions `42/42`, and visual packages `42/42`. The architecture remains
planner-routed route ownership.

June 5, 2026 seed20260635/preflight preservation update: the current manifest is
green at
`artifacts/session/analysis_planner_moonshot_regression_set_seed20260635_preflight_20260605/fetch_moonshot_regression_manifest/scorecard.md`.
It preserves seeds `20260627` through `20260633` plus seed `20260635`, seeded
gates `8/8`, live seeded missions `48/48`, visual packages `48/48`, the two
seed `20260629` boundary repairs, and the seed `20260635` scene03
base-controller preflight. This is the active preservation bar for future
planner-routed moonshots and hardware-transfer packaging.

June 4 route-only proof now covers the planner-owned non-fetch families:
`artifacts/session/live_planner_only_route_proof_seed20260633_20260604/fetch_planner_route_replay_batch/scorecard.md`.
The batch replayed one `scan_or_perceive_first` row and one
`ambiguous_or_unsafe_no_go` row from the seed `20260633` planner child. Both
rows passed route-only proof, produced browser-watchable visual packages,
withheld local fetch, and sampled `59` stopped-scene frames with measured robot
motion `0.000m` and ball motion `0.000m`. This is supporting route-family UAT
with `promotion_evidence=false`; the next useful architecture expansion is a
mixed route-family UAT batch over additional seeds before another local
contact-control moonshot.

June 4 mixed route-family UAT now validates the full planner handoff surface in
one live batch:
`artifacts/session/analysis_mixed_route_family_uat_seed20260633_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The replay selected one seed `20260633` row per route family from
`fetch_ready_local`, `recovery_or_reaim`, `scan_or_perceive_first`,
`ambiguous_or_unsafe_no_go`, and `nav2_reposition_first`. It passed mixed route
contracts `5/5`, visual packages `5/5`, executable deliveries `3/3`,
route-only proofs `2/2`, clean execution/setup/contact analysis, and
first-contact blockers `0`. The executable rows delivered at closest approach
`0.195m..0.197m`; the planner-only rows withheld local fetch and passed
`planner_route_only_pass=true`. This supports the current architecture choice:
planner route ownership first, deterministic subsystem execution second, and
contact-control changes only after a larger mixed-family breadth replay.

The same seed `20260633` now has a two-per-route mixed-family UAT pass:
`artifacts/session/analysis_mixed_route_family_2per_route_seed20260633_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The resumed replay selected `10` rows, skipped the existing `5` green rows,
and added the second sample for each route family. It passed route contracts
`10/10`, visual packages `10/10`, executable deliveries `6/6`, route-only
proofs `4/4`, clean analyzer status, and first-contact blockers `0`.
Executable closest approach stayed within `0.194m..0.197m`. This moves the
next research question from this seed to either a second rough mixed-family
seed or hardware-transfer packaging.

The second rough mixed-family seed is now green:
`artifacts/session/analysis_mixed_route_family_2per_route_seed20260632_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The replay selected `10` fresh rows from seed `20260632`, with two live samples
for each route family. It passed route contracts `10/10`, visual packages
`10/10`, executable deliveries `6/6`, route-only proofs `4/4`, clean
execution/setup/contact analysis, and first-contact blockers `0`. Raw-camera
plus topdown frame-sequence review matched the telemetry: executable rows
showed setup, contact, push, and visible delivery, while planner-only rows
withheld local fetch and stayed stopped. This strengthens the route-gated
architecture decision. The next research gate should deliberately stress hard
scenario geometry, especially opposite-side-of-circle starts, large setup
angles, forward-only setup pressure, and unknown-scene refusal boundaries.
Alternative architectures remain reserve lanes for reproduced stage gaps.

`hard_mixed_fetch_planner_v1` is now a named hard route-family gate:
`artifacts/session/analysis_hard_mixed_route_family_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
It deliberately covers wide-angle direct local fetch, opposite-side
Nav2-first setup, large-angle recovery/re-aim, scan/defer, and safe no-go with
two rows per route family. The live matrix passed route contracts `10/10`,
visual packages `10/10`, executable deliveries `6/6`, route-only proofs
`4/4`, clean execution/setup/contact analysis, and first-contact blockers
`0`. Raw-camera plus topdown sequence review matched the telemetry. This
evidence further supports the planner-gated architecture and reduces the need
for a broad architecture pause.

LLM-shadow route classification is now green on the hard matrix:
`artifacts/session/shadow_llm_hard_mixed_fetch_planner_v1_20260604/fetch_planner_handoff_gate/scorecard.md`.
The real provider returned `ok` for all ten scenes, agreed with the
deterministic guard `10/10`, produced zero wrong fetch-ready dispatches, and set
`llm_shadow_ready=True`. This is shadow-only high-level route evidence. Live
execution still belongs to deterministic guards and bounded route owners. The
rough-seed rollup is also green at
`artifacts/session/analysis_llm_shadow_hard_plus_rough_mixed_20260604/fetch_planner_llm_shadow_evidence/scorecard.md`:
hard matrix plus seeds `20260632` and `20260633`, `70/70` provider-ok route
classifications, `70/70` guard agreement, and wrong fetch-ready dispatches `0`.
The full hard-plus-seven-seed manifest is now green at
`artifacts/session/analysis_llm_shadow_hard_plus_seven_seed_manifest_20260604/fetch_planner_llm_shadow_evidence/scorecard.md`:
hard matrix plus seeds `20260627` through `20260633`, `220/220` provider-ok
classifications, `220/220` guard agreement, route pass/fail `220/0`, and wrong
fetch-ready dispatches `0`. Seed `20260630` had one transient read timeout that
cleared on rerun. The next research step is defining the supervised-live
route-selection threshold and hardware-transfer plan.

The first supervised route guard proof is now green:
`artifacts/session/supervised_llm_hard_mixed_fetch_planner_v1_20260604/fetch_planner_handoff_gate/scorecard.md`.
`llm_supervised_guarded` accepted the hard-matrix model route output `10/10`,
vetoed `0`, kept guard agreement `10/10`, and kept wrong fetch-ready dispatches
at `0`. This establishes the route-level acceptance policy in dry mode before
any live LLM route authority.

The supervised hard-plus-seven-seed manifest now extends that proof:
`artifacts/session/analysis_supervised_llm_hard_plus_seven_seed_manifest_20260604/fetch_planner_llm_supervised_evidence/scorecard.md`.
Across `220` provider-backed cases, route pass/fail was `220/0`, provider `ok`
was `220/220`, guard agreement was `220/220`, and wrong fetch-ready dispatches
were `0`. The guard accepted `217` proposals and vetoed `3` confidence-only
proposals into deterministic fallback. The research interpretation is guarded
fallback readiness for high-level route choice; physical fetch generalization
still depends on live route-owner visual UAT and canonical promotion gates.

The first supervised hard route-owner visual UAT is now green:
`artifacts/session/analysis_supervised_hard_mixed_route_family_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The replay used the supervised hard planner gate, passed `10/10` route
contracts, produced `10/10` visual packages, delivered `6/6` executable routes,
and passed `4/4` route-only no-fetch proofs. This strengthens the current
architecture path: LLM-level routing plus deterministic guards can feed live
route owners, while broader live batches and canonical gates remain open.

June 5 roughest-seed authority and contact-watch update: seed `20260634`
extends breadth with a roughest-order live replay:
`artifacts/session/live_supervised_planner_seeded_generalization_gate_seed20260634_roughest_provider_reuse_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
It passed the visual UAT surface with `6/6` deliveries and `6/6` visual
packages across two recovery, two Nav2-first, and two fetch-ready rows. Visual
frame review agreed with telemetry. Recovery and Nav2 rows stayed clean; the
direct fetch-ready rows delivered near `0.198m` and kept
`ball_lateral_knock_away` / `contact_trajectory_angle_error` watches.

The provider-backed reuse pass now closes the credential gap:
`artifacts/session/live_supervised_planner_seeded_generalization_gate_seed20260634_roughest_provider_reuse_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The provider returned `ok` for all `30` generated scenes, guard agreement stayed
`30/30`, wrong fetch dispatches stayed `0`, and the parent scorecard reports
`planner_authority_ready=true`. Strict all-accepted authority remains false
because one `scan_or_perceive_first` row used deterministic fallback for
`confidence_below_threshold`; this is guarded fallback authority rather than a
route-disagreement failure. The architecture direction remains planner-gated
route ownership with deterministic execution; the next focused control work is
direct local-fetch contact smoothness, with hardware-transfer planning in
parallel.

June 5 targeted contact-smoothing recheck: the direct local-fetch watch rows now
have a clean repair proof:
`artifacts/session/live_fetch_ready_contact_smoothing_recheck_seed20260634_20260605/fetch_planner_route_uat_analyzer/scorecard.md`.
Planner-route defaults tighten `fetch_ready_local` contact readiness to
`0.024m` only when route-quality metadata requests `pre_contact_smoothing`.
Scene04 and scene28 reran with browser-watchable onboard/topdown proof and
cleared execution, setup, contact, and first-contact watches. Max ball lateral
error fell to `0.000224m` and `0.000273m`, respectively, and contact-angle
error fell to near `0deg`.

The full rough executable route-family preservation rerun is now green:
`artifacts/session/live_fetch_ready_contact_smoothing_full_rough_analysis_seed20260634_20260605/fetch_planner_route_uat_analyzer/scorecard.md`.
It delivered `6/6` missions with `6/6` visual packages across recovery/re-aim,
Nav2-first, and fetch-ready rows, and the analyzer reports clean execution,
setup, and contact quality with `0` first-contact blockers. This preserves the
rough route-owner UAT lane with `promotion_evidence=false`; the promotion lane
should refresh through the canonical seeded/saved-layout gates with smoothing
active.

June 5 supervised seeded promotion refresh: seed `20260635` now carries the
current canonical promotion proof for the planner-routed architecture:
`artifacts/session/live_supervised_planner_seeded_generalization_gate_seed20260635_smoothing_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The provider-backed planner child routed `30/30` generated scenes with provider
`ok=30/30`, guard agreement `30/30`, wrong fetch dispatches `0`, and one
confidence-only deterministic fallback. The executable replay selected two
`nav2_reposition_first`, two `recovery_or_reaim`, and two `fetch_ready_local`
rows; all six delivered into the `0.300m` contract with browser-watchable
packages, clean execution/setup/contact analysis, and first-contact blockers
`0`. Closest approach ranged from `0.194m` to `0.197m`.

The refresh also fixed a diagnostic gap. Scene03 first failed as a no-motion
executor run: commands were published, but visual and telemetry evidence showed
the robot and ball stayed fixed because the base controller was unavailable.
Executable fetch now records a base-controller preflight through
`/controller_manager/list_controllers` and fails before scoring if
`jetbot_base_controller` is not active. The repaired scene03 session
`20260605T045353381785Z` confirmed active control, observed first contact at
`27.631s`, moved the ball roughly `0.46m`, and delivered at `0.197m`.

Interpretation: the planner-routed route-owner stack is simulation
promotion-green again with current smoothing and controller preflight active.
The hardware-transfer readiness package is now green:
`artifacts/session/analysis_fetch_hardware_transfer_readiness_20260605/fetch_hardware_transfer_readiness/scorecard.md`.
It reports `hardware_transfer_ready=true`, `hardware_proven=false`, and
`promotion_evidence=false` after checking the seed20260635/preflight
preservation bar, dashboard UAT package, `robot_fidelity_orin` contract,
`tensorrt_int8` runtime documentation, and controller-preflight evidence. The
next milestone work is a robot-side rehearsal that records base-controller
preflight, mission verdict, onboard raw-camera video, topdown/world context,
frame-sequence review, and TensorRT/runtime provenance.

The robot-side rehearsal now has a generated plan artifact:
`artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/fetch_hardware_rehearsal_plan/scorecard.md`.
It defines the next sequence as runtime stack smoke, saved-anchor fetch
rehearsal, then seed20260635 mixed-route rehearsal. The claim remains
`hardware_proven=false` until those runs produce controller, mission, video,
keyframe, and runtime-provenance artifacts from the robot-side rehearsal
surface.

The rehearsal runner preflight is also green:
`artifacts/session/analysis_fetch_hardware_rehearsal_runner_preflight_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
It confirms the three rehearsal commands resolve locally and sets
`execute_runtime_stack_smoke` as the next action. Treat this as launch
readiness rather than hardware proof.

The runtime stack smoke has now executed:
`artifacts/session/live_fetch_hardware_rehearsal_runtime_stack_smoke_artifact_contract_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The run passed with session `20260605T054242Z`, coordinate UAT green, operator
status present, and milestone raw/debug screenshots inspected. The first attempt
found a CRLF shell-script boundary in `uat/orchestrator/run_uat_orchestrator.sh`;
the source is now LF-pinned and regression-tested. The next research gate is
saved-anchor fetch rehearsal with delivery videos.

The saved-anchor fetch rehearsal is now green:
`artifacts/session/live_fetch_hardware_rehearsal_saved_anchors_batch_contract_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The batch delivered `left05`, `right05`, and `zero` with `3/3` mission passes,
`3/3` visual packages, controller preflight, raw/topdown/world videos, and
keyframe sheets. Visual review found coherent delivery evidence for all three.
The next research gate is seed20260635 mixed-route rehearsal.

The seed20260635 mixed-route hardware rehearsal is now green:
`artifacts/session/live_fetch_hardware_rehearsal_seed20260635_mixed_route_contract_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The parent seeded gate is
`artifacts/session/hardware_rehearsal_seed20260635_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The replay batch is
`artifacts/session/hardware_rehearsal_seed20260635_20260605_replay/fetch_planner_route_replay_batch/scorecard.md`.
The planner classified `30/30` generated scenes, then the replay executed six
route-owner rows across fetch-ready, Nav2-first, and recovery/re-aim. All six
missions passed with browser-watchable visual packages, clean analyzer status,
and closest approaches around `0.194m..0.197m`. Visual review of the six
raw/topdown keyframe sheets found the camera evidence and topdown geometry
aligned through setup, first contact, push, and terminal delivery. This clears
the current simulation hardware-rehearsal ladder; the remaining proof gap is
robot-side/onboard execution, so `hardware_proven=false` remains the correct
claim boundary.

The robot-side rehearsal preflight is now ready:
`artifacts/session/analysis_fetch_robot_side_rehearsal_preflight_20260605/fetch_robot_side_rehearsal_preflight/scorecard.md`.
It validates the local run package after the seed20260635 rehearsal, including
the refreshed hardware-transfer readiness summary, rehearsal plan, command
availability, dashboard service, runtime sync, stack-smoke command,
saved-anchor runner, and seed mixed-route runner. It deliberately reports
`hardware_connected=false` and `hardware_proven=false`; physical proof still
requires onboard execution with controller preflight, mission verdict,
raw-camera/topdown/world videos, keyframe sheets, and operator sequence review.

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
