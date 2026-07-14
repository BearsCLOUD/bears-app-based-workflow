"""Append immutable process v3 records with exact repo-wave lifecycle rules."""

from __future__ import annotations

from collections import defaultdict, deque
import fcntl
import json
import os
import re
import secrets
from typing import Any

from app_graph_store import *


STAGES = (
    "app-constitution",
    "app-research",
    "app-specify",
    "app-functional-graph",
    "app-plan",
    "app-dev",
    "app-analyze",
)
ACTORS = {"DIRECT-primary", "repo-L2"}
EVENT_KINDS = {
    "run-start", "stage", "delegation", "task-result", "review",
    "repo-handoff", "analysis",
}
STATUSES = {
    "constitution-ready", "needs-research", "research-ready", "needs-spec",
    "spec-ready", "needs-graph", "graph-ready", "waiting", "needs-plan",
    "plan-ready", "ready", "in_progress", "implemented", "no-work",
    "audited", "done", "failed", "blocked", "superseded",
}
FINDING_ROUTES = {
    "missing-source": "needs-research",
    "product-conflict": "needs-spec",
    "decision-conflict": "needs-spec",
    "semantic-gap": "needs-graph",
    "reference-gap": "needs-graph",
    "cycle-gap": "needs-graph",
    "task-gap": "needs-plan",
    "implementation-gap": "needs-plan",
    "evidence-gap": "needs-plan",
    "review-gap": "needs-plan",
    "remediation-gap": "needs-plan",
    "credential-stop": "blocked",
    "access-stop": "blocked",
    "operator-stop": "blocked",
}
ROUTES = {
    "constitution-ready": "app-research",
    "needs-research": "app-research",
    "research-ready": "app-specify",
    "needs-spec": "app-specify",
    "spec-ready": "app-functional-graph",
    "needs-graph": "app-functional-graph",
    "graph-ready": "app-plan",
    "waiting": "app-plan",
    "needs-plan": "app-plan",
    "plan-ready": "app-dev",
    "ready": "app-dev",
    "implemented": "app-analyze",
    "no-work": "app-analyze",
    "audited": "none",
    "blocked": "none",
}
ANALYSIS_ROUTE_REDUCTION = {
    "blocked_dominance": True,
    "corrective_priority": ["needs-research", "needs-spec", "needs-graph", "needs-plan"],
    "clean_route": "none",
}
CORRECTIVE_BOUNDARY_STATUSES = {
    "needs-research", "needs-spec", "needs-graph", "needs-plan", "blocked",
}
EDGE_TYPES = {
    "depends_on": {
        "family": "dependency", "direction": "dependent-to-prerequisite",
        "transitive": True, "impact": True, "topological": True,
        "cycle": "forbidden",
    },
    "constrains": {
        "family": "dependency", "direction": "constraint-to-constrained",
        "transitive": True, "impact": True, "topological": False,
        "cycle": "forbidden",
    },
    "defines": {
        "family": "trace", "direction": "defining-to-defined",
        "transitive": False, "impact": True, "topological": False,
        "cycle": "forbidden",
    },
    "decomposes_to": {
        "family": "trace", "direction": "aggregate-to-component",
        "transitive": True, "impact": True, "topological": False,
        "cycle": "forbidden",
    },
    "implemented_by": {
        "family": "trace", "direction": "task-to-implementation",
        "transitive": True, "impact": True, "topological": False,
        "cycle": "forbidden",
    },
    "evidenced_by": {
        "family": "trace", "direction": "claim-to-evidence",
        "transitive": True, "impact": True, "topological": False,
        "cycle": "forbidden",
    },
    "replaces": {
        "family": "replacement", "direction": "replacement-to-replaced",
        "transitive": True, "impact": True, "topological": False,
        "cycle": "forbidden",
    },
    "remediates": {
        "family": "process", "direction": "corrective-to-source",
        "transitive": False, "impact": True, "topological": False,
        "cycle": "forbidden", "single_successor": True,
        "single_successor_scope": "source-run",
    },
}
WORKFLOW_SCHEMA_REFS = {
    "handoff_schema": "contracts/app-stage-handoff.v4.schema.json",
    "manifest_schema": "contracts/app-graph-source-manifest.v1.schema.json",
    "event_schema": "contracts/app-process-event.v3.schema.json",
    "task_ledger_schema": "contracts/app-task-ledger.v3.schema.json",
    "artifact_catalog_schema": "contracts/app-artifact-catalog.v2.schema.json",
    "functional_map_schema": "contracts/app-functional-map.v4.schema.json",
    "traceability_index_schema": "contracts/app-traceability-index.v4.schema.json",
    "process_index_schema": "contracts/app-process-index.v4.schema.json",
    "index_build_schema": "contracts/app-index-build.v1.schema.json",
    "semantic_analysis_schema": "contracts/app-semantic-analysis-result.v1.schema.json",
    "context_result_schema": "contracts/app-context-index-result.v2.schema.json",
    "compile_result_schema": "contracts/app-graph-compile-result.v2.schema.json",
}
WORKFLOW_FIELDS = {
    "schema", *WORKFLOW_SCHEMA_REFS, "entry_gate", "stages", "stage_owners",
    "event_rules", "routes", "finding_routes", "analysis_route_reduction",
    "analysis_gate", "remediation_gate", "handoff_gate", "publication_gate",
    "delegated_process", "graph", "protocol_persistence",
}
EVENT_RULES = {
    "run-start": {
        "app-constitution": ["constitution-ready"],
        "app-plan": ["plan-ready"],
    },
    "stage": {
        "app-research": ["needs-research", "research-ready", "blocked"],
        "app-specify": ["needs-research", "needs-spec", "spec-ready", "blocked"],
        "app-functional-graph": ["needs-research", "needs-spec", "needs-graph", "graph-ready", "blocked"],
        "app-plan": [
            "needs-research", "needs-spec", "needs-graph", "waiting",
            "needs-plan", "plan-ready", "ready", "no-work", "blocked",
        ],
        "app-dev": ["needs-research", "needs-spec", "needs-graph", "needs-plan", "blocked"],
    },
    "delegation": {stage: ["in_progress"] for stage in STAGES if stage != "app-analyze"},
    "task-result": {"app-dev": ["done", "failed", "blocked"]},
    "review": {"app-dev": ["done"]},
    "repo-handoff": {"app-dev": ["implemented"]},
    "analysis": {
        "app-analyze": [
            "needs-research", "needs-spec", "needs-graph", "needs-plan",
            "audited", "blocked",
        ],
    },
}
REQUIRED_STRINGS = (
    "run_ref", "event_ref", "event_kind", "stage", "status", "actor",
    "owner_session_ref", "repo_ref", "wave_ref", "origin",
)
REQUIRED_ARRAYS = ("causal_refs", "trace_refs", "artifact_refs", "task_refs")
TASK_SPEC_EXCLUDED_FIELDS = {"status", "replacement_task_refs"}
OPTIONAL_FIELDS = {
    "task_ref", "terminal_result", "reviewed_task_refs", "finding_refs",
    "commit_range", "remediates_run_ref", "analysis_ref", "analysis_result",
    "delegation_record", "delegation_records", "commit_refs", "changed_paths", "handoff_payload_digest",
    "finding_records", "replacement_bindings",
}
OPTIONAL_BY_KIND = {
    "run-start": {"remediates_run_ref", "handoff_payload_digest"},
    "stage": {"finding_refs", "finding_records", "replacement_bindings", "handoff_payload_digest"},
    "delegation": {"delegation_record"},
    "task-result": {"task_ref", "terminal_result", "commit_refs", "changed_paths"},
    "review": {"reviewed_task_refs", "commit_range", "finding_refs", "finding_records"},
    "repo-handoff": {"handoff_payload_digest"},
    "analysis": {"analysis_ref", "analysis_result", "delegation_records", "handoff_payload_digest"},
}
HANDOFF_EVENT_KINDS = {"run-start", "stage", "repo-handoff", "analysis"}
ANALYSIS_FIELDS = {
    "schema", "analysis_ref", "profile_ref", "model_ref", "checklist_ref",
    "basis_build_ref", "input_refs", "coverage", "findings",
    "unmapped_decision_refs", "unmapped_requirement_refs",
    "open_remediation_refs", "complete", "route",
}
ANALYSIS_STRING_FIELDS = {
    "analysis_ref", "profile_ref", "model_ref", "checklist_ref", "basis_build_ref",
}
COVERAGE_TO_INPUT = {
    "sources": "source_refs",
    "decisions": "decision_refs",
    "requirements": "requirement_refs",
    "functionalities": "functionality_refs",
    "dimensions": "dimension_refs",
    "dimension_mappings": "dimension_mapping_refs",
    "relations": "relation_refs",
    "graph_edges": "graph_edge_refs",
    "functional_map": "functional_map_refs",
    "ledger": "ledger_refs",
    "artifacts": "artifact_refs",
    "evidence": "evidence_refs",
    "tasks": "task_refs",
    "task_results": "task_result_refs",
    "reviews": "review_refs",
    "remediations": "remediation_refs",
    "process_records": "process_record_refs",
    "incoming_handoff": "incoming_handoff_refs",
}
COVERAGE_FIELDS = set(COVERAGE_TO_INPUT)
ANALYSIS_INPUT_FIELDS = set(COVERAGE_TO_INPUT.values())
FINDING_FIELDS = {
    "finding_ref", "kind", "subject_refs", "conflict_refs", "route", "summary",
}
DIMENSION_KINDS = {"behavior", "dependency", "state", "api", "data", "integration", "error"}
ARTIFACT_KINDS = {"code", "configuration", "document", "evidence"}
DELEGATION_FIELDS = {
    "dispatch_schema", "result_schema", "delegation_authority_ref",
    "assignment_authority_ref", "assignment_id", "task_id", "role",
    "role_kind", "agent_level", "orchestrator_session_id",
    "result_ref", "result_digest", "completion_status",
    "profile_ref", "model_ref", "checklist_ref",
}
DELEGATION_OPTIONAL_FIELDS = {"app_task_schema"}
GIT_REF = re.compile(r"^[0-9a-f]{40}$")
COMMIT_RANGE = re.compile(r"^[0-9a-f]{40}\.\.[0-9a-f]{40}$")


def _valid_refs(value: Any, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item) for item in value)
        and len(value) == len(set(value))
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _valid_git_refs(value: Any, *, allow_empty: bool = True) -> bool:
    return (
        _valid_refs(value, allow_empty=allow_empty)
        and all(GIT_REF.fullmatch(item) is not None for item in value)
    )


def _ref_set_binding(refs: list[str]) -> dict[str, Any]:
    ordered = sorted(set(refs))
    return {"count": len(ordered), "refs_digest": digest_bytes(canonical(ordered))}


def _task_spec_digest(task: dict[str, Any]) -> str:
    stable = {
        field: value
        for field, value in task.items()
        if field not in TASK_SPEC_EXCLUDED_FIELDS
    }
    return digest_bytes(canonical(stable))


