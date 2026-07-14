"""Compatibility facade for graph compilation, bounded queries, and process records."""

from __future__ import annotations

from typing import Any

from app_graph_compiler import graph_compile
from app_graph_process import process_record_event
from app_graph_query import GraphStore, execute_query
from app_graph_store import GraphError, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES

READ_TOOLS = {"dependency_slice","impact_analysis","graph_trace","graph_diagnostics","topological_plan","workflow_state"}
MAINTAINER_TOOLS = {"graph_compile","process_record_event"}


def execute_tool(name: str, arguments: dict[str, Any], *, maintainer: bool = False) -> dict[str, Any]:
    """Route the stable MCP surface to focused graph modules."""
    if not isinstance(arguments, dict): raise GraphError("QUERY_INVALID", "arguments must be an object")
    if maintainer:
        if name == "graph_compile": return graph_compile(arguments)
        if name == "process_record_event": return process_record_event(arguments)
        raise GraphError("METHOD_NOT_FOUND", "unknown maintainer tool")
    if name not in READ_TOOLS: raise GraphError("METHOD_NOT_FOUND", "unknown read-only tool")
    return execute_query(name, arguments)


__all__ = ["GraphError","GraphStore","MAX_REQUEST_BYTES","MAX_RESPONSE_BYTES","execute_tool","graph_compile","process_record_event"]
