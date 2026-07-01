#!/usr/bin/env python3
"""Thin orchestrator for mono fetch sim validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import golf_ball_circle_delivery_demo_runner as runner  # noqa: E402
from passive_ball_roll_calibration_runner import DEFAULT_DASHBOARD_URL  # noqa: E402
from passive_ball_roll_calibration_runner import DEFAULT_WORLD_NAME  # noqa: E402
from passive_ball_roll_calibration_runner import discover_compose_project  # noqa: E402
from passive_ball_roll_calibration_runner import to_container_repo_path  # noqa: E402


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def gate_stack_popen(compose_project: str, script: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["docker", "compose", "-p", compose_project, "exec", "-T", "gate-stack", "bash", "-lc", script],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def launch_mono_node(args: argparse.Namespace, *, artifact_dir: Path) -> tuple[subprocess.Popen[str], Path]:
    node_log_dir = artifact_dir / "node"
    node_log_dir.mkdir(parents=True, exist_ok=True)
    calibration = to_container_repo_path(Path(args.calibration).resolve())
    model = to_container_repo_path(Path(args.model).resolve())
    node_artifacts = to_container_repo_path(node_log_dir.resolve())
    node_script = "/workspaces/chasecar/ros2_scripts/chasecar_mono_fetch_node.py"
    command = (
        "set -eo pipefail\n"
        "set +u\n"
        "source /opt/ros/${CORE_ROS_DISTRO:-kilted}/setup.bash\n"
        "if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi\n"
        "set -u\n"
        f"python3 {node_script} "
        f"--calibration {json.dumps(calibration)} "
        f"--artifact-dir {json.dumps(node_artifacts)} "
        f"--model {json.dumps(model)} "
        "--ros-args "
        "-p use_sim_time:=true "
        f"-p detector:={json.dumps(args.detector)} "
        f"-p image_topic:={json.dumps(args.image_topic)} "
        f"-p camera_info_topic:={json.dumps(args.camera_info_topic)} "
        f"-p cmd_vel_topic:={json.dumps(args.cmd_vel_topic)} "
        f"-p publish_hz:={float(args.publish_hz):.3f} "
        f"-p confidence_threshold:={float(args.confidence_threshold):.6f} "
        f"-p min_confidence:={float(args.min_confidence):.6f} "
        f"-p standoff_m:={float(args.standoff_m):.6f} "
        f"-p push_linear_x:={float(args.push_linear_x):.6f} "
        f"-p push_steps:={int(args.push_steps)} "
        f"-p push_max_distance_m:={float(args.push_max_distance_m):.6f} "
        f"-p forward_budget:={int(args.forward_budget)} "
        f"-p approach_linear_x:={float(args.approach_linear_x):.6f} "
        f"-p max_steps:={int(args.max_steps)}"
    )
    return gate_stack_popen(args.compose_project, command), node_log_dir / "mono_fetch_node.jsonl"


def run_scorer(args: argparse.Namespace, *, artifact_dir: Path, node_log: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "chasecar_mono_fetch_scorer.py"),
        "--compose-project",
        args.compose_project,
        "--world-name",
        args.world_name,
        "--robot-model-name",
        args.robot_model_name,
        "--ball-model-name",
        args.ball_model_name,
        "--duration-s",
        str(args.duration_s),
        "--poll-period-s",
        str(args.poll_period_s),
        "--node-log",
        str(node_log),
        "--artifact-dir",
        str(artifact_dir / "scorer"),
        "--contact-threshold-m",
        str(args.contact_threshold_m),
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=float(args.duration_s) + 120.0,
        check=False,
    )
    verdict_path = artifact_dir / "scorer" / "mono_fetch_verdict.json"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8-sig")) if verdict_path.is_file() else {}
    return {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "verdict_path": str(verdict_path),
        "verdict": verdict,
        "pass": completed.returncode == 0 and bool(verdict.get("pass", False)),
    }


def setup_scene(args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_setup:
        return {"skipped": True, "pass": True}
    setup: dict[str, Any] = {"skipped": False, "steps": []}
    if args.set_robot_pose:
        setup["steps"].append(
            {
                "step": "set_robot_pose",
                **runner.set_model_pose(
                    compose_project=args.compose_project,
                    world_name=args.world_name,
                    model_name=args.robot_model_name,
                    x=float(args.robot_x),
                    y=float(args.robot_y),
                    z=float(args.robot_z),
                    yaw=float(args.robot_yaw),
                ),
            }
        )
    if args.spawn_ball:
        setup["steps"].append(
            {
                "step": "spawn_ball",
                **runner.spawn_model(
                    compose_project=args.compose_project,
                    world_name=args.world_name,
                    model_sdf=Path(args.ball_sdf),
                    model_name=args.ball_model_name,
                    x=float(args.ball_x),
                    y=float(args.ball_y),
                    z=float(args.ball_z),
                    yaw=0.0,
                    set_pose_after_spawn=True,
                ),
            }
        )
    setup["pass"] = all(bool(step.get("pass", False)) for step in setup["steps"]) if setup["steps"] else True
    return setup


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    if not args.compose_project:
        args.compose_project = discover_compose_project(args.dashboard_url)
    if not args.compose_project:
        return {"pass": False, "issues": ["compose_project_required"]}
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else REPO_ROOT / "artifacts" / "session" / ("mono_fetch_harness_%s" % utc_stamp())
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "type": "mono_fetch_harness_summary",
        "artifact_dir": str(artifact_dir),
        "compose_project": args.compose_project,
        "world_name": args.world_name,
        "issues": [],
    }
    summary["controller_preflight"] = runner.ensure_base_controller_active(compose_project=args.compose_project)
    if not bool(summary["controller_preflight"].get("pass", False)):
        summary["issues"].append("base_controller_not_active")
        summary["pass"] = False
        write_json(artifact_dir / "mono_fetch_harness_summary.json", summary)
        return summary
    summary["setup"] = setup_scene(args)
    if not bool(summary["setup"].get("pass", False)):
        summary["issues"].append("scene_setup_failed")
        summary["pass"] = False
        write_json(artifact_dir / "mono_fetch_harness_summary.json", summary)
        return summary

    node_proc = None
    try:
        node_proc, node_log = launch_mono_node(args, artifact_dir=artifact_dir)
        summary["node_log"] = str(node_log)
        time.sleep(max(float(args.node_warmup_s), 0.0))
        summary["scorer"] = run_scorer(args, artifact_dir=artifact_dir, node_log=node_log)
    finally:
        if node_proc is not None and node_proc.poll() is None:
            node_proc.terminate()
            try:
                node_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                node_proc.kill()
        summary["stop_robot_drive_publishers"] = runner.stop_robot_drive_publishers(args.compose_project)
        summary["publish_zero_stop"] = runner.publish_zero_stop(args.compose_project)
    summary["pass"] = bool(summary.get("scorer", {}).get("pass", False))
    write_json(artifact_dir / "mono_fetch_harness_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--world-name", default=DEFAULT_WORLD_NAME)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--model", default=str(REPO_ROOT / "runtime" / "yolo" / "yolov5m.onnx"))
    parser.add_argument("--detector", choices=["yolo", "color"], default="yolo")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--poll-period-s", type=float, default=0.1)
    parser.add_argument("--node-warmup-s", type=float, default=4.0)
    parser.add_argument("--contact-threshold-m", type=float, default=0.14)
    parser.add_argument("--robot-model-name", default=runner.DEFAULT_ROBOT_MODEL_NAME)
    parser.add_argument("--ball-model-name", default=runner.DEFAULT_BALL_MODEL_NAME)
    parser.add_argument("--ball-sdf", default=str(runner.DEFAULT_BALL_SDF))
    parser.add_argument("--spawn-ball", action="store_true")
    parser.add_argument("--skip-setup", action="store_true")
    parser.add_argument("--set-robot-pose", action="store_true")
    parser.add_argument("--robot-x", type=float, default=0.0)
    parser.add_argument("--robot-y", type=float, default=0.0)
    parser.add_argument("--robot-z", type=float, default=0.05)
    parser.add_argument("--robot-yaw", type=float, default=0.0)
    parser.add_argument("--ball-x", type=float, default=0.8)
    parser.add_argument("--ball-y", type=float, default=0.0)
    parser.add_argument("--ball-z", type=float, default=0.05)
    parser.add_argument("--image-topic", default="/d415/color/image_raw")
    parser.add_argument("--camera-info-topic", default="/d415/color/camera_info")
    parser.add_argument("--cmd-vel-topic", default="/jetbot_base_controller/cmd_vel")
    parser.add_argument("--publish-hz", type=float, default=20.0)
    parser.add_argument("--confidence-threshold", type=float, default=0.25)
    parser.add_argument("--min-confidence", type=float, default=0.25)
    parser.add_argument("--standoff-m", type=float, default=0.40)
    parser.add_argument("--push-linear-x", type=float, default=0.10)
    parser.add_argument("--push-steps", type=int, default=500)
    parser.add_argument("--push-max-distance-m", type=float, default=0.95)
    parser.add_argument("--forward-budget", type=int, default=250)
    parser.add_argument("--approach-linear-x", type=float, default=0.08)
    parser.add_argument("--max-steps", type=int, default=400)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_summary(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
