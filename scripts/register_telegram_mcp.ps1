param(
  [string]$ServerName = "chasecar-telegram-wait",
  [string]$ProjectName = "chasecar_telegram",
  [switch]$ServeStdio
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ComposePath = Join-Path $RepoRoot "docker-compose.yml"

function Invoke-Compose {
  param([string[]]$Arguments)

  Push-Location $RepoRoot
  try {
    & docker compose -f $ComposePath --project-directory $RepoRoot -p $ProjectName @Arguments
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

  foreach ($containerName in $staleContainers) {
    & docker rm -f $containerName
    if ($LASTEXITCODE -ne 0) {
      throw "docker rm failed with exit code $LASTEXITCODE"
    }
  }
}

if ($ServeStdio) {
  Remove-StaleTelegramMcpRunContainers
  Invoke-Compose -Arguments @("--profile", "telegram", "up", "-d", "telegram-daemon", "telegram-mcp-stdio")
  Invoke-Compose -Arguments @("--profile", "telegram", "exec", "-T", "telegram-mcp-stdio", "python", "-m", "telegram_wait_bridge.mcp_server")
  exit $LASTEXITCODE
}

& codex mcp remove $ServerName *> $null

& codex mcp add $ServerName -- powershell -ExecutionPolicy Bypass -File $PSCommandPath -ServeStdio -ProjectName $ProjectName
if ($LASTEXITCODE -ne 0) {
  throw "Failed to register MCP server $ServerName"
}

Write-Output "Registered MCP server $ServerName"
