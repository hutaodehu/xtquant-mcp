from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
from typing import Any
import uuid

from xtqmt_mcp.http_transport import serve_streamable_http
from xtqmt_mcp.mcp_rpc import initialize_result, jsonrpc_error, prompt_get_result, resource_read_result, tool_call_result
from xtqmt_mcp.runtime_truth import health_runtime_truth_payload
from xtqmt_mcp.trade_gateway.envelope import append_call_log, call_log_path

from .config import DataGatewayConfig, load_data_gateway_config
from .prompts import data_prompt_definitions, get_data_prompt
from .resources import cache_data_resource, data_resource_definitions, read_data_resource
from .service import DataGatewayService, DataToolResult, XtDataUnavailable


class ToolValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code or "validation_error")
        self.message = str(message or code or "validation error")


class DataGatewayServer:
    def __init__(
        self,
        config: DataGatewayConfig,
        *,
        service: DataGatewayService | None = None,
        uuid_factory: Any | None = None,
        time_fn: Any | None = None,
        now_fn: Any | None = None,
    ) -> None:
        self._config = config
        self._service = service or DataGatewayService(config)
        self._uuid_factory = uuid_factory or (lambda: str(uuid.uuid4()))
        self._time_fn = time_fn or time.monotonic
        self._now_fn = now_fn or datetime.now
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
            return {"jsonrpc": jsonrpc, "id": request_id, "result": {"resources": data_resource_definitions(self._config)}}
        if method == "prompts/list":
            return {"jsonrpc": jsonrpc, "id": request_id, "result": {"prompts": data_prompt_definitions(self._config)}}
        if method == "resources/read":
            params = self._ensure_object(request.get("params") or {})
            uri = self._require_string(params, "uri", "resources.read")
            return resource_read_result(jsonrpc, request_id, uri, self._resource_payload(uri))
        if method == "prompts/get":
            params = self._ensure_object(request.get("params") or {})
            name = self._require_string(params, "name", "prompts.get")
            try:
                payload = get_data_prompt(self._config, name)
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
            return tool_call_result(jsonrpc, request_id, self._call_tool(name, arguments))
        return jsonrpc_error(jsonrpc, request_id, -32601, f"unknown method: {method}")

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [self._tool_defs[name] for name in self._config.enabled_tools if name in self._tool_defs]

    def _build_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {"name": "xtdata.status", "description": "Show layered xtdata readiness and both configured/resolved runtime endpoints.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "xtdata.instruments.search", "description": "Search instruments from configured sectors with optional detail expansion.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "sectors": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}, "is_complete": {"type": "boolean"}}, "additionalProperties": False}},
            {"name": "xtdata.calendar.query", "description": "Query trading dates or trading calendar for one market.", "inputSchema": {"type": "object", "properties": {"market": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "count": {"type": "integer"}, "mode": {"type": "string", "enum": ["dates", "calendar"]}}, "additionalProperties": False}},
            {"name": "xtdata.snapshot.batch", "description": "Fetch latest batch snapshots using xtdata full tick.", "inputSchema": {"type": "object", "properties": {"codes": {"type": "array", "items": {"type": "string"}}}, "required": ["codes"], "additionalProperties": False}},
            {"name": "xtdata.history.get_bars", "description": "Fetch historical bar data for one or more symbols.", "inputSchema": {"type": "object", "properties": {"codes": {"type": "array", "items": {"type": "string"}}, "fields": {"type": "array", "items": {"type": "string"}}, "period": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "count": {"type": "integer"}, "dividend_type": {"type": "string"}, "fill_data": {"type": "boolean"}}, "required": ["codes"], "additionalProperties": False}},
            {"name": "xtdata.history.get_ticks", "description": "Fetch historical tick data for one or more symbols.", "inputSchema": {"type": "object", "properties": {"codes": {"type": "array", "items": {"type": "string"}}, "fields": {"type": "array", "items": {"type": "string"}}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "count": {"type": "integer"}, "dividend_type": {"type": "string"}}, "required": ["codes"], "additionalProperties": False}},
            {"name": "xtdata.download.submit", "description": "Submit one async historical download job.", "inputSchema": {"type": "object", "properties": {"codes": {"type": "array", "items": {"type": "string"}}, "period": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "incrementally": {"type": "boolean"}}, "required": ["codes"], "additionalProperties": False}},
            {"name": "xtdata.download.status", "description": "Show one download job or list current jobs.", "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}}, "additionalProperties": False}},
            {"name": "xtdata.download.cancel", "description": "Cancel one running download job.", "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"], "additionalProperties": False}},
            {"name": "xtdata.subscribe.start", "description": "Start one experimental server-side xtdata subscription lease and return lease recovery context. Durable reconnect or auto-rebuild is not proven.", "inputSchema": {"type": "object", "properties": {"codes": {"type": "array", "items": {"type": "string"}}, "period": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "count": {"type": "integer"}, "dividend_type": {"type": "string"}}, "required": ["codes"], "additionalProperties": False}},
            {"name": "xtdata.subscribe.stop", "description": "Stop one experimental server-side xtdata subscription lease and return whether a rebuild would be required to resume it.", "inputSchema": {"type": "object", "properties": {"subscription_id": {"type": "string"}}, "required": ["subscription_id"], "additionalProperties": False}},
        ]

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        trace_id = self._uuid_factory()
        started_at = self._time_fn()
        server_now = self._now_fn()
        log_path = call_log_path(self._config.audit.call_log_root, self._config.audit.call_log_name, now=server_now)
        base_artifacts = [log_path.as_posix()]
        try:
            result = self._dispatch_tool(tool_name, arguments)
        except ToolValidationError as exc:
            result = DataToolResult(ok=False, payload={}, code=exc.code, message=exc.message, category="validation")
        except XtDataUnavailable as exc:
            result = DataToolResult(ok=False, payload={}, code=exc.code, message=exc.message, category=exc.category, retryable=exc.retryable)
        except ModuleNotFoundError as exc:
            result = DataToolResult(ok=False, payload={}, code="xtquant_import_failed", message=str(exc), category="environment")
        except Exception as exc:
            result = DataToolResult(ok=False, payload={}, code="server_env_not_ready", message=str(exc), category="environment", retryable=True)
        envelope = self._result_to_envelope(tool_name, result, trace_id, started_at, base_artifacts, server_now)
        self._write_call_log(log_path, trace_id, tool_name, arguments, envelope, server_now)
        self._cache_resource_from_tool(tool_name, envelope)
        return envelope

    def _dispatch_tool(self, tool_name: str, arguments: dict[str, Any]) -> DataToolResult:
        if tool_name == "xtdata.status":
            self._require_empty(arguments, tool_name)
            return self._service.status_summary()
        if tool_name == "xtdata.instruments.search":
            return self._service.instruments_search(arguments)
        if tool_name == "xtdata.calendar.query":
            return self._service.calendar_query(arguments)
        if tool_name == "xtdata.snapshot.batch":
            return self._service.snapshot_batch(arguments)
        if tool_name == "xtdata.history.get_bars":
            return self._service.history_get_bars(arguments)
        if tool_name == "xtdata.history.get_ticks":
            return self._service.history_get_ticks(arguments)
        if tool_name == "xtdata.download.submit":
            return self._service.download_submit(arguments)
        if tool_name == "xtdata.download.status":
            return self._service.download_status(arguments)
        if tool_name == "xtdata.download.cancel":
            return self._service.download_cancel(arguments)
        if tool_name == "xtdata.subscribe.start":
            return self._service.subscribe_start(arguments)
        if tool_name == "xtdata.subscribe.stop":
            return self._service.subscribe_stop(arguments)
        raise ToolValidationError("validation_error", f"unsupported tool: {tool_name}")

    def _result_to_envelope(
        self,
        tool_name: str,
        result: DataToolResult,
        trace_id: str,
        started_at: float,
        base_artifacts: list[str],
        server_now: datetime,
    ) -> dict[str, Any]:
        error = None
        if not result.ok:
            error = {
                "code": str(result.code or "xtdata_call_failed"),
                "message": str(result.message or result.code or "xtdata call failed"),
                "category": str(result.category or "environment"),
                "retryable": bool(result.retryable),
            }
        return {
            "ok": bool(result.ok),
            "tool": tool_name,
            "data": dict(result.payload or {}),
            "error": error,
            "audit": {
                "trace_id": trace_id,
                "server_ts": server_now.isoformat(timespec="seconds"),
                "duration_ms": int(max(0.0, (self._time_fn() - started_at) * 1000.0)),
                "artifacts": base_artifacts + [str(item) for item in result.artifacts],
                "evidence_scope": self._evidence_scope(),
                "state_root": self._config.runtime_paths.state_root,
            },
            "warnings": list(result.warnings or ()),
        }

    def _resource_payload(self, uri: str) -> dict[str, Any]:
        if uri == "xtdata://service/status":
            return read_data_resource(
                self._config,
                uri,
                dynamic_provider=lambda: dict(self._service.status_summary().payload),
            ).get("payload", {})
        if uri == "xtdata://jobs/active":
            return read_data_resource(
                self._config,
                uri,
                dynamic_provider=lambda: dict(self._service.download_status({}).payload),
            ).get("payload", {})
        if uri == "xtdata://leases/active":
            return read_data_resource(
                self._config,
                uri,
                dynamic_provider=lambda: dict(self._service.list_subscriptions_payload()),
            ).get("payload", {})
        return read_data_resource(self._config, uri).get("payload", {})

    def _cache_resource_from_tool(self, tool_name: str, envelope: dict[str, Any]) -> None:
        payload = dict(envelope.get("data") or {})
        audit = dict(envelope.get("audit") or {})
        trace_id = str(audit.get("trace_id") or "")
        server_ts = str(audit.get("server_ts") or "")
        if tool_name == "xtdata.status":
            cache_data_resource(self._config, "xtdata://service/status", payload, trace_id=trace_id, server_ts=server_ts)
            cache_data_resource(
                self._config,
                "xtdata://leases/active",
                self._service.list_subscriptions_payload(),
                trace_id=trace_id,
                server_ts=server_ts,
            )
        elif tool_name == "xtdata.instruments.search":
            cache_data_resource(self._config, "xtdata://catalog/instruments", payload, trace_id=trace_id, server_ts=server_ts)
        elif tool_name.startswith("xtdata.download."):
            cache_data_resource(
                self._config,
                "xtdata://jobs/active",
                self._service.download_status({}).payload,
                trace_id=trace_id,
                server_ts=server_ts,
            )
        elif tool_name in {"xtdata.subscribe.start", "xtdata.subscribe.stop"}:
            cache_data_resource(
                self._config,
                "xtdata://leases/active",
                self._service.list_subscriptions_payload(),
                trace_id=trace_id,
                server_ts=server_ts,
            )

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run xtqmt data gateway over streamable_http")
    parser.add_argument("--config", default="", help="gateway YAML config path (default: configs/data_gateway.local.yaml)")
    args = parser.parse_args(argv)
    gateway = DataGatewayServer(load_data_gateway_config(args.config or None))
    return serve_streamable_http(gateway)
