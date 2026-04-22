from __future__ import annotations

import inspect
import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import probe_odom_world_sign_chain as audit  # noqa: E402


def _quat_from_yaw(yaw_rad: float) -> dict[str, float]:
    half = yaw_rad / 2.0
    return {
        "x": 0.0,
        "y": 0.0,
        "z": math.sin(half),
        "w": math.cos(half),
    }


def _truth_sample(t_s: float, yaw_rad: float) -> dict[str, object]:
    return {
        "t_s": t_s,
        "robot_truth_pose": {
            "name": "jetbot",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": _quat_from_yaw(yaw_rad),
        },
    }


def _truth_samples(*, yaw_step: float = 0.2) -> list[dict[str, object]]:
    return [
        _truth_sample(0.0, 0.0),
        _truth_sample(1.0, yaw_step),
        _truth_sample(2.0, 2.0 * yaw_step),
        _truth_sample(3.0, 3.0 * yaw_step),
        _truth_sample(4.0, 4.0 * yaw_step),
    ]


def _runtime_probe_world_truth_payload(
    sign: int | None,
    *,
    source_session_id: str = "probe_session",
) -> dict[str, object]:
    if sign is None:
        return {}
    return {
        "world_truth": {
            "sample_count": 18,
            "nonzero_step_count": 12 if sign != 0 else 0,
            "net_yaw_change_rad": float(sign),
            "absolute_yaw_change_rad": abs(1.4 * float(sign)),
            "first_nonzero_sign": int(sign),
            "last_nonzero_sign": int(sign),
            "dominant_yaw_sign": int(sign),
            "window_start_t_s": 0.0,
            "window_end_t_s": 4.0,
            "source_session_id": source_session_id,
        }
    }


def _runtime_probe_payload_for_bundle(
    *,
    model_sign: int,
    odom_sign: int,
    controller_odom_sign: int,
    runtime_world_sign: int | None,
    source_session_id: str = "probe_session",
) -> dict[str, object]:
    def _cmd_payload(topic: str, dominant_sign: int) -> dict[str, object]:
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

    def _odom_payload(topic: str, dominant_sign: int) -> dict[str, object]:
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
            "end_yaw_rad": 0.6,
        }

    payload: dict[str, object] = {
        "probe_type": "odom_world_sign_chain_runtime_probe",
        "cmd_vel_topics": {
            "/jetbot_base_controller/cmd_vel": _cmd_payload("/jetbot_base_controller/cmd_vel", 1),
            "/cmd_vel": _cmd_payload("/cmd_vel", 1),
            "/cmd_vel_nav": _cmd_payload("/cmd_vel_nav", 1),
        },
        "odom_topics": {
            "/model/jetbot/odometry": _odom_payload("/model/jetbot/odometry", model_sign),
            "/odom": _odom_payload("/odom", odom_sign),
            "/jetbot_base_controller/odom": _odom_payload(
                "/jetbot_base_controller/odom",
                controller_odom_sign,
            ),
        },
    }
    payload.update(
        _runtime_probe_world_truth_payload(
            runtime_world_sign,
            source_session_id=source_session_id,
        )
    )
    return payload


def _select_world_truth_metrics(
    *,
    truth_samples: list[dict[str, object]],
    runtime_probe_payload: dict[str, object],
    expected_session_id: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "truth_samples": truth_samples,
        "runtime_probe_payload": runtime_probe_payload,
        "start_t_s": 0.0,
        "end_t_s": 4.0,
    }
    signature = inspect.signature(audit.select_world_truth_metrics)
    if expected_session_id is not None:
        preferred_session_names = (
            "expected_source_session_id",
            "expected_session_id",
            "probe_session_id",
            "source_session_id",
            "session_id",
        )
        matched_name = next(
            (name for name in preferred_session_names if name in signature.parameters),
            None,
        )
        if matched_name is None:
            matched_name = next(
                (
                    name
                    for name in signature.parameters
                    if "session" in name.lower() and name not in kwargs
                ),
                None,
            )
        if matched_name is not None:
            kwargs[matched_name] = expected_session_id
    return audit.select_world_truth_metrics(**kwargs)


@pytest.mark.parametrize(
    ("runtime_probe_payload", "expected_source", "expected_reason", "expected_sign"),
    [
        (
            _runtime_probe_world_truth_payload(-1, source_session_id="probe_session"),
            "runtime_probe.world_truth",
            "runtime_probe_world_truth_usable",
            -1,
        ),
        (
            _runtime_probe_world_truth_payload(0, source_session_id="probe_session"),
            "truth_timeline",
            "runtime_probe_world_truth_zero_sign",
            1,
        ),
        (
            {},
            "truth_timeline",
            "runtime_probe_world_truth_missing",
            1,
        ),
    ],
)
def test_select_world_truth_metrics_handles_existing_runtime_probe_availability_cases(
    runtime_probe_payload: dict[str, object],
    expected_source: str,
    expected_reason: str,
    expected_sign: int,
):
    selection = _select_world_truth_metrics(
        truth_samples=_truth_samples(),
        runtime_probe_payload=runtime_probe_payload,
        expected_session_id="probe_session",
    )

    assert selection["selected_source"] == expected_source
    assert selection["selection_reason"] == expected_reason
    assert selection["selected_metrics"]["dominant_yaw_sign"] == expected_sign


