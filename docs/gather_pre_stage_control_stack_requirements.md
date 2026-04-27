# Gather Pre-Stage Control Stack Requirements

## Context

The blocked gather-control candidates now share the same first-attempt blocker: fresh `zero` and `plus45` live matrix attempts do not reliably reach behind-ball pre-stage handoff. The latest `pre_stage_path_tracker_v1` smoke failed safely: it recorded no pre-stage ball motion/contact, but both primary cases stayed on the `escape` waypoint until timeout.

## Requirements

- Own the full pre-stage motion from measured robot pose to measured handoff readiness, instead of layering another reactive overlay around the current pre-stage loop.
- Separate planned geometry progress from realized controller authority, so the evidence can distinguish "bad waypoint/path" from "commanded motion did not realize enough escape progress."
- Emit explicit commanded-vs-realized progress evidence for projection, lateral error, distance, yaw, waypoint/path progress, command mode, and manual-drive authority.
- Stop or hold on ball motion, predicted clearance violation, or measured clearance violation before handoff.
- Release to baseline only when measured pre-stage handoff is ready or a strict baseline-safe envelope is met.
- Stay out of portfolio/stress ingestion until a fresh one-run goal-side matrix shows `zero` and `plus45` both pass pre-stage handoff without pre-stage ball drift/contact.

## Non-Goals

- Do not retune `region_funnel_v1`, `nav2_reacquire_v1`, `constrained_local_planner_v1`, `docking_reacquire_v1`, `handoff_yaw_servo_v1`, `pre_stage_reacquire_fsm_v1`, or `pre_stage_path_tracker_v1`.
- Do not name or implement the next runtime branch in this requirements closeout.
- Do not refresh portfolio or stress evidence for blocked branches.
