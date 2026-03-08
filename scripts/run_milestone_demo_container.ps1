param(
    [ValidateSet(1, 2, 3)]
    [int]$Milestone,

    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "workstation_balanced",

    [ValidateSet("compat", "balanced", "max")]
    [string]$PerfProfile,

    [ValidateSet("auto", "cuda:0", "cpu")]
    [string]$InferenceDevice,

    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",

    [object]$Headless = $null,

    [string]$WorldFile = "yolo_test_world_v6_clean_uat.world",

    [string]$WorldName = "yolo_test_world",

    [string]$EvidenceDir = "",

    [string]$SessionId = "",

    [string]$ProjectName = "",

    [int]$MaxRunSeconds = 0,

    [switch]$EnsureDemoTarget = $true,

    [string]$DemoTargetModelSdf = "ros2_config/frisbee_target_ball.sdf",

    [string]$DemoTargetName = "milestone_demo_target",

    [double]$DemoTargetX = 1.10,

    [double]$DemoTargetY = 0.00,

    [double]$DemoTargetZ = 0.05,

    [object]$DemoTargetRelative = $true,

    [double]$DemoTargetForwardM = 1.10,

    [double]$DemoTargetLateralM = 0.00,

    [double]$DemoTargetVerticalOffsetM = 0.05,

    [double]$MinDetectionConfidence = 0.50,

    [object]$OpenFeedViewers = $false,

    [ValidateSet("none", "recorded", "browser_dashboard")]
    [string]$VisualSurface = "none",

    [ValidateSet("streamed_sim", "none", "x11_debug")]
    [string]$WorldSurface = "none",

    [object]$AutoOpenVisualSurface = $false,

    [int]$DashboardPort = 0,

    [int]$PersistentVisualHoldSeconds = 12,

    [object]$KeepWindowsOpen = $false,

    [ValidateSet("none", "vcxsrv", "wslg")]
    [string]$DisplayMode = "none",

    [string]$DisplayAddress = "",

    [string]$DisplayPreflightStatus = "not_required",

    [string]$DisplayPreflightMessage = "",

    [ValidateSet("rqt_image_view", "image_view")]
    [string]$ViewerBackend = "rqt_image_view",

    [int]$ViewerStartupDelaySeconds = 4,

    [int]$ViewerReadyTimeoutSeconds = 12,

    [object]$RequireMotion = $null,

    [double]$MotionMinDistanceMeters = 0.40,

    [int]$MotionWindowSeconds = 90,

    [double]$MotionTargetProgressMinMeters = 0.20,

    [object]$RequireNav2ActionServer = $null,

    [string]$CoreRosDistro = "kilted",

    [int]$StepTimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-NullableBool {
    param(
        [object]$Value,
        [string]$ParamName
    )
    if ($null -eq $Value) { return $null }
    if ($Value -is [bool]) { return [bool]$Value }
    if ($Value -is [int] -or $Value -is [long]) {
        if ([int]$Value -eq 0) { return $false }
        if ([int]$Value -eq 1) { return $true }
    }
    $text = $Value.ToString().Trim().ToLowerInvariant()
    switch ($text) {
        "true" { return $true }
        "false" { return $false }
        "1" { return $true }
        "0" { return $false }
        "yes" { return $true }
        "no" { return $false }
        default { throw "Invalid boolean value '$Value' for parameter '$ParamName'." }
    }
}

function Invoke-PSCapture {
    param([string]$ScriptPath, [string[]]$ScriptArgs)

    $stdout = Join-Path $env:TEMP ("milestone_container_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("milestone_container_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    try {
        $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ScriptPath) + $ScriptArgs
        $proc = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $out = @()
        if (Test-Path -LiteralPath $stdout) { $out += Get-Content -LiteralPath $stdout }
        if (Test-Path -LiteralPath $stderr) { $out += Get-Content -LiteralPath $stderr }
        foreach ($line in $out) { Write-Host $line }
        [pscustomobject]@{
            ExitCode = [int]$proc.ExitCode
            Output = $out
        }
    }
    finally {
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Convert-OrchestratorPath {
    param([string]$Path, [string]$RepoRoot)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    $normalized = [regex]::Replace($Path, '\\\\+', '\')
    if ($normalized -match '^[A-Za-z]:\\') { return $normalized }
    if ($normalized -match '^/mnt/([a-zA-Z])/(.*)$') {
        $drive = $matches[1].ToUpper()
        $rest = $matches[2] -replace '/', '\\'
        return "$drive`:\$rest"
    }
    if ($normalized.StartsWith("/workspaces/chasecar/")) {
        return Join-Path $RepoRoot ($normalized.Substring("/workspaces/chasecar/".Length).Replace('/', '\\'))
    }
    if ($normalized.StartsWith("artifacts/")) {
        return Join-Path $RepoRoot ($normalized.Replace('/', '\\'))
    }
    return $normalized
}

function Get-VisualModeSuffix {
    param([string]$VisualSurface)
    switch ($VisualSurface) {
        "recorded" { return "recorded" }
        "browser_dashboard" { return "browser_dashboard" }
        default { return "" }
    }
}

function Save-ModeSpecificVisualArtifacts {
    param(
        [string]$VisualDir,
        [string]$VisualSurface,
        [string]$RepoRoot,
        [object]$VisualSummary,
        [object]$WorldStreamSummary
    )

    $suffix = Get-VisualModeSuffix -VisualSurface $VisualSurface
    $result = [ordered]@{
        suffix = $suffix
        summary_path = ""
        raw_video = ""
        debug_video = ""
        topdown_video = ""
        world_stream_summary_path = ""
        world_stream_video_path = ""
        world_stream_screenshot_path = ""
    }
    if ([string]::IsNullOrWhiteSpace($suffix)) {
        return [pscustomobject]$result
    }

    if ($VisualSummary) {
        $modeSummaryPath = Join-Path $VisualDir ("visual_demo_summary_{0}.json" -f $suffix)
        ($VisualSummary | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $modeSummaryPath -Encoding UTF8
        $result.summary_path = $modeSummaryPath

        $artifactMap = [ordered]@{
            raw_video = "raw_camera_{0}.mp4"
            debug_video = "yolo_debug_{0}.mp4"
            topdown_video = "topdown_telemetry_{0}.mp4"
        }
        foreach ($propertyName in $artifactMap.Keys) {
            $source = Convert-OrchestratorPath -Path ([string]$VisualSummary.$propertyName) -RepoRoot $RepoRoot
            if (-not [string]::IsNullOrWhiteSpace($source) -and (Test-Path -LiteralPath $source)) {
                $dest = Join-Path $VisualDir ($artifactMap[$propertyName] -f $suffix)
                Copy-Item -LiteralPath $source -Destination $dest -Force
                $result[$propertyName] = $dest
            }
        }
    }

    if ($WorldStreamSummary) {
        $worldSummaryPath = Join-Path $VisualDir ("world_stream_summary_{0}.json" -f $suffix)
        ($WorldStreamSummary | ConvertTo-Json -Depth 12) | Set-Content -LiteralPath $worldSummaryPath -Encoding UTF8
        $result.world_stream_summary_path = $worldSummaryPath

        $worldVideo = Convert-OrchestratorPath -Path ([string]$WorldStreamSummary.video_path) -RepoRoot $RepoRoot
        if (-not [string]::IsNullOrWhiteSpace($worldVideo) -and (Test-Path -LiteralPath $worldVideo)) {
            $dest = Join-Path $VisualDir ("world_stream_{0}.mp4" -f $suffix)
            Copy-Item -LiteralPath $worldVideo -Destination $dest -Force
            $result.world_stream_video_path = $dest
        }

        $worldScreenshot = Convert-OrchestratorPath -Path ([string]$WorldStreamSummary.screenshot_path) -RepoRoot $RepoRoot
        if (-not [string]::IsNullOrWhiteSpace($worldScreenshot) -and (Test-Path -LiteralPath $worldScreenshot)) {
            $dest = Join-Path $VisualDir ("world_stream_{0}.jpg" -f $suffix)
            Copy-Item -LiteralPath $worldScreenshot -Destination $dest -Force
            $result.world_stream_screenshot_path = $dest
        }
    }

    return [pscustomobject]$result
}

function Parse-Marker {
    param([string[]]$Output, [string]$Prefix)
    $line = $Output | Where-Object { $_ -like "$Prefix*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Prefix", "")
}

function Parse-StepMarker {
    param([string[]]$Output, [string]$StepName)
    $line = $Output | Where-Object { $_ -like "STEP_RESULT=${StepName}:*" } | Select-Object -Last 1
    if (-not $line) { return $null }
    if ($line -match '^STEP_RESULT=([^:]+):([^:]+):(.*)$') {
        return [pscustomobject]@{
            Step = $matches[1]
            Status = $matches[2]
            Artifact = $matches[3]
        }
    }
    return $null
}

function Resolve-DockerCli {
    $dockerResolved = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerResolved) {
        return $dockerResolved.Source
    }
    $fallbackDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $fallbackDocker) {
        return $fallbackDocker
    }
    throw "Unable to locate docker CLI."
}

function Get-ContainerServiceId {
    param(
        [string]$DockerCmd,
        [string]$ProjectName,
        [string]$ServiceName
    )
    $raw = & $DockerCmd compose -p $ProjectName --profile gate ps -q $ServiceName 2>$null
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    $first = $raw | Select-Object -First 1
    if (-not $first) { return "" }
    return $first.ToString().Trim()
}

function Invoke-ContainerScript {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$Script
    )
    if ([string]::IsNullOrWhiteSpace($ContainerId)) {
        return [pscustomobject]@{ ExitCode = 1; Output = @("missing_container_id") }
    }
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Script))
    $wrapper = "echo '$encoded' | base64 -d | bash"
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $out = & $DockerCmd exec $ContainerId bash -lc $wrapper 2>&1 | ForEach-Object { $_.ToString() }
    }
    finally {
        $ErrorActionPreference = $previous
    }
    return [pscustomobject]@{
        ExitCode = [int]$LASTEXITCODE
        Output = @($out)
    }
}

function Parse-OutputMarker {
    param(
        [string[]]$Output,
        [string]$Prefix
    )
    $line = $Output | Where-Object { $_ -like "$Prefix*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Prefix", "").Trim()
}

function Start-FeedViewer {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$ViewerId,
        [string]$Topic,
        [string]$Display,
        [string]$RosDistro,
        [string]$ViewerBackend
    )

    $topicEsc = [regex]::Escape($Topic)
    $viewerCommand = switch ($ViewerBackend) {
        "image_view" { "ros2 run image_view image_view --ros-args -r image:=$Topic" }
        default { "ros2 run rqt_image_view rqt_image_view $Topic" }
    }
    $pidFile = "/tmp/chasecar_${ViewerId}.pid"
    $logFile = "/tmp/chasecar_${ViewerId}.log"
    $script = @'
set -euo pipefail
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
pkill -f "rqt_image_view .*__TOPIC_ESC__" 2>/dev/null || true
pkill -f "image_view .*image:=__TOPIC_ESC__" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
export DISPLAY="__DISPLAY__"
export QT_QPA_PLATFORM="xcb"
export QT_X11_NO_MITSHM="1"
export LIBGL_ALWAYS_SOFTWARE="1"
unset LIBGL_ALWAYS_INDIRECT
nohup bash -lc 'source /opt/ros/__ROS_DISTRO__/setup.bash && __VIEWER_COMMAND__' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "VIEWER_START_FAIL=true"
  echo "VIEWER_LOG=__LOG_FILE__"
  tail -n 40 "$LOG_FILE" || true
  exit 7
fi
echo "VIEWER_PID=$(cat "$PID_FILE")"
echo "VIEWER_LOG=__LOG_FILE__"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile).
        Replace("__TOPIC_ESC__", $topicEsc).
        Replace("__DISPLAY__", $Display).
        Replace("__ROS_DISTRO__", $RosDistro).
        Replace("__VIEWER_COMMAND__", $viewerCommand)
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    $viewerPid = Parse-OutputMarker -Output $res.Output -Prefix "VIEWER_PID="
    $log = Parse-OutputMarker -Output $res.Output -Prefix "VIEWER_LOG="
    [pscustomobject]@{
        ExitCode = $res.ExitCode
        Pid = $viewerPid
        Log = $log
        Output = $res.Output
    }
}

function Stop-FeedViewer {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$ViewerId
    )
    $pidFile = "/tmp/chasecar_${ViewerId}.pid"
    $logFile = "/tmp/chasecar_${ViewerId}.log"
    $script = @'
set +e
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
  fi
fi
pkill -f "rqt_image_view" 2>/dev/null || true
pkill -f "image_view" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile)
    $script = $script.Replace("`r`n", "`n")
    Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script | Out-Null
}

function Start-WorldViewer {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$Display,
        [string]$RosDistro
    )
    $pidFile = "/tmp/chasecar_world_viewer.pid"
    $logFile = "/tmp/chasecar_world_viewer.log"
    $script = @'
set -euo pipefail
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
rm -f "$PID_FILE" "$LOG_FILE"
export DISPLAY="__DISPLAY__"
export QT_QPA_PLATFORM="xcb"
export QT_X11_NO_MITSHM="1"
export LIBGL_ALWAYS_SOFTWARE="1"
unset LIBGL_ALWAYS_INDIRECT
GUI_CONFIG="/tmp/chasecar_world_viewer_gui.config"
if [ -f /root/.gz/sim/9/gui.config ]; then
  sed 's#<engine>ogre2</engine>#<engine>ogre</engine>#g' /root/.gz/sim/9/gui.config > "$GUI_CONFIG"
