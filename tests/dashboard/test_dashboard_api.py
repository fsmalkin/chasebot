from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO_ROOT / "runtime" / "dashboard" / "dashboard_session.lock.json"


def test_01_environment_start_is_idempotent(dashboard_client):
    dashboard_client.request("POST", "/api/env/stop")
    dashboard_client.wait_for(lambda state: state["environment_state"] == "stopped", 90, "Environment did not reach stopped state.")

    status, payload = dashboard_client.request("POST", "/api/env/start")
    assert status == 202, payload
    ready = dashboard_client.wait_for(
        lambda state: state["environment_state"] == "environment_ready" and state["scenario_state"] == "ready",
        360,
        "Environment did not become ready.",
    )
    assert ready["session_id"]
    assert LOCK_PATH.exists()

    status, payload = dashboard_client.request("POST", "/api/env/start")
    assert status == 200, payload
    assert payload["accepted"] is False


def test_02_second_scenario_is_blocked_while_active(dashboard_client):
    status, payload = dashboard_client.request("POST", "/api/scenario/run", {"scenario_id": "m3_single_target"})
    assert status == 202, payload
    dashboard_client.wait_for(lambda state: state["scenario_state"] == "running", 45, "Scenario did not start.")

    status, payload = dashboard_client.request("POST", "/api/scenario/run", {"scenario_id": "m3_left"})
    assert status == 409, payload

    status, payload = dashboard_client.request("POST", "/api/scenario/stop")
    assert status == 202, payload
    dashboard_client.wait_for(
        lambda state: state["environment_state"] == "environment_ready" and state["scenario_state"] == "ready",
        180,
        "Scenario stop did not return the environment to ready state.",
    )


def test_03_reset_sim_creates_new_session_id(dashboard_client):
    before = dashboard_client.state()
    old_session = before["session_id"]

    status, payload = dashboard_client.request("POST", "/api/sim/reset")
    assert status == 202, payload

    after = dashboard_client.wait_for(
        lambda state: state["environment_state"] == "environment_ready" and state["session_id"] and state["session_id"] != old_session,
        420,
        "Reset sim did not create a new session.",
    )
    assert after["session_id"] != old_session
    assert LOCK_PATH.exists()


def test_04_invalid_scenario_is_rejected_and_single_target_artifacts_exist(dashboard_client):
    status, payload = dashboard_client.request("POST", "/api/scenario/run", {"scenario_id": "not_real"})
    assert status == 400, payload

    status, payload = dashboard_client.request("POST", "/api/scenario/run", {"scenario_id": "m3_single_target"})
    assert status == 202, payload
    final_state = dashboard_client.wait_for(
        lambda state: state["scenario_state"] == "ready" and state["motion_evidence"] is True,
        600,
        "m3_single_target did not complete successfully.",
    )

    nav_dir = Path(final_state["latest_artifacts"]["nav2"])
    snapshot_dir = Path(final_state["latest_artifacts"]["snapshot"])
    assert nav_dir.exists()
    assert snapshot_dir.exists()
    nav_summary = json.loads((nav_dir / "nav_summary.json").read_text(encoding="utf-8"))
    snapshot_summary = json.loads((snapshot_dir / "snapshot_summary.json").read_text(encoding="utf-8"))
    assert nav_summary["pass"] is True
    assert snapshot_summary["pass"] is True


def test_05_multi_target_transition_artifacts_and_stop_work(dashboard_client):
    status, payload = dashboard_client.request("POST", "/api/scenario/run", {"scenario_id": "multi_target_rehearsal"})
    assert status == 202, payload

    dashboard_client.wait_for(lambda state: state["scenario_state"] == "running", 45, "Multi-target rehearsal did not start.")
    transition_state = dashboard_client.wait_for(
        lambda state: state["target_transition_active"] is True,
        600,
        "target_transition_active never became true during multi-target rehearsal.",
    )
    assert transition_state["target_id"]

    final_state = dashboard_client.wait_for(
        lambda state: state["scenario_state"] == "ready",
        720,
        "Multi-target rehearsal did not return to ready state.",
    )
    multi_dir = Path(final_state["latest_artifacts"]["multi_target"])
    progress_path = Path(final_state["latest_artifacts"]["progress"])
    assert multi_dir.exists()
    assert progress_path.exists()
    summary = json.loads((multi_dir / "multi_target_summary.json").read_text(encoding="utf-8"))
    assert summary["pass"] is True


