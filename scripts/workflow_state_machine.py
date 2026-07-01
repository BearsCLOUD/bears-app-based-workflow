#!/usr/bin/env python3
"""Formal state-machine validator for Bears workflow goals."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import workflow_inference

CATALOG = PLUGIN_ROOT / "assets/catalog/workflow-state-machine.v1.json"
MACHINE_SCHEMA = PLUGIN_ROOT / "assets/schemas/workflow-state-machine.v1.schema.json"
TRANSITION_SCHEMA = PLUGIN_ROOT / "assets/schemas/workflow-transition.v1.schema.json"
INVARIANT_SCHEMA = PLUGIN_ROOT / "assets/schemas/workflow-invariant.v1.schema.json"
REQUIRED_STATES = {"intake","questioning","researching","planning","covered","ready_for_execution","running","waiting_validation","remediating","waiting_closeout","closed","blocked","manual_review","cancelled"}
REQUIRED_INVARIANTS = {"execution_requires_decision_graph","execution_requires_accepted_inference","write_requires_file_context","parallel_requires_disjoint_locks","closeout_requires_validation_pass","closeout_requires_no_blocking_debt","stale_context_cannot_unlock_execution","durable_json_remains_authority"}
EXECUTION_STATES = {"ready_for_execution", "running"}
CLOSEOUT_STATES = {"closed"}


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def catalog() -> dict[str, Any]:
    return load(CATALOG)


def validate_all() -> list[str]:
    data = catalog()
    errors = validate_json_schema(data, MACHINE_SCHEMA, "workflow-state-machine")
    states = set(data.get("states", []))
    if states != REQUIRED_STATES:
        errors.append("states must equal issue #439 required state set")
    invariants = {item.get("invariant_id") for item in data.get("invariants", [])}
    missing = sorted(REQUIRED_INVARIANTS - invariants)
    errors.extend(f"missing invariant: {item}" for item in missing)
    for index, invariant in enumerate(data.get("invariants", [])):
        errors.extend(validate_json_schema(invariant, INVARIANT_SCHEMA, f"invariants[{index}]"))
    seen_edges: set[tuple[str, str, str]] = set()
    for index, transition in enumerate(data.get("transitions", [])):
        errors.extend(validate_json_schema(transition, TRANSITION_SCHEMA, f"transitions[{index}]"))
        if transition.get("from_state") not in states:
            errors.append(f"transitions[{index}] unknown from_state")
        if transition.get("to_state") not in states:
            errors.append(f"transitions[{index}] unknown to_state")
        for invariant in transition.get("invariants_checked", []):
            if invariant not in REQUIRED_INVARIANTS:
                errors.append(f"transitions[{index}] unknown invariant {invariant}")
        edge = (str(transition.get("from_state")), str(transition.get("to_state")), str(transition.get("guard")))
        if edge in seen_edges:
            errors.append(f"duplicate transition edge: {edge}")
        seen_edges.add(edge)
    commands = set(data.get("commands", []))
    for command in [
        "python3 scripts/workflow_state_machine.py validate --json",
        "python3 scripts/workflow_state_machine.py can-transition --packet <path> --json",
        "python3 scripts/workflow_state_machine.py apply --packet <path> --json",
        "python3 scripts/workflow_state_machine.py check-invariants --goal-id <id> --json",
        "python3 scripts/workflow_state_machine.py doctor --json",
    ]:
        if command not in commands:
            errors.append(f"missing command: {command}")
    return sorted(set(errors))


def find_transition(packet: dict[str, Any]) -> dict[str, Any] | None:
    for row in catalog().get("transitions", []):
        if row.get("from_state") == packet.get("from_state") and row.get("to_state") == packet.get("to_state") and row.get("guard") == packet.get("guard"):
            return row
    return None


def check_invariants(goal_id: str, packet: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    checked = set(packet.get("invariants_checked", []) if packet else REQUIRED_INVARIANTS)
    evidence = set(packet.get("required_evidence", []) if packet else ["decision_graph", "accepted_inference", "file_context", "validation_pass", "no_blocking_debt", "fresh_context", "durable_json"])
    to_state = packet.get("to_state") if packet else "running"
    if to_state in EXECUTION_STATES:
        if "execution_requires_decision_graph" in checked and "decision_graph" not in evidence:
            errors.append("execution_requires_decision_graph missing decision_graph evidence")
        if "execution_requires_accepted_inference" in checked:
            q = workflow_inference.query("execution_allowed", json.dumps([goal_id, "bears-machine-first-execution-kernel-engineer", "codex_exec"]))
            if q.get("status") != "pass" and "accepted_inference" not in evidence:
                errors.append("execution_requires_accepted_inference missing accepted inference")
        if "write_requires_file_context" in checked and "file_context" not in evidence:
            errors.append("write_requires_file_context missing file_context evidence")
        if "stale_context_cannot_unlock_execution" in checked and "fresh_context" not in evidence and "file_context" not in evidence:
            errors.append("stale_context_cannot_unlock_execution missing fresh context evidence")
    if to_state in CLOSEOUT_STATES:
        if "closeout_requires_validation_pass" in checked and "validation_pass" not in evidence:
            errors.append("closeout_requires_validation_pass missing validation_pass evidence")
        if "closeout_requires_no_blocking_debt" in checked and "no_blocking_debt" not in evidence:
            errors.append("closeout_requires_no_blocking_debt missing no_blocking_debt evidence")
    if "durable_json_remains_authority" in checked and not any(str(item).endswith(".json") or item == "durable_json" for item in evidence):
        errors.append("durable_json_remains_authority missing durable JSON evidence")
    return {"schema": "bears-workflow-invariant-check.v1", "status": "pass" if not errors else "blocked", "goal_id": goal_id, "errors": errors}


def can_transition(packet: dict[str, Any]) -> dict[str, Any]:
    errors = validate_json_schema(packet, TRANSITION_SCHEMA, "transition")
    transition = find_transition(packet)
    if transition is None:
        errors.append("transition is not allowed by catalog")
    else:
        missing_evidence = sorted(set(transition.get("required_evidence", [])) - set(packet.get("required_evidence", [])))
        errors.extend(f"missing evidence: {item}" for item in missing_evidence)
        missing_invariants = sorted(set(transition.get("invariants_checked", [])) - set(packet.get("invariants_checked", [])))
        errors.extend(f"missing invariant check: {item}" for item in missing_invariants)
    invariant_result = check_invariants(str(packet.get("goal_id")), packet)
    errors.extend(invariant_result.get("errors", []))
    if packet.get("guard") == "degradation_event" and packet.get("to_state") != "manual_review":
        errors.append("degradation_event can only force manual_review")
    return {"schema": "bears-workflow-transition-result.v1", "status": "pass" if not errors else "blocked", "goal_id": packet.get("goal_id"), "from_state": packet.get("from_state"), "to_state": packet.get("to_state"), "errors": sorted(set(errors))}


def apply(packet: dict[str, Any]) -> dict[str, Any]:
    result = can_transition(packet)
    state = packet.get("to_state") if result.get("status") == "pass" else packet.get("from_state")
    return {"schema": "bears-workflow-state-apply-result.v1", "status": result["status"], "goal_id": packet.get("goal_id"), "state": state, "transition": result}


def doctor() -> dict[str, Any]:
    errors = validate_all() + workflow_inference.validate_all()
    return {"schema": "bears-workflow-state-machine-doctor.v1", "status": "pass" if not errors else "fail", "state_machine_consistency": "pass" if not errors else "fail", "state_count": len(catalog().get("states", [])), "transition_count": len(catalog().get("transitions", [])), "invariant_count": len(catalog().get("invariants", [])), "errors": errors}


def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--json", action="store_true")
    c = sub.add_parser("can-transition"); c.add_argument("--packet", required=True); c.add_argument("--json", action="store_true")
    a = sub.add_parser("apply"); a.add_argument("--packet", required=True); a.add_argument("--json", action="store_true")
    i = sub.add_parser("check-invariants"); i.add_argument("--goal-id", required=True); i.add_argument("--json", action="store_true")
    d = sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "validate":
        errors = validate_all(); packet = {"schema":"bears-workflow-state-machine-validation.v1", "status":"pass" if not errors else "fail", "errors":errors}; print_json(packet) if args.json else print(packet["status"]); return 0 if not errors else 1
    if args.cmd == "can-transition":
        packet = can_transition(load(Path(args.packet))); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    if args.cmd == "apply":
        packet = apply(load(Path(args.packet))); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    if args.cmd == "check-invariants":
        packet = check_invariants(args.goal_id); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    if args.cmd == "doctor":
        packet = doctor(); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
