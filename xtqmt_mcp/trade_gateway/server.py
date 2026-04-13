from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import time
from typing import Any, Callable
import uuid

from xtqmt_mcp.session_resolution import session_resolution_payload
from xtqmt_mcp.mcp_rpc import initialize_result, jsonrpc_error, prompt_get_result, resource_read_result, tool_call_result
from xtqmt_mcp.miniqmt_login.contracts import MiniQmtLoginConfig
from xtqmt_mcp.miniqmt_login.service import ensure_miniqmt_logged_in
from xtqmt_mcp.runtime_truth import health_runtime_truth_payload
from xtqmt_mcp.trade_ops import TradeOpsResult
from xtqmt_mcp.types import OrderPlaceRequest, Side

from .bootstrap import TradeOpsRuntimeContext, build_trade_ops_context
from .capability_v2 import place_order_capability
from .config import (
    ACCOUNT_CONTRACT_SINGLE_PRIMARY,
    ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
    DEFAULT_TOOL_NAMES,
    TradeGatewayConfig,
    load_trade_gateway_config,
)
from .envelope import (
    append_call_log,
    call_log_path,
    envelope_from_exception,
    envelope_from_login_payload,
    envelope_from_trade_result,
)
from .fills import list_fills
from .prompts import get_trade_prompt, trade_prompt_definitions
from .resources import cache_trade_resource, read_trade_resource, trade_resource_definitions
from .session_manager import GatewaySessionManager, SessionWarmError


class ToolValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code or "validation_error")
        self.message = str(message)


