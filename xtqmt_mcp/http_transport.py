from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from typing import Any
from urllib.parse import urlparse
import uuid


_LOG = logging.getLogger("xtqmt_mcp.http")


class GatewayHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], gateway: Any) -> None:
        super().__init__(server_address, GatewayHttpHandler)
        self.gateway = gateway


class GatewayHttpHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "xtqmt_mcp.http"

    @property
    def gateway_server(self) -> GatewayHttpServer:
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:
        path = self._request_path()
        if path == self.gateway_server.gateway.health_path:
            self._send_json(HTTPStatus.OK, self.gateway_server.gateway.health_payload())
            return
        if path == self.gateway_server.gateway.mcp_path:
            self._send_status(HTTPStatus.METHOD_NOT_ALLOWED, headers={"Allow": "POST"})
            return
        self._send_status(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        gateway = self.gateway_server.gateway
        if not self._origin_allowed(gateway.allowed_origin_hosts):
            return
        if self._request_path() != gateway.mcp_path:
            self._send_status(HTTPStatus.NOT_FOUND)
            return
        if self._request_content_type() != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"ok": False, "error": "content_type_must_be_application_json"})
            return
        raw = self._read_body_bytes()
        if raw is None:
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid_json:{exc}"})
            return
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "json_rpc_request_must_be_object"})
            return

        session_id = str(self.headers.get("Mcp-Session-Id", "") or "").strip() or str(uuid.uuid4())
        response = gateway.dispatch(payload, session_id=session_id)
        headers = {
            "MCP-Protocol-Version": gateway.protocol_version_http,
            "Mcp-Session-Id": session_id,
        }
        if response is None:
            self._send_status(HTTPStatus.ACCEPTED, headers=headers)
            return
        self._send_json(HTTPStatus.OK, response, headers=headers)

    def do_DELETE(self) -> None:
        if self._request_path() == self.gateway_server.gateway.mcp_path:
            self._send_status(HTTPStatus.METHOD_NOT_ALLOWED, headers={"Allow": "POST"})
            return
        self._send_status(HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        path = self._request_path()
        gateway = self.gateway_server.gateway
        if path == gateway.mcp_path:
            self._send_status(HTTPStatus.NO_CONTENT, headers={"Allow": "POST"})
            return
        if path == gateway.health_path:
            self._send_status(HTTPStatus.NO_CONTENT, headers={"Allow": "GET"})
            return
        self._send_status(HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: object) -> None:
        _LOG.info("%s - %s", self.address_string(), fmt % args)

    def _request_path(self) -> str:
        return urlparse(self.path).path or "/"

    def _request_content_type(self) -> str:
        header = str(self.headers.get("Content-Type", "") or "")
        return header.split(";", 1)[0].strip().lower()

    def _read_body_bytes(self) -> bytes | None:
        try:
            length = int(str(self.headers.get("Content-Length", "0") or "0"))
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_content_length"})
            return None
        if length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "content_length_required"})
            return None
        body = self.rfile.read(length)
        if not body:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty_request_body"})
            return None
        return body

    def _origin_allowed(self, allowed_hosts: tuple[str, ...]) -> bool:
        origin = str(self.headers.get("Origin", "") or "").strip()
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
        except Exception:
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin_invalid"})
            return False
        host = str(parsed.hostname or "").strip().lower()
        if host not in set(allowed_hosts):
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": f"origin_forbidden:{host}"})
            return False
        return True

    def _send_status(self, status: HTTPStatus, headers: dict[str, str] | None = None) -> None:
        self.send_response(int(status))
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(str(key), str(value))
        self.end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(str(key), str(value))
        self.end_headers()
        self.wfile.write(body)


def build_http_server(gateway: Any) -> GatewayHttpServer:
    return GatewayHttpServer((gateway.bind_host, int(gateway.bind_port)), gateway)


def serve_streamable_http(gateway: Any) -> int:
    httpd = build_http_server(gateway)
    _LOG.info("gateway listening on http://%s:%s%s", gateway.bind_host, gateway.bind_port, gateway.mcp_path)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:  # pragma: no cover - manual server path
        _LOG.info("gateway stopped by keyboard interrupt")
    finally:
        httpd.server_close()
    return 0
