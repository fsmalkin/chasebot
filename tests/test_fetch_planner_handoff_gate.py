from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_handoff_gate as gate  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402


def test_planner_gate_dry_run_scores_all_route_classes(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    args = SimpleNamespace(
        campaign_id="planner_gate_dry",
        scene_set=gate.DEFAULT_SCENE_SET,
        scene_descriptor_json=[],
        scene_dir="",
        random_cases=10,
        seed=123,
        planner_mode=gate.PLANNER_MODE_DETERMINISTIC,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["random_cases"] == 10
    assert summary["wrong_fetch_dispatch_count"] == 0
    for route in gate.ROUTE_LABELS:
        assert summary["expected_route_counts"][route] >= 1
    summary_path = tmp_path / "artifacts" / "session" / "planner_gate_dry" / gate.PLANNER_GATE_KIND / "gate_summary.json"
    assert summary_path.exists()
    scorecard_path = summary_path.with_name("scorecard.md")
    assert scorecard_path.exists()


def test_planner_gate_replays_frozen_scene_set(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    frozen_path = tmp_path / "scene_set.json"
    scenes = gate.generate_random_scenes(seed=321, random_cases=5)
    gate.write_json(frozen_path, {"scenes": scenes})
    args = SimpleNamespace(
        campaign_id="planner_gate_frozen",
        scene_set=gate.DEFAULT_SCENE_SET,
        scene_descriptor_json=[str(frozen_path)],
        scene_dir="",
        random_cases=99,
        seed=123,
        planner_mode=gate.PLANNER_MODE_DETERMINISTIC,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["scene_source"] == "frozen"
    assert summary["random_cases"] == 5
    assert summary["wrong_fetch_dispatch_count"] == 0
    assert {result["scene_id"] for result in summary["results"]} == {scene["scene_id"] for scene in scenes}


def test_deterministic_classifier_separates_reposition_recovery_and_fetch_ready():
    scenes = gate.generate_random_scenes(seed=321, random_cases=20)

    by_expected = {scene["expected_route_label"]: scene for scene in scenes}

    assert gate.deterministic_route_label(by_expected[gate.ROUTE_FETCH_READY]) == gate.ROUTE_FETCH_READY
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_NAV2_REPOSITION]) == gate.ROUTE_NAV2_REPOSITION
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_RECOVERY_OR_REAIM]) == gate.ROUTE_RECOVERY_OR_REAIM
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_LOCAL_SETUP_CAPTURE]) == gate.ROUTE_LOCAL_SETUP_CAPTURE
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_SCAN_OR_PERCEIVE]) == gate.ROUTE_SCAN_OR_PERCEIVE
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_NO_GO]) == gate.ROUTE_NO_GO
    assert by_expected[gate.ROUTE_FETCH_READY]["local_fetch_envelope"]["eligible"] is True
    assert by_expected[gate.ROUTE_SCAN_OR_PERCEIVE]["local_fetch_envelope"]["eligible"] is False
    assert by_expected[gate.ROUTE_RECOVERY_OR_REAIM]["local_fetch_envelope"]["eligible"] is False
    assert by_expected[gate.ROUTE_LOCAL_SETUP_CAPTURE]["local_fetch_envelope"]["eligible"] is False


def test_deterministic_classifier_routes_moderate_setup_debt_to_recovery():
    scene = {
        "perception": {"ball_confidence": 0.98, "target_confidence": 0.99, "state_age_s": 0.15},
        "corridor": {"blocked": False, "clearance_m": 0.35, "unsafe_drift_m": 0.0},
        "geometry": {
            "ball_target_distance_m": 0.612365,
            "ball_target_angle_deg": -13.762086,
            "robot_ball_distance_m": 0.372459,
            "robot_lateral_error_m": 0.071829,
            "robot_yaw_error_deg": -11.385805,
        },
    }

    gate._refresh_local_fetch_envelope(scene)

    assert gate.deterministic_route_label(scene) == gate.ROUTE_RECOVERY_OR_REAIM
    assert scene["local_fetch_envelope"]["eligible"] is False


