param(
    [ValidateSet(1, 2, 3)]
    [int]$Milestone,

    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "workstation_balanced",

    [ValidateSet("compat", "balanced", "max")]
    [string]$PerfProfile,

    [string]$InferenceDevice,

    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",

    [Nullable[bool]]$Headless = $null,

    [string]$Distro = "Ubuntu-24.04",

    [string]$WorkspacePath = "~/ros2_ws",

    [string]$WorldFile = "yolo_test_world_v6_clean_uat.world",

    [string]$RosDistro = "auto",

    [string]$EvidenceDir = "",

    [int]$MaxRunSeconds = 0,

    [ValidateSet("default", "sensor_data")]
    [string]$CaptureQosProfile = "sensor_data",

    [int]$CaptureMinFrames = 2,

    [string]$WorldName = "yolo_test_world",

    [switch]$EnsureDemoTarget = $true,

    [string]$DemoTargetModelSdf = "ros2_config/frisbee_target_ball.sdf",

    [string]$DemoTargetName = "milestone_demo_target",

    [double]$DemoTargetX = 1.10,

    [double]$DemoTargetY = 0.00,

    [double]$DemoTargetZ = 0.05,

    [int]$TargetSpawnTimeoutSeconds = 20,

    [double]$MinDetectionConfidence = 0.50,

    [Nullable[bool]]$OpenFeedViewers = $null,

    [int]$ViewerStartupDelaySeconds = 3,

    [int]$WorldReadyTimeoutSeconds = 45
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)
    $resolved = (Resolve-Path -LiteralPath $WindowsPath).Path
    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $matches[1].ToLower()
        $rest = $matches[2] -replace '\\', '/'
        return "/mnt/$drive/$rest"
    }
    return $resolved
}

function Resolve-RosDistro {
    param(
        [Parameter(Mandatory = $true)][string]$Distro,
        [string]$Requested = "auto"
    )
    if ($Requested -and $Requested -ne "auto") {
        return $Requested
    }

    $resolveCmd = @'
if [ -f /opt/ros/kilted/setup.bash ]; then
  echo kilted
elif [ -f /opt/ros/lyrical/setup.bash ]; then
  echo lyrical
elif [ -f /opt/ros/jazzy/setup.bash ]; then
  echo jazzy
elif [ -f /opt/ros/humble/setup.bash ]; then
  echo humble
elif [ -d /opt/ros ]; then
  ls -1 /opt/ros | head -n1
fi
'@
    $resolveCmd = $resolveCmd.Replace("`r`n", "`n")
    $detectedRaw = wsl -d $Distro -- bash -lc $resolveCmd 2>$null
    $detected = ($detectedRaw | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($detected)) {
        throw "Unable to resolve ROS distro in $Distro. Install ROS first or pass -RosDistro explicitly."
    }
    return $detected
}

$runtimeAliases = @{
    robot_fidelity = "robot_fidelity_orin"
}
if ($runtimeAliases.ContainsKey($RuntimeTarget)) {
    $RuntimeTarget = $runtimeAliases[$RuntimeTarget]
}

$defaults = @{
    robot_fidelity_orin = @{
        PerfProfile = "compat"
        InferenceDevice = "cuda:0"
        Headless = $true
    }
    workstation_balanced = @{
        PerfProfile = "balanced"
        InferenceDevice = "auto"
        Headless = $false
    }
    workstation_max = @{
        PerfProfile = "max"
        InferenceDevice = "cuda:0"
        Headless = $true
    }
}

if (-not $PSBoundParameters.ContainsKey("PerfProfile")) {
    $PerfProfile = $defaults[$RuntimeTarget].PerfProfile
}
if (-not $PSBoundParameters.ContainsKey("InferenceDevice")) {
    $InferenceDevice = $defaults[$RuntimeTarget].InferenceDevice
}
if ($Headless -eq $null) {
    $Headless = [bool]$defaults[$RuntimeTarget].Headless
}
if ($OpenFeedViewers -eq $null) {
    $OpenFeedViewers = -not [bool]$Headless
}
$RosDistro = Resolve-RosDistro -Distro $Distro -Requested $RosDistro

$headlessStr = if ($Headless) { "true" } else { "false" }
$includeExtractor = if ($Milestone -ge 2) { "true" } else { "false" }
$includeBridge = if ($Milestone -ge 3) { "true" } else { "false" }
$ensureDemoTargetStr = if ([bool]$EnsureDemoTarget) { "true" } else { "false" }
$openFeedViewersStr = if ([bool]$OpenFeedViewers) { "true" } else { "false" }

$repoRootWin = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$repoRootWsl = Convert-ToWslPath -WindowsPath $repoRootWin

