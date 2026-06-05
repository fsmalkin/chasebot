# Fetch Robot-Side Rehearsal Preflight

- campaign_id: `analysis_fetch_robot_side_rehearsal_preflight_20260605`
- pass: `True`
- local_preflight_ready: `True`
- hardware_connected: `False`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `robot_side_fetch_rehearsal_preflight_ready`
- issues: `[]`
- readiness_summary: [artifact](/artifacts/session/analysis_fetch_hardware_transfer_readiness_post_seed_rehearsal_20260605_fixed/fetch_hardware_transfer_readiness/hardware_transfer_readiness_summary.json)
- rehearsal_plan: [artifact](/artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json)
- dashboard_url: http://100.112.221.6:8883

## Command Checks

- `python` pass=`True` path=`C:\Users\afutu\AppData\Local\Programs\Python\Python312\python.EXE`
- `powershell` pass=`True` path=`C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.EXE`
- `git` pass=`True` path=`C:\Program Files\Git\cmd\git.EXE`

## Script Checks

- scripts/run_dashboard_service.ps1 pass=`True`
- scripts/sync_runtime_workspace.ps1 pass=`True`
- scripts/run_first_uat.ps1 pass=`True`
- scripts/fetch_hardware_rehearsal_runner.py pass=`True`
- scripts/fetch_planner_route_replay_batch.py pass=`True`
- scripts/fetch_planner_seeded_generalization_gate.py pass=`True`

## Required Robot-Side Artifacts

- control_preflight.json with /controller_manager/list_controllers evidence
- mission_verdict.json
- visual/raw_camera_browser.mp4
- visual/topdown_telemetry_browser.mp4
- visual/world_stream.mp4
- visual/keyframe_review_contact_sheet.png
- operator visual review notes for start/setup, pre-contact, first contact, mid-push, terminal arrival, final rest

## Next Commands

- `powershell -ExecutionPolicy Bypass -File scripts/run_dashboard_service.ps1 -BindHost 0.0.0.0 -Port 8883`
- `powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro kilted`
- `python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_fetch_rehearsal_runtime_stack_smoke_20260605 --step-id runtime_stack_smoke --execute --timeout-s 1800`
- `python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_fetch_rehearsal_saved_anchors_20260605 --step-id saved_anchor_one_run_fetch_rehearsal --execute --timeout-s 2400`
- `python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_fetch_rehearsal_seed20260635_20260605 --step-id seed20260635_mixed_route_fetch_rehearsal --execute --timeout-s 3600`

## Claim Boundary

This preflight proves the local run package is ready to attempt robot-side rehearsal. It does not prove onboard TensorRT execution, physical camera behavior, field physics, or hardware delivery.
