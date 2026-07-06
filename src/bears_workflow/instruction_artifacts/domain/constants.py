"""Domain constants for instruction artifact zones."""

from pathlib import Path

DEFAULT_ROOT = Path("/srv/bears")
DEFAULT_CODEX_CONFIG = Path("/home/ai1/.codex/config.toml")
DEFAULT_PERSONAL_AGENTS = Path("/home/ai1/.codex/AGENTS.md")
AGENTS_NAME = "AGENTS.md"
LEVEL4_EXCEPTION_PARENT_NAMES = {"dev"}
