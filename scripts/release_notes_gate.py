#!/usr/bin/env python3
"""Validate release notes coverage for behavior-changing @Bears plugin changes."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/release-notes-gate.v1.json"
RELEASE_NOTES = PLUGIN_ROOT / "assets/catalog/release-notes.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/release-notes.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/release_notes_gate/good"
BAD = PLUGIN_ROOT / "tests/fixtures/release_notes_gate/bad"
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def matches(path: str, patterns: list[str]) -> bool:
    item = normalize(path)
    return any(fnmatch.fnmatch(item, pattern) for pattern in patterns)


def validate_catalog(path: Path = CATALOG) -> list[str]:
    try:
        packet = load(path)
    except Exception as exc:
        return [f"cannot read catalog: {exc}"]
    errors: list[str] = []
    if packet.get("schema") != "bears-release-notes-gate.v1":
        errors.append("catalog schema must be bears-release-notes-gate.v1")
    if packet.get("component_issue") != "#384":
        errors.append("component_issue must be #384")
    if packet.get("owner_role") != "bears-machine-first-execution-kernel-engineer":
        errors.append("owner_role mismatch")
    behavior_patterns = packet.get("behavior_patterns")
    if not isinstance(behavior_patterns, list) or not behavior_patterns:
        errors.append("behavior_patterns must be a non-empty list")
    required_patterns = {"assets/catalog/**", "assets/schemas/**", "scripts/**", "hooks/**", "docs/reference/**", "systemd/**"}
    if isinstance(behavior_patterns, list) and not required_patterns.issubset(set(behavior_patterns)):
        errors.append("behavior_patterns must cover catalogs, schemas, scripts, hooks, and reference docs")
    notes = packet.get("release_notes")
    if notes != "assets/catalog/release-notes.v1.json":
        errors.append("release_notes must be assets/catalog/release-notes.v1.json")
    if not (PLUGIN_ROOT / "assets/catalog/release-notes.v1.json").exists():
        errors.append("release notes file is missing")
    commands = set(packet.get("commands", [])) if isinstance(packet.get("commands"), list) else set()
    if "python3 scripts/release_notes_gate.py validate" not in commands:
        errors.append("validate command missing")
    return errors


def validate_notes(path: Path = RELEASE_NOTES) -> list[str]:
    try:
        packet = load(path)
    except Exception as exc:
        return [f"cannot read release notes: {exc}"]
    errors = validate_json_schema(packet, SCHEMA, path.name)
    for index, entry in enumerate(packet.get("entries", [])):
        if not isinstance(entry, dict):
            continue
        if "#" not in str(entry.get("issue_ref", "")):
            errors.append(f"entries[{index}] issue_ref must be an issue reference")
    for index, exemption in enumerate(packet.get("exemptions", [])):
        if isinstance(exemption, dict) and not str(exemption.get("reason", "")).strip():
            errors.append(f"exemptions[{index}] reason is required")
    return errors


def changed_files_from_git(range_spec: str | None, *, staged: bool) -> list[str]:
    if staged:
        command = ["git", "diff", "--cached", "--name-only"]
    elif range_spec:
        command = ["git", "diff", "--name-only", range_spec]
    else:
        raise ValueError("from-git or --staged is required")
    proc = subprocess.run(command, cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    if proc.returncode != 0:
        raise RuntimeError("git changed-file lookup failed")
    return [normalize(line) for line in proc.stdout.splitlines() if line.strip()]


def covered_files(notes: dict[str, Any]) -> tuple[set[str], set[str]]:
    entry_files: set[str] = set()
    exemption_files: set[str] = set()
    for entry in notes.get("entries", []):
        if isinstance(entry, dict):
            entry_files.update(normalize(str(path)) for path in entry.get("files", []))
    for exemption in notes.get("exemptions", []):
        if isinstance(exemption, dict) and str(exemption.get("reason", "")).strip():
            exemption_files.update(normalize(str(path)) for path in exemption.get("files", []))
    return entry_files, exemption_files


def check_paths(paths: list[str]) -> list[str]:
    errors: list[str] = []
    catalog = load(CATALOG)
    notes = load(RELEASE_NOTES)
    behavior_patterns = [str(item) for item in catalog.get("behavior_patterns", [])]
    non_behavior_patterns = [str(item) for item in catalog.get("non_behavior_patterns", [])]
    entry_files, exemption_files = covered_files(notes)
    matched = [normalize(path) for path in paths if matches(path, behavior_patterns) and not matches(path, non_behavior_patterns)]
    for path in matched:
        if path not in entry_files and path not in exemption_files:
            errors.append(f"missing release note coverage: {path}")
    return errors


def validate_all() -> list[str]:
    errors = validate_catalog()
    errors.extend(validate_notes())
    for path in sorted(GOOD.glob("*.json")):
        errors.extend(f"good fixture failed: {item}" for item in validate_notes(path))
    for path in sorted(BAD.glob("*.json")):
        if not validate_notes(path):
            errors.append(f"bad fixture unexpectedly passed: {path.name}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    check = sub.add_parser("check")
    check.add_argument("--from-git")
    check.add_argument("--staged", action="store_true")
    check.add_argument("--changed-file", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
    else:
        errors = validate_catalog() + validate_notes()
        changed = [normalize(path) for path in args.changed_file]
        if args.from_git or args.staged:
            changed.extend(changed_files_from_git(args.from_git, staged=bool(args.staged)))
        errors.extend(check_paths(changed))
    packet = {"schema": "bears-release-notes-gate-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
