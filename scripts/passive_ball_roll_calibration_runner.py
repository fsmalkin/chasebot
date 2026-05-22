#!/usr/bin/env python3
"""Run a live passive golf-ball roll calibration against Gazebo."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from passive_ball_roll_calibration_helpers import GOLF_SHORT_TURF_ROLL_BAND
from passive_ball_roll_calibration_helpers import ROLL_BANDS_BY_SURFACE
from passive_ball_roll_calibration_helpers import build_scorecard_markdown
from passive_ball_roll_calibration_helpers import classify_roll_result
from passive_ball_roll_calibration_helpers import parse_ball_sdf_profile
from passive_ball_roll_calibration_helpers import summarize_campaign
from passive_ball_roll_calibration_helpers import summarize_roll_samples


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8860"
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_WORLD_FILE = "yolo_test_world_v6_calibrated_golf_turf.world"
DEFAULT_SURFACE_PROFILE = "calibrated_golf_turf"
DEFAULT_BALL_SDF = REPO_ROOT / "ros2_config" / "calibrated_golf_ball.sdf"
DEFAULT_RAMP_SDF = REPO_ROOT / "ros2_config" / "ball_roll_ramp_fixture.sdf"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "session"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_campaign_id() -> str:
    return datetime.now(timezone.utc).strftime("live_passive_golf_roll_calibration_%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def to_container_repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return str(resolved).replace("\\", "/")
    return "/workspaces/chasecar/" + rel.as_posix()


def dashboard_state(dashboard_url: str) -> dict[str, Any]:
    url = dashboard_url.rstrip("/") + "/api/state"
    try:
        with urllib.request.urlopen(url, timeout=4.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def discover_compose_project(dashboard_url: str) -> str:
    state = dashboard_state(dashboard_url)
    for key in ("compose_project", "launcher_project"):
        value = str(state.get(key, "") or "").strip()
        if value:
            return value
    try:
        completed = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    sim_gate_names = [name for name in names if name.endswith("-sim-gate-1")]
    if not sim_gate_names:
        return ""
    # Compose container names are <project>-sim-gate-1.
    return sim_gate_names[-1].removesuffix("-sim-gate-1")


def docker_exec(compose_project: str, script: str, *, timeout_s: float = 60.0) -> tuple[int, str]:
    completed = subprocess.run(
        ["docker", "compose", "-p", compose_project, "exec", "-T", "sim-gate", "bash", "-lc", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def spawn_model(
    *,
    compose_project: str,
    world_name: str,
    model_sdf: Path,
    model_name: str,
    x: float,
    y: float,
    z: float,
    yaw: float = 0.0,
) -> dict[str, Any]:
    model_file = to_container_repo_path(model_sdf)
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
MODEL_FILE={json.dumps(model_file)}
MODEL_NAME={json.dumps(model_name)}
WORLD_NAME={json.dumps(world_name)}
MODEL_X={json.dumps(f"{x:.6f}")}
MODEL_Y={json.dumps(f"{y:.6f}")}
MODEL_Z={json.dumps(f"{z:.6f}")}
MODEL_YAW={json.dumps(f"{yaw:.6f}")}
gz service -s "/world/$WORLD_NAME/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" type: 2" >/dev/null 2>&1 || true
spawn_create() {{
  local include_world="$1"
  local -a cmd=(ros2 run ros_gz_sim create)
  if [[ "$include_world" == "true" ]]; then
    cmd+=(-world "$WORLD_NAME")
  fi
  cmd+=(-file "$MODEL_FILE" -name "$MODEL_NAME" -x "$MODEL_X" -y "$MODEL_Y" -z "$MODEL_Z" -Y "$MODEL_YAW")
  "${{cmd[@]}}"
}}
set +e
spawn_create true > /tmp/chasecar_passive_roll_spawn.log 2>&1
rc=$?
if [[ "$rc" -ne 0 ]] && grep -Eq 'Waiting for service \\[/world/.*/create\\] to become available' /tmp/chasecar_passive_roll_spawn.log 2>/dev/null; then
  spawn_create false >> /tmp/chasecar_passive_roll_spawn.log 2>&1
  rc=$?
fi
if [[ "$rc" -eq 0 ]]; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" position {{ x: $MODEL_X y: $MODEL_Y z: $MODEL_Z }} orientation {{ x: 0 y: 0 z: 0 w: 1 }}" >> /tmp/chasecar_passive_roll_spawn.log 2>&1
  setpose_rc=$?
  if [[ "$setpose_rc" -ne 0 ]]; then
    rc="$setpose_rc"
  fi
fi
cat /tmp/chasecar_passive_roll_spawn.log
exit "$rc"
"""
    rc, output = docker_exec(compose_project, script, timeout_s=60.0)
    return {
        "model_name": model_name,
        "model_sdf": str(model_sdf),
        "pose": {"x": x, "y": y, "z": z, "yaw": yaw},
        "returncode": rc,
        "output": output,
        "pass": rc == 0,
    }


