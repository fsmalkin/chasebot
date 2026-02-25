param(
    [ValidateSet(1, 2, 3)]
    [int]$Milestone,

    [ValidateSet("robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "workstation_balanced",

    [ValidateSet("compat", "balanced", "max")]
    [string]$PerfProfile,

    [string]$InferenceDevice,

    [Nullable[bool]]$Headless = $null,

    [string]$Distro = "Ubuntu-22.04",

    [string]$WorkspacePath = "~/ros2_ws"
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
$includeExtractor = if ($Milestone -ge 2) { "true" } else { "false" }
$includeBridge = if ($Milestone -ge 3) { "true" } else { "false" }

$repoRootWin = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$repoRootWsl = Convert-ToWslPath -WindowsPath $repoRootWin

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
MILESTONE="__MILESTONE__"
RUNTIME_TARGET="__RUNTIME_TARGET__"
PERF_PROFILE="__PERF_PROFILE__"
INFERENCE_DEVICE="__INFERENCE_DEVICE__"
HEADLESS="__HEADLESS__"
DISPLAY_ENV="__DISPLAY_ENV__"
INCLUDE_EXTRACTOR="__INCLUDE_EXTRACTOR__"
INCLUDE_BRIDGE="__INCLUDE_BRIDGE__"

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
ARTIFACT_DIR="$PACKAGE_PATH/artifacts/demos/milestone_${MILESTONE}_$RUN_ID"
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

EXTRACTOR_PID=""
if [ "$INCLUDE_EXTRACTOR" = "true" ]; then
  sleep 3
  EXTRACTOR_CMD="source /opt/ros/humble/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_position_extractor.py --ros-args -p use_sim_time:=true"
  EXTRACTOR_PID=$(start_bg "extractor" "$EXTRACTOR_CMD")
fi

BRIDGE_PID=""
if [ "$INCLUDE_BRIDGE" = "true" ]; then
  sleep 3
  BRIDGE_CMD="source /opt/ros/humble/setup.bash; cd $WORKSPACE; if [ -f install/setup.bash ]; then source install/setup.bash; fi; python3 $PACKAGE_PATH/ros2_scripts/yolo_3d_to_nav2_bridge.py --ros-args -p use_sim_time:=true"
  BRIDGE_PID=$(start_bg "bridge" "$BRIDGE_CMD")
fi

cat >"$ARTIFACT_DIR/demo_pids.json" <<JSON
{
  "milestone": "$MILESTONE",
  "runtime_target": "$RUNTIME_TARGET",
  "perf_profile": "$PERF_PROFILE",
  "inference_device": "$INFERENCE_DEVICE",
  "headless": $HEADLESS,
  "launch_package": "$LAUNCH_PACKAGE",
  "pids": {
    "sim": "$SIM_PID",
    "detector": "$DETECTOR_PID",
    "extractor": "$EXTRACTOR_PID",
    "bridge": "$BRIDGE_PID"
  }
}
JSON

echo "ARTIFACT_DIR=$ARTIFACT_DIR"
echo "SIM_PID=$SIM_PID"
echo "DETECTOR_PID=$DETECTOR_PID"
echo "EXTRACTOR_PID=$EXTRACTOR_PID"
echo "BRIDGE_PID=$BRIDGE_PID"
echo "STOP_CMD=wsl -d __DISTRO__ -- bash -lc 'kill $SIM_PID $DETECTOR_PID ${EXTRACTOR_PID:-} ${BRIDGE_PID:-} 2>/dev/null || true'"
'@

$bash = $bashTemplate.
    Replace("__WORKSPACE__", $WorkspacePath).
    Replace("__REPO_PATH__", $repoRootWsl).
    Replace("__MILESTONE__", $Milestone.ToString()).
    Replace("__RUNTIME_TARGET__", $RuntimeTarget).
    Replace("__PERF_PROFILE__", $PerfProfile).
    Replace("__INFERENCE_DEVICE__", $InferenceDevice).
    Replace("__HEADLESS__", $headlessStr).
    Replace("__DISPLAY_ENV__", $displayEnv).
    Replace("__INCLUDE_EXTRACTOR__", $includeExtractor).
    Replace("__INCLUDE_BRIDGE__", $includeBridge).
    Replace("__DISTRO__", $Distro)

Write-Host "Launching milestone demo $Milestone..."
Write-Host "  Runtime target: $RuntimeTarget"
Write-Host "  Perf profile:   $PerfProfile"
Write-Host "  Inference dev:  $InferenceDevice"
Write-Host "  Headless:       $headlessStr"

wsl -d $Distro -- bash -lc $bash

Write-Host ""
if ($Milestone -eq 1) {
    Write-Host "Milestone 1 Checklist:"
    Write-Host "  1. Gazebo is visible (if not headless)."
    Write-Host "  2. YOLO debug output appears on /yolo/debug_image."
    Write-Host "  3. Detection confidence updates on /yolo/confidence."
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
