from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _install_executor_stubs() -> None:
    if "rclpy" not in sys.modules:
        rclpy_mod = ModuleType("rclpy")
        rclpy_mod.init = lambda *_args, **_kwargs: None
        rclpy_mod.shutdown = lambda *_args, **_kwargs: None
        rclpy_mod.ok = lambda: False

        parameter_mod = ModuleType("rclpy.parameter")

        class _Parameter:
            class Type:
                BOOL = "bool"

            def __init__(self, *_args, **_kwargs) -> None:
                return None

        parameter_mod.Parameter = _Parameter

        node_mod = ModuleType("rclpy.node")

        class _Node:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

        node_mod.Node = _Node

        qos_mod = ModuleType("rclpy.qos")

        class _Preset:
            SENSOR_DATA = SimpleNamespace(value=None)

        qos_mod.QoSPresetProfiles = _Preset

        action_mod = ModuleType("rclpy.action")

        class _ActionClient:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

        action_mod.ActionClient = _ActionClient

        sys.modules["rclpy"] = rclpy_mod
        sys.modules["rclpy.parameter"] = parameter_mod
        sys.modules["rclpy.node"] = node_mod
        sys.modules["rclpy.qos"] = qos_mod
        sys.modules["rclpy.action"] = action_mod

    if "geometry_msgs" not in sys.modules:
        geometry_mod = ModuleType("geometry_msgs")
        msg_mod = ModuleType("geometry_msgs.msg")

        class _Pose:
            def __init__(self) -> None:
                self.position = SimpleNamespace(x=0.0, y=0.0, z=0.0)
                self.orientation = SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)

        class _PointStamped:
            def __init__(self) -> None:
                self.point = SimpleNamespace(x=0.0, y=0.0, z=0.0)

        class _PoseStamped:
            def __init__(self) -> None:
                self.header = SimpleNamespace(frame_id="", stamp=None)
                self.pose = _Pose()

        class _Twist:
            def __init__(self) -> None:
                self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
                self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)

        class _TwistStamped:
            def __init__(self) -> None:
                self.header = SimpleNamespace(stamp=None, frame_id="")
                self.twist = _Twist()

        msg_mod.Pose = _Pose
        msg_mod.PointStamped = _PointStamped
        msg_mod.PoseStamped = _PoseStamped
        msg_mod.Twist = _Twist
        msg_mod.TwistStamped = _TwistStamped
        geometry_mod.msg = msg_mod
        sys.modules["geometry_msgs"] = geometry_mod
        sys.modules["geometry_msgs.msg"] = msg_mod

    if "nav2_msgs" not in sys.modules:
        nav2_mod = ModuleType("nav2_msgs")
        action_mod = ModuleType("nav2_msgs.action")

        class _NavigateToPose:
            class Goal:
                def __init__(self) -> None:
                    self.pose = None
                    self.behavior_tree = ""

        action_mod.NavigateToPose = _NavigateToPose
        nav2_mod.action = action_mod
        sys.modules["nav2_msgs"] = nav2_mod
        sys.modules["nav2_msgs.action"] = action_mod

    if "nav_msgs" not in sys.modules:
        nav_mod = ModuleType("nav_msgs")
        msg_mod = ModuleType("nav_msgs.msg")

        class _Odometry:
            def __init__(self) -> None:
                self.pose = SimpleNamespace(pose=None)

        msg_mod.Odometry = _Odometry
        nav_mod.msg = msg_mod
        sys.modules["nav_msgs"] = nav_mod
        sys.modules["nav_msgs.msg"] = msg_mod

    if "std_msgs" not in sys.modules:
        std_mod = ModuleType("std_msgs")
        msg_mod = ModuleType("std_msgs.msg")

        class _String:
            def __init__(self) -> None:
                self.data = ""

        msg_mod.String = _String
        std_mod.msg = msg_mod
        sys.modules["std_msgs"] = std_mod
        sys.modules["std_msgs.msg"] = msg_mod


_install_executor_stubs()

import brain_intent_executor as executor_mod  # noqa: E402


def _make_detection(*, x: float, z: float, y: float = 0.0):
    msg = executor_mod.PointStamped()
    msg.point.x = x
    msg.point.y = y
    msg.point.z = z
    return msg


