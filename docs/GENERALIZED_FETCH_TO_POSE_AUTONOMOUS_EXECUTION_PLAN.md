# Generalized Fetch-To-Pose Autonomous Execution Plan

This plan is the default execution path for `spike/fetch-arch-ai-push-coast-servo-20260529`.
It exists so agents can keep moving without asking for clarification when the
next safe step is covered here.

## Milestone

Deliver **Generalized Fetch-To-Pose v1**: a no-shoot, robot-owned local fetch
behavior that combines Nav2 corridor tracking, deterministic contact/terminal
routines, and a guarded AI/model handoff proposer, proven on saved layouts and
the first seeded random gate.

The broader product path is **Planner-Gated Generalized Fetch**. Mixed or
surprising random scenes must pass planner routing before local fetch is judged.

## Default Execution Order

1. Keep `spike/fetch-arch-ai-push-coast-servo-20260529` as the active
   implementation lane.
2. Keep shared docs/harness changes propagated to `physics-calibrated-golf-fetch-v1`
   and `main` after the spike has clean verification.
3. Run planner-handoff evidence before broad random UAT:
   - deterministic frozen scene gate:
     `python scripts/fetch_planner_handoff_gate.py --campaign-id <id> --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json --dry-run`
   - optional LLM shadow comparison:
     `python scripts/fetch_planner_handoff_gate.py --campaign-id <id> --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json --dry-run --planner-mode llm_shadow`
4. Run local fetch evidence only for planner-approved `fetch_ready_local` scenes.
5. Keep guarded-live execution terminal-only until saved-anchor and seeded-random
   shadow scoring are green.
6. Build a mobile visual UAT package before asking for operator signoff:
   `python scripts/fetch_visual_uat_package.py --campaign-id <id> --planner-summary <gate_summary.json> --seeded-evidence-summary <evidence_summary.json> --mission-summary <campaign_run_summary.json> --visual-dir <session>/visual`
7. Freeze reproduced seeded/random failures into named layouts before tuning.

## Gates

- Planner handoff gate passes only when no out-of-envelope scene dispatches
  local fetch.
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
