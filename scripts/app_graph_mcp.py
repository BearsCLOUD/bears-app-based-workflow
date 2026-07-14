#!/usr/bin/env python3
"""Strict lifecycle-correct stdio MCP surface for the app graph runtime."""
from __future__ import annotations

import json
import re
import sys
from typing import Any

from app_graph_engine import GraphError, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, execute_tool

SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18")
SERVER_VERSION = "0.4.3"

STR = {"type": "string", "minLength": 1}
REFS = {"type": "array", "items": STR, "uniqueItems": True}
NON_EMPTY_REFS = {**REFS, "minItems": 1}
GIT_REF = {"type": "string", "pattern": r"^[0-9a-f]{40}$"}
GIT_REFS = {"type": "array", "minItems": 1, "items": GIT_REF, "uniqueItems": True}
COMMIT_RANGE = {"type": "string", "pattern": r"^[0-9a-f]{40}\.\.[0-9a-f]{40}$"}
STAGES = [
    "app-constitution", "app-research", "app-specify", "app-functional-graph",
    "app-plan", "app-dev", "app-analyze",
]
STATUSES = [
    "constitution-ready", "needs-research", "research-ready", "needs-spec",
    "spec-ready", "needs-graph", "graph-ready", "waiting", "needs-plan",
    "plan-ready", "ready", "in_progress", "implemented", "no-work",
    "audited", "done", "failed", "blocked", "superseded",
]
FINDING_KINDS = [
    "missing-source", "product-conflict", "decision-conflict", "semantic-gap",
    "reference-gap", "cycle-gap", "task-gap", "implementation-gap",
    "evidence-gap", "review-gap", "remediation-gap", "credential-stop",
    "access-stop", "operator-stop",
]
ANALYSIS_INPUT_FIELDS = (
    "source_refs", "decision_refs", "requirement_refs", "functionality_refs",
    "dimension_refs", "dimension_mapping_refs", "relation_refs", "graph_edge_refs",
    "functional_map_refs", "ledger_refs", "artifact_refs", "evidence_refs", "task_refs",
    "task_result_refs", "review_refs", "remediation_refs", "process_record_refs",
    "incoming_handoff_refs",
)
COVERAGE_FIELDS = (
    "sources", "decisions", "requirements", "functionalities", "dimensions",
    "dimension_mappings", "relations", "graph_edges", "functional_map", "ledger",
    "artifacts", "evidence", "tasks", "task_results", "reviews", "remediations",
    "process_records", "incoming_handoff",
)
REF_SET_BINDING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["count", "refs_digest"],
    "properties": {
        "count": {"type": "integer", "minimum": 0},
        "refs_digest": {"type": "string", "pattern": r"^sha256:[a-f0-9]{64}$"},
    },
}
CURSOR = {"type": "string", "description": "Opaque snapshot/query-bound continuation token."}
BOUNDS = {
    "app_root": STR,
    "expected_build_ref": STR,
    "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
    "max_depth": {"type": "integer", "minimum": 1, "maximum": 32, "default": 8},
    "cursor": CURSOR,
}
DELEGATION_RECORD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "dispatch_schema", "result_schema", "delegation_authority_ref",
        "assignment_authority_ref", "assignment_id", "task_id", "role",
        "role_kind", "agent_level", "orchestrator_session_id",
    ],
    "properties": {
        "dispatch_schema": {"const": "dispatch-packet.v3"},
        "result_schema": {"const": "result-packet.v2"},
        "delegation_authority_ref": STR,
        "assignment_authority_ref": STR,
        "assignment_id": STR,
        "task_id": STR,
        "role": STR,
        "role_kind": {"enum": ["helper", "mutation-worker", "primary-critic"]},
        "agent_level": {"const": "L3"},
        "orchestrator_session_id": STR,
        "app_task_schema": {"const": "app-task-dispatch.v2"},
    },
}
ANALYSIS_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema", "analysis_ref", "profile_ref", "model_ref", "checklist_ref",
        "basis_build_ref", "input_refs", "coverage", "findings",
        "unmapped_decision_refs", "unmapped_requirement_refs",
        "open_remediation_refs", "complete", "route",
    ],
    "properties": {
        "schema": {"const": "app-semantic-analysis-result.v1"},
        "analysis_ref": STR,
        "profile_ref": STR,
        "model_ref": STR,
        "checklist_ref": STR,
        "basis_build_ref": {"type": "string", "pattern": r"^BUILD-[A-F0-9]{24}$"},
        "input_refs": {
            "type": "object",
            "additionalProperties": False,
            "required": list(ANALYSIS_INPUT_FIELDS),
            "properties": {name: REF_SET_BINDING for name in ANALYSIS_INPUT_FIELDS},
        },
        "coverage": {
            "type": "object",
            "additionalProperties": False,
            "required": list(COVERAGE_FIELDS),
            "properties": {
                name: {"type": "integer", "minimum": 0}
                for name in COVERAGE_FIELDS
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["finding_ref", "kind", "subject_refs", "conflict_refs", "route", "summary"],
                "properties": {
                    "finding_ref": STR,
                    "kind": {"enum": FINDING_KINDS},
                    "subject_refs": REFS,
                    "conflict_refs": REFS,
                    "route": {"enum": ["needs-research", "needs-spec", "needs-graph", "needs-plan", "blocked"]},
                    "summary": STR,
                },
            },
        },
        "unmapped_decision_refs": REFS,
        "unmapped_requirement_refs": REFS,
        "open_remediation_refs": REFS,
        "complete": {"type": "boolean"},
        "route": {"enum": ["none", "needs-research", "needs-spec", "needs-graph", "needs-plan", "blocked"]},
    },
}
EVENT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["schema", "run_ref", "event_ref", "event_kind", "stage", "status", "actor", "owner_session_ref", "causal_refs", "trace_refs", "artifact_refs", "task_refs", "origin", "repo_ref", "wave_ref"],
    "properties": {
        "schema": {"const": "app-process-event.v3"},
        **{name: STR for name in ("run_ref", "event_ref", "owner_session_ref", "repo_ref", "wave_ref")},
        "stage": {"enum": STAGES},
        "status": {"enum": STATUSES},
        "actor": {"enum": ["DIRECT-primary", "repo-L2"]},
        "event_kind": {"enum": ["run-start", "stage", "delegation", "task-result", "review", "remediation", "repo-handoff", "analysis"]},
        **{name: REFS for name in ("causal_refs", "trace_refs", "artifact_refs", "task_refs")},
        "origin": {"const": "native"},
        "task_ref": STR, "terminal_result": {"enum": ["done", "failed", "blocked"]},
        "commit_refs": GIT_REFS,
        "changed_paths": NON_EMPTY_REFS,
        "reviewed_task_refs": REFS,
        "finding_refs": REFS,
        "commit_range": COMMIT_RANGE, "remediates_run_ref": STR, "analysis_ref": STR,
        "analysis_result": ANALYSIS_RESULT_SCHEMA,
        "delegation_record": DELEGATION_RECORD_SCHEMA,
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
}
READ_DESCRIPTIONS = {
    "dependency_slice": "Return bounded graph prerequisites or dependents.",
    "impact_analysis": "Return bounded reverse dependency impact.",
    "graph_trace": "Return typed trace edges.",
    "graph_diagnostics": "Return compiler findings.",
    "topological_plan": "Return dependency-ordered task refs.",
    "workflow_state": "Return immutable process events.",
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
        if len(value) < schema.get("minItems", 0): raise ValueError(f"{path} contains too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]: raise ValueError(f"{path} contains too many items")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value): raise ValueError(f"{path} must contain unique items")
        for index, item in enumerate(value): _validate(schema["items"], item, f"{path}[{index}]")
    elif kind == "string":
        if not isinstance(value, str) or len(value) < schema.get("minLength", 0): raise ValueError(f"{path} must be a non-empty string")
        if schema.get("pattern") and re.fullmatch(schema["pattern"], value) is None: raise ValueError(f"{path} has an invalid format")
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


def _list_params_valid(params: Any) -> bool:
    """Accept MCP request metadata while rejecting unsupported pagination."""
    if params is None:
        return True
    if not isinstance(params, dict) or set(params) - {"cursor", "_meta"}:
        return False
    if params.get("cursor") is not None:
        return False
    return "_meta" not in params or isinstance(params["_meta"], dict)


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
            if not _list_params_valid(request.get("params")): _emit(_rpc_error(identifier, -32602, "invalid tools/list params")); continue
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
