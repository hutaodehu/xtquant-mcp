from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEMP_ROOT = ROOT / ".tmp" / "tests"
_TEMP_ROOT.mkdir(parents=True, exist_ok=True)

from xtqmt_mcp.trade_gateway.config import TradeAuditConfig, TradeGatewayConfig, TradeLoginConfig, TradeOpsGatewayConfig
from xtqmt_mcp.trade_gateway.capability_v2 import GOVERNED_ORDER_PLACE_GATE_SEQUENCE
from xtqmt_mcp.trade_gateway.bootstrap import trade_ops_needs_for_tool
from xtqmt_mcp.trade_gateway.resources import cache_trade_resource, read_trade_resource
from xtqmt_mcp.trade_gateway.server import TradeGatewayServer
from xtqmt_mcp.trade_ops import TradeOpsResult
from xtqmt_mcp.settings import QmtInstallConfig, ServiceIdentity, ServiceRuntimePaths, TransportConfig, XtquantBundleConfig


@contextmanager
def _workspace_tempdir():
    _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = _TEMP_ROOT / f"case_{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield str(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


class _FakeLoginResult:
    def as_payload(self) -> dict[str, object]:
        return {"ok": True, "status": "already_logged_in", "message": "ok"}


class _FakeSessionManager:
    def warm(self, *, account_id: str = "", force: bool = False) -> object:
        return type(
            "WarmState",
            (),
            {
                "summary": lambda self: {
                    "ready": True,
                    "account_id": "ACC001",
                    "owner_account_id": "ACC001",
                    "session_id": 100,
                    "warmed_at": "2026-03-27T09:30:00",
                    "last_used_at": "2026-03-27T09:30:00",
                    "last_error": "",
                    "reason": "",
                    "last_check_at": "2026-03-27T09:30:00",
                    "wake_report": {},
                    "warm_trace": [],
                    "status_trace": [],
                    "owner_generation": 1,
                    "owner_started_reason": "initial_warm",
                    "session_resolution": {
                        "configured_session_id": 1111,
                        "resolved_base_session_id": 1111,
                        "resolved_session_id": 100,
                        "configured_session_candidates": [1111, 1100, 1101, 100, 101, 111],
                        "effective_session_plan": [100, 1111, 1100, 1101, 101, 111, 2111, 2100, 2101],
                        "derived_session_fallback_enabled": True,
                        "max_session_attempts": 12,
                        "explicit_session_resolution_applied": True,
                    },
                }
            },
        )()

    def status(self, *, account_id: str = "") -> dict[str, object]:
        return {
            "ready": True,
            "account_id": "ACC001",
            "owner_account_id": "ACC001",
            "session_id": 100,
            "warmed_at": "2026-03-27T09:30:00",
            "last_used_at": "2026-03-27T09:30:00",
            "last_error": "",
            "reason": "",
            "last_check_at": "2026-03-27T09:30:00",
            "wake_report": {},
            "warm_trace": [],
            "status_trace": [],
            "owner_generation": 1,
            "owner_started_reason": "initial_warm",
            "session_resolution": {
                "configured_session_id": 1111,
                "resolved_base_session_id": 1111,
                "resolved_session_id": 100,
                "configured_session_candidates": [1111, 1100, 1101, 100, 101, 111],
                "effective_session_plan": [100, 1111, 1100, 1101, 101, 111, 2111, 2100, 2101],
                "derived_session_fallback_enabled": True,
                "max_session_attempts": 12,
                "explicit_session_resolution_applied": True,
            },
        }

    def close(self, *, account_id: str = "") -> dict[str, object]:
        return {
            "ok": True,
            "account_id": "ACC001",
            "closed": True,
            "message": "session closed",
            "owner_generation": 1,
        }


