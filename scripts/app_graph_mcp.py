#!/usr/bin/env python3
"""Strict lifecycle-correct stdio MCP surface for the app graph runtime."""
from __future__ import annotations

import json
import sys
from typing import Any

from app_graph_engine import GraphError, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, execute_tool

SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18")
SERVER_VERSION = "0.3.5"

STR = {"type": "string", "minLength": 1}
CURSOR = {"type": "string", "description": "Opaque snapshot/query-bound continuation token."}
BOUNDS = {
    "app_root": STR,
    "expected_build_ref": STR,
    "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
    "max_depth": {"type": "integer", "minimum": 1, "maximum": 32, "default": 8},
    "cursor": CURSOR,
}
EVENT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["schema", "run_ref", "event_ref", "event_kind", "stage", "status", "actor", "causal_refs", "trace_refs", "artifact_refs", "origin", "automation_status"],
    "properties": {
        "schema": {"const": "app-process-event.v1"},
        **{name: STR for name in ("run_ref", "event_ref", "event_kind", "stage", "status", "actor")},
        **{name: {"type": "array", "items": STR, "uniqueItems": True} for name in ("causal_refs", "trace_refs", "artifact_refs")},
        "origin": {"enum": ["native", "legacy-import"]},
        "automation_status": {"enum": ["unavailable", "not_run", "passed", "failed"]},
        "build_ref": STR, "source_snapshot_digest": STR, "journal_digest": STR,
        "process_audit_refs": {"type": "array", "items": STR, "uniqueItems": True},
        "trace_audit_refs": {"type": "array", "items": STR, "uniqueItems": True},
    },
}


def _object(properties: dict[str, Any], required: tuple[str, ...] = ("app_root",)) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


SCHEMAS = {
    "graph_compile": _object({"app_root": STR, "expected_build_ref": STR}),
    "process_record_event": _object({"app_root": STR, "event": EVENT_SCHEMA}, ("app_root", "event")),
    "dependency_slice": _object({**BOUNDS, "refs": {"type": "array", "items": STR, "uniqueItems": True}, "direction": {"enum": ["dependencies", "dependents"]}}, ("app_root", "refs")),
    "impact_analysis": _object({**BOUNDS, "refs": {"type": "array", "items": STR, "uniqueItems": True}}, ("app_root", "refs")),
    "graph_trace": _object({**BOUNDS, "refs": {"type": "array", "items": STR, "uniqueItems": True}}),
    "graph_diagnostics": _object(BOUNDS),
    "topological_plan": _object(BOUNDS),
    "workflow_state": _object({**BOUNDS, "run_ref": STR}),
    "process_audit": _object({**BOUNDS, "run_ref": STR, "terminal": {"type": "boolean"}}, ("app_root", "run_ref")),
    "trace_audit": _object({**BOUNDS, "profile": {"enum": ["semantic", "planning", "convergence"]}}, ("app_root", "profile")),
}
READ_DESCRIPTIONS = {
    "dependency_slice": "Return bounded graph prerequisites or dependents.",
    "impact_analysis": "Return bounded reverse dependency impact.",
    "graph_trace": "Return typed trace edges.",
    "graph_diagnostics": "Return compiler findings.",
    "topological_plan": "Return dependency-ordered task refs.",
    "workflow_state": "Return immutable process events.",
    "process_audit": "Audit one exact run's causal DAG, ownership, lifecycle, and terminal candidate.",
    "trace_audit": "Audit semantic, planning, or convergence trace completeness.",
}


