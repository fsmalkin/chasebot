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
    [ValidateSet("none", "recorded", "browser_dashboard")]
    [string]$VisualSurface = "",
    [ValidateSet("streamed_sim", "none", "x11_debug")]
    [string]$WorldSurface = "",
    [object]$AutoOpenVisualSurface = $false,
    [int]$DashboardPort = 0,
    [object]$KeepWindowsOpen = $false,
    [ValidateSet("auto", "vcxsrv", "wslg")]
    [string]$DisplayMode = "auto",
    [string]$DisplayAddress = "",
    [object]$AutoStartVcXsrv = $true,
    [int]$DisplayPreflightTimeoutSeconds = 12,
    [ValidateSet("rqt_image_view", "image_view")]
    [string]$ViewerBackend = "rqt_image_view",
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

function Get-PropValue {
    param(
        [object]$Object,
        [string[]]$Path,
        [object]$Default = $null
    )
    $current = $Object
    foreach ($segment in $Path) {
        if ($null -eq $current) { return $Default }
        if ($current -is [System.Collections.IDictionary]) {
            if (-not $current.Contains($segment)) { return $Default }
            $current = $current[$segment]
            continue
        }
        $prop = $current.PSObject.Properties[$segment]
        if ($null -eq $prop) { return $Default }
        $current = $prop.Value
    }
    if ($null -eq $current) { return $Default }
    return $current
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
    if ($netstat) {
        if ($netstat | Select-String -Pattern ("[:\.]{0}\s+.*LISTENING" -f $Port) -Quiet) {
            return $true
        }
    }
    return $false
}

function Resolve-VcXsrvExecutable {
    $commandPath = ""
    try {
        $command = Get-Command "vcxsrv.exe" -ErrorAction Stop | Select-Object -First 1
        if ($command -and -not [string]::IsNullOrWhiteSpace($command.Source)) {
            $commandPath = [string]$command.Source
        }
    }
    catch {
        $commandPath = ""
    }

    $candidates = @(
        $env:VCXSRV_EXE,
        $env:VCXSRV_PATH,
        $commandPath,
        "$env:ProgramFiles\VcXsrv\vcxsrv.exe",
        "$env:ProgramFiles(x86)\VcXsrv\vcxsrv.exe",
        "$env:LOCALAPPDATA\Programs\VcXsrv\vcxsrv.exe"
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return ""
}

function Resolve-GuiDisplayPreflight {
    param(
        [string]$Mode,
        [string]$DisplayAddress,
        [bool]$AutoStartVcXsrv,
        [int]$TimeoutSeconds
    )

    $result = [ordered]@{
        pass = $false
        status = "display_unresolved"
        message = ""
        selected_mode = "none"
        display_address = ""
        viewer_backend = $ViewerBackend
    }

    $timeout = [Math]::Max($TimeoutSeconds, 3)
    $tryVcXsrv = ($Mode -eq "auto" -or $Mode -eq "vcxsrv")
    if ($tryVcXsrv) {
        $vcxProc = Get-Process -Name "vcxsrv" -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $vcxProc -and $AutoStartVcXsrv) {
            $exe = Resolve-VcXsrvExecutable
            if ($exe) {
                Start-Process -FilePath $exe -ArgumentList @(":0", "-multiwindow", "-clipboard", "-nowgl", "-ac", "-silent-dup-error") | Out-Null
            }
        }

        for ($i = 0; $i -lt $timeout; $i++) {
            if (Test-LocalTcpListen -Port 6000) {
                $result.pass = $true
                $result.status = "ok"
                $result.message = "vcxsrv_ready"
                $result.selected_mode = "vcxsrv"
                $result.display_address = if ([string]::IsNullOrWhiteSpace($DisplayAddress)) { "host.docker.internal:0.0" } else { $DisplayAddress }
                return [pscustomobject]$result
            }
            Start-Sleep -Seconds 1
        }
        if ($Mode -eq "vcxsrv") {
            $result.status = "vcxsrv_unavailable"
            $result.message = "VcXsrv not listening on tcp/6000."
            return [pscustomobject]$result
        }
    }

    if ($Mode -eq "wslg" -or $Mode -eq "auto") {
        $result.status = "wslg_unsupported_for_docker"
        $result.message = "WSLg display forwarding is not validated for Docker Desktop containers on this host."
        $result.selected_mode = "wslg"
        return [pscustomobject]$result
    }

    return [pscustomobject]$result
}

