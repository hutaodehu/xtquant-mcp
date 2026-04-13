param(
    [Parameter(Mandatory = $true)]
    [string]$TaskId,
    [string]$RepoRoot = "D:\xtquant-mcp\repo",
    [string]$PythonExe = "",
    [int]$RecoveryWaitSeconds = 20
)

$ErrorActionPreference = "Stop"

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

function Resolve-ShellExe {
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwsh) {
        return $pwsh.Source
    }
    $powershell = Get-Command powershell -ErrorAction SilentlyContinue
    if ($powershell) {
        return $powershell.Source
    }
    throw "No PowerShell executable found for gateway wake scripts."
}

function New-TimestampSlug {
    $now = Get-Date
    return "{0}{1}" -f $now.ToString("yyyyMMddTHHmmss"), $now.ToString("zzz").Replace(":", "")
}

function Get-StructuredContent {
    param([object]$Response)

    if ($null -eq $Response) {
        return $null
    }
    if ($null -ne $Response.result -and $null -ne $Response.result.structuredContent) {
        return $Response.result.structuredContent
    }
    if ($null -ne $Response.result -and $null -ne $Response.result.content -and $Response.result.content.Count -gt 0) {
        $text = [string]$Response.result.content[0].text
        if ($text) {
            try {
                return $text | ConvertFrom-Json -Depth 100
            } catch {
                return $text
            }
        }
    }
    return $null
}

function Get-ResourcePayload {
    param([object]$Response)

    if ($null -eq $Response -or $null -eq $Response.result -or $null -eq $Response.result.contents -or $Response.result.contents.Count -eq 0) {
        return $null
    }
    $text = [string]$Response.result.contents[0].text
    if (-not $text) {
        return $null
    }
    try {
        return $text | ConvertFrom-Json -Depth 100
    } catch {
        return $text
    }
}

function Invoke-JsonRpc {
    param(
        [string]$Url,
        [hashtable]$Request
    )

    return Invoke-RestMethod -Method Post -Uri $Url -ContentType "application/json" -Body ($Request | ConvertTo-Json -Depth 50 -Compress) -TimeoutSec 90
}

function Invoke-McpInitialize {
    param([string]$Url)

    $request = [ordered]@{
        jsonrpc = "2.0"
        id = $script:RpcId
        method = "initialize"
    }
    $script:RpcId += 1
    try {
        $response = Invoke-JsonRpc -Url $Url -Request $request
        return [ordered]@{
            transport_ok = $true
            request = $request
            response = $response
        }
    } catch {
        return [ordered]@{
            transport_ok = $false
            request = $request
            error = $_.Exception.Message
        }
    }
}

function Invoke-McpTool {
    param(
        [string]$Url,
        [string]$Name,
        [hashtable]$Arguments
    )

    $request = [ordered]@{
        jsonrpc = "2.0"
        id = $script:RpcId
        method = "tools/call"
        params = [ordered]@{
            name = $Name
            arguments = $Arguments
        }
    }
    $script:RpcId += 1
    try {
        $response = Invoke-JsonRpc -Url $Url -Request $request
        return [ordered]@{
            transport_ok = $true
            request = $request
            response = $response
            structured = Get-StructuredContent -Response $response
        }
    } catch {
        return [ordered]@{
            transport_ok = $false
            request = $request
            error = $_.Exception.Message
        }
    }
}

function Invoke-McpResource {
    param(
        [string]$Url,
        [string]$Uri
    )

    $request = [ordered]@{
        jsonrpc = "2.0"
        id = $script:RpcId
        method = "resources/read"
        params = [ordered]@{
            uri = $Uri
        }
    }
    $script:RpcId += 1
    try {
        $response = Invoke-JsonRpc -Url $Url -Request $request
        return [ordered]@{
            transport_ok = $true
            request = $request
            response = $response
            payload = Get-ResourcePayload -Response $response
        }
    } catch {
        return [ordered]@{
            transport_ok = $false
            request = $request
            error = $_.Exception.Message
        }
    }
}

function Test-ActiveMarketWindow {
    $now = Get-Date
    $weekday = $now.DayOfWeek
    $isWeekday = $weekday -in @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
    $minutes = ($now.Hour * 60) + $now.Minute
    $morningOpen = ($minutes -ge 570 -and $minutes -lt 690)
    $afternoonOpen = ($minutes -ge 780 -and $minutes -lt 900)
    $open = $isWeekday -and ($morningOpen -or $afternoonOpen)
    $session = if ($morningOpen) {
        "morning"
    } elseif ($afternoonOpen) {
        "afternoon"
    } elseif ($minutes -ge 690 -and $minutes -lt 780) {
        "midday_break"
    } else {
        "closed"
    }
    $reason = if ($open) {
        "market_window_open"
    } elseif (-not $isWeekday) {
        "market_window_closed_non_trading_day"
    } else {
        "market_window_closed"
    }
    return [ordered]@{
        open = $open
        session = $session
        observed_at = $now.ToString("o")
        reason = $reason
    }
}

