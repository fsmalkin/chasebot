# Fresh Thread Continuation Prompt

You are continuing work in `D:\dev\chasecar` on branch `object-centric-gather-policy-v1`.

## Telegram Instruction

Use the routed Telegram tools by default. Before first Telegram contact, choose a stable thread slug and call ensure_agent_thread or use send_agent_message(auto_create_topic=true). For decisions use send_agent_message(wait_for_response=true, block_until_response=false), record the wait_id, keep working on safe adjacent tasks, and check telegram_wait/telegram_status before handoff. Do not use legacy telegram_send/telegram_notify unless routed tools are unavailable.

Recommended stable thread slug: `chasecar-object-centric-gather-20260506`.

## Current Objective

Produce an object-centric gather policy version that passes the saved-layout `zero` and `plus45` pair for `corral_single_ball_place` using `object_centric_gather_policy_v1`.

Immediate objective: get saved-layout `zero` to a full pass. Do not run `plus45` until `zero` is clean enough under the existing gates. The current failure is downstream place/release, not MPPI or odom.

## Latest User Request And Accepted Plan

Latest user request in the old thread: stop implementation and create this handoff so a fresh Codex/Claude thread can pick up updated global prompt and routed Telegram MCP schema.

Accepted implementation plan before the handoff:

- Continue until a full saved-layout `zero` plus `plus45` pair passes.
- Patch only narrow object-centric geometry/control behavior in `scripts/gather_object_centric_policy_helpers.py` and tests unless there is strong evidence otherwise.
- Validate offline, sync runtime, run saved-layout `zero`, inspect the artifact, patch again if needed.
- Run `plus45` only after `zero` clears the relevant fresh approach gates and downstream zero is no longer the blocker.
- Stop the dashboard environment after every live run.

Do not tune MPPI, loosen readiness/pass gates, redefine `/odom`, change frozen contracts, add helper/manual-drive branches or overlays, or touch Telegram bridge files.

## Current Status

Current committed base noted at start of this work: `c884ba8 Add object-centric yaw settle and Telegram MCP updates`.

Current worktree is dirty and uncommitted. The most recent live zero run did not pass:

- Campaign: `live_object_centric_gather_policy_v1_zero_fast_positive_opposed_20260506`
- Summary: `artifacts/session/live_object_centric_gather_policy_v1_zero_fast_positive_opposed_20260506/gather_mission_repeatability/campaign_run_summary.json`
- Mission root: `artifacts/session/20260506T023643496161Z/gather_mission/20260506T023656Z`
- Result: return code `2`, mission failed with `release_roll_away`
- `latest_approach_pre_stage_handoff_pass_count=1`
- `latest_approach_stage_pose_reached_count=1`
- `latest_approach_capture_entry_pass_count=1`
- `entered_goal_side_before_capture_count=0`
- `fresh_attempt_pre_stage_handoff_pass_count=0`
- Fresh attempt failed with `entered_goal_side_before_capture`
- `plus45` has not been run in this continuation.

The dashboard environment was explicitly stopped after the last live run:

- `environment_state=stopped`
- `mission_status=idle`
- `session_id=20260506T023643496161Z`

The most recent patch is live-validated only to the above failed zero result. Do not assume it is good enough.

## Definition Of Done

Full goal:

- Saved-layout `zero` pass.
- Saved-layout `plus45` pass.
- No pre-stage ball motion/contact regression.
- No goal-side violation before capture.
- No readiness/pass gate changes.
- Dashboard stopped after validation.
- Offline tests and runtime sync green.

Immediate gate:

- Reproduce and fix the current saved-layout `zero` place/release failure without broadening the scope beyond object-centric helper/tests.
- If `zero` still fails before a fresh pre-stage handoff, stop and inspect that artifact before touching downstream behavior.

## Files Changed Or Relevant

Uncommitted dirty files currently reported by `git status --short`:

- `scripts/gather_mission_runner.py`
- `scripts/gather_object_centric_policy_helpers.py`
- `telegram_wait_bridge/wait_daemon.py`
- `telegram_wait_bridge/wait_service.py`
- `tests/test_gather_mission_runner.py`
- `tests/test_gather_object_centric_policy_helpers.py`

