# Session tie-off — June 11, 2026 (Claude supervisory session)

Cold-start brief for the next supervisory session. Written at handoff; verify
live state against the repo before acting — this file is a snapshot, not live
state.

## Where the project is

- Goal of record: Multi-Ball Retrieval v1 (see the `/goal` text in the Codex
  thread; decisions and bar below). Branch: `spike/fetch-multiball-open-field-20260606`.
- Fred's decisions (June 9, recorded in `docs/ROADMAP_2026_H2.md` and
  `docs/ACTIVE_WORKFLOW.md`): v1 promotes WITH bounded give-up accepted; the
  open-field setup trajectory owner is v1.1. Promotion bar: five consecutive
  green route-diverse seeds, delivery >= 90%, every non-delivery
  bounded-and-diagnosed, visual package green every run.
- Streak: **4/5 greens** — `20260647`, `20260648`, `20260649` (rerun2, after
  two environment-failed attempts), `20260650`.
- **Blocking item: seed `20260651` failed** as
  `live_multiball_route_diverse_seed20260651_4x3_breadth_20260611`. Scene 1
  delivered ball 1; step 2 `ball_2` (`local_setup_capture`) failed live —
  `runner_returned_nonzero` rc 2, runner reason
  `nav2_reposition_failed_before_fetch`; 0 env-fail rows, 0 bounded give-ups.
  Pointers: gate_summary.json under
  `artifacts/session/live_multiball_route_diverse_seed20260651_4x3_breadth_20260611/fetch_multiball_retrieval_gate/`,
  runner logs `runtime/live_multiball_route_diverse_seed20260651_4x3_breadth_20260611.{out,err}.log`,
  visual package `..._visual_package/`. **Next gate: classify env vs
  robot-behavior before any rerun or tuning.** Env → rerun, streak preserved.
  Robot-behavior → true red, stop-and-report trigger, streak broken.

## Lane ownership

- The GPT-5.5 Codex thread executes the v1 lane under the bounded plan in
  `docs/ACTIVE_WORKFLOW.md` ("Codex execution plan (June 9, 2026)"), with
  hard stop-and-report bounds. It recorded greens 3 and 4 (commits `75231dc`,
  `9827bc7`).
- New supervisory sessions can also reach Codex directly as an MCP subagent
  (`mcp__codex__codex`, pinned gpt-5.5 xhigh) — see the global working
  agreement for delegation rules.
- Claude sessions own design/review/research. Artifacts from this rotation:
  `docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md` (v1.1 design, judged
  study, mandatory grafts + requalification ladder; slice 2 needs Fred's
  sign-off) and `docs/ARCHITECTURE_SOTA_REVIEW_2026_06.md` (verdict: keep the
  deterministic stack; R1–R6 bounded follow-ups; open area: LLM-planner
  production evidence).

## Comms policy (changed June 10)

Telegram is retired for agent comms globally; the repo overlay (`AGENTS.md`,
committed `21ac149`) says: updates in chat plus repo handoff surfaces;
mobile push notifications for pings; routed Telegram only on explicit request.

## Running infrastructure (do not kill blindly)

- Dashboard service on port 8895: powershell wrapper + `dashboard_service.py`
  (pid file `runtime/dashboard_8895_codex_resume.pid`) — Codex-lane owned,
  stays up. All gate-runner PIDs in `runtime/*.pid` are dead as of this
  tie-off; no orphaned gates or subagents.
- Docker: `chasecar_gate_20260606235143-*` stack (sim-gate, gate-stack,
  world-viewer, etc.). `dashboard-control-1` reports unhealthy chronically,
  including during green runs — known red herring, but the stack has needed
  full restarts twice (June 9 wedges: HTTP 409 fresh-session conflict; world
  stream not ready). Restart escalation: POST /api/env/stop → kill `-Port
  8895` processes → relaunch `scripts/run_dashboard_service.ps1 -BindHost
  0.0.0.0 -Port 8895` → if still wedged, full gate-stack compose restart →
  verify a smoke session reaches `environment_ready` before any gate.

## Repo hygiene state at tie-off

- Working tree clean except untracked `runtime/` files — left untracked
  deliberately per repo convention (gate evidence lives in
  `artifacts/session/` + doc pointers; runtime logs/PIDs are local
  diagnostics). Includes three cached research source pages
  (`runtime/bianchini_page.html`, `runtime/push_anything*.html`) — safe to
  delete, re-fetchable from the URLs cited in the SOTA review.
- `runtime/visual_review_seed20260649/` and `..._seed20260650/` are
  Codex-lane frame-review scratch for the green records.

## Standard gate recipe (for reference)

```text
python scripts/fetch_multiball_retrieval_gate.py
  --campaign-id live_multiball_route_diverse_seed<SEED>_4x3_breadth_<DATE>
  --profile open_field_multiball_route_diverse_v1 --seed <SEED>
  --random-cases 4 --balls-per-scene 3 --planner-mode llm_supervised_guarded
  --fresh-dashboard-session --fresh-session-per-scene
  --dashboard-url http://127.0.0.1:8895 --fetch-delivery-radius-m 0.300
  --timeout-s 600 --package-timeout-s 240 --stop-on-fail
```

Dry-run first (`--dry-run`, drop the session/timeout flags) per convention.

## After the bar is met (sequenced, do not reorder)

1. v1 promotion package (gate ladder evidence rules in the planning docs).
2. Hardware entry (R5): qualify one-ball `fetch_to_pose` on the Orin with
   onboard TensorRT INT8 + physical camera — before any v1.1 capability work
   meets hardware.
3. v1.1 slice 1 per the design doc (twelve grafts + requalification ladder).
   Slice 2, contact-MPC spike (R3), and opennav_docking evaluation (R4) are
   proposals to Fred first.
