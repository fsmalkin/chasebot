# Gather Pre-Stage Architecture Options Review

## Current Test Signal

The eight blocked gather-control branches prove that helper/manual-drive overlays are not enough for the current fresh `zero` / `plus45` pre-stage blocker. The tests and matrix artifacts are still useful, but they mostly prove wiring, branch activation, safety guards, and artifact truthfulness. They do not by themselves prove that selected manual-drive commands have enough authority in the live plant, that the realized motion matches the helper's projected geometry, or that the handoff gate exactly matches the measured state the controller is optimizing.

The command-authority audit and the failed `pre_stage_trajectory_owner_v1` live matrix point below the gather-runner helper layer: motion is often realized and the ball stays still, but measured handoff still does not converge before timeout. The next active branch is `nav2_follow_path_reacquire_v1`, which dispatches an explicit short odom-frame pre-stage path to Nav2 controller-server `FollowPath` / DWB. If that cannot clear fresh `zero`, the next fallback should be MPPI/MPC or a controller-plugin/config-level change rather than another helper overlay.

## Assumptions To Peel Back

- Command authority: selected `linear_x` / `angular_z` may be too weak, clipped, delayed, or poorly realized even when helper projections look plausible.
- Geometry progress: realized motion may be real but may not reduce projection, lateral error, distance, yaw, or waypoint progress enough for handoff.
- Gate alignment: a controller may reach a state that looks handoff-ready in debug fields while repeatability summaries still count the case as failed.
- Test shape: fresh `zero` and `plus45` are the right promotion gate, but intermediate diagnostics should distinguish goal-side clearance, waypoint reach, lateral reduction, yaw reduction, and ball-still safety.
- Evidence completeness: missing state history or missing branch debug fields should trigger more instrumentation, not a pass/fail interpretation.

## Architecture Families To Compare

- Authority-owning local trajectory controller: represented by blocked `pre_stage_trajectory_owner_v1`; it owned the full pre-stage motion and command limits from measured pose to measured handoff readiness but still stalled before fresh handoff.
- True local trajectory tracker: represented by blocked `pre_stage_path_tracker_v1` and `pre_stage_trajectory_owner_v1`; both used measured progress, but neither had enough convergence authority in live `zero` / `plus45`.
- Nav2 controller-server `FollowPath` / DWB: selected for `nav2_follow_path_reacquire_v1`; it uses the lower-stack configured local planner directly on an explicit short pre-stage path instead of black-box `NavigateToPose`.
- MPC/MPPI local planner: first fallback if `FollowPath` cannot handle the geometry, optimizing bounded short-horizon commands against ball clearance, goal-side escape, and handoff geometry.
- Contact-aware manipulation planner: consider deliberate contact only if non-contact pre-stage remains too brittle and safety gates can be made explicit.
- Behavior-tree or action-server pre-stage owner: move pre-stage ownership out of the mission loop so progress, holds, aborts, and release conditions are first-class runtime states.
- Learned or Google/RT-style model path: use only as a shadow-mode maneuver proposer, critic, or switch/abstain sidecar. Direct real-time motor control is out of scope for this phase.
- Other architecture families: explicitly search for approaches not represented above before committing to the next runtime branch.

## Next Decision Gate

Implement `nav2_follow_path_reacquire_v1` behind the existing gather-control family seam and verify it offline first. Run the one-run goal-side matrix only after the implementation checkpoint is committed. Continue only if fresh `zero` and `plus45` both reach measured pre-stage handoff with no pre-stage ball drift/contact; otherwise stop promotion work and plan MPPI/MPC or controller-plugin/config-level changes rather than retuning blocked overlays.
