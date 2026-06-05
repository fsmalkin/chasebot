# Fetch Visual UAT Package

- campaign_id: `hardware_rehearsal_seed20260643_mixed_all_routes_20260605_seed20260643_scene01_ambiguous_or_unsafe_no_go`
- pass: `True`
- route_only_proof: `True`
- mobile_watchable: `True`
- onboard_camera_watchable: `True`
- visual_confirmation_seen: `True`
- local_fetch_visual_confirmed: `False`
- planner_route_only_visual_confirmed: `True`
- planner_gate_green: `True`
- local_fetch_pass_seen: `False`
- planner_route_only_pass_seen: `True`
- raw_local_fetch_pass_seen: `False`
- fetch_marker_geometry_mismatch_seen: `False`
- fetch_model_provenance_invalid_seen: `False`
- stage_quality_green: `False`
- stage_quality_status: ``
- promotion_evidence: `False`
- interpretation: `planner_route_only_visual_uat_ready_not_promotion`

## Videos

### Browser-Safe Onboard Camera
- [raw_camera_browser.mp4](/artifacts/session/20260605T135059296860Z/visual/raw_camera_browser.mp4)

### Browser-Safe Context Views
- [topdown_telemetry_browser.mp4](/artifacts/session/20260605T135059296860Z/visual/topdown_telemetry_browser.mp4)
- [world_stream.mp4](/artifacts/session/20260605T135059296860Z/visual/world_stream.mp4)

## All Video Artifacts
- [raw_camera_browser.mp4](/artifacts/session/20260605T135059296860Z/visual/raw_camera_browser.mp4)
- [topdown_telemetry_browser.mp4](/artifacts/session/20260605T135059296860Z/visual/topdown_telemetry_browser.mp4)
- [world_stream.mp4](/artifacts/session/20260605T135059296860Z/visual/world_stream.mp4)
- `yolo_debug.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`
- `raw_camera.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`
- `topdown_telemetry.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`

## Video Recovery
- `raw_camera_browser.mp4` source=`raw_keyframes` ok=`True` frames=`11` previous=`video_missing_or_tiny` error=``
- `topdown_telemetry_browser.mp4` source=`topdown_keyframes` ok=`True` frames=`11` previous=`video_missing_or_tiny` error=``
- `world_stream.mp4` source=`world_stream_frames` ok=`True` frames=`73` previous=`video_missing_or_tiny` error=``

## Visual Keyframe Reviews
- [keyframe_review_contact_sheet.png](/artifacts/session/20260605T135059296860Z/visual/keyframe_review_contact_sheet.png) session=`20260605T135059296860Z` ok=`True` selected=`10` paired=`11` source=`raw_topdown_keyframes` error=``

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260643_rough_breadth_50x4_20260605_planner` pass=`True` routes=`50/50` wrong_fetch=`0`

## Seeded Evidence
- none

## Stage Quality
- none

## Missions
- route=`ambiguous_or_unsafe_no_go` session=`20260605T135059296860Z` fetch_to_pose=`False` route_only=`True` raw_fetch_to_pose=`False` executor=`safe_no_go` reason=`planner_route_only_local_fetch_withheld` closest=`1.718m` geometry=`unknown` geometry_reason=`` model_provenance=`True` target_model=`calibrated_golf_ball` ai_mode=`` route_outcome=`safe_no_go_selected` [summary](/artifacts/session/20260605T135059296860Z/golf_ball_circle_delivery/20260605T135430394230Z/mission_verdict.json)

## Visual Evidence
- `artifacts/session/20260605T135059296860Z/visual` confirmation=`True` visual_demo=`False` world_stream=`True` target_persistence=`False` world_degraded=`False` world_failure=``

## Warnings
- `visual_confirmation_keyframe_recovery`
