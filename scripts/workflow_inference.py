#!/usr/bin/env python3
"""Datalog-style inference for Bears workflow facts."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

CATALOG = PLUGIN_ROOT / "assets/catalog/workflow-inference-rules.v1.json"
FACT_SCHEMA = PLUGIN_ROOT / "assets/schemas/inference-fact.v1.schema.json"
RULE_SCHEMA = PLUGIN_ROOT / "assets/schemas/inference-rule.v1.schema.json"
QUERY_SCHEMA = PLUGIN_ROOT / "assets/schemas/inference-query.v1.schema.json"
REQUIRED_GROUPS = {
    "context_required", "can_read", "can_write", "execution_allowed", "research_required",
    "planning_required", "validator_required", "closeout_blocked", "roadmap_leaf_eligible",
    "parallel_unit_allowed", "manual_review_required",
}
PERMISSION_PREDICATES = {"can_read", "can_write", "execution_allowed", "parallel_unit_allowed", "roadmap_leaf_eligible"}
CANDIDATE_OUTPUTS = {"research_required", "planning_required", "manual_review_required"}


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def catalog() -> dict[str, Any]:
    return load(CATALOG)


def is_var(value: str) -> bool:
    return isinstance(value, str) and value.startswith("$")


def fact_key(fact: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return str(fact.get("predicate")), tuple(str(x) for x in fact.get("arguments", []))


def bind_args(pattern: list[str], values: list[str], binding: dict[str, str]) -> dict[str, str] | None:
    if len(pattern) != len(values):
        return None
    result = dict(binding)
    for pattern_value, actual in zip(pattern, values):
        if is_var(pattern_value):
            if pattern_value in result and result[pattern_value] != actual:
                return None
            result[pattern_value] = actual
        elif pattern_value != actual:
            return None
    return result


def instantiate(args: list[str], binding: dict[str, str]) -> list[str]:
    return [binding.get(arg, arg) for arg in args]


def validate_catalog_packet(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema") not in {"bears-workflow-inference-rules.v1", None}:
        errors.append("catalog schema must be bears-workflow-inference-rules.v1")
    groups = set()
    for index, fact in enumerate(data.get("facts", [])):
        errors.extend(validate_json_schema(fact, FACT_SCHEMA, f"facts[{index}]"))
    for index, rule in enumerate(data.get("rules", [])):
        errors.extend(validate_json_schema(rule, RULE_SCHEMA, f"rules[{index}]"))
        groups.add(str(rule.get("group")))
        if not rule.get("stratified"):
            errors.append(f"rules[{index}] must be stratified")
        if rule.get("max_depth") is None and any(str(atom.get("predicate")) == str(rule.get("head", {}).get("predicate")) for atom in rule.get("body", [])):
            errors.append(f"rules[{index}] recursive rule requires max_depth")
        for atom in rule.get("body", []):
            if atom.get("negated") and not atom.get("requires_closed_world"):
                errors.append(f"rules[{index}] negation requires closed-world declaration")
            if atom.get("requires_closed_world") and atom.get("predicate") not in data.get("closed_world_predicates", []):
                errors.append(f"rules[{index}] closed-world predicate is not declared: {atom.get('predicate')}")
    return sorted(set(errors))


def validate_all() -> list[str]:
    errors: list[str] = []
    data = catalog()
    errors.extend(validate_catalog_packet(data))
    groups = {str(rule.get("group")) for rule in data.get("rules", [])}
    missing = sorted(REQUIRED_GROUPS - groups)
    errors.extend(f"missing required rule group: {item}" for item in missing)
    commands = set(data.get("commands", []))
    for command in [
        "python3 scripts/workflow_inference.py validate --json",
        "python3 scripts/workflow_inference.py materialize --input <path> --json",
        "python3 scripts/workflow_inference.py query --predicate <name> --args <json> --json",
        "python3 scripts/workflow_inference.py explain --fact <id> --json",
        "python3 scripts/workflow_inference.py doctor --json",
    ]:
        if command not in commands:
            errors.append(f"missing command: {command}")
    return sorted(set(errors))


def derive(input_facts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = catalog()
    base_facts = list(data.get("facts", [])) + list(input_facts or [])
    facts_by_pred: dict[str, list[dict[str, Any]]] = {}
    for fact in base_facts:
        facts_by_pred.setdefault(str(fact.get("predicate")), []).append(fact)
    derived: dict[str, dict[str, Any]] = {}
    errors: list[str] = validate_all()
    for rule in data.get("rules", []):
        bindings = [({}, [])]
        blocked_rule = False
        for atom in rule.get("body", []):
            pred = str(atom.get("predicate"))
            if atom.get("negated"):
                if pred not in data.get("closed_world_predicates", []):
                    errors.append(f"closed-world negation blocked for undeclared predicate: {pred}")
                    blocked_rule = True
                continue
            next_bindings = []
            for binding, proof_ids in bindings:
                for fact in facts_by_pred.get(pred, []):
                    bound = bind_args(list(atom.get("arguments", [])), list(fact.get("arguments", [])), binding)
                    if bound is not None:
                        next_bindings.append((bound, proof_ids + [str(fact.get("fact_id"))]))
            bindings = next_bindings
        if blocked_rule:
            continue
        for binding, proof_ids in bindings:
            args = instantiate(list(rule.get("head", {}).get("arguments", [])), binding)
            pred = str(rule.get("head", {}).get("predicate"))
            body_facts = [f for f in base_facts if str(f.get("fact_id")) in proof_ids]
            confidences = {str(f.get("confidence")) for f in body_facts}
            if rule.get("confidence_policy") == "accepted_only" and confidences != {"accepted"}:
                continue
            if pred in PERMISSION_PREDICATES and confidences != {"accepted"}:
                continue
            if "candidate" in confidences and pred not in CANDIDATE_OUTPUTS:
                continue
            confidence = "candidate" if "candidate" in confidences else "accepted"
            fact_id = "derived-" + pred + "-" + "-".join(args).replace("/", "_").replace(" ", "_")
            packet = {
                "schema": "bears-inference-derived-fact.v1",
                "fact_id": fact_id,
                "predicate": pred,
                "arguments": args,
                "confidence": confidence,
                "rule_id": rule.get("rule_id"),
                "proof_trace": proof_ids,
            }
            derived[fact_id] = packet
    return {"schema": "bears-workflow-inference-materialization.v1", "status": "pass" if not errors else "fail", "facts": sorted(derived.values(), key=lambda x: x["fact_id"]), "errors": errors}


def materialize(path: Path | None = None) -> dict[str, Any]:
    extra: list[dict[str, Any]] = []
    if path:
        packet = load(path)
        if isinstance(packet, dict) and "facts" in packet:
            extra = list(packet.get("facts", []))
        elif isinstance(packet, dict):
            extra = [packet]
    return derive(extra)


def query(predicate: str, args_json: str) -> dict[str, Any]:
    try:
        args = json.loads(args_json)
    except Exception:
        args = []
    packet = {"schema": "bears-inference-query.v1", "predicate": predicate, "arguments": args}
    errors = validate_json_schema(packet, QUERY_SCHEMA, "query")
    mat = derive()
    matches = [fact for fact in mat.get("facts", []) if fact.get("predicate") == predicate and list(fact.get("arguments", [])) == list(args)]
    return {"schema": "bears-workflow-inference-query-result.v1", "status": "pass" if matches and not errors and mat.get("status") == "pass" else "blocked", "predicate": predicate, "arguments": args, "matches": matches, "errors": errors + mat.get("errors", [])}


def explain(fact_id: str) -> dict[str, Any]:
    mat = derive()
    match = next((fact for fact in mat.get("facts", []) if fact.get("fact_id") == fact_id), None)
    errors = list(mat.get("errors", []))
    if not match:
        errors.append(f"derived fact not found: {fact_id}")
    return {"schema": "bears-workflow-inference-explanation.v1", "status": "pass" if match and not errors else "blocked", "fact_id": fact_id, "proof_trace": match.get("proof_trace", []) if match else [], "fact": match, "errors": errors}


def doctor() -> dict[str, Any]:
    mat = derive()
    rule_errors = mat.get("errors", [])
    return {"schema": "bears-workflow-inference-doctor.v1", "status": "pass" if not rule_errors else "fail", "inference_freshness": "pass" if not rule_errors else "fail", "rule_errors": rule_errors, "derived_fact_count": len(mat.get("facts", [])), "required_rule_groups": sorted(REQUIRED_GROUPS)}


def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--json", action="store_true")
    m = sub.add_parser("materialize"); m.add_argument("--input"); m.add_argument("--json", action="store_true")
    q = sub.add_parser("query"); q.add_argument("--predicate", required=True); q.add_argument("--args", required=True); q.add_argument("--json", action="store_true")
    e = sub.add_parser("explain"); e.add_argument("--fact", required=True); e.add_argument("--json", action="store_true")
    d = sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "validate":
        errors = validate_all(); packet = {"schema":"bears-workflow-inference-validation.v1", "status":"pass" if not errors else "fail", "errors":errors}; print_json(packet) if args.json else print(packet["status"]); return 0 if not errors else 1
    if args.cmd == "materialize":
        packet = materialize(Path(args.input) if args.input else None); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    if args.cmd == "query":
        packet = query(args.predicate, args.args); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    if args.cmd == "explain":
        packet = explain(args.fact); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    if args.cmd == "doctor":
        packet = doctor(); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
