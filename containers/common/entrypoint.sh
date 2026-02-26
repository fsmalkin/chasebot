#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${ROS_DISTRO:-}" && -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
fi

if [[ -d "/root/ros2_ws/install" && -f "/root/ros2_ws/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "/root/ros2_ws/install/setup.bash"
fi

exec "$@"
