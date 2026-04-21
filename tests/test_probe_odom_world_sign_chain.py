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
import probe_odom_world_sign_chain as audit  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
GOAL_SIDE_ONLY_LOCAL = {"x": 0.023141687334822705, "y": 1.3629109105513886, "yaw": -0.8439014238462192}
REPRESENTATIVE_FIXTURE_LABELS = (
    "first_post_yaw_gate",
    "early_stall",
    "mid_stall",
    "late_stall",
    "terminal_stall",
)


def _quat_from_yaw(yaw_rad: float) -> dict[str, float]:
    half = yaw_rad / 2.0
    return {"x": 0.0, "y": 0.0, "z": math.sin(half), "w": math.cos(half)}


def _world_pose_from_local(local_pose: dict[str, float], ball_pose: dict[str, float] | None = None) -> dict[str, float]:
    world_pose = sandbox.local_pose_to_world(local_pose, ball_pose or BALL_POSE, zone=ZONE)
    assert world_pose is not None
    return world_pose


def _state_row(index: int, local_pose: dict[str, float], *, angular_z: float = 0.45) -> dict[str, object]:
    return {
        "generated_utc": f"2026-04-20T12:00:{index:02d}+00:00",
        "phase": "pre_stage",
        "attempt": 0,
        "fixture_index": index,
        "robot_pose": _world_pose_from_local(local_pose),
        "ball_pose": dict(BALL_POSE),
        "selected_command": {
            "angular_z": angular_z,
            "linear_x": -0.18,
            "mode": "pre_stage_escape_goal_side",
        },
    }


