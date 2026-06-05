# Fetch Hardware Transfer Readiness

- campaign_id: `analysis_fetch_hardware_transfer_readiness_20260605`
- pass: `True`
- hardware_transfer_ready: `True`
- hardware_proven: `False`
- readiness_level: `ready_for_hardware_rehearsal`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_ready`
- issue_count: `0`

## Evidence Checks

- `regression_manifest` pass=`True` issues=`[]` [artifact](/artifacts/session/analysis_planner_moonshot_regression_set_seed20260635_preflight_20260605/fetch_moonshot_regression_manifest/regression_summary.json)
- `dashboard_plan` pass=`True` issues=`[]` [artifact](/runtime/dashboard/fetch_plan_data.json)
- `hardware_contract` pass=`True` issues=`[]` [artifact](/docs/ROBOT_HARDWARE_CONTRACT_ORIN_NANO.md)
- `hardware_constraints` pass=`True` issues=`[]` [artifact](/docs/ROBOT_HARDWARE_CONSTRAINTS.md)
- `tensorrt_runtime` pass=`True` issues=`[]` [artifact](/runtime/tensorrt/README.md)

## Open Hardware Gates

- `robot_side_live_rehearsal_not_run`
- `onboard_tensorrt_execution_not_proven`
- `physical_camera_visual_package_not_recorded`
- `field_physics_not_proven`

## Required Next Rehearsal

- runtime_target: `robot_fidelity_orin`
- inference_backend: `tensorrt_int8`
- minimum_live_contract: `saved anchors one-run plus one seed20260635-style mixed route sample before hardware promotion discussion`
- required_artifacts: `['control_preflight.json', 'mission_verdict.json', 'raw_camera_browser.mp4', 'topdown_telemetry_browser.mp4', 'world_stream.mp4', 'keyframe_review_contact_sheet.png']`
