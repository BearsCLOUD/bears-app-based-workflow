"""Read-only exact-build validation for app stage handoff packets."""

from __future__ import annotations

from typing import Any

from app_graph_process import _event_finding_refs, _terminal_stage_payload, _validate_workflow
from app_graph_query import GraphStore
from app_graph_store import GraphError, canonical, digest_bytes


HANDOFF_FIELDS = {
    "schema", "handoff_ref", "run_ref", "event_ref", "status", "target_stage",
    "owner_mode", "owner_session_ref", "repo_ref", "wave_ref", "causal_refs",
    "trace_links", "build_ref", "source_snapshot_digest", "journal_digest",
    "artifact_refs", "decision_refs", "requirement_refs", "functionality_refs",
    "graph_entity_refs", "task_refs", "remediation_refs", "finding_refs",
    "evidence_refs", "delegation_records", "stage_payload",
}
HANDOFF_EVENT_KINDS = {"run-start", "stage", "repo-handoff", "analysis"}
ARTIFACT_KINDS = {"code", "configuration", "document", "evidence"}


def _handoff_ref(event_ref: str, build_ref: str) -> str:
    binding = digest_bytes(canonical({"build_ref": build_ref, "event_ref": event_ref}))
    return "HANDOFF-" + binding.removeprefix("sha256:")[:24].upper()