def test_deterministic_classifier_routes_near_field_long_setup_to_recovery():
    scene = {
        "expected_route_label": gate.ROUTE_NAV2_REPOSITION,
        "perception": {"ball_confidence": 0.98, "target_confidence": 0.99, "state_age_s": 0.15},
        "corridor": {"blocked": False, "clearance_m": 0.35, "unsafe_drift_m": 0.0},
        "geometry": {
            "ball_target_distance_m": 0.680424,
            "ball_target_angle_deg": 16.930711,
            "robot_ball_distance_m": 0.846004,
            "robot_lateral_error_m": 0.100922,
            "robot_yaw_error_deg": -4.807588,
        },
    }

    gate._refresh_local_fetch_envelope(scene)
    admissibility = gate.route_admissibility_for_scene(scene, gate.ROUTE_NAV2_REPOSITION)

    assert gate.deterministic_route_label(scene) == gate.ROUTE_RECOVERY_OR_REAIM
    assert admissibility["changed"] is True
    assert admissibility["route_label"] == gate.ROUTE_RECOVERY_OR_REAIM
    assert admissibility["reason"] == "near_field_setup_prefers_bounded_recovery_reaim"
    assert scene["local_fetch_envelope"]["eligible"] is False


def test_deterministic_classifier_keeps_exact_centerline_anchor_fetch_ready():
    scene = {
        "perception": {"ball_confidence": 0.98, "target_confidence": 0.99, "state_age_s": 0.15},
        "corridor": {"blocked": False, "clearance_m": 0.35, "unsafe_drift_m": 0.0},
        "geometry": {
            "ball_target_distance_m": 0.57,
            "ball_target_angle_deg": 0.0,
            "robot_ball_distance_m": 0.38,
            "robot_lateral_error_m": 0.0,
            "robot_yaw_error_deg": 0.0,
        },
    }

    gate._refresh_local_fetch_envelope(scene)

    assert gate.deterministic_route_label(scene) == gate.ROUTE_FETCH_READY
    assert scene["local_fetch_envelope"]["eligible"] is True


def test_route_quality_scores_clean_fetch_ready_and_recovery_watch():
    scenes = gate.generate_random_scenes(seed=321, random_cases=20)
    by_expected = {scene["expected_route_label"]: scene for scene in scenes}
    clean_scene = dict(by_expected[gate.ROUTE_FETCH_READY])
    clean_scene["geometry"] = {
        **clean_scene["geometry"],
        "robot_lateral_error_m": 0.010,
        "robot_yaw_error_deg": 1.2,
    }

    clean_quality = gate.score_route_quality(clean_scene, gate.ROUTE_FETCH_READY)
    recovery_quality = gate.score_route_quality(
        by_expected[gate.ROUTE_RECOVERY_OR_REAIM],
        gate.ROUTE_RECOVERY_OR_REAIM,
    )

    assert clean_quality["predicted_contact_quality"] == "clean"
    assert clean_quality["predicted_first_contact_risk"] == "low"
    assert clean_quality["quality_score"] > recovery_quality["quality_score"]
    assert recovery_quality["predicted_contact_quality"] == "watch"
    assert "bounded_recovery_required" in recovery_quality["flags"]


def test_generated_nav2_scenes_start_outside_recovery_band():
    scenes = gate.generate_random_scenes(seed=20260627, random_cases=30)
    nav2_scenes = [
        scene for scene in scenes
        if scene["expected_route_label"] == gate.ROUTE_NAV2_REPOSITION
    ]

    assert nav2_scenes
    assert all(
        scene["geometry"]["robot_ball_distance_m"] >= gate.NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M
        for scene in nav2_scenes
    )


def test_hard_scene_set_covers_deliberate_route_pressure_cases():
    scenes = gate.generate_random_scenes(
        seed=123,
        random_cases=10,
        scene_set=gate.HARD_SCENE_SET,
    )

    assert len(scenes) == 10
    assert {scene["scene_id"] for scene in scenes} >= {
        "hard_nav2_opposite_side_left_01",
        "hard_nav2_opposite_side_right_02",
        "hard_recovery_large_angle_left_01",
        "hard_scan_stale_opposite_02",
    }
    assert {
        route: sum(1 for scene in scenes if scene["expected_route_label"] == route)
        for route in gate.ROUTE_LABELS
    } == {
        gate.ROUTE_FETCH_READY: 2,
        gate.ROUTE_NAV2_REPOSITION: 0,
        gate.ROUTE_SCAN_OR_PERCEIVE: 2,
        gate.ROUTE_RECOVERY_OR_REAIM: 2,
        gate.ROUTE_LOCAL_SETUP_CAPTURE: 2,
        gate.ROUTE_NO_GO: 2,
    }
    assert all(
        gate.deterministic_route_label(scene) == scene["expected_route_label"]
        for scene in scenes
    )

    local_setup_angles = [
        abs(scene["geometry"]["ball_target_angle_deg"])
        for scene in scenes
        if scene["expected_route_label"] == gate.ROUTE_LOCAL_SETUP_CAPTURE
    ]
    assert local_setup_angles == [170.0, 170.0]
    assert all(
        scene["geometry"]["robot_ball_distance_m"] >= gate.NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M
        for scene in scenes
        if scene["expected_route_label"] == gate.ROUTE_LOCAL_SETUP_CAPTURE
    )