function Invoke-WakeScript {
    param(
        [string]$ShellExe,
        [string]$ScriptPath,
        [string]$RepoRoot,
        [string]$ConfigPath,
        [string]$HealthUrl,
        [int]$WaitSeconds,
        [string]$OutputPath
    )

    $stdoutPath = "$OutputPath.stdout"
    $stderrPath = "$OutputPath.stderr"
    $proc = Start-Process `
        -FilePath $ShellExe `
        -ArgumentList @("-NoProfile", "-File", $ScriptPath, "-RepoRoot", $RepoRoot, "-ConfigPath", $ConfigPath, "-HealthUrl", $HealthUrl, "-WaitSeconds", [string]$WaitSeconds) `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    $waitTimeoutSeconds = [Math]::Max(($WaitSeconds + 15), 45)
    $finished = $proc.WaitForExit($waitTimeoutSeconds * 1000)
    if (-not $finished) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        } catch {
        }
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8 } else { "" }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -Encoding UTF8 } else { "" }
        $raw = ($stdout + [Environment]::NewLine + $stderr).Trim()
        if (-not $raw) {
            $raw = "wake script timed out after $waitTimeoutSeconds seconds without structured output"
        }
        Set-Content -LiteralPath $OutputPath -Value $raw -Encoding UTF8
        return [ordered]@{
            exit_code = 124
            output_path = $OutputPath
            parsed = [ordered]@{
                ok = $false
                status = "process_timeout"
                reason = "wake script timed out before returning structured output"
                pid = $proc.Id
            }
        }
    }

    $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8 } else { "" }
    $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -Encoding UTF8 } else { "" }
    $raw = ($stdout + [Environment]::NewLine + $stderr).Trim()
    $exitCode = $proc.ExitCode
    Set-Content -LiteralPath $OutputPath -Value $raw -Encoding UTF8
    $parsed = $null
    try {
        $parsed = $raw | ConvertFrom-Json -Depth 100
    } catch {
        $parsed = [ordered]@{
            ok = $false
            status = "invalid_json"
            reason = $_.Exception.Message
            raw = $raw
        }
    }
    return [ordered]@{
        exit_code = $exitCode
        output_path = $OutputPath
        parsed = $parsed
    }
}

function Invoke-PythonJsonCommand {
    param(
        [string]$PythonExe,
        [string]$ScriptPath,
        [string[]]$Arguments,
        [string]$OutputPath
    )

    $raw = & $PythonExe $ScriptPath @Arguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    Set-Content -LiteralPath $OutputPath -Value $raw -Encoding UTF8
    $parsed = $null
    try {
        $parsed = $raw | ConvertFrom-Json -Depth 100
    } catch {
        $parsed = [ordered]@{
            ok = $false
            parse_error = $_.Exception.Message
            raw = $raw
        }
    }
    return [ordered]@{
        exit_code = $exitCode
        output_path = $OutputPath
        parsed = $parsed
    }
}

function Get-NativeProbeSessionSummary {
    param([object]$NativeProbe)

    if ($null -eq $NativeProbe -or $null -eq $NativeProbe.results) {
        return ""
    }
    $parts = @()
    foreach ($item in $NativeProbe.results) {
        $parts += ("{0}={1}" -f [string]$item.session_id, [string]$item.ok)
    }
    return ($parts -join ", ")
}

function Get-TransportFailureSummary {
    param(
        [string]$ToolName,
        [object]$Call
    )

    if ($Call.transport_ok) {
        return $null
    }
    return "{0} transport failed: {1}" -f $ToolName, $Call.error
}

function Get-CallErrorCategory {
    param([object]$Call)

    if ($null -eq $Call -or -not $Call.transport_ok -or $null -eq $Call.structured) {
        return ""
    }
    if ($null -ne $Call.structured.error -and $Call.structured.error.category) {
        return [string]$Call.structured.error.category
    }
    return ""
}

function Get-CallBrokerOrderId {
    param([object]$Call)

    if ($null -eq $Call -or -not $Call.transport_ok -or $null -eq $Call.structured) {
        return ""
    }
    if ($null -ne $Call.structured.data -and $Call.structured.data.broker_order_id) {
        return [string]$Call.structured.data.broker_order_id
    }
    return ""
}

function Get-CallTraceId {
    param([object]$Call)

    if ($null -eq $Call -or -not $Call.transport_ok -or $null -eq $Call.structured) {
        return ""
    }
    if ($null -ne $Call.structured.audit -and $Call.structured.audit.trace_id) {
        return [string]$Call.structured.audit.trace_id
    }
    return ""
}

function Get-CallServerTs {
    param([object]$Call)

    if ($null -eq $Call -or -not $Call.transport_ok -or $null -eq $Call.structured) {
        return ""
    }
    if ($null -ne $Call.structured.audit -and $Call.structured.audit.server_ts) {
        return [string]$Call.structured.audit.server_ts
    }
    return ""
}

function Get-CallData {
    param([object]$Call)

    if ($null -eq $Call -or -not $Call.transport_ok -or $null -eq $Call.structured) {
        return $null
    }
    if ($null -ne $Call.structured.data) {
        return $Call.structured.data
    }
    return $null
}

function Get-CallAccountId {
    param([object]$Call)

    $data = Get-CallData -Call $Call
    if ($null -ne $data -and $data.account_id) {
        return [string]$data.account_id
    }
    return ""
}

function Get-CallReadyFlag {
    param([object]$Call)

    $data = Get-CallData -Call $Call
    if ($null -eq $data) {
        return $false
    }
    if ($data.ready -is [bool]) {
        return [bool]$data.ready
    }
    $text = [string]$data.ready
    if (-not $text.Trim()) {
        return $false
    }
    return $text.Trim().ToLowerInvariant() -eq "true"
}

function Get-CallDataFieldValue {
    param(
        [object]$Call,
        [string]$FieldName
    )

    $data = Get-CallData -Call $Call
    if ($null -eq $data -or -not $FieldName) {
        return $null
    }
    $property = $data.PSObject.Properties[$FieldName]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-CallBooleanField {
    param(
        [object]$Call,
        [string]$FieldName
    )

    $value = Get-CallDataFieldValue -Call $Call -FieldName $FieldName
    if ($null -eq $value) {
        return $false
    }
    if ($value -is [bool]) {
        return [bool]$value
    }
    $text = [string]$value
    if (-not $text.Trim()) {
        return $false
    }
    return $text.Trim().ToLowerInvariant() -eq "true"
}

function Get-CallStringField {
    param(
        [object]$Call,
        [string]$FieldName
    )

    $value = Get-CallDataFieldValue -Call $Call -FieldName $FieldName
    if ($null -eq $value) {
        return ""
    }
    return [string]$value
}

function Get-ProbeAuthorityState {
    param([object]$ProbeCall)

    $samePlanVerdict = Get-CallBooleanField -Call $ProbeCall -FieldName "same_plan_verdict"
    $probeCompleteVerdict = Get-CallBooleanField -Call $ProbeCall -FieldName "probe_complete_verdict"
    $freshConnectVerified = Get-CallBooleanField -Call $ProbeCall -FieldName "fresh_connect_verified"
    $writeAuthorityReady = Get-CallBooleanField -Call $ProbeCall -FieldName "write_authority_ready"
    $sessionResolution = Get-CallSessionResolution -Call $ProbeCall
    $sessionPlanVersion = Get-FirstNonEmptyValue -Values @(
        (Get-CallStringField -Call $ProbeCall -FieldName "session_plan_version"),
        [string]$sessionResolution.session_plan_version
    )
    return [ordered]@{
        same_plan_verdict = $samePlanVerdict
        probe_complete_verdict = $probeCompleteVerdict
        fresh_connect_verified = $freshConnectVerified
        write_authority_ready = $writeAuthorityReady
        ready = ($samePlanVerdict -and $probeCompleteVerdict -and $freshConnectVerified -and $writeAuthorityReady)
        reason = Get-CallStringField -Call $ProbeCall -FieldName "reason"
        probe_mode = Get-CallStringField -Call $ProbeCall -FieldName "probe_mode"
        session_id = Get-CallStringField -Call $ProbeCall -FieldName "session_id"
        observed_probe_session_id = Get-CallStringField -Call $ProbeCall -FieldName "observed_probe_session_id"
        session_plan_version = $sessionPlanVersion
    }
}

function New-SkippedNativeProbeBundle {
    param(
        [string]$OutputPath,
        [object]$RequestedSessions,
        [string]$Reason,
        [string]$UserDataPath,
        [string]$UserDataSource
    )

    $requested = ConvertTo-SessionIdArray -Value $RequestedSessions
    $probe = [ordered]@{
        overall_ok = $false
        skipped = $true
        reason = [string]$Reason
        requested_sessions = @($requested)
        user_data_path = [string]$UserDataPath
        user_data_source = [string]$UserDataSource
        results = @()
    }
    $probe | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    return [ordered]@{
        parsed = $probe
        output_path = $OutputPath
        ok = $false
        requested_sessions = @($requested)
        requested_sessions_text = (Get-SessionPlanText -Plan $requested)
        observed_sessions = @()
    }
}

function Get-CallQmtUserDataPath {
    param([object]$Call)

    $data = Get-CallData -Call $Call
    if ($null -eq $data) {
        return ""
    }
    if ($data.qmt_userdata) {
        return [string]$data.qmt_userdata
    }
    if ($null -ne $data.evidence -and $data.evidence.qmt_userdata) {
        return [string]$data.evidence.qmt_userdata
    }
    return ""
}

function Get-CallSessionResolution {
    param([object]$Call)

    $data = Get-CallData -Call $Call
    if ($null -ne $data -and $null -ne $data.effective_session_resolution) {
        return $data.effective_session_resolution
    }
    if ($null -ne $data -and $null -ne $data.session_resolution) {
        return $data.session_resolution
    }
    return $null
}

function Get-ResourceSessionResolution {
    param([object]$ResourceCall)

    if ($null -eq $ResourceCall -or -not $ResourceCall.transport_ok -or $null -eq $ResourceCall.payload) {
        return $null
    }
    if ($null -ne $ResourceCall.payload.payload -and $null -ne $ResourceCall.payload.payload.effective_session_resolution) {
        return $ResourceCall.payload.payload.effective_session_resolution
    }
    if ($null -ne $ResourceCall.payload.payload -and $null -ne $ResourceCall.payload.payload.session_resolution) {
        return $ResourceCall.payload.payload.session_resolution
    }
    if ($null -ne $ResourceCall.payload.effective_session_resolution) {
        return $ResourceCall.payload.effective_session_resolution
    }
    if ($null -ne $ResourceCall.payload.session_resolution) {
        return $ResourceCall.payload.session_resolution
    }
    return $null
}

function Get-ResourceQmtUserDataPath {
    param([object]$ResourceCall)

    if ($null -eq $ResourceCall -or -not $ResourceCall.transport_ok -or $null -eq $ResourceCall.payload) {
        return ""
    }
    if ($null -ne $ResourceCall.payload.payload) {
        if ($ResourceCall.payload.payload.qmt_userdata) {
            return [string]$ResourceCall.payload.payload.qmt_userdata
        }
        if ($null -ne $ResourceCall.payload.payload.evidence -and $ResourceCall.payload.payload.evidence.qmt_userdata) {
            return [string]$ResourceCall.payload.payload.evidence.qmt_userdata
        }
    }
    if ($ResourceCall.payload.qmt_userdata) {
        return [string]$ResourceCall.payload.qmt_userdata
    }
    if ($null -ne $ResourceCall.payload.evidence -and $ResourceCall.payload.evidence.qmt_userdata) {
        return [string]$ResourceCall.payload.evidence.qmt_userdata
    }
    return ""
}

function ConvertTo-SessionIdArray {
    param([object]$Value)

    $seen = @{}
    $result = New-Object System.Collections.ArrayList
    $pending = New-Object System.Collections.Queue
    if ($null -ne $Value) {
        $pending.Enqueue($Value)
    }
    while ($pending.Count -gt 0) {
        $item = $pending.Dequeue()
        if ($null -eq $item) {
            continue
        }
        if ($item -is [string]) {
            $text = [string]$item
            if (-not $text.Trim()) {
                continue
            }
            if ($text.Trim().StartsWith("[") -and $text.Trim().EndsWith("]")) {
                try {
                    $parsed = $text | ConvertFrom-Json -Depth 20
                    $pending.Enqueue($parsed)
                    continue
                } catch {
                }
            }
            foreach ($token in ($text -split ",")) {
                $pending.Enqueue($token)
            }
            continue
        }
        if ($item -is [System.Collections.IEnumerable] -and -not ($item -is [string])) {
            foreach ($child in $item) {
                $pending.Enqueue($child)
            }
            continue
        }
        try {
            $sessionId = [int]$item
        } catch {
            continue
        }
        if ($sessionId -lt 100) {
            $sessionId = 100
        }
        if (-not $seen.ContainsKey($sessionId)) {
            $seen[$sessionId] = $true
            [void]$result.Add($sessionId)
        }
    }
    return @($result)
}

function Get-SessionPlanText {
    param([object]$Plan)

    $normalized = ConvertTo-SessionIdArray -Value $Plan
    if ($normalized.Count -eq 0) {
        return "N/A"
    }
    return (($normalized | ForEach-Object { [string]$_ }) -join ",")
}

function Get-CallSessionPlan {
    param([object]$Call)

    return (ConvertTo-SessionIdArray -Value ((Get-CallSessionResolution -Call $Call).effective_session_plan))
}

function Get-ResourceSessionPlan {
    param([object]$ResourceCall)

    return (ConvertTo-SessionIdArray -Value ((Get-ResourceSessionResolution -ResourceCall $ResourceCall).effective_session_plan))
}

function Get-FirstNonEmptyValue {
    param([object[]]$Values)

    foreach ($value in $Values) {
        if ($null -eq $value) {
            continue
        }
        $text = [string]$value
        if ($text.Trim()) {
            return $text.Trim()
        }
    }
    return ""
}

function Normalize-PathText {
    param([object]$Value)

    $text = [string]$Value
    if (-not $text.Trim()) {
        return ""
    }
    $normalized = [Environment]::ExpandEnvironmentVariables($text.Trim())
    if ($normalized.Length -ge 2) {
        $first = $normalized.Substring(0, 1)
        $last = $normalized.Substring($normalized.Length - 1, 1)
        if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
            $normalized = $normalized.Substring(1, $normalized.Length - 2)
        }
    }
    try {
        return [System.IO.Path]::GetFullPath($normalized)
    } catch {
        return $normalized
    }
}

function Get-TradeConfigQmtUserDataPath {
    param([string]$ConfigPath)

    if (-not $ConfigPath) {
        return [ordered]@{
            found = $false
            path = ""
            source = ""
            reason = "trade_config_path_missing"
        }
    }
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        return [ordered]@{
            found = $false
            path = ""
            source = ""
            reason = "trade_config_not_found"
        }
    }

    $section = ""
    $values = @{}
    foreach ($line in (Get-Content -LiteralPath $ConfigPath -Encoding UTF8)) {
        if ($line -match '^\s*(#.*)?$') {
            continue
        }
        if ($line -match '^([A-Za-z0-9_]+):\s*$') {
            $section = $Matches[1].ToLowerInvariant()
            continue
        }
        if ($line -match '^\s{2}([A-Za-z0-9_]+):\s*(.+?)\s*$') {
            $key = $Matches[1].ToLowerInvariant()
            $value = Normalize-PathText -Value $Matches[2]
            if ($key -eq "qmt_userdata" -and $section) {
                $values[$section] = $value
            }
        }
    }

    foreach ($candidate in @("trade", "login", "qmt")) {
        if ($values.ContainsKey($candidate) -and $values[$candidate]) {
            return [ordered]@{
                found = $true
                path = [string]$values[$candidate]
                source = "trade_config:$candidate.qmt_userdata"
                reason = "ok"
            }
        }
    }

    return [ordered]@{
        found = $false
        path = ""
        source = ""
        reason = "qmt_userdata_missing_in_trade_config"
    }
}

function Get-TradeConfigQmtExePath {
    param([string]$ConfigPath)

    if (-not $ConfigPath) {
        return [ordered]@{
            found = $false
            path = ""
            source = ""
            reason = "trade_config_path_missing"
        }
    }
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        return [ordered]@{
            found = $false
            path = ""
            source = ""
            reason = "trade_config_not_found"
        }
    }

    $section = ""
    $values = @{}
    foreach ($line in (Get-Content -LiteralPath $ConfigPath -Encoding UTF8)) {
        if ($line -match '^\s*(#.*)?$') {
            continue
        }
        if ($line -match '^([A-Za-z0-9_]+):\s*$') {
            $section = $Matches[1].ToLowerInvariant()
            continue
        }
        if ($line -match '^\s{2}([A-Za-z0-9_]+):\s*(.+?)\s*$') {
            $key = $Matches[1].ToLowerInvariant()
            $value = Normalize-PathText -Value $Matches[2]
            if ($key -eq "qmt_exe" -and $section) {
                $values[$section] = $value
            }
        }
    }

    foreach ($candidate in @("trade", "login", "qmt")) {
        if ($values.ContainsKey($candidate) -and $values[$candidate]) {
            return [ordered]@{
                found = $true
                path = [string]$values[$candidate]
                source = "trade_config:$candidate.qmt_exe"
                reason = "ok"
            }
        }
    }

    return [ordered]@{
        found = $false
        path = ""
        source = ""
        reason = "qmt_exe_missing_in_trade_config"
    }
}

function Resolve-NativeUserDataPath {
    param(
        [string]$TradeConfigPath,
        [object]$LoginCall,
        [object]$LoginResource
    )

    $candidates = New-Object System.Collections.ArrayList
    foreach ($envName in @("XTQMT_NATIVE_USERDATA", "QMT_USERDATA")) {
        $envValue = Normalize-PathText -Value ([Environment]::GetEnvironmentVariable($envName))
        if ($envValue) {
            [void]$candidates.Add([ordered]@{
                    source = "env:$envName"
                    path = $envValue
                })
        }
    }

    $configCandidate = Get-TradeConfigQmtUserDataPath -ConfigPath $TradeConfigPath
    if ($configCandidate.found) {
        [void]$candidates.Add([ordered]@{
                source = [string]$configCandidate.source
                path = [string]$configCandidate.path
            })
    }

    $loginPath = Normalize-PathText -Value (Get-CallQmtUserDataPath -Call $LoginCall)
    if ($loginPath) {
        [void]$candidates.Add([ordered]@{
                source = "miniqmt.ensure_logged_in.evidence.qmt_userdata"
                path = $loginPath
            })
    }

    $loginResourcePath = Normalize-PathText -Value (Get-ResourceQmtUserDataPath -ResourceCall $LoginResource)
    if ($loginResourcePath) {
        [void]$candidates.Add([ordered]@{
                source = "diag://login/latest.evidence.qmt_userdata"
                path = $loginResourcePath
            })
    }

    $deduped = New-Object System.Collections.ArrayList
    $seenPaths = @{}
    foreach ($candidate in $candidates) {
        if (-not $candidate.path) {
            continue
        }
        if ($seenPaths.ContainsKey($candidate.path)) {
            continue
        }
        $seenPaths[$candidate.path] = $true
        $exists = Test-Path -LiteralPath $candidate.path -PathType Container
        [void]$deduped.Add([ordered]@{
                source = [string]$candidate.source
                path = [string]$candidate.path
                exists = $exists
            })
    }

    $selected = $null
    foreach ($candidate in $deduped) {
        if ($candidate.exists) {
            $selected = $candidate
            break
        }
    }
    if ($null -eq $selected -and $deduped.Count -gt 0) {
        $selected = $deduped[0]
    }

    $distinctPaths = @($deduped | ForEach-Object { [string]$_.path })
    return [ordered]@{
        ok = ($null -ne $selected -and $selected.exists)
        path = if ($null -ne $selected) { [string]$selected.path } else { "" }
        source = if ($null -ne $selected) { [string]$selected.source } else { "" }
        path_exists = ($null -ne $selected -and $selected.exists)
        mismatch = ($distinctPaths.Count -gt 1)
        distinct_paths = $distinctPaths
        candidates = @($deduped)
        reason = if ($null -eq $selected) { "qmt_userdata_unresolved" } elseif ($selected.exists) { "ok" } else { "qmt_userdata_path_not_found" }
        trade_config_path = [string]$TradeConfigPath
    }
}

function Test-SessionPlanAgreement {
    param([object[]]$Entries)

    $usable = @()
    foreach ($entry in $Entries) {
        $plan = ConvertTo-SessionIdArray -Value $entry.plan
        $usable += [ordered]@{
            name = [string]$entry.name
            plan = $plan
            plan_text = Get-SessionPlanText -Plan $plan
            available = ($plan.Count -gt 0)
        }
    }
    $available = @($usable | Where-Object { $_.available })
    if ($available.Count -eq 0) {
        return [ordered]@{
            ok = $false
            reason = "session_resolution_missing"
            canonical_source = ""
            canonical_plan = @()
            canonical_plan_text = "N/A"
            details = $usable
        }
    }
    $canonical = $available[0]
    $mismatches = @()
    $details = @()
    foreach ($entry in $usable) {
        $matches = $entry.available -and (($entry.plan -join ",") -eq ($canonical.plan -join ","))
        if (-not $entry.available) {
            $mismatches += ("{0}:missing" -f $entry.name)
        } elseif (-not $matches) {
            $mismatches += ("{0}:{1}" -f $entry.name, $entry.plan_text)
        }
        $details += [ordered]@{
            name = $entry.name
            available = $entry.available
            plan = $entry.plan
            plan_text = $entry.plan_text
            matches_canonical = $matches
        }
    }
    return [ordered]@{
        ok = ($mismatches.Count -eq 0)
        reason = if ($mismatches.Count -eq 0) { "ok" } else { "session_plan_mismatch" }
        canonical_source = $canonical.name
        canonical_plan = $canonical.plan
        canonical_plan_text = $canonical.plan_text
        mismatch_entries = $mismatches
        details = $details
    }
}

function Compare-SessionPlanToExpected {
    param(
        [object]$ExpectedPlan,
        [object[]]$Entries
    )

    $expected = ConvertTo-SessionIdArray -Value $ExpectedPlan
    $expectedText = Get-SessionPlanText -Plan $expected
    $usable = @()
    foreach ($entry in $Entries) {
        $plan = ConvertTo-SessionIdArray -Value $entry.plan
        $usable += [ordered]@{
            name = [string]$entry.name
            plan = $plan
            plan_text = Get-SessionPlanText -Plan $plan
            available = ($plan.Count -gt 0)
        }
    }
    if ($expected.Count -eq 0) {
        return [ordered]@{
            ok = $false
            reason = "expected_session_plan_missing"
            expected_plan = @()
            expected_plan_text = "N/A"
            details = $usable
        }
    }
    $mismatches = @()
    $details = @()
    foreach ($entry in $usable) {
        $matches = $entry.available -and (($entry.plan -join ",") -eq ($expected -join ","))
        if (-not $entry.available) {
            $mismatches += ("{0}:missing" -f $entry.name)
        } elseif (-not $matches) {
            $mismatches += ("{0}:{1}" -f $entry.name, $entry.plan_text)
        }
        $details += [ordered]@{
            name = $entry.name
            available = $entry.available
            plan = $entry.plan
            plan_text = $entry.plan_text
            matches_expected = $matches
        }
    }
    return [ordered]@{
        ok = ($mismatches.Count -eq 0)
        reason = if ($mismatches.Count -eq 0) { "ok" } else { "session_plan_mismatch" }
        expected_plan = $expected
        expected_plan_text = $expectedText
        mismatch_entries = $mismatches
        details = $details
    }
}

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

function Get-HealthProcessId {
    param([object]$Health)

    if ($null -eq $Health -or $null -eq $Health.process_identity) {
        return 0
    }
    try {
        return [int]$Health.process_identity.process_id
    } catch {
        return 0
    }
}

function Stop-ProcessIds {
    param([int[]]$Ids)

    $stopped = @()
    $errors = @()
    foreach ($id in @($Ids | Where-Object { $_ -gt 0 } | Select-Object -Unique)) {
        try {
            Stop-Process -Id $id -Force -ErrorAction Stop
            $stopped += [int]$id
        } catch {
            $errors += ("{0}:{1}" -f [int]$id, $_.Exception.Message)
        }
    }
    return [ordered]@{
        stopped = @($stopped)
        errors = @($errors)
        ok = ($errors.Count -eq 0)
    }
}

function Wait-ProcessNamesGone {
    param(
        [string[]]$Names,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds([Math]::Max(1, $TimeoutSeconds))
    while ((Get-Date) -lt $deadline) {
        $alive = @()
        foreach ($name in $Names) {
            $alive += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
        }
        if ($alive.Count -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    foreach ($name in $Names) {
        if (@(Get-Process -Name $name -ErrorAction SilentlyContinue).Count -gt 0) {
            return $false
        }
    }
    return $true
}

function Invoke-TradePreflightBundle {
    param(
        [string]$TradeMcpUrl,
        [string]$TradeConfigPath
    )

    $bundle = [ordered]@{}
    $bundle.init = Invoke-McpInitialize -Url $TradeMcpUrl
    $bundle.login = Invoke-McpTool -Url $TradeMcpUrl -Name "miniqmt.ensure_logged_in" -Arguments @{ login_timeout_seconds = 20 }
    $bundle.session_warm = Invoke-McpTool -Url $TradeMcpUrl -Name "session.warm" -Arguments @{}
    $bundle.session_status_pre = Invoke-McpTool -Url $TradeMcpUrl -Name "session.status" -Arguments @{}
    $bundle.probe_pre = Invoke-McpTool -Url $TradeMcpUrl -Name "probe.connection" -Arguments @{}
    $bundle.orders_pre = Invoke-McpTool -Url $TradeMcpUrl -Name "orders.list" -Arguments @{}
    $bundle.resource_session_pre = Invoke-McpResource -Url $TradeMcpUrl -Uri "trade://session/current"
    $bundle.resource_probe_pre = Invoke-McpResource -Url $TradeMcpUrl -Uri "diag://probe/latest"
    $bundle.resource_login_pre = Invoke-McpResource -Url $TradeMcpUrl -Uri "diag://login/latest"
    $bundle.native_probe_user_data = Resolve-NativeUserDataPath -TradeConfigPath $TradeConfigPath -LoginCall $bundle.login -LoginResource $bundle.resource_login_pre
    $bundle.session_resolution = [ordered]@{
        session_warm = Get-CallSessionResolution -Call $bundle.session_warm
        session_status_pre = Get-CallSessionResolution -Call $bundle.session_status_pre
        probe_pre = Get-CallSessionResolution -Call $bundle.probe_pre
        orders_pre = Get-CallSessionResolution -Call $bundle.orders_pre
        resource_session_pre = Get-ResourceSessionResolution -ResourceCall $bundle.resource_session_pre
    }
    $bundle.preflight_session_plan = Test-SessionPlanAgreement -Entries @(
        [ordered]@{ name = "session.warm"; plan = (Get-CallSessionPlan -Call $bundle.session_warm) },
        [ordered]@{ name = "session.status"; plan = (Get-CallSessionPlan -Call $bundle.session_status_pre) },
        [ordered]@{ name = "probe.connection"; plan = (Get-CallSessionPlan -Call $bundle.probe_pre) },
        [ordered]@{ name = "trade://session/current"; plan = (Get-ResourceSessionPlan -ResourceCall $bundle.resource_session_pre) }
    )
    $bundle.native_probe_requested_sessions = @($bundle.preflight_session_plan.canonical_plan)
    $bundle.native_probe_requested_sessions_text = Get-SessionPlanText -Plan $bundle.native_probe_requested_sessions
    $bundle.native_probe_session_source = [string]$bundle.preflight_session_plan.canonical_source
    $bundle.native_probe_account_id = Get-FirstNonEmptyValue -Values @(
        (Get-CallAccountId -Call $bundle.session_status_pre),
        (Get-CallAccountId -Call $bundle.session_warm),
        (Get-CallAccountId -Call $bundle.probe_pre)
    )
    return $bundle
}

function Invoke-NativeProbeBundle {
    param(
        [string]$PythonExe,
        [string]$ScriptPath,
        [string]$OutputPath,
        [object]$NativeUserData,
        [object]$RequestedSessions,
        [string]$AccountId
    )

    $requestedSessions = ConvertTo-SessionIdArray -Value $RequestedSessions
    $requestedText = Get-SessionPlanText -Plan $requestedSessions
    if ($requestedSessions.Count -eq 0) {
        $probe = [ordered]@{
            overall_ok = $false
            error = "preflight effective session plan is unavailable"
            requested_sessions = @()
            results = @()
        }
        $probe | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
        return [ordered]@{
            parsed = $probe
            output_path = $OutputPath
            ok = $false
            requested_sessions = @()
            requested_sessions_text = "N/A"
            observed_sessions = @()
            same_plan = (Compare-SessionPlanToExpected -ExpectedPlan @() -Entries @())
        }
    }
    if (-not $NativeUserData.ok) {
        $probe = [ordered]@{
            overall_ok = $false
            error = "native user-data-path unavailable: $($NativeUserData.reason)"
            requested_sessions = @($requestedSessions)
            user_data_path = [string]$NativeUserData.path
            user_data_source = [string]$NativeUserData.source
            results = @()
        }
        $probe | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
        return [ordered]@{
            parsed = $probe
            output_path = $OutputPath
            ok = $false
            requested_sessions = @($requestedSessions)
            requested_sessions_text = $requestedText
            observed_sessions = @()
            same_plan = (Compare-SessionPlanToExpected -ExpectedPlan $requestedSessions -Entries @())
        }
    }

    $args = @("--user-data-path", [string]$NativeUserData.path, "--sessions", $requestedText)
    if ($AccountId) {
        $args += @("--account-id", [string]$AccountId)
    }
    $probeCall = Invoke-PythonJsonCommand -PythonExe $PythonExe -ScriptPath $ScriptPath -Arguments $args -OutputPath $OutputPath
    $parsed = $probeCall.parsed
    $observedSessions = if ($null -ne $parsed -and $null -ne $parsed.results) {
        ConvertTo-SessionIdArray -Value @($parsed.results | ForEach-Object { $_.session_id })
    } else {
        @()
    }
    $samePlan = Compare-SessionPlanToExpected -ExpectedPlan $requestedSessions -Entries @(
        [ordered]@{ name = "native_probe"; plan = $observedSessions }
    )
    return [ordered]@{
        parsed = $parsed
        output_path = $probeCall.output_path
        ok = ($probeCall.exit_code -eq 0) -and $parsed.overall_ok
        requested_sessions = @($requestedSessions)
        requested_sessions_text = $requestedText
        observed_sessions = @($observedSessions)
        same_plan = $samePlan
    }
}

function Get-Conclusion {
    param(
        [object]$Runtime
    )

    if (-not $Runtime.market_window.open) {
        return [ordered]@{
            conclusion = "blocked"
            failure_layer = "environment"
            acceptance_position = "G4 not started"
            summary = "market window is closed; stop before order.place"
        }
    }

    if (-not $Runtime.trade_health_ok -or -not $Runtime.data_health_ok) {
        return [ordered]@{
            conclusion = "fail_env"
            failure_layer = "environment"
            acceptance_position = "Round 1 preflight failed"
            summary = "trade/data gateway health is not fully available after controlled recovery"
        }
    }

    if ($Runtime.clean_window.attempted -and -not $Runtime.clean_window.ok) {
        return [ordered]@{
            conclusion = "fail_env"
            failure_layer = "environment"
            acceptance_position = "Round 2 clean-window failed"
            summary = "session.close did not produce a clean pre-probe window before native broker/session probing"
        }
    }

    foreach ($pair in @(
        @{ name = "initialize"; call = $Runtime.init },
        @{ name = "miniqmt.ensure_logged_in"; call = $Runtime.login },
        @{ name = "session.warm"; call = $Runtime.session_warm },
        @{ name = "session.status"; call = $Runtime.session_status_pre },
        @{ name = "probe.connection"; call = $Runtime.probe_pre },
        @{ name = "orders.list"; call = $Runtime.orders_pre },
        @{ name = "trade://session/current"; call = $Runtime.resource_session_pre },
        @{ name = "diag://probe/latest"; call = $Runtime.resource_probe_pre },
        @{ name = "diag://login/latest"; call = $Runtime.resource_login_pre }
    )) {
        $failure = Get-TransportFailureSummary -ToolName $pair.name -Call $pair.call
        if ($failure) {
            return [ordered]@{
                conclusion = "fail_env"
                failure_layer = "environment"
                acceptance_position = "G4 preflight failed"
                summary = $failure
            }
        }
    }

    if (-not $Runtime.preflight_session_plan.ok) {
        return [ordered]@{
            conclusion = "fail_design"
            failure_layer = "design"
            acceptance_position = "Round 2 session plan mismatch"
            summary = "preflight tools did not expose one canonical session_resolution.effective_session_plan"
        }
    }

    if (-not $Runtime.packet_readiness.go) {
        switch ([string]$Runtime.packet_readiness.no_go_reason) {
            "runtime_same_plan_not_ready" {
                return [ordered]@{
                    conclusion = "fail_design"
                    failure_layer = "design"
                    acceptance_position = "Round 2 runtime same-plan verify failed"
                    summary = "gateway-side fresh authority did not stay on one canonical write session plan"
                }
            }
            "runtime_probe_not_complete" {
                return [ordered]@{
                    conclusion = "fail_env"
                    failure_layer = "environment"
                    acceptance_position = "Round 2 runtime probe incomplete"
                    summary = "gateway-side fresh authority did not complete the required same-session verify chain"
                }
            }
            "runtime_fresh_connect_not_verified" {
                return [ordered]@{
                    conclusion = "fail_env"
                    failure_layer = "environment"
                    acceptance_position = "Round 2 fresh connect not verified"
                    summary = "gateway-side probe.connection did not verify a fresh broker connect on the resolved write session"
                }
            }
            "runtime_write_authority_not_ready" {
                return [ordered]@{
                    conclusion = "fail_env"
                    failure_layer = "environment"
                    acceptance_position = "Round 2 runtime write authority not ready"
                    summary = "gateway-side fresh authority still does not permit a governed write attempt"
                }
            }
        }
    }

    if (-not $Runtime.order_place.executed) {
        return [ordered]@{
            conclusion = "blocked"
            failure_layer = "environment"
            acceptance_position = "G4 stopped before order.place"
            summary = "preflight did not authorize a real order.place call"
        }
    }

    if (-not $Runtime.postwrite_session_plan.ok) {
        return [ordered]@{
            conclusion = "fail_design"
            failure_layer = "design"
            acceptance_position = "G4 session plan mismatch"
            summary = "order.place packet did not preserve the canonical effective session plan across post-write evidence"
        }
    }

    $brokerOrderId = Get-CallBrokerOrderId -Call $Runtime.order_place.call
    if (-not $brokerOrderId) {
        $category = Get-CallErrorCategory -Call $Runtime.order_place.call
        return [ordered]@{
            conclusion = if ($category -eq "validation") { "fail_design" } else { "fail_env" }
            failure_layer = if ($category -eq "validation") { "design" } else { "environment" }
            acceptance_position = "G4 not passed"
            summary = "real order.place executed but no broker_order_id was obtained"
        }
    }

    $orderStatusOk = $Runtime.order_status.transport_ok
    $ordersAfterOk = $Runtime.orders_after.transport_ok
    $fillsOk = $Runtime.fills_list.transport_ok
    $cancelOk = $Runtime.order_cancel.skipped -or $Runtime.order_cancel.transport_ok
    if ($orderStatusOk -and $ordersAfterOk -and $fillsOk -and $cancelOk) {
        return [ordered]@{
            conclusion = "pass"
            failure_layer = ""
            acceptance_position = "G4 passed"
            summary = "broker_order_id and downstream order chain were observed"
        }
    }

    return [ordered]@{
        conclusion = "partial"
        failure_layer = "environment"
        acceptance_position = "G4 partially observed"
        summary = "broker_order_id was obtained but downstream order chain is incomplete"
    }
}

function Write-ControllerJudgment {
    param(
        [string]$Path,
        [object]$Contract,
        [string]$Timestamp,
        [string]$Mode,
        [object]$ArtifactSnapshot,
        [string]$ArtifactSnapshotPath,
        [object]$TradeWake,
        [object]$DataWake,
        [string]$RuntimePath,
        [bool]$ExecutedTest,
        [string]$Summary,
        [string]$NextStep
    )

    $localStage = if ($ArtifactSnapshot.local_stage) { [string]$ArtifactSnapshot.local_stage } else { "unknown" }
    $controllerAction = if ($ArtifactSnapshot.controller_action) { [string]$ArtifactSnapshot.controller_action } else { "unknown" }
    $latestReviewDecision = if ($ArtifactSnapshot.latest_review_decision) { [string]$ArtifactSnapshot.latest_review_decision } else { "N/A" }
    $executedText = if ($ExecutedTest) { "yes" } else { "no" }
    $runtimeCaptureRef = if ($RuntimePath) { [string]$RuntimePath } else { "N/A" }
    $content = @"
# $($Contract.task_id) Controller Judgment

Task ID: $($Contract.task_id)
Controller Mode: $Mode
Date: $Timestamp
Repo Root: $RepoRoot
Harness Skill Path: .agents/skills/spec-task-harness

## Task Contract

- Controller Test Policy: $($Contract.controller_test_policy)
- Acceptance Gate: $($Contract.acceptance_gate)
- Automation Policy: $($Contract.automation_policy)
- Execution Class: $($Contract.execution_class)
- Risk Class: $($Contract.risk_class)
- Formal Truth Snapshot: $ArtifactSnapshotPath
- Local Stage Before Run: $localStage
- Controller Action Before Run: $controllerAction
- Latest Review Decision: $latestReviewDecision
- Fixed Packet:
  - side: $($Contract.packet.side)
  - symbol: $($Contract.packet.symbol)
  - qty: $($Contract.packet.qty)
  - price_mode: $($Contract.packet.price_mode)
  - cancel_timeout: $($Contract.packet.cancel_timeout)

## Gateway Recovery

- Trade wake output: $($TradeWake.output_path)
- Trade wake status: $($TradeWake.parsed.status)
- Data wake output: $($DataWake.output_path)
- Data wake status: $($DataWake.parsed.status)

## Judgment

- Summary: $Summary
- Executed Test Role Work: $executedText
- Raw Runtime Capture: $runtimeCaptureRef
- Next Step: $NextStep
"@
    Set-Content -LiteralPath $Path -Value $content.TrimStart() -Encoding UTF8
}

function Write-EnvSnapshot {
    param(
        [string]$Path,
        [object]$Contract,
        [string]$Timestamp,
        [string]$ArtifactSnapshotPath,
        [string]$JudgmentPath,
        [string]$RuntimePath,
        [string]$TradeWakePath,
        [string]$DataWakePath,
        [string]$NativeProbePath,
        [string]$HostRecoveryPath,
        [string]$PacketReadinessPath,
        [object]$Runtime,
        [object]$Conclusion
    )

    $orderPlaceTrace = Get-CallTraceId -Call $Runtime.order_place.call
    $orderPlaceTs = Get-CallServerTs -Call $Runtime.order_place.call
    $nativeProbeSummary = Get-NativeProbeSessionSummary -NativeProbe $Runtime.native_probe
    if (-not $nativeProbeSummary) {
        $nativeProbeSummary = "N/A"
    }
    $content = @"
# EnvSnapshot

Task ID: $($Contract.task_id)
Date: $Timestamp
Role: test

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: $JudgmentPath
- Formal Truth Snapshot Link: $ArtifactSnapshotPath
- Raw Runtime Capture: $RuntimePath
- Gateway Recovery Output Link 1: $TradeWakePath
- Gateway Recovery Output Link 2: $DataWakePath
- Native Probe Output Link: $NativeProbePath
- Host Recovery Output Link: $HostRecoveryPath
- Packet Readiness Output Link: $PacketReadinessPath

## Environment

- Host: $env:COMPUTERNAME
- Repo Root: $RepoRoot
- Trade Health URL: $($Runtime.trade_health_url)
- Data Health URL: $($Runtime.data_health_url)
- Market Window Open: $($Runtime.market_window.open)
- Market Window Session: $($Runtime.market_window.session)
- Trade Health OK: $($Runtime.trade_health_ok)
- Data Health OK: $($Runtime.data_health_ok)

## Ordered Chain

- initialize transport_ok: $($Runtime.init.transport_ok)
- miniqmt.ensure_logged_in transport_ok: $($Runtime.login.transport_ok)
- session.warm transport_ok: $($Runtime.session_warm.transport_ok)
- session.status pre transport_ok: $($Runtime.session_status_pre.transport_ok)
- probe.connection pre transport_ok: $($Runtime.probe_pre.transport_ok)
- orders.list pre transport_ok: $($Runtime.orders_pre.transport_ok)
- trade://session/current pre transport_ok: $($Runtime.resource_session_pre.transport_ok)
- diag://probe/latest pre transport_ok: $($Runtime.resource_probe_pre.transport_ok)
- diag://login/latest pre transport_ok: $($Runtime.resource_login_pre.transport_ok)
- clean-window attempted: $($Runtime.clean_window.attempted)
- clean-window ok: $($Runtime.clean_window.ok)
- clean-window reason: $($Runtime.clean_window.reason)
- clean-window status_ready_after_close: $($Runtime.clean_window.status_ready_after_close)
- host recovery attempted: $($Runtime.host_recovery.attempted)
- host recovery ok: $($Runtime.host_recovery.ok)
- host recovery reason: $($Runtime.host_recovery.reason)
- runtime fresh authority ready: $($Runtime.preflight_runtime_authority.ready)
- runtime fresh authority reason: $($Runtime.preflight_runtime_authority.reason)
- runtime fresh authority probe_mode: $($Runtime.preflight_runtime_authority.probe_mode)
- runtime same-plan verdict: $($Runtime.preflight_runtime_authority.same_plan_verdict)
- runtime probe-complete verdict: $($Runtime.preflight_runtime_authority.probe_complete_verdict)
- runtime fresh-connect verified: $($Runtime.preflight_runtime_authority.fresh_connect_verified)
- runtime write-authority ready: $($Runtime.preflight_runtime_authority.write_authority_ready)
- native probe overall_ok: $($Runtime.native_probe_ok)
- native probe skipped: $($Runtime.native_probe.skipped)
- native probe user_data_path: $($Runtime.native_probe_user_data.path)
- native probe user_data source: $($Runtime.native_probe_user_data.source)
- native probe user_data exists: $($Runtime.native_probe_user_data.path_exists)
- native probe sessions: $nativeProbeSummary
- native probe requested sessions: $($Runtime.native_probe_requested_sessions_text)
- native probe session source: $($Runtime.native_probe_session_source)
- preflight effective session plan: $($Runtime.preflight_session_plan.canonical_plan_text)
- session_plan_version: $($Runtime.packet_readiness.session_plan_version)
- preflight same-plan verdict: $($Runtime.preflight_session_plan.ok)
- native probe same-plan verdict: $($Runtime.native_probe_same_plan.ok)
- packet readiness status: $($Runtime.packet_readiness.status)
- packet readiness no_go_reason: $($Runtime.packet_readiness.no_go_reason)
- order.place executed: $($Runtime.order_place.executed)
- order.place session plan: $($Runtime.order_place_session_plan_text)
- postwrite same-plan verdict: $($Runtime.postwrite_session_plan.ok)
- order.place trace_id: $orderPlaceTrace
- order.place server_ts: $orderPlaceTs
- Conclusion: $($Conclusion.conclusion)
- Acceptance Position: $($Conclusion.acceptance_position)
"@
    Set-Content -LiteralPath $Path -Value $content.TrimStart() -Encoding UTF8
}

function Write-EvidencePack {
    param(
        [string]$Path,
        [object]$Contract,
        [string]$Timestamp,
        [string]$ArtifactSnapshotPath,
        [string]$JudgmentPath,
        [string]$EnvSnapshotPath,
        [string]$RuntimePath,
        [string]$TradeWakePath,
        [string]$DataWakePath,
        [string]$NativeProbePath,
        [string]$HostRecoveryPath,
        [string]$PacketReadinessPath,
        [object]$Runtime,
        [object]$Conclusion
    )

    $orderPlaceTrace = Get-CallTraceId -Call $Runtime.order_place.call
    $orderPlaceTs = Get-CallServerTs -Call $Runtime.order_place.call
    $brokerOrderId = Get-CallBrokerOrderId -Call $Runtime.order_place.call
    $nativeProbeSummary = Get-NativeProbeSessionSummary -NativeProbe $Runtime.native_probe
    if (-not $nativeProbeSummary) {
        $nativeProbeSummary = "N/A"
    }
    $brokerOrderIdDisplay = if ($brokerOrderId) { [string]$brokerOrderId } else { "" }
    $content = @"
# EvidencePack

Task ID: $($Contract.task_id)
Role: test
Date: $Timestamp
Acceptance Gate: $($Contract.acceptance_gate)
Conclusion: $($Conclusion.conclusion)
Change Package Link: $($Contract.change_package_link)
Env Snapshot Link: $EnvSnapshotPath

## Execution Mode

- Executor: controller direct test execution
- Authorization Basis: operator-triggered execution on a TaskCard with Controller Test Policy: controller_direct_required
- Controller Judgment Link: $JudgmentPath
- Formal Truth Snapshot Link: $ArtifactSnapshotPath
- Raw Runtime Capture: $RuntimePath
- Gateway Recovery Output Link 1: $TradeWakePath
- Gateway Recovery Output Link 2: $DataWakePath
- Native Probe Output Link: $NativeProbePath
- Host Recovery Output Link: $HostRecoveryPath
- Packet Readiness Output Link: $PacketReadinessPath

## Fixed Packet

- side: $($Contract.packet.side)
- symbol: $($Contract.packet.symbol)
- qty: $($Contract.packet.qty)
- price_mode: $($Contract.packet.price_mode)
- cancel_timeout: $($Contract.packet.cancel_timeout)

## Gateway Recovery

- trade status: $($Runtime.trade_wake_status)
- data status: $($Runtime.data_wake_status)
- trade health ok: $($Runtime.trade_health_ok)
- data health ok: $($Runtime.data_health_ok)

## Raw Results

- market window open: $($Runtime.market_window.open)
- miniqmt.ensure_logged_in transport_ok: $($Runtime.login.transport_ok)
- session.warm transport_ok: $($Runtime.session_warm.transport_ok)
- session.status pre transport_ok: $($Runtime.session_status_pre.transport_ok)
- probe.connection pre transport_ok: $($Runtime.probe_pre.transport_ok)
- orders.list pre transport_ok: $($Runtime.orders_pre.transport_ok)
- trade://session/current pre transport_ok: $($Runtime.resource_session_pre.transport_ok)
- diag://probe/latest pre transport_ok: $($Runtime.resource_probe_pre.transport_ok)
- diag://login/latest pre transport_ok: $($Runtime.resource_login_pre.transport_ok)
- clean-window attempted: $($Runtime.clean_window.attempted)
- clean-window ok: $($Runtime.clean_window.ok)
- clean-window reason: $($Runtime.clean_window.reason)
- clean-window status_ready_after_close: $($Runtime.clean_window.status_ready_after_close)
- host recovery attempted: $($Runtime.host_recovery.attempted)
- host recovery ok: $($Runtime.host_recovery.ok)
- host recovery reason: $($Runtime.host_recovery.reason)
- runtime fresh authority ready: $($Runtime.preflight_runtime_authority.ready)
- runtime fresh authority reason: $($Runtime.preflight_runtime_authority.reason)
- runtime fresh authority probe_mode: $($Runtime.preflight_runtime_authority.probe_mode)
- runtime same-plan verdict: $($Runtime.preflight_runtime_authority.same_plan_verdict)
- runtime probe-complete verdict: $($Runtime.preflight_runtime_authority.probe_complete_verdict)
- runtime fresh-connect verified: $($Runtime.preflight_runtime_authority.fresh_connect_verified)
- runtime write-authority ready: $($Runtime.preflight_runtime_authority.write_authority_ready)
- native probe overall_ok: $($Runtime.native_probe_ok)
- native probe skipped: $($Runtime.native_probe.skipped)
- native probe user_data_path: $($Runtime.native_probe_user_data.path)
- native probe user_data source: $($Runtime.native_probe_user_data.source)
- native probe user_data exists: $($Runtime.native_probe_user_data.path_exists)
- native probe sessions: $nativeProbeSummary
- native probe requested sessions: $($Runtime.native_probe_requested_sessions_text)
- native probe session source: $($Runtime.native_probe_session_source)
- preflight effective session plan: $($Runtime.preflight_session_plan.canonical_plan_text)
- session_plan_version: $($Runtime.packet_readiness.session_plan_version)
- preflight same-plan verdict: $($Runtime.preflight_session_plan.ok)
- native probe same-plan verdict: $($Runtime.native_probe_same_plan.ok)
- packet readiness status: $($Runtime.packet_readiness.status)
- packet readiness no_go_reason: $($Runtime.packet_readiness.no_go_reason)
- real order.place executed: $($Runtime.order_place.executed)
- order.place session plan: $($Runtime.order_place_session_plan_text)
- postwrite same-plan verdict: $($Runtime.postwrite_session_plan.ok)
- order.place trace_id: $orderPlaceTrace
- order.place server_ts: $orderPlaceTs
- broker_order_id: $brokerOrderIdDisplay
- post-session.status transport_ok: $($Runtime.session_status_post.transport_ok)
- post-probe.connection transport_ok: $($Runtime.probe_post.transport_ok)
- post-orders.list transport_ok: $($Runtime.orders_after.transport_ok)
- order.status transport_ok: $($Runtime.order_status.transport_ok)
- order.cancel skipped: $($Runtime.order_cancel.skipped)
- order.cancel transport_ok: $($Runtime.order_cancel.transport_ok)
- fills.list transport_ok: $($Runtime.fills_list.transport_ok)

## Classification

- Final Conclusion: $($Conclusion.conclusion)
- Failure Layer: $($Conclusion.failure_layer)
- Acceptance Position: $($Conclusion.acceptance_position)

## Test Conclusion

$($Conclusion.summary)
"@
    Set-Content -LiteralPath $Path -Value $content.TrimStart() -Encoding UTF8
}

function Write-TradeWriteAuthoritySource {
    param(
        [string]$Path,
        [string]$LatestPath,
        [string]$PacketId,
        [object]$Contract,
        [string]$Timestamp,
        [object]$ArtifactSnapshot,
        [string]$ArtifactSnapshotPath,
        [string]$JudgmentPath,
        [string]$EvidencePath,
        [string]$EnvSnapshotPath,
        [string]$RuntimePath,
        [string]$PacketReadinessPath,
        [string]$DiagProbePath,
        [object]$Runtime
    )

    $reviewDecision = ""
    $tradeLaneWriteClosed = $false
    $tradeLaneWriteState = "open"
    $taskStatus = "Blocked"
    $blockingReason = Get-FirstNonEmptyValue -Values @(
        [string]$Runtime.packet_readiness.no_go_reason,
        "fresh_review_pending"
    )
    $traceId = Get-FirstNonEmptyValue -Values @(
        (Get-CallTraceId -Call $Runtime.probe_post),
        (Get-CallTraceId -Call $Runtime.probe_pre),
        (Get-CallTraceId -Call $Runtime.order_place.call)
    )

    $carrier = [ordered]@{
        schema_version = "v1"
        carrier_type = "trade_write_formal_authority"
        task_id = [string]$Contract.task_id
        acceptance_gate = [string]$Contract.acceptance_gate
        packet_id = [string]$PacketId
        generated_at = [string]$Timestamp
        trace_id = [string]$traceId
        diag_probe_ref = [string]$DiagProbePath
        controller_judgment_ref = [string]$JudgmentPath
        review_ref = ""
        formal_truth_snapshot_ref = [string]$ArtifactSnapshotPath
        env_snapshot_ref = [string]$EnvSnapshotPath
        evidence_pack_ref = [string]$EvidencePath
        runtime_capture_ref = [string]$RuntimePath
        packet_readiness_ref = [string]$PacketReadinessPath
        formal_closeout_state = [ordered]@{
            trade_lane_write_closed = [bool]$tradeLaneWriteClosed
            trade_lane_write_state = [string]$tradeLaneWriteState
            task_id = [string]$Contract.task_id
            status = [string]$taskStatus
            gate = [string]$Contract.acceptance_gate
            reason = [string]$blockingReason
            review_decision = [string]$reviewDecision
        }
        artifact_refs = [ordered]@{
            review_pack = ""
            evidence_pack = [string]$EvidencePath
            env_snapshot = [string]$EnvSnapshotPath
            controller_judgment = [string]$JudgmentPath
            runtime_capture = [string]$RuntimePath
            diag_probe = [string]$DiagProbePath
            packet_readiness = [string]$PacketReadinessPath
        }
    }

    $json = $carrier | ConvertTo-Json -Depth 20
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
    if ($LatestPath) {
        $latestDir = Split-Path -Parent $LatestPath
        if ($latestDir) {
            New-Item -ItemType Directory -Path $latestDir -Force | Out-Null
        }
        Set-Content -LiteralPath $LatestPath -Value $json -Encoding UTF8
    }
}

$python = Resolve-PythonExe -RequestedPythonExe $PythonExe
$shellExe = Resolve-ShellExe
$tmpDir = Join-Path $RepoRoot ".tmp\spec-task-harness"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
$instanceRoot = Join-Path (Split-Path -Parent $RepoRoot) "instance\prod"
$slug = New-TimestampSlug
$artifactStamp = Get-Date -Format "yyyyMMddHHmm"
$timestamp = Get-Date -Format "o"

$validator = Join-Path $RepoRoot ".agents\skills\spec-task-harness\scripts\validate_taskcard.py"
$contractRaw = & $python $validator --repo-root $RepoRoot --task-id $TaskId --dump-json 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    throw "TaskCard validation failed for $TaskId`n$contractRaw"
}
$contract = $contractRaw | ConvertFrom-Json -Depth 100
if ([string]$contract.controller_test_policy -ne "controller_direct_required") {
    throw "Task $TaskId is not configured for controller direct test execution."
}