def _refs(value: Any, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise GraphError("HANDOFF_INVALID", f"{field} must contain unique non-empty refs")
    return value


def _causal_closure(store: GraphStore, event: dict[str, Any]) -> list[dict[str, Any]]:
    run_events = {
        item["event_ref"]: item
        for item in store.process.get("events", [])
        if item.get("run_ref") == event["run_ref"]
    }
    closure: set[str] = set()
    frontier = [event["event_ref"]]
    while frontier:
        event_ref = frontier.pop()
        if event_ref in closure:
            continue
        item = run_events.get(event_ref)
        if item is None:
            raise GraphError("HANDOFF_INVALID", "handoff causal closure is incomplete", event_ref=event_ref)
        closure.add(event_ref)
        frontier.extend(item.get("causal_refs", []))
    return [run_events[event_ref] for event_ref in sorted(closure)]


def _derived_bindings(
    store: GraphStore,
    event: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    task_by_ref: dict[str, dict[str, Any]],
) -> dict[str, set[str]]:
    closure = _causal_closure(store, event)
    source_events = closure if event["status"] == "implemented" else [event]
    task_refs = {
        task_ref
        for item in source_events
        for task_ref in item.get("task_refs", [])
    }
    trace_refs = {
        ref
        for item in source_events
        for ref in item.get("trace_refs", [])
    }
    artifact_refs = {
        ref
        for item in source_events
        for ref in item.get("artifact_refs", [])
    }
    finding_refs = {
        ref
        for item in source_events
        for ref in _event_finding_refs(item)
    }
    if event["status"] == "implemented":
        for task_ref in sorted(task_refs):
            task = task_by_ref.get(task_ref)
            if task is None:
                raise GraphError("HANDOFF_INVALID", "implemented handoff task is missing", task_ref=task_ref)
            trace_refs.add(task_ref)
            for field in (
                "requirement_refs",
                "functionality_refs",
                "graph_entity_refs",
            ):
                trace_refs.update(task.get(field, []))
            artifact_refs.update(task.get("implementation_refs", []))
            artifact_refs.update(task.get("evidence_refs", []))

        finding_by_ref = {
            finding["finding_ref"]: finding
            for finding in store.process.get("findings", [])
            if isinstance(finding, dict) and isinstance(finding.get("finding_ref"), str)
        }
        for finding_ref in sorted(finding_refs):
            finding = finding_by_ref.get(finding_ref)
            if finding is None:
                raise GraphError("HANDOFF_INVALID", "causal finding is absent from the bound process index", finding_ref=finding_ref)
            for subject_ref in finding.get("subject_refs", []) + finding.get("conflict_refs", []):
                kind = entities.get(subject_ref, {}).get("kind")
                if kind in ARTIFACT_KINDS:
                    artifact_refs.add(subject_ref)
                elif kind is not None:
                    trace_refs.add(subject_ref)

    bound_refs = (
        trace_refs
        | artifact_refs
        | task_refs
        | finding_refs
        | {item["event_ref"] for item in closure}
    )
    return {
        "trace_refs": trace_refs,
        "artifact_refs": artifact_refs,
        "task_refs": task_refs,
        "finding_refs": finding_refs,
        "bound_refs": bound_refs,
    }


def _trace_links(store: GraphStore, bound: set[str]) -> list[dict[str, str]]:
    links = [
        {key: edge[key] for key in ("ref", "kind", "from_ref", "to_ref")}
        for edge in store.trace.get("edges", [])
        if edge.get("from_ref") in bound and edge.get("to_ref") in bound
    ]
    links.extend(
        {key: link[key] for key in ("ref", "kind", "from_ref", "to_ref")}
        for link in store.process.get("links", [])
        if link.get("from_ref") in bound and link.get("to_ref") in bound
    )
    return sorted(links, key=lambda item: item["ref"])


def handoff_validate(arguments: dict[str, Any]) -> dict[str, Any]:
    store = GraphStore.load(arguments)
    try:
        packet = arguments.get("handoff")
        if not isinstance(packet, dict) or set(packet) != HANDOFF_FIELDS:
            raise GraphError("HANDOFF_INVALID", "handoff fields are incomplete")
        if packet.get("schema") != "app-stage-handoff.v4" or not isinstance(packet.get("handoff_ref"), str) or not packet["handoff_ref"]:
            raise GraphError("HANDOFF_INVALID", "handoff identity is invalid")
        for field in (
            "causal_refs", "artifact_refs", "decision_refs", "requirement_refs",
            "functionality_refs", "graph_entity_refs", "task_refs",
            "remediation_refs", "finding_refs", "evidence_refs",
        ):
            _refs(packet.get(field), field)
        if (
            not isinstance(packet.get("trace_links"), list)
            or not isinstance(packet.get("delegation_records"), list)
            or not isinstance(packet.get("stage_payload"), dict)
            or not packet["stage_payload"]
        ):
            raise GraphError("HANDOFF_INVALID", "handoff trace links or payload are invalid")
        routes = _validate_workflow(store.workflow)
        events = {
            item["event_ref"]: item
            for item in store.process.get("events", [])
            if isinstance(item, dict) and isinstance(item.get("event_ref"), str)
        }
        event = events.get(packet.get("event_ref"))
        if event is None or event["event_kind"] not in HANDOFF_EVENT_KINDS:
            raise GraphError("HANDOFF_INVALID", "handoff event is not an eligible current boundary")
        run_events = [
            item for item in store.process.get("events", [])
            if item.get("run_ref") == event["run_ref"]
        ]
        causal_parents = {
            cause_ref
            for item in run_events
            for cause_ref in item.get("causal_refs", [])
        }
        leaf_refs = {
            item["event_ref"] for item in run_events
            if item["event_ref"] not in causal_parents
        }
        if leaf_refs != {event["event_ref"]}:
            raise GraphError("HANDOFF_INVALID", "handoff event is not the sole current run boundary")
        owner_mode = "DIRECT" if event["actor"] == "DIRECT-primary" else "DELEGATED"
        expected_scalars = {
            "handoff_ref": _handoff_ref(event["event_ref"], store.build["build_ref"]),
            "run_ref": event["run_ref"],
            "event_ref": event["event_ref"],
            "status": event["status"],
            "target_stage": routes[event["status"]],
            "owner_mode": owner_mode,
            "owner_session_ref": event["owner_session_ref"],
            "repo_ref": event["repo_ref"],
            "wave_ref": event["wave_ref"],
            "build_ref": store.build["build_ref"],
            "source_snapshot_digest": store.build["source_snapshot_digest"],
            "journal_digest": store.build["journal_digest"],
        }
        for field, expected in expected_scalars.items():
            if packet.get(field) != expected:
                raise GraphError("HANDOFF_INVALID", f"handoff {field} differs from the current boundary")
        if packet["causal_refs"] != event["causal_refs"]:
            raise GraphError("HANDOFF_INVALID", "handoff causes differ from its event")

        entities = {item["ref"]: item for item in store.trace.get("entities", [])}
        if any(entities.get(ref, {}).get("kind") not in ARTIFACT_KINDS for ref in event["artifact_refs"]):
            raise GraphError("HANDOFF_INVALID", "event artifact refs are not typed artifacts")
        if any(ref not in entities for ref in event["trace_refs"] + event["task_refs"]):
            raise GraphError("HANDOFF_INVALID", "event trace refs are not typed current entities")
        task_by_ref = {task["task_id"]: task for task in store.ledger.get("tasks", [])}
        derived = _derived_bindings(store, event, entities, task_by_ref)
        expected_artifacts = sorted(derived["artifact_refs"])
        expected_decisions = sorted(ref for ref in derived["trace_refs"] if entities[ref]["kind"] == "decision")
        expected_requirements = sorted(ref for ref in derived["trace_refs"] if entities[ref]["kind"] == "requirement")
        expected_functionalities = sorted(ref for ref in derived["trace_refs"] if entities[ref]["kind"] == "functionality")
        expected_tasks = sorted(derived["task_refs"])
        categorized_trace = set(expected_decisions + expected_requirements + expected_functionalities + expected_tasks)
        expected_graph_entities = sorted(set(derived["trace_refs"]) - categorized_trace)
        expected_remediations = sorted(
            ref
            for ref in derived["task_refs"]
            if task_by_ref.get(ref, {}).get("task_kind") == "remediation"
        )
        expected_evidence = sorted(ref for ref in derived["artifact_refs"] if entities[ref]["kind"] == "evidence")
        expected_findings = sorted(derived["finding_refs"])
        if event["status"] == "implemented" and (not expected_artifacts or not expected_evidence):
            raise GraphError("HANDOFF_INVALID", "implemented handoff needs bound implementation artifacts and evidence")
        expected_lists = {
            "artifact_refs": expected_artifacts,
            "decision_refs": expected_decisions,
            "requirement_refs": expected_requirements,
            "functionality_refs": expected_functionalities,
            "graph_entity_refs": expected_graph_entities,
            "task_refs": expected_tasks,
            "remediation_refs": expected_remediations,
            "finding_refs": expected_findings,
            "evidence_refs": expected_evidence,
            "delegation_records": event.get("delegation_records", []),
            "trace_links": _trace_links(store, derived["bound_refs"]),
        }
        for field, expected in expected_lists.items():
            if packet[field] != expected:
                raise GraphError("HANDOFF_INVALID", f"handoff {field} differs from its derived current value")

        payload_digest = digest_bytes(canonical(packet["stage_payload"]))
        if payload_digest != event["handoff_payload_digest"]:
            raise GraphError("HANDOFF_INVALID", "handoff stage payload differs from its recorded digest")
        expected_payload = _terminal_stage_payload(
            store.process.get("events", []), task_by_ref, event,
        )
        if expected_payload is not None and packet["stage_payload"] != expected_payload:
            raise GraphError("HANDOFF_INVALID", "handoff stage payload differs from its derived current value")
        return {
            "schema": "app-stage-handoff-validation-result.v1",
            "status": "valid",
            "valid": True,
            "handoff_ref": packet["handoff_ref"],
            "event_ref": event["event_ref"],
            "build_ref": store.build["build_ref"],
        }
    finally:
        store.close()
