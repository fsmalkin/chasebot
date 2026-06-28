param(
    [string]$KnownHost = "192.168.1.11",
    [string]$BaseUrl = "http://192.168.1.11:8765",
    [string[]]$Subnets = @("192.168.86.0/24"),
    [int]$PingTimeoutMs = 1000,
    [int]$BridgeTimeoutSeconds = 5,
    [int]$SshTimeoutMs = 300,
    [int]$BeaconTimeoutSeconds = 8,
    [string]$ArtifactDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Get-UtcStamp {
    return (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
}

function Invoke-Captured {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Script
    )
    $started = Get-Date
    $output = ""
    $exitCode = 0
    try {
        $result = & $Script 2>&1
        $exitCode = if ($global:LASTEXITCODE -is [int]) { $global:LASTEXITCODE } else { 0 }
        $output = ($result | Out-String).Trim()
    }
    catch {
        $exitCode = 1
        $output = $_.Exception.Message
    }
    [ordered]@{
        label = $Label
        exit_code = $exitCode
        started_utc = $started.ToUniversalTime().ToString("o")
        completed_utc = (Get-Date).ToUniversalTime().ToString("o")
        output = $output
    }
}

function Get-IpEnabledAdapters {
    $adapters = @()
    foreach ($adapter in @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled = True")) {
        $adapters += [ordered]@{
            description = [string]$adapter.Description
            ip_address = @($adapter.IPAddress)
            default_gateway = @($adapter.DefaultIPGateway)
            mac_address = [string]$adapter.MACAddress
        }
    }
    return @($adapters)
}

function Get-SerialPorts {
    $ports = @()
    foreach ($port in @(Get-CimInstance Win32_SerialPort)) {
        $ports += [ordered]@{
            device_id = [string]$port.DeviceID
            name = [string]$port.Name
            description = [string]$port.Description
            pnp_device_id = [string]$port.PNPDeviceID
        }
    }
    return @($ports)
}

function Get-UsbHints {
    $hints = @()
    $entities = Get-CimInstance Win32_PnPEntity | Where-Object {
        $_.Name -match 'Jetson|Linux|RNDIS|USB Ethernet|Mass Storage|APX|L4T' -or
        $_.PNPDeviceID -match 'VID_0955|VID_18D1|VID_0525|VID_1D6B|RNDIS'
    }
    foreach ($entity in @($entities)) {
        $hints += [ordered]@{
            name = [string]$entity.Name
            status = [string]$entity.Status
            pnp_device_id = [string]$entity.PNPDeviceID
        }
    }
    return @($hints)
}

function Write-AccessMarkdown {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Summary
    )
    $lines = @(
        "# Robot Access Gate",
        "",
        "- generated_utc: ``$($Summary.generated_utc)``",
        "- known_host: ``$($Summary.known_host)``",
        "- base_url: ``$($Summary.base_url)``",
        "- access_ready: ``$($Summary.access_ready)``",
        "- bridge_ready: ``$($Summary.bridge_ready)``",
        "- ssh_candidate_count: ``$($Summary.ssh_candidate_count)``",
        "- beacon_seen: ``$($Summary.beacon_seen)``",
        "- jetbot_ap_visible: ``$($Summary.jetbot_ap_visible)``",
        "- motion_commands_sent: ``False``",
        "- next_action: $($Summary.next_action)",
        "",
        "## Checks",
        ""
    )
    foreach ($check in @($Summary.checks)) {
        $preview = ($check.output -replace "`r?`n", " ").Trim()
        if ($preview.Length -gt 180) {
            $preview = $preview.Substring(0, 180) + "..."
        }
        $lines += "- $($check.label): exit_code=``$($check.exit_code)`` output=``$preview``"
    }
    $lines += @(
        "",
        "## Boundary",
        "",
        "This gate discovers transport only. It sends no credentials and no movement commands."
    )
    $lines | Set-Content -Path $Path -Encoding UTF8
}

$repoRoot = Get-RepoRoot
if ([string]::IsNullOrWhiteSpace($ArtifactDir)) {
    $ArtifactDir = Join-Path $repoRoot ("artifacts/session/robot_access_gate_{0}" -f (Get-UtcStamp))
}
New-Item -ItemType Directory -Force -Path $ArtifactDir | Out-Null