Cautions:

- `telegram_wait_bridge/wait_daemon.py` and `telegram_wait_bridge/wait_service.py` are externally owned dirty files. Do not edit, revert, format, or commit them unless Fred explicitly asks.
- `scripts/gather_mission_runner.py` and `tests/test_gather_mission_runner.py` were already dirty during this continuation. Do not revert them. The current handoff work did not intentionally modify them.
- Main active code surface is `scripts/gather_object_centric_policy_helpers.py`.
- Main active test surface is `tests/test_gather_object_centric_policy_helpers.py`.

Important helper/test work already in the dirty patch:

- Pre-stage and stage yaw/reverse geometry patches:
  - `object_stage_close_yaw_settle`
  - pre-stage early/deep/near/wide yaw settle envelopes
  - close/near/wide reverse-to-handoff branches
- Place/release patches accumulated during zero validation:
  - far/near line recenter and wide reel handling
  - positive and negative world-lateral recenter branches
  - centered pre-entry coast
  - inside-retrieval centerline rollthrough hold
  - latest fast positive-opposed far recenter envelope
- Helper test count is now `217 passed`.

Relevant inspected artifacts:

- Latest zero summary: `artifacts/session/live_object_centric_gather_policy_v1_zero_fast_positive_opposed_20260506/gather_mission_repeatability/campaign_run_summary.json`
- Latest zero state history: `artifacts/session/20260506T023643496161Z/gather_mission/20260506T023656Z/state_history.jsonl`
- Previous zero summary: `artifacts/session/live_object_centric_gather_policy_v1_zero_negative_world_reel_20260506/gather_mission_repeatability/campaign_run_summary.json`
- Previous mission root: `artifacts/session/20260506T023109606249Z/gather_mission/20260506T023123Z`
- Earlier centered-preentry run: `artifacts/session/live_object_centric_gather_policy_v1_zero_centered_preentry_coast_20260506/gather_mission_repeatability/campaign_run_summary.json`

## Commands And Results

Latest offline validation before the last live run:

```powershell
python -m pytest tests/test_gather_object_centric_policy_helpers.py -q
# 217 passed

python -m pytest tests/test_gather_mission_runner.py -q
# 140 passed

python -m pytest tests/test_gather_object_centric_policy_evaluator.py -q
# 2 passed

python -m pytest tests/test_gather_mission_repeatability_runner.py -q
# 36 passed

git diff --check
# passed; CRLF warnings only, including externally dirty Telegram files

powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro kilted
# RUNTIME_SYNC_OK=1
```

Latest live zero command:

```powershell
python scripts/gather_mission_repeatability_runner.py --dashboard-url http://127.0.0.1:8860 --scenario-id corral_single_ball_place --runs 1 --campaign-id live_object_centric_gather_policy_v1_zero_fast_positive_opposed_20260506 --provider openai --execution-mode direct --promotion-gate-mode pass_only --world-file yolo_test_world_v6_clean_uat_short_turf.world --surface-profile short_turf --gather-control-family object_centric_gather_policy_v1 --target-layout-json artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_diag_rerun_20260503/gather_goal_side_matrix/target_layouts/zero.json --max-retries-per-target 2
```

Latest live zero result:

- Failed with `release_roll_away`.
- Latest approach path passed pre-stage, stage, and capture-entry.
- Fresh attempt still failed before handoff with `entered_goal_side_before_capture`.
- Do not run `plus45` from this state.

Dashboard cleanup command was run after the live failure and reached stopped/idle.

## Active Background Processes Or Pending Waits

No needed long-running commands are active.

No known pending tool waits.

Dashboard environment was stopped after the final live run.

Docker has unrelated non-chasecar containers running; do not stop unrelated projects.

## Telegram Wait IDs

No Telegram wait_ids were created in the old thread.

Legacy Telegram MCP tools (`telegram_notify`) failed earlier with `Transport closed`; the fresh thread should use the routed Telegram tools per the instruction at the top of this file.

## Blockers And Decisions

Current blocker:

