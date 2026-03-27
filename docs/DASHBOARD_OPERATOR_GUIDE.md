# Dashboard Operator Guide

## Purpose

Use the browser dashboard for the simple operator flow:

1. Start the environment
2. Run the recommended capability demos
3. Watch the visual cues
4. Stop the environment

The dashboard is meant to help you trust and understand current real capabilities before a future LLM layer is added on top. It is the control/status plane; the recommended live operator view opens separately through Xpra.

## Launch

1. Open Docker Desktop.
2. Click play on the Chasecar app.
3. Open `http://127.0.0.1:8860`.
4. Use the `Open Xpra` link in the dashboard for the live visual session.

If the warm services are still coming up, the dashboard will load first and the controls will enable once the control plane is ready.

## Default Dashboard Flow

The landing view is intentionally simple.

- `Next Step` shows the single recommended action.
- `Session Status` shows only the operator essentials:
  - environment
  - scenario
  - phase
  - target
  - last result
  - session id
- `Main Visuals` keeps the world view and topdown telemetry visible at all times.
- `Live View` shows whether Xpra is ready and which backend is active.
- `Open Xpra` launches the recommended live operator surface.
- `Camera Detail` lets you switch between raw camera and YOLO debug without crowding the page.
- `What To Watch` explains the current visual cues in plain operator language.

Use `Advanced Controls` only when you want the deeper signal-level truth, frozen-intent tools, or manual scenario selector.

## Recommended Rehearsal Order

1. `Start Environment`
2. `m3_single_target`
3. `m3_center`
4. `m3_left`
5. `m3_right`
6. `multi_target_rehearsal`
7. `Stop Environment`

`Reset Sim` is available when you want a fresh session id without closing the dashboard.

## Expected Visual Observations

### Environment Start

What good looks like:

- `Environment` moves to `environment_ready`
- `Session ID` populates
- world and topdown panes begin updating
- camera detail panes become live when you switch tabs
- Xpra is ready and the `Open Xpra` link is available for the live session

### M3 Single Target

This is the first human-facing proof.

What to watch:

- the robot starts moving instead of sitting still
- the topdown pane shows a clear approach path
- the run resolves cleanly and the dashboard returns to ready

### M3 Center

This is a repeatability check for the simple forward motion story.

What to watch:

- the robot drives cleanly toward the centered target
- the path looks continuous, not hesitant
- the run returns to ready cleanly

### M3 Left

This proves the robot can handle a left offset target.

What to watch:

- the path visibly bends or offsets left
- the topdown pane shows the target offset left of center
- the robot settles after reaching the target

### M3 Right

This mirrors the left offset case.

What to watch:

- the path visibly bends or offsets right
- the topdown pane shows the target on the right side
- the run ends cleanly and returns to ready

### Multi-Target Rehearsal

This is mainly a motion-and-state handoff demo, not a dramatic camera demo.

What to watch:

- the robot moves through multiple legs instead of one
- `Target` changes as the rehearsal advances
- transition activity becomes active briefly during handoff
- the world and topdown views continue updating through the whole sequence
- the live operator view continues separately in Xpra if you keep it open

What not to expect:

- big camera effects
- flashy target handoff graphics
- dramatic phase changes beyond the visible motion and target progression

## Advanced Controls

Open `Advanced Controls` when you want:

- the `LLM Workbench` lanes:
  - perception
  - belief
  - decision
  - outcome
- the structured frozen-intent console with `Preview` then `Execute`
- quick frozen-intent buttons
- manual access to preset scenarios, including `m2_single_target`
- control-plane and warm-service detail

This is where you verify the real signal boundary, not just the operator story.

## Current Capability Boundary

### What the system has now

- perception from the current target pipeline
- goal creation and motion execution through the frozen control path
- track, abort, and safe_stop through the frozen intent set

### What a future LLM layer would sit on top of

- the frozen intent boundary
- current perception and state signals
- returned feedback and outcome signals

### What is not here yet

- freeform language understanding
- open-ended planning
- arbitrary task decomposition
- unbounded action selection

## Troubleshooting

### Dashboard loads but controls are disabled

- wait a few seconds for warm services to finish coming up
- open `Advanced Controls` and check warm-service/control-plane status

### Environment will not start

- confirm Docker Desktop is running
- confirm the Chasecar app is started in Docker Desktop
- use `Refresh` once before retrying

### Visual panes are blank

- make sure the environment is actually `environment_ready`
- give the session a few seconds to start publishing live images
- use `Reset Sim` if the session looks stale
- if the browser world pane looks stale, open the Xpra live view instead of treating the browser pane as authoritative

### Scenario looks stuck

- use `Stop Scenario`
- wait for the dashboard to return to ready
- rerun the recommended demo

### You want the exact technical truth

- open `Advanced Controls`
- inspect the workbench lanes and intent tools there

## Related Docs

- [First UAT Runbook](./FIRST_UAT_RUNBOOK.md)
- [LLM Browser UAT Plan](./LLM_BROWSER_UAT_PLAN.md)
- [LLM Research Notes](./LLM_RESEARCH_NOTES.md)
