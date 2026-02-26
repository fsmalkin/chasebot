#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/workspaces/chasecar}"
MODE="${CHASECAR_UAT_MODE:-full}"
RUNTIME_TARGET="${CHASECAR_RUNTIME_TARGET:-robot_fidelity_orin}"
SIM_LANE="${CHASECAR_SIM_LANE:-jetty_gate}"
INFERENCE_BACKEND="${CHASECAR_INFERENCE_BACKEND:-tensorrt_int8}"

if [[ ! -d "${REPO_ROOT}" ]]; then
  echo "[uat-orchestrator] Missing repo path: ${REPO_ROOT}" >&2
  exit 2
fi

cd "${REPO_ROOT}"

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
SESSION_DIR="artifacts/session/${RUN_ID}"
LOG_DIR="${SESSION_DIR}/logs"
mkdir -p "${LOG_DIR}"

STATIC_CHECK_LOG="${LOG_DIR}/static_checks.log"
{
  echo "run_id=${RUN_ID}"
  echo "mode=${MODE}"
  echo "runtime_target=${RUNTIME_TARGET}"
  echo "sim_lane=${SIM_LANE}"
  echo "inference_backend=${INFERENCE_BACKEND}"
  echo ""
  echo "[py_compile] coordinate/orientation/nav runners"
  python3 -m py_compile scripts/coordinate_uat_runner.py scripts/orientation_uat_runner.py scripts/nav2_readiness_runner.py
} >"${STATIC_CHECK_LOG}" 2>&1

cat >"${SESSION_DIR}/manifest.json" <<JSON
{
  "run_id": "${RUN_ID}",
  "mode": "${MODE}",
  "runtime_target": "${RUNTIME_TARGET}",
  "sim_lane": "${SIM_LANE}",
  "inference_backend": "${INFERENCE_BACKEND}",
  "artifacts": {
    "logs": "${LOG_DIR}",
    "static_check_log": "${STATIC_CHECK_LOG}"
  }
}
JSON

cat >"${SESSION_DIR}/readiness_report.json" <<JSON
{
  "run_id": "${RUN_ID}",
  "runtime_target": "${RUNTIME_TARGET}",
  "sim_lane": "${SIM_LANE}",
  "inference_backend": "${INFERENCE_BACKEND}",
  "status": "prepared",
  "notes": [
    "Container orchestrator validation completed.",
    "Use host lane scripts for full ROS/Gazebo/Isaac UAT execution."
  ]
}
JSON

echo "ARTIFACT_DIR=${SESSION_DIR}"
echo "UAT_ORCHESTRATOR_STATUS=prepared"
