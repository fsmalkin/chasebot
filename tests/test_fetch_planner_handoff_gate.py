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
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_SCAN_OR_PERCEIVE]) == gate.ROUTE_SCAN_OR_PERCEIVE
    assert gate.deterministic_route_label(by_expected[gate.ROUTE_NO_GO]) == gate.ROUTE_NO_GO
    assert by_expected[gate.ROUTE_FETCH_READY]["local_fetch_envelope"]["eligible"] is True
    assert by_expected[gate.ROUTE_SCAN_OR_PERCEIVE]["local_fetch_envelope"]["eligible"] is False
    assert by_expected[gate.ROUTE_RECOVERY_OR_REAIM]["local_fetch_envelope"]["eligible"] is False


def test_route_executor_mapping_covers_all_route_labels():
    assert gate.executor_for_route(gate.ROUTE_FETCH_READY) == gate.ROUTE_EXECUTOR_LOCAL_FETCH
    assert gate.executor_for_route(gate.ROUTE_NAV2_REPOSITION) == gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert gate.executor_for_route(gate.ROUTE_SCAN_OR_PERCEIVE) == gate.ROUTE_EXECUTOR_SCAN
    assert gate.executor_for_route(gate.ROUTE_RECOVERY_OR_REAIM) == gate.ROUTE_EXECUTOR_RECOVERY
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
