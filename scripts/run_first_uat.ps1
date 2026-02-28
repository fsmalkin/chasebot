param(
    [string]$Distro = "Ubuntu-24.04",
    [string]$RosDistro = "auto",
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$ProjectName = "",
    [object]$IncludeVisual = $true,
    [ValidateSet("container_kilted", "host_ros")]
    [string]$ExecutionLane = "container_kilted",
    [int]$StepTimeoutMinutes = 20,
    [int]$HeartbeatSeconds = 20,
    [int]$VisualMaxRunSeconds = 90,
    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$WorkspacePath = "~/ros2_ws",
    [string]$CoreRosDistro = "kilted",
    [ValidateSet("sim_gate", "gate_stack", "uat_orchestrator")]
    [string]$UatExecutionContext = "sim_gate"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Convert-ToBoolean {
    param(
        [Parameter(Mandatory = $false)]
        [object]$Value,
        [bool]$Default = $true
    )
    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }
    if ($Value -is [int] -or $Value -is [long]) { return ([int]$Value -ne 0) }
    $text = $Value.ToString().Trim().ToLowerInvariant()
    switch ($text) {
        "true" { return $true }
        "false" { return $false }
        "1" { return $true }
        "0" { return $false }
        "yes" { return $true }
        "no" { return $false }
        default { throw "Invalid boolean value '$Value' for IncludeVisual. Use true/false." }
    }
}

function Resolve-DockerCli {
    $dockerResolved = Get-Command docker -ErrorAction SilentlyContinue
    $docker = $null
    if ($dockerResolved) {
        $docker = $dockerResolved.Source
    }
    if (-not $docker) {
        $fallback = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        if (Test-Path -LiteralPath $fallback) {
            $docker = $fallback
        }
    }
    if (-not $docker) {
        throw "Unable to locate docker CLI."
    }
    $bin = Split-Path -Parent $docker
    if ($bin -and -not (($env:Path -split ';') -contains $bin)) {
        $env:Path = "$bin;$env:Path"
    }
    return $docker
}

