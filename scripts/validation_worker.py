#!/usr/bin/env python3
"""Validate and create bounded async validation worker packets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/async-validation.v1.json"
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
        return [f"catalog missing: {path.relative_to(PLUGIN_ROOT)}"]
    try:
        packet = load(path)
    except Exception as exc:
        return [f"catalog read error: {exc}"]
    errors: list[str] = []
    if not str(packet.get("schema", "")).startswith("bears-"):
        errors.append("catalog schema must be a Bears schema")
    if has_forbidden(packet):
        errors.append("catalog contains forbidden data marker")
    return errors


def create_fixer_step(remediation: Path, output: Path) -> list[str]:
    if not remediation.exists():
        return [f"remediation missing: {remediation}"]
    packet = {
        "schema": "bears-validation-fixer-step.v1",
        "status": "queued",
        "remediation": str(remediation),
        "allowed_actions": ["read remediation packet", "prepare bounded fix assignment"],
        "forbidden_actions": ["secret read", "raw log read", "production data read"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return []


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    fixer = sub.add_parser("create-fixer-step")
    fixer.add_argument("--remediation", required=True)
    fixer.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog()
        print_packet({"schema": "bears-validation-worker-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "create-fixer-step":
        errors = create_fixer_step(Path(args.remediation), Path(args.output))
        print_packet({"schema": "bears-validation-worker-create-fixer-step.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