class TradeGatewayServer:
    def __init__(
        self,
        config: TradeGatewayConfig,
        *,
        login_handler: Callable[[MiniQmtLoginConfig], Any] = ensure_miniqmt_logged_in,
        trade_context_factory: Callable[[str], TradeOpsRuntimeContext] | None = None,
        uuid_factory: Callable[[], str] | None = None,
        time_fn: Callable[[], float] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._login_handler = login_handler
        self._trade_context_factory = trade_context_factory
        self._uuid_factory = uuid_factory or (lambda: str(uuid.uuid4()))
        self._time_fn = time_fn or time.monotonic
        self._now_fn = now_fn or datetime.now
        self._session_manager = GatewaySessionManager(
            config.trade_ops,
            context_builder=(
                (lambda cfg, tool_name: self._trade_context_factory(tool_name))
                if self._trade_context_factory is not None
                else (lambda cfg, tool_name: build_trade_ops_context(cfg, tool_name))
            ),
        )
        self._tool_defs = {item["name"]: item for item in self._build_tool_definitions()}

    @property
    def bind_host(self) -> str:
        return self._config.transport.bind_host

    @property
    def bind_port(self) -> int:
        return int(self._config.transport.bind_port)

    @property
    def mcp_path(self) -> str:
        return self._config.transport.mcp_path

    @property
    def health_path(self) -> str:
        return self._config.transport.health_path

    @property
    def protocol_version_http(self) -> str:
        return self._config.transport.protocol_version_http

    @property
    def allowed_origin_hosts(self) -> tuple[str, ...]:
        return tuple(self._config.transport.allow_origin_hosts or ("127.0.0.1", "localhost", "::1"))

    def health_payload(self) -> dict[str, Any]:
        payload = {
            "ok": True,
            "server_name": self._config.identity.server_name,
            "server_version": self._config.identity.server_version,
            "protocol_version": self._config.identity.protocol_version,
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
            "mcp_path": self.mcp_path,
            "health_path": self.health_path,
            "enabled_tools": list(self._config.enabled_tools),
            "enabled_resources": list(self._config.enabled_resources),
            "enabled_prompts": list(self._config.enabled_prompts),
            "bundle_root": self._config.bundle.bundle_root,
            "abi_tag": self._config.bundle.abi_tag,
            "execution_mode": str(self._config.trade_ops.execution_mode or "live"),
            "account_contract": ACCOUNT_CONTRACT_SINGLE_PRIMARY,
            "account_input_mode": ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
            "readiness_layers": {
                "read_only": {
                    "summary": "Read-only preflight gates probe.connection and snapshot diagnostics.",
                    "diagnostic_tools": ["probe.connection", "snapshot.l1"],
                    "blocking": True,
                },
                "write_permission": {
                    "summary": "Write-permission preflight (for example up_queue_xtquant) is reported separately and blocks write tools only.",
                    "diagnostic_source": "probe.connection.data.readiness_layers.write_permission",
                    "blocking": False,
                    "write_tools": ["order.place", "order.cancel"],
                },
            },
        }
        kill_switch_file = str(self._config.trade_ops.kill_switch_file or "")
        payload["write_safety"] = {
            "kill_switch_configured": bool(kill_switch_file),
            "kill_switch_file": kill_switch_file,
            "release_blockers": ["kill_switch_unconfigured"] if (self._evidence_scope() == "prod" and not kill_switch_file) else [],
        }
        payload.update(
            health_runtime_truth_payload(
                server_name=self._config.identity.server_name,
                bind_host=self.bind_host,
                bind_port=self.bind_port,
                config_path=self._config.config_path,
                audit_root=self._config.audit.call_log_root,
                audit_filename=self._config.audit.call_log_name,
                state_root=self._config.runtime_paths.state_root,
                artifact_root=self._config.runtime_paths.artifact_root,
                now=self._now_fn(),
            )
        )
        return payload

    def _build_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "miniqmt.ensure_logged_in",
                "description": "Ensure MiniQMT is launched and logged in using the server-side primary account config and saved credentials.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "login_timeout_seconds": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "session.warm",
                "description": "Warm and persist the server-side primary trading session for later MCP calls.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "force": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "session.status",
                "description": "Show the current server-side primary session status.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "session.close",
                "description": "Close the current server-side primary session and release broker resources.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "probe.connection",
                "description": "Run xtquant connection probe on the active owner-managed session (no explicit account argument).",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "account.show",
                "description": "Show the current primary-account asset snapshot from the warmed session.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "positions.list",
                "description": "List current positions for the primary account from the warmed session.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "orders.list",
                "description": (
                    "List current open orders for the primary account; prefer broker read and expose explicit "
                    "owner-session shadow fallback when the broker read path is unavailable or broker connect fails. "
                    "Warm-health-only shadow results are not equivalent to public broker readiness."
                ),
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "fills.list",
                "description": "List fills for the primary account on one trading day with optional idempotency filters.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "trading_day": {"type": "string"},
                        "broker_order_id": {"type": "string"},
                        "client_order_key": {"type": "string"},
                        "intent_id": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "snapshot.l1",
                "description": "Fetch one latest L1 top-of-book snapshot for the symbol from the primary session context.",
                "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"], "additionalProperties": False},
            },
            {
                "name": "order.status",
                "description": "Query one broker order status by decimal broker_order_id.",
                "inputSchema": {"type": "object", "properties": {"broker_order_id": {"type": "string"}}, "required": ["broker_order_id"], "additionalProperties": False},
            },
            {
                "name": "order.cancel",
                "description": "Cancel one broker order by decimal broker_order_id.",
                "inputSchema": {"type": "object", "properties": {"broker_order_id": {"type": "string"}}, "required": ["broker_order_id"], "additionalProperties": False},
            },
            {
                "name": "order.place",
                "description": "Place one governed broker order through the server-side write path on the warmed primary-account trading session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "side": {"type": "string", "enum": ["BUY", "SELL"]},
                        "qty": {"type": "integer", "minimum": 1},
                        "price_mode": {"type": "string", "enum": ["l1_protect", "fixed"]},
                        "limit_price": {"type": "number", "exclusiveMinimum": 0},
                        "client_order_key": {"type": "string"},
                        "intent_id": {"type": "string"},
                    },
                    "required": ["code", "side", "qty"],
                    "additionalProperties": False,
                },
            },
        ]

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [self._tool_defs[name] for name in self._config.enabled_tools if name in self._tool_defs]

    def dispatch(self, request: dict[str, Any], *, session_id: str = "") -> dict[str, Any] | None:
        if not isinstance(request, dict):
            return None
        jsonrpc = str(request.get("jsonrpc", "2.0") or "2.0")
        request_id = request.get("id")
        method = str(request.get("method", "") or "")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return initialize_result(
                jsonrpc=jsonrpc,
                request_id=request_id,
                protocol_version=self._config.identity.protocol_version,
                server_name=self._config.identity.server_name,
                server_version=self._config.identity.server_version,
            )
        if method == "ping":
            return {"jsonrpc": jsonrpc, "id": request_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": jsonrpc, "id": request_id, "result": {"tools": self.tool_definitions()}}
        if method == "resources/list":
            return {"jsonrpc": jsonrpc, "id": request_id, "result": {"resources": trade_resource_definitions(self._config)}}
        if method == "prompts/list":
            return {"jsonrpc": jsonrpc, "id": request_id, "result": {"prompts": trade_prompt_definitions(self._config)}}
        if method == "resources/read":
            params = self._ensure_object(request.get("params") or {})
            uri = self._require_string(params, "uri", "resources.read")
            payload = read_trade_resource(
                self._config,
                uri,
                session_summary_provider=lambda: self._session_manager.status(),
                capability_summary_provider=self._capability_resource_payload,
            )
            return resource_read_result(jsonrpc, request_id, uri, payload["payload"])
        if method == "prompts/get":
            params = self._ensure_object(request.get("params") or {})
            name = self._require_string(params, "name", "prompts.get")
            try:
                payload = get_trade_prompt(self._config, name)
            except KeyError:
                return jsonrpc_error(jsonrpc, request_id, -32601, f"unknown prompt: {name}")
            return prompt_get_result(jsonrpc, request_id, payload)
        if method == "tools/call":
            params = self._ensure_object(request.get("params") or {})
            name = str(params.get("name", "") or "")
            if name not in self._config.enabled_tools or name not in self._tool_defs:
                return jsonrpc_error(jsonrpc, request_id, -32601, f"unknown tool: {name}")
            try:
                arguments = self._ensure_object(params.get("arguments") or {})
            except ValueError as exc:
                return jsonrpc_error(jsonrpc, request_id, -32602, str(exc))
            envelope = self._call_tool(name, arguments)
            return tool_call_result(jsonrpc, request_id, envelope)
        return jsonrpc_error(jsonrpc, request_id, -32601, f"unknown method: {method}")

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        trace_id = self._uuid_factory()
        started_at = self._time_fn()
        server_now = self._now_fn()
        log_path = call_log_path(self._config.audit.call_log_root, self._config.audit.call_log_name, now=server_now)
        base_artifacts = [log_path.as_posix()]
        try:
            if tool_name == "miniqmt.ensure_logged_in":
                envelope = self._handle_login(arguments, trace_id, started_at, base_artifacts, server_now)
            else:
                envelope = self._handle_trade_tool(tool_name, arguments, trace_id, started_at, base_artifacts, server_now)
        except ToolValidationError as exc:
            envelope = envelope_from_exception(
                tool=tool_name,
                trace_id=trace_id,
                started_at=started_at,
                error_code=exc.code,
                message=exc.message,
                artifacts=base_artifacts,
                server_ts=server_now.isoformat(timespec="seconds"),
                default_category="validation",
            )
        except ModuleNotFoundError as exc:
            message = str(exc).split(":", 1)[-1] if str(exc).startswith("xtquant_import_failed:") else str(exc)
            envelope = envelope_from_exception(
                tool=tool_name,
                trace_id=trace_id,
                started_at=started_at,
                error_code="xtquant_import_failed",
                message=f"xtquant import failed: {message}",
                artifacts=base_artifacts,
                server_ts=server_now.isoformat(timespec="seconds"),
            )
        except Exception as exc:
            envelope = envelope_from_exception(
                tool=tool_name,
                trace_id=trace_id,
                started_at=started_at,
                error_code="server_env_not_ready",
                message=str(exc),
                artifacts=base_artifacts,
                server_ts=server_now.isoformat(timespec="seconds"),
            )
        self._write_call_log(log_path, trace_id, tool_name, arguments, envelope, server_now)
        self._cache_resource_from_tool(tool_name, envelope)
        return envelope

    def _handle_login(
        self,
        arguments: dict[str, Any],
        trace_id: str,
        started_at: float,
        base_artifacts: list[str],
        server_now: datetime,
    ) -> dict[str, Any]:
        self._require_known_fields(arguments, "miniqmt.ensure_logged_in", ("login_timeout_seconds",))
        account_id = str(self._config.login.account_id or "").strip()
        timeout_seconds = max(1, int(arguments.get("login_timeout_seconds", self._config.login.login_timeout_seconds)))
        result = self._login_handler(
            MiniQmtLoginConfig(
                qmt_exe=self._config.login.qmt_exe,
                qmt_userdata=self._config.login.qmt_userdata,
                account_id=account_id,
                credential_target=self._config.login.credential_target,
                login_timeout_seconds=timeout_seconds,
                startup_grace_seconds=self._config.login.startup_grace_seconds,
                port_host=self._config.login.port_host,
                port_num=self._config.login.port_num,
            )
        )
        payload = result.as_payload() if hasattr(result, "as_payload") else dict(result or {})
        return envelope_from_login_payload(
            tool="miniqmt.ensure_logged_in",
            payload=payload,
            trace_id=trace_id,
            started_at=started_at,
            artifacts=base_artifacts,
            server_ts=server_now.isoformat(timespec="seconds"),
        )

    def _handle_trade_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        trace_id: str,
        started_at: float,
        base_artifacts: list[str],
        server_now: datetime,
    ) -> dict[str, Any]:
        if tool_name == "session.warm":
            self._require_known_fields(arguments, tool_name, ("force",))
            force = bool(arguments.get("force", False))
            try:
                state = self._session_manager.warm(force=force)
            except SessionWarmError as exc:
                return envelope_from_exception(
                    tool=tool_name,
                    trace_id=trace_id,
                    started_at=started_at,
                    error_code="session_warm_failed",
                    message=str(exc),
                    artifacts=base_artifacts,
                    server_ts=server_now.isoformat(timespec="seconds"),
                    data=dict(exc.payload),
                )
            result = TradeOpsResult(
                command="session.warm",
                ok=True,
                payload=self._decorate_payload(dict(state.summary()), scope="primary_session"),
            )
            return envelope_from_trade_result(tool=tool_name, result=result, trace_id=trace_id, started_at=started_at, artifacts=base_artifacts, server_ts=server_now.isoformat(timespec="seconds"))
        if tool_name == "session.status":
            self._require_empty(arguments, tool_name)
            payload = self._decorate_payload(self._session_manager.status(), scope="primary_session")
            result = TradeOpsResult(command="session.status", ok=True, payload=payload)
            return envelope_from_trade_result(tool=tool_name, result=result, trace_id=trace_id, started_at=started_at, artifacts=base_artifacts, server_ts=server_now.isoformat(timespec="seconds"))
        if tool_name == "session.close":
            self._require_empty(arguments, tool_name)
            payload = self._decorate_payload(self._session_manager.close(), scope="primary_session")
            result = TradeOpsResult(command="session.close", ok=True, payload=payload)
            return envelope_from_trade_result(tool=tool_name, result=result, trace_id=trace_id, started_at=started_at, artifacts=base_artifacts, server_ts=server_now.isoformat(timespec="seconds"))
        if tool_name == "probe.connection":
            self._require_empty(arguments, tool_name)
            try:
                state, result = self._session_manager.execute(
                    account_id="",
                    runner=lambda context: context.service.probe_connection(),
                    require_ready=False,
                )
            except RuntimeError as exc:
                error_code = str(exc).strip() or "probe_connection_unavailable"
                return envelope_from_exception(
                    tool=tool_name,
                    trace_id=trace_id,
                    started_at=started_at,
                    error_code=error_code,
                    message=str(exc),
                    artifacts=base_artifacts,
                    server_ts=server_now.isoformat(timespec="seconds"),
                )
            self._decorate_result_payload(result, scope="primary_session", context=state.context)
            return envelope_from_trade_result(
                tool=tool_name,
                result=result,
                trace_id=trace_id,
                started_at=started_at,
                artifacts=base_artifacts + self._service_artifacts(tool_name, state.context),
                warnings=self._context_warnings(state.context),
                server_ts=server_now.isoformat(timespec="seconds"),
            )
        if tool_name == "snapshot.l1":
            self._require_known_fields(arguments, tool_name, ("code",))
            code = self._require_string(arguments, "code", tool_name)
            try:
                state, result = self._session_manager.execute(
                    account_id="",
                    runner=lambda context, code=code: context.service.snapshot_l1(code),
                    require_ready=False,
                )
            except RuntimeError as exc:
                error_code = str(exc).strip() or "snapshot_unavailable"
                return envelope_from_exception(
                    tool=tool_name,
                    trace_id=trace_id,
                    started_at=started_at,
                    error_code=error_code,
                    message=str(exc),
                    artifacts=base_artifacts,
                    server_ts=server_now.isoformat(timespec="seconds"),
                )
            self._decorate_result_payload(result, scope="primary_session", context=state.context)
            return envelope_from_trade_result(
                tool=tool_name,
                result=result,
                trace_id=trace_id,
                started_at=started_at,
                artifacts=base_artifacts + self._service_artifacts(tool_name, state.context),
                warnings=self._context_warnings(state.context),
                server_ts=server_now.isoformat(timespec="seconds"),
            )

        if tool_name == "account.show":
            self._require_empty(arguments, tool_name)
            runner = lambda context: context.service.account_show()
        elif tool_name == "positions.list":
            self._require_empty(arguments, tool_name)
            runner = lambda context: context.service.positions_list()
        elif tool_name == "orders.list":
            self._require_empty(arguments, tool_name)
            runner = lambda context: context.service.orders_list()
        elif tool_name == "fills.list":
            self._require_known_fields(arguments, tool_name, ("trading_day", "broker_order_id", "client_order_key", "intent_id"))
            fills_args = self._parse_fills_list(arguments)
            runner = lambda context, fills_args=fills_args: list_fills(context.service, **fills_args)
        elif tool_name == "order.status":
            self._require_known_fields(arguments, tool_name, ("broker_order_id",))
            broker_order_id = self._require_decimal_id(arguments, tool_name)
            runner = lambda context, broker_order_id=broker_order_id: context.service.order_status(broker_order_id)
        elif tool_name == "order.cancel":
            self._require_known_fields(arguments, tool_name, ("broker_order_id",))
            broker_order_id = self._require_decimal_id(arguments, tool_name)
            runner = lambda context, broker_order_id=broker_order_id: context.service.order_cancel(broker_order_id)
        elif tool_name == "order.place":
            self._require_known_fields(arguments, tool_name, ("code", "side", "qty", "price_mode", "limit_price", "client_order_key", "intent_id"))
            req = self._parse_order_place_capability(arguments, account_id="")
            runner = lambda context, req=req: place_order_capability(context.service, req)
        else:
            raise ToolValidationError("validation_error", f"unsupported tool: {tool_name}")

        require_ready = tool_name in {"fills.list", "order.status", "order.cancel", "order.place"}
        try:
            state, result = self._session_manager.execute(
                account_id="",
                runner=runner,
                require_ready=require_ready,
            )
        except RuntimeError as exc:
            error_code = str(exc).strip() or f"{tool_name}_failed"
            return envelope_from_exception(
                tool=tool_name,
                trace_id=trace_id,
                started_at=started_at,
                error_code=error_code,
                message=str(exc),
                artifacts=base_artifacts,
                server_ts=server_now.isoformat(timespec="seconds"),
            )
        self._decorate_result_payload(result, scope=self._tool_account_scope(tool_name), context=state.context)
        return envelope_from_trade_result(
            tool=tool_name,
            result=result,
            trace_id=trace_id,
            started_at=started_at,
            artifacts=base_artifacts + self._service_artifacts(tool_name, state.context),
            warnings=self._context_warnings(state.context),
            server_ts=server_now.isoformat(timespec="seconds"),
        )

    def _cache_resource_from_tool(self, tool_name: str, envelope: dict[str, Any]) -> None:
        payload = dict(envelope.get("data") or {})
        audit = dict(envelope.get("audit") or {})
        trace_id = str(audit.get("trace_id") or "")
        server_ts = str(audit.get("server_ts") or "")
        if tool_name in {"session.warm", "session.status", "session.close"}:
            cache_trade_resource(self._config, "trade://session/current", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "account.show":
            cache_trade_resource(self._config, "trade://account/current", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "orders.list":
            cache_trade_resource(self._config, "trade://orders/today", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "fills.list":
            cache_trade_resource(self._config, "trade://fills/today", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "order.place":
            cache_trade_resource(self._config, "diag://order_place/latest", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "order.cancel":
            cache_trade_resource(self._config, "diag://order_cancel/latest", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "order.status":
            cache_trade_resource(self._config, "diag://order_status/latest", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "probe.connection":
            cache_trade_resource(self._config, "diag://probe/latest", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name == "miniqmt.ensure_logged_in":
            cache_trade_resource(self._config, "diag://login/latest", payload, trace_id=trace_id, server_ts=server_ts)

    def _service_artifacts(self, tool_name: str, context: TradeOpsRuntimeContext) -> list[str]:
        service_cfg = getattr(getattr(context, "service", None), "cfg", None)
        if service_cfg is None:
            return []
        output_dir = Path(str(getattr(service_cfg, "output_dir", "") or ""))
        state_dir = Path(str(getattr(service_cfg, "state_dir", "") or ""))
        day = getattr(service_cfg, "trading_day", None)
        day_key = day.strftime("%Y%m%d") if day else self._now_fn().strftime("%Y%m%d")
        day_root = output_dir / day_key if output_dir else output_dir
        if tool_name == "order.place":
            return [
                (day_root / "real" / "orders_submit_log.csv").as_posix(),
                (day_root / "real" / "orders_state_timeline.csv").as_posix(),
            ]
        if tool_name == "fills.list":
            return [
                (day_root / "real" / "trades_real.csv").as_posix(),
                (state_dir / "order_state_timeline.sqlite3").as_posix(),
            ]
        if tool_name == "probe.connection":
            return [(Path(self._config.runtime_paths.artifact_root) / "trade_probe_latest.json").as_posix()]
        return []

    def _context_warnings(self, context: TradeOpsRuntimeContext) -> list[str]:
        report = dict(getattr(context, "wake_report", {}) or {})
        warnings: list[str] = []
        if bool(report.get("process_started", False)):
            warnings.append("xtminiqmt_process_started_during_call")
        if bool(report.get("xtdata_port_ready_before", False)) is False and bool(report.get("xtdata_port_ready_after", False)):
            warnings.append("xtdata_port_became_ready_during_call")
        return warnings

    def _parse_order_place_capability(self, arguments: dict[str, Any], *, account_id: str = "") -> OrderPlaceRequest:
        code = self._require_string(arguments, "code", "order.place").upper()
        side_text = self._require_string(arguments, "side", "order.place").upper()
        if side_text not in {"BUY", "SELL"}:
            raise ToolValidationError("validation_error", "order.place.side must be BUY or SELL")
        qty_raw = arguments.get("qty")
        if qty_raw is None:
            raise ToolValidationError("invalid_quantity", "order.place.qty is required")
        try:
            qty = int(qty_raw)
        except Exception as exc:
            raise ToolValidationError("invalid_quantity", f"order.place.qty must be integer: {exc}") from exc
        price_mode = str(arguments.get("price_mode", self._config.trade_ops.price_mode) or self._config.trade_ops.price_mode).strip().lower() or "l1_protect"
        limit_price_raw = arguments.get("limit_price")
        limit_price = None if limit_price_raw in (None, "") else float(limit_price_raw)
        if (limit_price is not None) and price_mode != "fixed":
            raise ToolValidationError("limit_price_requires_fixed_mode", "limit_price requires price_mode=fixed")
        return OrderPlaceRequest(
            account_id=str(account_id or "").strip(),
            code=code,
            side=Side(side_text),
            quantity=qty,
            guard_token="",
            price_mode=price_mode,
            limit_price=limit_price,
            client_order_key=str(arguments.get("client_order_key", "") or "").strip(),
            intent_id=str(arguments.get("intent_id", "") or "").strip(),
        )

    def _parse_fills_list(self, arguments: dict[str, Any]) -> dict[str, Any]:
        trading_day_text = str(arguments.get("trading_day", "") or "").strip()
        trading_day = date.fromisoformat(trading_day_text) if trading_day_text else self._config.trade_ops.trading_day
        return {
            "trading_day": trading_day,
            "broker_order_id": str(arguments.get("broker_order_id", "") or "").strip(),
            "client_order_key": str(arguments.get("client_order_key", "") or "").strip(),
            "intent_id": str(arguments.get("intent_id", "") or "").strip(),
        }

    def _decorate_payload(self, payload: dict[str, Any], *, scope: str) -> dict[str, Any]:
        payload.setdefault("account_contract", ACCOUNT_CONTRACT_SINGLE_PRIMARY)
        payload.setdefault("account_input_mode", ACCOUNT_INPUT_MODE_SERVICE_CONTEXT)
        payload.setdefault("account_scope", scope)
        return payload

    def _decorate_result_payload(
        self,
        result: TradeOpsResult,
        *,
        scope: str,
        context: TradeOpsRuntimeContext | None = None,
    ) -> None:
        payload = getattr(result, "payload", None)
        if isinstance(payload, dict):
            if "session_resolution" not in payload:
                resolved = session_resolution_payload(getattr(context, "session_resolution", None))
                if not resolved:
                    service = getattr(context, "service", None) if context is not None else None
                    resolved = session_resolution_payload(getattr(service, "session_resolution", None))
                if resolved:
                    payload["session_resolution"] = resolved
            self._decorate_payload(payload, scope=scope)

    def _tool_account_scope(self, tool_name: str) -> str:
        if tool_name in {"session.warm", "session.status", "session.close", "probe.connection", "snapshot.l1"}:
            return "primary_session"
        if tool_name in {"account.show", "positions.list", "orders.list", "fills.list", "order.status", "order.cancel", "order.place"}:
            return "primary_account"
        return "service_context"

    def _require_known_fields(self, arguments: dict[str, Any], tool_name: str, allowed_fields: tuple[str, ...]) -> None:
        extras = sorted(set(arguments or {}).difference(allowed_fields))
        if not extras:
            return
        raise ToolValidationError("validation_error", f"{tool_name} does not accept: {', '.join(extras)}")

    def _ensure_object(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        raise ValueError("request params must be object")

    def _require_empty(self, arguments: dict[str, Any], tool_name: str) -> None:
        if dict(arguments or {}):
            raise ToolValidationError("validation_error", f"{tool_name} does not accept arguments")

    def _require_string(self, arguments: dict[str, Any], field: str, tool_name: str) -> str:
        token = str(arguments.get(field, "") or "").strip()
        if not token:
            raise ToolValidationError("validation_error", f"{tool_name}.{field} is required")
        return token

    def _require_decimal_id(self, arguments: dict[str, Any], tool_name: str) -> str:
        broker_order_id = self._require_string(arguments, "broker_order_id", tool_name)
        if not broker_order_id.isdigit():
            raise ToolValidationError("invalid_broker_order_id", f"{tool_name}.broker_order_id must be a decimal string")
        return broker_order_id

    def _write_call_log(
        self,
        log_path: Path,
        trace_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        envelope: dict[str, Any],
        server_now: datetime,
    ) -> None:
        if not self._config.audit.enabled:
            return
        append_call_log(
            log_path,
            {
                "trace_id": trace_id,
                "server_ts": server_now.isoformat(timespec="seconds"),
                "tool": tool_name,
                "arguments": dict(arguments),
                "envelope": envelope,
                "evidence_scope": self._evidence_scope(),
                "state_root": self._config.runtime_paths.state_root,
            },
        )

    def _evidence_scope(self) -> str:
        parts = tuple(str(part).lower() for part in Path(self._config.runtime_paths.state_root).parts)
        for idx in range(0, max(0, len(parts) - 2)):
            if parts[idx : idx + 3] == ("instance", "prod", "state"):
                return "prod"
        return "non_prod"

    def _capability_resource_payload(self) -> dict[str, Any]:
        return {
            "server_name": self._config.identity.server_name,
            "server_version": self._config.identity.server_version,
            "enabled_tools": list(self._config.enabled_tools),
            "enabled_resources": list(self._config.enabled_resources),
            "enabled_prompts": list(self._config.enabled_prompts),
            "order_echo_fields": ["client_order_key", "intent_id"],
            "write_contract_flags": ["broker_submission_attempted", "local_gate_intercepted"],
            "session_contract_version": "trade_session_contract_v1",
            "execution_mode": str(self._config.trade_ops.execution_mode or "live"),
            "account_contract": ACCOUNT_CONTRACT_SINGLE_PRIMARY,
            "account_input_mode": ACCOUNT_INPUT_MODE_SERVICE_CONTEXT,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run xtqmt trade gateway over streamable_http")
    parser.add_argument("--config", default="", help="gateway YAML config path (default: configs/trade_gateway.local.yaml)")
    from xtqmt_mcp.http_transport import serve_streamable_http

    args = parser.parse_args(argv)
    gateway = TradeGatewayServer(load_trade_gateway_config(args.config or None))
    return serve_streamable_http(gateway)