- Saved-layout `zero` still fails at release/place with `release_roll_away`.
- The latest artifact shows place behavior can still drift wide on the positive world-lateral side and fall back toward `capture` before successful retrieval. Inspect latest `state_history.jsonl` before patching again.

Recommended default if no human decision is available:

- Continue with narrow object-centric helper/test patches only.
- Do not edit mission gates, readiness constants, MPPI params, `/odom`, frozen contracts, Telegram bridge files, or runner behavior.
- Do not run `plus45` until a fresh zero run is clean enough to justify it.
- Stop the dashboard environment after every live attempt.

## Next Steps

1. Read repo guidance (`AGENTS.md`, and `CLAUDE.md` if present), then run `git status --short` and verify dashboard state. Use routed Telegram to announce start with slug `chasecar-object-centric-gather-20260506`.

2. Inspect the latest zero artifact before editing:

   ```powershell
   Get-Content artifacts/session/live_object_centric_gather_policy_v1_zero_fast_positive_opposed_20260506/gather_mission_repeatability/campaign_run_summary.json -Raw
   Get-Content artifacts/session/20260506T023643496161Z/gather_mission/20260506T023656Z/state_history.jsonl
   ```

   Focus on attempt `2`, `phase=place`, around rows where the ball drifts toward positive world `y` and the mode falls through toward `capture`.

3. Add the smallest helper/test patch that addresses the latest zero place/release failure. Likely surface: continue steering by world/zone lateral earlier or longer for the positive-side far/near drift without adding forward energy. Keep it in `scripts/gather_object_centric_policy_helpers.py` and `tests/test_gather_object_centric_policy_helpers.py`.

4. Run offline validation:

   ```powershell
   python -m pytest tests/test_gather_object_centric_policy_helpers.py -q
   python -m pytest tests/test_gather_mission_runner.py -q
   python -m pytest tests/test_gather_object_centric_policy_evaluator.py -q
   python -m pytest tests/test_gather_mission_repeatability_runner.py -q
   git diff --check
   powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro kilted
   ```

5. Run saved-layout `zero` only with a new unique campaign id, for example:

   ```powershell
   python scripts/gather_mission_repeatability_runner.py --dashboard-url http://127.0.0.1:8860 --scenario-id corral_single_ball_place --runs 1 --campaign-id live_object_centric_gather_policy_v1_zero_<short_patch_name>_20260506 --provider openai --execution-mode direct --promotion-gate-mode pass_only --world-file yolo_test_world_v6_clean_uat_short_turf.world --surface-profile short_turf --gather-control-family object_centric_gather_policy_v1 --target-layout-json artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_diag_rerun_20260503/gather_goal_side_matrix/target_layouts/zero.json --max-retries-per-target 2
   ```

6. Stop the dashboard environment after the live run, then inspect the new summary. If zero still fails, patch only after reading the new terminal artifact.

7. Run saved-layout `plus45` only after zero is sufficiently green under the accepted gates. Use the same saved layout source family and direct repeatability command shape, with a unique campaign id.

## Repo-Specific Rules That Matter

- Follow act-or-wait discipline: always be acting or explicitly waiting.
- Use routed Telegram for start, material milestones, blockers/decisions, and completion.
- Do not use legacy `telegram_send` or `telegram_notify` unless routed tools are unavailable.
- Prefer `rg`/`rg --files` for searches.
- Use `apply_patch` for manual file edits.
- Do not revert dirty user/external changes.
- Do not touch externally owned dirty Telegram files.
- Keep Nav2/MPPI as baseline evidence; this branch is object-centric manipulation policy work.
- Do not tune MPPI, loosen gates, redefine `/odom`, change frozen contracts, add helper/manual-drive branches, or edit mission readiness/pass constants.
- Runtime mirror path: `~/ros2_ws/src/chasecar_runtime`.
- Primary ROS distro: `kilted`.
- Saved-layout zero JSON: `artifacts/session/live_nav2_mppi_follow_path_reacquire_v1_capture_diag_rerun_20260503/gather_goal_side_matrix/target_layouts/zero.json`.
- Dashboard URL for live validation: `http://127.0.0.1:8860`.
