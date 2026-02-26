ARG BRIDGE_ROS_DISTRO=jazzy
FROM osrf/ros:${BRIDGE_ROS_DISTRO}-ros-base

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=${BRIDGE_ROS_DISTRO}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    jq \
    python3-yaml \
    && \
    for pkg in \
      "ros-${BRIDGE_ROS_DISTRO}-ros-gz-bridge" \
      "ros-${BRIDGE_ROS_DISTRO}-ros-gz-sim"; do \
      if apt-cache show "${pkg}" >/dev/null 2>&1; then \
        apt-get install -y --no-install-recommends "${pkg}"; \
      else \
        echo "[bridge-jazzy] package unavailable in apt index: ${pkg}"; \
      fi; \
    done && \
    rm -rf /var/lib/apt/lists/*

COPY containers/common/entrypoint.sh /opt/chasecar/entrypoint.sh
RUN chmod +x /opt/chasecar/entrypoint.sh && mkdir -p /root/ros2_ws/src

WORKDIR /workspaces/chasecar
ENTRYPOINT ["/opt/chasecar/entrypoint.sh"]
CMD ["bash"]
