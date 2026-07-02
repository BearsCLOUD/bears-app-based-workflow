#!/usr/bin/env python3
"""Validate bounded GitHub issue autostart policy for @Bears."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/issue-autostart.v1.json"
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
        return ["issue autostart catalog missing"]
    packet = load(path)
    errors: list[str] = []
    if packet.get("schema") != "bears-issue-autostart.v1":
        errors.append("catalog schema mismatch")
    for required in ("discover", "enqueue", "run-next", "status", "pause", "resume", "drain", "cancel"):
        if required not in packet.get("commands", []):
            errors.append(f"catalog commands missing {required}")
    if has_forbidden(packet):
        errors.append("catalog contains forbidden data marker")
    return errors


def status_packet() -> dict[str, Any]:
    errors = validate_catalog()
    return {"schema": "bears-issue-autostart-status.v1", "status": "pass" if not errors else "fail", "errors": errors}


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "roadmap-status", "status", "discover", "enqueue", "run-next", "pause", "resume", "drain", "cancel"):
        sub.add_parser(name).add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        packet = status_packet()
    else:
        packet = status_packet() | {"command": args.command}
    print_packet(packet)
    return 0 if packet["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
