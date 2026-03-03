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
NAV2_BRIDGE_MAX_GOALS="${CHASECAR_NAV2_BRIDGE_MAX_GOALS:-1}"
NAV2_CONFIG="${CHASECAR_NAV2_CONFIG:-ros2_config/config/nav2_readiness_fidelity.yaml}"

SNAPSHOT_WORLD_NAME="${CHASECAR_SNAPSHOT_WORLD_NAME:-${NAV2_WORLD_NAME}}"
SNAPSHOT_MODEL_SDF="${CHASECAR_SNAPSHOT_MODEL_SDF:-ros2_config/frisbee_target_ball.sdf}"
SNAPSHOT_MODEL_NAME="${CHASECAR_SNAPSHOT_MODEL_NAME:-uat_snapshot_target}"
SNAPSHOT_TARGET_X="${CHASECAR_SNAPSHOT_TARGET_X:-0.9}"
SNAPSHOT_TARGET_Y="${CHASECAR_SNAPSHOT_TARGET_Y:-0.0}"
SNAPSHOT_TARGET_Z="${CHASECAR_SNAPSHOT_TARGET_Z:-0.05}"
SNAPSHOT_RGB_TOPIC="${CHASECAR_SNAPSHOT_RGB_TOPIC:-/d415/color/image_raw}"
SNAPSHOT_DEBUG_TOPIC="${CHASECAR_SNAPSHOT_DEBUG_TOPIC:-/yolo/debug_image}"
SNAPSHOT_TIMEOUT_S="${CHASECAR_SNAPSHOT_TIMEOUT_S:-12}"
SNAPSHOT_MIN_MEAN_ABS_DIFF="${CHASECAR_SNAPSHOT_MIN_MEAN_ABS_DIFF:-1.0}"
SNAPSHOT_MIN_CHANGED_PIXEL_RATIO="${CHASECAR_SNAPSHOT_MIN_CHANGED_PIXEL_RATIO:-0.001}"
SNAPSHOT_MIN_FRAMES="${CHASECAR_SNAPSHOT_MIN_FRAMES:-1}"

MULTI_TARGET_CONFIG="${CHASECAR_MULTI_TARGET_CONFIG:-ros2_config/config/multi_target_nav2.yaml}"
MULTI_TARGET_GOAL_TIMEOUT_S="${CHASECAR_MULTI_TARGET_GOAL_TIMEOUT_S:-55}"
MODEL_SPAWN_TIMEOUT_S="${CHASECAR_MODEL_SPAWN_TIMEOUT_S:-20}"

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
  local elapsed_s="${7:-0}"
  local retry_count="${8:-0}"
  local evidence_complete="${9:-false}"
  local evidence_missing_csv="${10:-}"
  local started_utc="${11:-}"
  local ended_utc="${12:-}"

  jq -nc \
    --arg id "${id}" \
    --arg status "${status}" \
    --arg failure_class "${failure_class}" \
    --arg artifact_dir "${artifact_dir}" \
    --argjson exit_code "${exit_code}" \
    --arg log_file "${log_file}" \
    --argjson elapsed_s "${elapsed_s}" \
    --argjson retry_count "${retry_count}" \
    --arg evidence_complete "${evidence_complete}" \
    --arg evidence_missing_csv "${evidence_missing_csv}" \
    --arg started_utc "${started_utc}" \
    --arg ended_utc "${ended_utc}" \
    '{
      id: $id,
      status: $status,
      failure_class: $failure_class,
      artifact_dir: (if $artifact_dir == "" then null else $artifact_dir end),
      exit_code: $exit_code,
      log_file: $log_file,
      started_utc: (if $started_utc == "" then null else $started_utc end),
      ended_utc: (if $ended_utc == "" then null else $ended_utc end),
      elapsed_s: $elapsed_s,
      retry_count: $retry_count,
      evidence_complete: ($evidence_complete == "true"),
      evidence_missing: (if $evidence_missing_csv == "" then [] else ($evidence_missing_csv | split(",")) end)
    }' >> "${STEP_RESULTS_FILE}"

  echo "STEP_RESULT=${id}:${status}:${artifact_dir}"
}

