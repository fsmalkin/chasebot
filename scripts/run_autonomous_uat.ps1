param(
    [string]$Distro = "Ubuntu-24.04",
    [string]$WorkspacePath = "~/ros2_ws",
    [string]$RosDistro = "auto",
    [int]$RetryCount = 1,
    [int]$SoakMinutes = 15,
    [int]$SoakProbeSeconds = 10,
    [switch]$SkipM5Regression
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RosDistro {
    param(
        [Parameter(Mandatory = $true)][string]$Distro,
        [string]$Requested = "auto"
    )
    if ($Requested -and $Requested -ne "auto") {
        return $Requested
    }

    $resolveCmd = "if [ -f /opt/ros/jazzy/setup.bash ]; then echo jazzy; elif [ -f /opt/ros/humble/setup.bash ]; then echo humble; elif [ -d /opt/ros ]; then ls -1 /opt/ros | head -n1; fi"
    $detectedRaw = wsl -d $Distro -- bash -lc $resolveCmd 2>$null
    $detected = ($detectedRaw | Out-String).Trim()

    if ([string]::IsNullOrWhiteSpace($detected)) {
        throw "Unable to resolve ROS distro in $Distro. Install ROS first or pass -RosDistro explicitly."
    }
    return $detected
}

function New-MilestoneResult {
    param(
        [string]$Id,
        [string]$Objective
    )
    return [pscustomobject][ordered]@{
        id = $Id
        objective = $Objective
        status = "pending"
        started_utc = $null
        ended_utc = $null
        duration_s = $null
        exit_code = $null
        command = $null
        artifact_dir = $null
        log_file = $null
        notes = @()
    }
}

function Complete-Milestone {
    param(
        [object]$Milestone,
        [string]$Status,
        [int]$ExitCode = 0
    )
    $Milestone.status = $Status
    $Milestone.exit_code = $ExitCode
    $Milestone.ended_utc = (Get-Date).ToUniversalTime().ToString("o")
    if ($Milestone.started_utc) {
        $start = [DateTime]::Parse($Milestone.started_utc)
        $end = [DateTime]::Parse($Milestone.ended_utc)
        $Milestone.duration_s = [Math]::Round(($end - $start).TotalSeconds, 2)
    }
}

function Invoke-ScriptWithLog {
    param(
        [string]$ScriptPath,
        [string[]]$Args,
        [string]$LogPath,
        [switch]$AppendLog
    )

    $stdoutFile = Join-Path $env:TEMP ("chasecar_uat_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderrFile = Join-Path $env:TEMP ("chasecar_uat_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))

    try {
        $argList = @("-ExecutionPolicy", "Bypass", "-File", $ScriptPath) + $Args
        $proc = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList $argList `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile

        $exitCode = $proc.ExitCode
        $outputText = @()
        if (Test-Path -LiteralPath $stdoutFile) {
            $outputText += Get-Content -LiteralPath $stdoutFile
        }
        if (Test-Path -LiteralPath $stderrFile) {
            $outputText += Get-Content -LiteralPath $stderrFile
        }

        if ($AppendLog) {
            if ($outputText.Count -gt 0) {
                Add-Content -Path $LogPath -Value $outputText
            }
        }
        else {
            if ($outputText.Count -gt 0) {
                Set-Content -Path $LogPath -Value $outputText
            }
            else {
                Set-Content -Path $LogPath -Value @()
            }
        }

        foreach ($line in $outputText) {
            Write-Host $line
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrFile -Force -ErrorAction SilentlyContinue
    }

    $artifactLine = $outputText | Where-Object { $_ -like "ARTIFACT_DIR=*" } | Select-Object -Last 1
    $artifactDir = $null
    if ($artifactLine) {
        $artifactDir = $artifactLine -replace "^ARTIFACT_DIR=", ""
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $outputText
        ArtifactDir = $artifactDir
    }
}

function Get-StackPidsFromArtifact {
    param(
        [string]$ArtifactDir,
        [string]$Distro
    )
    if ([string]::IsNullOrWhiteSpace($ArtifactDir)) {
        return @()
    }
    try {
        if ($ArtifactDir -like "/*") {
            if ([string]::IsNullOrWhiteSpace($Distro)) {
                return @()
            }
            $escaped = $ArtifactDir
            $jsonRaw = wsl -d $Distro -- bash -lc "if [ -f '$escaped/stack_pids.json' ]; then cat '$escaped/stack_pids.json'; fi"
            if (-not $jsonRaw) {
                return @()
            }
            $json = ($jsonRaw | Out-String) | ConvertFrom-Json
        }
        else {
            $pidsPath = Join-Path $ArtifactDir "stack_pids.json"
            if (-not (Test-Path -LiteralPath $pidsPath)) {
                return @()
            }
            $json = Get-Content -LiteralPath $pidsPath -Raw | ConvertFrom-Json
        }
        $values = @(
            $json.pids.sim,
            $json.pids.detector,
            $json.pids.extractor,
            $json.pids.bridge
        )
        return @(
            $values |
                Where-Object { $_ -and $_.ToString() -match '^\d+$' } |
                ForEach-Object { $_.ToString() } |
                Select-Object -Unique
        )
    }
    catch {
        return @()
    }
}

function Stop-Stack {
    param(
        [string]$Distro,
        [string[]]$Pids,
        [string]$LogFile
    )
    if (-not $Pids -or $Pids.Count -eq 0) {
        return
    }

    $pidArg = ($Pids -join " ")
    if ($LogFile) {
        Add-Content -Path $LogFile -Value ""
        Add-Content -Path $LogFile -Value "Stopping stack pids: $pidArg"
    }
    $stopOut = wsl -d $Distro -- bash -lc "kill $pidArg 2>/dev/null || true"
    if ($LogFile -and $stopOut) {
        Add-Content -Path $LogFile -Value ($stopOut | Out-String)
    }
}

function Test-StackProcessHealth {
    param(
        [string]$Distro,
        [string[]]$Pids,
        [int]$DurationSeconds,
        [int]$PollSeconds = 10
    )
    if (-not $Pids -or $Pids.Count -eq 0) {
        return [pscustomobject]@{
            Ok = $false
            Message = "No stack pids were captured from stack_pids.json."
        }
    }

    $duration = [Math]::Max($DurationSeconds, 1)
    $poll = [Math]::Max($PollSeconds, 2)
    $pidArg = ($Pids -join " ")
    $probeCmd = 'end=$((SECONDS+{0})); while [ $SECONDS -lt $end ]; do for pid in {1}; do kill -0 $pid >/dev/null 2>&1 || exit 3; done; sleep {2}; done; exit 0' -f $duration, $pidArg, $poll
    wsl -d $Distro -- bash -lc $probeCmd
    if ($LASTEXITCODE -eq 0) {
        return [pscustomobject]@{
            Ok = $true
            Message = "All stack processes stayed alive for $duration seconds."
        }
    }

    return [pscustomobject]@{
        Ok = $false
        Message = "One or more stack processes exited during the soak window."
    }
}

function Run-MilestoneScript {
    param(
        [object]$Milestone,
        [string]$ScriptName,
        [string[]]$Args,
        [int]$Retries = 1
    )
    $Milestone.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    $Milestone.log_file = (Join-Path $logsDir ("{0}_{1}.log" -f $Milestone.id, $ScriptName))
    $Milestone.command = "$ScriptName $($Args -join ' ')"
    $attempt = 0
    while ($attempt -le $Retries) {
        $attempt++
        $result = Invoke-ScriptWithLog `
            -ScriptPath (Join-Path $repoRoot "scripts/$ScriptName") `
            -Args $Args `
            -LogPath $Milestone.log_file `
            -AppendLog:($attempt -gt 1)
        if ($result.ArtifactDir) {
            $Milestone.artifact_dir = $result.ArtifactDir
        }
        if ($result.ExitCode -eq 0) {
            $Milestone.notes += "Attempt $attempt passed."
            Complete-Milestone -Milestone $Milestone -Status "pass" -ExitCode 0
            return
        }
        $Milestone.notes += "Attempt $attempt failed with exit code $($result.ExitCode)."
        if ($attempt -le $Retries) {
            Start-Sleep -Seconds 3
        }
    }
    Complete-Milestone -Milestone $Milestone -Status "fail" -ExitCode 2
}

function Block-Milestones {
    param(
        [int]$StartIndex,
        [int]$EndIndex,
        [string]$Reason
    )
    for ($i = $StartIndex; $i -le $EndIndex; $i++) {
        if ($milestones[$i].status -eq "pending") {
            $milestones[$i].started_utc = (Get-Date).ToUniversalTime().ToString("o")
            $milestones[$i].notes += $Reason
            Complete-Milestone -Milestone $milestones[$i] -Status "blocked" -ExitCode 2
        }
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$sessionDir = Join-Path $repoRoot "artifacts/session/$timestamp"
$logsDir = Join-Path $sessionDir "logs"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$manifestPath = Join-Path $sessionDir "manifest.json"
$readinessPath = Join-Path $sessionDir "readiness_report.json"

$milestones = @(
    (New-MilestoneResult -Id "M0" -Objective "Baseline lock and environment gate"),
    (New-MilestoneResult -Id "M1" -Objective "Headless canonical stack reliability"),
    (New-MilestoneResult -Id "M2" -Objective "Coordinate UAT expansion"),
    (New-MilestoneResult -Id "M3" -Objective "Orientation snapshot UAT"),
    (New-MilestoneResult -Id "M4" -Objective "Nav2 readiness UAT"),
    (New-MilestoneResult -Id "M5" -Objective "Stability and regression cycle"),
    (New-MilestoneResult -Id "M6" -Objective "Pre-LLM readiness package")
)

$resolvedRosDistro = $null
try {
    $resolvedRosDistro = Resolve-RosDistro -Distro $Distro -Requested $RosDistro
}
catch {
    $resolvedRosDistro = $null
}
$effectiveRosDistro = if ($resolvedRosDistro) { $resolvedRosDistro } else { $RosDistro }

$m0 = $milestones[0]
$m0.started_utc = (Get-Date).ToUniversalTime().ToString("o")
$m0.log_file = (Join-Path $logsDir "M0_environment.log")
$m0.command = "sync_runtime_workspace + windows_reinstall_preflight + wsl checks"

$runtimeSync = Invoke-ScriptWithLog `
    -ScriptPath (Join-Path $repoRoot "scripts/sync_runtime_workspace.ps1") `
    -Args @("-Distro", $Distro, "-WorkspacePath", $WorkspacePath, "-RosDistro", $effectiveRosDistro, "-SkipBuild") `
    -LogPath $m0.log_file

$preflight = Invoke-ScriptWithLog `
    -ScriptPath (Join-Path $repoRoot "scripts/windows_reinstall_preflight.ps1") `
    -Args @("-ExpectedDistro", $Distro) `
    -LogPath $m0.log_file

$rosSetupPath = "/opt/ros/$effectiveRosDistro/setup.bash"
$rosCheckParts = @(
    "if [ -f '$rosSetupPath' ]; then source '$rosSetupPath'; fi",
    "if command -v ros2 >/dev/null 2>&1; then echo ROS2_OK=1; else echo ROS2_OK=0; fi",
    "if [ -d /opt/ros ]; then echo ROS_ROOT_OK=1; else echo ROS_ROOT_OK=0; fi",
    "if [ -f '$rosSetupPath' ]; then echo ROS_SETUP_OK=1; else echo ROS_SETUP_OK=0; fi",
    "if [ -d $WorkspacePath ]; then echo WORKSPACE_OK=1; else echo WORKSPACE_OK=0; fi"
)
$rosCheckCmd = ($rosCheckParts -join "; ")

$rosCheckOut = wsl -d $Distro -- bash -lc $rosCheckCmd 2>&1
$rosCheckText = ($rosCheckOut | Out-String).Trim()
Add-Content -Path $m0.log_file -Value ""
Add-Content -Path $m0.log_file -Value "WSL runtime check:"
Add-Content -Path $m0.log_file -Value $rosCheckText

$rosOk = $rosCheckText -match "ROS2_OK=1"
$rosRootOk = $rosCheckText -match "ROS_ROOT_OK=1"
$rosSetupOk = $rosCheckText -match "ROS_SETUP_OK=1"
$workspaceOk = $rosCheckText -match "WORKSPACE_OK=1"

if ($runtimeSync.ExitCode -eq 0 -and $preflight.ExitCode -eq 0 -and $rosOk -and $rosRootOk -and $rosSetupOk -and $workspaceOk) {
    $m0.notes += "Environment checks passed for distro $Distro."
    $m0.notes += "ROS distro resolved to $effectiveRosDistro."
    $m0.notes += "Runtime workspace mirror sync succeeded."
    Complete-Milestone -Milestone $m0 -Status "pass" -ExitCode 0
}
else {
    if ($runtimeSync.ExitCode -ne 0) {
        $m0.notes += "Runtime workspace sync failed."
    }
    if (-not $rosOk) {
        $m0.notes += "ros2 command is missing in $Distro."
    }
    if (-not $rosRootOk) {
        $m0.notes += "/opt/ros directory is missing in $Distro."
    }
    if (-not $rosSetupOk) {
        $m0.notes += "/opt/ros/$effectiveRosDistro/setup.bash not found in $Distro."
    }
    if (-not $workspaceOk) {
        $m0.notes += "Workspace path $WorkspacePath not found in $Distro."
    }
    Complete-Milestone -Milestone $m0 -Status "blocked" -ExitCode 2
    Block-Milestones -StartIndex 1 -EndIndex 5 -Reason "Blocked because M0 environment gate did not pass."
}

if ($m0.status -eq "pass") {
    Run-MilestoneScript -Milestone $milestones[1] -ScriptName "run_canonical_stack.ps1" -Args @(
        "-RuntimeTarget", "robot_fidelity",
        "-Distro", $Distro,
        "-WorkspacePath", $WorkspacePath,
        "-RosDistro", $effectiveRosDistro
    ) -Retries $RetryCount

    if ($milestones[1].status -eq "pass") {
        $soakSeconds = [Math]::Max($SoakMinutes, 1) * 60
        $pids = Get-StackPidsFromArtifact -ArtifactDir $milestones[1].artifact_dir -Distro $Distro
        $health = Test-StackProcessHealth -Distro $Distro -Pids $pids -DurationSeconds $soakSeconds -PollSeconds $SoakProbeSeconds
        $milestones[1].notes += $health.Message
        Stop-Stack -Distro $Distro -Pids $pids -LogFile $milestones[1].log_file
        if (-not $health.Ok) {
            $milestones[1].notes += "M1 failed process health soak."
            Complete-Milestone -Milestone $milestones[1] -Status "fail" -ExitCode 2
            Block-Milestones -StartIndex 2 -EndIndex 5 -Reason "Blocked because M1 soak gate failed."
        }
    }
    else {
        Block-Milestones -StartIndex 2 -EndIndex 5 -Reason "Blocked because M1 launch gate failed."
    }
}

if ($milestones[2].status -eq "pending") {
    Run-MilestoneScript -Milestone $milestones[2] -ScriptName "run_coordinate_uat.ps1" -Args @(
        "-RuntimeTarget", "robot_fidelity",
        "-Distro", $Distro,
        "-WorkspacePath", $WorkspacePath,
        "-RosDistro", $effectiveRosDistro
    ) -Retries $RetryCount
    if ($milestones[2].status -ne "pass") {
        Block-Milestones -StartIndex 3 -EndIndex 5 -Reason "Blocked because M2 coordinate UAT gate failed."
    }
}

if ($milestones[3].status -eq "pending") {
    Run-MilestoneScript -Milestone $milestones[3] -ScriptName "run_orientation_uat.ps1" -Args @(
        "-RuntimeTarget", "robot_fidelity",
        "-Distro", $Distro,
        "-WorkspacePath", $WorkspacePath,
        "-RosDistro", $effectiveRosDistro
    ) -Retries $RetryCount
    if ($milestones[3].status -ne "pass") {
        Block-Milestones -StartIndex 4 -EndIndex 5 -Reason "Blocked because M3 orientation UAT gate failed."
    }
}

if ($milestones[4].status -eq "pending") {
    Run-MilestoneScript -Milestone $milestones[4] -ScriptName "run_nav2_readiness_uat.ps1" -Args @(
        "-RuntimeTarget", "robot_fidelity",
        "-Distro", $Distro,
        "-WorkspacePath", $WorkspacePath,
        "-RosDistro", $effectiveRosDistro,
        "-DurationSeconds", "120"
    ) -Retries $RetryCount
    if ($milestones[4].status -ne "pass") {
        Block-Milestones -StartIndex 5 -EndIndex 5 -Reason "Blocked because M4 Nav2 readiness gate failed."
    }
}

if ($milestones[5].status -eq "pending") {
    $m5 = $milestones[5]
    $m5.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    $m5.log_file = (Join-Path $logsDir "M5_regression.log")
    $m5.command = "regression replay of coordinate/orientation/nav2"
    if ($SkipM5Regression) {
        $m5.notes += "Skipped by flag."
        Complete-Milestone -Milestone $m5 -Status "skipped" -ExitCode 0
    }
    else {
        $m5a = Invoke-ScriptWithLog `
            -ScriptPath (Join-Path $repoRoot "scripts/run_coordinate_uat.ps1") `
            -Args @("-RuntimeTarget", "robot_fidelity", "-Distro", $Distro, "-WorkspacePath", $WorkspacePath, "-RosDistro", $effectiveRosDistro) `
            -LogPath $m5.log_file
        if ($m5a.ArtifactDir) { $m5.notes += "coordinate artifact: $($m5a.ArtifactDir)" }

        $m5b = Invoke-ScriptWithLog `
            -ScriptPath (Join-Path $repoRoot "scripts/run_orientation_uat.ps1") `
            -Args @("-RuntimeTarget", "robot_fidelity", "-Distro", $Distro, "-WorkspacePath", $WorkspacePath, "-RosDistro", $effectiveRosDistro) `
            -LogPath $m5.log_file `
            -AppendLog
        if ($m5b.ArtifactDir) { $m5.notes += "orientation artifact: $($m5b.ArtifactDir)" }

        $m5c = Invoke-ScriptWithLog `
            -ScriptPath (Join-Path $repoRoot "scripts/run_nav2_readiness_uat.ps1") `
            -Args @("-RuntimeTarget", "robot_fidelity", "-Distro", $Distro, "-WorkspacePath", $WorkspacePath, "-RosDistro", $effectiveRosDistro, "-DurationSeconds", "120") `
            -LogPath $m5.log_file `
            -AppendLog
        if ($m5c.ArtifactDir) { $m5.notes += "nav2 artifact: $($m5c.ArtifactDir)" }

        if ($m5a.ExitCode -eq 0 -and $m5b.ExitCode -eq 0 -and $m5c.ExitCode -eq 0) {
            $m5.notes += "Regression replay passed."
            Complete-Milestone -Milestone $m5 -Status "pass" -ExitCode 0
        }
        else {
            $m5.notes += "Regression replay failed."
            Complete-Milestone -Milestone $m5 -Status "fail" -ExitCode 2
        }
    }
}

