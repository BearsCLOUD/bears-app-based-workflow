#!/usr/bin/env python3
"""Enforcement hooks for the bears-app-based-workflow plugin.

Two modes, selected by argv[1]:

  cas    PreToolUse guard on the maintainer MCP server. Denies any mutation
         whose input is missing a well-formed CAS triple (request_id,
         expected_revision, expected_logical_digest). This is defense in
         depth; the primary barrier is that subagents are never granted the
         maintainer tools at all.

  phase  Stop / SubagentStop guard. Refuses to end the turn while the
         per-project workflow database is left in an inconsistent state.

Both modes read the hook payload as JSON on stdin and are fail-open: any
unexpected condition exits 0 without a decision so a broken hook can never
wedge a session. Stdlib only.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sqlite3
import sys

MAINTAINER_TOOL_RE = re.compile(r"^mcp__.*app-workflow-maintainer__(.+)$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
DB_RELATIVE_PATH = os.path.join(".bears", "app-workflow.sqlite3")
PHASES = (
    "app-constitution",
    "app-research",
    "app-specify",
    "app-functional-graph",
    "app-plan",
    "app-dev",
    "app-analyze",
)
# Phases the runtime settles on its own, without a process record: plan_replace
# marks 'app-plan' completed and analysis_record marks 'app-analyze' ready. A
# missing process record for those two is legitimate, not an inconsistency.
SELF_SETTLING_PHASES = ("app-plan", "app-analyze")


def maintainer_tool(tool_name: object) -> str | None:
    """Return the bare maintainer tool name, or None for any other tool."""
    if not isinstance(tool_name, str):
        return None
    match = MAINTAINER_TOOL_RE.match(tool_name)
    return match.group(1) if match else None


def cas_violations(tool_input: object) -> list[str]:
    """Return human-readable reasons the CAS triple is unusable, if any."""
    if not isinstance(tool_input, dict):
        return ["tool input is not an object"]
    problems: list[str] = []

    request_id = tool_input.get("request_id")
    if request_id is None:
        problems.append("missing 'request_id'")
    elif not isinstance(request_id, str) or not REF_RE.match(request_id):
        problems.append("'request_id' must be a short reference string")

    revision = tool_input.get("expected_revision")
    if revision is None:
        problems.append("missing 'expected_revision'")
    elif isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        problems.append("'expected_revision' must be a non-negative integer")

    digest = tool_input.get("expected_logical_digest")
    if digest is None:
        problems.append("missing 'expected_logical_digest'")
    elif not isinstance(digest, str) or not DIGEST_RE.match(digest):
        problems.append("'expected_logical_digest' must match sha256:<64 hex>")

    return problems


def run_cas(payload: dict) -> int:
    tool = maintainer_tool(payload.get("tool_name"))
    if tool is None:
        return 0
    problems = cas_violations(payload.get("tool_input"))
    if not problems:
        return 0
    reason = (
        "Blocked maintainer mutation '%s': %s. Every app-workflow maintainer "
        "call is compare-and-set guarded. Read 'project_status' on the "
        "read-only app-workflow server to obtain the current revision and "
        "logical digest, then retry with a fresh unique request_id."
        % (tool, "; ".join(problems))
    )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    return 0


def phase_inconsistencies(connection: sqlite3.Connection) -> list[str]:
    """Return descriptions of workflow states that must not survive a turn."""
    problems: list[str] = []
    waves = connection.execute(
        "SELECT wave_id, status, current_phase FROM waves"
    ).fetchall()
    for wave_id, wave_status, current_phase in waves:
        phase_rows = connection.execute(
            "SELECT phase, status, process_record_ref FROM phases WHERE wave_id=?",
            (wave_id,),
        ).fetchall()
        known = {row[0] for row in phase_rows}

        if current_phase is not None and current_phase not in known:
            problems.append(
                "wave %s points at current_phase '%s', which has no phase row"
                % (wave_id, current_phase)
            )
        if current_phase is not None and current_phase not in PHASES:
            problems.append(
                "wave %s points at unknown phase '%s'" % (wave_id, current_phase)
            )

        for phase, status, record_ref in phase_rows:
            if record_ref is not None:
                # A phase pointing at a record that is absent or no longer the
                # active one is always a corruption, whatever the status.
                dangling = connection.execute(
                    "SELECT 1 FROM process_records "
                    "WHERE record_ref=? AND wave_id=? AND phase=? AND active=1",
                    (record_ref, wave_id, phase),
                ).fetchone()
                if dangling is None:
                    problems.append(
                        "wave %s phase '%s' points at process record '%s', which "
                        "is not the active record for that phase"
                        % (wave_id, phase, record_ref)
                    )
            elif status == "completed" and phase not in SELF_SETTLING_PHASES:
                problems.append(
                    "wave %s phase '%s' is marked completed but has no active "
                    "process record; call phase_record before ending the turn"
                    % (wave_id, phase)
                )

        audited = connection.execute(
            "SELECT 1 FROM audit_attestations WHERE wave_id=? AND status='active'",
            (wave_id,),
        ).fetchone()
        if wave_status == "ready" or audited is not None:
            open_corrections = connection.execute(
                "SELECT COUNT(*) FROM corrections c "
                "JOIN tasks t ON t.task_ref = c.task_ref "
                "WHERE t.wave_id=? AND c.status='open'",
                (wave_id,),
            ).fetchone()[0]
            if open_corrections:
                problems.append(
                    "wave %s is at audit state with %d open correction(s); resolve "
                    "them with correction_record before ending the turn"
                    % (wave_id, open_corrections)
                )
    return problems


def run_phase(payload: dict) -> int:
    if payload.get("stop_hook_active"):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    if not isinstance(cwd, str):
        return 0
    db_path = os.path.join(cwd, DB_RELATIVE_PATH)
    if not os.path.isfile(db_path):
        return 0
    uri = pathlib.Path(db_path).as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    try:
        problems = phase_inconsistencies(connection)
    finally:
        connection.close()
    if not problems:
        return 0
    json.dump(
        {
            "decision": "block",
            "reason": (
                "The app-workflow state is inconsistent:\n- "
                + "\n- ".join(problems)
                + "\nResolve this before ending the turn, or say so explicitly."
            ),
        },
        sys.stdout,
    )
    return 0


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        if mode == "cas":
            return run_cas(payload)
        if mode == "phase":
            return run_phase(payload)
    except Exception:  # never wedge a session on a hook defect
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
