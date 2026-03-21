param(
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity_orin",

    [ValidateSet("compat", "balanced", "max")]
    [string]$PerfProfile,

    [string]$InferenceDevice,

    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",

    [Nullable[bool]]$Headless = $null,

    [string]$Distro = "Ubuntu-24.04",

    [string]$WorkspacePath = "~/ros2_ws",

    [string]$WorldFile = "yolo_test_world_v6_clean_uat.world",

    [string]$ConfigPath = "ros2_config/config/nav2_readiness.yaml",

    [double]$DurationSeconds = 120,

    [double]$TargetX = 1.20,

    [double]$TargetY = 0.00,

    [double]$TargetZ = 0.05,

    [string]$RosDistro = "auto"
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
$RosDistro = Resolve-RosDistro -Distro $Distro -Requested $RosDistro

$headlessStr = if ($Headless) { "true" } else { "false" }
$repoRootWin = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$repoRootWsl = Convert-ToWslPath -WindowsPath $repoRootWin

$configInputWsl = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    $configWin = Resolve-Path -LiteralPath $ConfigPath
    Convert-ToWslPath -WindowsPath $configWin
} else {
    $ConfigPath.Replace('\', '/')
}

$displayEnv = ""
if (-not $Headless) {
    $displayIp = (wsl -d $Distro -- bash -lc "ip route show default | awk '{print \$3}' | head -n1").Trim()
    if ([string]::IsNullOrWhiteSpace($displayIp)) {
        $displayIp = "127.0.0.1"
    }
    $displayEnv = "$displayIp`:0.0"
}

$bashTemplate = @'
set -eo pipefail

WORKSPACE="__WORKSPACE__"
REPO_PATH="__REPO_PATH__"
CONFIG_PATH_INPUT="__CONFIG_PATH_INPUT__"
RUNTIME_TARGET="__RUNTIME_TARGET__"
PERF_PROFILE="__PERF_PROFILE__"
INFERENCE_DEVICE="__INFERENCE_DEVICE__"
INFERENCE_BACKEND="__INFERENCE_BACKEND__"
HEADLESS="__HEADLESS__"
DISPLAY_ENV="__DISPLAY_ENV__"
DURATION_S="__DURATION_S__"
WORLD_FILE="__WORLD_FILE__"
ROS_DISTRO="__ROS_DISTRO__"
TARGET_X="__TARGET_X__"
TARGET_Y="__TARGET_Y__"
TARGET_Z="__TARGET_Z__"

if [[ "$WORKSPACE" == "~/"* ]]; then
  WORKSPACE="$HOME/${WORKSPACE:2}"
elif [[ "$WORKSPACE" == "~" ]]; then
  WORKSPACE="$HOME"
fi

if [ -d "$WORKSPACE/src/chasecar_runtime" ]; then
  PACKAGE_PATH="$WORKSPACE/src/chasecar_runtime"
elif [ -d "$WORKSPACE/src/chasecar" ]; then
  PACKAGE_PATH="$WORKSPACE/src/chasecar"
elif [ -d "$WORKSPACE/src/chasebot_description" ]; then
  PACKAGE_PATH="$WORKSPACE/src/chasebot_description"
elif [ -d "$REPO_PATH" ]; then
  PACKAGE_PATH="$REPO_PATH"
else
  echo "Unable to resolve package path under workspace: $WORKSPACE" >&2
  exit 1
fi

if [[ "$CONFIG_PATH_INPUT" == /* ]]; then
  CONFIG_PATH="$CONFIG_PATH_INPUT"
elif [ -f "$PACKAGE_PATH/$CONFIG_PATH_INPUT" ]; then
  CONFIG_PATH="$PACKAGE_PATH/$CONFIG_PATH_INPUT"
elif [ -f "$REPO_PATH/$CONFIG_PATH_INPUT" ]; then
  CONFIG_PATH="$REPO_PATH/$CONFIG_PATH_INPUT"
else
  echo "Unable to resolve config path: $CONFIG_PATH_INPUT" >&2
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
ARTIFACT_DIR="$PACKAGE_PATH/artifacts/nav2/$RUN_ID"
mkdir -p "$ARTIFACT_DIR/logs"

start_bg() {
  local name="$1"
  local cmd="$2"
  nohup bash -lc "$cmd" >"$ARTIFACT_DIR/logs/${name}.log" 2>&1 &
  echo $!
}

SIM_LAUNCH_FILE="$PACKAGE_PATH/ros2_config/launch/jetbot_gz_control_camera_test_v5.launch.py"
SIM_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; export CHASECAR_SOURCE_PATH=$PACKAGE_PATH; ros2 launch $SIM_LAUNCH_FILE world:=$WORLD_FILE headless:=$HEADLESS perf_profile:=$PERF_PROFILE inference_device:=$INFERENCE_DEVICE"
SIM_PID=$(start_bg "sim" "$SIM_CMD")
sleep 12

DETECTOR_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/chasecar_tensorrt_detector.py --ros-args -p use_sim_time:=true -p input_topic:=/d415/color/image_raw -p inference_device:=$INFERENCE_DEVICE -p perf_profile:=$PERF_PROFILE -p headless:=$HEADLESS -p inference_backend:=$INFERENCE_BACKEND -p allow_red_fallback:=true"
DETECTOR_PID=$(start_bg "detector" "$DETECTOR_CMD")
sleep 4

EXTRACTOR_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_position_extractor.py --ros-args -p use_sim_time:=true"
EXTRACTOR_PID=$(start_bg "extractor" "$EXTRACTOR_CMD")
sleep 3

TARGET_NAME="nav2_uat_target"
TARGET_SDF="$PACKAGE_PATH/ros2_config/frisbee_target_ball.sdf"
SPAWN_LOG="$ARTIFACT_DIR/logs/spawn_target.log"
SPAWN_TARGET_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; if command -v gz >/dev/null 2>&1; then gz service -s /world/yolo_test_world/remove/blocking --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 1000 --req 'name: \"$TARGET_NAME\" type: 2' >/dev/null 2>&1 || true; fi; ros2 run ros_gz_sim create -world yolo_test_world -file $TARGET_SDF -name $TARGET_NAME -x $TARGET_X -y $TARGET_Y -z $TARGET_Z"
bash -lc "$SPAWN_TARGET_CMD" >"$SPAWN_LOG" 2>&1 || true

NAV2_LAUNCH_FILE="$PACKAGE_PATH/ros2_config/launch/jetbot_nav2_rosgz_readiness.launch.py"
NAV2_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; export CHASECAR_SOURCE_PATH=$PACKAGE_PATH; ros2 launch $NAV2_LAUNCH_FILE use_sim_time:=true autostart:=true"
NAV2_PID=$(start_bg "nav2" "$NAV2_CMD")
sleep 8

RELAY_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/cmd_vel_relay.py"
RELAY_PID=$(start_bg "cmd_vel_relay" "$RELAY_CMD")
sleep 2

ACTION_WAIT_LOG="$ARTIFACT_DIR/logs/nav2_action_wait.log"
bash -lc "source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; for i in \$(seq 1 90); do if ros2 action list 2>/dev/null | grep -q '^/navigate_to_pose$'; then echo READY:\$i; exit 0; fi; sleep 1; done; echo TIMEOUT" >"$ACTION_WAIT_LOG" 2>&1 || true

BRIDGE_CMD="source /opt/ros/$ROS_DISTRO/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_to_nav2_bridge.py --ros-args -p use_sim_time:=true -p action_server_wait_s:=90.0"
BRIDGE_PID=$(start_bg "goal_bridge" "$BRIDGE_CMD")
sleep 2

set +e
python3 "$PACKAGE_PATH/scripts/nav2_readiness_runner.py" \
  --config "$CONFIG_PATH" \
  --runtime-target "$RUNTIME_TARGET" \
  --profile "$PERF_PROFILE" \
  --inference-device "$INFERENCE_DEVICE" \
  --duration-s "$DURATION_S"
UAT_EXIT=$?
set -e

kill "$SIM_PID" "$DETECTOR_PID" "$EXTRACTOR_PID" "$NAV2_PID" "$RELAY_PID" "$BRIDGE_PID" 2>/dev/null || true
sleep 1

echo "ARTIFACT_DIR=$ARTIFACT_DIR"
echo "UAT_EXIT=$UAT_EXIT"
exit "$UAT_EXIT"
'@

$bash = $bashTemplate.
    Replace("__WORKSPACE__", $WorkspacePath).
    Replace("__REPO_PATH__", $repoRootWsl).
    Replace("__CONFIG_PATH_INPUT__", $configInputWsl).
    Replace("__RUNTIME_TARGET__", $RuntimeTarget).
    Replace("__PERF_PROFILE__", $PerfProfile).
    Replace("__INFERENCE_DEVICE__", $InferenceDevice).
    Replace("__INFERENCE_BACKEND__", $InferenceBackend).
    Replace("__HEADLESS__", $headlessStr).
    Replace("__DISPLAY_ENV__", $displayEnv).
    Replace("__DURATION_S__", $DurationSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__WORLD_FILE__", $WorldFile).
    Replace("__ROS_DISTRO__", $RosDistro).
    Replace("__TARGET_X__", $TargetX.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__TARGET_Y__", $TargetY.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
    Replace("__TARGET_Z__", $TargetZ.ToString([System.Globalization.CultureInfo]::InvariantCulture))
$bash = $bash.Replace("`r`n", "`n")

Write-Host "Running Nav2 readiness UAT..."
Write-Host "  Runtime target: $RuntimeTarget"
Write-Host "  Perf profile:   $PerfProfile"
Write-Host "  Inference dev:  $InferenceDevice"
Write-Host "  Inference back: $InferenceBackend"
Write-Host "  Headless:       $headlessStr"
Write-Host "  World:          $WorldFile"
Write-Host "  ROS distro:     $RosDistro"
Write-Host "  Duration (s):   $DurationSeconds"
Write-Host "  Target spawn:   x=$TargetX y=$TargetY z=$TargetZ"
Write-Host "  Config:         $ConfigPath"

$tempScriptWin = Join-Path $env:TEMP ("chasecar_run_nav2_uat_{0}.sh" -f ([Guid]::NewGuid().ToString("N")))
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
    Write-Error "Nav2 readiness UAT failed with exit code $exitCode"
}
exit $exitCode





