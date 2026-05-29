from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_generalization_gate as gate  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402


def test_fetch_generalization_gate_dry_run_generates_layouts_and_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    args = SimpleNamespace(
        campaign_id="dry_seeded_gate",
        dry_run=True,
        random_cases=2,
        runs=1,
        seed=123,
        architecture=["ai_push_coast_servo_v1"],
        world_file="yolo_test_world_v6_calibrated_golf_turf.world",
        surface_profile="calibrated_golf_turf",
        fetch_delivery_radius_m=0.3,
        ai_push_coast_mode="guarded_live",
        dashboard_url="http://127.0.0.1:8860",
        provider="local_stub",
        timeout_s=30.0,
        scenario_timeout_s=240.0,
    )

    summary = gate.run_gate(args)

    assert summary["pass"] is True
    assert summary["dry_run"] is True
    assert summary["random_cases"] == 2
    assert len(summary["results"]) == 2
    for result in summary["results"]:
        layout_path = Path(result["layout_path"])
        assert layout_path.exists()
        layout = read_json(layout_path)
        assert layout["targets"][0]["start_visible"] is True
        command = result["command"]
        assert "--gather-control-family" in command
        assert command[command.index("--gather-control-family") + 1] == "ai_push_coast_servo_v1"
        assert "--ai-push-coast-mode" in command
        assert command[command.index("--ai-push-coast-mode") + 1] == "guarded_live"
        assert "--target-layout-json" in command
        assert command[command.index("--target-layout-json") + 1] == str(layout_path)
    summary_path = tmp_path / "artifacts" / "session" / "dry_seeded_gate" / "fetch_generalization_gate" / "gate_summary.json"
    assert summary_path.exists()
