#!/usr/bin/env python3
"""Launch the @Bears instruction zones MCP server."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PLUGIN_ROOT / "src"
if str(SCRIPT_ROOT) in sys.path:
    sys.path.remove(str(SCRIPT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from bears_workflow.instruction_artifacts.entrypoints.mcp import main


if __name__ == "__main__":
    main()
