param(
  [string]$ServerName = "chasecar-telegram-wait",
  [string]$ProjectName = "chasecar_telegram"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ComposePath = Join-Path $RepoRoot "docker-compose.yml"

try {
  codex mcp remove $ServerName | Out-Null
}
catch {
}

codex mcp add $ServerName -- docker compose -f $ComposePath --project-directory $RepoRoot -p $ProjectName --profile telegram run --rm -T telegram-mcp-stdio
if ($LASTEXITCODE -ne 0) {
  throw "Failed to register MCP server $ServerName"
}

Write-Output "Registered MCP server $ServerName"
