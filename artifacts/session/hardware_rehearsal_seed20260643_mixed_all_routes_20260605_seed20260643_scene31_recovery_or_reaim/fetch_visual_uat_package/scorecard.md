# Fetch Visual UAT Package

- campaign_id: `hardware_rehearsal_seed20260643_mixed_all_routes_20260605_seed20260643_scene31_recovery_or_reaim`
- pass: `True`
- route_only_proof: `False`
- mobile_watchable: `True`
- onboard_camera_watchable: `True`
- visual_confirmation_seen: `True`
- local_fetch_visual_confirmed: `True`
- planner_route_only_visual_confirmed: `False`
- planner_gate_green: `True`
- local_fetch_pass_seen: `True`
- planner_route_only_pass_seen: `False`
- raw_local_fetch_pass_seen: `True`
- fetch_marker_geometry_mismatch_seen: `False`
- fetch_model_provenance_invalid_seen: `False`
- stage_quality_green: `False`
- stage_quality_status: ``
- promotion_evidence: `False`
- interpretation: `mobile_visual_uat_ready_not_promotion`

## Videos

### Browser-Safe Onboard Camera
- [raw_camera_browser.mp4](/artifacts/session/20260605T140137011496Z/visual/raw_camera_browser.mp4)

### Browser-Safe Context Views
- [topdown_telemetry_browser.mp4](/artifacts/session/20260605T140137011496Z/visual/topdown_telemetry_browser.mp4)
- [world_stream.mp4](/artifacts/session/20260605T140137011496Z/visual/world_stream.mp4)

## All Video Artifacts
- [raw_camera_browser.mp4](/artifacts/session/20260605T140137011496Z/visual/raw_camera_browser.mp4)
- [topdown_telemetry_browser.mp4](/artifacts/session/20260605T140137011496Z/visual/topdown_telemetry_browser.mp4)
- [world_stream.mp4](/artifacts/session/20260605T140137011496Z/visual/world_stream.mp4)
- `yolo_debug.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`
- `raw_camera.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`
- `topdown_telemetry.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`

## Video Recovery
- `raw_camera_browser.mp4` source=`raw_keyframes` ok=`True` frames=`32` previous=`video_missing_or_tiny` error=``
- `topdown_telemetry_browser.mp4` source=`topdown_keyframes` ok=`True` frames=`32` previous=`video_missing_or_tiny` error=``
- `world_stream.mp4` source=`world_stream_frames` ok=`True` frames=`193` previous=`video_missing_or_tiny` error=``

## Visual Keyframe Reviews
- [keyframe_review_contact_sheet.png](/artifacts/session/20260605T140137011496Z/visual/keyframe_review_contact_sheet.png) session=`20260605T140137011496Z` ok=`True` selected=`10` paired=`32` source=`raw_topdown_keyframes` error=``

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260643_rough_breadth_50x4_20260605_planner` pass=`True` routes=`50/50` wrong_fetch=`0`

## Seeded Evidence
- none

## Stage Quality
- none

## Missions
- route=`recovery_or_reaim` session=`20260605T140137011496Z` fetch_to_pose=`True` route_only=`False` raw_fetch_to_pose=`True` executor=`bounded_recovery_reaim` reason=`trajectory_intersects_delivery_radius` closest=`0.197m` geometry=`unknown` geometry_reason=`` model_provenance=`True` target_model=`calibrated_golf_ball` ai_mode=`` route_outcome=`` [summary](/artifacts/session/20260605T140137011496Z/golf_ball_circle_delivery/20260605T140244284875Z/mission_verdict.json)

## Visual Evidence
- `artifacts/session/20260605T140137011496Z/visual` confirmation=`True` visual_demo=`False` world_stream=`True` target_persistence=`False` world_degraded=`False` world_failure=``

## Warnings
- `visual_confirmation_keyframe_recovery`
