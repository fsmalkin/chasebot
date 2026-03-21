#!/usr/bin/env python3
"""
Coordinate UAT runner for the chasecar/chasebot simulation stack.

Outputs:
- artifacts/uat/<timestamp>/detections.csv
- artifacts/uat/<timestamp>/summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import yaml

import rclpy
from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter


FAILURE_NO_DETECTION = 'no_detection'
FAILURE_INVALID_DEPTH = 'invalid_depth'
FAILURE_STALE_TOPIC = 'stale_topic'
FAILURE_TRANSFORM = 'transform_failure'


@dataclass
class DetectionResult:
    status: str
    failure_class: str
    measured_x_m: Optional[float]
    measured_z_m: Optional[float]
    frame_id: str
    sample_count: int
    latency_s: float
    elapsed_s: float


class TopicMonitor(Node):
    def __init__(self, detection_topic: str):
        super().__init__('coordinate_uat_runner')
        self.latest_detection: Optional[PointStamped] = None
        self.latest_detection_mono = 0.0
        self.latest_odom: Optional[Odometry] = None

        self.create_subscription(
            PointStamped,
            detection_topic,
            self._on_detection,
            10,
        )
        self.create_subscription(
            Odometry,
            '/odom',
            self._on_odom,
            10,
        )

    def _on_detection(self, msg: PointStamped) -> None:
        self.latest_detection = msg
        self.latest_detection_mono = time.monotonic()

    def _on_odom(self, msg: Odometry) -> None:
        self.latest_odom = msg


def percentile(values: List[float], p: float) -> float:
    if not values:
        return float('inf')
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    ratio = rank - low
    return sorted_values[low] * (1.0 - ratio) + sorted_values[high] * ratio


def resolve_path(path_str: str, config_path: Path, repo_root: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    candidate_repo = repo_root / path
    if candidate_repo.exists():
        return candidate_repo
    return (config_path.parent / path).resolve()


def stamp_to_seconds(stamp) -> float:
    return float(stamp.sec) + (float(stamp.nanosec) / 1e9)


def run_command(cmd: List[str], timeout_s: float = 20.0) -> Tuple[int, str, str]:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode('utf-8', errors='ignore') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
        stderr = exc.stderr.decode('utf-8', errors='ignore') if isinstance(exc.stderr, bytes) else (exc.stderr or '')
        return 124, stdout.strip(), stderr.strip()


def sim_service_binary() -> Optional[str]:
    for candidate in ('gz', 'ign'):
        if shutil.which(candidate):
            return candidate
    return None


def remove_model(
    world_name: str,
    model_name: str,
    timeout_s: float = 5.0,
    verbose: bool = False,
) -> Tuple[bool, str]:
    service_bin = sim_service_binary()
    if service_bin is None:
        return False, 'gz/ign service binary not found'

    # Gazebo remove expects an Entity with model type; type 0 (NONE) won't remove by name.
    req = f'name: "{model_name}" type: 2'
    cmd = [
        service_bin,
        'service',
        '-s',
        f'/world/{world_name}/remove/blocking',
        '--reqtype',
        'gz.msgs.Entity',
        '--reptype',
        'gz.msgs.Boolean',
        '--timeout',
        str(max(1000, int(timeout_s * 1000))),
        '--req',
        req,
    ]
    rc, out, err = run_command(cmd, timeout_s=timeout_s)
    if verbose and out:
        print(out)
    if rc != 0:
        return False, err or out or f'remove command failed with exit code {rc}'
    if 'data: true' not in (out or '').lower():
        return False, out or 'remove returned false'
    return True, out or 'remove requested'


def spawn_target(
    model_sdf: Path,
    model_name: str,
    world_name: str,
    scenario: Dict,
    verbose: bool = False,
) -> Tuple[bool, str]:
    spawn = scenario.get('spawn_world', {})
    x = float(spawn.get('x', 0.0))
    y = float(spawn.get('y', 0.0))
    z = float(spawn.get('z', 0.025))

    def build_cmd(include_world: bool) -> List[str]:
        cmd_local = [
            'ros2',
            'run',
            'ros_gz_sim',
            'create',
        ]
        if include_world and world_name:
            cmd_local += ['-world', world_name]
        cmd_local += [
            '-file',
            str(model_sdf),
            '-name',
            model_name,
            '-x',
            str(x),
            '-y',
            str(y),
            '-z',
            str(z),
        ]
        return cmd_local

    rc, out, err = run_command(build_cmd(include_world=True), timeout_s=20.0)
    if verbose and out:
        print(out)
    if rc != 0:
        combined = f'{out}\n{err}'.lower()
        if (
            '/create] to become available' in combined
            or 'service unavailable' in combined
        ):
            # Gazebo Sim 9 exposes /create_multiple services; retry without -world
            rc_fb, out_fb, err_fb = run_command(build_cmd(include_world=False), timeout_s=20.0)
            if verbose and out_fb:
                print(out_fb)
            if rc_fb == 0:
                combined_fb = f'{out_fb}\n{err_fb}'.lower()
                if 'already exists' in combined_fb:
                    return False, err_fb or out_fb or 'model already exists'
                return True, out_fb or 'spawned (fallback no-world)'
            msg_fb = err_fb or out_fb or f'fallback create command failed with exit code {rc_fb}'
            msg = err or out or f'create command failed with exit code {rc}'
            return False, f'{msg}; fallback_no_world={msg_fb}'
        msg = err or out or f'create command failed with exit code {rc}'
        return False, msg
    combined = f'{out}\n{err}'.lower()
    if 'already exists' in combined:
        return False, err or out or 'model already exists'
    return True, out or 'spawned'


def set_model_pose(
    world_name: str,
    model_name: str,
    scenario: Dict,
    timeout_s: float = 5.0,
) -> Tuple[bool, str]:
    service_bin = sim_service_binary()
    if service_bin is None:
        return False, 'gz/ign service binary not found'

    spawn = scenario.get('spawn_world', {})
    x = float(spawn.get('x', 0.0))
    y = float(spawn.get('y', 0.0))
    z = float(spawn.get('z', 0.025))
    yaw = float(spawn.get('yaw', 0.0))
    half_yaw = 0.5 * yaw
    qz = math.sin(half_yaw)
    qw = math.cos(half_yaw)

    req = (
        f'name: "{model_name}" '
        f'position {{ x: {x} y: {y} z: {z} }} '
        f'orientation {{ x: 0 y: 0 z: {qz} w: {qw} }}'
    )
    cmd = [
        service_bin,
        'service',
        '-s',
        f'/world/{world_name}/set_pose/blocking',
        '--reqtype',
        'gz.msgs.Pose',
        '--reptype',
        'gz.msgs.Boolean',
        '--timeout',
        str(max(1000, int(timeout_s * 1000))),
        '--req',
        req,
    ]
    rc, out, err = run_command(cmd, timeout_s=timeout_s)
    if rc != 0:
        return False, err or out or f'set_pose failed with code {rc}'
    if 'data: true' not in (out or '').lower():
        return False, out or 'set_pose returned false'
    return True, out or 'set_pose requested'


def position_target_with_fallback(
    world_name: str,
    model_name: str,
    scenario: Dict,
    model_sdf: Path,
    set_pose_timeout_s: float,
    set_pose_retries: int,
    set_pose_retry_sleep_s: float,
    respawn_on_failure: bool,
    remove_timeout_s: float,
) -> Tuple[bool, str]:
    retries = max(1, set_pose_retries)
    messages: List[str] = []
    for _ in range(retries):
        ok, msg = set_model_pose(
            world_name=world_name,
            model_name=model_name,
            scenario=scenario,
            timeout_s=set_pose_timeout_s,
        )
        messages.append(msg)
        if ok:
            return True, msg
        time.sleep(max(0.0, set_pose_retry_sleep_s))

    if not respawn_on_failure:
        return False, '; '.join(messages)

    remove_ok, remove_msg = remove_model(
        world_name=world_name,
        model_name=model_name,
        timeout_s=remove_timeout_s,
    )
    spawn_ok, spawn_msg = spawn_target(
        model_sdf=model_sdf,
        model_name=model_name,
        world_name=world_name,
        scenario=scenario,
    )
    if not spawn_ok:
        return False, f'set_pose failed ({messages[-1]}), remove={remove_msg}, spawn={spawn_msg}'
    return True, f'set_pose fallback respawn (remove_ok={remove_ok}): {spawn_msg}'


def wait_for_stable_detection(
    node: TopicMonitor,
    timeout_s: float,
    stale_after_s: float,
    stabilization_samples: int,
    stabilization_window_s: float,
    expected_frame: str,
    min_detection_mono: float,
    min_detection_stamp_s: float,
) -> DetectionResult:
    start_mono = time.monotonic()
    samples: List[Tuple[float, float, float, str]] = []
    first_fresh_detection_mono: Optional[float] = None
    saw_detection = False
    stamp_gate_enabled = min_detection_stamp_s > 0.0
    stamp_domain_checked = False

    while time.monotonic() - start_mono < timeout_s and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)

        msg = node.latest_detection
        if msg is None:
            continue

        saw_detection = True
        age_s = time.monotonic() - node.latest_detection_mono
        if age_s > stale_after_s:
            continue
        if node.latest_detection_mono < min_detection_mono:
            continue
        if stamp_gate_enabled:
            msg_stamp_s = stamp_to_seconds(msg.header.stamp)
            if msg_stamp_s > 0.0:
                if not stamp_domain_checked:
                    stamp_domain_checked = True
                    # Handle wall-clock vs sim-clock mismatch by falling back to monotonic freshness.
                    if abs(msg_stamp_s - min_detection_stamp_s) > 300.0:
                        stamp_gate_enabled = False
                if stamp_gate_enabled and msg_stamp_s + 1e-6 < min_detection_stamp_s:
                    continue

        if first_fresh_detection_mono is None:
            first_fresh_detection_mono = node.latest_detection_mono

        frame_id = msg.header.frame_id or ''
        if expected_frame and frame_id and expected_frame not in frame_id:
            elapsed = time.monotonic() - start_mono
            return DetectionResult(
                status='fail',
                failure_class=FAILURE_TRANSFORM,
                measured_x_m=None,
                measured_z_m=None,
                frame_id=frame_id,
                sample_count=0,
                latency_s=first_fresh_detection_mono - start_mono,
                elapsed_s=elapsed,
            )

        x_m = float(msg.point.x)
        z_m = float(msg.point.z)
        if not math.isfinite(x_m) or not math.isfinite(z_m):
            elapsed = time.monotonic() - start_mono
            return DetectionResult(
                status='fail',
                failure_class=FAILURE_TRANSFORM,
                measured_x_m=None,
                measured_z_m=None,
                frame_id=frame_id,
                sample_count=0,
                latency_s=(first_fresh_detection_mono or start_mono) - start_mono,
                elapsed_s=elapsed,
            )
        if z_m <= 0.01 or z_m > 10.0:
            elapsed = time.monotonic() - start_mono
            return DetectionResult(
                status='fail',
                failure_class=FAILURE_INVALID_DEPTH,
                measured_x_m=x_m,
                measured_z_m=z_m,
                frame_id=frame_id,
                sample_count=1,
                latency_s=(first_fresh_detection_mono or start_mono) - start_mono,
                elapsed_s=elapsed,
            )

        if not samples or node.latest_detection_mono > samples[-1][0]:
            samples.append((node.latest_detection_mono, x_m, z_m, frame_id))

        newest_mono = samples[-1][0]
        samples = [s for s in samples if newest_mono - s[0] <= stabilization_window_s]

        if len(samples) >= stabilization_samples:
            measured_x = statistics.median([s[1] for s in samples])
            measured_z = statistics.median([s[2] for s in samples])
            elapsed = time.monotonic() - start_mono
            return DetectionResult(
                status='pass',
                failure_class='',
                measured_x_m=measured_x,
                measured_z_m=measured_z,
                frame_id=samples[-1][3],
                sample_count=len(samples),
                latency_s=(first_fresh_detection_mono or start_mono) - start_mono,
                elapsed_s=elapsed,
            )

    elapsed = time.monotonic() - start_mono
    if saw_detection and node.latest_detection is not None:
        failure = FAILURE_STALE_TOPIC
    else:
        failure = FAILURE_NO_DETECTION
    return DetectionResult(
        status='fail',
        failure_class=failure,
        measured_x_m=None,
        measured_z_m=None,
        frame_id='',
        sample_count=0,
        latency_s=elapsed,
        elapsed_s=elapsed,
    )


def observe_navigation_distance(
    node: TopicMonitor,
    truth_world: Dict,
    timeout_s: float,
) -> Optional[float]:
    start = time.monotonic()
    min_distance = float('inf')
    got_odom = False
    truth_x = float(truth_world.get('x', 0.0))
    truth_y = float(truth_world.get('y', 0.0))

    while time.monotonic() - start < timeout_s and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)
        odom = node.latest_odom
        if odom is None:
            continue
        got_odom = True
        dx = odom.pose.pose.position.x - truth_x
        dy = odom.pose.pose.position.y - truth_y
        dist = math.hypot(dx, dy)
        if dist < min_distance:
            min_distance = dist

    if not got_odom:
        return None
    return min_distance


def ensure_output_dir(base_output_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output_dir = base_output_dir / ts
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def write_csv(path: Path, rows: List[Dict]) -> None:
    columns = [
        'scenario_id',
        'status',
        'failure_class',
        'spawn_x_m',
        'spawn_y_m',
        'spawn_z_m',
        'truth_x_m',
        'truth_z_m',
        'measured_x_m',
        'measured_z_m',
        'error_xy_m',
        'latency_s',
        'elapsed_s',
        'sample_count',
        'frame_id',
        'spawn_ok',
        'spawn_message',
        'nav_min_distance_m',
        'nav_success',
    ]
    with path.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_summary(
    run_id: str,
    timestamp_utc: str,
    rows: List[Dict],
    thresholds: Dict,
    runtime_target: str,
    profile: str,
    inference_device: str,
    navigation_thresholds: Dict,
    evaluate_navigation: bool,
) -> Dict:
    total = len(rows)
    passes = [r for r in rows if r['status'] == 'pass']
    errors = [float(r['error_xy_m']) for r in passes if r['error_xy_m'] not in ('', None)]
    success_rate = (len(passes) / total) if total else 0.0
    mean_xy = statistics.fmean(errors) if errors else float('inf')
    p95_xy = percentile(errors, 95.0) if errors else float('inf')
    max_timeout = max((float(r['elapsed_s']) for r in rows), default=0.0)

    failure_counts = {
        FAILURE_NO_DETECTION: 0,
        FAILURE_INVALID_DEPTH: 0,
        FAILURE_STALE_TOPIC: 0,
        FAILURE_TRANSFORM: 0,
    }
    for row in rows:
        failure_class = row.get('failure_class') or ''
        if failure_class in failure_counts:
            failure_counts[failure_class] += 1

    pass_result = (
        success_rate >= float(thresholds.get('detection_success_rate_min', 0.90))
        and mean_xy <= float(thresholds.get('mean_xy_error_max_m', 0.25))
        and p95_xy <= float(thresholds.get('p95_xy_error_max_m', 0.40))
        and max_timeout <= float(thresholds.get('max_timeout_s', 20.0))
    )

    nav_summary = {}
    if evaluate_navigation:
        nav_distances = [
            float(r['nav_min_distance_m'])
            for r in rows
            if r.get('nav_min_distance_m') not in ('', None)
        ]
        nav_successes = [r for r in rows if str(r.get('nav_success')).lower() == 'true']
        nav_success_rate = (len(nav_successes) / total) if total else 0.0
        nav_median_distance = statistics.median(nav_distances) if nav_distances else float('inf')
        nav_pass = (
            nav_success_rate >= float(navigation_thresholds.get('approach_success_rate_min', 0.80))
            and nav_median_distance <= float(navigation_thresholds.get('median_final_distance_max_m', 0.35))
        )
        nav_summary = {
            'enabled': True,
            'approach_success_rate': nav_success_rate,
            'median_final_distance_m': nav_median_distance,
            'pass': nav_pass,
        }
        pass_result = pass_result and nav_pass

    return {
        'run_id': run_id,
        'timestamp_utc': timestamp_utc,
        'runtime_target': runtime_target,
        'profile': profile,
        'inference_device_resolved': inference_device,
        'scenario_count': total,
        'detection_success_rate': success_rate,
        'mean_xy_error_m': mean_xy,
        'p95_xy_error_m': p95_xy,
        'max_timeout_s': max_timeout,
        'thresholds': {
            'detection_success_rate_min': float(thresholds.get('detection_success_rate_min', 0.90)),
            'mean_xy_error_max_m': float(thresholds.get('mean_xy_error_max_m', 0.25)),
            'p95_xy_error_max_m': float(thresholds.get('p95_xy_error_max_m', 0.40)),
            'max_timeout_s': float(thresholds.get('max_timeout_s', 20.0)),
        },
        'failure_counts': failure_counts,
        'navigation': nav_summary,
        'pass': pass_result,
    }


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Run deterministic coordinate UAT scenarios.')
    parser.add_argument(
        '--config',
        default=str(repo_root / 'ros2_config' / 'config' / 'uat_coordinates.yaml'),
        help='Path to UAT scenario YAML.',
    )
    parser.add_argument(
        '--output-base',
        default=str(repo_root / 'artifacts' / 'uat'),
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
    parser.add_argument(
        '--skip-spawn',
        action='store_true',
        help='Skip spawn commands and only evaluate detections against scenarios.',
    )
    parser.add_argument(
        '--evaluate-navigation',
        action='store_true',
        help='Collect optional navigation approach metrics from /odom.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose command output.',
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
    repo_root = Path(__file__).resolve().parents[1]
    config_path = Path(args.config).resolve()

    with config_path.open('r', encoding='utf-8') as fp:
        cfg = yaml.safe_load(fp)

    metadata = cfg.get('metadata', {})
    defaults = cfg.get('defaults', {})
    thresholds = cfg.get('thresholds', {})
    navigation_thresholds = cfg.get('navigation_thresholds', {})
    scenarios = cfg.get('scenarios', [])
    detection_topic = metadata.get('detection_topic', '/yolo/ball_position_3d')
    expected_frame = metadata.get('truth_frame', '')
    world_name = str(metadata.get('world_name', 'yolo_test_world'))
    cleanup_between_scenarios = bool(defaults.get('cleanup_between_scenarios', True))
    cleanup_model_names = [
        str(name)
        for name in metadata.get(
            'cleanup_model_names',
            [
                'red_ball_forward',
                'blue_ball_left',
                'yellow_ball_right',
                'white_ball_behind',
                'green_ball_behind',
            ],
        )
    ]
    target_model_name = str(metadata.get('target_model_name', 'uat_ball_target'))

    output_base = Path(args.output_base).resolve()
    output_dir = ensure_output_dir(output_base)
    detections_csv = output_dir / 'detections.csv'
    summary_json = output_dir / 'summary.json'

    model_sdf = resolve_path(
        metadata.get('model_sdf', 'ros2_config/green_golf_ball.sdf'),
        config_path,
        repo_root,
    )

    print(f'Running coordinate UAT with {len(scenarios)} scenarios')
    print(f'Config: {config_path}')
    print(f'Output: {output_dir}')
    print(f'Detection topic: {detection_topic}')
    print(f'Model SDF: {model_sdf}')
    print(f'World: {world_name}')

    rclpy.init()
    node = TopicMonitor(detection_topic=detection_topic)
    if args.use_sim_time:
        node.set_parameters(
            [Parameter('use_sim_time', Parameter.Type.BOOL, True)]
        )

    rows: List[Dict] = []
    warmup_s = float(defaults.get('warmup_s', 2.0))
    post_spawn_settle_s = float(defaults.get('post_spawn_settle_s', 0.75))
    spawn_strategy = str(defaults.get('spawn_strategy', 'set_pose')).strip().lower()
    if spawn_strategy not in {'set_pose', 'respawn'}:
        spawn_strategy = 'set_pose'
    remove_timeout_s = float(defaults.get('remove_timeout_s', 5.0))
    set_pose_timeout_s = float(defaults.get('set_pose_timeout_s', 5.0))
    set_pose_retries = int(defaults.get('set_pose_retries', 3))
    set_pose_retry_sleep_s = float(defaults.get('set_pose_retry_sleep_s', 0.2))
    respawn_on_set_pose_failure = bool(defaults.get('respawn_on_set_pose_failure', True))

    if warmup_s > 0:
        warmup_end = time.monotonic() + warmup_s
        while time.monotonic() < warmup_end and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)

    spawned_once_ok = True
    spawned_once_message = 'skipped'
    if not args.skip_spawn and spawn_strategy == 'set_pose':
        if cleanup_between_scenarios:
            remove_model(
                world_name=world_name,
                model_name=target_model_name,
                timeout_s=remove_timeout_s,
                verbose=args.verbose,
            )
            for cleanup_name in cleanup_model_names:
                if cleanup_name != target_model_name:
                    remove_model(
                        world_name=world_name,
                        model_name=cleanup_name,
                        timeout_s=remove_timeout_s,
                        verbose=args.verbose,
                    )

        initial_scenario: Dict = scenarios[0] if scenarios else {'spawn_world': {'x': 1.5, 'y': 0.0, 'z': 0.05}}
        spawned_once_ok, spawned_once_message = spawn_target(
            model_sdf=model_sdf,
            model_name=target_model_name,
            world_name=world_name,
            scenario=initial_scenario,
            verbose=args.verbose,
        )
        if (
            not spawned_once_ok
            and 'already exists' in (spawned_once_message or '').lower()
            and cleanup_between_scenarios
        ):
            remove_model(
                world_name=world_name,
                model_name=target_model_name,
                timeout_s=remove_timeout_s,
                verbose=args.verbose,
            )
            spawned_once_ok, spawned_once_message = spawn_target(
                model_sdf=model_sdf,
                model_name=target_model_name,
                world_name=world_name,
                scenario=initial_scenario,
                verbose=args.verbose,
            )
        if args.verbose:
            print(f'initial spawn_ok={spawned_once_ok} message={spawned_once_message}')

    for index, scenario in enumerate(scenarios):
        scenario_id = scenario.get('id', f'scenario_{index + 1}')
        timeout_s = float(scenario.get('timeout_s', defaults.get('timeout_s', 20.0)))
        stale_after_s = float(defaults.get('stale_after_s', 1.0))
        stabilization_samples = int(defaults.get('stabilization_samples', 8))
        stabilization_window_s = float(defaults.get('stabilization_window_s', 1.5))

        spawn = scenario.get('spawn_world', {})
        truth = scenario.get('truth_camera', {})
        truth_x = float(truth.get('x_m', 0.0))
        truth_z = float(truth.get('z_m', 0.0))

        print(f'[{index + 1}/{len(scenarios)}] {scenario_id}')
        spawn_ok = True
        spawn_message = 'skipped'
        if not args.skip_spawn:
            if spawn_strategy == 'set_pose':
                if spawned_once_ok:
                    spawn_ok, spawn_message = position_target_with_fallback(
                        world_name=world_name,
                        model_name=target_model_name,
                        scenario=scenario,
                        model_sdf=model_sdf,
                        set_pose_timeout_s=set_pose_timeout_s,
                        set_pose_retries=set_pose_retries,
                        set_pose_retry_sleep_s=set_pose_retry_sleep_s,
                        respawn_on_failure=respawn_on_set_pose_failure,
                        remove_timeout_s=remove_timeout_s,
                    )
                else:
                    spawn_ok = False
                    spawn_message = f'initial spawn failed: {spawned_once_message}'
                if args.verbose:
                    print(f'  set_pose_ok={spawn_ok} message={spawn_message}')
            else:
                if cleanup_between_scenarios:
                    # Keep only deterministic UAT targets active.
                    remove_model(
                        world_name=world_name,
                        model_name=target_model_name,
                        timeout_s=remove_timeout_s,
                        verbose=args.verbose,
                    )
                    for cleanup_name in cleanup_model_names:
                        if cleanup_name != target_model_name:
                            remove_model(
                                world_name=world_name,
                                model_name=cleanup_name,
                                timeout_s=remove_timeout_s,
                                verbose=args.verbose,
                            )

                spawn_ok, spawn_message = spawn_target(
                    model_sdf=model_sdf,
                    model_name=target_model_name,
                    world_name=world_name,
                    scenario=scenario,
                    verbose=args.verbose,
                )
                if (
                    not spawn_ok
                    and 'already exists' in (spawn_message or '').lower()
                    and cleanup_between_scenarios
                ):
                    remove_model(
                        world_name=world_name,
                        model_name=target_model_name,
                        timeout_s=remove_timeout_s,
                        verbose=args.verbose,
                    )
                    spawn_ok, spawn_message = spawn_target(
                        model_sdf=model_sdf,
                        model_name=target_model_name,
                        world_name=world_name,
                        scenario=scenario,
                        verbose=args.verbose,
                    )
                if args.verbose:
                    print(f'  spawn_ok={spawn_ok} message={spawn_message}')
            if not spawn_ok:
                print(f'  spawn failed: {spawn_message}')

        if not spawn_ok:
            rows.append(
                {
                    'scenario_id': scenario_id,
                    'status': 'fail',
                    'failure_class': FAILURE_TRANSFORM,
                    'spawn_x_m': spawn.get('x', ''),
                    'spawn_y_m': spawn.get('y', ''),
                    'spawn_z_m': spawn.get('z', ''),
                    'truth_x_m': truth_x,
                    'truth_z_m': truth_z,
                    'measured_x_m': '',
                    'measured_z_m': '',
                    'error_xy_m': '',
                    'latency_s': '',
                    'elapsed_s': 0.0,
                    'sample_count': 0,
                    'frame_id': '',
                    'spawn_ok': False,
                    'spawn_message': spawn_message,
                    'nav_min_distance_m': '',
                    'nav_success': '',
                }
            )
            continue

        # Flush stale detections from the previous scenario before sampling.
        node.latest_detection = None
        node.latest_detection_mono = 0.0
        if post_spawn_settle_s > 0.0:
            settle_end = time.monotonic() + post_spawn_settle_s
            while time.monotonic() < settle_end and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.05)
        scenario_detection_min_mono = time.monotonic()
        scenario_detection_min_stamp_s = node.get_clock().now().nanoseconds / 1e9

        detection = wait_for_stable_detection(
            node=node,
            timeout_s=timeout_s,
            stale_after_s=stale_after_s,
            stabilization_samples=stabilization_samples,
            stabilization_window_s=stabilization_window_s,
            expected_frame=expected_frame,
            min_detection_mono=scenario_detection_min_mono,
            min_detection_stamp_s=scenario_detection_min_stamp_s,
        )

        measured_x = detection.measured_x_m
        measured_z = detection.measured_z_m
        error_xy = ''
        if detection.status == 'pass' and measured_x is not None and measured_z is not None:
            error_xy = math.hypot(measured_x - truth_x, measured_z - truth_z)

        nav_min_distance = ''
        nav_success = ''
        if args.evaluate_navigation and detection.status == 'pass':
            nav_timeout = float(navigation_thresholds.get('nav_observe_timeout_s', 20.0))
            nav_threshold = float(navigation_thresholds.get('median_final_distance_max_m', 0.35))
            nav_min_distance_value = observe_navigation_distance(
                node=node,
                truth_world=spawn,
                timeout_s=nav_timeout,
            )
            if nav_min_distance_value is not None:
                nav_min_distance = nav_min_distance_value
                nav_success = bool(nav_min_distance_value <= nav_threshold)

        rows.append(
            {
                'scenario_id': scenario_id,
                'status': detection.status,
                'failure_class': detection.failure_class,
                'spawn_x_m': spawn.get('x', ''),
                'spawn_y_m': spawn.get('y', ''),
                'spawn_z_m': spawn.get('z', ''),
                'truth_x_m': truth_x,
                'truth_z_m': truth_z,
                'measured_x_m': '' if measured_x is None else measured_x,
                'measured_z_m': '' if measured_z is None else measured_z,
                'error_xy_m': error_xy,
                'latency_s': detection.latency_s,
                'elapsed_s': detection.elapsed_s,
                'sample_count': detection.sample_count,
                'frame_id': detection.frame_id,
                'spawn_ok': True,
                'spawn_message': spawn_message,
                'nav_min_distance_m': nav_min_distance,
                'nav_success': nav_success,
            }
        )

        if cleanup_between_scenarios and not args.skip_spawn and spawn_strategy != 'set_pose':
            remove_model(
                world_name=world_name,
                model_name=target_model_name,
                timeout_s=remove_timeout_s,
                verbose=args.verbose,
            )

    if cleanup_between_scenarios and not args.skip_spawn and spawn_strategy == 'set_pose':
        remove_model(
            world_name=world_name,
            model_name=target_model_name,
            timeout_s=remove_timeout_s,
            verbose=args.verbose,
        )

    run_id = output_dir.name
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    summary = build_summary(
        run_id=run_id,
        timestamp_utc=timestamp_utc,
        rows=rows,
        thresholds=thresholds,
        runtime_target=args.runtime_target,
        profile=args.profile,
        inference_device=args.inference_device,
        navigation_thresholds=navigation_thresholds,
        evaluate_navigation=args.evaluate_navigation,
    )

    write_csv(detections_csv, rows)
    with summary_json.open('w', encoding='utf-8') as fp:
        json.dump(summary, fp, indent=2, sort_keys=True)
        fp.write('\n')

    print(f'Wrote {detections_csv}')
    print(f'Wrote {summary_json}')
    print(f'Overall pass: {summary["pass"]}')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if summary['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
