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

## Phase 1: Harden The Headless Decision Path — Complete

### Objective

Reduce invalid provider outputs and make the LLM action path easier to trust before we expose it in the browser.

### Completed work

1. ✓ one strict tool per decision: `emit_search_for_target`, `emit_acquire_target`, `emit_plan_to_target`, `emit_track_target`, `emit_abort`, `emit_safe_stop`, `emit_blocked` (in `llm_provider_openai.py` `INTENT_TOOL_NAMES`)
2. ✓ only the legal subset of tools exposed for the current digest state (`_ready_intents_from_digest`)
3. ✓ `tool_choice: required` enforced on every provider call
4. ✓ invalid provider output → `blocked_decision`, never a near-match (`validate_decision_against_contract`, `validate_decision_against_canonical_space`)

### Acceptance — met

1. ✓ no extra-arg failures in the proof path for repeated runs
2. ✓ headless proof stays inside the frozen contract and canonical args every time
3. ✓ proof harness passes 3+ consecutive times on the authoritative path

## Phase 2: Add Proof-Focused Dashboard State — Complete

### Objective

Make the browser surface show the LLM proof in a way that is easy to understand without opening engineering-heavy detail.

### Completed work

1. ✓ `GET /api/state` includes: `proof_state` (waiting/searching/target_locked/moving/completed/failed), `latest_proof_decision`, `latest_proof_feedback`, `proof_verdict`, `proof_artifact_dir`
2. ✓ `llm_supervisor` section in state: `latest_decision`, `mode`, `model`, `status`, `recent_history`
3. ✓ Watch tab default view shows proof stage bar and event log — operator can tell searching vs moving without opening Advanced
4. ✓ Inspect tab provides decision timeline, provider/model, artifact links

### Acceptance — met

1. ✓ first-time operator can tell whether the system is searching or moving
2. ✓ dashboard shows the same decision sequence that appears in artifacts
3. ✓ default page remains simple

## Phase 3: Create A Dedicated Browser UAT Demo Flow — Complete

### Objective

Use the dashboard as the operator-facing proof surface, not as a second execution path.

### Completed demo flow

1. ✓ Open Docker Desktop → Start the Chasecar app → Open dashboard at `http://localhost:8860/`
2. ✓ Start the environment (Start button or `POST /api/env/start`)
3. ✓ Run LLM Turn + Go scenario from Scenarios dropdown
4. ✓ Watch the robot turn until the ball is visible, then move toward it
5. ✓ Proof panel updates through waiting → searching → target_locked → moving → completed

### Acceptance — met

1. ✓ browser shows `search_for_target(ball)` → `acquire_target(ball)` → `plan_to_target(0.25)` → `track_target()` progression
2. ✓ robot visibly turns before moving
3. ✓ world and topdown panes show the same sequence as the proof panel
4. ✓ final browser state and session artifacts agree on pass/fail

## Phase 4: Browser UAT Readiness Gate — Complete

All gate criteria met:

1. ✓ headless proof green for 3+ consecutive runs (multiple sessions)
2. ✓ no invalid provider-output path escapes fail-closed handling
3. ✓ dashboard default view shows proof sequence clearly
4. ✓ same-session artifact bundle contains:
   - `command_history.jsonl` (decision history)
   - `brain_feedback.jsonl` + `brain_state.json` (executor feedback)
   - `scenarios/llm_turn_then_go_proof.json` (proof verdict)
   - `raw_camera.mp4`, `world_stream.mp4`, `topdown_telemetry.mp4`, `yolo_debug.mp4` (visual evidence)

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
- outdoor field deployment for sports ball retrieval (grass/turf, real perception, weather variability)

The route planning phase is the bridge: it proves multi-target planning logic
in sim using the same decision shape that transfers to outdoor hardware. If a
lightweight model can handle route planning in sim, the same model runs on the
robot's Orin Nano GPU on the field — no cloud dependency, no latency penalty.

It does not commit us yet to:

- open-ended task planning
- browser freeform prompt control
- end-to-end learned action generation
- autonomous environment lifecycle management by the LLM

## What We Are Not Doing In This Phase

To keep the demo honest and legible, this phase does not include:

- freeform language control from the browser
- autonomous environment lifecycle control by the LLM
- end-to-end VLA control

## Next Phase: LLM Route Planning and Model Evaluation

The single-target UAT phase is complete. The next phase promotes the LLM from
reactive supervisor to route planner, then evaluates lightweight models for
on-robot inference. This is the sim proving ground for the end-state use case:
a robot on a grass or turf field retrieving scattered sports balls after practice.

### Route Planning Status Snapshot

Fresh-session route planning now clears the main object-avoidance bar: the robot
visits all 3 balls and avoids driving through already-visited balls on the next leg.

