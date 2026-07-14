"""Append immutable process v3 records with exact repo-wave lifecycle rules."""

from __future__ import annotations

import fcntl
import os
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
    "remediation", "repo-handoff", "analysis",
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
REQUIRED_STRINGS = (
    "run_ref", "event_ref", "event_kind", "stage", "status", "actor",
    "repo_ref", "wave_ref", "origin",
)
REQUIRED_ARRAYS = ("causal_refs", "trace_refs", "artifact_refs", "task_refs")
OPTIONAL_FIELDS = {
    "task_ref", "terminal_result", "reviewed_task_refs", "finding_refs",
    "commit_range", "remediates_run_ref", "analysis_ref", "analysis_result",
    "delegation_record",
}
OPTIONAL_BY_KIND = {
    "run-start": {"remediates_run_ref"},
    "stage": set(),
    "delegation": {"delegation_record"},
    "task-result": {"task_ref", "terminal_result"},
    "review": {"reviewed_task_refs", "commit_range"},
    "remediation": {"finding_refs"},
    "repo-handoff": set(),
    "analysis": {"analysis_ref", "analysis_result"},
}
ANALYSIS_FIELDS = {
    "schema", "analysis_ref", "profile_ref", "model_ref", "checklist_ref",
    "basis_build_ref", "input_refs", "coverage", "findings",
    "unmapped_decision_refs", "unmapped_requirement_refs",
    "open_remediation_refs", "complete", "route",
}
ANALYSIS_STRING_FIELDS = {
    "analysis_ref", "profile_ref", "model_ref", "checklist_ref", "basis_build_ref",
}
COVERAGE_FIELDS = {
    "sources", "decisions", "requirements", "dimensions", "tasks",
    "process_records",
}
FINDING_FIELDS = {
    "finding_ref", "kind", "subject_refs", "conflict_refs", "route", "summary",
}
DELEGATION_FIELDS = {
    "dispatch_schema", "result_schema", "delegation_authority_ref",
    "assignment_authority_ref", "assignment_id", "task_id", "role",
    "role_kind", "agent_level", "orchestrator_session_id",
}
DELEGATION_OPTIONAL_FIELDS = {"app_task_schema"}


def _valid_refs(value: Any, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item) for item in value)
        and len(value) == len(set(value))
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _route_registry(workflow: dict[str, Any] | None) -> dict[str, str]:
    if workflow is None:
        return FINDING_ROUTES
    routes = workflow.get("finding_routes")
    if routes != FINDING_ROUTES:
        raise GraphError("SCHEMA_UNSUPPORTED", "workflow finding routes drifted from the runtime")
    return routes


def _validate_workflow(workflow: Any) -> dict[str, str]:
    if (
        not isinstance(workflow, dict)
        or workflow.get("schema") != "app-workflow-definition.v3"
        or workflow.get("stages") != list(STAGES)
        or workflow.get("routes") != ROUTES
        or workflow.get("finding_routes") != FINDING_ROUTES
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", "workflow stage or route registry is invalid")
    return ROUTES


def _validate_delegation(event: dict[str, Any]) -> None:
    record = event.get("delegation_record")
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
    ):
        raise GraphError("DELEGATION_INVALID", "delegation packet identity is invalid")
    if (record["role"] == "app-worker") != (record.get("app_task_schema") == "app-task-dispatch.v2"):
        raise GraphError("DELEGATION_INVALID", "app task packet identity disagrees with the selected role")
    if record["task_id"] not in event["task_refs"]:
        raise GraphError("RUN_SCOPE_INVALID", "delegated task is outside the event task set")


def _validate_analysis(event: dict[str, Any], routes: dict[str, str]) -> None:
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
    for field in (
        "input_refs", "unmapped_decision_refs", "unmapped_requirement_refs",
        "open_remediation_refs",
    ):
        if not _valid_refs(result.get(field), allow_empty=field != "input_refs"):
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
    findings = result.get("findings")
    if not isinstance(findings, list):
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis findings are invalid")
    finding_refs: set[str] = set()
    finding_routes: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != FINDING_FIELDS:
            raise GraphError("ANALYSIS_INCOMPLETE", "analysis finding fields are incomplete")
        finding_ref = finding.get("finding_ref")
        kind = finding.get("kind")
        if (
            not _nonempty_string(finding_ref)
            or finding_ref in finding_refs
            or kind not in routes
            or finding.get("route") != routes[kind]
            or not _nonempty_string(finding.get("summary"))
            or not _valid_refs(finding.get("subject_refs"))
            or not _valid_refs(finding.get("conflict_refs"))
        ):
            raise GraphError("ANALYSIS_INCOMPLETE", "analysis finding identity or route is invalid")
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
    route_priority = ("needs-research", "needs-spec", "needs-graph", "needs-plan")
    if "blocked" in possible_routes:
        expected_route = "blocked"
    else:
        expected_route = next((candidate for candidate in route_priority if candidate in possible_routes), "none")
    if route != expected_route:
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis route disagrees with its findings")
    if route != "none" and result["complete"] is not False:
        raise GraphError("ANALYSIS_INCOMPLETE", "routed analysis must remain incomplete")
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


