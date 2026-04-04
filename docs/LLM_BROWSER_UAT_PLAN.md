# LLM Browser UAT Plan

## Purpose

This document captures the next steps from the current headless LLM proof to an operator-facing browser UAT demo.

For the underlying layered control model that this browser demo sits on top of, see [LLM_CONTROL_ARCHITECTURE.md](./LLM_CONTROL_ARCHITECTURE.md).

The target demo is specific and concrete:

1. the robot starts without the ball in view
2. the LLM-driven control path causes a visible search turn
3. the ball enters perception
4. the LLM-driven control path causes motion toward the ball
5. the browser dashboard shows that sequence clearly enough for operator UAT

## Current Status

Current working baseline:

- headless proof exists for the turn-then-go path
- the frozen contract includes `search_for_target`
- the authoritative brain executor exists
- the shadow supervisor and provider path exist
- the dashboard is still not the primary proof surface for this sequence

Current limitation:

- the browser dashboard does not yet present the emitted LLM decision sequence and proof verdict in a simple UAT-ready way
- the provider path can still produce avoidable invalid outputs when the schema is too permissive for `gpt-5-nano`

## Immediate Goal

Promote the current headless proof into a browser UAT demo only after the action-selection path is hardened and the emitted decision sequence is visible in the dashboard.

## Outcome We Are Driving Toward

Near-term success means all of the following are true in one operator-visible flow:

1. the browser starts from Docker Desktop with minimal operator friction
2. the operator runs `LLM Turn + Go`
3. the robot visibly turns until the ball is seen
4. the robot then visibly moves toward the ball
5. the browser shows the same high-level decision sequence and final verdict
6. the same behavior remains grounded in the frozen contract and deterministic lower layers

This is intentionally narrower than full autonomy. The goal is to prove that the current bounded LLM layer can supervise a real behavior legibly and repeatably.

## Next Steps

These are the concrete next slices from the current baseline.

### Step 1: Repeatability Gate For The Existing Turn-And-Go Proof

Goal:

- prove that the current turn-and-go path is stable enough to be treated as the baseline LLM demo

Work:

1. run the authoritative headless proof repeatedly on `container_kilted`
2. record a short run summary for each attempt
3. fail any run that:
   - emits an invalid tool output
   - leaves the frozen contract
   - fails to produce visible search then movement

Outcome:

- `3/3` consecutive green proof runs on the authoritative path
- one compact proof scorecard artifact for the run set

Why it matters:

- this turns the current single successful demo into a promotion-worthy baseline

### Step 2: Formalize Escalation Rules Above The Lower-Level Loops — Complete

Goal:

- make the supervisor policy more explicit than "pick one next step" by documenting and enforcing when it should escalate between search, acquire, plan, track, and stop

Completed work:

1. ✓ deterministic escalation table added to [LLM_CONTROL_ARCHITECTURE.md](./LLM_CONTROL_ARCHITECTURE.md) — 10-row policy stage ladder with conditions, preferred intents, and allowed intents
2. ✓ unsafe conditions documented: search exhausted, pursuit without feedback, scenario error
3. ✓ stage transitions documented: forward progression (blocked → search → acquire → plan → track) and backward re-escalation paths
4. ✓ policy test suite expanded from 11 to 19 tests covering all escalation rows, unsafe conditions, and blocked states
5. ✓ existing `brain_supervisor_policy.py` already implements the table correctly — no code changes needed

Outcome:

- a clear, testable escalation table
- fewer ambiguous transitions in the LLM decision path
- a cleaner bridge from proof demo to the longer-term bounded-supervisor design

### Step 3: Generalize From One Proof To The Visible-Ball M3 Scenarios — Complete

Goal:

- show that the bounded LLM layer is supervising a reusable policy pattern, not only one custom proof harness

Completed work:

1. ✓ `visit_m3_positions` scenario added — visits center (0.0m), left (+0.12m), and right (-0.12m) targets using the same bounded supervisor policy
2. ✓ sim truth probe and dashboard model name lists extended for M3 visit target names
3. ✓ 3/3 M3 positions visited on attempt 0 (0.34m, 0.32m, 0.27m — all within 0.35m tolerance)
4. ✓ same digest, frozen action space, and policy layer used across all scenarios
5. ✓ combined with three-ball sequence: 6/6 unique target positions visited successfully across two scenarios

