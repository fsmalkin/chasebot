# Object-Centric Gather Policy Research Plan

## Status

Superseded by the fetch pivot in [OBJECT_CENTRIC_FETCH_POLICY_PLAN.md](OBJECT_CENTRIC_FETCH_POLICY_PLAN.md).

This document remains as historical context for the May 3, 2026 post-MPPI
research direction. Treat `nav2_mppi_follow_path_reacquire_v1` as a
baseline/evidence branch, not the primary promotion path. MPPI recovered
saved-layout `zero` and `plus45` pre-stage handoff after terminal geometry
repair, but full missions still fail downstream in contact-rich capture
behavior.

The active research target is no longer object-centric gather/place into the
corral. The emergent roll/launch behavior is now the core primitive. Near-term
work should prove `fetch_to_pose` first, then add user/person detection once the
pose-delivery loop is measurable and repeatable.

Architecture revisit conclusion: the calibrated golf-ball/turf physics lane and
object-centric fetch architecture are the UAT baseline after the May 27, 2026
demo-readiness gate:
`artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/calibrated_golf_fetch_gate/gate_summary.json`.
Historical pre-stage-only branches remain blocked. Any alternative architecture
must requalify through that calibrated `fetch_to_pose` gate instead of reopening
the old gather/place promotion path.

## Historical Thesis

Use Nav2/MPPI for long-range repositioning and obstacle-aware path following.
Do not rely on FollowPath to infer ball capture or placement. The gather skill
was proposed as an object-centric policy over robot, ball, zone, recent motion,
and contact state, wrapped by deterministic safety gates.

The previous experimental family was:

`object_centric_gather_policy_v1`

It would have owned one-ball gather behavior from pre-stage through
capture/place as a short-horizon object manipulation skill. That line is frozen
unless fetch-to-pose evidence later shows that corral/place behavior is again
needed.

## Research Basis

- RoboCup small-size and middle-size systems commonly use layered strategy, approach-angle planning, vision servoing, and ball-handling controllers rather than expecting a generic path follower to solve contact behavior.
- Nonprehensile pushing literature treats robot-ball-object motion as contact-rich manipulation with unilateral/friction constraints; slippage and poor contact geometry are task failures, not just navigation errors.
- Modern object-pushing work increasingly uses object-centric MPC or learned local dynamics with online adaptation.
- Recent robot soccer learning systems use simulation, domain randomization, and learned policies for ball interaction, with classical or deterministic safety still surrounding deployment.
- JetBot/Jetson-class examples support the same practical direction: use simulation/domain randomization for learned perception or control components, then keep deployed policies compact enough for onboard compute.

Useful references:

- `https://link.springer.com/article/10.1007/s13173-011-0028-4`
- `https://arxiv.org/abs/2003.10247`
- `https://arxiv.org/abs/2403.13274`
- `https://arxiv.org/abs/2405.02425`
- `https://arxiv.org/abs/2304.13653`
- `https://developer.nvidia.com/blog/?p=24447`

## Baseline Freeze

Freeze the MPPI branch as a comparison baseline:

- `nav2_mppi_follow_path_reacquire_v1` is recovered for primary pre-stage
  handoff but remains blocked downstream and out of portfolio/stress ingestion.
- Keep terminal-geometry evidence as proof that Nav2 MPPI can recover primary
  pre-stage handoff.
- Keep capture-entry/capture/first-contact/release failures as the
  contact-contaminated negative baseline for downstream behavior.
- Do not continue broad MPPI critic/threshold tuning unless it is needed to maintain long-range repositioning infrastructure for the object-centric branch.

Baseline artifacts:

- `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_live_audit_20260503/gather_follow_path_research_analyzer/follow_path_research_summary.json`
- `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_zero_3run_20260503/gather_mission_repeatability/campaign_run_summary.json`
- `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_terminal_geometry_plus45_3run_20260503/gather_mission_repeatability/campaign_run_summary.json`

## Requalification Boundary

This plan is historical context, not a new pivot request. Candidate alternative
architectures for calibrated fetch-to-pose must:

