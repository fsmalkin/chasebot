# Fetch Planner Route UAT Scorecard

- Campaign: `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_analysis`
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
- Predicted contact quality: `{'watch': 8, 'clean': 1}`
- Predicted first-contact risk: `{'high': 3, 'medium': 4, 'low': 2}`

## Route Coverage
- route=`fetch_ready_local` planner=`7` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`nav2_reposition_first` planner=`6` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`scan_or_perceive_first` planner=`7` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`
- route=`recovery_or_reaim` planner=`5` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`ambiguous_or_unsafe_no_go` planner=`5` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_planner` pass=`True` routes=`30/30` wrong_fetch=`0` guard_agree=`30/30` provider=`{'skipped_missing_openai_api_key': 30}` llm_shadow_ready=`False` source=`generated` seed=`20260639` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)

## Live Missions
- route=`recovery_or_reaim` session=`20260605T092835363811Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`high` score=`41.764` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T092835363811Z/golf_ball_circle_delivery/20260605T093238077017Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T093705334876Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`high` score=`46.533` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T093705334876Z/golf_ball_circle_delivery/20260605T093944555711Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T094215911302Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`high` score=`47.167` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T094215911302Z/golf_ball_circle_delivery/20260605T094732064886Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T094947648537Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`medium` score=`60.187` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T094947648537Z/golf_ball_circle_delivery/20260605T095036466797Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T095216418466Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`medium` score=`60.983` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T095216418466Z/golf_ball_circle_delivery/20260605T095305721646Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T095435354525Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.198m` predicted=`watch` risk=`medium` score=`63.338` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T095435354525Z/golf_ball_circle_delivery/20260605T095518711109Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T095638909786Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`medium` score=`72.563` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T095638909786Z/golf_ball_circle_delivery/20260605T095722586626Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T095836646728Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`low` score=`89.739` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T095836646728Z/golf_ball_circle_delivery/20260605T095919981671Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T100026696094Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`clean` risk=`low` score=`100.0` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T100026696094Z/golf_ball_circle_delivery/20260605T100110578163Z/mission_verdict.json)

## Visual Packages
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene23_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene23_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene15_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`3/3` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene15_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene13_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene13_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene12_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene12_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene18_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene18_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene17_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene17_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene06_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene06_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene25_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene25_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene08_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay_seed20260639_scene08_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
