from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_generalization_gate as gate  # noqa: E402


def _args(**overrides):
    values = {
        "dashboard_url": "http://127.0.0.1:8860",
        "campaign_id": "test_generalization",
        "seed": 1234,
        "random_cases": 6,
        "include_saved_anchors": True,
        "architecture": [],
        "runs": 1,
        "provider": "local_stub",
        "world_file": gate.fetch_gate.DEFAULT_WORLD_FILE,
        "surface_profile": gate.fetch_gate.DEFAULT_SURFACE_PROFILE,
        "scenario_timeout_s": 240.0,
        "timeout_s": 30.0,
        "dry_run": True,
        "stop_on_failure": False,
        "output_root": REPO_ROOT / "artifacts" / "session",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_seeded_cases_cover_required_generalization_tags(tmp_path: Path):
    case_dir = tmp_path / "layouts"
    cases = gate.build_saved_anchor_cases(case_dir)
    cases.extend(gate.build_seeded_random_cases(case_dir, seed=1234, count=6))

    coverage = gate._coverage_summary(cases)

    assert coverage["coverage_pass"] is True
    for required in gate.REQUIRED_GENERALIZATION_TAGS:
        assert required in coverage["observed_tags"]
    opposite = next(case for case in cases if "opposite_side_start" in case.coverage_tags)
    assert opposite.geometry["target_relative_side"] == "opposite_side"
    payload = json.loads(opposite.layout_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["case_id"] == opposite.case_id
    assert payload["targets"][0]["id"] == "ball_1"


def test_architecture_specs_build_comparable_commands(tmp_path: Path):
    case = gate.build_seeded_random_cases(tmp_path / "layouts", seed=42, count=1)[0]
    args = _args(campaign_id="cmp", architecture=["object_centric_gather_policy_v1", "contact_aware_geometric_shooter"])

    specs = gate.build_architecture_specs(args, cases=[case], logs_root=tmp_path / "logs")

    assert [spec.architecture for spec in specs] == [
        "object_centric_gather_policy_v1",
        "contact_aware_geometric_shooter",
    ]
    object_command = specs[0].command
    assert object_command[object_command.index("--mission-objective") + 1] == "fetch_to_pose"
    assert object_command[object_command.index("--robot-x") + 1] == f"{case.robot_start_pose['x']:.6f}"
    assert object_command[object_command.index("--robot-yaw") + 1] == f"{case.robot_start_pose['yaw']:.6f}"
    assert object_command[object_command.index("--target-layout-json") + 1].endswith(f"{case.case_id}.json")
    assert specs[0].robot_owned_contact is True

    shooter_command = specs[1].command
    assert shooter_command[shooter_command.index("--target-layout-json") + 1].endswith(f"{case.case_id}.json")
    assert shooter_command[shooter_command.index("--speed-mode") + 1] == "center"
    assert specs[1].robot_owned_contact is False


def test_failure_classification_maps_geometry_relevant_reasons():
    side_selection = {
        "return_code": 2,
        "pass": False,
        "metrics": {
            "pass": False,
            "failure_reasons": ["entered_goal_side_before_capture"],
        },
    }
    assert gate._classify_result(side_selection, delivery_radius_m=0.3) == "side_selection"

    first_contact = {
        "return_code": 2,
        "pass": False,
        "metrics": {
            "pass": False,
            "failure_reasons": ["missing_first_contact_alignment"],
        },
    }
    assert gate._classify_result(first_contact, delivery_radius_m=0.3) == "first_contact_alignment"

    shot_infeasible = {
        "return_code": 2,
        "pass": False,
        "metrics": {
            "pass": False,
            "offline_model_pass": False,
            "failure_reasons": [],
        },
    }
    assert gate._classify_result(shot_infeasible, delivery_radius_m=0.3) == "shot_infeasible"


def test_dry_run_writes_contract_summary(tmp_path: Path, monkeypatch):
    args = _args(output_root=tmp_path, campaign_id="dry_contract", dry_run=True)
    monkeypatch.setattr(gate, "parse_args", lambda: args)

    assert gate.main() == 0

    summary_path = tmp_path / "dry_contract" / "fetch_generalization_gate" / "generalization_gate_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["coverage"]["coverage_pass"] is True
    assert summary["recommended_next_action"] == "run_live_saved_anchor_and_seeded_generalization_gate"
    assert {result["classification"] for result in summary["results"]} == {"dry_run_contract_only"}
