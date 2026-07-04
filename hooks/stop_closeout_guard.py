#!/usr/bin/env python3
"""Non-blocking Stop hook that records redacted dialogue statistics."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
STATS_PATH = WORKSPACE_ROOT / ".codex/runtime/dialogue-stats/dialogue-stats.jsonl"
MAX_STRING_LENGTH = 240
MAX_HINTS = 24
SECRET_PATTERNS = (
    re.compile(r"(?i)(sk-[a-z0-9_-]{12,})"),
    re.compile(r"(?i)(xox[baprs]-[a-z0-9-]{10,})"),
    re.compile(r"(?i)(gh[pousr]_[a-z0-9_]{20,})"),
    re.compile(r"(?i)(telegram[_-]?(bot)?[_-]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)[^\s,;]+"),
)
SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "env",
    "header",
    "key",
    "log",
    "message",
    "output",
    "password",
    "prompt",
    "secret",
    "stderr",
    "stdout",
    "text",
    "token_value",
    "transcript",
)
ID_KEYS = (
    "conversation_id",
    "conversationId",
    "dialogue_id",
    "dialogueId",
    "parent_id",
    "parentId",
    "request_id",
    "requestId",
    "run_id",
    "runId",
    "session_id",
    "sessionId",
    "thread_id",
    "threadId",
    "trace_id",
    "traceId",
    "turn_id",
    "turnId",
)
COUNTER_KEYS = (
    "cached_input_tokens",
    "cachedInputTokens",
    "completion_tokens",
    "completionTokens",
    "input_tokens",
    "inputTokens",
    "output_tokens",
    "outputTokens",
    "prompt_tokens",
    "promptTokens",
    "reasoning_tokens",
    "reasoningTokens",
    "total_tokens",
    "totalTokens",
    "tool_calls",
    "toolCalls",
    "tool_errors",
    "toolErrors",
    "tool_successes",
    "toolSuccesses",
)
CLOSEOUT_KEYS = (
    "bears_closeout",
    "closeout",
    "closeout_hint",
    "closeout_intent",
    "delivery_closeout",
    "final_closeout",
    "task_closeout",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _redact_string(value: str) -> str:
    redacted = value.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        is_bare_secret = (
            pattern.pattern.startswith("(?i)(sk-")
            or pattern.pattern.startswith("(?i)(xox")
            or pattern.pattern.startswith("(?i)(gh")
        )
        if is_bare_secret:
            redacted = pattern.sub("[REDACTED]", redacted)
        else:
            redacted = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    if len(redacted) > MAX_STRING_LENGTH:
        return f"{redacted[:MAX_STRING_LENGTH]}…"
    return redacted


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").casefold()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _walk_dicts(obj: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stack = [obj]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            found.append(current)
            for key, value in current.items():
                if not isinstance(key, str) or _is_sensitive_key(key):
                    continue
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(item for item in current if isinstance(item, (dict, list)))
    return found


def _first_string(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for source in _walk_dicts(obj):
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return _redact_string(value.strip())
    return None


def _collect_ids(event: dict[str, Any]) -> dict[str, Any]:
    ids: dict[str, Any] = {}
    for source in _walk_dicts(event):
        for key in ID_KEYS:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                ids[_snake_case(key)] = _redact_string(value.strip())
    return ids


def _collect_counters(event: dict[str, Any]) -> dict[str, Any]:
    counters: dict[str, Any] = {}
    for source in _walk_dicts(event):
        for key in COUNTER_KEYS:
            value = source.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                counters[_snake_case(key)] = value
            elif isinstance(value, float) and value.is_integer():
                counters[_snake_case(key)] = int(value)
    return counters


def _collect_closeout_hints(event: dict[str, Any]) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    for source in _walk_dicts(event):
        for key in CLOSEOUT_KEYS:
            if key in source and len(hints) < MAX_HINTS:
                hints[_snake_case(key)] = _safe_scalar(source[key])
    return hints


def _snake_case(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars).replace("-", "_")


def _event_name(event: dict[str, Any]) -> str:
    raw = _first_string(event, ("hook_event_name", "hookEventName", "event", "event_name", "eventName"))
    return raw or "Stop"


def _timestamp(event: dict[str, Any]) -> str:
    raw = _first_string(event, ("timestamp", "created_at", "createdAt", "started_at", "startedAt"))
    return raw or _utc_now()


def _cwd(event: dict[str, Any]) -> str | None:
    raw = _first_string(event, ("cwd", "workdir", "working_directory", "workingDirectory"))
    if raw:
        return raw
    current = os.getcwd()
    return _redact_string(current) if current else None


def _git_summary(cwd: str | None) -> dict[str, Any]:
    if not cwd:
        return {"available": False}
    try:
        path = Path(cwd).expanduser().resolve()
    except Exception:
        return {"available": False}
    if not path.exists() or not path.is_dir():
        return {"available": False}
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return {"available": False}
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=str(path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
    except Exception:
        return {"available": False}
    dirty_count = 0 if status.returncode != 0 else len([line for line in status.stdout.splitlines() if line.strip()])
    return {
        "available": True,
        "branch": _redact_string(branch.stdout.strip()) if branch.returncode == 0 and branch.stdout.strip() else None,
        "dirty_count": dirty_count,
    }


def _statistics_row(event: dict[str, Any], payload_present: bool) -> dict[str, Any]:
    cwd = _cwd(event)
    row: dict[str, Any] = {
        "schema": "bears-dialogue-stop-statistics.v1",
        "recorded_at": _utc_now(),
        "timestamp": _timestamp(event),
        "event": _event_name(event),
        "payload_present": payload_present,
        "cwd": cwd,
        "ids": _collect_ids(event),
        "model": _first_string(event, ("model", "model_name", "modelName")),
        "counters": _collect_counters(event),
        "git": _git_summary(cwd),
        "closeout_hints": _collect_closeout_hints(event),
    }
    return {key: value for key, value in row.items() if value not in ({}, None)}


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _stdout(status: str, row: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hook": {
            "name": "bears-dialogue-stop-statistics",
            "status": status,
            "stats_path": str(STATS_PATH),
            "payload_present": bool(row.get("payload_present")),
        },
        "hookSpecificOutput": {"hookEventName": "Stop"},
    }
    if error:
        payload["hook"]["error"] = _redact_string(error)
    return payload


def main() -> int:
    stdin_text = sys.stdin.read()
    payload_present = bool(stdin_text.strip())
    if payload_present:
        try:
            event_raw = json.loads(stdin_text)
        except json.JSONDecodeError:
            event_raw = {}
    else:
        event_raw = {}
    event = event_raw if isinstance(event_raw, dict) else {}
    row = _statistics_row(event, payload_present)
    try:
        _append_jsonl(STATS_PATH, row)
        print(json.dumps(_stdout("ok", row), indent=2, sort_keys=True))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps(_stdout("error", row, str(exc)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
