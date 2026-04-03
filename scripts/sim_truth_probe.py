#!/usr/bin/env python3
"""Poll Gazebo pose info and persist same-session truth state for visual runs."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll Gazebo pose info for same-session truth state.")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--world-name", required=True)
    parser.add_argument("--robot-model-name", default="jetbot")
    parser.add_argument(
        "--target-model-names",
        default=(
            "visit_mission_target_ball_1,"
            "visit_mission_target_ball_2,"
            "visit_mission_target_ball_3,"
            "milestone_demo_target,"
            "milestone_demo_target_viewer,"
            "uat_nav2_target,"
            "uat_snapshot_target,"
            "llm_turn_then_go_target"
        ),
    )
    parser.add_argument("--topic", default="")
    parser.add_argument("--duration-s", type=float, default=180.0)
    parser.add_argument("--poll-period-s", type=float, default=0.5)
    return parser.parse_args()


def parse_pose_message(text: str) -> list[dict[str, object]]:
    poses: list[dict[str, object]] = []
    stack: list[str] = []
    current: dict[str, object] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("{"):
            key = line[:-1].strip()
            stack.append(key)
            if key == "pose":
                current = {
                    "name": "",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                }
            continue
        if line == "}":
            if not stack:
                continue
            popped = stack.pop()
            if popped == "pose" and current is not None:
                poses.append(current)
                current = None
            continue
        if current is None or ":" not in line:
            continue

        key, raw_value = [part.strip() for part in line.split(":", 1)]
        section = stack[-1] if stack else ""
        if raw_value.startswith('"') and raw_value.endswith('"'):
            value: object = raw_value[1:-1]
        else:
            try:
                value = float(raw_value)
            except ValueError:
                value = raw_value

        if key == "name":
            current["name"] = value
        elif section in ("position", "orientation"):
            current_section = current[section]
            if isinstance(current_section, dict):
                current_section[key] = value

    return poses


def sample_pose_topic(topic: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["gz", "topic", "-e", "-n", "1", "-t", topic],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, ""
    if completed.returncode != 0:
        return False, (completed.stdout or "") + "\n" + (completed.stderr or "")
    return True, completed.stdout or ""


def select_target_poses(
    poses: list[dict[str, object]],
    target_candidates: list[str],
) -> tuple[dict[str, dict[str, object]], list[str], dict[str, object] | None, str]:
    target_poses_by_name: dict[str, dict[str, object]] = {}
    target_names_seen: list[str] = []
    first_target_pose: dict[str, object] | None = None
    first_target_name = ""
    for candidate in target_candidates:
        target_pose = next((pose for pose in poses if pose.get("name") == candidate), None)
        if not isinstance(target_pose, dict):
            continue
        target_poses_by_name[candidate] = target_pose
        target_names_seen.append(candidate)
        if first_target_pose is None:
            first_target_pose = target_pose
            first_target_name = candidate
    return target_poses_by_name, target_names_seen, first_target_pose, first_target_name


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "truth_state.json"
    timeline_path = output_dir / "truth_timeline.json"
    summary_path = output_dir / "truth_summary.json"
    target_candidates = [item.strip() for item in args.target_model_names.split(",") if item.strip()]
    topic = args.topic or f"/world/{args.world_name}/dynamic_pose/info"
    started = time.monotonic()
    deadline = started + max(args.duration_s, 1.0)
    timeline: list[dict[str, object]] = []
    stop_requested = False

    def request_stop(*_args: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    samples = 0
    robot_seen = 0
    target_seen = 0
    latest_robot = None
    latest_target = None
    latest_target_name = ""
    latest_target_poses_by_name: dict[str, dict[str, object]] = {}
    latest_target_names_seen: list[str] = []

    while not stop_requested and time.monotonic() < deadline:
        ok, payload = sample_pose_topic(topic)
        elapsed = round(time.monotonic() - started, 3)
        record: dict[str, object] = {
            "t_s": elapsed,
            "topic_ok": ok,
            "robot_truth_pose": None,
            "true_target_pose": None,
            "target_model_name": "",
            "target_poses_by_name": {},
            "target_names_seen": [],
        }
        if ok and payload:
            poses = parse_pose_message(payload)
            robot_pose = next((pose for pose in poses if pose.get("name") == args.robot_model_name), None)
            target_poses_by_name, target_names_seen, target_pose, target_name = select_target_poses(poses, target_candidates)
            if robot_pose is not None:
                robot_seen += 1
                latest_robot = robot_pose
                record["robot_truth_pose"] = robot_pose
            record["target_poses_by_name"] = target_poses_by_name
            record["target_names_seen"] = target_names_seen
            if target_pose is not None:
                target_seen += 1
                latest_target = target_pose
                latest_target_name = target_name
                record["true_target_pose"] = target_pose
                record["target_model_name"] = target_name
            if target_poses_by_name:
                latest_target_poses_by_name = dict(target_poses_by_name)
                latest_target_names_seen = list(target_names_seen)

        timeline.append(record)
        samples += 1
        state_payload = {
            "session_id": args.session_id,
            "topic": topic,
            "samples": samples,
            "robot_truth_seen": latest_robot is not None,
            "true_target_seen": latest_target is not None,
            "robot_truth_pose": latest_robot,
            "true_target_pose": latest_target,
            "target_model_name": latest_target_name,
            "target_poses_by_name": dict(latest_target_poses_by_name),
            "target_names_seen": list(latest_target_names_seen),
            "target_model_candidates": target_candidates,
        }
        state_path.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")
        time.sleep(max(args.poll_period_s, 0.1))

    summary = {
        "session_id": args.session_id,
        "topic": topic,
        "samples": samples,
        "robot_truth_seen": latest_robot is not None,
        "true_target_seen": latest_target is not None,
        "robot_truth_ratio": round(robot_seen / max(samples, 1), 6),
        "true_target_ratio": round(target_seen / max(samples, 1), 6),
        "target_model_name": latest_target_name,
        "target_poses_by_name": dict(latest_target_poses_by_name),
        "target_names_seen": list(latest_target_names_seen),
        "target_model_candidates": target_candidates,
        "pass": latest_robot is not None and latest_target is not None,
        "state_path": str(state_path),
        "timeline_path": str(timeline_path),
    }
    timeline_path.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"TRUTH_STATE={state_path}")
    print(f"TRUTH_TIMELINE={timeline_path}")
    print(f"TRUTH_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
