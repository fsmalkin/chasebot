#!/usr/bin/env python3
"""Run a canonical one-shot geometric-shooter fetch probe in Gazebo."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fetch_geometric_shooter_screen import DEFAULT_DECEL_MPS2
from fetch_geometric_shooter_screen import DEFAULT_MAX_SHOT_SPEED_MPS
from fetch_geometric_shooter_screen import build_geometric_shot_model
from gather_mission_repeatability_runner import ensure_environment_ready
from golf_ball_circle_delivery_demo_runner import build_shot_outcome
from passive_ball_roll_calibration_helpers import parse_ball_sdf_profile
from passive_ball_roll_calibration_runner import DEFAULT_BALL_SDF
from passive_ball_roll_calibration_runner import DEFAULT_DASHBOARD_URL
from passive_ball_roll_calibration_runner import DEFAULT_WORLD_FILE
from passive_ball_roll_calibration_runner import DEFAULT_WORLD_NAME
from passive_ball_roll_calibration_runner import collect_ball_samples
from passive_ball_roll_calibration_runner import dashboard_state
from passive_ball_roll_calibration_runner import discover_compose_project
from passive_ball_roll_calibration_runner import prepare_direct_velocity_ball_model
from passive_ball_roll_calibration_runner import remove_model
from passive_ball_roll_calibration_runner import spawn_model
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
DEFAULT_ZONE_SDF = REPO_ROOT / "ros2_config" / "golf_ball_delivery_zone_marker.sdf"
DEFAULT_TARGET_LAYOUT = REPO_ROOT / "ros2_config" / "target_layouts" / "golf_ball_circle_delivery_zero.json"
OUTPUT_KIND = "fetch_geometric_shooter_probe"
DEFAULT_BALL_MODEL_NAME = "geometric_shooter_ball"
DEFAULT_ZONE_MODEL_NAME = "geometric_shooter_delivery_zone"


def make_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_first_layout_target(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    targets = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"target layout has no targets: {path}")
    first = targets[0]
    if not isinstance(first, dict):
        raise ValueError(f"target layout first target is invalid: {path}")
    return {
        "x": float(first.get("forward_m", 0.0) or 0.0),
        "y": float(first.get("lateral_m", 0.0) or 0.0),
        "z": float(first.get("z_m", 0.021336) or 0.021336),
    }


def shot_heading_deg(*, ball_x: float, ball_y: float, target_x: float, target_y: float) -> float:
    return math.degrees(math.atan2(float(target_y) - float(ball_y), float(target_x) - float(ball_x)))


def select_shot_speed_mps(model: dict[str, Any], *, mode: str) -> float:
    if mode == "entry":
        key = "required_entry_speed_mps"
    elif mode == "far_edge":
        key = "required_far_edge_speed_mps"
    else:
        key = "required_target_center_speed_mps"
    try:
        return float(model[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"geometric model did not produce {key}") from exc


def render_scorecard(summary: dict[str, Any]) -> str:
    verdict = summary.get("mission_verdict", {}) if isinstance(summary.get("mission_verdict"), dict) else {}
    shot = verdict.get("shot_outcome", {}) if isinstance(verdict.get("shot_outcome"), dict) else {}
    model = summary.get("geometric_shooter", {}) if isinstance(summary.get("geometric_shooter"), dict) else {}
    return "\n".join(
        [
            "# Fetch Geometric Shooter Probe",
            "",
            f"- Campaign: `{summary.get('campaign_id', '')}`",
            f"- Layout: `{summary.get('target_layout_json', '')}`",
            f"- Probe status: `{summary.get('probe_status', '')}`",
            f"- Fetch pass: `{verdict.get('fetch_to_pose_pass', False)}`",
            f"- Closest approach: `{shot.get('closest_approach_distance_m')}`",
            f"- Final distance: `{shot.get('distance_to_fetch_pose_m')}`",
            f"- Initial speed: `{summary.get('initial_speed_mps')}`",
            f"- Initial heading: `{summary.get('initial_heading_deg')}`",
            f"- Offline model reason: `{model.get('reason', '')}`",
            "",
            "This is a live canonical probe for a bounded shot impulse. It is not repeatability or promotion evidence.",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a canonical geometric-shooter one-shot fetch probe.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--world-name", default=DEFAULT_WORLD_NAME)
    parser.add_argument("--world-file", default=DEFAULT_WORLD_FILE)
    parser.add_argument("--surface-profile", default="calibrated_golf_turf")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--target-layout-json", type=Path, default=DEFAULT_TARGET_LAYOUT)
    parser.add_argument("--ball-model-sdf", type=Path, default=DEFAULT_BALL_SDF)
    parser.add_argument("--zone-model-sdf", type=Path, default=DEFAULT_ZONE_SDF)
    parser.add_argument("--ball-model-name", default=DEFAULT_BALL_MODEL_NAME)
    parser.add_argument("--zone-model-name", default=DEFAULT_ZONE_MODEL_NAME)
    parser.add_argument("--fetch-target-x", type=float, default=0.95)
    parser.add_argument("--fetch-target-y", type=float, default=0.0)
    parser.add_argument("--fetch-target-z", type=float, default=0.001)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=0.30)
    parser.add_argument("--decel-mps2", type=float, default=DEFAULT_DECEL_MPS2)
    parser.add_argument("--max-shot-speed-mps", type=float, default=DEFAULT_MAX_SHOT_SPEED_MPS)
    parser.add_argument("--speed-mode", choices=("entry", "center", "far_edge"), default="center")
    parser.add_argument("--sample-duration-s", type=float, default=6.0)
    parser.add_argument("--poll-period-s", type=float, default=0.08)
    parser.add_argument("--initial-velocity-link-name", default="link")
    parser.add_argument("--initial-velocity-delay-s", type=float, default=0.0)
    parser.add_argument("--no-rolling-angular-velocity", action="store_true")
    parser.add_argument("--rolling-resistance-decel-mps2", type=float, default=0.0)
    parser.add_argument("--rolling-resistance-stop-speed-threshold-mps", type=float, default=0.03)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--keep-models", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.campaign_id = args.campaign_id or f"live_fetch_geometric_shooter_probe_{make_session_id()}"
    target_layout = args.target_layout_json if args.target_layout_json.is_absolute() else REPO_ROOT / args.target_layout_json
    ball_model_sdf = args.ball_model_sdf if args.ball_model_sdf.is_absolute() else REPO_ROOT / args.ball_model_sdf
    zone_model_sdf = args.zone_model_sdf if args.zone_model_sdf.is_absolute() else REPO_ROOT / args.zone_model_sdf
    ball_start = load_first_layout_target(target_layout)
    fetch_pose = {
        "x": float(args.fetch_target_x),
        "y": float(args.fetch_target_y),
        "z": float(args.fetch_target_z),
        "radius_m": float(args.fetch_delivery_radius_m),
    }
    geometric_model = build_geometric_shot_model(
        ball_start_pose=ball_start,
        fetch_pose_world=fetch_pose,
        decel_mps2=float(args.decel_mps2),
        max_shot_speed_mps=float(args.max_shot_speed_mps),
    )
    requested_speed = min(select_shot_speed_mps(geometric_model, mode=args.speed_mode), float(args.max_shot_speed_mps))
    heading_deg = shot_heading_deg(
        ball_x=ball_start["x"],
        ball_y=ball_start["y"],
        target_x=float(args.fetch_target_x),
        target_y=float(args.fetch_target_y),
    )

    ensure_environment_ready(
        args.dashboard_url,
        timeout_s=float(args.timeout_s),
        startup_payload={
            "world_file": str(args.world_file),
            "surface_profile": str(args.surface_profile),
            "scenario_id": "corral_single_ball_place",
            "mission_objective": "fetch_to_pose",
            "fetch_target_x": float(args.fetch_target_x),
            "fetch_target_y": float(args.fetch_target_y),
            "fetch_target_z": float(args.fetch_target_z),
            "fetch_delivery_radius_m": float(args.fetch_delivery_radius_m),
        },
    )
    state = dashboard_state(args.dashboard_url)
    compose_project = args.compose_project or str(state.get("compose_project", "") or state.get("launcher_project", "") or "")
    if not compose_project:
        compose_project = discover_compose_project(args.dashboard_url)
    if not compose_project:
        raise SystemExit("Unable to discover compose project; pass --compose-project.")

    session_id = str(state.get("session_id", "") or args.campaign_id)
    artifact_dir = ensure_dir(SESSION_ROOT / args.campaign_id / OUTPUT_KIND)
    mission_dir = ensure_dir(artifact_dir / session_id)
    trace_path = mission_dir / "ball_trace.jsonl"
    spawn_log_path = mission_dir / "spawn.json"
    summary_path = artifact_dir / "geometric_shooter_probe_summary.json"
    scorecard_path = artifact_dir / "scorecard.md"

    ball_profile = parse_ball_sdf_profile(ball_model_sdf)
    launch_args = SimpleNamespace(
        compose_project=compose_project,
        initial_speed_mps=requested_speed,
        initial_heading_deg=heading_deg,
        no_rolling_angular_velocity=bool(args.no_rolling_angular_velocity),
        initial_velocity_link_name=args.initial_velocity_link_name,
        initial_velocity_delay_s=float(args.initial_velocity_delay_s),
        rolling_resistance_decel_mps2=float(args.rolling_resistance_decel_mps2),
        rolling_resistance_stop_speed_threshold_mps=float(args.rolling_resistance_stop_speed_threshold_mps),
        ball_model_sdf=str(ball_model_sdf),
    )
    launch_payload = prepare_direct_velocity_ball_model(
        launch_args,
        run_index=1,
        artifact_dir=mission_dir,
        ball_radius_m=float(ball_profile.radius_m),
        ball_mass_kg=float(ball_profile.mass_kg),
    )
    if not bool(launch_payload.get("pass", False)):
        write_json(spawn_log_path, {"launch": launch_payload})
        raise RuntimeError(f"direct-velocity model preparation failed; see {spawn_log_path}")

    remove_model(compose_project=compose_project, world_name=args.world_name, model_name=args.ball_model_name)
    remove_model(compose_project=compose_project, world_name=args.world_name, model_name=args.zone_model_name)
    spawn_zone = spawn_model(
        compose_project=compose_project,
        world_name=args.world_name,
        model_sdf=zone_model_sdf,
        model_name=args.zone_model_name,
        x=float(args.fetch_target_x),
        y=float(args.fetch_target_y),
        z=float(args.fetch_target_z),
        yaw=0.0,
    )
    spawn_ball = spawn_model(
        compose_project=compose_project,
        world_name=args.world_name,
        model_sdf=Path(str(launch_payload["prepared_model_sdf"])),
        model_name=args.ball_model_name,
        x=ball_start["x"],
        y=ball_start["y"],
        z=ball_start["z"],
        yaw=0.0,
        set_pose_after_spawn=False,
    )
    write_json(spawn_log_path, {"zone": spawn_zone, "ball": spawn_ball, "launch": launch_payload})
    if not bool(spawn_zone.get("pass", False) and spawn_ball.get("pass", False)):
        raise RuntimeError(f"spawn failed; see {spawn_log_path}")

    samples = [
        {
            "sample_index": -1,
            "t_s": 0.0,
            "topic_ok": True,
            "model_name": args.ball_model_name,
            "position": {"x": ball_start["x"], "y": ball_start["y"], "z": ball_start["z"]},
            "orientation": {},
            "synthetic_start": True,
        }
    ]
    samples.extend(
        collect_ball_samples(
            compose_project=compose_project,
            world_name=args.world_name,
            ball_model_name=args.ball_model_name,
            duration_s=float(args.sample_duration_s),
            poll_period_s=float(args.poll_period_s),
        )
    )
    append_jsonl(trace_path, samples)

    shot_outcome = build_shot_outcome(
        samples,
        target_x=float(args.fetch_target_x),
        target_y=float(args.fetch_target_y),
        target_z=float(args.fetch_target_z),
        radius_m=float(args.fetch_delivery_radius_m),
    )
    mission_completed = bool(shot_outcome.get("pass", False))
    verdict = {
        "pass": mission_completed,
        "mission_completed_pass": mission_completed,
        "fetch_to_pose_pass": mission_completed,
        "fetch_to_pose_reached": mission_completed,
        "fetch_to_pose_failure_reason": "" if mission_completed else str(shot_outcome.get("reason", "missed_delivery_radius")),
        "mission_objective": "fetch_to_pose",
        "shot_outcome": shot_outcome,
    }
    write_json(mission_dir / "mission_verdict.json", verdict)
    write_json(mission_dir / "target_results.json", {"targets": [{"target_id": "ball_1", **verdict}]})

    summary = {
        "campaign_id": args.campaign_id,
        "generated_utc": utc_now(),
        "type": OUTPUT_KIND,
        "architecture_family": "contact_aware_geometric_shooter",
        "probe_status": "canonical_zero_one_run_probe",
        "promotion_allowed": False,
        "world_file": str(args.world_file),
        "surface_profile": str(args.surface_profile),
        "target_layout_json": str(target_layout.relative_to(REPO_ROOT) if target_layout.is_relative_to(REPO_ROOT) else target_layout),
        "compose_project": compose_project,
        "session_id": session_id,
        "artifact_dir": str(mission_dir),
        "ball_trace_path": str(trace_path),
        "initial_speed_mps": round(float(requested_speed), 6),
        "initial_heading_deg": round(float(heading_deg), 6),
        "speed_mode": str(args.speed_mode),
        "geometric_shooter": geometric_model,
        "spawn": {"zone": spawn_zone, "ball": spawn_ball, "launch": launch_payload},
        "mission_verdict": verdict,
    }
    write_json(summary_path, summary)
    scorecard_path.write_text(render_scorecard(summary), encoding="utf-8")

    if not bool(args.keep_models):
        remove_model(compose_project=compose_project, world_name=args.world_name, model_name=args.ball_model_name)
        remove_model(compose_project=compose_project, world_name=args.world_name, model_name=args.zone_model_name)

    print(f"FETCH_GEOMETRIC_SHOOTER_PROBE_SUMMARY={summary_path}")
    print(f"FETCH_GEOMETRIC_SHOOTER_PROBE_SCORECARD={scorecard_path}")
    print(f"FETCH_GEOMETRIC_SHOOTER_PROBE_PASS={str(mission_completed).lower()}")
    return 0 if mission_completed else 2


if __name__ == "__main__":
    raise SystemExit(main())
