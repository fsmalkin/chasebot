param(
    [int]$Runs = 3,
    [int]$FastStepTimeoutSeconds = 360,
    [int]$FidelityStepTimeoutSeconds = 480,
    [int]$FastNav2DurationSeconds = 60,
    [int]$FidelityNav2DurationSeconds = 90,
    [int]$FastMultiTargetGoalTimeoutSeconds = 45,
    [int]$FidelityMultiTargetGoalTimeoutSeconds = 60,
    [double]$SnapshotMinMeanAbsDiff = 1.0,
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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$includeSoakResolved = Resolve-Bool -Value $IncludeSoak -ParamName "IncludeSoak"
$campaignStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$campaignDir = Join-Path $repoRoot "artifacts/session/$campaignStamp"
New-Item -ItemType Directory -Path $campaignDir -Force | Out-Null

$runSummaries = @()
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
        "-SnapshotMinMeanAbsDiff", $SnapshotMinMeanAbsDiff
    )

    $summaryPath = Parse-SummaryPath -Output $run.Output
    if (-not [string]::IsNullOrWhiteSpace($summaryPath)) {
        $runSummaries += $summaryPath
    }

    if ($run.ExitCode -ne 0) {
        throw "Dual run $i failed (exit=$($run.ExitCode))."
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
        "-SnapshotMinMeanAbsDiff", $SnapshotMinMeanAbsDiff
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
    dual_runs = $runSummaries
    campaign_report = $campaignReport
    soak_summary = $soakSummary
    rc_manifest = if ($includeSoakResolved) { Join-Path $campaignDir "rc/manifest.json" } else { "" }
    rc_readiness = if ($includeSoakResolved) { Join-Path $campaignDir "rc/readiness_report.json" } else { "" }
}

$campaignSummaryPath = Join-Path $campaignDir "campaign_run_summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $campaignSummaryPath -Encoding UTF8

Write-Host "Campaign summary: $campaignSummaryPath"
