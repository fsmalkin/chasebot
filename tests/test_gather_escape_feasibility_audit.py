from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_escape_feasibility_audit as audit  # noqa: E402
import gather_escape_sandbox as sandbox  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}

CONTROLLER_SHAPE_LOCAL = {"x": 0.31361758022929265, "y": 0.25607254243872984, "yaw": -2.3296093313272754}
TURN_RADIUS_LIMITED_LOCAL = {"x": 0.14523364170764383, "y": 0.3385909832920025, "yaw": -1.2033441888605616}
FOOTPRINT_MARGIN_LIMITED_LOCAL = {"x": 0.3223909812516138, "y": 0.3171626973771378, "yaw": -2.1716046501660506}
CORRIDOR_MARGIN_LIMITED_LOCAL = {"x": 0.07248942563841407, "y": 0.9408443089846991, "yaw": -2.9813658571690147}
GOAL_SIDE_ONLY_LOCAL = {"x": 0.023141687334822705, "y": 1.3629109105513886, "yaw": -0.8439014238462192}

LIVE_POST_YAW_GATE_POSE = {"x": -0.097434, "y": 0.157671, "yaw": -2.01106}
LIVE_MID_STALLED_POSE = {"x": 0.308136, "y": 0.436242, "yaw": -2.688203}

AUDIT_CONTRACT = audit.load_audit_repo_contract()
FIXTURE_LABELS = {
    "first_post_yaw_gate",
    "early_stall",
    "mid_stall",
    "late_stall",
    "terminal_stall",
}


def _mirror_macro_name(name: str) -> str:
    if "_left" in name:
        return name.replace("_left", "_right")
    if "_right" in name:
        return name.replace("_right", "_left")
    return name


def _mirror_local_pose(local_pose: dict[str, float]) -> dict[str, float]:
    return {"x": local_pose["x"], "y": -local_pose["y"], "yaw": -local_pose["yaw"]}


def _best_results_for_local_fixture(local_pose: dict[str, float]) -> dict[str, audit.AuditSequenceResult]:
    results: dict[str, audit.AuditSequenceResult] = {}
    for profile_name in audit.DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER:
        top = audit.search_audit_maneuvers_local(
            local_pose,
            BALL_POSE,
            zone=ZONE,
            audit_contract=AUDIT_CONTRACT,
            profile_name=profile_name,
            top_k=1,
        )
        assert top
        results[profile_name] = top[0]
    return results


def _profile_result_map(results: dict[str, audit.AuditSequenceResult]) -> dict[str, dict[str, object]]:
    return {
        profile_name: {
            "corridor_clear_available": bool(item.corridor_clearable),
            "goal_side_clear_available": bool(item.goal_side_clearable or item.corridor_clearable),
            "feasibility_class": item.feasibility_class,
        }
        for profile_name, item in results.items()
    }


def _write_state_history_for_world_pose(tmp_path: Path, robot_pose: dict[str, float], *, stem: str) -> Path:
    state_history_path = tmp_path / f"{stem}_state_history.jsonl"
    rows = []
    for index in range(5):
        rows.append(
            {
                "generated_utc": f"2026-04-19T23:00:{index:02d}Z",
                "phase": "pre_stage",
                "attempt": 0,
                "robot_pose": dict(robot_pose),
                "ball_pose": dict(BALL_POSE),
                "pre_stage": {"yaw_error_deg": 30.0},
            }
        )
    state_history_path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
    return state_history_path


def _write_state_history_for_local_pose(tmp_path: Path, local_pose: dict[str, float], *, stem: str) -> Path:
    world_pose = sandbox.local_pose_to_world(local_pose, BALL_POSE, zone=ZONE)
    assert world_pose is not None
    return _write_state_history_for_world_pose(tmp_path, world_pose, stem=stem)


