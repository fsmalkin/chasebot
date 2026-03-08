param(
    [int]$Runs = 3,
    [int]$FastStepTimeoutSeconds = 360,
    [int]$FidelityStepTimeoutSeconds = 480,
    [int]$FastNav2DurationSeconds = 60,
    [int]$FidelityNav2DurationSeconds = 90,
    [int]$FastMultiTargetGoalTimeoutSeconds = 45,
    [int]$FidelityMultiTargetGoalTimeoutSeconds = 60,
    [double]$SnapshotMinMeanAbsDiff = 1.0,
    [double]$SnapshotMinChangedPixelRatio = 0.001,
    [object]$IncludeGuiParity = $true,
    [ValidateSet("robot_fidelity_orin", "workstation_balanced", "workstation_max")]
    [string]$GuiRuntimeTarget = "robot_fidelity_orin",
    [int]$GuiMilestone2MaxRunSeconds = 120,
    [int]$GuiMilestone3MaxRunSeconds = 150,
    [int]$GuiMilestone2MaxAttempts = 2,
    [int]$GuiMilestone3MaxAttemptsPerTarget = 2,
    [object]$GuiOpenFeedViewers = $true,
    [ValidateSet("auto", "vcxsrv", "wslg")]
    [string]$GuiDisplayMode = "auto",
    [string]$GuiDisplayAddress = "",
    [object]$GuiAutoStartVcXsrv = $true,
    [int]$GuiDisplayPreflightTimeoutSeconds = 12,
    [ValidateSet("rqt_image_view")]
    [string]$GuiViewerBackend = "rqt_image_view",
    [string]$GuiCoreRosDistro = "kilted",
    [object]$IncludeSoak = $true,
    [int]$SoakStepTimeoutSeconds = 2100,
    [int]$SoakNav2DurationSeconds = 1200,
    [int]$SoakMultiTargetGoalTimeoutSeconds = 60,
    [string]$SoakMultiTargetConfig = "ros2_config/config/multi_target_nav2_fidelity_soak.yaml"
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

function Invoke-PSCapture {
    param([string]$ScriptPath, [string[]]$ScriptArgs)

    $stdout = Join-Path $env:TEMP ("pre_llm_campaign_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("pre_llm_campaign_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
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

function Parse-SummaryPath {
    param([string[]]$Output)
    $line = $Output | Where-Object { $_ -like "Summary:*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    $path = ($line -replace '^Summary:\s*', '').Trim()
    if ([string]::IsNullOrWhiteSpace($path)) { return "" }
    return [regex]::Replace($path, '\\\\+', '\')
}

function Parse-Marker {
    param([string[]]$Output, [string]$Prefix)
    $line = $Output | Where-Object { $_ -like "$Prefix*" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Prefix", "").Trim()
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$includeSoakResolved = Resolve-Bool -Value $IncludeSoak -ParamName "IncludeSoak"
$includeGuiParityResolved = Resolve-Bool -Value $IncludeGuiParity -ParamName "IncludeGuiParity"
$guiOpenFeedViewersResolved = Resolve-Bool -Value $GuiOpenFeedViewers -ParamName "GuiOpenFeedViewers"
$guiAutoStartVcXsrvResolved = Resolve-Bool -Value $GuiAutoStartVcXsrv -ParamName "GuiAutoStartVcXsrv"
$campaignStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$campaignDir = Join-Path $repoRoot "artifacts/session/$campaignStamp"
New-Item -ItemType Directory -Path $campaignDir -Force | Out-Null

$runSummaries = @()
$guiRunSummaries = @()
for ($i = 1; $i -le $Runs; $i++) {
    Write-Host ("[{0}/{1}] Running dual pre-LLM cycle..." -f $i, $Runs) -ForegroundColor Cyan
    $run = Invoke-PSCapture -ScriptPath (Join-Path $repoRoot "scripts/run_headless_pre_llm.ps1") -ScriptArgs @(
        "-Lane", "dual",
        "-FastStepTimeoutSeconds", $FastStepTimeoutSeconds,
        "-FidelityStepTimeoutSeconds", $FidelityStepTimeoutSeconds,
        "-FastNav2DurationSeconds", $FastNav2DurationSeconds,
        "-FidelityNav2DurationSeconds", $FidelityNav2DurationSeconds,
        "-FastMultiTargetGoalTimeoutSeconds", $FastMultiTargetGoalTimeoutSeconds,
        "-FidelityMultiTargetGoalTimeoutSeconds", $FidelityMultiTargetGoalTimeoutSeconds,
        "-SnapshotMinMeanAbsDiff", $SnapshotMinMeanAbsDiff,
        "-SnapshotMinChangedPixelRatio", $SnapshotMinChangedPixelRatio
    )

    $summaryPath = Parse-SummaryPath -Output $run.Output
    if (-not [string]::IsNullOrWhiteSpace($summaryPath)) {
        $runSummaries += $summaryPath
    }

    if ($run.ExitCode -ne 0) {
        throw "Dual run $i failed (exit=$($run.ExitCode))."
    }

    if ($includeGuiParityResolved) {
        if ([string]::IsNullOrWhiteSpace($summaryPath) -or -not (Test-Path -LiteralPath $summaryPath)) {
            throw "Dual run $i did not produce a headless summary for GUI parity."
        }

        $headlessObj = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
        $runId = [string]$headlessObj.run_id
        if ([string]::IsNullOrWhiteSpace($runId)) {
            throw "Dual run $i produced headless summary without run_id."
        }

        Write-Host ("[{0}/{1}] Running recorded visual bundle for session {2}..." -f $i, $Runs, $runId) -ForegroundColor Cyan
        $recorded = Invoke-PSCapture -ScriptPath (Join-Path $repoRoot "scripts/run_recorded_visual_demo.ps1") -ScriptArgs @(
            "-Milestone", 3,
            "-RuntimeTarget", $GuiRuntimeTarget,
            "-CoreRosDistro", $GuiCoreRosDistro,
            "-SessionId", $runId,
            "-MaxRunSeconds", $GuiMilestone3MaxRunSeconds
        )
        $recordedSummaryPath = Parse-Marker -Output $recorded.Output -Prefix "RECORDED_VISUAL_SUMMARY="
        if ([string]::IsNullOrWhiteSpace($recordedSummaryPath)) {
            $recordedSummaryPath = Join-Path $repoRoot "artifacts/session/$runId/visual/visual_demo_summary_recorded.json"
        }
        if (-not [System.IO.Path]::IsPathRooted($recordedSummaryPath)) {
            $recordedSummaryPath = Join-Path $repoRoot $recordedSummaryPath
        }
        $recordedPass = $false
        if (Test-Path -LiteralPath $recordedSummaryPath) {
            try {
                $recordedObj = Get-Content -LiteralPath $recordedSummaryPath -Raw | ConvertFrom-Json
                $recordedPass = [bool]$recordedObj.pass
            }
            catch {
                $recordedPass = $false
            }
        }
        if ($recorded.ExitCode -ne 0 -or -not $recordedPass) {
            throw "Recorded visual bundle failed for dual run $i (session $runId)."
        }

        Write-Host ("[{0}/{1}] Running GUI rehearsal + parity for session {2}..." -f $i, $Runs, $runId) -ForegroundColor Cyan
        $guiArgs = @(
            "-SessionId", $runId,
            "-HeadlessSummaryPath", $summaryPath,
            "-RuntimeTarget", $GuiRuntimeTarget,
            "-ExecutionLane", "container_kilted",
            "-CoreRosDistro", $GuiCoreRosDistro,
            "-OpenFeedViewers", ($(if ($guiOpenFeedViewersResolved) { "true" } else { "false" })),
            "-DisplayMode", $GuiDisplayMode,
            "-AutoStartVcXsrv", ($(if ($guiAutoStartVcXsrvResolved) { "true" } else { "false" })),
            "-DisplayPreflightTimeoutSeconds", $GuiDisplayPreflightTimeoutSeconds,
            "-ViewerBackend", $GuiViewerBackend,
            "-RequireParityGreenForOperatorView", "false",
            "-Milestone2MaxRunSeconds", $GuiMilestone2MaxRunSeconds,
            "-Milestone3MaxRunSeconds", $GuiMilestone3MaxRunSeconds,
            "-Milestone2MaxAttempts", $GuiMilestone2MaxAttempts,
            "-Milestone3MaxAttemptsPerTarget", $GuiMilestone3MaxAttemptsPerTarget
        )
        if (-not [string]::IsNullOrWhiteSpace($GuiDisplayAddress)) {
            $guiArgs += @("-DisplayAddress", $GuiDisplayAddress)
        }
        $gui = Invoke-PSCapture -ScriptPath (Join-Path $repoRoot "scripts/run_pre_llm_gui_rehearsal.ps1") -ScriptArgs $guiArgs

        $guiSummaryPath = Parse-Marker -Output $gui.Output -Prefix "GUI_REHEARSAL_SUMMARY="
        if ([string]::IsNullOrWhiteSpace($guiSummaryPath)) {
            $guiSummaryPath = Join-Path $repoRoot "artifacts/session/$runId/pre_llm_gui_rehearsal_summary.json"
        }
        if (-not [System.IO.Path]::IsPathRooted($guiSummaryPath)) {
            $guiSummaryPath = Join-Path $repoRoot $guiSummaryPath
        }
        $paritySummaryPath = Join-Path $repoRoot "artifacts/session/$runId/parity_summary.json"
        $parityPass = $false
        $guiVisualReady = $false
        if (Test-Path -LiteralPath $paritySummaryPath) {
            try {
                $parityObj = Get-Content -LiteralPath $paritySummaryPath -Raw | ConvertFrom-Json
                $parityPass = [bool]$parityObj.pass
            }
            catch {
                $parityPass = $false
            }
        }
        if (Test-Path -LiteralPath $guiSummaryPath) {
            try {
                $guiObj = Get-Content -LiteralPath $guiSummaryPath -Raw | ConvertFrom-Json
                $guiVisualReady = [bool]$guiObj.visual_ready
            }
            catch {
                $guiVisualReady = $false
            }
        }
        $visualGatePass = if ($guiOpenFeedViewersResolved) { $guiVisualReady } else { $true }

        $guiStatus = if ($gui.ExitCode -eq 0 -and $parityPass -and $visualGatePass) { "pass" } else { "fail" }
        $guiRunSummaries += [ordered]@{
            run_index = $i
            run_id = $runId
            status = $guiStatus
            headless_summary = $summaryPath
            recorded_visual_summary = $recordedSummaryPath
            gui_summary = $guiSummaryPath
            parity_summary = $paritySummaryPath
            visual_ready = $guiVisualReady
        }

        if ($gui.ExitCode -ne 0 -or -not $parityPass -or -not $visualGatePass) {
            throw "GUI parity rehearsal failed for dual run $i (session $runId)."
        }
    }
}

$campaignReport = Join-Path $campaignDir "pre_llm_campaign_trend.json"

Push-Location $repoRoot
try {
    $aggregateArgs = @("scripts/aggregate_pre_llm_campaign.py", "--runs") + $runSummaries + @("--output", $campaignReport)
    & python @aggregateArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Campaign aggregation failed."
    }
}
finally {
    Pop-Location
}

$soakSummary = ""
if ($includeSoakResolved) {
    Write-Host "Running fidelity soak cycle..." -ForegroundColor Cyan
    $soak = Invoke-PSCapture -ScriptPath (Join-Path $repoRoot "scripts/run_headless_pre_llm.ps1") -ScriptArgs @(
        "-Lane", "fidelity",
        "-FidelityStepTimeoutSeconds", $SoakStepTimeoutSeconds,
        "-FidelityNav2DurationSeconds", $SoakNav2DurationSeconds,
        "-FidelityMultiTargetGoalTimeoutSeconds", $SoakMultiTargetGoalTimeoutSeconds,
        "-FidelityMultiTargetConfig", $SoakMultiTargetConfig,
        "-SnapshotMinMeanAbsDiff", $SnapshotMinMeanAbsDiff,
        "-SnapshotMinChangedPixelRatio", $SnapshotMinChangedPixelRatio
    )

    $soakSummary = Parse-SummaryPath -Output $soak.Output
    if ($soak.ExitCode -ne 0) {
        throw "Fidelity soak run failed (exit=$($soak.ExitCode))."
    }
    if ([string]::IsNullOrWhiteSpace($soakSummary)) {
        throw "Unable to locate soak summary path."
    }
}

if (-not [string]::IsNullOrWhiteSpace($soakSummary)) {
    Push-Location $repoRoot
    try {
        $rcDir = Join-Path $campaignDir "rc"
        python scripts/build_pre_llm_rc_package.py --campaign "$campaignReport" --soak "$soakSummary" --output-dir "$rcDir"
        if ($LASTEXITCODE -ne 0) {
            throw "RC package build failed."
        }
    }
    finally {
        Pop-Location
    }
}

$summary = [ordered]@{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    campaign_dir = $campaignDir
    include_gui_parity = $includeGuiParityResolved
    gui_open_feed_viewers = $guiOpenFeedViewersResolved
    gui_display_mode = $GuiDisplayMode
    gui_viewer_backend = $GuiViewerBackend
    dual_runs = $runSummaries
    gui_runs = $guiRunSummaries
    gui_parity_all_green = if ($includeGuiParityResolved) { (@($guiRunSummaries | Where-Object { $_.status -ne "pass" }).Count -eq 0) } else { $null }
    campaign_report = $campaignReport
    soak_summary = $soakSummary
    rc_manifest = if ($includeSoakResolved) { Join-Path $campaignDir "rc/manifest.json" } else { "" }
    rc_readiness = if ($includeSoakResolved) { Join-Path $campaignDir "rc/readiness_report.json" } else { "" }
}

$campaignSummaryPath = Join-Path $campaignDir "campaign_run_summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $campaignSummaryPath -Encoding UTF8

Write-Host "Campaign summary: $campaignSummaryPath"