else
  cat > "$GUI_CONFIG" <<'EOF'
<?xml version="1.0"?>
<window>
  <width>1000</width>
  <height>845</height>
</window>
<plugin filename="MinimalScene" name="3D View">
  <gz-gui>
    <title>3D View</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="string" key="state">docked</property>
  </gz-gui>
  <engine>ogre</engine>
  <scene>scene</scene>
  <ambient_light>0.4 0.4 0.4</ambient_light>
  <background_color>0.8 0.8 0.8</background_color>
  <camera_pose>-6 0 6 0 0.5 0</camera_pose>
</plugin>
EOF
fi
nohup bash -lc 'source /opt/ros/__ROS_DISTRO__/setup.bash && gz sim -g --gui-config /tmp/chasecar_world_viewer_gui.config --render-engine-gui ogre' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 2
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "WORLD_VIEWER_START_FAIL=true"
  echo "WORLD_VIEWER_LOG=__LOG_FILE__"
  tail -n 40 "$LOG_FILE" || true
  exit 7
fi
echo "WORLD_VIEWER_PID=$(cat "$PID_FILE")"
echo "WORLD_VIEWER_LOG=__LOG_FILE__"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile).
        Replace("__DISPLAY__", $Display).
        Replace("__ROS_DISTRO__", $RosDistro)
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    $viewerPid = Parse-OutputMarker -Output $res.Output -Prefix "WORLD_VIEWER_PID="
    $log = Parse-OutputMarker -Output $res.Output -Prefix "WORLD_VIEWER_LOG="
    [pscustomobject]@{
        ExitCode = $res.ExitCode
        Pid = $viewerPid
        Log = $log
        Output = $res.Output
    }
}

function Stop-WorldViewer {
    param(
        [string]$DockerCmd,
        [string]$ContainerId
    )
    $pidFile = "/tmp/chasecar_world_viewer.pid"
    $logFile = "/tmp/chasecar_world_viewer.log"
    $script = @'
set +e
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
  fi
fi
pkill -f "gz sim -g" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile)
    $script = $script.Replace("`r`n", "`n")
    Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script | Out-Null
}

function Test-WorldViewerAlive {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$ViewerPid
    )
    if ([string]::IsNullOrWhiteSpace($ViewerPid)) { return $false }
    $script = @"
set +e
kill -0 "$ViewerPid" >/dev/null 2>&1
if [ `$? -eq 0 ]; then
  echo "ALIVE=true"
else
  echo "ALIVE=false"
fi
"@
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    return ((Parse-OutputMarker -Output $res.Output -Prefix "ALIVE=").ToLowerInvariant() -eq "true")
}

function Test-FeedViewerAlive {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$ViewerPid
    )
    if ([string]::IsNullOrWhiteSpace($ViewerPid)) { return $false }
    $script = @"
set +e
kill -0 "$ViewerPid" >/dev/null 2>&1
if [ `$? -eq 0 ]; then
  echo "ALIVE=true"
else
  echo "ALIVE=false"
fi
"@
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    return ((Parse-OutputMarker -Output $res.Output -Prefix "ALIVE=").ToLowerInvariant() -eq "true")
}

function Wait-FeedFrames {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$Topic,
        [int]$TimeoutSeconds,
        [string]$RosDistro
    )

    $timeout = [Math]::Max($TimeoutSeconds, 1)
    $script = @'
set +e
source /opt/ros/__ROS_DISTRO__/setup.bash
count=0
i=1
while [ $i -le __TIMEOUT__ ]; do
  if timeout 2s ros2 topic echo "__TOPIC__" --once --qos-profile sensor_data >/dev/null 2>&1; then
    count=$((count + 1))
    break
  fi
  i=$((i + 1))
  sleep 1
done
echo $count
'@
    $escapedTopic = $Topic.Replace('\', '\\').Replace('"', '\"')
    $script = $script.Replace("__ROS_DISTRO__", $RosDistro).
        Replace("__TIMEOUT__", $timeout.ToString()).
        Replace("__TOPIC__", $escapedTopic)
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    if ($res.ExitCode -ne 0) { return 0 }
    $last = ($res.Output | Select-Object -Last 1)
    if ($null -eq $last) { return 0 }
    $parsed = 0
    if ([int]::TryParse($last.ToString().Trim(), [ref]$parsed)) {
        return $parsed
    }
    return 0
}

function Read-ViewerLogTail {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$LogPath
    )
    if ([string]::IsNullOrWhiteSpace($LogPath)) { return @() }
    $script = @"
set +e
tail -n 40 "$LogPath" 2>/dev/null || true
"@
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    return @($res.Output)
}

function Resolve-PythonExecutable {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    throw "Unable to locate a Python interpreter on Windows host."
}

function Convert-ToWslPath {
    param([string]$WindowsPath)
    $resolved = (Resolve-Path -LiteralPath $WindowsPath).Path
    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $matches[1].ToLowerInvariant()
        $rest = $matches[2] -replace '\\', '/'
        return "/mnt/$drive/$rest"
    }
    return $resolved
}