$evidenceInputWsl = ""
if (-not [string]::IsNullOrWhiteSpace($EvidenceDir)) {
    if ([System.IO.Path]::IsPathRooted($EvidenceDir)) {
        New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
        $evidenceResolvedWin = Resolve-Path -LiteralPath $EvidenceDir
        $evidenceInputWsl = Convert-ToWslPath -WindowsPath $evidenceResolvedWin
    }
    else {
        $evidenceInputWsl = $EvidenceDir.Replace('\', '/')
    }
}

$displayEnv = ""
if (-not $Headless) {
    $displayProbe = @'
if [ -n "${DISPLAY:-}" ]; then
  echo "$DISPLAY"
elif [ -n "${WAYLAND_DISPLAY:-}" ]; then
  echo ":0"
elif [ -S /mnt/wslg/runtime-dir/wayland-0 ] || [ -d /mnt/wslg/.X11-unix ]; then
  echo ":0"
else
  ip route show default | awk '{print $3}' | head -n1
fi
'@
    $displayProbe = $displayProbe.Replace("`r`n", "`n")
    $displayDetected = (wsl -d $Distro -- bash -lc $displayProbe).Trim()
    if ([string]::IsNullOrWhiteSpace($displayDetected)) {
        $displayDetected = "127.0.0.1:0.0"
    }
    elseif ($displayDetected -notmatch '[:.]') {
        $displayDetected = "$displayDetected`:0.0"
    }
    $displayEnv = $displayDetected
}

$bashTemplate = @'
set -eo pipefail

WORKSPACE="__WORKSPACE__"
REPO_PATH="__REPO_PATH__"
MILESTONE="__MILESTONE__"
RUNTIME_TARGET="__RUNTIME_TARGET__"
PERF_PROFILE="__PERF_PROFILE__"
INFERENCE_DEVICE="__INFERENCE_DEVICE__"
INFERENCE_BACKEND="__INFERENCE_BACKEND__"
HEADLESS="__HEADLESS__"
DISPLAY_ENV="__DISPLAY_ENV__"
INCLUDE_EXTRACTOR="__INCLUDE_EXTRACTOR__"
INCLUDE_BRIDGE="__INCLUDE_BRIDGE__"
WORLD_FILE="__WORLD_FILE__"
WORLD_NAME="__WORLD_NAME__"
ROS_DISTRO="__ROS_DISTRO__"
EVIDENCE_DIR_INPUT="__EVIDENCE_DIR_INPUT__"
MAX_RUN_SECONDS="__MAX_RUN_SECONDS__"
CAPTURE_QOS_PROFILE="__CAPTURE_QOS_PROFILE__"
CAPTURE_MIN_FRAMES="__CAPTURE_MIN_FRAMES__"
ENSURE_DEMO_TARGET="__ENSURE_DEMO_TARGET__"
DEMO_TARGET_MODEL_SDF="__DEMO_TARGET_MODEL_SDF__"
DEMO_TARGET_NAME="__DEMO_TARGET_NAME__"
DEMO_TARGET_X="__DEMO_TARGET_X__"
DEMO_TARGET_Y="__DEMO_TARGET_Y__"
DEMO_TARGET_Z="__DEMO_TARGET_Z__"
TARGET_SPAWN_TIMEOUT_S="__TARGET_SPAWN_TIMEOUT_S__"
MIN_DETECTION_CONFIDENCE="__MIN_DETECTION_CONFIDENCE__"
OPEN_FEED_VIEWERS="__OPEN_FEED_VIEWERS__"
VIEWER_START_DELAY_S="__VIEWER_START_DELAY_S__"
WORLD_READY_TIMEOUT_S="__WORLD_READY_TIMEOUT_S__"

if [[ "$WORKSPACE" == "~/"* ]]; then
  WORKSPACE="$HOME/${WORKSPACE:2}"
elif [[ "$WORKSPACE" == "~" ]]; then
  WORKSPACE="$HOME"
fi

if [ -d "$REPO_PATH" ]; then
  PACKAGE_PATH="$REPO_PATH"
elif [ -d "$WORKSPACE/src/chasecar" ]; then
  PACKAGE_PATH="$WORKSPACE/src/chasecar"
elif [ -d "$WORKSPACE/src/chasebot_description" ]; then
  PACKAGE_PATH="$WORKSPACE/src/chasebot_description"
else
  echo "Unable to resolve package path under workspace: $WORKSPACE" >&2
  exit 1
fi

if [ ! -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
  echo "ROS distro setup not found: /opt/ros/$ROS_DISTRO/setup.bash" >&2
  exit 1
fi
source /opt/ros/$ROS_DISTRO/setup.bash
cd "$WORKSPACE"
if [ -f "install/setup.bash" ]; then
  source install/setup.bash
fi

if [ "$HEADLESS" = "false" ] && [ -n "$DISPLAY_ENV" ]; then
  export DISPLAY="$DISPLAY_ENV"
  if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -S /mnt/wslg/runtime-dir/wayland-0 ]; then
    export WAYLAND_DISPLAY=wayland-0
  fi
  if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d /mnt/wslg/runtime-dir ]; then
    export XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir
  fi
  export QT_X11_NO_MITSHM=1
fi
if [ "$PERF_PROFILE" = "compat" ]; then
  export LIBGL_ALWAYS_SOFTWARE=1
fi

cleanup_stale_stack() {
  pkill -f "jetbot_gz_control_camera_test_v5.launch.py" 2>/dev/null || true
  pkill -f "chasecar_tensorrt_detector.py" 2>/dev/null || true
  pkill -f "yolo_3d_position_extractor.py" 2>/dev/null || true
  pkill -f "yolo_3d_to_nav2_bridge.py" 2>/dev/null || true
  pkill -f "jetbot_nav2_complete.launch.py" 2>/dev/null || true
  pkill -f "cmd_vel_relay.py" 2>/dev/null || true
  pkill -f "gz sim -v" 2>/dev/null || true
  pkill -f "gz sim server" 2>/dev/null || true
  pkill -f "ign gazebo" 2>/dev/null || true
}

cleanup_stale_stack
sleep 1

RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
START_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_EPOCH=$(date +%s)
if [ -n "$EVIDENCE_DIR_INPUT" ]; then
  if [[ "$EVIDENCE_DIR_INPUT" == /* ]]; then
    ARTIFACT_DIR="$EVIDENCE_DIR_INPUT"
  else
    ARTIFACT_DIR="$PACKAGE_PATH/$EVIDENCE_DIR_INPUT"
  fi
else
  ARTIFACT_DIR="$PACKAGE_PATH/artifacts/demos/milestone_${MILESTONE}_$RUN_ID"
fi
mkdir -p "$ARTIFACT_DIR/logs" "$ARTIFACT_DIR/screenshots"

start_bg() {
  local name="$1"
  local cmd="$2"
  nohup bash -lc "$cmd" >"$ARTIFACT_DIR/logs/${name}.log" 2>&1 &
  echo $!
}

wait_for_world_services() {
  local timeout_s="$1"
  local deadline=$(( $(date +%s) + timeout_s ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if command -v gz >/dev/null 2>&1; then
      if gz service -l 2>/dev/null | grep -q "/world/${WORLD_NAME}/create"; then
        echo "world_ready"
        return 0
      fi
    elif command -v ign >/dev/null 2>&1; then
      if ign service -l 2>/dev/null | grep -q "/world/${WORLD_NAME}/create"; then
        echo "world_ready"
        return 0
      fi
    fi
    echo "[heartbeat] waiting_for_world_service /world/${WORLD_NAME}/create"
    sleep 2
  done
  echo "world_service_timeout"
  return 1
}

remove_model_by_name() {
  local model_name="$1"
  local req
  req="name: \"$model_name\" type: 2"
  if command -v gz >/dev/null 2>&1; then
    timeout 4s gz service \
      -s "/world/${WORLD_NAME}/remove/blocking" \
      --reqtype gz.msgs.Entity \
      --reptype gz.msgs.Boolean \
      --timeout 2000 \
      --req "$req" >/dev/null 2>&1 || true
    return 0
  fi
  if command -v ign >/dev/null 2>&1; then
    timeout 4s ign service \
      -s "/world/${WORLD_NAME}/remove/blocking" \
      --reqtype ignition.msgs.Entity \
      --reptype ignition.msgs.Boolean \
      --timeout 2000 \
      --req "$req" >/dev/null 2>&1 || true
    return 0
  fi
  return 0
}

spawn_demo_target() {
  local model_path="$DEMO_TARGET_MODEL_SDF"
  if [[ "$model_path" != /* ]]; then
    model_path="$PACKAGE_PATH/$model_path"
  fi
  if [ ! -f "$model_path" ]; then
    echo "missing_demo_target_sdf:$model_path"
    return 1
  fi

  remove_model_by_name "$DEMO_TARGET_NAME"
  # Remove legacy baked model from yolo_test_world so demo shows one deterministic target.
  remove_model_by_name "golf_ball"

  for attempt in 1 2 3; do
    if timeout "${TARGET_SPAWN_TIMEOUT_S}s" ros2 run ros_gz_sim create \
      -world "$WORLD_NAME" \
      -file "$model_path" \
      -name "$DEMO_TARGET_NAME" \
      -x "$DEMO_TARGET_X" \
      -y "$DEMO_TARGET_Y" \
      -z "$DEMO_TARGET_Z" >/tmp/chasecar_demo_target_spawn.log 2>&1; then
      echo "spawn_ok"
      return 0
    fi
    sleep 2
  done

  echo "spawn_failed"
  return 1
}

SIM_LAUNCH_FILE="$PACKAGE_PATH/ros2_config/launch/jetbot_gz_control_camera_test_v5.launch.py"
SIM_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; export CHASECAR_SOURCE_PATH=$PACKAGE_PATH; ros2 launch $SIM_LAUNCH_FILE world:=$WORLD_FILE headless:=$HEADLESS perf_profile:=$PERF_PROFILE inference_device:=$INFERENCE_DEVICE"
SIM_PID=$(start_bg "sim" "$SIM_CMD")
sleep 6

WORLD_READY=true
WORLD_READY_STATUS="not_checked"
if WORLD_READY_RESULT=$(wait_for_world_services "$WORLD_READY_TIMEOUT_S"); then
  WORLD_READY=true
  WORLD_READY_STATUS="$WORLD_READY_RESULT"
else
  WORLD_READY=false
  WORLD_READY_STATUS="$WORLD_READY_RESULT"
fi

DETECTOR_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/chasecar_tensorrt_detector.py --ros-args -p use_sim_time:=true -p input_topic:=/d415/color/image_raw -p inference_device:=$INFERENCE_DEVICE -p perf_profile:=$PERF_PROFILE -p headless:=$HEADLESS -p inference_backend:=$INFERENCE_BACKEND -p allow_red_fallback:=true"
DETECTOR_PID=$(start_bg "detector" "$DETECTOR_CMD")

FEED_VIEWERS_REQUIRED=false
FEED_VIEWERS_RUNNING=true
FEED_RAW_VIEWER_PID=""
FEED_DEBUG_VIEWER_PID=""
FEED_VIEWER_STATUS="skipped"
if [ "$HEADLESS" = "false" ] && [ "$OPEN_FEED_VIEWERS" = "true" ]; then
  FEED_VIEWERS_REQUIRED=true
  if ! ros2 pkg executables rqt_image_view 2>/dev/null | grep -q "rqt_image_view"; then
    FEED_VIEWERS_RUNNING=false
    FEED_VIEWER_STATUS="rqt_image_view_missing"
  else
    VIEWER_RGB_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; ros2 run rqt_image_view rqt_image_view /d415/color/image_raw"
    VIEWER_DEBUG_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; ros2 run rqt_image_view rqt_image_view /yolo/debug_image"
    FEED_RAW_VIEWER_PID=$(start_bg "viewer_rgb" "$VIEWER_RGB_CMD")
    FEED_DEBUG_VIEWER_PID=$(start_bg "viewer_debug" "$VIEWER_DEBUG_CMD")
    sleep "$VIEWER_START_DELAY_S"
    if [ -n "$FEED_RAW_VIEWER_PID" ] && ! kill -0 "$FEED_RAW_VIEWER_PID" 2>/dev/null; then
      FEED_VIEWERS_RUNNING=false
    fi
    if [ -n "$FEED_DEBUG_VIEWER_PID" ] && ! kill -0 "$FEED_DEBUG_VIEWER_PID" 2>/dev/null; then
      FEED_VIEWERS_RUNNING=false
    fi
    if [ "$FEED_VIEWERS_RUNNING" = "true" ]; then
      FEED_VIEWER_STATUS="running"
    else
      FEED_VIEWER_STATUS="viewer_process_exit"
    fi
  fi
fi

TARGET_SPAWN_OK=true
TARGET_SPAWN_STATUS="skipped"
if [ "$ENSURE_DEMO_TARGET" = "true" ]; then
  sleep 4
  if [ "$WORLD_READY" = "true" ]; then
    if TARGET_SPAWN_RESULT=$(spawn_demo_target); then
      TARGET_SPAWN_OK=true
      TARGET_SPAWN_STATUS="$TARGET_SPAWN_RESULT"
    else
      TARGET_SPAWN_OK=false
      TARGET_SPAWN_STATUS="$TARGET_SPAWN_RESULT"
    fi
  else
    TARGET_SPAWN_OK=false
    TARGET_SPAWN_STATUS="blocked_world_not_ready"
  fi
fi

EXTRACTOR_PID=""
if [ "$INCLUDE_EXTRACTOR" = "true" ]; then
  sleep 3
  EXTRACTOR_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_position_extractor.py --ros-args -p use_sim_time:=true"
  EXTRACTOR_PID=$(start_bg "extractor" "$EXTRACTOR_CMD")
fi

BRIDGE_PID=""
if [ "$INCLUDE_BRIDGE" = "true" ]; then
  sleep 3
  BRIDGE_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_to_nav2_bridge.py --ros-args -p use_sim_time:=true"
  BRIDGE_PID=$(start_bg "bridge" "$BRIDGE_CMD")
fi

CAPTURE_DELAY_S=4
if [ "$INCLUDE_EXTRACTOR" = "true" ]; then
  CAPTURE_DELAY_S=$((CAPTURE_DELAY_S + 2))
fi
if [ "$INCLUDE_BRIDGE" = "true" ]; then
  CAPTURE_DELAY_S=$((CAPTURE_DELAY_S + 3))
fi
sleep "$CAPTURE_DELAY_S"

RGB_CAPTURE_RAW=$(python3 "$PACKAGE_PATH/scripts/capture_topic_image.py" \
  --topic /d415/color/image_raw \
  --output "$ARTIFACT_DIR/screenshots/d415_color.png" \
  --timeout-s 10.0 \
  --placeholder-label "rgb_missing" \
  --qos-profile "$CAPTURE_QOS_PROFILE" \
  --min-frames "$CAPTURE_MIN_FRAMES" \
  --use-sim-time 2>&1 || true)

DEBUG_CAPTURE_RAW=$(python3 "$PACKAGE_PATH/scripts/capture_topic_image.py" \
  --topic /yolo/debug_image \
  --output "$ARTIFACT_DIR/screenshots/yolo_debug.png" \
  --timeout-s 10.0 \
  --placeholder-label "debug_missing" \
  --qos-profile "$CAPTURE_QOS_PROFILE" \
  --min-frames "$CAPTURE_MIN_FRAMES" \
  --use-sim-time 2>&1 || true)

RGB_CAPTURED=false
DEBUG_CAPTURED=false
RGB_TOPIC_SEEN=false
DEBUG_TOPIC_SEEN=false
RGB_FRAMES_SEEN=0
DEBUG_FRAMES_SEEN=0
RGB_CAPTURE_ERROR="none"
DEBUG_CAPTURE_ERROR="none"
if echo "$RGB_CAPTURE_RAW" | grep -q "CAPTURED=true"; then
  RGB_CAPTURED=true
fi
if echo "$DEBUG_CAPTURE_RAW" | grep -q "CAPTURED=true"; then
  DEBUG_CAPTURED=true
fi
if echo "$RGB_CAPTURE_RAW" | grep -q "TOPIC_SEEN=true"; then
  RGB_TOPIC_SEEN=true
fi
if echo "$DEBUG_CAPTURE_RAW" | grep -q "TOPIC_SEEN=true"; then
  DEBUG_TOPIC_SEEN=true
fi
RGB_FRAMES_SEEN=$(echo "$RGB_CAPTURE_RAW" | awk -F= '/FRAMES_SEEN=/{print $2}' | tail -n1)
DEBUG_FRAMES_SEEN=$(echo "$DEBUG_CAPTURE_RAW" | awk -F= '/FRAMES_SEEN=/{print $2}' | tail -n1)
if [[ -z "$RGB_FRAMES_SEEN" ]]; then RGB_FRAMES_SEEN=0; fi
if [[ -z "$DEBUG_FRAMES_SEEN" ]]; then DEBUG_FRAMES_SEEN=0; fi
RGB_CAPTURE_ERROR=$(echo "$RGB_CAPTURE_RAW" | awk -F= '/CAPTURE_ERROR=/{print $2}' | tail -n1)
DEBUG_CAPTURE_ERROR=$(echo "$DEBUG_CAPTURE_RAW" | awk -F= '/CAPTURE_ERROR=/{print $2}' | tail -n1)
if [[ -z "$RGB_CAPTURE_ERROR" ]]; then RGB_CAPTURE_ERROR="none"; fi
if [[ -z "$DEBUG_CAPTURE_ERROR" ]]; then DEBUG_CAPTURE_ERROR="none"; fi

OVERLAY_DISTINCT=false
IMAGE_DIFF_ABS_MEAN=0
IMAGE_DIFF_MAX=0
IMAGE_BYTE_IDENTICAL=true
IMAGE_DIFF_JSON="$ARTIFACT_DIR/screenshots/image_diff_metrics.json"
if [ "$RGB_CAPTURED" = "true" ] && [ "$DEBUG_CAPTURED" = "true" ]; then
  DIFF_RAW=$(python3 "$PACKAGE_PATH/scripts/image_diff_metrics.py" \
    --left "$ARTIFACT_DIR/screenshots/d415_color.png" \
    --right "$ARTIFACT_DIR/screenshots/yolo_debug.png" \
    --json-out "$IMAGE_DIFF_JSON" 2>&1 || true)
  IMAGE_DIFF_ABS_MEAN=$(echo "$DIFF_RAW" | awk -F= '/MEAN_ABS_DIFF=/{print $2}' | tail -n1)
  IMAGE_DIFF_MAX=$(echo "$DIFF_RAW" | awk -F= '/MAX_ABS_DIFF=/{print $2}' | tail -n1)
  if echo "$DIFF_RAW" | grep -q "BYTE_IDENTICAL=true"; then
    IMAGE_BYTE_IDENTICAL=true
  else
    IMAGE_BYTE_IDENTICAL=false
  fi
  if [[ -z "$IMAGE_DIFF_ABS_MEAN" ]]; then IMAGE_DIFF_ABS_MEAN=0; fi
  if [[ -z "$IMAGE_DIFF_MAX" ]]; then IMAGE_DIFF_MAX=0; fi
fi

DETECTION_CONFIDENCE_RAW=$(timeout 8s ros2 topic echo /yolo/confidence --once 2>/dev/null || true)
DETECTION_CONFIDENCE=$(echo "$DETECTION_CONFIDENCE_RAW" | awk '/data:/{print $2}' | tail -n1)
DETECTION_SEEN=false
DETECTION_ABOVE_THRESHOLD=false
if [ -n "$DETECTION_CONFIDENCE" ]; then
  DETECTION_SEEN=true
  if awk -v v="$DETECTION_CONFIDENCE" -v t="$MIN_DETECTION_CONFIDENCE" 'BEGIN{exit !(v+0 >= t+0)}'; then
    DETECTION_ABOVE_THRESHOLD=true
  fi
else
  DETECTION_CONFIDENCE=0
fi
if [ "$DETECTION_ABOVE_THRESHOLD" = "true" ]; then
  if awk -v v="$IMAGE_DIFF_ABS_MEAN" 'BEGIN{exit !(v+0 > 0.5)}'; then
    OVERLAY_DISTINCT=true
  fi
fi

SIM_RUNNING=false
DETECTOR_RUNNING=false
EXTRACTOR_RUNNING=false
BRIDGE_RUNNING=false
FEED_RAW_VIEWER_RUNNING=false
FEED_DEBUG_VIEWER_RUNNING=false
if kill -0 "$SIM_PID" 2>/dev/null; then
  SIM_RUNNING=true
fi
if kill -0 "$DETECTOR_PID" 2>/dev/null; then
  DETECTOR_RUNNING=true
fi
if [ -n "$EXTRACTOR_PID" ] && kill -0 "$EXTRACTOR_PID" 2>/dev/null; then
  EXTRACTOR_RUNNING=true
fi
if [ -n "$BRIDGE_PID" ] && kill -0 "$BRIDGE_PID" 2>/dev/null; then
  BRIDGE_RUNNING=true
fi
if [ -n "$FEED_RAW_VIEWER_PID" ] && kill -0 "$FEED_RAW_VIEWER_PID" 2>/dev/null; then
  FEED_RAW_VIEWER_RUNNING=true
fi
if [ -n "$FEED_DEBUG_VIEWER_PID" ] && kill -0 "$FEED_DEBUG_VIEWER_PID" 2>/dev/null; then
  FEED_DEBUG_VIEWER_RUNNING=true
fi
if [ "$FEED_VIEWERS_REQUIRED" = "true" ]; then
  if [ "$FEED_RAW_VIEWER_RUNNING" != "true" ] || [ "$FEED_DEBUG_VIEWER_RUNNING" != "true" ]; then
    FEED_VIEWERS_RUNNING=false
  fi
fi

DEMO_PASS=false
EXTRACTOR_REQUIRED=false
BRIDGE_REQUIRED=false
EXTRACTOR_CHECK_PASS=true
BRIDGE_CHECK_PASS=true
if [ "$MILESTONE" = "1" ]; then
  if [ "$WORLD_READY" = true ] \
    && [ "$SIM_RUNNING" = true ] \
    && [ "$DETECTOR_RUNNING" = true ] \
    && [ "$DEBUG_CAPTURED" = true ] \
    && [ "$TARGET_SPAWN_OK" = true ] \
    && [ "$DETECTION_ABOVE_THRESHOLD" = true ] \
    && [ "$OVERLAY_DISTINCT" = true ] \
    && [ "$FEED_VIEWERS_RUNNING" = true ]; then
    DEMO_PASS=true
  fi
elif [ "$MILESTONE" = "2" ]; then
  EXTRACTOR_REQUIRED=true
  EXTRACTOR_CHECK_PASS=$EXTRACTOR_RUNNING
  if [ "$SIM_RUNNING" = true ] && [ "$DETECTOR_RUNNING" = true ] && [ "$EXTRACTOR_RUNNING" = true ] && [ "$DEBUG_CAPTURED" = true ]; then
    DEMO_PASS=true
  fi
else
  EXTRACTOR_REQUIRED=true
  BRIDGE_REQUIRED=true
  EXTRACTOR_CHECK_PASS=$EXTRACTOR_RUNNING
  BRIDGE_CHECK_PASS=$BRIDGE_RUNNING
  if [ "$SIM_RUNNING" = true ] && [ "$DETECTOR_RUNNING" = true ] && [ "$EXTRACTOR_RUNNING" = true ] && [ "$BRIDGE_RUNNING" = true ] && [ "$DEBUG_CAPTURED" = true ]; then
    DEMO_PASS=true
  fi
fi

cat >"$ARTIFACT_DIR/operator_checklist.json" <<JSON
{
  "milestone": "$MILESTONE",
  "generated_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "items": [
    {
      "id": "sim_running",
      "description": "Simulation process is running",
      "pass": $SIM_RUNNING
    },
    {
      "id": "detector_running",
      "description": "Detector process is running",
      "pass": $DETECTOR_RUNNING
    },
    {
      "id": "world_ready",
      "description": "World service became available",
      "pass": $WORLD_READY
    },
    {
      "id": "target_spawn",
      "description": "Deterministic demo target spawn completed",
      "required": $ENSURE_DEMO_TARGET,
      "pass": $TARGET_SPAWN_OK
    },
    {
      "id": "detection_confidence",
      "description": "Detection confidence reached minimum threshold",
      "required": true,
      "pass": $DETECTION_ABOVE_THRESHOLD
    },
    {
      "id": "overlay_distinct",
      "description": "Debug image differs from raw image when detection is above threshold",
      "required": true,
      "pass": $OVERLAY_DISTINCT
    },
    {
      "id": "extractor_running",
      "description": "3D extractor process is running when required",
      "required": $EXTRACTOR_REQUIRED,
      "pass": $EXTRACTOR_CHECK_PASS
    },
    {
      "id": "bridge_running",
      "description": "Nav bridge process is running when required",
      "required": $BRIDGE_REQUIRED,
      "pass": $BRIDGE_CHECK_PASS
    },
    {
      "id": "rgb_snapshot",
      "description": "RGB screenshot capture completed",
      "pass": $RGB_CAPTURED
    },
    {
      "id": "debug_snapshot",
      "description": "YOLO debug screenshot capture completed",
      "pass": $DEBUG_CAPTURED
    },
    {
      "id": "feed_viewers_running",
      "description": "Live feed viewer windows are running when requested",
      "required": $FEED_VIEWERS_REQUIRED,
      "pass": $FEED_VIEWERS_RUNNING
    }
  ]
}
JSON

cat >"$ARTIFACT_DIR/demo_summary.json" <<JSON
{
  "milestone": "$MILESTONE",
  "runtime_target": "$RUNTIME_TARGET",
  "perf_profile": "$PERF_PROFILE",
  "inference_device": "$INFERENCE_DEVICE",
  "inference_backend": "$INFERENCE_BACKEND",
  "headless": $HEADLESS,
  "start_utc": "$START_UTC",
  "end_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "evidence_generated_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "max_run_seconds": ${MAX_RUN_SECONDS:-0},
  "auto_stop_enabled": $([ "${MAX_RUN_SECONDS:-0}" -gt 0 ] && echo true || echo false),
  "commands": {
    "sim": "$SIM_CMD",
    "detector": "$DETECTOR_CMD",
    "extractor": "${EXTRACTOR_CMD:-}",
    "bridge": "${BRIDGE_CMD:-}"
  },
  "screenshots": {
    "rgb": "screenshots/d415_color.png",
    "yolo_debug": "screenshots/yolo_debug.png"
  },
  "capture": {
    "rgb_captured": $RGB_CAPTURED,
    "debug_captured": $DEBUG_CAPTURED,
    "rgb_topic_seen": $RGB_TOPIC_SEEN,
    "debug_topic_seen": $DEBUG_TOPIC_SEEN,
    "rgb_frames_seen": $RGB_FRAMES_SEEN,
    "debug_frames_seen": $DEBUG_FRAMES_SEEN,
    "rgb_capture_error": "$RGB_CAPTURE_ERROR",
    "debug_capture_error": "$DEBUG_CAPTURE_ERROR",
    "capture_qos_profile": "$CAPTURE_QOS_PROFILE",
    "capture_min_frames": $CAPTURE_MIN_FRAMES,
    "capture_delay_s": $CAPTURE_DELAY_S,
    "detection_seen": $DETECTION_SEEN,
    "detection_confidence": $DETECTION_CONFIDENCE,
    "detection_confidence_threshold": $MIN_DETECTION_CONFIDENCE,
    "detection_above_threshold": $DETECTION_ABOVE_THRESHOLD,
    "overlay_distinct": $OVERLAY_DISTINCT,
    "image_byte_identical": $IMAGE_BYTE_IDENTICAL,
    "image_diff_abs_mean": $IMAGE_DIFF_ABS_MEAN,
    "image_diff_max": $IMAGE_DIFF_MAX,
    "image_diff_metrics_json": "screenshots/image_diff_metrics.json"
  },
  "demo_target": {
    "ensure_demo_target": $ENSURE_DEMO_TARGET,
    "world_name": "$WORLD_NAME",
    "target_model_sdf": "$DEMO_TARGET_MODEL_SDF",
    "target_name": "$DEMO_TARGET_NAME",
    "target_spawn_x": $DEMO_TARGET_X,
    "target_spawn_y": $DEMO_TARGET_Y,
    "target_spawn_z": $DEMO_TARGET_Z,
    "target_spawn_ok": $TARGET_SPAWN_OK,
    "target_spawn_status": "$TARGET_SPAWN_STATUS",
    "target_spawn_timeout_s": $TARGET_SPAWN_TIMEOUT_S,
    "world_ready": $WORLD_READY,
    "world_ready_status": "$WORLD_READY_STATUS",
    "world_ready_timeout_s": $WORLD_READY_TIMEOUT_S
  },
  "viewers": {
    "open_feed_viewers_requested": $OPEN_FEED_VIEWERS,
    "feed_viewers_required": $FEED_VIEWERS_REQUIRED,
    "feed_viewers_running": $FEED_VIEWERS_RUNNING,
    "feed_viewer_status": "$FEED_VIEWER_STATUS",
    "viewer_start_delay_s": $VIEWER_START_DELAY_S
  },
  "process_health": {
    "sim_running": $SIM_RUNNING,
    "detector_running": $DETECTOR_RUNNING,
    "extractor_running": $EXTRACTOR_RUNNING,
    "bridge_running": $BRIDGE_RUNNING,
    "feed_raw_viewer_running": $FEED_RAW_VIEWER_RUNNING,
    "feed_debug_viewer_running": $FEED_DEBUG_VIEWER_RUNNING
  },
  "pass": $DEMO_PASS
}
JSON

WATCHDOG_PID=""
if [[ "$MAX_RUN_SECONDS" =~ ^[0-9]+$ ]] && [ "$MAX_RUN_SECONDS" -gt 0 ]; then
  NOW_EPOCH=$(date +%s)
  ELAPSED_S=$((NOW_EPOCH - START_EPOCH))
  REMAINING_S=$((MAX_RUN_SECONDS - ELAPSED_S))
  if [ "$REMAINING_S" -gt 0 ]; then
    sleep "$REMAINING_S"
  fi
  kill "$SIM_PID" "$DETECTOR_PID" ${EXTRACTOR_PID:+$EXTRACTOR_PID} ${BRIDGE_PID:+$BRIDGE_PID} ${FEED_RAW_VIEWER_PID:+$FEED_RAW_VIEWER_PID} ${FEED_DEBUG_VIEWER_PID:+$FEED_DEBUG_VIEWER_PID} 2>/dev/null || true
fi

cat >"$ARTIFACT_DIR/demo_pids.json" <<JSON
{
  "milestone": "$MILESTONE",
  "runtime_target": "$RUNTIME_TARGET",
  "perf_profile": "$PERF_PROFILE",
  "inference_device": "$INFERENCE_DEVICE",
  "headless": $HEADLESS,
  "launch_package": "source_path",
  "evidence_dir": "$ARTIFACT_DIR",
  "max_run_seconds": ${MAX_RUN_SECONDS:-0},
  "watchdog_pid": "$WATCHDOG_PID",
  "pids": {
    "sim": "$SIM_PID",
    "detector": "$DETECTOR_PID",
    "extractor": "$EXTRACTOR_PID",
    "bridge": "$BRIDGE_PID",
    "feed_rgb_viewer": "$FEED_RAW_VIEWER_PID",
    "feed_debug_viewer": "$FEED_DEBUG_VIEWER_PID"
  }
}
JSON

echo "ARTIFACT_DIR=$ARTIFACT_DIR"
echo "SIM_PID=$SIM_PID"
echo "DETECTOR_PID=$DETECTOR_PID"
echo "EXTRACTOR_PID=$EXTRACTOR_PID"
echo "BRIDGE_PID=$BRIDGE_PID"
echo "FEED_RGB_VIEWER_PID=$FEED_RAW_VIEWER_PID"
echo "FEED_DEBUG_VIEWER_PID=$FEED_DEBUG_VIEWER_PID"
echo "WATCHDOG_PID=$WATCHDOG_PID"
echo "EVIDENCE_CAPTURE_RGB=$RGB_CAPTURED"
echo "EVIDENCE_CAPTURE_DEBUG=$DEBUG_CAPTURED"
echo "STOP_CMD=wsl -d __DISTRO__ -- bash -lc 'kill $SIM_PID $DETECTOR_PID ${EXTRACTOR_PID:-} ${BRIDGE_PID:-} ${FEED_RAW_VIEWER_PID:-} ${FEED_DEBUG_VIEWER_PID:-} 2>/dev/null || true'"
'@

$bash = $bashTemplate.
    Replace("__WORKSPACE__", $WorkspacePath).
    Replace("__REPO_PATH__", $repoRootWsl).
    Replace("__MILESTONE__", $Milestone.ToString()).
    Replace("__RUNTIME_TARGET__", $RuntimeTarget).
    Replace("__PERF_PROFILE__", $PerfProfile).
    Replace("__INFERENCE_DEVICE__", $InferenceDevice).
    Replace("__INFERENCE_BACKEND__", $InferenceBackend).
    Replace("__HEADLESS__", $headlessStr).
    Replace("__DISPLAY_ENV__", $displayEnv).
    Replace("__INCLUDE_EXTRACTOR__", $includeExtractor).
    Replace("__INCLUDE_BRIDGE__", $includeBridge).
    Replace("__WORLD_FILE__", $WorldFile).
    Replace("__WORLD_NAME__", $WorldName).
    Replace("__ROS_DISTRO__", $RosDistro).
    Replace("__EVIDENCE_DIR_INPUT__", $evidenceInputWsl).
    Replace("__MAX_RUN_SECONDS__", $MaxRunSeconds.ToString()).
    Replace("__CAPTURE_QOS_PROFILE__", $CaptureQosProfile).
    Replace("__CAPTURE_MIN_FRAMES__", ([Math]::Max($CaptureMinFrames, 1)).ToString()).
    Replace("__ENSURE_DEMO_TARGET__", $ensureDemoTargetStr).
    Replace("__DEMO_TARGET_MODEL_SDF__", $DemoTargetModelSdf.Replace('\', '/')).
    Replace("__DEMO_TARGET_NAME__", $DemoTargetName).
    Replace("__DEMO_TARGET_X__", $DemoTargetX.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__DEMO_TARGET_Y__", $DemoTargetY.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__DEMO_TARGET_Z__", $DemoTargetZ.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__TARGET_SPAWN_TIMEOUT_S__", ([Math]::Max($TargetSpawnTimeoutSeconds, 5)).ToString()).
    Replace("__MIN_DETECTION_CONFIDENCE__", $MinDetectionConfidence.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__OPEN_FEED_VIEWERS__", $openFeedViewersStr).
    Replace("__VIEWER_START_DELAY_S__", ([Math]::Max($ViewerStartupDelaySeconds, 1)).ToString()).
    Replace("__WORLD_READY_TIMEOUT_S__", ([Math]::Max($WorldReadyTimeoutSeconds, 10)).ToString()).
    Replace("__DISTRO__", $Distro)
$bash = $bash.Replace("`r`n", "`n")

Write-Host "Launching milestone demo $Milestone..."
Write-Host "  Runtime target: $RuntimeTarget"
Write-Host "  Perf profile:   $PerfProfile"
Write-Host "  Inference dev:  $InferenceDevice"
Write-Host "  Inference back: $InferenceBackend"
Write-Host "  Headless:       $headlessStr"
Write-Host "  Capture QoS:    $CaptureQosProfile"
Write-Host "  Capture frames: $([Math]::Max($CaptureMinFrames, 1))"
Write-Host "  World:          $WorldFile"
Write-Host "  World name:     $WorldName"
Write-Host "  Ensure target:  $([bool]$EnsureDemoTarget)"
Write-Host "  Open viewers:   $([bool]$OpenFeedViewers)"
Write-Host "  ROS distro:     $RosDistro"

$tempScriptWin = Join-Path $env:TEMP ("chasecar_run_milestone_demo_{0}.sh" -f ([Guid]::NewGuid().ToString("N")))
[System.IO.File]::WriteAllText($tempScriptWin, $bash, [System.Text.Encoding]::ASCII)
$tempScriptWsl = Convert-ToWslPath -WindowsPath $tempScriptWin

try {
    wsl -d $Distro -- bash $tempScriptWsl
    $exitCode = $LASTEXITCODE
}
finally {
    Remove-Item -LiteralPath $tempScriptWin -Force -ErrorAction SilentlyContinue
}

if ($exitCode -ne 0) {
    Write-Error "Milestone demo launch failed with exit code $exitCode"
    exit $exitCode
}

Write-Host ""
if ($Milestone -eq 1) {
    Write-Host "Milestone 1 Checklist:"
    Write-Host "  1. Gazebo is visible (if not headless)."
    Write-Host "  2. Two feed windows are visible: /d415/color/image_raw and /yolo/debug_image (when OpenFeedViewers=true)."
    Write-Host "  3. Detection confidence updates on /yolo/confidence."
    Write-Host "  4. debug image overlay differs from raw RGB once confidence gate is met."
    Write-Host "Success criteria: stable detections across multiple target positions."
}
elseif ($Milestone -eq 2) {
    Write-Host "Milestone 2 Checklist:"
    Write-Host "  1. Milestone 1 checks all pass."
    Write-Host "  2. /yolo/ball_position_3d publishes continuously."
    Write-Host "  3. Error table updates during target movement."
    Write-Host "Success criteria: truth-vs-estimate error remains within UAT thresholds."
}
else {
    Write-Host "Milestone 3 Checklist:"
    Write-Host "  1. Milestone 2 checks all pass."
    Write-Host "  2. Nav2 bridge receives 3D positions."
    Write-Host "  3. Robot approaches selected target autonomously."
    Write-Host "Success criteria: robot reaches approach distance without controller failure."
}

exit 0





