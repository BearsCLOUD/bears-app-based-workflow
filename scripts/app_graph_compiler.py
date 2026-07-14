"""Compile authoritative app sources into immutable build-bound graph indexes."""

from __future__ import annotations

from collections import defaultdict, deque
import fcntl
import json
import os
from pathlib import Path
import secrets
from typing import Any

from app_graph_process import (
    _validate_analysis_basis_binding,
    _validate_event,
    _validate_process_lifecycles,
    _validate_workflow,
)
from app_graph_store import *


DIMENSIONS = {"behavior", "dependency", "state", "api", "data", "integration", "error"}
ARTIFACT_KINDS = {"code", "configuration", "document", "evidence"}
ACTIVE_TASK_STATES = {"waiting", "ready", "in_progress", "done", "failed", "blocked"}
TASK_REQUIRED_FIELDS = {
    "task_id", "repo_ref", "wave_id", "owner_role", "decision_state", "status",
    "queue_sequence", "task_kind", "requirement_refs", "functionality_refs",
    "graph_entity_refs", "target_paths", "allowed_files", "depends_on",
    "definition_of_done", "proof_requirement", "implementation_refs", "evidence_refs",
    "retirement_commit_refs",
}
TASK_OPTIONAL_FIELDS = {"replacement_task_refs", "remediation_basis"}
TASK_STATES = ACTIVE_TASK_STATES | {"superseded"}
TASK_KINDS = {"documentation", "graph", "implementation", "review", "remediation"}


def _entity(ref: str, kind: str, path: str, digest: str, **extra: Any) -> dict[str, Any]:
    return {
        "ref": ref,
        "kind": kind,
        "scope": extra.get("scope", "app"),
        "active": extra.get("active", True),
        "source": {"path": path, "anchor": ref, "digest": digest},
    }