def _make_executor(monkeypatch):
    executor = executor_mod.BrainIntentExecutor.__new__(executor_mod.BrainIntentExecutor)
    executor.args = SimpleNamespace(
        search_detection_burst=2,
        search_turn_speed_radps=0.3,
        detection_stale_after_s=1.5,
        search_timeout_s=28.0,
        search_max_rotation_rad=6.6,
        approach_distance_m=0.25,
        track_replan_cooldown_s=1.5,
        goal_frame="odom",
        acquire_radius_m=1.5,
    )
    executor.latest_detection = None
    executor.last_detection_monotonic = 0.0
    executor.detection_burst_count = 0
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_pose_stamp = ""
    executor.latest_goal_pose = None
    executor.last_goal_dispatched_monotonic = 0.0
    executor.last_goal_dispatched_utc = ""
    executor.feedback_count = 0
    executor.last_feedback_text = ""
    executor.last_feedback_status = ""
    executor.last_feedback_utc = ""
    executor.last_intent = "search_for_target"
    executor.last_intent_args = {}
    executor.search_active = False
    executor.search_state = "idle"
    executor.search_started_monotonic = 0.0
    executor.search_rotation_accum_rad = 0.0
    executor.search_last_yaw = None
    executor.search_target_class = ""
    executor.search_rotation_sign = 1.0
    executor.last_search_feedback_monotonic = 0.0
    executor.target_locked = False
    executor.target_locked_class = ""
    executor.target_locked_utc = ""
    executor.track_active = False
    executor.track_needs_replan = False
    executor.goal_in_progress = False
    executor.current_goal_handle = None
    executor.pending_cancel_reason = ""
    executor.last_state_write_monotonic = 0.0
    executor.state_path = None
    executor.feedback_history_path = None
    executor.visit_runtime_path = None
    executor.prior_lock_tolerance_m = 0.50
    executor.active_prior = None
    executor.last_prior_read_monotonic = 0.0
    executor.visit_active = False
    executor.visit_target_id = ""
    executor.visit_started_monotonic = 0.0
    executor.visit_phase = ""
    executor.visit_locked = False
    executor.visit_approach_dispatched = False
    executor.latest_detections_3d = []
    executor.latest_detections_3d_mono = 0.0

    published_feedback = []
    published_twists = []
    published_stops = []
    canceled_goals = []
    locked_targets = []
    state_writes = []

    def _publish_feedback(text: str, *, status: str, extra=None) -> None:
        published_feedback.append({"text": text, "status": status, "extra": extra or {}})
        executor.last_feedback_text = text
        executor.last_feedback_status = status

    def _publish_twist(twist) -> None:
        published_twists.append(twist)

    def _publish_stop() -> None:
        published_stops.append(True)

    def _cancel_goal(reason: str) -> None:
        canceled_goals.append(reason)

    def _write_state(*, force: bool) -> None:
        state_writes.append(force)

    original_clear_motion_state = executor_mod.BrainIntentExecutor._clear_motion_state.__get__(executor, executor_mod.BrainIntentExecutor)
    original_reset_pursuit_state = executor_mod.BrainIntentExecutor._reset_pursuit_state.__get__(executor, executor_mod.BrainIntentExecutor)

    def _lock_target(target_class: str, source: str) -> None:
        locked_targets.append((target_class, source))
        executor.target_locked = True
        executor.target_locked_class = target_class
        executor.target_locked_utc = "now"
        if executor.search_active:
            executor.search_active = False
            executor.search_state = "locked"

    dispatched_nav_goals = []
    dispatched_prior_goals = []

    def _dispatch_nav_goal(*, reason: str, approach_distance_m: float) -> bool:
        dispatched_nav_goals.append({"reason": reason, "approach_distance_m": approach_distance_m})
        return True

    def _dispatch_prior_approach_goal(*, reason: str, approach_distance_m: float) -> bool:
        dispatched_prior_goals.append({"reason": reason, "approach_distance_m": approach_distance_m})
        return True

    executor._publish_feedback = _publish_feedback
    executor._publish_twist = _publish_twist
    executor._publish_stop = _publish_stop
    executor._cancel_goal = _cancel_goal
    executor._write_state = _write_state
    executor._lock_target = _lock_target
    executor._dispatch_nav_goal = _dispatch_nav_goal
    executor._dispatch_prior_approach_goal = _dispatch_prior_approach_goal
    executor._clear_motion_state = original_clear_motion_state
    executor._reset_pursuit_state = original_reset_pursuit_state

    monkeypatch.setattr(executor_mod.time, "monotonic", lambda: 100.0)

    executor._published_feedback = published_feedback
    executor._published_twists = published_twists
    executor._dispatched_nav_goals = dispatched_nav_goals
    executor._dispatched_prior_goals = dispatched_prior_goals
    executor._published_stops = published_stops
    executor._canceled_goals = canceled_goals
    executor._locked_targets = locked_targets
    executor._state_writes = state_writes
    return executor


