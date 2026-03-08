param(
    [ValidateSet(2, 3)]
    [int]$Milestone = 2,
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$SessionId = "",
    [string]$CoreRosDistro = "kilted",
    [int]$MaxRunSeconds = 0
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

$evidenceDir = Join-Path $repoRoot "artifacts/session/$runId/recorded_visual/milestone_$Milestone"
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
        "-RequireParityGreenForOperatorView", "false"
    )
    if ($MaxRunSeconds -gt 0) {
        $args += @("-MaxRunSeconds", $MaxRunSeconds)
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
    Write-Host "RECORDED_DEMO_SUMMARY=$demoSummaryPath"
    Write-Host "RECORDED_VISUAL_SUMMARY=$visualSummaryPath"

    exit $proc.ExitCode
}
finally {
    Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
}
