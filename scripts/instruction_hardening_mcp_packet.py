#!/usr/bin/env python3
"""Call the local Bears instruction-hardening MCP over stdio and print bounded JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) in sys.path:
    sys.path.remove(str(SCRIPT_ROOT))

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ALLOWED_TOOLS = {"instruction_hardening_startup", "instruction_hardening_graphs"}
DEFAULT_LINE_BUDGET = 200
MAX_LINE_BUDGET = 1000
MAX_OUTPUT_BYTES = 250_000


def _plugin_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".codex-plugin" / "plugin.json").is_file():
            return parent
    raise RuntimeError("plugin root not found")


def _bounded_budget(value: int) -> int:
    return max(1, min(int(value), MAX_LINE_BUDGET))


def _json_from_call_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", None)
    if not content:
        return {}
    first = content[0]
    text = getattr(first, "text", None)
    if isinstance(text, str):
        return json.loads(text)
    return json.loads(first.model_dump_json())


def _graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    decision = graph.get("decision") if isinstance(graph.get("decision"), dict) else {}
    live = graph.get("live_confirmation") if isinstance(graph.get("live_confirmation"), dict) else {}
    standard = graph.get("standardization") if isinstance(graph.get("standardization"), dict) else {}
    escalation = graph.get("escalation_candidate") if isinstance(graph.get("escalation_candidate"), dict) else {}
    dependency_refs = graph.get("dependency_decision_refs")
    if not isinstance(dependency_refs, list):
        dependency_refs = []
    return {
        "target": graph.get("target"),
        "chain": graph.get("chain", []),
        "decision_status": decision.get("status"),
        "live_confirmation_status": live.get("status"),
        "standardization_status": standard.get("status"),
        "escalation_candidate_status": escalation.get("status"),
        "escalation_reason": escalation.get("reason"),
        "dependency_decision_ref_count": len(dependency_refs),
        "escalation_evidence_dependency_refs": escalation.get("evidence_dependency_refs", []),
    }


def _doc_summary(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc.get("id"),
        "path": doc.get("path"),
        "kind": doc.get("kind"),
        "title": doc.get("title"),
    }


def _surface_summary(surface: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": surface.get("path"),
        "kind": surface.get("kind"),
        "weak_term_count": surface.get("weak_term_count"),
        "weak_terms_found": surface.get("weak_terms_found", []),
    }


def _summary_wrapper(payload: Any, *, max_bytes: int, original_bytes: int) -> dict[str, Any]:
    docs = payload.get("docs", []) if isinstance(payload, dict) else []
    graphs = payload.get("graphs", []) if isinstance(payload, dict) else []
    instruction_surfaces = (
        payload.get("instruction_surfaces", []) if isinstance(payload, dict) else []
    )
    graph_summaries = [_graph_summary(graph) for graph in graphs if isinstance(graph, dict)]
    escalation_required = [
        graph for graph in graph_summaries if graph.get("escalation_candidate_status") == "required"
    ]
    decision_missing = [
        graph for graph in graph_summaries if graph.get("decision_status") == "missing"
    ]
    return {
        "schema": "bears.instruction_hardening.mcp_packet_cli.summary.v1",
        "derived_from_mcp_payload": True,
        "truncated": True,
        "truncation_reason": "max_output_bytes",
        "max_output_bytes": max_bytes,
        "original_bytes": original_bytes,
        "counts": payload.get("counts") if isinstance(payload, dict) else None,
        "source": payload.get("source") if isinstance(payload, dict) else None,
        "next_calls": payload.get("next_calls") if isinstance(payload, dict) else [],
        "summary_counts": {
            "docs_returned": len(docs) if isinstance(docs, list) else 0,
            "graphs_returned": len(graph_summaries),
            "instruction_surfaces_returned": (
                len(instruction_surfaces) if isinstance(instruction_surfaces, list) else 0
            ),
            "escalation_required_graphs": len(escalation_required),
            "decision_missing_graphs": len(decision_missing),
        },
        "surface_summary": payload.get("surface_summary") if isinstance(payload, dict) else None,
        "docs": [_doc_summary(doc) for doc in docs if isinstance(doc, dict)],
        "graphs": graph_summaries,
        "instruction_surfaces": [
            _surface_summary(surface)
            for surface in instruction_surfaces
            if isinstance(surface, dict)
        ],
    }


def _bounded_dump(payload: Any, *, max_bytes: int) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text + "\n"
    wrapper = _summary_wrapper(payload, max_bytes=max_bytes, original_bytes=len(encoded))
    return json.dumps(wrapper, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


async def _call(args: argparse.Namespace) -> Any:
    plugin_root = _plugin_root()
    tool_args: dict[str, Any] = {
        "include_untracked_level4": args.include_untracked_level4,
    }
    if args.root:
        tool_args["root"] = args.root
    if args.codex_config:
        tool_args["codex_config"] = args.codex_config
    if args.personal_agents:
        tool_args["personal_agents"] = args.personal_agents
    if args.tool == "instruction_hardening_startup":
        tool_args["response_line_budget"] = _bounded_budget(args.response_line_budget)

    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "LOGNAME", "PATH", "SHELL", "TERM", "USER", "CODEX_HOME"}
        or key.startswith("BEARS_")
    }
    server = StdioServerParameters(
        command="python3",
        args=[str(plugin_root / "scripts" / "mcp.py")],
        env=env,
        cwd=str(plugin_root),
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(server, errlog=errlog) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(args.tool, tool_args)
                if getattr(result, "isError", False):
                    raise RuntimeError("MCP tool returned error")
                return _json_from_call_result(result)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call @Bears instruction-hardening MCP evidence tools over stdio."
    )
    parser.add_argument("tool", choices=sorted(ALLOWED_TOOLS))
    parser.add_argument("--root", help="Instruction root passed to the MCP tool.")
    parser.add_argument("--codex-config", help="Codex config path passed to the MCP tool.")
    parser.add_argument("--personal-agents", help="Personal AGENTS.md path passed to the MCP tool.")
    parser.add_argument("--include-untracked-level4", action="store_true")
    parser.add_argument("--response-line-budget", type=int, default=DEFAULT_LINE_BUDGET)
    parser.add_argument("--max-output-bytes", type=int, default=MAX_OUTPUT_BYTES)
    parser.add_argument("--bounded-json", action="store_true", help="Required acknowledgment for bounded JSON output.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.bounded_json:
        print("error: --bounded-json is required", file=sys.stderr)
        return 2
    payload = anyio.run(_call, args)
    sys.stdout.write(_bounded_dump(payload, max_bytes=args.max_output_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
