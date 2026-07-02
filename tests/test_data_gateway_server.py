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
    def gateway_health(self, arguments: dict | None = None) -> DataToolResult:
        del arguments
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
            "configured_endpoint": {"host": "127.0.0.1", "port": 0, "source": "unconfigured", "port_ready": None},
            "resolved_runtime_endpoint": {"host": "127.0.0.1", "port": 58888, "source": "connectivity_probe", "port_ready": True, "matches_configured": False},
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
                    "resolved_runtime_endpoint": {"host": "127.0.0.1", "port": 58888, "source": "connectivity_probe", "port_ready": True, "matches_configured": False},
                }
            ],
        }

    def instruments_search(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": []})

    def calendar_resolve_trade_day(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "target_trading_day": "20260327"})

    def sector_list(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": [{"sector_name": "GN上海"}]})

    def sector_members_at(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": [{"sector_name": "GN上海", "stock_code": "000001.SZ"}]})

    def sector_change_history(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": [{"sector_name": "GN上海", "stock_code": "000001.SZ", "action": "add", "effective_date": "20260326"}]})

    def snapshot_batch(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": []})

    def history_get_bars(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": {}})

    def history_get_ticks(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "items": {}})

    def integrity_plan(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "route_decision": {"route": "bulk_sync"}})

    def bulk_sync_job_submit(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "job_id": "job-1", "state": "running"})

    def bulk_sync_job_status(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "job_id": "job-1", "state": "completed"})

    def bulk_sync_job_cancel(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "job_id": "job-1", "state": "cancel_requested"})

    def artifact_manifest(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "job_id": "job-1", "changed_files": ["calendars/day.txt"]})

    def qlib_health_check(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "passed": True})

    def qlib_acceptance_check(self, arguments: dict) -> DataToolResult:
        return DataToolResult(ok=True, payload={"echo": arguments, "verdict": "pass"})

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

    def test_tools_list_contains_modern_only_surface(self) -> None:
        response = self.server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = response["result"]["tools"]
        tool_names = {item["name"] for item in tools}
        self.assertEqual(
            tool_names,
            {
                "gateway.health",
                "calendar.resolve_trade_day",
                "integrity.plan",
                "sector.list",
                "sector.members_at",
                "sector.change_history",
                "market.snapshot.batch",
                "market.history.get_bars",
                "bulk.sync_job.submit",
                "bulk.sync_job.status",
                "bulk.sync_job.cancel",
                "artifact.manifest",
                "qlib.health.check",
                "qlib.acceptance.check",
            },
        )
        self.assertNotIn("xtdata.status", tool_names)
        self.assertNotIn("xtdata.download.submit", tool_names)

    def test_sector_members_at_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "sector.members_at", "arguments": {"sector_name": "GN上海", "asof_date": "20260327"}},
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tool"], "sector.members_at")
        self.assertEqual(payload["data"]["echo"], {"sector_name": "GN上海", "asof_date": "20260327"})

    def test_sector_change_history_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "sector.change_history", "arguments": {"sector_name": "GN上海", "start_date": "20260326", "end_date": "20260327"}},
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tool"], "sector.change_history")
        self.assertEqual(payload["data"]["echo"]["sector_name"], "GN上海")

    def test_bulk_sync_job_cancel_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "bulk.sync_job.cancel", "arguments": {"job_id": "job-1"}},
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tool"], "bulk.sync_job.cancel")
        self.assertEqual(payload["data"]["state"], "cancel_requested")

    def test_resources_list_contains_active_leases(self) -> None:
        response = self.server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
        resources = response["result"]["resources"]
        resource_uris = {item["uri"] for item in resources}
        self.assertIn("xtdata://leases/active", resource_uris)
        leases_resource = next(item for item in resources if item["uri"] == "xtdata://leases/active")
        self.assertIn("Not proof of durable reconnect", leases_resource["description"])

    def test_gateway_health_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "gateway.health", "arguments": {}},
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["source"], "fake")
        cache_path = self._runtime_root / "state" / "data_resources" / "xtdata_service_status.json"
        self.assertTrue(cache_path.exists())
        self.assertTrue(str(cache_path).startswith(str(self._runtime_root)))

    def test_market_snapshot_batch_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "market.snapshot.batch", "arguments": {"codes": ["000001.SZ"]}},
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tool"], "market.snapshot.batch")
        self.assertEqual(payload["data"]["echo"], {"codes": ["000001.SZ"]})

    def test_market_history_get_bars_tool_call(self) -> None:
        response = self.server.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "market.history.get_bars",
                    "arguments": {"codes": ["000001.SZ"], "period": "1d", "start_time": "20260327", "end_time": "20260331"},
                },
            }
        )
        payload = response["result"]["structuredContent"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["tool"], "market.history.get_bars")
        self.assertEqual(payload["data"]["echo"]["codes"], ["000001.SZ"])

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
