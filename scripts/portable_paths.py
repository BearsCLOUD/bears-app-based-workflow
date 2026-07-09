#!/usr/bin/env python3
"""Detect newly introduced server-specific absolute paths in plugin source."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "bears-plugin-portable-paths.v1"
DEFAULT_FORBIDDEN = ("/srv" + "/bears", "/home" + "/ai1", "/t" + "mp")
ALLOWED_TEXT_RE = re.compile(r"^#!\s*/usr/bin/env\b")
GIT_ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_env() -> dict[str, str]:
    import os

    env = os.environ.copy()
    for key in GIT_ENV_KEYS:
        env.pop(key, None)
    return env


def run(argv: list[str], *, timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(argv, cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout, env=clean_env())
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    return proc.returncode, proc.stdout, proc.stderr


def added_lines_from_diff(args: argparse.Namespace) -> tuple[int, str, str, list[tuple[str, int, str]]]:
    cmd = ["git", "diff", "--unified=0"]
    if args.staged:
        cmd.append("--cached")
    elif args.from_git:
        cmd.append(args.from_git)
    code, stdout, stderr = run(cmd)
    if code != 0:
        return code, stdout, stderr, []
    rows: list[tuple[str, int, str]] = []
    path = ""
    new_line = 0
    for line in stdout.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            new_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            text = line[1:]
            rows.append((path, new_line, text))
            new_line += 1
        elif not line.startswith("-"):
            new_line += 1
    return 0, stdout, stderr, rows


def is_allowed_text(line: str) -> bool:
    return bool(ALLOWED_TEXT_RE.search(line))


def scan_rows(rows: list[tuple[str, int, str]], forbidden: tuple[str, ...]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, line_no, text in rows:
        if is_allowed_text(text):
            continue
        hits = [token for token in forbidden if token in text]
        if hits:
            findings.append({"path": path, "line": line_no, "tokens": hits, "excerpt": text[:240]})
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check added diff lines for server-specific absolute paths")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--from-git")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--forbidden", action="append", default=[])
    args = parser.parse_args(argv)
    forbidden = tuple(args.forbidden) if args.forbidden else DEFAULT_FORBIDDEN
    code, stdout, stderr, rows = added_lines_from_diff(args)
    if code != 0:
        packet = {"schema": SCHEMA, "updated_at": utc_now(), "status": "fail", "error": (stderr or stdout).strip()[:800]}
        print(json.dumps(packet, indent=2, sort_keys=True) if args.json else packet["error"])
        return code
    findings = scan_rows(rows, forbidden)
    packet = {"schema": SCHEMA, "updated_at": utc_now(), "status": "pass" if not findings else "fail", "checked_added_lines": len(rows), "findings": findings}
    print(json.dumps(packet, indent=2, sort_keys=True) if args.json else packet["status"])
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