class _FakeSessionManagerWithOverride(_FakeSessionManager):
    def warm(self, *, account_id: str = "", force: bool = False) -> object:
        return type("WarmState", (), {"summary": lambda self: _FakeSessionManagerWithOverride().status()})()

    def status(self, *, account_id: str = "") -> dict[str, object]:
        return {
            "ready": True,
            "account_id": "ACC001",
            "owner_account_id": "ACC001",
            "session_id": 2101,
            "warmed_at": "2026-04-13T09:30:00",
            "last_used_at": "2026-04-13T09:31:00",
            "last_error": "",
            "reason": "",
            "last_check_at": "2026-04-13T09:31:00",
            "wake_report": {},
            "warm_trace": [],
            "status_trace": [],
            "owner_generation": 2,
            "owner_started_reason": "probe_realign",
            "session_resolution": {
                "configured_session_id": 2111,
                "resolved_base_session_id": 2111,
                "resolved_session_id": 2100,
                "configured_session_candidates": [2100, 2111, 2101],
                "effective_session_plan": [2100, 2111, 2101],
                "derived_session_fallback_enabled": False,
                "max_session_attempts": 3,
                "explicit_session_resolution_applied": True,
            },
            "effective_session_resolution": {
                "configured_session_id": 2111,
                "resolved_base_session_id": 2111,
                "resolved_session_id": 2101,
                "configured_session_candidates": [2101, 2100, 2111],
                "effective_session_plan": [2101, 2100, 2111],
                "derived_session_fallback_enabled": False,
                "max_session_attempts": 3,
                "explicit_session_resolution_applied": True,
                "runtime_session_resolution_applied": True,
            },
            "runtime_session_override": {
                "event_type": "runtime_session_resolution_realign",
                "event_source": "probe.connection",
                "reason": "probe_resolution_confirmed",
                "previous_resolved_session_id": 2100,
                "resolved_session_id": 2101,
            },
        }


class _RecordingTradeService:
    def __init__(self) -> None:
        self.place_order_calls: list[object] = []
        self.order_cancel_calls: list[str] = []
        self.session_resolution = {
            "configured_session_id": 1111,
            "resolved_base_session_id": 1111,
            "resolved_session_id": 2111,
            "configured_session_candidates": [1111, 1100, 1101, 100, 101, 111],
            "effective_session_plan": [2111, 1111, 1100, 1101, 100, 101, 111, 3111, 2100, 2101],
            "derived_session_fallback_enabled": True,
            "max_session_attempts": 12,
            "explicit_session_resolution_applied": True,
        }

    def place_order(self, req: object) -> TradeOpsResult:
        self.place_order_calls.append(req)
        return TradeOpsResult(
            command="order.place",
            ok=False,
            payload={
                "ok": False,
                "code": "connect_gate_failed",
                "message": "pretrade connect gate failed",
                "status": "risk_rejected",
                "broker_submission_attempted": False,
                "local_gate_intercepted": True,
                "submission_scope": "local_gate",
                "submission_stage": "connect_gate",
                "persist_ok": True,
                "reconcile_required": False,
                "persistence_error": "",
            },
        )

    def order_cancel(self, broker_order_id: str) -> TradeOpsResult:
        self.order_cancel_calls.append(broker_order_id)
        return TradeOpsResult(
            command="order.cancel",
            ok=False,
            payload={
                "ok": False,
                "code": "connect_gate_failed",
                "message": "pretrade connect gate failed",
                "status": "risk_rejected",
                "broker_order_id": broker_order_id,
                "broker_submission_attempted": False,
                "local_gate_intercepted": True,
                "submission_scope": "local_gate",
                "submission_stage": "connect_gate",
                "persist_ok": True,
                "reconcile_required": False,
                "persistence_error": "",
            },
        )


class _RecordingSessionManager:
    def __init__(self, service: _RecordingTradeService) -> None:
        self.service = service
        self.execute_calls: list[dict[str, object]] = []

    def execute(self, *, account_id: str = "", runner, require_ready: bool = False):  # type: ignore[no-untyped-def]
        self.execute_calls.append({"account_id": account_id, "require_ready": require_ready})
        context = SimpleNamespace(service=self.service, wake_report={})
        state = SimpleNamespace(context=context)
        return state, runner(context)


