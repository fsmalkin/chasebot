param(
    [ValidateSet("robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity",

    [ValidateSet("compat", "balanced", "max")]
    [string]$PerfProfile,

    [string]$InferenceDevice,

    [Nullable[bool]]$Headless = $null,

    [switch]$EvaluateNavigation,

    [string]$Distro = "Ubuntu-22.04",

    [string]$WorkspacePath = "~/ros2_ws",

    [string]$ConfigPath = "ros2_config/config/uat_coordinates.yaml"
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

$defaults = @{
    robot_fidelity = @{
        PerfProfile = "compat"
        InferenceDevice = "cpu"
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

$headlessStr = if ($Headless) { "true" } else { "false" }
$evaluateNavigationStr = if ($EvaluateNavigation) { "true" } else { "false" }

$repoRootWin = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$repoRootWsl = Convert-ToWslPath -WindowsPath $repoRootWin

$configWin = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    Resolve-Path -LiteralPath $ConfigPath
} else {
    Resolve-Path -LiteralPath (Join-Path $repoRootWin $ConfigPath)
}
$configWsl = Convert-ToWslPath -WindowsPath $configWin

$displayEnv = ""
if (-not $Headless) {
    $displayIp = (wsl -d $Distro -- bash -lc "ip route show default | awk '{print \$3}' | head -n1").Trim()
    if ([string]::IsNullOrWhiteSpace($displayIp)) {
        $displayIp = "127.0.0.1"
    }
    $displayEnv = "$displayIp`:0.0"
}

$bashTemplate = @'
set -euo pipefail

WORKSPACE="__WORKSPACE__"
REPO_PATH="__REPO_PATH__"
CONFIG_PATH="__CONFIG_PATH__"
RUNTIME_TARGET="__RUNTIME_TARGET__"
PERF_PROFILE="__PERF_PROFILE__"
INFERENCE_DEVICE="__INFERENCE_DEVICE__"
HEADLESS="__HEADLESS__"
DISPLAY_ENV="__DISPLAY_ENV__"
EVAL_NAV="__EVAL_NAV__"

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

source /opt/ros/humble/setup.bash
cd "$WORKSPACE"
if [ -f "install/setup.bash" ]; then
  source install/setup.bash
fi

if ros2 pkg prefix chasebot_sim >/dev/null 2>&1; then
  LAUNCH_PACKAGE="chasebot_sim"
else
  LAUNCH_PACKAGE="chasebot_description"
fi

if [ "$HEADLESS" = "false" ] && [ -n "$DISPLAY_ENV" ]; then
  export DISPLAY="$DISPLAY_ENV"
  export QT_X11_NO_MITSHM=1
fi
if [ "$PERF_PROFILE" = "compat" ]; then
  export LIBGL_ALWAYS_SOFTWARE=1
fi

RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
ARTIFACT_DIR="$PACKAGE_PATH/artifacts/uat/$RUN_ID"
mkdir -p "$ARTIFACT_DIR/logs"

start_bg() {
  local name="$1"
  local cmd="$2"
  nohup bash -lc "$cmd" >"$ARTIFACT_DIR/logs/${name}.log" 2>&1 &
  echo $!
}

SIM_CMD="source /opt/ros/humble/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; ros2 launch $LAUNCH_PACKAGE jetbot_gz_control_camera_test_v5.launch.py headless:=$HEADLESS perf_profile:=$PERF_PROFILE inference_device:=$INFERENCE_DEVICE"
SIM_PID=$(start_bg "sim" "$SIM_CMD")
sleep 12

DETECTOR_CMD="source /opt/ros/humble/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/ros2_yolo_detector_frisbee_quiet.py --ros-args -p use_sim_time:=true -p input_topic:=/d415/color/image_raw -p inference_device:=$INFERENCE_DEVICE -p perf_profile:=$PERF_PROFILE -p headless:=$HEADLESS"
DETECTOR_PID=$(start_bg "detector" "$DETECTOR_CMD")
sleep 4

EXTRACTOR_CMD="source /opt/ros/humble/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_position_extractor.py --ros-args -p use_sim_time:=true"
EXTRACTOR_PID=$(start_bg "extractor" "$EXTRACTOR_CMD")
sleep 3

BRIDGE_PID=""
if [ "$EVAL_NAV" = "true" ]; then
  BRIDGE_CMD="source /opt/ros/humble/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_to_nav2_bridge.py --ros-args -p use_sim_time:=true"
  BRIDGE_PID=$(start_bg "bridge" "$BRIDGE_CMD")
  sleep 2
fi

set +e
UAT_ARGS=(
  "--config" "$CONFIG_PATH"
  "--runtime-target" "$RUNTIME_TARGET"
  "--profile" "$PERF_PROFILE"
  "--inference-device" "$INFERENCE_DEVICE"
)
if [ "$EVAL_NAV" = "true" ]; then
  UAT_ARGS+=("--evaluate-navigation")
fi

python3 "$PACKAGE_PATH/scripts/coordinate_uat_runner.py" "${UAT_ARGS[@]}"
UAT_EXIT=$?
set -e

kill "$SIM_PID" "$DETECTOR_PID" "$EXTRACTOR_PID" ${BRIDGE_PID:+$BRIDGE_PID} 2>/dev/null || true
sleep 1

echo "ARTIFACT_DIR=$ARTIFACT_DIR"
echo "UAT_EXIT=$UAT_EXIT"
exit "$UAT_EXIT"
'@

$bash = $bashTemplate.
    Replace("__WORKSPACE__", $WorkspacePath).
    Replace("__REPO_PATH__", $repoRootWsl).
    Replace("__CONFIG_PATH__", $configWsl).
    Replace("__RUNTIME_TARGET__", $RuntimeTarget).
    Replace("__PERF_PROFILE__", $PerfProfile).
    Replace("__INFERENCE_DEVICE__", $InferenceDevice).
    Replace("__HEADLESS__", $headlessStr).
    Replace("__DISPLAY_ENV__", $displayEnv).
    Replace("__EVAL_NAV__", $evaluateNavigationStr)

Write-Host "Running coordinate UAT..."
Write-Host "  Runtime target: $RuntimeTarget"
Write-Host "  Perf profile:   $PerfProfile"
Write-Host "  Inference dev:  $InferenceDevice"
Write-Host "  Headless:       $headlessStr"
Write-Host "  Evaluate nav:   $evaluateNavigationStr"
Write-Host "  Config:         $ConfigPath"

wsl -d $Distro -- bash -lc $bash
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "Coordinate UAT failed with exit code $exitCode"
}
exit $exitCode
