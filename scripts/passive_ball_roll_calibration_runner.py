#!/usr/bin/env python3
"""Run a live passive golf-ball roll calibration against Gazebo."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from passive_ball_roll_calibration_helpers import GOLF_SHORT_TURF_ROLL_BAND
from passive_ball_roll_calibration_helpers import G_ACCEL_MPS2
from passive_ball_roll_calibration_helpers import ROLL_BANDS_BY_SURFACE
from passive_ball_roll_calibration_helpers import build_scorecard_markdown
from passive_ball_roll_calibration_helpers import classify_roll_result
from passive_ball_roll_calibration_helpers import deceleration_from_stop
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


INITIAL_LINK_VELOCITY_PLUGIN_SOURCE = r"""
#include <memory>
#include <string>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <gz/math/Vector3.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Types.hh>
#include <sdf/Element.hh>

namespace chasecar
{
class InitialLinkVelocity:
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate,
  public gz::sim::ISystemPostUpdate
{
  public: void Configure(
    const gz::sim::Entity &_entity,
    const std::shared_ptr<const sdf::Element> &_sdf,
    gz::sim::EntityComponentManager &,
    gz::sim::EventManager &) override
  {
    this->modelEntity = _entity;
    if (_sdf->HasElement("link_name"))
      this->linkName = _sdf->Get<std::string>("link_name");
    if (_sdf->HasElement("linear_velocity"))
      this->linearVelocity = _sdf->Get<gz::math::Vector3d>("linear_velocity");
    if (_sdf->HasElement("angular_velocity"))
      this->angularVelocity = _sdf->Get<gz::math::Vector3d>("angular_velocity");
    if (_sdf->HasElement("delay_s"))
      this->delayS = _sdf->Get<double>("delay_s");
    if (_sdf->HasElement("rolling_resistance_decel_mps2"))
      this->rollingResistanceDecelMps2 = _sdf->Get<double>("rolling_resistance_decel_mps2");
    if (_sdf->HasElement("rolling_resistance_mass_kg"))
      this->rollingResistanceMassKg = _sdf->Get<double>("rolling_resistance_mass_kg");
    if (_sdf->HasElement("rolling_resistance_ball_radius_m"))
      this->rollingResistanceBallRadiusM = _sdf->Get<double>("rolling_resistance_ball_radius_m");
    if (_sdf->HasElement("rolling_resistance_stop_speed_threshold_mps"))
      this->rollingResistanceStopSpeedThresholdMps = _sdf->Get<double>("rolling_resistance_stop_speed_threshold_mps");
    if (_sdf->HasElement("debug_log_path"))
      this->debugLogPath = _sdf->Get<std::string>("debug_log_path");
    this->DebugLog("configure");
  }

  public: void PreUpdate(
    const gz::sim::UpdateInfo &_info,
    gz::sim::EntityComponentManager &_ecm) override
  {
    gz::sim::Model model(this->modelEntity);
    const auto linkEntity = model.LinkByName(_ecm, this->linkName);
    if (linkEntity == gz::sim::kNullEntity)
      return;

    gz::sim::Link link(linkEntity);
    if (this->applied)
    {
      this->ApplyRollingResistance(_info, _ecm, link);
      return;
    }
    if (!this->firstUpdateSeen)
    {
      this->firstUpdateSeen = true;
      this->firstUpdateSimTime = _info.simTime;
    }
    const auto elapsed = std::chrono::duration<double>(_info.simTime - this->firstUpdateSimTime).count();
    if (elapsed < this->delayS)
      return;

    link.SetLinearVelocity(_ecm, this->linearVelocity);
    link.SetAngularVelocity(_ecm, this->angularVelocity);
    link.EnableVelocityChecks(_ecm, true);
    this->applied = true;
    this->DebugLog("initial_velocity_applied");
  }

  public: void PostUpdate(
    const gz::sim::UpdateInfo &_info,
    const gz::sim::EntityComponentManager &_ecm) override
  {
    gz::sim::Model model(this->modelEntity);
    const auto linkEntity = model.LinkByName(_ecm, this->linkName);
    if (linkEntity == gz::sim::kNullEntity)
      return;

    gz::sim::Link link(linkEntity);
    const auto pose = link.WorldPose(_ecm);
    if (!pose)
      return;

    if (this->lastPostPoseSeen)
    {
      const double dt = std::chrono::duration<double>(_info.simTime - this->lastPostPoseSimTime).count();
      if (dt > 0.0)
      {
        this->observedVelocityVx = (pose->Pos().X() - this->lastPostPoseX) / dt;
        this->observedVelocityVy = (pose->Pos().Y() - this->lastPostPoseY) / dt;
        this->observedVelocityDt = dt;
        this->observedVelocitySeen = true;
      }
    }

    this->lastPostPoseSeen = true;
    this->lastPostPoseSimTime = _info.simTime;
    this->lastPostPoseX = pose->Pos().X();
    this->lastPostPoseY = pose->Pos().Y();
    this->lastPostPose = *pose;
    this->lastPostPoseRot = pose->Rot();
  }

  private: void ApplyRollingResistance(
    const gz::sim::UpdateInfo &_info,
    gz::sim::EntityComponentManager &_ecm,
    const gz::sim::Link &_link)
  {
    if (_info.paused || this->rollingResistanceDecelMps2 <= 0.0 || this->rollingResistanceMassKg <= 0.0)
      return;
    if (!this->observedVelocitySeen || this->observedVelocityDt <= 0.0)
    {
      if (!this->debugNoObservedVelocityLogged)
      {
        this->DebugLog("rolling_resistance_waiting_for_observed_velocity");
        this->debugNoObservedVelocityLogged = true;
      }
      return;
    }

    const double vx = this->observedVelocityVx;
    const double vy = this->observedVelocityVy;

    const double planarSpeed = std::sqrt(vx * vx + vy * vy);
    if (!this->debugResistanceActiveLogged)
    {
      this->DebugLog("rolling_resistance_active speed=" + std::to_string(planarSpeed) + " dt=" + std::to_string(this->observedVelocityDt));
      this->debugResistanceActiveLogged = true;
    }
    if (planarSpeed <= this->rollingResistanceStopSpeedThresholdMps)
    {
      _link.SetLinearVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      _link.SetAngularVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      return;
    }

    const double nextSpeed = std::max(0.0, planarSpeed - this->rollingResistanceDecelMps2 * this->observedVelocityDt);
    if (nextSpeed <= this->rollingResistanceStopSpeedThresholdMps)
    {
      _link.SetLinearVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      _link.SetAngularVelocity(_ecm, gz::math::Vector3d(0, 0, 0));
      return;
    }

    const double scale = nextSpeed / planarSpeed;
    const gz::math::Vector3d worldLinear(scale * vx, scale * vy, 0);
    const auto localLinear = this->lastPostPoseRot.Inverse().RotateVector(worldLinear);
    _link.SetLinearVelocity(_ecm, localLinear);

    const double radius = std::max(this->rollingResistanceBallRadiusM, 1e-9);
    const gz::math::Vector3d worldAngular(-worldLinear.Y() / radius, worldLinear.X() / radius, 0);
    const auto localAngular = this->lastPostPoseRot.Inverse().RotateVector(worldAngular);
    _link.SetAngularVelocity(_ecm, localAngular);
  }

  private: gz::sim::Entity modelEntity{gz::sim::kNullEntity};
  private: void DebugLog(const std::string &_message) const
  {
    if (this->debugLogPath.empty())
      return;
    std::ofstream out(this->debugLogPath, std::ios::app);
    out << _message << std::endl;
  }
  private: std::string linkName{"link"};
  private: gz::math::Vector3d linearVelocity{0, 0, 0};
  private: gz::math::Vector3d angularVelocity{0, 0, 0};
  private: double delayS{0.0};
  private: double rollingResistanceDecelMps2{0.0};
  private: double rollingResistanceMassKg{0.04593};
  private: double rollingResistanceBallRadiusM{0.021336};
  private: double rollingResistanceStopSpeedThresholdMps{0.03};
  private: bool firstUpdateSeen{false};
  private: std::chrono::steady_clock::duration firstUpdateSimTime{std::chrono::steady_clock::duration::zero()};
  private: bool lastPostPoseSeen{false};
  private: std::chrono::steady_clock::duration lastPostPoseSimTime{std::chrono::steady_clock::duration::zero()};
  private: double lastPostPoseX{0.0};
  private: double lastPostPoseY{0.0};
  private: gz::math::Pose3d lastPostPose{0, 0, 0, 0, 0, 0};
  private: gz::math::Quaterniond lastPostPoseRot{1, 0, 0, 0};
  private: bool observedVelocitySeen{false};
  private: double observedVelocityVx{0.0};
  private: double observedVelocityVy{0.0};
  private: double observedVelocityDt{0.0};
  private: std::string debugLogPath{""};
  private: bool debugNoObservedVelocityLogged{false};
  private: bool debugResistanceActiveLogged{false};
  private: bool applied{false};
};
}