class TradeGatewayServerTests(unittest.TestCase):
    def test_session_manager_builder_uses_runtime_cfg_by_default_and_custom_factory_when_provided(self) -> None:
        captured: dict[str, object] = {}

        class _FakeSessionManager:
            def __init__(self, config, *, context_builder):  # type: ignore[no-untyped-def]
                runtime_cfg = TradeOpsGatewayConfig(
                    account_id="RUNTIME_ACC",
                    output_dir="/tmp/runtime-output",
                    state_dir="/tmp/runtime-state",
                )
                captured["default_context"] = context_builder(runtime_cfg, "session.warm")
                captured["custom_context"] = context_builder(runtime_cfg, "order.place")

        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="STATIC_ACC",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )

            with (
                patch("xtqmt_mcp.trade_gateway.server.GatewaySessionManager", _FakeSessionManager),
                patch(
                    "xtqmt_mcp.trade_gateway.server.build_trade_ops_context",
                    side_effect=lambda cfg, tool_name: {
                        "factory": "default",
                        "tool_name": tool_name,
                        "account_id": cfg.account_id,
                        "output_dir": cfg.output_dir,
                    },
                ),
            ):
                TradeGatewayServer(config)

            self.assertEqual(captured["default_context"], {
                "factory": "default",
                "tool_name": "session.warm",
                "account_id": "RUNTIME_ACC",
                "output_dir": "/tmp/runtime-output",
            })

            def _custom_factory(tool_name: str) -> object:
                captured["custom_tool_name"] = tool_name
                return {"factory": "custom", "tool_name": tool_name}

            with (
                patch("xtqmt_mcp.trade_gateway.server.GatewaySessionManager", _FakeSessionManager),
                patch(
                    "xtqmt_mcp.trade_gateway.server.build_trade_ops_context",
                    side_effect=lambda cfg, tool_name: {
                        "factory": "default",
                        "tool_name": tool_name,
                        "account_id": cfg.account_id,
                    },
                ),
            ):
                TradeGatewayServer(config, trade_context_factory=_custom_factory)

        self.assertEqual(captured["custom_tool_name"], "order.place")
        self.assertEqual(captured["custom_context"], {"factory": "custom", "tool_name": "order.place"})

    def test_trade_context_factory_is_forwarded_into_session_manager_builder(self) -> None:
        captured: dict[str, object] = {}

        class _FakeSessionManager:
            def __init__(self, config, *, context_builder):  # type: ignore[no-untyped-def]
                captured["config"] = config
                captured["built_context"] = context_builder(config, "session.warm")

        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )

            def _custom_factory(tool_name: str) -> object:
                captured["tool_name"] = tool_name
                return {"factory": "custom", "tool_name": tool_name}

            with (
                patch("xtqmt_mcp.trade_gateway.server.GatewaySessionManager", _FakeSessionManager),
                patch(
                    "xtqmt_mcp.trade_gateway.server.build_trade_ops_context",
                    side_effect=lambda cfg, tool_name: {"factory": "default", "tool_name": tool_name},
                ),
            ):
                TradeGatewayServer(config, trade_context_factory=_custom_factory)

        self.assertEqual(captured["tool_name"], "session.warm")
        self.assertEqual(captured["built_context"], {"factory": "custom", "tool_name": "session.warm"})

    def test_trade_ops_needs_distinguish_warm_health_from_public_orders(self) -> None:
        warm_needs = trade_ops_needs_for_tool("session.warm")
        public_orders_needs = trade_ops_needs_for_tool("orders.list")

        self.assertTrue(warm_needs.need_shadow)
        self.assertFalse(warm_needs.need_broker)
        self.assertTrue(public_orders_needs.need_shadow)
        self.assertTrue(public_orders_needs.need_broker)

    def test_initialize_login_resource_and_prompt(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            server._session_manager = _FakeSessionManager()

            init_payload = server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            self.assertEqual(init_payload["result"]["serverInfo"]["name"], "xtqmtTradeGateway")

            login_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "miniqmt.ensure_logged_in", "arguments": {}},
                }
            )
            structured = login_payload["result"]["structuredContent"]
            self.assertTrue(structured["ok"])
            self.assertEqual(structured["data"]["status"], "already_logged_in")

            resource_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "resources/read",
                    "params": {"uri": "trade://capability/current"},
                }
            )
            capability_payload = json.loads(resource_payload["result"]["contents"][0]["text"])
            self.assertEqual(capability_payload["server_name"], "xtqmtTradeGateway")
            self.assertEqual(capability_payload["server_version"], "test")
            self.assertIn("order.place", capability_payload["enabled_tools"])
            self.assertIn("trade://capability/current", capability_payload["enabled_resources"])
            self.assertEqual(capability_payload["order_echo_fields"], ["client_order_key", "intent_id"])
            self.assertEqual(
                capability_payload["write_contract_flags"],
                ["broker_submission_attempted", "local_gate_intercepted"],
            )
            self.assertEqual(capability_payload["execution_mode"], "live")
            self.assertEqual(capability_payload["account_scope"], "service_contract")
            self.assertEqual(capability_payload["resource_authority"], "service_runtime_contract")

            resource_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "resources/read",
                    "params": {"uri": "trade://session/current"},
                }
            )
            parsed = json.loads(resource_payload["result"]["contents"][0]["text"])
            self.assertEqual(parsed["session_id"], 100)
            self.assertEqual(parsed["account_contract"], "single_account_primary")
            self.assertEqual(parsed["account_input_mode"], "service_context_only")
            self.assertEqual(parsed["account_scope"], "primary_session")
            self.assertEqual(parsed["session_resolution"]["resolved_session_id"], 100)
            self.assertEqual(parsed["freshness_status"], "live_runtime_truth")
            self.assertEqual(parsed["resource_authority"], "live_runtime_truth")
            self.assertTrue(parsed["resource_server_ts"])
            health_payload = server.health_payload()
            self.assertEqual(health_payload["evidence_scope"], "non_prod")
            self.assertEqual(health_payload["account_contract"], "single_account_primary")
            self.assertEqual(health_payload["account_input_mode"], "service_context_only")
            self.assertIn("readiness_layers", health_payload)
            self.assertIn("read_only", health_payload["readiness_layers"])
            self.assertIn("write_permission", health_payload["readiness_layers"])
            self.assertIn("order.place", health_payload["readiness_layers"]["write_permission"]["write_tools"])
            self.assertIn("order.cancel", health_payload["readiness_layers"]["write_permission"]["write_tools"])
            self.assertEqual(health_payload["freshness_status"], "live_process_health")
            self.assertIn("process_identity", health_payload)
            self.assertIn("latest_audit_log", health_payload)
            self.assertEqual(health_payload["execution_mode"], "live")
            self.assertFalse(health_payload["write_safety"]["kill_switch_configured"])
            self.assertEqual(health_payload["write_safety"]["release_blockers"], [])

            prompt_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "prompts/get",
                    "params": {"name": "trade-preflight"},
                }
            )
            text = prompt_payload["result"]["messages"][0]["content"]["text"]
            self.assertIn("miniqmt.ensure_logged_in", text)
            self.assertIn("server-side primary account context", text)

    def test_session_current_resource_exposes_base_and_effective_session_resolution(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            server._session_manager = _FakeSessionManagerWithOverride()

            resource_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 41,
                    "method": "resources/read",
                    "params": {"uri": "trade://session/current"},
                }
            )
            parsed = json.loads(resource_payload["result"]["contents"][0]["text"])
            self.assertEqual(parsed["session_id"], 2101)
            self.assertEqual(parsed["session_resolution"]["resolved_session_id"], 2100)
            self.assertEqual(parsed["effective_session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(parsed["effective_session_resolution"]["effective_session_plan"][0], 2101)
            self.assertEqual(parsed["runtime_session_override"]["event_source"], "probe.connection")
            self.assertEqual(parsed["freshness_status"], "live_runtime_truth")
            self.assertEqual(parsed["resource_authority"], "live_runtime_truth")

    def test_primary_account_flow_schemas_hide_explicit_account_inputs(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            server._session_manager = _FakeSessionManager()

            defs = {item["name"]: item for item in server.tool_definitions()}
            self.assertNotIn("account_id", defs["miniqmt.ensure_logged_in"]["inputSchema"]["properties"])
            self.assertNotIn("account_id", defs["session.warm"]["inputSchema"]["properties"])
            self.assertNotIn("account_id", defs["session.status"]["inputSchema"]["properties"])
            self.assertNotIn("account_id", defs["session.close"]["inputSchema"]["properties"])
            self.assertNotIn("account_id", defs["fills.list"]["inputSchema"]["properties"])
            self.assertIn("shadow fallback", defs["orders.list"]["description"])
            self.assertIn("Warm-health-only shadow results are not equivalent", defs["orders.list"]["description"])
            self.assertIn("governed", defs["order.place"]["description"])
            self.assertNotIn("thin broker order", defs["order.place"]["description"])

    def test_primary_account_flow_rejects_explicit_account_selectors(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            server._session_manager = _FakeSessionManager()

            status_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {"name": "session.status", "arguments": {"account_id": "ACC002"}},
                }
            )
            structured = status_payload["result"]["structuredContent"]
            self.assertFalse(structured["ok"])
            self.assertEqual(structured["error"]["category"], "validation")

            fills_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {"name": "fills.list", "arguments": {"account_id": "ACC002"}},
                }
            )
            fills_structured = fills_payload["result"]["structuredContent"]
            self.assertFalse(fills_structured["ok"])
            self.assertEqual(fills_structured["error"]["category"], "validation")

            login_payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 12,
                    "method": "tools/call",
                    "params": {"name": "miniqmt.ensure_logged_in", "arguments": {"account_id": "ACC002"}},
                }
            )
            login_structured = login_payload["result"]["structuredContent"]
            self.assertFalse(login_structured["ok"])
            self.assertEqual(login_structured["error"]["category"], "validation")

    def test_read_trade_resource_blocks_fake_payload_in_prod_scope(self) -> None:
        prod_like_state_root = ROOT / "instance" / "prod" / "state" / "ops001_probe"
        prod_like_artifact_root = ROOT / "instance" / "prod" / "artifacts" / "ops001_probe"
        shutil.rmtree(prod_like_state_root, ignore_errors=True)
        shutil.rmtree(prod_like_artifact_root, ignore_errors=True)
        config = TradeGatewayConfig(
            identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
            runtime_paths=ServiceRuntimePaths(
                config_root=str(ROOT / "instance" / "prod" / "config"),
                logs_root=str(ROOT / "instance" / "prod" / "logs"),
                state_root=str(prod_like_state_root),
                artifact_root=str(prod_like_artifact_root),
            ),
            bundle=XtquantBundleConfig(bundle_root=str(ROOT / "vendor" / "xtquant_250807")),
            qmt=QmtInstallConfig(account_id="ACC001"),
            transport=TransportConfig(bind_port=0),
            audit=TradeAuditConfig(call_log_root=str(prod_like_artifact_root / "trade_gateway")),
            trade_ops=TradeOpsGatewayConfig(
                account_id="ACC001",
                output_dir=str(prod_like_artifact_root / "trade_ops"),
                state_dir=str(prod_like_state_root / "trade_ops"),
            ),
            login=TradeLoginConfig(account_id="ACC001"),
        )
        cache_trade_resource(config, "diag://probe/latest", {"ready": True, "source": "fake"})
        payload = read_trade_resource(config, "diag://probe/latest")["payload"]
        self.assertEqual(payload["reason"], "fake_payload_blocked")
        self.assertEqual(payload["state_scope"], "prod")
        self.assertEqual(payload["resource_authority"], "cached_last_known_state")
        shutil.rmtree(prod_like_state_root, ignore_errors=True)
        shutil.rmtree(prod_like_artifact_root, ignore_errors=True)

    def test_health_payload_reports_prod_kill_switch_release_blocker(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            prod_like_state_root = root / "instance" / "prod" / "state"
            prod_like_artifact_root = root / "instance" / "prod" / "artifacts"
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "instance" / "prod" / "config"),
                    logs_root=str(root / "instance" / "prod" / "logs"),
                    state_root=str(prod_like_state_root),
                    artifact_root=str(prod_like_artifact_root),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(prod_like_artifact_root / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(prod_like_artifact_root / "trade_ops"),
                    state_dir=str(prod_like_state_root / "trade_ops"),
                    kill_switch_file="",
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            payload = server.health_payload()
            self.assertEqual(payload["evidence_scope"], "prod")
            self.assertFalse(payload["write_safety"]["kill_switch_configured"])
            self.assertEqual(payload["write_safety"]["release_blockers"], ["kill_switch_unconfigured"])

    def test_order_place_routes_through_governed_server_write_path(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            service = _RecordingTradeService()
            session_manager = _RecordingSessionManager(service)
            server._session_manager = session_manager

            payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 20,
                    "method": "tools/call",
                    "params": {
                        "name": "order.place",
                        "arguments": {
                            "code": "000001.SZ",
                            "side": "BUY",
                            "qty": 100,
                            "client_order_key": "COID-TG001-TEST",
                            "intent_id": "INT-TG001-TEST",
                        },
                    },
                }
            )

            structured = payload["result"]["structuredContent"]
            self.assertFalse(structured["ok"])
            self.assertEqual(structured["error"]["code"], "connect_gate_failed")
            self.assertEqual(structured["error"]["category"], "connectivity")
            self.assertEqual(session_manager.execute_calls, [{"account_id": "", "require_ready": True}])
            self.assertEqual(len(service.place_order_calls), 1)
            req = service.place_order_calls[0]
            self.assertEqual(req.guard_token, "mcp_server_governed_write_path")
            self.assertEqual(req.client_order_key, "COID-TG001-TEST")
            self.assertEqual(req.intent_id, "INT-TG001-TEST")
            self.assertTrue(structured["data"]["governed_write_path"])
            self.assertEqual(structured["data"]["write_path"], "governed_service_order_place")
            self.assertEqual(structured["data"]["gate_sequence"], list(GOVERNED_ORDER_PLACE_GATE_SEQUENCE))
            self.assertEqual(structured["data"]["session_resolution"]["resolved_session_id"], 2111)
            self.assertFalse(structured["data"]["broker_submission_attempted"])
            self.assertTrue(structured["data"]["local_gate_intercepted"])
            self.assertEqual(structured["data"]["submission_scope"], "local_gate")
            self.assertEqual(structured["data"]["submission_stage"], "connect_gate")

    def test_order_cancel_routes_through_gateway_session_dispatch(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            service = _RecordingTradeService()
            session_manager = _RecordingSessionManager(service)
            server._session_manager = session_manager

            payload = server.dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 62,
                    "method": "tools/call",
                    "params": {"name": "order.cancel", "arguments": {"broker_order_id": "20001"}},
                }
            )

            structured = payload["result"]["structuredContent"]
            self.assertFalse(structured["ok"])
            self.assertEqual(structured["error"]["code"], "connect_gate_failed")
            self.assertEqual(structured["error"]["category"], "connectivity")
            self.assertEqual(session_manager.execute_calls, [{"account_id": "", "require_ready": True}])
            self.assertEqual(service.order_cancel_calls, ["20001"])
            self.assertFalse(structured["data"]["broker_submission_attempted"])
            self.assertTrue(structured["data"]["local_gate_intercepted"])
            self.assertEqual(structured["data"]["submission_scope"], "local_gate")
            self.assertEqual(structured["data"]["submission_stage"], "connect_gate")

    def test_order_resources_are_cached_to_distinct_uris(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )
            server = TradeGatewayServer(config, login_handler=lambda cfg: _FakeLoginResult())
            audit = {"trace_id": "trace-001", "server_ts": "2026-04-13T15:10:00"}
            server._cache_resource_from_tool("orders.list", {"data": {"rows": [{"broker_order_id": "1"}], "count": 1}, "audit": audit})
            server._cache_resource_from_tool("fills.list", {"data": {"rows": [{"trade_id": "T1"}], "row_count": 1}, "audit": audit})
            server._cache_resource_from_tool("order.place", {"data": {"code": "connect_gate_failed"}, "audit": audit})
            server._cache_resource_from_tool("order.cancel", {"data": {"code": "cancel_failed"}, "audit": audit})
            server._cache_resource_from_tool("order.status", {"data": {"broker_order_id": "1", "status": "submitted"}, "audit": audit})

            orders_payload = read_trade_resource(config, "trade://orders/today")["payload"]
            fills_payload = read_trade_resource(config, "trade://fills/today")["payload"]
            place_payload = read_trade_resource(config, "diag://order_place/latest")["payload"]
            cancel_payload = read_trade_resource(config, "diag://order_cancel/latest")["payload"]
            status_payload = read_trade_resource(config, "diag://order_status/latest")["payload"]

            self.assertEqual(orders_payload["rows"], [{"broker_order_id": "1"}])
            self.assertEqual(orders_payload["count"], 1)
            self.assertEqual(fills_payload["rows"], [{"trade_id": "T1"}])
            self.assertEqual(fills_payload["row_count"], 1)
            self.assertEqual(place_payload["code"], "connect_gate_failed")
            self.assertEqual(cancel_payload["code"], "cancel_failed")
            self.assertEqual(status_payload["status"], "submitted")
            self.assertEqual(orders_payload["resource_authority"], "cached_last_known_state")
            self.assertEqual(fills_payload["resource_authority"], "cached_last_known_state")
            self.assertEqual(orders_payload["freshness_status"], "cached_last_known_state")
            self.assertEqual(orders_payload["resource_trace_id"], "trace-001")
            self.assertEqual(orders_payload["resource_server_ts"], "2026-04-13T15:10:00")
            self.assertEqual(fills_payload["freshness_status"], "cached_last_known_state")
            self.assertEqual(fills_payload["resource_trace_id"], "trace-001")
            self.assertEqual(fills_payload["resource_server_ts"], "2026-04-13T15:10:00")

    def test_read_trade_resource_cache_miss_includes_resource_metadata(self) -> None:
        with _workspace_tempdir() as tmp:
            root = Path(tmp)
            config = TradeGatewayConfig(
                identity=ServiceIdentity(server_name="xtqmtTradeGateway", server_version="test"),
                runtime_paths=ServiceRuntimePaths(
                    config_root=str(root / "config"),
                    logs_root=str(root / "logs"),
                    state_root=str(root / "state"),
                    artifact_root=str(root / "artifacts"),
                ),
                bundle=XtquantBundleConfig(bundle_root=str(root / "vendor")),
                qmt=QmtInstallConfig(account_id="ACC001"),
                transport=TransportConfig(bind_port=0),
                audit=TradeAuditConfig(enabled=False, call_log_root=str(root / "artifacts" / "trade_gateway")),
                trade_ops=TradeOpsGatewayConfig(
                    account_id="ACC001",
                    output_dir=str(root / "artifacts" / "trade_ops"),
                    state_dir=str(root / "state" / "trade_ops"),
                ),
                login=TradeLoginConfig(account_id="ACC001"),
            )

            payload = read_trade_resource(config, "diag://order_cancel/latest")["payload"]

            self.assertFalse(payload["available"])
            self.assertEqual(payload["reason"], "resource_not_cached")
            self.assertEqual(payload["freshness_status"], "cached_state_missing")
            self.assertEqual(payload["resource_authority"], "unavailable")
            self.assertIn("resource_trace_id", payload)
            self.assertIn("resource_server_ts", payload)
            self.assertEqual(payload["resource_trace_id"], "")
            self.assertEqual(payload["resource_server_ts"], "")


if __name__ == "__main__":
    unittest.main()
