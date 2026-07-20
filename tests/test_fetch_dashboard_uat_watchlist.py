from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_dashboard_uat_watchlist as watchlist  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "watchlist",
        "dashboard_plan": str(tmp_path / "runtime" / "dashboard" / "fetch_plan_data.json"),
        "min_per_route": 1,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write(path: Path, content: bytes = b"x" * 20) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sample(route: str, index: int, *, interpretation: str = "") -> dict:
    session = f"{route}_{index}"
    prefix = f"/artifacts/session/{session}"
    if not interpretation:
        interpretation = "planner-only abstention" if route in watchlist.PLANNER_ONLY_ROUTES else "delivery pass"
    return {
        "label": f"{route}_{index}",
        "route": route,
        "session_id": session,
        "video_url": f"{prefix}/visual/raw_camera_browser.mp4",
        "topdown_url": f"{prefix}/visual/topdown_telemetry_browser.mp4",
        "world_url": f"{prefix}/visual/world_stream.mp4",
        "contact_sheet_url": f"{prefix}/visual/keyframe_review_contact_sheet.png",
        "scorecard_url": f"{prefix}/fetch_visual_uat_package/scorecard.md",
        "interpretation": interpretation,
    }


def _dashboard(tmp_path: Path, samples: list[dict]) -> Path:
    for sample in samples:
        session = sample["session_id"]
        for rel in (
            "visual/raw_camera_browser.mp4",
            "visual/topdown_telemetry_browser.mp4",
            "visual/world_stream.mp4",
            "visual/keyframe_review_contact_sheet.png",
            "fetch_visual_uat_package/scorecard.md",
        ):
            _write(tmp_path / "artifacts" / "session" / session / rel)
    payload = {
        "uat_review_bundle": {
            "title": "Seed 20260648 mixed all-routes video bundle",
            "route_samples": samples,
        }
    }
    path = tmp_path / "runtime" / "dashboard" / "fetch_plan_data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(watchlist.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _green_samples() -> list[dict]:
    return [_sample(route, 1) for route in watchlist.ROUTE_ORDER]


def test_uat_watchlist_scores_green_bundle(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(watchlist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(watchlist, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _dashboard(tmp_path, _green_samples())

    summary = watchlist.build_summary(_args(tmp_path))

    assert summary["pass"] is True
    assert summary["sample_count"] == 5
    assert summary["route_counts"]["fetch_ready_local"] == 1
    assert summary["recommended_watchlist"][0]["route"] == "ambiguous_or_unsafe_no_go"
    assert summary["recommended_watchlist"][-1]["route"] == "fetch_ready_local"
    assert summary["recommended_watchlist"][0]["contract"] == "planner_only_abstention"
    assert summary["recommended_watchlist"][-1]["contract"] == "delivery_pass"


def test_uat_watchlist_fails_when_route_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(watchlist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(watchlist, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _dashboard(tmp_path, [row for row in _green_samples() if row["route"] != "scan_or_perceive_first"])

    summary = watchlist.build_summary(_args(tmp_path))

    assert summary["pass"] is False
    assert "scan_or_perceive_first_below_1" in summary["issues"]


def test_uat_watchlist_fails_when_route_interpretation_is_wrong(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(watchlist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(watchlist, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    samples = _green_samples()
    samples[0]["interpretation"] = "delivery pass"
    _dashboard(tmp_path, samples)

    summary = watchlist.build_summary(_args(tmp_path))

    assert summary["pass"] is False
    assert any("planner_only_interpretation_missing" in issue for issue in summary["issues"])


def test_uat_watchlist_scorecard_lists_onboard_and_keyframes(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(watchlist, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(watchlist, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    _dashboard(tmp_path, _green_samples())
    summary = watchlist.build_summary(_args(tmp_path))
    scorecard = tmp_path / "scorecard.md"

    watchlist.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Dashboard UAT Watchlist" in text
    assert "raw_camera_browser.mp4" in text
    assert "keyframe_review_contact_sheet.png" in text
