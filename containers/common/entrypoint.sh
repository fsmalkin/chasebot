#!/usr/bin/env bash
set -euo pipefail

source_safe() {
  local script_path="$1"
  # ROS setup scripts can reference unset vars; disable nounset while sourcing.
  set +u
  # shellcheck disable=SC1090
  source "${script_path}"
  set -u
}

if [[ -n "${ROS_DISTRO:-}" && -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  source_safe "/opt/ros/${ROS_DISTRO}/setup.bash"
fi

if [[ -d "/root/ros2_ws/install" && -f "/root/ros2_ws/install/setup.bash" ]]; then
  source_safe "/root/ros2_ws/install/setup.bash"
fi

exec "$@"
