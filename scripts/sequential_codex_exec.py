#!/usr/bin/env python3
"""Validate sequential Codex Exec adapter policy for @Bears."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/codex-exec-adapter.v1.json"
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret=", ".env=", "credential=")


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


def validate_catalog(path: Path = CATALOG) -> list[str]:
    if not path.exists():
        return ["codex exec adapter catalog missing"]
    packet = load(path)
    errors: list[str] = []
    if packet.get("schema") != "bears-codex-exec-adapter.v1":
        errors.append("catalog schema mismatch")
    if "execute" not in packet.get("commands", []):
        errors.append("catalog commands must include execute")
    if has_forbidden(packet):
        errors.append("catalog contains forbidden data marker")
    return errors


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    execute = sub.add_parser("execute")
    execute.add_argument("--plan", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog()
        print_packet({"schema": "bears-sequential-codex-exec-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "execute":
        plan = Path(args.plan)
        errors = [] if plan.exists() else [f"plan missing: {plan}"]
        print_packet({"schema": "bears-sequential-codex-exec-execute.v1", "status": "pass" if not errors else "fail", "errors": errors, "plan": str(plan)})
        return 0 if not errors else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