```mermaid
flowchart LR
    A[Spawn 3 balls] --> B[LLM chooses route]
    B --> C[visit_target target_id]
    C --> D[Vision + depth-backed scan]
    D --> E[Visited-target obstacle cloud]
    E --> F[Nav2 local/global costmaps]
    F --> G[Avoid visited balls on next leg]
```

Validated fresh-session evidence:

1. `artifacts/session/20260412T021011Z/visit_mission/20260412T021044Z/mission_verdict.json` — pass
2. `artifacts/session/20260412T022002Z/visit_mission/20260412T022019Z/mission_verdict.json` — pass
3. `artifacts/session/20260412T021011Z/route_clearance_monitor_persistent_obstacles.jsonl` — minimum center clearance to visited `ball_b` during the `ball_a` leg: `0.269 m`
4. `artifacts/session/20260412T022002Z/route_clearance_monitor_fresh2.jsonl` — minimum center clearance to visited `ball_b` during the `ball_a` leg: `0.262 m`

What changed to make that possible:

1. the HSV obstacle scan now uses D415 depth-backed ranges instead of pixel-only heuristics
2. Nav2's `BaseObstacle` critic is weighted strongly enough to matter in route choice
3. visited targets are republished as persistent world-frame obstacle points so the next leg still sees them as obstacles

Repeatability status:

1. `visit_route_planning` now behaves as a one-click self-contained dashboard scenario: the dashboard queues a sim reset before launch so each click starts from a fresh session
2. consecutive operator clicks validated without a manual env restart:
   - `artifacts/session/20260412T033747Z/visit_mission/20260412T033759Z/mission_verdict.json` â€” pass
   - `artifacts/session/20260412T033934Z/visit_mission/20260412T033947Z/mission_verdict.json` â€” pass
3. the mission runner still uses the canonical origin anchor for route-planning target spawn, so the target field remains deterministic even if the robot pose from the previous run was near a ball

See [ROADMAP_2026_H2.md](./ROADMAP_2026_H2.md) for the full 3-step plan:

1. **LLM-planned multi-target route** — LLM decides visit order for 3+ balls based on visibility and proximity; same frozen contract and deterministic lower layers
2. **Stabilize on current GPT provider** — 5+ consecutive green runs, baseline quality scorecard (path length, visit order optimality, time)
3. **Model evaluation for on-robot inference** — replay GPT decision traces through lightweight candidates (Phi-3-mini, Llama-3.2-3B, Qwen-2.5-3B) on Orin Nano GPU; live end-to-end proof with top candidate

### New capabilities needed

- `visit_target(target_id)` intent — high-level planning intent for target selection
- multi-target digest — remaining targets, visited targets, per-target visibility and estimated distance
- route planning policy stage above the existing search/acquire/plan/track stages
- `visit_route_planning` dashboard scenario

## Recommended Execution Order

1. ✓ lock in `3/3` repeatability for the current turn-and-go proof
2. ✓ formalize escalation rules in the policy layer
3. ✓ generalize the bounded supervisor across the visible-ball M3 scenarios
4. ✓ implement target prior contract so multi-target discrimination transfers to hardware
5. ✓ browser UAT surface meets acceptance criteria
6. ✓ provider abstraction and replay comparison infrastructure in place for future local-provider lane
7. ✓ direct intent dispatch — eliminate docker-exec-per-intent bottleneck

### Step 7: Direct Intent Dispatch — Eliminate Docker-Exec-Per-Intent Bottleneck — Complete

Goal:

- reduce intent dispatch latency from ~13s to under 1s so the UAT demo feels responsive and the architecture matches the real-time ambition

Problem:

- every intent dispatch previously spawned: `docker exec` → bash sourcing → Python startup → rclpy init → readiness wait (12s) → publish → observe (3s) → exit
- this added ~13s between the LLM deciding and the robot moving
- the executor (`brain_intent_executor.py`) is already a long-running ROS2 node that could process intents instantly, but intents were routing through the heavyweight subprocess path

Completed work:

1. ✓ file-based intent inbox added to executor: watches `runtime/dashboard/intent_inbox.json` via existing 10Hz timer
2. ✓ executor processes inbox intents immediately through the same `_on_intent` path as the ROS2 topic
3. ✓ executor writes acknowledgment to `runtime/dashboard/intent_ack.json`
4. ✓ dashboard writes intents to inbox file instead of spawning `docker exec` (when gate-stack is up)
5. ✓ docker exec path preserved as `_run_intent_sync_docker` fallback when gate-stack is not ready
6. ✓ ROS2 topic subscription remains — nothing removed

Results:

1. ✓ intent dispatch latency: 13s → <1s (verified: `search_for_target` dispatched and `search_active=True` in same 1s poll)
2. ✓ LLM Turn+Go proof passes end-to-end with direct inbox dispatch
3. ✓ all 25 executor tests + 55 policy/mission tests pass
4. ✓ all intents confirmed `dispatch_method=direct_inbox` in command history
