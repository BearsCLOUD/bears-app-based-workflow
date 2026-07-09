#!/usr/bin/env python3
"""Validate repo-visible external review audit packets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/external-review-audit.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/external-review-audit.v1.schema.json"
SUMMARY_SCHEMA = "bears-external-review-delivery-summary.v1"
COMMANDS = (
    "python3 scripts/external_review_audit.py validate",
    "python3 scripts/external_review_audit.py check-delivery --delivery-id <id> --json",
)

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> Any:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    """Return a plugin-root relative path when possible."""
    try:
        return path.resolve().relative_to(PLUGIN_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def strings(value: Any) -> list[str]:
    """Flatten strings from nested JSON values."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def forbidden_markers(catalog: dict[str, Any]) -> tuple[str, ...]:
    """Return forbidden evidence markers from the catalog."""
    return tuple(str(item) for item in catalog.get("forbidden_content", []))


def has_forbidden(value: Any, catalog: dict[str, Any]) -> bool:
    """Detect forbidden raw content markers in a packet."""
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in forbidden_markers(catalog))


def validate_catalog() -> list[str]:
    """Validate the external review audit catalog and referenced summaries."""
    errors: list[str] = []
    if not CATALOG.exists():
        return ["external review audit catalog missing"]
    if not SCHEMA.exists():
        errors.append("external review audit schema missing")
    catalog = load(CATALOG)
    errors.extend(validate_json_schema(catalog, SCHEMA, CATALOG.name))
    for command in COMMANDS:
        if command not in catalog.get("commands", []):
            errors.append(f"catalog missing command: {command}")
    required = set(catalog.get("required_chain", []))
    expected = {"github_issue_state", "delivery_manifest", "decision_ledger", "changelog_or_release_note", "validation_proof", "bears_doctor_closeout_summary"}
    if required != expected:
        errors.append("required_chain must contain the six external review links")
    content_packet = {key: value for key, value in catalog.items() if key != "forbidden_content"}
    if has_forbidden(content_packet, catalog):
        errors.append("catalog contains forbidden raw data marker")
    for row in catalog.get("deliveries", []):
        path = PLUGIN_ROOT / str(row.get("summary_path", ""))
        if not path.exists():
            errors.append(f"delivery summary missing: {rel(path)}")
    return errors


def delivery_record(delivery_id: str, catalog: dict[str, Any]) -> dict[str, Any] | None:
    """Find a configured delivery summary record."""
    for row in catalog.get("deliveries", []):
        if row.get("delivery_id") == delivery_id:
            return row
    return None


def validate_summary(summary: dict[str, Any], delivery_id: str, catalog: dict[str, Any]) -> list[str]:
    """Validate one repo-visible delivery summary packet."""
    errors: list[str] = []
    if summary.get("schema") != SUMMARY_SCHEMA:
        errors.append("summary schema mismatch")
    if summary.get("delivery_id") != delivery_id:
        errors.append("summary delivery_id mismatch")
    if summary.get("status") not in {"externally_reviewable", "pass"}:
        errors.append("summary status is not externally reviewable")
    chain = summary.get("evidence_chain", {})
    for item in catalog.get("required_chain", []):
        entry = chain.get(item)
        if not isinstance(entry, dict):
            errors.append(f"evidence_chain missing: {item}")
            continue
        if entry.get("status") != "pass":
            errors.append(f"evidence_chain {item} is not pass")
        path_value = str(entry.get("path") or entry.get("reference") or "")
        if not path_value:
            errors.append(f"evidence_chain {item} missing path or reference")
    summary_path = str(summary.get("summary_path", ""))
    if not summary_path.startswith("docs/audits/"):
        errors.append("summary_path must be repo-visible under docs/audits")
    if has_forbidden(summary, catalog):
        errors.append("summary contains forbidden raw data marker")
    return errors


def check_delivery(delivery_id: str) -> dict[str, Any]:
    """Check that a delivery has repo-visible external review proof."""
    catalog = load(CATALOG)
    errors = validate_catalog()
    record = delivery_record(delivery_id, catalog)
    if not record:
        errors.append(f"delivery not registered for external review: {delivery_id}")
        return {
            "schema": "bears-external-review-delivery-check.v1",
            "status": "fail",
            "delivery_id": delivery_id,
            "summary_path": None,
            "errors": errors,
        }
    path = PLUGIN_ROOT / str(record["summary_path"])
    summary: dict[str, Any] = {}
    if path.exists():
        summary = load(path)
        errors.extend(validate_summary(summary, delivery_id, catalog))
    return {
        "schema": "bears-external-review-delivery-check.v1",
        "status": "pass" if not errors else "fail",
        "delivery_id": delivery_id,
        "summary_path": rel(path),
        "issue": record.get("issue"),
        "evidence_chain": summary.get("evidence_chain", {}),
        "errors": errors,
    }


def validate_packet() -> dict[str, Any]:
    """Build the top-level validator packet."""
    errors = validate_catalog()
    return {
        "schema": "bears-external-review-audit-validation.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    check = sub.add_parser("check-delivery")
    check.add_argument("--delivery-id", required=True)
    check.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the external review audit CLI."""
    args = build_parser().parse_args(argv)
    packet = validate_packet() if args.command == "validate" else check_delivery(str(args.delivery_id))
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
