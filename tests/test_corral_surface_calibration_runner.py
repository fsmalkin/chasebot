import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import corral_surface_calibration_runner as calibration_runner  # noqa: E402


def test_surface_calibration_runner_writes_campaign_summary_and_scorecard(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(calibration_runner, "REPO_ROOT", tmp_path)

    def fake_wait_for_dashboard(_dashboard_url: str, timeout_s: float) -> None:
        assert timeout_s == 90.0

    lane_roots: dict[str, Path] = {}

    def fake_subprocess_run(command, cwd, capture_output, text, check):
        assert cwd == str(tmp_path)
        assert capture_output is True
        assert text is True
        assert check is False
        surface_profile = command[command.index("--surface-profile") + 1]
        lane_campaign_id = command[command.index("--campaign-id") + 1]
        lane_root = tmp_path / "artifacts" / "session" / lane_campaign_id / "gather_mission_repeatability"
        lane_root.mkdir(parents=True, exist_ok=True)
        summary_path = lane_root / "campaign_run_summary.json"
        lane_roots[surface_profile] = summary_path
        if surface_profile == "baseline":
            runs = [
                {
                    "settled_in_corral_pass": True,
                    "final_settle_distance_m": 0.30,
                    "max_overshoot_distance_m": 0.12,
                    "settle_time_s": 2.1,
                    "release_recontact_count": 1,
                    "mission_time_s": 74.0,
                }
            ]
        elif surface_profile == "short_turf":
            runs = [
                {
                    "settled_in_corral_pass": True,
                    "final_settle_distance_m": 0.18,
                    "max_overshoot_distance_m": 0.06,
                    "settle_time_s": 1.4,
                    "release_recontact_count": 0,
                    "mission_time_s": 68.0,
                }
            ]
        else:
            runs = [
                {
                    "settled_in_corral_pass": True,
                    "final_settle_distance_m": 0.10,
                    "max_overshoot_distance_m": 0.03,
                    "settle_time_s": 0.9,
                    "release_recontact_count": 0,
                    "mission_time_s": 61.0,
                }
            ]
        summary_path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
        (lane_root / "scorecard.md").write_text("# lane", encoding="utf-8")

        class Completed:
            returncode = 0
            stdout = f"GATHER_MISSION_REPEATABILITY_SUMMARY={summary_path}\n"
            stderr = ""

        return Completed()

    monkeypatch.setattr(calibration_runner, "wait_for_dashboard", fake_wait_for_dashboard)
    monkeypatch.setattr(calibration_runner.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(
        calibration_runner,
        "parse_args",
        lambda: calibration_runner.argparse.Namespace(
            dashboard_url="http://127.0.0.1:8860",
            scenario_id="corral_single_ball_place",
            scenario_label="Corral Single Ball Place",
            runs_per_lane=3,
            campaign_id="surface-calibration-test",
            provider="openai",
            execution_mode="dashboard_scenario",
            promotion_gate_mode="pass_only",
            visit_runtime_json="",
            gather_runtime_json="",
            preferred_surface_profile="short_turf",
        ),
    )

    result = calibration_runner.main()

    summary_path = tmp_path / "artifacts" / "session" / "surface-calibration-test" / "corral_surface_calibration" / "campaign_summary.json"
    scorecard_path = tmp_path / "artifacts" / "session" / "surface-calibration-test" / "corral_surface_calibration" / "scorecard.md"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert result == 0
    assert summary_path.exists()
    assert scorecard_path.exists()
    assert payload["type"] == "corral_surface_calibration"
    assert payload["runs_per_lane"] == 3
    assert payload["canonical_surface_profile"] == "short_turf"
    assert payload["settle_distance_order_ok"] is True
    assert payload["overshoot_order_ok"] is True
    assert payload["settle_time_order_ok"] is True
    assert [item["surface_profile"] for item in payload["lane_summaries"]] == ["baseline", "short_turf", "short_grass"]
    assert all(Path(item["repeatability_summary_path"]).exists() for item in payload["lane_summaries"])
    assert "short_turf" in scorecard_path.read_text(encoding="utf-8")