def test_opposite_behind_scene_set_covers_broad_spatial_cases():
    scenes = gate.generate_random_scenes(
        seed=123,
        random_cases=12,
        scene_set=gate.OPPOSITE_BEHIND_SCENE_SET,
    )

    assert len(scenes) == 12
    assert sum(
        1 for scene in scenes
        if scene["geometry"]["robot_ball_relative_bearing_abs_deg"] >= 90.0
    ) >= 6
    assert sum(
        1 for scene in scenes
        if scene["geometry"]["opposite_side_of_circle"] is True
    ) >= 3
    assert {
        route: sum(1 for scene in scenes if scene["expected_route_label"] == route)
        for route in gate.ROUTE_LABELS
    } == {
        gate.ROUTE_FETCH_READY: 1,
        gate.ROUTE_NAV2_REPOSITION: 0,
        gate.ROUTE_SCAN_OR_PERCEIVE: 1,
        gate.ROUTE_RECOVERY_OR_REAIM: 2,
        gate.ROUTE_LOCAL_SETUP_CAPTURE: 6,
        gate.ROUTE_NO_GO: 2,
    }
    assert all(
        gate.deterministic_route_label(scene) == scene["expected_route_label"]
        for scene in scenes
    )

    nav2_wraparound = next(scene for scene in scenes if scene["scene_id"] == "opbehind_nav2_wraparound_left_03")
    quality = gate.score_route_quality(nav2_wraparound, gate.ROUTE_LOCAL_SETUP_CAPTURE)

    assert "ball_behind_robot_heading" in quality["flags"]
    assert "local_setup_capture_required" in quality["flags"]
    assert "measured_local_setup_capture" in quality["recommendations"]


def test_opposite_behind_layout_preserves_profile_and_geometry(tmp_path):
    scene = next(
        item for item in gate.generate_random_scenes(
            seed=123,
            random_cases=12,
            scene_set=gate.OPPOSITE_BEHIND_SCENE_SET,
        )
        if item["expected_route_label"] == gate.ROUTE_LOCAL_SETUP_CAPTURE
    )
    layout_path = tmp_path / "layout.json"

    gate.write_fetch_ready_layout_from_scene(
        layout_path,
        scene,
        route_label=gate.ROUTE_LOCAL_SETUP_CAPTURE,
        route_executor=gate.ROUTE_EXECUTOR_LOCAL_SETUP_CAPTURE,
    )

    layout = read_json(layout_path)
    assert layout["random_profile"] == gate.OPPOSITE_BEHIND_PROFILE
    assert layout["random_draw"]["random_profile"] == gate.OPPOSITE_BEHIND_PROFILE
    assert layout["random_draw"]["scene_set"] == gate.OPPOSITE_BEHIND_SCENE_SET
    assert layout["random_draw"]["robot_ball_relative_bearing_abs_deg"] >= 90.0


def test_broad_spatial_scene_set_covers_open_field_geometry_classes():
    scenes = gate.generate_random_scenes(
        seed=123,
        random_cases=18,
        scene_set=gate.BROAD_SPATIAL_SCENE_SET,
    )
    coverage = gate.summarize_scene_geometry_coverage(scenes)
    route_counts = {
        route: sum(1 for scene in scenes if scene["expected_route_label"] == route)
        for route in gate.ROUTE_LABELS
    }

    assert len(scenes) == 18
    assert coverage["behind_robot_heading_count"] >= 6
    assert coverage["opposite_side_of_circle_count"] >= 6
    assert route_counts[gate.ROUTE_FETCH_READY] >= 1
    assert route_counts[gate.ROUTE_NAV2_REPOSITION] == 0
    assert route_counts[gate.ROUTE_RECOVERY_OR_REAIM] >= 2
    assert route_counts[gate.ROUTE_LOCAL_SETUP_CAPTURE] >= 10
    assert route_counts[gate.ROUTE_SCAN_OR_PERCEIVE] >= 2
    assert route_counts[gate.ROUTE_NO_GO] >= 2
    assert all(
        gate.deterministic_route_label(scene) == scene["expected_route_label"]
        for scene in scenes
    )


