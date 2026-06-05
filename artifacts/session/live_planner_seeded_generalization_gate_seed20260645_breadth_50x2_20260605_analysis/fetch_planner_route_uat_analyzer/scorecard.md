# Fetch Planner Route UAT Scorecard

- Campaign: `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_analysis`
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
- Predicted first-contact risk: `{'high': 2, 'medium': 3, 'low': 1}`

## Route Coverage
- route=`fetch_ready_local` planner=`11` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`nav2_reposition_first` planner=`9` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`scan_or_perceive_first` planner=`11` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`
- route=`recovery_or_reaim` planner=`14` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`ambiguous_or_unsafe_no_go` planner=`5` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_planner` pass=`True` routes=`50/50` wrong_fetch=`0` guard_agree=`50/50` provider=`{'skipped_missing_openai_api_key': 50}` llm_shadow_ready=`False` source=`generated` seed=`20260645` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)

## Live Missions
- route=`recovery_or_reaim` session=`20260605T153331488473Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`high` score=`40.741` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T153331488473Z/golf_ball_circle_delivery/20260605T153733744130Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T153859946442Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`high` score=`41.6` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T153859946442Z/golf_ball_circle_delivery/20260605T153938869162Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T154101860604Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.198m` predicted=`watch` risk=`medium` score=`58.954` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T154101860604Z/golf_ball_circle_delivery/20260605T154127849585Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T154300021779Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`medium` score=`59.443` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T154300021779Z/golf_ball_circle_delivery/20260605T154332830268Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T154450774249Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`medium` score=`79.407` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T154450774249Z/golf_ball_circle_delivery/20260605T154522392427Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T154618474059Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.196m` predicted=`watch` risk=`low` score=`81.23` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T154618474059Z/golf_ball_circle_delivery/20260605T154644585413Z/mission_verdict.json)

## Visual Packages
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene30_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`3/3` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene30_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene15_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene15_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene09_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene09_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene45_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene45_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene13_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene13_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene07_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_replay_seed20260645_scene07_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
