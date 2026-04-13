from __future__ import annotations

import json
from typing import Any


def jsonrpc_error(jsonrpc: str, request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": jsonrpc, "id": request_id, "error": {"code": int(code), "message": str(message)}}


def initialize_result(
    *,
    jsonrpc: str,
    request_id: Any,
    protocol_version: str,
    server_name: str,
    server_version: str,
    has_tools: bool = True,
    has_resources: bool = True,
    has_prompts: bool = True,
) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    if has_tools:
        capabilities["tools"] = {"listChanged": False}
    if has_resources:
        capabilities["resources"] = {"listChanged": True}
    if has_prompts:
        capabilities["prompts"] = {"listChanged": True}
    return {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "protocolVersion": protocol_version,
            "serverInfo": {"name": server_name, "version": server_version},
            "capabilities": capabilities,
        },
    }


def tool_call_result(jsonrpc: str, request_id: Any, envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(envelope, ensure_ascii=False)}],
            "structuredContent": envelope,
            "isError": not bool(envelope.get("ok", False)),
        },
    }


def resource_read_result(jsonrpc: str, request_id: Any, uri: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False)
    return {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": text,
                }
            ]
        },
    }


def prompt_get_result(jsonrpc: str, request_id: Any, prompt_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": prompt_payload,
    }