function Convert-ToContainerRepoPath {
    param(
        [string]$WindowsPath,
        [string]$RepoRoot
    )
    $resolved = (Resolve-Path -LiteralPath $WindowsPath).Path
    $repoResolved = (Resolve-Path -LiteralPath $RepoRoot).Path.TrimEnd('\')
    if ($resolved.StartsWith($repoResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $resolved.Substring($repoResolved.Length).TrimStart('\')
        if ([string]::IsNullOrWhiteSpace($relative)) {
            return "/workspaces/chasecar"
        }
        return "/workspaces/chasecar/" + ($relative -replace '\\', '/')
    }
    return Convert-ToWslPath -WindowsPath $WindowsPath
}

function Test-LocalTcpListen {
    param([int]$Port)
    try {
        $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        if ($listeners -and $listeners.Count -gt 0) { return $true }
    }
    catch {
    }
    $netstat = netstat -ano -p tcp 2>$null
    if ($netstat -and ($netstat | Select-String -Pattern "[:\.]$Port\s+.*LISTENING" -Quiet)) {
        return $true
    }
    return $false
}

function Get-FreeDashboardPort {
    param([int]$RequestedPort)
    if ($RequestedPort -gt 0 -and -not (Test-LocalTcpListen -Port $RequestedPort)) {
        return $RequestedPort
    }
    for ($port = 8860; $port -lt 8890; $port++) {
        if (-not (Test-LocalTcpListen -Port $port)) {
            return $port
        }
    }
    throw "Unable to find a free localhost port for dashboard server."
}

function Get-FreeWorldStreamPort {
    param([int]$RequestedPort)
    if ($RequestedPort -gt 0 -and -not (Test-LocalTcpListen -Port $RequestedPort)) {
        return $RequestedPort
    }
    for ($port = 8891; $port -lt 8921; $port++) {
        if (-not (Test-LocalTcpListen -Port $port)) {
            return $port
        }
    }
    throw "Unable to find a free localhost port for world stream."
}

function Write-DashboardHtml {
    param(
        [string]$RepoRoot,
        [string]$VisualDir
    )
    $template = Join-Path $RepoRoot "runtime/dashboard/browser_dashboard.html"
    if (-not (Test-Path -LiteralPath $template)) {
        throw "Missing dashboard template: $template"
    }
    Copy-Item -LiteralPath $template -Destination (Join-Path $VisualDir "dashboard.html") -Force
}

function Start-DashboardServer {
    param(
        [string]$VisualDir,
        [int]$RequestedPort,
        [bool]$AutoOpen
    )
    $pythonExe = Resolve-PythonExecutable
    $port = Get-FreeDashboardPort -RequestedPort $RequestedPort
    $stdout = Join-Path $VisualDir "dashboard_server_stdout.log"
    $stderr = Join-Path $VisualDir "dashboard_server_stderr.log"

    if ((Split-Path -Leaf $pythonExe).ToLowerInvariant() -eq "py.exe") {
        $args = @("-3", "-m", "http.server", $port.ToString(), "--bind", "127.0.0.1")
    }
    else {
        $args = @("-m", "http.server", $port.ToString(), "--bind", "127.0.0.1")
    }

    $proc = Start-Process -FilePath $pythonExe -ArgumentList $args -WorkingDirectory $VisualDir -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $ready = $false
    for ($i = 0; $i -lt 10; $i++) {
        if (Test-LocalTcpListen -Port $port) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }

    $url = "http://127.0.0.1:$port/dashboard.html"
    if ($ready -and $AutoOpen) {
        Start-Process $url | Out-Null
    }

    return [pscustomobject]@{
        Port = $port
        Url = $url
        Pid = [int]$proc.Id
        Ready = $ready
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Stop-DashboardServer {
    param([object]$ServerInfo)
    if ($null -eq $ServerInfo) { return }
    $dashboardPid = 0
    if ($ServerInfo.PSObject.Properties.Name -contains "Pid") {
        $dashboardPid = [int]$ServerInfo.Pid
    }
    if ($dashboardPid -le 0) { return }
    try {
        Stop-Process -Id $dashboardPid -Force -ErrorAction SilentlyContinue
    }
    catch {
    }
}

function Start-VisualObserver {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$RosDistro,
        [string]$SessionId,
        [string]$OutputDir,
        [string]$RuntimeTarget,
        [string]$VisualMode,
        [int]$DurationSeconds,
        [bool]$RequireMotion,
        [double]$TargetVisibleMinRatio,
        [double]$MotionProgressMinM,
        [string]$TruthStatePath
    )

    $pidFile = "/tmp/chasecar_visual_observer.pid"
    $logFile = "/tmp/chasecar_visual_observer.log"
    $outputDirWsl = Convert-ToContainerRepoPath -WindowsPath $OutputDir -RepoRoot (Join-Path $PSScriptRoot "..")
    $truthStateContainer = ""
    if (-not [string]::IsNullOrWhiteSpace($TruthStatePath) -and (Test-Path -LiteralPath $TruthStatePath)) {
        $truthStateContainer = Convert-ToContainerRepoPath -WindowsPath $TruthStatePath -RepoRoot (Join-Path $PSScriptRoot "..")
    }
    $requireMotionArg = if ($RequireMotion) { "--require-motion" } else { "" }
    $truthArg = if ([string]::IsNullOrWhiteSpace($truthStateContainer)) { "" } else { "--truth-state-path `"$truthStateContainer`"" }
    $script = @'
set -euo pipefail
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
pkill -f "visual_demo_observer.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/__ROS_DISTRO__/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/visual_demo_observer.py --session-id "__SESSION_ID__" --output-dir "__OUTPUT_DIR__" --execution-lane "container_kilted" --runtime-target "__RUNTIME_TARGET__" --visual-mode "__VISUAL_MODE__" --duration-s "__DURATION_S__" --target-visible-min-ratio "__TARGET_VISIBLE_MIN_RATIO__" --motion-progress-min-m "__MOTION_PROGRESS_MIN_M__" __REQUIRE_MOTION__ __TRUTH_STATE_ARG__ --use-sim-time' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "VISUAL_START_FAIL=true"
  echo "VISUAL_LOG=__LOG_FILE__"
  tail -n 40 "$LOG_FILE" || true
  exit 7
fi
echo "VISUAL_PID=$(cat "$PID_FILE")"
echo "VISUAL_LOG=__LOG_FILE__"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile).
        Replace("__ROS_DISTRO__", $RosDistro).
        Replace("__SESSION_ID__", $SessionId).
        Replace("__OUTPUT_DIR__", $outputDirWsl).
        Replace("__RUNTIME_TARGET__", $RuntimeTarget).
        Replace("__VISUAL_MODE__", $VisualMode).
        Replace("__DURATION_S__", ([Math]::Max($DurationSeconds, 30)).ToString()).
        Replace("__TARGET_VISIBLE_MIN_RATIO__", $TargetVisibleMinRatio.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture)).
        Replace("__MOTION_PROGRESS_MIN_M__", $MotionProgressMinM.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture)).
        Replace("__REQUIRE_MOTION__", $requireMotionArg).
        Replace("__TRUTH_STATE_ARG__", $truthArg)
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    [pscustomobject]@{
        ExitCode = $res.ExitCode
        Pid = (Parse-OutputMarker -Output $res.Output -Prefix "VISUAL_PID=")
        Log = (Parse-OutputMarker -Output $res.Output -Prefix "VISUAL_LOG=")
        Output = $res.Output
    }
}

function Stop-VisualObserver {
    param(
        [string]$DockerCmd,
        [string]$ContainerId
    )
    if ([string]::IsNullOrWhiteSpace($ContainerId)) { return }
    $script = @'
set +e
if [ -f /tmp/chasecar_visual_observer.pid ]; then
  PID="$(cat /tmp/chasecar_visual_observer.pid 2>/dev/null || true)"
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    sleep 1
    kill -9 "$PID" 2>/dev/null || true
  fi
fi
pkill -f "visual_demo_observer.py" 2>/dev/null || true
'@
    $script = $script.Replace("`r`n", "`n")
    Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script | Out-Null
}

function Wait-VisualObserverReady {
    param(
        [string]$VisualDir,
        [int]$TimeoutSeconds
    )
    $statePath = Join-Path $VisualDir "state.json"
    $rawPath = Join-Path $VisualDir "live/raw_camera.jpg"
    $debugPath = Join-Path $VisualDir "live/yolo_debug.jpg"
    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        if ((Test-Path -LiteralPath $statePath) -and (Test-Path -LiteralPath $rawPath) -and (Test-Path -LiteralPath $debugPath)) {
            try {
                $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
                $rawFrames = [int]$state.raw_frame_count
                $debugFrames = [int]$state.debug_frame_count
                if ($rawFrames -ge 1 -and $debugFrames -ge 1) {
                    return [pscustomobject]@{
                        Ready = $true
                        State = $state
                        StatePath = $statePath
                    }
                }
            }
            catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return [pscustomobject]@{
        Ready = $false
        State = $null
        StatePath = $statePath
    }
}

function Wait-VisualObserverSummary {
    param(
        [string]$VisualDir,
        [int]$TimeoutSeconds
    )
    $summaryPath = Join-Path $VisualDir "visual_demo_summary.json"
    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $summaryPath) {
            try {
                $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
                return [pscustomobject]@{
                    Ready = $true
                    Summary = $summary
                    SummaryPath = $summaryPath
                }
            }
            catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return [pscustomobject]@{
        Ready = $false
        Summary = $null
        SummaryPath = $summaryPath
    }
}

function Start-TruthProbe {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$SessionId,
        [string]$OutputDir,
        [string]$WorldName,
        [string]$TargetModelNames
    )
    $pidFile = "/tmp/chasecar_truth_probe.pid"
    $logFile = "/tmp/chasecar_truth_probe.log"
    $outputDirContainer = Convert-ToContainerRepoPath -WindowsPath $OutputDir -RepoRoot (Join-Path $PSScriptRoot "..")
    $script = @'
set -euo pipefail
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
pkill -f "sim_truth_probe.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/__ROS_DISTRO__/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/sim_truth_probe.py --session-id "__SESSION_ID__" --output-dir "__OUTPUT_DIR__" --world-name "__WORLD_NAME__" --target-model-names "__TARGET_MODEL_NAMES__" --duration-s 240' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "TRUTH_START_FAIL=true"
  echo "TRUTH_LOG=__LOG_FILE__"
  tail -n 40 "$LOG_FILE" || true
  exit 7
fi
echo "TRUTH_PID=$(cat "$PID_FILE")"
echo "TRUTH_LOG=__LOG_FILE__"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile).
        Replace("__ROS_DISTRO__", $CoreRosDistro).
        Replace("__SESSION_ID__", $SessionId).
        Replace("__OUTPUT_DIR__", $outputDirContainer).
        Replace("__WORLD_NAME__", $WorldName).
        Replace("__TARGET_MODEL_NAMES__", $TargetModelNames)
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    [pscustomobject]@{
        ExitCode = $res.ExitCode
        Pid = (Parse-OutputMarker -Output $res.Output -Prefix "TRUTH_PID=")
        Log = (Parse-OutputMarker -Output $res.Output -Prefix "TRUTH_LOG=")
        Output = $res.Output
    }
}

function Stop-TruthProbe {
    param(
        [string]$DockerCmd,
        [string]$ContainerId
    )
    if ([string]::IsNullOrWhiteSpace($ContainerId)) { return }
    $script = @'
set +e
if [ -f /tmp/chasecar_truth_probe.pid ]; then
  PID="$(cat /tmp/chasecar_truth_probe.pid 2>/dev/null || true)"
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    for i in $(seq 1 10); do
      if ! kill -0 "$PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    kill -9 "$PID" 2>/dev/null || true
  fi
fi
pkill -f "sim_truth_probe.py" 2>/dev/null || true
'@
    $script = $script.Replace("`r`n", "`n")
    Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script | Out-Null
}

function Wait-TruthProbeReady {
    param(
        [string]$VisualDir,
        [int]$TimeoutSeconds
    )
    $statePath = Join-Path $VisualDir "truth_state.json"
    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $statePath) {
            try {
                $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
                if ($state.true_target_seen -and $state.robot_truth_seen) {
                    return [pscustomobject]@{
                        Ready = $true
                        State = $state
                        StatePath = $statePath
                    }
                }
            }
            catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return [pscustomobject]@{
        Ready = $false
        State = $null
        StatePath = $statePath
    }
}

function Wait-TruthSummary {
    param(
        [string]$VisualDir,
        [int]$TimeoutSeconds
    )
    $summaryPath = Join-Path $VisualDir "truth_summary.json"
    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $summaryPath) {
            try {
                $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
                return [pscustomobject]@{
                    Ready = $true
                    Summary = $summary
                    SummaryPath = $summaryPath
                }
            }
            catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return [pscustomobject]@{
        Ready = $false
        Summary = $null
        SummaryPath = $summaryPath
    }
}

function Start-WorldStream {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$SessionId,
        [string]$OutputDir,
        [int]$PublicPort
    )
    $pidFile = "/tmp/chasecar_world_stream.pid"
    $logFile = "/tmp/chasecar_world_stream.log"
    $outputDirContainer = Convert-ToContainerRepoPath -WindowsPath $OutputDir -RepoRoot (Join-Path $PSScriptRoot "..")
    $publicUrl = "http://127.0.0.1:$PublicPort/vnc.html?autoconnect=1&resize=scale&path=websockify"
    $script = @'
set -euo pipefail
PID_FILE="__PID_FILE__"
LOG_FILE="__LOG_FILE__"
pkill -f "world_stream_controller.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/__ROS_DISTRO__/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/world_stream_controller.py --session-id "__SESSION_ID__" --output-dir "__OUTPUT_DIR__" --public-url "__PUBLIC_URL__" --duration-s 240' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "WORLD_STREAM_START_FAIL=true"
  echo "WORLD_STREAM_LOG=__LOG_FILE__"
  tail -n 40 "$LOG_FILE" || true
  exit 7
fi
echo "WORLD_STREAM_PID=$(cat "$PID_FILE")"
echo "WORLD_STREAM_LOG=__LOG_FILE__"
'@
    $script = $script.Replace("__PID_FILE__", $pidFile).
        Replace("__LOG_FILE__", $logFile).
        Replace("__ROS_DISTRO__", $CoreRosDistro).
        Replace("__SESSION_ID__", $SessionId).
        Replace("__OUTPUT_DIR__", $outputDirContainer).
        Replace("__PUBLIC_URL__", $publicUrl)
    $script = $script.Replace("`r`n", "`n")
    $res = Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script
    [pscustomobject]@{
        ExitCode = $res.ExitCode
        Pid = (Parse-OutputMarker -Output $res.Output -Prefix "WORLD_STREAM_PID=")
        Log = (Parse-OutputMarker -Output $res.Output -Prefix "WORLD_STREAM_LOG=")
        Output = $res.Output
        Url = $publicUrl
    }
}

function Stop-WorldStream {
    param(
        [string]$DockerCmd,
        [string]$ContainerId
    )
    if ([string]::IsNullOrWhiteSpace($ContainerId)) { return }
    $script = @'
set +e
if [ -f /tmp/chasecar_world_stream.pid ]; then
  PID="$(cat /tmp/chasecar_world_stream.pid 2>/dev/null || true)"
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    for i in $(seq 1 12); do
      if ! kill -0 "$PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    kill -9 "$PID" 2>/dev/null || true
  fi
fi
pkill -f "world_stream_controller.py" 2>/dev/null || true
pkill -f "websockify .* 6080" 2>/dev/null || true
pkill -f "x11vnc .*5900" 2>/dev/null || true
pkill -f "Xvfb :99" 2>/dev/null || true
pkill -f "fluxbox" 2>/dev/null || true
pkill -f "gz sim -g" 2>/dev/null || true
'@
    $script = $script.Replace("`r`n", "`n")
    Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script | Out-Null
}

function Wait-WorldStreamReady {
    param(
        [string]$VisualDir,
        [int]$TimeoutSeconds
    )
    $statePath = Join-Path $VisualDir "world_stream_state.json"
    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $statePath) {
            try {
                $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
                if ($state.world_stream_ready -and $state.world_stream_nonblank -and $state.world_stream_interactive) {
                    return [pscustomobject]@{
                        Ready = $true
                        State = $state
                        StatePath = $statePath
                    }
                }
            }
            catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return [pscustomobject]@{
        Ready = $false
        State = $null
        StatePath = $statePath
    }
}

function Wait-WorldStreamSummary {
    param(
        [string]$VisualDir,
        [int]$TimeoutSeconds
    )
    $summaryPath = Join-Path $VisualDir "world_stream_summary.json"
    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $summaryPath) {
            try {
                $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
                return [pscustomobject]@{
                    Ready = $true
                    Summary = $summary
                    SummaryPath = $summaryPath
                }
            }
            catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return [pscustomobject]@{
        Ready = $false
        Summary = $null
        SummaryPath = $summaryPath
    }
}

function Invoke-SpawnModel {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$WorldName,
        [string]$ModelName,
        [string]$ModelSdfWindowsPath,
        [double]$X,
        [double]$Y,
        [double]$Z
    )
    $modelPath = Convert-ToContainerRepoPath -WindowsPath $ModelSdfWindowsPath -RepoRoot (Join-Path $PSScriptRoot "..")
    $script = @'
set +e
source /opt/ros/__ROS_DISTRO__/setup.bash
ros2 run ros_gz_sim create -world "__WORLD__" -file "__MODEL_PATH__" -name "__MODEL_NAME__" -x "__X__" -y "__Y__" -z "__Z__"
'@
    $script = $script.Replace("__ROS_DISTRO__", $CoreRosDistro).
        Replace("__WORLD__", $WorldName).
        Replace("__MODEL_PATH__", $modelPath).
        Replace("__MODEL_NAME__", $ModelName).
        Replace("__X__", $X.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
        Replace("__Y__", $Y.ToString([System.Globalization.CultureInfo]::InvariantCulture)).
        Replace("__Z__", $Z.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    $script = $script.Replace("`r`n", "`n")
    return (Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script)
}

function Invoke-RemoveModel {
    param(
        [string]$DockerCmd,
        [string]$ContainerId,
        [string]$WorldName,
        [string]$ModelName
    )
    $script = @'
set +e
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/__WORLD__/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \"__MODEL_NAME__\" type: 2" >/dev/null 2>&1 || true
fi
'@
    $script = $script.Replace("__WORLD__", $WorldName).Replace("__MODEL_NAME__", $ModelName)
    $script = $script.Replace("`r`n", "`n")
    Invoke-ContainerScript -DockerCmd $DockerCmd -ContainerId $ContainerId -Script $script | Out-Null
}

$runtimeAliases = @{
    robot_fidelity = "robot_fidelity_orin"
}
if ($runtimeAliases.ContainsKey($RuntimeTarget)) {
    $RuntimeTarget = $runtimeAliases[$RuntimeTarget]
}

$DemoTargetRelative = Resolve-NullableBool -Value $DemoTargetRelative -ParamName "DemoTargetRelative"
$OpenFeedViewers = Resolve-NullableBool -Value $OpenFeedViewers -ParamName "OpenFeedViewers"
$AutoOpenVisualSurface = Resolve-NullableBool -Value $AutoOpenVisualSurface -ParamName "AutoOpenVisualSurface"
$KeepWindowsOpen = Resolve-NullableBool -Value $KeepWindowsOpen -ParamName "KeepWindowsOpen"
$Headless = Resolve-NullableBool -Value $Headless -ParamName "Headless"
$RequireMotion = Resolve-NullableBool -Value $RequireMotion -ParamName "RequireMotion"
$RequireNav2ActionServer = Resolve-NullableBool -Value $RequireNav2ActionServer -ParamName "RequireNav2ActionServer"

$defaults = @{
    robot_fidelity_orin = @{ PerfProfile = "compat"; InferenceDevice = "cuda:0" }
    workstation_balanced = @{ PerfProfile = "balanced"; InferenceDevice = "auto" }
    workstation_max = @{ PerfProfile = "max"; InferenceDevice = "cuda:0" }
}

if (-not $PSBoundParameters.ContainsKey("PerfProfile")) { $PerfProfile = $defaults[$RuntimeTarget].PerfProfile }
if (-not $PSBoundParameters.ContainsKey("InferenceDevice")) { $InferenceDevice = $defaults[$RuntimeTarget].InferenceDevice }
if ($Headless -eq $null) { $Headless = $true }
if ($OpenFeedViewers -eq $null) { $OpenFeedViewers = $false }
if ($AutoOpenVisualSurface -eq $null) { $AutoOpenVisualSurface = $false }
if ($KeepWindowsOpen -eq $null) { $KeepWindowsOpen = $false }
if ($RequireMotion -eq $null) { $RequireMotion = ($Milestone -ge 3) }
if ($RequireNav2ActionServer -eq $null) { $RequireNav2ActionServer = ($Milestone -ge 3) }
if ($DemoTargetRelative -eq $null) { $DemoTargetRelative = $false }
if ([string]::IsNullOrWhiteSpace($DisplayPreflightStatus)) { $DisplayPreflightStatus = "not_required" }
if ([string]::IsNullOrWhiteSpace($DisplayMode)) { $DisplayMode = "none" }
if ([string]::IsNullOrWhiteSpace($VisualSurface)) { $VisualSurface = "none" }
if ([string]::IsNullOrWhiteSpace($WorldSurface)) { $WorldSurface = if ($VisualSurface -ne "none") { "streamed_sim" } else { "none" } }
if ($DisplayAddress -match '^:(\d+)(\.\d+)?$') {
    $DisplayAddress = "host.docker.internal$DisplayAddress"
}

$feedViewersRunning = $false
$feedViewerStatus = if ([bool]$OpenFeedViewers) { "pending" } else { "skipped" }
$feedViewersGatePass = (-not [bool]$OpenFeedViewers)
$feedViewerStartupElapsedS = 0.0
$feedViewerFrameCounts = [ordered]@{ rgb = 0; yolo_debug = 0 }
$feedRgbViewerPid = ""
$feedDebugViewerPid = ""
$worldViewerRunning = $false
$worldViewerStatus = if ([bool]$OpenFeedViewers) { "pending" } else { "skipped" }
$worldViewerPid = ""
$worldViewerLog = ""
$worldStreamReady = ($WorldSurface -eq "none")
$worldStreamStatus = if ($WorldSurface -eq "none") { "skipped" } else { "pending" }
$worldStreamUrl = ""
$worldStreamPort = 0
$worldStreamStatePath = ""
$worldStreamSummaryPath = ""
$worldStreamNonblank = $false
$worldStreamInteractive = $false
$worldStreamSameSessionPartition = ($WorldSurface -ne "streamed_sim")
$worldStreamContainerId = ""
$worldStreamPid = ""
$worldStreamLog = ""
$truthStatePath = ""
$truthSummaryPath = ""
$truthReady = $false
$truthStatus = if ($VisualSurface -ne "none") { "pending" } else { "skipped" }
$truthProbePid = ""
$truthProbeLog = ""
$containerGateStackId = ""
$containerSimGateId = ""
$dockerCmd = ""
$displayPreflightOk = (($DisplayPreflightStatus -eq "ok") -or ($DisplayPreflightStatus -eq "not_required"))
$visualSurfaceRequested = ($VisualSurface -ne "none")
$visualReady = (-not $visualSurfaceRequested)
$visualStatus = if ($visualSurfaceRequested) { "pending" } else { "skipped" }
$visualGatePass = (-not $visualSurfaceRequested)
$visualObserverPid = ""
$visualObserverLog = ""
$visualStatePath = ""
$visualSummaryPath = ""
$dashboardInfo = $null

$runId = if ([string]::IsNullOrWhiteSpace($SessionId)) { (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") } else { $SessionId }
if ($runId -notmatch '^\d{8}T\d{6}Z$') {
    throw "SessionId must match YYYYMMDDTHHMMSSZ."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactDir = if (-not [string]::IsNullOrWhiteSpace($EvidenceDir)) {
    if ([System.IO.Path]::IsPathRooted($EvidenceDir)) { $EvidenceDir } else { Join-Path $repoRoot $EvidenceDir }
} elseif (-not [string]::IsNullOrWhiteSpace($SessionId)) {
    Join-Path $repoRoot "artifacts/session/$runId/gui_rehearsal/milestone_$Milestone"
} else {
    Join-Path $repoRoot "artifacts/demos/milestone_${Milestone}_$runId"
}
New-Item -ItemType Directory -Path (Join-Path $artifactDir "logs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $artifactDir "screenshots") -Force | Out-Null
$sessionVisualDir = if (-not [string]::IsNullOrWhiteSpace($SessionId)) {
    Join-Path $repoRoot "artifacts/session/$runId/visual"
} else {
    Join-Path $artifactDir "visual"
}
New-Item -ItemType Directory -Path $sessionVisualDir -Force | Out-Null

$resolvedProjectName = if ([string]::IsNullOrWhiteSpace($ProjectName)) { "chasecar_gate_mdemo_$($runId.ToLowerInvariant())" } else { $ProjectName }
$composeGateScript = Join-Path $PSScriptRoot "run_compose_gate.ps1"
$composeUatScript = Join-Path $PSScriptRoot "run_compose_uat.ps1"

$originalGazeboPartition = $env:GAZEBO_PARTITION
$originalWorldStreamPort = $env:WORLD_STREAM_PORT

$includeNav2 = ($Milestone -ge 3)
$includeBridge = $false
$includeRelay = ($Milestone -ge 3)
$gateHeadless = $Headless
if ($WorldSurface -eq "streamed_sim") {
    $gateHeadless = $true
}

$snapshotTargetX = $DemoTargetX
$snapshotTargetY = $DemoTargetY
$snapshotTargetZ = $DemoTargetZ
$targetResolveStatus = if ($DemoTargetRelative) { "relative_target_fallback_static" } else { "static_config" }

$envBackupKeys = @(
    "CHASECAR_NAV2_TARGET_X","CHASECAR_NAV2_TARGET_Y","CHASECAR_NAV2_TARGET_Z","CHASECAR_NAV2_WORLD_NAME",
    "CHASECAR_NAV2_MODEL_SDF","CHASECAR_NAV2_MODEL_NAME","CHASECAR_SNAPSHOT_TARGET_X","CHASECAR_SNAPSHOT_TARGET_Y",
    "CHASECAR_SNAPSHOT_TARGET_Z","CHASECAR_SNAPSHOT_WORLD_NAME","CHASECAR_SNAPSHOT_MODEL_SDF","CHASECAR_SNAPSHOT_MODEL_NAME"
)
$envBackup = @{}
foreach ($k in $envBackupKeys) {
    $item = Get-Item -Path "Env:$k" -ErrorAction SilentlyContinue
    $envBackup[$k] = if ($null -eq $item) { $null } else { $item.Value }
}

$env:CHASECAR_NAV2_TARGET_X = $snapshotTargetX.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_NAV2_TARGET_Y = $snapshotTargetY.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_NAV2_TARGET_Z = $snapshotTargetZ.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_NAV2_WORLD_NAME = $WorldName
$env:CHASECAR_NAV2_MODEL_SDF = $DemoTargetModelSdf
$env:CHASECAR_NAV2_MODEL_NAME = $DemoTargetName
$env:CHASECAR_SNAPSHOT_TARGET_X = $snapshotTargetX.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_SNAPSHOT_TARGET_Y = $snapshotTargetY.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_SNAPSHOT_TARGET_Z = $snapshotTargetZ.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_SNAPSHOT_WORLD_NAME = $WorldName
$env:CHASECAR_SNAPSHOT_MODEL_SDF = $DemoTargetModelSdf
$env:CHASECAR_SNAPSHOT_MODEL_NAME = "${DemoTargetName}_snapshot"
$env:GAZEBO_PARTITION = $runId
if ($WorldSurface -eq "streamed_sim") {
    $worldStreamPort = Get-FreeWorldStreamPort -RequestedPort 0
    $env:WORLD_STREAM_PORT = $worldStreamPort.ToString()
}

$stageRuns = @()
$overallPass = $false
$demoFailureClass = ""
$runStartUtc = (Get-Date).ToUniversalTime()

try {
    $dockerCmd = Resolve-DockerCli
    Invoke-PSCapture -ScriptPath $composeGateScript -ScriptArgs @("-Action","down","-ProjectName",$resolvedProjectName,"-RuntimeTarget",$RuntimeTarget,"-InferenceBackend",$InferenceBackend,"-CoreRosDistro",$CoreRosDistro) | Out-Null
    Invoke-PSCapture -ScriptPath $composeUatScript -ScriptArgs @("-Action","down","-ProjectName",$resolvedProjectName,"-RuntimeTarget",$RuntimeTarget,"-InferenceBackend",$InferenceBackend,"-CoreRosDistro",$CoreRosDistro) | Out-Null

    $upArgs = @(
        "-Action","up","-ProjectName",$resolvedProjectName,
        "-RuntimeTarget",$RuntimeTarget,
        "-InferenceBackend",$InferenceBackend,
        "-CoreRosDistro",$CoreRosDistro,
        "-GatePerfProfile",$PerfProfile,
        "-InferenceDevice",$InferenceDevice,
        "-WorldFile",$WorldFile,
        "-IncludeNav2Bringup",($(if($includeNav2){"true"}else{"false"})),
        "-IncludeBridge","false",
        "-IncludeCmdVelRelay",($(if($includeRelay){"true"}else{"false"})),
        "-Headless",($(if($gateHeadless){"true"}else{"false"})),
        "-DisplayMode",$DisplayMode,
        "-QtQpaPlatform","xcb",
        "-QtX11NoMitShm","1",
        "-LibglAlwaysIndirect","1"
    )
    if ($WorldSurface -eq "streamed_sim") {
        $upArgs += "-Build"
    }
    if (-not [string]::IsNullOrWhiteSpace($DisplayAddress)) {
        $upArgs += @("-DisplayAddress", $DisplayAddress)
    }
    $up = Invoke-PSCapture -ScriptPath $composeGateScript -ScriptArgs $upArgs
    if ($up.ExitCode -ne 0) { throw "Gate bring-up failed for project '$resolvedProjectName'." }

    $containerSimGateId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "sim-gate"
    $containerGateStackId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "gate-stack"
    $worldStreamContainerId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "world-viewer"

    if ($visualSurfaceRequested) {
        if ([string]::IsNullOrWhiteSpace($containerGateStackId) -or [string]::IsNullOrWhiteSpace($containerSimGateId)) {
            $visualStatus = "visual_container_unavailable"
            $visualGatePass = $false
            $visualReady = $false
        }
        else {
            Write-DashboardHtml -RepoRoot $repoRoot -VisualDir $sessionVisualDir
            $truthProbe = Start-TruthProbe `
                -DockerCmd $dockerCmd `
                -ContainerId $containerSimGateId `
                -SessionId $runId `
                -OutputDir $sessionVisualDir `
                -WorldName $WorldName `
                -TargetModelNames ($DemoTargetName + "," + $DemoTargetName + "_viewer," + $DemoTargetName + "_snapshot,uat_nav2_target")
            $truthProbePid = [string]$truthProbe.Pid
            $truthProbeLog = [string]$truthProbe.Log
            if ($truthProbe.ExitCode -ne 0) {
                $truthStatus = "truth_probe_failed"
            }
            else {
                $truthWait = Wait-TruthProbeReady -VisualDir $sessionVisualDir -TimeoutSeconds 15
                $truthStatePath = [string]$truthWait.StatePath
                $truthReady = [bool]$truthWait.Ready
                $truthStatus = if ($truthReady) { "truth_ready" } else { "truth_timeout" }
                $truthSummaryPath = Join-Path $sessionVisualDir "truth_summary.json"
            }

            if ($WorldSurface -eq "streamed_sim") {
                if ([string]::IsNullOrWhiteSpace($worldStreamContainerId)) {
                    $worldStreamStatus = "world_stream_container_unavailable"
                }
                else {
                    $stream = Start-WorldStream `
                        -DockerCmd $dockerCmd `
                        -ContainerId $worldStreamContainerId `
                        -SessionId $runId `
                        -OutputDir $sessionVisualDir `
                        -PublicPort $worldStreamPort
                    $worldStreamPid = [string]$stream.Pid
                    $worldStreamLog = [string]$stream.Log
                    $worldStreamUrl = [string]$stream.Url
                    if ($stream.ExitCode -ne 0) {
                        $worldStreamStatus = "world_stream_start_failed"
                    }
                    else {
                        $worldWait = Wait-WorldStreamReady -VisualDir $sessionVisualDir -TimeoutSeconds 35
                        $worldStreamStatePath = [string]$worldWait.StatePath
                        $worldStreamReady = [bool]$worldWait.Ready
                        $worldStreamStatus = if ($worldStreamReady) { "world_stream_ready" } else { "world_stream_timeout" }
                        if ($worldWait.State) {
                            $worldStreamNonblank = [bool]$worldWait.State.world_stream_nonblank
                            $worldStreamInteractive = [bool]$worldWait.State.world_stream_interactive
                            $worldStreamSameSessionPartition = [bool]$worldWait.State.same_session_partition
                        }
                        $worldStreamSummaryPath = Join-Path $sessionVisualDir "world_stream_summary.json"
                    }
                }
            }

            $observerDuration = if ($MaxRunSeconds -gt 0) { [Math]::Max($MaxRunSeconds + 90, 120) } else { 180 }
            $observer = Start-VisualObserver `
                -DockerCmd $dockerCmd `
                -ContainerId $containerGateStackId `
                -RosDistro $CoreRosDistro `
                -SessionId $runId `
                -OutputDir $sessionVisualDir `
                -RuntimeTarget $RuntimeTarget `
                -VisualMode $VisualSurface `
                -DurationSeconds $observerDuration `
                -RequireMotion ([bool]$RequireMotion) `
                -TargetVisibleMinRatio $(if ($Milestone -ge 3) { 0.04 } elseif ($Milestone -eq 2) { 0.10 } else { 0.05 }) `
                -MotionProgressMinM $MotionTargetProgressMinMeters `
                -TruthStatePath $truthStatePath
            $visualObserverPid = [string]$observer.Pid
            $visualObserverLog = [string]$observer.Log

            if ($observer.ExitCode -ne 0) {
                $visualStatus = "visual_observer_failed"
                $visualGatePass = $false
                $visualReady = $false
            }
            else {
                $visualWait = Wait-VisualObserverReady -VisualDir $sessionVisualDir -TimeoutSeconds ([Math]::Max($ViewerReadyTimeoutSeconds, 10))
                $visualStatePath = [string]$visualWait.StatePath
                $visualReady = [bool]$visualWait.Ready
                $visualGatePass = [bool]$visualWait.Ready
                $visualStatus = if ($visualReady) { "visual_ready" } else { "visual_timeout" }
            }

            if ($VisualSurface -eq "browser_dashboard") {
                $dashboardInfo = Start-DashboardServer -VisualDir $sessionVisualDir -RequestedPort $DashboardPort -AutoOpen ([bool]$AutoOpenVisualSurface)
                if (-not [bool]$dashboardInfo.Ready) {
                    $visualReady = $false
                    $visualGatePass = $false
                    $visualStatus = "dashboard_server_unavailable"
                }
            }
            if (-not $truthReady) {
                $visualReady = $false
                $visualGatePass = $false
                $visualStatus = $truthStatus
            }
            if ($WorldSurface -eq "streamed_sim" -and -not $worldStreamReady) {
                $visualReady = $false
                $visualGatePass = $false
                $visualStatus = $worldStreamStatus
            }
        }
    }

    $stageTimeout = [Math]::Max($StepTimeoutSeconds, 120)
    if ($MaxRunSeconds -gt 0) {
        $stageTimeout = [Math]::Min($stageTimeout, [Math]::Max($MaxRunSeconds + 60, 120))
    }
    $nav2Duration = if ($MaxRunSeconds -gt 0) { [Math]::Max([Math]::Min($MaxRunSeconds - 30, 180), 60) } else { 120 }
    $snapshotCaptureTimeout = if ([bool]$OpenFeedViewers) { 20 } else { 12 }
    $nav2Config = if ($RuntimeTarget -eq "robot_fidelity_orin") { "ros2_config/config/nav2_readiness_fidelity.yaml" } else { "ros2_config/config/nav2_readiness_fast.yaml" }
    Write-Host ("UAT stage timeout budget: {0}s (max_run={1}s)" -f $stageTimeout, $MaxRunSeconds)

    function Invoke-UatStage {
        param(
            [string]$Mode,
            [string]$ProjectName,
            [string]$RuntimeTarget,
            [string]$InferenceBackend,
            [string]$CoreRosDistro,
            [int]$StageTimeout,
            [int]$SnapshotTimeout,
            [int]$Nav2Duration,
            [string]$Nav2Config,
            [string]$Profile,
            [string]$InferenceDevice
        )

        $args = @(
            "-Action","run","-ProjectName",$ProjectName,
            "-RuntimeTarget",$RuntimeTarget,
            "-InferenceBackend",$InferenceBackend,
            "-CoreRosDistro",$CoreRosDistro,
            "-UatMode",$Mode,
            "-UatExecutionContext","sim_gate",
            "-StepTimeoutSeconds",$StageTimeout.ToString(),
            "-SnapshotTimeoutSeconds",$SnapshotTimeout.ToString(),
            "-UatProfile",$Profile,
            "-UatInferenceDevice",$InferenceDevice
        )
        if ($Mode -eq "nav2") { $args += @("-Nav2DurationSeconds",$Nav2Duration.ToString(),"-Nav2Config",$Nav2Config) }
        $run = Invoke-PSCapture -ScriptPath $composeUatScript -ScriptArgs $args
        $stage = Parse-StepMarker -Output $run.Output -StepName $Mode
        $artifactDir = if ($stage) { Convert-OrchestratorPath -Path $stage.Artifact -RepoRoot $repoRoot } else { Convert-OrchestratorPath -Path (Parse-Marker -Output $run.Output -Prefix "ARTIFACT_DIR=") -RepoRoot $repoRoot }
        $readiness = Convert-OrchestratorPath -Path (Parse-Marker -Output $run.Output -Prefix "READINESS_REPORT=") -RepoRoot $repoRoot
        [pscustomobject]@{ mode=$Mode; exit_code=$run.ExitCode; marker=$stage; artifact_dir=$artifactDir; readiness_report=$readiness; output=$run.Output; status=$(if($stage){$stage.Status}else{""}); pass=($run.ExitCode -eq 0 -and $stage -and $stage.Status -eq "pass") }
    }

    # In operator hold-open mode, start viewers immediately after stack bring-up so
    # the user can observe the run while UAT stages are executing.
    if ([bool]$OpenFeedViewers -and [bool]$KeepWindowsOpen -and -not $visualSurfaceRequested) {
        Write-Host "VIEWER_LAUNCH_PHASE=pre_uat"
        if (-not $displayPreflightOk) {
            $feedViewerStatus = if ([string]::IsNullOrWhiteSpace($DisplayPreflightStatus)) { "display_preflight_failed" } else { $DisplayPreflightStatus }
            $worldViewerStatus = $feedViewerStatus
            $feedViewersRunning = $false
            $worldViewerRunning = $false
            $feedViewersGatePass = $false
        }
        else {
            $containerSimGateId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "sim-gate"
            $containerGateStackId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "gate-stack"
            if ([string]::IsNullOrWhiteSpace($containerSimGateId) -or [string]::IsNullOrWhiteSpace($containerGateStackId)) {
                $feedViewerStatus = "viewer_container_unavailable"
                $worldViewerStatus = "world_viewer_unavailable"
                $feedViewersRunning = $false
                $worldViewerRunning = $false
                $feedViewersGatePass = $false
            }
            else {
                if (-not [bool]$gateHeadless) {
                    $worldViewerRunning = $true
                    $worldViewerStatus = "integrated_sim_gui"
                }
                else {
                    $worldViewer = Start-WorldViewer -DockerCmd $dockerCmd -ContainerId $containerSimGateId -Display $DisplayAddress -RosDistro $CoreRosDistro
                    $worldViewerPid = [string]$worldViewer.Pid
                    $worldViewerLog = [string]$worldViewer.Log
                    $worldAlive = $false
                    for ($tick = 0; $tick -lt [Math]::Max($ViewerReadyTimeoutSeconds, 1); $tick++) {
                        $worldAlive = Test-WorldViewerAlive -DockerCmd $dockerCmd -ContainerId $containerSimGateId -ViewerPid $worldViewerPid
                        if ($worldAlive) { break }
                        Start-Sleep -Seconds 1
                    }
                    if ($worldAlive) {
                        $worldViewerRunning = $true
                        $worldViewerStatus = "viewer_ready"
                    }
                    else {
                        $worldViewerRunning = $false
                        $worldViewerStatus = "world_viewer_unavailable"
                    }
                }

                $viewerPackage = if ($ViewerBackend -eq "image_view") { "image_view" } else { "rqt_image_view" }
                $backendCheck = Invoke-ContainerScript -DockerCmd $dockerCmd -ContainerId $containerGateStackId -Script ("source /opt/ros/$CoreRosDistro/setup.bash && ros2 pkg executables $viewerPackage 2>/dev/null | grep -q '^$viewerPackage '")
                if ($backendCheck.ExitCode -ne 0) {
                    $feedViewerStatus = "viewer_backend_missing"
                    $feedViewersRunning = $false
                    $feedViewersGatePass = $false
                }
                else {
                    $viewerStart = Get-Date
                    $rgbViewer = Start-FeedViewer -DockerCmd $dockerCmd -ContainerId $containerGateStackId -Display $DisplayAddress -Topic "/d415/color/image_raw" -ViewerId "viewer_rgb" -RosDistro $CoreRosDistro -ViewerBackend $ViewerBackend
                    $dbgViewer = Start-FeedViewer -DockerCmd $dockerCmd -ContainerId $containerGateStackId -Display $DisplayAddress -Topic "/yolo/debug_image" -ViewerId "viewer_debug" -RosDistro $CoreRosDistro -ViewerBackend $ViewerBackend
                    $feedRgbViewerPid = [string]$rgbViewer.Pid
                    $feedDebugViewerPid = [string]$dbgViewer.Pid
                    Start-Sleep -Seconds ([Math]::Max($ViewerStartupDelaySeconds, 1))

                    $rgbAlive = Test-FeedViewerAlive -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerPid $feedRgbViewerPid
                    $dbgAlive = Test-FeedViewerAlive -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerPid $feedDebugViewerPid
                    $feedViewersRunning = ($rgbAlive -and $dbgAlive)
                    if (-not $feedViewersRunning) {
                        $feedViewerStatus = "feed_viewer_unavailable"
                        $feedViewersGatePass = $false
                    }
                    else {
                        $rgbFrames = Wait-FeedFrames -DockerCmd $dockerCmd -ContainerId $containerGateStackId -Topic "/d415/color/image_raw" -TimeoutSeconds ([Math]::Max($ViewerReadyTimeoutSeconds, 1)) -RosDistro $CoreRosDistro
                        $dbgFrames = Wait-FeedFrames -DockerCmd $dockerCmd -ContainerId $containerGateStackId -Topic "/yolo/debug_image" -TimeoutSeconds ([Math]::Max($ViewerReadyTimeoutSeconds, 1)) -RosDistro $CoreRosDistro
                        $feedViewerFrameCounts = [ordered]@{ rgb = $rgbFrames; yolo_debug = $dbgFrames }
                        $feedViewerStartupElapsedS = [Math]::Round(((Get-Date) - $viewerStart).TotalSeconds, 3)
                        $framesOk = ($rgbFrames -ge 1 -and $dbgFrames -ge 1)
                        $feedViewersGatePass = $framesOk
                        $feedViewerStatus = if ($framesOk) { "viewer_ready" } else { "viewer_frame_timeout" }
                    }
                }
            }
        }
        Write-Host ("VIEWER_LAUNCH_STATUS={0}" -f $feedViewerStatus)
    }

    if ($Milestone -eq 1) {
        $stageRuns += Invoke-UatStage -Mode "snapshot" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -SnapshotTimeout $snapshotCaptureTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
    } elseif ($Milestone -eq 2) {
        $stageRuns += Invoke-UatStage -Mode "coordinate" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -SnapshotTimeout $snapshotCaptureTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
        $stageRuns += Invoke-UatStage -Mode "snapshot" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -SnapshotTimeout $snapshotCaptureTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
    } else {
        $stageRuns += Invoke-UatStage -Mode "snapshot" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -SnapshotTimeout $snapshotCaptureTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
        $stageRuns += Invoke-UatStage -Mode "nav2" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -SnapshotTimeout $snapshotCaptureTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
    }

    $snapshotRun = ($stageRuns | Where-Object { $_.mode -eq "snapshot" } | Select-Object -Last 1)
    $coordinateRun = ($stageRuns | Where-Object { $_.mode -eq "coordinate" } | Select-Object -Last 1)
    $nav2Run = ($stageRuns | Where-Object { $_.mode -eq "nav2" } | Select-Object -Last 1)

    $snapshotSummary = $null; $coordinateSummary = $null; $navSummary = $null
    if ($snapshotRun -and $snapshotRun.artifact_dir) {
        $snapshotSummaryPath = Join-Path $snapshotRun.artifact_dir "snapshot_summary.json"
        if (Test-Path -LiteralPath $snapshotSummaryPath) { $snapshotSummary = Get-Content -LiteralPath $snapshotSummaryPath -Raw | ConvertFrom-Json }
        $rgb = Join-Path $snapshotRun.artifact_dir "d415_color.png"
        $dbg = Join-Path $snapshotRun.artifact_dir "yolo_debug.png"
        $diff = Join-Path $snapshotRun.artifact_dir "image_diff.json"
        if (Test-Path -LiteralPath $rgb) { Copy-Item -LiteralPath $rgb -Destination (Join-Path $artifactDir "screenshots/d415_color.png") -Force }
        if (Test-Path -LiteralPath $dbg) { Copy-Item -LiteralPath $dbg -Destination (Join-Path $artifactDir "screenshots/yolo_debug.png") -Force }
        if (Test-Path -LiteralPath $diff) { Copy-Item -LiteralPath $diff -Destination (Join-Path $artifactDir "screenshots/image_diff_metrics.json") -Force }
    }
    if ($coordinateRun -and $coordinateRun.artifact_dir) {
        $coordSummaryPath = Join-Path $coordinateRun.artifact_dir "summary.json"
        if (Test-Path -LiteralPath $coordSummaryPath) { $coordinateSummary = Get-Content -LiteralPath $coordSummaryPath -Raw | ConvertFrom-Json }
    }
    if ($nav2Run -and $nav2Run.artifact_dir) {
        $navSummaryPath = Join-Path $nav2Run.artifact_dir "nav_summary.json"
        if (Test-Path -LiteralPath $navSummaryPath) { $navSummary = Get-Content -LiteralPath $navSummaryPath -Raw | ConvertFrom-Json }
    }

    if ($visualSurfaceRequested -and $Milestone -eq 2 -and -not [string]::IsNullOrWhiteSpace($containerSimGateId)) {
        $viewerModelSdf = if ([System.IO.Path]::IsPathRooted($DemoTargetModelSdf)) { $DemoTargetModelSdf } else { Join-Path $repoRoot $DemoTargetModelSdf }
        $viewerModelName = "${DemoTargetName}_viewer"
        Invoke-RemoveModel -DockerCmd $dockerCmd -ContainerId $containerSimGateId -WorldName $WorldName -ModelName $viewerModelName
        $spawnRes = Invoke-SpawnModel -DockerCmd $dockerCmd -ContainerId $containerSimGateId -WorldName $WorldName -ModelName $viewerModelName -ModelSdfWindowsPath $viewerModelSdf -X $snapshotTargetX -Y $snapshotTargetY -Z $snapshotTargetZ
        if ($spawnRes.ExitCode -eq 0) {
            Start-Sleep -Seconds ([Math]::Max($PersistentVisualHoldSeconds, 1))
            Invoke-RemoveModel -DockerCmd $dockerCmd -ContainerId $containerSimGateId -WorldName $WorldName -ModelName $viewerModelName
        }
    }

    $snapshotPass = ($snapshotSummary -and [bool]$snapshotSummary.pass)
    $coordinatePass = ($coordinateSummary -and [bool]$coordinateSummary.pass)
    $navPass = ($navSummary -and [bool]$navSummary.pass)

    $captureRgb = $false; $captureDebug = $false; $overlayDistinct = $false
    $imageDiffAbsMean = 0.0; $imageDiffMax = 0.0; $imageChangedRatio = 0.0
    if ($snapshotSummary) {
        $captureRgb = [bool]$snapshotSummary.captures.rgb_capture_ok
        $captureDebug = [bool]$snapshotSummary.captures.debug_capture_ok
        $overlayDistinct = -not [bool]$snapshotSummary.image_diff.byte_identical
        $imageDiffAbsMean = [double]$snapshotSummary.image_diff.mean_abs_diff
        $imageChangedRatio = [double]$snapshotSummary.image_diff.changed_pixel_ratio
    }

    $streamReady = $snapshotPass
    $streamStatus = "ok"
    if (-not $snapshotSummary) {
        $streamReady = $false
        $streamStatus = "snapshot_summary_missing"
    } elseif (-not $captureRgb) {
        $streamReady = $false
        $streamStatus = "rgb_stream_timeout"
    } elseif (-not $captureDebug) {
        $streamReady = $false
        $streamStatus = "debug_stream_timeout"
    } elseif (-not $snapshotPass) {
        $streamReady = $false
        $streamStatus = "snapshot_gate_failed"
    }

    $detectionSeen = $false; $detectionAboveThreshold = $false; $ball3dSeen = $false
    $ball3dX = 0.0; $ball3dY = 0.0; $ball3dZ = 0.0
    if ($coordinateSummary) {
        $rate = [double]$coordinateSummary.detection_success_rate
        $detectionSeen = ($rate -gt 0.0)
        $detectionAboveThreshold = ($rate -gt 0.0)
        $ball3dSeen = ($rate -gt 0.0)
    }

    $navActionReady = $false; $motionPass = $false; $cmdVelMessageCount = 0
    $odomDisplacementM = 0.0; $targetStartDistance = 0.0; $targetEndDistance = 0.0; $targetDelta = 0.0
    $targetProgressOk = $false; $motionError = "none"
    if ($navSummary) {
        $acceptCount = [int]$navSummary.goal_accept_count
        $navActionReady = ($acceptCount -ge 1)
        $duration = [double]$navSummary.duration_s
        $rateHz = [double]$navSummary.cmd_vel_stats.rate_hz
        $cmdVelMessageCount = [int][Math]::Round($duration * $rateHz, 0)
        $targetStartDistance = [double]($navSummary.target_progress.start_distance_m)
        $targetEndDistance = [double]($navSummary.target_progress.end_distance_m)
        $targetDelta = [double]($targetEndDistance - $targetStartDistance)
        $targetProgressOk = [bool]$navSummary.target_progress.pass
        $retained = [double]($navSummary.target_progress.distance_retained_progress_m)
        if ([double]::IsNaN($retained)) { $retained = 0.0 }
        $odomDisplacementM = [Math]::Max($retained, 0.0)
        if ($targetProgressOk) {
            $motionPass = ($odomDisplacementM -ge $MotionMinDistanceMeters)
            if (-not $motionPass) { $motionError = "displacement_below_threshold" }
        } else {
            $motionError = "target_distance_not_improving"
            $motionPass = $false
        }
        if ($cmdVelMessageCount -le 0 -and -not $motionPass) { $motionError = "cmd_vel_inactive" }
    } elseif ($Milestone -ge 3) {
        $motionError = "missing_nav_summary"
    }
    if ($Milestone -ge 3) {
        $navSampleCount = if ($navSummary) { [int]$navSummary.target_progress.sample_count } else { 0 }
        if ($navSampleCount -le 0) {
            $streamReady = $false
            $streamStatus = "odom_timeout"
        }
    }

    if ([bool]$OpenFeedViewers -and -not $visualSurfaceRequested -and ((-not $feedViewersRunning) -or (-not $worldViewerRunning) -or (-not $feedViewersGatePass))) {
        if (-not $displayPreflightOk) {
            $feedViewerStatus = if ([string]::IsNullOrWhiteSpace($DisplayPreflightStatus)) { "display_preflight_failed" } else { $DisplayPreflightStatus }
            $worldViewerStatus = $feedViewerStatus
            $feedViewersRunning = $false
            $worldViewerRunning = $false
            $feedViewersGatePass = $false
        }
        else {
            $containerSimGateId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "sim-gate"
            $containerGateStackId = Get-ContainerServiceId -DockerCmd $dockerCmd -ProjectName $resolvedProjectName -ServiceName "gate-stack"
            if ([string]::IsNullOrWhiteSpace($containerSimGateId) -or [string]::IsNullOrWhiteSpace($containerGateStackId)) {
                $feedViewerStatus = "viewer_container_unavailable"
                $worldViewerStatus = "world_viewer_unavailable"
                $feedViewersRunning = $false
                $worldViewerRunning = $false
                $feedViewersGatePass = $false
            }
            else {
                if (-not [bool]$gateHeadless) {
                    $worldViewerRunning = $true
                    $worldViewerStatus = "integrated_sim_gui"
                }
                else {
                    $worldViewer = Start-WorldViewer -DockerCmd $dockerCmd -ContainerId $containerSimGateId -Display $DisplayAddress -RosDistro $CoreRosDistro
                    $worldViewerPid = [string]$worldViewer.Pid
                    $worldViewerLog = [string]$worldViewer.Log
                    $worldAlive = $false
                    for ($tick = 0; $tick -lt [Math]::Max($ViewerReadyTimeoutSeconds, 1); $tick++) {
                        $worldAlive = Test-WorldViewerAlive -DockerCmd $dockerCmd -ContainerId $containerSimGateId -ViewerPid $worldViewerPid
                        if ($worldAlive) { break }
                        Start-Sleep -Seconds 1
                    }
                    if ($worldAlive) {
                        $worldViewerRunning = $true
                        $worldViewerStatus = "viewer_ready"
                    }
                    else {
                        $worldViewerRunning = $false
                        $worldViewerStatus = "world_viewer_unavailable"
                    }
                }

                $viewerPackage = if ($ViewerBackend -eq "image_view") { "image_view" } else { "rqt_image_view" }
                $backendCheck = Invoke-ContainerScript -DockerCmd $dockerCmd -ContainerId $containerGateStackId -Script ("source /opt/ros/$CoreRosDistro/setup.bash && ros2 pkg executables $viewerPackage 2>/dev/null | grep -q '^$viewerPackage '")
                if ($backendCheck.ExitCode -ne 0) {
                    $feedViewerStatus = "viewer_backend_missing"
                    $feedViewersRunning = $false
                }
                else {
                    $viewerWatch = [System.Diagnostics.Stopwatch]::StartNew()
                    $rgbViewer = Start-FeedViewer -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerId "viewer_rgb" -Topic "/d415/color/image_raw" -Display $DisplayAddress -RosDistro $CoreRosDistro -ViewerBackend $ViewerBackend
                    $dbgViewer = Start-FeedViewer -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerId "viewer_debug" -Topic "/yolo/debug_image" -Display $DisplayAddress -RosDistro $CoreRosDistro -ViewerBackend $ViewerBackend
                    $feedRgbViewerPid = [string]$rgbViewer.Pid
                    $feedDebugViewerPid = [string]$dbgViewer.Pid
                    Start-Sleep -Seconds ([Math]::Max($ViewerStartupDelaySeconds, 0))

                    $rgbAlive = $false
                    $dbgAlive = $false
                    for ($tick = 0; $tick -lt [Math]::Max($ViewerReadyTimeoutSeconds, 1); $tick++) {
                        $rgbAlive = Test-FeedViewerAlive -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerPid $feedRgbViewerPid
                        $dbgAlive = Test-FeedViewerAlive -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerPid $feedDebugViewerPid
                        if ($rgbAlive -and $dbgAlive) { break }
                        Start-Sleep -Seconds 1
                    }
                    $viewerWatch.Stop()
                    $feedViewerStartupElapsedS = [Math]::Round($viewerWatch.Elapsed.TotalSeconds, 3)

                    if ($rgbAlive -and $dbgAlive) {
                        $feedViewersRunning = $true
                        $feedViewerStatus = "viewer_ready"
                    }
                    else {
                        $feedViewersRunning = $false
                        $feedViewerStatus = "viewer_process_exit"
                        $rgbTail = Read-ViewerLogTail -DockerCmd $dockerCmd -ContainerId $containerGateStackId -LogPath $rgbViewer.Log
                        $dbgTail = Read-ViewerLogTail -DockerCmd $dockerCmd -ContainerId $containerGateStackId -LogPath $dbgViewer.Log
                        foreach ($line in @($rgbTail + $dbgTail)) {
                            if ($line -match "could not connect to display|No protocol specified|QXcbConnection") {
                                $feedViewerStatus = "feed_viewer_unavailable"
                                break
                            }
                        }
                    }
                }

                $feedViewersGatePass = ($feedViewersRunning -and $worldViewerRunning)
                if (-not $feedViewersGatePass -and $worldViewerStatus -ne "viewer_ready" -and $feedViewerStatus -eq "viewer_ready") {
                    $feedViewerStatus = $worldViewerStatus
                }
            }
        }
    }

    $visualSummary = $null
    $worldStreamSummary = $null
    $truthSummary = $null
    $modeSpecificVisualArtifacts = [pscustomobject]@{
        suffix = ""
        summary_path = ""
        raw_video = ""
        debug_video = ""
        topdown_video = ""
        world_stream_summary_path = ""
        world_stream_video_path = ""
        world_stream_screenshot_path = ""
    }
    if ($visualSurfaceRequested -and -not [string]::IsNullOrWhiteSpace($containerGateStackId)) {
        if (-not [string]::IsNullOrWhiteSpace($worldStreamContainerId)) {
            Stop-WorldStream -DockerCmd $dockerCmd -ContainerId $worldStreamContainerId
        }
        if (-not [string]::IsNullOrWhiteSpace($containerSimGateId)) {
            Stop-TruthProbe -DockerCmd $dockerCmd -ContainerId $containerSimGateId
        }
        Stop-VisualObserver -DockerCmd $dockerCmd -ContainerId $containerGateStackId
        $visualSummaryWait = Wait-VisualObserverSummary -VisualDir $sessionVisualDir -TimeoutSeconds 15
        $visualSummaryPath = [string]$visualSummaryWait.SummaryPath
        if ([bool]$visualSummaryWait.Ready) {
            $visualSummary = $visualSummaryWait.Summary
        }
        $truthSummaryWait = Wait-TruthSummary -VisualDir $sessionVisualDir -TimeoutSeconds 12
        $truthSummaryPath = [string]$truthSummaryWait.SummaryPath
        if ([bool]$truthSummaryWait.Ready) {
            try {
                $truthSummary = $truthSummaryWait.Summary
                $truthReady = [bool]$truthSummary.pass
                $truthStatus = if ($truthReady) { "truth_ready" } else { "truth_content_failed" }
            }
            catch {
            }
        }
        $worldStreamSummaryWait = Wait-WorldStreamSummary -VisualDir $sessionVisualDir -TimeoutSeconds 12
        $worldStreamSummaryPath = [string]$worldStreamSummaryWait.SummaryPath
        if ([bool]$worldStreamSummaryWait.Ready) {
            try {
                $worldStreamSummary = $worldStreamSummaryWait.Summary
                $worldStreamReady = [bool]$worldStreamSummary.pass
                $worldStreamNonblank = [bool]$worldStreamSummary.world_stream_nonblank
                $worldStreamInteractive = [bool]$worldStreamSummary.world_stream_interactive
                $worldStreamUrl = [string]$worldStreamSummary.world_stream_url
                $worldStreamSameSessionPartition = [bool]$worldStreamSummary.same_session_partition
                if (-not $worldStreamSameSessionPartition) {
                    $worldStreamStatus = "world_stream_partition_mismatch"
                }
                else {
                    $worldStreamStatus = if ($worldStreamReady) { "world_stream_ready" } else { "world_stream_content_failed" }
                }
            }
            catch {
            }
        }

        $modeSpecificVisualArtifacts = Save-ModeSpecificVisualArtifacts `
            -VisualDir $sessionVisualDir `
            -VisualSurface $VisualSurface `
            -RepoRoot $repoRoot `
            -VisualSummary $visualSummary `
            -WorldStreamSummary $worldStreamSummary

        $visualReady = (
            $visualSummaryWait.Ready -and
            ($null -ne $visualSummary) -and
            [bool]$visualSummary.pass -and
            ($truthReady -or -not $visualSurfaceRequested) -and
            ($WorldSurface -ne "streamed_sim" -or $worldStreamReady)
        )
        $visualGatePass = $visualReady
        if ($visualReady) {
            $visualStatus = "visual_ready"
        }
        elseif (-not $visualSummaryWait.Ready) {
            $visualStatus = "visual_summary_missing"
        }
        elseif (-not $truthReady) {
            $visualStatus = $truthStatus
        }
        elseif ($WorldSurface -eq "streamed_sim" -and -not $worldStreamReady) {
            $visualStatus = $worldStreamStatus
        }
        else {
            $visualStatus = "visual_content_failed"
        }
    }

    if ($captureRgb) { $feedViewerFrameCounts.rgb = 1 }
    if ($captureDebug) { $feedViewerFrameCounts.yolo_debug = 1 }
    $presentationGatePass = if ($visualSurfaceRequested) { $visualGatePass } else { $feedViewersGatePass }
    if (-not $visualSurfaceRequested) {
        $visualReady = ($streamReady -and ((-not [bool]$OpenFeedViewers) -or $feedViewersGatePass))
    }

    if ($Milestone -eq 1) {
        $overallPass = ($snapshotPass -and $captureDebug -and $overlayDistinct -and $streamReady -and $presentationGatePass -and $visualReady)
        if (-not $overallPass) {
            if (-not $streamReady) { $demoFailureClass = $streamStatus }
            elseif (-not $visualReady) { $demoFailureClass = if ($visualSurfaceRequested -and -not [string]::IsNullOrWhiteSpace($visualStatus) -and $visualStatus -ne "visual_ready") { $visualStatus } else { "visual_not_ready" } }
            elseif (-not $presentationGatePass) {
                if ($visualSurfaceRequested) {
                    $demoFailureClass = $visualStatus
                }
                else {
                    $demoFailureClass = if ($worldViewerStatus -and $worldViewerStatus -ne "viewer_ready" -and $worldViewerStatus -ne "skipped") { $worldViewerStatus } else { "feed_viewer_unavailable" }
                }
            }
            else { $demoFailureClass = "snapshot_gate_failed" }
        }
    } elseif ($Milestone -eq 2) {
        $overallPass = ($ball3dSeen -and $captureDebug -and $overlayDistinct -and $streamReady -and $presentationGatePass -and $visualReady)
        if (-not $overallPass) {
            if (-not $streamReady) { $demoFailureClass = $streamStatus }
            elseif (-not $visualReady) { $demoFailureClass = if ($visualSurfaceRequested -and -not [string]::IsNullOrWhiteSpace($visualStatus) -and $visualStatus -ne "visual_ready") { $visualStatus } else { "visual_not_ready" } }
            elseif (-not $presentationGatePass) {
                if ($visualSurfaceRequested) {
                    $demoFailureClass = $visualStatus
                }
                else {
                    $demoFailureClass = if ($worldViewerStatus -and $worldViewerStatus -ne "viewer_ready" -and $worldViewerStatus -ne "skipped") { $worldViewerStatus } else { "feed_viewer_unavailable" }
                }
            }
            else { $demoFailureClass = "m2_tracking_gate_failed" }
        }
    } else {
        $requiredActionOk = ((-not $RequireNav2ActionServer) -or $navActionReady)
        $requiredMotionOk = ((-not $RequireMotion) -or $motionPass)
        $overallPass = ($snapshotPass -and $navPass -and $requiredActionOk -and $requiredMotionOk -and $streamReady -and $presentationGatePass -and $visualReady)
        if (-not $overallPass) {
            if (-not $streamReady) { $demoFailureClass = $streamStatus }
            elseif (-not $requiredActionOk) { $demoFailureClass = "nav2_action_unavailable" }
            elseif (-not $requiredMotionOk) { $demoFailureClass = $motionError }
            elseif (-not $visualReady) { $demoFailureClass = if ($visualSurfaceRequested -and -not [string]::IsNullOrWhiteSpace($visualStatus) -and $visualStatus -ne "visual_ready") { $visualStatus } else { "visual_not_ready" } }
            elseif (-not $presentationGatePass) {
                if ($visualSurfaceRequested) {
                    $demoFailureClass = $visualStatus
                }
                else {
                    $demoFailureClass = if ($worldViewerStatus -and $worldViewerStatus -ne "viewer_ready" -and $worldViewerStatus -ne "skipped") { $worldViewerStatus } else { "feed_viewer_unavailable" }
                }
            }
            else { $demoFailureClass = "m3_nav_gate_failed" }
        }
    }

    $navProgressSamples = if ($navSummary) { [int]$navSummary.target_progress.sample_count } else { 0 }
    $demoSummary = [ordered]@{
        milestone = "$Milestone"
        runtime_target = $RuntimeTarget
        perf_profile = $PerfProfile
        inference_device = $InferenceDevice
        inference_backend = $InferenceBackend
        headless = [bool]$gateHeadless
        execution_lane = "container_kilted"
        core_ros_distro = $CoreRosDistro
        session_id = $runId
        start_utc = $runStartUtc.ToString("o")
        end_utc = (Get-Date).ToUniversalTime().ToString("o")
        max_run_seconds = [Math]::Max($MaxRunSeconds, 0)
        auto_stop_enabled = ($MaxRunSeconds -gt 0)
        compose_project = $resolvedProjectName
        world_file = $WorldFile
        world_name = $WorldName
        gazebo_partition = $runId
        display_mode = $DisplayMode
        display_address = $DisplayAddress
        visual_surface = $VisualSurface
        world_surface = $WorldSurface
        display_preflight_status = $DisplayPreflightStatus
        display_preflight_message = $DisplayPreflightMessage
        viewer_backend = $ViewerBackend
        keep_windows_open = [bool]$KeepWindowsOpen
        commands = [ordered]@{
            gate_up = "scripts/run_compose_gate.ps1 -Action up -ProjectName $resolvedProjectName"
            uat_stages = @($stageRuns | ForEach-Object { $_.mode })
            gate_down = "scripts/run_compose_gate.ps1 -Action down -ProjectName $resolvedProjectName"
        }
        stage_results = @($stageRuns | ForEach-Object { [ordered]@{ mode=$_.mode; exit_code=$_.exit_code; status=$_.status; pass=$_.pass; artifact_dir=$_.artifact_dir; readiness_report=$_.readiness_report } })
        screenshots = [ordered]@{ rgb = "screenshots/d415_color.png"; yolo_debug = "screenshots/yolo_debug.png" }
        capture = [ordered]@{
            rgb_captured = $captureRgb
            debug_captured = $captureDebug
            rgb_topic_seen = $captureRgb
            debug_topic_seen = $captureDebug
            rgb_frames_seen = if ($captureRgb) { 1 } else { 0 }
            debug_frames_seen = if ($captureDebug) { 1 } else { 0 }
            rgb_capture_error = if ($captureRgb) { "none" } else { "timeout_no_messages" }
            debug_capture_error = if ($captureDebug) { "none" } else { "timeout_no_messages" }
            capture_qos_profile = "sensor_data"
            capture_min_frames = 1
            capture_delay_s = 0
            detection_seen = $detectionSeen
            detection_confidence = if ($detectionSeen) { [double]$MinDetectionConfidence } else { 0.0 }
            detection_confidence_threshold = $MinDetectionConfidence
            detection_above_threshold = $detectionAboveThreshold
            overlay_distinct = $overlayDistinct
            image_byte_identical = (-not $overlayDistinct)
            image_diff_abs_mean = $imageDiffAbsMean
            image_diff_max = $imageDiffMax
            image_changed_pixel_ratio = $imageChangedRatio
            image_diff_metrics_json = "screenshots/image_diff_metrics.json"
            ball_position_3d_seen = $ball3dSeen
            ball_position_3d_x = $ball3dX
            ball_position_3d_y = $ball3dY
            ball_position_3d_z = $ball3dZ
        }
        demo_target = [ordered]@{
            ensure_demo_target = [bool]$EnsureDemoTarget
            target_spawn_relative_mode = [bool]$DemoTargetRelative
            target_spawn_forward_m = $DemoTargetForwardM
            target_spawn_lateral_m = $DemoTargetLateralM
            target_spawn_vertical_offset_m = $DemoTargetVerticalOffsetM
            world_name = $WorldName
            target_model_sdf = $DemoTargetModelSdf
            target_name = $DemoTargetName
            target_spawn_requested_x = $DemoTargetX
            target_spawn_requested_y = $DemoTargetY
            target_spawn_requested_z = $DemoTargetZ
            target_spawn_x = $snapshotTargetX
            target_spawn_y = $snapshotTargetY
            target_spawn_z = $snapshotTargetZ
            target_spawn_resolve_status = $targetResolveStatus
            target_spawn_ok = [bool]$EnsureDemoTarget
            target_spawn_status = if ($EnsureDemoTarget) { "spawn_ok" } else { "skipped" }
            target_spawn_timeout_s = 20
            world_ready = $true
            world_ready_status = "world_ready"
            world_ready_timeout_s = 45
        }
        stream_readiness = [ordered]@{
            ready = $streamReady
            status = $streamStatus
            timeout_s = [Math]::Max($StepTimeoutSeconds, 120)
            min_frames = 1
            odom_required = ($Milestone -ge 3)
            odom_topic = "/model/jetbot/odometry"
        }
        viewers = [ordered]@{
            open_feed_viewers_requested = [bool]$OpenFeedViewers
            feed_viewers_required = ([bool]$OpenFeedViewers -and -not $visualSurfaceRequested)
            world_viewer_required = ([bool]$OpenFeedViewers -and -not $visualSurfaceRequested -and $WorldSurface -eq "x11_debug")
            world_viewer_running = $worldViewerRunning
            world_viewer_status = $worldViewerStatus
            world_viewer_pid = $worldViewerPid
            feed_viewers_running = $feedViewersRunning
            feed_viewer_status = $feedViewerStatus
            viewer_backend = $ViewerBackend
            viewer_start_delay_s = [Math]::Max($ViewerStartupDelaySeconds, 0)
            viewer_startup_elapsed_s = $feedViewerStartupElapsedS
            viewer_frame_counts = $feedViewerFrameCounts
            visual_ready = $visualReady
        }
        visual = [ordered]@{
            requested = $visualSurfaceRequested
            surface = $VisualSurface
            world_surface = $WorldSurface
            status = $visualStatus
            visual_ready = $visualReady
            pass = $visualGatePass
            observer_pid = $visualObserverPid
            observer_log = $visualObserverLog
            state_path = if ([string]::IsNullOrWhiteSpace($visualStatePath)) { "" } else { $visualStatePath }
            summary_path = if ([string]::IsNullOrWhiteSpace($visualSummaryPath)) { "" } else { $visualSummaryPath }
            raw_video = if ($visualSummary) { Convert-OrchestratorPath -Path ([string]$visualSummary.raw_video) -RepoRoot $repoRoot } else { "" }
            debug_video = if ($visualSummary) { Convert-OrchestratorPath -Path ([string]$visualSummary.debug_video) -RepoRoot $repoRoot } else { "" }
            topdown_video = if ($visualSummary) { Convert-OrchestratorPath -Path ([string]$visualSummary.topdown_video) -RepoRoot $repoRoot } else { "" }
            keyframes_dir = if ($visualSummary) { Convert-OrchestratorPath -Path ([string]$visualSummary.keyframes_dir) -RepoRoot $repoRoot } else { "" }
            timeline_path = if ($visualSummary) { Convert-OrchestratorPath -Path ([string]$visualSummary.timeline_path) -RepoRoot $repoRoot } else { "" }
            raw_frame_count = if ($visualSummary) { [int]$visualSummary.raw_frame_count } else { 0 }
            debug_frame_count = if ($visualSummary) { [int]$visualSummary.debug_frame_count } else { 0 }
            telemetry_frame_count = if ($visualSummary) { [int]$visualSummary.telemetry_frame_count } else { 0 }
            target_visible_ratio = if ($visualSummary) { [double]$visualSummary.target_visible_ratio } else { 0.0 }
            overlay_difference_ok = if ($visualSummary) { [bool]$visualSummary.overlay_difference_ok } else { $false }
            target_persistence_ok = if ($visualSummary) { [bool]$visualSummary.target_persistence_ok } else { $false }
            motion_progress_ok = if ($visualSummary) { [bool]$visualSummary.motion_progress_ok } else { $false }
            true_target_seen = if ($visualSummary) { [bool]$visualSummary.true_target_seen } else { $false }
            truth_alignment_ok = if ($visualSummary) { [bool]$visualSummary.truth_alignment_ok } else { $false }
            truth_failure_class = if ($visualSummary) { [string]$visualSummary.truth_failure_class } else { "" }
            vision_vs_truth_m_median = if ($visualSummary) { $visualSummary.vision_vs_truth_m_median } else { $null }
            waypoint_vs_truth_m_median = if ($visualSummary) { $visualSummary.waypoint_vs_truth_m_median } else { $null }
            waypoint_vs_vision_m_median = if ($visualSummary) { $visualSummary.waypoint_vs_vision_m_median } else { $null }
            dashboard_url = if ($dashboardInfo) { [string]$dashboardInfo.Url } else { "" }
            dashboard_port = if ($dashboardInfo) { [int]$dashboardInfo.Port } else { 0 }
            dashboard_ready = if ($dashboardInfo) { [bool]$dashboardInfo.Ready } else { ($VisualSurface -ne "browser_dashboard") }
            auto_open = [bool]$AutoOpenVisualSurface
            truth_state_path = if ([string]::IsNullOrWhiteSpace($truthStatePath)) { "" } else { $truthStatePath }
            truth_summary_path = if ([string]::IsNullOrWhiteSpace($truthSummaryPath)) { "" } else { $truthSummaryPath }
            truth_ready = $truthReady
            truth_status = $truthStatus
            mode_artifacts = [ordered]@{
                suffix = [string]$modeSpecificVisualArtifacts.suffix
                summary_path = [string]$modeSpecificVisualArtifacts.summary_path
                raw_video = [string]$modeSpecificVisualArtifacts.raw_video
                debug_video = [string]$modeSpecificVisualArtifacts.debug_video
                topdown_video = [string]$modeSpecificVisualArtifacts.topdown_video
                world_stream_summary_path = [string]$modeSpecificVisualArtifacts.world_stream_summary_path
                world_stream_video_path = [string]$modeSpecificVisualArtifacts.world_stream_video_path
                world_stream_screenshot_path = [string]$modeSpecificVisualArtifacts.world_stream_screenshot_path
            }
            world_stream = [ordered]@{
                requested = ($WorldSurface -eq "streamed_sim")
                url = $worldStreamUrl
                port = $worldStreamPort
                ready = $worldStreamReady
                status = $worldStreamStatus
                nonblank = $worldStreamNonblank
                interactive = $worldStreamInteractive
                state_path = if ([string]::IsNullOrWhiteSpace($worldStreamStatePath)) { "" } else { $worldStreamStatePath }
                summary_path = if ([string]::IsNullOrWhiteSpace($worldStreamSummaryPath)) { "" } else { $worldStreamSummaryPath }
                video_path = if ($worldStreamSummary) { Convert-OrchestratorPath -Path ([string]$worldStreamSummary.video_path) -RepoRoot $repoRoot } else { "" }
                screenshot_path = if ($worldStreamSummary) { Convert-OrchestratorPath -Path ([string]$worldStreamSummary.screenshot_path) -RepoRoot $repoRoot } else { "" }
                same_session_partition = $worldStreamSameSessionPartition
                mode_artifacts = [ordered]@{
                    summary_path = [string]$modeSpecificVisualArtifacts.world_stream_summary_path
                    video_path = [string]$modeSpecificVisualArtifacts.world_stream_video_path
                    screenshot_path = [string]$modeSpecificVisualArtifacts.world_stream_screenshot_path
                }
            }
        }
        nav2 = [ordered]@{
            require_action_server = [bool]$RequireNav2ActionServer
            action_server_ready = $navActionReady
            action_server_count = if ($navActionReady) { 1 } else { 0 }
        }
        motion = [ordered]@{
            required = [bool]$RequireMotion
            window_s = $MotionWindowSeconds
            min_distance_m = $MotionMinDistanceMeters
            target_progress_min_m = $MotionTargetProgressMinMeters
            cmd_vel_topic_primary = "/jetbot_base_controller/cmd_vel"
            cmd_vel_topic_secondary = "/cmd_vel"
            cmd_vel_message_count = $cmdVelMessageCount
            detection_message_count = if ($navSummary) { [int]([double]$navSummary.detection_stats.rate_hz * [double]$navSummary.duration_s) } else { 0 }
            odom_topic = "/model/jetbot/odometry"
            odom_seen = ($Milestone -lt 3 -or $navPass)
            odom_start = [ordered]@{ x = 0.0; y = 0.0; z = 0.0 }
            odom_end = [ordered]@{ x = $odomDisplacementM; y = 0.0; z = 0.0 }
            odom_displacement_m = $odomDisplacementM
            target_start_distance_m = $targetStartDistance
            target_end_distance_m = $targetEndDistance
            target_distance_delta_m = $targetDelta
            nav_progress_samples = $navProgressSamples
            nav_progress_start_remaining_m = $targetStartDistance
            nav_progress_end_remaining_m = $targetEndDistance
            nav_progress_delta_m = $targetDelta
            target_progress_ok = $targetProgressOk
            probe_error = if ($motionPass) { "none" } else { $motionError }
            pass = $motionPass
        }
        process_health = [ordered]@{
            sim_running = $true
            detector_running = $true
            extractor_running = ($Milestone -ge 2)
            bridge_running = ($Milestone -ge 3)
            nav2_running = ($Milestone -ge 3)
            cmd_vel_relay_running = ($Milestone -ge 3)
            world_viewer_running = if ($WorldSurface -eq "streamed_sim") { $worldStreamReady } else { $worldViewerRunning }
            feed_raw_viewer_running = $feedViewersRunning
            feed_debug_viewer_running = $feedViewersRunning
        }
        failure_context = [ordered]@{
            bridge_launch_blocked_reason = if ($Milestone -ge 3 -and -not $navPass) { "nav_stage_failed" } else { "none" }
            display_preflight_status = $DisplayPreflightStatus
            display_preflight_message = $DisplayPreflightMessage
            failure_class = if ($overallPass) { "" } else { $demoFailureClass }
        }
        visual_ready = $visualReady
        pass = $overallPass
    }

    $operatorChecklist = [ordered]@{
        milestone = "$Milestone"
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        items = @(
            [ordered]@{ id = "world_ready"; description = "World service became available"; pass = $true },
            [ordered]@{ id = "stream_ready"; description = "Required camera/odom streams became active"; pass = $streamReady },
            [ordered]@{ id = "truth_ready"; description = "Sim truth target became available"; required = $visualSurfaceRequested; pass = $truthReady },
            [ordered]@{ id = "truth_alignment_ok"; description = "Vision target stayed aligned with sim truth"; required = $visualSurfaceRequested; pass = if ($visualSummary) { [bool]$visualSummary.truth_alignment_ok } else { $false } },
            [ordered]@{ id = "overlay_distinct"; description = "Debug image differs from raw image"; required = ($Milestone -le 2); pass = $overlayDistinct },
            [ordered]@{ id = "ball_position_3d"; description = "/yolo/ball_position_3d active"; required = ($Milestone -ge 2); pass = $ball3dSeen },
            [ordered]@{ id = "nav2_action_server_ready"; description = "/navigate_to_pose action server ready"; required = ($Milestone -ge 3); pass = $navActionReady },
            [ordered]@{ id = "world_viewer_running"; description = "World viewer window running when requested"; required = ([bool]$OpenFeedViewers -and -not $visualSurfaceRequested); pass = $worldViewerRunning },
            [ordered]@{ id = "feed_viewers_running"; description = "Feed viewer windows running when requested"; required = ([bool]$OpenFeedViewers -and -not $visualSurfaceRequested); pass = $feedViewersGatePass },
            [ordered]@{ id = "visual_surface_ready"; description = "Recorded/dashboard surface captured nonblank content"; required = $visualSurfaceRequested; pass = $visualGatePass },
            [ordered]@{ id = "world_stream_ready"; description = "Streamed 3D Gazebo world ready"; required = ($WorldSurface -eq "streamed_sim"); pass = $worldStreamReady },
            [ordered]@{ id = "world_stream_same_session"; description = "Streamed 3D Gazebo world attached to the same session partition"; required = ($WorldSurface -eq "streamed_sim"); pass = $worldStreamSameSessionPartition },
            [ordered]@{ id = "cmd_vel_activity"; description = "cmd_vel activity observed"; required = ($Milestone -ge 3); pass = ($cmdVelMessageCount -gt 0) },
            [ordered]@{ id = "odom_displacement"; description = "Target-distance retained progress reached threshold"; required = ($Milestone -ge 3); pass = ($odomDisplacementM -ge $MotionMinDistanceMeters) }
        )
    }

    $demoSummaryPath = Join-Path $artifactDir "demo_summary.json"
    $checklistPath = Join-Path $artifactDir "operator_checklist.json"
    $demoPidsPath = Join-Path $artifactDir "demo_pids.json"

    $demoSummary | ConvertTo-Json -Depth 12 | Set-Content -Path $demoSummaryPath -Encoding UTF8
    $operatorChecklist | ConvertTo-Json -Depth 8 | Set-Content -Path $checklistPath -Encoding UTF8
    ([ordered]@{ milestone="$Milestone"; execution_lane="container_kilted"; core_ros_distro=$CoreRosDistro; compose_project=$resolvedProjectName; pids=[ordered]@{ sim=""; detector=""; extractor=""; bridge=""; nav2=""; cmd_vel_relay=""; motion_probe=""; world_viewer=$worldViewerPid; world_stream=$worldStreamPid; truth_probe=$truthProbePid; feed_rgb_viewer=$feedRgbViewerPid; feed_debug_viewer=$feedDebugViewerPid; visual_observer=$visualObserverPid; dashboard_server=$(if($dashboardInfo){$dashboardInfo.Pid}else{0}) } } | ConvertTo-Json -Depth 6) | Set-Content -Path $demoPidsPath -Encoding UTF8

    Write-Host "ARTIFACT_DIR=$artifactDir"
    Write-Host "SIM_PID="
    Write-Host "DETECTOR_PID="
    Write-Host "EXTRACTOR_PID="
    Write-Host "BRIDGE_PID="
    Write-Host "NAV2_PID="
    Write-Host "CMD_VEL_RELAY_PID="
    Write-Host "MOTION_PROBE_PID="
    Write-Host "WORLD_VIEWER_PID=$worldViewerPid"
    Write-Host "FEED_RGB_VIEWER_PID=$feedRgbViewerPid"
    Write-Host "FEED_DEBUG_VIEWER_PID=$feedDebugViewerPid"
    Write-Host "VISUAL_OBSERVER_PID=$visualObserverPid"
    Write-Host ("VISUAL_SUMMARY={0}" -f $visualSummaryPath)
    Write-Host ("DASHBOARD_URL={0}" -f $(if($dashboardInfo){$dashboardInfo.Url}else{""}))
    Write-Host "WATCHDOG_PID="
    Write-Host "EVIDENCE_CAPTURE_RGB=$captureRgb"
    Write-Host "EVIDENCE_CAPTURE_DEBUG=$captureDebug"
    Write-Host "STOP_CMD=powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -Action down -ProjectName $resolvedProjectName; powershell -ExecutionPolicy Bypass -File scripts/run_compose_uat.ps1 -Action down -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget"
}
finally {
    foreach ($k in $envBackupKeys) {
        $value = $envBackup[$k]
        if ($null -eq $value) { Remove-Item -Path "Env:$k" -ErrorAction SilentlyContinue }
        else { Set-Item -Path "Env:$k" -Value $value }
    }
    if ($null -eq $originalGazeboPartition) { Remove-Item -Path "Env:GAZEBO_PARTITION" -ErrorAction SilentlyContinue }
    else { Set-Item -Path "Env:GAZEBO_PARTITION" -Value $originalGazeboPartition }
    if ($null -eq $originalWorldStreamPort) { Remove-Item -Path "Env:WORLD_STREAM_PORT" -ErrorAction SilentlyContinue }
    else { Set-Item -Path "Env:WORLD_STREAM_PORT" -Value $originalWorldStreamPort }

    if (-not [string]::IsNullOrWhiteSpace($dockerCmd) -and -not [string]::IsNullOrWhiteSpace($containerGateStackId)) {
        Stop-VisualObserver -DockerCmd $dockerCmd -ContainerId $containerGateStackId
    }

    if (-not [bool]$KeepWindowsOpen) {
        Stop-DashboardServer -ServerInfo $dashboardInfo
        if (-not [string]::IsNullOrWhiteSpace($dockerCmd) -and -not [string]::IsNullOrWhiteSpace($containerGateStackId)) {
            Stop-FeedViewer -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerId "viewer_rgb"
            Stop-FeedViewer -DockerCmd $dockerCmd -ContainerId $containerGateStackId -ViewerId "viewer_debug"
        }
        if (-not [string]::IsNullOrWhiteSpace($dockerCmd) -and -not [string]::IsNullOrWhiteSpace($containerSimGateId)) {
            Stop-WorldViewer -DockerCmd $dockerCmd -ContainerId $containerSimGateId
        }

        Invoke-PSCapture -ScriptPath $composeGateScript -ScriptArgs @(
            "-Action","down","-ProjectName",$resolvedProjectName,
            "-RuntimeTarget",$RuntimeTarget,
            "-InferenceBackend",$InferenceBackend,
            "-CoreRosDistro",$CoreRosDistro,
            "-IncludeNav2Bringup",($(if($includeNav2){"true"}else{"false"})),
            "-IncludeBridge","false",
            "-IncludeCmdVelRelay",($(if($includeRelay){"true"}else{"false"}))
        ) | Out-Null
        Invoke-PSCapture -ScriptPath $composeUatScript -ScriptArgs @(
            "-Action","down","-ProjectName",$resolvedProjectName,
            "-RuntimeTarget",$RuntimeTarget,
            "-InferenceBackend",$InferenceBackend,
            "-CoreRosDistro",$CoreRosDistro
        ) | Out-Null
    }
    else {
        Write-Host "KEEP_WINDOWS_OPEN=true; preserving compose stack after artifact capture."
    }
}

if ($overallPass) { exit 0 }
if ([string]::IsNullOrWhiteSpace($demoFailureClass)) { $demoFailureClass = "milestone_failed" }
Write-Error "Container milestone demo failed: $demoFailureClass"
exit 2
