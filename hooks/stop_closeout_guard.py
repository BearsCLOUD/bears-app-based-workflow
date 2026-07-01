#!/usr/bin/env python3
"""Stop hook for Bears plugin closeout delivery guard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from _agentic_enterprise_hook_common import read_stdin_event

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_STATE = PLUGIN_ROOT / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"
VALIDATION_STATE_ROOT = PLUGIN_ROOT / "runtime/validation-state"
DOCTOR_SCRIPT = PLUGIN_ROOT / "scripts/bears_doctor.py"
TRUE_STRINGS = {"1", "true", "yes", "y", "on"}
CLOSEOUT_KEYS = {
    "bears_closeout",
    "closeout",
    "closeout_intent",
    "delivery_closeout",
    "final_closeout",
    "final_report",
    "task_closeout",
}


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in TRUE_STRINGS
    return False


def _has_closeout_intent(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in CLOSEOUT_KEYS and _is_true(value):
                return True
            if key in {"state", "workflow", "metadata", "bears"} and _has_closeout_intent(value):
                return True
    return False


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _git_status() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=3,
    )
    if proc.returncode != 0:
        return ["git_status_unavailable"]
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _head_sha() -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=3,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _validation_status() -> str:
    sha = _head_sha()
    if not sha:
        return "missing"
    state = _load_json(VALIDATION_STATE_ROOT / sha / "validation-state.v1.json")
    return str(state.get("status") or "missing")


def _head_range(sha: str | None) -> str:
    if not sha:
        return "HEAD~1..HEAD"
    proc = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", sha],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=3,
    )
    if proc.returncode != 0:
        return f"HEAD~1..{sha}"
    parts = proc.stdout.strip().split()
    parent = parts[1] if len(parts) > 1 else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    return f"{parent}..{sha}"


def _doctor_status() -> str:
    if not DOCTOR_SCRIPT.exists():
        return "not_available"
    sha = _head_sha()
    proc = subprocess.run(
        [sys.executable, str(DOCTOR_SCRIPT), "emit-summary", "--from-git", _head_range(sha), "--json"],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=15,
    )
    try:
        packet = json.loads(proc.stdout)
    except Exception:
        return "fail"
    return str(packet.get("status") or "fail")


def _delivery_complete() -> bool:
    state = _load_json(DELIVERY_STATE)
    return state.get("delivery_complete") is True


def _result(decision: str, reason: str, *, dirty_count: int, delivery_complete: bool, closeout_intent: bool, validation_status: str, doctor_status: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "bears-plugin-stop-closeout-guard.v1",
        "event": "Stop",
        "decision": decision,
        "reason": reason,
        "closeout_intent": closeout_intent,
        "delivery_complete": delivery_complete,
        "validation_status": validation_status,
        "doctor_status": doctor_status,
        "dirty_count": dirty_count,
        "hookSpecificOutput": {"hookEventName": "Stop"},
    }
    if decision == "deny":
        payload["hookSpecificOutput"].update(
            {
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        )
        payload["next_actions"] = [
            "commit task changes directly to main",
            "run python3 scripts/bears_doctor.py validate-closeout --from-git <parent_sha>..<main_sha> --json",
            "run python3 scripts/plugin_cache_sync.py watch --interval-seconds 15 --timeout-seconds 1200",
            "close only after runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json has delivery_complete=true",
        ]
    return payload


def main() -> int:
    event = read_stdin_event()
    closeout_intent = _has_closeout_intent(event) or _is_true(os.environ.get("BEARS_PLUGIN_CLOSEOUT"))
    delivery_complete = _delivery_complete()
    validation_status = _validation_status()
    doctor_status = _doctor_status()
    dirty = _git_status()
    if closeout_intent and (dirty or not delivery_complete or doctor_status != "pass"):
        reason = "Bears plugin closeout blocked until main commit, bears_doctor pass, cache sync, and delivery_complete=true."
        print(json.dumps(_result("deny", reason, dirty_count=len(dirty), delivery_complete=delivery_complete, closeout_intent=True, validation_status=validation_status, doctor_status=doctor_status), indent=2, sort_keys=True))
        return 2
    reason = "closeout guard passed" if closeout_intent else "no closeout intent in Stop payload"
    print(json.dumps(_result("allow", reason, dirty_count=len(dirty), delivery_complete=delivery_complete, closeout_intent=closeout_intent, validation_status=validation_status, doctor_status=doctor_status), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
