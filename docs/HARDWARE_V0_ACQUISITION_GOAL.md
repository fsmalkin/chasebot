# Hardware V0 Acquisition and Smooth Approach Goal

Owner direction: 2026-07-09

## Outcome

Chasebot should use fully onboard perception to find a golf ball, establish a
stable track, turn toward it, and approach a calibrated standoff with visibly
damped control. The robot should handle representative starting bearings and
ranges on hard floor without human correction after the operator starts the
episode.

This milestone establishes the dependable last-meter primitive needed by
fetch and delivery. Delivery-target planning resumes after acquisition and
approach meet the evidence bar below.

## Evidence Bar

Every qualifying run must satisfy the safety contract:

- The bridge begins locked with both motors at zero.
- The operator starts the episode from the dashboard.
- The onboard TensorRT detector owns ball perception during control.
- The episode ends with `final_safe=true`, motion disabled, and both motors at
  zero.
- The onboard trace and laptop episode summary are preserved together.

The initial hard-floor matrix covers the controller regimes that remain
unproven on the real chassis:

| Case | Initial observation | Purpose |
| --- | --- | --- |
| Center | `abs(center_error) <= 0.12` | Straight approach and standoff |
| Mid-left | `-0.55 <= center_error < -0.12` | Forward arc correction |
| Mid-right | `0.12 < center_error <= 0.55` | Forward arc correction |
| Far-left | `center_error < -0.60` | Turn regime, transition, approach |
| Far-right | `center_error > 0.60` | Turn regime, transition, approach |

Place the ball roughly 0.7-1.2 m from the robot for the first matrix. Run one
diagnostic episode per case, then run five consecutive mixed placements chosen
by the operator. A successful episode must reach the calibrated standoff before
any push phase. `lost_target`, `max_steps_reached`, and
`forward_budget_exhausted` are failures for this milestone.

## Smoothness Standard

The camera-relative trace is the measurement source because the chassis has no
wheel encoders. The approach should show:

- decreasing absolute center error through the turn-to-forward transition;
- decreasing estimated range during forward control;
- no sustained alternating left-right limit cycle after first entering the
  center deadband;
- bounded coasting through brief detector misses;
- a single stable arrival at the standoff threshold.

The first live traces will set quantitative limits for direction reversals,
settling time, and range progress. Simulator tuning gains authority only after
it reproduces any observed hardware failure.

## Execution Ladder

1. Restore the locked bench stack and verify bridge health, camera freshness,
   onboard detector readiness, and the STOP read-back path.
2. Run the existing hardwood far-offset ARC experiment before changing control
   code.
3. Pull the onboard JSONL trace and classify tracker, regime-transition,
   stiction, or perception behavior from measured evidence.
4. Add an offline trace scorecard for acquisition success and smoothness.
5. Implement the smallest generalized correction supported by the trace, then
   rerun Python 3.6 compatibility, self-test, simulator reproduction, and CI.
6. Clear the five-case matrix and five consecutive mixed placements.
7. Expand to lighting variation, then treat carpet pivoting as a separate
   surface-control lane.

## Progress (2026-07-09)

- The Windows host joined `jetbot-mini`; the factory bridge was redeployed with
  camera enabled and `TurnGain=1.0`.
- Locked preflight passed with motion disabled, motors at zero, a fresh
  gstreamer frame, and verified STOP/relock responses.
- The current onboard brain was deployed and passed its Python 3.6 self-test.
- A three-frame onboard TensorRT dry-run detected the ball at about `0.92`
  confidence and ended `final_safe=true` with zero motion commands.
- `scripts/onboard_acquisition_trace_scorecard.py` now distinguishes smooth
  acquisition, stalled turn response, stalled forward response, target loss,
  and center-limit-cycle behavior from onboard JSONL traces.
- The historical baseline scorecard reproduced the known evidence classes. Its
  local output is
  `artifacts/session/hardware_acquisition_baseline_20260709/onboard_acquisition_trace_scorecard/scorecard.md`.
- The robot has been relocated to a second hardwood room. A locked inspection
  confirmed a fresh gstreamer frame, bridge health `ok=true`, both motors at
  zero, and `commands_received=0`; the raw setup frame is
  `artifacts/session/hardware_live_20260709/new_room_camera.jpg`.
