#!/usr/bin/env python3
"""Deterministic git workflow runner for bounded @bears packets."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PLUGIN_ROOT / "assets/schemas/git-workflow-runner-packet.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/deterministic_runners/good/git-workflow.json"
BAD = PLUGIN_ROOT / "tests/fixtures/deterministic_runners/bad/forbidden.json"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "production data")
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def has_forbidden(value: Any) -> bool:
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN)


def run_git(repo: Path, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=str(repo), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10, env=clean_env())
    return proc.returncode, (proc.stdout or proc.stderr).strip()[:400]


def in_allowed(path: str, allowed: list[str]) -> bool:
    norm = path.strip().strip("/")
    return any(norm == item.strip().strip("/") or norm.startswith(item.strip().strip("/").rstrip("/") + "/") for item in allowed)


def validate_packet(packet: dict[str, Any], label: str = "packet") -> list[str]:
    errors = validate_json_schema(packet, SCHEMA, label)
    if has_forbidden(packet):
        errors.append(f"{label}: restricted data marker detected")
    if packet.get("forbid_force_push") is not True:
        errors.append(f"{label}: forbid_force_push must be true")
    return errors


def run_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors = validate_packet(packet)
    repo = Path(str(packet.get("repo_path", PLUGIN_ROOT))).resolve()
    branch_code, branch = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    head_code, head = run_git(repo, ["rev-parse", "HEAD"])
    staged_code, staged = run_git(repo, ["diff", "--cached", "--name-only"])
    staged_files = [line.strip() for line in staged.splitlines() if line.strip()] if staged_code == 0 else []
    if branch_code != 0:
        errors.append("branch lookup failed")
    elif branch != packet.get("expected_branch"):
        errors.append("expected branch mismatch")
    if head_code != 0:
        errors.append("HEAD lookup failed")
    elif packet.get("start_sha") and not head.startswith(str(packet.get("start_sha"))):
        errors.append("start_sha mismatch")
    for item in staged_files:
        if not in_allowed(item, list(packet.get("allowed_files", []))):
            errors.append(f"staged file outside allowed_files: {item}")
    status = "pass" if not errors else "fail"
    evidence = {
        "schema": "bears-deterministic-runner-result.v1",
        "runner": "git_workflow_runner",
        "command_id": packet.get("command_id"),
        "status": status,
        "updated_at": utc_now(),
        "exit_code": 0 if status == "pass" else 1,
        "affected_files": staged_files,
        "sanitized_summary": "git workflow checks passed" if status == "pass" else "; ".join(errors)[:800],
    }
    path = PLUGIN_ROOT / "runtime/deterministic-runners/git" / f"{packet.get('command_id', 'unknown')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def validate_all() -> list[str]:
    errors = validate_packet(load(GOOD), "good")
    if not validate_packet(load(BAD), "bad"):
        errors.append("bad fixture unexpectedly passed")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    run = sub.add_parser("run")
    run.add_argument("--packet", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        print(json.dumps({"schema": "bears-runner-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
        return 0 if not errors else 1
    result = run_packet(load(Path(args.packet)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
