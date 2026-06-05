# Fetch Planner Route UAT Scorecard

- Campaign: `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_analysis`
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
- Predicted contact quality: `{'watch': 6}`
- Predicted first-contact risk: `{'high': 2, 'medium': 4}`

## Route Coverage
- route=`fetch_ready_local` planner=`4` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`nav2_reposition_first` planner=`6` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`scan_or_perceive_first` planner=`6` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`
- route=`recovery_or_reaim` planner=`9` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`ambiguous_or_unsafe_no_go` planner=`5` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_planner` pass=`True` routes=`30/30` wrong_fetch=`0` guard_agree=`30/30` provider=`{'skipped_missing_openai_api_key': 30}` llm_shadow_ready=`False` source=`generated` seed=`20260636` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)

## Live Missions
- route=`recovery_or_reaim` session=`20260605T071908185252Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`high` score=`41.729` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T071908185252Z/golf_ball_circle_delivery/20260605T072026066292Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T072227157645Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`high` score=`41.429` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T072227157645Z/golf_ball_circle_delivery/20260605T072311116299Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T072440649066Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.193m` predicted=`watch` risk=`medium` score=`65.483` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T072440649066Z/golf_ball_circle_delivery/20260605T072519048388Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T072633943898Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`medium` score=`80.401` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T072633943898Z/golf_ball_circle_delivery/20260605T072730764583Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T072913696023Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`medium` score=`79.111` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T072913696023Z/golf_ball_circle_delivery/20260605T073028617469Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T073337808566Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`medium` score=`64.976` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T073337808566Z/golf_ball_circle_delivery/20260605T073410101431Z/mission_verdict.json)

## Visual Packages
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene02_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene02_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene03_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene03_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene04_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene04_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene07_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene07_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene08_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene08_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene15_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay_seed20260636_scene15_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
