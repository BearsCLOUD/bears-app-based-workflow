#!/usr/bin/env python3
"""Decide and gate Codex workflow execution from Bears JSON policy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
POLICY = PLUGIN_ROOT / "assets/catalog/codex-workflow-policy.v1.json"
POLICY_SCHEMA = PLUGIN_ROOT / "assets/schemas/codex-workflow-policy.v1.schema.json"
DECISION_SCHEMA = PLUGIN_ROOT / "assets/schemas/codex-execution-decision.v1.schema.json"
ADAPTER = PLUGIN_ROOT / "assets/catalog/codex-exec-adapter.v1.json"
ROADMAP = PLUGIN_ROOT / "assets/catalog/workflow-roadmap.v1.json"

EXECUTORS = {
    "deterministic_runner",
    "cheap_research_shard",
    "codex_subagent",
    "sequential_codex_exec",
    "manual_review",
}
TASK_CLASSES = {"research", "planning", "implementation", "review", "fix", "validation", "closeout", "roadmap"}
ROLE_OMISSION_REASON_CODES = {
    "role_not_needed_deterministic",
    "role_covered_by_existing_profile",
    "role_blocked_by_scope",
    "role_blocked_by_budget",
    "role_blocked_by_missing_contract",
}
ROLE_PROFILE_ROLES = {"planner", "implementer", "reviewer", "fixer", "validator", "release_notes_writer", "closeout_reporter"}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def plugin_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PLUGIN_ROOT / path


def policy() -> dict[str, Any]:
    data = load(POLICY)
    if not isinstance(data, dict):
        raise ValueError("policy root must be an object")
    return data


def role_profiles() -> dict[str, dict[str, Any]]:
    if not ADAPTER.is_file():
        return {}
    data = load(ADAPTER)
    profiles = data.get("role_profiles", {}) if isinstance(data, dict) else {}
    return {str(key): value for key, value in profiles.items() if isinstance(value, dict)} if isinstance(profiles, dict) else {}


def task_default(task_class: str) -> dict[str, Any]:
    defaults = policy().get("task_class_defaults", {})
    packet = defaults.get(task_class, {}) if isinstance(defaults, dict) else {}
    if not isinstance(packet, dict):
        return {}
    return packet


def normalize_issue(issue: str | None) -> str | None:
    if not issue:
        return None
    issue = issue.strip()
    if not issue:
        return None
    return issue if issue.startswith("#") else f"#{issue}"


def explicit_paths(paths: list[str]) -> list[str]:
    return [path.strip() for path in paths if path and path.strip()]


def append_prefixed_gates(gates: list[str], prefix: str, values: list[str]) -> list[str]:
    merged = list(gates)
    for value in values:
        value = value.strip()
        if value:
            merged.append(value if value.startswith(prefix) else f"{prefix}{value}")
    return merged


def decision_packet(
    *,
    issue: str | None,
    workflow_node: str | None,
    task_class: str,
    selected_executor: str | None = None,
    required_role: str | None = None,
    reason_code: str | None = None,
    token_policy: str | None = None,
    allowed_write_scope: list[str] | None = None,
    required_gates: list[str] | None = None,
    evidence_paths: list[str] | None = None,
    manual_review: bool = False,
) -> dict[str, Any]:
    default = task_default(task_class)
    executor = selected_executor or str(default.get("selected_executor", "manual_review"))
    role = required_role if required_role is not None else default.get("required_role")
    reason = reason_code or str(default.get("reason_code", "manual_review_required"))
    token = token_policy or str(default.get("token_policy", "manual_review"))
    gates = list(default.get("required_gates", [])) if isinstance(default.get("required_gates"), list) else []
    gates.extend(required_gates or [])
    if manual_review:
        executor = "manual_review"
        role = None
        reason = "role_blocked_by_scope"
        token = "manual_review"
        gates = ["manual:operator_review"]
    return {
        "schema": "bears-codex-execution-decision.v1",
        "issue": normalize_issue(issue),
        "workflow_node": workflow_node or None,
        "task_class": task_class,
        "selected_executor": executor,
        "required_role": role,
        "reason_code": reason,
        "token_policy": token,
        "may_spawn_children": False,
        "may_call_codex_exec": False,
        "allowed_write_scope": explicit_paths(allowed_write_scope or []),
        "required_gates": gates,
        "evidence_paths": explicit_paths(evidence_paths or []),
    }


def validate_policy() -> list[str]:
    errors: list[str] = []
    for path in [POLICY, POLICY_SCHEMA, DECISION_SCHEMA]:
        if not path.is_file():
            errors.append(f"missing artifact: {path.relative_to(PLUGIN_ROOT)}")
    if errors:
        return errors
    data = load(POLICY)
    errors.extend(validate_json_schema(data, POLICY_SCHEMA, "policy"))
    executor_ids = {item.get("id") for item in data.get("executors", []) if isinstance(item, dict)}
    if executor_ids != EXECUTORS:
        errors.append("policy executors must match issue #414 executor set")
    defaults = data.get("task_class_defaults", {})
    if not isinstance(defaults, dict) or set(defaults) != TASK_CLASSES:
        errors.append("policy task_class_defaults must cover every task_class")
    omission_codes = set(data.get("role_omission_reason_codes", []))
    if omission_codes != ROLE_OMISSION_REASON_CODES:
        errors.append("policy role_omission_reason_codes must match #414 codes")
    cheap = data.get("cheap_research_token_policy", {})
    if cheap.get("token_policy") != "cheap_required" or cheap.get("parent_context") != "none":
        errors.append("cheap research must require cheap tokens and parent_context none")
    return errors


def validate_decision(packet: dict[str, Any], *, label: str = "decision") -> list[str]:
    errors = validate_json_schema(packet, DECISION_SCHEMA, label)
    if packet.get("schema") != "bears-codex-execution-decision.v1":
        errors.append(f"{label}.schema must be bears-codex-execution-decision.v1")
    if packet.get("selected_executor") not in EXECUTORS:
        errors.append(f"{label}.selected_executor is not allowed")
    if packet.get("task_class") not in TASK_CLASSES:
        errors.append(f"{label}.task_class is not allowed")
    if packet.get("required_role") is None and packet.get("reason_code") not in ROLE_OMISSION_REASON_CODES:
        errors.append(f"{label}.reason_code must explain omitted role")
    if packet.get("selected_executor") == "cheap_research_shard":
        if packet.get("token_policy") != "cheap_required":
            errors.append(f"{label}.token_policy must be cheap_required for cheap_research_shard")
        gates = packet.get("required_gates", [])
        if "context:parent_none" not in gates:
            errors.append(f"{label}.required_gates must include context:parent_none for cheap_research_shard")
    if packet.get("selected_executor") == "manual_review" and packet.get("token_policy") != "manual_review":
        errors.append(f"{label}.token_policy must be manual_review for manual_review")
    if packet.get("may_spawn_children") is not False:
        errors.append(f"{label}.may_spawn_children must be false")
    if packet.get("may_call_codex_exec") is not False:
        errors.append(f"{label}.may_call_codex_exec must be false before allow-exec")
    return errors


def load_decision(path: Path | None) -> tuple[dict[str, Any] | None, list[str]]:
    if path is None:
        return None, ["decision packet path required"]
    if not path.is_file():
        return None, [f"decision packet missing: {path}"]
    data = load(path)
    if not isinstance(data, dict):
        return None, ["decision packet root must be object"]
    return data, []


def has_prefixed_gate(packet: dict[str, Any], prefix: str) -> bool:
    return any(isinstance(gate, str) and gate.startswith(prefix) and gate[len(prefix):].strip() for gate in packet.get("required_gates", []))


def lease_path(packet: dict[str, Any]) -> Path | None:
    for gate in packet.get("required_gates", []):
        if isinstance(gate, str) and gate.startswith("lease:") and gate[len("lease:"):].strip():
            return plugin_path(gate[len("lease:"):].strip())
    return None


def paths_are_explicit(paths: list[Any]) -> bool:
    if not isinstance(paths, list) or not paths:
        return False
    forbidden = {"", ".", "..", "/", "*", "**"}
    for item in paths:
        if not isinstance(item, str):
            return False
        value = item.strip().replace("\\", "/")
        if value in forbidden or "*" in value or value.startswith("~") or "//" in value:
            return False
    return True


def roadmap_leaf_eligible(workflow_node: str | None) -> tuple[bool, str]:
    if not workflow_node:
        return True, "not_applicable"
    if not ROADMAP.is_file():
        return False, "workflow roadmap catalog missing"
    data = load(ROADMAP)
    nodes = data.get("nodes", []) if isinstance(data, dict) else []
    if not isinstance(nodes, list):
        return False, "workflow roadmap nodes missing"
    index = {str(node.get("node_id")): node for node in nodes if isinstance(node, dict)}
    node = index.get(workflow_node)
    if node is None:
        return False, f"workflow_node not found: {workflow_node}"
    has_children = bool(node.get("decomposes_to"))
    deps_ready = all(index.get(dep, {}).get("state") in {"validated", "closed"} for dep in node.get("depends_on", []))
    if node.get("state") == "queued" and node.get("autostart_policy") == "eligible" and not has_children and not node.get("blocked_by") and deps_ready:
        return True, "eligible_leaf"
    return False, "workflow_node is not an eligible roadmap leaf"


def allow_exec_packet(decision_path: Path | None) -> dict[str, Any]:
    packet, errors = load_decision(decision_path)
    if packet is not None:
        errors.extend(validate_decision(packet))
        if packet.get("selected_executor") != "sequential_codex_exec":
            errors.append("selected_executor must be sequential_codex_exec")
        if not packet.get("issue") and not packet.get("workflow_node"):
            errors.append("issue or workflow_node is required")
        role = packet.get("required_role")
        profiles = role_profiles()
        if role not in ROLE_PROFILE_ROLES or role not in profiles:
            errors.append("required_role must have a codex exec role profile")
        lease = lease_path(packet)
        if lease is None:
            errors.append("required_gates must include lease:<path>")
        elif not lease.is_file():
            errors.append(f"lease file missing: {lease}")
        if not paths_are_explicit(packet.get("allowed_write_scope", [])):
            errors.append("allowed_write_scope must contain explicit paths")
        if not has_prefixed_gate(packet, "validation:"):
            errors.append("required_gates must include validation:<gate>")
        if not has_prefixed_gate(packet, "closeout:"):
            errors.append("required_gates must include closeout:<gate>")
        ok, reason = roadmap_leaf_eligible(packet.get("workflow_node"))
        if not ok:
            errors.append(reason)
    return {
        "schema": "bears-codex-workflow-allow-exec.v1",
        "status": "pass" if not errors else "fail",
        "allow_exec": not errors,
        "decision": str(decision_path) if decision_path else None,
        "errors": errors,
    }



def legacy_goal_state_decide(goal_state: str | None) -> dict[str, Any]:
    errors: list[str] = []
    if not goal_state:
        errors.append("goal state path required")
    else:
        path = plugin_path(goal_state)
        if not path.is_file():
            errors.append("goal state missing")
    return {
        "schema": "bears-codex-workflow-decision.v1",
        "status": "pass" if not errors else "blocked",
        "executor": "codex_exec",
        "requires_allow_exec": True,
        "goal_state": goal_state or "",
        "errors": errors,
    }


def legacy_goal_state_allow_exec(goal_state: str | None) -> dict[str, Any]:
    errors: list[str] = []
    state: dict[str, Any] = {}
    if not goal_state:
        errors.append("goal state path required")
    else:
        path = plugin_path(goal_state)
        if not path.is_file():
            errors.append("goal state missing")
        else:
            try:
                state = load(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"goal state invalid json: {exc}")
            if state.get("state") in {"blocked", "manual_review", "closed"}:
                errors.append(f"goal state is {state.get('state')}")
            if state.get("blockers"):
                errors.append("goal state has blockers")
    return {
        "schema": "bears-codex-workflow-allow-exec.v1",
        "status": "pass" if not errors else "blocked",
        "allow_exec": not errors,
        "goal_id": state.get("goal_id", ""),
        "goal_state": goal_state or "",
        "errors": errors,
    }

def validation_packet(errors: list[str], schema: str, **extra: Any) -> dict[str, Any]:
    return {"schema": schema, "status": "pass" if not errors else "fail", "errors": errors, **extra}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")

    decide = sub.add_parser("decide")
    decide.add_argument("--issue")
    decide.add_argument("--goal-state")
    decide.add_argument("--workflow-node")
    decide.add_argument("--task-class", choices=sorted(TASK_CLASSES), default="implementation")
    decide.add_argument("--executor", choices=sorted(EXECUTORS))
    decide.add_argument("--required-role")
    decide.add_argument("--reason-code")
    decide.add_argument("--token-policy", choices=["cheap_required", "standard_allowed", "expensive_blocked", "manual_review"])
    decide.add_argument("--allowed-path", action="append", default=[])
    decide.add_argument("--gate", action="append", default=[])
    decide.add_argument("--lease")
    decide.add_argument("--validation-gate", action="append", default=[])
    decide.add_argument("--closeout-gate", action="append", default=[])
    decide.add_argument("--evidence-path", action="append", default=[])
    decide.add_argument("--manual-review", action="store_true")
    decide.add_argument("--json", action="store_true")

    validate_dec = sub.add_parser("validate-decision")
    validate_dec.add_argument("--decision", type=Path)
    validate_dec.add_argument("--json", action="store_true")

    allow = sub.add_parser("allow-exec")
    allow.add_argument("--decision", type=Path)
    allow.add_argument("--goal-state")
    allow.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "validate":
        packet = validation_packet(validate_policy(), "bears-codex-workflow-policy-validation.v1")
    elif args.command == "decide":
        if args.goal_state:
            packet = legacy_goal_state_decide(args.goal_state)
            if getattr(args, "json", False):
                print_json(packet)
            else:
                print(packet["status"])
            return 0 if packet["status"] == "pass" else 1
        gates = list(args.gate)
        evidence = list(args.evidence_path)
        if args.lease:
            gates = append_prefixed_gates(gates, "lease:", [args.lease])
            evidence.append(args.lease)
        gates = append_prefixed_gates(gates, "validation:", args.validation_gate)
        gates = append_prefixed_gates(gates, "closeout:", args.closeout_gate)
        packet = decision_packet(
            issue=args.issue,
            workflow_node=args.workflow_node,
            task_class=args.task_class,
            selected_executor=args.executor,
            required_role=args.required_role,
            reason_code=args.reason_code,
            token_policy=args.token_policy,
            allowed_write_scope=args.allowed_path,
            required_gates=gates,
            evidence_paths=evidence,
            manual_review=args.manual_review,
        )
        errors = validate_decision(packet)
        if errors:
            packet = {**packet, "validation_status": "fail", "validation_errors": errors}
    elif args.command == "validate-decision":
        decision, errors = load_decision(args.decision)
        if decision is not None:
            errors.extend(validate_decision(decision))
        packet = validation_packet(errors, "bears-codex-execution-decision-validation.v1", decision=str(args.decision) if args.decision else None)
    else:
        packet = legacy_goal_state_allow_exec(args.goal_state) if args.goal_state else allow_exec_packet(args.decision)

    if getattr(args, "json", False):
        print_json(packet)
    else:
        print(packet["status"] if "status" in packet else packet.get("validation_status", "pass"))
    status = packet.get("status", packet.get("validation_status", "pass"))
    return 0 if status == "pass" or args.command == "decide" else 1


if __name__ == "__main__":
    raise SystemExit(main())
