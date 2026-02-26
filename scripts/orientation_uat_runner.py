#!/usr/bin/env python3
"""
Headless orientation UAT runner.

Outputs:
- artifacts/orientation/<timestamp>/orientation_samples.csv
- artifacts/orientation/<timestamp>/orientation_summary.json
- artifacts/orientation/<timestamp>/snapshots/*.png
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
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
from sensor_msgs.msg import Image

try:
    import cv2
    from cv_bridge import CvBridge

    CV_ENABLED = True
except Exception:
    CV_ENABLED = False
    cv2 = None  # type: ignore[assignment]
    CvBridge = None  # type: ignore[assignment]


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


class OrientationMonitor(Node):
    def __init__(self, detection_topic: str, rgb_topic: str, debug_topic: str, odom_topic: str):
        super().__init__('orientation_uat_runner')
        self.latest_detection: Optional[PointStamped] = None
        self.latest_detection_mono = 0.0
        self.latest_rgb: Optional[Image] = None
        self.latest_debug: Optional[Image] = None
        self.latest_yaw: Optional[float] = None
        self.latest_odom_mono = 0.0

        self.create_subscription(
            PointStamped,
            detection_topic,
            self._on_detection,
            10,
        )
        self.create_subscription(
            Image,
            rgb_topic,
            self._on_rgb,
            10,
        )
        self.create_subscription(
            Image,
            debug_topic,
            self._on_debug,
            10,
        )
        self.create_subscription(
            Odometry,
            odom_topic,
            self._on_odom,
            10,
        )

        self.bridge = CvBridge() if CV_ENABLED else None

    def _on_detection(self, msg: PointStamped) -> None:
        self.latest_detection = msg
        self.latest_detection_mono = time.monotonic()

    def _on_rgb(self, msg: Image) -> None:
        self.latest_rgb = msg

    def _on_debug(self, msg: Image) -> None:
        self.latest_debug = msg

    def _on_odom(self, msg: Odometry) -> None:
        q = msg.pose.pose.orientation
        self.latest_yaw = quaternion_to_yaw(q.x, q.y, q.z, q.w)
        self.latest_odom_mono = time.monotonic()

    def save_snapshot(self, image_msg: Optional[Image], output_path: Path) -> bool:
        if not CV_ENABLED or self.bridge is None or image_msg is None:
            return False
        try:
            cv_image = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding='bgr8')
            return bool(cv2.imwrite(str(output_path), cv_image))
        except Exception:
            return False


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def wrap_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def stamp_to_seconds(stamp) -> float:
    return float(stamp.sec) + (float(stamp.nanosec) / 1e9)


def resolve_path(path_str: str, config_path: Path, repo_root: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    candidate_repo = repo_root / path
    if candidate_repo.exists():
        return candidate_repo
    return (config_path.parent / path).resolve()


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
    if rc != 0:
        return False, err or out or f'remove command failed with code {rc}'
    if 'data: true' not in (out or '').lower():
        return False, out or 'remove returned false'
    return True, out or 'remove requested'


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
    attempts = max(1, set_pose_retries)
    last_msg = ''
    for attempt in range(attempts):
        ok, msg = set_model_pose(
            world_name=world_name,
            model_name=model_name,
            scenario=scenario,
            timeout_s=set_pose_timeout_s,
        )
        if ok:
            return True, msg
        last_msg = msg
        if attempt < attempts - 1 and set_pose_retry_sleep_s > 0.0:
            time.sleep(set_pose_retry_sleep_s)

    if not respawn_on_failure:
        return False, last_msg or 'set_pose failed'

    remove_model(world_name=world_name, model_name=model_name, timeout_s=remove_timeout_s)
    ok, msg = spawn_target(
        model_sdf=model_sdf,
        model_name=model_name,
        world_name=world_name,
        scenario=scenario,
    )
    if ok:
        return True, f'set_pose failed; respawned ({msg})'
    return False, f'set_pose failed; respawn failed ({msg or last_msg})'


def spawn_target(
    model_sdf: Path,
    model_name: str,
    world_name: str,
    scenario: Dict,
) -> Tuple[bool, str]:
    spawn = scenario.get('spawn_world', {})
    x = float(spawn.get('x', 0.0))
    y = float(spawn.get('y', 0.0))
    z = float(spawn.get('z', 0.025))

    cmd = [
        'ros2',
        'run',
        'ros_gz_sim',
        'create',
        '-world',
        world_name,
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
    rc, out, err = run_command(cmd, timeout_s=20.0)
    if rc != 0:
        return False, err or out or f'spawn failed with code {rc}'
    return True, out or 'spawned'


def classify_side(x_m: float, threshold_m: float) -> str:
    if x_m < -threshold_m:
        return 'left'
    if x_m > threshold_m:
        return 'right'
    return 'center'


def is_expected_absent(expected_side: str) -> bool:
    return expected_side in {'none', 'absent', 'no_detection'}


def wait_for_stable_detection(
    node: OrientationMonitor,
    timeout_s: float,
    stale_after_s: float,
    stabilization_samples: int,
    stabilization_window_s: float,
    expected_frame: str,
    min_detection_mono: float,
    min_detection_stamp_s: float,
    verbose: bool = False,
) -> DetectionResult:
    start_mono = time.monotonic()
    hard_deadline_mono = start_mono + max(timeout_s + 5.0, 5.0)
    samples: List[Tuple[float, float, float, str]] = []
    first_fresh_detection_mono: Optional[float] = None
    saw_detection = False
    stamp_gate_enabled = min_detection_stamp_s > 0.0
    stamp_domain_checked = False

    while time.monotonic() - start_mono < timeout_s and rclpy.ok():
        if time.monotonic() > hard_deadline_mono:
            if verbose:
                print('wait_for_stable_detection hit hard deadline')
            break
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
                        if verbose:
                            print(
                                'stamp freshness gate disabled due to clock domain mismatch: '
                                f'msg={msg_stamp_s:.3f}s min={min_detection_stamp_s:.3f}s'
                            )
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
                latency_s=(first_fresh_detection_mono or start_mono) - start_mono,
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
            measured_x = float(sum(s[1] for s in samples) / len(samples))
            measured_z = float(sum(s[2] for s in samples) / len(samples))
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
    failure = FAILURE_STALE_TOPIC if saw_detection else FAILURE_NO_DETECTION
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


def ensure_output_dir(base_output_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output_dir = base_output_dir / ts
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / 'snapshots').mkdir(parents=True, exist_ok=True)
    return output_dir


def write_csv(path: Path, rows: List[Dict]) -> None:
    columns = [
        'scenario_id',
        'status',
        'failure_class',
        'expected_side',
        'observed_side',
        'side_pass',
        'heading_start_rad',
        'heading_end_rad',
        'heading_delta_rad',
        'expected_heading_delta_rad',
        'heading_error_rad',
        'heading_pass',
        'frame_id',
        'frame_pass',
        'measured_x_m',
        'measured_z_m',
        'sample_count',
        'latency_s',
        'elapsed_s',
        'spawn_ok',
        'spawn_message',
        'rgb_snapshot',
        'debug_snapshot',
        'snapshot_pass',
    ]
    with path.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Run deterministic orientation UAT scenarios.')
    parser.add_argument(
        '--config',
        default=str(repo_root / 'ros2_config' / 'config' / 'orientation_scenarios.yaml'),
        help='Path to orientation scenario YAML.',
    )
    parser.add_argument(
        '--output-base',
        default=str(repo_root / 'artifacts' / 'orientation'),
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
    parser.add_argument(
        '--skip-spawn',
        action='store_true',
        help='Skip spawn commands and only evaluate detections against scenarios.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose progress output.',
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
    scenarios = cfg.get('scenarios', [])

    detection_topic = metadata.get('detection_topic', '/yolo/ball_position_3d')
    rgb_topic = metadata.get('rgb_topic', '/d415/color/image_raw')
    debug_topic = metadata.get('debug_topic', '/yolo/debug_image')
    odom_topic = metadata.get('odom_topic', '/odom')
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
    target_model_name = str(metadata.get('target_model_name', 'orientation_ball_target'))

    output_base = Path(args.output_base).resolve()
    output_dir = ensure_output_dir(output_base)
    csv_path = output_dir / 'orientation_samples.csv'
    summary_path = output_dir / 'orientation_summary.json'
    snapshot_dir = output_dir / 'snapshots'

    model_sdf = resolve_path(
        metadata.get('model_sdf', 'ros2_config/green_golf_ball.sdf'),
        config_path,
        repo_root,
    )

    timeout_s_default = float(defaults.get('timeout_s', 20.0))
    stale_after_s = float(defaults.get('stale_after_s', 1.0))
    stabilization_samples = int(defaults.get('stabilization_samples', 8))
    stabilization_window_s = float(defaults.get('stabilization_window_s', 1.5))
    warmup_s = float(defaults.get('warmup_s', 2.0))
    post_spawn_settle_s = float(defaults.get('post_spawn_settle_s', 0.75))
    side_threshold_m = float(defaults.get('side_threshold_m', 0.08))
    heading_tolerance = float(defaults.get('heading_tolerance_rad', 0.35))
    spawn_strategy = str(defaults.get('spawn_strategy', 'set_pose')).strip().lower()
    if spawn_strategy not in {'set_pose', 'respawn'}:
        spawn_strategy = 'set_pose'
    remove_timeout_s = float(defaults.get('remove_timeout_s', 5.0))
    set_pose_timeout_s = float(defaults.get('set_pose_timeout_s', 5.0))
    set_pose_retries = int(defaults.get('set_pose_retries', 3))
    set_pose_retry_sleep_s = float(defaults.get('set_pose_retry_sleep_s', 0.2))
    respawn_on_set_pose_failure = bool(defaults.get('respawn_on_set_pose_failure', True))

    print(f'Running orientation UAT with {len(scenarios)} scenarios')
    print(f'Config: {config_path}')
    print(f'Output: {output_dir}')
    print(f'CV snapshot support: {CV_ENABLED}')
    print(f'World: {world_name}')

    rclpy.init()
    node = OrientationMonitor(
        detection_topic=detection_topic,
        rgb_topic=rgb_topic,
        debug_topic=debug_topic,
        odom_topic=odom_topic,
    )
    if args.use_sim_time:
        node.set_parameters(
            [Parameter('use_sim_time', Parameter.Type.BOOL, True)]
        )

    if warmup_s > 0.0:
        warmup_end = time.monotonic() + warmup_s
        while time.monotonic() < warmup_end and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)

    rows: List[Dict] = []
    side_pass_count = 0
    heading_pass_count = 0
    heading_evaluable_count = 0
    frame_pass_count = 0
    snapshot_pass_count = 0

    failure_counts = {
        FAILURE_NO_DETECTION: 0,
        FAILURE_INVALID_DEPTH: 0,
        FAILURE_STALE_TOPIC: 0,
        FAILURE_TRANSFORM: 0,
    }

    spawned_once_ok = True
    spawned_once_message = 'skipped'
    if not args.skip_spawn and spawn_strategy == 'set_pose':
        if cleanup_between_scenarios:
            ok, msg = remove_model(
                world_name=world_name,
                model_name=target_model_name,
                timeout_s=remove_timeout_s,
            )
            if args.verbose and not ok:
                print(f'initial cleanup target remove: {msg}')
            for cleanup_name in cleanup_model_names:
                if cleanup_name != target_model_name:
                    ok, msg = remove_model(
                        world_name=world_name,
                        model_name=cleanup_name,
                        timeout_s=remove_timeout_s,
                    )
                    if args.verbose and not ok:
                        print(f'initial cleanup remove [{cleanup_name}]: {msg}')

        initial_scenario: Dict = scenarios[0] if scenarios else {'spawn_world': {'x': 1.5, 'y': 0.0, 'z': 0.05}}
        spawned_once_ok, spawned_once_message = spawn_target(
            model_sdf=model_sdf,
            model_name=target_model_name,
            world_name=world_name,
            scenario=initial_scenario,
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
            )
            spawned_once_ok, spawned_once_message = spawn_target(
                model_sdf=model_sdf,
                model_name=target_model_name,
                world_name=world_name,
                scenario=initial_scenario,
            )
        if args.verbose:
            print(f'initial spawn_ok={spawned_once_ok} message={spawned_once_message}')

    for index, scenario in enumerate(scenarios):
        scenario_id = scenario.get('id', f'orientation_{index + 1}')
        timeout_s = float(scenario.get('timeout_s', timeout_s_default))
        timeout_s = max(0.1, min(timeout_s, 60.0))
        expected_side = str(scenario.get('expected_side', 'center')).strip().lower()
        expected_absent = is_expected_absent(expected_side)
        expected_heading_delta = float(
            scenario.get(
                'expected_heading_delta_rad',
                defaults.get('expected_heading_delta_rad', 0.0),
            )
        )

        if args.verbose:
            print(f'[{index + 1}/{len(scenarios)}] {scenario_id} (timeout={timeout_s:.1f}s)')

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
                    ok, msg = remove_model(
                        world_name=world_name,
                        model_name=target_model_name,
                        timeout_s=remove_timeout_s,
                    )
                    if args.verbose and not ok:
                        print(f'  cleanup target remove: {msg}')
                    for cleanup_name in cleanup_model_names:
                        if cleanup_name != target_model_name:
                            ok, msg = remove_model(
                                world_name=world_name,
                                model_name=cleanup_name,
                                timeout_s=remove_timeout_s,
                            )
                            if args.verbose and not ok:
                                print(f'  cleanup remove [{cleanup_name}]: {msg}')

                spawn_ok, spawn_message = spawn_target(
                    model_sdf=model_sdf,
                    model_name=target_model_name,
                    world_name=world_name,
                    scenario=scenario,
                )
                if args.verbose:
                    print(f'  spawn_ok={spawn_ok} message={spawn_message}')
                if (
                    not spawn_ok
                    and 'already exists' in (spawn_message or '').lower()
                    and cleanup_between_scenarios
                ):
                    remove_model(
                        world_name=world_name,
                        model_name=target_model_name,
                        timeout_s=remove_timeout_s,
                    )
                    spawn_ok, spawn_message = spawn_target(
                        model_sdf=model_sdf,
                        model_name=target_model_name,
                        world_name=world_name,
                        scenario=scenario,
                    )
                    if args.verbose:
                        print(f'  respawn_ok={spawn_ok} message={spawn_message}')

        # Flush stale detections from previous scenario before sampling.
        node.latest_detection = None
        node.latest_detection_mono = 0.0
        if post_spawn_settle_s > 0.0:
            settle_end = time.monotonic() + post_spawn_settle_s
            while time.monotonic() < settle_end and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.05)
        scenario_detection_min_mono = time.monotonic()
        scenario_detection_min_stamp_s = node.get_clock().now().nanoseconds / 1e9

        heading_start = node.latest_yaw
        detection = wait_for_stable_detection(
            node=node,
            timeout_s=timeout_s,
            stale_after_s=stale_after_s,
            stabilization_samples=stabilization_samples,
            stabilization_window_s=stabilization_window_s,
            expected_frame=expected_frame,
            min_detection_mono=scenario_detection_min_mono,
            min_detection_stamp_s=scenario_detection_min_stamp_s,
            verbose=args.verbose,
        )
        if args.verbose:
            print(
                f'  detection status={detection.status} failure={detection.failure_class} '
                f'samples={detection.sample_count} elapsed={detection.elapsed_s:.2f}s'
            )
        heading_end = node.latest_yaw

        heading_delta = None
        heading_error = None
        heading_pass: Optional[bool] = None
        if heading_start is not None and heading_end is not None:
            heading_delta = wrap_angle(heading_end - heading_start)
            heading_error = abs(wrap_angle(heading_delta - expected_heading_delta))
            heading_evaluable_count += 1
            heading_pass = heading_error <= heading_tolerance
            if heading_pass:
                heading_pass_count += 1

        observed_side = ''
        side_pass = False
        if expected_absent:
            observed_side = 'none' if detection.status != 'pass' else classify_side(
                float(detection.measured_x_m or 0.0),
                side_threshold_m,
            )
            side_pass = detection.status != 'pass'
        elif detection.status == 'pass' and detection.measured_x_m is not None:
            observed_side = classify_side(detection.measured_x_m, side_threshold_m)
            side_pass = observed_side == expected_side
        if side_pass:
            side_pass_count += 1

        if expected_absent:
            frame_pass = detection.status != 'pass'
        else:
            frame_pass = detection.status == 'pass' and (
                (expected_frame in detection.frame_id) if expected_frame else True
            )
        if frame_pass:
            frame_pass_count += 1

        rgb_snapshot_rel = ''
        debug_snapshot_rel = ''
        snapshot_pass = False
        rgb_snapshot_path = snapshot_dir / f'{index + 1:02d}_{scenario_id}_rgb.png'
        debug_snapshot_path = snapshot_dir / f'{index + 1:02d}_{scenario_id}_debug.png'

        rgb_ok = node.save_snapshot(node.latest_rgb, rgb_snapshot_path)
        debug_ok = node.save_snapshot(node.latest_debug, debug_snapshot_path)
        if rgb_ok:
            rgb_snapshot_rel = str(rgb_snapshot_path.relative_to(output_dir))
        if debug_ok:
            debug_snapshot_rel = str(debug_snapshot_path.relative_to(output_dir))
        snapshot_pass = rgb_ok and debug_ok
        if snapshot_pass:
            snapshot_pass_count += 1

        if detection.failure_class in failure_counts:
            failure_counts[detection.failure_class] += 1

        rows.append(
            {
                'scenario_id': scenario_id,
                'status': detection.status if spawn_ok else 'fail',
                'failure_class': detection.failure_class if spawn_ok else FAILURE_TRANSFORM,
                'expected_side': expected_side,
                'observed_side': observed_side,
                'side_pass': side_pass,
                'heading_start_rad': heading_start,
                'heading_end_rad': heading_end,
                'heading_delta_rad': heading_delta,
                'expected_heading_delta_rad': expected_heading_delta,
                'heading_error_rad': heading_error,
                'heading_pass': heading_pass,
                'frame_id': detection.frame_id,
                'frame_pass': frame_pass,
                'measured_x_m': detection.measured_x_m,
                'measured_z_m': detection.measured_z_m,
                'sample_count': detection.sample_count,
                'latency_s': detection.latency_s,
                'elapsed_s': detection.elapsed_s,
                'spawn_ok': spawn_ok,
                'spawn_message': spawn_message,
                'rgb_snapshot': rgb_snapshot_rel,
                'debug_snapshot': debug_snapshot_rel,
                'snapshot_pass': snapshot_pass,
            }
        )

        if cleanup_between_scenarios and not args.skip_spawn and spawn_strategy != 'set_pose':
            ok, msg = remove_model(
                world_name=world_name,
                model_name=target_model_name,
                timeout_s=remove_timeout_s,
            )
            if args.verbose and not ok:
                print(f'  post-scenario remove: {msg}')

    if cleanup_between_scenarios and not args.skip_spawn and spawn_strategy == 'set_pose':
        ok, msg = remove_model(
            world_name=world_name,
            model_name=target_model_name,
            timeout_s=remove_timeout_s,
        )
        if args.verbose and not ok:
            print(f'final cleanup target remove: {msg}')

    total = len(rows) if rows else 1
    side_accuracy = side_pass_count / total
    heading_accuracy = (
        heading_pass_count / heading_evaluable_count
        if heading_evaluable_count > 0
        else 1.0
    )
    frame_accuracy = frame_pass_count / total
    snapshot_coverage = snapshot_pass_count / total

    summary = {
        'run_id': output_dir.name,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'runtime_target': args.runtime_target,
        'profile': args.profile,
        'inference_device_resolved': args.inference_device,
        'scenario_count': len(rows),
        'side_classification_accuracy': side_accuracy,
        'heading_consistency_accuracy': heading_accuracy,
        'heading_samples_evaluated': heading_evaluable_count,
        'frame_accuracy': frame_accuracy,
        'snapshot_coverage': snapshot_coverage,
        'thresholds': {
            'side_accuracy_min': float(thresholds.get('side_accuracy_min', 0.90)),
            'heading_accuracy_min': float(thresholds.get('heading_accuracy_min', 0.90)),
            'frame_accuracy_min': float(thresholds.get('frame_accuracy_min', 1.00)),
            'snapshot_coverage_min': float(thresholds.get('snapshot_coverage_min', 1.00)),
        },
        'failure_counts': failure_counts,
        'cv_snapshot_support': CV_ENABLED,
    }
    summary['pass'] = (
        summary['side_classification_accuracy'] >= summary['thresholds']['side_accuracy_min']
        and summary['heading_consistency_accuracy'] >= summary['thresholds']['heading_accuracy_min']
        and summary['frame_accuracy'] >= summary['thresholds']['frame_accuracy_min']
        and summary['snapshot_coverage'] >= summary['thresholds']['snapshot_coverage_min']
    )

    write_csv(csv_path, rows)
    with summary_path.open('w', encoding='utf-8') as fp:
        json.dump(summary, fp, indent=2, sort_keys=True)
        fp.write('\n')

    print(f'Wrote {csv_path}')
    print(f'Wrote {summary_path}')
    print(f'Overall pass: {summary["pass"]}')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if summary['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