def _truth_sample(t_s: float, local_pose: dict[str, float]) -> dict[str, object]:
    robot_world = _world_pose_from_local(local_pose)
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
                "x": BALL_POSE["x"],
                "y": BALL_POSE["y"],
                "z": BALL_POSE["z"],
            },
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def _write_state_history(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def _source_audit_bundle(root: Path) -> tuple[Path, Path]:
    audit_root = root / "artifacts" / "session" / "source_audit" / "gather_manual_drive_sign_parity_audit"
    fixtures_root = audit_root / "fixtures"
    fixtures_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "campaign_id": "source_audit",
        "source_campaign_id": "live_plus45_short_horizon_v2_20260419",
        "representative_fixture_count": 5,
        "root_cause_gate": {
            "dominant_diagnosis": "odom_world_sign_divergent",
            "odom_world_sign_divergent_fixture_count": 4,
        },
        "next_action": {
            "decision": "probe_odom_world_sign_chain",
            "live_probe_required": True,
        },
    }
    summary_path = audit_root / "manual_drive_sign_parity_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for index, fixture_label in enumerate(REPRESENTATIVE_FIXTURE_LABELS):
        fixture_diagnosis = "odom_world_sign_divergent" if fixture_label != "first_post_yaw_gate" else "command_to_odom_sign_divergent"
        payload = {
            "fixture_label": fixture_label,
            "fixture_index": index,
            "fixture_diagnosis": fixture_diagnosis,
            "command_sign": 1,
            "sign_matches": {
                "command_to_odom_sign_match": fixture_diagnosis != "command_to_odom_sign_divergent",
                "command_to_world_sign_match": False,
                "odom_to_world_sign_match": fixture_diagnosis != "odom_world_sign_divergent",
            },
        }
        (fixtures_root / f"{fixture_label}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return summary_path, audit_root


def _probe_campaign_summary(root: Path) -> Path:
    session_id = "probe_session"
    mission_root = root / "artifacts" / "session" / session_id / "gather_mission" / "20260420T120010Z"
    visual_root = root / "artifacts" / "session" / session_id / "visual"
    mission_root.mkdir(parents=True, exist_ok=True)
    visual_root.mkdir(parents=True, exist_ok=True)
    state_rows = [
        _state_row(0, GOAL_SIDE_ONLY_LOCAL, angular_z=0.45),
        _state_row(1, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.15}, angular_z=0.45),
        _state_row(2, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.30}, angular_z=0.45),
        _state_row(3, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.45}, angular_z=0.45),
        _state_row(4, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.04, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.60}, angular_z=0.45),
    ]
    _write_state_history(mission_root / "state_history.jsonl", state_rows)
    truth_samples = [
        _truth_sample(0.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(1.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.15}),
        _truth_sample(2.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.30}),
        _truth_sample(3.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.45}),
        _truth_sample(4.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"], "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.04, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.60}),
    ]
    (visual_root / "truth_timeline.json").write_text(json.dumps(truth_samples, indent=2), encoding="utf-8")
    (visual_root / "timeline.json").write_text(
        json.dumps(
            {
                "samples": [{"t_s": item["t_s"]} for item in truth_samples],
                "events": [
                    {
                        "event_type": "feedback_observed",
                        "timestamp_utc": "2026-04-20T12:00:00+00:00",
                        "t_s": 0.0,
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (visual_root / "timeline_events.jsonl").write_text("", encoding="utf-8")
    (mission_root / "mission_verdict.json").write_text(json.dumps({"pre_stage_handoff_pass": False}, indent=2), encoding="utf-8")
    (mission_root / "gather_sequence.jsonl").write_text(
        json.dumps({"event_type": "pre_stage_result", "status": "pre_stage_timeout"}) + "\n",
        encoding="utf-8",
    )
    campaign_summary = {
        "campaign_id": "probe_campaign",
        "requested_world_file": "yolo_test_world_v6_clean_uat_short_turf.world",
        "requested_surface_profile": "short_turf",
        "requested_target_layout_json": "artifacts/session/plus45.json",
        "execution_mode": "direct",
        "runs": [
            {
                "run_index": 0,
                "session_id": session_id,
                "mission_root": str(mission_root),
            }
        ],
    }
    campaign_summary_path = root / "probe_campaign_run_summary.json"
    campaign_summary_path.write_text(json.dumps(campaign_summary, indent=2), encoding="utf-8")
    return campaign_summary_path


def _runtime_probe_payload(
    *,
    model_sign: int,
    odom_sign: int,
    controller_odom_sign: int,
    world_like_sign: int = 1,
    runtime_world_sign: int | None = None,
) -> dict[str, object]:
    def cmd_payload(topic: str, dominant_sign: int) -> dict[str, object]:
        return {
            "topic": topic,
            "message_count": 12,
            "nonzero_message_count": 12,
            "peak_abs_angular_z_radps": 0.45,
            "net_angular_integral_rad": 1.2 * dominant_sign,
            "first_nonzero_sign": dominant_sign,
            "last_nonzero_sign": dominant_sign,
            "dominant_angular_sign": dominant_sign,
        }

    def odom_payload(topic: str, dominant_sign: int) -> dict[str, object]:
        return {
            "topic": topic,
            "message_count": 18,
            "nonzero_step_count": 12,
            "peak_abs_yaw_step_rad": 0.14,
            "net_yaw_change_rad": 1.0 * dominant_sign,
            "cumulative_abs_yaw_change_rad": 1.4,
            "first_nonzero_sign": dominant_sign,
            "last_nonzero_sign": dominant_sign,
            "dominant_yaw_sign": dominant_sign,
            "start_yaw_rad": 0.0,
            "end_yaw_rad": 0.6 * world_like_sign,
        }

    payload: dict[str, object] = {
        "probe_type": "odom_world_sign_chain_runtime_probe",
        "cmd_vel_topics": {
            "/jetbot_base_controller/cmd_vel": cmd_payload("/jetbot_base_controller/cmd_vel", 1),
            "/cmd_vel": cmd_payload("/cmd_vel", 1),
            "/cmd_vel_nav": cmd_payload("/cmd_vel_nav", 1),
        },
        "odom_topics": {
            "/model/jetbot/odometry": odom_payload("/model/jetbot/odometry", model_sign),
            "/odom": odom_payload("/odom", odom_sign),
            "/jetbot_base_controller/odom": odom_payload("/jetbot_base_controller/odom", controller_odom_sign),
        },
    }
    if runtime_world_sign is not None:
        payload["world_truth"] = {
            "sample_count": 18,
            "nonzero_step_count": 12 if runtime_world_sign != 0 else 0,
            "net_yaw_change_rad": 1.0 * runtime_world_sign,
            "absolute_yaw_change_rad": abs(1.4 * runtime_world_sign),
            "first_nonzero_sign": runtime_world_sign,
            "last_nonzero_sign": runtime_world_sign,
            "dominant_yaw_sign": runtime_world_sign,
            "window_start_t_s": 0.0,
            "window_end_t_s": 4.0,
        }
    return payload


def test_classify_runtime_sign_chain_marks_odom_publication_chain_divergent():
    payload = audit.classify_runtime_sign_chain(
        requested_command_metrics={"dominant_command_sign": 1},
        world_truth_metrics={"dominant_yaw_sign": 1},
        runtime_probe_payload=_runtime_probe_payload(model_sign=1, odom_sign=-1, controller_odom_sign=-1),
        source_root_cause_gate={"dominant_diagnosis": "odom_world_sign_divergent"},
    )

    assert payload["diagnosis"] == "odom_publication_chain_divergent"
    assert payload["decision"] == "inspect_odom_publication_chain"
    assert payload["supports_source_odom_world_hypothesis"] is True


def test_classify_runtime_sign_chain_marks_sign_chain_aligned():
    payload = audit.classify_runtime_sign_chain(
        requested_command_metrics={"dominant_command_sign": 1},
        world_truth_metrics={"dominant_yaw_sign": 1},
        runtime_probe_payload=_runtime_probe_payload(model_sign=1, odom_sign=1, controller_odom_sign=1),
        source_root_cause_gate={"dominant_diagnosis": "odom_world_sign_divergent"},
    )

    assert payload["diagnosis"] == "sign_chain_aligned"
    assert payload["decision"] == "revisit_source_alignment"
    assert payload["supports_source_odom_world_hypothesis"] is False


def test_build_and_write_probe_odom_world_sign_chain_bundle(tmp_path: Path):
    source_summary_path, _ = _source_audit_bundle(tmp_path)
    probe_campaign_summary_path = _probe_campaign_summary(tmp_path)
    runtime_probe_json_path = tmp_path / "runtime_probe.json"
    runtime_probe_json_path.write_text(
        json.dumps(_runtime_probe_payload(model_sign=1, odom_sign=-1, controller_odom_sign=-1), indent=2),
        encoding="utf-8",
    )

    summary, fixture_payloads = audit.build_odom_world_sign_chain_bundle(
        campaign_id="temp_probe_odom_world_sign_chain",
        campaign_summary_path=probe_campaign_summary_path,
        runtime_probe_json_path=runtime_probe_json_path,
        source_audit_summary_path=source_summary_path,
        source_campaign_summary_path=probe_campaign_summary_path,
    )
    output_paths = audit.write_odom_world_sign_chain_bundle(
        campaign_id="temp_probe_odom_world_sign_chain",
        summary=summary,
        fixture_payloads=fixture_payloads,
        repo_root=tmp_path,
        runtime_probe_json_path=runtime_probe_json_path,
    )

    assert summary["type"] == "probe_odom_world_sign_chain"
    assert summary["relevant_source_fixture_count"] == 4
    assert summary["runtime_supported_source_fixture_count"] == 4
    assert summary["runtime_classification"]["diagnosis"] == "odom_publication_chain_divergent"
    assert output_paths["summary_path"].exists()
    assert output_paths["scorecard_path"].exists()
    assert output_paths["runtime_probe_json_path"].exists()
    scorecard_text = output_paths["scorecard_path"].read_text(encoding="utf-8")
    assert "- World truth source: `truth_timeline`" in scorecard_text
    assert "- Timeline cross-check sign: `1`" in scorecard_text
    assert "- Runtime probe world truth sign: `0`" in scorecard_text
    for fixture_label in REPRESENTATIVE_FIXTURE_LABELS:
        assert (output_paths["fixtures_root"] / f"{fixture_label}.json").exists()


def test_build_bundle_prefers_runtime_probe_world_truth_when_nonzero(tmp_path: Path):
    source_summary_path, _ = _source_audit_bundle(tmp_path)
    probe_campaign_summary_path = _probe_campaign_summary(tmp_path)
    runtime_probe_json_path = tmp_path / "runtime_probe.json"
    runtime_probe_json_path.write_text(
        json.dumps(
            _runtime_probe_payload(
                model_sign=1,
                odom_sign=-1,
                controller_odom_sign=-1,
                runtime_world_sign=-1,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    summary, _ = audit.build_odom_world_sign_chain_bundle(
        campaign_id="temp_probe_odom_world_sign_chain_runtime_truth",
        campaign_summary_path=probe_campaign_summary_path,
        runtime_probe_json_path=runtime_probe_json_path,
        source_audit_summary_path=source_summary_path,
        source_campaign_summary_path=probe_campaign_summary_path,
    )

    assert summary["world_truth_source"] == "runtime_probe.world_truth"
    assert summary["world_truth_source_reason"] == "runtime_probe_world_truth_usable"
    assert summary["world_truth_metrics"]["dominant_yaw_sign"] == -1
    assert summary["timeline_world_truth_metrics"]["dominant_yaw_sign"] == 1
    assert summary["runtime_probe_world_truth_metrics"]["dominant_yaw_sign"] == -1
    assert summary["world_truth_cross_check"]["timeline_matches_selected"] is False
    assert summary["runtime_classification"]["diagnosis"] == "model_odom_vs_world_divergent"


def test_build_bundle_falls_back_to_truth_timeline_when_runtime_probe_world_truth_zero_sign(tmp_path: Path):
    source_summary_path, _ = _source_audit_bundle(tmp_path)
    probe_campaign_summary_path = _probe_campaign_summary(tmp_path)
    runtime_probe_json_path = tmp_path / "runtime_probe.json"
    runtime_probe_json_path.write_text(
        json.dumps(
            _runtime_probe_payload(
                model_sign=1,
                odom_sign=-1,
                controller_odom_sign=-1,
                runtime_world_sign=0,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    summary, _ = audit.build_odom_world_sign_chain_bundle(
        campaign_id="temp_probe_odom_world_sign_chain_timeline_fallback",
        campaign_summary_path=probe_campaign_summary_path,
        runtime_probe_json_path=runtime_probe_json_path,
        source_audit_summary_path=source_summary_path,
        source_campaign_summary_path=probe_campaign_summary_path,
    )

    assert summary["world_truth_source"] == "truth_timeline"
    assert summary["world_truth_source_reason"] == "runtime_probe_world_truth_zero_sign"
    assert summary["world_truth_metrics"]["dominant_yaw_sign"] == 1
    assert summary["timeline_world_truth_metrics"]["dominant_yaw_sign"] == 1
    assert summary["runtime_probe_world_truth_metrics"]["dominant_yaw_sign"] == 0
    assert summary["world_truth_cross_check"]["runtime_probe_matches_selected"] is None
    assert summary["runtime_classification"]["diagnosis"] == "odom_publication_chain_divergent"


def test_build_bundle_tracks_non_reproduction_when_runtime_chain_is_aligned(tmp_path: Path):
    source_summary_path, _ = _source_audit_bundle(tmp_path)
    probe_campaign_summary_path = _probe_campaign_summary(tmp_path)
    runtime_probe_json_path = tmp_path / "runtime_probe.json"
    runtime_probe_json_path.write_text(
        json.dumps(_runtime_probe_payload(model_sign=1, odom_sign=1, controller_odom_sign=1), indent=2),
        encoding="utf-8",
    )

    summary, _ = audit.build_odom_world_sign_chain_bundle(
        campaign_id="temp_probe_odom_world_sign_chain_aligned",
        campaign_summary_path=probe_campaign_summary_path,
        runtime_probe_json_path=runtime_probe_json_path,
        source_audit_summary_path=source_summary_path,
        source_campaign_summary_path=probe_campaign_summary_path,
    )

    assert summary["runtime_classification"]["diagnosis"] == "sign_chain_aligned"
    assert summary["next_action"]["decision"] == "revisit_source_alignment"
    assert summary["runtime_supported_source_fixture_count"] == 0
    assert summary["world_truth_source"] == "truth_timeline"
    assert summary["world_truth_source_reason"] == "runtime_probe_world_truth_missing"
    assert summary["runtime_probe_world_truth_metrics"] == {}
