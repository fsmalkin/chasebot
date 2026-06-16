param(
    [Parameter(Mandatory = $true)]
    [string]$RobotHost,

    [string]$RobotUser = "",

    [string]$RobotRepoPath = "",

    [string]$RuntimeWorkspacePath = "~/ros2_ws/src/chasecar_runtime",

    [string]$CampaignId = ("robot_direct_access_preflight_{0}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")),

    [int]$ConnectTimeoutSeconds = 8,

    [switch]$AllowPasswordPrompt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function ConvertTo-BashLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value.Contains("'")) {
        throw "Single quotes are not supported in remote path values for this preflight script."
    }
    return "'$Value'"
}

function Invoke-RobotSshCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$RemoteCommand
    )

    $target = if ([string]::IsNullOrWhiteSpace($RobotUser)) { $RobotHost } else { "$RobotUser@$RobotHost" }
    $sshArgs = @(
        "-o", "ConnectTimeout=$ConnectTimeoutSeconds",
        "-o", "StrictHostKeyChecking=accept-new"
    )
    if (-not $AllowPasswordPrompt) {
        $sshArgs += @("-o", "BatchMode=yes")
    }
    $sshArgs += @($target, $RemoteCommand)

    Write-Host "[$Label] ssh $target" -ForegroundColor Cyan
    $output = & ssh @sshArgs 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | Out-String).Trim()
    if ($text) {
        Write-Host $text
    }
    return [ordered]@{
        label = $Label
        target = $target
        exit_code = $exitCode
        pass = ($exitCode -eq 0)
        output = $text
    }
}

$repoRoot = Get-RepoRoot
$artifactRoot = Join-Path $repoRoot ("artifacts/session/{0}/robot_direct_access_preflight" -f $CampaignId)
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

$checks = New-Object System.Collections.Generic.List[object]

$identityCommand = @'
set -eo pipefail
echo CHASECAR_SSH_OK=1
echo "hostname=$(hostname)"
echo "user=$(whoami)"
uname -a
'@
$checks.Add((Invoke-RobotSshCheck -Label "identity" -RemoteCommand $identityCommand))

$toolingCommand = @'
set -eo pipefail
for cmd in bash git python3 ssh; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd=$(command -v "$cmd")"
  else
    echo "$cmd=MISSING"
  fi
done
if command -v ros2 >/dev/null 2>&1; then
  echo "ros2=$(command -v ros2)"
else
  echo "ros2=MISSING"
fi
if command -v tailscale >/dev/null 2>&1; then
  tailscale ip -4 2>/dev/null | sed 's/^/tailscale_ipv4=/'
else
  echo "tailscale=MISSING"
fi
if [ -d /opt/ros ]; then
  find /opt/ros -maxdepth 1 -mindepth 1 -type d -printf 'ros_distro=%f\n' | sort
else
  echo "opt_ros=MISSING"
fi
'@
$checks.Add((Invoke-RobotSshCheck -Label "tooling" -RemoteCommand $toolingCommand))

$runtimePathLiteral = ConvertTo-BashLiteral -Value $RuntimeWorkspacePath
$repoPathLiteral = if ([string]::IsNullOrWhiteSpace($RobotRepoPath)) { "''" } else { ConvertTo-BashLiteral -Value $RobotRepoPath }
$pathCommand = @"
set -eo pipefail
expand_path() {
  case "`$1" in
    "~") echo "`$HOME" ;;
    "~/"*) echo "`$HOME/`${1#~/}" ;;
    *) echo "`$1" ;;
  esac
}
runtime_path=`$(expand_path $runtimePathLiteral)
repo_path=`$(expand_path $repoPathLiteral)
for item in "`$runtime_path" "`$repo_path"; do
  if [ -z "`$item" ]; then
    continue
  fi
  if [ -d "`$item" ]; then
    echo "path_exists=`$item"
    if [ -d "`$item/.git" ]; then
      git -C "`$item" rev-parse --show-toplevel | sed 's/^/git_root=/'
      git -C "`$item" rev-parse --abbrev-ref HEAD | sed 's/^/git_branch=/'
      git -C "`$item" rev-parse --short HEAD | sed 's/^/git_head=/'
    fi
  else
    echo "path_missing=`$item"
  fi
done
"@
$checks.Add((Invoke-RobotSshCheck -Label "paths" -RemoteCommand $pathCommand))

$issues = New-Object System.Collections.Generic.List[string]
foreach ($check in $checks) {
    if (-not $check.pass) {
        $issues.Add(("ssh_check_failed:{0}" -f $check.label))
    }
}

$combinedOutput = ($checks | ForEach-Object { $_.output }) -join "`n"
foreach ($required in @("CHASECAR_SSH_OK=1", "bash=", "git=", "python3=")) {
    if ($combinedOutput -notmatch [regex]::Escape($required)) {
        $issues.Add(("required_output_missing:{0}" -f $required))
    }
}
foreach ($warning in @("ros2=MISSING", "opt_ros=MISSING")) {
    if ($combinedOutput -match [regex]::Escape($warning)) {
        $issues.Add(("ros_command_surface_incomplete:{0}" -f $warning))
    }
}

$directAccessReady = -not ($issues | Where-Object { $_ -like "ssh_check_failed:*" -or $_ -like "required_output_missing:*" })
$rosCommandReady = $directAccessReady -and -not ($issues | Where-Object { $_ -like "ros_command_surface_incomplete:*" })
$runtimeUpdateReady = $directAccessReady -and ($combinedOutput -match "path_exists=")

$summary = [ordered]@{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    type = "robot_direct_access_preflight"
    campaign_id = $CampaignId
    robot_host = $RobotHost
    robot_user = $RobotUser
    robot_repo_path = $RobotRepoPath
    runtime_workspace_path = $RuntimeWorkspacePath
    direct_access_ready = [bool]$directAccessReady
    ros_command_ready = [bool]$rosCommandReady
    runtime_update_ready = [bool]$runtimeUpdateReady
    motion_commands_sent = $false
    issues = @($issues)
    checks = @($checks)
}

$summaryPath = Join-Path $artifactRoot "preflight_summary.json"
$scorecardPath = Join-Path $artifactRoot "scorecard.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8

$scorecard = @(
    "# Robot Direct Access Preflight",
    "",
    "- campaign_id: ``$CampaignId``",
    "- robot_host: ``$RobotHost``",
    "- robot_user: ``$RobotUser``",
    "- direct_access_ready: ``$directAccessReady``",
    "- ros_command_ready: ``$rosCommandReady``",
    "- runtime_update_ready: ``$runtimeUpdateReady``",
    "- motion_commands_sent: ``False``",
    "- issues: ``$($issues -join ', ')``",
    "",
    "## Checks",
    ""
)
foreach ($check in $checks) {
    $scorecard += "- $($check.label): pass=``$($check.pass)`` exit_code=``$($check.exit_code)``"
}
$scorecard += @(
    "",
    "## Boundary",
    "",
    "This preflight proves SSH-level command access and selected no-motion host surfaces. It does not send movement commands or prove physical robot safety."
)
$scorecard | Set-Content -Path $scorecardPath -Encoding UTF8

Write-Host "ROBOT_DIRECT_ACCESS_PREFLIGHT_SUMMARY=$summaryPath"
Write-Host "ROBOT_DIRECT_ACCESS_PREFLIGHT_SCORECARD=$scorecardPath"

if ($directAccessReady) {
    exit 0
}
exit 1
