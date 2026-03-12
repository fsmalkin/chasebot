param(
    [ValidateSet(2, 3)]
    [int]$Milestone = 2,
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$SessionId = "",
    [string]$CoreRosDistro = "kilted",
    [int]$MaxRunSeconds = 0,
    [int]$MaxAttempts = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Get-FailureClass {
    param([object]$DemoSummary)
    if ($null -eq $DemoSummary) { return "missing_demo_summary" }
    $failureClass = [string]($DemoSummary.failure_context.failure_class)
    if (-not [string]::IsNullOrWhiteSpace($failureClass)) { return $failureClass }
    $failureClass = [string]($DemoSummary.visual.world_stream.failure_class)
    if (-not [string]::IsNullOrWhiteSpace($failureClass)) { return $failureClass }
    $failureClass = [string]($DemoSummary.visual.status)
    if (-not [string]::IsNullOrWhiteSpace($failureClass)) { return $failureClass }
    return ""
}

$transientWorldFailures = @(
    "world_stream_target_not_visible",
    "world_stream_blank",
    "world_stream_scene_missing",
    "world_stream_robot_not_visible",
    "world_stream_client_crash"
)

$baseEvidenceDir = Join-Path $repoRoot "artifacts/session/$runId/recorded_visual/milestone_$Milestone"
New-Item -ItemType Directory -Path $baseEvidenceDir -Force | Out-Null

$effectiveMaxRunSeconds = if ($MaxRunSeconds -gt 0) {
    $MaxRunSeconds
}
elseif ($Milestone -eq 3) {
    150
}
else {
    120
}

$finalExitCode = 1
$finalDemoSummaryPath = ""
$finalVisualSummaryPath = ""

for ($attempt = 1; $attempt -le [Math]::Max($MaxAttempts, 1); $attempt++) {
    $evidenceDir = if ($MaxAttempts -gt 1) {
        Join-Path $baseEvidenceDir ("attempt_{0}" -f $attempt)
    }
    else {
        $baseEvidenceDir
    }
    New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

    $stdout = Join-Path $env:TEMP ("recorded_visual_stdout_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path $env:TEMP ("recorded_visual_stderr_{0}.log" -f ([Guid]::NewGuid().ToString("N")))
    try {
        $args = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $PSScriptRoot "run_milestone_demo.ps1"),
            "-Milestone", $Milestone,
            "-RuntimeTarget", $RuntimeTarget,
            "-ExecutionLane", "container_kilted",
            "-CoreRosDistro", $CoreRosDistro,
            "-SessionId", $runId,
            "-EvidenceDir", $evidenceDir,
            "-Headless", "true",
            "-VisualSurface", "recorded",
            "-WorldSurface", "streamed_sim",
            "-AutoOpenVisualSurface", "false",
            "-OpenFeedViewers", "false",
            "-KeepWindowsOpen", "false",
            "-RequireParityGreenForOperatorView", "false",
            "-OperatorPhase", ("M{0}" -f $Milestone),
            "-TargetId", $(if ($Milestone -ge 3) { "single_target" } else { "detection_only" }),
            "-TargetTransitionActive", "false",
            "-MaxRunSeconds", [string]$effectiveMaxRunSeconds
        )
        if ($Milestone -ge 3) {
            $args += @(
                "-DemoTargetRelative", "false",
                "-DemoTargetX", "1.10",
                "-DemoTargetY", "0.00",
                "-DemoTargetZ", "0.05"
            )
        }

        $proc = Start-Process -FilePath "powershell.exe" -ArgumentList $args -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $output = @()
        if (Test-Path -LiteralPath $stdout) { $output += Get-Content -LiteralPath $stdout }
        if (Test-Path -LiteralPath $stderr) { $output += Get-Content -LiteralPath $stderr }
        foreach ($line in $output) { Write-Host $line }

        $demoSummaryPath = Join-Path $evidenceDir "demo_summary.json"
        $visualSummaryPath = Join-Path $repoRoot "artifacts/session/$runId/visual/visual_demo_summary_recorded.json"
        if (-not (Test-Path -LiteralPath $visualSummaryPath)) {
            $visualSummaryPath = Join-Path $repoRoot "artifacts/session/$runId/visual/visual_demo_summary.json"
        }

        $demoSummary = $null
        if (Test-Path -LiteralPath $demoSummaryPath) {
            try {
                $demoSummary = Get-Content -LiteralPath $demoSummaryPath -Raw | ConvertFrom-Json
            }
            catch {
                $demoSummary = $null
            }
        }

        $finalExitCode = [int]$proc.ExitCode
        $finalDemoSummaryPath = $demoSummaryPath
        $finalVisualSummaryPath = $visualSummaryPath

        $demoPass = $false
        if ($null -ne $demoSummary -and ($demoSummary.PSObject.Properties.Name -contains "pass")) {
            $demoPass = [bool]$demoSummary.pass
        }

        if ($finalExitCode -eq 0 -and $demoPass) {
            break
        }

        $failureClass = Get-FailureClass -DemoSummary $demoSummary
        $shouldRetry = ($attempt -lt [Math]::Max($MaxAttempts, 1) -and $transientWorldFailures -contains $failureClass)
        if (-not $shouldRetry) {
            break
        }
        Write-Host ("RECORDED_VISUAL_RETRY attempt={0} failure_class={1}" -f $attempt, $failureClass)
    }
    finally {
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "RECORDED_DEMO_SUMMARY=$finalDemoSummaryPath"
Write-Host "RECORDED_VISUAL_SUMMARY=$finalVisualSummaryPath"
exit $finalExitCode
