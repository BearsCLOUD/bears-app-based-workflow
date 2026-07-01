#!/usr/bin/env python3
"""Validate and render the Bears Telegram workflow catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/telegram-workflow-catalog.v1.json"

REQUIRED_WORKFLOW_FIELDS = {
    "name",
    "trigger",
    "owning_skill",
    "reference",
    "input_packet",
    "output_packet",
    "validation",
    "security_rules",
    "reuse_targets",
}
REQUIRED_SURFACE_FIELDS = {
    "name",
    "owner_group",
    "surface_type",
    "current_framework_status",
    "target_state",
    "migration_status",
    "test_status",
    "exception_status",
    "trust_status",
    "last_verified",
    "evidence_source",
    "next_action",
}
ALLOWED_TRUST_STATUS = {"trusted", "candidate", "deferred", "blocked", "exception"}


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"catalog not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("catalog root must be an object")
    return data


def validate_catalog(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "bears-telegram-workflow-catalog.v1":
        errors.append("schema must be bears-telegram-workflow-catalog.v1")
    if not data.get("updated"):
        errors.append("updated date is required")

    workflows = data.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        errors.append("workflows must be a non-empty list")
    else:
        names: set[str] = set()
        for index, item in enumerate(workflows):
            if not isinstance(item, dict):
                errors.append(f"workflows[{index}] must be an object")
                continue
            missing = REQUIRED_WORKFLOW_FIELDS - item.keys()
            if missing:
                errors.append(f"workflow {item.get('name', index)} missing: {sorted(missing)}")
            name = item.get("name")
            if name in names:
                errors.append(f"duplicate workflow name: {name}")
            if name:
                names.add(str(name))
            for list_field in ("input_packet", "output_packet", "validation", "security_rules", "reuse_targets"):
                if not isinstance(item.get(list_field), list) or not item.get(list_field):
                    errors.append(
                        f"workflow {item.get('name', index)} {list_field} must be non-empty list"
                    )

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("surfaces must be a non-empty list")
    else:
        names = set()
        for index, item in enumerate(surfaces):
            if not isinstance(item, dict):
                errors.append(f"surfaces[{index}] must be an object")
                continue
            missing = REQUIRED_SURFACE_FIELDS - item.keys()
            if missing:
                errors.append(f"surface {item.get('name', index)} missing: {sorted(missing)}")
            name = item.get("name")
            if name in names:
                errors.append(f"duplicate surface name: {name}")
            if name:
                names.add(str(name))
            trust = item.get("trust_status")
            if trust not in ALLOWED_TRUST_STATUS:
                errors.append(f"surface {item.get('name', index)} invalid trust_status: {trust}")
            if not isinstance(item.get("evidence_source"), list) or not item.get("evidence_source"):
                errors.append(f"surface {item.get('name', index)} evidence_source must be non-empty list")

    for key in ("security_rules", "workspace_rules"):
        value = data.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"{key} must be a non-empty list")
    migration_backlog = data.get("migration_backlog")
    if migration_backlog is not None:
        if not isinstance(migration_backlog, str) or not migration_backlog:
            errors.append("migration_backlog must be a non-empty relative path when set")
        elif not (PLUGIN_ROOT / migration_backlog).is_file():
            errors.append(f"migration_backlog path does not exist: {migration_backlog}")
    return errors


def render_summary(data: dict[str, Any]) -> str:
    lines = [
        f"schema: {data.get('schema')}",
        f"updated: {data.get('updated')}",
        "",
        "workflows:",
    ]
    for item in data.get("workflows", []):
        lines.append(f"- {item.get('name')} -> {item.get('owning_skill')} ({item.get('trigger')})")
        if item.get("input_packet"):
            lines.append(f"  input_packet: {len(item.get('input_packet', []))} fields")
        if item.get("output_packet"):
            lines.append(f"  output_packet: {len(item.get('output_packet', []))} fields")
    lines.append("")
    if data.get("migration_backlog"):
        lines.append(f"migration_backlog: {data.get('migration_backlog')}")
        lines.append("")
    lines.append("surfaces:")
    for item in data.get("surfaces", []):
        lines.append(
            "- {name}: {migration_status}, trust={trust_status}, tests={test_status}".format(**item)
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "summary", "json"])
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args(argv)

    try:
        data = load_catalog(args.catalog)
        errors = validate_catalog(data)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.command == "summary":
        print(render_summary(data))
    elif args.command == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"catalog ok: {args.catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