$runtimeAliases = @{
    robot_fidelity = "robot_fidelity_orin"
}
if ($runtimeAliases.ContainsKey($RuntimeTarget)) {
    $RuntimeTarget = $runtimeAliases[$RuntimeTarget]
}
$openFeedViewersResolved = Resolve-Bool -Value $OpenFeedViewers -ParamName "OpenFeedViewers"
$autoOpenVisualSurfaceResolved = Resolve-Bool -Value $AutoOpenVisualSurface -ParamName "AutoOpenVisualSurface"
$keepWindowsOpenResolved = Resolve-Bool -Value $KeepWindowsOpen -ParamName "KeepWindowsOpen"
$requireParityForViewResolved = Resolve-Bool -Value $RequireParityGreenForOperatorView -ParamName "RequireParityGreenForOperatorView"
$autoStartVcXsrvResolved = Resolve-Bool -Value $AutoStartVcXsrv -ParamName "AutoStartVcXsrv"
if ([string]::IsNullOrWhiteSpace($VisualSurface)) {
    $VisualSurface = if ($openFeedViewersResolved) { "browser_dashboard" } else { "none" }
}
if ([string]::IsNullOrWhiteSpace($WorldSurface)) {
    $WorldSurface = if ($VisualSurface -ne "none") { "streamed_sim" } else { "none" }
}

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

$displayPreflight = [ordered]@{
    pass = $true
    status = "not_required"
    message = ""
    selected_mode = "none"
    display_address = ""
    viewer_backend = $ViewerBackend
}
if ($openFeedViewersResolved -and $VisualSurface -eq "none" -and $WorldSurface -eq "x11_debug") {
    $displayPreflight = Resolve-GuiDisplayPreflight `
        -Mode $DisplayMode `
        -DisplayAddress $DisplayAddress `
        -AutoStartVcXsrv $autoStartVcXsrvResolved `
        -TimeoutSeconds $DisplayPreflightTimeoutSeconds
}

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
        "-VisualSurface", $VisualSurface,
        "-WorldSurface", $WorldSurface,
        "-AutoOpenVisualSurface", ([string][bool]$autoOpenVisualSurfaceResolved),
        "-DashboardPort", $DashboardPort.ToString(),
        "-KeepWindowsOpen", ([string][bool]$keepWindowsOpenResolved),
        "-RequireParityGreenForOperatorView", ([string][bool]$requireParityForViewResolved),
        "-AutoStartVcXsrv", ([string][bool]$autoStartVcXsrvResolved),
        "-DisplayPreflightTimeoutSeconds", [string]$DisplayPreflightTimeoutSeconds,
        "-ViewerBackend", $ViewerBackend,
        "-EvidenceDir", $EvidenceDir,
        "-MaxRunSeconds", $MaxRunSeconds
    )
    if ($BypassParityGuard.IsPresent) {
        $args += "-BypassParityGuard"
    }
    if ([string]$displayPreflight.selected_mode -in @("auto", "vcxsrv", "wslg")) {
        $args += @("-DisplayMode", [string]$displayPreflight.selected_mode)
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$displayPreflight.display_address)) {
        $args += @("-DisplayAddress", [string]$displayPreflight.display_address)
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

function New-GuiRehearsalSummary {
    param(
        [string]$FailureClass = "",
        [string]$BlockedReason = "",
        [string]$ErrorMessage = ""
    )
    return [ordered]@{
        run_id = $runId
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        runtime_target = $RuntimeTarget
        execution_lane = $ExecutionLane
        core_ros_distro = $CoreRosDistro
        world_file = $WorldFile
        world_name = $WorldName
        open_feed_viewers = [bool]$openFeedViewersResolved
        visual_surface = $VisualSurface
        world_surface = $WorldSurface
        display = $displayPreflight
        pass = $false
        blocked_reason = $BlockedReason
        failure_class = $FailureClass
        error_message = $ErrorMessage
        parity = [ordered]@{
            required = $true
            pass = $false
            summary_path = ""
            headless_summary_path = ""
            failure_class = ""
        }
        results = @()
    }
}

function Write-GuiRehearsalSummaryArtifact {
    param([object]$SummaryObject)
    if ($null -eq $SummaryObject) {
        $SummaryObject = New-GuiRehearsalSummary -FailureClass "missing_gui_summary" -BlockedReason "missing_gui_summary"
    }
    if (-not ($SummaryObject.PSObject.Properties.Name -contains "generated_utc")) {
        $SummaryObject | Add-Member -NotePropertyName generated_utc -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
    }
    else {
        $SummaryObject.generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    }
    if (-not ($SummaryObject.PSObject.Properties.Name -contains "results")) {
        $SummaryObject | Add-Member -NotePropertyName results -NotePropertyValue @($results) -Force
    }
    else {
        $SummaryObject.results = @($results)
    }
    $SummaryObject | ConvertTo-Json -Depth 12 | Set-Content -Path $summaryPath -Encoding UTF8
}

function New-SubrunFailureResult {
    param(
        [int]$Milestone,
        [string]$EvidenceDir,
        [string]$ErrorMessage,
        [string]$TargetId = "",
        [int]$Attempt = 0
    )
    $result = [ordered]@{
        milestone = $Milestone
        command = ""
        exit_code = -1
        evidence_dir = $EvidenceDir
        demo_summary_path = (Join-Path $EvidenceDir "demo_summary.json")
        demo_summary = $null
        pass = $false
        failure_class = "subrun_exception"
        error_message = $ErrorMessage
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetId)) {
        $result.target_id = $TargetId
    }
    if ($Attempt -gt 0) {
        $result.attempt = $Attempt
    }
    return [pscustomobject]$result
}

