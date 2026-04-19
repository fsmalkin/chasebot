#!/usr/bin/env python3
"""Deterministic phase-manager helpers for pre-capture gather orchestration."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GatherManagerState:
    phase: str
    phase_elapsed_s: float
    pre_stage_snapshot: dict[str, Any] | None = None
    approach_snapshot: dict[str, Any] | None = None
    capture_snapshot: dict[str, Any] | None = None
    capture_entry_snapshot: dict[str, Any] | None = None
    phase_ready_observed: bool = False
    phase_ready_latched: bool = False
    attempt_kind: str = ""
    latest_command_mode: str = ""


@dataclass(frozen=True)
class GatherManagerDecision:
    directive: str
    next_phase: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bool(payload: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get(key, False))


def decide_gather_manager_directive(state: GatherManagerState) -> GatherManagerDecision:
    phase = str(state.phase or "").strip().lower()

    if phase == "pre_stage":
        if _bool(state.pre_stage_snapshot, "entered_goal_side_before_capture") or _bool(
            state.approach_snapshot,
            "robot_on_goal_side",
        ):
            return GatherManagerDecision(
                directive="recover_goal_side",
                next_phase="pre_stage",
                rationale="Stay in coarse behind-ball recovery while the robot remains on the goal side.",
            )
        if bool(state.phase_ready_observed) or bool(state.phase_ready_latched):
            return GatherManagerDecision(
                directive="stabilize_stage",
                next_phase="stage",
                rationale="The coarse behind-ball arrival has been observed; prepare the fine staging handoff.",
            )
        return GatherManagerDecision(
            directive="stabilize_pre_stage",
            next_phase="pre_stage",
            rationale="Keep refining the coarse behind-ball arrival pose.",
        )

    if phase == "stage":
        if _bool(state.approach_snapshot, "robot_on_goal_side"):
            return GatherManagerDecision(
                directive="recover_goal_side",
                next_phase="stage",
                rationale="Do not advance out of staging while the robot is back on the goal side.",
            )
        if bool(state.phase_ready_observed) or bool(state.phase_ready_latched):
            return GatherManagerDecision(
                directive="close_capture_gap",
                next_phase="capture_entry",
                rationale="The fine staging pose has been observed; advance into the capture-entry corridor.",
            )
        return GatherManagerDecision(
            directive="stabilize_stage",
            next_phase="stage",
            rationale="Keep refining the fine staging pose before starting capture entry.",
        )

    if phase == "capture_entry":
        if _bool(state.capture_entry_snapshot, "robot_on_goal_side"):
            return GatherManagerDecision(
                directive="recover_goal_side",
                next_phase="capture_entry",
                rationale="Capture entry cannot advance while the robot is back on the goal side.",
            )
        if bool(state.phase_ready_observed) or bool(state.phase_ready_latched):
            return GatherManagerDecision(
                directive="handoff_to_capture",
                next_phase="capture",
                rationale="The capture-entry corridor has been observed; hand off into generic capture.",
            )
        return GatherManagerDecision(
            directive="close_capture_gap",
            next_phase="capture_entry",
            rationale="Keep closing the final gap between staging and generic capture.",
        )

    return GatherManagerDecision(
        directive="handoff_to_capture",
        next_phase="capture",
        rationale="Generic capture owns the mission once the pre-capture phases are complete.",
    )
