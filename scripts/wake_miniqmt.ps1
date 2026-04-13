param(
    [string]$QmtExe = "D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe",
    [string]$PortHost = "127.0.0.1",
    [int]$Port = 58610,
    [int]$WaitSeconds = 30
)

$ErrorActionPreference = "Stop"

function Test-PortReady {
    param([string]$TargetHost, [int]$PortNumber)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($TargetHost, $PortNumber, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($async) | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

$report = [ordered]@{
    ok = $false
    qmt_exe = $QmtExe
    port_host = $PortHost
    port = $Port
    xtdata_port_ready_before = (Test-PortReady -TargetHost $PortHost -PortNumber $Port)
    process_started = $false
    process_id = $null
    status = ""
}

if ($report.xtdata_port_ready_before) {
    $report.ok = $true
    $report.status = "already_ready"
    $report | ConvertTo-Json -Depth 4
    exit 0
}

$existing = Get-Process -Name XtMiniQmt -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $existing) {
    if (-not (Test-Path -LiteralPath $QmtExe)) {
        throw "QMT executable not found: $QmtExe"
    }
    $proc = Start-Process -FilePath $QmtExe -PassThru
    $report.process_started = $true
    $report.process_id = $proc.Id
} else {
    $report.process_id = $existing.Id
}

$deadline = (Get-Date).AddSeconds([Math]::Max(1, $WaitSeconds))
while ((Get-Date) -lt $deadline) {
    if (Test-PortReady -TargetHost $PortHost -PortNumber $Port) {
        $report.ok = $true
        $report.status = "xtdata_port_ready"
        $report.xtdata_port_ready_after = $true
        $report | ConvertTo-Json -Depth 4
        exit 0
    }
    Start-Sleep -Seconds 1
}

$report.xtdata_port_ready_after = (Test-PortReady -TargetHost $PortHost -PortNumber $Port)
$report.ok = [bool]$report.xtdata_port_ready_after
$report.status = if ($report.ok) { "xtdata_port_ready" } else { "xtdata_port_not_ready" }
$report | ConvertTo-Json -Depth 4
if ($report.ok) {
    exit 0
}
exit 1