$tradeConfigPath = if ($contract.trade_config_path) { [string]$contract.trade_config_path } else { "D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml" }
$dataConfigPath = if ($contract.data_config_path) { [string]$contract.data_config_path } else { "D:\xtquant-mcp\instance\prod\config\data_gateway.local.yaml" }
$tradeHealthUrl = if ($contract.trade_health_url) { [string]$contract.trade_health_url } else { "http://127.0.0.1:8765/healthz" }
$dataHealthUrl = if ($contract.data_health_url) { [string]$contract.data_health_url } else { "http://127.0.0.1:8766/healthz" }
$tradeMcpUrl = ($tradeHealthUrl -replace "/healthz$", "/mcp")
$nativeUserDataPath = ""
$nativeProbeSessions = ""

$artifactSnapshotPath = Join-Path $tmpDir ("{0}-artifact-snapshot-{1}.json" -f $TaskId.ToLower(), $slug)
$tradeWakePath = Join-Path $tmpDir ("{0}-trade-wake-{1}.json" -f $TaskId.ToLower(), $slug)
$dataWakePath = Join-Path $tmpDir ("{0}-data-wake-{1}.json" -f $TaskId.ToLower(), $slug)
$nativeProbePath = Join-Path $tmpDir ("{0}-native-probe-{1}.json" -f $TaskId.ToLower(), $slug)
$hostRecoveryPath = Join-Path $tmpDir ("{0}-host-recovery-{1}.json" -f $TaskId.ToLower(), $slug)
$packetReadinessPath = Join-Path $tmpDir ("{0}-packet-readiness-{1}.json" -f $TaskId.ToLower(), $slug)
$runtimePath = Join-Path $tmpDir ("{0}-controller-direct-runtime-{1}.json" -f $TaskId.ToLower(), $slug)
$judgmentPath = Join-Path $tmpDir ("{0}-controller-judgment-{1}-controller-direct-test.md" -f $TaskId, $slug)
$authoritySourcePath = Join-Path $tmpDir ("{0}-trade-write-authority-source-{1}.json" -f $TaskId.ToLower(), $slug)
$authoritySourceLatestPath = Join-Path $instanceRoot "state\trade_resources\trade_write_authority_source_latest.json"
$diagProbeLatestPath = Join-Path $instanceRoot "state\trade_resources\diag_probe_latest.json"
$evidencePath = Join-Path $RepoRoot ("docs\evidence_packs\{0}-test-{1}-controller-direct-live.md" -f $TaskId, $artifactStamp)
$envSnapshotPath = Join-Path $RepoRoot ("docs\env_snapshots\{0}-{1}-controller-direct-live.md" -f $TaskId, $artifactStamp)

