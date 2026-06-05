# Fetch Hardware Rehearsal Runner

- campaign_id: `analysis_fetch_hardware_rehearsal_runner_preflight_20260605`
- mode: `preflight`
- pass: `True`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_preflight_ready`
- next_action: `execute_runtime_stack_smoke`
- issues: `[]`
- plan_summary: [artifact](/artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json)

## Step Preflights

- `runtime_stack_smoke` pass=`True` issues=`[]`
  - command: `powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -IncludeVisual true`
  - required_artifacts: `['first_uat_summary.json', 'visual/raw_camera_browser.mp4', 'visual/world_stream.mp4']`
- `saved_anchor_one_run_fetch_rehearsal` pass=`True` issues=`[]`
  - command: `python scripts/fetch_planner_route_replay_batch.py --campaign-id hardware_rehearsal_saved_anchors_20260605 --gate-summary artifacts/session/dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604/fetch_planner_handoff_gate/gate_summary.json --max-per-route 3 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
  - required_artifacts: `['control_preflight.json', 'mission_verdict.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/world_stream.mp4', 'visual/keyframe_review_contact_sheet.png']`
- `seed20260635_mixed_route_fetch_rehearsal` pass=`True` issues=`[]`
  - command: `python scripts/fetch_planner_seeded_generalization_gate.py --campaign-id hardware_rehearsal_seed20260635_20260605 --seed 20260635 --random-cases 30 --planner-mode llm_supervised_guarded --max-per-route 2 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
  - required_artifacts: `['fetch_planner_handoff_gate/gate_summary.json', 'fetch_planner_route_replay_batch/batch_summary.json', 'fetch_planner_route_uat_analyzer/route_uat_summary.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/keyframe_review_contact_sheet.png']`
