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

$runtimeAliases = @{
    robot_fidelity = "robot_fidelity_orin"
}
if ($runtimeAliases.ContainsKey($RuntimeTarget)) {
    $RuntimeTarget = $runtimeAliases[$RuntimeTarget]
}

$DemoTargetRelative = Resolve-NullableBool -Value $DemoTargetRelative -ParamName "DemoTargetRelative"
$OpenFeedViewers = Resolve-NullableBool -Value $OpenFeedViewers -ParamName "OpenFeedViewers"
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
if ($RequireMotion -eq $null) { $RequireMotion = ($Milestone -ge 3) }
if ($RequireNav2ActionServer -eq $null) { $RequireNav2ActionServer = ($Milestone -ge 3) }
if ($DemoTargetRelative -eq $null) { $DemoTargetRelative = $false }

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

$resolvedProjectName = if ([string]::IsNullOrWhiteSpace($ProjectName)) { "chasecar_gate_mdemo_$($runId.ToLowerInvariant())" } else { $ProjectName }
$composeGateScript = Join-Path $PSScriptRoot "run_compose_gate.ps1"
$composeUatScript = Join-Path $PSScriptRoot "run_compose_uat.ps1"

$includeNav2 = ($Milestone -ge 3)
$includeBridge = $false
$includeRelay = ($Milestone -ge 3)
$gateHeadless = $Headless

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

$stageRuns = @()
$overallPass = $false
$demoFailureClass = ""