$collectArtifacts = Join-Path $RepoRoot ".agents\skills\spec-task-harness\scripts\collect_artifacts.py"
$artifactSnapshot = Invoke-PythonJsonCommand -PythonExe $python -ScriptPath $collectArtifacts -Arguments @("--repo-root", $RepoRoot, "--task-id", $TaskId) -OutputPath $artifactSnapshotPath
if ($artifactSnapshot.exit_code -ne 0) {
    throw "Failed to collect current formal truth for $TaskId"
}

$tradeWake = Invoke-WakeScript -ShellExe $shellExe -ScriptPath (Join-Path $RepoRoot "scripts\wake_trade_gateway.ps1") -RepoRoot $RepoRoot -ConfigPath $tradeConfigPath -HealthUrl $tradeHealthUrl -WaitSeconds $RecoveryWaitSeconds -OutputPath $tradeWakePath
$dataWake = Invoke-WakeScript -ShellExe $shellExe -ScriptPath (Join-Path $RepoRoot "scripts\wake_data_gateway.ps1") -RepoRoot $RepoRoot -ConfigPath $dataConfigPath -HealthUrl $dataHealthUrl -WaitSeconds $RecoveryWaitSeconds -OutputPath $dataWakePath

$tradeWakeOk = ($tradeWake.exit_code -eq 0) -and $tradeWake.parsed.ok
$dataWakeOk = ($dataWake.exit_code -eq 0) -and $dataWake.parsed.ok

