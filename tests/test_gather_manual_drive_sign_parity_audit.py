from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_escape_sandbox as sandbox  # noqa: E402
import gather_manual_drive_sign_parity_audit as audit  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
GOAL_SIDE_ONLY_LOCAL = {"x": 0.023141687334822705, "y": 1.3629109105513886, "yaw": -0.8439014238462192}


def _quat_from_yaw(yaw_rad: float) -> dict[str, float]:
    half = yaw_rad / 2.0
    return {"x": 0.0, "y": 0.0, "z": math.sin(half), "w": math.cos(half)}


def _world_pose_from_local(local_pose: dict[str, float], ball_pose: dict[str, float] | None = None) -> dict[str, float]:
    world_pose = sandbox.local_pose_to_world(local_pose, ball_pose or BALL_POSE, zone=ZONE)
    assert world_pose is not None
    return world_pose


def _truth_sample(t_s: float, local_pose: dict[str, float], *, ball_pose: dict[str, float] | None = None) -> dict[str, object]:
    resolved_ball_pose = ball_pose or BALL_POSE
    robot_world = _world_pose_from_local(local_pose, resolved_ball_pose)
    return {
        "t_s": t_s,
        "robot_truth_pose": {
            "name": "jetbot",
            "position": {"x": robot_world["x"], "y": robot_world["y"], "z": 0.0},
            "orientation": _quat_from_yaw(robot_world["yaw"]),
        },
        "true_target_pose": {
            "name": "ball_1",
            "position": {
                "x": resolved_ball_pose["x"],
                "y": resolved_ball_pose["y"],
                "z": resolved_ball_pose.get("z", 0.05),
            },
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def _state_row(
    index: int,
    local_pose: dict[str, float],
    *,
    angular_z: float = 0.45,
    linear_x: float = -0.18,
    mode: str = "pre_stage_escape_goal_side",
    controller_family: str = "short_horizon_v2",
) -> dict[str, object]:
    robot_world = _world_pose_from_local(local_pose, BALL_POSE)
    return {
        "generated_utc": f"2026-04-19T22:00:{index:02d}+00:00",
        "phase": "pre_stage",
        "attempt": 0,
        "fixture_index": index,
        "robot_pose": robot_world,
        "ball_pose": dict(BALL_POSE),
        "robot_pose_local": dict(local_pose),
        "pre_stage": {
            "yaw_error_deg": 30.0,
            "robot_longitudinal_projection_m": local_pose["x"],
            "robot_lateral_signed_m": local_pose["y"],
            "robot_lateral_error_m": abs(local_pose["y"]),
        },
        "selected_command": {
            "angular_z": angular_z,
            "linear_x": linear_x,
            "mode": mode,
        },
        "manager_directive": "recover_goal_side",
        "controller_family": controller_family,
        "strategy_name": "synthetic",
        "objective_name": "synthetic",
        "progress_score": 0.0,
        "stall_s": 0.0,
        "projected_projection_gain": 0.0,
        "projected_lateral_gain": 0.0,
        "projected_distance_gain": 0.0,
    }


def _write_state_history(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def _sign_surfaces(*, static_config_parity_expected: bool = True) -> dict[str, object]:
    return {
        "bridge_sign_preserved": static_config_parity_expected,
        "controller_configs_match": static_config_parity_expected,
        "controller_negative_symmetric_radius_multipliers": static_config_parity_expected,
        "static_config_parity_expected": static_config_parity_expected,
        "state_history_robot_pose_from_belief_pose": True,
        "visual_latest_robot_pose_from_odom": True,
        "dashboard_truth_fallback_present": True,
    }


def test_classify_fixture_sign_parity_marks_odom_world_divergence():
    payload = audit.classify_fixture_sign_parity(
        fixture_label="synthetic_fixture",
        fixture_index=0,
        controller_family="short_horizon_v2",
        alignment_quality="good",
        target_turn_sign=1,
        command_sign=1,
        odom_metrics={
            "dominant_yaw_sign": 1,
            "wrong_sign_episode_count": 0,
            "wrong_sign_step_count": 0,
        },
        world_metrics={
            "dominant_yaw_sign": -1,
            "wrong_sign_episode_count": 2,
            "wrong_sign_step_count": 6,
        },
        turn_flags={"sign_parity_limited": True},
        sign_parity_surfaces=_sign_surfaces(static_config_parity_expected=True),
    )

    assert payload["classifier_flags"]["odom_world_sign_divergent"] is True
    assert payload["fixture_diagnosis"] == "odom_world_sign_divergent"


def test_classify_fixture_sign_parity_marks_static_surface_mismatch():
    payload = audit.classify_fixture_sign_parity(
        fixture_label="synthetic_fixture",
        fixture_index=0,
        controller_family="short_horizon_v2",
        alignment_quality="good",
        target_turn_sign=1,
        command_sign=1,
        odom_metrics={
            "dominant_yaw_sign": 1,
            "wrong_sign_episode_count": 0,
            "wrong_sign_step_count": 0,
        },
        world_metrics={
            "dominant_yaw_sign": 1,
            "wrong_sign_episode_count": 0,
            "wrong_sign_step_count": 0,
        },
        turn_flags={"sign_parity_limited": True},
        sign_parity_surfaces=_sign_surfaces(static_config_parity_expected=False),
    )

    assert payload["classifier_flags"]["static_sign_surface_mismatch"] is True
    assert payload["fixture_diagnosis"] == "static_sign_surface_mismatch"


def test_build_and_write_manual_drive_sign_parity_bundle_from_temp_artifacts(tmp_path: Path):
    session_id = "session_manual_drive_sign_parity_temp"
    mission_root = tmp_path / "artifacts" / "session" / session_id / "gather_mission" / "20260419T220438Z"
    visual_root = tmp_path / "artifacts" / "session" / session_id / "visual"
    mission_root.mkdir(parents=True, exist_ok=True)
    visual_root.mkdir(parents=True, exist_ok=True)

    state_rows = [
        _state_row(index, GOAL_SIDE_ONLY_LOCAL, angular_z=0.45, mode=f"mode_{index}")
        for index in range(5)
    ]
    _write_state_history(mission_root / "state_history.jsonl", state_rows)

    truth_samples = [
        _truth_sample(1.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(
            2.0,
            {
                "x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.01,
                "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01,
                "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.15,
            },
        ),
        _truth_sample(
            3.0,
            {
                "x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.02,
                "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02,
                "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.30,
            },
        ),
        _truth_sample(
            4.0,
            {
                "x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.03,
                "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03,
                "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.45,
            },
        ),
        _truth_sample(
            5.0,
            {
                "x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.04,
                "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.04,
                "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.60,
            },
        ),
    ]
    (visual_root / "truth_timeline.json").write_text(json.dumps(truth_samples, indent=2), encoding="utf-8")
    timeline_payload = {
        "samples": [{"t_s": item["t_s"]} for item in truth_samples],
        "events": [
            {
                "event_type": "feedback_observed",
                "timestamp_utc": "2026-04-19T22:00:00+00:00",
                "t_s": 1.0,
            }
        ],
    }
    (visual_root / "timeline.json").write_text(json.dumps(timeline_payload, indent=2), encoding="utf-8")
    (visual_root / "timeline_events.jsonl").write_text("", encoding="utf-8")
    (mission_root / "mission_verdict.json").write_text(
        json.dumps({"pre_stage_handoff_pass": False, "approach_failure_reason": "pre_stage_timeout"}, indent=2),
        encoding="utf-8",
    )
    (mission_root / "gather_sequence.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "route_planned", "timestamp_utc": "2026-04-19T22:00:00+00:00"}),
                json.dumps(
                    {
                        "event_type": "pre_stage_result",
                        "timestamp_utc": "2026-04-19T22:00:05+00:00",
                        "status": "pre_stage_timeout",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    campaign_summary = {
        "campaign_id": "temp_manual_drive_sign_parity_source",
        "runs": [
            {
                "run_index": 0,
                "session_id": session_id,
                "mission_root": str(mission_root),
            }
        ],
    }
    campaign_summary_path = tmp_path / "campaign_run_summary.json"
    campaign_summary_path.write_text(json.dumps(campaign_summary, indent=2), encoding="utf-8")

    summary, fixture_payloads = audit.build_manual_drive_sign_parity_audit_bundle(
        campaign_id="temp_manual_drive_sign_parity_audit",
        campaign_summary_path=campaign_summary_path,
        run_index=0,
    )
    output_paths = audit.write_manual_drive_sign_parity_audit_bundle(
        campaign_id="temp_manual_drive_sign_parity_audit",
        summary=summary,
        fixture_payloads=fixture_payloads,
        repo_root=tmp_path,
    )

    assert summary["type"] == "gather_manual_drive_sign_parity_audit"
    assert summary["source_campaign_id"] == "temp_manual_drive_sign_parity_source"
    assert summary["representative_fixture_count"] == 5
    assert output_paths["summary_path"].exists()
    assert output_paths["scorecard_path"].exists()
    for fixture_label in (
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    ):
        assert (output_paths["fixtures_root"] / f"{fixture_label}.json").exists()


def test_decide_sign_parity_root_cause_opens_odom_world_probe():
    payloads = [
        {"classifier_flags": {"sign_parity_fixture_from_turn_audit": True, "static_sign_surface_mismatch": False, "odom_world_sign_divergent": True, "command_odom_sign_divergent": False}},
        {"classifier_flags": {"sign_parity_fixture_from_turn_audit": True, "static_sign_surface_mismatch": False, "odom_world_sign_divergent": True, "command_odom_sign_divergent": False}},
        {"classifier_flags": {"sign_parity_fixture_from_turn_audit": True, "static_sign_surface_mismatch": False, "odom_world_sign_divergent": True, "command_odom_sign_divergent": False}},
        {"classifier_flags": {"sign_parity_fixture_from_turn_audit": True, "static_sign_surface_mismatch": False, "odom_world_sign_divergent": False, "command_odom_sign_divergent": False}},
        {"classifier_flags": {"sign_parity_fixture_from_turn_audit": True, "static_sign_surface_mismatch": False, "odom_world_sign_divergent": False, "command_odom_sign_divergent": False}},
    ]
    gate = audit.decide_sign_parity_root_cause(
        payloads,
        sign_parity_surfaces=_sign_surfaces(static_config_parity_expected=True),
    )
    action = audit._next_action_recommendation(gate["dominant_diagnosis"])

    assert gate["dominant_diagnosis"] == "odom_world_sign_divergent"
    assert action["decision"] == "probe_odom_world_sign_chain"


def test_decide_sign_parity_root_cause_prefers_static_surface_fix():
    payloads = [
        {"classifier_flags": {"sign_parity_fixture_from_turn_audit": True, "static_sign_surface_mismatch": True, "odom_world_sign_divergent": False, "command_odom_sign_divergent": False}}
        for _ in range(5)
    ]
    gate = audit.decide_sign_parity_root_cause(
        payloads,
        sign_parity_surfaces=_sign_surfaces(static_config_parity_expected=False),
    )
    action = audit._next_action_recommendation(gate["dominant_diagnosis"])

    assert gate["dominant_diagnosis"] == "static_sign_surface_mismatch"
    assert action["decision"] == "fix_static_sign_surface"
