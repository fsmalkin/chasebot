from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import calibrated_fetch_architecture_revisit as revisit  # noqa: E402


def test_default_candidate_family_is_nav2_corridor_push():
    assert revisit.DEFAULT_CANDIDATE_FAMILY == "nav2_followpath_corridor_push_v1"
    assert revisit._comparison_scope(revisit.DEFAULT_CANDIDATE_FAMILY) == "nav2_corridor_push_contact_candidate"
    assert revisit._comparison_scope("nav2_mppi_follow_path_reacquire_v1") == "setup_prestage_candidate_with_fetch_fallback"


def test_nav2_corridor_push_decision_requests_live_gate_after_first_screen():
    decision = revisit._family_decision(
        family="nav2_followpath_corridor_push_v1",
        one_run_results=[{"layout_id": "zero", "pass": True, "metrics": {}}],
        promotion_results=[],
        baseline_by_layout={},
        delivery_radius_m=0.3,
    )

    assert decision["recommended_next_action"] == "run_live_nav2_corridor_push_gate"
    assert decision["comparison_scope"] == "nav2_corridor_push_contact_candidate"


def _args(**overrides):
    values = {
        "dashboard_url": "http://127.0.0.1:8860",
        "campaign_id": "test_arch_revisit",
        "baseline_summary": revisit.DEFAULT_BASELINE_SUMMARY,
        "screen_scope": revisit.DEFAULT_SCREEN_SCOPE,
        "candidate_family": [],
        "layout": [],
        "runs": 1,
        "promote_runs": 3,
        "promote_on_green": False,
        "short_circuit_on_failure": False,
        "provider": "local_stub",
        "world_file": revisit.fetch_gate.DEFAULT_WORLD_FILE,
        "fast_screen": False,
        "fast_world_file": revisit.FAST_SCREEN_WORLD_FILE,
        "surface_profile": revisit.fetch_gate.DEFAULT_SURFACE_PROFILE,
        "fetch_target_x": 0.95,
        "fetch_target_y": 0.0,
        "fetch_target_z": 0.001,
        "fetch_delivery_radius_m": 0.30,
        "scenario_timeout_s": 240.0,
        "timeout_s": 30.0,
        "dry_run": False,
        "reuse_existing": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_candidate_specs_uses_calibrated_layouts_and_candidate_family():
    specs = revisit.build_candidate_specs(
        _args(),
        stage="one_run",
        families=["nav2_mppi_follow_path_reacquire_v1"],
        runs=1,
    )

    assert [spec.layout_id for spec in specs] == ["zero", "left05", "right05"]
    zero_command = specs[0].command
    assert zero_command[zero_command.index("--mission-objective") + 1] == "fetch_to_pose"
    assert zero_command[zero_command.index("--gather-control-family") + 1] == "nav2_mppi_follow_path_reacquire_v1"
    assert zero_command[zero_command.index("--max-retries-per-target") + 1] == "0"
    assert zero_command[zero_command.index("--fetch-delivery-radius-m") + 1] == "0.300000"
    assert zero_command[zero_command.index("--target-layout-json") + 1] == revisit.LAYOUTS["zero"]


def test_fast_screen_default_world_can_select_fast_calibrated_world():
    args = _args(fast_screen=True)

    if args.fast_screen and args.world_file == revisit.fetch_gate.DEFAULT_WORLD_FILE:
        args.world_file = args.fast_world_file
    specs = revisit.build_candidate_specs(
        args,
        stage="one_run",
        families=["region_funnel_v1"],
        runs=1,
    )

    zero_command = specs[0].command
    assert zero_command[zero_command.index("--world-file") + 1] == revisit.FAST_SCREEN_WORLD_FILE


def test_layout_filter_limits_candidate_specs():
    specs = revisit.build_candidate_specs(
        _args(layout=["zero"]),
        stage="one_run",
        families=["region_funnel_v1", "nav2_reacquire_v1"],
        runs=1,
    )

    assert [spec.layout_id for spec in specs] == ["zero", "zero"]


def test_summarize_repeatability_extracts_fetch_metrics():
    summary = {
        "promotion_gate_pass": True,
        "required_green_runs": 1,
        "runs": [
            {
                "mission_completed_pass": True,
                "fetch_to_pose_pass": True,
                "pre_stage_handoff_pass": True,
                "shot_outcome": {"closest_approach_distance_m": 0.27},
            }
        ],
    }

    metrics = revisit._summarize_repeatability(summary)

    assert metrics["pass"] is True
    assert metrics["mission_completed_pass_count"] == 1
    assert metrics["fetch_to_pose_pass_count"] == 1
    assert metrics["pre_stage_handoff_pass_count"] == 1
    assert metrics["worst_closest_approach_distance_m"] == 0.27


def test_family_decision_does_not_promote_setup_only_candidate():
    result = {
        "family": "nav2_mppi_follow_path_reacquire_v1",
        "layout_id": "zero",
        "return_code": 0,
        "pass": True,
        "metrics": {
            "required_green_runs": 1,
            "pre_stage_handoff_pass_count": 1,
            "worst_closest_approach_distance_m": 0.2,
        },
    }

    decision = revisit._family_decision(
        family="nav2_mppi_follow_path_reacquire_v1",
        one_run_results=[{**result, "layout_id": "zero"}, {**result, "layout_id": "left05"}, {**result, "layout_id": "right05"}],
        promotion_results=[],
        baseline_by_layout={},
        delivery_radius_m=0.3,
    )

    assert decision["one_run_green"] is True
    assert decision["comparison_scope"] == "setup_prestage_candidate_with_fetch_fallback"
    assert decision["recommended_next_action"] == "preserve_as_setup_baseline_evidence"


def test_classify_failed_candidate_uses_artifact_failure_reason_not_runner_code():
    result = {
        "return_code": 2,
        "pass": False,
        "metrics": {
            "required_green_runs": 1,
            "pre_stage_handoff_pass_count": 0,
            "fetch_to_pose_failure_reasons": ["nav2_follow_path_path_clearance_guard"],
            "approach_failure_reasons": ["pre_stage_pose_not_reached"],
        },
    }

    assert revisit._classify_layout_result(result, delivery_radius_m=0.3) == "pre_stage_path_clearance_guard"
