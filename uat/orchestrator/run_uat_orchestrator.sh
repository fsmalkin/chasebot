#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/workspaces/chasecar}"
MODE="${CHASECAR_UAT_MODE:-prepare}"
RUNTIME_TARGET="${CHASECAR_RUNTIME_TARGET:-robot_fidelity_orin}"
SIM_LANE="${CHASECAR_SIM_LANE:-jetty_gate}"
INFERENCE_BACKEND="${CHASECAR_INFERENCE_BACKEND:-tensorrt_int8}"
CONTAINER_ROS_DISTRO="${ROS_DISTRO:-kilted}"
STEP_TIMEOUT_S="${CHASECAR_STEP_TIMEOUT_S:-900}"
NAV2_DURATION_S="${CHASECAR_NAV2_DURATION_S:-120}"
UAT_PROFILE="${CHASECAR_UAT_PROFILE:-compat}"
UAT_INFERENCE_DEVICE="${CHASECAR_UAT_INFERENCE_DEVICE:-cuda:0}"
NAV2_WORLD_NAME="${CHASECAR_NAV2_WORLD_NAME:-yolo_test_world}"
NAV2_MODEL_SDF="${CHASECAR_NAV2_MODEL_SDF:-ros2_config/frisbee_target_ball.sdf}"
NAV2_MODEL_NAME="${CHASECAR_NAV2_MODEL_NAME:-uat_nav2_target}"
NAV2_TARGET_X="${CHASECAR_NAV2_TARGET_X:-1.2}"
NAV2_TARGET_Y="${CHASECAR_NAV2_TARGET_Y:-0.0}"
NAV2_TARGET_Z="${CHASECAR_NAV2_TARGET_Z:-0.05}"
NAV2_START_BRIDGE="${CHASECAR_NAV2_START_BRIDGE:-true}"
NAV2_BRIDGE_SCRIPT="${CHASECAR_NAV2_BRIDGE_SCRIPT:-ros2_scripts/yolo_3d_to_nav2_bridge.py}"
NAV2_BRIDGE_START_DELAY_S="${CHASECAR_NAV2_BRIDGE_START_DELAY_S:-4}"

if [[ ! -d "${REPO_ROOT}" ]]; then
  echo "[uat-orchestrator] Missing repo path: ${REPO_ROOT}" >&2
  exit 2
fi

cd "${REPO_ROOT}"

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
SESSION_DIR="artifacts/session/${RUN_ID}"
LOG_DIR="${SESSION_DIR}/logs"
STEP_RESULTS_FILE="${SESSION_DIR}/step_results.ndjson"
mkdir -p "${LOG_DIR}"
: > "${STEP_RESULTS_FILE}"

if [[ ! -f "/opt/ros/${CONTAINER_ROS_DISTRO}/setup.bash" ]]; then
  echo "[uat-orchestrator] Missing ROS setup: /opt/ros/${CONTAINER_ROS_DISTRO}/setup.bash" >&2
  exit 2
fi
set +u
source "/opt/ros/${CONTAINER_ROS_DISTRO}/setup.bash"
if [[ -f "/root/ros2_ws/install/setup.bash" ]]; then
  source "/root/ros2_ws/install/setup.bash"
fi
set -u

append_step() {
  local id="$1"
  local status="$2"
  local failure_class="$3"
  local artifact_dir="$4"
  local exit_code="$5"
  local log_file="$6"

  jq -nc \
    --arg id "${id}" \
    --arg status "${status}" \
    --arg failure_class "${failure_class}" \
    --arg artifact_dir "${artifact_dir}" \
    --argjson exit_code "${exit_code}" \
    --arg log_file "${log_file}" \
    '{
      id: $id,
      status: $status,
      failure_class: $failure_class,
      artifact_dir: (if $artifact_dir == "" then null else $artifact_dir end),
      exit_code: $exit_code,
      log_file: $log_file
    }' >> "${STEP_RESULTS_FILE}"

  echo "STEP_RESULT=${id}:${status}:${artifact_dir}"
}

run_cmd_with_timeout() {
  local log_file="$1"
  shift
  local rc=0
  if command -v timeout >/dev/null 2>&1; then
    timeout "${STEP_TIMEOUT_S}s" "$@" >"${log_file}" 2>&1 || rc=$?
  else
    "$@" >"${log_file}" 2>&1 || rc=$?
  fi
  echo "${rc}"
}

latest_file() {
  local pattern="$1"
  ls -1dt ${pattern} 2>/dev/null | head -n1 || true
}

has_world_create_service_error() {
  local log_file="$1"
  grep -Eq 'Waiting for service \[/world/.*/create\] to become available' "${log_file}" 2>/dev/null
}