if (-not ($tradeWakeOk -and $dataWakeOk)) {
    $summary = "gateway recovery did not reach expected repo listeners"
    $nextStep = "stay no-go; do not execute direct test until trade and data wake scripts both report ok=true without ForceRestart"
    Write-ControllerJudgment -Path $judgmentPath -Contract $contract -Timestamp $timestamp -Mode "controller-only" -ArtifactSnapshot $artifactSnapshot.parsed -ArtifactSnapshotPath $artifactSnapshot.output_path -TradeWake $tradeWake -DataWake $dataWake -RuntimePath "" -ExecutedTest $false -Summary $summary -NextStep $nextStep
    [ordered]@{
        ok = $false
        status = "gateway_recovery_failed"
        task_id = $TaskId
        controller_judgment = $judgmentPath
        formal_truth_snapshot = $artifactSnapshot.output_path
        trade_wake = $tradeWake.output_path
        data_wake = $dataWake.output_path
    } | ConvertTo-Json -Depth 8
    exit 1
}

$script:RpcId = 1
$runtime = [ordered]@{
    task_id = $TaskId
    wall_clock_start = (Get-Date).ToString("o")
    trade_wake_status = $tradeWake.parsed.status
    data_wake_status = $dataWake.parsed.status
    trade_health_url = $tradeHealthUrl
    data_health_url = $dataHealthUrl
}

