#!/usr/bin/env python3
"""Maintain the @bears plugin artifact registry."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = PLUGIN_ROOT / "assets/catalog/artifact-registry.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/artifact-registry.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/artifact_registry/good/minimal.json"
BAD = PLUGIN_ROOT / "tests/fixtures/artifact_registry/bad/missing-owner.json"
KNOWN_TYPES = {"schema", "catalog", "script", "test", "fixture", "doc", "runtime", "cache", "local_proof"}
TRACKED_LIFECYCLES = {"durable", "generated_tracked", "fixture", "schema", "doc", "test", "script", "catalog"}
RUNTIME_PREFIXES = ("runtime/", ".pytest_cache/", ".ruff_cache/", "__pycache__/")
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV:
        env.pop(key, None)
    return env


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def records(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in registry.get("records", []) if isinstance(item, dict)]


def match_record(registry: dict[str, Any], path: str) -> dict[str, Any] | None:
    target = normalize(path)
    for record in records(registry):
        item = normalize(str(record.get("path", "")))
        if item.endswith("/") and target.startswith(item):
            return record
        if target == item or fnmatch.fnmatch(target, item):
            return record
    return None


def record_errors(record: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"records[{index}] {record.get('path', '<missing>')}"
    if record.get("artifact_type") not in KNOWN_TYPES:
        errors.append(f"{prefix}: unknown artifact_type")
    if record.get("git_tracked") is True and not (record.get("owner_issue") or record.get("scope_id")):
        errors.append(f"{prefix}: missing owner_issue or scope_id")
    if not record.get("owner_role"):
        errors.append(f"{prefix}: missing owner_role")
    if record.get("git_tracked") is True and record.get("lifecycle") not in TRACKED_LIFECYCLES:
        errors.append(f"{prefix}: tracked file has untracked lifecycle")
    if record.get("git_tracked") is False and record.get("lifecycle") in TRACKED_LIFECYCLES:
        errors.append(f"{prefix}: untracked file has tracked lifecycle")
    if record.get("lifecycle") == "generated_tracked" and not record.get("source_of_truth"):
        errors.append(f"{prefix}: generated file missing source_of_truth")
    if record.get("lifecycle") in {"durable", "schema", "script", "catalog"} and not record.get("validation"):
        errors.append(f"{prefix}: durable artifact missing validation")
    if record.get("decision_ref_required") is True and not record.get("decision_ref"):
        errors.append(f"{prefix}: decision_ref required")
    return errors


def validate_registry(path: Path = REGISTRY) -> list[str]:
    registry = load(path)
    errors = validate_json_schema(registry, SCHEMA, path.name)
    seen: set[str] = set()
    for index, record in enumerate(records(registry)):
        item = normalize(str(record.get("path", "")))
        if item in seen:
            errors.append(f"records[{index}] {item}: duplicate path")
        seen.add(item)
        errors.extend(record_errors(record, index))
    return errors


def added_files_from_git(range_spec: str | None, *, staged: bool) -> list[str]:
    if staged:
        command = ["git", "diff", "--cached", "--name-status", "--diff-filter=A"]
    elif range_spec:
        command = ["git", "diff", "--name-status", "--diff-filter=A", range_spec]
    else:
        raise ValueError("from-git or --staged is required")
    proc = subprocess.run(command, cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    if proc.returncode != 0:
        raise RuntimeError("git added-file lookup failed")
    result: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            result.append(parts[-1])
    return result


def check_paths(paths: list[str], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        item = normalize(path)
        if item.startswith(RUNTIME_PREFIXES):
            errors.append(f"runtime or temporary file staged: {item}")
            continue
        record = match_record(registry, item)
        if not record:
            errors.append(f"missing artifact registry entry: {item}")
            continue
        if record.get("git_tracked") is not True:
            errors.append(f"registered as untracked but staged: {item}")
    return errors


def default_record(path: str, artifact_type: str, issue: str, owner_role: str) -> dict[str, Any]:
    lifecycle = artifact_type if artifact_type in TRACKED_LIFECYCLES else "durable"
    return {
        "path": normalize(path),
        "artifact_type": artifact_type,
        "lifecycle": lifecycle,
        "git_tracked": True,
        "owner_issue": issue,
        "owner_role": owner_role,
        "allowed_writers": [owner_role],
        "validation": ["python3 scripts/artifact_registry.py validate"],
        "changelog_required": False,
        "decision_ref_required": False,
        "source_of_truth_status": "canonical",
    }


def command_register(args: argparse.Namespace) -> int:
    registry = load(REGISTRY)
    if match_record(registry, args.path):
        packet = {"schema": "bears-artifact-registry-event.v1", "status": "exists", "path": normalize(args.path)}
    else:
        registry["records"].append(default_record(args.path, args.type, args.issue, args.owner_role))
        registry["updated"] = utc_today()
        write(REGISTRY, registry)
        packet = {"schema": "bears-artifact-registry-event.v1", "status": "registered", "path": normalize(args.path)}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def command_register_from_plan(args: argparse.Namespace) -> int:
    plan = load(Path(args.plan))
    count = 0
    for item in plan.get("artifacts", []):
        if isinstance(item, dict) and item.get("path"):
            command_register(argparse.Namespace(path=item["path"], type=item.get("artifact_type", "doc"), issue=item.get("owner_issue", "#unknown"), owner_role=item.get("owner_role", "bears-machine-first-execution-kernel-engineer")))
            count += 1
    print(json.dumps({"schema": "bears-artifact-registry-event.v1", "status": "registered_from_plan", "count": count}, indent=2, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    errors = validate_registry(REGISTRY)
    good_errors = validate_registry(GOOD)
    if good_errors:
        errors.extend(f"good fixture failed: {item}" for item in good_errors)
    if not validate_registry(BAD):
        errors.append("bad fixture unexpectedly passed")
    print(json.dumps({"schema": "bears-artifact-registry-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_check_path(args: argparse.Namespace) -> int:
    errors = check_paths([args.path], load(REGISTRY))
    print(json.dumps({"schema": "bears-artifact-registry-check.v1", "status": "pass" if not errors else "fail", "path": normalize(args.path), "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_check_added(args: argparse.Namespace) -> int:
    paths = added_files_from_git(args.from_git, staged=bool(args.staged))
    errors = check_paths(paths, load(REGISTRY))
    print(json.dumps({"schema": "bears-artifact-registry-added-files.v1", "status": "pass" if not errors else "fail", "paths": paths, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_report(args: argparse.Namespace) -> int:
    registry = load(REGISTRY)
    tracked = [record for record in records(registry) if record.get("git_tracked") is True]
    runtime = [record for record in records(registry) if record.get("git_tracked") is False]
    packet = {"schema": "bears-artifact-registry-report.v1", "status": "pass" if not validate_registry(REGISTRY) else "fail", "tracked_count": len(tracked), "runtime_count": len(runtime), "baseline_existing_files_exempt": registry.get("baseline", {}).get("existing_files_exempt")}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=command_validate)
    register = sub.add_parser("register")
    register.add_argument("--path", required=True)
    register.add_argument("--type", required=True, choices=sorted(KNOWN_TYPES))
    register.add_argument("--issue", required=True)
    register.add_argument("--owner-role", required=True)
    register.set_defaults(func=command_register)
    plan = sub.add_parser("register-from-plan")
    plan.add_argument("--plan", required=True)
    plan.set_defaults(func=command_register_from_plan)
    check = sub.add_parser("check-path")
    check.add_argument("--path", required=True)
    check.set_defaults(func=command_check_path)
    added = sub.add_parser("check-added-files")
    added.add_argument("--from-git")
    added.add_argument("--staged", action="store_true")
    added.set_defaults(func=command_check_added)
    report = sub.add_parser("emit-report")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=command_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
