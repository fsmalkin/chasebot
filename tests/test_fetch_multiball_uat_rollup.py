import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_multiball_uat_rollup as rollup  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(rollup, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(rollup, "SESSION_ROOT", tmp_path / "artifacts" / "session")


def _sequence_plan(tmp_path: Path, campaign: str, scene_id: str, balls: list[str], *, retry_step: int = 0) -> str:
    sequence = []
    for index, ball_id in enumerate(balls, start=1):
        attempts = [{"attempt": 1, "status": "ok"}]
        if index == retry_step:
            attempts = [{"attempt": 1, "status": "error"}, {"attempt": 2, "status": "ok"}]
        sequence.append(
            {
                "ball_id": ball_id,
                "decision": {
                    "confidence": 0.94,
                    "guard_agrees": True,
                    "guard_route_label": "local_setup_capture",
                    "llm_confidence": 0.94,
                    "llm_route_label": "local_setup_capture",
                    "llm_rationale_short": "Use measured local setup/capture, validate push-ready, then fetch.",
                    "llm_supervised_guard": {
                        "accepted": True,
                        "decision": "accepted",
                        "guard_route_label": "local_setup_capture",
                        "llm_confidence": 0.94,
                        "llm_route_label": "local_setup_capture",
                        "provider_status": "ok",
                    },
                    "planner_mode": "llm_supervised_guarded",
                    "planner_mode_effective": "llm_supervised_guarded",
                    "provider_attempts": attempts,
                    "provider_error": "",
                },
            }
        )
    path = tmp_path / "artifacts" / "session" / campaign / "fetch_multiball_retrieval_gate" / "sequence_plans" / f"{scene_id}.json"
    _write_json(
        path,
        {
            "scene_id": scene_id,
            "planner_mode": "llm_supervised_guarded",
            "planner_ready": True,
            "retrieval_order": balls,
            "sequence": sequence,
        },
    )
    return rollup.artifact_display_path(path)


def _gate_summary(
    tmp_path: Path,
    campaign: str,
    scene_id: str,
    balls: list[str],
    *,
    hidden_nav2_step: int = 0,
    retry_step: int = 0,
) -> Path:
    plan_path = _sequence_plan(tmp_path, campaign, scene_id, balls, retry_step=retry_step)
    step_rows = []
    for index, ball_id in enumerate(balls, start=1):
        command = ["python", "scripts/golf_ball_circle_delivery_demo_runner.py", "--planner-route-label", "local_setup_capture"]
        if index == hidden_nav2_step:
            command.append("--nav2-reposition-before-fetch")
        step_rows.append(
            {
                "scene_id": scene_id,
                "step_index": index,
                "ball_id": ball_id,
                "route_label": "local_setup_capture",
                "route_executor": "measured_local_setup_capture",
                "layout_path": f"artifacts/session/{campaign}/layout_{index}.json",
                "mission_summary_path": f"artifacts/session/{campaign}/mission_{index}.json",
                "mission": {
                    "closest_approach_distance_m": 0.197 + (index * 0.001),
                    "contact_quality_flags": [],
                    "fetch_to_pose_pass": True,
                    "first_contact_quality_flags": [],
                    "measured_push_ready_handoff_pass": True,
                    "measured_push_ready_handoff_required": True,
                    "outcome_reason": "trajectory_intersects_delivery_radius",
                    "pre_fetch_reposition_attempted": index == hidden_nav2_step,
                },
                "command": command,
            }
        )
    path = tmp_path / "artifacts" / "session" / campaign / "fetch_multiball_retrieval_gate" / "gate_summary.json"
    _write_json(
        path,
        {
            "campaign_id": campaign,
            "dry_run": False,
            "expected_session_id": f"{campaign}_session",
            "multiball_visual_evidence_pass": True,
            "pass": True,
            "planned_step_count": len(balls),
            "planner_mode": "llm_supervised_guarded",
            "profile": "open_field_multiball_v1",
            "scene_count": 1,
            "scene_rows": [
                {
                    "scene_id": scene_id,
                    "pass": True,
                    "ball_count": len(balls),
                    "fetch_to_pose_pass_count": len(balls),
                    "fetch_to_pose_fail_count": 0,
                    "planner_ready": True,
                    "retrieval_order": balls,
                    "sequence_plan_path": plan_path,
                }
            ],
            "step_rows": step_rows,
            "visual_package_effective_pass": True,
            "visual_package_pass": True,
            "visual_package": {
                "mobile_watchable": True,
                "onboard_camera_watchable": True,
                "videos": [
                    {
                        "browser_playable": True,
                        "duration_s": 12.0,
                        "name": "raw_camera_browser.mp4",
                        "path": f"artifacts/session/{campaign}_session/visual/raw_camera_browser.mp4",
                        "role": "onboard_camera",
                        "url": f"/artifacts/session/{campaign}_session/visual/raw_camera_browser.mp4",
                    }
                ],
                "keyframe_reviews": [
                    {
                        "ok": True,
                        "output_name": "keyframe_review_contact_sheet.png",
                        "path": f"artifacts/session/{campaign}_session/visual/keyframe_review_contact_sheet.png",
                        "selected_count": 10,
                        "url": f"/artifacts/session/{campaign}_session/visual/keyframe_review_contact_sheet.png",
                    }
                ],
            },
        },
    )
    return path


def _args(**overrides):
    payload = {
        "campaign_id": "rollup",
        "dashboard_base_url": "http://100.112.221.6:8895",
        "gate_summary": [],
        "min_live_gates": 2,
        "min_scenes": 2,
        "min_steps": 6,
        "min_llm_supervised_gates": 2,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_multiball_rollup_scores_supervised_visual_uat_green(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    gate_a = _gate_summary(tmp_path, "gate_a", "scene_a", ["ball_1", "ball_2", "ball_3"])
    gate_b = _gate_summary(tmp_path, "gate_b", "scene_b", ["ball_2", "ball_1", "ball_3"], retry_step=2)

    summary = rollup.summarize_rollup(_args(gate_summary=[str(gate_a), str(gate_b)]))

    assert summary["pass"] is True
    assert summary["promotion_evidence"] is False
    assert summary["milestone_interpretation"] == "multiball_llm_supervised_visual_uat_green_not_promotion"
    assert summary["live_gate_count"] == 2
    assert summary["llm_supervised_live_gate_count"] == 2
    assert summary["scene_count"] == 2
    assert summary["live_step_count"] == 6
    assert summary["fetch_to_pose_pass_count"] == 6
    assert summary["hidden_nav2_prefetch_count"] == 0
    assert summary["provider_retry_count"] == 1
    assert summary["provider_status_counts"] == {"ok": 6}
    assert summary["stage_label_counts"] == {"complete": 6}
    assert summary["visual_proof"][0]["links"][0]["url"].startswith("http://100.112.221.6:8895/artifacts/session/")


def test_multiball_rollup_flags_hidden_nav2_in_local_setup(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    gate_a = _gate_summary(tmp_path, "gate_a", "scene_a", ["ball_1", "ball_2", "ball_3"], hidden_nav2_step=1)
    gate_b = _gate_summary(tmp_path, "gate_b", "scene_b", ["ball_2", "ball_1", "ball_3"])

    summary = rollup.summarize_rollup(_args(gate_summary=[str(gate_a), str(gate_b)]))

    assert summary["pass"] is False
    assert summary["hidden_nav2_prefetch_count"] == 1
    assert "hidden_nav2_prefetch_in_local_setup" in summary["issues"]
    assert summary["stage_label_counts"]["setup"] == 1
