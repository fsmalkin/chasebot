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
6. Keep guarded-live AI/contact execution terminal-only until corrected
   saved-anchor and seeded-random shadow scoring prove a reproducible benefit.
7. Build a mobile visual UAT package before asking for operator signoff:
   `python scripts/fetch_visual_uat_package.py --campaign-id <id> --planner-summary <gate_summary.json> --seeded-evidence-summary <evidence_summary.json> --mission-summary <campaign_run_summary.json> --visual-dir <session>/visual`
8. Freeze reproduced seeded/random failures into named layouts before tuning.

## Gates

- Planner handoff gate passes only when no out-of-envelope scene dispatches
  local fetch.
- Fetch UAT evidence passes only when corrected marker geometry, calibrated model
  provenance, and same-session video are present.
- Mobile visual UAT passes only when the package has planner-green evidence, a
  local fetch pass, and playable `world_stream.mp4` plus `topdown_telemetry.mp4`.
- Saved-layout gate requires `zero`, `left05`, and `right05` one-run, then `3/3`.
- Seeded gate uses `scripts/fetch_generalization_gate.py` and
  `scripts/fetch_seeded_gate_evidence_analyzer.py`.
- Promotion evidence must be canonical `real_time_factor=1.0`; accelerated runs
  are rejection/training evidence only.

## Stop Conditions

Continue autonomously through reversible edits, tests, docs, commits, pushes,
and evidence runs. Stop only for destructive operations, paid credentials,
hardware safety risk, or a repeated blocker that the current gates do not cover.
