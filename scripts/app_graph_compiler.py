"""Compile structured app sources into immutable build receipts and current indexes."""

from __future__ import annotations

from collections import defaultdict, deque
import fcntl
import os
from pathlib import Path
import secrets
import stat
from typing import Any

from app_graph_store import *


def _entity(ref: str, kind: str, path: str, digest: str, **extra: Any) -> dict[str, Any]:
    return {"ref": ref, "kind": kind, "scope": extra.get("scope", "app"), "active": extra.get("active", True), "source": {"path": path, "anchor": ref, "digest": digest}}


def _atomic_write(root: RepoRoot, relative: str, payload: bytes, *, immutable: bool = False) -> None:
    names = parts(relative); parent = open_directory(root, names[:-1], create=True)
    temporary = f".{names[-1]}.{secrets.token_hex(8)}.tmp"; descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    try:
        os.write(descriptor, payload); os.fsync(descriptor)
    finally: os.close(descriptor)
    try:
        if immutable:
            try: os.link(temporary, names[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            except FileExistsError:
                current = read_regular(root, relative)
                if current != payload: raise GraphError("RECEIPT_CONFLICT", "immutable receipt already differs", path=relative)
        else: os.replace(temporary, names[-1], src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        try: os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError: pass
        os.close(parent)


def _validate_dimensions(fmap: dict[str, Any]) -> None:
    if fmap.get("schema") == "app-functional-map.v2": return
    if fmap.get("schema") != "app-functional-map.v3": raise GraphError("SCHEMA_UNSUPPORTED", "functional map must be v3; v2 is read-only")
    expected = {"behavior", "dependency", "state", "api", "data", "integration", "error"}
    active = [x["ref"] for x in fmap.get("entities", []) if x.get("kind") == "requirement" and x.get("active", True)]
    coverage = fmap.get("requirement_dimensions", {})
    if set(coverage) != set(active): raise GraphError("DIMENSION_COVERAGE", "every active requirement needs exactly seven dimensions")
    for requirement, dimensions in coverage.items():
        if set(dimensions) != expected: raise GraphError("DIMENSION_COVERAGE", "dimension set must be exact", requirement_ref=requirement)
        for name, value in dimensions.items():
            if value.get("status") == "not-applicable":
                if not value.get("rationale") or value.get("refs") != []: raise GraphError("DIMENSION_NA_INVALID", "not-applicable needs rationale and empty refs", requirement_ref=requirement, dimension=name)
            elif value.get("status") != "applicable" or not value.get("refs"): raise GraphError("DIMENSION_COVERAGE", "applicable dimension needs refs", requirement_ref=requirement, dimension=name)


def build_indexes(root: RepoRoot, source_manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = source_manifest["sources"]; values, locators, snapshot = source_snapshot(root, config)
    fmap, ledger, artifacts, workflow = (values[config[key]] for key in ("functional_map", "task_ledger", "artifact_catalog", "workflow"))
    _validate_dimensions(fmap)
    if ledger.get("schema") != "app-task-ledger.v2" or workflow.get("schema") != "app-workflow-definition.v2": raise GraphError("SCHEMA_UNSUPPORTED", "workflow v2 and ledger v2 are required")
    source_digest = {x["path"]: x["digest"] for x in locators}; registry = workflow.get("graph", {}).get("edge_types", {})
    entities: dict[str, dict[str, Any]] = {}; edges: dict[str, dict[str, Any]] = {}
    def add_entity(item: dict[str, Any], path: str, *, digest: str | None = None) -> None:
        ref, kind = item.get("ref"), item.get("kind")
        if not ref or not kind or ref in entities: raise GraphError("DUPLICATE_REF", "entity ref is missing or duplicated", ref=ref)
        entities[ref] = _entity(ref, kind, path, digest or source_digest[path], scope=item.get("scope", "app"), active=item.get("active", True))
    def add_edge(item: dict[str, Any], path: str) -> None:
        ref, kind = item.get("ref"), item.get("kind")
        if not ref or ref in edges or kind not in registry: raise GraphError("EDGE_KIND_UNKNOWN", "edge ref/kind is invalid", ref=ref)
        edges[ref] = {"ref": ref, "kind": kind, "from_ref": item.get("from_ref"), "to_ref": item.get("to_ref"), "source_refs": [path], "condition_refs": sorted(item.get("condition_refs", [])), "active": item.get("active", True)}
    for item in fmap.get("entities", []): add_entity(item, config["functional_map"])
    for item in fmap.get("relations", []): add_edge(item, config["functional_map"])
    artifact_refs = {}
    for item in artifacts.get("artifacts", []):
        artifact_refs[item["ref"]] = item; add_entity({"ref": item["ref"], "kind": item["kind"]}, item["path"], digest=digest_bytes(read_regular(root, item["path"]) or b""))
    tasks = {item["task_id"]: item for item in ledger.get("tasks", [])}
    for task_ref, task in tasks.items():
        add_entity({"ref": task_ref, "kind": "task", "scope": task.get("wave_id", "app"), "active": task.get("status") != "superseded"}, config["task_ledger"])
        for prerequisite in task.get("depends_on", []):
            if prerequisite not in tasks: raise GraphError("DANGLING_REF", "task prerequisite is missing", task_ref=task_ref, prerequisite_ref=prerequisite)
            add_edge({"ref": f"LEDGER-DEP:{task_ref}:{prerequisite}", "kind": "depends_on", "from_ref": task_ref, "to_ref": prerequisite}, config["task_ledger"])
        for functionality in task.get("functionality_refs", []): add_edge({"ref": f"TRACE:{functionality}:{task_ref}", "kind": "decomposes_to", "from_ref": functionality, "to_ref": task_ref}, config["task_ledger"])
        for code in task.get("code_refs", []): add_edge({"ref": f"TRACE:{task_ref}:{code}", "kind": "implemented_by", "from_ref": task_ref, "to_ref": code}, config["task_ledger"])
        for code in task.get("code_refs", []):
            for test in task.get("test_refs", []):
                ref = f"TRACE:{code}:{test}"
                if ref not in edges: add_edge({"ref": ref, "kind": "verified_by", "from_ref": code, "to_ref": test}, config["task_ledger"])
        for test in task.get("test_refs", []):
            for evidence in task.get("evidence_refs", []):
                ref = f"TRACE:{test}:{evidence}"
                if ref not in edges: add_edge({"ref": ref, "kind": "evidenced_by", "from_ref": test, "to_ref": evidence}, config["task_ledger"])
    for edge in edges.values():
        if edge["from_ref"] not in entities or edge["to_ref"] not in entities: raise GraphError("DANGLING_REF", "edge endpoint is missing", edge_ref=edge["ref"])
    dependency = [x for x in edges.values() if x["kind"] == "depends_on" and entities[x["from_ref"]].get("active") and entities[x["to_ref"]].get("active")]
    indegree = {ref: 0 for ref, x in entities.items() if x["kind"] == "task" and x.get("active")}; outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in dependency: indegree[edge["from_ref"]] += 1; outgoing[edge["to_ref"]].append(edge["from_ref"])
    queue = deque(sorted(x for x, degree in indegree.items() if not degree)); visited = 0
    while queue:
        ref = queue.popleft(); visited += 1
        for target in outgoing[ref]:
            indegree[target] -= 1
            if not indegree[target]: queue.append(target)
    if visited != len(indegree): raise GraphError("GRAPH_CYCLE", "active ledger dependency cycle")
    events = []
    for path in event_paths(root, config["event_roots"]):
        event = values[path]; schema = event.get("schema")
        if schema not in {"app-process-event.v1", "app-process-event.v2"}: raise GraphError("JOURNAL_CORRUPT", "unsupported event schema", path=path)
        if schema == "app-process-event.v2" and not path.startswith(config["event_roots"][-1] + "/"): raise GraphError("JOURNAL_CORRUPT", "v2 event is outside v2 journal", path=path)
        events.append(event)
    links = [{"ref": f"CAUSE:{cause}:{event['event_ref']}", "kind": "causes", "from_ref": cause, "to_ref": event["event_ref"]} for event in events for cause in event.get("causal_refs", [])]
    trace_body = {"schema": "app-traceability-index.v3", "app_id": fmap.get("app_id"), "source_snapshot_digest": snapshot, "generated_from": locators, "roots": sorted(x for x, e in entities.items() if e["kind"] == "spec"), "evidence_sinks": sorted(x for x, e in entities.items() if e["kind"] == "evidence"), "entities": sorted(entities.values(), key=lambda x:x["ref"]), "edges": sorted(edges.values(), key=lambda x:x["ref"]), "replacements": fmap.get("replacements", []), "findings": []}
    process_body = {"schema": "app-process-index.v3", "app_id": fmap.get("app_id"), "workflow_definition_ref": config["workflow"], "workflow_definition_digest": source_digest[config["workflow"]], "source_snapshot_digest": snapshot, "runs": sorted({x["run_ref"] for x in events}), "events": sorted(events, key=lambda x:x["event_ref"]), "links": sorted(links, key=lambda x:x["ref"]), "findings": []}
    content = digest_bytes(canonical({"trace": trace_body, "process": process_body})); build_ref = "BUILD-" + content[7:31].upper()
    trace = {**trace_body, "build_ref": build_ref}; process = {**process_body, "build_ref": build_ref, "journal_digest": digest_bytes(canonical(events))}
    build = {"schema":"app-index-build.v1","build_ref":build_ref,"source_snapshot_digest":snapshot,"journal_digest":process["journal_digest"],"trace_index_digest":digest_bytes(canonical(trace)),"process_index_digest":digest_bytes(canonical(process)),"source_count":len(locators),"entity_count":len(entities),"edge_count":len(edges),"event_count":len(events)}
    context = {"schema":"app-context-index-result.v1","status":"built","build_ref":build_ref,"source_snapshot_digest":snapshot,"journal_digest":process["journal_digest"],"traceability_index_ref":TRACE_PATH,"process_index_ref":PROCESS_PATH,"build_receipt_ref":f"{BUILD_ROOT}/{build_ref}.json"}
    return trace, process, build, context


def graph_compile(arguments: dict[str, Any]) -> dict[str, Any]:
    root = safe_root(arguments.get("app_root"))
    try:
        source_manifest = manifest(root, require_maintainer=True); lock = open_directory(root, ("docs",)); fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            pointer_raw = read_regular(root, CURRENT_BUILD_PATH, max_bytes=262144, missing=True); pointer = {} if pointer_raw is None else __import__("json").loads(pointer_raw)
            expected, current = arguments.get("expected_build_ref"), pointer.get("build_ref")
            if expected is not None and expected != current: raise GraphError("CAS_MISMATCH", "expected build does not match current build", expected=expected, actual=current)
            trace, process, build, context = build_indexes(root, source_manifest)
            _, stable, snapshot = source_snapshot(root, source_manifest["sources"])
            if snapshot != build["source_snapshot_digest"] or stable != trace["generated_from"]: raise GraphError("SOURCE_DRIFT", "sources changed during compilation")
            receipt = f"{BUILD_ROOT}/{build['build_ref']}.json"; current_pointer = {"schema":"app-index-current.v1","build_ref":build["build_ref"],"receipt_ref":receipt}
            if current == build["build_ref"] and pointer == current_pointer: return {**context,"schema":"app-graph-compile-result.v1","status":"current","no_op":True}
            _atomic_write(root, receipt, canonical(build), immutable=True)
            for path, value in ((TRACE_PATH,trace),(PROCESS_PATH,process),(CONTEXT_PATH,context),(CURRENT_BUILD_PATH,current_pointer)): _atomic_write(root,path,canonical(value))
            QUERY_CACHE.clear(); return {**context,"schema":"app-graph-compile-result.v1","no_op":False}
        finally: os.close(lock)
    finally: root.close()