try {
    $runtime.trade_health = Invoke-RestMethod -Method Get -Uri $tradeHealthUrl -TimeoutSec 5
    $runtime.trade_health_ok = $true
} catch {
    $runtime.trade_health = [ordered]@{ error = $_.Exception.Message }
    $runtime.trade_health_ok = $false
}
try {
    $runtime.data_health = Invoke-RestMethod -Method Get -Uri $dataHealthUrl -TimeoutSec 5
    $runtime.data_health_ok = $true
} catch {
    $runtime.data_health = [ordered]@{ error = $_.Exception.Message }
    $runtime.data_health_ok = $false
}

$runtime.market_window = Test-ActiveMarketWindow
$nativeProbeScript = Join-Path $RepoRoot ".agents\skills\spec-task-harness\scripts\run_native_broker_session_probe.py"
$hostRecoveryScript = Join-Path $RepoRoot "scripts\controller_direct_host_recovery.py"
$cooldownSeconds = 5
$qmtExeCandidate = Get-TradeConfigQmtExePath -ConfigPath $tradeConfigPath
$runtime.clean_window = [ordered]@{
    attempted = $false
    ok = $false
    cooldown_seconds = $cooldownSeconds
    reason = "not_needed"
}
$runtime.host_recovery = [ordered]@{
    attempted = $false
    ok = $false
    reason = "not_needed"
}

$initialPreflight = Invoke-TradePreflightBundle -TradeMcpUrl $tradeMcpUrl -TradeConfigPath $tradeConfigPath
$initialFreshAuthority = Get-ProbeAuthorityState -ProbeCall $initialPreflight.probe_pre
$runtime.round2_initial_preflight = [ordered]@{
    preflight_session_plan = $initialPreflight.preflight_session_plan
    native_probe_user_data = $initialPreflight.native_probe_user_data
    fresh_authority = $initialFreshAuthority
}

