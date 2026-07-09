"""Domain constants and runtime default resolvers for instruction artifact zones."""

import os
from pathlib import Path

ENV_INSTRUCTION_ROOT = "BEARS_INSTRUCTION_ROOT"
ENV_CODEX_CONFIG = "BEARS_CODEX_CONFIG"
ENV_PERSONAL_AGENTS = "BEARS_PERSONAL_AGENTS"
ENV_CODEX_HOME = "CODEX_HOME"
AGENTS_NAME = "AGENTS.md"
LEVEL4_EXCEPTION_PARENT_NAMES = {"dev"}


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return Path(value).expanduser()


def default_codex_home() -> Path:
    """Return the local Codex home without embedding host-specific paths."""
    return _env_path(ENV_CODEX_HOME) or (Path.home() / ".codex")


def default_root() -> Path:
    """Return the instruction workspace root for this process."""
    return _env_path(ENV_INSTRUCTION_ROOT) or Path.cwd()


def default_codex_config() -> Path:
    """Return the Codex config path for instruction inheritance discovery."""
    return _env_path(ENV_CODEX_CONFIG) or (default_codex_home() / "config.toml")


def default_personal_agents() -> Path:
    """Return the personal AGENTS.md path for instruction inheritance discovery."""
    return _env_path(ENV_PERSONAL_AGENTS) or (default_codex_home() / AGENTS_NAME)
