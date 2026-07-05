#!/usr/bin/env python3
"""Compatibility shim for the renamed @Bears subagents-roles router."""
from __future__ import annotations

from subagents_roles import main

if __name__ == "__main__":
    raise SystemExit(main())
