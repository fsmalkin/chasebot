# Fetch Planner Route UAT Scorecard

- Campaign: `hardware_rehearsal_seed20260635_20260605_analysis`
- Evidence scope: `route_owner_visual_uat`
- Pass: `True`
- Interpretation: `randomized_route_owner_visual_uat_green`
- Promotion evidence: `False`
- Mission green: `True`
- Visual package green: `True`
- Execution quality: `clean`
- Execution watches: `0`
- Setup quality: `clean`
- Setup watches: `0`
- Contact quality: `clean`
- Contact watches: `0`
- First-contact blockers: `0`
- Predicted contact quality: `{'watch': 5, 'clean': 1}`
- Predicted first-contact risk: `{'medium': 3, 'low': 2, 'high': 1}`

## Route Coverage
- route=`fetch_ready_local` planner=`9` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`1` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`nav2_reposition_first` planner=`8` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`scan_or_perceive_first` planner=`4` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`
- route=`recovery_or_reaim` planner=`7` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`ambiguous_or_unsafe_no_go` planner=`2` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`

## Planner Gates
- `hardware_rehearsal_seed20260635_20260605_planner` pass=`True` routes=`30/30` wrong_fetch=`0` guard_agree=`30/30` provider=`{'skipped_missing_openai_api_key': 30}` llm_shadow_ready=`False` source=`generated` seed=`20260635` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)

## Live Missions
- route=`nav2_reposition_first` session=`20260605T062655532643Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`medium` score=`65.768` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T062655532643Z/golf_ball_circle_delivery/20260605T062733105356Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T062848905204Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`medium` score=`58.918` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T062848905204Z/golf_ball_circle_delivery/20260605T062920127412Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T063036140143Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.194m` predicted=`watch` risk=`medium` score=`58.293` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T063036140143Z/golf_ball_circle_delivery/20260605T063108236202Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T063225158607Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`clean` risk=`low` score=`100.0` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T063225158607Z/golf_ball_circle_delivery/20260605T063257224629Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T063400908945Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`low` score=`88.235` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T063400908945Z/golf_ball_circle_delivery/20260605T063432723094Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T063530711030Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`high` score=`43.454` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T063530711030Z/golf_ball_circle_delivery/20260605T063608675589Z/mission_verdict.json)

## Visual Packages
- `hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene02_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene02_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene03_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene03_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene05_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene05_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene07_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene07_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene08_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene08_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene09_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene09_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
