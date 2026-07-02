from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xtqmt_mcp.trade_ops import TradeOpsConfig, TradeOpsService
from xtqmt_mcp.types import ChannelProbeReport, ConnectionStageResult


class _LiveShadow:
    def __init__(self, *, ok: bool = True, reason: str = "", session_id: str = "101", message: str = "") -> None:
        self.ok = ok
        self.reason = reason
        self.session_id = session_id
        self.message = message

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        return {
            "available": True,
            "reused_session": True,
            "ok": self.ok,
            "reason": self.reason,
            "message": self.message,
            "account_id": "ACC001",
            "session_id": self.session_id,
            "source": "xttrader_shadow",
            "positions_rows": 2,
            "asset_rows": 1,
            "snapshot_requires_position": snapshot_requires_position,
        }


class _NoLiveShadow:
    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        return {
            "available": False,
            "reused_session": False,
            "ok": False,
            "reason": "shadow_not_connected",
            "account_id": "ACC001",
            "session_id": "101",
            "source": "xttrader_shadow",
            "snapshot_requires_position": snapshot_requires_position,
        }


class _FreshBrokerAdapter:
    def __init__(self, *, session_id: str = "2111") -> None:
        self._connected = False
        self._active_session_id = session_id

    def query_open_orders(self, account_id: str):
        self._connected = True
        return []

    def close(self) -> None:
        self._connected = False


class _FailingFreshBrokerAdapter:
    def __init__(self, *, session_id: str = "2101", error: str = "xttrader connect failed") -> None:
        self._connected = False
        self._active_session_id = session_id
        self._error = error

    def query_open_orders(self, account_id: str):
        raise RuntimeError(self._error)

    def close(self) -> None:
        self._connected = False


class _BrokerCapableLiveShadow:
    def __init__(self, *, session_id: str = "2101") -> None:
        self.session_id = session_id
        self.place_calls = 0
        self.open_order_calls = 0
        self.query_order_calls = 0
        self.trade_calls = 0
        self.cancel_calls = 0
        self.cfg = type("Cfg", (), {"session_id": int(session_id)})()

    def active_session_id(self) -> int:
        return int(self.session_id)

    def probe_live_readiness(self, *, snapshot_requires_position: bool = False) -> dict[str, object]:
        return {
            "available": True,
            "reused_session": True,
            "ok": True,
            "reason": "",
            "account_id": "ACC001",
            "session_id": self.session_id,
            "source": "xttrader_shadow",
            "positions_rows": 2,
            "asset_rows": 1,
            "snapshot_requires_position": snapshot_requires_position,
        }

    def query_open_orders(self, account_id: str):
        self.open_order_calls += 1
        return []

    def query_order(self, account_id: str, broker_order_id: str):
        self.query_order_calls += 1
        return None

    def query_trades(self, account_id: str, since_ts=None):
        self.trade_calls += 1
        return []

    def place_order(self, intent):
        self.place_calls += 1
        raise AssertionError("probe_connection promotion should not place an order")

    def cancel_order(self, account_id: str, broker_order_id: str):
        self.cancel_calls += 1
        raise AssertionError("probe_connection promotion should not cancel an order")

    def close(self) -> None:
        return None