$finalPreflight = $initialPreflight
if ($initialFreshAuthority.ready) {
    $runtime.clean_window.ok = $true
    $runtime.clean_window.reason = "skipped_runtime_fresh_authority_ready"
    $finalNativeProbe = New-SkippedNativeProbeBundle `
        -OutputPath $nativeProbePath `
        -RequestedSessions $initialPreflight.native_probe_requested_sessions `
        -Reason "skipped_runtime_fresh_authority_ready" `
        -UserDataPath ([string]$initialPreflight.native_probe_user_data.path) `
        -UserDataSource ([string]$initialPreflight.native_probe_user_data.source)
} else {
    $runtime.clean_window.attempted = $true
    $runtime.clean_window.session_close = Invoke-McpTool -Url $tradeMcpUrl -Name "session.close" -Arguments @{}
    $runtime.clean_window.session_status_after_close = Invoke-McpTool -Url $tradeMcpUrl -Name "session.status" -Arguments @{}
    $runtime.clean_window.resource_session_after_close = Invoke-McpResource -Url $tradeMcpUrl -Uri "trade://session/current"
    $runtime.clean_window.status_ready_after_close = Get-CallReadyFlag -Call $runtime.clean_window.session_status_after_close
    $runtime.clean_window.ok = (
        $runtime.clean_window.session_close.transport_ok -and
        $runtime.clean_window.session_status_after_close.transport_ok -and
        (-not $runtime.clean_window.status_ready_after_close)
    )
    $runtime.clean_window.reason = if ($runtime.clean_window.ok) { "ok" } else { "session_still_ready_after_close" }
    Start-Sleep -Seconds $cooldownSeconds

    $initialNativeProbe = Invoke-NativeProbeBundle `
        -PythonExe $python `
        -ScriptPath $nativeProbeScript `
        -OutputPath $nativeProbePath `
        -NativeUserData $initialPreflight.native_probe_user_data `
        -RequestedSessions $initialPreflight.native_probe_requested_sessions `
        -AccountId ([string]$initialPreflight.native_probe_account_id)
    $runtime.clean_window.native_probe_before_recovery = $initialNativeProbe.parsed

    $finalNativeProbe = $initialNativeProbe

    if (-not $initialNativeProbe.ok -and $initialPreflight.native_probe_user_data.ok -and $initialPreflight.native_probe_requested_sessions.Count -gt 0) {
        $runtime.host_recovery.attempted = $true
        $inspect = Invoke-PythonJsonCommand -PythonExe $python -ScriptPath $hostRecoveryScript -Arguments @(
            "inspect",
            "--user-data-path", [string]$initialPreflight.native_probe_user_data.path,
            "--sessions", [string]$initialNativeProbe.requested_sessions_text,
            "--log-tail-lines", "120"
        ) -OutputPath $hostRecoveryPath
        $runtime.host_recovery.inspect = $inspect.parsed
        $runtime.host_recovery.inspect_ok = ($inspect.exit_code -eq 0)

        $tradePort = ([Uri]$tradeHealthUrl).Port
        $dataPort = ([Uri]$dataHealthUrl).Port
        $tradeGatewayPids = @((Get-HealthProcessId -Health $runtime.trade_health)) + @(Get-ListenerPids -Port $tradePort)
        $dataGatewayPids = @((Get-HealthProcessId -Health $runtime.data_health)) + @(Get-ListenerPids -Port $dataPort)
        $runtime.host_recovery.trade_gateway_stop = Stop-ProcessIds -Ids $tradeGatewayPids
        $runtime.host_recovery.data_gateway_stop = Stop-ProcessIds -Ids $dataGatewayPids
        $runtime.host_recovery.trade_listener_gone = Wait-ListenerGone -Port $tradePort -TimeoutSeconds 10
        $runtime.host_recovery.data_listener_gone = Wait-ListenerGone -Port $dataPort -TimeoutSeconds 10

        $miniQmtPids = @(Get-Process -Name XtMiniQmt, miniquote -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id -ErrorAction SilentlyContinue)
        $runtime.host_recovery.miniqmt_stop = Stop-ProcessIds -Ids $miniQmtPids
        $runtime.host_recovery.miniqmt_gone = Wait-ProcessNamesGone -Names @("XtMiniQmt", "miniquote") -TimeoutSeconds 20

        if ($runtime.host_recovery.miniqmt_gone) {
            $cleanup = Invoke-PythonJsonCommand -PythonExe $python -ScriptPath $hostRecoveryScript -Arguments @(
                "cleanup",
                "--user-data-path", [string]$initialPreflight.native_probe_user_data.path,
                "--sessions", [string]$initialNativeProbe.requested_sessions_text
            ) -OutputPath $hostRecoveryPath
            $runtime.host_recovery.cleanup = $cleanup.parsed
            $runtime.host_recovery.cleanup_ok = ($cleanup.exit_code -eq 0)
        } else {
            $runtime.host_recovery.cleanup = [ordered]@{
                skipped = $true
                reason = "miniqmt_process_still_alive"
            }
            $runtime.host_recovery.cleanup_ok = $false
        }

        if ($qmtExeCandidate.found -and (Test-Path -LiteralPath $qmtExeCandidate.path)) {
            $qmtProc = Start-Process -FilePath $qmtExeCandidate.path -PassThru
            $runtime.host_recovery.miniqmt_restart = [ordered]@{
                started = $true
                pid = $qmtProc.Id
                qmt_exe = [string]$qmtExeCandidate.path
                source = [string]$qmtExeCandidate.source
            }
            Start-Sleep -Seconds 3
        } else {
            $runtime.host_recovery.miniqmt_restart = [ordered]@{
                started = $false
                reason = [string]$qmtExeCandidate.reason
                qmt_exe = [string]$qmtExeCandidate.path
            }
        }

        $runtime.host_recovery.trade_wake = Invoke-WakeScript -ShellExe $shellExe -ScriptPath (Join-Path $RepoRoot "scripts\wake_trade_gateway.ps1") -RepoRoot $RepoRoot -ConfigPath $tradeConfigPath -HealthUrl $tradeHealthUrl -WaitSeconds $RecoveryWaitSeconds -OutputPath $tradeWakePath
        $runtime.host_recovery.data_wake = Invoke-WakeScript -ShellExe $shellExe -ScriptPath (Join-Path $RepoRoot "scripts\wake_data_gateway.ps1") -RepoRoot $RepoRoot -ConfigPath $dataConfigPath -HealthUrl $dataHealthUrl -WaitSeconds $RecoveryWaitSeconds -OutputPath $dataWakePath
        $runtime.host_recovery.trade_wake_ok = ($runtime.host_recovery.trade_wake.exit_code -eq 0) -and $runtime.host_recovery.trade_wake.parsed.ok
        $runtime.host_recovery.data_wake_ok = ($runtime.host_recovery.data_wake.exit_code -eq 0) -and $runtime.host_recovery.data_wake.parsed.ok
        $runtime.trade_wake_status = [string]$runtime.host_recovery.trade_wake.parsed.status
        $runtime.data_wake_status = [string]$runtime.host_recovery.data_wake.parsed.status

        try {
            $runtime.trade_health = Invoke-RestMethod -Method Get -Uri $tradeHealthUrl -TimeoutSec 5
            $runtime.trade_health_ok = $true
        } catch {
            $runtime.trade_health = [ordered]@{ error = $_.Exception.Message }
            $runtime.trade_health_ok = $false
        }
        try {
            $runtime.data_health = Invoke-RestMethod -Method Get -Uri $dataHealthUrl -TimeoutSec 5
            $runtime.data_health_ok = $true
        } catch {
            $runtime.data_health = [ordered]@{ error = $_.Exception.Message }
            $runtime.data_health_ok = $false
        }

        if ($runtime.host_recovery.trade_wake_ok -and $runtime.host_recovery.data_wake_ok) {
            $recoveryPreflight = Invoke-TradePreflightBundle -TradeMcpUrl $tradeMcpUrl -TradeConfigPath $tradeConfigPath
            $recoveryFreshAuthority = Get-ProbeAuthorityState -ProbeCall $recoveryPreflight.probe_pre
            $runtime.host_recovery.recovery_preflight = [ordered]@{
                preflight_session_plan = $recoveryPreflight.preflight_session_plan
                native_probe_user_data = $recoveryPreflight.native_probe_user_data
                fresh_authority = $recoveryFreshAuthority
            }
            if ($recoveryFreshAuthority.ready) {
                $runtime.host_recovery.ok = $true
                $runtime.host_recovery.reason = "runtime_fresh_authority_ready_after_recovery"
                $finalPreflight = $recoveryPreflight
                $finalNativeProbe = New-SkippedNativeProbeBundle `
                    -OutputPath $nativeProbePath `
                    -RequestedSessions $recoveryPreflight.native_probe_requested_sessions `
                    -Reason "skipped_runtime_fresh_authority_ready_after_recovery" `
                    -UserDataPath ([string]$recoveryPreflight.native_probe_user_data.path) `
                    -UserDataSource ([string]$recoveryPreflight.native_probe_user_data.source)
            } else {
                $runtime.host_recovery.session_close_after_recovery = Invoke-McpTool -Url $tradeMcpUrl -Name "session.close" -Arguments @{}
                $runtime.host_recovery.session_status_after_close = Invoke-McpTool -Url $tradeMcpUrl -Name "session.status" -Arguments @{}
                $runtime.host_recovery.resource_session_after_close = Invoke-McpResource -Url $tradeMcpUrl -Uri "trade://session/current"
                $runtime.host_recovery.status_ready_after_close = Get-CallReadyFlag -Call $runtime.host_recovery.session_status_after_close
                Start-Sleep -Seconds $cooldownSeconds

                $finalNativeProbe = Invoke-NativeProbeBundle `
                    -PythonExe $python `
                    -ScriptPath $nativeProbeScript `
                    -OutputPath $nativeProbePath `
                    -NativeUserData $recoveryPreflight.native_probe_user_data `
                    -RequestedSessions $recoveryPreflight.native_probe_requested_sessions `
                    -AccountId ([string]$recoveryPreflight.native_probe_account_id)
                $runtime.host_recovery.native_probe_after_recovery = $finalNativeProbe.parsed
                $runtime.host_recovery.ok = $finalNativeProbe.ok
                $runtime.host_recovery.reason = if ($finalNativeProbe.ok) { "ok" } else { "native_probe_failed_after_recovery" }
                $finalPreflight = $recoveryPreflight
            }
        } else {
            $runtime.host_recovery.reason = "gateway_recovery_failed_after_cleanup"
        }
    }
}

if ($finalNativeProbe.ok) {
    $finalPreflight = Invoke-TradePreflightBundle -TradeMcpUrl $tradeMcpUrl -TradeConfigPath $tradeConfigPath
}

$runtime.init = $finalPreflight.init
$runtime.login = $finalPreflight.login
$runtime.session_warm = $finalPreflight.session_warm
$runtime.session_status_pre = $finalPreflight.session_status_pre
$runtime.probe_pre = $finalPreflight.probe_pre
$runtime.orders_pre = $finalPreflight.orders_pre
$runtime.resource_session_pre = $finalPreflight.resource_session_pre
$runtime.resource_probe_pre = $finalPreflight.resource_probe_pre
$runtime.resource_login_pre = $finalPreflight.resource_login_pre
$runtime.native_probe_user_data = $finalPreflight.native_probe_user_data
$nativeUserDataPath = [string]$runtime.native_probe_user_data.path
$runtime.session_resolution = $finalPreflight.session_resolution
$runtime.preflight_runtime_authority = Get-ProbeAuthorityState -ProbeCall $finalPreflight.probe_pre
$runtime.preflight_session_plan = $finalPreflight.preflight_session_plan
$runtime.native_probe_requested_sessions = @($finalNativeProbe.requested_sessions)
$runtime.native_probe_requested_sessions_text = [string]$finalNativeProbe.requested_sessions_text
$runtime.native_probe_session_source = [string]$finalPreflight.native_probe_session_source
$runtime.native_probe_account_id = [string]$finalPreflight.native_probe_account_id
$runtime.native_probe = $finalNativeProbe.parsed
$runtime.native_probe_output_path = $finalNativeProbe.output_path
$runtime.native_probe_ok = $finalNativeProbe.ok
$runtime.native_probe_observed_sessions = @($finalNativeProbe.observed_sessions)
$runtime.native_probe_same_plan = Compare-SessionPlanToExpected -ExpectedPlan $runtime.preflight_session_plan.canonical_plan -Entries @(
    [ordered]@{ name = "native_probe"; plan = $runtime.native_probe_observed_sessions }
)
$runtime.host_recovery | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $hostRecoveryPath -Encoding UTF8

