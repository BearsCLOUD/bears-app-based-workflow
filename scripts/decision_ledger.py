#!/usr/bin/env python3
"""Validate compact @bears decision ledger records."""
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
LEDGER = PLUGIN_ROOT / "assets/catalog/decision-ledger.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/decision-ledger.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/decision_ledger/good/minimal.json"
BAD = PLUGIN_ROOT / "tests/fixtures/decision_ledger/bad/unresolved.json"
REQUIRES_DECISION_PREFIXES = ("assets/catalog/", "assets/schemas/", "hooks/", "scripts/")
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "production data")
REPORT_RECORD_LIMIT = 50

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


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def forbidden(value: Any) -> bool:
    text = "\n".join(strings(value)).casefold()
    return any(item.casefold() in text for item in FORBIDDEN)


def records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in ledger.get("records", []) if isinstance(item, dict)]


def report_records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the bounded record slice used by compact ledger reports."""
    return records(ledger)[-REPORT_RECORD_LIMIT:]


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/")


def affects(record: dict[str, Any], path: str) -> bool:
    target = normalize(path)
    for item in record.get("affected_paths", []):
        pattern = normalize(str(item))
        if target == pattern or fnmatch.fnmatch(target, pattern):
            return True
    return False


def record_errors(record: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"records[{index}] {record.get('decision_id', '<missing>')}"
    if record.get("status") == "accepted" and record.get("unresolved_inputs"):
        errors.append(f"{prefix}: accepted decision has unresolved_inputs")
    if record.get("status") == "accepted" and record.get("contradictions"):
        errors.append(f"{prefix}: accepted decision has contradictions")
    if record.get("redaction") != "safe":
        errors.append(f"{prefix}: record is not safe for durable storage")
    if forbidden(record):
        errors.append(f"{prefix}: restricted data marker detected")
    return errors


def validate_ledger(path: Path = LEDGER) -> list[str]:
    ledger = load(path)
    errors = validate_json_schema(ledger, SCHEMA, path.name)
    seen: set[str] = set()
    for index, record in enumerate(records(ledger)):
        decision_id = str(record.get("decision_id"))
        if decision_id in seen:
            errors.append(f"records[{index}] {decision_id}: duplicate decision_id")
        seen.add(decision_id)
        errors.extend(record_errors(record, index))
    return errors


def changed_files(*, staged: bool, range_spec: str | None) -> list[str]:
    if staged:
        command = ["git", "diff", "--cached", "--name-only"]
    elif range_spec:
        command = ["git", "diff", "--name-only", range_spec]
    else:
        return []
    proc = subprocess.run(command, cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30, env=clean_env())
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def decision_required(path: str) -> bool:
    item = normalize(path)
    return item != "assets/catalog/decision-ledger.v1.json" and item.startswith(REQUIRES_DECISION_PREFIXES)


def missing_required_decisions(paths: list[str], ledger: dict[str, Any]) -> list[str]:
    accepted = [record for record in records(ledger) if record.get("status") == "accepted" and not record.get("unresolved_inputs") and not record.get("contradictions")]
    errors: list[str] = []
    for path in paths:
        if decision_required(path) and not any(affects(record, path) for record in accepted):
            errors.append(f"missing accepted decision for {normalize(path)}")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    errors = validate_ledger(LEDGER)
    if validate_ledger(GOOD):
        errors.append("good fixture failed")
    if not validate_ledger(BAD):
        errors.append("bad fixture unexpectedly passed")
    print(json.dumps({"schema": "bears-decision-ledger-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_add(args: argparse.Namespace) -> int:
    ledger = load(LEDGER)
    record = {
        "decision_id": args.decision_id,
        "status": "accepted",
        "scope_id": args.scope_id,
        "change_type": args.change_type,
        "owner_issue": args.issue,
        "owner_role": args.owner_role,
        "affected_paths": args.affected_path,
        "decision": args.decision,
        "rationale": args.rationale,
        "unresolved_inputs": [],
        "contradictions": [],
        "redaction": "safe",
    }
    ledger["records"].append(record)
    ledger["updated"] = utc_today()
    write(LEDGER, ledger)
    print(json.dumps({"schema": "bears-decision-ledger-event.v1", "status": "added", "decision_id": args.decision_id}, indent=2, sort_keys=True))
    return 0


def command_check_required(args: argparse.Namespace) -> int:
    paths = list(args.changed_file or []) + changed_files(staged=bool(args.staged), range_spec=args.from_git)
    errors = missing_required_decisions(paths, load(LEDGER))
    print(json.dumps({"schema": "bears-decision-ledger-required.v1", "status": "pass" if not errors else "fail", "paths": sorted(set(paths)), "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_check_record(args: argparse.Namespace) -> int:
    ledger = load(LEDGER)
    matched = [record for record in records(ledger) if record.get("decision_id") == args.decision_id]
    errors = ["decision record missing"] if not matched else record_errors(matched[0], 0)
    print(json.dumps({"schema": "bears-decision-ledger-record.v1", "status": "pass" if not errors else "fail", "decision_id": args.decision_id, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_report(args: argparse.Namespace) -> int:
    ledger = load(LEDGER)
    errors = validate_ledger(LEDGER)
    rendered_records = report_records(ledger)
    print(
        json.dumps(
            {
                "schema": "bears-decision-ledger-report.v1",
                "status": "pass" if not errors else "fail",
                "record_count": len(rendered_records),
                "total_record_count": len(records(ledger)),
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=command_validate)
    add = sub.add_parser("add")
    add.add_argument("--decision-id", required=True)
    add.add_argument("--scope-id", required=True)
    add.add_argument("--change-type", required=True, choices=["policy", "workflow", "role", "schema", "hook", "validation", "artifact"])
    add.add_argument("--issue", required=True)
    add.add_argument("--owner-role", required=True)
    add.add_argument("--affected-path", action="append", required=True)
    add.add_argument("--decision", required=True)
    add.add_argument("--rationale", required=True)
    add.set_defaults(func=command_add)
    required = sub.add_parser("check-required")
    required.add_argument("--changed-file", action="append", default=[])
    required.add_argument("--from-git")
    required.add_argument("--staged", action="store_true")
    required.set_defaults(func=command_check_required)
    record = sub.add_parser("check-record")
    record.add_argument("--decision-id", required=True)
    record.set_defaults(func=command_check_record)
    report = sub.add_parser("emit-report")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=command_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
