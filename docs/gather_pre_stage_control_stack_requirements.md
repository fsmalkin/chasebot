# Gather Pre-Stage Control Stack Requirements

## Current Status

This document is historical gather/place architecture context. The active
control baseline is calibrated golf-ball `fetch_to_pose`, documented in
[OBJECT_CENTRIC_FETCH_POLICY_PLAN.md](OBJECT_CENTRIC_FETCH_POLICY_PLAN.md) and
[FETCH_BRANCH_STRATEGY.md](FETCH_BRANCH_STRATEGY.md). Do not use this document
to reopen a blocked pre-stage branch without fresh calibrated fetch evidence.

## Context

The blocked gather-control candidates originally shared the same first-attempt blocker: fresh `zero` and `plus45` live matrix attempts did not reliably reach behind-ball pre-stage handoff. The latest helper-layer owners failed safely with no pre-stage ball motion/contact. The first lower-stack DWB FollowPath probe accepted `/follow_path` goals but aborted immediately before measured robot progress, while the MPPI FollowPath probe accepted goals and moved the robot without moving the ball. The May 3, 2026 terminal-geometry repair recovered saved-layout `zero` and `plus45` MPPI pre-stage handoff, but full missions remained blocked downstream at capture-entry/capture.

The assumption peel-back is complete enough to stop treating path-following convergence as the main research problem. MPPI is useful baseline evidence for safe pre-stage movement, but contact-rich ball capture and placement need an object-centric manipulation policy. That thread became the object-centric fetch pivot: keep `object_centric_gather_policy_v1` as historical gather/place context, and use `object_centric_fetch_policy_v1` as the active calibrated manipulation lane.

## Next Branch Steps

- Treat `nav2_mppi_follow_path_reacquire_v1` as blocked baseline evidence rather than the primary promotion path.
- Keep `object_centric_gather_policy_v1` frozen as historical gather/place context.
- Use `physics-calibrated-golf-fetch-v1` for active calibrated fetch work.
- Run any alternative architecture as a short-lived calibrated fetch spike, not by reviving a blocked branch in place.
- Keep the current `zero` / `plus45` gates, measured pre-stage handoff acceptance, `/odom`, and frozen contracts unchanged.

## Requirements

- Own one-ball gather interaction from pre-stage through capture/place as a short-horizon object-centric policy.
- Use robot pose, ball pose, zone pose, recent robot/ball deltas, previous command, and capture/contact flags as the core structured state.
- Emit bounded `linear_x` / `angular_z` commands or bounded relative waypoints.
- Keep deterministic safety filters around every proposal: command bounds, ball drift, clearance, goal-side violation, timeout, stuck state, and safe-stop fallback.
- Separate object-servo nominal commands from learned residual corrections if learning is introduced.
- Stay out of portfolio/stress ingestion until fresh saved-layout `zero` and `plus45` pass full mission gates without pre-stage ball drift/contact, followed by the full four-case matrix.

## Architecture Options To Revisit

- Structured object servo: default next candidate for `object_centric_gather_policy_v1`.
- Learned residual: add only after structured servo failure modes are measured.
- Direct short-horizon policy: later candidate, still behind deterministic safety gates.
- MPC/MPPI-style local planner: retain as long-range repositioning and baseline evidence, not the main contact-control owner.
- Nav2 controller-plugin path: use for infrastructure and comparison, not final ball manipulation.
- Learned or Google/RT-style model path: bounded policy/proposer/critic only; no direct high-frequency LLM motor control.
- Other architecture families: explicitly search for and evaluate alternatives not already represented here before committing to the next branch.

## Non-Goals

- Do not retune `region_funnel_v1`, `nav2_reacquire_v1`, `constrained_local_planner_v1`, `docking_reacquire_v1`, `handoff_yaw_servo_v1`, `pre_stage_reacquire_fsm_v1`, or `pre_stage_path_tracker_v1`.
- Do not keep tuning MPPI/capture thresholds as the main research path.
- Do not name or implement another helper/manual-drive runtime branch as a substitute for object-centric policy work.
- Do not refresh portfolio or stress evidence for blocked branches.