$summary = $null
$results = @()

trap {
    $message = $_.Exception.Message
    if ($null -eq $summary) {
        $summary = New-GuiRehearsalSummary -FailureClass "wrapper_exception" -BlockedReason "wrapper_exception" -ErrorMessage $message
    }
    else {
        if (-not ($summary.PSObject.Properties.Name -contains "failure_class") -or [string]::IsNullOrWhiteSpace([string]$summary.failure_class)) {
            $summary | Add-Member -NotePropertyName failure_class -NotePropertyValue "wrapper_exception" -Force
        }
        if (-not ($summary.PSObject.Properties.Name -contains "blocked_reason") -or [string]::IsNullOrWhiteSpace([string]$summary.blocked_reason)) {
            $summary | Add-Member -NotePropertyName blocked_reason -NotePropertyValue "wrapper_exception" -Force
        }
        $summary | Add-Member -NotePropertyName error_message -NotePropertyValue $message -Force
        $summary | Add-Member -NotePropertyName pass -NotePropertyValue $false -Force
    }
    Write-GuiRehearsalSummaryArtifact -SummaryObject $summary
    if (-not $keepWindowsOpenResolved) {
        try {
            Invoke-StaleCleanup
        }
        catch {
        }
    }
    Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
    Write-Host "GUI_REHEARSAL_PASS=False"
    exit 2
}

if ($openFeedViewersResolved -and $requireParityForViewResolved -and -not $BypassParityGuard.IsPresent) {
    $latestParity = Get-LatestParitySummary -RepoRoot $repoRoot
    $parityPass = $false
    $parityPath = ""
    if ($latestParity) {
        $parityPath = $latestParity.path
        $parityPass = [bool]$latestParity.summary.pass
    }
    if (-not $parityPass) {
        $summary = New-GuiRehearsalSummary -FailureClass "parity_guard_blocked" -BlockedReason "parity_guard_blocked"
        $summary.display = $displayPreflight
        $summary.parity_guard = [ordered]@{
            required = $true
            bypassed = $false
            latest_parity_path = $parityPath
            latest_parity_pass = $parityPass
        }
        Write-GuiRehearsalSummaryArtifact -SummaryObject $summary
        Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
        Write-Host "GUI_REHEARSAL_PASS=False"
        exit 2
    }
}

