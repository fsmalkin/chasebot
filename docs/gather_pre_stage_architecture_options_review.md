# Gather Pre-Stage Architecture Options Review

## Current Status

This is now a historical gather/place architecture review. It remains useful for
classifying old branch evidence, but the active UAT baseline is calibrated
golf-ball `fetch_to_pose` on `physics-calibrated-golf-fetch-v1`. The current
comparison package is:
`artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`.

## Current Test Signal

The eight blocked gather-control branches prove that helper/manual-drive overlays are not enough for the current fresh `zero` / `plus45` pre-stage blocker. The tests and matrix artifacts are still useful, but they mostly prove wiring, branch activation, safety guards, and artifact truthfulness. They do not by themselves prove that selected manual-drive commands have enough authority in the live plant, that the realized motion matches the helper's projected geometry, or that the handoff gate exactly matches the measured state the controller is optimizing.

The command-authority audit and the failed `pre_stage_trajectory_owner_v1` live matrix pointed below the gather-runner helper layer: motion was often realized and the ball stayed still, but measured handoff still did not converge before timeout. The next lower-stack probe, `nav2_follow_path_reacquire_v1`, also failed fresh `zero` and `plus45`: FollowPath goals were accepted but immediately aborted with no measured handoff and no ball motion. The MPPI continuation, `nav2_mppi_follow_path_reacquire_v1`, improved that failure mode by accepting FollowPath goals and moving the robot without moving the ball. The May 3, 2026 terminal-geometry patch recovered saved-layout `zero` and `plus45` pre-stage handoff, but full missions still failed downstream in capture-entry/capture. That shifted the main research question from path-following convergence to object-centric ball manipulation.

The May 27, 2026 calibrated fetch gate answers the physics-overindexing
question narrowly: do not resurrect old gather/place branches just because the
ball physics is now better. Most failed before intended ball contact. Only
contact-rich downstream ideas should be reconsidered, and only as short-lived
calibrated fetch spikes that keep the same ball model, turf world, `0.300m`
delivery radius, saved layouts, no retries, and approach telemetry.

The first such spike reran `nav2_mppi_follow_path_reacquire_v1` under calibrated
fetch-to-pose on May 27, 2026:
`artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`.
It failed `zero`, `left05`, and `right05` before contact with
`pre_stage_path_clearance_guard`, so MPPI remains evidence-only rather than a
new development branch.

## Assumptions To Peel Back

- Command authority: selected `linear_x` / `angular_z` may be too weak, clipped, delayed, or poorly realized even when helper projections look plausible.
- Geometry progress: realized motion may be real but may not reduce projection, lateral error, distance, yaw, or waypoint progress enough for handoff.
- Gate alignment: a controller may reach a state that looks handoff-ready in debug fields while repeatability summaries still count the case as failed.
- Test shape: fresh `zero` and `plus45` are the right promotion gate, but intermediate diagnostics should distinguish goal-side clearance, waypoint reach, lateral reduction, yaw reduction, and ball-still safety.
- Evidence completeness: missing state history or missing branch debug fields should trigger more instrumentation, not a pass/fail interpretation.

## Architecture Families To Compare

- Authority-owning local trajectory controller: represented by blocked `pre_stage_trajectory_owner_v1`; it owned the full pre-stage motion and command limits from measured pose to measured handoff readiness but still stalled before fresh handoff.
- True local trajectory tracker: represented by blocked `pre_stage_path_tracker_v1` and `pre_stage_trajectory_owner_v1`; both used measured progress, but neither had enough convergence authority in live `zero` / `plus45`.
- Nav2 controller-server `FollowPath` / DWB: represented by blocked `nav2_follow_path_reacquire_v1`; it used the lower-stack configured local planner directly on an explicit short pre-stage path instead of black-box `NavigateToPose`, but the action aborted immediately in the primary live cases.
- MPC/MPPI local planner: represented first by blocked `nav2_mppi_follow_path_reacquire_v1`; it optimizes bounded short-horizon commands against ball clearance, goal-side escape, and handoff geometry through the Nav2 MPPI controller rather than the gather-runner manual-drive loop, and is now retained as a baseline for safe pre-stage movement rather than the primary contact-control architecture.
- Object-centric manipulation policy: historical next gather family, represented by `object_centric_gather_policy_v1`; its useful result is now the active `object_centric_fetch_policy_v1` direction, where success is measured by trajectory intersection with a target-pose delivery radius rather than final stop in a corral.
- Contact-aware manipulation planner: first implement as a structured object-servo baseline; learned residuals or direct policies should come only after measured servo failure modes are understood.
- Behavior-tree or action-server pre-stage owner: move pre-stage ownership out of the mission loop so progress, holds, aborts, and release conditions are first-class runtime states.
- Learned or Google/RT-style model path: use only as a bounded short-horizon policy, residual, maneuver proposer, critic, or switch/abstain sidecar behind deterministic safety gates. Direct high-frequency LLM motor control is out of scope.
- Other architecture families: explicitly search for approaches not represented above before committing to the next runtime branch.

## Next Decision Gate

Stop promotion work on `nav2_follow_path_reacquire_v1` and broad
`nav2_mppi_follow_path_reacquire_v1` contact tuning, and preserve both as
lower-stack evidence. The active branch decision is now documented in
[FETCH_BRANCH_STRATEGY.md](FETCH_BRANCH_STRATEGY.md): preserve
`physics-calibrated-golf-fetch-v1` as the stable demo/UAT branch, treat blocked
architecture branches as evidence only, and use short-lived `spike/...`
branches for any targeted calibrated fetch requalification.
