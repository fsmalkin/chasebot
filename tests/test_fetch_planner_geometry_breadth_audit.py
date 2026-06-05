from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_geometry_breadth_audit as audit  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(audit.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _result(route: str, flag: str, *, index: int, total: int) -> dict:
    ratio = index / max(total - 1, 1)
    return {
        "route_label": route,
        "route_quality": {
            "flags": [flag],
            "setup_debt": {
                "ball_target_distance_m": 0.45 + 1.4 * ratio,
                "ball_target_angle_abs_deg": 0.1 + 40.0 * ratio,
                "lateral_m": 0.001 + 0.2 * ratio,
                "robot_ball_distance_m": 0.29 + 1.0 * ratio,
                "yaw_deg": 0.1 + 30.0 * ratio,
            },
        },
    }


def _gate(tmp_path: Path, seed: int, *, omit_route: str = "", omit_flag: str = "", narrow: bool = False) -> Path:
    routes = list(audit.ROUTE_LABELS)
    flags = list(audit.REQUIRED_FLAGS)
    if omit_route:
        routes = [route for route in routes if route != omit_route]
    if omit_flag:
        flags = [flag for flag in flags if flag != omit_flag]
    results = []
    total = 100
    for index in range(total):
        route = routes[index % len(routes)]
        flag = flags[index % len(flags)]
        result = _result(route, flag, index=index, total=total)
        if narrow:
            result["route_quality"]["setup_debt"]["ball_target_angle_abs_deg"] = 2.0
        results.append(result)
    return _write_json(
        tmp_path / f"seed{seed}" / "planner_gate.json",
        {
            "pass": True,
            "seed": seed,
            "results": results,
            "provider_status_counts": {"skipped_missing_openai_api_key": total},
            "planner_mode_effective_counts": {"deterministic_fallback": total},
            "scorecard_path": f"artifacts/session/seed{seed}/scorecard.md",
        },
    )


def _args(paths: list[Path], **overrides):
    payload = {
        "campaign_id": "geometry",
        "gate_summary": [str(path) for path in paths],
        "min_scenes": 100,
        "min_ball_target_distance_span_m": 1.0,
        "min_ball_target_angle_span_deg": 30.0,
        "min_lateral_span_m": 0.15,
        "min_robot_ball_distance_span_m": 0.8,
        "min_yaw_span_deg": 20.0,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_geometry_breadth_audit_scores_green_varied_gate(tmp_path: Path):
    summary = audit.build_summary(_args([_gate(tmp_path, 20260650)]))

    assert summary["pass"] is True
    assert summary["scene_count"] == 100
    assert set(summary["route_counts"]) == set(audit.ROUTE_LABELS)
    assert summary["ranges"]["ball_target_distance_m"]["count"] == 100
    assert summary["ranges"]["ball_target_distance_m"]["span"] >= 1.0
    assert summary["ranges"]["yaw_deg"]["span"] >= 20.0
    assert summary["provider_backed_authority_ready"] is False


def test_geometry_breadth_audit_fails_when_route_family_missing(tmp_path: Path):
    summary = audit.build_summary(_args([_gate(tmp_path, 20260650, omit_route="scan_or_perceive_first")]))

    assert summary["pass"] is False
    assert "missing_route_family:scan_or_perceive_first" in summary["issues"]


def test_geometry_breadth_audit_fails_when_setup_flag_missing(tmp_path: Path):
    summary = audit.build_summary(_args([_gate(tmp_path, 20260650, omit_flag="perception_refresh_required")]))

    assert summary["pass"] is False
    assert "missing_setup_flag:perception_refresh_required" in summary["issues"]


def test_geometry_breadth_audit_fails_when_angle_span_too_narrow(tmp_path: Path):
    summary = audit.build_summary(_args([_gate(tmp_path, 20260650, narrow=True)]))

    assert summary["pass"] is False
    assert "ball_target_angle_abs_deg_span_below_30.0" in summary["issues"]


def test_geometry_breadth_scorecard_lists_ranges(tmp_path: Path):
    summary = audit.build_summary(_args([_gate(tmp_path, 20260650)]))
    scorecard = tmp_path / "scorecard.md"

    audit.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Planner Geometry Breadth Audit" in text
    assert "ball_target_distance_m" in text
    assert "geometry_breadth_not_promotion_evidence" in text
