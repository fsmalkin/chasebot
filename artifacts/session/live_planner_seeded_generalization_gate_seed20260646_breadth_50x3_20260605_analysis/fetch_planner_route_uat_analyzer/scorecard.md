# Fetch Planner Route UAT Scorecard

- Campaign: `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_analysis`
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
- Predicted contact quality: `{'watch': 9}`
- Predicted first-contact risk: `{'high': 3, 'medium': 3, 'low': 3}`

## Route Coverage
- route=`fetch_ready_local` planner=`8` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`nav2_reposition_first` planner=`11` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`scan_or_perceive_first` planner=`11` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`
- route=`recovery_or_reaim` planner=`9` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`ambiguous_or_unsafe_no_go` planner=`11` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_planner` pass=`True` routes=`50/50` wrong_fetch=`0` guard_agree=`50/50` provider=`{'skipped_missing_openai_api_key': 50}` llm_shadow_ready=`False` source=`generated` seed=`20260646` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)

## Live Missions
- route=`recovery_or_reaim` session=`20260605T163210153330Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.194m` predicted=`watch` risk=`high` score=`42.862` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T163210153330Z/golf_ball_circle_delivery/20260605T163528734697Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T163817727054Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.194m` predicted=`watch` risk=`high` score=`42.988` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T163817727054Z/golf_ball_circle_delivery/20260605T164117639005Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T164240635982Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`high` score=`48.694` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T164240635982Z/golf_ball_circle_delivery/20260605T164337931141Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T164524284741Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`medium` score=`58.704` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T164524284741Z/golf_ball_circle_delivery/20260605T164602941503Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T164730151943Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`medium` score=`59.184` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T164730151943Z/golf_ball_circle_delivery/20260605T164756320161Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T164937407125Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`medium` score=`60.282` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T164937407125Z/golf_ball_circle_delivery/20260605T165015923999Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T165141820473Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.198m` predicted=`watch` risk=`low` score=`81.259` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T165141820473Z/golf_ball_circle_delivery/20260605T165207803821Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T165308107491Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`low` score=`81.91` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T165308107491Z/golf_ball_circle_delivery/20260605T165334108398Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T165449258531Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.190m` predicted=`watch` risk=`low` score=`83.956` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T165449258531Z/golf_ball_circle_delivery/20260605T165515456181Z/mission_verdict.json)

## Visual Packages
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene39_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene39_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene35_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene35_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene45_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene45_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene48_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene48_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene50_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene50_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene47_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene47_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene08_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene08_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene06_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene06_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene10_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260646_breadth_50x3_20260605_replay_seed20260646_scene10_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