def remove_model(*, compose_project: str, world_name: str, model_name: str) -> None:
    script = f"""
set +e
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
MODEL_NAME={json.dumps(model_name)}
gz service -s "/world/$WORLD_NAME/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" type: 2" >/dev/null 2>&1 || true
"""
    docker_exec(compose_project, script, timeout_s=20.0)


def set_world_gravity(
    *,
    compose_project: str,
    world_name: str,
    gravity_x_mps2: float,
    gravity_y_mps2: float = 0.0,
    gravity_z_mps2: float = -9.80665,
) -> dict[str, Any]:
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
GX={json.dumps(f"{gravity_x_mps2:.6f}")}
GY={json.dumps(f"{gravity_y_mps2:.6f}")}
GZ={json.dumps(f"{gravity_z_mps2:.6f}")}
REQ="max_step_size: 0.001 real_time_factor: 1.0 gravity {{ x: $GX y: $GY z: $GZ }}"
gz service -s "/world/$WORLD_NAME/set_physics/blocking" --reqtype gz.msgs.Physics --reptype gz.msgs.Boolean --timeout 2000 --req "$REQ"
"""
    rc, output = docker_exec(compose_project, script, timeout_s=10.0)
    return {
        "gravity_x_mps2": gravity_x_mps2,
        "gravity_y_mps2": gravity_y_mps2,
        "gravity_z_mps2": gravity_z_mps2,
        "returncode": rc,
        "output": output,
        "pass": rc == 0 and "data: true" in output,
    }


def apply_gravity_impulse(args: argparse.Namespace) -> dict[str, Any]:
    impulse = set_world_gravity(
        compose_project=args.compose_project,
        world_name=args.world_name,
        gravity_x_mps2=args.impulse_gravity_x_mps2,
    )
    time.sleep(max(0.0, float(args.impulse_duration_s)))
    restore = set_world_gravity(
        compose_project=args.compose_project,
        world_name=args.world_name,
        gravity_x_mps2=0.0,
    )
    return {
        "method": "gravity_impulse",
        "impulse_duration_s": round(float(args.impulse_duration_s), 6),
        "impulse_gravity_x_mps2": round(float(args.impulse_gravity_x_mps2), 6),
        "impulse": impulse,
        "restore": restore,
        "pass": bool(impulse.get("pass", False) and restore.get("pass", False)),
    }


def collect_ball_samples(
    *,
    compose_project: str,
    world_name: str,
    ball_model_name: str,
    duration_s: float,
    poll_period_s: float,
) -> list[dict[str, Any]]:
    script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
export WORLD_NAME={json.dumps(world_name)}
export BALL_MODEL_NAME={json.dumps(ball_model_name)}
export DURATION_S={json.dumps(f"{duration_s:.6f}")}
export POLL_PERIOD_S={json.dumps(f"{poll_period_s:.6f}")}
python3 - <<'PY'
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/workspaces/chasecar/scripts")
from sim_truth_probe import parse_pose_message

world_name = os.environ["WORLD_NAME"]
ball_model_name = os.environ["BALL_MODEL_NAME"]
duration_s = float(os.environ["DURATION_S"])
poll_period_s = float(os.environ["POLL_PERIOD_S"])
topic = f"/world/{{world_name}}/dynamic_pose/info"
started = time.monotonic()
deadline = started + max(duration_s, 0.1)
index = 0
while time.monotonic() < deadline:
    tick_started = time.monotonic()
    record = {{
        "sample_index": index,
        "t_s": round(tick_started - started, 6),
        "topic_ok": False,
        "model_name": ball_model_name,
        "position": None,
        "orientation": None,
    }}
    try:
        completed = subprocess.run(
            ["gz", "topic", "-e", "-n", "1", "-t", topic],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        record["topic_ok"] = completed.returncode == 0
        if completed.returncode == 0:
            poses = parse_pose_message(completed.stdout or "")
            pose = next((item for item in poses if item.get("name") == ball_model_name), None)
            if pose:
                record["position"] = pose.get("position")
                record["orientation"] = pose.get("orientation")
    except Exception as exc:
        record["error"] = str(exc)
    print(json.dumps(record, sort_keys=True), flush=True)
    index += 1
    elapsed = time.monotonic() - tick_started
    if elapsed < poll_period_s:
        time.sleep(poll_period_s - elapsed)
PY
"""
    rc, output = docker_exec(compose_project, script, timeout_s=duration_s + 30.0)
    samples: list[dict[str, Any]] = []
    for line in output.splitlines():
        text = line.strip()
        if not text or not text.startswith("{"):
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row.get("position"), dict):
            samples.append(row)
    if rc != 0 and not samples:
        raise RuntimeError(output.strip() or "failed to sample Gazebo pose topic")
    return samples


