param(
  [string]$ProjectName = "chasecar_telegram",
  [ValidateSet("up", "down", "logs", "status", "build", "cleanup")]
  [string]$Action = "up",
  [switch]$Build,
  [int]$Tail = 100
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-Docker {
  param([string[]]$Arguments)

  & docker @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "docker failed with exit code $LASTEXITCODE"
  }
}

function Invoke-Compose {
  param([string[]]$Arguments)

  Push-Location $RepoRoot
  try {
    & docker compose -p $ProjectName @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose failed with exit code $LASTEXITCODE"
    }
  }
  finally {
    Pop-Location
  }
}

function Remove-StaleTelegramMcpRunContainers {
  $nameFilter = "name=$ProjectName-telegram-mcp-stdio-run-"
  $staleContainers = @((
      & docker ps -a --filter $nameFilter --format "{{.Names}}"
    ) | Where-Object { $_ })
  if ($LASTEXITCODE -ne 0) {
    throw "docker ps failed with exit code $LASTEXITCODE"
  }

  if (-not $staleContainers) {
    Write-Output "No stale telegram MCP run containers found."
    return
  }

  foreach ($containerName in $staleContainers) {
    Invoke-Docker -Arguments @("rm", "-f", $containerName)
  }
}

switch ($Action) {
  "up" {
    Remove-StaleTelegramMcpRunContainers
    $args = @("--profile", "telegram", "up", "-d")
    if ($Build) {
      $args += "--build"
    }
    $args += "telegram-daemon", "telegram-mcp-stdio"
    Invoke-Compose -Arguments $args
  }
  "down" {
    Invoke-Compose -Arguments @("--profile", "telegram", "stop", "telegram-daemon", "telegram-mcp-stdio")
    Invoke-Compose -Arguments @("--profile", "telegram", "rm", "-f", "telegram-daemon", "telegram-mcp-stdio")
    Remove-StaleTelegramMcpRunContainers
  }
  "logs" {
    Invoke-Compose -Arguments @("--profile", "telegram", "logs", "-f", "--tail", "$Tail", "telegram-daemon")
  }
  "status" {
    Invoke-Compose -Arguments @("--profile", "telegram", "ps", "telegram-daemon", "telegram-mcp-stdio")
  }
  "build" {
    Invoke-Compose -Arguments @("--profile", "telegram", "build", "telegram-daemon", "telegram-mcp-stdio")
  }
  "cleanup" {
    Remove-StaleTelegramMcpRunContainers
  }
}