remove_nav2_target() {
  local log_file="$1"
  local req
  req="name: \"${NAV2_MODEL_NAME}\" type: 2"

  if command -v gz >/dev/null 2>&1; then
    gz service \
      -s "/world/${NAV2_WORLD_NAME}/remove/blocking" \
      --reqtype gz.msgs.Entity \
      --reptype gz.msgs.Boolean \
      --timeout 2000 \
      --req "${req}" >>"${log_file}" 2>&1 || true
    return 0
  fi

  if command -v ign >/dev/null 2>&1; then
    ign service \
      -s "/world/${NAV2_WORLD_NAME}/remove/blocking" \
      --reqtype ignition.msgs.Entity \
      --reptype ignition.msgs.Boolean \
      --timeout 2000 \
      --req "${req}" >>"${log_file}" 2>&1 || true
    return 0
  fi

  echo "[nav2] gz/ign service binary not found for cleanup" >>"${log_file}" 2>&1
  return 0
}

spawn_nav2_target() {
  local log_file="$1"
  local model_path="${NAV2_MODEL_SDF}"
  if [[ "${model_path}" != /* ]]; then
    model_path="${REPO_ROOT}/${model_path}"
  fi

  if [[ ! -f "${model_path}" ]]; then
    echo "[nav2] Missing model SDF: ${model_path}" >>"${log_file}" 2>&1
    return 1
  fi

  remove_nav2_target "${log_file}"

  ros2 run ros_gz_sim create \
    -world "${NAV2_WORLD_NAME}" \
    -file "${model_path}" \
    -name "${NAV2_MODEL_NAME}" \
    -x "${NAV2_TARGET_X}" \
    -y "${NAV2_TARGET_Y}" \
    -z "${NAV2_TARGET_Z}" >>"${log_file}" 2>&1
}

run_prepare() {
  local log_file="${LOG_DIR}/prepare.log"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 -m py_compile \
    scripts/coordinate_uat_runner.py \
    scripts/orientation_uat_runner.py \
    scripts/nav2_readiness_runner.py \
    scripts/capture_topic_image.py)

  if [[ "${rc}" -eq 0 ]]; then
    append_step "prepare" "pass" "" "" 0 "${log_file}"
    return 0
  fi
  local failure_class="command_failed"
  if [[ "${rc}" -eq 124 ]]; then
    failure_class="timeout"
  fi
  append_step "prepare" "fail" "${failure_class}" "" "${rc}" "${log_file}"
  return 2
}

run_coordinate() {
  local log_file="${LOG_DIR}/coordinate.log"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/coordinate_uat_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "ros2_config/config/uat_coordinates.yaml")

  local summary_path
  summary_path="$(latest_file "artifacts/uat/*/summary.json")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi

  if [[ "${rc}" -eq 0 && -n "${summary_path}" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      append_step "coordinate" "pass" "" "${artifact_dir}" 0 "${log_file}"
      return 0
    fi
    local failure_class="threshold_failed"
    if has_world_create_service_error "${log_file}"; then
      failure_class="service_unavailable"
    fi
    append_step "coordinate" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}"
    return 2
  fi

  local failure_class="command_failed"
  if has_world_create_service_error "${log_file}"; then
    failure_class="service_unavailable"
  elif [[ "${rc}" -eq 124 ]]; then
    failure_class="timeout"
  elif [[ -z "${summary_path}" ]]; then
    failure_class="missing_artifact"
  fi
  append_step "coordinate" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}"
  return 2
}

run_orientation() {
  local log_file="${LOG_DIR}/orientation.log"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/orientation_uat_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "ros2_config/config/orientation_scenarios.yaml")

  local summary_path
  summary_path="$(latest_file "artifacts/orientation/*/orientation_summary.json")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi

  if [[ "${rc}" -eq 0 && -n "${summary_path}" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      append_step "orientation" "pass" "" "${artifact_dir}" 0 "${log_file}"
      return 0
    fi
    append_step "orientation" "fail" "threshold_failed" "${artifact_dir}" 2 "${log_file}"
    return 2
  fi

  local failure_class="command_failed"
  if [[ "${rc}" -eq 124 ]]; then
    failure_class="timeout"
  elif [[ -z "${summary_path}" ]]; then
    failure_class="missing_artifact"
  fi
  append_step "orientation" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}"
  return 2
}

run_nav2() {
  local log_file="${LOG_DIR}/nav2.log"
  local prep_log="${LOG_DIR}/nav2_prep.log"
  local bridge_log="${LOG_DIR}/nav2_bridge.log"
  local bridge_pid=""
  : > "${prep_log}"

  if [[ "${NAV2_START_BRIDGE}" == "true" ]]; then
    if [[ ! -f "${REPO_ROOT}/${NAV2_BRIDGE_SCRIPT}" ]]; then
      echo "[nav2] bridge script missing: ${REPO_ROOT}/${NAV2_BRIDGE_SCRIPT}" >>"${prep_log}" 2>&1
      append_step "nav2" "fail" "missing_artifact" "" 2 "${prep_log}"
      return 2
    fi
    python3 "${REPO_ROOT}/${NAV2_BRIDGE_SCRIPT}" --ros-args -p use_sim_time:=true >"${bridge_log}" 2>&1 &
    bridge_pid="$!"
    sleep "${NAV2_BRIDGE_START_DELAY_S}"
  fi

  if ! spawn_nav2_target "${prep_log}"; then
    if [[ -n "${bridge_pid}" ]]; then
      kill "${bridge_pid}" 2>/dev/null || true
      wait "${bridge_pid}" 2>/dev/null || true
    fi
    local failure_class="command_failed"
    if has_world_create_service_error "${prep_log}"; then
      failure_class="service_unavailable"
    elif grep -Eq "Missing model SDF" "${prep_log}" 2>/dev/null; then
      failure_class="missing_artifact"
    fi
    append_step "nav2" "fail" "${failure_class}" "" 2 "${prep_log}"
    return 2
  fi

  sleep 2

  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/nav2_readiness_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "ros2_config/config/nav2_readiness.yaml" \
    --duration-s "${NAV2_DURATION_S}")

  if [[ -n "${bridge_pid}" ]]; then
    kill "${bridge_pid}" 2>/dev/null || true
    wait "${bridge_pid}" 2>/dev/null || true
  fi
  remove_nav2_target "${prep_log}"

  local summary_path
  summary_path="$(latest_file "artifacts/nav2/*/nav_summary.json")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi

  if [[ "${rc}" -eq 0 && -n "${summary_path}" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      append_step "nav2" "pass" "" "${artifact_dir}" 0 "${log_file}"
      return 0
    fi
    append_step "nav2" "fail" "threshold_failed" "${artifact_dir}" 2 "${log_file}"
    return 2
  fi

  local failure_class="command_failed"
  if [[ "${rc}" -eq 124 ]]; then
    failure_class="timeout"
  elif has_world_create_service_error "${log_file}"; then
    failure_class="service_unavailable"
  elif [[ -z "${summary_path}" ]]; then
    failure_class="missing_artifact"
  fi
  append_step "nav2" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}"
  return 2
}

overall_status="pass"
case "${MODE}" in
  prepare)
    run_prepare || overall_status="fail"
    ;;
  coordinate)
    run_coordinate || overall_status="fail"
    ;;
  orientation)
    run_orientation || overall_status="fail"
    ;;
  nav2)
    run_nav2 || overall_status="fail"
    ;;
  first_uat)
    run_coordinate || overall_status="fail"
    ;;
  full_replay)
    run_coordinate || overall_status="fail"
    run_orientation || overall_status="fail"
    run_nav2 || overall_status="fail"
    ;;
  *)
    echo "[uat-orchestrator] Unsupported mode: ${MODE}" >&2
    exit 2
    ;;
