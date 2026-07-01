#!/usr/bin/env python3
"""Validate Bears workflow technical-debt matrix packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/tech-debt-matrix.v1.json"
SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/tech-debt-matrix.v1.schema.json"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.local_json_schema import validate_json_schema


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors = validate_json_schema(catalog, SCHEMA_PATH, "tech-debt-matrix")
    policy = catalog.get("policy") if isinstance(catalog, dict) else {}
    required_state_files = set(policy.get("state_files_required", [])) if isinstance(policy, dict) else set()
    required_policy_refs = {"workflow_state", "merge_authority_state", "plugin_cache_sync_state"}
    if required_policy_refs - required_state_files:
        errors.append("tech-debt-matrix.policy.state_files_required must include workflow_state, merge_authority_state, and plugin_cache_sync_state")
    seen_ids: set[str] = set()
    for index, item in enumerate(catalog.get("items", [])):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if isinstance(item_id, str):
            if item_id in seen_ids:
                errors.append(f"tech-debt-matrix.items[{index}].id must be unique")
            seen_ids.add(item_id)
        state_refs = item.get("state_refs")
        if isinstance(state_refs, dict):
            for ref_name in ("workflow_state", "merge_authority_state", "plugin_cache_sync_state"):
                if not str(state_refs.get(ref_name, "")).strip():
                    errors.append(f"tech-debt-matrix.items[{index}].state_refs.{ref_name} is required")
        if item.get("status") == "closed" and not any("local commit validation PASS" in row for row in item.get("acceptance", [])):
            errors.append(f"tech-debt-matrix.items[{index}].acceptance must keep local commit validation PASS closure evidence")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "status"))
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog = load_json(args.catalog)
    errors = validate_catalog(catalog)
    open_items = [item for item in catalog.get("items", []) if isinstance(item, dict) and item.get("status") != "closed"]
    packet = {
        "schema": "bears-tech-debt-matrix-validation.v1",
        "status": "pass" if not errors else "fail",
        "open_count": len(open_items),
        "blocker_count": sum(1 for item in open_items if item.get("severity") == "blocker"),
        "errors": errors,
    }
    if args.json or args.command == "status":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(packet["status"])
        for error in errors:
            print(error, file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
