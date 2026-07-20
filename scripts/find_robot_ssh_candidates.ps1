param(
    [string[]]$Subnets = @(),

    [int]$Port = 22,

    [int]$TimeoutMs = 300,

    [int]$ThrottleLimit = 64
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DefaultSubnets {
    $configs = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled = True"
    $results = New-Object System.Collections.Generic.List[string]
    foreach ($config in $configs) {
        foreach ($ip in @($config.IPAddress)) {
            if ($ip -notmatch '^\d+\.\d+\.\d+\.\d+$') {
                continue
            }
            if ($ip -match '^(127|169\.254)\.') {
                continue
            }
            $parts = $ip.Split(".")
            if ($parts.Count -eq 4) {
                $results.Add(("{0}.{1}.{2}.0/24" -f $parts[0], $parts[1], $parts[2]))
            }
        }
    }
    return @($results | Select-Object -Unique)
}

function Expand-Subnet24 {
    param([Parameter(Mandatory = $true)][string]$Subnet)
    if ($Subnet -notmatch '^(\d+)\.(\d+)\.(\d+)\.0/24$') {
        throw "Only /24 subnets are supported by this lightweight scanner: $Subnet"
    }
    $prefix = "{0}.{1}.{2}" -f $matches[1], $matches[2], $matches[3]
    for ($i = 1; $i -le 254; $i++) {
        "$prefix.$i"
    }
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)][string]$HostAddress,
        [Parameter(Mandatory = $true)][int]$TargetPort,
        [Parameter(Mandatory = $true)][int]$Timeout
    )
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($HostAddress, $TargetPort, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne($Timeout, $false)
        if (-not $connected) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

if ($Subnets.Count -eq 0) {
    $Subnets = Get-DefaultSubnets
}

if ($Subnets.Count -eq 0) {
    throw "No active IPv4 /24 subnet found. Pass -Subnets manually, for example -Subnets 192.168.1.0/24."
}

$addresses = foreach ($subnet in $Subnets) { Expand-Subnet24 -Subnet $subnet }
$queue = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
foreach ($address in $addresses) {
    $queue.Enqueue($address)
}

$results = [System.Collections.Concurrent.ConcurrentBag[object]]::new()
$workers = for ($i = 0; $i -lt [Math]::Max(1, $ThrottleLimit); $i++) {
    [powershell]::Create().AddScript({
        param($Queue, $Results, $TargetPort, $Timeout)
        $address = ""
        while ($Queue.TryDequeue([ref]$address)) {
            $client = [System.Net.Sockets.TcpClient]::new()
            $open = $false
            try {
                $async = $client.BeginConnect($address, $TargetPort, $null, $null)
                $connected = $async.AsyncWaitHandle.WaitOne($Timeout, $false)
                if ($connected) {
                    $client.EndConnect($async)
                    $open = $true
                }
            }
            catch {
                $open = $false
            }
            finally {
                $client.Close()
            }
            if ($open) {
                $name = ""
                try {
                    $entry = [System.Net.Dns]::GetHostEntry($address)
                    $name = $entry.HostName
                }
                catch {
                    $name = ""
                }
                $Results.Add([pscustomobject]@{
                    ip = $address
                    port = $TargetPort
                    reverse_dns = $name
                })
            }
        }
    }).AddArgument($queue).AddArgument($results).AddArgument($Port).AddArgument($TimeoutMs)
}

$handles = foreach ($worker in $workers) { $worker.BeginInvoke() }
for ($i = 0; $i -lt $workers.Count; $i++) {
    $workers[$i].EndInvoke($handles[$i])
    $workers[$i].Dispose()
}

$ordered = @($results | Sort-Object ip)
if ($ordered.Count -eq 0) {
    Write-Host "No SSH candidates found on $($Subnets -join ', ') port $Port."
    exit 1
}

$ordered | ConvertTo-Json -Depth 4
exit 0
