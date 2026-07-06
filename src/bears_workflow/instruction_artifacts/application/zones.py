"""Build normalized instruction zones for callers that do not need metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bears_workflow.instruction_artifacts.adapters import exporter
from bears_workflow.instruction_artifacts.domain.constants import (
    default_codex_config,
    default_personal_agents,
    default_root,
)

DEFAULT_RESPONSE_LINE_BUDGET = 200
MAX_RESPONSE_LINE_BUDGET = 1000


def _resolve_path(value: str | None, fallback: Any) -> Path:
    if value is None:
        return fallback()
    return Path(value).expanduser()


def _bounded_budget(value: int) -> int:
    return max(1, min(int(value), MAX_RESPONSE_LINE_BUDGET))


def build_zones(
    *,
    root: str | Path | None = None,
    codex_config: str | Path | None = None,
    personal_agents: str | Path | None = None,
    include_untracked_level4: bool = False,
) -> dict[str, Any]:
    """Return normalized instruction zones without transport or cache metadata."""
    resolved_root = (
        root.expanduser() if isinstance(root, Path) else _resolve_path(root, default_root)
    ).resolve()
    resolved_codex_config = (
        codex_config.expanduser()
        if isinstance(codex_config, Path)
        else _resolve_path(codex_config, default_codex_config)
    )
    resolved_personal_agents = (
        personal_agents.expanduser()
        if isinstance(personal_agents, Path)
        else _resolve_path(personal_agents, default_personal_agents)
    )
    developer_instructions, _config_warnings = exporter.parse_model_instructions_file(
        resolved_codex_config
    )
    targets, _discovery_warnings = exporter.discover_agents(
        resolved_root,
        include_untracked_level4=include_untracked_level4,
    )
    normalized = exporter.build_normalized_export(
        root=resolved_root,
        targets=targets,
        personal_agents=resolved_personal_agents,
        developer_instructions=developer_instructions,
        codex_root=resolved_codex_config.parent.resolve(),
    )
    docs = normalized.get("docs", [])
    graphs = normalized.get("graphs", [])
    return {"docs": docs, "graphs": graphs}


def build_zones_startup(
    *,
    root: str | Path | None = None,
    codex_config: str | Path | None = None,
    personal_agents: str | Path | None = None,
    include_untracked_level4: bool = False,
    response_line_budget: int = DEFAULT_RESPONSE_LINE_BUDGET,
) -> dict[str, Any]:
    """Return a bounded startup packet for Codex MCP initialization."""
    budget = _bounded_budget(response_line_budget)
    payload = build_zones(
        root=root,
        codex_config=codex_config,
        personal_agents=personal_agents,
        include_untracked_level4=include_untracked_level4,
    )
    docs = list(payload.get("docs", []))
    graphs = list(payload.get("graphs", []))
    docs_budget = min(len(docs), budget // 2)
    graphs_budget = min(len(graphs), budget - docs_budget)
    response_lines = docs_budget + graphs_budget
    truncated = docs_budget < len(docs) or graphs_budget < len(graphs)
    return {
        "schema": "bears.instruction_zones.startup.v1",
        "response_line_budget": budget,
        "response_lines": response_lines,
        "truncated": truncated,
        "truncation_reason": "response_line_budget" if truncated else None,
        "counts": {
            "docs": len(docs),
            "graphs": len(graphs),
            "returned_docs": docs_budget,
            "returned_graphs": graphs_budget,
        },
        "next_calls": [
            {
                "tool": "zones",
                "reason": "Fetch the full normalized docs and graphs payload when explicitly needed.",
            }
        ]
        if truncated
        else [],
        "docs": docs[:docs_budget],
        "graphs": graphs[:graphs_budget],
    }
