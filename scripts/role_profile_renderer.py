#!/usr/bin/env python3
"""CLI facade for the root-gateway-owned safe role profile renderer."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "runner"))
from bears_deploy.role_renderer import *  # noqa: F401,F403,E402

if __name__ == "__main__":
    raise SystemExit(main())