- Before the first run, the ball was live at about `z=0.59 m` and
  `center_error=-0.79`, fully visible at the far-left edge. ARC was selected
  and the bridge was locked.
- The first far-left hard-floor diagnostic ran as
  `onboard_1652159798` from `center_error=-0.7926`. It issued ten continuous
  turn-regime commands, made no measured centering or range progress, swept the
  ball out of view, and ended `lost_target` with `final_safe=true`. The preserved
  scorecard is
  `artifacts/session/hardware_live_20260709/failed_far_left_2300/onboard_acquisition_trace_scorecard/scorecard.md`.
- Root cause: ARC treated repeated cached camera frames as fresh and continued
  a full-speed in-place pivot through tracker coasting. The tuning simulator
  also incorrectly allowed a pure pivot to satisfy standoff by shrinking
  forward-axis projection; that metric is now physical robot-to-ball range.
- Decision: the far-off ARC regime now uses a bounded `0.08-0.16 s` pivot,
  stops, discards the first post-turn frame, and requires a fresh camera
  judgment before another pivot. The forward ARC regime is unchanged. The
  trace-calibrated simulator reproduces `lost_target` with the old unbounded
  turn and reaches standoff with the bounded controller; symmetric left/right
  delayed-camera cases also pass.
- The repair was deployed while locked at commit `996a51c`; local and robot
  SHA-256 matched (`80906b1d765a0077669096ff74c190c23448376fe1c846cc6d43a7f268c11542`).
  The Jetson Python 3.6 self-test and a three-frame TensorRT dry-run passed with
  `final_safe=true`, `commands_received=57` unchanged from the failed episode,
  motion disabled, and both motors at zero. The current raw frame contains no
  visible ball, so a hard-floor operator rerun remains required before the
  repair is called proven.
- Owner direction on 2026-07-10 authorized unattended acquisition as a standing
  lane. Commits `afcd1bc` and `ce6eccb` add a no-contact acquire/STOP/trace/
  reverse/geometry runner and force its private endpoint to ARC independently
  of the dashboard toggle. Sixteen safety-focused tests pass. The locked live
  runner artifact at
  `artifacts/session/hardware_unattended_locked_20260710/campaign_summary.json`
  recorded five correct onboard TRT detections, no added motion commands, and
  verified final STOP/lock. The refreshed laptop service is live on port 8791;
  the first live cycle waits only for confirmation that the physical room is
  closed to dogs and people.

## Direction Impact

| Surface | Effect |
| --- | --- |
| Cost | No new hardware spend for the hard-floor milestone |
| Timeline | The first decisive evidence can come from one bench session; completion depends on trace results |
| Claims strengthened | Fully onboard acquisition, controlled approach, repeatability, and safety |
| Claims deferred | Delivery-to-fiducial, carpet pivoting, and planner-grade world state |
| Work displaced | ArUco planner wiring pauses until acquisition and approach are repeatable |

## Operator and Agent Roles

The operator powers the robot, establishes a hard-floor test room closed to
dogs and people, clears the path, and places the ball. The agent owns transport
checks, locked deployment, camera and detector verification, trace collection,
diagnosis, code, tests, and evidence packaging.

Owner direction on 2026-07-10 additionally authorizes agent-operated unattended
acquisition cycles through `scripts/hardware_acquisition_unattended_runner.py`.
That lane is limited to no-contact ARC standoff, verified STOP/lock, trace
preservation, reverse replay of completed motion tapes, and post-reset geometry
verification. Contact/push, delivery, dashboard jog, and arbitrary GO/RESET
outside the guarded runner remain supervised.

When progress needs a physical action, safety observation, or owner decision,
the agent sends a mobile attention notification with the exact request. Safe
autonomous work continues between those operator gates.

## Stop Conditions

Bench continuation requires verified STOP, a locked bridge, fresh camera state,
coherent detector output, motors at zero after each episode, and a safe physical
area. If any requirement fails, preserve the newest trace and end the bench
sequence before changing controller logic.