Outcome:

- one supervisor policy operating across the visible-ball demo set
- stronger confidence that the browser UAT demo is representative, not staged

### Step 3b: Target Prior Contract For Multi-Target Discrimination — Complete

Goal:

- make the executor's target lock verification portable to hardware by using mission-provided priors instead of sim ground truth

Problem:

- the executor currently has no way to tell Ball 1 from Ball 2 without an external oracle
- the proposed sim-truth gate (reading `truth_state.json` from Gazebo's god-view) solves this in sim but creates a dead end for hardware
- we should solve target discrimination in sim before loading into hardware, using a mechanism that transfers

Completed work:

1. ✓ visit mission runtime state extended with `current_target_prior` (set on first target lock, cleared before each spawn)
2. ✓ executor reads target priors from the mission layer's runtime state via `--visit-runtime-json`
3. ✓ executor's lock gate checks detection world position against the mission-provided prior (0.50m tolerance)
4. ✓ prior-based track approach: when depth estimation error causes detection-based goals to fall short, the executor dispatches nav goals toward the prior position with tight 0.05m approach distance
5. ✓ visit runtime path plumbed end-to-end: `CHASECAR_VISIT_RUNTIME_PATH` env var through compose → launch → executor CLI
6. ✓ `visit_single_ball_proof` scenario passes (0.33m visit distance, within 0.35m tolerance)
7. ✓ bugs fixed: port 8860 conflict, 409 intent ownership guard, approach_timeout depth-error gap
8. ✓ `visit_three_ball_sequence` passes: 3/3 balls visited on attempt 0 (0.34m, 0.33m, 0.34m)
9. ✓ mission runner's sim-truth lock rejection bypassed in visit missions — executor's prior gate is authoritative
10. ✓ sim truth probe is a test-time validation oracle, not a runtime dependency

Outcome:

- the executor's target discrimination works identically in sim and on hardware
- the sim truth probe becomes a test-time confidence check, not a runtime dependency
- hardware POC does not hit a "we never built the real version" wall

Why it matters:

- this is the difference between "works in sim" and "works on the robot" for any multi-target scenario

### Step 4: Finish The Minimal Browser UAT Surface — Complete

Goal:

- keep the browser simple enough that an operator can understand the demo without reading engineering detail

Current state (meets the acceptance criteria):

1. ✓ Watch tab: World Surface + YOLO Debug feeds, proof stage bar, event log, environment/scenario controls
2. ✓ Drive tab: "What the LLM sees" (compact digest) + "Your action" (same bounded intent buttons the LLM has) — interactive demo of the layered architecture
3. ✓ Inspect tab: L1 robot behavior, L2 LLM decision layer, L3 raw signals — maps directly to the architecture layers, collapsed by default
4. ✓ all scenarios (including visit missions and M3 positions) available from the Scenarios dropdown
5. ✓ browser reflects authoritative backend state via `/api/state` polling — not a second LLM path

Outcome:

- a browser surface that clearly answers:
   - what scenario is running
   - what the LLM most recently caused
   - whether the robot responded
   - whether the run passed

### Step 5: Prepare The On-Machine Model Lane Without Changing The Control Shape — Complete

Goal:

- preserve a path from Wi-Fi/cloud inference to a smaller on-device model later

Current state (meets the acceptance criteria):

1. ✓ digest is bounded and fixed-shape (`brain_state_digest.py`)
2. ✓ action space is canonical and small (6 frozen intents)
3. ✓ provider abstraction exists (`llm_provider_base.py` — `DecisionProvider` protocol)
4. ✓ replay comparison tool exists (`llm_provider_replay_compare.py`) — replays recorded state history across providers and compares decisions
5. ✓ local provider placeholders exist (`llm_provider_local.py` — `LocalStubProvider` and `LocalModelProvider`)
6. ✓ the deterministic policy layer (`brain_supervisor_policy.py`) works identically regardless of provider — it owns stage/intent selection, the provider is optional

Outcome:

- a realistic path toward local inference on the Orin Nano GPU without reworking the architecture
- same digest, same action space, same policy/gating layer — only the provider backend changes

## Phase 1: Harden The Headless Decision Path

### Objective

Reduce invalid provider outputs and make the LLM action path easier to trust before we expose it in the browser.

### Next changes

1. Replace the single generic action tool with one strict tool per decision:
   - `emit_search_for_target`
   - `emit_acquire_target`
   - `emit_plan_to_target`
   - `emit_track_target`
   - `emit_abort`
   - `emit_safe_stop`
   - `emit_blocked`
2. Expose only the legal subset of tools for the current digest state.
3. Keep `tool_choice` required and keep deterministic validation fail-closed.
4. Treat any invalid provider output as `blocked`, never as a near-match.

### Acceptance

1. No extra-arg failures in the proof path for repeated runs.
2. Headless proof stays inside the frozen contract and canonical args every time.
3. The proof harness passes at least 3 consecutive times on the authoritative path.

## Phase 2: Add Proof-Focused Dashboard State

### Objective

Make the browser surface show the LLM proof in a way that is easy to understand without opening engineering-heavy detail.

### Dashboard additions

Default view should gain a small `LLM Proof` panel with:

- current proof status:
  - `waiting`
  - `searching`
  - `target locked`
  - `moving to target`
  - `completed`
  - `failed`
- latest emitted LLM decision
- latest executor feedback
- last evaluation time
- session proof verdict when the run ends

Advanced view can include:

- recent decision timeline
- preview gate result per decision
- provider/model name
- artifact links

### API/state additions

Extend `GET /api/state` with a compact proof section:

- `llm_proof.status`
- `llm_proof.latest_decision`
- `llm_proof.latest_feedback`
- `llm_proof.verdict`
- `llm_proof.artifact_dir`

### Acceptance

1. A first-time operator can tell whether the system is still searching or has moved on to go-to-target behavior.
2. The dashboard shows the same decision sequence that appears in artifacts.
3. The default page remains simple and does not require opening Advanced.

## Phase 3: Create A Dedicated Browser UAT Demo Flow

### Objective

Use the dashboard as the operator-facing proof surface, not as a second execution path.

### Demo flow

1. Open Docker Desktop.
2. Start the Chasecar app.
3. Open the dashboard.
4. Start the environment.
5. Run the dedicated turn-then-go proof scenario.
6. Watch the robot:
   - turn until the ball becomes visible
   - then move toward it
7. Observe the proof panel update through the same sequence.

### Browser UAT surface requirements

The operator should be able to answer these questions without opening Advanced:

1. Is the LLM path idle, searching, or moving?
2. What decision was emitted most recently?
3. Did the robot actually respond to that decision?
4. Did the demo finish successfully?

### Acceptance

1. During the run, the browser clearly shows:
   - `search_for_target(ball)`
   - then `plan_to_target(0.25)` or equivalent bounded move progression
   - then motion completion or steady tracking state
2. The robot visibly turns before it moves.
3. The world and topdown panes show the same sequence as the proof panel.
4. The final browser state and session artifacts agree on pass/fail.

## Phase 4: Browser UAT Readiness Gate

Promote to operator-facing UAT only when all of the following are true:

1. Headless proof is green for at least 3 consecutive runs.
2. No invalid provider-output path escapes fail-closed handling.
3. The dashboard default view shows the proof sequence clearly.
4. The same-session artifact bundle contains:
   - decision history
   - executor feedback
   - proof verdict
   - visual evidence

## Clear Exit Outcomes

The plan should produce these visible outcomes in order:

### Outcome A: Stable Proof Baseline

- the turn-and-go proof passes repeatedly
- provider/gating failures are fail-closed rather than ambiguous
- the same proof can be trusted as a baseline demo

### Outcome B: Clear Layered Supervisor Behavior

- the LLM remains the high-level bounded decision layer
- deterministic policy and preview logic remain the contract/safety layer
- executor and lower loops remain the real-time control layer

### Outcome C: Browser UAT Demo That Is Easy To Read

- operator can run the demo from Docker Desktop
- operator sees turn, detect, and move in the two main panes
- operator sees the same story reflected in the run log and proof state

### Outcome D: Future Local-Model Compatibility

- digest and action space stay small enough for a local provider benchmark
- we do not bake cloud-only assumptions into the control model

## Alignment With Long-Term Roadmap

This plan aligns with the longer-term roadmap in [ROADMAP_2026_H2.md](./ROADMAP_2026_H2.md) and the current architecture note in [LLM_CONTROL_ARCHITECTURE.md](./LLM_CONTROL_ARCHITECTURE.md) in these ways:

1. It preserves the Docker-first, authoritative `container_kilted` lane instead of introducing a separate debug-only execution path.
2. It builds on the frozen pre-LLM contract rather than widening the robot action surface prematurely.
3. It keeps the LLM at the supervisory layer and leaves lower-level perception, planning, and control loops deterministic.
4. It treats browser UAT as a promotion gate after headless proof repeatability, which matches the repo's broader headless-first promotion philosophy.
5. It keeps the digest/provider split compatible with the longer-term goal of evaluating a smaller on-machine model on Orin Nano hardware.

## Long-Term Connection Without Overcommitting

This plan is meant to support, but not prematurely expand into, the broader long-term goals:

- high-level LLM planning over bounded subsystem capabilities
- explicit escalation between search, acquire, plan, track, and safe-stop behaviors
- eventual provider flexibility between Wi-Fi/cloud and local inference
- operator-visible trust and evidence before any broader autonomy claims

It does not commit us yet to:

- open-ended task planning
- browser freeform prompt control
- end-to-end learned action generation
- autonomous environment lifecycle management by the LLM

## What We Are Not Doing In This Phase

To keep the demo honest and legible, this phase does not include:

- freeform language control from the browser
- multi-step mission planning
- autonomous environment lifecycle control by the LLM
- end-to-end VLA control
- broader long-term roadmap commitments

## Recommended Execution Order

1. ✓ lock in `3/3` repeatability for the current turn-and-go proof
2. ✓ formalize escalation rules in the policy layer
3. ✓ generalize the bounded supervisor across the visible-ball M3 scenarios
4. ✓ implement target prior contract so multi-target discrimination transfers to hardware
5. ✓ browser UAT surface meets acceptance criteria
6. ✓ provider abstraction and replay comparison infrastructure in place for future local-provider lane
7. **direct intent dispatch — eliminate docker-exec-per-intent bottleneck** (in progress)

### Step 7: Direct Intent Dispatch — Eliminate Docker-Exec-Per-Intent Bottleneck

Goal:

- reduce intent dispatch latency from ~13s to under 1s so the UAT demo feels responsive and the architecture matches the real-time ambition

Problem:

- every intent dispatch currently spawns: `docker exec` → bash sourcing → Python startup → rclpy init → readiness wait (12s) → publish → observe (3s) → exit
- this adds ~13s between the LLM deciding and the robot moving
- the executor (`brain_intent_executor.py`) is already a long-running ROS2 node that could process intents instantly, but intents still route through the heavyweight subprocess path

Approach:

1. add a file-based intent inbox to the executor: it watches `runtime/dashboard/intent_inbox.json` via a 10Hz timer
2. when a new intent appears, the executor processes it immediately (same `_on_intent` path as the ROS2 topic)
3. executor writes acknowledgment to `runtime/dashboard/intent_ack.json`
4. dashboard writes intents to the inbox file instead of spawning `docker exec`
5. dashboard polls the ack file (up to 2s) for confirmation, then collects feedback from executor state as usual
6. the ROS2 topic path remains as a fallback — nothing is removed

Acceptance:

1. intent dispatch latency < 1s (measured from dashboard dispatch to executor processing)
2. LLM Turn+Go proof passes end-to-end with the new path
3. existing tests pass without regression
4. dashboard UI scenario trigger works for operator UAT
