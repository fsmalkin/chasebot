# Fetch Hardware Rehearsal Plan

- campaign_id: `analysis_fetch_hardware_rehearsal_plan_20260605`
- pass: `True`
- hardware_rehearsal_plan_ready: `True`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_plan_ready`
- issues: `[]`
- readiness_summary: [artifact](/artifacts/session/analysis_fetch_hardware_transfer_readiness_20260605/fetch_hardware_transfer_readiness/hardware_transfer_readiness_summary.json)

## Runtime Contract

- runtime_target: `robot_fidelity_orin`
- inference_backend: `tensorrt_int8`
- dashboard_url: `http://127.0.0.1:8883`
- visual_review_required: `True`
- visual_review_phases: `['start_setup', 'pre_contact', 'first_contact', 'mid_push_or_coast', 'terminal_arrival', 'final_rest']`

## Planned Steps

### runtime_stack_smoke

- purpose: Confirm the robot_fidelity_orin/tensorrt_int8 stack and visual capture path before fetch scoring.
- promotion_evidence: `False`
- command: `powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -IncludeVisual true`
- required_artifacts: `['session:readiness_report.json', 'session:visual/operator_status.json', 'readiness_path:artifacts.coordinate_summary', 'readiness_path:artifacts.milestone_1_evidence_dir:screenshots/d415_color.png', 'readiness_path:artifacts.milestone_1_evidence_dir:screenshots/yolo_debug.png']`

### saved_anchor_one_run_fetch_rehearsal

- purpose: Run zero, left05, and right05 through the planner-routed fetch stack on the hardware rehearsal surface.
- promotion_evidence: `False`
- command: `python scripts/fetch_planner_route_replay_batch.py --campaign-id hardware_rehearsal_saved_anchors_20260605 --gate-summary artifacts/session/dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604/fetch_planner_handoff_gate/gate_summary.json --max-per-route 3 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
- required_artifacts: `['control_preflight.json', 'mission_verdict.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/world_stream.mp4', 'visual/keyframe_review_contact_sheet.png']`

### seed20260635_mixed_route_fetch_rehearsal

- purpose: Repeat the current broad mixed-route seed across Nav2-first, recovery/re-aim, and fetch-ready route owners.
- promotion_evidence: `False`
- command: `python scripts/fetch_planner_seeded_generalization_gate.py --campaign-id hardware_rehearsal_seed20260635_20260605 --seed 20260635 --random-cases 30 --planner-mode llm_supervised_guarded --max-per-route 2 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
- required_artifacts: `['fetch_planner_handoff_gate/gate_summary.json', 'fetch_planner_route_replay_batch/batch_summary.json', 'fetch_planner_route_uat_analyzer/route_uat_summary.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/keyframe_review_contact_sheet.png']`

## Pass Contract

- saved_anchors: `zero/left05/right05 one-run pass with browser-watchable onboard/context video`
- seeded_mixed_route: `seed20260635 executable route sample pass across fetch_ready_local, nav2_reposition_first, recovery_or_reaim`
- blocked_claims_until_recorded: `['robot_side_live_rehearsal', 'onboard_tensorrt_execution', 'physical_camera_visual_package', 'field_physics']`
