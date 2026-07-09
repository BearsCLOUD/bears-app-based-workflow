#!/usr/bin/env python3
"""PreToolUse hook for L1 deny-all and L2/L3 scope checks."""

from __future__ import annotations

from _agentic_enterprise_hook_common import read_stdin_event, run_decision

if __name__ == "__main__":
    raise SystemExit(run_decision("PreToolUse", read_stdin_event()))
