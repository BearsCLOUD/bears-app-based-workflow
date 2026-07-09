#!/usr/bin/env python3
"""Deterministic formal semantics checks for Bears workflow logic."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TYPE_CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/semantic-type-system.v1.json"
KERNEL_PATH = PLUGIN_ROOT / "assets/catalog/formal-semantics-kernel.v1.json"
TYPE_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/semantic-type.v1.schema.json"
RELATION_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/semantic-relation.v1.schema.json"
KERNEL_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/formal-semantics-kernel.v1.schema.json"
SEMANTIC_TYPES = {"goal","issue","file","symbol","role","executor","workflow_node","decision","evidence","contract","validator","event","store","term"}
RELATIONS = {"is_a","part_of","depends_on","requires","blocks","enables","implements","validates","owns","reads","writes","uses","produces","consumes","proves","supersedes","conflicts_with"}
FORBIDDEN_OUTPUT_MARKERS = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "raw log", "raw chat", "raw vpn config", "production data")

sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema  # noqa: E402


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_catalogs() -> tuple[dict[str, Any], dict[str, Any]]:
    return _load_json(TYPE_CATALOG_PATH), _load_json(KERNEL_PATH)


def _relation_map(type_catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("id", ""): item for item in type_catalog.get("relations", []) if isinstance(item, dict)}


def _type_ids(type_catalog: dict[str, Any]) -> set[str]:
    return {item.get("id", "") for item in type_catalog.get("types", []) if isinstance(item, dict)}


def validate_all() -> list[str]:
    errors: list[str] = []
    type_catalog, kernel = load_catalogs()
    errors.extend(validate_json_schema(kernel, KERNEL_SCHEMA_PATH, "formal-semantics-kernel"))
    type_ids = _type_ids(type_catalog)
    if type_ids != SEMANTIC_TYPES:
        errors.append("semantic-type-system.types must equal the issue #435 closed-world semantic type set")
    relation_map = _relation_map(type_catalog)
    if set(relation_map) != RELATIONS:
        errors.append("semantic-type-system.relations must equal the issue #435 closed-world relation set")
    seen_types: set[str] = set()
    for index, item in enumerate(type_catalog.get("types", [])):
        errors.extend(validate_json_schema(item, TYPE_SCHEMA_PATH, f"semantic-type-system.types[{index}]"))
        item_id = item.get("id") if isinstance(item, dict) else None
        if item_id in seen_types:
            errors.append(f"semantic-type-system.types[{index}].id must be unique")
        if isinstance(item_id, str):
            seen_types.add(item_id)
        for relation in item.get("allowed_relations", []) if isinstance(item, dict) else []:
            if relation not in RELATIONS:
                errors.append(f"semantic-type-system.types[{index}].allowed_relations has unknown relation {relation}")
    for index, item in enumerate(type_catalog.get("relations", [])):
        errors.extend(validate_json_schema(item, RELATION_SCHEMA_PATH, f"semantic-type-system.relations[{index}]"))
        for field in ("source_types", "target_types"):
            for type_id in item.get(field, []) if isinstance(item, dict) else []:
                if type_id not in SEMANTIC_TYPES:
                    errors.append(f"semantic-type-system.relations[{index}].{field} has unknown semantic type {type_id}")
    for set_name in ("accepted", "candidate"):
        for index, fact in enumerate(kernel.get("fact_sets", {}).get(set_name, [])):
            result = check_fact(fact, material_decision=False, unlock_execution=False)
            if result["status"] not in ("pass", "candidate"):
                errors.append(f"formal-semantics-kernel.fact_sets.{set_name}[{index}] invalid: " + "; ".join(result["errors"]))
            expected_status = "accepted" if set_name == "accepted" else "candidate"
            if fact.get("status") != expected_status:
                errors.append(f"formal-semantics-kernel.fact_sets.{set_name}[{index}].status must be {expected_status}")
    return sorted(set(errors))


def _extract_fact(packet: dict[str, Any]) -> tuple[dict[str, Any], bool, bool]:
    fact = packet.get("fact") if isinstance(packet.get("fact"), dict) else packet
    material = bool(packet.get("material_decision", packet.get("material_workflow_decision", False)))
    unlock = bool(packet.get("unlock_execution", packet.get("graph_write", False)))
    return fact, material, unlock


def check_relation(source_type: str, relation_id: str, target_type: str) -> dict[str, Any]:
    type_catalog, _ = load_catalogs()
    relation_map = _relation_map(type_catalog)
    errors: list[str] = []
    if source_type not in SEMANTIC_TYPES:
        errors.append(f"unknown source semantic_type: {source_type}")
    if target_type not in SEMANTIC_TYPES:
        errors.append(f"unknown target semantic_type: {target_type}")
    relation = relation_map.get(relation_id)
    if relation_id not in RELATIONS or relation is None:
        errors.append(f"unknown relation: {relation_id}")
    if not errors and source_type not in relation.get("source_types", []):
        errors.append(f"invalid relation direction: {source_type} cannot be source of {relation_id}")
    if not errors and target_type not in relation.get("target_types", []):
        errors.append(f"invalid relation direction: {target_type} cannot be target of {relation_id}")
    status = "pass" if not errors else "blocked"
    return {
        "schema": "bears-formal-semantics-relation-check-result.v1",
        "status": status,
        "relation": relation_id,
        "source_type": source_type,
        "target_type": target_type,
        "direction_valid": not errors,
        "closed_world": bool(relation.get("closed_world", True)) if isinstance(relation, dict) else True,
        "graph_write_allowed": not errors,
        "errors": errors,
    }


def check_relation_packet(packet: dict[str, Any]) -> dict[str, Any]:
    source_type = packet.get("source_type") or packet.get("subject", {}).get("semantic_type")
    target_type = packet.get("target_type") or packet.get("object", {}).get("semantic_type")
    relation_id = packet.get("relation") or packet.get("relation_id")
    return check_relation(str(source_type), str(relation_id), str(target_type))


def check_fact(fact: dict[str, Any], *, material_decision: bool, unlock_execution: bool) -> dict[str, Any]:
    errors: list[str] = []
    subject = fact.get("subject", {}) if isinstance(fact, dict) else {}
    obj = fact.get("object", {}) if isinstance(fact, dict) else {}
    source_type = subject.get("semantic_type")
    target_type = obj.get("semantic_type")
    relation_id = fact.get("relation") if isinstance(fact, dict) else None
    rel_result = check_relation(str(source_type), str(relation_id), str(target_type))
    errors.extend(rel_result["errors"])
    status_value = fact.get("status") if isinstance(fact, dict) else None
    accepted = status_value == "accepted" and not errors
    candidate = status_value == "candidate" and not errors
    rejected = status_value == "rejected"
    if status_value not in {"accepted", "candidate", "rejected"}:
        errors.append(f"unknown fact status: {status_value}")
    if rejected:
        errors.append("rejected fact cannot be used as truth")
    if candidate and (material_decision or unlock_execution):
        errors.append("candidate fact cannot unlock material workflow execution")
    if unlock_execution and not accepted:
        errors.append("execution unlock requires an accepted semantic fact")
    if material_decision and not accepted:
        errors.append("material workflow decision requires an accepted semantic fact")
    result_status = "pass" if not errors and accepted else "candidate" if candidate and not (material_decision or unlock_execution) else "blocked" if errors else "blocked"
    return {
        "schema": "bears-formal-semantics-fact-check-result.v1",
        "status": result_status,
        "fact_id": fact.get("id") if isinstance(fact, dict) else None,
        "accepted": accepted,
        "candidate": candidate,
        "unlocks_execution": bool(unlock_execution and accepted and not errors),
        "material_decision_allowed": bool(material_decision and accepted and not errors),
        "closed_world": True,
        "errors": errors,
    }


def check_fact_packet(packet: dict[str, Any]) -> dict[str, Any]:
    fact, material, unlock = _extract_fact(packet)
    return check_fact(fact, material_decision=material, unlock_execution=unlock)


def query_fact(fact_id: str) -> dict[str, Any]:
    _, kernel = load_catalogs()
    for set_name in ("accepted", "candidate"):
        for fact in kernel.get("fact_sets", {}).get(set_name, []):
            if fact.get("id") == fact_id:
                result = check_fact(fact, material_decision=False, unlock_execution=False)
                result["fact"] = fact
                result["fact_set"] = set_name
                return result
    return {"schema": "bears-formal-semantics-fact-query-result.v1", "status": "blocked", "fact_id": fact_id, "accepted": False, "candidate": False, "errors": ["fact not found"]}


def doctor_result() -> dict[str, Any]:
    errors = validate_all()
    type_catalog, kernel = load_catalogs()
    return {
        "schema": "bears-formal-semantics-doctor.v1",
        "status": "pass" if not errors else "fail",
        "formal_semantics_status": "pass" if not errors else "fail",
        "types": len(type_catalog.get("types", [])),
        "relations": len(type_catalog.get("relations", [])),
        "accepted_facts": len(kernel.get("fact_sets", {}).get("accepted", [])),
        "candidate_facts": len(kernel.get("fact_sets", {}).get("candidate", [])),
        "closed_world": True,
        "errors": errors,
    }


def _safe_print(packet: dict[str, Any]) -> None:
    text = json.dumps(packet, indent=2, sort_keys=True)
    for marker in FORBIDDEN_OUTPUT_MARKERS:
        if marker in text:
            raise SystemExit(f"forbidden output marker: {marker}")
    print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    check_fact_parser = sub.add_parser("check-fact")
    check_fact_parser.add_argument("--packet", required=True)
    check_fact_parser.add_argument("--json", action="store_true")
    check_relation_parser = sub.add_parser("check-relation")
    check_relation_parser.add_argument("--packet", required=True)
    check_relation_parser.add_argument("--json", action="store_true")
    query = sub.add_parser("query-fact")
    query.add_argument("--fact-id", required=True)
    query.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        packet = {"schema": "bears-formal-semantics-validate-result.v1", "status": "pass" if not errors else "fail", "errors": errors}
        _safe_print(packet) if args.json else print(packet["status"])
        return 0 if not errors else 1
    if args.command == "check-fact":
        result = check_fact_packet(_load_json(Path(args.packet)))
        _safe_print(result) if args.json else print(result["status"])
        return 0 if result["status"] in {"pass", "candidate"} else 1
    if args.command == "check-relation":
        result = check_relation_packet(_load_json(Path(args.packet)))
        _safe_print(result) if args.json else print(result["status"])
        return 0 if result["status"] == "pass" else 1
    if args.command == "query-fact":
        result = query_fact(args.fact_id)
        _safe_print(result) if args.json else print(result["status"])
        return 0 if result.get("accepted") else 1
    if args.command == "doctor":
        result = doctor_result()
        _safe_print(result) if args.json else print(result["status"])
        return 0 if result["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