def _tools(maintainer: bool) -> list[dict[str, Any]]:
    names = ("graph_compile", "process_record_event") if maintainer else tuple(READ_DESCRIPTIONS)
    descriptions = {
        "graph_compile": "Compile structured sources and immutable journal into deterministic indexes using CAS.",
        "process_record_event": "Idempotently append one immutable process event in an opted-in repository.",
        **READ_DESCRIPTIONS,
    }
    return [{"name": name, "description": descriptions[name], "inputSchema": SCHEMAS[name], **({} if maintainer else {"annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}})} for name in names]


def _validate(schema: dict[str, Any], value: Any, path: str = "arguments") -> None:
    if "const" in schema and value != schema["const"]: raise ValueError(f"{path} must equal {schema['const']}")
    if "enum" in schema and value not in schema["enum"]: raise ValueError(f"{path} has an unsupported value")
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict): raise ValueError(f"{path} must be an object")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(props): raise ValueError(f"{path} contains unknown fields")
        missing = set(schema.get("required", [])) - set(value)
        if missing: raise ValueError(f"{path} is missing {sorted(missing)[0]}")
        for key, item in value.items():
            if key in props: _validate(props[key], item, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list): raise ValueError(f"{path} must be an array")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value): raise ValueError(f"{path} must contain unique items")
        for index, item in enumerate(value): _validate(schema["items"], item, f"{path}[{index}]")
    elif kind == "string":
        if not isinstance(value, str) or len(value) < schema.get("minLength", 0): raise ValueError(f"{path} must be a non-empty string")
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int) or value < schema.get("minimum", value) or value > schema.get("maximum", value): raise ValueError(f"{path} is outside its integer bounds")
    elif kind == "boolean" and not isinstance(value, bool): raise ValueError(f"{path} must be a boolean")


def _rpc_error(identifier: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    result = {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}
    if data is not None: result["error"]["data"] = data
    return result


def _tool_result(payload: dict[str, Any], *, error: bool = False) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result = {"content": [{"type": "text", "text": raw}], "structuredContent": payload, "isError": error}
    if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) > MAX_RESPONSE_BYTES - 512:
        payload = {"error": {"code": "RESPONSE_LIMIT", "message": "response exceeds 16 KiB; reduce the page size"}}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        result = {"content": [{"type": "text", "text": raw}], "structuredContent": payload, "isError": True}
    return result


def _emit(response: dict[str, Any]) -> None:
    raw = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode()
    if len(raw) > MAX_RESPONSE_BYTES:
        raw = json.dumps(_rpc_error(response.get("id"), -32603, "bounded response limit exceeded"), separators=(",", ":")).encode()
    sys.stdout.buffer.write(raw + b"\n"); sys.stdout.buffer.flush()


def main() -> int:
    maintainer = "--maintainer" in sys.argv[1:]
    negotiated = initialized = False
    allowed = {"graph_compile", "process_record_event"} if maintainer else set(READ_DESCRIPTIONS)
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_REQUEST_BYTES:
            _emit(_rpc_error(None, -32600, "request exceeds 64 KiB")); continue
        try: request = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError):
            _emit(_rpc_error(None, -32700, "parse error")); continue
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            if isinstance(request, dict) and "id" not in request: continue
            _emit(_rpc_error(request.get("id") if isinstance(request, dict) else None, -32600, "invalid request")); continue
        method, identifier, notification = request["method"], request.get("id"), "id" not in request
        if method == "initialize":
            if notification: continue
            params = request.get("params", {})
            if negotiated or initialized: _emit(_rpc_error(identifier, -32600, "server is already initialized")); continue
            if not isinstance(params, dict) or not isinstance(params.get("protocolVersion"), str): _emit(_rpc_error(identifier, -32602, "initialize requires protocolVersion")); continue
            if params["protocolVersion"] not in SUPPORTED_PROTOCOLS: _emit(_rpc_error(identifier, -32602, "unsupported protocol version", {"supported": list(SUPPORTED_PROTOCOLS)})); continue
            negotiated = True
            _emit({"jsonrpc": "2.0", "id": identifier, "result": {"protocolVersion": params["protocolVersion"], "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "app-graph-maintainer" if maintainer else "app-graph", "version": SERVER_VERSION}}}); continue
        if method == "notifications/initialized":
            if negotiated: initialized = True
            continue
        if method.startswith("notifications/") or notification: continue
        if not initialized: _emit(_rpc_error(identifier, -32002, "server is not initialized")); continue
        if method == "ping": result: Any = {}
        elif method == "tools/list":
            if request.get("params", {}) not in ({}, None): _emit(_rpc_error(identifier, -32602, "tools/list params must be empty")); continue
            result = {"tools": _tools(maintainer)}
        elif method == "tools/call":
            params = request.get("params")
            if not isinstance(params, dict) or set(params) - {"name", "arguments"} or not isinstance(params.get("name"), str) or not isinstance(params.get("arguments", {}), dict): _emit(_rpc_error(identifier, -32602, "invalid tools/call params")); continue
            name, arguments = params["name"], params.get("arguments", {})
            if name not in allowed: _emit(_rpc_error(identifier, -32602, "tool is not exposed by this server")); continue
            try:
                _validate(SCHEMAS[name], arguments)
                result = _tool_result(execute_tool(name, arguments, maintainer=maintainer))
            except ValueError as exc: _emit(_rpc_error(identifier, -32602, str(exc))); continue
            except GraphError as exc: result = _tool_result({"error": {"code": exc.code, "message": str(exc), "details": exc.details}}, error=True)
            except Exception: result = _tool_result({"error": {"code": "INTERNAL_ERROR", "message": "bounded internal error"}}, error=True)
        else: _emit(_rpc_error(identifier, -32601, "method not found")); continue
        _emit({"jsonrpc": "2.0", "id": identifier, "result": result})
    return 0


if __name__ == "__main__": raise SystemExit(main())
