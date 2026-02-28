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

SNAPSHOT_WORLD_NAME="${CHASECAR_SNAPSHOT_WORLD_NAME:-${NAV2_WORLD_NAME}}"
SNAPSHOT_MODEL_SDF="${CHASECAR_SNAPSHOT_MODEL_SDF:-ros2_config/frisbee_target_ball.sdf}"
SNAPSHOT_MODEL_NAME="${CHASECAR_SNAPSHOT_MODEL_NAME:-uat_snapshot_target}"
SNAPSHOT_TARGET_X="${CHASECAR_SNAPSHOT_TARGET_X:-0.9}"
SNAPSHOT_TARGET_Y="${CHASECAR_SNAPSHOT_TARGET_Y:-0.0}"
SNAPSHOT_TARGET_Z="${CHASECAR_SNAPSHOT_TARGET_Z:-0.05}"
SNAPSHOT_RGB_TOPIC="${CHASECAR_SNAPSHOT_RGB_TOPIC:-/d415/color/image_raw}"
SNAPSHOT_DEBUG_TOPIC="${CHASECAR_SNAPSHOT_DEBUG_TOPIC:-/yolo/debug_image}"
SNAPSHOT_TIMEOUT_S="${CHASECAR_SNAPSHOT_TIMEOUT_S:-12}"
SNAPSHOT_MIN_MEAN_ABS_DIFF="${CHASECAR_SNAPSHOT_MIN_MEAN_ABS_DIFF:-1.5}"
SNAPSHOT_MIN_FRAMES="${CHASECAR_SNAPSHOT_MIN_FRAMES:-2}"

MULTI_TARGET_CONFIG="${CHASECAR_MULTI_TARGET_CONFIG:-ros2_config/config/multi_target_nav2.yaml}"
MULTI_TARGET_GOAL_TIMEOUT_S="${CHASECAR_MULTI_TARGET_GOAL_TIMEOUT_S:-55}"

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

