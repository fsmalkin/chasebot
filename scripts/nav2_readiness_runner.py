#!/usr/bin/env python3
"""
Nav2 readiness runner for acquire/plan/track validation.

Outputs:
- artifacts/nav2/<timestamp>/nav_summary.json
"""

from __future__ import annotations

import argparse
import csv
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
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import Log
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles


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
    def __init__(
        self,
        status_topic: str,
        cmd_vel_topic_primary: str,
        cmd_vel_topic_secondary: str,
        detection_topic: str,
        odom_topic: str,
    ):
        super().__init__('nav2_readiness_runner')
        self.goal_statuses: Dict[str, set[int]] = {}
        self.cmd_vel_times: List[float] = []
        self.detection_times: List[float] = []
        self.latest_odom: Odometry | None = None
        self.planner_errors = 0
        self.controller_errors = 0
        self.goal_accept_events = 0
        self.goal_success_events = 0

        self.create_subscription(
            GoalStatusArray,
            status_topic,
            self._on_status,
            20,
        )
        cmd_vel_topics = []
        for topic in (cmd_vel_topic_primary, cmd_vel_topic_secondary, '/cmd_vel_nav'):
            if topic and topic not in cmd_vel_topics:
                cmd_vel_topics.append(topic)
        for topic in cmd_vel_topics:
            self.create_subscription(
                TwistStamped,
                topic,
                self._on_cmd_vel_stamped,
                20,
            )
            self.create_subscription(
                Twist,
                topic,
                self._on_cmd_vel,
                20,
            )
        self.create_subscription(
            PointStamped,
            detection_topic,
            self._on_detection,
            20,
        )
        odom_topics = []
        for topic in (odom_topic, '/model/jetbot/odometry', '/jetbot_base_controller/odom'):
            if topic and topic not in odom_topics:
                odom_topics.append(topic)
        for topic in odom_topics:
            self.create_subscription(
                Odometry,
                topic,
                self._on_odom,
                QoSPresetProfiles.SENSOR_DATA.value,
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
        self.goal_accept_events = 0
        self.goal_success_events = 0

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

    def _on_odom(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def _on_rosout(self, msg: Log) -> None:
        name = (msg.name or '').lower()
        text = (msg.msg or '').lower()
        if 'goal accepted by nav2' in text:
            self.goal_accept_events += 1
        if 'navigation goal reached successfully' in text:
            self.goal_success_events += 1
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


def compute_target_distance_m(odom: Odometry, target_x: float, target_y: float) -> float:
    dx = float(odom.pose.pose.position.x) - target_x
    dy = float(odom.pose.pose.position.y) - target_y
    return math.hypot(dx, dy)


def compute_trend_slope_mps(samples: List[tuple[float, float]]) -> float:
    if len(samples) < 2:
        return float('nan')
    xs = [s[0] for s in samples]
    ys = [s[1] for s in samples]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in samples)
    den = sum((x - x_mean) ** 2 for x in xs)
    if den <= 1e-9:
        return float('nan')
    return float(num / den)


def compute_away_ratio(samples: List[tuple[float, float]], delta_epsilon_m: float = 0.005) -> float:
    if len(samples) < 2:
        return 1.0
    away_steps = 0
    step_count = 0
    for i in range(1, len(samples)):
        prev = samples[i - 1][1]
        curr = samples[i][1]
        step_count += 1
        if curr - prev > delta_epsilon_m:
            away_steps += 1
    if step_count == 0:
        return 1.0
    return float(away_steps / step_count)


def prefix_to_first_minimum(samples: List[tuple[float, float]]) -> List[tuple[float, float]]:
    if len(samples) < 2:
        return samples
    min_index = min(range(len(samples)), key=lambda i: samples[i][1])
    if min_index < 1:
        return samples[:2]
    return samples[: min_index + 1]


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
        default='robot_fidelity_orin',
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
    odom_topic = metadata.get('odom_topic', '/odom')
    spawn_world = metadata.get('spawn_world', {})
    target_x_raw = spawn_world.get('x', None)
    target_y_raw = spawn_world.get('y', None)
    target_progress_enabled = target_x_raw is not None and target_y_raw is not None
    target_x = float(target_x_raw) if target_x_raw is not None else 0.0
    target_y = float(target_y_raw) if target_y_raw is not None else 0.0

    out_base = Path(args.output_base).resolve()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_dir = out_base / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    out_path = out_dir / 'nav_summary.json'
    distance_samples_csv = out_dir / 'distance_samples.csv'

    rclpy.init()
    node = Nav2Monitor(
        status_topic=status_topic,
        cmd_vel_topic_primary=cmd_vel_topic_primary,
        cmd_vel_topic_secondary=cmd_vel_topic_secondary,
        detection_topic=detection_topic,
        odom_topic=odom_topic,
    )

    if warmup_s > 0.0:
        warmup_start = time.monotonic()
        while time.monotonic() - warmup_start < warmup_s and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=sample_interval_s)
        node.reset_metrics()

    start = time.monotonic()
    target_distance_start_m: float | None = None
    target_distance_end_m: float | None = None
    target_distance_min_m: float | None = None
    target_distance_samples: List[tuple[float, float]] = []
    while time.monotonic() - start < duration_s and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=sample_interval_s)
        if target_progress_enabled and node.latest_odom is not None:
            distance_m = compute_target_distance_m(node.latest_odom, target_x, target_y)
            if math.isfinite(distance_m):
                elapsed_s = time.monotonic() - start
                target_distance_samples.append((float(elapsed_s), float(distance_m)))
                if target_distance_start_m is None:
                    target_distance_start_m = distance_m
                target_distance_end_m = distance_m
                if target_distance_min_m is None or distance_m < target_distance_min_m:
                    target_distance_min_m = distance_m

    requested_goals = len(node.goal_statuses)
    accepted_goals = 0
    succeeded_goals = 0
    goal_event_source = 'status_topic'
    for statuses in node.goal_statuses.values():
        if statuses:
            accepted_goals += 1
        if 4 in statuses:
            succeeded_goals += 1

    if requested_goals == 0 and (node.goal_accept_events > 0 or node.goal_success_events > 0):
        goal_event_source = 'bridge_rosout_fallback'
        accepted_goals = int(max(node.goal_accept_events, node.goal_success_events))
        succeeded_goals = int(min(node.goal_success_events, accepted_goals))
        requested_goals = accepted_goals

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

    target_distance_improvement_m = None
    if target_distance_start_m is not None and target_distance_min_m is not None:
        target_distance_improvement_m = target_distance_start_m - target_distance_min_m
    target_distance_retained_progress_m = None
    if target_distance_start_m is not None and target_distance_end_m is not None:
        target_distance_retained_progress_m = target_distance_start_m - target_distance_end_m
    target_distance_improvement_ratio = None
    if (
        target_distance_improvement_m is not None
        and target_distance_start_m is not None
        and target_distance_start_m > 1e-6
    ):
        target_distance_improvement_ratio = target_distance_improvement_m / target_distance_start_m

    approach_samples = prefix_to_first_minimum(target_distance_samples)
    target_distance_trend_slope_mps = compute_trend_slope_mps(approach_samples)
    target_away_ratio = compute_away_ratio(approach_samples)
    target_sample_count = len(target_distance_samples)
    target_approach_sample_count = len(approach_samples)

    target_distance_improvement_min_m = float(thresholds.get('target_distance_improvement_min_m', 0.10))
    target_distance_retained_progress_min_m = float(thresholds.get('target_distance_retained_progress_min_m', 0.05))
    target_distance_improvement_ratio_min = float(thresholds.get('target_distance_improvement_ratio_min', 0.10))
    target_final_distance_max_m = float(thresholds.get('target_final_distance_max_m', 0.80))
    target_away_ratio_max = float(thresholds.get('target_away_ratio_max', 0.60))
    target_trend_slope_max_mps = float(thresholds.get('target_trend_slope_max_mps', -0.001))
    target_min_samples = int(thresholds.get('target_min_samples', 20))

    target_sample_pass = target_sample_count >= target_min_samples
    target_improvement_pass = (
        target_distance_improvement_m is not None
        and target_distance_improvement_m >= target_distance_improvement_min_m
    )
    target_retained_progress_pass = (
        target_distance_retained_progress_m is not None
        and target_distance_retained_progress_m >= target_distance_retained_progress_min_m
    )
    target_improvement_ratio_pass = (
        target_distance_improvement_ratio is not None
        and target_distance_improvement_ratio >= target_distance_improvement_ratio_min
    )
    target_final_distance_pass = (
        target_distance_end_m is not None
        and target_distance_end_m <= target_final_distance_max_m
    )
    target_away_ratio_pass = target_away_ratio <= target_away_ratio_max
    target_trend_pass = (
        math.isfinite(target_distance_trend_slope_mps)
        and target_distance_trend_slope_mps <= target_trend_slope_max_mps
    )
    target_progress_pass = (
        (not target_progress_enabled)
        or (
            target_sample_pass
            and target_improvement_pass
            and target_retained_progress_pass
            and target_improvement_ratio_pass
            and target_final_distance_pass
            and target_away_ratio_pass
            and target_trend_pass
        )
    )

    with distance_samples_csv.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=['t_s', 'distance_m'])
        writer.writeheader()
        for elapsed_s, distance_m in target_distance_samples:
            writer.writerow({'t_s': elapsed_s, 'distance_m': distance_m})

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
        'goal_event_source': goal_event_source,
        'goal_accept_rate': goal_accept_rate,
        'goal_success_rate': goal_success_rate,
        'cmd_vel_publish_stability': cmd_vel_publish_stability,
        'planner/controller_error_counts': {
            'planner': node.planner_errors,
            'controller': node.controller_errors,
        },
        'tracking_continuity_score': tracking_continuity_score,
        'target_progress': {
            'enabled': target_progress_enabled,
            'target_x_m': target_x if target_progress_enabled else None,
            'target_y_m': target_y if target_progress_enabled else None,
            'start_distance_m': target_distance_start_m,
            'end_distance_m': target_distance_end_m,
            'min_distance_m': target_distance_min_m,
            'distance_improvement_m': target_distance_improvement_m,
            'distance_retained_progress_m': target_distance_retained_progress_m,
            'distance_improvement_ratio': target_distance_improvement_ratio,
            'distance_trend_slope_mps': target_distance_trend_slope_mps,
            'away_ratio': target_away_ratio,
            'sample_count': target_sample_count,
            'approach_sample_count': target_approach_sample_count,
            'distance_samples_csv': str(distance_samples_csv),
            'checks': {
                'min_samples': target_sample_pass,
                'improvement': target_improvement_pass,
                'retained_progress': target_retained_progress_pass,
                'improvement_ratio': target_improvement_ratio_pass,
                'final_distance': target_final_distance_pass,
                'away_ratio': target_away_ratio_pass,
                'trend_slope': target_trend_pass,
            },
            'pass': target_progress_pass,
        },
        'cmd_vel_stats': cmd_vel_stats,
        'detection_stats': detection_stats,
        'thresholds': {
            'goal_accept_rate_min': float(thresholds.get('goal_accept_rate_min', 0.80)),
            'goal_success_rate_min': float(thresholds.get('goal_success_rate_min', 0.60)),
            'cmd_vel_publish_stability_min': float(thresholds.get('cmd_vel_publish_stability_min', 0.70)),
            'tracking_continuity_score_min': float(thresholds.get('tracking_continuity_score_min', 0.70)),
            'target_distance_improvement_min_m': target_distance_improvement_min_m,
            'target_distance_retained_progress_min_m': target_distance_retained_progress_min_m,
            'target_distance_improvement_ratio_min': target_distance_improvement_ratio_min,
            'target_final_distance_max_m': target_final_distance_max_m,
            'target_away_ratio_max': target_away_ratio_max,
            'target_trend_slope_max_mps': target_trend_slope_max_mps,
            'target_min_samples': target_min_samples,
            'planner_errors_max': int(thresholds.get('planner_errors_max', 0)),
            'controller_errors_max': int(thresholds.get('controller_errors_max', 0)),
        },
    }
    summary['pass'] = (
        summary['goal_accept_rate'] >= summary['thresholds']['goal_accept_rate_min']
        and summary['goal_success_rate'] >= summary['thresholds']['goal_success_rate_min']
        and summary['cmd_vel_publish_stability'] >= summary['thresholds']['cmd_vel_publish_stability_min']
        and summary['tracking_continuity_score'] >= summary['thresholds']['tracking_continuity_score_min']
        and summary['target_progress']['pass']
        and summary['planner/controller_error_counts']['planner'] <= summary['thresholds']['planner_errors_max']
        and summary['planner/controller_error_counts']['controller'] <= summary['thresholds']['controller_errors_max']
    )

    with out_path.open('w', encoding='utf-8') as fp:
        json.dump(summary, fp, indent=2, sort_keys=True)
        fp.write('\n')

    print(f'Wrote {out_path}')
    print(f'Wrote {distance_samples_csv}')
    print(f'Overall pass: {summary["pass"]}')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if summary['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
