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
- The ball is currently live at about `z=0.73 m` and `center_error=-0.19`.
  Distance is in range; the first far-left episode is waiting only for lateral
  placement below `center_error=-0.60`. ARC is selected and the bridge remains
  locked.

## Direction Impact

| Surface | Effect |
| --- | --- |
| Cost | No new hardware spend for the hard-floor milestone |
| Timeline | The first decisive evidence can come from one bench session; completion depends on trace results |
| Claims strengthened | Fully onboard acquisition, controlled approach, repeatability, and safety |
| Claims deferred | Delivery-to-fiducial, carpet pivoting, and planner-grade world state |
| Work displaced | ArUco planner wiring pauses until acquisition and approach are repeatable |

## Operator and Agent Roles

The operator powers the robot, clears the floor, places the ball, selects ARC,
and presses GO or STOP. The agent owns transport checks, locked deployment,
camera and detector verification, trace collection, diagnosis, code, tests, and
evidence packaging. The operator exclusively owns motion activation and the GO,
RESET, and jog controls.

When progress needs a physical action, safety observation, or owner decision,
the agent sends a mobile attention notification with the exact request. Safe
autonomous work continues between those operator gates.

## Stop Conditions

Bench continuation requires verified STOP, a locked bridge, fresh camera state,
coherent detector output, motors at zero after each episode, and a safe physical
area. If any requirement fails, preserve the newest trace and end the bench
sequence before changing controller logic.