class TradeProbeReadinessSplitTests(unittest.TestCase):
    def _session_resolution(self) -> dict[str, object]:
        return {
            "configured_session_id": 1111,
            "resolved_base_session_id": 1111,
            "resolved_session_id": 2111,
            "configured_session_candidates": [1111, 1100, 1101, 100, 101, 111],
            "effective_session_plan": [2111, 1111, 1100, 1101, 100, 101, 111, 3111, 2100, 2101],
            "session_plan_version": "v1:2111,1111,1100,1101,100,101,111,3111,2100,2101",
            "derived_session_fallback_enabled": True,
            "max_session_attempts": 12,
            "explicit_session_resolution_applied": True,
        }

    def _build_service(self, root: Path, *, shadow_adapter: object | None = None) -> TradeOpsService:
        userdata = root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(root / "output"),
            state_dir=str(root / "state"),
            qmt_userdata=str(userdata),
        )
        return TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=shadow_adapter if shadow_adapter is not None else object(),
            broker_order_adapter=object(),
            session_resolution=self._session_resolution(),
        )

    def test_probe_connection_unavailable_uses_primary_account_context_wording(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg003_probe_unavailable_wording"
        shutil.rmtree(work_root, ignore_errors=True)
        work_root.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata="",
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=object(),
            broker_order_adapter=object(),
            session_resolution=self._session_resolution(),
        )
        try:
            result = service.probe_connection()
            self.assertFalse(result.ok)
            self.assertEqual(result.payload["error"], "probe_connection_unavailable")
            self.assertEqual(
                result.payload["message"],
                "probe.connection requires server-side qmt_userdata and primary account context",
            )
            self.assertNotIn("explicit account_id", result.payload["message"])
            self.assertEqual(result.payload["session_resolution"]["resolved_session_id"], 2111)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_read_only_ready_with_write_permission_blocked(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_reuse_ready_write_blocked"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root, shadow_adapter=_LiveShadow())
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": False, "report": {"ok": False}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True), patch(
                "xtqmt_mcp.channel_probe.run_channel_probe",
                side_effect=AssertionError("fresh connect probe should not run when owner session is live"),
            ):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "write_permission_precheck_failed")
            self.assertTrue(result.payload["read_only_ready"])
            self.assertFalse(result.payload["write_permission_ready"])
            self.assertFalse(result.payload["write_authority_ready"])
            self.assertFalse(result.payload["write_permission_precheck_ok"])
            self.assertTrue(result.payload["write_permission_blocked"])
            self.assertEqual(result.payload["write_permission_block_reason"], "write_permission_precheck_failed")
            self.assertEqual(result.payload["write_failure_classification"], "write_permission_precheck_failed")
            self.assertEqual(result.payload["probe_mode"], "owner_managed_session_reuse")
            self.assertTrue(result.payload["session_reused"])
            self.assertFalse(result.payload["fresh_connect_attempted"])
            self.assertFalse(result.payload["probe_complete_verdict"])
            self.assertEqual(result.payload["read_only_probe_source"], "active_owner_shadow")
            self.assertEqual(result.payload["write_permission_probe_source"], "userdata_precheck")
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "101")
            self.assertFalse(result.payload["same_plan_verdict"])
            self.assertFalse(result.payload["overall_trade_ready"])
            self.assertEqual(result.payload["session_plan_version"], self._session_resolution()["session_plan_version"])
            self.assertFalse(result.payload["write_session_alignment"]["same_session_as_write_path"])
            self.assertEqual(
                result.payload["write_session_alignment"]["same_plan_reason"],
                "probe_session_differs_from_resolved_write_session",
            )
            self.assertEqual(result.payload["session_resolution"]["effective_session_plan"][0], 2111)
            self.assertNotIn("error", result.payload)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_reuses_live_owner_shadow_for_read_only_ready(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_reuse_read_only_ready"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root, shadow_adapter=_LiveShadow())
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True), patch(
                "xtqmt_mcp.channel_probe.run_channel_probe",
                side_effect=AssertionError("fresh connect probe should not run when owner session is live"),
            ):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertTrue(result.payload["read_only_ready"])
            self.assertTrue(result.payload["write_permission_precheck_ok"])
            self.assertFalse(result.payload["write_permission_ready"])
            self.assertFalse(result.payload["write_authority_ready"])
            self.assertFalse(result.payload["overall_trade_ready"])
            self.assertEqual(result.payload["reason"], "probe_session_differs_from_resolved_write_session")
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "101")
            self.assertFalse(result.payload["same_plan_verdict"])
            self.assertEqual(result.payload["probe_mode"], "owner_managed_session_reuse")
            self.assertTrue(result.payload["session_reused"])
            self.assertFalse(result.payload["fresh_connect_attempted"])
            self.assertEqual(result.payload["read_only_probe"]["source"], "active_owner_shadow")
            self.assertTrue(result.payload["read_only_probe"]["session_reused"])
            self.assertEqual(result.payload["read_only_probe"]["session_id"], "101")
            self.assertEqual(result.payload["write_session_alignment"]["resolved_session_id"], "2111")
            self.assertFalse(result.payload["write_session_alignment"]["same_session_as_write_path"])
            self.assertFalse(result.payload["write_permission_probe"]["implies_write_permission"])
            self.assertTrue(result.payload["session_resolution"]["explicit_session_resolution_applied"])
            self.assertEqual(result.payload["connection_trace"][-1]["name"], "query_shadow_session_smoke")
            self.assertEqual(result.payload["connection_trace"][-1]["details"]["reused_session"], "True")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_owner_shadow_allows_configured_58610_when_socket_ready(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_shadow_configured_58610"
        shutil.rmtree(work_root, ignore_errors=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
            xtdata_port=58610,
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=_LiveShadow(session_id="2111"),
            broker_order_adapter=object(),
            session_resolution=self._session_resolution(),
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True), patch(
                "xtqmt_mcp.channel_probe.run_channel_probe",
                side_effect=AssertionError("fresh connect probe should not run when owner session is live"),
            ):
                result = service.probe_connection()

            self.assertTrue(result.ok)
            self.assertTrue(result.payload["read_only_ready"])
            self.assertTrue(result.payload["precheck"]["xtdata_port_ready"])
            self.assertEqual(result.payload["precheck"]["xtdata_port"], 58610)
            self.assertFalse(result.payload["precheck"].get("legacy_port_detected", False))
            self.assertEqual(result.payload["connection_trace"][2]["code"], "ok")
            self.assertEqual(result.payload["connection_trace"][2]["details"]["port"], "58610")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_read_only_failure_sets_error_code(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_fallback_read_only_failed"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root, shadow_adapter=_NoLiveShadow())
        now = datetime.now()
        report = ChannelProbeReport(
            started_at=now,
            finished_at=now,
            overall_ok=False,
            selected_session_id=100,
            precheck={
                "xtdata_port_ready": False,
                "readiness_layers": {
                    "read_only": {"ok": False, "blocking": True, "reason": "connect_failed"},
                    "write_permission": {"ok": True, "blocking": False, "reason": ""},
                },
                "read_only_failure_classification": "connect_failed",
                "write_failure_classification": "",
            },
            failure_classification="connect_failed",
            connection_trace=[
                ConnectionStageResult(name="connect_session_100", ok=False, code="-1", message="connect failed"),
            ],
        )
        try:
            with patch("xtqmt_mcp.channel_probe.run_channel_probe", return_value=report):
                result = service.probe_connection()
            self.assertFalse(result.ok)
            self.assertEqual(result.payload["reason"], "connect_failed")
            self.assertEqual(result.payload["failure_classification"], "connect_failed")
            self.assertEqual(result.payload["error"], "connect_failed")
            self.assertEqual(result.payload["code"], "connect_failed")
            self.assertFalse(result.payload["read_only_ready"])
            self.assertFalse(result.payload["write_permission_ready"])
            self.assertFalse(result.payload["write_authority_ready"])
            self.assertTrue(result.payload["write_permission_precheck_ok"])
            self.assertFalse(result.payload["same_plan_verdict"])
            self.assertEqual(result.payload["probe_mode"], "fresh_connect_orchestrator")
            self.assertFalse(result.payload["session_reused"])
            self.assertTrue(result.payload["fresh_connect_attempted"])
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "100")
            self.assertEqual(result.payload["session_resolution"]["configured_session_id"], 1111)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_requires_same_session_and_fresh_verify_before_write_ready(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_same_session_write_ready"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root, shadow_adapter=_NoLiveShadow())
        now = datetime.now()
        report = ChannelProbeReport(
            started_at=now,
            finished_at=now,
            overall_ok=True,
            selected_session_id=2111,
            precheck={
                "xtdata_port_ready": True,
                "readiness_layers": {
                    "read_only": {"ok": True, "blocking": True, "reason": ""},
                    "write_permission": {"ok": True, "blocking": False, "reason": ""},
                },
                "read_only_failure_classification": "",
                "write_failure_classification": "",
            },
            failure_classification="",
            connection_trace=[
                ConnectionStageResult(name="connect_session_2111", ok=True, code="0", message="connect ok"),
                ConnectionStageResult(name="subscribe_account", ok=True, code="0", message="subscribe ok"),
                ConnectionStageResult(name="query_snapshot_smoke", ok=True, code="0", message="snapshot ok"),
            ],
        )
        try:
            with patch("xtqmt_mcp.channel_probe.run_channel_probe", return_value=report):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "ok")
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "2111")
            self.assertTrue(result.payload["same_plan_verdict"])
            self.assertTrue(result.payload["probe_complete_verdict"])
            self.assertTrue(result.payload["write_permission_precheck_ok"])
            self.assertTrue(result.payload["write_permission_ready"])
            self.assertTrue(result.payload["write_authority_ready"])
            self.assertTrue(result.payload["overall_trade_ready"])
            self.assertTrue(result.payload["fresh_connect_attempted"])
            self.assertTrue(result.payload["fresh_connect_verified"])
            self.assertEqual(result.payload["session_plan_version"], self._session_resolution()["session_plan_version"])
            self.assertEqual(result.payload["connection_evidence_source"], "fresh_connect")
            self.assertTrue(result.payload["fresh_connect_pass"])
            self.assertTrue(result.payload["subscribe_pass"])
            self.assertTrue(result.payload["write_permission_probe"]["implies_write_permission"])
            self.assertTrue(result.payload["read_only_probe"]["fresh_connect_verified"])
            self.assertEqual(result.payload["read_only_probe"]["connection_evidence_source"], "fresh_connect")
            self.assertTrue(result.payload["write_session_alignment"]["same_session_as_write_path"])
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_owner_managed_broker_verify_can_realign_write_session(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_broker_realign"
        shutil.rmtree(work_root, ignore_errors=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
        )
        session_resolution = self._session_resolution()
        session_resolution["resolved_session_id"] = 2111
        session_resolution["effective_session_plan"] = [2111, 2100, 2101]
        session_resolution["session_plan_version"] = "v1:2111,2100,2101"
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=_LiveShadow(session_id="2111"),
            broker_order_adapter=None,
            broker_order_adapter_factory=lambda require_write_permission: _FreshBrokerAdapter(session_id="2101"),
            session_resolution=session_resolution,
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "ok")
            self.assertEqual(result.payload["session_id"], "2101")
            self.assertEqual(result.payload["observed_probe_session_id"], "2101")
            self.assertTrue(result.payload["same_plan_verdict"])
            self.assertTrue(result.payload["fresh_connect_verified"])
            self.assertTrue(result.payload["write_permission_ready"])
            self.assertEqual(result.payload["session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(result.payload["session_resolution"]["effective_session_plan"][0], 2101)
            self.assertEqual(result.payload["session_plan_version"], "v1:2101,2111,2100")
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_owner_managed_can_fresh_verify_even_when_owner_shadow_differs_from_resolved_write_session(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_shadow_differs_but_fresh_verify_recovers"
        shutil.rmtree(work_root, ignore_errors=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
        )
        session_resolution = self._session_resolution()
        session_resolution["resolved_session_id"] = 2101
        session_resolution["effective_session_plan"] = [2101, 2100, 2111]
        session_resolution["session_plan_version"] = "v1:2101,2100,2111"
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=_LiveShadow(session_id="2100"),
            broker_order_adapter=None,
            broker_order_adapter_factory=lambda require_write_permission: _FreshBrokerAdapter(session_id="2101"),
            session_resolution=session_resolution,
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "ok")
            self.assertEqual(result.payload["probe_mode"], "owner_managed_broker_fresh_verify")
            self.assertEqual(result.payload["session_id"], "2101")
            self.assertEqual(result.payload["observed_probe_session_id"], "2101")
            self.assertTrue(result.payload["same_plan_verdict"])
            self.assertTrue(result.payload["probe_complete_verdict"])
            self.assertTrue(result.payload["fresh_connect_verified"])
            self.assertTrue(result.payload["write_permission_ready"])
            self.assertTrue(result.payload["write_authority_ready"])
            self.assertEqual(result.payload["session_resolution"]["resolved_session_id"], 2101)
            self.assertEqual(result.payload["session_resolution"]["effective_session_plan"][0], 2101)
            trace_names = [item["name"] for item in result.payload["connection_trace"]]
            self.assertIn("connect_session_2101", trace_names)
            self.assertIn("subscribe_account", trace_names)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_owner_managed_fresh_verify_connect_failure_keeps_owner_truth_until_broker_verify_turns_green(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_shadow_differs_but_fresh_verify_connect_fail"
        shutil.rmtree(work_root, ignore_errors=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
        )
        session_resolution = self._session_resolution()
        session_resolution["resolved_session_id"] = 2111
        session_resolution["effective_session_plan"] = [2111, 2100, 2101]
        session_resolution["session_plan_version"] = "v1:2111,2100,2101"
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=_LiveShadow(session_id="2100"),
            broker_order_adapter=None,
            broker_order_adapter_factory=lambda require_write_permission: _FailingFreshBrokerAdapter(session_id="2101"),
            session_resolution=session_resolution,
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "probe_session_differs_from_resolved_write_session")
            self.assertEqual(result.payload["probe_mode"], "owner_managed_broker_fresh_verify_failed")
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "2101")
            self.assertTrue(result.payload["fresh_connect_attempted"])
            self.assertFalse(result.payload["fresh_connect_verified"])
            self.assertFalse(result.payload["write_permission_ready"])
            self.assertFalse(result.payload["write_authority_ready"])
            self.assertTrue(result.payload["write_permission_precheck_ok"])
            self.assertFalse(result.payload["same_plan_verdict"])
            self.assertEqual(
                result.payload["write_permission_block_reason"],
                "probe_session_differs_from_resolved_write_session",
            )
            self.assertEqual(result.payload["write_session_alignment"]["resolved_session_id"], "2111")
            self.assertEqual(result.payload["write_session_alignment"]["observed_probe_session_id"], "2101")
            self.assertFalse(result.payload["write_session_alignment"]["same_session_as_write_path"])
            self.assertTrue(result.payload["session_resolution"]["resolved_session_id"], 2111)
            self.assertEqual(result.payload["session_resolution"]["effective_session_plan"][0], 2111)
            trace_names = [item["name"] for item in result.payload["connection_trace"]]
            self.assertIn("connect_session_2101", trace_names)
            self.assertNotIn("subscribe_account", trace_names)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_same_plan_hard_stop_when_probe_session_only_matches_effective_plan(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_same_plan_hard_stop"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root, shadow_adapter=_NoLiveShadow())
        now = datetime.now()
        report = ChannelProbeReport(
            started_at=now,
            finished_at=now,
            overall_ok=True,
            selected_session_id=1111,
            precheck={
                "xtdata_port_ready": True,
                "readiness_layers": {
                    "read_only": {"ok": True, "blocking": True, "reason": ""},
                    "write_permission": {"ok": True, "blocking": False, "reason": ""},
                },
                "read_only_failure_classification": "",
                "write_failure_classification": "",
            },
            failure_classification="",
            connection_trace=[
                ConnectionStageResult(name="connect_session_1111", ok=True, code="0", message="connect ok"),
                ConnectionStageResult(name="subscribe_account", ok=True, code="0", message="subscribe ok"),
                ConnectionStageResult(name="query_snapshot_smoke", ok=True, code="0", message="snapshot ok"),
            ],
        )
        try:
            with patch("xtqmt_mcp.channel_probe.run_channel_probe", return_value=report):
                result = service.probe_connection()
            self.assertFalse(result.payload["overall_trade_ready"])
            self.assertFalse(result.payload["write_permission_ready"])
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "1111")
            self.assertFalse(result.payload["same_plan_verdict"])
            self.assertEqual(result.payload["reason"], "probe_session_differs_from_resolved_write_session")
            self.assertEqual(
                result.payload["write_permission_block_reason"],
                "probe_session_differs_from_resolved_write_session",
            )
            self.assertFalse(result.payload["fresh_connect_verified"])
            self.assertEqual(result.payload["write_session_alignment"]["resolved_session_id"], "2111")
            self.assertEqual(result.payload["write_session_alignment"]["observed_probe_session_id"], "1111")
            self.assertTrue(result.payload["write_session_alignment"]["observed_probe_session_in_effective_plan"])
            self.assertFalse(result.payload["write_session_alignment"]["same_session_as_write_path"])
            self.assertFalse(result.payload["write_session_alignment"]["same_plan_verdict"])
            self.assertEqual(
                result.payload["write_session_alignment"]["same_plan_reason"],
                "probe_session_differs_from_resolved_write_session",
            )
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_owner_managed_same_session_requires_fresh_verify_for_write_ready(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_same_session_write_ready"
        shutil.rmtree(work_root, ignore_errors=True)
        service = self._build_service(work_root, shadow_adapter=_LiveShadow(session_id="2111"))
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True), patch(
                "xtqmt_mcp.channel_probe.run_channel_probe",
                side_effect=AssertionError("fresh connect probe should not run when owner session is live"),
            ):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "reuse_only_not_sufficient")
            self.assertEqual(result.payload["session_id"], "2111")
            self.assertEqual(result.payload["observed_probe_session_id"], "2111")
            self.assertTrue(result.payload["same_plan_verdict"])
            self.assertTrue(result.payload["probe_complete_verdict"])
            self.assertTrue(result.payload["write_permission_precheck_ok"])
            self.assertFalse(result.payload["write_permission_ready"])
            self.assertFalse(result.payload["write_authority_ready"])
            self.assertFalse(result.payload["overall_trade_ready"])
            self.assertFalse(result.payload["fresh_connect_attempted"])
            self.assertFalse(result.payload["fresh_connect_verified"])
            self.assertEqual(result.payload["session_plan_version"], self._session_resolution()["session_plan_version"])
            self.assertEqual(result.payload["connection_evidence_source"], "reused_owner_session")
            self.assertEqual(result.payload["probe_mode"], "owner_managed_session_reuse")
            self.assertTrue(result.payload["session_reused"])
            self.assertFalse(result.payload["write_permission_probe"]["implies_write_permission"])
            self.assertFalse(result.payload["read_only_probe"]["fresh_connect_verified"])
            self.assertEqual(result.payload["read_only_probe"]["connection_evidence_source"], "reused_owner_session")
            self.assertTrue(result.payload["write_session_alignment"]["same_session_as_write_path"])
            trace_names = [item["name"] for item in result.payload["connection_trace"]]
            self.assertIn("owner_session_connect_verified", trace_names)
            self.assertIn("owner_session_subscribe_verified", trace_names)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_probe_connection_owner_managed_same_session_can_upgrade_to_fresh_broker_verify(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_same_session_fresh_broker_verify"
        shutil.rmtree(work_root, ignore_errors=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
        )
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=_LiveShadow(session_id="2111"),
            broker_order_adapter=None,
            broker_order_adapter_factory=lambda require_write_permission: _FreshBrokerAdapter(session_id="2111"),
            session_resolution=self._session_resolution(),
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "ok")
            self.assertEqual(result.payload["probe_mode"], "owner_managed_broker_fresh_verify")
            self.assertTrue(result.payload["session_reused"])
            self.assertTrue(result.payload["fresh_connect_attempted"])
            self.assertTrue(result.payload["fresh_connect_verified"])
            self.assertTrue(result.payload["write_permission_ready"])
            self.assertTrue(result.payload["write_authority_ready"])
            self.assertTrue(result.payload["overall_trade_ready"])
            self.assertEqual(result.payload["observed_probe_session_id"], "2111")
            self.assertEqual(result.payload["session_id"], "2111")
            trace_names = [item["name"] for item in result.payload["connection_trace"]]
            self.assertIn("owner_session_connect_verified", trace_names)
            self.assertIn("connect_session_2111", trace_names)
            self.assertIn("subscribe_account", trace_names)
            self.assertEqual(result.payload["connection_evidence_source"], "fresh_connect")
            self.assertTrue(result.payload["fresh_connect_pass"])
            self.assertTrue(result.payload["subscribe_pass"])
            self.assertTrue(result.payload["write_session_alignment"]["same_session_as_write_path"])
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)

    def test_owner_managed_probe_connection_does_not_spawn_ephemeral_second_broker_trader(self) -> None:
        work_root = ROOT / "instance" / "test_tmp" / "tg004_probe_owner_shadow_promoted_without_ephemeral_broker"
        shutil.rmtree(work_root, ignore_errors=True)
        userdata = work_root / "userdata"
        userdata.mkdir(parents=True, exist_ok=True)
        cfg = TradeOpsConfig(
            account_id="ACC001",
            trading_day=date(2026, 3, 30),
            output_dir=str(work_root / "output"),
            state_dir=str(work_root / "state"),
            qmt_userdata=str(userdata),
        )
        session_resolution = self._session_resolution()
        session_resolution["resolved_session_id"] = 2100
        session_resolution["configured_session_candidates"] = [2100, 2101, 111]
        session_resolution["effective_session_plan"] = [2100, 2101, 111]
        session_resolution["session_plan_version"] = "v1:2100,2101,111"
        shadow = _BrokerCapableLiveShadow(session_id="2101")
        service = TradeOpsService(
            cfg,
            market_data_provider=object(),
            shadow_adapter=shadow,
            broker_order_adapter=None,
            broker_order_adapter_factory=lambda require_write_permission: (_ for _ in ()).throw(
                AssertionError("ephemeral broker factory should not be called when owner live session is promoted")
            ),
            session_resolution=session_resolution,
        )
        try:
            with patch(
                "xtqmt_mcp.trade_ops.run_layered_user_data_precheck",
                return_value={
                    "read_only": {"ok": True, "report": {"ok": True}},
                    "write_permission": {"ok": True, "report": {"ok": True}},
                },
            ), patch("xtqmt_mcp.trade_ops._tcp_port_ready", return_value=True), patch(
                "xtqmt_mcp.channel_probe.run_channel_probe",
                side_effect=AssertionError("connection orchestrator should not run for promoted owner live session"),
            ):
                result = service.probe_connection()
            self.assertTrue(result.ok)
            self.assertEqual(result.payload["reason"], "ok")
            self.assertEqual(result.payload["probe_mode"], "owner_managed_broker_fresh_verify")
            self.assertEqual(result.payload["session_id"], "2101")
            self.assertEqual(result.payload["observed_probe_session_id"], "2101")
            self.assertTrue(result.payload["same_plan_verdict"])
            self.assertTrue(result.payload["probe_complete_verdict"])
            self.assertTrue(result.payload["fresh_connect_attempted"])
            self.assertTrue(result.payload["fresh_connect_verified"])
            self.assertTrue(result.payload["write_permission_ready"])
            self.assertTrue(result.payload["write_authority_ready"])
            self.assertTrue(result.payload["overall_trade_ready"])
            trace_names = [item["name"] for item in result.payload["connection_trace"]]
            self.assertIn("owner_session_connect_verified", trace_names)
            self.assertIn("owner_session_subscribe_verified", trace_names)
            self.assertIn("connect_session_2101", trace_names)
            self.assertIn("subscribe_account", trace_names)
            self.assertIs(service._ensure_broker_adapter(require_write_permission=True), shadow)
            self.assertIs(service._ensure_broker_adapter(require_write_permission=False), shadow)
            self.assertEqual(shadow.open_order_calls, 0)
        finally:
            service.close()
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
