from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_manager_helpers as gather_manager  # noqa: E402


def test_manager_recovers_goal_side_while_pre_stage_is_on_the_wrong_side():
    decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="pre_stage",
            phase_elapsed_s=3.0,
            pre_stage_snapshot={"entered_goal_side_before_capture": True},
            phase_ready_observed=False,
            attempt_kind="initial_visit",
            latest_command_mode="pre_stage_escape_goal_side",
        )
    )

    assert decision.directive == "recover_goal_side"
    assert decision.next_phase == "pre_stage"


def test_manager_keeps_pre_stage_stable_until_a_ready_sample_is_observed():
    continue_decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="pre_stage",
            phase_elapsed_s=8.0,
            pre_stage_snapshot={"entered_goal_side_before_capture": False, "pre_stage_pose_reached": False},
            phase_ready_observed=False,
            attempt_kind="initial_visit",
            latest_command_mode="pre_stage_traverse",
        )
    )
    handoff_decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="pre_stage",
            phase_elapsed_s=8.5,
            pre_stage_snapshot={"entered_goal_side_before_capture": False, "pre_stage_pose_reached": True},
            phase_ready_observed=True,
            attempt_kind="initial_visit",
            latest_command_mode="pre_stage_ready",
        )
    )

    assert continue_decision.directive == "stabilize_pre_stage"
    assert continue_decision.next_phase == "pre_stage"
    assert handoff_decision.directive == "stabilize_stage"
    assert handoff_decision.next_phase == "stage"


def test_manager_keeps_stage_stable_until_a_ready_sample_is_observed():
    continue_decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="stage",
            phase_elapsed_s=1.5,
            approach_snapshot={"robot_on_goal_side": False, "staging_pose_reached": False},
            phase_ready_observed=False,
            attempt_kind="retry_visit",
            latest_command_mode="stage_align",
        )
    )
    handoff_decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="stage",
            phase_elapsed_s=1.9,
            approach_snapshot={"robot_on_goal_side": False, "staging_pose_reached": True},
            phase_ready_observed=True,
            attempt_kind="retry_visit",
            latest_command_mode="stage_ready",
        )
    )

    assert continue_decision.directive == "stabilize_stage"
    assert continue_decision.next_phase == "stage"
    assert handoff_decision.directive == "close_capture_gap"
    assert handoff_decision.next_phase == "capture_entry"


def test_manager_keeps_stage_handoff_latched_after_one_off_band_sample():
    decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="stage",
            phase_elapsed_s=2.4,
            approach_snapshot={"robot_on_goal_side": False, "staging_pose_reached": False},
            phase_ready_observed=False,
            phase_ready_latched=True,
            attempt_kind="retry_visit",
            latest_command_mode="stage_align",
        )
    )

    assert decision.directive == "close_capture_gap"
    assert decision.next_phase == "capture_entry"


def test_manager_hands_off_capture_entry_once_ready_is_observed():
    decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="capture_entry",
            phase_elapsed_s=3.8,
            capture_entry_snapshot={"capture_entry_reached": True, "robot_on_goal_side": False},
            phase_ready_observed=True,
            attempt_kind="initial_visit",
            latest_command_mode="capture_entry_ready",
        )
    )

    assert decision.directive == "handoff_to_capture"
    assert decision.next_phase == "capture"


def test_manager_keeps_capture_entry_handoff_latched_after_one_off_band_sample():
    decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="capture_entry",
            phase_elapsed_s=4.1,
            capture_entry_snapshot={"capture_entry_reached": False, "robot_on_goal_side": False},
            phase_ready_observed=False,
            phase_ready_latched=True,
            attempt_kind="initial_visit",
            latest_command_mode="capture_entry",
        )
    )

    assert decision.directive == "handoff_to_capture"
    assert decision.next_phase == "capture"


def test_manager_goal_side_loss_overrides_a_latched_handoff_window():
    decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="capture_entry",
            phase_elapsed_s=4.1,
            capture_entry_snapshot={"capture_entry_reached": False, "robot_on_goal_side": True},
            phase_ready_observed=False,
            phase_ready_latched=True,
            attempt_kind="initial_visit",
            latest_command_mode="capture_entry_ready",
        )
    )

    assert decision.directive == "recover_goal_side"
    assert decision.next_phase == "capture_entry"


def test_manager_never_skips_directly_from_pre_stage_to_capture():
    decision = gather_manager.decide_gather_manager_directive(
        gather_manager.GatherManagerState(
            phase="pre_stage",
            phase_elapsed_s=10.0,
            pre_stage_snapshot={"entered_goal_side_before_capture": False, "pre_stage_pose_reached": True},
            phase_ready_observed=True,
            attempt_kind="initial_visit",
            latest_command_mode="pre_stage_ready",
        )
    )

    assert decision.directive != "handoff_to_capture"
    assert decision.next_phase == "stage"