append_blocked_step() {
  local id="$1"
  local reason="$2"
  local log_file="${LOG_DIR}/${id}_blocked.log"
  echo "${reason}" > "${log_file}"
  append_step "${id}" "blocked" "blocked_dependency" "" 2 "${log_file}"
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

resolve_model_path() {
  local model_path="$1"
  if [[ "${model_path}" == /* ]]; then
    echo "${model_path}"
  else
    echo "${REPO_ROOT}/${model_path}"
  fi
}

remove_model_by_name() {
  local world_name="$1"
  local model_name="$2"
  local log_file="$3"
  local req
  req="name: \"${model_name}\" type: 2"

  if command -v gz >/dev/null 2>&1; then
    gz service \
      -s "/world/${world_name}/remove/blocking" \
      --reqtype gz.msgs.Entity \
      --reptype gz.msgs.Boolean \
      --timeout 2000 \
      --req "${req}" >>"${log_file}" 2>&1 || true
    return 0
  fi

  if command -v ign >/dev/null 2>&1; then
    ign service \
      -s "/world/${world_name}/remove/blocking" \
      --reqtype ignition.msgs.Entity \
      --reptype ignition.msgs.Boolean \
      --timeout 2000 \
      --req "${req}" >>"${log_file}" 2>&1 || true
    return 0
  fi

  echo "[orchestrator] gz/ign service binary not found for cleanup" >>"${log_file}" 2>&1
  return 0
}

spawn_model() {
  local world_name="$1"
  local model_sdf="$2"
  local model_name="$3"
  local pos_x="$4"
  local pos_y="$5"
  local pos_z="$6"
  local log_file="$7"

  local resolved_model
  resolved_model="$(resolve_model_path "${model_sdf}")"
  if [[ ! -f "${resolved_model}" ]]; then
    echo "[orchestrator] Missing model SDF: ${resolved_model}" >>"${log_file}" 2>&1
    return 1
  fi

  remove_model_by_name "${world_name}" "${model_name}" "${log_file}"

  ros2 run ros_gz_sim create \
    -world "${world_name}" \
    -file "${resolved_model}" \
    -name "${model_name}" \
    -x "${pos_x}" \
    -y "${pos_y}" \
    -z "${pos_z}" >>"${log_file}" 2>&1
}

run_prepare() {
  local log_file="${LOG_DIR}/prepare.log"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 -m py_compile \
    scripts/coordinate_uat_runner.py \
    scripts/orientation_uat_runner.py \
    scripts/nav2_readiness_runner.py \
    scripts/multi_target_nav2_runner.py \
    scripts/capture_topic_image.py \
    scripts/image_diff_metrics.py)

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

run_snapshot() {
  local log_file="${LOG_DIR}/snapshot.log"
  local prep_log="${LOG_DIR}/snapshot_prep.log"
  local artifact_dir="artifacts/snapshots/${RUN_ID}"
  local rgb_file="${artifact_dir}/d415_color.png"
  local debug_file="${artifact_dir}/yolo_debug.png"
  local diff_json="${artifact_dir}/image_diff.json"
  local summary_json="${artifact_dir}/snapshot_summary.json"

  mkdir -p "${artifact_dir}"
  : > "${prep_log}"

  if ! spawn_model \
    "${SNAPSHOT_WORLD_NAME}" \
    "${SNAPSHOT_MODEL_SDF}" \
    "${SNAPSHOT_MODEL_NAME}" \
    "${SNAPSHOT_TARGET_X}" \
    "${SNAPSHOT_TARGET_Y}" \
    "${SNAPSHOT_TARGET_Z}" \
    "${prep_log}"; then
    local failure_class="command_failed"
    if has_world_create_service_error "${prep_log}"; then
      failure_class="service_unavailable"
    elif grep -Eq "Missing model SDF" "${prep_log}" 2>/dev/null; then
      failure_class="missing_artifact"
    fi
    append_step "snapshot" "fail" "${failure_class}" "${artifact_dir}" 2 "${prep_log}"
    return 2
  fi

  sleep 2

  local rgb_log="${artifact_dir}/capture_rgb.log"
  local debug_log="${artifact_dir}/capture_debug.log"
  local diff_log="${artifact_dir}/image_diff.log"

  local rgb_rc
  rgb_rc=$(run_cmd_with_timeout "${rgb_log}" python3 scripts/capture_topic_image.py \
    --topic "${SNAPSHOT_RGB_TOPIC}" \
    --output "${rgb_file}" \
    --timeout-s "${SNAPSHOT_TIMEOUT_S}" \
    --use-sim-time \
    --min-frames "${SNAPSHOT_MIN_FRAMES}" \
    --placeholder-label "rgb_timeout")

  local debug_rc
  debug_rc=$(run_cmd_with_timeout "${debug_log}" python3 scripts/capture_topic_image.py \
    --topic "${SNAPSHOT_DEBUG_TOPIC}" \
    --output "${debug_file}" \
    --timeout-s "${SNAPSHOT_TIMEOUT_S}" \
    --use-sim-time \
    --min-frames "${SNAPSHOT_MIN_FRAMES}" \
    --placeholder-label "debug_timeout")

  local diff_rc
  diff_rc=$(run_cmd_with_timeout "${diff_log}" python3 scripts/image_diff_metrics.py \
    --left "${rgb_file}" \
    --right "${debug_file}" \
    --json-out "${diff_json}")

  remove_model_by_name "${SNAPSHOT_WORLD_NAME}" "${SNAPSHOT_MODEL_NAME}" "${prep_log}"

  local capture_rgb_ok
  local capture_debug_ok
  capture_rgb_ok="$(grep -E '^CAPTURED=' "${rgb_log}" 2>/dev/null | tail -n1 | cut -d'=' -f2 | tr '[:upper:]' '[:lower:]' || true)"
  capture_debug_ok="$(grep -E '^CAPTURED=' "${debug_log}" 2>/dev/null | tail -n1 | cut -d'=' -f2 | tr '[:upper:]' '[:lower:]' || true)"

  local left_exists="false"
  local right_exists="false"
  local byte_identical="true"
  local mean_abs_diff="0"
  local shape_match="false"
  if [[ -f "${diff_json}" ]]; then
    left_exists="$(jq -r '.left_exists // false' "${diff_json}" 2>/dev/null || echo false)"
    right_exists="$(jq -r '.right_exists // false' "${diff_json}" 2>/dev/null || echo false)"
    byte_identical="$(jq -r 'if has("byte_identical") then .byte_identical else true end' "${diff_json}" 2>/dev/null || echo true)"
    mean_abs_diff="$(jq -r '.mean_abs_diff // 0' "${diff_json}" 2>/dev/null || echo 0)"
    shape_match="$(jq -r '.shape_match // false' "${diff_json}" 2>/dev/null || echo false)"
  fi

  local diff_pass="false"
  if awk -v a="${mean_abs_diff}" -v b="${SNAPSHOT_MIN_MEAN_ABS_DIFF}" 'BEGIN{exit !(a+0 >= b+0)}'; then
    diff_pass="true"
  fi

  local pass="false"
  if [[ "${rgb_rc}" -eq 0 && "${debug_rc}" -eq 0 && "${diff_rc}" -eq 0 \
     && "${capture_rgb_ok}" == "true" && "${capture_debug_ok}" == "true" \
     && "${left_exists}" == "true" && "${right_exists}" == "true" \
     && "${byte_identical}" != "true" && "${diff_pass}" == "true" ]]; then
    pass="true"
  fi

  jq -n \
    --arg run_id "${RUN_ID}" \
    --arg timestamp_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg rgb_topic "${SNAPSHOT_RGB_TOPIC}" \
    --arg debug_topic "${SNAPSHOT_DEBUG_TOPIC}" \
    --arg rgb_file "${rgb_file}" \
    --arg debug_file "${debug_file}" \
    --argjson rgb_capture_ok "$( [[ "${capture_rgb_ok}" == "true" ]] && echo true || echo false )" \
    --argjson debug_capture_ok "$( [[ "${capture_debug_ok}" == "true" ]] && echo true || echo false )" \
    --argjson left_exists "$( [[ "${left_exists}" == "true" ]] && echo true || echo false )" \
    --argjson right_exists "$( [[ "${right_exists}" == "true" ]] && echo true || echo false )" \
    --argjson shape_match "$( [[ "${shape_match}" == "true" ]] && echo true || echo false )" \
    --argjson byte_identical "$( [[ "${byte_identical}" == "true" ]] && echo true || echo false )" \
    --argjson mean_abs_diff "${mean_abs_diff}" \
    --argjson min_mean_abs_diff "${SNAPSHOT_MIN_MEAN_ABS_DIFF}" \
    --argjson pass "$( [[ "${pass}" == "true" ]] && echo true || echo false )" \
    '{
      run_id: $run_id,
      timestamp_utc: $timestamp_utc,
      rgb_topic: $rgb_topic,
      debug_topic: $debug_topic,
      captures: {
        rgb_path: $rgb_file,
        debug_path: $debug_file,
        rgb_capture_ok: $rgb_capture_ok,
        debug_capture_ok: $debug_capture_ok
      },
      image_diff: {
        left_exists: $left_exists,
        right_exists: $right_exists,
        shape_match: $shape_match,
        byte_identical: $byte_identical,
        mean_abs_diff: $mean_abs_diff,
        min_mean_abs_diff: $min_mean_abs_diff
      },
      pass: $pass
    }' > "${summary_json}"

  if [[ "${pass}" == "true" ]]; then
    append_step "snapshot" "pass" "" "${artifact_dir}" 0 "${log_file}"
    cat "${rgb_log}" "${debug_log}" "${diff_log}" > "${log_file}" 2>/dev/null || true
    return 0
  fi

  local failure_class="threshold_failed"
  if [[ "${rgb_rc}" -eq 124 || "${debug_rc}" -eq 124 || "${diff_rc}" -eq 124 ]]; then
    failure_class="timeout"
  elif [[ "${rgb_rc}" -ne 0 || "${debug_rc}" -ne 0 || "${diff_rc}" -ne 0 ]]; then
    failure_class="command_failed"
  elif [[ ! -f "${diff_json}" ]]; then
    failure_class="missing_artifact"
  fi
  cat "${rgb_log}" "${debug_log}" "${diff_log}" > "${log_file}" 2>/dev/null || true
  append_step "snapshot" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}"
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

  if ! spawn_model \
    "${NAV2_WORLD_NAME}" \
    "${NAV2_MODEL_SDF}" \
    "${NAV2_MODEL_NAME}" \
    "${NAV2_TARGET_X}" \
    "${NAV2_TARGET_Y}" \
    "${NAV2_TARGET_Z}" \
    "${prep_log}"; then

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
  remove_model_by_name "${NAV2_WORLD_NAME}" "${NAV2_MODEL_NAME}" "${prep_log}"

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

run_multi_target() {
  local log_file="${LOG_DIR}/multi_target.log"
  local cfg="${MULTI_TARGET_CONFIG}"
  if [[ "${cfg}" != /* ]]; then
    cfg="${REPO_ROOT}/${cfg}"
  fi

  if [[ ! -f "${cfg}" ]]; then
    append_step "multi_target" "fail" "missing_artifact" "" 2 "${log_file}"
    return 2
  fi

  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/multi_target_nav2_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "${cfg}" \
    --goal-timeout-s "${MULTI_TARGET_GOAL_TIMEOUT_S}")

  local summary_path
  summary_path="$(latest_file "artifacts/nav2_multi/*/multi_target_summary.json")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi

  if [[ "${rc}" -eq 0 && -n "${summary_path}" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      append_step "multi_target" "pass" "" "${artifact_dir}" 0 "${log_file}"
      return 0
    fi
    append_step "multi_target" "fail" "threshold_failed" "${artifact_dir}" 2 "${log_file}"
    return 2
  fi

  local failure_class="command_failed"
  if [[ "${rc}" -eq 124 ]]; then
    failure_class="timeout"
  elif [[ -z "${summary_path}" ]]; then
    failure_class="missing_artifact"
  fi
  append_step "multi_target" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}"
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
  snapshot)
    run_snapshot || overall_status="fail"
    ;;
  orientation)
    run_orientation || overall_status="fail"
    ;;
  nav2)
    run_nav2 || overall_status="fail"
    ;;
  multi_target)
    run_multi_target || overall_status="fail"
    ;;
  first_uat)
    run_coordinate || overall_status="fail"
    ;;
  full_replay)
    run_coordinate || overall_status="fail"
    run_orientation || overall_status="fail"
    run_nav2 || overall_status="fail"
    ;;
  pre_llm)
    coord_ok=true
    snapshot_ok=true
    orient_ok=true
    nav2_ok=true

    run_coordinate || coord_ok=false
    if [[ "${coord_ok}" != "true" ]]; then
      overall_status="fail"
      append_blocked_step "snapshot" "Blocked: coordinate gate failed."
      append_blocked_step "orientation" "Blocked: coordinate gate failed."
      append_blocked_step "nav2" "Blocked: coordinate gate failed."
      append_blocked_step "multi_target" "Blocked: coordinate gate failed."
    else
      run_snapshot || snapshot_ok=false
      if [[ "${snapshot_ok}" != "true" ]]; then
        overall_status="fail"
        append_blocked_step "orientation" "Blocked: snapshot gate failed."
        append_blocked_step "nav2" "Blocked: snapshot gate failed."
        append_blocked_step "multi_target" "Blocked: snapshot gate failed."
      else
        run_orientation || orient_ok=false
        if [[ "${orient_ok}" != "true" ]]; then
          overall_status="fail"
          append_blocked_step "nav2" "Blocked: orientation gate failed."
          append_blocked_step "multi_target" "Blocked: orientation gate failed."
        else
          run_nav2 || nav2_ok=false
          if [[ "${nav2_ok}" != "true" ]]; then
            overall_status="fail"
            append_blocked_step "multi_target" "Blocked: nav2 gate failed."
          else
            run_multi_target || overall_status="fail"
          fi
        fi
      fi
    fi
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
  --arg snapshot_timeout_s "${SNAPSHOT_TIMEOUT_S}" \
  --arg snapshot_min_mean_abs_diff "${SNAPSHOT_MIN_MEAN_ABS_DIFF}" \
  --arg multi_target_goal_timeout_s "${MULTI_TARGET_GOAL_TIMEOUT_S}" \
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
    snapshot_timeout_s: ($snapshot_timeout_s | tonumber),
    snapshot_min_mean_abs_diff: ($snapshot_min_mean_abs_diff | tonumber),
    multi_target_goal_timeout_s: ($multi_target_goal_timeout_s | tonumber),
    status: $status,
    pass: ($status == "pass"),
    pre_llm_ready: ($mode == "pre_llm" and $status == "pass"),
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
