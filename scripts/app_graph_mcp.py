#!/usr/bin/env python3
"""Lifecycle-correct stdio MCP surface for graph reads or fixed maintainer writes."""

from __future__ import annotations

import json
import sys
from typing import Any

from app_graph_engine import GraphError, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, execute_tool

SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18")
SERVER_VERSION = "0.3.0"
CURSOR = {"type": "string", "description": "Opaque snapshot-bound continuation token."}
BASE = {"type": "object", "properties": {"app_root": {"type": "string"}, "expected_build_ref": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}, "max_depth": {"type": "integer", "minimum": 1, "maximum": 32, "default": 8}, "cursor": CURSOR}, "required": ["app_root"], "additionalProperties": True}


def _tools(maintainer: bool) -> list[dict[str, Any]]:
    if maintainer:
        return [
            {"name": "graph_compile", "description": "Compile structured sources and immutable journal into deterministic indexes using CAS.", "inputSchema": BASE},
            {"name": "process_record_event", "description": "Idempotently append one immutable process event in an opted-in repository.", "inputSchema": {"type": "object", "properties": {"app_root": {"type": "string"}, "event": {"type": "object"}}, "required": ["app_root", "event"], "additionalProperties": False}},
        ]
    names = {
        "dependency_slice": "Return bounded graph prerequisites or dependents.", "impact_analysis": "Return bounded reverse dependency impact.", "graph_trace": "Return typed trace edges.", "graph_diagnostics": "Return compiler findings.", "topological_plan": "Return dependency-ordered task refs.", "workflow_state": "Return immutable process events.", "process_audit": "Audit causal DAG, ownership, lifecycle, and terminal candidates.", "trace_audit": "Audit semantic, planning, or convergence trace completeness."
    }
    return [{"name": name, "description": description, "inputSchema": BASE, "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}} for name, description in names.items()]


def _rpc_error(identifier: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    value = {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}
    if data is not None: value["error"]["data"] = data
    return value


def _tool_result(payload: dict[str, Any], *, error: bool = False) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(raw.encode()) > MAX_RESPONSE_BYTES:
        payload = {"error": {"code": "RESPONSE_LIMIT", "message": "response exceeds 16 KiB; reduce page size"}}; error = True
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {"content": [{"type": "text", "text": raw}], "structuredContent": payload, "isError": error}


def main() -> int:
    maintainer = "--maintainer" in sys.argv[1:]
    initialized = False
    negotiated = False
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_REQUEST_BYTES:
            print(json.dumps(_rpc_error(None, -32600, "request exceeds 64 KiB")), flush=True); continue
        try:
            request = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError):
            print(json.dumps(_rpc_error(None, -32700, "parse error")), flush=True); continue
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            if isinstance(request, dict) and "id" not in request: continue
            print(json.dumps(_rpc_error(request.get("id") if isinstance(request, dict) else None, -32600, "invalid request")), flush=True); continue
        method, identifier = request["method"], request.get("id")
        notification = "id" not in request
        if method == "initialize":
            if notification:
                continue
            if negotiated or initialized:
                print(json.dumps(_rpc_error(identifier, -32600, "server is already initialized")), flush=True); continue
            params = request.get("params", {})
            if not isinstance(params, dict):
                print(json.dumps(_rpc_error(identifier, -32602, "initialize params must be an object")), flush=True); continue
            version = params.get("protocolVersion")
            selected_version = version if version in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            negotiated = True
            response = {"jsonrpc": "2.0", "id": identifier, "result": {"protocolVersion": selected_version, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "app-graph-maintainer" if maintainer else "app-graph", "version": SERVER_VERSION}}}
            print(json.dumps(response, separators=(",", ":")), flush=True); continue
        if method == "notifications/initialized":
            if negotiated: initialized = True
            continue
        if method.startswith("notifications/"):
            continue
        if notification:
            continue
        if not initialized:
            print(json.dumps(_rpc_error(identifier, -32002, "server is not initialized")), flush=True); continue
        if method == "ping": result: Any = {}
        elif method == "tools/list": result = {"tools": _tools(maintainer)}
        elif method == "tools/call":
            params = request.get("params", {})
            try:
                payload = execute_tool(params.get("name"), params.get("arguments", {}), maintainer=maintainer)
                result = _tool_result(payload)
            except GraphError as exc:
                result = _tool_result({"error": {"code": exc.code, "message": str(exc), "details": exc.details}}, error=True)
            except Exception:
                result = _tool_result({"error": {"code": "INTERNAL_ERROR", "message": "bounded internal error"}}, error=True)
        else:
            if notification: continue
            print(json.dumps(_rpc_error(identifier, -32601, "method not found")), flush=True); continue
        print(json.dumps({"jsonrpc": "2.0", "id": identifier, "result": result}, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