append_blocked_step() {
  local id="$1"
  local reason="$2"
  local started_utc
  local ended_utc
  started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ended_utc="${started_utc}"
  local log_file="${LOG_DIR}/${id}_blocked.log"
  echo "${reason}" > "${log_file}"
  append_step "${id}" "blocked" "blocked_dependency" "" 2 "${log_file}" 0 0 "false" "" "${started_utc}" "${ended_utc}"
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

latest_file_after() {
  local pattern="$1"
  local before="$2"
  local latest
  latest="$(latest_file "${pattern}")"
  if [[ -z "${latest}" ]]; then
    echo ""
    return 0
  fi
  if [[ -n "${before}" && "${latest}" == "${before}" ]]; then
    echo ""
    return 0
  fi
  echo "${latest}"
}

file_nonempty() {
  local path="$1"
  [[ -f "${path}" && -s "${path}" ]]
}

dir_has_glob() {
  local dir="$1"
  local glob="$2"
  compgen -G "${dir}/${glob}" >/dev/null 2>&1
}

missing_csv_from_array() {
  local -a missing=("$@")
  local -a filtered=()
  local item
  for item in "${missing[@]}"; do
    if [[ -n "${item}" ]]; then
      filtered+=("${item}")
    fi
  done
  if [[ "${#filtered[@]}" -eq 0 ]]; then
    echo ""
    return 0
  fi
  local joined
  joined="$(IFS=','; echo "${filtered[*]}")"
  echo "${joined}"
}

classify_failure() {
  local rc="$1"
  local default_class="$2"
  if [[ "${rc}" -eq 124 ]]; then
    echo "timeout"
    return 0
  fi
  echo "${default_class}"
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

  run_spawn_create() {
    local include_world="$1"
    local -a cmd=(ros2 run ros_gz_sim create)
    if [[ "${include_world}" == "true" ]]; then
      cmd+=(-world "${world_name}")
    fi
    cmd+=(
      -file "${resolved_model}"
      -name "${model_name}"
      -x "${pos_x}"
      -y "${pos_y}"
      -z "${pos_z}"
    )
    local rc=0
    if command -v timeout >/dev/null 2>&1; then
      timeout "${MODEL_SPAWN_TIMEOUT_S}s" "${cmd[@]}" >>"${log_file}" 2>&1 || rc=$?
    else
      "${cmd[@]}" >>"${log_file}" 2>&1 || rc=$?
    fi
    return "${rc}"
  }

  local spawn_rc=0
  run_spawn_create "true" || spawn_rc=$?
  if [[ "${spawn_rc}" -ne 0 ]] && grep -Eq 'Waiting for service \[/world/.*/create\] to become available' "${log_file}" 2>/dev/null; then
    echo "[orchestrator] fallback spawn without -world for create_multiple compatibility" >>"${log_file}" 2>&1
    run_spawn_create "false" || spawn_rc=$?
  fi
  if [[ "${spawn_rc}" -eq 124 ]]; then
    echo "[orchestrator] spawn timeout after ${MODEL_SPAWN_TIMEOUT_S}s for model=${model_name} world=${world_name}" >>"${log_file}" 2>&1
  fi
  return "${spawn_rc}"
}

run_prepare() {
  local log_file="${LOG_DIR}/prepare.log"
  local step_started_utc
  local step_ended_utc
  local step_started_epoch
  local elapsed_s
  step_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step_started_epoch="$(date +%s)"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 -m py_compile \
    scripts/coordinate_uat_runner.py \
    scripts/orientation_uat_runner.py \
    scripts/nav2_readiness_runner.py \
    scripts/multi_target_nav2_runner.py \
    scripts/capture_topic_image.py \
    scripts/image_diff_metrics.py)
  step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  elapsed_s="$(( $(date +%s) - step_started_epoch ))"

  if [[ "${rc}" -eq 0 ]]; then
    append_step "prepare" "pass" "" "" 0 "${log_file}" "${elapsed_s}" 0 "true" "" "${step_started_utc}" "${step_ended_utc}"
    return 0
  fi

  local failure_class
  failure_class="$(classify_failure "${rc}" "blocked_dependency")"
  append_step "prepare" "fail" "${failure_class}" "" "${rc}" "${log_file}" "${elapsed_s}" 0 "false" "compile_step" "${step_started_utc}" "${step_ended_utc}"
  return 2
}

