#!/usr/bin/env python3
"""Run the shared read-only SQLite workflow validator."""
from __future__ import annotations

from pathlib import Path
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from app_workflow import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["validate", *sys.argv[1:]]))
