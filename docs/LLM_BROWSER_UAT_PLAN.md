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

## What We Are Not Doing In This Phase

To keep the demo honest and legible, this phase does not include:

- freeform language control from the browser
- multi-step mission planning
- autonomous environment lifecycle control by the LLM
- end-to-end VLA control
- broader long-term roadmap commitments

## Recommended Execution Order

1. tighten the per-intent tool schema
2. revalidate headless proof repeatability
3. add the browser proof panel and proof state
4. run the same scenario through the dashboard as a viewer
5. conduct operator UAT on the browser demo
