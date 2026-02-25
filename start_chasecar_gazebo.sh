#!/usr/bin/env bash
set -e
source /opt/ros/humble/setup.bash
export DISPLAY=:0

ROS2_WS="${ROS2_WS:-$HOME/ros2_ws}"
PACKAGE_DIR="$ROS2_WS/src/chasecar"
if [ ! -d "$PACKAGE_DIR" ] && [ -d "$ROS2_WS/src/chasebot_description" ]; then
  PACKAGE_DIR="$ROS2_WS/src/chasebot_description"
fi

WORLD_FILE="${WORLD_FILE:-$PACKAGE_DIR/ros2_config/worlds/multi_ball_test_world.world}"

if [ ! -f "$WORLD_FILE" ]; then
  echo "World file not found: $WORLD_FILE" >&2
  exit 1
fi

ros2 launch gazebo_ros gazebo.launch.py world:="$WORLD_FILE" >> /tmp/chasecar_gazebo.log 2>&1