def test_broad_spatial_layout_preserves_profile(tmp_path):
    scene = next(
        item for item in gate.generate_random_scenes(
            seed=123,
            random_cases=18,
            scene_set=gate.BROAD_SPATIAL_SCENE_SET,
        )
        if item["geometry"]["opposite_side_of_circle"] is True
    )
    layout_path = tmp_path / "layout.json"

    gate.write_fetch_ready_layout_from_scene(
        layout_path,
        scene,
        route_label=scene["expected_route_label"],
        route_executor=gate.executor_for_route(scene["expected_route_label"]),
    )

    layout = read_json(layout_path)
    assert layout["random_profile"] == gate.BROAD_SPATIAL_PROFILE
    assert layout["random_draw"]["random_profile"] == gate.BROAD_SPATIAL_PROFILE
    assert layout["random_draw"]["scene_set"] == gate.BROAD_SPATIAL_SCENE_SET
    assert layout["random_draw"]["opposite_side_of_circle"] is True


def test_planner_gate_scores_hard_scene_set(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    args = SimpleNamespace(
        campaign_id="planner_gate_hard_matrix",
        scene_set=gate.HARD_SCENE_SET,
        scene_descriptor_json=[],
        scene_dir="",
        random_cases=10,
        seed=123,
        planner_mode=gate.PLANNER_MODE_DETERMINISTIC,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["scene_set"] == gate.HARD_SCENE_SET
    assert summary["random_cases"] == 10
    assert summary["wrong_fetch_dispatch_count"] == 0
    expected_counts = {
        gate.ROUTE_FETCH_READY: 2,
        gate.ROUTE_NAV2_REPOSITION: 0,
        gate.ROUTE_SCAN_OR_PERCEIVE: 2,
        gate.ROUTE_RECOVERY_OR_REAIM: 2,
        gate.ROUTE_LOCAL_SETUP_CAPTURE: 2,
        gate.ROUTE_NO_GO: 2,
    }
    assert summary["expected_route_counts"] == expected_counts
    assert summary["route_counts"] == expected_counts


def test_planner_gate_scores_opposite_behind_scene_set(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    args = SimpleNamespace(
        campaign_id="planner_gate_opposite_behind_matrix",
        scene_set=gate.OPPOSITE_BEHIND_SCENE_SET,
        scene_descriptor_json=[],
        scene_dir="",
        random_cases=12,
        seed=123,
        planner_mode=gate.PLANNER_MODE_DETERMINISTIC,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)
    coverage = summary["geometry_coverage"]

    assert summary["pass"] is True
    assert summary["scene_set"] == gate.OPPOSITE_BEHIND_SCENE_SET
    assert coverage["scene_count"] == 12
    assert coverage["behind_robot_heading_count"] >= 6
    assert coverage["opposite_side_of_circle_count"] >= 3
    assert all(coverage["success_bar"].values())
    assert (tmp_path / "artifacts" / "session" / "planner_gate_opposite_behind_matrix" / gate.PLANNER_GATE_KIND / "scorecard.md").exists()


def test_decision_records_route_quality_for_planner_artifacts():
    scene = next(
        item for item in gate.generate_random_scenes(seed=20260612, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_FETCH_READY
    )

    decision = gate.decide_scene(scene)

    assert decision["route_quality"]["route_label"] == gate.ROUTE_FETCH_READY
    assert decision["route_quality"]["predicted_contact_quality"] in {"clean", "watch"}
    assert decision["route_quality"]["quality_score"] > 0.0
    assert decision["maneuver_plan"]["maneuver_sequence"] == [
        gate.MANEUVER_VALIDATE_PUSH_READY,
        gate.MANEUVER_LOCAL_FETCH,
        gate.MANEUVER_MONITOR_DELIVERY,
    ]
    assert decision["maneuver_plan"]["requires_measured_push_ready_before_fetch"] is True


def test_local_setup_capture_opposite_side_plan_includes_wraparound_and_push_ready_gate():
    scene = next(
        item for item in gate.generate_random_scenes(
            seed=123,
            random_cases=18,
            scene_set=gate.BROAD_SPATIAL_SCENE_SET,
        )
        if item["geometry"]["opposite_side_of_circle"] is True
        and item["expected_route_label"] == gate.ROUTE_LOCAL_SETUP_CAPTURE
    )

    plan = gate.compile_maneuver_plan(scene, gate.ROUTE_LOCAL_SETUP_CAPTURE)

    assert gate.MANEUVER_LOCAL_SETUP_CAPTURE in plan["maneuver_sequence"]
    assert gate.MANEUVER_WRAPAROUND_SETUP in plan["maneuver_sequence"]
    assert gate.MANEUVER_VALIDATE_PUSH_READY in plan["maneuver_sequence"]
    assert gate.MANEUVER_LOCAL_FETCH in plan["maneuver_sequence"]
    assert plan["push_ready_index"] < plan["local_fetch_index"]
    assert plan["requires_measured_push_ready_before_fetch"] is True


def test_local_setup_capture_plan_requires_setup_capture_before_push_ready():
    scene = next(
        item for item in gate.generate_random_scenes(seed=123, random_cases=12)
        if item["expected_route_label"] == gate.ROUTE_LOCAL_SETUP_CAPTURE
    )

    plan = gate.compile_maneuver_plan(scene, gate.ROUTE_LOCAL_SETUP_CAPTURE)

    assert gate.MANEUVER_LOCAL_SETUP_CAPTURE in plan["maneuver_sequence"]
    assert gate.MANEUVER_VALIDATE_PUSH_READY in plan["maneuver_sequence"]
    assert gate.MANEUVER_LOCAL_FETCH in plan["maneuver_sequence"]
    assert plan["maneuver_sequence"].index(gate.MANEUVER_LOCAL_SETUP_CAPTURE) < plan["push_ready_index"]
    assert plan["push_ready_index"] < plan["local_fetch_index"]
    assert plan["requires_measured_push_ready_before_fetch"] is True


def test_plan_compiler_vetoes_fetch_before_push_ready_for_executable_route():
    scene = next(
        item for item in gate.generate_random_scenes(seed=123, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_NAV2_REPOSITION
    )

    plan = gate.compile_maneuver_plan(
        scene,
        gate.ROUTE_NAV2_REPOSITION,
        proposed={"maneuver_sequence": [gate.MANEUVER_LOCAL_FETCH, gate.MANEUVER_VALIDATE_PUSH_READY]},
    )

    assert plan["source"] == "deterministic_compiled_after_veto"
    assert "validate_push_ready_after_fetch" in plan["veto_reasons"]
    assert plan["push_ready_index"] < plan["local_fetch_index"]


def test_plan_compiler_vetoes_planner_only_local_fetch():
    scene = next(
        item for item in gate.generate_random_scenes(seed=123, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_NO_GO
    )

    plan = gate.compile_maneuver_plan(
        scene,
        gate.ROUTE_NO_GO,
        proposed={"maneuver_sequence": [gate.MANEUVER_LOCAL_FETCH]},
    )

    assert plan["source"] == "deterministic_compiled_after_veto"
    assert "planner_only_route_attempted_local_fetch" in plan["veto_reasons"]
    assert plan["maneuver_sequence"] == [gate.MANEUVER_NO_GO]
    assert plan["requires_measured_push_ready_before_fetch"] is False


def test_route_executor_mapping_covers_all_route_labels():
    assert gate.executor_for_route(gate.ROUTE_FETCH_READY) == gate.ROUTE_EXECUTOR_LOCAL_FETCH
    assert gate.executor_for_route(gate.ROUTE_NAV2_REPOSITION) == gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert gate.executor_for_route(gate.ROUTE_SCAN_OR_PERCEIVE) == gate.ROUTE_EXECUTOR_SCAN
    assert gate.executor_for_route(gate.ROUTE_RECOVERY_OR_REAIM) == gate.ROUTE_EXECUTOR_RECOVERY
    assert gate.executor_for_route(gate.ROUTE_LOCAL_SETUP_CAPTURE) == gate.ROUTE_EXECUTOR_LOCAL_SETUP_CAPTURE
    assert gate.executor_for_route(gate.ROUTE_NO_GO) == gate.ROUTE_EXECUTOR_NO_GO
    assert gate.executor_for_route("unknown") == "unsupported_route"


def test_llm_shadow_without_api_key_records_request_and_uses_guard_fallback():
    scene = next(
        item for item in gate.generate_random_scenes(seed=456, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_NAV2_REPOSITION
    )

    decision = gate.decide_scene(scene, planner_mode=gate.PLANNER_MODE_LLM_SHADOW, openai_api_key="")

    assert decision["route_label"] == gate.ROUTE_NAV2_REPOSITION
    assert decision["route_executor"] == gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert decision["route_executable"] is True
    assert decision["planner_mode_effective"] == "deterministic_fallback"
    assert decision["provider_status"] == "skipped_missing_openai_api_key"
    assert decision["provider_request"]["tools"][0]["name"] == gate.OPENAI_TOOL_NAME
    assert decision["should_dispatch_fetch_to_pose"] is False


def test_llm_shadow_gate_without_api_key_reports_fallback_not_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    args = SimpleNamespace(
        campaign_id="planner_gate_llm_shadow_missing_key",
        scene_set=gate.HARD_SCENE_SET,
        scene_descriptor_json=[],
        scene_dir="",
        random_cases=10,
        seed=123,
        planner_mode=gate.PLANNER_MODE_LLM_SHADOW,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["llm_shadow_ready"] is False
    assert summary["llm_shadow_provider_ok_count"] == 0
    assert summary["provider_status_counts"] == {"skipped_missing_openai_api_key": 10}
    assert summary["planner_mode_effective_counts"] == {"deterministic_fallback": 10}
    assert summary["guard_agreement_count"] == 10
    assert summary["guard_disagreement_count"] == 0


def test_llm_shadow_gate_provider_ok_sets_ready_when_guard_agrees(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    expected_routes = iter(
        scene["expected_route_label"]
        for scene in gate.generate_random_scenes(seed=123, random_cases=10, scene_set=gate.HARD_SCENE_SET)
    )

    def fake_call_openai_responses(**_kwargs):
        route_label = next(expected_routes)
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": gate.OPENAI_TOOL_NAME,
                    "arguments": (
                        '{"route_label": "%s", "rationale_short": "fixture route", "confidence": 0.99}'
                        % route_label
                    ),
                }
            ]
        }

    monkeypatch.setattr(gate, "call_openai_responses", fake_call_openai_responses)
    args = SimpleNamespace(
        campaign_id="planner_gate_llm_shadow_provider_ok",
        scene_set=gate.HARD_SCENE_SET,
        scene_descriptor_json=[],
        scene_dir="",
        random_cases=10,
        seed=123,
        planner_mode=gate.PLANNER_MODE_LLM_SHADOW,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="test-key",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["llm_shadow_ready"] is True
    assert summary["llm_shadow_provider_ok_count"] == 10
    assert summary["provider_status_counts"] == {"ok": 10}
    assert summary["planner_mode_effective_counts"] == {gate.PLANNER_MODE_LLM_SHADOW: 10}
    assert summary["guard_agreement_count"] == 10
    assert summary["guard_disagreement_count"] == 0


def test_llm_supervised_guarded_accepts_only_guard_agreeing_high_confidence(monkeypatch):
    scene = next(
        item for item in gate.generate_random_scenes(seed=456, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_NAV2_REPOSITION
    )

    def fake_call_openai_responses(**_kwargs):
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": gate.OPENAI_TOOL_NAME,
                    "arguments": (
                        '{"route_label": "nav2_reposition_first", '
                        '"rationale_short": "matches guard", "confidence": 0.96}'
                    ),
                }
            ]
        }

    monkeypatch.setattr(gate, "call_openai_responses", fake_call_openai_responses)

    decision = gate.decide_scene(
        scene,
        planner_mode=gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
        openai_api_key="test-key",
    )

    assert decision["route_label"] == gate.ROUTE_NAV2_REPOSITION
    assert decision["planner_mode_effective"] == gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED
    assert decision["provider_status"] == "ok"
    assert decision["llm_supervised_guard"]["accepted"] is True
    assert decision["llm_supervised_guard"]["veto_reasons"] == []


def test_llm_supervised_guarded_vetoes_disagreement_and_keeps_guard_route(monkeypatch):
    scene = next(
        item for item in gate.generate_random_scenes(seed=456, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_NAV2_REPOSITION
    )

    def fake_call_openai_responses(**_kwargs):
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": gate.OPENAI_TOOL_NAME,
                    "arguments": (
                        '{"route_label": "fetch_ready_local", '
                        '"rationale_short": "too eager", "confidence": 0.99}'
                    ),
                }
            ]
        }

    monkeypatch.setattr(gate, "call_openai_responses", fake_call_openai_responses)

    decision = gate.decide_scene(
        scene,
        planner_mode=gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
        openai_api_key="test-key",
    )

    assert decision["route_label"] == gate.ROUTE_NAV2_REPOSITION
    assert decision["planner_mode_effective"] == "deterministic_fallback"
    assert decision["provider_status"] == "ok"
    assert decision["wrong_fetch_ready_dispatch"] is False
    assert decision["llm_supervised_guard"]["accepted"] is False
    assert decision["llm_supervised_guard"]["decision"] == "vetoed"
    assert "guard_disagreement" in decision["llm_supervised_guard"]["veto_reasons"]


def test_llm_supervised_gate_summary_reports_accepts(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    expected_routes = iter(
        scene["expected_route_label"]
        for scene in gate.generate_random_scenes(seed=123, random_cases=10, scene_set=gate.HARD_SCENE_SET)
    )

    def fake_call_openai_responses(**_kwargs):
        route_label = next(expected_routes)
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": gate.OPENAI_TOOL_NAME,
                    "arguments": (
                        '{"route_label": "%s", "rationale_short": "fixture route", "confidence": 0.95}'
                        % route_label
                    ),
                }
            ]
        }

    monkeypatch.setattr(gate, "call_openai_responses", fake_call_openai_responses)
    args = SimpleNamespace(
        campaign_id="planner_gate_llm_supervised_provider_ok",
        scene_set=gate.HARD_SCENE_SET,
        scene_descriptor_json=[],
        scene_dir="",
        random_cases=10,
        seed=123,
        planner_mode=gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
        dry_run=True,
        openai_model=gate.DEFAULT_OPENAI_MODEL,
        openai_api_key="test-key",
        openai_base_url=gate.DEFAULT_OPENAI_BASE_URL,
        openai_org_id="",
        openai_project_id="",
        reasoning_effort=gate.DEFAULT_REASONING_EFFORT,
        timeout_s=30.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["llm_supervised_ready"] is True
    assert summary["llm_supervised_accept_count"] == 10
    assert summary["llm_supervised_veto_count"] == 0
    assert summary["provider_status_counts"] == {"ok": 10}
    assert summary["planner_mode_effective_counts"] == {gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED: 10}


def test_fetch_ready_layout_writer_preserves_planner_scene(tmp_path):
    scene = next(
        item for item in gate.generate_random_scenes(seed=789, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_FETCH_READY
    )
    layout_path = tmp_path / "layout.json"

    gate.write_fetch_ready_layout_from_scene(layout_path, scene)

    layout = read_json(layout_path)
    assert layout["layout_family"] == "planner_gated_fetch_ready"
    assert layout["random_profile"] == gate.PLANNER_MIXED_PROFILE
    assert layout["planner_scene"]["scene_id"] == scene["scene_id"]
    assert layout["route_quality"]["route_label"] == gate.ROUTE_FETCH_READY
    assert layout["maneuver_plan"]["requires_measured_push_ready_before_fetch"] is True
    assert layout["random_draw"]["route_quality"]["route_label"] == gate.ROUTE_FETCH_READY
    assert layout["random_draw"]["maneuver_plan"]["push_ready_index"] < layout["random_draw"]["maneuver_plan"]["local_fetch_index"]
    assert layout["targets"][0]["forward_m"] == scene["ball_pose"]["x"]


def test_layout_writer_preserves_nonlocal_planner_route_metadata(tmp_path):
    scene = next(
        item for item in gate.generate_random_scenes(seed=789, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_NAV2_REPOSITION
    )
    layout_path = tmp_path / "layout.json"

    gate.write_fetch_ready_layout_from_scene(
        layout_path,
        scene,
        route_label=gate.ROUTE_NAV2_REPOSITION,
        route_executor=gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH,
    )

    layout = read_json(layout_path)
    assert layout["layout_family"] == "planner_gated_nav2_reposition_first"
    assert layout["planner_route_label"] == gate.ROUTE_NAV2_REPOSITION
    assert layout["route_executor"] == gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert layout["random_draw"]["planner_route_label"] == gate.ROUTE_NAV2_REPOSITION
