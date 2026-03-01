param(
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [ValidateSet("compat", "balanced", "max")]
    [string]$UatProfile = "compat",
    [string]$CoreRosDistro = "kilted",
    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",
    [ValidateSet("auto", "cuda:0", "cpu")]
    [string]$InferenceDevice = "cuda:0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-PSCapture {
    param([string]$ScriptPath, [string[]]$ScriptArgs)

    $stdout = Join-Path $env:TEMP ("pre_llm_adv_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("pre_llm_adv_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
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

function Parse-Marker {
    param([string[]]$Output, [string]$Prefix)
    $line = $Output | Where-Object { $_ -like "$Prefix*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Prefix", "")
}

function Convert-OrchestratorPath {
    param([string]$Path, [string]$RepoRoot)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    $normalized = [regex]::Replace($Path, '\\\\+', '\')
    if ($normalized -match '^[A-Za-z]:\\') { return $normalized }
    if ($normalized -match '^/mnt/([a-zA-Z])/(.*)$') {
        $drive = $matches[1].ToUpper()
        $rest = $matches[2] -replace '/', '\'
        return "$drive`:\$rest"
    }
    if ($normalized.StartsWith("/workspaces/chasecar/")) {
        return Join-Path $RepoRoot ($normalized.Substring("/workspaces/chasecar/".Length).Replace('/', '\'))
    }
    if ($normalized.StartsWith("artifacts/")) {
        return Join-Path $RepoRoot ($normalized.Replace('/', '\'))
    }
    return $normalized
}

function Set-EnvOverrides {
    param([hashtable]$Overrides)

    $backup = @{}
    foreach ($key in $Overrides.Keys) {
        $envItem = Get-Item -Path "Env:$key" -ErrorAction SilentlyContinue
        if ($envItem) {
            $backup[$key] = [ordered]@{ exists = $true; value = $envItem.Value }
        }
        else {
            $backup[$key] = [ordered]@{ exists = $false; value = "" }
        }
        Set-Item -Path "Env:$key" -Value ([string]$Overrides[$key])
    }
    return $backup
}

function Restore-EnvOverrides {
    param([hashtable]$Backup)

    foreach ($key in $Backup.Keys) {
        $entry = $Backup[$key]
        if ([bool]$entry.exists) {
            Set-Item -Path "Env:$key" -Value ([string]$entry.value)
        }
        else {
            Remove-Item -Path "Env:$key" -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-AdversarialCase {
    param(
        [hashtable]$Case,
        [string]$RepoRoot,
        [string]$RuntimeTarget,
        [string]$CoreRosDistro,
        [string]$InferenceBackend,
        [string]$InferenceDevice,
        [string]$UatProfile
    )

    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    $project = "chasecar_gate_adv_$($Case.id)_$stamp"
    $result = [ordered]@{
        id = $Case.id
        description = $Case.description
        expected_failure_class = $Case.expected_failure_class
        expected_step_status = "fail"
        project_name = $project
        status = "fail"
        assertions = @()
        artifacts = [ordered]@{
            readiness_report = ""
            artifact_dir = ""
        }
    }

    $envBackup = @{}
    $gateUp = $false
    try {
        if ($Case.ContainsKey("env_overrides") -and $Case.env_overrides.Count -gt 0) {
            $envBackup = Set-EnvOverrides -Overrides $Case.env_overrides
        }

        $up = Invoke-PSCapture -ScriptPath (Join-Path $RepoRoot "scripts/run_compose_gate.ps1") -ScriptArgs @(
            "-Action", "up",
            "-ProjectName", $project,
            "-RuntimeTarget", $RuntimeTarget,
            "-InferenceBackend", $InferenceBackend,
            "-CoreRosDistro", $CoreRosDistro,
            "-IncludeNav2Bringup", "1",
            "-IncludeBridge", "0",
            "-IncludeCmdVelRelay", "1",
            "-InferenceDevice", $InferenceDevice
        )
        if ($up.ExitCode -ne 0) {
            $result.assertions += [ordered]@{ id = "gate_up"; pass = $false; detail = "gate bring-up failed" }
            return [pscustomobject]$result
        }
        $gateUp = $true

        $uatArgs = @(
            "-Action", "run",
            "-ProjectName", $project,
            "-RuntimeTarget", $RuntimeTarget,
            "-InferenceBackend", $InferenceBackend,
            "-CoreRosDistro", $CoreRosDistro,
            "-UatMode", $Case.mode,
            "-UatExecutionContext", "sim_gate",
            "-UatProfile", $UatProfile,
            "-UatInferenceDevice", $InferenceDevice
        )
        if ($Case.ContainsKey("uat_args")) {
            $uatArgs += [string[]]$Case.uat_args
        }

        $run = Invoke-PSCapture -ScriptPath (Join-Path $RepoRoot "scripts/run_compose_uat.ps1") -ScriptArgs $uatArgs
        $readinessRaw = Parse-Marker -Output $run.Output -Prefix "READINESS_REPORT="
        $artifactRaw = Parse-Marker -Output $run.Output -Prefix "ARTIFACT_DIR="
        $readinessPath = Convert-OrchestratorPath -Path $readinessRaw -RepoRoot $RepoRoot
        $artifactDir = Convert-OrchestratorPath -Path $artifactRaw -RepoRoot $RepoRoot
        $result.artifacts.readiness_report = $readinessPath

        if (-not [string]::IsNullOrWhiteSpace($readinessPath) -and (Test-Path -LiteralPath $readinessPath)) {
            $readiness = Get-Content -LiteralPath $readinessPath -Raw | ConvertFrom-Json
            $step = @($readiness.steps | Where-Object { $_.id -eq $Case.mode }) | Select-Object -First 1
            if (-not $step) {
                $result.assertions += [ordered]@{ id = "step_exists"; pass = $false; detail = "step '$($Case.mode)' missing in readiness report" }
                return [pscustomobject]$result
            }

            $statusPass = ([string]$step.status -eq "fail")
            $result.assertions += [ordered]@{
                id = "step_status"
                pass = $statusPass
                detail = "observed=$($step.status) expected=fail"
            }

            $fcPass = ([string]$step.failure_class -eq [string]$Case.expected_failure_class)
            $result.assertions += [ordered]@{
                id = "failure_class"
                pass = $fcPass
                detail = "observed=$($step.failure_class) expected=$($Case.expected_failure_class)"
            }

            $stepArtifactDir = Convert-OrchestratorPath -Path ([string]$step.artifact_dir) -RepoRoot $RepoRoot
            if (-not [string]::IsNullOrWhiteSpace($stepArtifactDir)) {
                $result.artifacts.artifact_dir = $stepArtifactDir
            }
            elseif (-not [string]::IsNullOrWhiteSpace($artifactDir)) {
                $result.artifacts.artifact_dir = $artifactDir
            }

            if ($Case.id -eq "nav2_non_progress_threshold") {
                $navSummaryPath = Join-Path $result.artifacts.artifact_dir "nav_summary.json"
                if (Test-Path -LiteralPath $navSummaryPath) {
                    $nav = Get-Content -LiteralPath $navSummaryPath -Raw | ConvertFrom-Json
                    $tp = $nav.target_progress
                    $tpPass = $false
                    if ($tp) { $tpPass = -not [bool]$tp.pass }
                    $result.assertions += [ordered]@{
                        id = "target_progress_rejected"
                        pass = $tpPass
                        detail = "target_progress.pass=$($tp.pass)"
                    }
                }
                else {
                    $result.assertions += [ordered]@{
                        id = "target_progress_rejected"
                        pass = $false
                        detail = "nav_summary.json missing"
                    }
                }
            }

            if ($Case.id -eq "nav2_cmdvel_instability_threshold") {
                $navSummaryPath = Join-Path $result.artifacts.artifact_dir "nav_summary.json"
                if (Test-Path -LiteralPath $navSummaryPath) {
                    $nav = Get-Content -LiteralPath $navSummaryPath -Raw | ConvertFrom-Json
                    $cmdThreshold = [double]$nav.thresholds.cmd_vel_publish_stability_min
                    $cmdObserved = [double]$nav.cmd_vel_publish_stability
                    $goalPass = ($cmdObserved -lt $cmdThreshold)
                    $result.assertions += [ordered]@{
                        id = "cmd_vel_stability_rejected"
                        pass = $goalPass
                        detail = "cmd_vel_publish_stability=$cmdObserved threshold=$cmdThreshold"
                    }
                }
                else {
                    $result.assertions += [ordered]@{
                        id = "cmd_vel_stability_rejected"
                        pass = $false
                        detail = "nav_summary.json missing"
                    }
                }
            }
        }
        else {
            $result.assertions += [ordered]@{ id = "readiness_report"; pass = $false; detail = "missing readiness_report marker/output" }
        }
    }
    finally {
        if ($gateUp) {
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
        if ($envBackup.Count -gt 0) {
            Restore-EnvOverrides -Backup $envBackup
        }
    }

    $allPass = (@($result.assertions | Where-Object { -not [bool]$_.pass }).Count -eq 0)
    if ($allPass) {
        $result.status = "pass"
    }
    return [pscustomobject]$result
}

$runtimeAliases = @{
    robot_fidelity = "robot_fidelity_orin"
}
if ($runtimeAliases.ContainsKey($RuntimeTarget)) {
    $RuntimeTarget = $runtimeAliases[$RuntimeTarget]
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$sessionDir = Join-Path $repoRoot "artifacts/session/$runId"
New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null
$summaryPath = Join-Path $sessionDir "adversarial_headless_summary.json"

$cases = @(
    @{
        id = "snapshot_missing_debug_feed"
        mode = "snapshot"
        description = "Missing debug feed must fail snapshot as blocked_dependency."
        expected_failure_class = "blocked_dependency"
        env_overrides = @{}
        uat_args = @(
            "-SnapshotTimeoutSeconds", "8",
            "-SnapshotDebugTopic", "/chasecar/adversarial/missing_debug_feed"
        )
    },
    @{
        id = "nav2_non_progress_threshold"
        mode = "nav2"
        description = "Non-progress thresholds must fail nav2 as threshold_failed."
        expected_failure_class = "threshold_failed"
        env_overrides = @{}
        uat_args = @("-Nav2Config", "ros2_config/config/nav2_readiness_adversarial_nonprogress.yaml")
    },
    @{
        id = "nav2_cmdvel_instability_threshold"
        mode = "nav2"
        description = "cmd_vel instability thresholds must fail nav2 gate."
        expected_failure_class = "threshold_failed"
        env_overrides = @{}
        uat_args = @("-Nav2Config", "ros2_config/config/nav2_readiness_adversarial_cmdvel.yaml")
    },
    @{
        id = "multi_target_missing_config"
        mode = "multi_target"
        description = "Missing config must fail multi_target as missing_artifact."
        expected_failure_class = "missing_artifact"
        env_overrides = @{}
        uat_args = @("-MultiTargetConfig", "ros2_config/config/does_not_exist.yaml")
    }
)

$results = @()
foreach ($case in $cases) {
    Write-Host "Running adversarial case: $($case.id)" -ForegroundColor Cyan
    $results += Invoke-AdversarialCase `
        -Case $case `
        -RepoRoot $repoRoot `
        -RuntimeTarget $RuntimeTarget `
        -CoreRosDistro $CoreRosDistro `
        -InferenceBackend $InferenceBackend `
        -InferenceDevice $InferenceDevice `
        -UatProfile $UatProfile
}

$overallPass = (@($results | Where-Object { $_.status -ne "pass" }).Count -eq 0)
$summary = [ordered]@{
    run_id = $runId
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    runtime_target = $RuntimeTarget
    core_ros_distro = $CoreRosDistro
    inference_backend = $InferenceBackend
    inference_device = $InferenceDevice
    total_cases = $results.Count
    passed_cases = @($results | Where-Object { $_.status -eq "pass" }).Count
    failed_cases = @($results | Where-Object { $_.status -ne "pass" }).Count
    pass = $overallPass
    cases = $results
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host "ADVERSARIAL_SUMMARY=$summaryPath"
Write-Host "ADVERSARIAL_PASS=$overallPass"

if ($overallPass) { exit 0 }
exit 2
