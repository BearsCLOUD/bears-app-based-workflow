#!/usr/bin/env python3
"""UserPromptSubmit hook for compact Bears workflow packet checks."""

from __future__ import annotations

from _agentic_enterprise_hook_common import read_stdin_event, run_decision

if __name__ == "__main__":
    raise SystemExit(run_decision("UserPromptSubmit", read_stdin_event()))
