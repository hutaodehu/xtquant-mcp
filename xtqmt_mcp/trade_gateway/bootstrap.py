from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from xtqmt_mcp.runtime_support import ensure_miniqmt_awake as _ensure_miniqmt_awake
from xtqmt_mcp.runtime_support import resolve_account_for_ops as _resolve_account_for_ops
from xtqmt_mcp.risk import parse_white_list
from xtqmt_mcp.session_resolution import SessionResolution, build_effective_session_plan, prioritize_session_candidates, session_resolution_payload

from .config import TradeOpsGatewayConfig


@dataclass
class TradeOpsRuntimeContext:
    service: Any
    wake_report: dict[str, Any]
    resolved_account_id: str
    resolved_session_id: int
    session_resolution: SessionResolution | None = None

    def close(self) -> None:
        close_fn = getattr(self.service, "close", None)
        if callable(close_fn):
            close_fn()


@dataclass(frozen=True)
class TradeOpsNeeds:
    need_shadow: bool
    need_broker: bool
    need_account: bool


def _wake_report_requires_hard_block(wake_report: dict[str, Any]) -> bool:
    if bool(wake_report.get("xtdata_port_ready_after", False)):
        return False
    if bool(wake_report.get("ok", False)):
        return False
    process_visible = bool(
        wake_report.get("process_exists_before", False)
        or wake_report.get("process_started", False)
        or wake_report.get("process_id")
    )
    if process_visible:
        return False
    return True

def _tool_requires_write_permission_gate(tool_name: str) -> bool:
    return tool_name in {"order.place", "order.cancel"}


def _resolve_explicit_account_session(
    config: TradeOpsGatewayConfig,
    *,
    account_id: str,
    fallback_session_id: int,
) -> int:
    resolved_account_id = str(account_id or "").strip()
    if not resolved_account_id:
        return int(fallback_session_id)
    session_plans: list[tuple[int, ...]] = [tuple(config.session_candidates or (100, 101, 111))]
    legacy_candidates = tuple(candidate for candidate in (100, 101, 111) if candidate not in session_plans[0])
    if legacy_candidates:
        session_plans.append(tuple(session_plans[0] + legacy_candidates))
    try:
        from xtqmt_mcp.connection_orchestrator import ConnectionOrchestratorConfig, run_connection_orchestrator

        for session_plan in session_plans:
            trace = run_connection_orchestrator(
                ConnectionOrchestratorConfig(
                    qmt_exe=str(config.qmt_exe or ""),
                    qmt_userdata=str(config.qmt_userdata or ""),
                    account_id=resolved_account_id,
                    session_plan=tuple(session_plan),
                    connect_retries=max(1, int(config.connect_retries)),
                    connect_retry_interval_seconds=max(3.0, float(config.connect_retry_interval_seconds)),
                    wake_wait_seconds=max(1, int(config.wake_wait_seconds)),
                    require_connect_stage=bool(config.require_connect_stage),
                    require_subscribe_stage=bool(config.require_subscribe_stage),
                    require_snapshot_stage=bool(config.require_snapshot_stage),
                    snapshot_requires_position=bool(config.snapshot_requires_position),
                )
            )
            selected_session_id = int(getattr(trace, "selected_session_id", 0) or 0)
            if bool(getattr(trace, "overall_ok", False)) and selected_session_id > 0:
                return selected_session_id
    except Exception:
        return int(fallback_session_id)

    return int(fallback_session_id)


def trade_ops_needs_for_tool(tool_name: str) -> TradeOpsNeeds:
    need_shadow = tool_name in {
        "account.show",
        "positions.list",
        "orders.list",
        "fills.list",
        "probe.connection",
        "order.place",
        "session.warm",
    }
    need_broker = tool_name in {"orders.list", "order.status", "order.cancel", "order.place"}
    return TradeOpsNeeds(
        need_shadow=bool(need_shadow),
        need_broker=bool(need_broker),
        need_account=bool(need_shadow or need_broker),
    )


