param(
    [int]$TimeoutSeconds = 30,
    [int]$Port = 45454
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$udp = [System.Net.Sockets.UdpClient]::new($Port)
$udp.Client.ReceiveTimeout = 1000
$end = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 1))
$seen = @{}

try {
    while ((Get-Date) -lt $end) {
        $remote = [System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, 0)
        try {
            $bytes = $udp.Receive([ref]$remote)
        }
        catch [System.Net.Sockets.SocketException] {
            continue
        }
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
        try {
            $payload = $text | ConvertFrom-Json
        }
        catch {
            continue
        }
        if ($payload.type -ne "chasecar_robot_beacon") {
            continue
        }
        $key = "$($payload.hostname)|$($remote.Address)"
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            Write-Host "CHASECAR_ROBOT_BEACON=$text"
            Write-Host "REMOTE_ENDPOINT=$($remote.Address):$($remote.Port)"
        }
    }
}
finally {
    $udp.Close()
}

if ($seen.Count -gt 0) {
    exit 0
}

Write-Host "No Chasecar robot beacon received on UDP port $Port within $TimeoutSeconds seconds."
exit 1