$preflightTransportOk = $true
foreach ($call in @($runtime.init, $runtime.login, $runtime.session_warm, $runtime.session_status_pre, $runtime.probe_pre, $runtime.orders_pre, $runtime.resource_session_pre, $runtime.resource_probe_pre, $runtime.resource_login_pre)) {
    if (-not $call.transport_ok) {
        $preflightTransportOk = $false
        break
    }
}
$packetReadiness = & (Join-Path $RepoRoot "scripts\check_packet_readiness.ps1") `
    -MarketWindowOpen:([bool]$runtime.market_window.open) `
    -TradeHealthOk:([bool]$runtime.trade_health_ok) `
    -DataHealthOk:([bool]$runtime.data_health_ok) `
    -CleanWindowOk:([bool]$runtime.clean_window.ok) `
    -PreflightSessionPlanOk:([bool]$runtime.preflight_session_plan.ok) `
    -NativeProbeOk:([bool]$runtime.native_probe_ok) `
    -NativeProbeSamePlanOk:([bool]$runtime.native_probe_same_plan.ok) `
    -HostRecoveryAttempted:([bool]$runtime.host_recovery.attempted) `
    -HostRecoveryOk:([bool]$runtime.host_recovery.ok) `
    -PreflightTransportOk:([bool]$preflightTransportOk) `
    -RuntimeSamePlanOk:([bool]$runtime.preflight_runtime_authority.same_plan_verdict) `
    -RuntimeProbeCompleteOk:([bool]$runtime.preflight_runtime_authority.probe_complete_verdict) `
    -FreshConnectVerified:([bool]$runtime.preflight_runtime_authority.fresh_connect_verified) `
    -WriteAuthorityReady:([bool]$runtime.preflight_runtime_authority.write_authority_ready) `
    -SessionPlanVersion:([string]$runtime.session_resolution.session_plan_version) `
    -OutputPath $packetReadinessPath
$runtime.packet_readiness = $packetReadiness
$runtime.packet_readiness_output_path = $packetReadinessPath

$canPlaceOrder = [bool]$runtime.packet_readiness.go

$runtime.order_place = [ordered]@{
    executed = $false
    call = $null
}
$runtime.session_status_post = [ordered]@{ transport_ok = $false }
$runtime.probe_post = [ordered]@{ transport_ok = $false }
$runtime.orders_after = [ordered]@{ transport_ok = $false }
$runtime.order_status = [ordered]@{ transport_ok = $false }
$runtime.order_cancel = [ordered]@{ skipped = $true; transport_ok = $false }
$runtime.fills_list = [ordered]@{ transport_ok = $false }
$runtime.resource_session_post = [ordered]@{ transport_ok = $false }
$runtime.resource_probe_post = [ordered]@{ transport_ok = $false }
$runtime.resource_login_post = [ordered]@{ transport_ok = $false }
$runtime.order_place_session_plan_text = "N/A"
$runtime.resource_session_post_plan_text = "N/A"
$runtime.postwrite_session_plan = [ordered]@{
    ok = $false
    reason = "order_place_not_executed"
    expected_plan = @($runtime.preflight_session_plan.canonical_plan)
    expected_plan_text = [string]$runtime.preflight_session_plan.canonical_plan_text
    details = @()
}

if ($canPlaceOrder) {
    $orderPlaceCall = Invoke-McpTool -Url $tradeMcpUrl -Name "order.place" -Arguments @{
        code = [string]$contract.packet.symbol
        side = [string]$contract.packet.side
        qty = [int]$contract.packet.qty
        price_mode = [string]$contract.packet.price_mode
    }
    $runtime.order_place.executed = $true
    $runtime.order_place.call = $orderPlaceCall
    $runtime.order_place_session_plan_text = Get-SessionPlanText -Plan (Get-CallSessionPlan -Call $orderPlaceCall)

    $runtime.session_status_post = Invoke-McpTool -Url $tradeMcpUrl -Name "session.status" -Arguments @{}
    $runtime.probe_post = Invoke-McpTool -Url $tradeMcpUrl -Name "probe.connection" -Arguments @{}
    $runtime.orders_after = Invoke-McpTool -Url $tradeMcpUrl -Name "orders.list" -Arguments @{}

    $brokerOrderId = Get-CallBrokerOrderId -Call $orderPlaceCall
    if ($brokerOrderId) {
        $runtime.order_status = Invoke-McpTool -Url $tradeMcpUrl -Name "order.status" -Arguments @{ broker_order_id = $brokerOrderId }
        $runtime.orders_after = Invoke-McpTool -Url $tradeMcpUrl -Name "orders.list" -Arguments @{}
        $orderStatusValue = ""
        if ($runtime.order_status.transport_ok -and $null -ne $runtime.order_status.structured -and $null -ne $runtime.order_status.structured.data -and $runtime.order_status.structured.data.status) {
            $orderStatusValue = [string]$runtime.order_status.structured.data.status
        }
        if ($orderStatusValue -notin @("filled", "cancelled", "rejected", "canceled")) {
            $runtime.order_cancel = Invoke-McpTool -Url $tradeMcpUrl -Name "order.cancel" -Arguments @{ broker_order_id = $brokerOrderId }
            $runtime.order_cancel.skipped = $false
        }
        $runtime.fills_list = Invoke-McpTool -Url $tradeMcpUrl -Name "fills.list" -Arguments @{ broker_order_id = $brokerOrderId }
    }
}

$runtime.resource_session_post = Invoke-McpResource -Url $tradeMcpUrl -Uri "trade://session/current"
$runtime.resource_probe_post = Invoke-McpResource -Url $tradeMcpUrl -Uri "diag://probe/latest"
$runtime.resource_login_post = Invoke-McpResource -Url $tradeMcpUrl -Uri "diag://login/latest"
$runtime.resource_session = $runtime.resource_session_post
$runtime.resource_probe = $runtime.resource_probe_post
$runtime.resource_login = $runtime.resource_login_post
$runtime.resource_session_post_plan_text = Get-SessionPlanText -Plan (Get-ResourceSessionPlan -ResourceCall $runtime.resource_session_post)
if ($runtime.order_place.executed) {
    $runtime.session_resolution.order_place = Get-CallSessionResolution -Call $runtime.order_place.call
    $runtime.session_resolution.session_status_post = Get-CallSessionResolution -Call $runtime.session_status_post
    $runtime.session_resolution.probe_post = Get-CallSessionResolution -Call $runtime.probe_post
    $runtime.session_resolution.resource_session_post = Get-ResourceSessionResolution -ResourceCall $runtime.resource_session_post
    $runtime.postwrite_session_plan = Compare-SessionPlanToExpected -ExpectedPlan $runtime.preflight_session_plan.canonical_plan -Entries @(
        [ordered]@{ name = "order.place"; plan = (Get-CallSessionPlan -Call $runtime.order_place.call) },
        [ordered]@{ name = "session.status.post"; plan = (Get-CallSessionPlan -Call $runtime.session_status_post) },
        [ordered]@{ name = "probe.connection.post"; plan = (Get-CallSessionPlan -Call $runtime.probe_post) },
        [ordered]@{ name = "trade://session/current.post"; plan = (Get-ResourceSessionPlan -ResourceCall $runtime.resource_session_post) }
    )
} else {
    $runtime.session_resolution.resource_session_post = Get-ResourceSessionResolution -ResourceCall $runtime.resource_session_post
}
$runtime.wall_clock_end = (Get-Date).ToString("o")

$runtime | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $runtimePath -Encoding UTF8
$conclusion = Get-Conclusion -Runtime $runtime

$summary = if ($runtime.order_place.executed) {
    "controller direct test executed the live chain and produced formal test artifacts"
} else {
    "controller direct test stopped in preflight and produced formal blocked evidence: $($runtime.packet_readiness.no_go_reason)"
}
$nextStep = "independent review is still required before any closeout or reopen"
Write-ControllerJudgment -Path $judgmentPath -Contract $contract -Timestamp $timestamp -Mode "controller-only" -ArtifactSnapshot $artifactSnapshot.parsed -ArtifactSnapshotPath $artifactSnapshot.output_path -TradeWake $tradeWake -DataWake $dataWake -RuntimePath $runtimePath -ExecutedTest $true -Summary $summary -NextStep $nextStep
Write-EnvSnapshot -Path $envSnapshotPath -Contract $contract -Timestamp $timestamp -ArtifactSnapshotPath $artifactSnapshot.output_path -JudgmentPath $judgmentPath -RuntimePath $runtimePath -TradeWakePath $tradeWake.output_path -DataWakePath $dataWake.output_path -NativeProbePath $runtime.native_probe_output_path -HostRecoveryPath $hostRecoveryPath -PacketReadinessPath $packetReadinessPath -Runtime $runtime -Conclusion $conclusion
Write-EvidencePack -Path $evidencePath -Contract $contract -Timestamp $timestamp -ArtifactSnapshotPath $artifactSnapshot.output_path -JudgmentPath $judgmentPath -EnvSnapshotPath $envSnapshotPath -RuntimePath $runtimePath -TradeWakePath $tradeWake.output_path -DataWakePath $dataWake.output_path -NativeProbePath $runtime.native_probe_output_path -HostRecoveryPath $hostRecoveryPath -PacketReadinessPath $packetReadinessPath -Runtime $runtime -Conclusion $conclusion
Write-TradeWriteAuthoritySource -Path $authoritySourcePath -LatestPath $authoritySourceLatestPath -PacketId $slug -Contract $contract -Timestamp $timestamp -ArtifactSnapshot $artifactSnapshot.parsed -ArtifactSnapshotPath $artifactSnapshot.output_path -JudgmentPath $judgmentPath -EvidencePath $evidencePath -EnvSnapshotPath $envSnapshotPath -RuntimePath $runtimePath -PacketReadinessPath $packetReadinessPath -DiagProbePath $diagProbeLatestPath -Runtime $runtime

[ordered]@{
    ok = $true
    status = "controller_direct_test_complete"
    task_id = $TaskId
    conclusion = $conclusion.conclusion
    formal_truth_snapshot = $artifactSnapshot.output_path
    controller_judgment = $judgmentPath
    evidence_pack = $evidencePath
    env_snapshot = $envSnapshotPath
    native_probe = $runtime.native_probe_output_path
    host_recovery = $hostRecoveryPath
    packet_readiness = $packetReadinessPath
    runtime_capture = $runtimePath
    trade_write_authority_source = $authoritySourcePath
    trade_write_authority_source_latest = $authoritySourceLatestPath
} | ConvertTo-Json -Depth 8
exit 0