if ($openFeedViewersResolved -and -not [bool]$displayPreflight.pass) {
    $summary = New-GuiRehearsalSummary -FailureClass "display_preflight_failed" -BlockedReason "display_preflight_failed"
    $summary.display = $displayPreflight
    Write-GuiRehearsalSummaryArtifact -SummaryObject $summary
    Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
    Write-Host "GUI_REHEARSAL_PASS=False"
    exit 2
}

$m2 = $null
for ($attempt = 1; $attempt -le [Math]::Max($Milestone2MaxAttempts, 1); $attempt++) {
    $m2Evidence = Join-Path $guiDir ("milestone_2_attempt_{0}" -f $attempt)
    New-Item -ItemType Directory -Path $m2Evidence -Force | Out-Null
    Write-Host ("Running GUI rehearsal Milestone 2 (attempt {0}/{1})..." -f $attempt, [Math]::Max($Milestone2MaxAttempts, 1)) -ForegroundColor Cyan
    try {
        $run = Invoke-MilestoneDemo -Milestone 2 -EvidenceDir $m2Evidence -ForwardM 1.10 -LateralM 0.00 -MaxRunSeconds $Milestone2MaxRunSeconds
    }
    catch {
        $run = New-SubrunFailureResult -Milestone 2 -EvidenceDir $m2Evidence -ErrorMessage $_.Exception.Message -Attempt $attempt
    }
    $run | Add-Member -NotePropertyName attempt -NotePropertyValue $attempt -Force
    if (-not ($run.PSObject.Properties.Name -contains "failure_class")) {
        $run | Add-Member -NotePropertyName failure_class -NotePropertyValue "" -Force
    }
    $results += $run
    $m2 = $run
    if ($run.pass) { break }
}

