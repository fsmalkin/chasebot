param(
    [switch]$InstallBrowsers
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CurrentDashboardSessionId {
    param([string]$RepoRoot)

    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8860/api/state" -TimeoutSec 5
        $payload = $resp.Content | ConvertFrom-Json
        if ($payload -and -not [string]::IsNullOrWhiteSpace([string]$payload.session_id)) {
            return [string]$payload.session_id
        }
    }
    catch {
    }

    $statePath = Join-Path $RepoRoot "runtime/dashboard/dashboard_service_state.json"
    if (Test-Path -LiteralPath $statePath) {
        try {
            $payload = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            if ($payload -and -not [string]::IsNullOrWhiteSpace([string]$payload.session_id)) {
                return [string]$payload.session_id
            }
        }
        catch {
        }
    }
    return ""
}

function Copy-PlaywrightResults {
    param(
        [string]$RepoRoot,
        [string]$PlaywrightRoot,
        [string[]]$SessionIds
    )

    $resultsPath = Join-Path $PlaywrightRoot "test-results"
    if (-not (Test-Path -LiteralPath $resultsPath)) {
        return
    }

    foreach ($sessionId in ($SessionIds | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)) {
        $dest = Join-Path $RepoRoot "artifacts/session/$sessionId/dashboard_validation/playwright"
        if (Test-Path -LiteralPath $dest) {
            Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue
        }
        Copy-Item -LiteralPath $resultsPath -Destination $dest -Recurse -Force
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$playwrightRoot = Join-Path $repoRoot "dashboard_validation"

Push-Location $repoRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $playwrightRoot "node_modules"))) {
        npm install --prefix $playwrightRoot
    }
    if ($InstallBrowsers.IsPresent) {
        npx --prefix $playwrightRoot playwright install chromium
    }

    Push-Location $playwrightRoot
    try {
        npx playwright test
        $playwrightExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    $playwrightSessionId = Get-CurrentDashboardSessionId -RepoRoot $repoRoot
    Copy-PlaywrightResults -RepoRoot $repoRoot -PlaywrightRoot $playwrightRoot -SessionIds @($playwrightSessionId)

    pytest tests/dashboard
    $pytestExit = $LASTEXITCODE

    $finalSessionId = Get-CurrentDashboardSessionId -RepoRoot $repoRoot
    Copy-PlaywrightResults -RepoRoot $repoRoot -PlaywrightRoot $playwrightRoot -SessionIds @($playwrightSessionId, $finalSessionId)

    if ($playwrightExit -eq 0 -and $pytestExit -eq 0) {
        exit 0
    }
    exit 1
}
finally {
    Pop-Location
}
