# Fetch Visual UAT Package

- campaign_id: `hardware_rehearsal_saved_anchors_20260605_saved_anchor_right05`
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
- [raw_camera_browser.mp4](/artifacts/session/20260605T134446173266Z/visual/raw_camera_browser.mp4)

### Browser-Safe Context Views
- [topdown_telemetry_browser.mp4](/artifacts/session/20260605T134446173266Z/visual/topdown_telemetry_browser.mp4)
- [world_stream.mp4](/artifacts/session/20260605T134446173266Z/visual/world_stream.mp4)

## All Video Artifacts
- [raw_camera_browser.mp4](/artifacts/session/20260605T134446173266Z/visual/raw_camera_browser.mp4)
- [topdown_telemetry_browser.mp4](/artifacts/session/20260605T134446173266Z/visual/topdown_telemetry_browser.mp4)
- [world_stream.mp4](/artifacts/session/20260605T134446173266Z/visual/world_stream.mp4)
- `yolo_debug.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`
- `raw_camera.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`
- `topdown_telemetry.mp4` validation=`not_browser_h264_yuv420p:codec=mpeg4:pix_fmt=yuv420p`

## Video Recovery
- `raw_camera_browser.mp4` source=`raw_keyframes` ok=`True` frames=`28` previous=`video_missing_or_tiny` error=``
- `topdown_telemetry_browser.mp4` source=`topdown_keyframes` ok=`True` frames=`28` previous=`video_missing_or_tiny` error=``
- `world_stream.mp4` source=`world_stream_frames` ok=`True` frames=`162` previous=`video_missing_or_tiny` error=``

## Visual Keyframe Reviews
- [keyframe_review_contact_sheet.png](/artifacts/session/20260605T134446173266Z/visual/keyframe_review_contact_sheet.png) session=`20260605T134446173266Z` ok=`True` selected=`10` paired=`28` source=`raw_topdown_keyframes` error=``

## Planner Gates
- `dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604` pass=`True` routes=`3/3` wrong_fetch=`0`

## Seeded Evidence
- none

## Stage Quality
- none

## Missions
- route=`recovery_or_reaim` session=`20260605T134446173266Z` fetch_to_pose=`True` route_only=`False` raw_fetch_to_pose=`True` executor=`bounded_recovery_reaim` reason=`trajectory_intersects_delivery_radius` closest=`0.195m` geometry=`unknown` geometry_reason=`` model_provenance=`True` target_model=`calibrated_golf_ball` ai_mode=`` route_outcome=`` [summary](/artifacts/session/20260605T134446173266Z/golf_ball_circle_delivery/20260605T134529579483Z/mission_verdict.json)

## Visual Evidence
- `artifacts/session/20260605T134446173266Z/visual` confirmation=`True` visual_demo=`False` world_stream=`True` target_persistence=`False` world_degraded=`False` world_failure=``

## Warnings
- `visual_confirmation_keyframe_recovery`
