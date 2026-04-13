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
    if ($null -ne $ResourceCall.payload.payload -and $null -ne $ResourceCall.payload.payload.session_resolution) {
        return $ResourceCall.payload.payload.session_resolution
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

    if (-not $Runtime.native_probe_user_data.ok) {
        return [ordered]@{
            conclusion = "fail_env"
            failure_layer = "environment"
            acceptance_position = "Round 2 native probe path unavailable"
            summary = "native broker/session probe could not resolve a usable qmt_userdata path from trade config or login evidence"
        }
    }

    if (-not $Runtime.native_probe_same_plan.ok) {
        return [ordered]@{
            conclusion = "fail_design"
            failure_layer = "design"
            acceptance_position = "Round 2 same-plan probe failed"
            summary = "native probe did not run against the canonical effective session plan returned by gateway preflight"
        }
    }

    if (-not $Runtime.native_probe_ok) {
        return [ordered]@{
            conclusion = "fail_env"
            failure_layer = "environment"
            acceptance_position = "Round 2 broker/session probe failed"
            summary = "native broker/session probe did not complete the required bounded query chain on all configured sessions"
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
- native probe overall_ok: $($Runtime.native_probe_ok)
- native probe user_data_path: $($Runtime.native_probe_user_data.path)
- native probe user_data source: $($Runtime.native_probe_user_data.source)
- native probe user_data exists: $($Runtime.native_probe_user_data.path_exists)
- native probe sessions: $nativeProbeSummary
- native probe requested sessions: $($Runtime.native_probe_requested_sessions_text)
- native probe session source: $($Runtime.native_probe_session_source)
- preflight effective session plan: $($Runtime.preflight_session_plan.canonical_plan_text)
- preflight same-plan verdict: $($Runtime.preflight_session_plan.ok)
- native probe same-plan verdict: $($Runtime.native_probe_same_plan.ok)
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
- native probe overall_ok: $($Runtime.native_probe_ok)
- native probe user_data_path: $($Runtime.native_probe_user_data.path)
- native probe user_data source: $($Runtime.native_probe_user_data.source)
- native probe user_data exists: $($Runtime.native_probe_user_data.path_exists)
- native probe sessions: $nativeProbeSummary
- native probe requested sessions: $($Runtime.native_probe_requested_sessions_text)
- native probe session source: $($Runtime.native_probe_session_source)
- preflight effective session plan: $($Runtime.preflight_session_plan.canonical_plan_text)
- preflight same-plan verdict: $($Runtime.preflight_session_plan.ok)
- native probe same-plan verdict: $($Runtime.native_probe_same_plan.ok)
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

$python = Resolve-PythonExe -RequestedPythonExe $PythonExe
$shellExe = Resolve-ShellExe
$tmpDir = Join-Path $RepoRoot ".tmp\spec-task-harness"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
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
$runtimePath = Join-Path $tmpDir ("{0}-controller-direct-runtime-{1}.json" -f $TaskId.ToLower(), $slug)
$judgmentPath = Join-Path $tmpDir ("{0}-controller-judgment-{1}-controller-direct-test.md" -f $TaskId, $slug)
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
$runtime.init = Invoke-McpInitialize -Url $tradeMcpUrl
$runtime.login = Invoke-McpTool -Url $tradeMcpUrl -Name "miniqmt.ensure_logged_in" -Arguments @{ login_timeout_seconds = 20 }
$runtime.session_warm = Invoke-McpTool -Url $tradeMcpUrl -Name "session.warm" -Arguments @{}
$runtime.session_status_pre = Invoke-McpTool -Url $tradeMcpUrl -Name "session.status" -Arguments @{}
$runtime.probe_pre = Invoke-McpTool -Url $tradeMcpUrl -Name "probe.connection" -Arguments @{}
$runtime.orders_pre = Invoke-McpTool -Url $tradeMcpUrl -Name "orders.list" -Arguments @{}
$runtime.resource_session_pre = Invoke-McpResource -Url $tradeMcpUrl -Uri "trade://session/current"
$runtime.resource_probe_pre = Invoke-McpResource -Url $tradeMcpUrl -Uri "diag://probe/latest"
$runtime.resource_login_pre = Invoke-McpResource -Url $tradeMcpUrl -Uri "diag://login/latest"
$runtime.native_probe_user_data = Resolve-NativeUserDataPath -TradeConfigPath $tradeConfigPath -LoginCall $runtime.login -LoginResource $runtime.resource_login_pre
$nativeUserDataPath = [string]$runtime.native_probe_user_data.path
$runtime.session_resolution = [ordered]@{
    session_warm = Get-CallSessionResolution -Call $runtime.session_warm
    session_status_pre = Get-CallSessionResolution -Call $runtime.session_status_pre
    probe_pre = Get-CallSessionResolution -Call $runtime.probe_pre
    orders_pre = Get-CallSessionResolution -Call $runtime.orders_pre
    resource_session_pre = Get-ResourceSessionResolution -ResourceCall $runtime.resource_session_pre
}
$runtime.preflight_session_plan = Test-SessionPlanAgreement -Entries @(
    [ordered]@{ name = "session.warm"; plan = (Get-CallSessionPlan -Call $runtime.session_warm) },
    [ordered]@{ name = "session.status"; plan = (Get-CallSessionPlan -Call $runtime.session_status_pre) },
    [ordered]@{ name = "probe.connection"; plan = (Get-CallSessionPlan -Call $runtime.probe_pre) },
    [ordered]@{ name = "trade://session/current"; plan = (Get-ResourceSessionPlan -ResourceCall $runtime.resource_session_pre) }
)
$runtime.native_probe_requested_sessions = @($runtime.preflight_session_plan.canonical_plan)
$runtime.native_probe_requested_sessions_text = Get-SessionPlanText -Plan $runtime.native_probe_requested_sessions
$runtime.native_probe_session_source = [string]$runtime.preflight_session_plan.canonical_source
$runtime.native_probe_account_id = Get-FirstNonEmptyValue -Values @(
    (Get-CallAccountId -Call $runtime.session_status_pre),
    (Get-CallAccountId -Call $runtime.session_warm),
    (Get-CallAccountId -Call $runtime.probe_pre)
)
$nativeProbeScript = Join-Path $RepoRoot ".agents\skills\spec-task-harness\scripts\run_native_broker_session_probe.py"
if ($runtime.native_probe_requested_sessions.Count -gt 0) {
    if (-not $runtime.native_probe_user_data.ok) {
        $runtime.native_probe = [ordered]@{
            overall_ok = $false
            error = "native user-data-path unavailable: $($runtime.native_probe_user_data.reason)"
            requested_sessions = @($runtime.native_probe_requested_sessions)
            user_data_path = $nativeUserDataPath
            user_data_source = [string]$runtime.native_probe_user_data.source
            results = @()
        }
        $runtime.native_probe_output_path = $nativeProbePath
        $runtime.native_probe_ok = $false
        $runtime.native_probe | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $nativeProbePath -Encoding UTF8
    } else {
        $nativeProbeSessions = $runtime.native_probe_requested_sessions_text
        $nativeProbeArgs = @("--user-data-path", $nativeUserDataPath, "--sessions", $nativeProbeSessions)
        if ($runtime.native_probe_account_id) {
            $nativeProbeArgs += @("--account-id", $runtime.native_probe_account_id)
        }
        $nativeProbe = Invoke-PythonJsonCommand -PythonExe $python -ScriptPath $nativeProbeScript -Arguments $nativeProbeArgs -OutputPath $nativeProbePath
        $runtime.native_probe = $nativeProbe.parsed
        $runtime.native_probe_output_path = $nativeProbe.output_path
        $runtime.native_probe_ok = ($nativeProbe.exit_code -eq 0) -and $runtime.native_probe.overall_ok
    }
} else {
    $runtime.native_probe = [ordered]@{
        overall_ok = $false
        error = "preflight effective session plan is unavailable"
        requested_sessions = @()
        results = @()
    }
    $runtime.native_probe_output_path = $nativeProbePath
    $runtime.native_probe_ok = $false
    $runtime.native_probe | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $nativeProbePath -Encoding UTF8
}
$runtime.native_probe_observed_sessions = if ($null -ne $runtime.native_probe -and $null -ne $runtime.native_probe.results) {
    ConvertTo-SessionIdArray -Value @($runtime.native_probe.results | ForEach-Object { $_.session_id })
} else {
    @()
}
$runtime.native_probe_same_plan = Compare-SessionPlanToExpected -ExpectedPlan $runtime.native_probe_requested_sessions -Entries @(
    [ordered]@{ name = "native_probe"; plan = $runtime.native_probe_observed_sessions }
)

$canPlaceOrder = $runtime.market_window.open -and $runtime.trade_health_ok -and $runtime.data_health_ok -and $runtime.native_probe_ok -and $runtime.preflight_session_plan.ok -and $runtime.native_probe_same_plan.ok
foreach ($call in @($runtime.init, $runtime.login, $runtime.session_warm, $runtime.session_status_pre, $runtime.probe_pre, $runtime.orders_pre, $runtime.resource_session_pre, $runtime.resource_probe_pre, $runtime.resource_login_pre)) {
    if (-not $call.transport_ok) {
        $canPlaceOrder = $false
    }
}

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
    "controller direct test stopped in preflight and produced formal blocked evidence"
}
$nextStep = "independent review is still required before any closeout or reopen"
Write-ControllerJudgment -Path $judgmentPath -Contract $contract -Timestamp $timestamp -Mode "controller-only" -ArtifactSnapshot $artifactSnapshot.parsed -ArtifactSnapshotPath $artifactSnapshot.output_path -TradeWake $tradeWake -DataWake $dataWake -RuntimePath $runtimePath -ExecutedTest $true -Summary $summary -NextStep $nextStep
Write-EnvSnapshot -Path $envSnapshotPath -Contract $contract -Timestamp $timestamp -ArtifactSnapshotPath $artifactSnapshot.output_path -JudgmentPath $judgmentPath -RuntimePath $runtimePath -TradeWakePath $tradeWake.output_path -DataWakePath $dataWake.output_path -NativeProbePath $nativeProbe.output_path -Runtime $runtime -Conclusion $conclusion
Write-EvidencePack -Path $evidencePath -Contract $contract -Timestamp $timestamp -ArtifactSnapshotPath $artifactSnapshot.output_path -JudgmentPath $judgmentPath -EnvSnapshotPath $envSnapshotPath -RuntimePath $runtimePath -TradeWakePath $tradeWake.output_path -DataWakePath $dataWake.output_path -NativeProbePath $nativeProbe.output_path -Runtime $runtime -Conclusion $conclusion

[ordered]@{
    ok = $true
    status = "controller_direct_test_complete"
    task_id = $TaskId
    conclusion = $conclusion.conclusion
    formal_truth_snapshot = $artifactSnapshot.output_path
    controller_judgment = $judgmentPath
    evidence_pack = $evidencePath
    env_snapshot = $envSnapshotPath
    native_probe = $nativeProbe.output_path
    runtime_capture = $runtimePath
} | ConvertTo-Json -Depth 8
exit 0
