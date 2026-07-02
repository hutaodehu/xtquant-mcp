param(
    [bool]$MarketWindowOpen,
    [bool]$TradeHealthOk,
    [bool]$DataHealthOk,
    [bool]$CleanWindowOk,
    [bool]$PreflightSessionPlanOk,
    [bool]$NativeProbeOk,
    [bool]$NativeProbeSamePlanOk,
    [bool]$HostRecoveryAttempted = $false,
    [bool]$HostRecoveryOk = $true,
    [bool]$PreflightTransportOk = $true,
    [bool]$RuntimeSamePlanOk = $false,
    [bool]$RuntimeProbeCompleteOk = $false,
    [bool]$FreshConnectVerified = $false,
    [bool]$WriteAuthorityReady = $false,
    [string]$SessionPlanVersion = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

$checks = [ordered]@{
    market_window_open = [bool]$MarketWindowOpen
    trade_gateway_ready = [bool]$TradeHealthOk
    data_gateway_ready = [bool]$DataHealthOk
    clean_window_ready = [bool]$CleanWindowOk
    preflight_session_plan_ready = [bool]$PreflightSessionPlanOk
    runtime_same_plan_ready = [bool]$RuntimeSamePlanOk
    runtime_probe_complete_ready = [bool]$RuntimeProbeCompleteOk
    runtime_fresh_connect_ready = [bool]$FreshConnectVerified
    runtime_write_authority_ready = [bool]$WriteAuthorityReady
    preflight_transport_ready = [bool]$PreflightTransportOk
    legacy_native_probe_ready = [bool]$NativeProbeOk
    legacy_native_probe_same_plan_ready = [bool]$NativeProbeSamePlanOk
    legacy_host_recovery_ready = ((-not [bool]$HostRecoveryAttempted) -or [bool]$HostRecoveryOk)
}

$noGoReason = ""
if (-not $checks.market_window_open) {
    $noGoReason = "market_window_closed"
} elseif (-not $checks.trade_gateway_ready) {
    $noGoReason = "trade_gateway_not_ready"
} elseif (-not $checks.data_gateway_ready) {
    $noGoReason = "data_gateway_not_ready"
} elseif (-not $checks.clean_window_ready) {
    $noGoReason = "clean_window_not_ready"
} elseif (-not $checks.preflight_session_plan_ready) {
    $noGoReason = "preflight_session_plan_not_ready"
} elseif (-not $checks.runtime_same_plan_ready) {
    $noGoReason = "runtime_same_plan_not_ready"
} elseif (-not $checks.runtime_probe_complete_ready) {
    $noGoReason = "runtime_probe_not_complete"
} elseif (-not $checks.runtime_fresh_connect_ready) {
    $noGoReason = "runtime_fresh_connect_not_verified"
} elseif (-not $checks.runtime_write_authority_ready) {
    $noGoReason = "runtime_write_authority_not_ready"
} elseif (-not $checks.preflight_transport_ready) {
    $noGoReason = "preflight_transport_not_ready"
}

$payload = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    report_type = "controller_packet_readiness"
    status = if ($noGoReason) { "no_go" } else { "go" }
    go = (-not [bool]$noGoReason)
    no_go_reason = [string]$noGoReason
    session_plan_version = [string]$SessionPlanVersion
    gate_checks = $checks
}

if ($OutputPath) {
    $dir = Split-Path -Parent $OutputPath
    if ($dir) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
}

$payload
