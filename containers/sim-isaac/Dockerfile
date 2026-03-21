ARG ISAAC_SIM_IMAGE=nvcr.io/nvidia/isaac-sim:4.5.0
FROM ${ISAAC_SIM_IMAGE}

SHELL ["/bin/bash", "-c"]

COPY containers/common/entrypoint.sh /opt/chasecar/entrypoint.sh
COPY containers/sim-isaac/start_isaac_lane.sh /opt/chasecar/start_isaac_lane.sh
RUN chmod +x /opt/chasecar/entrypoint.sh /opt/chasecar/start_isaac_lane.sh

WORKDIR /workspaces/chasecar
ENTRYPOINT ["/opt/chasecar/entrypoint.sh"]
CMD ["bash", "-lc", "/opt/chasecar/start_isaac_lane.sh"]