def test_06_frozen_intents_write_command_history_and_contract_results(dashboard_client):
    session_id = dashboard_client.state()["session_id"]
    validation_dir = REPO_ROOT / "artifacts" / "session" / session_id / "dashboard_validation"
    history_path = validation_dir / "command_history.jsonl"

    checks = [
        ("/api/intents/acquire_target", {"target_class": "ball"}, "acquire_target"),
        ("/api/intents/plan_to_target", {"approach_distance_m": 0.25}, "plan_to_target"),
        ("/api/intents/track_target", {}, "track_target"),
        ("/api/intents/abort", {}, "abort"),
        ("/api/intents/safe_stop", {}, "safe_stop"),
    ]
    for path, body, intent_name in checks:
        status, payload = dashboard_client.request("POST", path, body)
        assert status == 202, payload
        state = dashboard_client.wait_for(
            lambda current, intent=intent_name: current["last_intent"] == intent,
            90,
            f"{intent_name} did not update dashboard state.",
        )
        assert intent_name in state["last_result"]

    status, payload = dashboard_client.request("POST", "/api/intents/not_in_contract", {})
    assert status == 404, payload

    assert history_path.exists()
    history_lines = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    recorded_intents = {entry["intent"] for entry in history_lines}
    assert {"acquire_target", "plan_to_target", "track_target", "abort", "safe_stop"}.issubset(recorded_intents)
    for entry in history_lines:
        summary_path = Path(entry["summary_path"])
        assert summary_path.exists()


def test_07_reset_while_scenario_active_recovers_to_ready(dashboard_client):
    before = dashboard_client.state()["session_id"]

    status, payload = dashboard_client.request("POST", "/api/scenario/run", {"scenario_id": "multi_target_rehearsal"})
    assert status == 202, payload
    dashboard_client.wait_for(lambda state: state["scenario_state"] == "running", 45, "Scenario did not start before reset.")

    status, payload = dashboard_client.request("POST", "/api/sim/reset")
    assert status == 202, payload
    ready = dashboard_client.wait_for(
        lambda state: state["environment_state"] == "environment_ready" and state["session_id"] != before,
        420,
        "Reset during active scenario did not recover to a new ready session.",
    )
    assert ready["session_id"] != before


def test_08_stop_clears_lock_and_chasecar_containers(dashboard_client):
    status, payload = dashboard_client.request("POST", "/api/env/stop")
    assert status in {200, 202}, payload
    final_state = dashboard_client.wait_for(
        lambda state: state["environment_state"] == "stopped",
        180,
        "Environment did not stop cleanly.",
    )

    assert not LOCK_PATH.exists()
    docker = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    chasecar_names = [name.strip() for name in docker.stdout.splitlines() if name.strip().startswith("chasecar_dashboard_")]
    assert chasecar_names == [], json.dumps({"stale": chasecar_names, "state": final_state}, indent=2)


def test_09_interrupted_start_leaves_recoverable_stopped_state(dashboard_client):
    status, payload = dashboard_client.request("POST", "/api/env/start")
    assert status == 202, payload

    status, payload = dashboard_client.request("POST", "/api/env/stop")
    assert status in {202, 200}, payload
    dashboard_client.wait_for(lambda state: state["environment_state"] == "stopped", 240, "Interrupted start did not settle to stopped.")

    status, payload = dashboard_client.request("POST", "/api/env/start")
    assert status == 202, payload
    dashboard_client.wait_for(
        lambda state: state["environment_state"] == "environment_ready",
        360,
        "Environment did not recover after interrupted start.",
    )
    dashboard_client.request("POST", "/api/env/stop")
    dashboard_client.wait_for(lambda state: state["environment_state"] == "stopped", 180, "Final cleanup stop did not complete.")