def run_one(args: argparse.Namespace, *, run_index: int, artifact_dir: Path, reference_band: Any) -> dict[str, Any]:
    spawn_log_path = artifact_dir / f"run_{run_index:02d}_spawn.json"
    trace_path = artifact_dir / f"run_{run_index:02d}_trace.jsonl"
    summary_path = artifact_dir / f"run_{run_index:02d}_summary.json"

    ramp_spawn: dict[str, Any] = {"method": args.launch_method, "pass": True, "skipped": True}
    if args.launch_method == "ramp":
        ramp_spawn = spawn_model(
            compose_project=args.compose_project,
            world_name=args.world_name,
            model_sdf=Path(args.ramp_fixture_sdf),
            model_name=args.ramp_model_name,
            x=0.0,
            y=0.0,
            z=0.0,
            yaw=0.0,
        )
    ball_spawn = spawn_model(
        compose_project=args.compose_project,
        world_name=args.world_name,
        model_sdf=Path(args.ball_model_sdf),
        model_name=args.ball_model_name,
        x=args.ball_start_x,
        y=args.ball_start_y,
        z=args.ball_start_z,
        yaw=0.0,
    )
    launch_payload: dict[str, Any] = {}
    if args.launch_method == "gravity_impulse" and ball_spawn["pass"]:
        launch_payload = apply_gravity_impulse(args)
    write_json(spawn_log_path, {"ramp": ramp_spawn, "ball": ball_spawn, "launch": launch_payload})
    if not ramp_spawn["pass"] or not ball_spawn["pass"]:
        raise RuntimeError(f"spawn failed; see {spawn_log_path}")
    if launch_payload and not bool(launch_payload.get("pass", False)):
        raise RuntimeError(f"launch impulse failed; see {spawn_log_path}")

    samples = collect_ball_samples(
        compose_project=args.compose_project,
        world_name=args.world_name,
        ball_model_name=args.ball_model_name,
        duration_s=args.sample_duration_s,
        poll_period_s=args.poll_period_s,
    )
    for sample in samples:
        append_jsonl(trace_path, sample)

    metrics = summarize_roll_samples(
        samples,
        ground_start_x_m=args.ground_start_x,
        stop_speed_threshold_mps=reference_band.stop_speed_threshold_mps,
        rest_dwell_s=reference_band.rest_dwell_s,
    )
    classification = classify_roll_result(
        metrics,
        reference_band=reference_band,
        min_peak_speed_mps=args.min_peak_speed_mps,
    )
    result = {
        "run_index": run_index,
        "generated_utc": utc_now(),
        "compose_project": args.compose_project,
        "world_name": args.world_name,
        "surface_profile": args.surface_profile,
        "trace_path": str(trace_path),
        "spawn_log_path": str(spawn_log_path),
        **metrics,
        **classification,
    }
    write_json(summary_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a passive golf-ball roll calibration gate.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--world-name", default=DEFAULT_WORLD_NAME)
    parser.add_argument("--world-file", default=DEFAULT_WORLD_FILE)
    parser.add_argument("--surface-profile", default=DEFAULT_SURFACE_PROFILE)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--sample-duration-s", type=float, default=12.0)
    parser.add_argument("--poll-period-s", type=float, default=0.12)
    parser.add_argument("--min-peak-speed-mps", type=float, default=0.35)
    parser.add_argument("--launch-method", choices=("gravity_impulse", "ramp"), default="gravity_impulse")
    parser.add_argument("--impulse-gravity-x-mps2", type=float, default=2.2)
    parser.add_argument("--impulse-duration-s", type=float, default=0.55)
    parser.add_argument("--ground-start-x", type=float, default=-2.0)
    parser.add_argument("--ball-start-x", type=float, default=-0.75)
    parser.add_argument("--ball-start-y", type=float, default=1.0)
    parser.add_argument("--ball-start-z", type=float, default=0.021336)
    parser.add_argument("--ball-model-name", default="passive_roll_calibration_ball")
    parser.add_argument("--ball-model-sdf", default=str(DEFAULT_BALL_SDF))
    parser.add_argument("--ramp-model-name", default="passive_roll_calibration_ramp")
    parser.add_argument("--ramp-fixture-sdf", default=str(DEFAULT_RAMP_SDF))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--keep-models", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.campaign_id = args.campaign_id or make_campaign_id()
    args.compose_project = args.compose_project or discover_compose_project(args.dashboard_url)
    if not args.compose_project:
        raise SystemExit("Unable to discover compose project; pass --compose-project.")
    reference_band = ROLL_BANDS_BY_SURFACE.get(args.surface_profile, GOLF_SHORT_TURF_ROLL_BAND)
    artifact_dir = Path(args.artifact_root) / args.campaign_id / "passive_ball_roll_calibration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    ball_profile = parse_ball_sdf_profile(Path(args.ball_model_sdf))

    run_results: list[dict[str, Any]] = []
    try:
        for run_index in range(1, max(1, int(args.runs)) + 1):
            result = run_one(args, run_index=run_index, artifact_dir=artifact_dir, reference_band=reference_band)
            run_results.append(result)
            print(
                "PASSIVE_ROLL_RUN="
                + json.dumps(
                    {
                        "run_index": run_index,
                        "pass": result["pass"],
                        "reason": result["reason"],
                        "peak_speed_mps": result["peak_speed_mps"],
                        "roll_distance_m": result["roll_distance_m"],
                    },
                    sort_keys=True,
                )
            )
            time.sleep(0.5)
    finally:
        if not args.keep_models:
            remove_model(compose_project=args.compose_project, world_name=args.world_name, model_name=args.ball_model_name)
            remove_model(compose_project=args.compose_project, world_name=args.world_name, model_name=args.ramp_model_name)

    summary = summarize_campaign(
        campaign_id=args.campaign_id,
        surface_profile=args.surface_profile,
        world_file=args.world_file,
        ball_profile=ball_profile,
        reference_band=reference_band,
        run_results=run_results,
    )
    summary_path = artifact_dir / "campaign_summary.json"
    scorecard_path = artifact_dir / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    print(f"PASSIVE_BALL_ROLL_SUMMARY={summary_path}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
