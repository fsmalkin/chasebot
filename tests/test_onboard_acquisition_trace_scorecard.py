from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import onboard_acquisition_trace_scorecard as scorecard  # noqa: E402


def _row(
    step: int,
    error: float,
    z_m: float,
    *,
    regime: str = "forward",
    angular_z: float = 0.0,
    reason: str = "arc_approach",
    source: str = "onboard_trt",
) -> dict:
    action = "stop" if reason != "arc_approach" else "forward"
    decision = {
        "action": action,
        "reason": reason,
        "z_m": z_m,
    }
    if action == "forward":
        decision.update(
            {
                "linear_x": 0.0 if regime == "turn" else 0.55,
                "angular_z": angular_z,
                "arc_regime": regime,
                "center_error": error,
            }
        )
    return {
        "t": float(step) * 0.12,
        "obs": {
            "detected": True,
            "center_error": error,
            "confidence": 0.9,
            "source": source,
        },
        "policy_obs": {
            "detected": True,
            "center_error": error,
            "confidence": 0.9,
            "source": source,
            "coasting": False,
        },
        "decision": decision,
        "state": {"step": step, "forward_steps": step, "lost_count": 0},
    }


def _entry(case: str, *, phase: str = "diagnostic") -> dict:
    return {
        "run_id": "%s-%s" % (phase, case),
        "expected_case": case,
        "phase": phase,
        "surface": "hard_floor",
        "operator_started": True,
        "preflight_safe": True,
    }


def test_analyze_run_accepts_smooth_far_offset_turn_transition():
    rows = [
        _row(1, 0.82, 0.92, regime="turn", angular_z=-2.3),
        _row(2, 0.63, 0.91, regime="turn", angular_z=-2.3),
        _row(3, 0.44, 0.88, regime="forward", angular_z=-0.3),
        _row(4, 0.18, 0.70, regime="forward", angular_z=-0.1),
        _row(5, 0.06, 0.48, regime="forward", angular_z=0.0),
        _row(6, 0.03, 0.34, reason="standoff_reached"),
    ]
    summary = {"final_safe": True, "stop_reason": "standoff_then_pushed"}

    result = scorecard.analyze_run(_entry("far-right"), rows, summary)

    assert result["observed_case"] == "far-right"
    assert result["turn_to_forward_transition"] is True
    assert result["range_progress_m"] > 0.5
    assert result["direction_reversal_count"] == 0
    assert result["diagnosis"] == "smooth_acquisition_pass"
    assert result["qualifying_pass"] is True


def test_analyze_run_classifies_turn_response_stall():
    rows = [
        _row(i, 0.82 - (0.001 * i), 0.90, regime="turn", angular_z=-2.3)
        for i in range(1, 21)
    ]
    rows.append(_row(21, 0.80, 0.90, reason="max_steps_reached"))

    result = scorecard.analyze_run(
        _entry("far-right"), rows, {"final_safe": True, "stop_reason": "max_steps_reached"}
    )

    assert result["turn_regime_rows"] == 20
    assert result["center_error_progress"] < 0.1
    assert result["diagnosis"] == "turn_response_stalled"
    assert result["qualifying_pass"] is False


def test_analyze_run_classifies_forward_response_stall():
    rows = [
        _row(i, -0.90, 0.70 - (0.0005 * i), regime="forward", angular_z=1.0)
        for i in range(1, 21)
    ]
    rows.append(_row(21, -0.90, 0.69, reason="forward_budget_exhausted"))

    result = scorecard.analyze_run(
        _entry("far-left"),
        rows,
        {"final_safe": True, "stop_reason": "forward_budget_exhausted"},
    )

    assert result["forward_regime_rows"] == 20
    assert result["range_progress_m"] < 0.05
    assert result["diagnosis"] == "forward_response_stalled"
    assert result["qualifying_pass"] is False


def test_analyze_run_rejects_post_deadband_limit_cycle_even_if_standoff_reached():
    errors = [0.35, 0.08, -0.16, 0.07, -0.18, 0.06, -0.14, 0.04]
    angular = [-0.5, -0.3, 0.5, -0.5, 0.5, -0.5, 0.5, 0.0]
    rows = [
        _row(i + 1, error, 0.90 - (0.07 * i), angular_z=angular[i])
        for i, error in enumerate(errors)
    ]
    rows.append(_row(9, 0.03, 0.34, reason="standoff_reached"))

    result = scorecard.analyze_run(
        _entry("mid-right"), rows, {"final_safe": True, "stop_reason": "standoff_then_pushed"}
    )

    assert result["direction_reversal_count"] >= 4
    assert result["deadband_entry_count"] >= 2
    assert result["limit_cycle_detected"] is True
    assert result["diagnosis"] == "center_limit_cycle"
    assert result["qualifying_pass"] is False


def test_analyze_run_requires_onboard_perception_and_safety_evidence():
    rows = [
        _row(1, 0.05, 0.80, source="remote_yolo"),
        _row(2, 0.02, 0.34, reason="standoff_reached", source="remote_yolo"),
    ]
    entry = _entry("center")
    entry["preflight_safe"] = False

    result = scorecard.analyze_run(entry, rows, {"final_safe": None})

    assert result["onboard_perception_pass"] is False
    assert result["preflight_safe"] is False
    assert result["final_safe"] is None
    assert result["qualifying_pass"] is False


def test_campaign_requires_diagnostic_coverage_then_five_mixed_passes():
    cases = list(scorecard.REQUIRED_CASES)
    diagnostic = [
        {"run_id": "diagnostic-%s" % case, "phase": "diagnostic", "observed_case": case,
         "qualifying_pass": True}
        for case in cases
    ]
    mixed = [
        {"run_id": "mixed-%d" % i, "phase": "mixed", "observed_case": cases[i % len(cases)],
         "qualifying_pass": True}
        for i in range(5)
    ]

    result = scorecard.summarize_campaign(diagnostic + mixed)

    assert result["diagnostic_case_coverage_pass"] is True
    assert result["mixed_consecutive_passes"] == 5
    assert result["goal_ready"] is True


def test_campaign_fail_closes_when_one_diagnostic_case_is_missing():
    cases = list(scorecard.REQUIRED_CASES[:-1])
    runs = [
        {"run_id": "diagnostic-%s" % case, "phase": "diagnostic", "observed_case": case,
         "qualifying_pass": True}
        for case in cases
    ]
    runs.extend(
        {"run_id": "mixed-%d" % i, "phase": "mixed", "observed_case": "center",
         "qualifying_pass": True}
        for i in range(5)
    )

    result = scorecard.summarize_campaign(runs)

    assert result["diagnostic_case_coverage_pass"] is False
    assert result["missing_diagnostic_cases"] == [scorecard.REQUIRED_CASES[-1]]
    assert result["goal_ready"] is False
