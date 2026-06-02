# Generalized Fetch-To-Pose Autonomous Execution Plan

This plan is the default execution path for `spike/fetch-arch-ai-push-coast-servo-20260529`.
It exists so agents can keep moving without asking for clarification when the
next safe step is covered here.

## Milestone

Deliver **Planner-Gated Generalized Fetch-To-Pose v1**: a no-shoot,
robot-owned fetch behavior where an LLM/world-state planner selects the route
class, Nav2 owns as much real-time robot motion as corrected evidence supports,
and a thin fetch adapter monitors corrected delivery geometry, object progress,
escape, stale state, and replanning triggers.

The default control sequence is deliberately simple: classify the route, compute
the intended ball path, compute the capture pose behind the ball, reach and gate
that setup, let Nav2 push through the ball-target corridor, then let the monitor
classify success or the next bounded recovery.

The broader product path is **Planner-Gated Generalized Fetch**. Mixed or
surprising random scenes must pass planner routing before local fetch is judged.
Custom contact routines and AI push-coast proposals remain fallback lanes that
earn live authority only from corrected, reproducible stage-gap evidence.

## Evidence Reset

May 31, 2026 reset: a local fetch result counts as UAT or architecture evidence
only when `geometry_consistency.pass=true`, the visible delivery marker matches
`fetch_pose_world`, and same-session browser-watchable onboard plus context
video exists. Pre-fix or marker-mismatched fetch passes are diagnostic
implementation evidence.

June 1, 2026 provenance reset: direct `fetch_to_pose` evidence also needs
`model_provenance_valid=true`, target model `calibrated_golf_ball`, target
radius `0.021336m`, and marker model `golf_ball_delivery_zone_marker`. Commit
`680e393 Use calibrated ball for fetch direct runs` is the boundary for direct
fetch reruns. Older direct artifacts with missing or legacy model provenance
are diagnostic and should be rebuilt through the saved-layout ladder.

Corrected reference artifacts:

- mission:
  `artifacts/session/20260531T204154158382Z/gather_mission/20260531T204255Z/mission_verdict.json`
- visual package:
  `artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`
- geometry audit:
  `artifacts/session/fetch_geometry_evidence_audit_postfix_20260531/fetch_geometry_evidence_audit/scorecard.md`

June 1, 2026 contact-buffer handoff validation: commit
`02a4c12 Fix Nav2 contact-buffer fetch handoff` fixes the stop-short behavior
seen in operator video review. Nav2 now uses the tight
`corridor_push_goal_checker`, the readiness launch publishes the missing depth
scan TF, and the fetch adapter treats a close/aligned no-object-motion Nav2 stop
as `monitor_contact_buffer_handoff`. The bounded deterministic contact servo
then confirms first contact before the corridor push continues.

Reference proof:

- campaign:
  `artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`
- visual package:
  `artifacts/session/uat_contact_buffer_monitor_servo_zero_probe_20260601/fetch_visual_uat_package/scorecard.md`
- result:
  `fetch_to_pose_pass=true`, closest delivery distance `0.179959m`, Nav2
  handoff at `robot_ball_distance_m=0.195671`, first-contact servo motion
  `0.046811m`

Saved-anchor requalification, later June 1:

- planner gate:
  `artifacts/session/live_planner_handoff_mixed_fetch_20260601/fetch_planner_handoff_gate/gate_summary.json`
  passed `5/5`
- `zero`:
  `artifacts/session/live_contact_buffer_saved_anchor_zero_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  passed, closest `0.152567m`
- `left05`:
  `artifacts/session/live_contact_buffer_saved_anchor_left05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  passed, closest `0.266102m`, contact-quality watch
- `right05`:
  `artifacts/session/live_contact_buffer_saved_anchor_right05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  failed at `capture_entry_timeout`
- audit:
  `artifacts/session/audit_contact_buffer_right05_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
  classifies the blocker as setup/capture

Stage-owner comparison, later June 1:

- analyzer:
  `scripts/fetch_stage_owner_comparison.py`
- artifact:
  `artifacts/session/live_fetch_stage_owner_comparison_20260601/fetch_stage_owner_comparison/scorecard.md`
- recommended action:
  `run_setup_capture_gap_fill_or_port_prior_behavior`
- interpretation:
  the planner handoff is green; current staged Nav2/contact-buffer is red on
  `right05` setup/capture; Nav2 corridor-push and the corrected direct
  `right05` reference show reusable setup/capture behavior; current staged
  first-contact and push/coast are yellow because `right05` stopped before
  those stages; May 27 object-centric fetch remains the best terminal-delivery
  comparison, with yellow margin flags near the delivery-radius boundary.

Setup/capture gap-fill probe, later June 1:

- analyzer:
  `scripts/fetch_setup_capture_gap_fill_probe.py`
- gap-fill artifact:
  `artifacts/session/live_fetch_setup_capture_gap_fill_20260601/fetch_setup_capture_gap_fill_probe/scorecard.md`
- saved-anchor one-run rebuild:
  `artifacts/session/live_ai_push_coast_saved_anchor_gapfill_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`
- stage-quality audit:
  `artifacts/session/audit_ai_push_coast_gapfill_saved_anchor_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
- capture-entry diagnostic:
  `artifacts/session/audit_ai_push_coast_gapfill_saved_anchor_one_run_20260601/fetch_capture_entry_diagnostic_analyzer/scorecard.md`
- interpretation:
  setup/capture is requalified on the corrected staged path. The latest
  saved-anchor one-run set is `2/3`: `zero` passed cleanly, `left05` passed
  with a first-contact alignment watch, and `right05` reached capture-entry but
  missed the delivery radius at `0.520765m` after a Nav2 corridor-push action
  abort. This initially pointed at terminal-arrival correction. The later
  clip-review reframe below supersedes that sequence.

Clip-review reframe, later June 1:

- audit:
  `artifacts/session/audit_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
