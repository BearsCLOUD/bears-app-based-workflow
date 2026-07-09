#!/usr/bin/env python3
"""Validate JSON-first Bears metadata store policy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
POLICY = PLUGIN_ROOT / "assets/catalog/metadata-store-policy.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/metadata-store-policy.v1.schema.json"
EXPORTS = [
    PLUGIN_ROOT / "assets/catalog/workspace-semantic-graph.v1.json",
    PLUGIN_ROOT / "assets/catalog/workspace-dictionary.v1.json",
    POLICY,
]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy() -> list[str]:
    errors: list[str] = []
    if not POLICY.exists():
        return ["metadata store policy missing"]
    packet = load(POLICY)
    errors.extend(validate_json_schema(packet, SCHEMA, POLICY.name))
    if packet.get("source_of_truth") != "validated_json_in_git":
        errors.append("validated JSON in git must remain source of truth")
    for row in packet.get("materialized_stores", []):
        if row.get("authority") != "cache_only":
            errors.append(f"external store is not cache_only: {row.get('store')}")
    return errors


def export_json() -> dict[str, Any]:
    packets = {path.relative_to(PLUGIN_ROOT).as_posix(): load(path) for path in EXPORTS if path.exists()}
    return {"schema": "bears-metadata-store-export.v1", "status": "pass", "source_of_truth": "validated_json_in_git", "packets": packets}


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-policy")
    exp = sub.add_parser("export-json")
    exp.add_argument("--json", action="store_true")
    doc = sub.add_parser("doctor")
    doc.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "validate-policy":
        errors = validate_policy()
        print_packet({"schema": "bears-metadata-store-policy-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "export-json":
        print_packet(export_json())
        return 0
    if args.command == "doctor":
        errors = validate_policy()
        print_packet({"schema": "bears-metadata-store-doctor.v1", "status": "pass" if not errors else "fail", "errors": errors, "authority": "validated_json_in_git"})
        return 0 if not errors else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