$checks = @()
$wifiInterfaces = Invoke-Captured -Label "wifi_interfaces" -Script { netsh wlan show interfaces }
$checks += $wifiInterfaces
$wifiNetworks = Invoke-Captured -Label "wifi_networks" -Script { netsh wlan show networks mode=bssid }
$checks += $wifiNetworks
$wlanEvents = Invoke-Captured -Label "wlan_autoconfig_recent" -Script {
    Get-WinEvent -LogName Microsoft-Windows-WLAN-AutoConfig/Operational -MaxEvents 12 |
        Select-Object TimeCreated, Id, Message |
        Format-List
}
$checks += $wlanEvents
$knownPing = Invoke-Captured -Label "known_host_ping" -Script { ping -n 1 -w $PingTimeoutMs $KnownHost }
$checks += $knownPing
$bridgeHealth = Invoke-Captured -Label "bridge_health" -Script {
    curl.exe --http1.0 --no-keepalive --max-time $BridgeTimeoutSeconds --silent --show-error "$BaseUrl/health"
}
$checks += $bridgeHealth
$sshCandidates = Invoke-Captured -Label "ssh_candidates" -Script {
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "find_robot_ssh_candidates.ps1") -Subnets $Subnets -TimeoutMs $SshTimeoutMs -ThrottleLimit 96
}
$checks += $sshCandidates
$beacon = Invoke-Captured -Label "robot_beacon" -Script {
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "find_robot_beacon.ps1") -TimeoutSeconds $BeaconTimeoutSeconds
}
$checks += $beacon

$jetbotApVisible = $wifiNetworks.output -match 'jetbot-mini'
$knownHostReachable = $knownPing.exit_code -eq 0
$bridgeReady = $bridgeHealth.exit_code -eq 0 -and $bridgeHealth.output -match '"ok"\s*:\s*true'
$beaconSeen = $beacon.exit_code -eq 0 -and $beacon.output -match 'CHASECAR_ROBOT_BEACON='
$sshCandidateCount = 0
if ($sshCandidates.exit_code -eq 0 -and -not [string]::IsNullOrWhiteSpace($sshCandidates.output)) {
    try {
        $parsed = $sshCandidates.output | ConvertFrom-Json
        $sshCandidateCount = @($parsed).Count
    }
    catch {
        $sshCandidateCount = 0
    }
}

$nextAction = "Connect robot Ethernet to the mesh/router or restore a stable jetbot-mini AP, then rerun this gate."
if ($bridgeReady) {
    $nextAction = "Run locked bridge/camera/YOLO proof with --camera-fetch-mode ssh before any motion."
}
elseif ($sshCandidateCount -gt 0 -or $beaconSeen) {
    $nextAction = "Run scripts/check_robot_direct_access.ps1 against the reported candidate before deploying the bridge."
}

$summary = [ordered]@{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    type = "robot_access_gate"
    known_host = $KnownHost
    base_url = $BaseUrl
    subnets = @($Subnets)
    access_ready = [bool]($bridgeReady -or $sshCandidateCount -gt 0 -or $beaconSeen)
    bridge_ready = [bool]$bridgeReady
    known_host_reachable = [bool]$knownHostReachable
    ssh_candidate_count = [int]$sshCandidateCount
    beacon_seen = [bool]$beaconSeen
    jetbot_ap_visible = [bool]$jetbotApVisible
    motion_commands_sent = $false
    next_action = $nextAction
    checks = @($checks)
    adapters = @(Get-IpEnabledAdapters)
    serial_ports = @(Get-SerialPorts)
    usb_hints = @(Get-UsbHints)
}

$summaryPath = Join-Path $ArtifactDir "robot_access_gate_summary.json"
$scorecardPath = Join-Path $ArtifactDir "robot_access_gate.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8
Write-AccessMarkdown -Path $scorecardPath -Summary $summary

Write-Host "ROBOT_ACCESS_GATE_SUMMARY=$summaryPath"
Write-Host "ROBOT_ACCESS_GATE_SCORECARD=$scorecardPath"

if ($summary.access_ready) {
    exit 0
}
exit 1
