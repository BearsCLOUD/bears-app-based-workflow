#!/usr/bin/env python3
"""Validate the @Bears enterprise issue automation release manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PLUGIN_ROOT / "assets/catalog/enterprise-issue-automation-release.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/enterprise-issue-automation-release.v1.schema.json"
CLOSEOUT = PLUGIN_ROOT / "assets/catalog/commit-closeout.v1.json"
EXPECTED_ORDER = [394, 390, 384, 385, 395, 396, 397, 398, 399, 400, 401, 403, 402]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_delivery_id() -> str:
    return str(load(CLOSEOUT).get("canonical_delivery_id", "bears-governance-kernel-v1"))


def validate_manifest(path: Path = MANIFEST) -> list[str]:
    packet = load(path)
    errors = validate_json_schema(packet, SCHEMA, path.name)
    canonical = canonical_delivery_id()
    if packet.get("release_id") != canonical:
        errors.append(f"release_id must equal canonical delivery id {canonical}")
    if packet.get("delivery_id") != canonical:
        errors.append(f"delivery_id must equal canonical delivery id {canonical}")
    if packet.get("issue_order") != EXPECTED_ORDER:
        errors.append("issue_order must match enterprise dependency order")
    completed = packet.get("completed_issues")
    if not isinstance(completed, list):
        errors.append("completed_issues must be a list")
        completed = []
    if completed != EXPECTED_ORDER[: len(completed)]:
        errors.append("completed_issues must be a prefix of issue_order")
    active = packet.get("active_issue")
    expected_active = EXPECTED_ORDER[len(completed)] if len(completed) < len(EXPECTED_ORDER) else None
    if active != expected_active:
        errors.append("active_issue must be the next issue after completed_issues")
    if packet.get("dependency_policy", {}).get("max_active") != 1:
        errors.append("max_active must be 1")
    if packet.get("dependency_policy", {}).get("one_release_manifest") is not True:
        errors.append("one_release_manifest must be true")
    if packet.get("hook_policy", {}).get("no_issue_solving_from_hooks") is not True:
        errors.append("hooks must not solve issues")
    if packet.get("service_policy", {}).get("auto_install") is not False:
        errors.append("service auto-install must be false")
    if packet.get("closeout_policy", {}).get("canonical_delivery_id_required") != canonical:
        errors.append("closeout policy must require canonical delivery id")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args(argv)
    errors = validate_manifest(Path(args.manifest))
    print(json.dumps({"schema": "bears-enterprise-issue-automation-release-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
