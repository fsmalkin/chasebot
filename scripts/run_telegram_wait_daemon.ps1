param(
  [string]$ProjectName = "chasecar_telegram",
  [ValidateSet("up", "down", "logs", "status", "build")]
  [string]$Action = "up",
  [switch]$Build,
  [int]$Tail = 100
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

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

switch ($Action) {
  "up" {
    $args = @("--profile", "telegram", "up", "-d")
    if ($Build) {
      $args += "--build"
    }
    $args += "telegram-daemon"
    Invoke-Compose -Arguments $args
  }
  "down" {
    Invoke-Compose -Arguments @("--profile", "telegram", "stop", "telegram-daemon")
    Invoke-Compose -Arguments @("--profile", "telegram", "rm", "-f", "telegram-daemon")
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
}