def _atomic_write(root: RepoRoot, relative: str, payload: bytes, *, immutable: bool = False) -> None:
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
        if immutable:
            try:
                os.link(temporary, names[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            except FileExistsError:
                current = read_regular(root, relative)
                if current != payload:
                    raise GraphError("RECEIPT_CONFLICT", "immutable receipt already differs", path=relative)
        else:
            os.replace(temporary, names[-1], src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def _refs(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", f"{field} must contain unique non-empty refs")
    return value


def _git_refs(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    refs = _refs(value, field=field, allow_empty=allow_empty)
    if any(len(ref) != 40 or any(character not in "0123456789abcdef" for character in ref) for ref in refs):
        raise GraphError("SCHEMA_UNSUPPORTED", f"{field} must contain full lowercase Git refs")
    return refs


def _ref_set_binding(refs: list[str]) -> dict[str, Any]:
    ordered = sorted(set(refs))
    return {"count": len(ordered), "refs_digest": digest_bytes(canonical(ordered))}


def _validate_dimensions(fmap: dict[str, Any], entities: dict[str, dict[str, Any]]) -> None:
    active_requirements = {
        ref for ref, item in entities.items()
        if item.get("kind") == "requirement" and item.get("active", True)
    }
    dimensions = fmap.get("requirement_dimensions")
    coverage = fmap.get("coverage")
    if not isinstance(dimensions, dict) or not isinstance(coverage, list):
        raise GraphError("DIMENSION_COVERAGE", "dimension mappings must be explicit")
    if set(dimensions) != active_requirements:
        raise GraphError("DIMENSION_COVERAGE", "every active requirement needs exactly seven dimensions")
    coverage_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    consumed_entity_refs: set[str] = set()
    for item in coverage:
        if not isinstance(item, dict):
            raise GraphError("DIMENSION_COVERAGE", "coverage entries must be objects")
        requirement = item.get("requirement_ref")
        dimension = item.get("dimension")
        key = (requirement, dimension)
        if requirement not in active_requirements or dimension not in DIMENSIONS or key in coverage_by_key:
            raise GraphError("DIMENSION_COVERAGE", "coverage entry identity is invalid")
        refs = _refs(item.get("entity_refs"), field="coverage.entity_refs")
        status = item.get("status")
        if status == "mapped":
            if not refs:
                raise GraphError("DIMENSION_COVERAGE", "mapped dimensions need typed entities", requirement_ref=requirement, dimension=dimension)
            for ref in refs:
                if ref in consumed_entity_refs:
                    raise GraphError("DIMENSION_COVERAGE", "dimension entities cannot be reused", ref=ref)
                if entities.get(ref, {}).get("kind") != dimension:
                    raise GraphError("DIMENSION_COVERAGE", "dimension ref has the wrong kind", ref=ref, expected=dimension)
                consumed_entity_refs.add(ref)
        elif status == "not-applicable":
            if refs or not isinstance(item.get("rationale"), str) or not item["rationale"]:
                raise GraphError("DIMENSION_NA_INVALID", "not-applicable needs a rationale and no entity refs")
        else:
            raise GraphError("DIMENSION_COVERAGE", "dimension status is invalid")
        _refs(item.get("evidence_refs"), field="coverage.evidence_refs")
        coverage_by_key[key] = item
    expected_keys = {(requirement, dimension) for requirement in active_requirements for dimension in DIMENSIONS}
    if set(coverage_by_key) != expected_keys:
        raise GraphError("DIMENSION_COVERAGE", "coverage must contain seven entries per requirement")
    for requirement, dimension_set in dimensions.items():
        if not isinstance(dimension_set, dict) or set(dimension_set) != DIMENSIONS:
            raise GraphError("DIMENSION_COVERAGE", "dimension set must be exact", requirement_ref=requirement)
        for dimension, value in dimension_set.items():
            if not isinstance(value, dict):
                raise GraphError("DIMENSION_COVERAGE", "dimension value must be an object")
            refs = _refs(value.get("refs"), field="requirement_dimensions.refs")
            coverage_item = coverage_by_key[(requirement, dimension)]
            expected_status = "applicable" if coverage_item["status"] == "mapped" else "not-applicable"
            if value.get("status") != expected_status or refs != coverage_item["entity_refs"]:
                raise GraphError("DIMENSION_COVERAGE", "dimension indexes disagree", requirement_ref=requirement, dimension=dimension)
            if expected_status == "not-applicable" and not value.get("rationale"):
                raise GraphError("DIMENSION_NA_INVALID", "not-applicable needs a rationale")


def _validate_ledger(ledger: Any) -> dict[str, dict[str, Any]]:
    """Validate the complete v3 ledger contract before using any task field."""
    if (
        not isinstance(ledger, dict)
        or set(ledger) != {"schema", "app_id", "revision", "tasks"}
        or ledger.get("schema") != "app-task-ledger.v3"
        or not isinstance(ledger.get("app_id"), str)
        or not ledger["app_id"]
        or isinstance(ledger.get("revision"), bool)
        or not isinstance(ledger.get("revision"), int)
        or ledger["revision"] < 1
        or not isinstance(ledger.get("tasks"), list)
        or len(ledger["tasks"]) > 25_000
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", "task ledger root is invalid")
    tasks: dict[str, dict[str, Any]] = {}
    queue_keys: set[tuple[str, str, int]] = set()
    for task in ledger["tasks"]:
        if not isinstance(task, dict) or not TASK_REQUIRED_FIELDS.issubset(task):
            raise GraphError("SCHEMA_UNSUPPORTED", "task ledger entry is incomplete")
        if set(task) - TASK_REQUIRED_FIELDS - TASK_OPTIONAL_FIELDS:
            raise GraphError("SCHEMA_UNSUPPORTED", "task ledger entry has unknown fields")
        task_ref = task.get("task_id")
        string_fields = ("task_id", "repo_ref", "wave_id", "definition_of_done", "proof_requirement")
        if any(not isinstance(task.get(field), str) or not task[field] for field in string_fields):
            raise GraphError("SCHEMA_UNSUPPORTED", "task scalar fields are invalid", task_ref=task_ref)
        if task_ref in tasks:
            raise GraphError("DUPLICATE_REF", "task ref is duplicated", ref=task_ref)
        if (
            task.get("owner_role") not in {"DIRECT-primary", "repo-L2"}
            or task.get("decision_state") not in {"planned", "closed"}
            or task.get("status") not in TASK_STATES
            or task.get("task_kind") not in TASK_KINDS
            or isinstance(task.get("queue_sequence"), bool)
            or not isinstance(task.get("queue_sequence"), int)
            or task["queue_sequence"] < 0
        ):
            raise GraphError("SCHEMA_UNSUPPORTED", "task enum or queue fields are invalid", task_ref=task_ref)
        queue_key = (task["repo_ref"], task["wave_id"], task["queue_sequence"])
        if queue_key in queue_keys:
            raise GraphError("DUPLICATE_REF", "task queue sequence is duplicated within repo-wave", task_ref=task_ref)
        queue_keys.add(queue_key)
        for field in (
            "requirement_refs", "functionality_refs", "graph_entity_refs", "target_paths",
            "allowed_files", "depends_on", "implementation_refs", "evidence_refs",
        ):
            _refs(task.get(field), field=f"task.{field}")
        _git_refs(task.get("retirement_commit_refs"), field="task.retirement_commit_refs")
        if not set(task["target_paths"]).issubset(task["allowed_files"]):
            raise GraphError("RUN_SCOPE_INVALID", "task target paths exceed allowed files", task_ref=task_ref)
        superseded = task["status"] == "superseded"
        if superseded != ("replacement_task_refs" in task):
            raise GraphError("TASK_REPLACEMENT_INVALID", "replacement refs must exactly mark superseded tasks", task_ref=task_ref)
        if superseded:
            _refs(task["replacement_task_refs"], field="task.replacement_task_refs", allow_empty=False)
        remediation = task["task_kind"] == "remediation"
        if remediation != ("remediation_basis" in task):
            raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation basis presence disagrees with task kind", task_ref=task_ref)
        if remediation:
            basis = task["remediation_basis"]
            if (
                not isinstance(basis, dict)
                or set(basis) != {"run_ref", "source_event_refs", "finding_refs"}
                or not isinstance(basis.get("run_ref"), str)
                or not basis["run_ref"]
            ):
                raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation task basis is incomplete", task_ref=task_ref)
            _refs(basis.get("source_event_refs"), field="task.remediation_basis.source_event_refs", allow_empty=False)
            _refs(basis.get("finding_refs"), field="task.remediation_basis.finding_refs")
        tasks[task_ref] = task
    return tasks


def _acyclic_task_order(
    tasks: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    registry: dict[str, dict[str, Any]],
) -> None:
    indegree = {ref: 0 for ref, item in tasks.items() if item.get("status") in ACTIVE_TASK_STATES}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges.values():
        if (
            registry[edge["kind"]]["topological"] is not True
            or edge["from_ref"] not in indegree
            or edge["to_ref"] not in indegree
        ):
            continue
        indegree[edge["from_ref"]] += 1
        outgoing[edge["to_ref"]].append(edge["from_ref"])
    queue = deque(sorted(ref for ref, degree in indegree.items() if not degree))
    visited = 0
    while queue:
        ref = queue.popleft()
        visited += 1
        for target in sorted(outgoing[ref]):
            indegree[target] -= 1
            if not indegree[target]:
                queue.append(target)
    if visited != len(indegree):
        raise GraphError("GRAPH_CYCLE", "active ledger dependency cycle")


def _validate_forbidden_edge_cycles(
    edges: dict[str, dict[str, Any]],
    registry: dict[str, dict[str, Any]],
) -> None:
    """Reject cycles across every active edge governed by a forbidden policy."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {}
    active_kinds: set[str] = set()
    for edge_ref in sorted(edges):
        edge = edges[edge_ref]
        kind = edge["kind"]
        semantics = registry.get(kind)
        if (
            not isinstance(semantics, dict)
            or semantics.get("cycle") != "forbidden"
            or edge.get("active", True) is not True
        ):
            continue
        source, target = edge["from_ref"], edge["to_ref"]
        adjacency[source].append(target)
        indegree.setdefault(source, 0)
        indegree[target] = indegree.get(target, 0) + 1
        active_kinds.add(kind)
    queue = deque(sorted(ref for ref, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        ref = queue.popleft()
        visited += 1
        for target in sorted(adjacency.get(ref, [])):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(indegree):
        cycle_ref = min(ref for ref, degree in indegree.items() if degree > 0)
        raise GraphError(
            "GRAPH_CYCLE",
            "forbidden active-edge cycle",
            edge_kinds=sorted(active_kinds),
            ref=cycle_ref,
        )


def _validate_task_replacements(tasks: dict[str, dict[str, Any]]) -> None:
    """Require same-scope, acyclic replacement lineage for superseded tasks."""
    for task_ref, task in tasks.items():
        replacements = _refs(
            task.get("replacement_task_refs", []),
            field="task.replacement_task_refs",
            allow_empty=task.get("status") != "superseded",
        )
        if task.get("status") != "superseded" and "replacement_task_refs" in task:
            raise GraphError("TASK_REPLACEMENT_INVALID", "only superseded tasks may declare replacements", task_ref=task_ref)
        for replacement_ref in replacements:
            replacement = tasks.get(replacement_ref)
            if replacement is None or replacement_ref == task_ref:
                raise GraphError("TASK_REPLACEMENT_INVALID", "task replacement is missing or self-referential", task_ref=task_ref)
            if any(
                replacement.get(field) != task.get(field)
                for field in ("repo_ref", "wave_id", "owner_role")
            ) or replacement.get("task_kind") != "remediation":
                raise GraphError("TASK_REPLACEMENT_INVALID", "task replacement crosses its authority scope", task_ref=task_ref)
            if task.get("task_kind") == "remediation":
                basis = task["remediation_basis"]
                replacement_basis = replacement["remediation_basis"]
                if replacement_basis["run_ref"] == basis["run_ref"]:
                    raise GraphError(
                        "TASK_REPLACEMENT_INVALID",
                        "recursive remediation replacement must advance to the current correction run",
                        task_ref=task_ref,
                    )

    indegree = {task_ref: 0 for task_ref in tasks}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for task_ref, task in tasks.items():
        for replacement_ref in task.get("replacement_task_refs", []):
            outgoing[task_ref].append(replacement_ref)
            indegree[replacement_ref] += 1
    queue = deque(sorted(task_ref for task_ref, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        task_ref = queue.popleft()
        visited += 1
        for replacement_ref in sorted(outgoing.get(task_ref, [])):
            indegree[replacement_ref] -= 1
            if indegree[replacement_ref] == 0:
                queue.append(replacement_ref)
    if visited != len(tasks):
        cycle_ref = min(task_ref for task_ref, degree in indegree.items() if degree > 0)
        raise GraphError("GRAPH_CYCLE", "task replacement cycle", task_ref=cycle_ref)


def _validate_event_journal(
    root: RepoRoot,
    config: dict[str, Any],
    values: dict[str, dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    event_root = config["event_roots"][0]
    workflow = values[config["workflow"]]
    _validate_workflow(workflow)
    events: list[dict[str, Any]] = []
    event_runs: dict[str, str] = {}
    for path in event_paths(root, config["event_roots"]):
        event = _validate_event(values[path], workflow)
        if not path.startswith(event_root + "/"):
            raise GraphError("JOURNAL_CORRUPT", "only process event v3 is active", path=path)
        ref, run_ref = event.get("event_ref"), event.get("run_ref")
        expected_path = f"{event_root}/{run_ref}/{ref}.json"
        if (
            not isinstance(ref, str)
            or not isinstance(run_ref, str)
            or ref in event_runs
            or path != expected_path
            or Path(path).stem != ref
        ):
            raise GraphError("JOURNAL_CORRUPT", "event identity is missing or duplicated", path=path)
        if any(ref not in tasks for ref in event["task_refs"]):
            raise GraphError("DANGLING_REF", "event task ref is missing", event_ref=event["event_ref"])
        if any(ref not in entities for ref in event["trace_refs"] + event["artifact_refs"]):
            raise GraphError("DANGLING_REF", "event graph ref is missing", event_ref=event["event_ref"])
        if (
            set(event["trace_refs"]) & set(event["artifact_refs"])
            or any(entities[ref]["kind"] in ARTIFACT_KINDS for ref in event["trace_refs"])
            or any(entities[ref]["kind"] not in ARTIFACT_KINDS for ref in event["artifact_refs"])
        ):
            raise GraphError(
                "RUN_SCOPE_INVALID",
                "event trace and artifact refs are not disjoint typed categories",
                event_ref=event["event_ref"],
            )
        event_runs[ref] = run_ref
        events.append(event)
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[event["run_ref"]].append(event)
    ordered_runs = _validate_process_lifecycles(
        by_run,
        tasks,
        workflow,
        root,
        known_refs=set(entities),
    )
    ordered = causal_order(events)
    links: list[dict[str, str]] = [
        {"ref": f"CAUSE:{cause}:{event['event_ref']}", "kind": "causes", "from_ref": cause, "to_ref": event["event_ref"]}
        for event in ordered for cause in event["causal_refs"]
    ]
    findings: dict[str, dict[str, Any]] = {}
    for event in ordered:
        if event["event_kind"] in {"stage", "review"}:
            records = event.get("finding_records", [])
        elif event["event_kind"] == "analysis":
            records = event["analysis_result"].get("findings", [])
        else:
            records = []
        for finding in records:
            finding_ref = finding["finding_ref"]
            previous = findings.get(finding_ref)
            if previous is not None and canonical(previous) != canonical(finding):
                raise GraphError(
                    "FINDING_INVALID",
                    "finding identity has conflicting canonical records",
                    finding_ref=finding_ref,
                )
            findings[finding_ref] = finding

    for run_ref, run_events in ordered_runs.items():
        start = run_events[0]
        source_run_ref = start.get("remediates_run_ref")
        if source_run_ref is not None:
            source_terminal = ordered_runs[source_run_ref][-1]
            links.append(
                {
                    "ref": f"REMEDIATE:RUN:{start['event_ref']}:{source_terminal['event_ref']}",
                    "kind": "remediates",
                    "from_ref": start["event_ref"],
                    "to_ref": source_terminal["event_ref"],
                }
            )

    for task_ref, task in tasks.items():
        basis = task.get("remediation_basis")
        if not isinstance(basis, dict):
            continue
        for source_ref in sorted(set(basis["source_event_refs"] + basis["finding_refs"])):
            links.append(
                {
                    "ref": f"REMEDIATE:TASK:{task_ref}:{source_ref}",
                    "kind": "remediates",
                    "from_ref": task_ref,
                    "to_ref": source_ref,
                }
            )

    for event in ordered:
        for binding in event.get("replacement_bindings", []):
            for replacement_ref in binding["replacement_task_refs"]:
                links.append(
                    {
                        "ref": f"REMEDIATE:REPLACE:{replacement_ref}:{binding['task_ref']}",
                        "kind": "remediates",
                        "from_ref": replacement_ref,
                        "to_ref": binding["task_ref"],
                    }
                )

    links_by_ref: dict[str, dict[str, str]] = {}
    for link in links:
        previous = links_by_ref.get(link["ref"])
        if previous is not None and previous != link:
            raise GraphError("DUPLICATE_REF", "process link ref has conflicting meanings", ref=link["ref"])
        links_by_ref[link["ref"]] = link
    if len(links_by_ref) > MAX_PROCESS_LINKS:
        raise GraphError("SOURCE_LIMIT", "process link limit exceeded")
    _validate_forbidden_edge_cycles(links_by_ref, workflow["graph"]["edge_types"])
    return (
        ordered,
        sorted(links_by_ref.values(), key=lambda item: item["ref"]),
        sorted(findings.values(), key=lambda item: item["finding_ref"]),
    )


def build_indexes(root: RepoRoot, source_manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = source_manifest["sources"]
    values, locators, snapshot = source_snapshot(root, config)
    fmap, ledger, artifacts, workflow = (
        values[config[key]] for key in ("functional_map", "task_ledger", "artifact_catalog", "workflow")
    )
    if (
        not all(isinstance(value, dict) for value in (fmap, ledger, artifacts, workflow))
        or fmap.get("schema") != "app-functional-map.v4"
        or ledger.get("schema") != "app-task-ledger.v3"
        or artifacts.get("schema") != "app-artifact-catalog.v2"
        or workflow.get("schema") != "app-workflow-definition.v3"
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", "the active source set must use workflow v3 graph contracts")
    source_digest = {item["path"]: item["digest"] for item in locators}
    declared_sources = set(source_digest)
    registry = workflow.get("graph", {}).get("edge_types", {})
    entities: dict[str, dict[str, Any]] = {}
    functional_items: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def add_entity(item: dict[str, Any], path: str, *, digest: str | None = None) -> None:
        ref, kind = item.get("ref"), item.get("kind")
        scope = item.get("scope", "app")
        active = item.get("active", True)
        if (
            not isinstance(ref, str)
            or not ref
            or not isinstance(kind, str)
            or not kind
            or not isinstance(scope, str)
            or not scope
            or not isinstance(active, bool)
            or path not in declared_sources
            or ref in entities
        ):
            raise GraphError("DUPLICATE_REF", "entity ref is missing or duplicated", ref=ref)
        if len(entities) >= MAX_ENTITIES:
            raise GraphError("SOURCE_LIMIT", "entity limit exceeded")
        entities[ref] = _entity(
            ref, kind, path, digest or source_digest[path],
            scope=scope, active=active,
        )

    def add_edge(item: dict[str, Any], path: str) -> None:
        ref, kind = item.get("ref"), item.get("kind")
        from_ref, to_ref = item.get("from_ref"), item.get("to_ref")
        active = item.get("active", True)
        if (
            not isinstance(ref, str)
            or not ref
            or ref in edges
            or kind not in registry
            or not isinstance(from_ref, str)
            or not from_ref
            or not isinstance(to_ref, str)
            or not to_ref
            or not isinstance(active, bool)
            or path not in declared_sources
        ):
            raise GraphError("EDGE_KIND_UNKNOWN", "edge ref or kind is invalid", ref=ref)
        if len(edges) >= MAX_EDGES:
            raise GraphError("SOURCE_LIMIT", "edge limit exceeded")
        source_refs = _refs(item.get("source_refs", []), field="edge.source_refs")
        bound_sources = sorted(set(source_refs + [path]))
        if any(source_ref not in declared_sources for source_ref in bound_sources):
            raise GraphError("DANGLING_REF", "edge source ref is not manifest-declared", ref=ref)
        edges[ref] = {
            "ref": ref,
            "kind": kind,
            "from_ref": from_ref,
            "to_ref": to_ref,
            "source_refs": bound_sources,
            "condition_refs": sorted(_refs(item.get("condition_refs", []), field="edge.condition_refs")),
            "active": active,
        }

    functional_source_refs = _refs(fmap.get("source_refs"), field="functional_map.source_refs", allow_empty=False)
    if any(ref not in declared_sources for ref in functional_source_refs):
        raise GraphError("DANGLING_REF", "functional map source ref is not manifest-declared")
    for item in fmap.get("entities", []):
        item_sources = _refs(item.get("source_refs"), field="entity.source_refs", allow_empty=False)
        if any(ref not in declared_sources for ref in item_sources):
            raise GraphError("DANGLING_REF", "functional entity source ref is not manifest-declared", ref=item.get("ref"))
        add_entity(item, config["functional_map"])
        functional_items[item["ref"]] = item
    _validate_dimensions(fmap, functional_items)
    for item in fmap.get("relations", []):
        relation_sources = _refs(item.get("source_refs"), field="relation.source_refs", allow_empty=False)
        if any(ref not in declared_sources for ref in relation_sources):
            raise GraphError("DANGLING_REF", "functional relation source ref is not manifest-declared", ref=item.get("ref"))
        add_edge(item, config["functional_map"])

    artifact_items: dict[str, dict[str, Any]] = {}
    for item in artifacts.get("artifacts", []):
        ref, kind, path = item.get("ref"), item.get("kind"), item.get("path")
        if ref in artifact_items or kind not in ARTIFACT_KINDS or not isinstance(path, str):
            raise GraphError("SCHEMA_UNSUPPORTED", "artifact entry is invalid", ref=ref)
        if path not in declared_sources:
            raise GraphError("DANGLING_REF", "artifact path is not manifest-declared", ref=ref)
        raw = read_regular(root, path)
        assert raw is not None
        artifact_items[ref] = item
        add_entity({"ref": ref, "kind": kind}, path, digest=digest_bytes(raw))

    for item in fmap["coverage"]:
        for evidence_ref in item["evidence_refs"]:
            if artifact_items.get(evidence_ref, {}).get("kind") != "evidence":
                raise GraphError("DANGLING_REF", "dimension evidence ref is missing", ref=evidence_ref)

    tasks = _validate_ledger(ledger)
    for task_ref, task in tasks.items():
        active = task.get("status") != "superseded"
        requirement_refs = _refs(task.get("requirement_refs"), field="task.requirement_refs", allow_empty=not active)
        functionality_refs = _refs(task.get("functionality_refs"), field="task.functionality_refs", allow_empty=not active)
        graph_refs = _refs(task.get("graph_entity_refs"), field="task.graph_entity_refs", allow_empty=not active)
        implementation_refs = _refs(task.get("implementation_refs"), field="task.implementation_refs", allow_empty=not active)
        evidence_refs = _refs(task.get("evidence_refs"), field="task.evidence_refs")
        target_paths = _refs(task.get("target_paths"), field="task.target_paths", allow_empty=not active)
        allowed_files = _refs(task.get("allowed_files"), field="task.allowed_files", allow_empty=not active)
        retirement_commit_refs = _git_refs(task.get("retirement_commit_refs"), field="task.retirement_commit_refs")
        for commit_ref in retirement_commit_refs:
            validate_git_commit(root, commit_ref)
        remediation_basis = task.get("remediation_basis")
        if task.get("task_kind") == "remediation":
            if (
                not isinstance(remediation_basis, dict)
                or set(remediation_basis) != {"run_ref", "source_event_refs", "finding_refs"}
            ):
                raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation task basis is incomplete", task_ref=task_ref)
            _refs(remediation_basis.get("source_event_refs"), field="task.remediation_basis.source_event_refs", allow_empty=False)
            _refs(remediation_basis.get("finding_refs"), field="task.remediation_basis.finding_refs")
            if not isinstance(remediation_basis.get("run_ref"), str) or not remediation_basis["run_ref"]:
                raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation task source run is invalid", task_ref=task_ref)
        elif remediation_basis is not None:
            raise GraphError("SCHEMA_UNSUPPORTED", "ordinary task cannot carry a remediation basis", task_ref=task_ref)
        if any(functional_items.get(ref, {}).get("kind") != "requirement" for ref in requirement_refs):
            raise GraphError("DANGLING_REF", "task requirement ref is invalid", task_ref=task_ref)
        if any(functional_items.get(ref, {}).get("kind") != "functionality" for ref in functionality_refs):
            raise GraphError("DANGLING_REF", "task functionality ref is invalid", task_ref=task_ref)
        if any(ref not in functional_items for ref in graph_refs):
            raise GraphError("DANGLING_REF", "task graph ref is invalid", task_ref=task_ref)
        if any(artifact_items.get(ref, {}).get("kind") == "evidence" or ref not in artifact_items for ref in implementation_refs):
            raise GraphError("DANGLING_REF", "task implementation ref is invalid", task_ref=task_ref)
        if any(artifact_items.get(ref, {}).get("kind") != "evidence" for ref in evidence_refs):
            raise GraphError("DANGLING_REF", "task evidence ref is invalid", task_ref=task_ref)
        if task.get("status") == "done" and not evidence_refs:
            raise GraphError("EVIDENCE_REQUIRED", "done task needs evidence refs", task_ref=task_ref)
        if active and task.get("status") == "done":
            implementation_paths = {artifact_items[ref]["path"] for ref in implementation_refs}
            if implementation_paths != set(allowed_files):
                raise GraphError(
                    "TASK_ARTIFACT_DRIFT",
                    "done task implementation artifacts must match allowed files",
                    task_ref=task_ref,
                )
            if not set(target_paths).issubset(implementation_paths):
                raise GraphError(
                    "TASK_ARTIFACT_DRIFT",
                    "done task targets must be covered by implementation artifacts",
                    task_ref=task_ref,
                )
        add_entity(
            {"ref": task_ref, "kind": "task", "scope": task.get("wave_id", "app"), "active": active},
            config["task_ledger"],
        )

    _validate_task_replacements(tasks)
    for task_ref, task in tasks.items():
        for replacement_ref in task.get("replacement_task_refs", []):
            add_edge(
                {
                    "ref": f"LEDGER-REPLACE:{replacement_ref}:{task_ref}",
                    "kind": "replaces",
                    "from_ref": replacement_ref,
                    "to_ref": task_ref,
                },
                config["task_ledger"],
            )
        for prerequisite in task.get("depends_on", []):
            if prerequisite not in tasks:
                raise GraphError("DANGLING_REF", "task prerequisite is missing", task_ref=task_ref, prerequisite_ref=prerequisite)
            add_edge({"ref": f"LEDGER-DEP:{task_ref}:{prerequisite}", "kind": "depends_on", "from_ref": task_ref, "to_ref": prerequisite}, config["task_ledger"])
        for functionality in task.get("functionality_refs", []):
            add_edge({"ref": f"TRACE:{functionality}:{task_ref}", "kind": "decomposes_to", "from_ref": functionality, "to_ref": task_ref}, config["task_ledger"])
        for implementation in task.get("implementation_refs", []):
            add_edge({"ref": f"TRACE:{task_ref}:{implementation}", "kind": "implemented_by", "from_ref": task_ref, "to_ref": implementation}, config["task_ledger"])
            for evidence in task.get("evidence_refs", []):
                ref = f"TRACE:{implementation}:{evidence}"
                if ref not in edges:
                    add_edge({"ref": ref, "kind": "evidenced_by", "from_ref": implementation, "to_ref": evidence}, config["task_ledger"])

    for edge in edges.values():
        if edge["from_ref"] not in entities or edge["to_ref"] not in entities:
            raise GraphError("DANGLING_REF", "edge endpoint is missing", edge_ref=edge["ref"])
        if any(ref not in entities for ref in edge["condition_refs"]):
            raise GraphError("DANGLING_REF", "edge condition ref is missing", edge_ref=edge["ref"])
    _validate_forbidden_edge_cycles(edges, registry)
    _acyclic_task_order(tasks, edges, registry)
    events, links, findings = _validate_event_journal(root, config, values, tasks, entities)

    trace_body = {
        "schema": "app-traceability-index.v4",
        "app_id": fmap.get("app_id"),
        "source_snapshot_digest": snapshot,
        "generated_from": locators,
        "roots": sorted(ref for ref, item in entities.items() if item["kind"] == "spec"),
        "evidence_sinks": sorted(ref for ref, item in entities.items() if item["kind"] == "evidence"),
        "entities": sorted(entities.values(), key=lambda item: item["ref"]),
        "edges": sorted(edges.values(), key=lambda item: item["ref"]),
        "replacements": fmap.get("replacements", []),
        "findings": [],
    }
    ordered_events = events
    journal_digest = digest_bytes(canonical(ordered_events))
    process_body = {
        "schema": "app-process-index.v4",
        "app_id": fmap.get("app_id"),
        "workflow_definition_ref": config["workflow"],
        "workflow_definition_digest": source_digest[config["workflow"]],
        "source_snapshot_digest": snapshot,
        "journal_digest": journal_digest,
        "runs": sorted({item["run_ref"] for item in ordered_events}),
        "events": ordered_events,
        "links": links,
        "findings": findings,
    }
    content = digest_bytes(canonical({"trace": trace_body, "process": process_body}))
    build_ref = "BUILD-" + content[7:31].upper()
    trace = {**trace_body, "build_ref": build_ref}
    process = {**process_body, "build_ref": build_ref}
    build = {
        "schema": "app-index-build.v1",
        "build_ref": build_ref,
        "source_snapshot_digest": snapshot,
        "journal_digest": journal_digest,
        "trace_index_digest": digest_bytes(canonical(trace)),
        "process_index_digest": digest_bytes(canonical(process)),
        "source_count": len(locators),
        "entity_count": len(entities),
        "edge_count": len(edges),
        "event_count": len(events),
    }
    context = {
        "schema": "app-context-index-result.v2",
        "status": "built",
        "build_ref": build_ref,
        "source_snapshot_digest": snapshot,
        "journal_digest": journal_digest,
        "traceability_index_ref": TRACE_PATH,
        "process_index_ref": PROCESS_PATH,
        "build_receipt_ref": f"{BUILD_ROOT}/{build_ref}.json",
    }
    return trace, process, build, context


def _read_bound_bundle(
    root: RepoRoot,
    pointer: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return read_bound_indexes(root, pointer)


def _locator_map(trace: dict[str, Any]) -> dict[str, str]:
    locators = trace.get("generated_from")
    if not isinstance(locators, list):
        raise GraphError("BUILD_RECEIPT_INVALID", "trace source locators are invalid")
    result: dict[str, str] = {}
    for locator in locators:
        if (
            not isinstance(locator, dict)
            or set(locator) != {"path", "digest"}
            or not isinstance(locator.get("path"), str)
            or not isinstance(locator.get("digest"), str)
            or locator["path"] in result
        ):
            raise GraphError("BUILD_RECEIPT_INVALID", "trace source locator is invalid")
        result[locator["path"]] = locator["digest"]
    return result


def _enforce_analysis_publish(
    root: RepoRoot,
    pointer: dict[str, Any] | None,
    trace: dict[str, Any],
    process: dict[str, Any],
) -> None:
    """Keep the journal append-only and bind analysis to its predecessor build."""
    candidate_events = {event["event_ref"]: event for event in process["events"]}
    candidate_analyses = {
        event["event_ref"]: event
        for event in process["events"] if event.get("event_kind") == "analysis"
    }
    if pointer is None:
        if candidate_analyses:
            raise GraphError("ANALYSIS_BASIS_INVALID", "analysis requires an immediate predecessor build")
        return
    previous_build, previous_trace, previous_process = _read_bound_bundle(root, pointer)
    previous_events = {event["event_ref"]: event for event in previous_process.get("events", [])}
    added_refs = set(candidate_events) - set(previous_events)
    removed_refs = set(previous_events) - set(candidate_events)
    changed_refs = {
        ref for ref in set(previous_events) & set(candidate_events)
        if canonical(previous_events[ref]) != canonical(candidate_events[ref])
    }
    if removed_refs or changed_refs:
        raise GraphError(
            "JOURNAL_IMMUTABLE",
            "published process records must remain a canonical-identical subset",
            removed_refs=sorted(removed_refs),
            changed_refs=sorted(changed_refs),
        )
    new_analyses = [event for ref, event in candidate_analyses.items() if ref not in previous_events]
    if not new_analyses:
        return
    if len(new_analyses) != 1:
        raise GraphError("ANALYSIS_BASIS_INVALID", "one compile may publish only one analysis event")
    analysis_event = new_analyses[0]
    if added_refs != {analysis_event["event_ref"]} or removed_refs or changed_refs:
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis compile may add only its native analysis event")
    previous_locators = _locator_map(previous_trace)
    candidate_locators = _locator_map(trace)
    event_path = (
        "docs/app-process-events/v3/"
        f"{analysis_event['run_ref']}/{analysis_event['event_ref']}.json"
    )
    if (
        set(candidate_locators) - set(previous_locators) != {event_path}
        or set(previous_locators) - set(candidate_locators)
        or any(candidate_locators[path] != digest for path, digest in previous_locators.items())
    ):
        raise GraphError("ANALYSIS_BASIS_INVALID", "analysis is not bound to an unchanged source snapshot")
    functional_map, _ = read_json(root, SOURCE_PATHS["functional_map"])
    ledger, _ = read_json(root, SOURCE_PATHS["task_ledger"])
    _validate_analysis_basis_binding(
        analysis_event,
        previous_build,
        previous_trace,
        previous_process,
        functional_map,
        ledger,
    )


def _bundle_is_current(
    root: RepoRoot,
    pointer: dict[str, Any],
    build: dict[str, Any],
    trace: dict[str, Any],
    process: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    immutable = immutable_build_paths(build["build_ref"])
    expected = {
        pointer["receipt_ref"]: canonical(build),
        immutable["trace"]: canonical(trace),
        immutable["process"]: canonical(process),
        immutable["context"]: canonical(context),
        TRACE_PATH: canonical(trace),
        PROCESS_PATH: canonical(process),
        CONTEXT_PATH: canonical(context),
        CURRENT_BUILD_PATH: canonical(pointer),
    }
    for path, payload in expected.items():
        try:
            current = read_regular(root, path, missing=True)
        except GraphError as exc:
            if exc.code in {"ARTIFACT_MISSING", "PATH_ESCAPE"}:
                return False
            raise
        if current != payload:
            return False
    return True


def graph_compile(arguments: dict[str, Any]) -> dict[str, Any]:
    root = safe_root(arguments.get("app_root"))
    try:
        source_manifest = manifest(root, require_maintainer=True)
        lock = open_directory(root, ("docs",))
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            pointer_raw = read_regular(root, CURRENT_BUILD_PATH, max_bytes=262144, missing=True)
            try:
                pointer = None if pointer_raw is None else json.loads(pointer_raw)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise GraphError("BUILD_POINTER_INVALID", "current build pointer is invalid JSON") from exc
            if pointer is not None:
                validate_current_pointer(pointer)
            expected = arguments.get("expected_build_ref")
            if expected is not None and not valid_build_ref(expected):
                raise GraphError("CAS_MISMATCH", "expected build ref is invalid", expected=expected)
            current = None if pointer is None else pointer["build_ref"]
            if expected is not None and expected != current:
                raise GraphError("CAS_MISMATCH", "expected build does not match current build", expected=expected, actual=current)
            trace, process, build, context = build_indexes(root, source_manifest)
            _, stable, snapshot = source_snapshot(root, source_manifest["sources"])
            if snapshot != build["source_snapshot_digest"] or stable != trace["generated_from"]:
                raise GraphError("SOURCE_DRIFT", "sources changed during compilation")
            receipt = f"{BUILD_ROOT}/{build['build_ref']}.json"
            current_pointer = {"schema": "app-index-current.v1", "build_ref": build["build_ref"], "receipt_ref": receipt}
            _enforce_analysis_publish(root, pointer, trace, process)
            if current == build["build_ref"] and pointer == current_pointer and _bundle_is_current(
                root, current_pointer, build, trace, process, context,
            ):
                return {**context, "schema": "app-graph-compile-result.v2", "status": "current", "no_op": True}
            immutable = immutable_build_paths(build["build_ref"])
            # Publish a complete immutable bundle first. The pointer is the sole
            # transaction switch; shared paths are recoverable projections only.
            for path, value in (
                (immutable["trace"], trace),
                (immutable["process"], process),
                (immutable["context"], context),
                (receipt, build),
            ):
                _atomic_write(root, path, canonical(value), immutable=True)
            _atomic_write(root, CURRENT_BUILD_PATH, canonical(current_pointer))
            for path, value in (
                (TRACE_PATH, trace),
                (PROCESS_PATH, process),
                (CONTEXT_PATH, context),
            ):
                _atomic_write(root, path, canonical(value))
            QUERY_CACHE.clear()
            return {**context, "schema": "app-graph-compile-result.v2", "no_op": False}
        finally:
            os.close(lock)
    finally:
        root.close()