GZ_ADD_PLUGIN(
  chasecar::InitialLinkVelocity,
  gz::sim::System,
  chasecar::InitialLinkVelocity::ISystemConfigure,
  chasecar::InitialLinkVelocity::ISystemPreUpdate,
  chasecar::InitialLinkVelocity::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(
  chasecar::InitialLinkVelocity,
  "chasecar::InitialLinkVelocity")
"""


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


def _vector_text(vector: dict[str, float]) -> str:
    return " ".join(f"{_clean_float(float(vector[key])):.9f}" for key in ("x", "y", "z"))


def _clean_float(value: float, *, epsilon: float = 1e-12) -> float:
    return 0.0 if abs(float(value)) < epsilon else float(value)


def direct_velocity_components(
    *,
    initial_speed_mps: float,
    heading_deg: float,
    ball_radius_m: float,
    rolling_angular_velocity: bool = True,
) -> dict[str, Any]:
    speed = max(float(initial_speed_mps), 0.0)
    heading_rad = math.radians(float(heading_deg))
    radius = max(float(ball_radius_m), 1e-9)
    linear = {
        "x": speed * math.cos(heading_rad),
        "y": speed * math.sin(heading_rad),
        "z": 0.0,
    }
    angular = {"x": 0.0, "y": 0.0, "z": 0.0}
    if rolling_angular_velocity and speed > 0.0:
        angular = {
            "x": -linear["y"] / radius,
            "y": linear["x"] / radius,
            "z": 0.0,
        }
    return {
        "requested_initial_speed_mps": round(speed, 6),
        "requested_heading_deg": round(float(heading_deg), 6),
        "rolling_angular_velocity": bool(rolling_angular_velocity),
        "linear_velocity_mps": {key: _clean_float(round(value, 9)) for key, value in linear.items()},
        "angular_velocity_radps": {key: _clean_float(round(value, 9)) for key, value in angular.items()},
        "ball_radius_m": round(radius, 9),
    }


def compile_initial_velocity_plugin(*, compose_project: str, plugin_dir: Path) -> dict[str, Any]:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    source_path = plugin_dir / "initial_link_velocity_system.cc"
    library_path = plugin_dir / "libchasecar_initial_link_velocity_system.so"
    source_path.write_text(INITIAL_LINK_VELOCITY_PLUGIN_SOURCE.lstrip(), encoding="utf-8")

    script = f"""
set -eo pipefail
SRC={json.dumps(to_container_repo_path(source_path))}
OUT={json.dumps(to_container_repo_path(library_path))}
g++ -std=c++17 -shared -fPIC "$SRC" -o "$OUT" \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_sim_vendor/include/gz/sim9 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_plugin_vendor/include/gz/plugin3 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_math_vendor/include/gz/math8 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_msgs_vendor/include/gz/msgs11 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_transport_vendor/include/gz/transport14 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_utils_vendor/include/gz/utils3 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_common_vendor/include/gz/common6 \
  -I/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/sdformat_vendor/include/gz/sdformat15 \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_sim_vendor/lib \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_plugin_vendor/lib \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_math_vendor/lib \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_msgs_vendor/lib \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_transport_vendor/lib \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/gz_common_vendor/lib \
  -L/opt/ros/${{CORE_ROS_DISTRO:-kilted}}/opt/sdformat_vendor/lib \
  -lgz-sim9 -lgz-plugin3 -lgz-math8 -lgz-msgs11 -lgz-transport14 -lgz-transport14-parameters -lgz-common6 -lsdformat15
test -s "$OUT"
"""
    rc, output = docker_exec(compose_project, script, timeout_s=60.0)
    return {
        "source_path": str(source_path),
        "library_path": str(library_path),
        "library_path_container": to_container_repo_path(library_path),
        "returncode": rc,
        "output": output,
        "pass": rc == 0,
    }


def write_direct_velocity_ball_sdf(
    *,
    base_ball_sdf: Path,
    output_sdf: Path,
    plugin_library_container_path: str,
    link_name: str,
    velocity_request: dict[str, Any],
    delay_s: float,
    rolling_resistance_decel_mps2: float = 0.0,
    rolling_resistance_mass_kg: float = 0.04593,
    rolling_resistance_ball_radius_m: float = 0.021336,
    rolling_resistance_stop_speed_threshold_mps: float = 0.03,
    debug_log_path_container: str = "",
) -> None:
    tree = ET.parse(base_ball_sdf)
    root = tree.getroot()
    model = root.find("model")
    if model is None:
        raise ValueError(f"{base_ball_sdf} does not contain an SDF model")
    plugin = ET.SubElement(
        model,
        "plugin",
        {
            "filename": plugin_library_container_path,
            "name": "chasecar::InitialLinkVelocity",
        },
    )
    ET.SubElement(plugin, "link_name").text = str(link_name)
    ET.SubElement(plugin, "linear_velocity").text = _vector_text(velocity_request["linear_velocity_mps"])
    ET.SubElement(plugin, "angular_velocity").text = _vector_text(velocity_request["angular_velocity_radps"])
    ET.SubElement(plugin, "delay_s").text = f"{max(0.0, float(delay_s)):.6f}"
    if debug_log_path_container:
        ET.SubElement(plugin, "debug_log_path").text = debug_log_path_container
    if float(rolling_resistance_decel_mps2) > 0.0:
        ET.SubElement(plugin, "rolling_resistance_mass_kg").text = f"{float(rolling_resistance_mass_kg):.9f}"
        ET.SubElement(plugin, "rolling_resistance_ball_radius_m").text = f"{float(rolling_resistance_ball_radius_m):.9f}"
        ET.SubElement(plugin, "rolling_resistance_decel_mps2").text = f"{float(rolling_resistance_decel_mps2):.9f}"
        ET.SubElement(plugin, "rolling_resistance_stop_speed_threshold_mps").text = f"{float(rolling_resistance_stop_speed_threshold_mps):.9f}"
    output_sdf.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_sdf, encoding="utf-8", xml_declaration=True)


def prepare_direct_velocity_ball_model(
    args: argparse.Namespace,
    *,
    run_index: int,
    artifact_dir: Path,
    ball_radius_m: float,
    ball_mass_kg: float,
) -> dict[str, Any]:
    velocity_request = direct_velocity_components(
        initial_speed_mps=args.initial_speed_mps,
        heading_deg=args.initial_heading_deg,
        ball_radius_m=ball_radius_m,
        rolling_angular_velocity=not bool(args.no_rolling_angular_velocity),
    )
    plugin = compile_initial_velocity_plugin(
        compose_project=args.compose_project,
        plugin_dir=artifact_dir / "direct_velocity_plugin",
    )
    prepared_sdf = artifact_dir / f"run_{run_index:02d}_direct_velocity_ball.sdf"
    debug_log_path = artifact_dir / f"run_{run_index:02d}_physics_plugin.log"
    if plugin["pass"]:
        write_direct_velocity_ball_sdf(
            base_ball_sdf=Path(args.ball_model_sdf),
            output_sdf=prepared_sdf,
            plugin_library_container_path=str(plugin["library_path_container"]),
            link_name=args.initial_velocity_link_name,
            velocity_request=velocity_request,
            delay_s=args.initial_velocity_delay_s,
            rolling_resistance_decel_mps2=args.rolling_resistance_decel_mps2,
            rolling_resistance_mass_kg=ball_mass_kg,
            rolling_resistance_ball_radius_m=ball_radius_m,
            rolling_resistance_stop_speed_threshold_mps=args.rolling_resistance_stop_speed_threshold_mps,
            debug_log_path_container=to_container_repo_path(debug_log_path),
        )
    return {
        "method": "direct_velocity",
        "pass": bool(plugin["pass"] and prepared_sdf.exists()),
        "prepared_model_sdf": str(prepared_sdf),
        "initial_velocity_link_name": args.initial_velocity_link_name,
        "initial_velocity_delay_s": round(max(0.0, float(args.initial_velocity_delay_s)), 6),
        "rolling_resistance_decel_mps2": round(max(0.0, float(args.rolling_resistance_decel_mps2)), 6),
        "rolling_resistance_stop_speed_threshold_mps": round(
            max(0.0, float(args.rolling_resistance_stop_speed_threshold_mps)),
            6,
        ),
        "debug_log_path": str(debug_log_path),
        "velocity_request": velocity_request,
        "plugin": plugin,
    }


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
    set_pose_after_spawn: bool = True,
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
SET_POSE_AFTER_SPAWN={json.dumps("true" if set_pose_after_spawn else "false")}
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
if [[ "$rc" -eq 0 && "$SET_POSE_AFTER_SPAWN" == "true" ]]; then
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
        "set_pose_after_spawn": bool(set_pose_after_spawn),
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


def run_one(
    args: argparse.Namespace,
    *,
    run_index: int,
    artifact_dir: Path,
    reference_band: Any,
    ball_profile: Any,
) -> dict[str, Any]:
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
    launch_payload: dict[str, Any] = {}
    ball_model_sdf = Path(args.ball_model_sdf)
    set_pose_after_spawn = True
    if args.launch_method == "direct_velocity":
        launch_payload = prepare_direct_velocity_ball_model(
            args,
            run_index=run_index,
            artifact_dir=artifact_dir,
            ball_radius_m=float(ball_profile.radius_m),
            ball_mass_kg=float(ball_profile.mass_kg),
        )
        if not bool(launch_payload.get("pass", False)):
            write_json(spawn_log_path, {"ramp": ramp_spawn, "ball": {}, "launch": launch_payload})
            raise RuntimeError(f"launch impulse failed; see {spawn_log_path}")
        ball_model_sdf = Path(str(launch_payload.get("prepared_model_sdf", args.ball_model_sdf)))
        set_pose_after_spawn = False
    ball_spawn = spawn_model(
        compose_project=args.compose_project,
        world_name=args.world_name,
        model_sdf=ball_model_sdf,
        model_name=args.ball_model_name,
        x=args.ball_start_x,
        y=args.ball_start_y,
        z=args.ball_start_z,
        yaw=0.0,
        set_pose_after_spawn=set_pose_after_spawn,
    )
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

    if args.roll_start_selection == "auto":
        roll_start_selection = "first_motion" if args.launch_method == "direct_velocity" else "peak_speed"
    else:
        roll_start_selection = args.roll_start_selection
    metrics = summarize_roll_samples(
        samples,
        ground_start_x_m=args.ground_start_x,
        stop_speed_threshold_mps=reference_band.stop_speed_threshold_mps,
        rest_dwell_s=reference_band.rest_dwell_s,
        start_selection=roll_start_selection,
        motion_start_speed_threshold_mps=args.motion_start_speed_threshold_mps,
    )
    if args.launch_method == "direct_velocity" and metrics.get("observed"):
        end_pose = metrics.get("end_pose", {}) if isinstance(metrics.get("end_pose"), dict) else {}
        end_x = float(end_pose.get("x", args.ball_start_x) or args.ball_start_x)
        end_y = float(end_pose.get("y", args.ball_start_y) or args.ball_start_y)
        roll_distance = math.hypot(end_x - float(args.ball_start_x), end_y - float(args.ball_start_y))
        lateral_drift = abs(end_y - float(args.ball_start_y))
        effective_decel = deceleration_from_stop(args.initial_speed_mps, roll_distance) if roll_distance > 0.0 else 0.0
        metrics.update(
            {
                "start_selection": "configured_launch_pose",
                "reference_initial_speed_mps": round(max(0.0, float(args.initial_speed_mps)), 6),
                "start_pose": {
                    "x": round(float(args.ball_start_x), 6),
                    "y": round(float(args.ball_start_y), 6),
                    "t_s": 0.0,
                },
                "roll_distance_m": round(roll_distance, 6),
                "lateral_drift_m": round(lateral_drift, 6),
                "lateral_drift_ratio": round(lateral_drift / max(abs(end_x - float(args.ball_start_x)), 1e-6), 6),
                "effective_decel_mps2": round(effective_decel, 6),
                "effective_mu": round(effective_decel / G_ACCEL_MPS2, 6) if effective_decel > 0.0 else 0.0,
            }
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
    parser.add_argument("--launch-method", choices=("direct_velocity", "gravity_impulse", "ramp"), default="direct_velocity")
    parser.add_argument("--initial-speed-mps", type=float, default=1.0)
    parser.add_argument("--initial-heading-deg", type=float, default=0.0)
    parser.add_argument("--initial-velocity-link-name", default="link")
    parser.add_argument("--initial-velocity-delay-s", type=float, default=0.0)
    parser.add_argument("--no-rolling-angular-velocity", action="store_true")
    parser.add_argument("--rolling-resistance-decel-mps2", type=float, default=0.0)
    parser.add_argument("--rolling-resistance-stop-speed-threshold-mps", type=float, default=0.03)
    parser.add_argument("--roll-start-selection", choices=("auto", "peak_speed", "first_motion"), default="auto")
    parser.add_argument("--motion-start-speed-threshold-mps", type=float, default=0.05)
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
            result = run_one(
                args,
                run_index=run_index,
                artifact_dir=artifact_dir,
                reference_band=reference_band,
                ball_profile=ball_profile,
            )
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