run_coordinate() {
  local log_file="${LOG_DIR}/coordinate.log"
  local step_started_utc
  local step_ended_utc
  local step_started_epoch
  local elapsed_s
  step_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step_started_epoch="$(date +%s)"
  local summary_before
  summary_before="$(latest_file "artifacts/uat/*/summary.json")"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/coordinate_uat_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "ros2_config/config/uat_coordinates.yaml")
  step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  elapsed_s="$(( $(date +%s) - step_started_epoch ))"

  local summary_path
  summary_path="$(latest_file_after "artifacts/uat/*/summary.json" "${summary_before}")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi
  local detections_csv=""
  if [[ -n "${artifact_dir}" ]]; then
    detections_csv="${artifact_dir}/detections.csv"
  fi
  local summary_ok="false"
  local detections_ok="false"
  if [[ -n "${summary_path}" ]] && file_nonempty "${summary_path}"; then
    summary_ok="true"
  fi
  if [[ -n "${detections_csv}" ]] && file_nonempty "${detections_csv}"; then
    detections_ok="true"
  fi
  local evidence_complete="false"
  if [[ "${summary_ok}" == "true" && "${detections_ok}" == "true" ]]; then
    evidence_complete="true"
  fi
  local -a missing=()
  if [[ "${summary_ok}" != "true" ]]; then
    missing+=("summary.json")
  fi
  if [[ "${detections_ok}" != "true" ]]; then
    missing+=("detections.csv")
  fi
  local missing_csv
  missing_csv="$(missing_csv_from_array "${missing[@]}")"

  if [[ "${rc}" -eq 0 && "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" && "${evidence_complete}" == "true" ]]; then
      append_step "coordinate" "pass" "" "${artifact_dir}" 0 "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
      return 0
    fi

    local failure_class
    if has_world_create_service_error "${log_file}"; then
      failure_class="service_unavailable"
    elif [[ "${evidence_complete}" != "true" ]]; then
      failure_class="missing_artifact"
    else
      failure_class="threshold_failed"
    fi
    append_step "coordinate" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
    return 2
  fi

  local failure_class
  if has_world_create_service_error "${log_file}"; then
    failure_class="service_unavailable"
  elif [[ "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      failure_class="$(classify_failure "${rc}" "blocked_dependency")"
    else
      failure_class="threshold_failed"
    fi
  elif [[ "${summary_ok}" != "true" || "${detections_ok}" != "true" ]]; then
    failure_class="missing_artifact"
  else
    failure_class="$(classify_failure "${rc}" "blocked_dependency")"
  fi
  append_step "coordinate" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
  return 2
}

run_snapshot() {
  local log_file="${LOG_DIR}/snapshot.log"
  local step_started_utc
  local step_ended_utc
  local step_started_epoch
  local elapsed_s
  step_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step_started_epoch="$(date +%s)"
  local prep_log="${LOG_DIR}/snapshot_prep.log"
  local artifact_dir="artifacts/snapshots/${RUN_ID}"
  local rgb_file="${artifact_dir}/d415_color.png"
  local debug_file="${artifact_dir}/yolo_debug.png"
  local diff_json="${artifact_dir}/image_diff.json"
  local summary_json="${artifact_dir}/snapshot_summary.json"

  mkdir -p "${artifact_dir}"
  : > "${prep_log}"

  local spawn_rc=0
  spawn_model \
    "${SNAPSHOT_WORLD_NAME}" \
    "${SNAPSHOT_MODEL_SDF}" \
    "${SNAPSHOT_MODEL_NAME}" \
    "${SNAPSHOT_TARGET_X}" \
    "${SNAPSHOT_TARGET_Y}" \
    "${SNAPSHOT_TARGET_Z}" \
    "${prep_log}" || spawn_rc=$?
  if [[ "${spawn_rc}" -ne 0 ]]; then
    local failure_class="blocked_dependency"
    if [[ "${spawn_rc}" -eq 124 ]]; then
      failure_class="timeout"
    elif has_world_create_service_error "${prep_log}"; then
      failure_class="service_unavailable"
    elif grep -Eq "Missing model SDF" "${prep_log}" 2>/dev/null; then
      failure_class="missing_artifact"
    fi
    step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    elapsed_s="$(( $(date +%s) - step_started_epoch ))"
    append_step "snapshot" "fail" "${failure_class}" "${artifact_dir}" "${spawn_rc}" "${prep_log}" "${elapsed_s}" 0 "false" "spawn_target" "${step_started_utc}" "${step_ended_utc}"
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
  local changed_pixel_ratio="0"
  local shape_match="false"
  if [[ -f "${diff_json}" ]]; then
    left_exists="$(jq -r '.left_exists // false' "${diff_json}" 2>/dev/null || echo false)"
    right_exists="$(jq -r '.right_exists // false' "${diff_json}" 2>/dev/null || echo false)"
    byte_identical="$(jq -r 'if has("byte_identical") then .byte_identical else true end' "${diff_json}" 2>/dev/null || echo true)"
    mean_abs_diff="$(jq -r '.mean_abs_diff // 0' "${diff_json}" 2>/dev/null || echo 0)"
    changed_pixel_ratio="$(jq -r '.changed_pixel_ratio // 0' "${diff_json}" 2>/dev/null || echo 0)"
    shape_match="$(jq -r '.shape_match // false' "${diff_json}" 2>/dev/null || echo false)"
  fi

  local mean_pass="false"
  if awk -v a="${mean_abs_diff}" -v b="${SNAPSHOT_MIN_MEAN_ABS_DIFF}" 'BEGIN{exit !(a+0 >= b+0)}'; then
    mean_pass="true"
  fi

  local changed_ratio_pass="false"
  if awk -v a="${changed_pixel_ratio}" -v b="${SNAPSHOT_MIN_CHANGED_PIXEL_RATIO}" 'BEGIN{exit !(a+0 >= b+0)}'; then
    changed_ratio_pass="true"
  fi

  local pass="false"
  if [[ "${rgb_rc}" -eq 0 && "${debug_rc}" -eq 0 && "${diff_rc}" -eq 0 \
     && "${capture_rgb_ok}" == "true" && "${capture_debug_ok}" == "true" \
     && "${left_exists}" == "true" && "${right_exists}" == "true" \
     && "${shape_match}" == "true" \
     && "${byte_identical}" != "true" \
     && "${mean_pass}" == "true" \
     && "${changed_ratio_pass}" == "true" ]]; then
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
    --argjson changed_pixel_ratio "${changed_pixel_ratio}" \
    --argjson min_changed_pixel_ratio "${SNAPSHOT_MIN_CHANGED_PIXEL_RATIO}" \
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
        min_mean_abs_diff: $min_mean_abs_diff,
        changed_pixel_ratio: $changed_pixel_ratio,
        min_changed_pixel_ratio: $min_changed_pixel_ratio
      },
      pass: $pass
    }' > "${summary_json}"

  local rgb_exists="false"
  local debug_exists="false"
  local diff_exists="false"
  local summary_exists="false"
  if file_nonempty "${rgb_file}"; then rgb_exists="true"; fi
  if file_nonempty "${debug_file}"; then debug_exists="true"; fi
  if file_nonempty "${diff_json}"; then diff_exists="true"; fi
  if file_nonempty "${summary_json}"; then summary_exists="true"; fi
  local -a missing=()
  if [[ "${rgb_exists}" != "true" ]]; then missing+=("d415_color.png"); fi
  if [[ "${debug_exists}" != "true" ]]; then missing+=("yolo_debug.png"); fi
  if [[ "${diff_exists}" != "true" ]]; then missing+=("image_diff.json"); fi
  if [[ "${summary_exists}" != "true" ]]; then missing+=("snapshot_summary.json"); fi
  local missing_csv
  missing_csv="$(missing_csv_from_array "${missing[@]}")"
  local evidence_complete="false"
  if [[ "${rgb_exists}" == "true" && "${debug_exists}" == "true" && "${diff_exists}" == "true" && "${summary_exists}" == "true" ]]; then
    evidence_complete="true"
  fi
  step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  elapsed_s="$(( $(date +%s) - step_started_epoch ))"

  if [[ "${pass}" == "true" && "${evidence_complete}" == "true" ]]; then
    append_step "snapshot" "pass" "" "${artifact_dir}" 0 "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
    cat "${rgb_log}" "${debug_log}" "${diff_log}" > "${log_file}" 2>/dev/null || true
    return 0
  fi

  local failure_class="threshold_failed"
  if [[ "${rgb_rc}" -eq 124 || "${debug_rc}" -eq 124 || "${diff_rc}" -eq 124 ]]; then
    failure_class="timeout"
  elif [[ "${rgb_rc}" -ne 0 || "${debug_rc}" -ne 0 || "${diff_rc}" -ne 0 ]]; then
    failure_class="blocked_dependency"
  elif [[ "${capture_rgb_ok}" != "true" || "${capture_debug_ok}" != "true" || "${shape_match}" != "true" ]]; then
    failure_class="blocked_dependency"
  elif [[ "${evidence_complete}" != "true" ]]; then
    failure_class="missing_artifact"
  fi
  cat "${rgb_log}" "${debug_log}" "${diff_log}" > "${log_file}" 2>/dev/null || true
  append_step "snapshot" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
  return 2
}