if (-not $m2.pass) {
    $summary = New-GuiRehearsalSummary -FailureClass $(if (@($results | Where-Object { $_.milestone -eq 2 -and $_.failure_class -eq "subrun_exception" }).Count -gt 0) { "subrun_exception" } else { "milestone_2_failed" }) -BlockedReason "milestone_2_failed"
    $summary.display = $displayPreflight
    Write-GuiRehearsalSummaryArtifact -SummaryObject $summary
    if (-not $keepWindowsOpenResolved) {
        Invoke-StaleCleanup
    }
    Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
    Write-Host "GUI_REHEARSAL_PASS=False"
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
        try {
            $res = Invoke-MilestoneDemo `
                -Milestone 3 `
                -EvidenceDir $evidence `
                -ForwardM ([double]$target.forward_m) `
                -LateralM ([double]$target.lateral_m) `
                -MaxRunSeconds $Milestone3MaxRunSeconds
        }
        catch {
            $res = New-SubrunFailureResult -Milestone 3 -EvidenceDir $evidence -ErrorMessage $_.Exception.Message -TargetId $target.id -Attempt $attempt
        }
        $res | Add-Member -NotePropertyName target_id -NotePropertyValue $target.id -Force
        $res | Add-Member -NotePropertyName attempt -NotePropertyValue $attempt -Force
        if (-not ($res.PSObject.Properties.Name -contains "failure_class")) {
            $res | Add-Member -NotePropertyName failure_class -NotePropertyValue "" -Force
        }
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
$m2DemoSummary = Get-PropValue -Object $m2Final -Path @("demo_summary") -Default $null
$m2ViewersRunning = Resolve-Bool -Value (Get-PropValue -Object $m2DemoSummary -Path @("viewers", "feed_viewers_running") -Default $false) -ParamName "m2.feed_viewers_running"
$m2Visual = Get-PropValue -Object $m2DemoSummary -Path @("visual") -Default $null
$m2WorldSurface = [string](Get-PropValue -Object $m2DemoSummary -Path @("world_surface") -Default $WorldSurface)
$m2WorldStream = Get-PropValue -Object $m2Visual -Path @("world_stream") -Default $null
$m2DisplayMode = [string](Get-PropValue -Object $m2DemoSummary -Path @("display_mode") -Default [string]$displayPreflight.selected_mode)
$m2DisplayAddress = [string](Get-PropValue -Object $m2DemoSummary -Path @("display_address") -Default [string]$displayPreflight.display_address)
$m2ViewerBackend = [string](Get-PropValue -Object $m2DemoSummary -Path @("viewer_backend") -Default $ViewerBackend)
$m2ViewerStartupElapsedS = [double](Get-PropValue -Object $m2DemoSummary -Path @("viewers", "viewer_startup_elapsed_s") -Default 0.0)
$m2ViewerFrameCounts = Get-PropValue -Object $m2DemoSummary -Path @("viewers", "viewer_frame_counts") -Default ([ordered]@{ rgb = 0; yolo_debug = 0 })
$m2VisualFrameCounts = [ordered]@{
    raw = [int](Get-PropValue -Object $m2Visual -Path @("raw_frame_count") -Default 0)
    debug = [int](Get-PropValue -Object $m2Visual -Path @("debug_frame_count") -Default 0)
    telemetry = [int](Get-PropValue -Object $m2Visual -Path @("telemetry_frame_count") -Default 0)
}
$m2VisualReady = Resolve-Bool -Value (Get-PropValue -Object $m2Visual -Path @("visual_ready") -Default $false) -ParamName "m2.visual.visual_ready"
$m2DashboardUrl = [string](Get-PropValue -Object $m2Visual -Path @("dashboard_url") -Default "")
$m2WorldStreamReady = Resolve-Bool -Value (Get-PropValue -Object $m2WorldStream -Path @("ready") -Default ($m2WorldSurface -ne "streamed_sim")) -ParamName "m2.visual.world_stream.ready"
$m2WorldStreamNonblank = Resolve-Bool -Value (Get-PropValue -Object $m2WorldStream -Path @("nonblank") -Default ($m2WorldSurface -ne "streamed_sim")) -ParamName "m2.visual.world_stream.nonblank"
$m2WorldStreamInteractive = Resolve-Bool -Value (Get-PropValue -Object $m2WorldStream -Path @("interactive") -Default ($m2WorldSurface -ne "streamed_sim")) -ParamName "m2.visual.world_stream.interactive"
$m2WorldStreamSameSession = Resolve-Bool -Value (Get-PropValue -Object $m2WorldStream -Path @("same_session_partition") -Default ($m2WorldSurface -ne "streamed_sim")) -ParamName "m2.visual.world_stream.same_session_partition"
$m2TruthReady = Resolve-Bool -Value (Get-PropValue -Object $m2Visual -Path @("truth_ready") -Default $false) -ParamName "m2.visual.truth_ready"
$m2TruthAlignmentOk = Resolve-Bool -Value (Get-PropValue -Object $m2Visual -Path @("truth_alignment_ok") -Default $false) -ParamName "m2.visual.truth_alignment_ok"
$m3ViewersRunningAll = $true
$m3VisualReadyAll = $true
foreach ($m3 in $m3FinalByTarget) {
    $m3DemoSummary = Get-PropValue -Object $m3 -Path @("demo_summary") -Default $null
    $m3ViewersRunning = Resolve-Bool -Value (Get-PropValue -Object $m3DemoSummary -Path @("viewers", "feed_viewers_running") -Default $false) -ParamName "m3.feed_viewers_running"
    $m3Visual = Get-PropValue -Object $m3DemoSummary -Path @("visual") -Default $null
    $m3VisualReady = Resolve-Bool -Value (Get-PropValue -Object $m3Visual -Path @("visual_ready") -Default $false) -ParamName "m3.visual.visual_ready"
    if (-not $m3ViewersRunning) {
        $m3ViewersRunningAll = $false
    }
    if (-not $m3VisualReady) {
        $m3VisualReadyAll = $false
    }
}
$visualReady = if ($VisualSurface -eq "none") {
    if ($openFeedViewersResolved) { ($m2ViewersRunning -and $m3ViewersRunningAll) } else { $true }
}
else {
    ($m2VisualReady -and $m3VisualReadyAll -and $m2TruthReady -and $m2TruthAlignmentOk -and $m2WorldStreamReady -and $m2WorldStreamNonblank -and $m2WorldStreamInteractive -and $m2WorldStreamSameSession)
}
$allPass = ([bool]$m2Final.pass -and $m3AllPassed -and $visualReady)
$summary = [ordered]@{
    run_id = $runId
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    runtime_target = $RuntimeTarget
    execution_lane = $ExecutionLane
    core_ros_distro = $CoreRosDistro
    world_file = $WorldFile
    world_name = $WorldName
    open_feed_viewers = [bool]$openFeedViewersResolved
    visual_surface = $VisualSurface
    world_surface = $m2WorldSurface
    display = [ordered]@{
        preflight = $displayPreflight
        display_mode = $m2DisplayMode
        display_address = $m2DisplayAddress
        viewer_backend = $m2ViewerBackend
    }
    visual_ready = $visualReady
    display_mode = $m2DisplayMode
    viewer_backend = $m2ViewerBackend
    viewer_frame_counts = if ($VisualSurface -eq "none") { $m2ViewerFrameCounts } else { $m2VisualFrameCounts }
    viewer_startup_elapsed_s = $m2ViewerStartupElapsedS
    visual = [ordered]@{
        surface = $VisualSurface
        world_surface = $m2WorldSurface
        dashboard_url = $m2DashboardUrl
        world_stream_url = [string](Get-PropValue -Object $m2WorldStream -Path @("url") -Default "")
        world_stream_ready = $m2WorldStreamReady
        world_stream_nonblank = $m2WorldStreamNonblank
        world_stream_interactive = $m2WorldStreamInteractive
        same_session_partition = $m2WorldStreamSameSession
        truth_ready = $m2TruthReady
        truth_alignment_ok = $m2TruthAlignmentOk
        milestone2 = $m2Visual
        milestone3 = @($m3FinalByTarget | ForEach-Object { Get-PropValue -Object $_ -Path @("demo_summary", "visual") -Default $null })
    }
    pass = $allPass
    failure_class = ""
    error_message = ""
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
if (-not [bool]$m2Final.pass) {
    $summary.failure_class = if (@($m2Attempts | Where-Object { $_.failure_class -eq "subrun_exception" }).Count -gt 0) { "subrun_exception" } else { "milestone_2_failed" }
}
elseif (-not $m3AllPassed) {
    $summary.failure_class = if (@($m3FinalByTarget | Where-Object { $_.failure_class -eq "subrun_exception" }).Count -gt 0) { "subrun_exception" } else { "milestone_3_failed" }
}
elseif (-not $visualReady) {
    $summary.failure_class = "visual_gate_failed"
}
Write-GuiRehearsalSummaryArtifact -SummaryObject $summary

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
if (-not $parityPass -and [string]::IsNullOrWhiteSpace($summary.failure_class)) {
    $summary.failure_class = if ([string]::IsNullOrWhiteSpace($parityFailureClass)) { "parity_failed" } else { $parityFailureClass }
}
$summary.parity = [ordered]@{
    required = $true
    pass = $parityPass
    summary_path = $paritySummaryPath
    headless_summary_path = $resolvedHeadlessSummaryPath
    failure_class = if ($parityPass) { "" } else { $parityFailureClass }
}
Write-GuiRehearsalSummaryArtifact -SummaryObject $summary

if (-not $keepWindowsOpenResolved) {
    Invoke-StaleCleanup
}

Write-Host "GUI_REHEARSAL_SUMMARY=$summaryPath"
Write-Host "GUI_REHEARSAL_PASS=$allPass"

if ($allPass) { exit 0 }
exit 2
