#!/usr/bin/env python3
"""Validate and update the Bears workflow roadmap graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROADMAP = PLUGIN_ROOT / "assets/catalog/workflow-roadmap.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/workflow-roadmap.v1.schema.json"
TRANSITION_PACKET_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/roadmap-state-transition-authority-transition.v1.schema.json"
FORBIDDEN_MARKERS = (
    "BEGIN PRIVATE KEY",
    "raw_secret",
    "raw log",
    "raw chat",
    "raw vpn config",
    "production data",
    ".env=",
)
NODE_STATES = {
    "idea",
    "researched",
    "contracted",
    "decomposed",
    "queued",
    "running",
    "validated",
    "closed",
    "blocked",
    "manual_review",
}
NODE_TYPES = {
    "research",
    "contract",
    "implementation",
    "validator",
    "migration",
    "cleanup",
    "closeout",
}
REQUIRED_COMMANDS = {
    "scripts/workflow_roadmap.py validate",
    "scripts/workflow_roadmap.py add-node --packet <path>",
    "scripts/workflow_roadmap.py decompose --node <id>",
    "scripts/workflow_roadmap.py next --json",
    "scripts/workflow_roadmap.py reconcile --json",
}
REQUIRED_ROLES = {
    "roadmap_researcher",
    "roadmap_curator",
    "roadmap_decomposer",
    "roadmap_executor",
    "roadmap_reconciler",
}
DEPENDENCY_READY_STATES = {"researched", "contracted", "decomposed", "validated", "closed"}
TRANSITION_PACKET_SCHEMA = "bears-roadmap-state-transition-authority-transition.v1"
ROADMAP_RECONCILE_HAZARD_MARKERS = (
    "seller",
    "cutover",
    "migration",
    "gitlab",
    "production data",
    "dns",
    "deploy credentials",
    "kubeconfig",
    "rollback",
    "destructive",
    "imported repo",
)
RESOURCE_CONFLICT_ALLOW = "allow"
RESOURCE_CONFLICT_BLOCKED_REASONS = {
    "blocked": "blocked_resource_conflict_status",
    "stale": "stale_resource_conflict_status",
}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(strings(item))
        return out
    return []


def has_forbidden_data(value: Any) -> bool:
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN_MARKERS)


def nodes(roadmap: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in roadmap.get("nodes", []) if isinstance(item, dict)]


def node_index(roadmap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["node_id"]): item for item in nodes(roadmap) if isinstance(item.get("node_id"), str)}


def node_packet(packet: dict[str, Any]) -> dict[str, Any]:
    if "node" in packet and isinstance(packet["node"], dict):
        return packet["node"]
    return packet


def is_path_like_output(value: str) -> bool:
    """Return true for roadmap outputs that name repo-visible paths."""
    return value.startswith(("assets/", "docs/", "scripts/", "tests/", ".github/")) or "/" in value


def _ref_errors(roadmap: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    index = node_index(roadmap)
    seen: set[str] = set()
    issue_type_outputs: set[tuple[str, str, tuple[str, ...]]] = set()
    output_paths: dict[str, str] = {}
    for item in nodes(roadmap):
        node_id = item.get("node_id")
        if node_id in seen:
            errors.append(f"duplicate node_id: {node_id}")
        seen.add(str(node_id))
        issue_mapping = (str(item.get("issue")), str(item.get("node_type")), tuple(sorted(str(value) for value in item.get("outputs", []))))
        if issue_mapping in issue_type_outputs:
            errors.append(f"duplicate issue-node mapping: {item.get('issue')} {item.get('node_type')}")
        issue_type_outputs.add(issue_mapping)
        for output in item.get("outputs", []):
            if not isinstance(output, str) or output.startswith("github_issue:"):
                continue
            if not is_path_like_output(output):
                continue
            prior = output_paths.get(output)
            if prior and prior != node_id:
                errors.append(f"duplicate roadmap output path: {output}")
            output_paths[output] = str(node_id)
        for field in ("depends_on", "decomposes_to", "blocked_by"):
            for ref in item.get(field, []):
                if ref not in index:
                    errors.append(f"{node_id}.{field} missing node: {ref}")
    return errors


def _cycle_errors(roadmap: dict[str, Any], field: str) -> list[str]:
    index = node_index(roadmap)
    adjacency = {node_id: [ref for ref in node.get(field, []) if ref in index] for node_id, node in index.items()}
    visiting: set[str] = set()
    visited: set[str] = set()
    errors: list[str] = []

    def visit(node_id: str) -> None:
        if node_id in visiting:
            errors.append(f"{field} cycle at {node_id}")
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for nxt in adjacency.get(node_id, []):
            visit(nxt)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in index:
        visit(node_id)
    return errors


def _reachability_errors(roadmap: dict[str, Any]) -> list[str]:
    index = node_index(roadmap)
    if not index:
        return ["nodes must not be empty"]
    incoming: set[str] = set()
    child_edges: dict[str, list[str]] = defaultdict(list)
    for item in index.values():
        node_id = str(item["node_id"])
        for ref in item.get("depends_on", []):
            if ref in index:
                child_edges[ref].append(node_id)
                incoming.add(node_id)
        for child in item.get("decomposes_to", []):
            if child in index:
                child_edges[node_id].append(child)
                incoming.add(child)
    roots = [node_id for node_id in index if node_id not in incoming]
    if not roots:
        return ["roadmap graph must have at least one root"]
    seen: set[str] = set()
    queue: deque[str] = deque(sorted(roots))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(child_edges.get(current, []))
    missing = sorted(set(index) - seen)
    return ["unreachable nodes: " + ", ".join(missing)] if missing else []


def validate_roadmap(roadmap: dict[str, Any], *, label: str = "workflow-roadmap") -> list[str]:
    errors = validate_json_schema(roadmap, SCHEMA, label)
    if has_forbidden_data(roadmap):
        errors.append(f"{label}: forbidden data marker present")
    if set(roadmap.get("state_model", [])) != NODE_STATES:
        errors.append("state_model must match workflow roadmap states")
    if set(roadmap.get("node_type_model", [])) != NODE_TYPES:
        errors.append("node_type_model must match workflow roadmap node types")
    if not REQUIRED_COMMANDS <= set(roadmap.get("commands", [])):
        errors.append("commands missing required workflow_roadmap.py command")
    roles = {role.get("role_id") for role in roadmap.get("agent_roles", []) if isinstance(role, dict)}
    if roles != REQUIRED_ROLES:
        errors.append("agent_roles must match roadmap role contract")
    errors.extend(_ref_errors(roadmap))
    errors.extend(_cycle_errors(roadmap, "depends_on"))
    errors.extend(_cycle_errors(roadmap, "decomposes_to"))
    errors.extend(_reachability_errors(roadmap))
    return errors


def validate_node_for_add(node: dict[str, Any]) -> list[str]:
    shell = load(DEFAULT_ROADMAP)
    probe = dict(shell)
    probe["nodes"] = [node]
    errors = validate_json_schema(probe, SCHEMA, "node-packet")
    if has_forbidden_data(node):
        errors.append("node-packet: forbidden data marker present")
    return errors


def add_node(roadmap_path: Path, packet_path: Path) -> dict[str, Any]:
    roadmap = load(roadmap_path)
    packet = load(packet_path)
    node = node_packet(packet)
    errors = validate_node_for_add(node)
    if errors:
        raise ValueError("; ".join(errors))
    index = node_index(roadmap)
    node_id = str(node["node_id"])
    if node_id in index:
        raise ValueError(f"duplicate node_id: {node_id}")
    roadmap.setdefault("nodes", []).append(node)
    errors = validate_roadmap(roadmap)
    if errors:
        raise ValueError("; ".join(errors))
    write(roadmap_path, roadmap)
    return roadmap


def decompose(roadmap_path: Path, node_id: str) -> dict[str, Any]:
    roadmap = load(roadmap_path)
    index = node_index(roadmap)
    parent = index.get(node_id)
    if parent is None:
        raise ValueError(f"node not found: {node_id}")
    if parent.get("decomposes_to"):
        write(roadmap_path, roadmap)
        return {"schema": "bears-workflow-roadmap-decompose.v1", "status": "unchanged", "parent": node_id, "children": parent["decomposes_to"]}
    child_id = f"{node_id}.child-1"
    child = {
        "node_id": child_id,
        "issue": parent.get("issue", "null"),
        "node_type": "implementation" if parent.get("node_type") in {"research", "contract"} else parent.get("node_type", "implementation"),
        "state": "queued",
        "owner_role": "roadmap_executor",
        "source_of_truth": sorted(set(parent.get("source_of_truth", []) + ["catalog"])),
        "inputs": [f"parent:{node_id}"],
        "outputs": list(parent.get("outputs", [])),
        "depends_on": list(parent.get("depends_on", [])),
        "decomposes_to": [],
        "blocked_by": [],
        "autostart_policy": "manual_review" if parent.get("autostart_policy") == "manual_review" else "eligible",
        "evidence_paths": list(parent.get("evidence_paths", [])),
    }
    parent["outputs"] = []
    parent["decomposes_to"] = [child_id]
    parent["state"] = "decomposed"
    roadmap.setdefault("nodes", []).append(child)
    errors = validate_roadmap(roadmap)
    if errors:
        raise ValueError("; ".join(errors))
    write(roadmap_path, roadmap)
    return {"schema": "bears-workflow-roadmap-decompose.v1", "status": "created", "parent": node_id, "children": [child_id]}


def dependency_ready(node: dict[str, Any], index: dict[str, dict[str, Any]]) -> bool:
    for dep in node.get("depends_on", []):
        if index.get(dep, {}).get("state") not in DEPENDENCY_READY_STATES:
            return False
    return True


def eligible_leaf_nodes(roadmap: dict[str, Any]) -> list[dict[str, Any]]:
    index = node_index(roadmap)
    out: list[dict[str, Any]] = []
    for node in nodes(roadmap):
        if node.get("state") != "queued":
            continue
        if node.get("autostart_policy") != "eligible":
            continue
        if node.get("blocked_by"):
            continue
        if node.get("decomposes_to"):
            continue
        if not dependency_ready(node, index):
            continue
        if not executable_resource_ready(node):
            continue
        out.append(node)
    return sorted(out, key=lambda item: str(item.get("node_id")))


def next_packet(roadmap: dict[str, Any]) -> dict[str, Any]:
    selected = eligible_leaf_nodes(roadmap)
    return {
        "schema": "bears-workflow-roadmap-next.v1",
        "status": "pass",
        "delivery_id": roadmap.get("delivery_id"),
        "count": len(selected),
        "nodes": selected,
    }


def evidence_exists(path: str) -> bool:
    if path.startswith("http://") or path.startswith("https://") or "<" in path or ">" in path:
        return False
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PLUGIN_ROOT / candidate
    return candidate.exists()


def evidence_path(path: str) -> Path | None:
    """Resolve a local roadmap evidence path or return None for unsafe paths."""
    if path.startswith("http://") or path.startswith("https://") or "<" in path or ">" in path:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PLUGIN_ROOT / candidate
    try:
        candidate.resolve().relative_to(PLUGIN_ROOT)
    except ValueError:
        return None
    return candidate


def node_source_hash(node: dict[str, Any]) -> str:
    """Return the stable source hash that transition packets must bind."""
    encoded = json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def node_has_hazard_marker(node: dict[str, Any]) -> bool:
    """Return true when a node names a migration or live-operation hazard."""
    probe = {
        "node_id": node.get("node_id"),
        "issue": node.get("issue"),
        "node_type": node.get("node_type"),
        "source_of_truth": node.get("source_of_truth", []),
        "inputs": node.get("inputs", []),
        "outputs": node.get("outputs", []),
        "evidence_paths": node.get("evidence_paths", []),
    }
    text = "\n".join(strings(probe)).casefold()
    return any(marker in text for marker in ROADMAP_RECONCILE_HAZARD_MARKERS)


def resource_conflict_authorizes(node: dict[str, Any]) -> tuple[bool, list[str], str]:
    """Check resource-conflict authority for executable or validated transitions."""
    status = node.get("resource_conflict_status")
    if not isinstance(status, dict):
        return False, [], "missing_resource_conflict_status"
    gate_refs = status.get("gate_refs", [])
    if not isinstance(gate_refs, list) or not all(isinstance(ref, str) and ref for ref in gate_refs):
        gate_refs = []
    if status.get("mode") == "exclusive" and status.get("active_elsewhere") is True:
        return False, gate_refs, "exclusive_resource_active_elsewhere"
    state = str(status.get("status"))
    if state != RESOURCE_CONFLICT_ALLOW:
        return False, gate_refs, RESOURCE_CONFLICT_BLOCKED_REASONS.get(state, "missing_resource_conflict_status")
    if not gate_refs:
        return False, [], "missing_resource_conflict_status"
    return True, gate_refs, "resource_conflict_authorized"


def node_needs_resource_authority(node: dict[str, Any]) -> bool:
    """Return true when a roadmap node may become executable or validated from evidence."""
    evidence = [item for item in node.get("evidence_paths", []) if isinstance(item, str)]
    return node_has_hazard_marker(node) or bool(evidence and all(evidence_exists(item) for item in evidence))


def executable_resource_ready(node: dict[str, Any]) -> bool:
    """Return true when next --json may expose the node as executable-ready."""
    if not node_needs_resource_authority(node):
        return True
    allowed, _, _ = resource_conflict_authorizes(node)
    return allowed


def transition_packet_authorizes(node: dict[str, Any]) -> tuple[bool, list[str], str]:
    """Check whether local evidence contains a valid validated-state packet."""
    node_id = str(node.get("node_id"))
    from_state = str(node.get("state"))
    expected_hash = node_source_hash(node)
    saw_transition_packet = False
    saw_stale_packet = False
    for evidence in [item for item in node.get("evidence_paths", []) if isinstance(item, str)]:
        candidate = evidence_path(evidence)
        if candidate is None or not candidate.is_file():
            continue
        try:
            packet = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(packet, dict):
            continue
        if packet.get("schema") == TRANSITION_PACKET_SCHEMA:
            saw_transition_packet = True
        if validate_json_schema(packet, TRANSITION_PACKET_SCHEMA_PATH, "roadmap-transition-packet"):
            continue
        if packet.get("source_hash") != expected_hash:
            saw_stale_packet = True
            continue
        validator_result = packet.get("validator_command_result")
        gate_refs = packet.get("required_gate_refs", [])
        if (
            packet.get("schema") == TRANSITION_PACKET_SCHEMA
            and packet.get("status") == "pass"
            and packet.get("node_id") == node_id
            and packet.get("from_state") == from_state
            and packet.get("to_state") == "validated"
            and packet.get("source_hash") == expected_hash
            and isinstance(validator_result, dict)
            and validator_result.get("status") == "pass"
            and isinstance(gate_refs, list)
            and all(isinstance(ref, str) and ref for ref in gate_refs)
        ):
            issue = node.get("issue")
            if packet.get("issue_ref") not in (None, issue):
                continue
            return True, gate_refs, "transition_packet_authorized"
    if saw_stale_packet:
        return False, [], "stale_evidence_hash"
    if saw_transition_packet:
        return False, [], "missing_validator_packet"
    return False, [], "evidence_file_is_not_transition_authority"


def reconcile_transition_decision(node: dict[str, Any]) -> dict[str, Any]:
    """Return the fail-closed reconcile decision for one roadmap node."""
    state = str(node.get("state"))
    evidence = [item for item in node.get("evidence_paths", []) if isinstance(item, str)]
    base = {
        "node_id": str(node.get("node_id")),
        "from_state": state,
        "to_state": state,
        "status": "noop",
        "reason": "no_transition",
        "required_gate_refs": [],
    }
    if not evidence or not all(evidence_exists(item) for item in evidence):
        return base
    if state in {"validated", "closed", "blocked"}:
        return base
    base["to_state"] = "validated"
    if node.get("autostart_policy") == "disabled":
        return {**base, "status": "blocked", "reason": "disabled_preserved"}
    resource_allowed, resource_refs, resource_reason = resource_conflict_authorizes(node)
    if not resource_allowed:
        return {**base, "status": "blocked", "reason": resource_reason, "required_gate_refs": resource_refs}
    authorized, gate_refs, reason = transition_packet_authorizes(node)
    merged_gate_refs = sorted(set(resource_refs + gate_refs))
    if authorized:
        return {
            **base,
            "status": "allowed",
            "reason": "transition_packet_authorized",
            "required_gate_refs": merged_gate_refs,
        }
    if state == "manual_review" or node.get("autostart_policy") == "manual_review":
        return {**base, "status": "blocked", "reason": "manual_review_preserved", "required_gate_refs": resource_refs}
    if node_has_hazard_marker(node):
        return {**base, "status": "blocked", "reason": "hazard_requires_manual_review", "required_gate_refs": resource_refs}
    return {**base, "status": "blocked", "reason": reason, "required_gate_refs": resource_refs}


def reconcile(roadmap_path: Path) -> dict[str, Any]:
    roadmap = load(roadmap_path)
    changed: list[dict[str, str]] = []
    blocked_transitions: list[dict[str, Any]] = []
    for node in nodes(roadmap):
        old = node.get("state")
        if node.get("blocked_by"):
            node["state"] = "blocked"
        else:
            decision = reconcile_transition_decision(node)
            if decision["status"] == "allowed" and decision["to_state"] == "validated":
                node["state"] = "validated"
            elif decision["status"] == "blocked" and decision["to_state"] == "validated":
                blocked_transitions.append({
                    "node_id": str(node.get("node_id")),
                    "issue_ref": node.get("issue"),
                    "from_state": str(old),
                    "to_state": decision["to_state"],
                    "reason": decision["reason"],
                    "required_gate_refs": decision.get("required_gate_refs", []),
                })
        if node.get("state") != old:
            changed.append({"node_id": str(node.get("node_id")), "from": str(old), "to": str(node.get("state"))})
    errors = validate_roadmap(roadmap)
    if errors:
        raise ValueError("; ".join(errors))
    write(roadmap_path, roadmap)
    return {
        "schema": "bears-workflow-roadmap-reconcile.v1",
        "status": "pass",
        "changed": changed,
        "blocked_transitions": blocked_transitions,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roadmap", type=Path, default=DEFAULT_ROADMAP)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    add = sub.add_parser("add-node")
    add.add_argument("--packet", required=True, type=Path)
    decompose_cmd = sub.add_parser("decompose")
    decompose_cmd.add_argument("--node", required=True)
    next_cmd = sub.add_parser("next")
    next_cmd.add_argument("--json", action="store_true")
    reconcile_cmd = sub.add_parser("reconcile")
    reconcile_cmd.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_roadmap(load(args.roadmap))
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print("workflow roadmap ok")
            return 0
        if args.command == "add-node":
            roadmap = add_node(args.roadmap, args.packet)
            print(json.dumps({"schema": "bears-workflow-roadmap-add-node.v1", "status": "pass", "node_count": len(nodes(roadmap))}, indent=2, sort_keys=True))
            return 0
        if args.command == "decompose":
            print(json.dumps(decompose(args.roadmap, args.node), indent=2, sort_keys=True))
            return 0
        if args.command == "next":
            packet = next_packet(load(args.roadmap))
            print(json.dumps(packet, indent=2, sort_keys=True) if args.json else str(packet["count"]))
            return 0
        if args.command == "reconcile":
            packet = reconcile(args.roadmap)
            print(json.dumps(packet, indent=2, sort_keys=True) if args.json else str(len(packet["changed"])))
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
