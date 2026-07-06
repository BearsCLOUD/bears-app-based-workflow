"""MCP entrypoint exposing Bears instruction zones."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from bears_workflow.instruction_artifacts.application.zones import build_zones

mcp = FastMCP(
    "mcp",
    instructions=(
        "Use zones for bounded normalized Bears instruction graphs. "
        "The payload contains docs and graphs only; no full export is exposed."
    ),
)


@mcp.tool()
def zones() -> dict[str, Any]:
    """Return normalized Bears instruction zones without metadata."""
    return build_zones()


def main() -> None:
    """Run the Bears instruction zones MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
