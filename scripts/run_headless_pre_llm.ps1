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
    [string]$FastNav2Config = "ros2_config/config/nav2_readiness_fast.yaml",
    [string]$FidelityNav2Config = "ros2_config/config/nav2_readiness_fidelity.yaml",
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
        [string]$Nav2Config,
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
        nav2_config = $Nav2Config
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
        readiness = [ordered]@{
            status = "unknown"
            pass = $false
            pre_llm_ready = $false
            failure_class = $null
            failure_class_counts = @{}
            stage_timing_s = @{}
            stage_retry_counts = @{}
            evidence_complete = $false
            unresolved_issues = @()
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
            "-Nav2Config", $Nav2Config,
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

        $readinessPass = $false
        if (-not [string]::IsNullOrWhiteSpace($readiness) -and (Test-Path -LiteralPath $readiness)) {
            try {
                $readinessObj = Get-Content -LiteralPath $readiness -Raw | ConvertFrom-Json
                $result.readiness.status = [string]($readinessObj.status)
                $result.readiness.pass = [bool]$readinessObj.pass
                $result.readiness.pre_llm_ready = [bool]$readinessObj.pre_llm_ready
                $result.readiness.failure_class = $readinessObj.failure_class
                $result.readiness.failure_class_counts = if ($null -ne $readinessObj.failure_class_counts) { $readinessObj.failure_class_counts } else { @{} }
                $result.readiness.stage_timing_s = if ($null -ne $readinessObj.stage_timing_s) { $readinessObj.stage_timing_s } else { @{} }
                $result.readiness.stage_retry_counts = if ($null -ne $readinessObj.stage_retry_counts) { $readinessObj.stage_retry_counts } else { @{} }
                $result.readiness.evidence_complete = [bool]$readinessObj.evidence_complete
                $result.readiness.unresolved_issues = if ($null -ne $readinessObj.unresolved_issues) { @($readinessObj.unresolved_issues) } else { @() }
                $readinessPass = [bool]$readinessObj.pass
            }
            catch {
                $result.notes += "Failed to parse readiness report."
            }
        }
        else {
            $result.notes += "Readiness report missing."
        }

        if ($run.ExitCode -eq 0 -and $readinessPass) {
            $result.status = "pass"
            $result.notes += "pre_llm orchestrator run passed."
        }
        else {
            if ($run.ExitCode -ne 0) {
                $result.notes += "pre_llm orchestrator run failed."
            }
            if (-not $readinessPass) {
                $result.notes += "readiness report indicates failure."
            }
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
    $laneResults += Invoke-Lane -LaneName "fast" -RuntimeTarget $FastRuntimeTarget -UatProfile $FastUatProfile -StepTimeoutSeconds $FastStepTimeoutSeconds -Nav2DurationSeconds $FastNav2DurationSeconds -Nav2Config $FastNav2Config -MultiTargetGoalTimeoutSeconds $FastMultiTargetGoalTimeoutSeconds -MultiTargetConfig $FastMultiTargetConfig -WorldFile $FastWorldFile -GatePerfProfile "max" -RepoRoot $repoRoot -CoreRosDistro $CoreRosDistro -InferenceBackend $InferenceBackend -InferenceDevice $InferenceDevice -SnapshotMinMeanAbsDiff $SnapshotMinMeanAbsDiff -Build:$Build
}
if ($Lane -in @("fidelity", "dual")) {
    $laneResults += Invoke-Lane -LaneName "fidelity" -RuntimeTarget $FidelityRuntimeTarget -UatProfile $FidelityUatProfile -StepTimeoutSeconds $FidelityStepTimeoutSeconds -Nav2DurationSeconds $FidelityNav2DurationSeconds -Nav2Config $FidelityNav2Config -MultiTargetGoalTimeoutSeconds $FidelityMultiTargetGoalTimeoutSeconds -MultiTargetConfig $FidelityMultiTargetConfig -WorldFile $FidelityWorldFile -GatePerfProfile "compat" -RepoRoot $repoRoot -CoreRosDistro $CoreRosDistro -InferenceBackend $InferenceBackend -InferenceDevice $InferenceDevice -SnapshotMinMeanAbsDiff $SnapshotMinMeanAbsDiff -Build:$Build
}

$overallPass = (@($laneResults | Where-Object { $_.status -ne "pass" }).Count -eq 0)
$failureClassCounts = @{}
$stageTimingByLane = [ordered]@{}
$stageRetryByLane = [ordered]@{}
$unresolvedIssues = @()

foreach ($laneResult in $laneResults) {
    $laneName = [string]$laneResult.lane
    $stageTimingByLane[$laneName] = if ($null -ne $laneResult.readiness.stage_timing_s) { $laneResult.readiness.stage_timing_s } else { @{} }
    $stageRetryByLane[$laneName] = if ($null -ne $laneResult.readiness.stage_retry_counts) { $laneResult.readiness.stage_retry_counts } else { @{} }

    if ($null -ne $laneResult.readiness.failure_class_counts) {
        $counts = $laneResult.readiness.failure_class_counts
        if ($counts -is [System.Collections.IDictionary]) {
            foreach ($key in @($counts.Keys)) {
                $name = [string]$key
                $raw = $counts[$key]
                $val = 0
                if ($null -ne $raw -and [int]::TryParse($raw.ToString(), [ref]$val)) {
                    if (-not $failureClassCounts.ContainsKey($name)) {
                        $failureClassCounts[$name] = 0
                    }
                    $failureClassCounts[$name] += $val
                }
            }
        }
        else {
            foreach ($prop in $counts.PSObject.Properties) {
                $name = [string]$prop.Name
                $val = 0
                if ($null -ne $prop.Value -and [int]::TryParse($prop.Value.ToString(), [ref]$val)) {
                    if (-not $failureClassCounts.ContainsKey($name)) {
                        $failureClassCounts[$name] = 0
                    }
                    $failureClassCounts[$name] += $val
                }
            }
        }
    }

    if ($laneResult.status -ne "pass") {
        if ($laneResult.readiness.unresolved_issues -and @($laneResult.readiness.unresolved_issues).Count -gt 0) {
            foreach ($issue in @($laneResult.readiness.unresolved_issues)) {
                $unresolvedIssues += [ordered]@{
                    lane = $laneName
                    issue = $issue
                }
            }
        }
        else {
            $unresolvedIssues += [ordered]@{
                lane = $laneName
                issue = "Unknown failure. Check readiness report."
            }
        }
    }
}

$allowedFailureClasses = @("service_unavailable", "timeout", "missing_artifact", "threshold_failed", "blocked_dependency")
$allFailureClassesObserved = @($failureClassCounts.Keys | Sort-Object)
$summary = [ordered]@{
    run_id = $runId
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    mode = $Lane
    inference_backend = $InferenceBackend
    inference_device = $InferenceDevice
    stale_projects_cleaned = $cleaned
    overall_status = if ($overallPass) { "pass" } else { "fail" }
    pre_llm_ready = $overallPass
    failure_class_catalog = $allowedFailureClasses
    failure_class_counts = $failureClassCounts
    observed_failure_classes = $allFailureClassesObserved
    stage_timing_s_by_lane = $stageTimingByLane
    stage_retry_counts_by_lane = $stageRetryByLane
    unresolved_issues = $unresolvedIssues
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
