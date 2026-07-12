#!/usr/bin/env python3
"""Serve bounded read-only app graph queries over MCP stdio JSON-RPC."""

from __future__ import annotations

import json
import sys
from typing import Any

from app_graph_engine import GraphError, execute_tool


SERVER_NAME = "app-graph"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"


COMMON_PROPERTIES = {
    "app_root": {"type": "string", "description": "Absolute consuming app root."},
    "expected_digest": {"type": "string", "description": "Optional caller-pinned digest; indexed source digests are always rechecked."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
    "cursor": {"type": "integer", "minimum": 0, "default": 0},
    "max_depth": {"type": "integer", "minimum": 1, "maximum": 32, "default": 32},
}


def _schema(*, refs: bool = False, targets: bool = False, direction: bool = False) -> dict[str, Any]:
    properties = dict(COMMON_PROPERTIES)
    required = ["app_root"]
    if refs:
        properties["refs"] = {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 100}
        required.append("refs")
    if targets:
        properties["target_refs"] = {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 100}
    if direction:
        properties["direction"] = {"enum": ["dependencies", "dependents"], "default": "dependencies"}
    return {"type": "object", "additionalProperties": False, "required": required, "properties": properties}


TOOLS = [
    {"name": "graph_snapshot", "description": "Return index identity, digest, revision, and bounded counts.", "inputSchema": _schema(), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "graph_dependencies", "description": "Return transitive prerequisites or dependents with exact paths.", "inputSchema": _schema(refs=True, direction=True), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "graph_impact", "description": "Return declared impact propagation paths from changed refs.", "inputSchema": _schema(refs=True), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "graph_diagnostics", "description": "Return forbidden cycles, unreachable refs, trace gaps, and declared conflicts.", "inputSchema": _schema(), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "graph_plan", "description": "Return deterministic topological task layers plus cycle, trace, registry, and open-finding blockers.", "inputSchema": _schema(), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "graph_trace", "description": "Return trace paths from source refs to targets or evidence sinks.", "inputSchema": _schema(refs=True, targets=True), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "workflow_state", "description": "Return process-run events and unresolved workflow findings.", "inputSchema": _schema(), "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
]


def _result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > 16 * 1024:
        payload = {"error": {"code": "QUERY_LIMIT", "message": "response exceeds 16 KiB; reduce limit or use cursor"}}
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        is_error = True
    return {"content": [{"type": "text", "text": text}], "structuredContent": payload, "isError": is_error}


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": request.get("params", {}).get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": "Read-only queries over tracked app traceability and process indexes. The server cannot mutate artifacts or declare acceptance.",
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            result = _result({"error": {"code": "SCHEMA_UNSUPPORTED", "message": "invalid tools/call parameters"}}, is_error=True)
        else:
            try:
                result = _result(execute_tool(name, arguments))
            except GraphError as exc:
                result = _result({"error": {"code": exc.code, "message": str(exc), "details": exc.details}}, is_error=True)
            except Exception:
                result = _result({"error": {"code": "INTERNAL_ERROR", "message": "unexpected read-only query failure"}}, is_error=True)
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    """Read newline-delimited JSON-RPC messages until stdin closes."""
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError
            response = _handle(request)
        except (json.JSONDecodeError, ValueError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