function Invoke-CommandCapture {
    param([string]$FilePath, [string[]]$Arguments)
    $stdout = Join-Path $env:TEMP ("first_uat_cmd_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("first_uat_cmd_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        [pscustomobject]@{
            ExitCode = [int]$proc.ExitCode
            Stdout = if (Test-Path -LiteralPath $stdout) { (Get-Content -LiteralPath $stdout | Out-String).Trim() } else { "" }
            Stderr = if (Test-Path -LiteralPath $stderr) { (Get-Content -LiteralPath $stderr | Out-String).Trim() } else { "" }
        }
    }
    finally {
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Get-HostRosDistros {
    param([string]$Distro)
    $raw = wsl -d $Distro -- bash -lc "if [ -d /opt/ros ]; then ls -1 /opt/ros; fi" 2>$null
    return @($raw | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })
}

function Resolve-RosDistro {
    param([string]$Distro, [string]$Requested = "auto")
    if ($Requested -and $Requested -ne "auto") {
        return $Requested
    }
    $cmd = @'
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
    $cmd = $cmd.Replace("`r`n", "`n")
    $out = wsl -d $Distro -- bash -lc $cmd 2>$null
    $val = ($out | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($val)) {
        throw "Unable to resolve ROS distro in $Distro."
    }
    return $val
}

function New-Step {
    param([string]$Id, [string]$Objective)
    [pscustomobject][ordered]@{
        id = $Id
        objective = $Objective
        status = "pending"
        failure_class = ""
        started_utc = $null
        ended_utc = $null
        duration_s = $null
        exit_code = $null
        command = $null
        artifact_dir = $null
        notes = @()
    }
}

function Complete-Step {
    param([object]$Step, [string]$Status, [string]$FailureClass = "", [int]$ExitCode = 0)
    $Step.status = $Status
    $Step.failure_class = $FailureClass
    $Step.exit_code = $ExitCode
    $Step.ended_utc = (Get-Date).ToUniversalTime().ToString("o")
    if ($Step.started_utc) {
        $start = [DateTime]::Parse($Step.started_utc)
        $end = [DateTime]::Parse($Step.ended_utc)
        $Step.duration_s = [Math]::Round(($end - $start).TotalSeconds, 2)
    }
}

function Invoke-PSFile {
    param(
        [string]$ScriptPath,
        [string[]]$ScriptArgs,
        [string]$LogPath,
        [int]$TimeoutSeconds,
        [int]$HeartbeatSeconds,
        [string]$Label
    )
    $stdout = Join-Path $env:TEMP ("first_uat_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("first_uat_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $allOut = @()
    $timedOut = $false
    $exitCode = 2
    try {
        $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ScriptPath) + $ScriptArgs
        $proc = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $start = Get-Date
        $lastBeat = $start
        while (-not $proc.HasExited) {
            Start-Sleep -Seconds 2
            $proc.Refresh()
            $now = Get-Date
            $elapsed = ($now - $start).TotalSeconds
            if ($elapsed -ge [Math]::Max($TimeoutSeconds, 1)) {
                $timedOut = $true
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                break
            }
            if (($now - $lastBeat).TotalSeconds -ge [Math]::Max($HeartbeatSeconds, 10)) {
                $beat = "[heartbeat][$Label] elapsed=$([int]$elapsed)s"
                Write-Host $beat
                Add-Content -Path $LogPath -Value $beat
                $lastBeat = $now
            }
        }
        if (-not $timedOut) {
            $proc.WaitForExit()
            $proc.Refresh()
            $exitCode = [int]$proc.ExitCode
        }
        else {
            $exitCode = 124
            $allOut += "TIMEOUT: $ScriptPath exceeded $TimeoutSeconds seconds and was terminated."
        }
    }
    finally {
        if (Test-Path -LiteralPath $stdout) { $allOut += Get-Content -LiteralPath $stdout }
        if (Test-Path -LiteralPath $stderr) { $allOut += Get-Content -LiteralPath $stderr }
        if ($allOut.Count -gt 0) {
            Add-Content -Path $LogPath -Value $allOut
            foreach ($line in $allOut) { Write-Host $line }
        }
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
    $artifactDir = $null
    $artifactLine = $allOut | Where-Object { $_ -like "ARTIFACT_DIR=*" } | Select-Object -Last 1
    if ($artifactLine) {
        $artifactDir = $artifactLine -replace "^ARTIFACT_DIR=", ""
    }
    [pscustomobject]@{
        ExitCode = $exitCode
        Output = $allOut
        TimedOut = $timedOut
        ArtifactDir = $artifactDir
    }
}

function Convert-OrchestratorPath {
    param([string]$Path, [string]$RepoRoot)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    if ($Path -match '^[A-Za-z]:\\') { return $Path }
    if ($Path -match '^/mnt/([a-zA-Z])/(.*)$') {
        $drive = $matches[1].ToUpper()
        $rest = $matches[2] -replace '/', '\'
        return "$drive`:\$rest"
    }
    if ($Path.StartsWith("/workspaces/chasecar/")) {
        return Join-Path $RepoRoot ($Path.Substring("/workspaces/chasecar/".Length).Replace('/', '\'))
    }
    if ($Path.StartsWith("artifacts/") -or $Path.StartsWith("docs/") -or $Path.StartsWith("scripts/")) {
        return Join-Path $RepoRoot ($Path.Replace('/', '\'))
    }
    return $Path
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

function Test-VisualEvidence {
    param([string]$EvidenceDir)
    if ([string]::IsNullOrWhiteSpace($EvidenceDir)) { return $false }
    $required = @(
        (Join-Path $EvidenceDir "operator_checklist.json"),
        (Join-Path $EvidenceDir "demo_summary.json"),
        (Join-Path $EvidenceDir "screenshots\d415_color.png"),
        (Join-Path $EvidenceDir "screenshots\yolo_debug.png")
    )
    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path)) { return $false }
    }
    return $true
}

function Get-DemoPids {
    param([string]$ArtifactDir)
    $path = Join-Path $ArtifactDir "demo_pids.json"
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    try {
        $json = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    }
    catch {
        return @()
    }
    $allPids = @(
        $json.pids.sim,
        $json.pids.detector,
        $json.pids.extractor,
        $json.pids.bridge,
        $json.pids.nav2,
        $json.pids.cmd_vel_relay,
        $json.pids.feed_rgb_viewer,
        $json.pids.feed_debug_viewer
    )
    return $allPids |
        Where-Object { $_ -and $_.ToString() -match '^\d+$' } |
        ForEach-Object { $_.ToString() } |
        Select-Object -Unique
}

function Stop-WslPids {
    param([string]$Distro, [string[]]$Pids, [string]$LogPath)
    if (-not $Pids -or $Pids.Count -eq 0) { return }
    $pidArg = ($Pids -join " ")
    Add-Content -Path $LogPath -Value "Stopping WSL pids: $pidArg"
    wsl -d $Distro -- bash -lc "kill $pidArg 2>/dev/null || true" | Out-Null
}

function Cleanup-WslStack {
    param([string]$Distro)
    $cmd = @'
pkill -f "jetbot_gz_control_camera_test_v5.launch.py" 2>/dev/null || true
pkill -f "chasecar_tensorrt_detector.py" 2>/dev/null || true
pkill -f "yolo_3d_position_extractor.py" 2>/dev/null || true
pkill -f "yolo_3d_to_nav2_bridge.py" 2>/dev/null || true
pkill -f "jetbot_nav2_complete.launch.py" 2>/dev/null || true
pkill -f "cmd_vel_relay.py" 2>/dev/null || true
pkill -f "gz sim -v" 2>/dev/null || true
pkill -f "gz sim server" 2>/dev/null || true
pkill -f "ign gazebo" 2>/dev/null || true
'@
    $cmd = $cmd.Replace("`r`n", "`n")
    wsl -d $Distro -- bash -lc $cmd 2>$null | Out-Null
}

$runtimeAliases = @{ robot_fidelity = "robot_fidelity_orin" }
if ($runtimeAliases.ContainsKey($RuntimeTarget)) { $RuntimeTarget = $runtimeAliases[$RuntimeTarget] }
$IncludeVisual = Convert-ToBoolean -Value $IncludeVisual -Default $true

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$sessionDir = Join-Path $repoRoot "artifacts/session/$timestamp"
$logsDir = Join-Path $sessionDir "logs"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$manifestPath = Join-Path $sessionDir "manifest.json"
$readinessPath = Join-Path $sessionDir "readiness_report.json"
$sessionLog = Join-Path $logsDir "run_first_uat.log"
Set-Content -Path $sessionLog -Value @("First UAT session start: $((Get-Date).ToUniversalTime().ToString('o'))")

$docker = Resolve-DockerCli
$dockerInfo = Invoke-CommandCapture -FilePath $docker -Arguments @("info", "--format", "{{.ServerVersion}}")
$dockerReady = ($dockerInfo.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($dockerInfo.Stdout))

$detectedHostRos = @(Get-HostRosDistros -Distro $Distro)
$resolvedHostRos = $null
try { $resolvedHostRos = Resolve-RosDistro -Distro $Distro -Requested $RosDistro } catch { $resolvedHostRos = $null }

$stepTimeoutS = [Math]::Max($StepTimeoutMinutes, 1) * 60
$heartbeat = [Math]::Max($HeartbeatSeconds, 10)
$projectStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
$resolvedProjectName = if ([string]::IsNullOrWhiteSpace($ProjectName)) { "chasecar_gate_firstuat_$projectStamp" } else { $ProjectName }

$steps = @(
    (New-Step -Id "S0" -Objective "Pre-run stale compose project scan and cleanup"),
    (New-Step -Id "S1" -Objective "Bring up compose gate lane with Nav2 disabled"),
    (New-Step -Id "S2" -Objective "Run coordinate UAT and validate pass artifact"),
    (New-Step -Id "S3" -Objective "Run milestone 1 visual demo and capture evidence"),
    (New-Step -Id "S4" -Objective "Tear down compose gate lane and package reports")
)

$coordinateArtifactDir = $null
$coordinateSummaryPath = $null
$coordinatePass = $false
$visualArtifactDir = $null
$visualPass = $false
$orchestratorReadiness = $null
$staleFound = @()
$staleCleaned = @()
$originalNav2Env = $env:GATE_INCLUDE_NAV2_BRINGUP

try {
    $s0 = $steps[0]
    $s0.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    $s0.command = "docker compose ls + stale cleanup"
    if (-not $dockerReady) {
        $s0.notes += "Docker daemon unavailable."
        Complete-Step -Step $s0 -Status "fail" -FailureClass "docker_unavailable" -ExitCode 2
    }
    else {
        $raw = & $docker compose ls --format json 2>$null
        $projects = @()
        if ($LASTEXITCODE -eq 0 -and $raw) {
            try {
                $parsed = $raw | ConvertFrom-Json
                if ($parsed -is [System.Array]) { $projects = $parsed } else { $projects = @($parsed) }
            }
            catch {
                foreach ($line in ($raw -split "`r?`n")) {
                    if (-not [string]::IsNullOrWhiteSpace($line)) {
                        try { $projects += ($line | ConvertFrom-Json) } catch {}
                    }
                }
            }
        }
        $stale = @($projects | Where-Object {
            $_.Name -like "chasecar_gate_*" -and $_.Name -ne $resolvedProjectName -and ($_.Status -notmatch "exited|stopped")
        })
        foreach ($proj in $stale) {
            $staleFound += $proj.Name
            $cleanupGate = Invoke-PSFile `
                -ScriptPath (Join-Path $repoRoot "scripts/run_compose_gate.ps1") `
                -ScriptArgs @("-Action", "down", "-ProjectName", $proj.Name, "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-CoreRosDistro", $CoreRosDistro) `
                -LogPath $sessionLog `
                -TimeoutSeconds $stepTimeoutS `
                -HeartbeatSeconds $heartbeat `
                -Label "S0-cleanup-$($proj.Name)"
            $cleanupUat = Invoke-PSFile `
                -ScriptPath (Join-Path $repoRoot "scripts/run_compose_uat.ps1") `
                -ScriptArgs @("-Action", "down", "-ProjectName", $proj.Name, "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-CoreRosDistro", $CoreRosDistro) `
                -LogPath $sessionLog `
                -TimeoutSeconds $stepTimeoutS `
                -HeartbeatSeconds $heartbeat `
                -Label "S0-cleanup-uat-$($proj.Name)"
            if ($cleanupGate.ExitCode -eq 0 -and $cleanupUat.ExitCode -eq 0) { $staleCleaned += $proj.Name }
        }
        if ($staleFound.Count -eq 0 -or $staleFound.Count -eq $staleCleaned.Count) {
            if ($staleFound.Count -eq 0) { $s0.notes += "No stale gate projects detected." }
            else { $s0.notes += "Cleaned stale gate projects: $($staleCleaned -join ', ')" }
            Complete-Step -Step $s0 -Status "pass" -ExitCode 0
        }
        else {
            Complete-Step -Step $s0 -Status "fail" -FailureClass "cleanup_failed" -ExitCode 2
        }
    }

    $s1 = $steps[1]
    $s1.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    $s1.command = "run_compose_gate.ps1 -Action up -ProjectName $resolvedProjectName"
    if ($steps[0].status -ne "pass") {
        $s1.notes += "Blocked by S0."
        Complete-Step -Step $s1 -Status "blocked" -FailureClass "blocked_dependency" -ExitCode 2
    }
    else {
        $env:GATE_INCLUDE_NAV2_BRINGUP = "false"
        $up = Invoke-PSFile `
            -ScriptPath (Join-Path $repoRoot "scripts/run_compose_gate.ps1") `
            -ScriptArgs @("-Action", "up", "-ProjectName", $resolvedProjectName, "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-CoreRosDistro", $CoreRosDistro) `
            -LogPath $sessionLog `
            -TimeoutSeconds $stepTimeoutS `
            -HeartbeatSeconds $heartbeat `
            -Label "S1-gate-up"
        if ($up.ExitCode -eq 0) {
            $s1.notes += "Gate lane up."
            Complete-Step -Step $s1 -Status "pass" -ExitCode 0
        }
        else {
            Complete-Step -Step $s1 -Status "fail" -FailureClass ($(if ($up.TimedOut) { "timeout" } else { "command_failed" })) -ExitCode $up.ExitCode
        }
    }

    $s2 = $steps[2]
    $s2.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    if ($ExecutionLane -eq "container_kilted") {
        $s2.command = "run_compose_uat.ps1 -Action run -ProjectName $resolvedProjectName -UatMode coordinate -UatExecutionContext $UatExecutionContext"
    }
    else {
        $s2.command = "run_coordinate_uat.ps1 -RuntimeTarget $RuntimeTarget -RosDistro $resolvedHostRos"
    }
    if ($steps[1].status -ne "pass") {
        $s2.notes += "Blocked by S1."
        Complete-Step -Step $s2 -Status "blocked" -FailureClass "blocked_dependency" -ExitCode 2
    }
    else {
        if ($ExecutionLane -eq "container_kilted") {
            $coord = Invoke-PSFile `
                -ScriptPath (Join-Path $repoRoot "scripts/run_compose_uat.ps1") `
                -ScriptArgs @("-Action", "run", "-ProjectName", $resolvedProjectName, "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-CoreRosDistro", $CoreRosDistro, "-UatMode", "coordinate", "-UatExecutionContext", $UatExecutionContext, "-StepTimeoutSeconds", $stepTimeoutS.ToString()) `
                -LogPath $sessionLog `
                -TimeoutSeconds $stepTimeoutS `
                -HeartbeatSeconds $heartbeat `
                -Label "S2-coordinate-container"
            $marker = Parse-StepMarker -Output $coord.Output -StepName "coordinate"
            if ($marker) {
                $coordinateArtifactDir = Convert-OrchestratorPath -Path $marker.Artifact -RepoRoot $repoRoot
                $coordinateSummaryPath = Join-Path $coordinateArtifactDir "summary.json"
                $s2.artifact_dir = $coordinateArtifactDir
                $coordinatePass = ($marker.Status -eq "pass")
            }
            $coordinateSummary = $null
            if ($coordinateSummaryPath -and (Test-Path -LiteralPath $coordinateSummaryPath)) {
                try { $coordinateSummary = Get-Content -LiteralPath $coordinateSummaryPath -Raw | ConvertFrom-Json } catch {}
            }
            if ($coordinateSummary -and ($coordinateSummary.PSObject.Properties.Name -contains "pass")) {
                $coordinatePass = [bool]$coordinateSummary.pass
            }
            $rr = $coord.Output | Where-Object { $_ -like "READINESS_REPORT=*" } | Select-Object -Last 1
            $orchestratorFailureClass = ""
            if ($rr) {
                $orchestratorReadiness = Convert-OrchestratorPath -Path ($rr -replace "^READINESS_REPORT=", "") -RepoRoot $repoRoot
                if ($orchestratorReadiness -and (Test-Path -LiteralPath $orchestratorReadiness)) {
                    try {
                        $orJson = Get-Content -LiteralPath $orchestratorReadiness -Raw | ConvertFrom-Json
                        $coordStep = $orJson.steps | Where-Object { $_.id -eq "coordinate" } | Select-Object -First 1
                        if ($coordStep -and $coordStep.failure_class) {
                            $orchestratorFailureClass = $coordStep.failure_class.ToString()
                        }
                    }
                    catch {}
                }
            }
            if ($coord.ExitCode -eq 0 -and $coordinatePass) {
                Complete-Step -Step $s2 -Status "pass" -ExitCode 0
            }
            else {
                $fc = if ($coord.TimedOut) {
                    "timeout"
                }
                elseif (-not $marker) {
                    "missing_artifact"
                }
                elseif ($coordinateSummary -and ($coordinateSummary.PSObject.Properties.Name -contains "pass") -and -not [bool]$coordinateSummary.pass) {
                    "threshold_failed"
                }
                elseif ($marker.Status -ne "pass") {
                    "gate_failed"
                }
                else {
                    "command_failed"
                }
                if (-not [string]::IsNullOrWhiteSpace($orchestratorFailureClass)) {
                    $fc = $orchestratorFailureClass
                }
                $effectiveExit = if (($coord.ExitCode -eq 0) -and $marker -and ($marker.Status -ne "pass")) { 2 } else { $coord.ExitCode }
                Complete-Step -Step $s2 -Status "fail" -FailureClass $fc -ExitCode $effectiveExit
            }
        }
        else {
            if ([string]::IsNullOrWhiteSpace($resolvedHostRos)) {
                Complete-Step -Step $s2 -Status "fail" -FailureClass "host_ros_missing" -ExitCode 2
            }
            else {
                $coord = Invoke-PSFile `
                    -ScriptPath (Join-Path $repoRoot "scripts/run_coordinate_uat.ps1") `
                    -ScriptArgs @("-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-Distro", $Distro, "-WorkspacePath", $WorkspacePath, "-RosDistro", $resolvedHostRos) `
                    -LogPath $sessionLog `
                    -TimeoutSeconds $stepTimeoutS `
                    -HeartbeatSeconds $heartbeat `
                    -Label "S2-coordinate-host"
                $coordinateArtifactDir = $coord.ArtifactDir
                if ($coordinateArtifactDir) {
                    $coordinateSummaryPath = if ($coordinateArtifactDir -like "/*") { "$coordinateArtifactDir/summary.json" } else { Join-Path $coordinateArtifactDir "summary.json" }
                    $s2.artifact_dir = $coordinateArtifactDir
                }
                $summary = $null
                if ($coordinateSummaryPath) {
                    if ($coordinateSummaryPath -like "/*") {
                        $esc = $coordinateSummaryPath.Replace("'", "'\''")
                        $rawSummary = wsl -d $Distro -- bash -lc "if [ -f '$esc' ]; then cat '$esc'; fi"
                        if ($rawSummary) { try { $summary = ($rawSummary | ConvertFrom-Json) } catch {} }
                    }
                    elseif (Test-Path -LiteralPath $coordinateSummaryPath) {
                        try { $summary = Get-Content -LiteralPath $coordinateSummaryPath -Raw | ConvertFrom-Json } catch {}
                    }
                }
                if ($summary -and ($summary.PSObject.Properties.Name -contains "pass")) { $coordinatePass = [bool]$summary.pass }
                elseif ($coord.ExitCode -eq 0) { $coordinatePass = $true }

                if ($coord.ExitCode -eq 0 -and $coordinatePass) {
                    Complete-Step -Step $s2 -Status "pass" -ExitCode 0
                }
                else {
                    Complete-Step -Step $s2 -Status "fail" -FailureClass ($(if ($coord.TimedOut) { "timeout" } else { "command_failed" })) -ExitCode $coord.ExitCode
                }
            }
        }
    }

    $s3 = $steps[3]
    $s3.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    $s3.command = "run_milestone_demo.ps1 -Milestone 1"
    if (-not $IncludeVisual) {
        Complete-Step -Step $s3 -Status "skipped" -ExitCode 0
    }
    elseif (-not $coordinatePass) {
        $s3.notes += "Blocked by S2 coordinate gate."
        Complete-Step -Step $s3 -Status "blocked" -FailureClass "blocked_dependency" -ExitCode 2
    }
    else {
        $visualArtifactDir = Join-Path $repoRoot "artifacts/demos/milestone_1_$timestamp"
        New-Item -ItemType Directory -Path $visualArtifactDir -Force | Out-Null
        $rosForVisual = if ($ExecutionLane -eq "host_ros") { $resolvedHostRos } else { "auto" }
        $m1 = Invoke-PSFile `
            -ScriptPath (Join-Path $repoRoot "scripts/run_milestone_demo.ps1") `
            -ScriptArgs @("-Milestone", "1", "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-Distro", $Distro, "-WorkspacePath", $WorkspacePath, "-RosDistro", $rosForVisual, "-EvidenceDir", $visualArtifactDir, "-MaxRunSeconds", $VisualMaxRunSeconds.ToString()) `
            -LogPath $sessionLog `
            -TimeoutSeconds $stepTimeoutS `
            -HeartbeatSeconds $heartbeat `
            -Label "S3-visual-m1"
        if ($m1.ArtifactDir) { $visualArtifactDir = Convert-OrchestratorPath -Path $m1.ArtifactDir -RepoRoot $repoRoot }
        $s3.artifact_dir = $visualArtifactDir
        $pids = Get-DemoPids -ArtifactDir $visualArtifactDir
        Stop-WslPids -Distro $Distro -Pids $pids -LogPath $sessionLog
        if ($m1.ExitCode -eq 0 -and (Test-VisualEvidence -EvidenceDir $visualArtifactDir)) {
            $demoSummaryPath = Join-Path $visualArtifactDir "demo_summary.json"
            $demo = $null
            if (Test-Path -LiteralPath $demoSummaryPath) { try { $demo = Get-Content -LiteralPath $demoSummaryPath -Raw | ConvertFrom-Json } catch {} }
            $visualPass = if ($demo -and ($demo.PSObject.Properties.Name -contains "pass")) { [bool]$demo.pass } else { $true }
            if ($visualPass) {
                Complete-Step -Step $s3 -Status "pass" -ExitCode 0
            }
            else {
                Complete-Step -Step $s3 -Status "fail" -FailureClass "visual_failed" -ExitCode 2
            }
        }
        else {
            Complete-Step -Step $s3 -Status "fail" -FailureClass ($(if ($m1.TimedOut) { "timeout" } else { "missing_artifact" })) -ExitCode $m1.ExitCode
        }
    }
}
finally {
    Cleanup-WslStack -Distro $Distro
    $s4 = $steps[4]
    $s4.started_utc = (Get-Date).ToUniversalTime().ToString("o")
    $s4.command = "run_compose_gate.ps1 -Action down -ProjectName $resolvedProjectName"
    if ($dockerReady) {
        $downGate = Invoke-PSFile `
            -ScriptPath (Join-Path $repoRoot "scripts/run_compose_gate.ps1") `
            -ScriptArgs @("-Action", "down", "-ProjectName", $resolvedProjectName, "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-CoreRosDistro", $CoreRosDistro) `
            -LogPath $sessionLog `
            -TimeoutSeconds $stepTimeoutS `
            -HeartbeatSeconds $heartbeat `
            -Label "S4-gate-down"
        $downUat = Invoke-PSFile `
            -ScriptPath (Join-Path $repoRoot "scripts/run_compose_uat.ps1") `
            -ScriptArgs @("-Action", "down", "-ProjectName", $resolvedProjectName, "-RuntimeTarget", $RuntimeTarget, "-InferenceBackend", $InferenceBackend, "-CoreRosDistro", $CoreRosDistro) `
            -LogPath $sessionLog `
            -TimeoutSeconds $stepTimeoutS `
            -HeartbeatSeconds $heartbeat `
            -Label "S4-uat-down"
        if ($downGate.ExitCode -eq 0 -and $downUat.ExitCode -eq 0) {
            Complete-Step -Step $s4 -Status "pass" -ExitCode 0
        }
        else {
            $downTimedOut = $downGate.TimedOut -or $downUat.TimedOut
            $downExit = if ($downUat.ExitCode -ne 0) { $downUat.ExitCode } else { $downGate.ExitCode }
            Complete-Step -Step $s4 -Status "fail" -FailureClass ($(if ($downTimedOut) { "timeout" } else { "command_failed" })) -ExitCode $downExit
        }
    }
    else {
        Complete-Step -Step $s4 -Status "skipped" -ExitCode 0
    }
    if ($null -eq $originalNav2Env) { Remove-Item Env:\GATE_INCLUDE_NAV2_BRINGUP -ErrorAction SilentlyContinue } else { $env:GATE_INCLUDE_NAV2_BRINGUP = $originalNav2Env }
}

$firstUatComplete = $coordinatePass -and ((-not $IncludeVisual) -or $visualPass)
$overall = if ($firstUatComplete) { "pass" } else { "fail" }
$firstFailure = $steps | Where-Object { $_.status -eq "fail" } | Select-Object -First 1

$readiness = [ordered]@{
    session_id = $timestamp
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    status = $overall
    first_uat_complete = $firstUatComplete
    execution_lane = $ExecutionLane
    failure_class = if ($firstFailure) { $firstFailure.failure_class } else { "" }
    step_timeout_s = $stepTimeoutS
    container_core_ros_distro = $CoreRosDistro
    detected_host_ros_distros = $detectedHostRos
    inputs = [ordered]@{
        distro = $Distro
        ros_distro = if ($ExecutionLane -eq "host_ros") { $resolvedHostRos } else { $CoreRosDistro }
        runtime_target = $RuntimeTarget
        inference_backend = $InferenceBackend
        uat_execution_context = $UatExecutionContext
        workspace_path = $WorkspacePath
        project_name = $resolvedProjectName
        include_visual = $IncludeVisual
    }
    artifacts = [ordered]@{
        coordinate_artifact_dir = $coordinateArtifactDir
        coordinate_summary = $coordinateSummaryPath
        milestone_1_evidence_dir = $visualArtifactDir
        orchestrator_readiness_report = $orchestratorReadiness
    }
    stale_compose_cleanup = [ordered]@{
        found = $staleFound
        cleaned = $staleCleaned
    }
    steps = $steps
}
$readiness | ConvertTo-Json -Depth 12 | Set-Content -Path $readinessPath -Encoding UTF8

$manifest = [ordered]@{
    session_id = $timestamp
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    branch = (git -C $repoRoot rev-parse --abbrev-ref HEAD).Trim()
    head_commit = (git -C $repoRoot rev-parse HEAD).Trim()
    script = "scripts/run_first_uat.ps1"
    readiness_report = $readinessPath
    logs = $logsDir
    execution_lane = $ExecutionLane
    coordinate_artifact_dir = $coordinateArtifactDir
    milestone_1_evidence_dir = $visualArtifactDir
}
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host "Session directory: $sessionDir"
Write-Host "Manifest: $manifestPath"
Write-Host "Readiness report: $readinessPath"
Write-Host "First UAT complete: $firstUatComplete"

if ($firstUatComplete) { exit 0 }
exit 2