def test_audit_is_symmetric_for_mirrored_corridor_fixture():
    mirrored = _mirror_local_pose(CONTROLLER_SHAPE_LOCAL)

    for profile_name in audit.DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER:
        plus = audit.search_audit_maneuvers_local(
            CONTROLLER_SHAPE_LOCAL,
            BALL_POSE,
            zone=ZONE,
            audit_contract=AUDIT_CONTRACT,
            profile_name=profile_name,
            top_k=1,
        )
        minus = audit.search_audit_maneuvers_local(
            mirrored,
            BALL_POSE,
            zone=ZONE,
            audit_contract=AUDIT_CONTRACT,
            profile_name=profile_name,
            top_k=1,
        )

        assert plus
        assert minus
        assert plus[0].family_name == minus[0].family_name
        assert plus[0].feasibility_class == minus[0].feasibility_class
        assert tuple(_mirror_macro_name(name) for name in plus[0].macro_sequence) == minus[0].macro_sequence
        assert abs(float(plus[0].projection_gain) - float(minus[0].projection_gain)) < 1.0e-6
        assert abs(float(plus[0].lateral_gain) - float(minus[0].lateral_gain)) < 1.0e-6
        assert abs(float(plus[0].min_ball_clearance_margin_m) - float(minus[0].min_ball_clearance_margin_m)) < 1.0e-6


def test_turn_radius_limited_fixture_only_unlocks_corridor_with_tighter_turn_profile():
    results = _best_results_for_local_fixture(TURN_RADIUS_LIMITED_LOCAL)
    profile_map = _profile_result_map(results)

    assert results["nominal_current"].goal_side_clearable is True
    assert results["nominal_current"].corridor_clearable is False
    assert results["tight_turn_relaxed"].corridor_clearable is True
    assert results["footprint_relaxed"].corridor_clearable is False
    assert results["corridor_relaxed"].corridor_clearable is False
    assert audit.classify_fixture_limiter(profile_map) == "turn_radius_limited"


def test_footprint_margin_limited_fixture_only_unlocks_corridor_with_relaxed_clearance():
    results = _best_results_for_local_fixture(FOOTPRINT_MARGIN_LIMITED_LOCAL)
    profile_map = _profile_result_map(results)
    nominal_wide = audit.search_audit_maneuvers_local(
        FOOTPRINT_MARGIN_LIMITED_LOCAL,
        BALL_POSE,
        zone=ZONE,
        audit_contract=AUDIT_CONTRACT,
        profile_name="nominal_current",
        top_k=1,
        allowed_maneuver_names=("wide_loop_left", "wide_loop_right"),
    )[0]
    relaxed_wide = audit.search_audit_maneuvers_local(
        FOOTPRINT_MARGIN_LIMITED_LOCAL,
        BALL_POSE,
        zone=ZONE,
        audit_contract=AUDIT_CONTRACT,
        profile_name="footprint_relaxed",
        top_k=1,
        allowed_maneuver_names=("wide_loop_left", "wide_loop_right"),
    )[0]

    assert results["nominal_current"].corridor_clearable is False
    assert results["footprint_relaxed"].corridor_clearable is True
    assert results["tight_turn_relaxed"].corridor_clearable is False
    assert results["corridor_relaxed"].corridor_clearable is False
    assert nominal_wide.corridor_clearable is False
    assert nominal_wide.ball_clearance_ok is False
    assert float(nominal_wide.min_ball_clearance_margin_m) < 0.0
    assert relaxed_wide.corridor_clearable is True
    assert relaxed_wide.ball_clearance_ok is True
    assert float(relaxed_wide.min_ball_clearance_margin_m) > 0.0
    assert audit.classify_fixture_limiter(profile_map) == "footprint_margin_limited"


def test_goal_side_only_fixture_stays_outside_corridor():
    results = _best_results_for_local_fixture(GOAL_SIDE_ONLY_LOCAL)
    profile_map = _profile_result_map(results)

    assert results["nominal_current"].goal_side_clearable is True
    assert results["nominal_current"].corridor_clearable is False
    assert results["nominal_current"].feasibility_class == "goal_side_clearable"
    assert float(results["nominal_current"].projected_snapshot["robot_lateral_error_m"]) > (
        audit._profile("nominal_current", AUDIT_CONTRACT).corridor_max_lateral_m
    )
    assert audit.classify_fixture_limiter(profile_map) == "corridor_completion_limited"


def test_live_plus45_stall_rows_remain_non_promoting_when_safe_side_is_not_reached():
    for robot_pose in [LIVE_POST_YAW_GATE_POSE, LIVE_MID_STALLED_POSE]:
        for profile_name in audit.DEFAULT_ESCAPE_FEASIBILITY_AUDIT_PROFILE_ORDER:
            results = audit.search_audit_maneuvers(
                robot_pose,
                BALL_POSE,
                zone=ZONE,
                audit_contract=AUDIT_CONTRACT,
                profile_name=profile_name,
                top_k=3,
            )

            assert results
            assert all(item.corridor_clearable is False for item in results)
            assert all(item.goal_side_clearable is False for item in results)
            assert all(item.feasibility_class in {"near_clear", "not_clearable"} for item in results)