run_orientation() {
  local log_file="${LOG_DIR}/orientation.log"
  local step_started_utc
  local step_ended_utc
  local step_started_epoch
  local elapsed_s
  step_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step_started_epoch="$(date +%s)"
  local summary_before
  summary_before="$(latest_file "artifacts/orientation/*/orientation_summary.json")"
  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/orientation_uat_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "ros2_config/config/orientation_scenarios.yaml")
  step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  elapsed_s="$(( $(date +%s) - step_started_epoch ))"

  local summary_path
  summary_path="$(latest_file_after "artifacts/orientation/*/orientation_summary.json" "${summary_before}")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi
  local samples_csv=""
  local snapshots_dir=""
  if [[ -n "${artifact_dir}" ]]; then
    samples_csv="${artifact_dir}/orientation_samples.csv"
    snapshots_dir="${artifact_dir}/snapshots"
  fi
  local summary_ok="false"
  local samples_ok="false"
  local snapshots_ok="false"
  if [[ -n "${summary_path}" ]] && file_nonempty "${summary_path}"; then
    summary_ok="true"
  fi
  if [[ -n "${samples_csv}" ]] && file_nonempty "${samples_csv}"; then
    samples_ok="true"
  fi
  if [[ -n "${snapshots_dir}" ]] && dir_has_glob "${snapshots_dir}" "*.png"; then
    snapshots_ok="true"
  fi
  local evidence_complete="false"
  if [[ "${summary_ok}" == "true" && "${samples_ok}" == "true" && "${snapshots_ok}" == "true" ]]; then
    evidence_complete="true"
  fi
  local -a missing=()
  if [[ "${summary_ok}" != "true" ]]; then missing+=("orientation_summary.json"); fi
  if [[ "${samples_ok}" != "true" ]]; then missing+=("orientation_samples.csv"); fi
  if [[ "${snapshots_ok}" != "true" ]]; then missing+=("snapshots/*.png"); fi
  local missing_csv
  missing_csv="$(missing_csv_from_array "${missing[@]}")"

  if [[ "${rc}" -eq 0 && "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" && "${evidence_complete}" == "true" ]]; then
      append_step "orientation" "pass" "" "${artifact_dir}" 0 "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
      return 0
    fi
    local failure_class="threshold_failed"
    if [[ "${evidence_complete}" != "true" ]]; then
      failure_class="missing_artifact"
    fi
    append_step "orientation" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
    return 2
  fi

  local failure_class
  if [[ "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      failure_class="$(classify_failure "${rc}" "blocked_dependency")"
    else
      failure_class="threshold_failed"
    fi
  elif [[ "${summary_ok}" != "true" || "${samples_ok}" != "true" || "${snapshots_ok}" != "true" ]]; then
    failure_class="missing_artifact"
  else
    failure_class="$(classify_failure "${rc}" "blocked_dependency")"
  fi
  append_step "orientation" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}" "${elapsed_s}" 0 "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
  return 2
}

run_nav2() {
  local log_file="${LOG_DIR}/nav2.log"
  local prep_log="${LOG_DIR}/nav2_prep.log"
  local bridge_log="${LOG_DIR}/nav2_bridge.log"
  local step_started_utc
  local step_ended_utc
  local step_started_epoch
  local elapsed_s
  step_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step_started_epoch="$(date +%s)"
  local summary_before
  summary_before="$(latest_file "artifacts/nav2/*/nav_summary.json")"
  local bridge_pid=""
  : > "${prep_log}"

  if [[ "${NAV2_START_BRIDGE}" == "true" ]]; then
    if [[ ! -f "${REPO_ROOT}/${NAV2_BRIDGE_SCRIPT}" ]]; then
      echo "[nav2] bridge script missing: ${REPO_ROOT}/${NAV2_BRIDGE_SCRIPT}" >>"${prep_log}" 2>&1
      step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      elapsed_s="$(( $(date +%s) - step_started_epoch ))"
      append_step "nav2" "fail" "missing_artifact" "" 2 "${prep_log}" "${elapsed_s}" 0 "false" "bridge_script" "${step_started_utc}" "${step_ended_utc}"
      return 2
    fi
    python3 "${REPO_ROOT}/${NAV2_BRIDGE_SCRIPT}" \
      --ros-args \
      -p use_sim_time:=true \
      -p max_goal_count:="${NAV2_BRIDGE_MAX_GOALS}" >"${bridge_log}" 2>&1 &
    bridge_pid="$!"
    sleep "${NAV2_BRIDGE_START_DELAY_S}"
  fi

  local nav_spawn_rc=0
  spawn_model \
    "${NAV2_WORLD_NAME}" \
    "${NAV2_MODEL_SDF}" \
    "${NAV2_MODEL_NAME}" \
    "${NAV2_TARGET_X}" \
    "${NAV2_TARGET_Y}" \
    "${NAV2_TARGET_Z}" \
    "${prep_log}" || nav_spawn_rc=$?
  if [[ "${nav_spawn_rc}" -ne 0 ]]; then

    if [[ -n "${bridge_pid}" ]]; then
      kill "${bridge_pid}" 2>/dev/null || true
      wait "${bridge_pid}" 2>/dev/null || true
    fi

    local failure_class="blocked_dependency"
    if [[ "${nav_spawn_rc}" -eq 124 ]]; then
      failure_class="timeout"
    elif has_world_create_service_error "${prep_log}"; then
      failure_class="service_unavailable"
    elif grep -Eq "Missing model SDF" "${prep_log}" 2>/dev/null; then
      failure_class="missing_artifact"
    fi
    step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    elapsed_s="$(( $(date +%s) - step_started_epoch ))"
    append_step "nav2" "fail" "${failure_class}" "" "${nav_spawn_rc}" "${prep_log}" "${elapsed_s}" 0 "false" "spawn_target" "${step_started_utc}" "${step_ended_utc}"
    return 2
  fi

  sleep 2

  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/nav2_readiness_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "${NAV2_CONFIG}" \
    --duration-s "${NAV2_DURATION_S}")
  step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  elapsed_s="$(( $(date +%s) - step_started_epoch ))"

  if [[ -n "${bridge_pid}" ]]; then
    kill "${bridge_pid}" 2>/dev/null || true
    wait "${bridge_pid}" 2>/dev/null || true
  fi
  remove_model_by_name "${NAV2_WORLD_NAME}" "${NAV2_MODEL_NAME}" "${prep_log}"

  local summary_path
  summary_path="$(latest_file_after "artifacts/nav2/*/nav_summary.json" "${summary_before}")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi
  local summary_ok="false"
  if [[ -n "${summary_path}" ]] && file_nonempty "${summary_path}"; then
    summary_ok="true"
  fi
  local evidence_complete="${summary_ok}"
  local missing_csv=""
  if [[ "${summary_ok}" != "true" ]]; then
    missing_csv="nav_summary.json"
  fi
  local retry_count=0
  if [[ "${summary_ok}" == "true" ]]; then
    retry_count="$(jq -r '.retry_count // 0' "${summary_path}" 2>/dev/null || echo 0)"
    if [[ ! "${retry_count}" =~ ^[0-9]+$ ]]; then
      retry_count=0
    fi
  fi

  if [[ "${rc}" -eq 0 && "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" && "${evidence_complete}" == "true" ]]; then
      append_step "nav2" "pass" "" "${artifact_dir}" 0 "${log_file}" "${elapsed_s}" "${retry_count}" "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
      return 0
    fi
    local failure_class="threshold_failed"
    if [[ "${evidence_complete}" != "true" ]]; then
      failure_class="missing_artifact"
    fi
    append_step "nav2" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}" "${elapsed_s}" "${retry_count}" "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
    return 2
  fi

  local failure_class
  if has_world_create_service_error "${log_file}"; then
    failure_class="service_unavailable"
  elif [[ "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      failure_class="$(classify_failure "${rc}" "blocked_dependency")"
    else
      failure_class="threshold_failed"
    fi
  elif [[ "${summary_ok}" != "true" ]]; then
    failure_class="missing_artifact"
  else
    failure_class="$(classify_failure "${rc}" "blocked_dependency")"
  fi
  append_step "nav2" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}" "${elapsed_s}" "${retry_count}" "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
  return 2
}

run_multi_target() {
  local log_file="${LOG_DIR}/multi_target.log"
  local step_started_utc
  local step_ended_utc
  local step_started_epoch
  local elapsed_s
  step_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  step_started_epoch="$(date +%s)"
  local summary_before
  summary_before="$(latest_file "artifacts/nav2_multi/*/multi_target_summary.json")"
  local cfg="${MULTI_TARGET_CONFIG}"
  if [[ "${cfg}" != /* ]]; then
    cfg="${REPO_ROOT}/${cfg}"
  fi

  if [[ ! -f "${cfg}" ]]; then
    step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    elapsed_s="$(( $(date +%s) - step_started_epoch ))"
    append_step "multi_target" "fail" "missing_artifact" "" 2 "${log_file}" "${elapsed_s}" 0 "false" "multi_target_config" "${step_started_utc}" "${step_ended_utc}"
    return 2
  fi

  local rc
  rc=$(run_cmd_with_timeout "${log_file}" python3 scripts/multi_target_nav2_runner.py \
    --runtime-target "${RUNTIME_TARGET}" \
    --profile "${UAT_PROFILE}" \
    --inference-device "${UAT_INFERENCE_DEVICE}" \
    --config "${cfg}" \
    --goal-timeout-s "${MULTI_TARGET_GOAL_TIMEOUT_S}")
  step_ended_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  elapsed_s="$(( $(date +%s) - step_started_epoch ))"

  local summary_path
  summary_path="$(latest_file_after "artifacts/nav2_multi/*/multi_target_summary.json" "${summary_before}")"
  local artifact_dir=""
  if [[ -n "${summary_path}" ]]; then
    artifact_dir="$(dirname "${summary_path}")"
  fi
  local samples_csv=""
  if [[ -n "${artifact_dir}" ]]; then
    samples_csv="${artifact_dir}/multi_target_samples.csv"
  fi
  local summary_ok="false"
  local samples_ok="false"
  if [[ -n "${summary_path}" ]] && file_nonempty "${summary_path}"; then
    summary_ok="true"
  fi
  if [[ -n "${samples_csv}" ]] && file_nonempty "${samples_csv}"; then
    samples_ok="true"
  fi
  local evidence_complete="false"
  if [[ "${summary_ok}" == "true" && "${samples_ok}" == "true" ]]; then
    evidence_complete="true"
  fi
  local -a missing=()
  if [[ "${summary_ok}" != "true" ]]; then missing+=("multi_target_summary.json"); fi
  if [[ "${samples_ok}" != "true" ]]; then missing+=("multi_target_samples.csv"); fi
  local missing_csv
  missing_csv="$(missing_csv_from_array "${missing[@]}")"

  local retry_count=0
  if [[ "${samples_ok}" == "true" ]]; then
    local max_attempts
    max_attempts="$(python3 - "${samples_csv}" <<'PY'
import csv
import sys

path = sys.argv[1]
max_attempts = 1
try:
    with open(path, newline='', encoding='utf-8') as fp:
        for row in csv.DictReader(fp):
            raw = (row.get('attempts') or '1').strip()
            try:
                attempts = int(raw)
            except ValueError:
                attempts = 1
            if attempts > max_attempts:
                max_attempts = attempts
except FileNotFoundError:
    max_attempts = 1

print(max_attempts)
PY
)"
    if [[ "${max_attempts}" =~ ^[0-9]+$ ]]; then
      retry_count="$(( max_attempts > 0 ? max_attempts - 1 : 0 ))"
    fi
  fi

  if [[ "${rc}" -eq 0 && "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" && "${evidence_complete}" == "true" ]]; then
      append_step "multi_target" "pass" "" "${artifact_dir}" 0 "${log_file}" "${elapsed_s}" "${retry_count}" "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
      return 0
    fi
    local failure_class="threshold_failed"
    if [[ "${evidence_complete}" != "true" ]]; then
      failure_class="missing_artifact"
    fi
    append_step "multi_target" "fail" "${failure_class}" "${artifact_dir}" 2 "${log_file}" "${elapsed_s}" "${retry_count}" "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
    return 2
  fi

  local failure_class
  if [[ "${summary_ok}" == "true" ]]; then
    local pass_value
    pass_value="$(jq -r '.pass // false' "${summary_path}" 2>/dev/null || echo false)"
    if [[ "${pass_value}" == "true" ]]; then
      failure_class="$(classify_failure "${rc}" "blocked_dependency")"
    else
      failure_class="threshold_failed"
    fi
  elif [[ "${summary_ok}" != "true" || "${samples_ok}" != "true" ]]; then
    failure_class="missing_artifact"
  else
    failure_class="$(classify_failure "${rc}" "blocked_dependency")"
  fi
  append_step "multi_target" "fail" "${failure_class}" "${artifact_dir}" "${rc}" "${log_file}" "${elapsed_s}" "${retry_count}" "${evidence_complete}" "${missing_csv}" "${step_started_utc}" "${step_ended_utc}"
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
failure_class_counts_json="$(jq -s '
  map(.failure_class // "")
  | map(select(length > 0))
  | reduce .[] as $fc ({}; .[$fc] = ((.[$fc] // 0) + 1))
' "${STEP_RESULTS_FILE}")"
stage_timing_json="$(jq -s '
  reduce .[] as $step ({}; .[$step.id] = ($step.elapsed_s // 0))
' "${STEP_RESULTS_FILE}")"
stage_retry_json="$(jq -s '
  reduce .[] as $step ({}; .[$step.id] = ($step.retry_count // 0))
' "${STEP_RESULTS_FILE}")"
evidence_complete_json="$(jq -s '
  map((.evidence_complete // false) and (.status == "pass"))
  | all
' "${STEP_RESULTS_FILE}")"
unresolved_issues_json="$(jq -s '
  map(select(.status != "pass"))
  | map({
      step: .id,
      status: .status,
      failure_class: .failure_class,
      detail: (
        if (.evidence_missing | length) > 0 then
          ("missing: " + (.evidence_missing | join(", ")))
        else
          ""
        end
      )
    })
' "${STEP_RESULTS_FILE}")"
primary_failure_class="$(jq -r -s '
  map(select(.status != "pass") | .failure_class)
  | map(select(length > 0))
  | if length > 0 then .[0] else "" end
' "${STEP_RESULTS_FILE}")"
detected_ros_distros_json="$(find /opt/ros -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | jq -Rsc 'split("\n") | map(select(length > 0))')"
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
  --arg failure_class "${primary_failure_class}" \
  --arg status "${overall_status}" \
  --arg step_timeout_s "${STEP_TIMEOUT_S}" \
  --arg nav2_duration_s "${NAV2_DURATION_S}" \
  --arg snapshot_timeout_s "${SNAPSHOT_TIMEOUT_S}" \
  --arg snapshot_min_mean_abs_diff "${SNAPSHOT_MIN_MEAN_ABS_DIFF}" \
  --arg snapshot_min_changed_pixel_ratio "${SNAPSHOT_MIN_CHANGED_PIXEL_RATIO}" \
  --arg multi_target_goal_timeout_s "${MULTI_TARGET_GOAL_TIMEOUT_S}" \
  --arg generated_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson steps "${steps_json}" \
  --argjson detected_host_ros_distros "${detected_ros_distros_json}" \
  --argjson failure_class_counts "${failure_class_counts_json}" \
  --argjson stage_timing_s "${stage_timing_json}" \
  --argjson stage_retry_counts "${stage_retry_json}" \
  --argjson evidence_complete "${evidence_complete_json}" \
  --argjson unresolved_issues "${unresolved_issues_json}" \
  '{
    run_id: $run_id,
    mode: $mode,
    generated_utc: $generated_utc,
    runtime_target: $runtime_target,
    sim_lane: $sim_lane,
    inference_backend: $inference_backend,
    execution_lane: $execution_lane,
    container_core_ros_distro: $container_core_ros_distro,
    detected_host_ros_distros: $detected_host_ros_distros,
    step_timeout_s: ($step_timeout_s | tonumber),
    nav2_duration_s: ($nav2_duration_s | tonumber),
    snapshot_timeout_s: ($snapshot_timeout_s | tonumber),
    snapshot_min_mean_abs_diff: ($snapshot_min_mean_abs_diff | tonumber),
    snapshot_min_changed_pixel_ratio: ($snapshot_min_changed_pixel_ratio | tonumber),
    multi_target_goal_timeout_s: ($multi_target_goal_timeout_s | tonumber),
    failure_class: (if $failure_class == "" then null else $failure_class end),
    failure_class_counts: $failure_class_counts,
    stage_timing_s: $stage_timing_s,
    stage_retry_counts: $stage_retry_counts,
    evidence_complete: $evidence_complete,
    unresolved_issues: $unresolved_issues,
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
