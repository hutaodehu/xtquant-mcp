param(
    [string]$RepoRoot = "D:\xtquant-mcp\repo",
    [string]$ConfigPath = "D:\xtquant-mcp\instance\prod\config\data_gateway.local.yaml",
    [string]$PythonExe = "",
    [string]$HealthUrl = "http://127.0.0.1:8766/healthz",
    [int]$WaitSeconds = 20,
    [switch]$Foreground,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"
$ExpectedServerName = "xtqmtDataGateway"

function Get-ListenerPids {
    param([int]$Port)

    $pattern = ":{0}\s+.*LISTENING\s+(\d+)$" -f [Regex]::Escape([string]$Port)
    $matches = netstat -ano | Select-String -Pattern $pattern
    $pids = @()
    foreach ($match in $matches) {
        $parts = ($match.ToString() -split "\s+") | Where-Object { $_ }
        if ($parts.Count -gt 0) {
            $pidToken = $parts[-1]
            $pidValue = 0
            if ([int]::TryParse($pidToken, [ref]$pidValue)) {
                $pids += $pidValue
            }
        }
    }
    return @($pids | Select-Object -Unique)
}

function Get-HealthPayload {
    param([string]$Url)

    try {
        return Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 2
    } catch {
        return $null
    }
}

function Test-ExpectedHealth {
    param(
        [object]$Health,
        [string]$ServerName,
        [string]$HealthUrl
    )

    if ($null -eq $Health) {
        return $false
    }
    try {
        $uri = [Uri]$HealthUrl
    } catch {
        return $false
    }
    if ([string]$Health.server_name -ne $ServerName) {
        return $false
    }
    if ([string]$Health.health_path -and ([string]$Health.health_path -ne $uri.AbsolutePath)) {
        return $false
    }
    if ($Health.bind_port -and ([int]$Health.bind_port -ne $uri.Port)) {
        return $false
    }
    return $true
}

function Wait-ListenerGone {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
    while ((Get-Date) -lt $deadline) {
        if ((Get-ListenerPids -Port $Port).Count -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return ((Get-ListenerPids -Port $Port).Count -eq 0)
}

function Resolve-PythonExe {
    param([string]$RequestedPythonExe)

    if ($RequestedPythonExe -and (Test-Path -LiteralPath $RequestedPythonExe)) {
        return (Resolve-Path -LiteralPath $RequestedPythonExe).Path
    }

    $venvPython = "D:\xtquant-mcp\venv313\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return (Resolve-Path -LiteralPath $venvPython).Path
    }

    $py313 = ""
    try {
        $py313 = (& py -3.13 -c "import sys; print(sys.executable)") 2>$null
    } catch {
        $py313 = ""
    }
    if ($LASTEXITCODE -eq 0 -and $py313) {
        return $py313.Trim()
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "No usable Python interpreter found."
}

$python = Resolve-PythonExe -RequestedPythonExe $PythonExe
$runner = Join-Path $RepoRoot "scripts\run_data_gateway_http.py"
$healthUri = [Uri]$HealthUrl
$listenerPids = @(Get-ListenerPids -Port $healthUri.Port)
$existingHealth = Get-HealthPayload -Url $HealthUrl
$existingMatches = Test-ExpectedHealth -Health $existingHealth -ServerName $ExpectedServerName -HealthUrl $HealthUrl
$stoppedListenerPids = @()

if ($Foreground) {
    & $python $runner --config $ConfigPath
    exit $LASTEXITCODE
}

if ($existingMatches -and -not $ForceRestart) {
    $report = [ordered]@{
        ok = $true
        status = "already_ready"
        pid = if ($listenerPids.Count -eq 1) { $listenerPids[0] } else { $null }
        listener_pids = $listenerPids
        stopped_listener_pids = $stoppedListenerPids
        health_url = $HealthUrl
        config_path = $ConfigPath
        expected_server_name = $ExpectedServerName
        stdout_log = ""
        stderr_log = ""
        health = $existingHealth
    }
    $report | ConvertTo-Json -Depth 8
    exit 0
}

if ($listenerPids.Count -gt 0) {
    if (-not $ForceRestart) {
        $report = [ordered]@{
            ok = $false
            status = "port_conflict"
            pid = if ($listenerPids.Count -eq 1) { $listenerPids[0] } else { $null }
            listener_pids = $listenerPids
            stopped_listener_pids = $stoppedListenerPids
            health_url = $HealthUrl
            config_path = $ConfigPath
            expected_server_name = $ExpectedServerName
            reason = "listener already bound on expected port but /healthz does not match expected repo gateway; rerun with -ForceRestart to replace it"
            health = $existingHealth
        }
        $report | ConvertTo-Json -Depth 8
        exit 1
    }

    foreach ($listenerPid in $listenerPids) {
        try {
            Stop-Process -Id $listenerPid -Force -ErrorAction Stop
            $stoppedListenerPids += $listenerPid
        } catch {
            $report = [ordered]@{
                ok = $false
                status = "stop_failed"
                pid = $listenerPid
                listener_pids = $listenerPids
                stopped_listener_pids = $stoppedListenerPids
                health_url = $HealthUrl
                config_path = $ConfigPath
                expected_server_name = $ExpectedServerName
                reason = "failed to stop stale listener: $($_.Exception.Message)"
                health = $existingHealth
            }
            $report | ConvertTo-Json -Depth 8
            exit 1
        }
    }

    if (-not (Wait-ListenerGone -Port $healthUri.Port -TimeoutSeconds 10)) {
        $report = [ordered]@{
            ok = $false
            status = "port_still_busy"
            pid = $null
            listener_pids = @(Get-ListenerPids -Port $healthUri.Port)
            stopped_listener_pids = $stoppedListenerPids
            health_url = $HealthUrl
            config_path = $ConfigPath
            expected_server_name = $ExpectedServerName
            reason = "port remained busy after stopping stale listener"
            health = (Get-HealthPayload -Url $HealthUrl)
        }
        $report | ConvertTo-Json -Depth 8
        exit 1
    }
}

$logDir = "D:\xtquant-mcp\instance\prod\logs\data_gateway"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$stdoutLog = Join-Path $logDir "data_gateway_${stamp}.log"
$stderrLog = Join-Path $logDir "data_gateway_${stamp}.stderr.log"

$proc = Start-Process `
    -FilePath $python `
    -ArgumentList @($runner, "--config", $ConfigPath) `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$deadline = (Get-Date).AddSeconds([Math]::Max(1, $WaitSeconds))
$health = $null
while ((Get-Date) -lt $deadline) {
    $health = Get-HealthPayload -Url $HealthUrl
    if (Test-ExpectedHealth -Health $health -ServerName $ExpectedServerName -HealthUrl $HealthUrl) {
        break
    }
    $health = $null
    Start-Sleep -Seconds 1
}

$report = [ordered]@{
    ok = $null -ne $health
    status = if ($null -ne $health) { "started" } else { "health_mismatch_or_unavailable" }
    pid = $proc.Id
    health_url = $HealthUrl
    config_path = $ConfigPath
    expected_server_name = $ExpectedServerName
    listener_pids = @(Get-ListenerPids -Port $healthUri.Port)
    stopped_listener_pids = $stoppedListenerPids
    stdout_log = $stdoutLog
    stderr_log = $stderrLog
    health = $health
}
$report | ConvertTo-Json -Depth 8
if ($report.ok) {
    exit 0
}
exit 1