@pytest.mark.parametrize(
    ("label", "local_pose", "expected_decision", "expected_profile", "expected_family", "expected_limiter"),
    [
        (
            "controller_shape",
            CONTROLLER_SHAPE_LOCAL,
            "offline_distillation_from_winning_family",
            "nominal_current",
            "wide_loop",
            "controller_shape_limited",
        ),
        (
            "turn_radius",
            TURN_RADIUS_LIMITED_LOCAL,
            "geometry_footprint_turn_radius_contract_audit",
            "tight_turn_relaxed",
            "retreat_loop",
            "turn_radius_limited",
        ),
        (
            "footprint",
            FOOTPRINT_MARGIN_LIMITED_LOCAL,
            "geometry_footprint_turn_radius_contract_audit",
            "footprint_relaxed",
            "wide_loop",
            "footprint_margin_limited",
        ),
        (
            "corridor_margin",
            CORRIDOR_MARGIN_LIMITED_LOCAL,
            "geometry_footprint_turn_radius_contract_audit",
            "corridor_relaxed",
            "wide_loop",
            "corridor_margin_limited",
        ),
        (
            "corridor_completion",
            GOAL_SIDE_ONLY_LOCAL,
            "corridor_completion_sandbox",
            "nominal_current",
            "three_point_commit",
            "corridor_completion_limited",
        ),
    ],
)
def test_build_feasibility_bundle_rolls_up_profiles_and_decision_gate(
    tmp_path: Path,
    label: str,
    local_pose: dict[str, float],
    expected_decision: str,
    expected_profile: str,
    expected_family: str,
    expected_limiter: str,
):
    state_history_path = _write_state_history_for_local_pose(tmp_path, local_pose, stem=label)

    summary, primary_profiles = audit.build_feasibility_audit_bundle(
        [("short_horizon_v2", state_history_path)],
        campaign_id=f"audit-{label}",
    )

    assert summary["decision_outcome"] == expected_decision
    assert summary["selected_primary_profile"] == expected_profile
    assert summary["selected_primary_family"] == expected_family
    assert summary["primary_trace_limiter_class_counts"] == {expected_limiter: 5}
    assert set(primary_profiles.keys()) == FIXTURE_LABELS

    trace_summary = summary["trace_summaries"][0]
    assert trace_summary["trace_family"] == "short_horizon_v2"
    assert trace_summary["limiter_class_counts"] == {expected_limiter: 5}
    assert {item["limiter_class"] for item in trace_summary["fixture_results"]} == {expected_limiter}

    profile_summaries = {item["profile_name"]: item for item in trace_summary["profile_summaries"]}
    assert expected_profile in profile_summaries
    assert profile_summaries[expected_profile]["selected_primary_family"] == expected_family
    if expected_decision == "corridor_completion_sandbox":
        assert summary["primary_corridor_clear_count"] == 0
        assert summary["stable_goal_side_clear_count"] == 5
    else:
        assert summary["primary_corridor_clear_count"] == 5
        assert summary["stable_goal_side_clear_count"] == 5


def test_build_feasibility_bundle_stops_controller_family_work_when_no_profile_unlocks_progress(tmp_path: Path):
    state_history_path = _write_state_history_for_world_pose(tmp_path, LIVE_POST_YAW_GATE_POSE, stem="live_stop")

    summary, primary_profiles = audit.build_feasibility_audit_bundle(
        [("short_horizon_v2", state_history_path)],
        campaign_id="audit-live-stop",
    )

    assert summary["decision_outcome"] == "richer_world_dynamics_validation"
    assert summary["selected_primary_profile"] == "nominal_current"
    assert summary["primary_corridor_clear_count"] == 0
    assert summary["stable_goal_side_clear_count"] == 0
    assert summary["near_clear_count"] == 0
    assert summary["primary_trace_limiter_class_counts"] == {"modeling_or_world_limited": 5}
    assert set(primary_profiles.keys()) == FIXTURE_LABELS
    assert {item["limiter_class"] for item in summary["trace_summaries"][0]["fixture_results"]} == {
        "modeling_or_world_limited"
    }