$m6 = $milestones[6]
$m6.started_utc = (Get-Date).ToUniversalTime().ToString("o")
$m6.log_file = (Join-Path $logsDir "M6_packaging.log")
$m6.command = "assemble readiness package and manifest"

$blockedOrFailed = @($milestones | Where-Object { $_.id -ne "M6" -and $_.status -in @("blocked", "fail") })
$unresolvedIssues = @()
foreach ($m in $blockedOrFailed) {
    $unresolvedIssues += "$($m.id): $($m.objective) -> $($m.status)"
    foreach ($n in $m.notes) {
        $unresolvedIssues += "  - $n"
    }
}

$integrationContract = [ordered]@{
    accepted_high_level_commands = @(
        "acquire_target",
        "plan_to_target",
        "track_target",
        "stop",
        "hold_position"
    )
    ros_interfaces_consumed = @(
        "/yolo/ball_position_3d",
        "/odom",
        "/navigate_to_pose/_action/status",
        "/cmd_vel"
    )
    ros_interfaces_exposed = @(
        "/goal_pose",
        "/cmd_vel",
        "/navigate_to_pose"
    )
    safety_timeouts = [ordered]@{
        detection_stale_s = 2.0
        navigation_goal_timeout_s = 20.0
        command_watchdog_s = 2.0
    }
}

