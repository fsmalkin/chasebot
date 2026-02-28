param(
    [ValidateSet("fast", "fidelity", "dual")]
    [string]$Lane = "dual",
    [string]$ProjectNamePrefix = "chasecar_gate_prellm",
    [ValidateSet("robot_fidelity_orin", "workstation_balanced", "workstation_max")]
    [string]$FastRuntimeTarget = "workstation_max",
    [ValidateSet("robot_fidelity_orin", "workstation_balanced", "workstation_max")]
    [string]$FidelityRuntimeTarget = "robot_fidelity_orin",
    [int]$FastStepTimeoutSeconds = 420,
    [int]$FidelityStepTimeoutSeconds = 600,
    [int]$FastNav2DurationSeconds = 75,
    [int]$FidelityNav2DurationSeconds = 120,
    [int]$FastMultiTargetGoalTimeoutSeconds = 45,
    [int]$FidelityMultiTargetGoalTimeoutSeconds = 60,
    [string]$FastMultiTargetConfig = "ros2_config/config/multi_target_nav2_fast.yaml",
    [string]$FidelityMultiTargetConfig = "ros2_config/config/multi_target_nav2_fidelity.yaml",
    [double]$SnapshotMinMeanAbsDiff = 1.5,
    [string]$FastWorldFile = "yolo_test_world_v6_clean_uat_fast.world",
    [string]$FidelityWorldFile = "yolo_test_world_v6_clean_uat.world",
    [ValidateSet("auto", "cuda:0", "cpu")]
    [string]$InferenceDevice = "cuda:0",
    [ValidateSet("compat", "balanced", "max")]
    [string]$FastUatProfile = "max",
    [ValidateSet("compat", "balanced", "max")]
    [string]$FidelityUatProfile = "compat",
    [string]$CoreRosDistro = "kilted",
    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",
    [switch]$Build
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Invoke-PSCapture {
    param([string]$ScriptPath, [string[]]$ScriptArgs)

    $stdout = Join-Path $env:TEMP ("pre_llm_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("pre_llm_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
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
    if ($Path -match '^[A-Za-z]:\\') { return $Path }
    if ($Path -match '^/mnt/([a-zA-Z])/(.*)$') {
        $drive = $matches[1].ToUpper()
        $rest = $matches[2] -replace '/', '\\'
        return "$drive`:\$rest"
    }
    if ($Path.StartsWith("/workspaces/chasecar/")) {
        return Join-Path $RepoRoot ($Path.Substring("/workspaces/chasecar/".Length).Replace('/', '\\'))
    }
    if ($Path.StartsWith("artifacts/")) {
        return Join-Path $RepoRoot ($Path.Replace('/', '\\'))
    }
    return $Path
}

function Parse-Marker {
    param([string[]]$Output, [string]$Prefix)
    $line = $Output | Where-Object { $_ -like "$Prefix*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Prefix", "")
}

function Cleanup-StaleProjects {
    param([string]$Prefix, [string]$RepoRoot, [string]$RuntimeTarget, [string]$CoreRosDistro, [string]$InferenceBackend)

    $docker = Resolve-DockerCli
    $dockerBin = Split-Path -Parent $docker
    if ($dockerBin -and -not (($env:Path -split ';') -contains $dockerBin)) {
        $env:Path = "$dockerBin;$env:Path"
    }

    Push-Location $RepoRoot
    try {
        $raw = & $docker compose ls --format json 2>$null
        if ($LASTEXITCODE -ne 0) { return @() }

        $projects = @()
        if ($raw) {
            try {
                $parsed = $raw | ConvertFrom-Json
                if ($parsed -is [System.Array]) { $projects = $parsed } else { $projects = @($parsed) }
            }
            catch {
                foreach ($line in ($raw -split "`r?`n")) {
                    if ($line) {
                        try { $projects += ($line | ConvertFrom-Json) } catch {}
                    }
                }
            }
        }

        $cleaned = @()
        foreach ($proj in ($projects | Where-Object { $_.Name -like "$Prefix*" })) {
            $name = $proj.Name
            Write-Host "Cleaning stale project: $name"
            & (Join-Path $RepoRoot "scripts/run_compose_gate.ps1") -Action down -ProjectName $name -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro | Out-Null
            & (Join-Path $RepoRoot "scripts/run_compose_uat.ps1") -Action down -ProjectName $name -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro | Out-Null
            $cleaned += $name
        }
        return $cleaned
    }
    finally {
        Pop-Location
    }
}

function Invoke-Lane {
    param(
        [string]$LaneName,
        [string]$RuntimeTarget,
        [string]$UatProfile,
        [int]$StepTimeoutSeconds,
        [int]$Nav2DurationSeconds,
        [int]$MultiTargetGoalTimeoutSeconds,
        [string]$MultiTargetConfig,
        [string]$WorldFile,
        [string]$GatePerfProfile,
        [string]$RepoRoot,
        [string]$CoreRosDistro,
        [string]$InferenceBackend,
        [string]$InferenceDevice,
        [double]$SnapshotMinMeanAbsDiff,
        [switch]$Build
    )

    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    $project = "${ProjectNamePrefix}_${LaneName}_${stamp}"

    $result = [ordered]@{
        lane = $LaneName
        project_name = $project
        runtime_target = $RuntimeTarget
        uat_profile = $UatProfile
        step_timeout_s = $StepTimeoutSeconds
        nav2_duration_s = $Nav2DurationSeconds
        multi_target_goal_timeout_s = $MultiTargetGoalTimeoutSeconds
        multi_target_config = $MultiTargetConfig
        world_file = $WorldFile
        gate_perf_profile = $GatePerfProfile
        started_utc = (Get-Date).ToUniversalTime().ToString("o")
        status = "fail"
        artifacts = [ordered]@{
            readiness_report = ""
            session_dir = ""
        }
        notes = @()
    }

    $gateUpOk = $false
    try {
        $gateArgs = @(
            "-Action", "up",
            "-ProjectName", $project,
            "-RuntimeTarget", $RuntimeTarget,
            "-InferenceBackend", $InferenceBackend,
            "-CoreRosDistro", $CoreRosDistro,
            "-IncludeNav2Bringup", "1",
            "-IncludeBridge", "0",
            "-IncludeCmdVelRelay", "1",
            "-GatePerfProfile", $GatePerfProfile,
            "-InferenceDevice", $InferenceDevice,
            "-WorldFile", $WorldFile
        )
        if ($Build) { $gateArgs += "-Build" }

        $up = Invoke-PSCapture -ScriptPath (Join-Path $RepoRoot "scripts/run_compose_gate.ps1") -ScriptArgs $gateArgs
        if ($up.ExitCode -ne 0) {
            $result.notes += "Gate bring-up failed."
            return [pscustomobject]$result
        }
        $gateUpOk = $true

        $uatArgs = @(
            "-Action", "run",
            "-ProjectName", $project,
            "-RuntimeTarget", $RuntimeTarget,
            "-InferenceBackend", $InferenceBackend,
            "-CoreRosDistro", $CoreRosDistro,
            "-UatMode", "pre_llm",
            "-UatExecutionContext", "sim_gate",
            "-StepTimeoutSeconds", $StepTimeoutSeconds,
            "-Nav2DurationSeconds", $Nav2DurationSeconds,
            "-MultiTargetGoalTimeoutSeconds", $MultiTargetGoalTimeoutSeconds,
            "-MultiTargetConfig", $MultiTargetConfig,
            "-SnapshotMinMeanAbsDiff", $SnapshotMinMeanAbsDiff,
            "-UatProfile", $UatProfile,
            "-UatInferenceDevice", $InferenceDevice
        )

        $run = Invoke-PSCapture -ScriptPath (Join-Path $RepoRoot "scripts/run_compose_uat.ps1") -ScriptArgs $uatArgs
        $sessionDirRaw = Parse-Marker -Output $run.Output -Prefix "ARTIFACT_DIR="
        $readinessRaw = Parse-Marker -Output $run.Output -Prefix "READINESS_REPORT="
        $sessionDir = Convert-OrchestratorPath -Path $sessionDirRaw -RepoRoot $RepoRoot
        $readiness = Convert-OrchestratorPath -Path $readinessRaw -RepoRoot $RepoRoot
        $result.artifacts.session_dir = $sessionDir
        $result.artifacts.readiness_report = $readiness

        if ($run.ExitCode -eq 0) {
            $result.status = "pass"
            $result.notes += "pre_llm orchestrator run passed."
        }
        else {
            $result.notes += "pre_llm orchestrator run failed."
        }
        return [pscustomobject]$result
    }
    finally {
        if ($gateUpOk) {
            Invoke-PSCapture -ScriptPath (Join-Path $RepoRoot "scripts/run_compose_gate.ps1") -ScriptArgs @(
                "-Action", "down",
                "-ProjectName", $project,
                "-RuntimeTarget", $RuntimeTarget,
                "-InferenceBackend", $InferenceBackend,
                "-CoreRosDistro", $CoreRosDistro,
                "-IncludeNav2Bringup", "1",
                "-IncludeBridge", "0",
                "-IncludeCmdVelRelay", "1"
            ) | Out-Null

            Invoke-PSCapture -ScriptPath (Join-Path $RepoRoot "scripts/run_compose_uat.ps1") -ScriptArgs @(
                "-Action", "down",
                "-ProjectName", $project,
                "-RuntimeTarget", $RuntimeTarget,
                "-InferenceBackend", $InferenceBackend,
                "-CoreRosDistro", $CoreRosDistro
            ) | Out-Null
        }
        $result.ended_utc = (Get-Date).ToUniversalTime().ToString("o")
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$sessionDir = Join-Path $repoRoot "artifacts/session/$runId"
New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null
$summaryPath = Join-Path $sessionDir "pre_llm_headless_summary.json"

$cleaned = Cleanup-StaleProjects -Prefix $ProjectNamePrefix -RepoRoot $repoRoot -RuntimeTarget $FidelityRuntimeTarget -CoreRosDistro $CoreRosDistro -InferenceBackend $InferenceBackend

$laneResults = @()
if ($Lane -in @("fast", "dual")) {
    $laneResults += Invoke-Lane -LaneName "fast" -RuntimeTarget $FastRuntimeTarget -UatProfile $FastUatProfile -StepTimeoutSeconds $FastStepTimeoutSeconds -Nav2DurationSeconds $FastNav2DurationSeconds -MultiTargetGoalTimeoutSeconds $FastMultiTargetGoalTimeoutSeconds -MultiTargetConfig $FastMultiTargetConfig -WorldFile $FastWorldFile -GatePerfProfile "max" -RepoRoot $repoRoot -CoreRosDistro $CoreRosDistro -InferenceBackend $InferenceBackend -InferenceDevice $InferenceDevice -SnapshotMinMeanAbsDiff $SnapshotMinMeanAbsDiff -Build:$Build
}
if ($Lane -in @("fidelity", "dual")) {
    $laneResults += Invoke-Lane -LaneName "fidelity" -RuntimeTarget $FidelityRuntimeTarget -UatProfile $FidelityUatProfile -StepTimeoutSeconds $FidelityStepTimeoutSeconds -Nav2DurationSeconds $FidelityNav2DurationSeconds -MultiTargetGoalTimeoutSeconds $FidelityMultiTargetGoalTimeoutSeconds -MultiTargetConfig $FidelityMultiTargetConfig -WorldFile $FidelityWorldFile -GatePerfProfile "compat" -RepoRoot $repoRoot -CoreRosDistro $CoreRosDistro -InferenceBackend $InferenceBackend -InferenceDevice $InferenceDevice -SnapshotMinMeanAbsDiff $SnapshotMinMeanAbsDiff -Build:$Build
}

$overallPass = (@($laneResults | Where-Object { $_.status -ne "pass" }).Count -eq 0)
$summary = [ordered]@{
    run_id = $runId
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    mode = $Lane
    inference_backend = $InferenceBackend
    inference_device = $InferenceDevice
    stale_projects_cleaned = $cleaned
    overall_status = if ($overallPass) { "pass" } else { "fail" }
    pre_llm_ready = $overallPass
    lane_results = $laneResults
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host "Summary: $summaryPath"
foreach ($laneResult in $laneResults) {
    Write-Host ("{0}: {1} ({2})" -f $laneResult.lane, $laneResult.status, $laneResult.project_name)
    if ($laneResult.artifacts.readiness_report) {
        Write-Host ("  readiness: {0}" -f $laneResult.artifacts.readiness_report)
    }
}

if ($overallPass) {
    exit 0
}
exit 2
