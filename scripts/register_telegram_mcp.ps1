param(
  [string]$ServerName = "chasecar-telegram-wait",
  [string]$ProjectName = "chasecar_telegram",
  [switch]$ServeStdio
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ComposePath = Join-Path $RepoRoot "docker-compose.yml"
$GlobalServeMcpPath = "D:\services\codex-telegram\scripts\serve-mcp.ps1"

if ($ServeStdio -and (Test-Path $GlobalServeMcpPath)) {
  & powershell -ExecutionPolicy Bypass -File $GlobalServeMcpPath
  exit $LASTEXITCODE
}

function Convert-ToCanonicalPath {
  param([string]$Path)

  return [System.IO.Path]::GetFullPath($Path).TrimEnd("\", "/")
}

function Test-SamePath {
  param(
    [string]$Left,
    [string]$Right
  )

  if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
    return $false
  }

  try {
    return [StringComparer]::OrdinalIgnoreCase.Equals(
      (Convert-ToCanonicalPath -Path $Left),
      (Convert-ToCanonicalPath -Path $Right)
    )
  }
  catch {
    return $false
  }
}

function Invoke-Compose {
  param(
    [string[]]$Arguments,
    [switch]$Quiet,
    [switch]$SuppressStderr
  )

  Push-Location $RepoRoot
  try {
    if ($Quiet -or $SuppressStderr) {
      $nativeErrorPreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue
      $previousNativeErrorPreference = if ($nativeErrorPreference) { $global:PSNativeCommandUseErrorActionPreference } else { $null }
      $previousErrorActionPreference = $ErrorActionPreference
      try {
        $ErrorActionPreference = "Continue"
        if ($nativeErrorPreference) {
          $global:PSNativeCommandUseErrorActionPreference = $false
        }
        if ($Quiet) {
          & docker compose -f $ComposePath --project-directory $RepoRoot -p $ProjectName @Arguments > $null 2>&1
        }
        else {
          & docker compose -f $ComposePath --project-directory $RepoRoot -p $ProjectName @Arguments 2> $null
        }
      }
      finally {
        if ($nativeErrorPreference) {
          $global:PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
        $ErrorActionPreference = $previousErrorActionPreference
      }
    }
    else {
      & docker compose -f $ComposePath --project-directory $RepoRoot -p $ProjectName @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose failed with exit code $LASTEXITCODE"
    }
  }
  finally {
    Pop-Location
  }
}

function Remove-MismatchedTelegramComposeContainers {
  $containerNames = @((
      & docker ps -a --filter "label=com.docker.compose.project=$ProjectName" --format "{{.Names}}"
    ) | Where-Object { $_ })
  if ($LASTEXITCODE -ne 0) {
    throw "docker ps failed with exit code $LASTEXITCODE"
  }
  if ($containerNames.Count -eq 0) {
    return
  }

  $inspectedContainers = @(& docker inspect @containerNames | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0) {
    throw "docker inspect failed with exit code $LASTEXITCODE"
  }

  foreach ($container in $inspectedContainers) {
    $labels = $container.Config.Labels
    $service = $labels.'com.docker.compose.service'
    if ($service -notin @("telegram-daemon", "telegram-mcp-stdio")) {
      continue
    }

    $workingDir = $labels.'com.docker.compose.project.working_dir'
    $configFiles = @()
    if (-not [string]::IsNullOrWhiteSpace($labels.'com.docker.compose.project.config_files')) {
      $configFiles = @($labels.'com.docker.compose.project.config_files' -split ',')
    }
    $configMatches = ($configFiles | Where-Object { Test-SamePath -Left $_ -Right $ComposePath } | Select-Object -First 1) -ne $null

    if ((-not (Test-SamePath -Left $workingDir -Right $RepoRoot)) -or (-not $configMatches)) {
      $containerName = $container.Name.TrimStart("/")
      & docker rm -f $containerName *> $null
      if ($LASTEXITCODE -ne 0) {
        throw "docker rm failed with exit code $LASTEXITCODE"
      }
    }
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
    & docker rm -f $containerName *> $null
    if ($LASTEXITCODE -ne 0) {
      throw "docker rm failed with exit code $LASTEXITCODE"
    }
  }
}

if ($ServeStdio) {
  Remove-MismatchedTelegramComposeContainers
  Remove-StaleTelegramMcpRunContainers
  Invoke-Compose -Arguments @("--profile", "telegram", "up", "-d", "--build", "telegram-daemon", "telegram-mcp-stdio") -Quiet
  Invoke-Compose -Arguments @("--profile", "telegram", "exec", "-T", "telegram-mcp-stdio", "python", "-m", "telegram_wait_bridge.mcp_server") -SuppressStderr
  exit $LASTEXITCODE
}

& codex mcp remove $ServerName *> $null

& codex mcp add $ServerName -- powershell -ExecutionPolicy Bypass -File $PSCommandPath -ServeStdio -ProjectName $ProjectName
if ($LASTEXITCODE -ne 0) {
  throw "Failed to register MCP server $ServerName"
}

Write-Output "Registered MCP server $ServerName"