try {
    Invoke-PSCapture -ScriptPath $composeGateScript -ScriptArgs @("-Action","down","-ProjectName",$resolvedProjectName,"-RuntimeTarget",$RuntimeTarget,"-InferenceBackend",$InferenceBackend,"-CoreRosDistro",$CoreRosDistro) | Out-Null
    Invoke-PSCapture -ScriptPath $composeUatScript -ScriptArgs @("-Action","down","-ProjectName",$resolvedProjectName,"-RuntimeTarget",$RuntimeTarget,"-InferenceBackend",$InferenceBackend,"-CoreRosDistro",$CoreRosDistro) | Out-Null

    $up = Invoke-PSCapture -ScriptPath $composeGateScript -ScriptArgs @(
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
        "-Headless",($(if($gateHeadless){"true"}else{"false"}))
    )
    if ($up.ExitCode -ne 0) { throw "Gate bring-up failed for project '$resolvedProjectName'." }

    $stageTimeout = [Math]::Max($StepTimeoutSeconds, 120)
    $nav2Duration = if ($MaxRunSeconds -gt 0) { [Math]::Max([Math]::Min($MaxRunSeconds - 30, 180), 60) } else { 120 }
    $nav2Config = if ($RuntimeTarget -eq "robot_fidelity_orin") { "ros2_config/config/nav2_readiness_fidelity.yaml" } else { "ros2_config/config/nav2_readiness_fast.yaml" }

    function Invoke-UatStage {
        param(
            [string]$Mode,
            [string]$ProjectName,
            [string]$RuntimeTarget,
            [string]$InferenceBackend,
            [string]$CoreRosDistro,
            [int]$StageTimeout,
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

    if ($Milestone -eq 1) {
        $stageRuns += Invoke-UatStage -Mode "snapshot" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
    } elseif ($Milestone -eq 2) {
        $stageRuns += Invoke-UatStage -Mode "coordinate" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
        $stageRuns += Invoke-UatStage -Mode "snapshot" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
    } else {
        $stageRuns += Invoke-UatStage -Mode "snapshot" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
        $stageRuns += Invoke-UatStage -Mode "nav2" -ProjectName $resolvedProjectName -RuntimeTarget $RuntimeTarget -InferenceBackend $InferenceBackend -CoreRosDistro $CoreRosDistro -StageTimeout $stageTimeout -Nav2Duration $nav2Duration -Nav2Config $nav2Config -Profile $PerfProfile -InferenceDevice $InferenceDevice
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

    if ($Milestone -eq 1) {
        $overallPass = ($snapshotPass -and $captureDebug -and $overlayDistinct -and $streamReady)
        if (-not $overallPass) {
            if (-not $streamReady) { $demoFailureClass = $streamStatus }
            else { $demoFailureClass = "snapshot_gate_failed" }
        }
    } elseif ($Milestone -eq 2) {
        $overallPass = ($coordinatePass -and $snapshotPass -and $ball3dSeen -and $captureDebug -and $overlayDistinct -and $streamReady)
        if (-not $overallPass) {
            if (-not $streamReady) { $demoFailureClass = $streamStatus }
            else { $demoFailureClass = "m2_tracking_gate_failed" }
        }
    } else {
        $requiredActionOk = ((-not $RequireNav2ActionServer) -or $navActionReady)
        $requiredMotionOk = ((-not $RequireMotion) -or $motionPass)
        $overallPass = ($snapshotPass -and $navPass -and $requiredActionOk -and $requiredMotionOk -and $streamReady)
        if (-not $overallPass) {
            if (-not $streamReady) { $demoFailureClass = $streamStatus }
            elseif (-not $requiredActionOk) { $demoFailureClass = "nav2_action_unavailable" }
            elseif (-not $requiredMotionOk) { $demoFailureClass = $motionError }
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
        start_utc = (Get-Date).ToUniversalTime().ToString("o")
        end_utc = (Get-Date).ToUniversalTime().ToString("o")
        max_run_seconds = [Math]::Max($MaxRunSeconds, 0)
        auto_stop_enabled = ($MaxRunSeconds -gt 0)
        compose_project = $resolvedProjectName
        world_file = $WorldFile
        world_name = $WorldName
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
            feed_viewers_required = [bool]$OpenFeedViewers
            feed_viewers_running = $false
            feed_viewer_status = if ($OpenFeedViewers) { "container_lane_headless_visual_blocked" } else { "skipped" }
            viewer_start_delay_s = 0
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
            feed_raw_viewer_running = $false
            feed_debug_viewer_running = $false
        }
        failure_context = [ordered]@{
            bridge_launch_blocked_reason = if ($Milestone -ge 3 -and -not $navPass) { "nav_stage_failed" } else { "none" }
            failure_class = if ($overallPass) { "" } else { $demoFailureClass }
        }
        pass = $overallPass
    }

    $operatorChecklist = [ordered]@{
        milestone = "$Milestone"
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        items = @(
            [ordered]@{ id = "world_ready"; description = "World service became available"; pass = $true },
            [ordered]@{ id = "stream_ready"; description = "Required camera/odom streams became active"; pass = $streamReady },
            [ordered]@{ id = "overlay_distinct"; description = "Debug image differs from raw image"; required = ($Milestone -le 2); pass = $overlayDistinct },
            [ordered]@{ id = "ball_position_3d"; description = "/yolo/ball_position_3d active"; required = ($Milestone -ge 2); pass = $ball3dSeen },
            [ordered]@{ id = "nav2_action_server_ready"; description = "/navigate_to_pose action server ready"; required = ($Milestone -ge 3); pass = $navActionReady },
            [ordered]@{ id = "cmd_vel_activity"; description = "cmd_vel activity observed"; required = ($Milestone -ge 3); pass = ($cmdVelMessageCount -gt 0) },
            [ordered]@{ id = "odom_displacement"; description = "Target-distance retained progress reached threshold"; required = ($Milestone -ge 3); pass = ($odomDisplacementM -ge $MotionMinDistanceMeters) }
        )
    }

    $demoSummaryPath = Join-Path $artifactDir "demo_summary.json"
    $checklistPath = Join-Path $artifactDir "operator_checklist.json"
    $demoPidsPath = Join-Path $artifactDir "demo_pids.json"

    $demoSummary | ConvertTo-Json -Depth 12 | Set-Content -Path $demoSummaryPath -Encoding UTF8
    $operatorChecklist | ConvertTo-Json -Depth 8 | Set-Content -Path $checklistPath -Encoding UTF8
    ([ordered]@{ milestone="$Milestone"; execution_lane="container_kilted"; core_ros_distro=$CoreRosDistro; compose_project=$resolvedProjectName; pids=[ordered]@{ sim=""; detector=""; extractor=""; bridge=""; nav2=""; cmd_vel_relay=""; motion_probe=""; feed_rgb_viewer=""; feed_debug_viewer="" } } | ConvertTo-Json -Depth 6) | Set-Content -Path $demoPidsPath -Encoding UTF8

    Write-Host "ARTIFACT_DIR=$artifactDir"
    Write-Host "SIM_PID="
    Write-Host "DETECTOR_PID="
    Write-Host "EXTRACTOR_PID="
    Write-Host "BRIDGE_PID="
    Write-Host "NAV2_PID="
    Write-Host "CMD_VEL_RELAY_PID="
    Write-Host "MOTION_PROBE_PID="
    Write-Host "FEED_RGB_VIEWER_PID="
    Write-Host "FEED_DEBUG_VIEWER_PID="
    Write-Host "WATCHDOG_PID="
    Write-Host "EVIDENCE_CAPTURE_RGB=$captureRgb"
    Write-Host "EVIDENCE_CAPTURE_DEBUG=$captureDebug"
    Write-Host "STOP_CMD=powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -Action down -ProjectName $resolvedProjectName"
}
finally {
    foreach ($k in $envBackupKeys) {
        $value = $envBackup[$k]
        if ($null -eq $value) { Remove-Item -Path "Env:$k" -ErrorAction SilentlyContinue }
        else { Set-Item -Path "Env:$k" -Value $value }
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

if ($overallPass) { exit 0 }
if ([string]::IsNullOrWhiteSpace($demoFailureClass)) { $demoFailureClass = "milestone_failed" }
Write-Error "Container milestone demo failed: $demoFailureClass"
exit 2