$m6.notes += "Wrote readiness report: $readinessPath"
$m6.notes += "Wrote manifest: $manifestPath"
if ($blockedOrFailed.Count -eq 0) {
    Complete-Milestone -Milestone $m6 -Status "pass" -ExitCode 0
}
else {
    Complete-Milestone -Milestone $m6 -Status "fail" -ExitCode 2
}

$readiness = [ordered]@{
    session_id = $timestamp
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    distro = $Distro
    ros_distro = $effectiveRosDistro
    workspace = $WorkspacePath
    overall_status = if ($blockedOrFailed.Count -eq 0) { "ready_for_gui_rehearsal" } else { "not_ready" }
    milestone_status = $milestones
    unresolved_issues = $unresolvedIssues
    integration_contract = $integrationContract
}
$readiness | ConvertTo-Json -Depth 10 | Set-Content -Path $readinessPath -Encoding UTF8

$manifest = [ordered]@{
    session_id = $timestamp
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    branch = (git -C $repoRoot rev-parse --abbrev-ref HEAD).Trim()
    head_commit = (git -C $repoRoot rev-parse HEAD).Trim()
    plan = "Headless-First UAT Push Plan to Pre-LLM Integration Readiness"
    readiness_report = $readinessPath
    milestones = $milestones
}
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host "Session directory: $sessionDir"
Write-Host "Manifest: $manifestPath"
Write-Host "Readiness report: $readinessPath"
Write-Host ""
foreach ($m in $milestones) {
    Write-Host "$($m.id) [$($m.status)] - $($m.objective)"
}

if ((@($milestones | Where-Object { $_.status -in @("blocked", "fail") }).Count) -gt 0) {
    exit 2
}
exit 0

