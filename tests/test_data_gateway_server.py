from __future__ import annotations

import shutil
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.data_gateway.config import DataAuditConfig, DataGatewayConfig, DataGatewayRuntimeConfig
from xtqmt_mcp.data_gateway.resources import cache_data_resource, read_data_resource
from xtqmt_mcp.data_gateway.server import DataGatewayServer
from xtqmt_mcp.data_gateway.service import DataToolResult
from xtqmt_mcp.settings import QmtInstallConfig, ServiceIdentity, ServiceRuntimePaths, TransportConfig, XtquantBundleConfig


class _FakeService:
    def status_summary(self) -> DataToolResult:
        return DataToolResult(ok=True, payload={"ready": True, "source": "fake"})

    def list_subscriptions_payload(self, arguments: dict | None = None) -> dict[str, object]:
        return {
            "experimental": True,
            "capability": {
                "name": "xtdata.subscribe",
                "model": "subscription_lease",
                "stability": "experimental",
                "proven_live_reconnect": False,
                "reconnect_strategy": "explicit_rebuild_required",
            },
            "configured_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "configured", "port_ready": None},
            "resolved_runtime_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "connectivity_probe", "port_ready": True, "matches_configured": True},
            "count": 1,
            "active_count": 1,
            "stale_count": 0,
            "stopped_count": 0,
            "running_count": 1,
            "needs_rebuild_count": 0,
            "rebuild_reasons": {"ok": 1},
            "recovery_summary": {
                "active": 1,
                "stale": 0,
                "stopped": 0,
                "needs_rebuild": 0,
                "rebuild_reasons": {"ok": 1},
                "reconnect_strategy": "explicit_rebuild_required",
                "proven_live_reconnect": False,
            },
            "items": [
                {
                    "subscription_id": "sub-1",
                    "status": "running",
                    "lease_state": "active",
                    "needs_rebuild": False,
                    "rebuild_reason": "ok",
                    "recovery_action": "hold_lease",
                    "recovery": {
                        "lease_state": "active",
                        "needs_rebuild": False,
                        "rebuild_reason": "ok",
                        "recovery_action": "hold_lease",
                        "proven_live_reconnect": False,
                    },
                    "resolved_runtime_endpoint": {"host": "127.0.0.1", "port": 58610, "source": "connectivity_probe", "port_ready": True, "matches_configured": True},
                }
            ],
        }

    def instruments_search(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": []})

    def calendar_query(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "trading_days": ["2026-03-27"]})

    def snapshot_batch(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": []})

    def history_get_bars(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": {}})

    def history_get_ticks(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": {}})

    def download_submit(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "job_id": "job-1"})

    def download_status(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "active": []})

    def download_cancel(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "status": "cancelled"})

    def subscribe_start(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "subscription_id": "sub-1"})

    def subscribe_stop(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "status": "stopped"})


class DataGatewayServerTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = ROOT / "instance" / "test_runtime" / "data_gateway_server"
        shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self._runtime_root = runtime_root
        cfg = DataGatewayConfig(
            identity=ServiceIdentity(server_name="xtqmtDataGateway", server_version="test"),
            runtime_paths=ServiceRuntimePaths(
                config_root=str(runtime_root / "config"),
                logs_root=str(runtime_root / "logs"),
                state_root=str(runtime_root / "state"),
                artifact_root=str(runtime_root / "artifacts"),
            ),
            bundle=XtquantBundleConfig(bundle_root=str(runtime_root / "vendor")),
            qmt=QmtInstallConfig(),
            transport=TransportConfig(bind_port=0),
            audit=DataAuditConfig(call_log_root=str(runtime_root / "artifacts" / "data_gateway")),
            service=DataGatewayRuntimeConfig(
                jobs_root=str(runtime_root / "state" / "data_jobs"),
                subscriptions_root=str(runtime_root / "state" / "subscriptions"),
                download_root=str(runtime_root / "artifacts" / "data_downloads"),
                max_concurrent_jobs=1,
                max_query_symbols=10,
            ),
        )
        self.server = DataGatewayServer(
            cfg,
            service=_FakeService(),
            uuid_factory=lambda: "trace-1",
            time_fn=lambda: 1.0,
            now_fn=lambda: __import__("datetime").datetime(2026, 3, 27, 9, 30, 0),
        )

    def tearDown(self) -> None:
        shutil.rmtree(getattr(self, "_runtime_root", ROOT / "instance" / "test_runtime" / "data_gateway_server"), ignore_errors=True)

    def test_initialize(self) -> None:
        response = self.server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(response["result"]["serverInfo"]["name"], "xtqmtDataGateway")

    def test_tools_list_contains_status(self) -> None:
        response = self.server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = response["result"]["tools"]
        tool_names = {item["name"] for item in tools}
        self.assertIn("xtdata.status", tool_names)
        self.assertIn("xtdata.download.submit", tool_names)
        subscribe_start = next(item for item in tools if item["name"] == "xtdata.subscribe.start")
        self.assertIn("experimental", subscribe_start["description"])
        self.assertIn("not proven", subscribe_start["description"])

    def test_resources_list_contains_active_leases(self) -> None:
        response = self.server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
        resources = response["result"]["resources"]
        resource_uris = {item["uri"] for item in resources}
        self.assertIn("xtdata://leases/active", resource_uris)
        leases_resource = next(item for item in resources if item["uri"] == "xtdata://leases/active")
        self.assertIn("Not proof of durable reconnect", leases_resource["description"])

    def test_status_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "xtdata.status", "arguments": {}},
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["source"], "fake")
        cache_path = self._runtime_root / "state" / "data_resources" / "xtdata_service_status.json"
        self.assertTrue(cache_path.exists())
        self.assertTrue(str(cache_path).startswith(str(self._runtime_root)))

    def test_active_leases_resource_read(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/read",
                "params": {"uri": "xtdata://leases/active"},
            }
        )
        contents = response["result"]["contents"]
        self.assertEqual(len(contents), 1)
        self.assertIn("experimental", contents[0]["text"])
        self.assertIn("subscription_lease", contents[0]["text"])
        self.assertIn("explicit_rebuild_required", contents[0]["text"])
        self.assertIn("live_runtime_truth", contents[0]["text"])
        self.assertIn("resource_server_ts", contents[0]["text"])

    def test_prompt_get_recovery_mentions_explicit_rebuild(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "xtdata-service-recover"},
            }
        )
        messages = response["result"]["messages"]
        self.assertEqual(len(messages), 1)
        text = messages[0]["content"]["text"]
        self.assertIn("explicit rebuild", text)
        self.assertIn("durable reconnect", text)

    def test_health_payload_exposes_non_prod_evidence_scope(self) -> None:
        payload = self.server.health_payload()
        self.assertEqual(payload["evidence_scope"], "non_prod")
        self.assertEqual(payload["evidence_state_root"], str(self._runtime_root / "state"))
        self.assertEqual(payload["freshness_status"], "live_process_health")
        self.assertIn("process_identity", payload)
        self.assertIn("latest_audit_log", payload)

    def test_read_data_resource_blocks_fake_payload_in_prod_scope(self) -> None:
        prod_like_root = ROOT / "instance" / "prod" / "state" / "ops001_probe"
        prod_like_state_root = prod_like_root
        prod_like_artifact_root = ROOT / "instance" / "prod" / "artifacts" / "ops001_probe"
        shutil.rmtree(prod_like_state_root, ignore_errors=True)
        shutil.rmtree(prod_like_artifact_root, ignore_errors=True)
        cfg = DataGatewayConfig(
            identity=ServiceIdentity(server_name="xtqmtDataGateway", server_version="test"),
            runtime_paths=ServiceRuntimePaths(
                config_root=str(ROOT / "instance" / "prod" / "config"),
                logs_root=str(ROOT / "instance" / "prod" / "logs"),
                state_root=str(prod_like_state_root),
                artifact_root=str(prod_like_artifact_root),
            ),
            bundle=XtquantBundleConfig(bundle_root=str(ROOT / "vendor" / "xtquant_250807")),
            qmt=QmtInstallConfig(),
            transport=TransportConfig(bind_port=0),
            audit=DataAuditConfig(call_log_root=str(prod_like_artifact_root / "data_gateway")),
            service=DataGatewayRuntimeConfig(
                jobs_root=str(prod_like_state_root / "data_jobs"),
                subscriptions_root=str(prod_like_state_root / "subscriptions"),
                download_root=str(prod_like_artifact_root / "data_downloads"),
                max_concurrent_jobs=1,
                max_query_symbols=10,
            ),
        )
        cache_data_resource(cfg, "xtdata://catalog/instruments", {"ready": True, "source": "fake"})
        payload = read_data_resource(cfg, "xtdata://catalog/instruments")["payload"]
        self.assertEqual(payload["reason"], "fake_payload_blocked")
        self.assertEqual(payload["state_scope"], "prod")
        self.assertEqual(payload["resource_authority"], "cached_last_known_state")
        shutil.rmtree(prod_like_state_root, ignore_errors=True)
        shutil.rmtree(prod_like_artifact_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
