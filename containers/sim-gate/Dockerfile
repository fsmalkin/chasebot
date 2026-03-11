ARG ROS_DISTRO=kilted
FROM osrf/ros:${ROS_DISTRO}-desktop-full

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=${ROS_DISTRO}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    ffmpeg \
    fluxbox \
    jq \
    libgl1-mesa-dri \
    mesa-utils \
    novnc \
    websockify \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    python3-pip \
    python3-opencv \
    x11-xserver-utils \
    x11vnc \
    xauth \
    xserver-xorg-core \
    xserver-xorg-video-dummy \
    xvfb \
    && \
    for pkg in \
      "ros-${ROS_DISTRO}-nav2-bringup" \
      "ros-${ROS_DISTRO}-ros-gz" \
      "ros-${ROS_DISTRO}-ros-gz-bridge" \
      "ros-${ROS_DISTRO}-ros-gz-sim" \
      "ros-${ROS_DISTRO}-gz-ros2-control"; do \
      if apt-cache show "${pkg}" >/dev/null 2>&1; then \
        apt-get install -y --no-install-recommends "${pkg}"; \
      else \
        echo "[sim-gate] package unavailable in apt index: ${pkg}"; \
      fi; \
    done && \
    rm -rf /var/lib/apt/lists/*

COPY containers/common/entrypoint.sh /opt/chasecar/entrypoint.sh
RUN chmod +x /opt/chasecar/entrypoint.sh && mkdir -p /root/ros2_ws/src

WORKDIR /workspaces/chasecar
ENTRYPOINT ["/opt/chasecar/entrypoint.sh"]
CMD ["bash"]
