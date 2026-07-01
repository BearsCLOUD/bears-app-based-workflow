#!/usr/bin/env python3
"""Validate Bears principles and principle decision packets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/bears-principles.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/bears-principles.v1.schema.json"
DECISION_SCHEMA = PLUGIN_ROOT / "assets/schemas/principle-decision.v1.schema.json"
REQUIRED_ACTIVE = {
    "machine_contracts_over_prose",
    "cheap_research_by_default",
    "no_parent_context_for_shards",
    "no_silent_role_omission",
    "codex_exec_requires_gate",
    "deterministic_runner_before_llm",
    "main_only_closeout_authority",
    "exact_proof_before_issue_close",
    "no_unbounded_autostart",
    "roadmap_leaf_before_execution",
}
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "raw log", "raw chat", "raw vpn config", "production data")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import bears_goals


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


def principles(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in catalog.get("principles", []) if isinstance(item, dict)]


def active_principle_ids(catalog: dict[str, Any] | None = None) -> set[str]:
    catalog = catalog or load()
    return {str(item.get("principle_id")) for item in principles(catalog) if item.get("status") == "active"}


def validate_catalog(path: Path = CATALOG) -> list[str]:
    catalog = load(path)
    errors = validate_json_schema(catalog, SCHEMA, path.name)
    if has_forbidden(catalog):
        errors.append(f"{path.name}: forbidden data marker present")
    seen: set[str] = set()
    for index, item in enumerate(principles(catalog)):
        principle_id = str(item.get("principle_id"))
        if principle_id in seen:
            errors.append(f"principles[{index}] duplicate principle_id: {principle_id}")
        seen.add(principle_id)
        for exception_index, exception in enumerate(item.get("exceptions", [])):
            if not isinstance(exception, dict) or not str(exception.get("reason_code", "")).strip() or not str(exception.get("rationale", "")).strip():
                errors.append(f"principles[{index}].exceptions[{exception_index}] explicit reason required")
    active = active_principle_ids(catalog)
    missing = sorted(REQUIRED_ACTIVE - active)
    if missing:
        errors.append("missing required active principles: " + ", ".join(missing))
    return errors


def decision_errors(packet: dict[str, Any]) -> list[str]:
    errors = validate_json_schema(packet, DECISION_SCHEMA, "principle-decision")
    if has_forbidden(packet):
        errors.append("principle-decision: forbidden data marker present")
    active_principles = active_principle_ids()
    active_goals = bears_goals.active_goal_ids()
    principles_applied = {str(item) for item in packet.get("principles_applied", [])}
    goals_supported = {str(item) for item in packet.get("goals_supported", [])}
    if not principles_applied:
        errors.append("principles_applied must name at least one active principle")
    unknown_principles = sorted(principles_applied - active_principles)
    if unknown_principles:
        errors.append("unknown or inactive principles_applied: " + ", ".join(unknown_principles))
    if not goals_supported:
        errors.append("goals_supported must name at least one active goal")
    unknown_goals = sorted(goals_supported - active_goals)
    if unknown_goals:
        errors.append("unknown or inactive goals_supported: " + ", ".join(unknown_goals))
    if not str(packet.get("reason_code", "")).strip():
        errors.append("reason_code is required")
    return errors


def doctor_packet() -> dict[str, Any]:
    principle_errors = validate_catalog()
    goal_errors = bears_goals.validate_catalog()
    catalog = load()
    active_principles = sorted(active_principle_ids(catalog))
    active_goals = sorted(bears_goals.active_goal_ids())
    missing = sorted(REQUIRED_ACTIVE - set(active_principles))
    errors = goal_errors + principle_errors
    return {
        "schema": "bears-goals-principles-doctor.v1",
        "status": "pass" if not errors else "fail",
        "active_goal_count": len(active_goals),
        "active_principle_count": len(active_principles),
        "required_active_principles": sorted(REQUIRED_ACTIVE),
        "missing_required_active_principles": missing,
        "errors": errors,
    }


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    decision = sub.add_parser("decision-check")
    decision.add_argument("--packet", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog() + bears_goals.validate_catalog()
        print_packet({"schema": "bears-principles-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "decision-check":
        packet = load(Path(args.packet))
        errors = decision_errors(packet)
        print_packet({"schema": "bears-principle-decision-check.v1", "status": "pass" if not errors else "fail", "decision_id": packet.get("decision_id", "<missing>"), "errors": errors})
        return 0 if not errors else 1
    if args.command == "doctor":
        packet = doctor_packet()
        print_packet(packet) if args.json else print(packet["status"])
        return 0 if packet["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
