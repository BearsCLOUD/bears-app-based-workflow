#!/usr/bin/env python3
"""SessionStart hook for Bears L1 orchestrator initialization."""

from __future__ import annotations

from _agentic_enterprise_hook_common import read_stdin_event, run_decision

if __name__ == "__main__":
    raise SystemExit(run_decision("SessionStart", read_stdin_event()))