def test_select_world_truth_metrics_falls_back_to_truth_timeline_on_session_mismatch():
    selection = _select_world_truth_metrics(
        truth_samples=_truth_samples(),
        runtime_probe_payload=_runtime_probe_world_truth_payload(
            -1,
            source_session_id="stale_probe_session",
        ),
        expected_session_id="probe_session",
    )

    assert selection["selected_source"] == "truth_timeline"
    assert selection["selection_reason"] == "runtime_probe_world_truth_session_mismatch"
    assert selection["selected_metrics"]["dominant_yaw_sign"] == 1


def test_build_bundle_falls_back_to_truth_timeline_on_runtime_probe_session_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    state_history_path = tmp_path / "state_history.jsonl"
    truth_timeline_path = tmp_path / "truth_timeline.json"
    timeline_path = tmp_path / "timeline.json"
    timeline_events_path = tmp_path / "timeline_events.jsonl"
    runtime_probe_json_path = tmp_path / "runtime_probe.json"
    campaign_summary_path = tmp_path / "campaign_summary.json"

    state_history_path.write_text("", encoding="utf-8")
    truth_timeline_path.write_text(json.dumps(_truth_samples(), indent=2), encoding="utf-8")
    timeline_path.write_text(
        json.dumps(
            {
                "samples": [{"t_s": item["t_s"]} for item in _truth_samples()],
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
    timeline_events_path.write_text("", encoding="utf-8")
    runtime_probe_json_path.write_text(
        json.dumps(
            _runtime_probe_payload_for_bundle(
                model_sign=1,
                odom_sign=-1,
                controller_odom_sign=-1,
                runtime_world_sign=-1,
                source_session_id="stale_probe_session",
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    campaign_summary_path.write_text(
        json.dumps(
            {
                "campaign_id": "probe_campaign",
                "runs": [{"run_index": 0, "session_id": "probe_session"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        audit,
        "load_source_audit_bundle",
        lambda **_: (
            {
                "campaign_id": "source_audit",
                "source_campaign_id": "source_campaign",
                "representative_fixture_count": 0,
                "root_cause_gate": {
                    "dominant_diagnosis": "odom_world_sign_divergent",
                    "odom_world_sign_divergent_fixture_count": 0,
                },
                "next_action": {},
            },
            {},
        ),
    )

    def _resolve_run_artifact_paths(_: Path, *, run_index: int) -> dict[str, object]:
        return {
            "campaign_id": "probe_campaign",
            "selected_run_index": run_index,
            "session_id": "probe_session",
            "mission_root": str(tmp_path / "mission_root"),
            "visual_root": str(tmp_path / "visual_root"),
            "state_history_path": str(state_history_path),
            "truth_timeline_path": str(truth_timeline_path),
            "timeline_path": str(timeline_path),
            "timeline_events_path": str(timeline_events_path),
            "campaign_summary": {
                "requested_world_file": "world.sdf",
                "requested_surface_profile": "short_turf",
                "requested_target_layout_json": "layout.json",
                "execution_mode": "direct",
            },
            "run_summary": {
                "run_index": run_index,
                "session_id": "probe_session",
                "mission_root": str(tmp_path / "mission_root"),
            },
        }

    monkeypatch.setattr(audit.divergence, "resolve_run_artifact_paths", _resolve_run_artifact_paths)
    monkeypatch.setattr(audit.oracle, "load_pre_stage_attempt_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        audit,
        "extract_requested_command_metrics",
        lambda *_args, **_kwargs: {
            "sample_count": 4,
            "peak_requested_angular_z_radps": 0.45,
            "net_requested_angular_integral_rad": 1.2,
            "dominant_command_sign": 1,
            "first_nonzero_command_sign": 1,
            "last_nonzero_command_sign": 1,
            "window_start_t_s": 0.0,
            "window_end_t_s": 4.0,
            "window_scope": "attempt_window",
        },
    )
    monkeypatch.setattr(
        audit,
        "build_fresh_fixture_local_command_payloads",
        lambda *_args, **_kwargs: {},
    )

    summary, fixture_payloads = audit.build_odom_world_sign_chain_bundle(
        campaign_id="probe_odom_world_sign_chain_session_binding",
        campaign_summary_path=campaign_summary_path,
        runtime_probe_json_path=runtime_probe_json_path,
        source_audit_summary_path=tmp_path / "source_audit_summary.json",
        source_campaign_summary_path=campaign_summary_path,
    )

    assert fixture_payloads == {}
    assert summary["probe_session_id"] == "probe_session"
    assert summary["world_truth_source"] == "truth_timeline"
    assert summary["world_truth_source_reason"] == "runtime_probe_world_truth_session_mismatch"
    assert summary["world_truth_metrics"]["dominant_yaw_sign"] == 1
    assert summary["timeline_world_truth_metrics"]["dominant_yaw_sign"] == 1
    assert summary["runtime_classification"]["diagnosis"] == "odom_publication_chain_divergent"
