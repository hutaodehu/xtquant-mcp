from __future__ import annotations

from http.client import HTTPConnection
import json
from threading import Thread
import unittest

from xtqmt_mcp.http_transport import build_http_server


class _DummyGateway:
    bind_host = "127.0.0.1"
    bind_port = 0
    mcp_path = "/mcp"
    health_path = "/healthz"
    protocol_version_http = "2025-03-26"
    allowed_origin_hosts = ("127.0.0.1", "localhost")

    def health_payload(self) -> dict[str, object]:
        return {"ok": True, "server_name": "dummy"}

    def dispatch(self, request: dict[str, object], *, session_id: str = "") -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {"session_id": session_id, "method": request.get("method")},
        }


class HttpTransportTests(unittest.TestCase):
    def test_health_and_jsonrpc_roundtrip(self) -> None:
        gateway = _DummyGateway()
        server = build_http_server(gateway)
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            conn = HTTPConnection(host, port, timeout=5)
            conn.request("GET", "/healthz")
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            health = json.loads(response.read().decode("utf-8"))
            self.assertTrue(health["ok"])
            conn.close()

            conn = HTTPConnection(host, port, timeout=5)
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode("utf-8")
            conn.request(
                "POST",
                "/mcp",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["result"]["method"], "ping")
            self.assertTrue(response.getheader("Mcp-Session-Id"))
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
