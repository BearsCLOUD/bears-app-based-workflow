#!/usr/bin/env python3
"""Validate and report Bears goal records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/bears-goals.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/bears-goals.v1.schema.json"
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "raw log", "raw chat", "raw vpn config", "production data")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path = CATALOG) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


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
    return any(item.casefold() in text for item in FORBIDDEN)


def goals(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in catalog.get("goals", []) if isinstance(item, dict)]


def active_goal_ids(catalog: dict[str, Any] | None = None) -> set[str]:
    catalog = catalog or load()
    return {str(item.get("goal_id")) for item in goals(catalog) if item.get("status") == "active"}


def validate_catalog(path: Path = CATALOG) -> list[str]:
    catalog = load(path)
    errors = validate_json_schema(catalog, SCHEMA, path.name)
    if has_forbidden(catalog):
        errors.append(f"{path.name}: forbidden data marker present")
    seen: set[str] = set()
    for index, item in enumerate(goals(catalog)):
        goal_id = str(item.get("goal_id"))
        if goal_id in seen:
            errors.append(f"goals[{index}] duplicate goal_id: {goal_id}")
        seen.add(goal_id)
        if item.get("status") == "active" and not str(item.get("success_metric", "")).strip():
            errors.append(f"goals[{index}] active goal missing success_metric")
    if not any(item.get("status") == "active" for item in goals(catalog)):
        errors.append("at least one active goal is required")
    return errors


def status_packet() -> dict[str, Any]:
    catalog = load()
    active = [item for item in goals(catalog) if item.get("status") == "active"]
    by_priority: dict[str, int] = {}
    for item in active:
        priority = str(item.get("priority", "unknown"))
        by_priority[priority] = by_priority.get(priority, 0) + 1
    errors = validate_catalog()
    return {
        "schema": "bears-goals-status.v1",
        "status": "pass" if not errors else "fail",
        "active_goal_count": len(active),
        "active_goals": [str(item.get("goal_id")) for item in active],
        "by_priority": by_priority,
        "errors": errors,
    }


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog()
        print_packet({"schema": "bears-goals-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "status":
        packet = status_packet()
        print_packet(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
