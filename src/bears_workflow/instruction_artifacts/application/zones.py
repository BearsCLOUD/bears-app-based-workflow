"""Build normalized instruction zones for callers that do not need metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bears_workflow.instruction_artifacts.adapters import exporter
from bears_workflow.instruction_artifacts.domain.constants import (
    DEFAULT_CODEX_CONFIG,
    DEFAULT_PERSONAL_AGENTS,
    DEFAULT_ROOT,
)


def build_zones(
    *,
    root: Path = DEFAULT_ROOT,
    codex_config: Path = DEFAULT_CODEX_CONFIG,
    personal_agents: Path = DEFAULT_PERSONAL_AGENTS,
    include_untracked_level4: bool = False,
) -> dict[str, Any]:
    """Return normalized instruction zones without transport or cache metadata."""
    developer_instructions, _config_warnings = exporter.parse_model_instructions_file(codex_config)
    targets, _discovery_warnings = exporter.discover_agents(
        root,
        include_untracked_level4=include_untracked_level4,
    )
    normalized = exporter.build_normalized_export(
        root=root,
        targets=targets,
        personal_agents=personal_agents,
        developer_instructions=developer_instructions,
        codex_root=Path.home() / ".codex",
    )
    docs = normalized.get("docs", [])
    graphs = normalized.get("graphs", [])
    return {"docs": docs, "graphs": graphs}
