param(
    [string]$DashboardUrl = "http://127.0.0.1:8860",
    [string]$ProjectName = "chasecar",
    [string]$Model = "",
    [ValidateSet("minimal", "low", "medium", "high")]
    [string]$ReasoningEffort = "",
    [int]$Runs = 3,
    [double]$TimeoutSeconds = 45.0,
    [double]$MaxRuntimeSeconds = 180.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Get-Command python -ErrorAction Stop
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    $dockerFallback = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $dockerFallback) {
        $docker = Get-Item -LiteralPath $dockerFallback
    }
    else {
        throw "Unable to locate docker CLI."
    }
}

$envFile = Join-Path $repoRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            return
        }
        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            return
        }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ([string]::IsNullOrWhiteSpace($key)) {
            return
        }
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key, "Process"))) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

Push-Location $repoRoot
try {
    & $docker.Source compose -p $ProjectName up -d dashboard-control dashboard-utility brain-supervisor-shadow | Out-Null
    $argsList = @(
        (Join-Path $repoRoot "scripts/llm_turn_then_go_repeatability_runner.py"),
        "--dashboard-url", $DashboardUrl,
        "--runs", $Runs.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        "--timeout-s", $TimeoutSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        "--max-runtime-s", $MaxRuntimeSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $argsList += @("--model", $Model)
    }
    if (-not [string]::IsNullOrWhiteSpace($ReasoningEffort)) {
        $argsList += @("--reasoning-effort", $ReasoningEffort)
    }
    & $python.Source @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