def _validate_event(event: Any, workflow: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply the full event-shape and semantic checks shared by append and compile."""
    if not isinstance(event, dict) or event.get("schema") != "app-process-event.v3":
        raise GraphError("SCHEMA_UNSUPPORTED", "new events must use app-process-event.v3")
    allowed = {"schema", *REQUIRED_STRINGS, *REQUIRED_ARRAYS, *OPTIONAL_FIELDS}
    if set(event) - allowed:
        raise GraphError("JOURNAL_CORRUPT", "event contains unknown fields")
    if any(not _nonempty_string(event.get(field)) for field in REQUIRED_STRINGS):
        raise GraphError("JOURNAL_CORRUPT", "event string fields are incomplete")
    if any("/" in event[field] or ".." in event[field] for field in ("run_ref", "event_ref")):
        raise GraphError("PATH_ESCAPE", "event and run refs must be safe")
    if any(not _valid_refs(event.get(field)) for field in REQUIRED_ARRAYS):
        raise GraphError("JOURNAL_CORRUPT", "event reference arrays are invalid")
    for field in ("reviewed_task_refs", "finding_refs"):
        if field in event and not _valid_refs(event[field]):
            raise GraphError("JOURNAL_CORRUPT", f"{field} is invalid")
    if event["origin"] != "native" or event["actor"] not in ACTORS:
        raise GraphError("OWNERSHIP_INVALID", "only a primary or repo-L2 may record native events")
    if event["event_kind"] not in EVENT_KINDS:
        raise GraphError("JOURNAL_CORRUPT", "event kind is invalid")
    irrelevant = (OPTIONAL_FIELDS & set(event)) - OPTIONAL_BY_KIND[event["event_kind"]]
    if irrelevant:
        raise GraphError("JOURNAL_CORRUPT", "event contains fields irrelevant to its kind")
    if event["stage"] not in STAGES or event["status"] not in STATUSES:
        raise GraphError("JOURNAL_CORRUPT", "event stage or status is invalid")
    if event["event_kind"] == "stage" and event["status"] not in ROUTES:
        raise GraphError("RUN_TRANSITION_INVALID", "stage status has no workflow route")
    if event["event_kind"] in {"delegation", "task-result", "review", "remediation", "repo-handoff"} and event["stage"] != "app-dev":
        raise GraphError("RUN_SCOPE_INVALID", "app-dev lifecycle event has the wrong stage")
    if event["event_kind"] == "analysis" and event["stage"] != "app-analyze":
        raise GraphError("ANALYSIS_INCOMPLETE", "analysis event has the wrong stage")
    if event["event_kind"] == "run-start":
        remediation_ref = event.get("remediates_run_ref")
        if (
            not event["task_refs"]
            or event["causal_refs"]
            or (remediation_ref is not None and not _nonempty_string(remediation_ref))
            or remediation_ref == event["run_ref"]
        ):
            raise GraphError("RUN_SCOPE_INVALID", "run-start needs an exact task set and no local cause")
    elif not event["causal_refs"]:
        raise GraphError("RUN_SCOPE_INVALID", "every event after run-start needs a local cause")
    if event["event_kind"] == "task-result":
        if (
            not _nonempty_string(event.get("task_ref"))
            or event.get("task_ref") not in event["task_refs"]
            or event.get("terminal_result") not in {"done", "failed", "blocked"}
            or event["status"] != event["terminal_result"]
        ):
            raise GraphError("RUN_SCOPE_INVALID", "task-result needs one scoped terminal result")
    if event["event_kind"] == "review":
        if not _nonempty_string(event.get("commit_range")) or not _valid_refs(event.get("reviewed_task_refs"), allow_empty=False):
            raise GraphError("REVIEW_INCOMPLETE", "review needs an exact commit range and task set")
    if event["event_kind"] == "remediation" and not _valid_refs(event.get("finding_refs"), allow_empty=False):
        raise GraphError("REMEDIATION_RUN_REQUIRED", "remediation needs finding refs")
    if event["event_kind"] == "delegation":
        _validate_delegation(event)
    elif "delegation_record" in event:
        raise GraphError("DELEGATION_INVALID", "only delegation events may contain delegation records")
    if event["event_kind"] == "analysis":
        _validate_analysis(event, _route_registry(workflow))
    elif "analysis_ref" in event or "analysis_result" in event or event["status"] == "audited":
        raise GraphError("ANALYSIS_INCOMPLETE", "only analysis events may contain analysis data or audited status")
    return event


def _terminal_event(event: dict[str, Any]) -> bool:
    return event["status"] == "audited" or (
        event["status"] == "blocked" and event["event_kind"] != "task-result"
    )


def _validate_run_lifecycle(
    events: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    workflow: dict[str, Any],
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
    if any(event[key] != start[key] for event in checked for key in ("actor", "repo_ref", "wave_ref", "task_refs")):
        raise GraphError("RUN_SCOPE_INVALID", "event authority or scope differs from run-start")
    for task_ref in start["task_refs"]:
        task = tasks.get(task_ref)
        if not isinstance(task, dict):
            raise GraphError("DANGLING_REF", "run task is missing from the ledger", task_ref=task_ref)
        if (
            task.get("owner_role") != start["actor"]
            or task.get("repo_ref") != start["repo_ref"]
            or task.get("wave_id") != start["wave_ref"]
        ):
            raise GraphError("OWNERSHIP_INVALID", "run task authority or scope disagrees with the ledger", task_ref=task_ref)
    ordered = causal_order(checked)
    if ordered[0]["event_ref"] != start["event_ref"]:
        raise GraphError("RUN_SCOPE_INVALID", "run-start must be the only causal root")
    task_results: dict[str, dict[str, Any]] = {}
    by_ref = {event["event_ref"]: event for event in checked}
    for event in ordered:
        for cause_ref in event["causal_refs"]:
            cause = by_ref[cause_ref]
            if cause["stage"] != event["stage"] and routes.get(cause["status"]) != event["stage"]:
                raise GraphError(
                    "RUN_TRANSITION_INVALID",
                    "stage change does not follow the workflow route",
                    from_event_ref=cause_ref,
                    to_event_ref=event["event_ref"],
                )
        if event["event_kind"] == "task-result":
            task_ref = event["task_ref"]
            if task_ref not in start["task_refs"] or task_ref in task_results:
                raise GraphError("RUN_SCOPE_INVALID", "task result is outside scope or duplicated", task_ref=task_ref)
            task_results[task_ref] = event
        if event["event_kind"] == "review":
            if set(task_results) != set(start["task_refs"]):
                raise GraphError("REVIEW_INCOMPLETE", "review requires full-run terminal results")
            if set(event["reviewed_task_refs"]) != set(start["task_refs"]):
                raise GraphError("REVIEW_INCOMPLETE", "review task set differs from run scope")
        if event["event_kind"] == "analysis" and not any(
            by_ref[cause_ref]["status"] in {"implemented", "no-work"}
            for cause_ref in event["causal_refs"]
        ):
            raise GraphError("ANALYSIS_INCOMPLETE", "analysis must directly follow implemented or no-work")
    terminals = [event for event in ordered if _terminal_event(event)]
    if len(terminals) > 1:
        raise GraphError("RUN_TERMINAL_CONFLICT", "run has more than one terminal event")
    if terminals and ordered[-1]["event_ref"] != terminals[0]["event_ref"]:
        raise GraphError("RUN_SEALED", "run contains records after its terminal event")
    if terminals:
        ancestors: set[str] = set()
        frontier = list(terminals[0]["causal_refs"])
        while frontier:
            ref = frontier.pop()
            if ref in ancestors:
                continue
            ancestors.add(ref)
            frontier.extend(by_ref[ref]["causal_refs"])
        if ancestors != set(by_ref) - {terminals[0]["event_ref"]}:
            raise GraphError("RUN_SEALED", "terminal event must causally seal the full run")
    audited = [event for event in checked if event["status"] == "audited"]
    if audited:
        event = audited[0]
        if event["event_kind"] != "analysis" or event["stage"] != "app-analyze":
            raise GraphError("ANALYSIS_INCOMPLETE", "audited must be the final app-analyze event")
        if set(task_results) != set(start["task_refs"]):
            raise GraphError("ANALYSIS_INCOMPLETE", "audited requires terminal results for every run task")
    return ordered


def _existing_events(root: RepoRoot, event_roots: list[str]) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    for path in event_paths(root, event_roots):
        event, _ = read_json(root, path)
        records.append((path, event))
    return records


def process_record_event(arguments: dict[str, Any]) -> dict[str, Any]:
    root = safe_root(arguments.get("app_root"))
    try:
        source_manifest = manifest(root, require_maintainer=True)
        workflow, _ = read_json(root, source_manifest["sources"]["workflow"])
        ledger, _ = read_json(root, source_manifest["sources"]["task_ledger"])
        event = _validate_event(arguments.get("event"), workflow)
        tasks = {task.get("task_id"): task for task in ledger.get("tasks", []) if isinstance(task, dict)}
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
                    for run_events in existing_runs.values():
                        _validate_run_lifecycle(run_events, tasks, workflow)
                    return {
                        "schema": "app-process-event-result.v1", "status": "current",
                        "event_ref": ref, "no_op": True,
                    }
                raise GraphError("EVENT_CONFLICT", "event key already differs", event_ref=ref)
            existing_runs.setdefault(run_ref, []).append(event)
            for run_events in existing_runs.values():
                _validate_run_lifecycle(run_events, tasks, workflow)
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
