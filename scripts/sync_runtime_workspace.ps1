param(
    [string]$Distro = "Ubuntu-24.04",

    [string]$WorkspacePath = "~/ros2_ws",

    [string]$RuntimeSourceDir = "chasecar_runtime",

    [switch]$SkipBuild,

    [int]$ParallelWorkers = 0,

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

$rosResolved = Resolve-RosDistro -Distro $Distro -Requested $RosDistro
$repoRootWin = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$repoRootWsl = Convert-ToWslPath -WindowsPath $repoRootWin

$skipBuildStr = if ($SkipBuild) { "true" } else { "false" }

$bashTemplate = @'
set -eo pipefail

WORKSPACE="__WORKSPACE__"
REPO_PATH="__REPO_PATH__"
RUNTIME_SOURCE_DIR="__RUNTIME_SOURCE_DIR__"
SKIP_BUILD="__SKIP_BUILD__"
PARALLEL_WORKERS="__PARALLEL_WORKERS__"
ROS_DISTRO="__ROS_DISTRO__"

if [[ "$WORKSPACE" == "~/"* ]]; then
  WORKSPACE="$HOME/${WORKSPACE:2}"
elif [[ "$WORKSPACE" == "~" ]]; then
  WORKSPACE="$HOME"
fi

RUNTIME_PATH="$WORKSPACE/src/$RUNTIME_SOURCE_DIR"
mkdir -p "$WORKSPACE/src"

if [ ! -d "$REPO_PATH" ]; then
  echo "Repo path not found in WSL: $REPO_PATH" >&2
  exit 1
fi

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude ".git/" \
    --exclude ".tmp/" \
    --exclude ".tmp_manual_runner/" \
    --exclude "artifacts/" \
    --exclude "build/" \
    --exclude "install/" \
    --exclude "log/" \
    --exclude "__pycache__/" \
    --exclude ".venv/" \
    "$REPO_PATH"/ "$RUNTIME_PATH"/
else
  rm -rf "$RUNTIME_PATH"
  mkdir -p "$RUNTIME_PATH"
  cp -a "$REPO_PATH"/. "$RUNTIME_PATH"/
fi

if [ "$SKIP_BUILD" != "true" ]; then
  if [ ! -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    echo "ROS distro setup not found: /opt/ros/$ROS_DISTRO/setup.bash" >&2
    exit 1
  fi

  source "/opt/ros/$ROS_DISTRO/setup.bash"
  cd "$WORKSPACE"

  if [ "$PARALLEL_WORKERS" -gt 0 ]; then
    colcon build \
      --base-paths "$RUNTIME_PATH" \
      --packages-select chasebot_description \
      --parallel-workers "$PARALLEL_WORKERS"
  else
    colcon build \
      --base-paths "$RUNTIME_PATH" \
      --packages-select chasebot_description
  fi
fi

echo "RUNTIME_SOURCE_PATH=$RUNTIME_PATH"
echo "RUNTIME_SYNC_OK=1"
'@

$bash = $bashTemplate.
    Replace("__WORKSPACE__", $WorkspacePath).
    Replace("__REPO_PATH__", $repoRootWsl).
    Replace("__RUNTIME_SOURCE_DIR__", $RuntimeSourceDir).
    Replace("__SKIP_BUILD__", $skipBuildStr).
    Replace("__PARALLEL_WORKERS__", $ParallelWorkers.ToString()).
    Replace("__ROS_DISTRO__", $rosResolved)
$bash = $bash.Replace("`r`n", "`n")

Write-Host "Syncing runtime workspace mirror..."
Write-Host "  Distro:            $Distro"
Write-Host "  Workspace:         $WorkspacePath"
Write-Host "  Runtime source:    $RuntimeSourceDir"
Write-Host "  ROS distro:        $rosResolved"
Write-Host "  Skip build:        $skipBuildStr"
Write-Host "  Parallel workers:  $ParallelWorkers"

$tempScriptWin = Join-Path $env:TEMP ("chasecar_sync_runtime_{0}.sh" -f ([Guid]::NewGuid().ToString("N")))
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
    Write-Error "Runtime workspace sync failed with exit code $exitCode"
}
exit $exitCode

