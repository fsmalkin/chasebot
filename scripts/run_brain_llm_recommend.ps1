param(
    [Parameter(Mandatory = $true)]
    [string]$Task,
    [string]$DashboardUrl = "http://127.0.0.1:8860",
    [string]$Model = "",
    [ValidateSet("low", "medium", "high")]
    [string]$ReasoningEffort = "",
    [double]$TimeoutSeconds = 45.0,
    [switch]$Approve,
    [switch]$PromptApprove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Get-Command python -ErrorAction Stop
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

$argsList = @(
    (Join-Path $repoRoot "scripts/brain_llm_recommend_runner.py"),
    "--task", $Task,
    "--dashboard-url", $DashboardUrl,
    "--timeout-s", $TimeoutSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)
)

if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $argsList += @("--model", $Model)
}
if (-not [string]::IsNullOrWhiteSpace($ReasoningEffort)) {
    $argsList += @("--reasoning-effort", $ReasoningEffort)
}
if ($Approve) {
    $argsList += "--approve"
}
if ($PromptApprove) {
    $argsList += "--prompt-approve"
}

Push-Location $repoRoot
try {
    & $python.Source @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
