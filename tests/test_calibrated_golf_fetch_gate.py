from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import calibrated_golf_fetch_gate as gate  # noqa: E402


def _args(**overrides):
    values = {
        "dashboard_url": "http://127.0.0.1:8860",
        "suite": "all",
        "campaign_id": "test_calibrated_gate",
        "cta_runs": 3,
        "policy_runs": 3,
        "off_axis_runs": 1,
        "provider": "local_stub",
        "world_file": gate.DEFAULT_WORLD_FILE,
        "surface_profile": gate.DEFAULT_SURFACE_PROFILE,
        "fetch_target_x": 0.95,
        "fetch_target_y": 0.0,
        "fetch_target_z": 0.001,
        "fetch_delivery_radius_m": 0.30,
        "scenario_timeout_s": 240.0,
        "timeout_s": 30.0,
        "dry_run": False,
        "stop_on_failure": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_gate_specs_includes_centerline_and_off_axis_commands():
    specs = gate.build_gate_specs(_args())

    assert [spec.gate_id for spec in specs] == [
        "cta_centerline",
        "policy_centerline",
        "policy_left05",
        "policy_right05",
    ]
    cta = specs[0].command
    assert "--execution-mode" in cta
    assert cta[cta.index("--execution-mode") + 1] == "dashboard_scenario"
    assert cta[cta.index("--scenario-id") + 1] == "golf_ball_circle_delivery_uat"

    policy = specs[1].command
    assert policy[policy.index("--execution-mode") + 1] == "direct"
    assert policy[policy.index("--target-layout-json") + 1] == gate.DEFAULT_CENTERLINE_LAYOUT
    assert policy[policy.index("--target-model-sdf") + 1] == gate.DEFAULT_BALL_SDF
    assert policy[policy.index("--zone-model-sdf") + 1] == gate.DEFAULT_ZONE_SDF
    assert policy[policy.index("--max-retries-per-target") + 1] == "0"

    left = specs[2].command
    assert left[left.index("--target-layout-json") + 1] == gate.OFF_AXIS_LAYOUTS["left05"]


def test_run_gate_reads_repeatability_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    summary_path = tmp_path / "artifacts" / "session" / "campaign" / "gather_mission_repeatability" / "campaign_run_summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(
        '{"promotion_gate_pass": true, "fetch_to_pose_pass_count": 3, "fetch_to_pose_fail_count": 0, "required_green_runs": 3}\n',
        encoding="utf-8",
    )
    spec = gate.GateSpec(
        gate_id="policy_centerline",
        label="Policy",
        command=["python", "runner.py"],
        campaign_id="campaign",
        summary_path=summary_path,
    )

    def fake_run(command, cwd, capture_output, text, check):
        assert command == ["python", "runner.py"]
        assert cwd == str(tmp_path)
        return SimpleNamespace(stdout="ok", stderr="", returncode=0)

    monkeypatch.setattr(gate.subprocess, "run", fake_run)

    result = gate.run_gate(spec, logs_root=tmp_path / "logs", dry_run=False)

    assert result["pass"] is True
    assert result["fetch_to_pose_pass_count"] == 3
    assert result["fetch_to_pose_fail_count"] == 0