- visual package:
  `artifacts/session/uat_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_visual_uat_package/scorecard.md`
- interpretation:
  the latest operator-visible clips supersede the terminal-correction priority.
  `zero` is the desired behavior, but `left05` and `right05` show off-axis
  setup/capture/handoff instability. `left05` pushes the ball laterally out of
  the corridor; `right05` under-moves the ball after unstable capture. The next
  implementation work is a first-class capture-geometry setup stage before
  another terminal correction probe.

## Default Execution Order

1. Keep `spike/fetch-arch-ai-push-coast-servo-20260529` as the active lane for
   corrected requalification, analyzers, guards, and fallback AI/contact work.
2. Keep shared docs/harness changes propagated to `physics-calibrated-golf-fetch-v1`
   and `main` after the spike has clean verification.
3. Run planner-handoff evidence before broad random UAT:
   - deterministic frozen scene gate:
     `python scripts/fetch_planner_handoff_gate.py --campaign-id <id> --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json --dry-run`
   - optional LLM shadow comparison:
     `python scripts/fetch_planner_handoff_gate.py --campaign-id <id> --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json --dry-run --planner-mode llm_shadow`
4. Run local fetch evidence only for planner-approved `fetch_ready_local` scenes.
5. Rerun corrected saved-layout local fetch evidence before expanding custom
   control:
   - `zero`, `left05`, `right05`
   - no retries
   - `0.300m` delivery radius
   - `model_provenance_valid=true`
   - same-session visual package
6. Use the staged local fetch sequence as the current implementation baseline:
   planner-approved local case -> ball-target delivery line -> capture pose ->
   setup motion -> geometry gate -> Nav2 corridor push -> delivery monitor.
7. Treat the June 1 clip-reviewed saved-anchor rebuild as superseded by the
   June 2 fetch-ready handoff repair and one-run matrix.
8. Use the fetch-ready capture-entry handoff as the current setup stage:
   - compute the robot's standoff, lateral error, and yaw error against the
     ball-target line
   - hold when the fetch push-readiness gate is green under the tighter
     capture-entry `0.58m` standoff cap
   - hand off to `fetch_to_pose` corridor push with `handoff_kind =
     fetch_push_ready`
   - preserve gate decisions in mission verdicts, saved-anchor summaries, and
     visual UAT packages
9. Treat the June 2 saved-anchor one-run result as the current UAT screen:
   `artifacts/session/live_fetch_push_ready_handoff_saved_anchor_one_run_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
   The matrix is `3/3` at one run each with a green mobile visual package:
   `artifacts/session/uat_fetch_push_ready_handoff_saved_anchor_one_run_20260602/fetch_visual_uat_package/scorecard.md`.
10. Use the June 2 corrected saved-layout repeatability result as the current
    saved-anchor baseline:
    `artifacts/session/live_fetch_setup_contact_repair_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
    `zero`, `left05`, and `right05` passed promotion `3/3` with worst closest
    approaches `0.201194m`, `0.169541m`, and `0.136046m`.
11. Use the setup/contact audit as the stage-quality baseline:
    `artifacts/session/audit_fetch_setup_contact_repair_saved_anchor_3x_20260602/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
    The audit is `stage_quality_green=true` with one `left05`
    `capture_entry_time_watch`.
12. Treat the June 2 seeded shadow/evidence gate as the current blocker:
    `artifacts/session/live_fetch_setup_contact_repair_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
    The analyzer is
    `artifacts/session/evidence_fetch_setup_contact_repair_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
    The gate passed `4/6`; `case01` and `case06` reproduced
    `capture_entry_timeout` before corridor-push handoff.
13. Repair the frozen setup/capture layouts before additional live-control work:
    `artifacts/session/live_fetch_setup_contact_repair_seeded_gate_20260602/fetch_generalization_gate/frozen_failure_layouts`.
14. Resume terminal-arrival correction only for clean near-contract misses after
    saved-layout repeatability identifies a reproducible terminal-arrival gap.
15. Keep guarded-live AI/contact execution terminal-only until corrected
    saved-anchor and seeded-random shadow scoring prove a reproducible benefit.
16. Build a mobile visual UAT package before asking for operator signoff:
   `python scripts/fetch_visual_uat_package.py --campaign-id <id> --planner-summary <gate_summary.json> --seeded-evidence-summary <evidence_summary.json> --mission-summary <campaign_run_summary.json> --visual-dir <session>/visual`
17. Freeze reproduced seeded/random failures into named layouts before tuning.

## Gates

- Planner handoff gate passes only when no out-of-envelope scene dispatches
  local fetch.
- Fetch UAT evidence passes only when corrected marker geometry, calibrated model
  provenance, and same-session video are present.
- Mobile visual UAT passes only when the package has planner-green evidence, a
  local fetch pass, and playable `world_stream.mp4` plus `topdown_telemetry.mp4`.
- Operator-review videos are useful UAT evidence only when they are
  browser-watchable and traceable to the same session. Rebuilt videos can support
  review, but a green package should also carry healthy observer confirmation.
- Saved-layout gate requires `zero`, `left05`, and `right05` one-run, then `3/3`.
- Seeded gate uses `scripts/fetch_generalization_gate.py` and
  `scripts/fetch_seeded_gate_evidence_analyzer.py`.
- Promotion evidence must be canonical `real_time_factor=1.0`; accelerated runs
  are rejection/training evidence only.

## Stop Conditions

Continue autonomously through reversible edits, tests, docs, commits, pushes,
and evidence runs. Stop for destructive operations, paid credentials, hardware
safety risk, or a repeated blocker outside the current gates.