def test_detection_bearing_negative_for_right_of_center_target(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_detection = _make_detection(x=0.35, z=1.0)
    executor.last_detection_monotonic = 99.5

    bearing = executor._latest_detection_bearing_rad()

    assert bearing is not None
    assert bearing < 0.0


def test_detection_bearing_positive_for_left_of_center_target(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_detection = _make_detection(x=-0.35, z=1.0)
    executor.last_detection_monotonic = 99.5

    bearing = executor._latest_detection_bearing_rad()

    assert bearing is not None
    assert bearing > 0.0


def test_target_ready_for_lock_requires_centering_and_burst(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 1

    assert executor._target_centered_now() is True
    assert executor._target_ready_for_lock() is False

    executor.detection_burst_count = 2
    assert executor._target_ready_for_lock() is True


def test_search_intent_visible_off_center_enters_centering_not_lock(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_detection = _make_detection(x=0.4, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 4

    executor._handle_search_intent({"target_class": "ball"})

    assert executor.search_active is True
    assert executor.search_state == "centering"
    assert executor.target_locked is False
    assert executor._locked_targets == []


def test_search_intent_visible_centered_locks_after_burst(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 2

    executor._handle_search_intent({"target_class": "ball"})

    assert executor.target_locked is True
    assert executor._locked_targets == [("ball", "search_for_target")]


def test_acquire_intent_visible_off_center_enters_centering(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.last_intent = "acquire_target"
    executor.latest_detection = _make_detection(x=-0.35, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 4

    executor._handle_acquire_intent({"target_class": "ball"})

    assert executor.search_active is True
    assert executor.search_state == "centering"
    assert executor.target_locked is False
    assert executor._locked_targets == []


def test_timer_centers_visible_target_with_turn_direction(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.search_active = True
    executor.search_state = "rotating"
    executor.search_started_monotonic = 99.0
    executor.search_target_class = "ball"
    executor.latest_detection = _make_detection(x=0.35, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 1

    executor._on_timer()

    assert executor.search_state == "centering"
    assert executor._published_twists
    assert math.isclose(executor._published_twists[-1].angular.z, -0.3, abs_tol=1e-6)
    assert executor._locked_targets == []


def test_timer_locks_centered_visible_target_after_burst(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.search_active = True
    executor.search_state = "centering"
    executor.search_started_monotonic = 99.0
    executor.search_target_class = "ball"
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 2

    executor._on_timer()

    assert executor._locked_targets == [("ball", "search_for_target")]
    assert executor.search_state == "locked"


# --- Prior-based lock gating tests ---


def test_no_prior_allows_lock(monkeypatch):
    """When no target prior is set, lock proceeds as before."""
    executor = _make_executor(monkeypatch)
    executor.active_prior = None
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 2

    assert executor._prior_lock_alignment_ok() is True
    assert executor._target_ready_for_lock() is True


def test_aligned_prior_allows_lock(monkeypatch):
    """When detection world position is within tolerance of prior, lock proceeds."""
    executor = _make_executor(monkeypatch)
    # Robot at origin facing +x. Detection at (0.05, 0, 1.0) in local frame
    # -> ball world position is roughly (1.0, -0.05) in odom.
    # Set prior near that.
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 2

    world = executor._detection_world_position()
    assert world is not None
    executor.active_prior = {"x": world["x"], "y": world["y"]}

    assert executor._prior_lock_alignment_ok() is True
    assert executor._target_ready_for_lock() is True


def test_off_prior_blocks_lock(monkeypatch):
    """When detection world position is far from prior, lock is refused."""
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 2

    # Set prior far away from where the detection actually is
    executor.active_prior = {"x": 5.0, "y": 5.0}

    assert executor._prior_lock_alignment_ok() is False
    assert executor._target_ready_for_lock() is False


def test_search_timer_rotates_past_off_prior_detection(monkeypatch):
    """During search, if detection is visible but off-prior, executor keeps rotating."""
    executor = _make_executor(monkeypatch)
    executor.search_active = True
    executor.search_state = "centering"
    executor.search_started_monotonic = 99.0
    executor.search_target_class = "ball"
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 2
    executor.active_prior = {"x": 5.0, "y": 5.0}

    executor._on_timer()

    assert executor.search_state == "rotating"
    assert executor._locked_targets == []
    assert executor._published_twists
    assert executor._published_twists[-1].angular.z > 0


def test_search_timer_centers_on_prior_aligned_detection(monkeypatch):
    """During search, if detection is visible and on-prior, executor centers on it."""
    executor = _make_executor(monkeypatch)
    executor.search_active = True
    executor.search_state = "rotating"
    executor.search_started_monotonic = 99.0
    executor.search_target_class = "ball"
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    # Off-center detection (bearing != 0) so we're centering, not locking
    executor.latest_detection = _make_detection(x=0.35, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 1

    world = executor._detection_world_position()
    executor.active_prior = {"x": world["x"], "y": world["y"]}

    executor._on_timer()

    assert executor.search_state == "centering"
    assert executor._locked_targets == []


def test_acquire_blocks_on_off_prior_detection(monkeypatch):
    """acquire_target returns blocked when the visible target is off-prior."""
    executor = _make_executor(monkeypatch)
    executor.last_intent = "acquire_target"
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_detection = _make_detection(x=0.05, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.detection_burst_count = 4
    executor.active_prior = {"x": 5.0, "y": 5.0}

    executor._handle_acquire_intent({"target_class": "ball"})

    assert executor.target_locked is False
    assert executor._locked_targets == []
    assert any("off-prior" in fb["text"] for fb in executor._published_feedback)


def test_prior_delta_m_computes_distance(monkeypatch):
    """_prior_delta_m returns the distance between detection world and prior."""
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_detection = _make_detection(x=0.0, z=1.0)
    executor.last_detection_monotonic = 99.5

    world = executor._detection_world_position()
    assert world is not None
    executor.active_prior = {"x": world["x"] + 1.0, "y": world["y"]}

    delta = executor._prior_delta_m()
    assert delta is not None
    assert math.isclose(delta, 1.0, abs_tol=0.01)


def test_prior_delta_m_returns_none_without_prior(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.latest_detection = _make_detection(x=0.0, z=1.0)
    executor.last_detection_monotonic = 99.5
    executor.active_prior = None

    assert executor._prior_delta_m() is None


def test_refresh_prior_reads_runtime_file(monkeypatch, tmp_path):
    """_refresh_target_prior reads current_target_prior from visit runtime JSON."""
    executor = _make_executor(monkeypatch)
    runtime_file = tmp_path / "visit_mission_runtime.json"
    runtime_file.write_text('{"current_target_prior": {"x": 1.5, "y": -0.3}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_file
    executor.last_prior_read_monotonic = 0.0

    executor._refresh_target_prior()

    assert executor.active_prior == {"x": 1.5, "y": -0.3}


def test_refresh_prior_clears_when_empty(monkeypatch, tmp_path):
    """_refresh_target_prior clears the prior when runtime file has empty prior."""
    executor = _make_executor(monkeypatch)
    runtime_file = tmp_path / "visit_mission_runtime.json"
    runtime_file.write_text('{"current_target_prior": {}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_file
    executor.last_prior_read_monotonic = 0.0
    executor.active_prior = {"x": 1.0, "y": 2.0}

    executor._refresh_target_prior()

    assert executor.active_prior is None


def test_refresh_prior_tolerates_missing_file(monkeypatch, tmp_path):
    """_refresh_target_prior doesn't crash when the file doesn't exist."""
    executor = _make_executor(monkeypatch)
    executor.visit_runtime_path = tmp_path / "nonexistent.json"
    executor.last_prior_read_monotonic = 0.0
    executor.active_prior = {"x": 1.0, "y": 2.0}

    executor._refresh_target_prior()

    # Prior unchanged — file missing is not an error, just no update
    assert executor.active_prior == {"x": 1.0, "y": 2.0}


def test_prior_robot_distance_m(monkeypatch):
    """_prior_robot_distance_m returns euclidean distance from robot to prior."""
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.active_prior = {"x": 3.0, "y": 4.0}

    dist = executor._prior_robot_distance_m()
    assert dist is not None
    assert math.isclose(dist, 5.0, abs_tol=0.01)


def test_prior_robot_distance_m_none_without_prior(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.active_prior = None

    assert executor._prior_robot_distance_m() is None


def test_dispatch_prior_approach_goal_computes_correct_target(monkeypatch):
    """_dispatch_prior_approach_goal plans a goal approach_distance_m short of the prior."""
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.active_prior = {"x": 1.0, "y": 0.0}

    # Restore real _dispatch_prior_approach_goal (mocked in _make_executor)
    executor._dispatch_prior_approach_goal = executor_mod.BrainIntentExecutor._dispatch_prior_approach_goal.__get__(executor, executor_mod.BrainIntentExecutor)

    # Stub out nav client and clock
    executor.nav_client = SimpleNamespace(
        server_is_ready=lambda: True,
        send_goal_async=lambda *a, **kw: SimpleNamespace(add_done_callback=lambda cb: None),
    )
    executor.goal_pose_pub = SimpleNamespace(publish=lambda msg: None)
    executor.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: None))

    dispatched = executor._dispatch_prior_approach_goal(reason="track_target", approach_distance_m=0.25)

    assert dispatched is True
    assert executor.goal_in_progress is True
    # Goal should be at 0.75 in x (1.0 - 0.25)
    assert executor.latest_goal_pose is not None
    assert math.isclose(executor.latest_goal_pose.pose.position.x, 0.75, abs_tol=0.01)
    assert math.isclose(executor.latest_goal_pose.pose.position.y, 0.0, abs_tol=0.01)


def test_dispatch_prior_approach_goal_returns_false_when_close(monkeypatch):
    """_dispatch_prior_approach_goal returns False when already within approach distance."""
    executor = _make_executor(monkeypatch)
    executor.latest_pose = SimpleNamespace(x=0.9, y=0.0, yaw=0.0)
    executor.active_prior = {"x": 1.0, "y": 0.0}

    # Restore real _dispatch_prior_approach_goal (mocked in _make_executor)
    executor._dispatch_prior_approach_goal = executor_mod.BrainIntentExecutor._dispatch_prior_approach_goal.__get__(executor, executor_mod.BrainIntentExecutor)

    executor.nav_client = SimpleNamespace(
        server_is_ready=lambda: True,
    )

    dispatched = executor._dispatch_prior_approach_goal(reason="track_target", approach_distance_m=0.25)

    assert dispatched is False


def test_track_replan_uses_prior_when_robot_is_far_from_prior(monkeypatch):
    """Track replan uses prior-based goal when robot is far from prior, even if detection seems close."""
    executor = _make_executor(monkeypatch)
    executor.track_active = True
    executor.track_needs_replan = True
    executor.search_active = False
    executor.goal_in_progress = False
    executor.last_goal_dispatched_monotonic = 0.0
    # Robot is at origin, prior is at (1.0, 0.0)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor.active_prior = {"x": 1.0, "y": 0.0}
    # Detection says ball is close — detection-based approach would dispatch a short goal
    executor.latest_detection = _make_detection(x=0.0, z=0.5)
    executor.last_detection_monotonic = 99.5

    # Stub nav client
    dispatched_goals = []

    class FakeNavClient:
        def server_is_ready(self):
            return True

        def wait_for_server(self, timeout_sec=0.5):
            return True

        def send_goal_async(self, goal_msg, feedback_callback=None):
            dispatched_goals.append(goal_msg)
            return SimpleNamespace(add_done_callback=lambda cb: None)

    executor.nav_client = FakeNavClient()
    executor.goal_pose_pub = SimpleNamespace(publish=lambda msg: None)
    executor.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: None))

    # Restore real _dispatch_prior_approach_goal (mocked in _make_executor)
    executor._dispatch_prior_approach_goal = executor_mod.BrainIntentExecutor._dispatch_prior_approach_goal.__get__(executor, executor_mod.BrainIntentExecutor)

    executor._on_timer()

    # Should have dispatched a prior-based goal since robot is 1.0m from prior (> 0.05 prior approach)
    assert len(dispatched_goals) == 1
    assert executor.goal_in_progress is True
    # Goal should be toward prior with tight 0.05 approach distance (goal at ~0.95)
    goal_x = dispatched_goals[0].pose.pose.position.x
    assert goal_x > 0.9, f"Expected prior-based goal near 0.95, got {goal_x}"
    assert any("prior-based" in fb["text"] for fb in executor._published_feedback)


def test_track_replan_uses_detection_when_close_to_prior(monkeypatch):
    """Track replan uses detection-based goal when robot is already near the prior."""
    executor = _make_executor(monkeypatch)
    executor.track_active = True
    executor.track_needs_replan = True
    executor.search_active = False
    executor.goal_in_progress = False
    executor.last_goal_dispatched_monotonic = 0.0
    # Robot is within the tight prior approach distance (0.05m)
    executor.latest_pose = SimpleNamespace(x=0.96, y=0.0, yaw=0.0)
    executor.active_prior = {"x": 1.0, "y": 0.0}
    # Detection says ball is 0.5m ahead — will create a valid plan
    executor.latest_detection = _make_detection(x=0.0, z=0.5)
    executor.last_detection_monotonic = 99.5

    dispatched_goals = []

    class FakeNavClient:
        def server_is_ready(self):
            return True

        def wait_for_server(self, timeout_sec=0.5):
            return True

        def send_goal_async(self, goal_msg, feedback_callback=None):
            dispatched_goals.append(goal_msg)
            return SimpleNamespace(add_done_callback=lambda cb: None)

    executor.nav_client = FakeNavClient()
    executor.goal_pose_pub = SimpleNamespace(publish=lambda msg: None)
    executor.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: None))

    # Restore real _dispatch_nav_goal (mocked in _make_executor)
    executor._dispatch_nav_goal = executor_mod.BrainIntentExecutor._dispatch_nav_goal.__get__(executor, executor_mod.BrainIntentExecutor)

    executor._on_timer()

    # Should use detection-based goal since prior distance (0.04m) < prior_approach (0.05m)
    assert len(dispatched_goals) == 1
    # Detection-based feedback, not prior-based
    assert not any("prior-based" in fb["text"] for fb in executor._published_feedback)


# --- visit_target handler tests ---


def test_visit_target_writes_selection_and_starts_acquire(monkeypatch, tmp_path):
    """Without a distant prior, visit_target goes straight to acquiring phase."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{"running": true}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor._handle_visit_target_intent({"target_id": "ball_b"})

    data = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert data["llm_selected_target_id"] == "ball_b"
    assert "llm_selected_utc" in data
    # Visit lifecycle: should go to acquiring (no distant prior to navigate to)
    assert executor.visit_active is True
    assert executor.visit_target_id == "ball_b"
    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True
    assert executor._published_feedback[-1]["status"] == "visit_target_acquiring"


def test_visit_target_blocks_on_empty_target_id(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor._handle_visit_target_intent({"target_id": ""})
    assert executor._published_feedback[-1]["status"] == "blocked"
    assert "empty" in executor._published_feedback[-1]["text"]


def test_visit_target_blocks_without_runtime_path(monkeypatch):
    executor = _make_executor(monkeypatch)
    executor.visit_runtime_path = None
    executor._handle_visit_target_intent({"target_id": "ball_a"})
    assert executor._published_feedback[-1]["status"] == "blocked"
    assert "not configured" in executor._published_feedback[-1]["text"]


def test_on_intent_dispatches_visit_target(monkeypatch, tmp_path):
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    msg = SimpleNamespace(data=json.dumps({"intent": "visit_target", "args": {"target_id": "ball_c"}}))
    executor._on_intent(msg)

    data = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert data["llm_selected_target_id"] == "ball_c"
    assert executor.last_intent == "visit_target"


# --- Visit lifecycle tests ---


def test_visit_lock_auto_dispatches_approach_goal(monkeypatch, tmp_path):
    """When target locks during an active visit, approach goal is dispatched automatically."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    dispatched_goals = []

    class FakeNavClient:
        def server_is_ready(self):
            return True

        def wait_for_server(self, timeout_sec=0.5):
            return True

        def send_goal_async(self, goal_msg, feedback_callback=None):
            dispatched_goals.append(goal_msg)
            return SimpleNamespace(add_done_callback=lambda cb: None)

    executor.nav_client = FakeNavClient()
    executor.goal_pose_pub = SimpleNamespace(publish=lambda msg: None)
    executor.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: None))

    # Restore real _lock_target and _dispatch_nav_goal so visit lifecycle hooks fire
    executor._lock_target = executor_mod.BrainIntentExecutor._lock_target.__get__(executor, executor_mod.BrainIntentExecutor)
    executor._dispatch_nav_goal = executor_mod.BrainIntentExecutor._dispatch_nav_goal.__get__(executor, executor_mod.BrainIntentExecutor)

    # Start visit lifecycle
    executor._handle_visit_target_intent({"target_id": "ball_a"})
    assert executor.visit_active is True
    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True

    # Simulate detection that triggers lock
    executor.detection_burst_count = 5
    executor.latest_detection = _make_detection(x=0.0, z=1.5)
    executor.last_detection_monotonic = time.monotonic()
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor._lock_target("ball", "search_for_target")

    # Visit lifecycle should have auto-dispatched approach
    assert executor.visit_locked is True
    assert executor.visit_approach_dispatched is True
    assert executor.track_active is True
    assert len(dispatched_goals) == 1


def test_visit_search_timeout_restarts_search(monkeypatch, tmp_path):
    """When search fails during a visit, it restarts automatically."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor._handle_visit_target_intent({"target_id": "ball_b"})
    assert executor.visit_active is True
    assert executor.search_active is True

    # Simulate search failure (rotation limit exceeded)
    executor.search_rotation_accum_rad = 999.0
    executor._on_timer()

    # Visit should still be active, search restarted
    assert executor.visit_active is True
    assert executor.search_active is True
    assert executor.search_state == "rotating"


def test_visit_overall_timeout_ends_visit(monkeypatch, tmp_path):
    """Visit lifecycle ends with failure when overall timeout is exceeded."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor._handle_visit_target_intent({"target_id": "ball_c"})
    # Force visit to have started long ago
    executor.visit_started_monotonic = time.monotonic() - 200.0
    executor._on_timer()

    assert executor.visit_active is False
    assert executor._published_feedback[-1]["status"] == "visit_target_failed"
    assert "ball_c" in executor._published_feedback[-1]["text"]


def test_visit_proximity_check_declares_reached(monkeypatch, tmp_path):
    """When robot is close to prior during tracking, visit declares reached."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{"current_target_prior": {"x": 1.0, "y": 0.0}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor._handle_visit_target_intent({"target_id": "ball_a"})
    # Manually set visit state as if search→lock→approach completed
    executor.visit_locked = True
    executor.visit_approach_dispatched = True
    executor.track_active = True
    executor.track_needs_replan = True
    executor.search_active = False
    executor.goal_in_progress = False
    executor.last_goal_dispatched_monotonic = 0.0

    # Set prior and robot position close together
    executor.active_prior = {"x": 1.0, "y": 0.0}
    executor.latest_pose = SimpleNamespace(x=1.05, y=0.0, yaw=0.0)

    executor._on_timer()

    assert executor.visit_active is False
    reached = [fb for fb in executor._published_feedback if fb["status"] == "visit_target_reached"]
    assert len(reached) == 1
    assert reached[0]["extra"]["target_id"] == "ball_a"


def test_search_rotation_direction_follows_prior(monkeypatch, tmp_path):
    """Search rotation direction is chosen toward the active prior in acquiring phase."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    # Prior within acquire radius (1.5m) but to the right (negative bearing → CW)
    runtime_path.write_text('{"current_target_prior": {"x": 0.5, "y": -1.0}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    # Robot at origin facing +X (yaw=0)
    executor.latest_pose = type("P", (), {"x": 0.0, "y": 0.0, "yaw": 0.0})()
    executor._handle_visit_target_intent({"target_id": "ball_right"})
    assert executor.visit_phase == "acquiring"
    assert executor.search_rotation_sign == -1.0, "Should rotate CW toward prior on the right"

    # Prior within acquire radius but to the left (positive bearing → CCW)
    runtime_path.write_text('{"current_target_prior": {"x": 0.5, "y": 1.0}}', encoding="utf-8")
    executor._handle_visit_target_intent({"target_id": "ball_left"})
    assert executor.visit_phase == "acquiring"
    assert executor.search_rotation_sign == 1.0, "Should rotate CCW toward prior on the left"


def test_safe_stop_ends_active_visit(monkeypatch, tmp_path):
    """safe_stop during an active visit ends the visit with failure."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor._handle_visit_target_intent({"target_id": "ball_b"})
    assert executor.visit_active is True

    executor._handle_safe_stop_intent()
    assert executor.visit_active is False
    failed = [fb for fb in executor._published_feedback if fb["status"] == "visit_target_failed"]
    assert len(failed) == 1


def test_visit_navigates_to_distant_prior(monkeypatch, tmp_path):
    """When prior is farther than acquire_radius, visit dispatches nav goal to prior."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{"current_target_prior": {"x": 5.0, "y": 0.0}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor._handle_visit_target_intent({"target_id": "ball_far"})

    assert executor.visit_active is True
    assert executor.visit_phase == "navigating"
    assert executor.search_active is False  # Not searching — navigating
    assert len(executor._dispatched_prior_goals) == 1
    nav_fb = [fb for fb in executor._published_feedback if fb["status"] == "visit_target_navigating"]
    assert len(nav_fb) >= 1


def test_visit_near_prior_goes_straight_to_acquiring(monkeypatch, tmp_path):
    """When prior is within acquire_radius, visit skips navigating and goes to acquiring."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{"current_target_prior": {"x": 1.0, "y": 0.0}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor._handle_visit_target_intent({"target_id": "ball_near"})

    assert executor.visit_active is True
    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True
    assert len(executor._dispatched_prior_goals) == 0


def test_visit_navigating_transitions_to_acquiring_on_proximity(monkeypatch, tmp_path):
    """During navigating phase, timer transitions to acquiring when robot nears prior."""
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_path.write_text('{"current_target_prior": {"x": 5.0, "y": 0.0}}', encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)
    executor._handle_visit_target_intent({"target_id": "ball_x"})
    assert executor.visit_phase == "navigating"

    # Simulate robot has moved close to prior
    executor.latest_pose = SimpleNamespace(x=4.5, y=0.0, yaw=0.0)
    executor._on_timer()

    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True


# --- Scenario-level tests (real code paths, no core method mocks) ---


def _make_scenario_executor(monkeypatch, tmp_path, *, prior: dict | None = None, nav2_ready: bool = True):
    """Build an executor for scenario tests with real core methods and a fake Nav2 client.

    Unlike _make_executor, this restores the real _dispatch_prior_approach_goal,
    _dispatch_nav_goal, _lock_target, etc. Only I/O (ROS publishers, file writes)
    is stubbed.
    """
    executor = _make_executor(monkeypatch)
    runtime_path = tmp_path / "visit_mission_runtime.json"
    runtime_data = {}
    if prior:
        runtime_data["current_target_prior"] = prior
    runtime_path.write_text(json.dumps(runtime_data), encoding="utf-8")
    executor.visit_runtime_path = runtime_path

    dispatched_goals = []

    class FakeNavClient:
        def server_is_ready(self):
            return nav2_ready

        def wait_for_server(self, timeout_sec=0.5):
            return nav2_ready

        def send_goal_async(self, goal_msg, feedback_callback=None):
            dispatched_goals.append(goal_msg)
            return SimpleNamespace(add_done_callback=lambda cb: None)

    executor.nav_client = FakeNavClient()
    executor.goal_pose_pub = SimpleNamespace(publish=lambda msg: None)
    executor.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(to_msg=lambda: None))

    # Restore real core methods (overridden by _make_executor with mocks)
    for method_name in (
        "_dispatch_prior_approach_goal",
        "_dispatch_nav_goal",
        "_lock_target",
    ):
        real = getattr(executor_mod.BrainIntentExecutor, method_name)
        setattr(executor, method_name, real.__get__(executor, executor_mod.BrainIntentExecutor))

    executor._dispatched_goals = dispatched_goals
    return executor


def test_scenario_distant_prior_navigates_then_acquires(monkeypatch, tmp_path):
    """Full scenario: distant prior -> Nav2 goal dispatched -> arrive near prior -> search starts."""
    executor = _make_scenario_executor(monkeypatch, tmp_path, prior={"x": 5.0, "y": 0.0})
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)

    executor._handle_visit_target_intent({"target_id": "ball_a"})

    # Should navigate, not spin
    assert executor.visit_phase == "navigating"
    assert executor.search_active is False
    assert executor.goal_in_progress is True
    assert len(executor._dispatched_goals) == 1
    goal_x = executor._dispatched_goals[0].pose.pose.position.x
    assert goal_x > 1.0, f"Nav goal should be toward prior, got x={goal_x}"

    # Simulate arriving near prior (timer fires, robot is close)
    executor.latest_pose = SimpleNamespace(x=4.2, y=0.0, yaw=0.0)
    executor.goal_in_progress = False  # Nav2 goal finished
    executor._on_timer()

    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True


def test_scenario_nav2_not_ready_retries_on_timer(monkeypatch, tmp_path):
    """When Nav2 isn't ready, visit stays pending and retries on next timer tick."""
    executor = _make_scenario_executor(monkeypatch, tmp_path, prior={"x": 5.0, "y": 0.0}, nav2_ready=False)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)

    executor._handle_visit_target_intent({"target_id": "ball_a"})

    # Should NOT fall through to acquiring/spinning
    assert executor.visit_active is True
    assert executor.visit_phase == ""  # Waiting for Nav2
    assert executor.search_active is False
    assert len(executor._dispatched_goals) == 0

    # Simulate Nav2 becoming ready
    executor.nav_client = SimpleNamespace(
        server_is_ready=lambda: True,
        wait_for_server=lambda timeout_sec=0.5: True,
        send_goal_async=lambda goal_msg, feedback_callback=None: (
            executor._dispatched_goals.append(goal_msg) or SimpleNamespace(add_done_callback=lambda cb: None)
        ),
    )
    executor._on_timer()

    # Now should navigate
    assert executor.visit_phase == "navigating"
    assert executor.goal_in_progress is True
    assert len(executor._dispatched_goals) == 1


def test_scenario_lock_during_acquire_dispatches_approach(monkeypatch, tmp_path):
    """Full scenario: acquiring -> detection -> lock -> approach goal dispatched."""
    executor = _make_scenario_executor(monkeypatch, tmp_path, prior={"x": 1.0, "y": 0.0})
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)

    executor._handle_visit_target_intent({"target_id": "ball_a"})
    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True

    # Simulate centered detection with burst
    executor.detection_burst_count = 5
    executor.latest_detection = _make_detection(x=0.0, z=1.0)
    executor.last_detection_monotonic = time.monotonic()
    executor._lock_target("ball", "search_for_target")

    assert executor.visit_phase == "approaching"
    assert executor.visit_locked is True
    assert executor.track_active is True
    # Approach goal dispatched (via detection-based _dispatch_nav_goal)
    assert len(executor._dispatched_goals) >= 1


def test_scenario_no_prior_acquires_immediately(monkeypatch, tmp_path):
    """Without a prior, visit goes straight to acquiring (search rotation)."""
    executor = _make_scenario_executor(monkeypatch, tmp_path, prior=None)
    executor.latest_pose = SimpleNamespace(x=0.0, y=0.0, yaw=0.0)

    executor._handle_visit_target_intent({"target_id": "ball_a"})

    assert executor.visit_phase == "acquiring"
    assert executor.search_active is True
    assert len(executor._dispatched_goals) == 0