- use the same calibrated golf ball, calibrated turf world, `0.300m` delivery
  radius, saved layouts, no-retry policy runs, approach telemetry, and
  deterministic guards as the May 27 gate
- pass the dashboard CTA centerline and policy `zero`, `left05`, and `right05`
  gates before promotion discussion
- report closest approach, first-contact alignment, pre-contact yaw sign
  changes, lateral knock-away, and goal-side entry against the May 27 baseline
- avoid using old pre-stage-only smokes or MPPI downstream contact failures as
  evidence that the fetch architecture should be broadly replaced

## Historical Milestone 1: Offline Evaluation Harness

Build an offline evaluator before adding the runtime branch.

Inputs:

- existing `campaign_summary.json`, `campaign_run_summary.json`, `mission_verdict.json`, and `state_history.jsonl` artifacts
- saved hard-case layouts for `zero`, `plus45`, `minus45`, and `backside180`
- candidate policy trace outputs once available

Required metrics:

- pre-stage handoff pass
- capture-entry reached
- first-contact alignment observed
- ball motion before intended contact
- capture achieved
- zone entry / placement
- timeout class
- safety-stop count
- command smoothness and mode churn

Deliverable:

- an analyzer that can score the MPPI baseline and future `object_centric_gather_policy_v1` traces on the same cases
- implementation surface: `scripts/gather_object_centric_policy_evaluator.py`

## Historical Milestone 2: Structured Object Servo Baseline

Start with an interpretable object-centric servo policy, not full RL.

Inputs:

- robot pose
- ball pose
- zone pose
- relative robot-ball vector
- relative ball-zone vector
- recent robot and ball deltas
- previous selected command
- capture/contact flags

Behavior:

- compute the desired push line from ball to zone
- choose a behind-ball relative pose
- regulate robot-ball distance, lateral offset, push-line yaw, and ball-zone progress continuously
- emit bounded `linear_x` / `angular_z`
- keep deterministic safety guards for ball drift, goal-side violation, clearance, max command, timeout, and stuck state
- implementation surface: `scripts/gather_object_centric_policy_helpers.py`

Success gate:

- saved-layout `zero` and `plus45`, one run each, no retries, must pass full mission progress without pre-stage ball drift/contact
- then `zero --runs 3` and `plus45 --runs 3`, no retries

## Historical Milestone 3: Learned Residual

Only after the structured servo baseline exists, add a learned residual if the failure cases show consistent model error.

Preferred first learning shape:

- structured-state MLP
- inputs match the object-servo state vector
- output is a small correction to the nominal servo command
- deterministic guard may clip or reject any correction

Training data:

- generated in sim with randomized friction, ball mass/radius, spawn angle, robot pose noise, perception noise, and wheel slip
- include recovery states and failures, not only clean demonstrations

## Historical Milestone 4: Direct Short-Horizon Policy

Consider direct policy control only after the residual-policy lane is understood.

Constraints:

- no policy bypasses deterministic safety
- no direct high-frequency LLM motor control
- policy horizon stays short and bounded
- rejected policy actions must become explicit audit events

## Historical Live Gates

1. Object-servo smoke:
   - saved-layout `zero`, one run, no retries
   - saved-layout `plus45`, one run, no retries
2. Repeatability:
   - saved-layout `zero --runs 3`, no retries
   - saved-layout `plus45 --runs 3`, no retries
3. Full matrix:
   - `zero`
   - `plus45`
   - `minus45`
   - `backside180`
4. Portfolio/stress consideration:
   - only after full mission gates are green or the promotion scope is explicitly redefined

## Historical Non-Goals

- Do not loosen pre-stage handoff acceptance.
- Do not redefine `/odom`.
- Do not change frozen contracts.
- Do not add another helper/manual-drive overlay to patch one case at a time.
- Do not keep tuning MPPI/capture thresholds as the main research path.
- Do not allow a learned policy to bypass deterministic safety gates.

## Historical Stop Criteria

Retire or freeze a branch when:

- success depends on case-specific thresholds
- fresh reruns flip after minor session/runtime changes
- improvements only move the failure one phase later
- safety gates must be loosened to show progress
- the branch cannot beat the MPPI baseline on `zero` and `plus45` without adding special-case logic
