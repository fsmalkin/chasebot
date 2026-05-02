# Gather Pre-Stage Architecture Options Review

## Current Test Signal

The eight blocked gather-control branches prove that helper/manual-drive overlays are not enough for the current fresh `zero` / `plus45` pre-stage blocker. The tests and matrix artifacts are still useful, but they mostly prove wiring, branch activation, safety guards, and artifact truthfulness. They do not by themselves prove that selected manual-drive commands have enough authority in the live plant, that the realized motion matches the helper's projected geometry, or that the handoff gate exactly matches the measured state the controller is optimizing.

The command-authority audit and the failed `pre_stage_trajectory_owner_v1` live matrix pointed below the gather-runner helper layer: motion was often realized and the ball stayed still, but measured handoff still did not converge before timeout. The next lower-stack probe, `nav2_follow_path_reacquire_v1`, also failed fresh `zero` and `plus45`: FollowPath goals were accepted but immediately aborted with no measured handoff and no ball motion. The MPPI continuation, `nav2_mppi_follow_path_reacquire_v1`, improved that failure mode by accepting FollowPath goals and moving the robot without moving the ball, but April 29, 2026 evidence still timed out before measured pre-stage handoff.

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
- MPC/MPPI local planner: represented first by blocked `nav2_mppi_follow_path_reacquire_v1`; it optimizes bounded short-horizon commands against ball clearance, goal-side escape, and handoff geometry through the Nav2 MPPI controller rather than the gather-runner manual-drive loop, but the first matrix/tangent checks showed insufficient convergence before timeout.
- Contact-aware manipulation planner: consider deliberate contact only if non-contact pre-stage remains too brittle and safety gates can be made explicit.
- Behavior-tree or action-server pre-stage owner: move pre-stage ownership out of the mission loop so progress, holds, aborts, and release conditions are first-class runtime states.
- Learned or Google/RT-style model path: use only as a shadow-mode maneuver proposer, critic, or switch/abstain sidecar. Direct real-time motor control is out of scope for this phase.
- Other architecture families: explicitly search for approaches not represented above before committing to the next runtime branch.

## Next Decision Gate

Stop promotion work on `nav2_follow_path_reacquire_v1` and `nav2_mppi_follow_path_reacquire_v1`, and preserve both as blocked lower-stack evidence. The next live gate should be a repaired controller-stack pass that explains and improves MPPI/controller convergence before rerunning fresh `zero` and `plus45`; do not add another helper/manual-drive overlay to paper over the same handoff blocker.
