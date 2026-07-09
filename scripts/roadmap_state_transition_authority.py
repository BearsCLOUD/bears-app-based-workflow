#!/usr/bin/env python3
"""Validate roadmap state-transition authority before reconcile promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/roadmap-state-transition-authority.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/roadmap-state-transition-authority.v1.schema.json"
DEFAULT_ROADMAP = PLUGIN_ROOT / "assets/catalog/workflow-roadmap.v1.json"
RESULT_SCHEMA = "bears-roadmap-state-transition-authority-result.v1"
TRANSITION_PACKET_SCHEMA = "bears-roadmap-state-transition-authority-transition.v1"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.local_json_schema import validate_json_schema
from scripts import workflow_roadmap


def load_json(path: Path) -> Any:
    """Load a JSON file and return its decoded value."""
    return json.loads(path.read_text(encoding="utf-8"))


def source_hash(path: Path) -> str:
    """Return a stable sha256 hash for the checked roadmap file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_catalog() -> list[str]:
    """Validate the transition authority catalog and schema-bound values."""
    packet = load_json(CATALOG)
    errors = validate_json_schema(packet, SCHEMA, "roadmap-state-transition-authority")
    if packet.get("required_transition_packet_schema") != TRANSITION_PACKET_SCHEMA:
        errors.append("required_transition_packet_schema must match transition packet schema")
    return errors


def reconcile_check(roadmap_path: Path) -> dict[str, Any]:
    """Return blocked and allowed roadmap reconcile transitions."""
    roadmap = workflow_roadmap.load(roadmap_path)
    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    manual_review_promotions: list[dict[str, Any]] = []
    evidence_only_promotions: list[dict[str, Any]] = []
    for node in workflow_roadmap.nodes(roadmap):
        decision = workflow_roadmap.reconcile_transition_decision(node)
        if decision["status"] == "noop":
            continue
        if decision["to_state"] != "validated":
            continue
        row = {
            "node_id": str(node.get("node_id")),
            "issue_ref": node.get("issue") if node.get("issue") != "null" else None,
            "from_state": str(node.get("state")),
            "to_state": decision["to_state"],
            "reason": decision["reason"],
            "required_gate_refs": decision.get("required_gate_refs", []),
        }
        if decision["status"] == "allowed":
            allowed.append(row)
        else:
            blocked.append(row)
            if row["from_state"] == "manual_review" or node.get("autostart_policy") == "manual_review":
                manual_review_promotions.append(row)
            if row["reason"] == "evidence_file_is_not_transition_authority":
                evidence_only_promotions.append(row)
    return {
        "schema": RESULT_SCHEMA,
        "status": "blocked" if blocked else "pass",
        "roadmap_ref": str(roadmap_path),
        "checked_nodes": len(workflow_roadmap.nodes(roadmap)),
        "allowed_transitions": allowed,
        "blocked_transitions": blocked,
        "manual_review_promotions": manual_review_promotions,
        "evidence_only_promotions": evidence_only_promotions,
        "source_hash": source_hash(roadmap_path),
    }


def doctor() -> dict[str, Any]:
    """Return bounded doctor status for roadmap transition authority."""
    errors = validate_catalog()
    result = reconcile_check(DEFAULT_ROADMAP)
    return {
        "schema": "bears-roadmap-state-transition-authority-doctor.v1",
        "status": "pass" if not errors and result["schema"] == RESULT_SCHEMA else "fail",
        "component_issue": "#517",
        "catalog_errors": errors,
        "reconcile_status": result["status"],
        "blocked_transition_count": len(result["blocked_transitions"]),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--json", action="store_true")
    check_cmd = sub.add_parser("reconcile-check")
    check_cmd.add_argument("--roadmap", type=Path, default=DEFAULT_ROADMAP)
    check_cmd.add_argument("--json", action="store_true")
    doctor_cmd = sub.add_parser("doctor")
    doctor_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the roadmap transition authority CLI."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_catalog()
            packet = {"schema": "bears-roadmap-state-transition-authority-validate.v1", "status": "pass" if not errors else "fail", "errors": errors}
            print(json.dumps(packet, indent=2, sort_keys=True) if args.json else ("roadmap state transition authority ok" if not errors else "\n".join(errors)))
            return 0 if not errors else 1
        if args.command == "reconcile-check":
            packet = reconcile_check(args.roadmap)
            print(json.dumps(packet, indent=2, sort_keys=True) if args.json else packet["status"])
            return 0
        if args.command == "doctor":
            packet = doctor()
            print(json.dumps(packet, indent=2, sort_keys=True) if args.json else packet["status"])
            return 0 if packet["status"] == "pass" else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
