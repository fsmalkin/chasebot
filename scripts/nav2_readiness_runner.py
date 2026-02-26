#!/usr/bin/env python3
"""
Nav2 readiness runner for acquire/plan/track validation.

Outputs:
- artifacts/nav2/<timestamp>/nav_summary.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from typing import List

import yaml

import rclpy
from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import PointStamped
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from rcl_interfaces.msg import Log
from rclpy.node import Node


def goal_key(goal_info) -> str:
    return ''.join(f'{b:02x}' for b in goal_info.goal_id.uuid)


def score_from_rate_and_gap(rate: float, min_rate: float, longest_gap: float, max_gap: float) -> float:
    if min_rate <= 0:
        rate_score = 1.0
    else:
        rate_score = min(rate / min_rate, 1.0)

    if max_gap <= 0:
        gap_score = 1.0
    elif longest_gap <= max_gap:
        gap_score = 1.0
    else:
        gap_score = max(0.0, 1.0 - ((longest_gap - max_gap) / max_gap))

    return round((rate_score + gap_score) / 2.0, 4)


class Nav2Monitor(Node):
    def __init__(self, status_topic: str, cmd_vel_topic_primary: str, cmd_vel_topic_secondary: str, detection_topic: str):
        super().__init__('nav2_readiness_runner')
        self.goal_statuses: Dict[str, set[int]] = {}
        self.cmd_vel_times: List[float] = []
        self.detection_times: List[float] = []
        self.planner_errors = 0
        self.controller_errors = 0

        self.create_subscription(
            GoalStatusArray,
            status_topic,
            self._on_status,
            20,
        )
        self.create_subscription(
            TwistStamped,
            cmd_vel_topic_primary,
            self._on_cmd_vel_stamped,
            20,
        )
        self.create_subscription(
            Twist,
            cmd_vel_topic_secondary,
            self._on_cmd_vel,
            20,
        )
        self.create_subscription(
            PointStamped,
            detection_topic,
            self._on_detection,
            20,
        )
        self.create_subscription(
            Log,
            '/rosout',
            self._on_rosout,
            100,
        )

    def reset_metrics(self) -> None:
        self.goal_statuses = {}
        self.cmd_vel_times = []
        self.detection_times = []
        self.planner_errors = 0
        self.controller_errors = 0

    def _on_status(self, msg: GoalStatusArray) -> None:
        for status in msg.status_list:
            gid = goal_key(status.goal_info)
            if gid not in self.goal_statuses:
                self.goal_statuses[gid] = set()
            self.goal_statuses[gid].add(int(status.status))

    def _on_cmd_vel_stamped(self, msg: TwistStamped) -> None:
        _ = msg
        self.cmd_vel_times.append(time.monotonic())

    def _on_cmd_vel(self, msg: Twist) -> None:
        _ = msg
        self.cmd_vel_times.append(time.monotonic())

    def _on_detection(self, msg: PointStamped) -> None:
        _ = msg
        self.detection_times.append(time.monotonic())

    def _on_rosout(self, msg: Log) -> None:
        name = (msg.name or '').lower()
        text = (msg.msg or '').lower()
        # Treat only ERROR/FATAL as hard failures for readiness gating.
        if msg.level < Log.ERROR:
            return
        if 'planner' in name or 'planner_server' in text:
            self.planner_errors += 1
        if 'controller' in name or 'controller_server' in text:
            self.controller_errors += 1


def compute_rate_and_longest_gap(times: List[float]) -> Dict[str, float]:
    if len(times) < 2:
        return {'rate_hz': 0.0, 'longest_gap_s': float('inf'), 'avg_gap_s': float('inf')}
    sorted_times = sorted(times)
    gaps = [sorted_times[i] - sorted_times[i - 1] for i in range(1, len(sorted_times))]
    duration = sorted_times[-1] - sorted_times[0]
    rate_hz = (len(sorted_times) - 1) / duration if duration > 0 else 0.0
    return {
        'rate_hz': float(rate_hz),
        'longest_gap_s': float(max(gaps)),
        'avg_gap_s': float(statistics.fmean(gaps)),
    }


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Run Nav2 readiness monitor and emit nav_summary.json.')
    parser.add_argument(
        '--config',
        default=str(repo_root / 'ros2_config' / 'config' / 'nav2_readiness.yaml'),
        help='Path to nav2 readiness YAML.',
    )
    parser.add_argument(
        '--duration-s',
        type=float,
        default=None,
        help='Override monitor duration in seconds.',
    )
    parser.add_argument(
        '--output-base',
        default=str(repo_root / 'artifacts' / 'nav2'),
        help='Base output directory where run timestamp folder will be created.',
    )
    parser.add_argument(
        '--runtime-target',
        default='robot_fidelity',
        help='Runtime target label included in summary output.',
    )
    parser.add_argument(
        '--profile',
        default='compat',
        help='Performance profile label included in summary output.',
    )
    parser.add_argument(
        '--inference-device',
        default='auto',
        help='Resolved/selected inference device label included in summary output.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    with config_path.open('r', encoding='utf-8') as fp:
        cfg = yaml.safe_load(fp)

    metadata = cfg.get('metadata', {})
    defaults = cfg.get('defaults', {})
    thresholds = cfg.get('thresholds', {})

    duration_s = float(args.duration_s if args.duration_s is not None else defaults.get('duration_s', 120.0))
    warmup_s = float(defaults.get('warmup_s', 15.0))
    sample_interval_s = float(defaults.get('sample_interval_s', 0.1))
    min_cmd_vel_hz = float(defaults.get('min_cmd_vel_hz', 1.0))
    max_cmd_vel_gap_s = float(defaults.get('max_cmd_vel_gap_s', 2.0))
    min_detection_hz = float(defaults.get('min_detection_hz', 1.0))
    max_detection_gap_s = float(defaults.get('max_detection_gap_s', 2.0))

    status_topic = metadata.get('status_topic', '/navigate_to_pose/_action/status')
    cmd_vel_topic_primary = metadata.get('cmd_vel_topic_primary', '/jetbot_base_controller/cmd_vel')
    cmd_vel_topic_secondary = metadata.get('cmd_vel_topic_secondary', '/cmd_vel')
    detection_topic = metadata.get('detection_topic', '/yolo/ball_position_3d')

    out_base = Path(args.output_base).resolve()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_dir = out_base / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    out_path = out_dir / 'nav_summary.json'

    rclpy.init()
    node = Nav2Monitor(
        status_topic=status_topic,
        cmd_vel_topic_primary=cmd_vel_topic_primary,
        cmd_vel_topic_secondary=cmd_vel_topic_secondary,
        detection_topic=detection_topic,
    )

    if warmup_s > 0.0:
        warmup_start = time.monotonic()
        while time.monotonic() - warmup_start < warmup_s and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=sample_interval_s)
        node.reset_metrics()

    start = time.monotonic()
    while time.monotonic() - start < duration_s and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=sample_interval_s)

    requested_goals = len(node.goal_statuses)
    accepted_goals = 0
    succeeded_goals = 0
    for statuses in node.goal_statuses.values():
        if statuses:
            accepted_goals += 1
        if 4 in statuses:
            succeeded_goals += 1

    goal_accept_rate = accepted_goals / requested_goals if requested_goals else 0.0
    goal_success_rate = succeeded_goals / accepted_goals if accepted_goals else 0.0

    cmd_vel_stats = compute_rate_and_longest_gap(node.cmd_vel_times)
    detection_stats = compute_rate_and_longest_gap(node.detection_times)

    cmd_vel_publish_stability = score_from_rate_and_gap(
        rate=cmd_vel_stats['rate_hz'],
        min_rate=min_cmd_vel_hz,
        longest_gap=cmd_vel_stats['longest_gap_s'],
        max_gap=max_cmd_vel_gap_s,
    )
    tracking_continuity_score = score_from_rate_and_gap(
        rate=detection_stats['rate_hz'],
        min_rate=min_detection_hz,
        longest_gap=detection_stats['longest_gap_s'],
        max_gap=max_detection_gap_s,
    )

    summary = {
        'run_id': run_id,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'runtime_target': args.runtime_target,
        'profile': args.profile,
        'inference_device_resolved': args.inference_device,
        'duration_s': duration_s,
        'goal_request_count': requested_goals,
        'goal_accept_count': accepted_goals,
        'goal_success_count': succeeded_goals,
        'goal_accept_rate': goal_accept_rate,
        'goal_success_rate': goal_success_rate,
        'cmd_vel_publish_stability': cmd_vel_publish_stability,
        'planner/controller_error_counts': {
            'planner': node.planner_errors,
            'controller': node.controller_errors,
        },
        'tracking_continuity_score': tracking_continuity_score,
        'cmd_vel_stats': cmd_vel_stats,
        'detection_stats': detection_stats,
        'thresholds': {
            'goal_accept_rate_min': float(thresholds.get('goal_accept_rate_min', 0.80)),
            'goal_success_rate_min': float(thresholds.get('goal_success_rate_min', 0.60)),
            'cmd_vel_publish_stability_min': float(thresholds.get('cmd_vel_publish_stability_min', 0.70)),
            'tracking_continuity_score_min': float(thresholds.get('tracking_continuity_score_min', 0.70)),
            'planner_errors_max': int(thresholds.get('planner_errors_max', 0)),
            'controller_errors_max': int(thresholds.get('controller_errors_max', 0)),
        },
    }
    summary['pass'] = (
        summary['goal_accept_rate'] >= summary['thresholds']['goal_accept_rate_min']
        and summary['goal_success_rate'] >= summary['thresholds']['goal_success_rate_min']
        and summary['cmd_vel_publish_stability'] >= summary['thresholds']['cmd_vel_publish_stability_min']
        and summary['tracking_continuity_score'] >= summary['thresholds']['tracking_continuity_score_min']
        and summary['planner/controller_error_counts']['planner'] <= summary['thresholds']['planner_errors_max']
        and summary['planner/controller_error_counts']['controller'] <= summary['thresholds']['controller_errors_max']
    )

    with out_path.open('w', encoding='utf-8') as fp:
        json.dump(summary, fp, indent=2, sort_keys=True)
        fp.write('\n')

    print(f'Wrote {out_path}')
    print(f'Overall pass: {summary["pass"]}')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if summary['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