esac

steps_json="$(jq -s '.' "${STEP_RESULTS_FILE}")"
readiness_path="${SESSION_DIR}/readiness_report.json"
manifest_path="${SESSION_DIR}/manifest.json"

jq -n \
  --arg run_id "${RUN_ID}" \
  --arg mode "${MODE}" \
  --arg runtime_target "${RUNTIME_TARGET}" \
  --arg sim_lane "${SIM_LANE}" \
  --arg inference_backend "${INFERENCE_BACKEND}" \
  --arg container_core_ros_distro "${CONTAINER_ROS_DISTRO}" \
  --arg execution_lane "container_kilted" \
  --arg status "${overall_status}" \
  --arg step_timeout_s "${STEP_TIMEOUT_S}" \
  --arg nav2_duration_s "${NAV2_DURATION_S}" \
  --arg generated_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson steps "${steps_json}" \
  '{
    run_id: $run_id,
    mode: $mode,
    generated_utc: $generated_utc,
    runtime_target: $runtime_target,
    sim_lane: $sim_lane,
    inference_backend: $inference_backend,
    execution_lane: $execution_lane,
    container_core_ros_distro: $container_core_ros_distro,
    step_timeout_s: ($step_timeout_s | tonumber),
    nav2_duration_s: ($nav2_duration_s | tonumber),
    status: $status,
    pass: ($status == "pass"),
    steps: $steps
  }' > "${readiness_path}"

jq -n \
  --arg run_id "${RUN_ID}" \
  --arg mode "${MODE}" \
  --arg generated_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg readiness_report "${readiness_path}" \
  --arg logs "${LOG_DIR}" \
  --arg runtime_target "${RUNTIME_TARGET}" \
  --arg sim_lane "${SIM_LANE}" \
  --arg inference_backend "${INFERENCE_BACKEND}" \
  --arg execution_lane "container_kilted" \
  --argjson steps "${steps_json}" \
  '{
    run_id: $run_id,
    mode: $mode,
    generated_utc: $generated_utc,
    runtime_target: $runtime_target,
    sim_lane: $sim_lane,
    inference_backend: $inference_backend,
    execution_lane: $execution_lane,
    readiness_report: $readiness_report,
    artifacts: {
      logs: $logs
    },
    steps: $steps
  }' > "${manifest_path}"

echo "ARTIFACT_DIR=${SESSION_DIR}"
echo "READINESS_REPORT=${readiness_path}"
echo "UAT_ORCHESTRATOR_STATUS=${overall_status}"

if [[ "${overall_status}" == "pass" ]]; then
  exit 0
fi
exit 2