def _expected_task_spec_bindings(
    task_refs: list[str],
    tasks: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    bindings: list[dict[str, str]] = []
    for task_ref in sorted(task_refs):
        task = tasks.get(task_ref)
        if not isinstance(task, dict):
            raise GraphError("DANGLING_REF", "task spec binding references a missing task", task_ref=task_ref)
        bindings.append({"task_ref": task_ref, "task_spec_digest": _task_spec_digest(task)})
    return bindings


def _open_remediation_refs(tasks: dict[str, dict[str, Any]], done_task_refs: set[str]) -> list[str]:
    """Keep superseded remediation open until every replacement leaf is closed."""
    remediation_refs = {
        task_ref for task_ref, task in tasks.items()
        if task.get("task_kind") == "remediation"
    }
    closed = {
        task_ref for task_ref in remediation_refs
        if tasks[task_ref].get("status") != "superseded" and task_ref in done_task_refs
    }
    replacement_parents: dict[str, set[str]] = defaultdict(set)
    for task_ref in remediation_refs:
        if tasks[task_ref].get("status") != "superseded":
            continue
        for replacement_ref in tasks[task_ref].get("replacement_task_refs", []):
            replacement_parents[replacement_ref].add(task_ref)
    queue = deque(sorted(closed))
    while queue:
        closed_ref = queue.popleft()
        for parent_ref in sorted(replacement_parents.get(closed_ref, set())):
            if parent_ref in closed:
                continue
            replacements = tasks[parent_ref].get("replacement_task_refs", [])
            if replacements and all(replacement_ref in closed for replacement_ref in replacements):
                closed.add(parent_ref)
                queue.append(parent_ref)
    return sorted(remediation_refs - closed)


def _analysis_expected_state(
    event: dict[str, Any],
    trace: dict[str, Any],
    process: dict[str, Any],
    functional_map: dict[str, Any],
    ledger: dict[str, Any],
) -> tuple[dict[str, Any], list[str], dict[str, int]]:
    """Derive exact categorized analysis bindings from one predecessor bundle."""
    locator_paths: list[str] = []
    for locator in trace.get("generated_from", []):
        if (
            not isinstance(locator, dict)
            or set(locator) != {"path", "digest"}
            or not _nonempty_string(locator.get("path"))
            or not valid_digest(locator.get("digest"))
            or locator["path"] in locator_paths
        ):
            raise GraphError("BUILD_RECEIPT_INVALID", "trace source locator is invalid")
        locator_paths.append(locator["path"])
    entities = trace.get("entities", [])
    edges = trace.get("edges", [])
    process_events = process.get("events", [])
    if not all(isinstance(items, list) for items in (entities, edges, process_events)):
        raise GraphError("BUILD_RECEIPT_INVALID", "analysis predecessor collections are invalid")
    task_by_ref = {
        task["task_id"]: task
        for task in ledger.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }
    remediation_refs = sorted(
        task_ref for task_ref, task in task_by_ref.items()
        if task.get("task_kind") == "remediation"
    )
    done_task_refs = {
        item["task_ref"]
        for item in process_events
        if item.get("event_kind") == "task-result" and item.get("terminal_result") == "done"
    }
    expected_ref_sets = {
        "source_refs": sorted(locator_paths),
        "decision_refs": sorted(item["ref"] for item in entities if item.get("kind") == "decision"),
        "requirement_refs": sorted(item["ref"] for item in entities if item.get("kind") == "requirement"),
        "functionality_refs": sorted(item["ref"] for item in entities if item.get("kind") == "functionality"),
        "dimension_refs": sorted(item["ref"] for item in entities if item.get("kind") in DIMENSION_KINDS),
        "dimension_mapping_refs": sorted(item["ref"] for item in functional_map.get("coverage", [])),
        "relation_refs": sorted(item["ref"] for item in functional_map.get("relations", [])),
        "graph_edge_refs": sorted(item["ref"] for item in edges),
        "functional_map_refs": [SOURCE_PATHS["functional_map"]],
        "ledger_refs": [SOURCE_PATHS["task_ledger"]],
        "artifact_refs": sorted(
            item["ref"] for item in entities
            if item.get("kind") in ARTIFACT_KINDS - {"evidence"}
        ),
        "evidence_refs": sorted(item["ref"] for item in entities if item.get("kind") == "evidence"),
        "task_refs": sorted(item["ref"] for item in entities if item.get("kind") == "task"),
        "task_result_refs": sorted(
            item["event_ref"] for item in process_events if item.get("event_kind") == "task-result"
        ),
        "review_refs": sorted(
            item["event_ref"] for item in process_events if item.get("event_kind") == "review"
        ),
        "remediation_refs": remediation_refs,
        "process_record_refs": sorted(item["event_ref"] for item in process_events),
        "incoming_handoff_refs": list(event["causal_refs"]),
    }
    expected_inputs = {
        category: _ref_set_binding(refs)
        for category, refs in expected_ref_sets.items()
    }
    expected_open = _open_remediation_refs(task_by_ref, done_task_refs)
    expected_coverage = {
        count_field: expected_inputs[input_field]["count"]
        for count_field, input_field in COVERAGE_TO_INPUT.items()
    }
    return expected_inputs, expected_open, expected_coverage


def _validate_analysis_basis_binding(
    event: dict[str, Any],
    build: dict[str, Any],
    trace: dict[str, Any],
    process: dict[str, Any],
    functional_map: dict[str, Any],
    ledger: dict[str, Any],
) -> None:
    result = event["analysis_result"]
    if result["basis_build_ref"] != build["build_ref"]:
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis basis is not the immediate predecessor build")
    expected_inputs, expected_open, expected_coverage = _analysis_expected_state(
        event, trace, process, functional_map, ledger,
    )
    if result["input_refs"] != expected_inputs:
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis inputs disagree with its predecessor build")
    if result["open_remediation_refs"] != expected_open:
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis open remediation lineage disagrees with its predecessor build")
    if result["coverage"] != expected_coverage:
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis coverage disagrees with its predecessor build")
    entity_kinds = {
        item.get("ref"): item.get("kind")
        for item in trace.get("entities", [])
        if isinstance(item, dict)
    }
    if any(entity_kinds.get(ref) != "decision" for ref in result["unmapped_decision_refs"]):
        raise GraphError("ANALYSIS_BASIS_INVALID", "unmapped decision refs are not predecessor decisions")
    if any(entity_kinds.get(ref) != "requirement" for ref in result["unmapped_requirement_refs"]):
        raise GraphError("ANALYSIS_BASIS_INVALID", "unmapped requirement refs are not predecessor requirements")


def _route_registry(workflow: dict[str, Any] | None) -> dict[str, str]:
    if workflow is None:
        return FINDING_ROUTES
    routes = workflow.get("finding_routes")
    if routes != FINDING_ROUTES:
        raise GraphError("SCHEMA_UNSUPPORTED", "workflow finding routes drifted from the runtime")
    return routes


def _route_reduction(workflow: dict[str, Any] | None) -> dict[str, Any]:
    if workflow is None:
        return ANALYSIS_ROUTE_REDUCTION
    reduction = workflow.get("analysis_route_reduction")
    if reduction != ANALYSIS_ROUTE_REDUCTION:
        raise GraphError("SCHEMA_UNSUPPORTED", "workflow analysis route reduction is invalid")
    return reduction


def _validate_finding_record(finding: Any, routes: dict[str, str]) -> str:
    if not isinstance(finding, dict) or set(finding) != FINDING_FIELDS:
        raise GraphError("FINDING_INVALID", "finding fields are incomplete")
    finding_ref = finding.get("finding_ref")
    kind = finding.get("kind")
    if (
        not _nonempty_string(finding_ref)
        or kind not in routes
        or finding.get("route") != routes[kind]
        or not _nonempty_string(finding.get("summary"))
        or not _valid_refs(finding.get("subject_refs"), allow_empty=False)
        or not _valid_refs(finding.get("conflict_refs"))
    ):
        raise GraphError("FINDING_INVALID", "finding identity, references, or route is invalid")
    return finding_ref


def _reduced_finding_route(records: list[dict[str, Any]], reduction: dict[str, Any]) -> str:
    routes = {record["route"] for record in records}
    if reduction["blocked_dominance"] and "blocked" in routes:
        return "blocked"
    return next(
        (candidate for candidate in reduction["corrective_priority"] if candidate in routes),
        reduction["clean_route"],
    )


def _validate_workflow(workflow: Any) -> dict[str, str]:
    expected_entry_gate = {
        "skill": "app-context-index",
        "compiler_skill": "app-graph-compile",
        "run_at": ["run-start", "wave-start", "source-drift", "needs-index"],
        "unchanged_action": "reuse-current-build",
    }
    expected_analysis_gate = {
        "exact_source_snapshot": True,
        "basis": "immediate-predecessor-build",
        "applies_to": "every-analysis-outcome",
        "allowed_delta": "one-native-analysis-event",
        "exact_categorized_inputs": True,
        "exact_open_remediation_lineage": True,
        "audited": {
            "semantic_analysis_complete": True,
            "logical_contradictions": 0,
            "unmapped_decisions": 0,
            "unmapped_requirements": 0,
            "routable_findings": 0,
            "open_remediation_tasks": 0,
            "meaning": "constitution-specification-semantic-and-process-consistency",
        },
    }
    expected_remediation_gate = {
        "source_boundary": {
            "event_kind": "stage", "stage": "app-plan", "status": "needs-plan",
        },
        "successor_boundary": {
            "event_kind": "run-start", "stage": "app-plan", "status": "plan-ready",
        },
        "link_field": "remediates_run_ref",
        "single_successor": True,
        "acyclic": True,
        "recursive_replacement_basis": "current-correction-run",
        "replacement_lineage_acyclic": True,
    }
    expected_handoff_gate = {
        "schema": "app-stage-handoff.v4",
        "validator": "handoff_validate",
        "exact_current_build": True,
        "sole_current_run_leaf": True,
        "exact_event_and_payload_binding": True,
    }
    expected_publication_gate = {
        "compare_and_swap": True,
        "source_snapshot_recheck": True,
        "immutable_bundle_before_pointer": True,
        "analysis_delta": "one-native-analysis-event",
    }
    expected_delegated = {
        "repo_l2_scope": "all-app-stages",
        "journal_writer": "repo-orchestrator-or-DIRECT-primary",
        "l3_journal_write": False,
        "l3_dispatch_skill": "subagents",
        "l3_dispatch_owner_role_kind": "repo-orchestrator",
        "task_states": ["waiting", "ready", "in_progress", "done", "failed", "blocked", "superseded"],
        "l1_role": "workflow-orchestrator",
        "l1_role_kind": "workflow-orchestrator",
        "l1_authority": "native-repo-lane-coordination-only",
        "l1_may_own_app_stages": False,
        "l1_may_select_routes": False,
        "l1_may_write_journal": False,
        "l1_may_dispatch_l3": False,
        "repo_l2_role": "domain-lane-orchestrator",
        "repo_l2_role_kind": "repo-orchestrator",
        "repo_lane_schema": "repo-lane-dispatch.v1",
        "delegation_record": {
            "event_schema": "app-process-event.v3",
            "dispatch_schema": "dispatch-packet.v3",
            "result_schema": "result-packet.v2",
            "app_task_schema": "app-task-dispatch.v2",
            "durable_scope": "represented-l3-identity-and-completion-only",
            "analysis_persistence": "embedded-explorer-on-analysis-event",
            "analysis_role": "explorer",
            "completion_fields": [
                "result_ref", "result_digest", "completion_status",
                "profile_ref", "model_ref", "checklist_ref",
            ],
        },
        "native_event_kinds": [
            "run-start", "stage", "delegation", "task-result", "review",
            "repo-handoff", "analysis",
        ],
    }
    expected_graph = {
        "required_trace": [
            "spec", "decision", "requirement", "functionality-or-behavior",
            "task", "implementation-artifact", "evidence",
        ],
        "edge_types": EDGE_TYPES,
    }
    expected_protocol = {
        "native_event": "durable-graph-source",
        "lane_packet": "typed-transient",
        "l3_packet": "typed-transient",
        "outgoing_handoff": "typed-transient-build-bound",
        "route_application": "every-causal-adjacency",
        "corrective_boundary_evidence": "typed-finding-except-failed-task-needs-plan",
    }
    if (
        not isinstance(workflow, dict)
        or set(workflow) != WORKFLOW_FIELDS
        or workflow.get("schema") != "app-workflow-definition.v3"
        or any(workflow.get(field) != value for field, value in WORKFLOW_SCHEMA_REFS.items())
        or workflow.get("entry_gate") != expected_entry_gate
        or workflow.get("stages") != list(STAGES)
        or workflow.get("stage_owners") != {"DIRECT": "DIRECT-primary", "DELEGATED": "persistent-repo-L2"}
        or workflow.get("event_rules") != EVENT_RULES
        or workflow.get("routes") != ROUTES
        or workflow.get("finding_routes") != FINDING_ROUTES
        or workflow.get("analysis_route_reduction") != ANALYSIS_ROUTE_REDUCTION
        or workflow.get("analysis_gate") != expected_analysis_gate
        or workflow.get("remediation_gate") != expected_remediation_gate
        or workflow.get("handoff_gate") != expected_handoff_gate
        or workflow.get("publication_gate") != expected_publication_gate
        or workflow.get("delegated_process") != expected_delegated
        or workflow.get("graph") != expected_graph
        or workflow.get("protocol_persistence") != expected_protocol
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", "workflow event or route registry is invalid")
    return ROUTES


def _validate_delegation_record(event: dict[str, Any], record: Any) -> None:
    if event["actor"] != "repo-L2":
        raise GraphError("OWNERSHIP_INVALID", "DIRECT runs cannot delegate")
    if not isinstance(record, dict) or set(record) - (DELEGATION_FIELDS | DELEGATION_OPTIONAL_FIELDS):
        raise GraphError("DELEGATION_INVALID", "delegation needs one typed delegation record")
    if set(record) - DELEGATION_OPTIONAL_FIELDS != DELEGATION_FIELDS:
        raise GraphError("DELEGATION_INVALID", "delegation record fields are incomplete")
    string_fields = DELEGATION_FIELDS - {"dispatch_schema", "result_schema", "role_kind", "agent_level"}
    if any(not _nonempty_string(record.get(field)) for field in string_fields):
        raise GraphError("DELEGATION_INVALID", "delegation identity fields are incomplete")
    if (
        record.get("dispatch_schema") != "dispatch-packet.v3"
        or record.get("result_schema") != "result-packet.v2"
        or record.get("agent_level") != "L3"
        or record.get("role_kind") not in {"helper", "mutation-worker", "primary-critic"}
        or record.get("app_task_schema") not in (None, "app-task-dispatch.v2")
        or record.get("completion_status") != "completed"
        or not valid_digest(record.get("result_digest"))
    ):
        raise GraphError("DELEGATION_INVALID", "delegation packet identity is invalid")
    if (record["role"] == "app-worker") != (record.get("app_task_schema") == "app-task-dispatch.v2"):
        raise GraphError("DELEGATION_INVALID", "app task packet identity disagrees with the selected role")
    if record["role"] == "app-worker":
        if record["role_kind"] != "mutation-worker" or record["task_id"] not in event["task_refs"]:
            raise GraphError("RUN_SCOPE_INVALID", "app-worker delegation is outside the ledger task scope")
    elif (record["role"] == "worker") != (record["role_kind"] == "mutation-worker"):
        raise GraphError("DELEGATION_INVALID", "non-task mutation completion requires exactly the worker role")
    if (record["role"] == "wave-change-critic") != (record["role_kind"] == "primary-critic"):
        raise GraphError("DELEGATION_INVALID", "primary review completion requires exactly the critic role")
    if record["orchestrator_session_id"] != event["owner_session_ref"]:
        raise GraphError("OWNERSHIP_INVALID", "delegation session differs from the run owner session")


def _validate_delegation(event: dict[str, Any]) -> None:
    _validate_delegation_record(event, event.get("delegation_record"))


def _validate_analysis_delegations(event: dict[str, Any]) -> None:
    """Bind the completed L3 explorer result into the sole analysis delta event."""
    records = event.get("delegation_records")
    if event["actor"] == "DIRECT-primary":
        if records not in (None, []):
            raise GraphError("DELEGATION_INVALID", "DIRECT analysis cannot carry L3 completions")
        return
    if not isinstance(records, list) or len(records) != 1:
        raise GraphError(
            "DELEGATION_INVALID",
            "repo-L2 analysis needs exactly one embedded explorer completion",
            event_ref=event["event_ref"],
        )
    _validate_delegation_record(event, records[0])

    result = event["analysis_result"]
    result_identity = (
        result["profile_ref"], result["model_ref"], result["checklist_ref"],
    )
    analyst = records[0]
    if not (
        analyst["role"] == "explorer"
        and analyst["role_kind"] == "helper"
        and analyst["task_id"] == event["analysis_ref"]
        and analyst["result_ref"] == event["analysis_ref"]
        and analyst["result_digest"] == digest_bytes(canonical(result))
        and tuple(
            analyst[field] for field in ("profile_ref", "model_ref", "checklist_ref")
        ) == result_identity
    ):
        raise GraphError("DELEGATION_INVALID", "analysis explorer completion is not the exact semantic result")


def _validate_analysis(
    event: dict[str, Any],
    routes: dict[str, str],
    reduction: dict[str, Any],
) -> None:
    result = event.get("analysis_result")
    if (
        not _nonempty_string(event.get("analysis_ref"))
        or not isinstance(result, dict)
        or set(result) != ANALYSIS_FIELDS
        or result.get("schema") != "app-semantic-analysis-result.v1"
        or result.get("analysis_ref") != event.get("analysis_ref")
        or any(not _nonempty_string(result.get(field)) for field in ANALYSIS_STRING_FIELDS)
        or not valid_build_ref(result.get("basis_build_ref"))
    ):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis needs one complete typed result")
    input_refs = result.get("input_refs")
    if not isinstance(input_refs, dict) or set(input_refs) != ANALYSIS_INPUT_FIELDS:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis input categories are incomplete")
    for field in ANALYSIS_INPUT_FIELDS:
        binding = input_refs.get(field)
        if (
            not isinstance(binding, dict)
            or set(binding) != {"count", "refs_digest"}
            or isinstance(binding.get("count"), bool)
            or not isinstance(binding.get("count"), int)
            or binding["count"] < 0
            or not valid_digest(binding.get("refs_digest"))
        ):
            raise GraphError("ANALYSIS_INCOMPLETE", f"analysis input category {field} is invalid")
    if input_refs["source_refs"]["count"] < 1 or input_refs["process_record_refs"]["count"] < 1:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis source and process bindings cannot be empty")
    for field in ("functional_map_refs", "ledger_refs", "incoming_handoff_refs"):
        if input_refs[field]["count"] != 1:
            raise GraphError("ANALYSIS_INCOMPLETE", f"analysis input category {field} must bind one ref")
    for field in ("unmapped_decision_refs", "unmapped_requirement_refs", "open_remediation_refs"):
        if not _valid_refs(result.get(field)):
            raise GraphError("ANALYSIS_INCOMPLETE", f"analysis {field} is invalid")
    coverage = result.get("coverage")
    if not isinstance(coverage, dict) or set(coverage) != COVERAGE_FIELDS:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis coverage fields are incomplete")
    if any(
        isinstance(coverage[field], bool)
        or not isinstance(coverage[field], int)
        or coverage[field] < 0
        for field in COVERAGE_FIELDS
    ):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis coverage counts are invalid")
    expected_coverage = {
        count_field: input_refs[input_field]["count"]
        for count_field, input_field in COVERAGE_TO_INPUT.items()
    }
    if coverage != expected_coverage:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis coverage differs from its categorized inputs")
    findings = result.get("findings")
    if not isinstance(findings, list):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis findings are invalid")
    finding_refs: set[str] = set()
    finding_routes: set[str] = set()
    for finding in findings:
        finding_ref = _validate_finding_record(finding, routes)
        if finding_ref in finding_refs:
            raise GraphError("ANALYSIS_INCOMPLETE", "analysis finding identity is duplicated")
        finding_refs.add(finding_ref)
        finding_routes.add(finding["route"])
    route = result.get("route")
    if (
        not isinstance(result.get("complete"), bool)
        or route not in {"none", "needs-research", "needs-spec", "needs-graph", "needs-plan", "blocked"}
    ):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis route is invalid")
    possible_routes = set(finding_routes)
    if result["unmapped_decision_refs"]:
        possible_routes.add("needs-spec")
    if result["unmapped_requirement_refs"]:
        possible_routes.add("needs-graph")
    if result["open_remediation_refs"]:
        possible_routes.add("needs-plan")
    route_priority = reduction["corrective_priority"]
    if reduction["blocked_dominance"] and "blocked" in possible_routes:
        expected_route = "blocked"
    else:
        expected_route = next(
            (candidate for candidate in route_priority if candidate in possible_routes),
            reduction["clean_route"],
        )
    if route != expected_route:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis route disagrees with its findings")
    if route != "none" and not findings:
        raise GraphError("FINDING_INVALID", "every corrective analysis boundary needs a typed finding")
    if (route == "none") != (
        result["complete"] is True
        and not findings
        and not result["unmapped_decision_refs"]
        and not result["unmapped_requirement_refs"]
        and not result["open_remediation_refs"]
    ):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis clean route and completeness disagree")
    if route != "none" and result["complete"] is not False:
        raise GraphError("ANALYSIS_INCOMPLETE", "corrective analysis must remain incomplete")
    expected_status = "audited" if route == "none" else route
    if event["status"] != expected_status:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis event status disagrees with its route")
    if event["status"] == "audited" and (
        result.get("complete") is not True
        or findings
        or result["unmapped_decision_refs"]
        or result["unmapped_requirement_refs"]
        or result["open_remediation_refs"]
    ):
        raise GraphError("ANALYSIS_INCOMPLETE", "audited needs a complete contradiction-free result")
    _validate_analysis_delegations(event)


def _validate_event(event: Any, workflow: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply the full event-shape and semantic checks shared by append and compile."""
    if not isinstance(event, dict) or event.get("schema") != "app-process-event.v3":
        raise GraphError("SCHEMA_UNSUPPORTED", "new events must use app-process-event.v3")
    allowed = {"schema", *REQUIRED_STRINGS, *REQUIRED_ARRAYS, "task_spec_bindings", *OPTIONAL_FIELDS}
    if set(event) - allowed:
        raise GraphError("JOURNAL_CORRUPT", "event contains unknown fields")
    if any(not _nonempty_string(event.get(field)) for field in REQUIRED_STRINGS):
        raise GraphError("JOURNAL_CORRUPT", "event string fields are incomplete")
    if any("/" in event[field] or ".." in event[field] for field in ("run_ref", "event_ref")):
        raise GraphError("PATH_ESCAPE", "event and run refs must be safe")
    if any(not _valid_refs(event.get(field)) for field in REQUIRED_ARRAYS):
        raise GraphError("JOURNAL_CORRUPT", "event reference arrays are invalid")
    task_bindings = event.get("task_spec_bindings")
    if (
        not isinstance(task_bindings, list)
        or any(
            not isinstance(binding, dict)
            or set(binding) != {"task_ref", "task_spec_digest"}
            or not _nonempty_string(binding.get("task_ref"))
            or not valid_digest(binding.get("task_spec_digest"))
            for binding in task_bindings
        )
        or [binding["task_ref"] for binding in task_bindings] != sorted(event["task_refs"])
    ):
        raise GraphError("RUN_SCOPE_INVALID", "task spec bindings must exactly order the event task refs")
    for field in ("reviewed_task_refs", "finding_refs", "changed_paths"):
        if field in event and not _valid_refs(event[field]):
            raise GraphError("JOURNAL_CORRUPT", f"{field} is invalid")
    if event["origin"] != "native" or event["actor"] not in ACTORS:
        raise GraphError("OWNERSHIP_INVALID", "only a primary or repo-L2 may record native events")
    if (
        event["actor"] == "DIRECT-primary" and event["owner_session_ref"] != "none"
    ) or (
        event["actor"] == "repo-L2" and event["owner_session_ref"] == "none"
    ):
        raise GraphError("OWNERSHIP_INVALID", "owner mode and owner session disagree")
    if event["event_kind"] not in EVENT_KINDS:
        raise GraphError("JOURNAL_CORRUPT", "event kind is invalid")
    irrelevant = (OPTIONAL_FIELDS & set(event)) - OPTIONAL_BY_KIND[event["event_kind"]]
    if irrelevant:
        raise GraphError("JOURNAL_CORRUPT", "event contains fields irrelevant to its kind")
    if event["stage"] not in STAGES or event["status"] not in STATUSES:
        raise GraphError("JOURNAL_CORRUPT", "event stage or status is invalid")
    allowed_statuses = EVENT_RULES.get(event["event_kind"], {}).get(event["stage"])
    if allowed_statuses is None or event["status"] not in allowed_statuses:
        raise GraphError(
            "RUN_TRANSITION_INVALID",
            "event kind, stage, and status do not match the workflow rule",
            event_kind=event["event_kind"],
            stage=event["stage"],
            status=event["status"],
        )
    boundary_event = event["event_kind"] in HANDOFF_EVENT_KINDS
    if boundary_event != ("handoff_payload_digest" in event):
        raise GraphError("HANDOFF_INVALID", "only handoff boundary events require a payload digest")
    if boundary_event and not valid_digest(event["handoff_payload_digest"]):
        raise GraphError("HANDOFF_INVALID", "handoff payload digest is invalid")
    if event["event_kind"] == "run-start":
        remediation_ref = event.get("remediates_run_ref")
        if (
            event["causal_refs"]
            or (remediation_ref is not None and not _nonempty_string(remediation_ref))
            or remediation_ref == event["run_ref"]
        ):
            raise GraphError("RUN_SCOPE_INVALID", "run-start needs no local cause and a valid source link")
        if remediation_ref is None and (
            event["stage"] != "app-constitution" or event["status"] != "constitution-ready"
            or event["task_refs"]
        ):
            raise GraphError("RUN_SCOPE_INVALID", "ordinary run-start must enter app-constitution without a task scope")
        if remediation_ref is not None and (
            event["stage"] != "app-plan" or event["status"] != "plan-ready"
            or not event["task_refs"]
        ):
            raise GraphError("RUN_SCOPE_INVALID", "linked run-start must enter app-plan with remediation tasks")
    elif not event["causal_refs"]:
        raise GraphError("RUN_SCOPE_INVALID", "every event after run-start needs a local cause")
    if event["event_kind"] == "stage" and "finding_refs" not in event:
        raise GraphError("RUN_SCOPE_INVALID", "stage boundary must bind its outgoing finding refs")
    if event["event_kind"] in {"stage", "review"}:
        records = event.get("finding_records")
        if not isinstance(records, list):
            raise GraphError("FINDING_INVALID", "stage and review events need typed finding records")
        record_refs = [_validate_finding_record(record, _route_registry(workflow)) for record in records]
        if len(record_refs) != len(set(record_refs)) or event.get("finding_refs") != record_refs:
            raise GraphError("FINDING_INVALID", "finding refs must exactly match their typed records")
        if records and event["event_kind"] == "stage":
            expected_route = _reduced_finding_route(records, _route_reduction(workflow))
            if event["status"] != expected_route:
                raise GraphError("FINDING_INVALID", "stage status disagrees with its typed findings")
        deferred_failed_task_path = (
            event["event_kind"] == "stage"
            and event["stage"] in {"app-dev", "app-plan"}
            and event["status"] == "needs-plan"
        )
        if (
            event["event_kind"] == "stage"
            and event["status"] in CORRECTIVE_BOUNDARY_STATUSES
            and not records
            and not deferred_failed_task_path
        ):
            raise GraphError("FINDING_INVALID", "every corrective stage boundary needs a typed finding")
    replacement_bindings = event.get("replacement_bindings")
    replacement_boundary = (
        event["event_kind"] == "stage"
        and event["stage"] == "app-plan"
        and event["status"] == "needs-plan"
    )
    if replacement_boundary != (replacement_bindings is not None):
        raise GraphError("TASK_REPLACEMENT_INVALID", "only app-plan needs-plan requires replacement bindings")
    if replacement_boundary:
        if (
            not isinstance(replacement_bindings, list)
            or any(
                not isinstance(binding, dict)
                or set(binding) != {"task_ref", "replacement_task_refs"}
                or not _nonempty_string(binding.get("task_ref"))
                or not _valid_refs(binding.get("replacement_task_refs"), allow_empty=False)
                for binding in replacement_bindings
            )
            or [binding["task_ref"] for binding in replacement_bindings]
            != sorted(binding["task_ref"] for binding in replacement_bindings)
            or len({binding["task_ref"] for binding in replacement_bindings}) != len(replacement_bindings)
        ):
            raise GraphError("TASK_REPLACEMENT_INVALID", "replacement bindings are invalid or unordered")
    if event["status"] in {"plan-ready", "ready"} and not event["task_refs"]:
        raise GraphError("RUN_SCOPE_INVALID", "plan-ready and ready must establish a non-empty task scope")
    if event["event_kind"] == "delegation" and len(event["causal_refs"]) != 1:
        raise GraphError("DELEGATION_INVALID", "delegation must have exactly one direct cause")
    if event["event_kind"] == "task-result":
        if (
            not _nonempty_string(event.get("task_ref"))
            or event.get("task_ref") not in event["task_refs"]
            or event.get("terminal_result") not in {"done", "failed", "blocked"}
            or event["status"] != event["terminal_result"]
            or not _valid_git_refs(event.get("commit_refs"), allow_empty=False)
            or not _valid_refs(event.get("changed_paths"), allow_empty=False)
        ):
            raise GraphError("RUN_SCOPE_INVALID", "task-result needs scoped terminal and change provenance")
    if event["event_kind"] == "review":
        if (
            not _nonempty_string(event.get("commit_range"))
            or COMMIT_RANGE.fullmatch(event["commit_range"]) is None
            or not _valid_refs(event.get("reviewed_task_refs"), allow_empty=False)
            or "finding_refs" not in event
            or not _valid_refs(event["finding_refs"])
            or event["status"] != "done"
        ):
            raise GraphError("REVIEW_INCOMPLETE", "review needs an exact commit range and task set")
    if event["event_kind"] == "delegation":
        _validate_delegation(event)
    elif "delegation_record" in event:
        raise GraphError("DELEGATION_INVALID", "only delegation events may contain delegation records")
    if event["event_kind"] == "analysis":
        _validate_analysis(event, _route_registry(workflow), _route_reduction(workflow))
    elif "analysis_ref" in event or "analysis_result" in event or event["status"] == "audited":
        raise GraphError("ANALYSIS_INCOMPLETE", "only analysis events may contain analysis data or audited status")
    return event


def _terminal_stage_payload(
    events: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Reconstruct the exact payload of a derivable terminal boundary."""
    if event["event_kind"] == "analysis":
        return {
            "analysis_ref": event["analysis_ref"],
            "analysis_result": event["analysis_result"],
        }
    if event["status"] != "implemented":
        return None
    run_events = causal_order(
        item for item in events if item.get("run_ref") == event["run_ref"]
    )
    results = [item for item in run_events if item["event_kind"] == "task-result"]
    reviews = [item for item in run_events if item["event_kind"] == "review"]
    if not reviews or event["causal_refs"] != [reviews[-1]["event_ref"]]:
        raise GraphError("HANDOFF_INVALID", "implemented boundary lacks its final review")
    return {
        "task_result_refs": sorted(item["event_ref"] for item in results),
        "review_refs": sorted(item["event_ref"] for item in reviews),
        "final_review_ref": reviews[-1]["event_ref"],
        "commit_refs": sorted({ref for item in results for ref in item["commit_refs"]}),
        "commit_ranges": sorted({item["commit_range"] for item in reviews}),
        "remediation_refs": sorted(
            task_ref
            for task_ref in event["task_refs"]
            if tasks.get(task_ref, {}).get("task_kind") == "remediation"
        ),
    }


def _terminal_event(event: dict[str, Any]) -> bool:
    return (
        event["status"] == "audited"
        or (
            event["event_kind"] == "stage"
            and event["stage"] == "app-plan"
            and event["status"] == "needs-plan"
        )
        or (
            event["status"] == "blocked" and event["event_kind"] != "task-result"
        )
    )


def _result_event_digest(event: dict[str, Any]) -> str:
    if event["event_kind"] == "task-result":
        represented = {
            field: event[field]
            for field in (
                "task_ref", "terminal_result", "commit_refs", "changed_paths",
                "trace_refs", "artifact_refs",
            )
        }
    elif event["event_kind"] == "review":
        represented = {
            field: event[field]
            for field in ("reviewed_task_refs", "commit_range", "finding_records")
        }
    else:
        raise GraphError("DELEGATION_INVALID", "event has no represented L3 result digest")
    return digest_bytes(canonical(represented))


def _delegations_before(
    checked: list[dict[str, Any]],
    boundary: dict[str, Any],
    ancestor_refs: set[str],
) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in checked
        if candidate["event_kind"] == "delegation"
        and candidate["stage"] == boundary["stage"]
        and candidate["event_ref"] in ancestor_refs
        and candidate["delegation_record"]["completion_status"] == "completed"
    ]


def _validate_delegated_boundary(
    checked: list[dict[str, Any]],
    event: dict[str, Any],
    ancestor_refs: set[str],
) -> None:
    """Require completed L3 provenance compatible with each L2 boundary."""
    if event["event_kind"] == "analysis":
        # Analysis completions are embedded in the sole analysis event so the
        # immediate-predecessor build remains stable and no rebasing loop exists.
        _validate_analysis_delegations(event)
        return
    candidates = _delegations_before(checked, event, ancestor_refs)
    if event["event_kind"] not in {"stage", "repo-handoff"}:
        return
    mutation_statuses = {"research-ready", "spec-ready", "graph-ready", "plan-ready", "ready"}
    required_kind = (
        "mutation-worker"
        if event["status"] in mutation_statuses or bool(event.get("replacement_bindings"))
        else "helper"
    )
    suitable = [
        candidate for candidate in candidates
        if candidate["delegation_record"]["role_kind"] == required_kind
        and (
            required_kind != "mutation-worker"
            or candidate["delegation_record"]["role"] == "worker"
        )
        and candidate["delegation_record"]["task_id"] == event["event_ref"]
        and candidate["delegation_record"]["result_ref"] == event["event_ref"]
        and candidate["delegation_record"]["result_digest"] == event["handoff_payload_digest"]
    ]
    if len(suitable) != 1:
        raise GraphError(
            "DELEGATION_INVALID",
            "repo-L2 stage boundary lacks one compatible completed L3 result",
            event_ref=event["event_ref"],
            required_role_kind=required_kind,
        )


def _validate_replacement_boundary(
    event: dict[str, Any],
    scope_refs: list[str],
    task_results: dict[str, dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    source_events: list[dict[str, Any]],
) -> None:
    """Bind every unresolved scoped task to immutable remediation replacements."""
    subject_tasks: set[str] = set()
    finding_refs_by_task: dict[str, set[str]] = defaultdict(set)
    for source_event in source_events:
        for finding in _event_finding_records(source_event):
            for subject_ref in finding["subject_refs"]:
                if subject_ref in scope_refs:
                    subject_tasks.add(subject_ref)
                    finding_refs_by_task[subject_ref].add(finding["finding_ref"])
    unresolved = {
        task_ref for task_ref in scope_refs
        if task_ref not in task_results
        or task_results[task_ref]["terminal_result"] != "done"
    }
    required_old = sorted(unresolved | subject_tasks)
    bindings = event["replacement_bindings"]
    if [binding["task_ref"] for binding in bindings] != required_old:
        raise GraphError(
            "TASK_REPLACEMENT_INVALID",
            "app-plan needs-plan does not bind every and only unresolved scoped task",
            event_ref=event["event_ref"],
        )
    binding_map = {binding["task_ref"]: binding["replacement_task_refs"] for binding in bindings}
    for old_ref, replacement_refs in binding_map.items():
        old = tasks[old_ref]
        old_result = task_results.get(old_ref)
        if old_result is not None and old_result["terminal_result"] == "done":
            if old.get("status") != "done" or "replacement_task_refs" in old:
                raise GraphError(
                    "TASK_REPLACEMENT_INVALID",
                    "a completed task must remain immutable while remediation is linked externally",
                    task_ref=old_ref,
                )
        elif old.get("status") != "superseded" or old.get("replacement_task_refs") != replacement_refs:
            raise GraphError(
                "TASK_REPLACEMENT_INVALID",
                "an unresolved task replacement differs from the sealed ledger lineage",
                task_ref=old_ref,
            )
        for replacement_ref in replacement_refs:
            replacement = tasks.get(replacement_ref)
            if (
                not isinstance(replacement, dict)
                or replacement.get("task_kind") != "remediation"
                or replacement.get("status") == "superseded"
                or any(
                    replacement.get(field) != old.get(field)
                    for field in ("repo_ref", "wave_id", "owner_role")
                )
            ):
                raise GraphError(
                    "TASK_REPLACEMENT_INVALID",
                    "replacement task is missing, inactive, or crosses authority scope",
                    task_ref=old_ref,
                    replacement_ref=replacement_ref,
                )
            basis = replacement.get("remediation_basis", {})
            if (
                basis.get("run_ref") != event["run_ref"]
                or event["event_ref"] not in basis.get("source_event_refs", [])
                or not finding_refs_by_task[old_ref].issubset(basis.get("finding_refs", []))
            ):
                raise GraphError(
                    "REMEDIATION_RUN_REQUIRED",
                    "replacement task does not bind the sealed source event and findings",
                    replacement_ref=replacement_ref,
                )
            if (
                old.get("task_kind") == "remediation"
                and old["remediation_basis"]["run_ref"] == basis["run_ref"]
            ):
                raise GraphError(
                    "TASK_REPLACEMENT_INVALID",
                    "recursive remediation replacement must advance to the current correction run",
                    replacement_ref=replacement_ref,
                )
            result = old_result
            if (
                result is not None
                and result["terminal_result"] != "done"
                and result["event_ref"] not in basis["source_event_refs"]
            ):
                raise GraphError(
                    "REMEDIATION_RUN_REQUIRED",
                    "failed task replacement omits its terminal result",
                    replacement_ref=replacement_ref,
                )
            for dependency_ref in old.get("depends_on", []):
                if dependency_ref in binding_map and not set(binding_map[dependency_ref]).issubset(
                    replacement.get("depends_on", [])
                ):
                    raise GraphError(
                        "TASK_REPLACEMENT_INVALID",
                        "replacement tasks do not preserve dependency order",
                        replacement_ref=replacement_ref,
                        dependency_ref=dependency_ref,
                    )
def _validate_run_lifecycle(
    events: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    workflow: dict[str, Any],
    root: RepoRoot | None = None,
    global_task_results: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Check one run's scope, authority, causality, and terminal seal."""
    routes = _validate_workflow(workflow)
    if not events:
        return []
    checked = [_validate_event(event, workflow) for event in events]
    run_refs = {event["run_ref"] for event in checked}
    if len(run_refs) != 1:
        raise GraphError("RUN_SCOPE_INVALID", "lifecycle check requires one run")
    starts = [event for event in checked if event["event_kind"] == "run-start"]
    if len(starts) != 1:
        raise GraphError("RUN_SCOPE_INVALID", "run needs exactly one run-start")
    start = starts[0]
    linked_run = start.get("remediates_run_ref") is not None
    if any(
        event[key] != start[key]
        for event in checked
        for key in ("actor", "owner_session_ref", "repo_ref", "wave_ref")
    ):
        raise GraphError("RUN_SCOPE_INVALID", "event authority differs from run-start")
    ordered = causal_order(checked)
    if ordered[0]["event_ref"] != start["event_ref"]:
        raise GraphError("RUN_SCOPE_INVALID", "run-start must be the only causal root")
    by_ref = {event["event_ref"]: event for event in checked}
    ancestor_cache: dict[str, set[str]] = {}

    def ancestors(event_ref: str) -> set[str]:
        cached = ancestor_cache.get(event_ref)
        if cached is not None:
            return cached
        result: set[str] = set()
        frontier = list(by_ref[event_ref]["causal_refs"])
        while frontier:
            ref = frontier.pop()
            if ref in result:
                continue
            result.add(ref)
            frontier.extend(by_ref[ref]["causal_refs"])
        ancestor_cache[event_ref] = result
        return result

    scope_boundaries = [
        event for event in ordered
        if event["event_kind"] in {"run-start", "stage"}
        and event["status"] in {"plan-ready", "ready"}
    ]
    scope_roots = [
        event for event in scope_boundaries
        if not any(
            candidate["event_ref"] in ancestors(event["event_ref"])
            for candidate in scope_boundaries
        )
    ]
    if len(scope_roots) > 1:
        raise GraphError("RUN_SCOPE_INVALID", "run has competing task-scope boundaries")
    scope_boundary = scope_roots[0] if scope_roots else None
    scope_refs = list(scope_boundary["task_refs"]) if scope_boundary is not None else []
    if scope_boundary is not None and not scope_refs:
        raise GraphError("RUN_SCOPE_INVALID", "task scope boundary cannot be empty")
    if linked_run and scope_boundary is not start:
        raise GraphError("REMEDIATION_RUN_REQUIRED", "linked run must establish remediation scope at run-start")
    if not linked_run and start["task_refs"]:
        raise GraphError("RUN_SCOPE_INVALID", "ordinary run cannot establish task scope at run-start")
    for event in ordered:
        scoped = scope_boundary is not None and (
            event is scope_boundary or scope_boundary["event_ref"] in ancestors(event["event_ref"])
        )
        expected_refs = scope_refs if scoped else []
        if event["task_refs"] != expected_refs:
            raise GraphError(
                "RUN_SCOPE_INVALID",
                "event task refs disagree with the causal task-scope phase",
                event_ref=event["event_ref"],
            )
        if event["task_spec_bindings"] != _expected_task_spec_bindings(expected_refs, tasks):
            raise GraphError(
                "RUN_SCOPE_INVALID",
                "event task spec bindings differ from the immutable ledger task specification",
                event_ref=event["event_ref"],
            )
    for task_ref in scope_refs:
        task = tasks.get(task_ref)
        if not isinstance(task, dict):
            raise GraphError("DANGLING_REF", "run task is missing from the ledger", task_ref=task_ref)
        if (
            task.get("owner_role") != start["actor"]
            or task.get("repo_ref") != start["repo_ref"]
            or task.get("wave_id") != start["wave_ref"]
        ):
            raise GraphError("OWNERSHIP_INVALID", "run task authority or scope disagrees with the ledger", task_ref=task_ref)
        if not _valid_git_refs(task.get("retirement_commit_refs")):
            raise GraphError("RUN_SCOPE_INVALID", "task retirement commit refs are invalid", task_ref=task_ref)
        if root is not None:
            for commit_ref in task["retirement_commit_refs"]:
                validate_git_commit(root, commit_ref)
        remediation_basis = task.get("remediation_basis")
        if linked_run != (task.get("task_kind") == "remediation"):
            raise GraphError("REMEDIATION_RUN_REQUIRED", "run scope mixes ordinary and remediation tasks", task_ref=task_ref)
        if task.get("task_kind") == "remediation":
            if (
                not isinstance(remediation_basis, dict)
                or set(remediation_basis) != {"run_ref", "source_event_refs", "finding_refs"}
                or not _nonempty_string(remediation_basis.get("run_ref"))
                or not _valid_refs(remediation_basis.get("source_event_refs"), allow_empty=False)
                or not _valid_refs(remediation_basis.get("finding_refs"))
            ):
                raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation task basis is incomplete", task_ref=task_ref)
        elif remediation_basis is not None:
            raise GraphError("RUN_SCOPE_INVALID", "ordinary task cannot carry a remediation basis", task_ref=task_ref)
    task_results: dict[str, dict[str, Any]] = {}
    ordered_refs: list[str] = []
    reviews: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []

    for event in ordered:
        for cause_ref in event["causal_refs"]:
            cause = by_ref[cause_ref]
            expected_stage = routes.get(cause["status"])
            if (
                expected_stage is not None
                and expected_stage != event["stage"]
            ) or (
                expected_stage is None
                and cause["stage"] != event["stage"]
            ):
                raise GraphError(
                    "RUN_TRANSITION_INVALID",
                    "causal adjacency does not follow the workflow route",
                    from_event_ref=cause_ref,
                    to_event_ref=event["event_ref"],
                )
        if start["actor"] == "repo-L2" and event["event_kind"] in {"stage", "repo-handoff", "analysis"}:
            _validate_delegated_boundary(checked, event, ancestors(event["event_ref"]))
        if event["event_kind"] == "task-result":
            task_ref = event["task_ref"]
            if task_ref not in scope_refs or task_ref in task_results:
                raise GraphError("RUN_SCOPE_INVALID", "task result is outside scope or duplicated", task_ref=task_ref)
            task = tasks[task_ref]
            dependencies = list(task.get("depends_on", []))
            for dependency_ref in dependencies:
                dependency = tasks.get(dependency_ref)
                if not isinstance(dependency, dict):
                    raise GraphError("DANGLING_REF", "task dependency is missing", task_ref=task_ref)
                if dependency_ref in scope_refs:
                    dependency_result = task_results.get(dependency_ref)
                    if (
                        dependency_result is None
                        or dependency_result["terminal_result"] != "done"
                        or dependency_result["event_ref"] not in ancestors(event["event_ref"])
                    ):
                        raise GraphError("RUN_SCOPE_INVALID", "task dependency is not causally done", task_ref=task_ref)
                else:
                    dependency_result = (global_task_results or {}).get(dependency_ref)
                    if dependency_result is None or dependency_result["terminal_result"] != "done":
                        raise GraphError(
                            "RUN_SCOPE_INVALID",
                            "external task dependency lacks a canonical done result",
                            task_ref=task_ref,
                        )
            changed_paths = set(event["changed_paths"])
            allowed_files = set(task.get("allowed_files", []))
            target_paths = set(task.get("target_paths", []))
            expected_artifacts = set(task.get("implementation_refs", [])) | set(task.get("evidence_refs", []))
            expected_trace = {
                task_ref,
                *task.get("requirement_refs", []),
                *task.get("functionality_refs", []),
                *task.get("graph_entity_refs", []),
            }
            if not changed_paths.issubset(allowed_files) or not changed_paths.issubset(target_paths):
                raise GraphError("RUN_SCOPE_INVALID", "task result changed paths exceed the task scope", task_ref=task_ref)
            if set(event["artifact_refs"]) != expected_artifacts:
                raise GraphError("RUN_SCOPE_INVALID", "task result artifacts differ from the ledger", task_ref=task_ref)
            if set(event["trace_refs"]) != expected_trace:
                raise GraphError("RUN_SCOPE_INVALID", "task result trace refs differ from the ledger", task_ref=task_ref)
            retirement_refs = set(task["retirement_commit_refs"])
            result_refs = set(event["commit_refs"])
            if not retirement_refs.issubset(result_refs):
                raise GraphError("RUN_SCOPE_INVALID", "task result omits retirement commit provenance", task_ref=task_ref)
            if root is not None:
                actual_paths: set[str] = set()
                delivery_refs = result_refs - retirement_refs
                for commit_ref in delivery_refs:
                    actual_paths.update(git_commit_changed_paths(root, commit_ref))
                expected_paths = actual_paths if delivery_refs else allowed_files
                if expected_paths != changed_paths:
                    raise GraphError(
                        "GIT_PROVENANCE_INVALID",
                        "declared changed paths differ from current commits or the ledger-only delivery scope",
                        task_ref=task_ref,
                    )
            if start["actor"] == "repo-L2":
                suitable = [
                    candidate
                    for candidate in checked
                    if candidate["event_kind"] == "delegation"
                    and candidate["event_ref"] in ancestors(event["event_ref"])
                    and candidate["delegation_record"]["task_id"] == task_ref
                    and candidate["delegation_record"]["role"] == "app-worker"
                    and candidate["delegation_record"]["role_kind"] == "mutation-worker"
                    and candidate["delegation_record"]["result_ref"] == event["event_ref"]
                    and candidate["delegation_record"]["result_digest"] == _result_event_digest(event)
                ]
                if len(suitable) != 1:
                    raise GraphError("DELEGATION_INVALID", "repo-L2 task result lacks an ancestral app-worker delegation", task_ref=task_ref)
            task_results[task_ref] = event
        if event["event_kind"] == "review":
            if set(task_results) != set(scope_refs):
                raise GraphError("REVIEW_INCOMPLETE", "review requires full-run terminal results")
            if set(event["reviewed_task_refs"]) != set(scope_refs):
                raise GraphError("REVIEW_INCOMPLETE", "review task set differs from run scope")
            if not {item["event_ref"] for item in task_results.values()}.issubset(ancestors(event["event_ref"])):
                raise GraphError("REVIEW_INCOMPLETE", "review is not causally after every task result")
            if root is not None:
                range_commits = git_range_commits(root, event["commit_range"])
                base_ref, _ = event["commit_range"].split("..")
                retirement_refs = {
                    commit_ref
                    for task_ref in scope_refs
                    for commit_ref in tasks[task_ref]["retirement_commit_refs"]
                }
                delivery_refs = {
                    commit_ref
                    for task_ref, result in task_results.items()
                    for commit_ref in result["commit_refs"]
                    if commit_ref not in set(tasks[task_ref]["retirement_commit_refs"])
                }
                _, head_ref = event["commit_range"].split("..")
                if any(
                    commit_ref == base_ref
                    or not git_is_ancestor(root, base_ref, commit_ref)
                    or not git_is_ancestor(root, commit_ref, head_ref)
                    for commit_ref in delivery_refs
                ):
                    raise GraphError(
                        "GIT_PROVENANCE_INVALID",
                        "every delivery commit must be forward-contained by the review range",
                    )
                if range_commits != delivery_refs:
                    raise GraphError(
                        "GIT_PROVENANCE_INVALID",
                        "review range must equal the delivery commit set with zero extras",
                    )
                if any(
                    retirement_ref != base_ref
                    and not git_is_ancestor(root, retirement_ref, base_ref)
                    for retirement_ref in retirement_refs
                ):
                    raise GraphError(
                        "GIT_PROVENANCE_INVALID",
                        "retirement provenance must be at or before the review base",
                    )
                delivery_paths = {
                    path
                    for task_ref, result in task_results.items()
                    if set(result["commit_refs"]) - set(tasks[task_ref]["retirement_commit_refs"])
                    for path in result["changed_paths"]
                }
                if git_range_changed_paths(root, event["commit_range"]) != delivery_paths:
                    raise GraphError(
                        "GIT_PROVENANCE_INVALID",
                        "review range path delta differs from the exact delivery result paths",
                    )
            if start["actor"] == "repo-L2":
                suitable = [
                    candidate
                    for candidate in checked
                    if candidate["event_kind"] == "delegation"
                    and candidate["event_ref"] in ancestors(event["event_ref"])
                    and candidate["delegation_record"]["role"] == "wave-change-critic"
                    and candidate["delegation_record"]["role_kind"] == "primary-critic"
                    and candidate["delegation_record"]["task_id"] == event["event_ref"]
                    and candidate["delegation_record"]["result_ref"] == event["event_ref"]
                    and candidate["delegation_record"]["result_digest"] == _result_event_digest(event)
                ]
                if len(suitable) != 1:
                    raise GraphError("DELEGATION_INVALID", "repo-L2 review lacks an ancestral critic delegation")
            reviews.append(event)
        if (
            event["event_kind"] == "stage"
            and event["stage"] == "app-dev"
            and event["status"] in {"needs-research", "needs-spec", "needs-graph", "needs-plan"}
        ):
            ancestor_refs = ancestors(event["event_ref"])
            review_findings = [
                finding
                for review in reviews
                if review["event_ref"] in ancestor_refs
                for finding in review.get("finding_records", [])
            ]
            failed_result = any(
                result["event_ref"] in ancestor_refs
                and result["terminal_result"] in {"failed", "blocked"}
                for result in task_results.values()
            )
            if review_findings:
                expected_route = _reduced_finding_route(
                    review_findings,
                    _route_reduction(workflow),
                )
                if event["status"] != expected_route:
                    raise GraphError(
                        "RUN_TRANSITION_INVALID",
                        "app-dev corrective status differs from its critic findings",
                    )
            elif not (failed_result and event["status"] == "needs-plan"):
                raise GraphError(
                    "REMEDIATION_RUN_REQUIRED",
                    "app-dev corrective route needs a failed result or typed critic finding",
                )
        if (
            event["event_kind"] == "stage"
            and event["stage"] == "app-plan"
            and event["status"] == "needs-plan"
            and not event.get("finding_records")
        ):
            ancestor_refs = ancestors(event["event_ref"])
            failed_result_path = any(
                by_ref[ancestor_ref]["event_kind"] == "task-result"
                and by_ref[ancestor_ref].get("terminal_result") in {"failed", "blocked"}
                for ancestor_ref in ancestor_refs
            ) and any(
                by_ref[ancestor_ref]["event_kind"] == "stage"
                and by_ref[ancestor_ref]["stage"] == "app-dev"
                and by_ref[ancestor_ref]["status"] == "needs-plan"
                and not by_ref[ancestor_ref].get("finding_records")
                for ancestor_ref in ancestor_refs
            )
            if not failed_result_path:
                raise GraphError(
                    "FINDING_INVALID",
                    "empty app-plan needs-plan is limited to the failed-task correction path",
                )
        if (
            event["event_kind"] == "stage"
            and event["stage"] == "app-plan"
            and event["status"] == "needs-plan"
        ):
            source_events = [
                candidate
                for candidate in ordered
                if candidate["event_ref"] in ancestors(event["event_ref"])
                or candidate["event_ref"] == event["event_ref"]
            ]
            _validate_replacement_boundary(
                event,
                scope_refs,
                task_results,
                tasks,
                source_events,
            )
        if event["event_kind"] == "repo-handoff":
            handoffs.append(event)
            clean_reviews = [review for review in reviews if not review.get("finding_refs")]
            if (
                len(handoffs) != 1
                or set(task_results) != set(scope_refs)
                or any(result["terminal_result"] != "done" for result in task_results.values())
                or any(review.get("finding_refs") for review in reviews)
                or len(clean_reviews) != 1
                or reviews[-1]["event_ref"] != clean_reviews[0]["event_ref"]
                or event["causal_refs"] != [clean_reviews[0]["event_ref"]]
                or ancestors(event["event_ref"]) != set(ordered_refs)
            ):
                raise GraphError("REVIEW_INCOMPLETE", "implemented handoff needs full results and one final clean review")
        if event["event_kind"] == "analysis":
            if len(event["causal_refs"]) != 1:
                raise GraphError("ANALYSIS_INCOMPLETE", "analysis needs one direct incoming boundary")
            cause_ref = event["causal_refs"][0]
            cause = by_ref[cause_ref]
            implemented_input = cause["event_kind"] == "repo-handoff" and cause["status"] == "implemented"
            no_work_input = (
                cause["event_kind"] == "stage"
                and cause["stage"] == "app-plan"
                and cause["status"] == "no-work"
            )
            if not implemented_input and not no_work_input:
                raise GraphError("ANALYSIS_INCOMPLETE", "analysis must follow repo handoff or app-plan no-work")
            if event["analysis_result"]["input_refs"]["incoming_handoff_refs"] != _ref_set_binding([cause_ref]):
                raise GraphError("ANALYSIS_INCOMPLETE", "analysis input does not bind its incoming boundary")
        ordered_refs.append(event["event_ref"])
    for event in ordered:
        expected_payload = _terminal_stage_payload(ordered, tasks, event)
        if (
            expected_payload is not None
            and digest_bytes(canonical(expected_payload)) != event["handoff_payload_digest"]
        ):
            raise GraphError(
                "HANDOFF_INVALID",
                "terminal handoff payload digest differs from its reconstructed payload",
                event_ref=event["event_ref"],
            )
    terminals = [event for event in ordered if _terminal_event(event)]
    if len(terminals) > 1:
        raise GraphError("RUN_TERMINAL_CONFLICT", "run has more than one terminal event")
    if terminals and ordered[-1]["event_ref"] != terminals[0]["event_ref"]:
        raise GraphError("RUN_SEALED", "run contains records after its terminal event")
    if terminals:
        terminal_ancestors: set[str] = set()
        frontier = list(terminals[0]["causal_refs"])
        while frontier:
            ref = frontier.pop()
            if ref in terminal_ancestors:
                continue
            terminal_ancestors.add(ref)
            frontier.extend(by_ref[ref]["causal_refs"])
        if terminal_ancestors != set(by_ref) - {terminals[0]["event_ref"]}:
            raise GraphError("RUN_SEALED", "terminal event must causally seal the full run")
    audited = [event for event in checked if event["status"] == "audited"]
    if audited:
        event = audited[0]
        if event["event_kind"] != "analysis" or event["stage"] != "app-analyze":
            raise GraphError("ANALYSIS_INCOMPLETE", "audited must be the final app-analyze event")
        cause = by_ref[event["causal_refs"][0]]
        if cause["event_kind"] == "repo-handoff" and set(task_results) != set(scope_refs):
            raise GraphError("ANALYSIS_INCOMPLETE", "audited requires terminal results for every run task")
    return ordered


def _event_finding_refs(event: dict[str, Any]) -> set[str]:
    if event["event_kind"] in {"stage", "review"}:
        return set(event.get("finding_refs", []))
    if event["event_kind"] == "analysis":
        return {
            finding["finding_ref"]
            for finding in event["analysis_result"].get("findings", [])
            if isinstance(finding, dict) and _nonempty_string(finding.get("finding_ref"))
        }
    return set()


def _event_finding_records(event: dict[str, Any]) -> list[dict[str, Any]]:
    if event["event_kind"] in {"stage", "review"}:
        return list(event.get("finding_records", []))
    if event["event_kind"] == "analysis":
        return list(event["analysis_result"].get("findings", []))
    return []


def _validate_process_lifecycles(
    runs: dict[str, list[dict[str, Any]]],
    tasks: dict[str, dict[str, Any]],
    workflow: dict[str, Any],
    root: RepoRoot | None = None,
    known_refs: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Validate global result identity, run topology, and remediation lineage."""
    checked_runs: dict[str, list[dict[str, Any]]] = {}
    events_by_ref: dict[str, dict[str, Any]] = {}
    analysis_by_ref: dict[str, dict[str, Any]] = {}
    task_results: dict[str, dict[str, Any]] = {}
    delegations_by_result: dict[str, tuple[dict[str, Any], dict[str, Any], bool]] = {}
    assignment_refs: set[str] = set()
    findings: dict[str, dict[str, Any]] = {}

    def register_delegation(
        event: dict[str, Any],
        record: dict[str, Any],
        *,
        embedded: bool,
    ) -> None:
        assignment_ref = record["assignment_id"]
        result_ref = record["result_ref"]
        if assignment_ref in assignment_refs:
            raise GraphError("DELEGATION_INVALID", "delegation assignment identity is globally duplicated")
        if result_ref in delegations_by_result:
            raise GraphError(
                "DELEGATION_INVALID",
                "delegation result identity is globally duplicated",
                result_ref=result_ref,
            )
        assignment_refs.add(assignment_ref)
        delegations_by_result[result_ref] = (event, record, embedded)

    for run_ref, run_events in runs.items():
        checked_events = [_validate_event(event, workflow) for event in run_events]
        if any(event["run_ref"] != run_ref for event in checked_events):
            raise GraphError("RUN_SCOPE_INVALID", "run registry key differs from an event run ref", run_ref=run_ref)
        checked_runs[run_ref] = checked_events
        for event in checked_events:
            event_ref = event["event_ref"]
            if event_ref in events_by_ref:
                raise GraphError("JOURNAL_CORRUPT", "event ref is globally duplicated", event_ref=event_ref)
            events_by_ref[event_ref] = event
            if event["event_kind"] == "analysis":
                analysis_ref = event["analysis_ref"]
                if analysis_ref in analysis_by_ref or analysis_ref in events_by_ref:
                    raise GraphError("ANALYSIS_INCOMPLETE", "analysis result identity is globally duplicated", analysis_ref=analysis_ref)
                analysis_by_ref[analysis_ref] = event
            if event["event_kind"] == "task-result":
                task_ref = event["task_ref"]
                task = tasks.get(task_ref)
                if task is None:
                    raise GraphError("DANGLING_REF", "task result references a missing ledger task", task_ref=task_ref)
                if task_ref in task_results:
                    raise GraphError("RUN_SCOPE_INVALID", "task result is globally duplicated", task_ref=task_ref)
                ledger_status = task.get("status")
                terminal_result = event["terminal_result"]
                valid_status = (
                    ledger_status == "done"
                    if terminal_result == "done"
                    else ledger_status in {terminal_result, "superseded"}
                )
                if not valid_status:
                    raise GraphError(
                        "RUN_SCOPE_INVALID",
                        "task result differs from the terminal ledger state",
                        task_ref=task_ref,
                    )
                task_results[task_ref] = event
            if event["event_kind"] == "delegation":
                register_delegation(event, event["delegation_record"], embedded=False)
            elif event["event_kind"] == "analysis":
                for record in event.get("delegation_records", []):
                    register_delegation(event, record, embedded=True)
            for finding in _event_finding_records(event):
                finding_ref = finding["finding_ref"]
                previous = findings.get(finding_ref)
                if previous is not None and canonical(previous) != canonical(finding):
                    raise GraphError("FINDING_INVALID", "finding identity has conflicting canonical records", finding_ref=finding_ref)
                findings[finding_ref] = finding

    if set(events_by_ref) & set(analysis_by_ref):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis and event identities share a ref")
    resolved_refs = (
        set(known_refs or set())
        | set(tasks)
        | set(events_by_ref)
        | set(analysis_by_ref)
        | set(findings)
        | {
            ref
            for event in events_by_ref.values()
            for ref in event["trace_refs"] + event["artifact_refs"]
        }
    )
    for finding in findings.values():
        unresolved = set(finding["subject_refs"] + finding["conflict_refs"]) - resolved_refs
        if unresolved:
            raise GraphError(
                "DANGLING_REF",
                "finding references are not resolvable in the exact source and process graph",
                finding_ref=finding["finding_ref"],
                unresolved_refs=sorted(unresolved),
            )

    ordered_runs = {
        run_ref: _validate_run_lifecycle(
            run_events,
            tasks,
            workflow,
            root,
            task_results,
        )
        for run_ref, run_events in checked_runs.items()
    }
    starts = {run_ref: ordered[0] for run_ref, ordered in ordered_runs.items()}

    task_runs: dict[str, str] = {}
    for run_ref, ordered in ordered_runs.items():
        scoped_refs = {
            task_ref
            for event in ordered
            for task_ref in event["task_refs"]
        }
        for task_ref in scoped_refs:
            previous_run = task_runs.get(task_ref)
            if previous_run is not None and previous_run != run_ref:
                raise GraphError(
                    "RUN_SCOPE_INVALID",
                    "one task is active in more than one process run",
                    task_ref=task_ref,
                )
            task_runs[task_ref] = run_ref

    for task_ref, result in task_results.items():
        if task_runs.get(task_ref) != result["run_ref"]:
            raise GraphError("RUN_SCOPE_INVALID", "task result is not in its task's unique run", task_ref=task_ref)
    for task_ref, run_ref in task_runs.items():
        task = tasks[task_ref]
        status = task.get("status")
        result = task_results.get(task_ref)
        if status in {"done", "failed", "blocked"}:
            if result is None or result["terminal_result"] != status:
                raise GraphError(
                    "RUN_SCOPE_INVALID",
                    "terminal ledger task lacks its exact canonical result",
                    task_ref=task_ref,
                    run_ref=run_ref,
                )
        elif status in {"waiting", "ready", "in_progress"} and result is not None:
            raise GraphError("RUN_SCOPE_INVALID", "active ledger task already has a terminal result", task_ref=task_ref)
        elif status == "superseded" and result is not None and result["terminal_result"] == "done":
            raise GraphError("TASK_REPLACEMENT_INVALID", "a completed task cannot become superseded", task_ref=task_ref)

    source_of: dict[str, str] = {}
    successor_of: dict[str, str] = {}
    for run_ref, start in starts.items():
        source_run_ref = start.get("remediates_run_ref")
        if source_run_ref is None:
            continue
        if source_run_ref not in ordered_runs:
            raise GraphError("REMEDIATION_RUN_REQUIRED", "linked source run is missing", run_ref=run_ref)
        if source_run_ref in successor_of:
            raise GraphError("REMEDIATION_RUN_REQUIRED", "source run has more than one remediation successor", run_ref=source_run_ref)
        source = ordered_runs[source_run_ref]
        source_start = source[0]
        source_terminal = source[-1]
        if not (
            source_terminal["event_kind"] == "stage"
            and source_terminal["stage"] == "app-plan"
            and source_terminal["status"] == "needs-plan"
            and _terminal_event(source_terminal)
        ):
            raise GraphError(
                "REMEDIATION_RUN_REQUIRED",
                "linked source run is not sealed by app-plan needs-plan",
                run_ref=run_ref,
            )
        if any(
            start[field] != source_start[field]
            for field in ("actor", "owner_session_ref", "repo_ref", "wave_ref")
        ):
            raise GraphError("OWNERSHIP_INVALID", "linked run authority differs from its source", run_ref=run_ref)
        source_of[run_ref] = source_run_ref
        successor_of[source_run_ref] = run_ref

    for run_ref in ordered_runs:
        seen: set[str] = set()
        cursor = run_ref
        while cursor in source_of:
            if cursor in seen:
                raise GraphError("GRAPH_CYCLE", "remediation run lineage contains a cycle", run_ref=run_ref)
            seen.add(cursor)
            cursor = source_of[cursor]
        if cursor not in ordered_runs or starts[cursor].get("remediates_run_ref") is not None:
            raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation lineage has no ordinary root", run_ref=run_ref)

    remediation_by_source: dict[str, set[str]] = defaultdict(set)
    for task_ref, task in tasks.items():
        if task.get("task_kind") == "remediation":
            remediation_by_source[task["remediation_basis"]["run_ref"]].add(task_ref)

    for source_run_ref, remediation_refs in remediation_by_source.items():
        source = ordered_runs.get(source_run_ref)
        if source is None:
            raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation task source run is missing", run_ref=source_run_ref)
        source_terminal = source[-1]
        if not (
            source_terminal["event_kind"] == "stage"
            and source_terminal["stage"] == "app-plan"
            and source_terminal["status"] == "needs-plan"
        ):
            raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation tasks require a sealed app-plan source", run_ref=source_run_ref)
        source_by_ref = {event["event_ref"]: event for event in source}
        available_findings = {
            finding_ref
            for event in source
            for finding_ref in _event_finding_refs(event)
        }
        bound_replacements = {
            replacement_ref
            for binding in source_terminal["replacement_bindings"]
            for replacement_ref in binding["replacement_task_refs"]
        }
        if not bound_replacements.issubset(remediation_refs):
            raise GraphError("TASK_REPLACEMENT_INVALID", "source replacement binding points outside its remediation task set")
        for task_ref in sorted(remediation_refs):
            basis = tasks[task_ref]["remediation_basis"]
            if (
                source_terminal["event_ref"] not in basis["source_event_refs"]
                or any(ref not in source_by_ref for ref in basis["source_event_refs"])
                or not set(basis["finding_refs"]).issubset(available_findings)
            ):
                raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation task basis is not exact for its source run", task_ref=task_ref)
            failed_basis = any(
                source_by_ref[ref]["event_kind"] == "task-result"
                and source_by_ref[ref].get("terminal_result") in {"failed", "blocked"}
                for ref in basis["source_event_refs"]
            )
            if not basis["finding_refs"] and not failed_basis:
                raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation basis needs a finding or failed result", task_ref=task_ref)
            if task_ref not in bound_replacements and not basis["finding_refs"]:
                raise GraphError("REMEDIATION_RUN_REQUIRED", "a new-scope remediation task needs a typed finding", task_ref=task_ref)
        successor_ref = successor_of.get(source_run_ref)
        if successor_ref is not None and set(starts[successor_ref]["task_refs"]) != remediation_refs:
            raise GraphError(
                "REMEDIATION_RUN_REQUIRED",
                "linked run scope differs from the exact remediation tasks created for its source",
                run_ref=successor_ref,
            )

    for run_ref, ordered in ordered_runs.items():
        terminal = ordered[-1]
        if (
            terminal["event_kind"] == "stage"
            and terminal["stage"] == "app-plan"
            and terminal["status"] == "needs-plan"
            and not remediation_by_source.get(run_ref)
        ):
            raise GraphError("REMEDIATION_RUN_REQUIRED", "app-plan needs-plan must seal a non-empty remediation task set", run_ref=run_ref)
        if run_ref in source_of:
            expected_scope = remediation_by_source.get(source_of[run_ref], set())
            if set(starts[run_ref]["task_refs"]) != expected_scope:
                raise GraphError("REMEDIATION_RUN_REQUIRED", "linked run start does not bind its source remediation scope", run_ref=run_ref)

    def run_predecessors(run_ref: str) -> set[str]:
        result: set[str] = set()
        cursor = run_ref
        while cursor in source_of:
            cursor = source_of[cursor]
            result.add(cursor)
        return result

    for task_ref, result in task_results.items():
        current_run = result["run_ref"]
        for dependency_ref in tasks[task_ref].get("depends_on", []):
            dependency_result = task_results.get(dependency_ref)
            if dependency_result is None or dependency_result["terminal_result"] != "done":
                raise GraphError("RUN_SCOPE_INVALID", "task dependency lacks a canonical done result", task_ref=task_ref)
            dependency_run = dependency_result["run_ref"]
            if dependency_run != current_run and dependency_run not in run_predecessors(current_run):
                raise GraphError(
                    "RUN_SCOPE_INVALID",
                    "cross-run task dependency is not in the remediation predecessor chain",
                    task_ref=task_ref,
                )

    run_ancestors: dict[str, dict[str, set[str]]] = {}
    for run_ref, ordered in ordered_runs.items():
        by_ref = {event["event_ref"]: event for event in ordered}
        event_ancestors: dict[str, set[str]] = {}
        for event in ordered:
            ancestors: set[str] = set()
            frontier = list(event["causal_refs"])
            while frontier:
                ref = frontier.pop()
                if ref in ancestors:
                    continue
                ancestors.add(ref)
                frontier.extend(by_ref[ref]["causal_refs"])
            event_ancestors[event["event_ref"]] = ancestors
        run_ancestors[run_ref] = event_ancestors

    for result_ref, (delegation, record, embedded) in delegations_by_result.items():
        target = events_by_ref.get(result_ref)
        analysis_target = analysis_by_ref.get(result_ref)
        if embedded:
            represented = target or analysis_target
            if represented is not delegation:
                raise GraphError(
                    "DELEGATION_INVALID",
                    "embedded analysis completion does not resolve to its containing boundary",
                    result_ref=result_ref,
                )
            continue
        if target is None and analysis_target is None:
            descendants = [
                event
                for event in ordered_runs[delegation["run_ref"]]
                if delegation["event_ref"]
                in run_ancestors[delegation["run_ref"]][event["event_ref"]]
            ]
            if all(event["event_kind"] == "delegation" for event in descendants):
                continue
            raise GraphError("DELEGATION_INVALID", "delegation result is not represented by a process boundary", result_ref=result_ref)
        represented = target or analysis_target
        assert represented is not None
        if (
            represented["actor"] != "repo-L2"
            or represented["run_ref"] != delegation["run_ref"]
            or represented["stage"] != delegation["stage"]
            or delegation["event_ref"] not in run_ancestors[represented["run_ref"]][represented["event_ref"]]
        ):
            raise GraphError("DELEGATION_INVALID", "delegation is not a causal completion for its represented boundary", result_ref=result_ref)
        if analysis_target is not None:
            analysis_result = analysis_target["analysis_result"]
            identity = (
                analysis_result["profile_ref"],
                analysis_result["model_ref"],
                analysis_result["checklist_ref"],
            )
            if not (
                record["role"] == "explorer"
                and record["role_kind"] == "helper"
                and record["task_id"] == result_ref
                and record["result_digest"] == digest_bytes(canonical(analysis_result))
                and tuple(record[field] for field in ("profile_ref", "model_ref", "checklist_ref")) == identity
            ):
                raise GraphError("DELEGATION_INVALID", "analysis explorer completion identity is invalid", result_ref=result_ref)
            continue
        assert target is not None
        if target["event_kind"] in {"stage", "repo-handoff", "analysis"}:
            expected_digest = target["handoff_payload_digest"]
        elif target["event_kind"] in {"task-result", "review"}:
            expected_digest = _result_event_digest(target)
        else:
            raise GraphError("DELEGATION_INVALID", "delegation cannot represent this event kind", result_ref=result_ref)
        if record["result_digest"] != expected_digest:
            raise GraphError("DELEGATION_INVALID", "delegation result digest differs from its represented result", result_ref=result_ref)
        if target["event_kind"] == "task-result":
            compatible = (
                record["role"] == "app-worker"
                and record["role_kind"] == "mutation-worker"
                and record["task_id"] == target["task_ref"]
            )
        elif target["event_kind"] == "review":
            compatible = (
                record["role"] == "wave-change-critic"
                and record["role_kind"] == "primary-critic"
                and record["task_id"] == target["event_ref"]
            )
        elif target["event_kind"] == "analysis":
            compatible = (
                record["role"] == "worker"
                and record["role_kind"] == "mutation-worker"
                and record["task_id"] == target["analysis_ref"]
            )
        else:
            mutation = target["status"] in {"research-ready", "spec-ready", "graph-ready", "plan-ready", "ready"} or bool(target.get("replacement_bindings"))
            compatible = (
                record["task_id"] == target["event_ref"]
                and (
                    (mutation and record["role"] == "worker" and record["role_kind"] == "mutation-worker")
                    or (not mutation and record["role_kind"] == "helper")
                )
            )
        if not compatible:
            raise GraphError("DELEGATION_INVALID", "delegation role is incompatible with its represented result", result_ref=result_ref)

    return ordered_runs


def _existing_events(root: RepoRoot, event_roots: list[str]) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    for path in event_paths(root, event_roots):
        event, _ = read_json(root, path)
        records.append((path, event))
    return records


def _known_source_refs(
    functional_map: dict[str, Any],
    artifact_catalog: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
) -> set[str]:
    """Return the source-graph identities available before the next compile."""
    refs = set(tasks)
    for collection, key in (
        (functional_map.get("entities", []), "ref"),
        (artifact_catalog.get("artifacts", []), "ref"),
    ):
        if not isinstance(collection, list):
            continue
        refs.update(
            item[key]
            for item in collection
            if isinstance(item, dict) and _nonempty_string(item.get(key))
        )
    return refs


def _validate_analysis_record_basis(
    root: RepoRoot,
    source_manifest: dict[str, Any],
    event: dict[str, Any],
) -> None:
    """Reject an immutable analysis event unless the current build is its exact basis."""
    pointer, _ = read_json(root, CURRENT_BUILD_PATH, max_bytes=262144)
    build, trace, process = read_bound_indexes(root, pointer)
    _, _, snapshot = source_snapshot(root, source_manifest["sources"])
    if snapshot != build["source_snapshot_digest"]:
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis requires a current predecessor build")
    functional_map, _ = read_json(root, source_manifest["sources"]["functional_map"])
    ledger, _ = read_json(root, source_manifest["sources"]["task_ledger"])
    _validate_analysis_basis_binding(event, build, trace, process, functional_map, ledger)


def process_record_event(arguments: dict[str, Any]) -> dict[str, Any]:
    root = safe_root(arguments.get("app_root"))
    try:
        source_manifest = manifest(root, require_maintainer=True)
        workflow, _ = read_json(root, source_manifest["sources"]["workflow"])
        ledger, _ = read_json(root, source_manifest["sources"]["task_ledger"])
        functional_map, _ = read_json(root, source_manifest["sources"]["functional_map"])
        artifact_catalog, _ = read_json(root, source_manifest["sources"]["artifact_catalog"])
        event = _validate_event(arguments.get("event"), workflow)
        tasks = {task.get("task_id"): task for task in ledger.get("tasks", []) if isinstance(task, dict)}
        known_refs = _known_source_refs(functional_map, artifact_catalog, tasks)
        for task_ref, task in tasks.items():
            retirement_refs = task.get("retirement_commit_refs")
            if not _valid_git_refs(retirement_refs):
                raise GraphError("RUN_SCOPE_INVALID", "task retirement commit refs are invalid", task_ref=task_ref)
            for commit_ref in retirement_refs:
                validate_git_commit(root, commit_ref)
        event_root = source_manifest["sources"]["event_roots"][0]
        lock = open_directory(root, ("docs",))
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            ref, run_ref = event["event_ref"], event["run_ref"]
            if any("/" in item or ".." in item for item in (ref, run_ref)):
                raise GraphError("PATH_ESCAPE", "event and run refs must be safe")
            relative = f"{event_root}/{run_ref}/{ref}.json"
            payload = canonical(event)
            existing = _existing_events(root, source_manifest["sources"]["event_roots"])
            existing_refs: dict[str, tuple[str, dict[str, Any]]] = {}
            existing_runs: dict[str, list[dict[str, Any]]] = {}
            for path, item in existing:
                checked = _validate_event(item, workflow)
                item_ref = checked["event_ref"]
                item_run = checked["run_ref"]
                expected_path = f"{event_root}/{item_run}/{item_ref}.json"
                if path != expected_path or item_ref in existing_refs:
                    raise GraphError("JOURNAL_CORRUPT", "event identity or path is duplicated", path=path)
                existing_refs[item_ref] = (path, checked)
                existing_runs.setdefault(item_run, []).append(checked)
            matches = [existing_refs[ref]] if ref in existing_refs else []
            if matches:
                if len(matches) == 1 and matches[0][0] == relative and canonical(matches[0][1]) == payload:
                    _validate_process_lifecycles(
                        existing_runs,
                        tasks,
                        workflow,
                        root,
                        known_refs=known_refs,
                    )
                    return {
                        "schema": "app-process-event-result.v1", "status": "current",
                        "event_ref": ref, "no_op": True,
                    }
                raise GraphError("EVENT_CONFLICT", "event key already differs", event_ref=ref)
            existing_runs.setdefault(run_ref, []).append(event)
            _validate_process_lifecycles(
                existing_runs,
                tasks,
                workflow,
                root,
                known_refs=known_refs,
            )
            if event["event_kind"] == "analysis":
                _validate_analysis_record_basis(root, source_manifest, event)
            names = parts(relative)
            parent = open_directory(root, names[:-1], create=True)
            temporary = f".{names[-1]}.{secrets.token_hex(8)}.tmp"
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.link(temporary, names[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
                os.fsync(parent)
                os.close(parent)
            QUERY_CACHE.clear()
            return {
                "schema": "app-process-event-result.v1", "status": "recorded",
                "event_ref": ref, "event_digest": digest_bytes(payload), "no_op": False,
            }
        finally:
            os.close(lock)
    finally:
        root.close()
