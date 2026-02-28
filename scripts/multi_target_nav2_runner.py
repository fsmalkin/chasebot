#!/usr/bin/env python3
"""Run deterministic multi-target Nav2 readiness checks.

Outputs:
- artifacts/nav2_multi/<timestamp>/multi_target_samples.csv
- artifacts/nav2_multi/<timestamp>/multi_target_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

import yaml

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import Log
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSPresetProfiles


def yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    half = 0.5 * yaw
    return (0.0, 0.0, math.sin(half), math.cos(half))


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


def score_from_rate_and_gap(rate: float, min_rate: float, longest_gap: float, max_gap: float) -> float:
    rate_score = min(rate / min_rate, 1.0) if min_rate > 0 else 1.0
    if max_gap <= 0:
        gap_score = 1.0
    elif longest_gap <= max_gap:
        gap_score = 1.0
    else:
        gap_score = max(0.0, 1.0 - ((longest_gap - max_gap) / max_gap))
    return round((rate_score + gap_score) / 2.0, 4)


@dataclass
class GoalRunResult:
    scenario_id: str
    goal_x: float
    goal_y: float
    goal_yaw: float
    accepted: bool
    success: bool
    status_code: int
    elapsed_s: float
    final_distance_m: Optional[float]
    cmd_vel_message_count: int
    attempts: int
    error: str


class MultiTargetRunner(Node):
    def __init__(
        self,
        action_name: str,
        frame_id: str,
        odom_topic: str,
        cmd_vel_topic_primary: str,
        cmd_vel_topic_secondary: str,
        rosout_topic: str,
    ) -> None:
        super().__init__('multi_target_nav2_runner')
        self._frame_id = frame_id
        self._nav_client = ActionClient(self, NavigateToPose, action_name)

        self.latest_odom: Optional[Odometry] = None
        self.cmd_vel_times: List[float] = []
        self.planner_errors = 0
        self.controller_errors = 0

        sensor_qos = QoSPresetProfiles.SENSOR_DATA.value
        self.create_subscription(Odometry, odom_topic, self._on_odom, sensor_qos)
        self.create_subscription(Odometry, '/model/jetbot/odometry', self._on_odom, sensor_qos)
        self.create_subscription(Odometry, '/jetbot_base_controller/odom', self._on_odom, sensor_qos)
        self.create_subscription(TwistStamped, cmd_vel_topic_primary, self._on_cmd_vel_stamped, sensor_qos)
        self.create_subscription(Twist, cmd_vel_topic_secondary, self._on_cmd_vel, sensor_qos)
        self.create_subscription(Log, rosout_topic, self._on_rosout, 100)

    def _on_odom(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def _on_cmd_vel_stamped(self, msg: TwistStamped) -> None:
        _ = msg
        self.cmd_vel_times.append(time.monotonic())

    def _on_cmd_vel(self, msg: Twist) -> None:
        _ = msg
        self.cmd_vel_times.append(time.monotonic())

    def _on_rosout(self, msg: Log) -> None:
        if msg.level < Log.ERROR:
            return
        name = (msg.name or '').lower()
        text = (msg.msg or '').lower()
        if 'planner' in name or 'planner_server' in text:
            self.planner_errors += 1
        if 'controller' in name or 'controller_server' in text:
            self.controller_errors += 1

    def wait_for_server(self, timeout_s: float) -> bool:
        return bool(self._nav_client.wait_for_server(timeout_sec=max(timeout_s, 0.1)))

    def wait_for_odom(self, timeout_s: float, sample_interval_s: float) -> bool:
        end = time.monotonic() + max(timeout_s, 0.1)
        while time.monotonic() < end and rclpy.ok():
            if self.latest_odom is not None:
                return True
            rclpy.spin_once(self, timeout_sec=sample_interval_s)
        return self.latest_odom is not None

    def _wait_future(self, future, timeout_s: float):
        end = time.monotonic() + max(timeout_s, 0.1)
        while time.monotonic() < end and rclpy.ok():
            if future.done():
                return True
            rclpy.spin_once(self, timeout_sec=0.1)
        return future.done()

    def _final_distance(self, goal_x: float, goal_y: float) -> Optional[float]:
        if self.latest_odom is None:
            return None
        dx = float(self.latest_odom.pose.pose.position.x) - goal_x
        dy = float(self.latest_odom.pose.pose.position.y) - goal_y
        return math.hypot(dx, dy)

    def run_goal(self, scenario_id: str, goal_x: float, goal_y: float, goal_yaw: float, timeout_s: float) -> GoalRunResult:
        before_cmd_vel = len(self.cmd_vel_times)
        started = time.monotonic()

        goal = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = self._frame_id
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(goal_x)
        pose.pose.position.y = float(goal_y)
        pose.pose.position.z = 0.0
        qx, qy, qz, qw = yaw_to_quaternion(float(goal_yaw))
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        goal.pose = pose

        send_future = self._nav_client.send_goal_async(goal)
        if not self._wait_future(send_future, timeout_s=5.0):
            elapsed = time.monotonic() - started
            return GoalRunResult(
                scenario_id=scenario_id,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_yaw=goal_yaw,
                accepted=False,
                success=False,
                status_code=int(GoalStatus.STATUS_UNKNOWN),
                elapsed_s=elapsed,
                final_distance_m=self._final_distance(goal_x, goal_y),
                cmd_vel_message_count=len(self.cmd_vel_times) - before_cmd_vel,
                attempts=1,
                error='send_goal_timeout',
            )

        goal_handle = send_future.result()
        if goal_handle is None:
            elapsed = time.monotonic() - started
            return GoalRunResult(
                scenario_id=scenario_id,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_yaw=goal_yaw,
                accepted=False,
                success=False,
                status_code=int(GoalStatus.STATUS_UNKNOWN),
                elapsed_s=elapsed,
                final_distance_m=self._final_distance(goal_x, goal_y),
                cmd_vel_message_count=len(self.cmd_vel_times) - before_cmd_vel,
                attempts=1,
                error='send_goal_result_none',
            )

        if not goal_handle.accepted:
            elapsed = time.monotonic() - started
            return GoalRunResult(
                scenario_id=scenario_id,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_yaw=goal_yaw,
                accepted=False,
                success=False,
                status_code=int(GoalStatus.STATUS_REJECTED),
                elapsed_s=elapsed,
                final_distance_m=self._final_distance(goal_x, goal_y),
                cmd_vel_message_count=len(self.cmd_vel_times) - before_cmd_vel,
                attempts=1,
                error='goal_rejected',
            )

        result_future = goal_handle.get_result_async()
        done = self._wait_future(result_future, timeout_s=timeout_s)
        if not done:
            goal_handle.cancel_goal_async()
            elapsed = time.monotonic() - started
            return GoalRunResult(
                scenario_id=scenario_id,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_yaw=goal_yaw,
                accepted=True,
                success=False,
                status_code=int(GoalStatus.STATUS_ABORTED),
                elapsed_s=elapsed,
                final_distance_m=self._final_distance(goal_x, goal_y),
                cmd_vel_message_count=len(self.cmd_vel_times) - before_cmd_vel,
                attempts=1,
                error='goal_result_timeout',
            )

        result = result_future.result()
        status_code = int(result.status) if result is not None else int(GoalStatus.STATUS_UNKNOWN)
        elapsed = time.monotonic() - started
        success = status_code == int(GoalStatus.STATUS_SUCCEEDED)
        return GoalRunResult(
            scenario_id=scenario_id,
            goal_x=goal_x,
            goal_y=goal_y,
            goal_yaw=goal_yaw,
            accepted=True,
            success=success,
            status_code=status_code,
            elapsed_s=elapsed,
            final_distance_m=self._final_distance(goal_x, goal_y),
            cmd_vel_message_count=len(self.cmd_vel_times) - before_cmd_vel,
            attempts=1,
            error='' if success else f'goal_status_{status_code}',
        )


def ensure_output_dir(base_output_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_dir = base_output_dir / ts
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Run deterministic multi-target Nav2 readiness checks.')
    parser.add_argument(
        '--config',
        default=str(repo_root / 'ros2_config' / 'config' / 'multi_target_nav2.yaml'),
        help='Path to multi-target Nav2 config YAML.',
    )
    parser.add_argument(
        '--output-base',
        default=str(repo_root / 'artifacts' / 'nav2_multi'),
        help='Base output directory where run timestamp folder will be created.',
    )
    parser.add_argument(
        '--goal-timeout-s',
        type=float,
        default=None,
        help='Override per-goal timeout in seconds.',
    )
    parser.add_argument(
        '--runtime-target',
        default='robot_fidelity_orin',
        help='Runtime target label for summary output.',
    )
    parser.add_argument(
        '--profile',
        default='compat',
        help='Profile label for summary output.',
    )
    parser.add_argument(
        '--inference-device',
        default='auto',
        help='Inference device label for summary output.',
    )
    parser.add_argument(
        '--use-sim-time',
        action='store_true',
        default=True,
        help='Enable use_sim_time for this runner node (default: true).',
    )
    parser.add_argument(
        '--no-use-sim-time',
        dest='use_sim_time',
        action='store_false',
        help='Disable use_sim_time for this runner node.',
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
    scenarios = cfg.get('scenarios', [])

    action_name = str(metadata.get('action_name', '/navigate_to_pose'))
    frame_id = str(metadata.get('frame_id', 'map'))
    odom_topic = str(metadata.get('odom_topic', '/odom'))
    cmd_vel_topic_primary = str(metadata.get('cmd_vel_topic_primary', '/jetbot_base_controller/cmd_vel'))
    cmd_vel_topic_secondary = str(metadata.get('cmd_vel_topic_secondary', '/cmd_vel'))
    rosout_topic = str(metadata.get('rosout_topic', '/rosout'))

    warmup_s = float(defaults.get('warmup_s', 8.0))
    goal_timeout_s = float(args.goal_timeout_s if args.goal_timeout_s is not None else defaults.get('goal_timeout_s', 55.0))
    goal_retry_count = int(defaults.get('goal_retry_count', 1))
    goal_retry_delay_s = float(defaults.get('goal_retry_delay_s', 1.5))
    settle_after_goal_s = float(defaults.get('settle_after_goal_s', 1.5))
    warmup_wait_for_odom_s = float(defaults.get('warmup_wait_for_odom_s', 10.0))
    sample_interval_s = float(defaults.get('sample_interval_s', 0.1))
    min_cmd_vel_hz = float(defaults.get('min_cmd_vel_hz', 1.0))
    max_cmd_vel_gap_s = float(defaults.get('max_cmd_vel_gap_s', 2.0))

    out_base = Path(args.output_base).resolve()
    out_dir = ensure_output_dir(out_base)
    samples_csv = out_dir / 'multi_target_samples.csv'
    summary_json = out_dir / 'multi_target_summary.json'

    rclpy.init()
    node = MultiTargetRunner(
        action_name=action_name,
        frame_id=frame_id,
        odom_topic=odom_topic,
        cmd_vel_topic_primary=cmd_vel_topic_primary,
        cmd_vel_topic_secondary=cmd_vel_topic_secondary,
        rosout_topic=rosout_topic,
    )

    if args.use_sim_time:
        node.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])

    warmup_deadline = time.monotonic() + max(warmup_s, 0.0)
    while time.monotonic() < warmup_deadline and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=sample_interval_s)

    if not node.wait_for_server(timeout_s=30.0):
        summary = {
            'run_id': out_dir.name,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'runtime_target': args.runtime_target,
            'profile': args.profile,
            'inference_device_resolved': args.inference_device,
            'goal_count': len(scenarios),
            'status': 'action_server_unavailable',
            'pass': False,
        }
        with summary_json.open('w', encoding='utf-8') as fp:
            json.dump(summary, fp, indent=2, sort_keys=True)
            fp.write('\n')
        node.destroy_node()
        rclpy.shutdown()
        print(f'Wrote {summary_json}')
        print('Overall pass: False')
        return 2

    node.wait_for_odom(timeout_s=warmup_wait_for_odom_s, sample_interval_s=sample_interval_s)

    results: List[GoalRunResult] = []
    for scenario in scenarios:
        scenario_id = str(scenario.get('id', f'target_{len(results)+1}'))
        goal = scenario.get('goal', {})
        goal_x = float(goal.get('x', 0.0))
        goal_y = float(goal.get('y', 0.0))
        goal_yaw = float(goal.get('yaw', 0.0))

        attempts = 0
        run_result: Optional[GoalRunResult] = None
        while attempts <= max(goal_retry_count, 0) and rclpy.ok():
            attempts += 1
            candidate = node.run_goal(
                scenario_id=scenario_id,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_yaw=goal_yaw,
                timeout_s=goal_timeout_s,
            )
            candidate.attempts = attempts
            run_result = candidate
            if candidate.success:
                break
            if attempts <= max(goal_retry_count, 0):
                retry_end = time.monotonic() + max(goal_retry_delay_s, 0.0)
                while time.monotonic() < retry_end and rclpy.ok():
                    rclpy.spin_once(node, timeout_sec=sample_interval_s)

        if run_result is None:
            run_result = GoalRunResult(
                scenario_id=scenario_id,
                goal_x=goal_x,
                goal_y=goal_y,
                goal_yaw=goal_yaw,
                accepted=False,
                success=False,
                status_code=int(GoalStatus.STATUS_UNKNOWN),
                elapsed_s=0.0,
                final_distance_m=None,
                cmd_vel_message_count=0,
                attempts=attempts,
                error='runner_internal_error',
            )
        results.append(run_result)

        settle_end = time.monotonic() + max(settle_after_goal_s, 0.0)
        while time.monotonic() < settle_end and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=sample_interval_s)

    with samples_csv.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                'scenario_id',
                'goal_x',
                'goal_y',
                'goal_yaw',
                'accepted',
                'success',
                'status_code',
                'elapsed_s',
                'final_distance_m',
                'cmd_vel_message_count',
                'attempts',
                'error',
            ],
        )
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    'scenario_id': row.scenario_id,
                    'goal_x': row.goal_x,
                    'goal_y': row.goal_y,
                    'goal_yaw': row.goal_yaw,
                    'accepted': row.accepted,
                    'success': row.success,
                    'status_code': row.status_code,
                    'elapsed_s': row.elapsed_s,
                    'final_distance_m': row.final_distance_m,
                    'cmd_vel_message_count': row.cmd_vel_message_count,
                    'attempts': row.attempts,
                    'error': row.error,
                }
            )

    goal_count = len(results)
    accepted = len([r for r in results if r.accepted])
    succeeded = len([r for r in results if r.success])
    final_distances = [
        float(r.final_distance_m)
        for r in results
        if r.final_distance_m is not None and math.isfinite(float(r.final_distance_m))
    ]

    goal_accept_rate = accepted / goal_count if goal_count else 0.0
    goal_success_rate = succeeded / accepted if accepted else 0.0
    median_final_distance = statistics.median(final_distances) if final_distances else float('inf')

    cmd_vel_stats = compute_rate_and_longest_gap(node.cmd_vel_times)
    cmd_vel_publish_stability = score_from_rate_and_gap(
        rate=cmd_vel_stats['rate_hz'],
        min_rate=min_cmd_vel_hz,
        longest_gap=cmd_vel_stats['longest_gap_s'],
        max_gap=max_cmd_vel_gap_s,
    )

    summary = {
        'run_id': out_dir.name,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'runtime_target': args.runtime_target,
        'profile': args.profile,
        'inference_device_resolved': args.inference_device,
        'goal_count': goal_count,
        'goal_accept_count': accepted,
        'goal_success_count': succeeded,
        'goal_accept_rate': goal_accept_rate,
        'goal_success_rate': goal_success_rate,
        'median_final_distance_m': median_final_distance,
        'cmd_vel_publish_stability': cmd_vel_publish_stability,
        'cmd_vel_stats': cmd_vel_stats,
        'planner/controller_error_counts': {
            'planner': node.planner_errors,
            'controller': node.controller_errors,
        },
        'thresholds': {
            'goal_accept_rate_min': float(thresholds.get('goal_accept_rate_min', 0.90)),
            'goal_success_rate_min': float(thresholds.get('goal_success_rate_min', 0.80)),
            'median_final_distance_max_m': float(thresholds.get('median_final_distance_max_m', 0.35)),
            'cmd_vel_publish_stability_min': float(thresholds.get('cmd_vel_publish_stability_min', 0.70)),
            'planner_errors_max': int(thresholds.get('planner_errors_max', 0)),
            'controller_errors_max': int(thresholds.get('controller_errors_max', 0)),
        },
    }

    summary['pass'] = (
        summary['goal_accept_rate'] >= summary['thresholds']['goal_accept_rate_min']
        and summary['goal_success_rate'] >= summary['thresholds']['goal_success_rate_min']
        and summary['median_final_distance_m'] <= summary['thresholds']['median_final_distance_max_m']
        and summary['cmd_vel_publish_stability'] >= summary['thresholds']['cmd_vel_publish_stability_min']
        and summary['planner/controller_error_counts']['planner'] <= summary['thresholds']['planner_errors_max']
        and summary['planner/controller_error_counts']['controller'] <= summary['thresholds']['controller_errors_max']
    )

    with summary_json.open('w', encoding='utf-8') as fp:
        json.dump(summary, fp, indent=2, sort_keys=True)
        fp.write('\n')

    print(f'Wrote {samples_csv}')
    print(f'Wrote {summary_json}')
    print(f'Overall pass: {summary["pass"]}')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if summary['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
