ARG ROS_DISTRO=kilted
FROM osrf/ros:${ROS_DISTRO}-desktop-full

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=${ROS_DISTRO}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    ros-${ROS_DISTRO}-nav2-bringup \
    ros-${ROS_DISTRO}-nav2-msgs \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    python3-pip \
    python3-opencv \
    python3-typing-extensions \
    python3-yaml \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    onnx==1.17.0 \
    onnxruntime==1.20.1

COPY containers/common/entrypoint.sh /opt/chasecar/entrypoint.sh
RUN sed -i 's/\r$//' /opt/chasecar/entrypoint.sh && chmod +x /opt/chasecar/entrypoint.sh && mkdir -p /root/ros2_ws/src

WORKDIR /workspaces/chasecar
ENTRYPOINT ["/opt/chasecar/entrypoint.sh"]
CMD ["bash"]
