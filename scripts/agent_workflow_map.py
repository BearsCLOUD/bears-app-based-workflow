#!/usr/bin/env python3
"""Validate the canonical Bears agent workflow map."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = PLUGIN_ROOT / "assets/catalog/agent-workflow-map.v1.json"
SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/agent-workflow-map.v1.schema.json"
STATE_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/agent-workflow-state.v1.schema.json"
WORKER_STATE_SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/agent-workflow-worker-state.v1.schema.json"
DOC_PATH = PLUGIN_ROOT / "docs/reference/agent-workflow-map.md"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts import development_workflow_validate as workflow_packets
from scripts.local_json_schema import validate_json_schema

REQUIRED_ORDER = [
    "route_gate",
    "constitution_gate",
    "research_gate",
    "prototype_gate",
    "design_gate",
    "spec_kit_gate",
    "role_gate",
    "subagent_execution",
    "validation",
    "global_review",
    "stage_boundary_audit",
    "closeout",
    "merge_ready",
    "cleanup",
]
REQUIRED_FIX_STAGE = "fix_wave"
REQUIRED_GRAPH_STAGES = REQUIRED_ORDER + [REQUIRED_FIX_STAGE]
REQUIRED_BLOCKING_GATES = ["closeout", "merge_ready", "cleanup"]
REQUIRED_LOOP_EDGES = [
    ("validation", "global_review"),
    ("global_review", "fix_wave"),
    ("fix_wave", "validation"),
]
REQUIRED_DIRTY_TRIAGE_STATES = {
    "active_parallel_agent": {
        "actions": ["track_owner", "preserve_scope", "wait_for_closeout", "integrate_evidence"],
        "gate_effect": "does_not_block_intermediate_stages",
    },
    "completed_needs_integration": {
        "actions": ["review_changed_paths", "integrate_claims", "run_validation", "record_state_update"],
        "gate_effect": "blocks_closeout_until_integrated",
    },
    "abandoned_needs_review": {
        "actions": ["freeze_scope", "review_changed_paths", "classify_value", "record_state_update"],
        "gate_effect": "blocks_cleanup_until_classified",
    },
    "useful_abandoned_code": {
        "actions": ["assign_fix_owner", "move_to_fix_wave", "validate_after_fix", "record_state_update"],
        "gate_effect": "blocks_merge_ready_until_validated_or_removed",
    },
    "obsolete_cleanup_candidate": {
        "actions": ["mark_cleanup_candidate", "wait_for_global_review", "cleanup_after_gate", "record_state_update"],
        "gate_effect": "blocks_cleanup_until_reviewed",
    },
    "unsafe_dirty_blocker": {
        "actions": ["stop_affected_scope", "isolate_files", "request_operator_review", "block_closeout_merge_ready_cleanup"],
        "gate_effect": "blocks_closeout_merge_ready_cleanup",
    },
}
REQUIRED_WORKER_STATE_POLICY = {
    "global_workflow_state_role": "index_and_aggregate_only",
    "worker_state_path_template": "runtime/agent-workflow/<goal_id>/workers/<worker_id>/worker-state.v1.json",
    "blocking_gates": REQUIRED_BLOCKING_GATES,
    "required_worker_file_fields": [
        "goal_id",
        "worker_id",
        "assigned_scope",
        "scope_lock",
        "current_stage",
        "status",
        "heartbeat_at",
        "changed_paths",
        "validation_evidence",
        "integration_status",
    ],
}
REQUIRED_HOOK_AUTOMATION_HOOKS = {
    "pre_task": {
        "writes": ["worker_state_file"],
        "reads": ["assignment_packet"],
        "actions": ["create_or_validate_worker_state", "create_or_validate_scope_lock"],
        "forbidden_writes": ["workflow_state_aggregate"],
    },
    "heartbeat": {
        "writes": ["worker_state_file"],
        "reads": ["worker_state_file"],
        "actions": ["update_heartbeat", "update_current_stage", "update_status"],
        "forbidden_writes": ["workflow_state_aggregate", "other_worker_state_files"],
    },
    "closeout": {
        "writes": ["worker_state_file"],
        "reads": ["worker_state_file", "validation_evidence"],
        "actions": ["record_worker_closeout", "record_validation_evidence", "mark_integration_needed"],
        "forbidden_writes": ["workflow_state_aggregate"],
    },
    "aggregator_index_refresh": {
        "writes": ["workflow_state_aggregate"],
        "reads": ["worker_state_files"],
        "actions": ["read_worker_files", "refresh_workflow_state_index", "refresh_workflow_state_aggregate"],
        "forbidden_writes": ["worker_state_files"],
    },
}

WORKER_HOOK_EVENT_TYPE_ALIASES = {
    "pre_task": "pre_task",
    "heartbeat": "heartbeat",
    "closeout": "closeout",
    "aggregate_index_refresh": "aggregator_index_refresh",
    "aggregator_index_refresh": "aggregator_index_refresh",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _validate_schema(packet: Any, schema_path: Path, label: str) -> list[str]:
    return validate_json_schema(packet, schema_path, label)


def render_mermaid(process_graph: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    spine = process_graph.get("spine")
    if isinstance(spine, list) and all(isinstance(item, str) for item in spine):
        for left, right in zip(spine, spine[1:]):
            lines.append(f"  {left} --> {right}")
    spine_edges = set(zip(spine, spine[1:])) if isinstance(spine, list) else set()
    for edge in process_graph.get("edges", []):
        if isinstance(edge, dict):
            left = edge.get("from")
            right = edge.get("to")
            if isinstance(left, str) and isinstance(right, str) and (left, right) not in spine_edges:
                lines.append(f"  {left} --> {right}")
    return "\n".join(lines)


def _edge_set(process_graph: dict[str, Any]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for edge in process_graph.get("edges", []):
        if isinstance(edge, dict):
            left = edge.get("from")
            right = edge.get("to")
            if isinstance(left, str) and isinstance(right, str):
                edges.add((left, right))
    return edges


def _expected_edges_from_spine(spine: list[str]) -> set[tuple[str, str]]:
    return set(zip(spine, spine[1:])) | set(REQUIRED_LOOP_EDGES)


def _dotted_get(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _validate_process_graph(process_graph: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(process_graph, dict):
        return ["process_graph must be an object"]
    spine = process_graph.get("spine")
    if not isinstance(spine, list) or not all(isinstance(item, str) for item in spine):
        return ["process_graph.spine must be a string list"]
    if spine != REQUIRED_ORDER:
        errors.append("process_graph.spine must match required workflow spine")
    edges = _edge_set(process_graph)
    for edge in _expected_edges_from_spine(spine):
        if edge not in edges:
            errors.append(f"process_graph.edges missing edge {edge[0]} -> {edge[1]}")
    blocking_gates = process_graph.get("blocking_gates")
    if blocking_gates != REQUIRED_BLOCKING_GATES:
        errors.append("process_graph.blocking_gates must match closeout, merge_ready, cleanup")
    intermediate = process_graph.get("non_blocking_intermediate_stages")
    if not isinstance(intermediate, list) or REQUIRED_FIX_STAGE not in intermediate or "global_review" not in intermediate:
        errors.append("process_graph.non_blocking_intermediate_stages must include global_review and fix_wave")
    elif any(stage in REQUIRED_BLOCKING_GATES for stage in intermediate):
        errors.append("process_graph.non_blocking_intermediate_stages must not include blocking gates")
    loop_edges = process_graph.get("loop_edges")
    if not isinstance(loop_edges, list):
        errors.append("process_graph.loop_edges must be a list")
    else:
        has_fix_loop = any(
            isinstance(edge, dict)
            and edge.get("from") == "global_review"
            and edge.get("to") == "validation"
            and edge.get("through") == ["fix_wave"]
            for edge in loop_edges
        )
        if not has_fix_loop:
            errors.append("process_graph.loop_edges must include global_review -> fix_wave -> validation")
    return errors


def _validate_stages(data: dict[str, Any], process_graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stages = data.get("stages")
    if not isinstance(stages, dict):
        return ["stages must be an object"]
    expected_stages = set(REQUIRED_GRAPH_STAGES)
    missing = sorted(expected_stages - set(stages))
    if missing:
        errors.append("stages missing required stages: " + ", ".join(missing))
    adjacency: dict[str, list[str]] = {stage: [] for stage in expected_stages}
    for left, right in _edge_set(process_graph):
        adjacency.setdefault(left, []).append(right)
    for stage in expected_stages:
        row = stages.get(stage)
        if not isinstance(row, dict):
            continue
        for field in ("required_inputs", "required_outputs", "allowed_next"):
            if not isinstance(row.get(field), list):
                errors.append(f"stages.{stage}.{field} must be a list")
        if row.get("evidence_required") is not True:
            errors.append(f"stages.{stage}.evidence_required must be true")
        expected_next = sorted(adjacency.get(stage, []))
        actual_next = row.get("allowed_next")
        if sorted(actual_next) != expected_next:
            errors.append(f"stages.{stage}.allowed_next must be {expected_next}")
        expected_blocking = stage in REQUIRED_BLOCKING_GATES
        if row.get("blocking") is not expected_blocking:
            errors.append(f"stages.{stage}.blocking must be {str(expected_blocking).lower()}")
    validation_outputs = stages.get("validation", {}).get("required_outputs") if isinstance(stages.get("validation"), dict) else []
    if "validation_evidence" not in validation_outputs:
        errors.append("validation must have evidence-bearing output")
    return errors


def _validate_review_policy(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    review_policy = data.get("review_policy")
    if not isinstance(review_policy, dict):
        return ["review_policy must be an object"]
    if review_policy.get("intermediate_review_blockers") is not False:
        errors.append("review_policy.intermediate_review_blockers must be false")
    required_before = review_policy.get("global_review_required_before")
    if not isinstance(required_before, list) or sorted(required_before) != sorted(["closeout", "merge_ready"]):
        errors.append("review_policy.global_review_required_before must require closeout and merge_ready")
    if review_policy.get("blocking_gates") != REQUIRED_BLOCKING_GATES:
        errors.append("review_policy.blocking_gates must match closeout, merge_ready, cleanup")
    global_review = review_policy.get("global_review")
    if not isinstance(global_review, dict):
        errors.append("review_policy.global_review must be an object")
    else:
        if global_review.get("stage") != "global_review":
            errors.append("review_policy.global_review.stage must be global_review")
        allowed_results = global_review.get("allowed_results")
        expected_results = {"accept", "fix_required", "unsafe_dirty_blocker"}
        if not isinstance(allowed_results, list) or set(allowed_results) != expected_results:
            errors.append("review_policy.global_review.allowed_results must match accept, fix_required, unsafe_dirty_blocker")
        if global_review.get("fix_required_next") != "fix_wave":
            errors.append("review_policy.global_review.fix_required_next must be fix_wave")
    if not isinstance(review_policy.get("orchestrator_policy"), str) or not review_policy["orchestrator_policy"].strip():
        errors.append("review_policy.orchestrator_policy must be a non-empty string")
    return errors


def _validate_state_bindings(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bindings = data.get("state_bindings")
    if not isinstance(bindings, dict):
        return ["state_bindings must be an object"]
    expected_stages = set(REQUIRED_GRAPH_STAGES)
    missing = sorted(expected_stages - set(bindings))
    if missing:
        errors.append("state_bindings missing required stages: " + ", ".join(missing))
    seen_sections: set[str] = set()
    for stage in expected_stages:
        binding = bindings.get(stage)
        if not isinstance(binding, dict):
            continue
        packet_kind = binding.get("packet_kind")
        section = binding.get("workflow_state_section")
        if not isinstance(packet_kind, str) or not packet_kind.strip():
            errors.append(f"state_bindings.{stage}.packet_kind must be a non-empty string")
        if not isinstance(section, str) or not section.strip():
            errors.append(f"state_bindings.{stage}.workflow_state_section must be a non-empty string")
        elif not section.startswith("workflow_state."):
            errors.append(f"state_bindings.{stage}.workflow_state_section must start with workflow_state.")
        elif section in seen_sections:
            errors.append(f"state_bindings.{stage}.workflow_state_section must be unique")
        else:
            seen_sections.add(section)
    return errors


def _validate_dirty_triage_policy(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = data.get("dirty_triage_policy")
    if not isinstance(policy, dict):
        return ["dirty_triage_policy must be an object"]
    if policy.get("blocking_gates") != REQUIRED_BLOCKING_GATES:
        errors.append("dirty_triage_policy.blocking_gates must match closeout, merge_ready, cleanup")
    states = policy.get("states")
    if not isinstance(states, dict):
        return errors + ["dirty_triage_policy.states must be an object"]
    if set(states) != set(REQUIRED_DIRTY_TRIAGE_STATES):
        errors.append("dirty_triage_policy.states must match the required state machine names")
    for state_name, expected in REQUIRED_DIRTY_TRIAGE_STATES.items():
        row = states.get(state_name)
        if not isinstance(row, dict):
            continue
        if not isinstance(row.get("meaning"), str) or not row["meaning"].strip():
            errors.append(f"dirty_triage_policy.states.{state_name}.meaning must be a non-empty string")
        actions = row.get("actions")
        if not isinstance(actions, list) or set(actions) != set(expected["actions"]):
            errors.append(f"dirty_triage_policy.states.{state_name}.actions must match the planned actions")
        if row.get("gate_effect") != expected["gate_effect"]:
            errors.append(f"dirty_triage_policy.states.{state_name}.gate_effect must be {expected['gate_effect']}")
    return errors


def _validate_worker_state_policy(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = data.get("worker_state_policy")
    if not isinstance(policy, dict):
        return ["worker_state_policy must be an object"]
    for field in ("worker_write_scope", "shared_aggregate_write_policy", "contention_policy", "orchestrator_non_blocking_policy"):
        if not isinstance(policy.get(field), str) or not policy[field].strip():
            errors.append(f"worker_state_policy.{field} must be a non-empty string")
    for field, expected in REQUIRED_WORKER_STATE_POLICY.items():
        if policy.get(field) != expected:
            errors.append(f"worker_state_policy.{field} must match the canonical worker-state policy")
    return errors


def _validate_hook_automation_policy(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = data.get("hook_automation_policy")
    if not isinstance(policy, dict):
        return ["hook_automation_policy must be an object"]
    if policy.get("status") != "disabled_without_trust_proof":
        errors.append("hook_automation_policy.status must be disabled_without_trust_proof")
    if policy.get("scope") != "local_only":
        errors.append("hook_automation_policy.scope must be local_only")
    if policy.get("runtime_hook_registration") != "not_changed_by_this_map":
        errors.append("hook_automation_policy.runtime_hook_registration must be not_changed_by_this_map")
    if policy.get("blocking_gates") != REQUIRED_BLOCKING_GATES:
        errors.append("hook_automation_policy.blocking_gates must match closeout, merge_ready, cleanup")
    for field in ("contention_policy", "orchestrator_non_blocking_policy"):
        if not isinstance(policy.get(field), str) or not policy[field].strip():
            errors.append(f"hook_automation_policy.{field} must be a non-empty string")
    trust_gate = policy.get("trust_gate")
    if not isinstance(trust_gate, dict):
        errors.append("hook_automation_policy.trust_gate must be an object")
    else:
        if trust_gate.get("required_proof") != ["hook_trust", "effective_hooks"]:
            errors.append("hook_automation_policy.trust_gate.required_proof must require hook_trust and effective_hooks")
        if trust_gate.get("default") != "disabled":
            errors.append("hook_automation_policy.trust_gate.default must be disabled")
        if not isinstance(trust_gate.get("enforcement"), str) or not trust_gate["enforcement"].strip():
            errors.append("hook_automation_policy.trust_gate.enforcement must be a non-empty string")
    hooks = policy.get("hooks")
    if not isinstance(hooks, dict):
        return errors + ["hook_automation_policy.hooks must be an object"]
    if set(hooks) != set(REQUIRED_HOOK_AUTOMATION_HOOKS):
        errors.append("hook_automation_policy.hooks must match the canonical hook set")
    for hook_name, expected in REQUIRED_HOOK_AUTOMATION_HOOKS.items():
        row = hooks.get(hook_name)
        if not isinstance(row, dict):
            continue
        for field, expected_value in expected.items():
            if row.get(field) != expected_value:
                errors.append(f"hook_automation_policy.hooks.{hook_name}.{field} must match the canonical hook policy")
    return errors


def _validate_roles(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    roles = data.get("roles")
    if not isinstance(roles, dict):
        return ["roles must be an object"]
    allowed_stages = set(REQUIRED_GRAPH_STAGES)
    for role, row in roles.items():
        if not isinstance(row, dict):
            errors.append(f"roles.{role} must be an object")
            continue
        may = row.get("may_run_at")
        must_not = row.get("must_not_run_at", [])
        evidence = row.get("required_evidence")
        if not isinstance(may, list) or not may:
            errors.append(f"roles.{role}.may_run_at must be non-empty")
        elif any(stage not in allowed_stages for stage in may):
            errors.append(f"roles.{role}.may_run_at contains incompatible stage")
        if isinstance(must_not, list) and set(may or []) & set(must_not):
            errors.append(f"roles.{role} is allowed and forbidden at the same stage")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"roles.{role}.required_evidence must be non-empty")
    return errors


def validate_map(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["workflow map must be an object"]
    order = data.get("canonical_order")
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        return ["canonical_order must be a string list"]
    if len(order) != len(set(order)):
        errors.append("canonical_order must not contain duplicate stages")
    if order != REQUIRED_ORDER:
        errors.append("canonical_order must match required lifecycle order")
    authority = data.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority must be an object")
    else:
        if authority.get("primary_executable_process_authority") != str(MAP_PATH.relative_to(PLUGIN_ROOT)):
            errors.append("authority.primary_executable_process_authority must point to the canonical workflow map")
        for field in ("authority_scope",):
            if not isinstance(authority.get(field), str) or not authority[field].strip():
                errors.append(f"authority.{field} must be a non-empty string")
        non_authority_surfaces = authority.get("non_authority_surfaces")
        if not isinstance(non_authority_surfaces, list) or not non_authority_surfaces:
            errors.append("authority.non_authority_surfaces must be a non-empty list")
    process_graph = data.get("process_graph")
    errors.extend(_validate_process_graph(process_graph))
    if isinstance(process_graph, dict):
        errors.extend(_validate_stages(data, process_graph))
    errors.extend(_validate_review_policy(data))
    errors.extend(_validate_state_bindings(data))
    errors.extend(_validate_dirty_triage_policy(data))
    errors.extend(_validate_worker_state_policy(data))
    errors.extend(_validate_hook_automation_policy(data))
    errors.extend(_validate_roles(data))
    if isinstance(process_graph, dict) and data.get("generated_mermaid") != render_mermaid(process_graph):
        errors.append("generated_mermaid must match process_graph.edges")
    return errors


def validate_state_file(map_data: Any, state_data: Any, *, state_file: Path) -> list[str]:
    errors = validate_map(map_data)
    if errors:
        return errors
    if not isinstance(state_data, dict):
        return ["workflow state must be an object"]
    bindings = map_data.get("state_bindings")
    if not isinstance(bindings, dict):
        return ["state_bindings must be an object"]
    if state_data.get("state_kind") == "workflow_state_index" or "worker_state_refs" in state_data:
        errors.extend(_validate_schema(state_data, STATE_SCHEMA_PATH, "workflow-state"))
    for stage, binding in bindings.items():
        if not isinstance(binding, dict):
            continue
        section_path = binding.get("workflow_state_section")
        section = _dotted_get(state_data, section_path) if isinstance(section_path, str) else None
        if isinstance(section, dict):
            explicit_kind = section.get("packet_kind")
            expected_kind = binding.get("packet_kind")
            if explicit_kind is not None and explicit_kind != expected_kind:
                errors.append(f"workflow state section {section_path} packet_kind must match {expected_kind}")
    errors.extend(
        workflow_packets.validate_workflow_state_references(
            state_data,
            bindings,
            base_dir=state_file.parent,
        )
    )
    worker_state_refs = state_data.get("worker_state_refs")
    if worker_state_refs is not None and not isinstance(worker_state_refs, list):
        errors.append("workflow-state.worker_state_refs must be a list")
    elif isinstance(worker_state_refs, list):
        for index, row in enumerate(worker_state_refs):
            if not isinstance(row, dict):
                errors.append(f"workflow-state.worker_state_refs[{index}] must be an object")
                continue
            state_ref = row.get("path")
            if not isinstance(state_ref, str) or not state_ref.strip():
                errors.append(f"workflow-state.worker_state_refs[{index}].path must be a non-empty string")
                continue
            path_errors, _ = workflow_packets.validate_local_packet_ref_path(
                state_ref,
                base_dir=state_file.parent,
            )
            if path_errors:
                errors.extend(
                    f"workflow-state.worker_state_refs[{index}].{message}"
                    for message in path_errors
                )
                continue
            resolved = workflow_packets.resolve_local_packet_path(
                state_ref,
                base_dir=state_file.parent,
                packet_kind="workflow-worker-state",
            )
            if resolved is None:
                candidate = state_file.parent / state_ref
                errors.append(
                    "workflow-state.worker_state_refs"
                    f"[{index}].path does not resolve to a local worker-state file: {candidate}"
                )
                continue
            errors.extend(validate_worker_state_file(map_data, load_json(resolved), state_file=resolved))
    return errors


def validate_worker_state_file(map_data: Any, state_data: Any, *, state_file: Path) -> list[str]:
    errors = validate_map(map_data)
    if errors:
        return errors
    if not isinstance(state_data, dict):
        return ["worker state must be an object"]
    errors.extend(_validate_schema(state_data, WORKER_STATE_SCHEMA_PATH, "worker-state"))
    errors.extend(
        workflow_packets.validate_local_packet_ref_records(
            state_data,
            base_dir=state_file.parent,
            root_path="worker-state",
        )
    )
    worker_state_path = state_data.get("worker_state_path")
    if isinstance(worker_state_path, str):
        hook_events = state_data.get("hook_events")
        if isinstance(hook_events, list):
            for index, row in enumerate(hook_events):
                if not isinstance(row, dict):
                    errors.append(f"worker-state.hook_events[{index}] must be an object")
                    continue
                event_type = row.get("event_type")
                if not isinstance(event_type, str):
                    errors.append(f"worker-state.hook_events[{index}].event_type must be a non-empty string")
                    continue
                normalized_type = WORKER_HOOK_EVENT_TYPE_ALIASES.get(event_type)
                if normalized_type is None:
                    errors.append(f"worker-state.hook_events[{index}].event_type is not allowed")
                    continue
                if row.get("requires_network") is not False:
                    errors.append(f"worker-state.hook_events[{index}].requires_network must be false")
                write_scope = row.get("write_scope")
                target_path = row.get("target_path")
                if normalized_type == "aggregator_index_refresh":
                    if write_scope != "aggregate_index":
                        errors.append(
                            f"worker-state.hook_events[{index}].write_scope must be aggregate_index for aggregator refresh"
                        )
                    if not isinstance(target_path, str) or not target_path.endswith("/workflow-state.v1.json"):
                        errors.append(
                            f"worker-state.hook_events[{index}].target_path must point to workflow-state.v1.json for aggregator refresh"
                        )
                else:
                    if write_scope != "own_worker_state":
                        errors.append(
                            f"worker-state.hook_events[{index}].write_scope must be own_worker_state for worker-local hooks"
                        )
                    if target_path != worker_state_path:
                        errors.append(
                            f"worker-state.hook_events[{index}].target_path must match worker_state_path for worker-local hooks"
                        )
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    schema = load_json(SCHEMA_PATH)
    if schema.get("type") != "object":
        errors.append("schema type must be object")
    required = schema.get("required")
    expected_schema_fields = {
        "authority",
        "process_graph",
        "subagent_execution_tree",
        "review_policy",
        "state_bindings",
        "dirty_triage_policy",
        "worker_state_policy",
        "hook_automation_policy",
    }
    if not isinstance(required, list) or not expected_schema_fields.issubset(required):
        errors.append("schema.required must include extended workflow fields")
    data = load_json(MAP_PATH)
    errors.extend(validate_map(data))
    doc = DOC_PATH.read_text(encoding="utf-8")
    if str(MAP_PATH.relative_to(PLUGIN_ROOT)) not in doc:
        errors.append("reference doc must point to canonical workflow map")
    if data.get("generated_mermaid", "") not in doc:
        errors.append("reference doc mermaid block must match generated map")
    for marker in (
        "`global_review` is required before `closeout` and `merge_ready`",
        "`unsafe_dirty_blocker`: blocks_closeout_merge_ready_cleanup.",
        "`merge_ready` -> `merge-ready-packet` -> `workflow_state.merge_ready`",
    ):
        if marker not in doc:
            errors.append("reference doc must describe extended review or state binding rules")
            break
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "SPEC.md"):
        text = path.read_text(encoding="utf-8")
        if "assets/catalog/agent-workflow-map.v1.json" not in text:
            errors.append(f"{path.name} must identify agent workflow map as canonical source")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "validate-state", "validate-worker-state", "render-mermaid"])
    parser.add_argument("--state-file", dest="state_file")
    args = parser.parse_args(argv)

    data = load_json(MAP_PATH)
    if args.command == "render-mermaid":
        print(render_mermaid(data["process_graph"]))
        return 0
    if args.command == "validate-state":
        if not args.state_file:
            parser.error("validate-state requires --state-file")
        state_path = Path(args.state_file)
        if not state_path.is_file():
            errors = [f"state file not found: {state_path}"]
        else:
            errors = validate_state_file(data, load_json(state_path), state_file=state_path)
    elif args.command == "validate-worker-state":
        if not args.state_file:
            parser.error("validate-worker-state requires --state-file")
        state_path = Path(args.state_file)
        if not state_path.is_file():
            errors = [f"state file not found: {state_path}"]
        else:
            errors = validate_worker_state_file(data, load_json(state_path), state_file=state_path)
    else:
        errors = validate_all()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.command in {"validate-state", "validate-worker-state"}:
        print("agent workflow state ok")
    else:
        print("agent workflow map ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