def build_trade_ops_context(
    config: TradeOpsGatewayConfig,
    tool_name: str,
    *,
    ensure_miniqmt_awake_fn: Callable[..., dict[str, Any]] = _ensure_miniqmt_awake,
    discover_stock_account_ids_fn: Callable[..., list[str]] | None = None,
    market_data_factory: Callable[..., Any] | None = None,
    shadow_adapter_factory: Callable[..., Any] | None = None,
    broker_order_adapter_factory: Callable[..., Any] | None = None,
) -> TradeOpsRuntimeContext:
    try:
        from xtqmt_mcp.adapters.xttrader_shadow import XtTraderShadowAdapter, XtTraderShadowConfig, discover_stock_account_ids
        from xtqmt_mcp.broker_order import DryRunBrokerOrderAdapter, XtTraderBrokerOrderAdapter, XtTraderBrokerOrderConfig
        from xtqmt_mcp.market_data import XtQuantMarketDataProvider
        from xtqmt_mcp.policy import DataPolicy
        from xtqmt_mcp.trade_ops import TradeOpsConfig, TradeOpsService
    except ModuleNotFoundError as exc:
        missing = str(getattr(exc, "name", "") or "dependency")
        raise ModuleNotFoundError(f"xtquant_import_failed:{missing}") from exc

    needs = trade_ops_needs_for_tool(tool_name)
    require_write_permission_gate = _tool_requires_write_permission_gate(tool_name)
    execution_mode = str(getattr(config, "execution_mode", "live") or "live").strip().lower()
    flow_smoke_mode = execution_mode == "flow_smoke"
    wake_report = {"status": "skipped", "ok": True, "xtdata_port_ready_after": True}
    if (not flow_smoke_mode) and (str(config.qmt_exe or "").strip() or str(config.qmt_userdata or "").strip()):
        wake_report = ensure_miniqmt_awake_fn(
            qmt_exe=str(config.qmt_exe or ""),
            qmt_userdata=str(config.qmt_userdata or ""),
            account_id=str(config.account_id or ""),
            wait_seconds=max(1, int(config.wake_wait_seconds)),
            port=int(getattr(config, "xtdata_port", 0) or 0),
        )
        if _wake_report_requires_hard_block(wake_report):
            raise RuntimeError(
                "MiniQMT wake failed: "
                f"port_ready_before={wake_report.get('xtdata_port_ready_before')} "
                f"process_started={wake_report.get('process_started')} "
                f"error={wake_report.get('error') or wake_report.get('start_error')}"
            )

    resolved_account_id = str(config.account_id or "").strip()
    configured_session_id = int(config.session_id)
    configured_session_candidates = prioritize_session_candidates(
        configured_session_id,
        tuple(config.session_candidates or (100, 101, 111)),
    )
    resolved_base_session_id = int(configured_session_id)
    resolved_session_id = int(configured_session_id)
    explicit_session_resolution_applied = False
    if needs.need_account:
        if flow_smoke_mode:
            resolved_account_id = str(resolved_account_id or "FLOW_SMOKE").strip()
        else:
            qmt_userdata = str(config.qmt_userdata or "").strip()
            if not qmt_userdata:
                raise RuntimeError(f"{tool_name} requires server-side qmt_userdata")
            resolved = _resolve_account_for_ops(
                qmt_userdata=qmt_userdata,
                account_id=resolved_account_id,
                auto_account=bool(config.auto_account),
                session_id=int(configured_session_id),
                session_candidates=tuple(configured_session_candidates),
                discover_stock_account_ids=(discover_stock_account_ids_fn or discover_stock_account_ids),
                register_callback=bool(config.register_callback),
                connect_cooldown_seconds=float(config.connect_cooldown_seconds),
                enforce_connect_precheck=bool(config.enforce_connect_precheck),
                require_up_queue_file=bool(config.require_up_queue_file and require_write_permission_gate),
            )
            resolved_account_id, resolved_session_id = resolved.account_id, resolved.session_id
            resolved_base_session_id = int(resolved_session_id)
            if resolved_account_id:
                resolved_session_id = _resolve_explicit_account_session(
                    config,
                    account_id=resolved_account_id,
                    fallback_session_id=resolved_session_id,
                )
                explicit_session_resolution_applied = True
                if int(resolved_session_id) not in configured_session_candidates:
                    configured_session_candidates = (int(resolved_session_id),)
            if not resolved_account_id:
                raise RuntimeError(f"{tool_name} requires server-side account_id or auto_account")
    effective_session_plan = build_effective_session_plan(
        resolved_session_id,
        tuple(configured_session_candidates),
        bool(config.enable_derived_session_fallback),
        max_session_attempts=max(1, int(config.max_session_attempts)),
    )
    session_resolution = SessionResolution(
        configured_session_id=int(configured_session_id),
        resolved_base_session_id=int(resolved_base_session_id),
        resolved_session_id=int(resolved_session_id),
        configured_session_candidates=tuple(configured_session_candidates),
        effective_session_plan=tuple(effective_session_plan),
        derived_session_fallback_enabled=bool(config.enable_derived_session_fallback),
        max_session_attempts=max(1, int(config.max_session_attempts)),
        explicit_session_resolution_applied=bool(explicit_session_resolution_applied),
    )

    market_factory = market_data_factory or XtQuantMarketDataProvider
    policy = DataPolicy(enforce_today_online=not bool(config.allow_non_online_t0))
    market_data = market_factory(policy=policy, idle_timeout_seconds=float(config.idle_timeout_seconds))

    shadow_adapter = None
    if needs.need_shadow and (not flow_smoke_mode):
        shadow_factory = shadow_adapter_factory or XtTraderShadowAdapter
        shadow_cfg = XtTraderShadowConfig(
            user_data_path=str(config.qmt_userdata or ""),
            account_id=resolved_account_id,
            session_id=int(resolved_session_id),
            connect_retries=max(1, int(config.connect_retries)),
            connect_retry_interval_seconds=max(3.0, float(config.connect_retry_interval_seconds)),
            session_candidates=tuple(configured_session_candidates),
            enable_derived_session_fallback=bool(config.enable_derived_session_fallback),
            register_callback=bool(config.register_callback),
            connect_cooldown_seconds=max(0.0, float(config.connect_cooldown_seconds)),
            enforce_connect_precheck=bool(config.enforce_connect_precheck),
            require_up_queue_file=False,
            max_session_attempts=max(1, int(config.max_session_attempts)),
        )
        shadow_adapter = shadow_factory(shadow_cfg)

    broker_adapter = None
    broker_adapter_factory_for_service: Callable[[bool], Any] | None = None
    service_holder: dict[str, Any] = {}
    if needs.need_account:
        if flow_smoke_mode:
            broker_adapter = DryRunBrokerOrderAdapter()
            broker_adapter_factory_for_service = None
        else:
            broker_factory = broker_order_adapter_factory or XtTraderBrokerOrderAdapter
            def _build_broker_adapter(require_write_permission: bool) -> Any:
                current_session_id = int(resolved_session_id)
                current_session_candidates = tuple(configured_session_candidates)
                current_enable_derived_fallback = bool(config.enable_derived_session_fallback)
                current_max_session_attempts = max(1, int(config.max_session_attempts))
                service_ref = service_holder.get("service")
                if service_ref is not None:
                    resolution_payload = session_resolution_payload(getattr(service_ref, "session_resolution", None))
                    if resolution_payload:
                        current_session_id = int(resolution_payload.get("resolved_session_id") or current_session_id)
                        effective_session_plan = tuple(
                            int(item)
                            for item in tuple(resolution_payload.get("effective_session_plan") or ())
                            if str(item or "").strip()
                        )
                        if effective_session_plan:
                            current_session_candidates = effective_session_plan
                            current_enable_derived_fallback = False
                            current_max_session_attempts = len(effective_session_plan)
                broker_cfg = XtTraderBrokerOrderConfig(
                    user_data_path=str(config.qmt_userdata or ""),
                    account_id=resolved_account_id,
                    account_type="STOCK",
                    session_id=int(current_session_id),
                    connect_retries=max(1, int(config.connect_retries)),
                    connect_retry_interval_seconds=max(3.0, float(config.connect_retry_interval_seconds)),
                    strategy_name="xtqmt_trade_gateway",
                    register_callback=bool(config.register_callback),
                    connect_cooldown_seconds=max(0.0, float(config.connect_cooldown_seconds)),
                    enforce_connect_precheck=bool(config.enforce_connect_precheck),
                    require_up_queue_file=bool(config.require_up_queue_file and require_write_permission),
                    session_candidates=tuple(current_session_candidates),
                    enable_derived_session_fallback=bool(current_enable_derived_fallback),
                    max_session_attempts=max(1, int(current_max_session_attempts)),
                )
                return broker_factory(broker_cfg)
            broker_adapter_factory_for_service = _build_broker_adapter
            if needs.need_broker:
                broker_adapter = _build_broker_adapter(require_write_permission_gate)

    service = TradeOpsService(
        TradeOpsConfig(
            account_id=resolved_account_id,
            trading_day=config.trading_day,
            event_mode=str(config.event_mode or "tick"),
            output_dir=str(config.output_dir or "output"),
            state_dir=str(config.state_dir or "state"),
            execution_mode=execution_mode,
            enforce_guard_token=True,
            enforce_trading_session=bool(config.enforce_trading_session),
            risk_max_single_order_notional=float(config.risk_max_single_order_notional),
            risk_max_daily_notional=float(config.risk_max_daily_notional),
            risk_white_list=parse_white_list(",".join(str(item) for item in config.risk_white_list or ())),
            kill_switch_file=str(config.kill_switch_file or ""),
            pretrade_connect_window=max(1, int(config.pretrade_connect_window)),
            pretrade_connect_threshold=min(1.0, max(0.0, float(config.pretrade_connect_threshold))),
            pretrade_connect_interval_seconds=max(3.0, float(config.pretrade_connect_interval_seconds)),
            price_mode=str(config.price_mode or "l1_protect"),
            qmt_exe=str(config.qmt_exe or ""),
            qmt_userdata=str(config.qmt_userdata or ""),
            xtdata_port=int(getattr(config, "xtdata_port", 0) or 0),
            session_candidates=tuple(session_resolution.effective_session_plan),
            connect_retries=max(1, int(config.connect_retries)),
            connect_retry_interval_seconds=max(3.0, float(config.connect_retry_interval_seconds)),
            wake_wait_seconds=max(1, int(config.wake_wait_seconds)),
            require_connect_stage=bool(config.require_connect_stage),
            require_subscribe_stage=bool(config.require_subscribe_stage),
            require_snapshot_stage=bool(config.require_snapshot_stage),
            snapshot_requires_position=bool(config.snapshot_requires_position),
        ),
        market_data_provider=market_data,
        shadow_adapter=shadow_adapter,
        broker_order_adapter=broker_adapter,
        broker_order_adapter_factory=broker_adapter_factory_for_service,
        broker_order_adapter_requires_write_permission=require_write_permission_gate,
        session_resolution=session_resolution,
    )
    service_holder["service"] = service
    return TradeOpsRuntimeContext(
        service=service,
        wake_report=dict(wake_report),
        resolved_account_id=resolved_account_id,
        resolved_session_id=int(resolved_session_id),
        session_resolution=session_resolution,
    )
