"""MCP entrypoint exposing Bears instruction zones."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from bears_workflow.instruction_artifacts.application.zones import (
    DEFAULT_RESPONSE_LINE_BUDGET,
    build_zones,
    build_zones_startup,
)

mcp = FastMCP(
    "mcp",
    instructions=(
        "Use zones_startup for bounded normalized Bears instruction graph startup. "
        "Use zones only after explicit need for the full docs and graphs payload."
    ),
)


@mcp.tool()
def zones_startup(
    root: str | None = None,
    codex_config: str | None = None,
    personal_agents: str | None = None,
    include_untracked_level4: bool = False,
    response_line_budget: int = DEFAULT_RESPONSE_LINE_BUDGET,
) -> dict[str, Any]:
    """Return bounded Bears instruction zones with truncation metadata."""
    return build_zones_startup(
        root=root,
        codex_config=codex_config,
        personal_agents=personal_agents,
        include_untracked_level4=include_untracked_level4,
        response_line_budget=response_line_budget,
    )


@mcp.tool()
def zones(
    root: str | None = None,
    codex_config: str | None = None,
    personal_agents: str | None = None,
    include_untracked_level4: bool = False,
) -> dict[str, Any]:
    """Return full normalized Bears instruction zones without metadata."""
    return build_zones(
        root=root,
        codex_config=codex_config,
        personal_agents=personal_agents,
        include_untracked_level4=include_untracked_level4,
    )


def main() -> None:
    """Run the Bears instruction zones MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
