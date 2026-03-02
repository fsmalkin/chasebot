param(
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "workstation_balanced",
    [string]$Distro = "Ubuntu-24.04",
    [string]$RosDistro = "auto",
    [ValidateSet("container_kilted", "host_ros")]
    [string]$ExecutionLane = "container_kilted",
    [string]$CoreRosDistro = "kilted",
    [string]$WorldFile = "yolo_test_world_v6_clean_uat.world",
    [string]$WorldName = "yolo_test_world",
    [object]$OpenFeedViewers = $false,
    [object]$KeepWindowsOpen = $false,
    [string]$SessionId = "",
    [string]$HeadlessSummaryPath = "",
    [object]$RequireParityGreenForOperatorView = $true,
    [switch]$BypassParityGuard,
    [int]$Milestone2MaxRunSeconds = 120,
    [int]$Milestone3MaxRunSeconds = 150,
    [int]$Milestone2MaxAttempts = 3,
    [int]$Milestone3MaxAttemptsPerTarget = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-Bool {
    param(
        [object]$Value,
        [string]$ParamName
    )
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
        default { throw "Invalid boolean value '$Value' for '$ParamName'." }
    }
}

$runtimeAliases = @{
    robot_fidelity = "robot_fidelity_orin"
}
if ($runtimeAliases.ContainsKey($RuntimeTarget)) {
    $RuntimeTarget = $runtimeAliases[$RuntimeTarget]
}
$openFeedViewersResolved = Resolve-Bool -Value $OpenFeedViewers -ParamName "OpenFeedViewers"
$keepWindowsOpenResolved = Resolve-Bool -Value $KeepWindowsOpen -ParamName "KeepWindowsOpen"
$requireParityForViewResolved = Resolve-Bool -Value $RequireParityGreenForOperatorView -ParamName "RequireParityGreenForOperatorView"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = if ([string]::IsNullOrWhiteSpace($SessionId)) {
    (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
}
else {
    if ($SessionId -notmatch '^\d{8}T\d{6}Z$') {
        throw "SessionId must match YYYYMMDDTHHMMSSZ."
    }
    $SessionId
}
$sessionDir = Join-Path $repoRoot "artifacts/session/$runId"
$guiDir = Join-Path $sessionDir "gui_rehearsal"
$summaryPath = Join-Path $sessionDir "pre_llm_gui_rehearsal_summary.json"
New-Item -ItemType Directory -Path $guiDir -Force | Out-Null

function Invoke-StaleCleanup {
    $cleanup = @'
pkill -9 -f "[r]qt_image_view" 2>/dev/null || true
pkill -9 -f "[g]z sim" 2>/dev/null || true
pkill -9 -f "[j]etbot_gz_control_camera_test_v5.launch.py" 2>/dev/null || true
pkill -9 -f "[c]hasecar_tensorrt_detector.py" 2>/dev/null || true
pkill -9 -f "[y]olo_3d_position_extractor.py" 2>/dev/null || true
pkill -9 -f "[y]olo_3d_to_nav2_bridge.py" 2>/dev/null || true
pkill -9 -f "[j]etbot_nav2_rosgz_readiness.launch.py" 2>/dev/null || true
pkill -9 -f "[c]md_vel_relay.py" 2>/dev/null || true
'@
    $cleanup = $cleanup.Replace("`r`n", "`n")
    wsl -d $Distro -u root -- bash -lc $cleanup | Out-Null
}

function Resolve-RepoPath {
    param([string]$PathValue, [string]$RepoRoot)
    if ([string]::IsNullOrWhiteSpace($PathValue)) { return "" }
    if ([System.IO.Path]::IsPathRooted($PathValue)) { return (Resolve-Path -LiteralPath $PathValue).Path }
    $candidate = Join-Path $RepoRoot $PathValue
    if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    return $candidate
}

function Get-LatestParitySummary {
    param([string]$RepoRoot)
    $root = Join-Path $RepoRoot "artifacts/session"
    if (-not (Test-Path -LiteralPath $root)) { return $null }
    $candidates = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    foreach ($dir in $candidates) {
        $path = Join-Path $dir.FullName "parity_summary.json"
        if (Test-Path -LiteralPath $path) {
            try {
                $obj = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
                return [pscustomobject]@{
                    path = $path
                    summary = $obj
                }
            }
            catch {
                continue
            }
        }
    }
    return $null
}

function Get-LatestHeadlessSummary {
    param([string]$RepoRoot)
    $root = Join-Path $RepoRoot "artifacts/session"
    if (-not (Test-Path -LiteralPath $root)) { return "" }
    $candidates = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    foreach ($dir in $candidates) {
        $path = Join-Path $dir.FullName "pre_llm_headless_summary.json"
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return ""
}

function Parse-Marker {
    param(
        [string[]]$Output,
        [string]$Prefix
    )
    $line = $Output | Where-Object { $_ -like "$Prefix*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Prefix", "").Trim()
}

function Invoke-MilestoneDemo {
    param(
        [int]$Milestone,
        [string]$EvidenceDir,
        [double]$ForwardM,
        [double]$LateralM,
        [int]$MaxRunSeconds
    )

    Invoke-StaleCleanup
    $scriptPath = Join-Path $PSScriptRoot "run_milestone_demo.ps1"
    $args = @(
        "-ExecutionPolicy", "Bypass",
        "-File", $scriptPath,
        "-Milestone", $Milestone,
        "-RuntimeTarget", $RuntimeTarget,
        "-ExecutionLane", $ExecutionLane,
        "-CoreRosDistro", $CoreRosDistro,
        "-Distro", $Distro,
        "-RosDistro", $RosDistro,
        "-SessionId", $runId,
        "-WorldFile", $WorldFile,
        "-WorldName", $WorldName,
        "-EnsureDemoTarget",
        "-OpenFeedViewers", ([string][bool]$openFeedViewersResolved),
        "-RequireParityGreenForOperatorView", ([string][bool]$requireParityForViewResolved),
        "-EvidenceDir", $EvidenceDir,
        "-MaxRunSeconds", $MaxRunSeconds
    )
    if ($BypassParityGuard.IsPresent) {
        $args += "-BypassParityGuard"
    }
    if ($Milestone -ge 3) {
        $args += @(
            "-DemoTargetRelative", "false",
            "-DemoTargetX", $ForwardM.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            "-DemoTargetY", $LateralM.ToString([System.Globalization.CultureInfo]::InvariantCulture),
            "-DemoTargetZ", "0.05",
            "-RequireMotion", "true",
            "-RequireNav2ActionServer", "true"
        )
    }

    $formattedArgs = $args | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }
    $commandText = "powershell.exe " + ($formattedArgs -join ' ')

    $processOutput = @()
    $processOutput = & powershell.exe @args 2>&1
    $exitCode = $LASTEXITCODE
    foreach ($line in $processOutput) {
        Write-Host $line
    }

    $demoSummaryPath = Join-Path $EvidenceDir "demo_summary.json"
    $demoSummary = $null
    if (Test-Path -LiteralPath $demoSummaryPath) {
        $demoSummary = Get-Content -LiteralPath $demoSummaryPath -Raw | ConvertFrom-Json
    }

    $demoPass = $false
    if ($demoSummary -and ($demoSummary.PSObject.Properties.Name -contains "pass")) {
        $demoPass = [bool]$demoSummary.pass
    }

    return [pscustomobject]@{
        milestone = $Milestone
        command = $commandText
        exit_code = $exitCode
        evidence_dir = $EvidenceDir
        demo_summary_path = $demoSummaryPath
        demo_summary = $demoSummary
        pass = ($exitCode -eq 0 -and $demoPass)
    }
}

$results = @()

if ($openFeedViewersResolved -and $requireParityForViewResolved -and -not $BypassParityGuard.IsPresent) {
    $latestParity = Get-LatestParitySummary -RepoRoot $repoRoot
    $parityPass = $false
    $parityPath = ""
    if ($latestParity) {
        $parityPath = $latestParity.path
        $parityPass = [bool]$latestParity.summary.pass
    }
    if (-not $parityPass) {
        $summary = [ordered]@{
            run_id = $runId
            generated_utc = (Get-Date).ToUniversalTime().ToString("o")
            runtime_target = $RuntimeTarget
            execution_lane = $ExecutionLane
            core_ros_distro = $CoreRosDistro
            world_file = $WorldFile
            world_name = $WorldName
            open_feed_viewers = [bool]$openFeedViewersResolved
            pass = $false
            blocked_reason = "parity_guard_blocked"
            parity_guard = [ordered]@{
                required = $true
                bypassed = $false
                latest_parity_path = $parityPath
                latest_parity_pass = $parityPass
            }
            results = @()
        }
        $summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8
        Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
        Write-Host "GUI_REHEARSAL_PASS=False"
        exit 2
    }
}

$m2 = $null
for ($attempt = 1; $attempt -le [Math]::Max($Milestone2MaxAttempts, 1); $attempt++) {
    $m2Evidence = Join-Path $guiDir ("milestone_2_attempt_{0}" -f $attempt)
    New-Item -ItemType Directory -Path $m2Evidence -Force | Out-Null
    Write-Host ("Running GUI rehearsal Milestone 2 (attempt {0}/{1})..." -f $attempt, [Math]::Max($Milestone2MaxAttempts, 1)) -ForegroundColor Cyan
    $run = Invoke-MilestoneDemo -Milestone 2 -EvidenceDir $m2Evidence -ForwardM 1.10 -LateralM 0.00 -MaxRunSeconds $Milestone2MaxRunSeconds
    $run | Add-Member -NotePropertyName attempt -NotePropertyValue $attempt -Force
    $results += $run
    $m2 = $run
    if ($run.pass) { break }
}

if (-not $m2.pass) {
    $summary = [ordered]@{
        run_id = $runId
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        runtime_target = $RuntimeTarget
        execution_lane = $ExecutionLane
        core_ros_distro = $CoreRosDistro
        world_file = $WorldFile
        world_name = $WorldName
        open_feed_viewers = [bool]$openFeedViewersResolved
        pass = $false
        blocked_reason = "milestone_2_failed"
        results = $results
    }
    $summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8
    if (-not $keepWindowsOpenResolved) {
        Invoke-StaleCleanup
    }
    Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
    exit 2
}

$m3Targets = @(
    @{ id = "center"; forward_m = 1.10; lateral_m = 0.00 },
    @{ id = "left"; forward_m = 1.10; lateral_m = 0.12 },
    @{ id = "right"; forward_m = 1.10; lateral_m = -0.12 }
)

foreach ($target in $m3Targets) {
    $targetPassed = $false
    for ($attempt = 1; $attempt -le [Math]::Max($Milestone3MaxAttemptsPerTarget, 1); $attempt++) {
        $evidence = Join-Path $guiDir ("milestone_3_{0}_attempt_{1}" -f $target.id, $attempt)
        New-Item -ItemType Directory -Path $evidence -Force | Out-Null
        Write-Host ("Running GUI rehearsal Milestone 3 target={0} (attempt {1}/{2})..." -f $target.id, $attempt, [Math]::Max($Milestone3MaxAttemptsPerTarget, 1)) -ForegroundColor Cyan
        $res = Invoke-MilestoneDemo `
            -Milestone 3 `
            -EvidenceDir $evidence `
            -ForwardM ([double]$target.forward_m) `
            -LateralM ([double]$target.lateral_m) `
            -MaxRunSeconds $Milestone3MaxRunSeconds
        $res | Add-Member -NotePropertyName target_id -NotePropertyValue $target.id -Force
        $res | Add-Member -NotePropertyName attempt -NotePropertyValue $attempt -Force
        $results += $res
        if ($res.pass) {
            $targetPassed = $true
            break
        }
    }
    if (-not $targetPassed) { break }
}

$m2Attempts = @($results | Where-Object { $_.milestone -eq 2 })
$m2Final = $m2Attempts | Select-Object -Last 1
$m3FinalByTarget = @()
foreach ($target in $m3Targets) {
    $targetAttempts = @($results | Where-Object { $_.milestone -eq 3 -and $_.target_id -eq $target.id })
    if ($targetAttempts.Count -gt 0) {
        $m3FinalByTarget += ($targetAttempts | Select-Object -Last 1)
    }
}
$m3AllTargetsCovered = ($m3FinalByTarget.Count -eq $m3Targets.Count)
$m3AllPassed = ($m3AllTargetsCovered -and (@($m3FinalByTarget | Where-Object { -not $_.pass }).Count -eq 0))
$allPass = ([bool]$m2Final.pass -and $m3AllPassed)
$summary = [ordered]@{
    run_id = $runId
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    runtime_target = $RuntimeTarget
    execution_lane = $ExecutionLane
    core_ros_distro = $CoreRosDistro
    world_file = $WorldFile
    world_name = $WorldName
    open_feed_viewers = [bool]$openFeedViewersResolved
    pass = $allPass
    milestone2_pass = [bool]$m2Final.pass
    milestone2_attempts = $m2Attempts.Count
    milestone3_target_count = $m3Targets.Count
    milestone3_pass_count = @($m3FinalByTarget | Where-Object { $_.pass }).Count
    milestone3_attempts = @($results | Where-Object { $_.milestone -eq 3 }).Count
    milestone3_all_targets_covered = $m3AllTargetsCovered
    final_outcomes = [ordered]@{
        milestone2 = $m2Final
        milestone3 = $m3FinalByTarget
    }
    results = $results
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8

$resolvedHeadlessSummaryPath = ""
if (-not [string]::IsNullOrWhiteSpace($HeadlessSummaryPath)) {
    $resolvedHeadlessSummaryPath = Resolve-RepoPath -PathValue $HeadlessSummaryPath -RepoRoot $repoRoot
}
if ([string]::IsNullOrWhiteSpace($resolvedHeadlessSummaryPath)) {
    $sessionHeadless = Join-Path $sessionDir "pre_llm_headless_summary.json"
    if (Test-Path -LiteralPath $sessionHeadless) {
        $resolvedHeadlessSummaryPath = $sessionHeadless
    }
}
if ([string]::IsNullOrWhiteSpace($resolvedHeadlessSummaryPath)) {
    $resolvedHeadlessSummaryPath = Get-LatestHeadlessSummary -RepoRoot $repoRoot
}

$parityScript = Join-Path $PSScriptRoot "run_visual_parity_check.ps1"
$parityOutput = & powershell.exe -ExecutionPolicy Bypass -File $parityScript `
    -SessionId $runId `
    -HeadlessSummaryPath $resolvedHeadlessSummaryPath `
    -GuiSummaryPath $summaryPath 2>&1
$parityExitCode = $LASTEXITCODE
foreach ($line in $parityOutput) {
    Write-Host $line
}
$paritySummaryPath = Parse-Marker -Output $parityOutput -Prefix "PARITY_SUMMARY="
$parityPassMarker = Parse-Marker -Output $parityOutput -Prefix "PARITY_PASS="
$parityPass = ($parityExitCode -eq 0 -and $parityPassMarker.ToLowerInvariant() -eq "true")
$parityFailureClass = ""
if (-not [string]::IsNullOrWhiteSpace($paritySummaryPath) -and (Test-Path -LiteralPath $paritySummaryPath)) {
    try {
        $parityObj = Get-Content -LiteralPath $paritySummaryPath -Raw | ConvertFrom-Json
        $parityPass = [bool]$parityObj.pass
        $parityFailureClass = [string]$parityObj.failure_class
    }
    catch {
        if (-not $parityPass) {
            $parityFailureClass = "parity_summary_unreadable"
        }
    }
}
elseif (-not $parityPass) {
    $parityFailureClass = "missing_parity_summary"
}

$allPass = ($allPass -and $parityPass)
$summary.pass = $allPass
$summary.parity = [ordered]@{
    required = $true
    pass = $parityPass
    summary_path = $paritySummaryPath
    headless_summary_path = $resolvedHeadlessSummaryPath
    failure_class = if ($parityPass) { "" } else { $parityFailureClass }
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8

if (-not $keepWindowsOpenResolved) {
    Invoke-StaleCleanup
}

Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
Write-Host "GUI_REHEARSAL_PASS=$allPass"

if ($allPass) { exit 0 }
exit 2
