"""Deterministic graph compiler, immutable journal, and bounded audit/query engine."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any, Iterable

MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 16 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SOURCES = 2_048
MAX_ENTITIES = 25_000
MAX_EDGES = 100_000
MAX_EVENTS = 20_000
MAX_PROCESS_LINKS = 50_000
MAX_PAGE = 200
MAX_DEPTH = 32
MANIFEST_PATH = "docs/app-graph-source-manifest.v1.json"
TRACE_PATH = "docs/app-traceability-index.v3.json"
PROCESS_PATH = "docs/app-process-index.v2.json"
BUILD_PATH = "docs/app-index-build.v1.json"
CONTEXT_PATH = "docs/app-context-index-result.v1.json"
GENERATED_PATHS = {
    "trace_index": TRACE_PATH,
    "process_index": PROCESS_PATH,
    "build_receipt": BUILD_PATH,
    "context_result": CONTEXT_PATH,
}
FIXED_LIMITS = {
    "sources": MAX_SOURCES,
    "source_bytes": MAX_SOURCE_BYTES,
    "entities": MAX_ENTITIES,
    "edges": MAX_EDGES,
    "events": MAX_EVENTS,
    "process_links": MAX_PROCESS_LINKS,
}


class GraphError(RuntimeError):
    """Stable bounded failure returned by both MCP servers."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass
class RepoRoot:
    """One inode-bound repository root used for all graph filesystem access."""

    path: Path
    fd: int
    device: int
    inode: int

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __str__(self) -> str:
        return str(self.path)


def _safe_root(value: Any) -> RepoRoot:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise GraphError("INVALID_ROOT", "app_root must be a non-empty absolute path")
    supplied = Path(value)
    try:
        descriptor = os.open(supplied, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
    except OSError as exc:
        raise GraphError("INVALID_ROOT", "app_root must be a real non-symlink directory") from exc
    if not stat.S_ISDIR(info.st_mode):
        os.close(descriptor)
        raise GraphError("INVALID_ROOT", "app_root must be a directory")
    return RepoRoot(supplied.absolute(), descriptor, info.st_dev, info.st_ino)


def _parts(relative: str) -> tuple[str, ...]:
    if not isinstance(relative, str) or not relative:
        raise GraphError("PATH_ESCAPE", "relative path is required")
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise GraphError("PATH_ESCAPE", "path must remain below app_root", path=relative)
    if any(part in {"", "."} for part in rel.parts):
        raise GraphError("PATH_ESCAPE", "path contains an unsafe component", path=relative)
    return tuple(rel.parts)


def _open_directory(root: RepoRoot, parts: Iterable[str], *, create: bool = False) -> int:
    descriptor = os.dup(root.fd)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise GraphError("PATH_ESCAPE", "directory path is missing, linked, or unsafe") from exc


def _read_regular(root: RepoRoot, relative: str, *, max_bytes: int, missing: bool = False) -> bytes | None:
    parts = _parts(relative)
    parent = _open_directory(root, parts[:-1])
    descriptor = -1
    try:
        try:
            descriptor = os.open(parts[-1], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            if missing:
                return None
            raise GraphError("ARTIFACT_MISSING", "required regular file is missing", path=relative)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise GraphError("PATH_ESCAPE", "artifact must be an unlinked regular file", path=relative)
        if info.st_size > max_bytes:
            raise GraphError("SOURCE_LIMIT", "source exceeds byte limit", path=relative, limit=max_bytes)
        data = bytearray()
        while len(data) <= max_bytes:
            chunk = os.read(descriptor, min(64 * 1024, max_bytes + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > max_bytes:
            raise GraphError("SOURCE_LIMIT", "source exceeds byte limit", path=relative, limit=max_bytes)
        return bytes(data)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent)


def _json(root: RepoRoot, relative: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> tuple[dict[str, Any], bytes]:
    raw = _read_regular(root, relative, max_bytes=max_bytes)
    assert raw is not None
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GraphError("JOURNAL_CORRUPT" if "app-process-events/" in relative else "SCHEMA_UNSUPPORTED", "invalid JSON", path=relative) from exc
    if not isinstance(value, dict):
        raise GraphError("SCHEMA_UNSUPPORTED", "JSON root must be an object", path=relative)
    return value, raw


def _bytes(root: RepoRoot, relative: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    value = _read_regular(root, relative, max_bytes=max_bytes)
    assert value is not None
    return value


def _manifest(root: RepoRoot, *, require_maintainer: bool = False) -> dict[str, Any]:
    value, _ = _json(root, MANIFEST_PATH, max_bytes=256 * 1024)
    if value.get("schema") != "app-graph-source-manifest.v1":
        raise GraphError("SCHEMA_UNSUPPORTED", "unsupported graph source manifest")
    if require_maintainer and value.get("maintainer_enabled") is not True:
        raise GraphError("MAINTAINER_DISABLED", "repository has not opted in to graph maintenance")
    fixed = value.get("sources")
    if not isinstance(fixed, dict) or set(fixed) != {"workflow", "functional_map", "task_ledger", "artifact_catalog", "event_root"}:
        raise GraphError("SCHEMA_UNSUPPORTED", "manifest sources must contain only fixed contract paths")
    for key in ("workflow", "functional_map", "task_ledger", "artifact_catalog", "event_root"):
        if not isinstance(fixed[key], str) or not fixed[key]:
            raise GraphError("SCHEMA_UNSUPPORTED", "manifest source path is invalid", source=key)
        if key != "event_root":
            _read_regular(root, fixed[key], max_bytes=MAX_SOURCE_BYTES)
        else:
            try:
                directory = _open_directory(root, _parts(fixed[key]))
            except GraphError:
                directory = -1
            if directory >= 0:
                os.close(directory)
    roots, excludes = value.get("roots"), value.get("excludes")
    if (
        not isinstance(roots, list)
        or not roots
        or any(not isinstance(item, str) or not item for item in roots)
        or not isinstance(excludes, list)
        or any(not isinstance(item, str) or not item for item in excludes)
        or value.get("generated") != GENERATED_PATHS
        or value.get("limits") != FIXED_LIMITS
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", "manifest roots, excludes, generated paths, or limits drifted")
    for relative in [*roots, *excludes, *GENERATED_PATHS.values()]:
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise GraphError("PATH_ESCAPE", "manifest paths must remain below app_root", path=relative)
    return value


def _event_paths(root: RepoRoot, event_root: str) -> list[str]:
    try:
        directory = _open_directory(root, _parts(event_root))
    except GraphError:
        return []
    paths: list[str] = []
    stack: list[tuple[int, str]] = [(directory, event_root)]
    while stack:
        descriptor, prefix = stack.pop()
        try:
            names = sorted(os.listdir(descriptor))
            for name in names:
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                relative = f"{prefix}/{name}"
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=descriptor)
                    stack.append((child, relative))
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and name.endswith(".json"):
                    paths.append(relative)
                else:
                    raise GraphError("JOURNAL_CORRUPT", "journal contains an unexpected, linked, or non-JSON entry", path=relative)
        finally:
            os.close(descriptor)
    if len(paths) > MAX_EVENTS:
        raise GraphError("SOURCE_LIMIT", "event limit exceeded", limit=MAX_EVENTS)
    return sorted(paths)


def _sources(root: RepoRoot, manifest: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]], str]:
    configured = manifest["sources"]
    structured = {MANIFEST_PATH, configured["workflow"], configured["functional_map"], configured["task_ledger"], configured["artifact_catalog"]}
    tracked = manifest.get("tracked_paths", [])
    if not isinstance(tracked, list) or any(not isinstance(item, str) for item in tracked):
        raise GraphError("SCHEMA_UNSUPPORTED", "tracked_paths must be an array of fixed relative paths")
    paths = sorted(structured | set(tracked))
    paths += _event_paths(root, configured["event_root"])
    if len(paths) > MAX_SOURCES:
        raise GraphError("SOURCE_LIMIT", "source count exceeded", limit=MAX_SOURCES)
    total = 0
    values: dict[str, dict[str, Any]] = {}
    locators: list[dict[str, str]] = []
    for relative in paths:
        if relative in structured or relative.startswith(configured["event_root"] + "/"):
            value, raw = _json(root, relative)
            values[relative] = value
        else:
            raw = _bytes(root, relative)
        total += len(raw)
        if total > MAX_SOURCE_BYTES:
            raise GraphError("SOURCE_LIMIT", "aggregate source byte limit exceeded", limit=MAX_SOURCE_BYTES)
        locators.append({"path": relative, "digest": digest_bytes(raw)})
    snapshot = digest_bytes(canonical([[item["path"], item["digest"]] for item in locators]))
    return values, locators, snapshot


def _entity(ref: str, kind: str, path: str, digest: str, *, scope: str = "app") -> dict[str, Any]:
    return {"ref": ref, "kind": kind, "scope": scope, "source": {"path": path, "anchor": ref, "digest": digest}}


def _reject_forbidden_cycles(
    entities: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    registry: dict[str, Any],
) -> None:
    """Reject forbidden-edge SCCs with iterative Kosaraju traversal."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    reverse: dict[str, list[str]] = defaultdict(list)
    self_loops: set[str] = set()
    for edge in edges.values():
        if not edge.get("active", True) or registry[edge["kind"]].get("cycle") != "forbidden":
            continue
        left, right = edge["from_ref"], edge["to_ref"]
        adjacency[left].append(right)
        reverse[right].append(left)
        if left == right:
            self_loops.add(left)
    visited: set[str] = set()
    order: list[str] = []
    for start in sorted(entities):
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            stack.append((node, True))
            for target in sorted(adjacency[node], reverse=True):
                if target not in visited:
                    visited.add(target)
                    stack.append((target, False))
    assigned: set[str] = set()
    for start in reversed(order):
        if start in assigned:
            continue
        component: list[str] = []
        assigned.add(start)
        stack = [start]
        while stack:
            node = stack.pop()
            component.append(node)
            for target in reverse[node]:
                if target not in assigned:
                    assigned.add(target)
                    stack.append(target)
        if len(component) > 1 or component[0] in self_loops:
            raise GraphError("GRAPH_CYCLE", "forbidden graph cycle detected", refs=sorted(component)[:50])


def _build_indexes(root: RepoRoot, manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    values, locators, snapshot = _sources(root, manifest)
    source = manifest["sources"]
    workflow = values[source["workflow"]]
    fmap = values[source["functional_map"]]
    ledger = values[source["task_ledger"]]
    artifacts = values[source["artifact_catalog"]]
    if workflow.get("schema") != "app-workflow-definition.v2" or fmap.get("schema") != "app-functional-map.v2" or ledger.get("schema") != "app-task-ledger.v2" or artifacts.get("schema") != "app-artifact-catalog.v1":
        raise GraphError("SCHEMA_UNSUPPORTED", "compiler requires workflow v2, functional map v2, ledger v2, and artifact catalog v1")
    registry = workflow.get("graph", {}).get("edge_types", {})
    if not isinstance(registry, dict) or any(not isinstance(value, dict) for value in registry.values()):
        raise GraphError("SCHEMA_UNSUPPORTED", "workflow edge registry is invalid")
    entities: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    source_digest = {item["path"]: item["digest"] for item in locators}

    def add_entity(item: dict[str, Any], path: str, *, digest: str | None = None, artifact_path: str | None = None) -> None:
        ref, kind = item.get("ref"), item.get("kind")
        if not isinstance(ref, str) or not ref or not isinstance(kind, str) or not kind:
            raise GraphError("SCHEMA_UNSUPPORTED", "entity ref and kind are required", path=path)
        if ref in entities:
            raise GraphError("DUPLICATE_REF", "duplicate entity ref", ref=ref)
        entities[ref] = _entity(ref, kind, artifact_path or path, digest or source_digest[path], scope=str(item.get("scope", "app")))
        entities[ref]["active"] = item.get("active", True)

    def add_edge(item: dict[str, Any], path: str) -> None:
        ref, kind = item.get("ref"), item.get("kind")
        if not isinstance(ref, str) or not ref or ref in edges:
            raise GraphError("DUPLICATE_REF", "duplicate edge ref", ref=ref)
        if kind not in registry:
            raise GraphError("EDGE_KIND_UNKNOWN", "edge kind is not registered", ref=ref, kind=kind)
        edges[ref] = {"ref": ref, "kind": kind, "from_ref": item.get("from_ref"), "to_ref": item.get("to_ref"), "source_refs": [path], "condition_refs": sorted(item.get("condition_refs", [])), "active": item.get("active", True)}

    for item in fmap.get("entities", []):
        if not isinstance(item, dict):
            raise GraphError("SCHEMA_UNSUPPORTED", "functional entities must be objects")
        add_entity(item, source["functional_map"])
    for item in fmap.get("relations", []):
        if not isinstance(item, dict):
            raise GraphError("SCHEMA_UNSUPPORTED", "functional relations must be objects")
        add_edge(item, source["functional_map"])
    artifact_refs: dict[str, dict[str, Any]] = {}
    for artifact in artifacts.get("artifacts", []):
        if not isinstance(artifact, dict) or set(artifact) != {"ref", "kind", "path"}:
            raise GraphError("SCHEMA_UNSUPPORTED", "artifact catalog entries must contain only ref, kind, and path")
        ref, kind, artifact_path = artifact["ref"], artifact["kind"], artifact["path"]
        if kind not in {"code", "test", "evidence"} or not isinstance(ref, str) or not ref or not isinstance(artifact_path, str):
            raise GraphError("SCHEMA_UNSUPPORTED", "artifact catalog entry is invalid")
        if ref in artifact_refs:
            raise GraphError("DUPLICATE_REF", "duplicate artifact ref", ref=ref)
        raw = _bytes(root, artifact_path)
        artifact_refs[ref] = artifact
        add_entity({"ref": ref, "kind": kind}, source["artifact_catalog"], digest=digest_bytes(raw), artifact_path=artifact_path)
    for task in ledger.get("tasks", []):
        if not isinstance(task, dict) or not isinstance(task.get("task_id"), str):
            raise GraphError("SCHEMA_UNSUPPORTED", "ledger tasks require task_id")
        task_ref = task["task_id"]
        add_entity({"ref": task_ref, "kind": "task", "scope": task.get("wave_id", "app")}, source["task_ledger"])
        entities[task_ref]["active"] = task.get("status") != "superseded"
        functionality_refs = sorted(task.get("functionality_refs", []))
        if task.get("requirement_refs") and not functionality_refs:
            raise GraphError("DANGLING_REF", "active traced tasks require functionality_refs", task_ref=task_ref)
        for functionality in functionality_refs:
            add_edge({"ref": f"TRACE:{functionality}:{task_ref}", "kind": "decomposes_to", "from_ref": functionality, "to_ref": task_ref}, source["task_ledger"])
        code_refs = sorted(task.get("code_refs", [])); test_refs = sorted(task.get("test_refs", [])); evidence_refs = sorted(task.get("evidence_refs", []))
        for kind, refs in (("code", code_refs), ("test", test_refs), ("evidence", evidence_refs)):
            for ref in refs:
                if ref not in artifact_refs or artifact_refs[ref]["kind"] != kind:
                    raise GraphError("DANGLING_REF", "ledger artifact ref is missing or has the wrong kind", task_ref=task_ref, artifact_ref=ref, expected_kind=kind)
        for code in code_refs:
            add_edge({"ref": f"TRACE:{task_ref}:{code}", "kind": "implemented_by", "from_ref": task_ref, "to_ref": code}, source["task_ledger"])
            for test in test_refs:
                edge_ref = f"TRACE:{code}:{test}"
                if edge_ref not in edges:
                    add_edge({"ref": edge_ref, "kind": "verified_by", "from_ref": code, "to_ref": test}, source["task_ledger"])
        for test in test_refs:
            for evidence in evidence_refs:
                edge_ref = f"TRACE:{test}:{evidence}"
                if edge_ref not in edges:
                    add_edge({"ref": edge_ref, "kind": "evidenced_by", "from_ref": test, "to_ref": evidence}, source["task_ledger"])
    if len(entities) > MAX_ENTITIES or len(edges) > MAX_EDGES:
        raise GraphError("SOURCE_LIMIT", "graph entity or edge limit exceeded")
    for edge in edges.values():
        if edge["from_ref"] not in entities or edge["to_ref"] not in entities:
            raise GraphError("DANGLING_REF", "edge endpoint is missing", edge_ref=edge["ref"])
    _reject_forbidden_cycles(entities, edges, registry)

    events: list[dict[str, Any]] = []
    event_refs: set[str] = set()
    event_runs: dict[str, str] = {}
    event_prefix = source["event_root"] + "/"
    for relative in sorted(path for path in values if path.startswith(event_prefix)):
        event = values[relative]
        if event.get("schema") != "app-process-event.v1" or event.get("event_ref") != Path(relative).stem:
            raise GraphError("JOURNAL_CORRUPT", "event schema or filename/ref binding is invalid", path=relative)
        string_fields = ("run_ref", "event_ref", "event_kind", "stage", "status", "actor", "origin", "automation_status")
        array_fields = ("causal_refs", "trace_refs", "artifact_refs")
        if any(not isinstance(event.get(field), str) or not event[field] for field in string_fields):
            raise GraphError("JOURNAL_CORRUPT", "event string fields are incomplete", path=relative)
        if any(
            not isinstance(event.get(field), list)
            or len(event[field]) != len(set(event[field]))
            or any(not isinstance(item, str) or not item for item in event[field])
            for field in array_fields
        ):
            raise GraphError("JOURNAL_CORRUPT", "event reference arrays are invalid", path=relative)
        if event["origin"] not in {"native", "legacy-import"} or event["automation_status"] not in {"unavailable", "not_run", "passed", "failed"}:
            raise GraphError("JOURNAL_CORRUPT", "event origin or automation status is invalid", path=relative)
        if event["run_ref"] != Path(relative).parent.name:
            raise GraphError("JOURNAL_CORRUPT", "event run_ref disagrees with its journal directory", path=relative)
        ref = event["event_ref"]
        if ref in event_refs:
            raise GraphError("DUPLICATE_REF", "duplicate event ref", ref=ref)
        event_refs.add(ref)
        event_runs[ref] = event["run_ref"]
        events.append(event)
    links: list[dict[str, Any]] = []
    event_indegree = {ref: 0 for ref in event_refs}
    event_outgoing: dict[str, list[str]] = defaultdict(list)
    for event in events:
        for trace_ref in event["trace_refs"]:
            if trace_ref not in entities:
                raise GraphError("DANGLING_REF", "event trace ref is missing", event_ref=event["event_ref"], trace_ref=trace_ref)
        for cause in sorted(event.get("causal_refs", [])):
            if cause not in event_refs:
                raise GraphError("DANGLING_REF", "event cause is missing", event_ref=event["event_ref"], cause_ref=cause)
            if event_runs[cause] != event["run_ref"]:
                raise GraphError("JOURNAL_CORRUPT", "cross-run causal refs are forbidden", event_ref=event["event_ref"], cause_ref=cause)
            links.append({"ref": f"CAUSE:{cause}:{event['event_ref']}", "kind": "causes", "from_ref": cause, "to_ref": event["event_ref"]})
            event_indegree[event["event_ref"]] += 1
            event_outgoing[cause].append(event["event_ref"])
    if len(links) > MAX_PROCESS_LINKS:
        raise GraphError("SOURCE_LIMIT", "process link limit exceeded")
    event_queue = deque(sorted(ref for ref, degree in event_indegree.items() if degree == 0))
    visited_events = 0
    while event_queue:
        event_ref = event_queue.popleft()
        visited_events += 1
        for target in sorted(event_outgoing[event_ref]):
            event_indegree[target] -= 1
            if event_indegree[target] == 0:
                event_queue.append(target)
    if visited_events != len(events):
        raise GraphError("GRAPH_CYCLE", "process event journal contains a causal cycle")

    trace_body = {"schema": "app-traceability-index.v3", "app_id": fmap.get("app_id"), "source_snapshot_digest": snapshot, "generated_from": locators, "roots": sorted(ref for ref, e in entities.items() if e["kind"] == "spec"), "evidence_sinks": sorted(ref for ref, e in entities.items() if e["kind"] == "evidence"), "entities": sorted(entities.values(), key=lambda x: x["ref"]), "edges": sorted(edges.values(), key=lambda x: x["ref"]), "replacements": sorted(fmap.get("replacements", []), key=lambda x: str(x.get("old_ref", ""))), "findings": []}
    process_body = {"schema": "app-process-index.v2", "app_id": fmap.get("app_id"), "workflow_definition_ref": source["workflow"], "workflow_definition_digest": source_digest[source["workflow"]], "source_snapshot_digest": snapshot, "runs": sorted({event["run_ref"] for event in events}), "events": sorted(events, key=lambda x: x["event_ref"]), "links": sorted(links, key=lambda x: x["ref"]), "findings": []}
    content_ref = digest_bytes(canonical({"trace": trace_body, "process": process_body}))
    build_ref = "BUILD-" + content_ref.split(":", 1)[1][:24].upper()
    trace = {**trace_body, "build_ref": build_ref}
    process = {**process_body, "build_ref": build_ref, "journal_digest": digest_bytes(canonical(events))}
    build = {"schema": "app-index-build.v1", "build_ref": build_ref, "source_snapshot_digest": snapshot, "journal_digest": process["journal_digest"], "trace_index_digest": digest_bytes(canonical(trace)), "process_index_digest": digest_bytes(canonical(process)), "source_count": len(locators), "entity_count": len(entities), "edge_count": len(edges), "event_count": len(events)}
    context = {"schema": "app-context-index-result.v1", "status": "built", "build_ref": build_ref, "source_snapshot_digest": snapshot, "journal_digest": process["journal_digest"], "traceability_index_ref": TRACE_PATH, "process_index_ref": PROCESS_PATH, "build_receipt_ref": BUILD_PATH}
    return trace, process, build, context


def _atomic_write(root: RepoRoot, relative: str, payload: bytes) -> None:
    parts = _parts(relative)
    parent = _open_directory(root, parts[:-1], create=True)
    temporary = f".{parts[-1]}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    try:
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        current = _read_regular(root, relative, max_bytes=MAX_SOURCE_BYTES, missing=True)
        if current is not None:
            info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise GraphError("PATH_ESCAPE", "generated target is unsafe", path=relative)
        os.replace(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def graph_compile(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _safe_root(arguments.get("app_root"))
    try:
        manifest = _manifest(root, require_maintainer=True)
        lock = _open_directory(root, ("docs",))
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _graph_compile_locked(root, manifest, arguments)
        finally:
            os.close(lock)
    finally:
        root.close()


def _graph_compile_locked(root: RepoRoot, manifest: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    """Compile while holding the fixed output-directory CAS lock."""
    expected = arguments.get("expected_build_ref")
    current: dict[str, Any] | None = None
    current_raw = _read_regular(root, BUILD_PATH, max_bytes=256 * 1024, missing=True)
    if current_raw is not None:
        current, _ = _json(root, BUILD_PATH, max_bytes=256 * 1024)
    current_ref = current.get("build_ref") if current else None
    if expected is not None and expected != current_ref:
        raise GraphError("CAS_MISMATCH", "expected build does not match current build", expected=expected, actual=current_ref)
    trace, process, build, context = _build_indexes(root, manifest)
    _, stable_locators, stable_snapshot = _sources(root, manifest)
    if stable_snapshot != build["source_snapshot_digest"] or stable_locators != trace["generated_from"]:
        raise GraphError("SOURCE_DRIFT", "sources changed during compilation; retry with the current build")
    outputs = ((TRACE_PATH, trace), (PROCESS_PATH, process), (CONTEXT_PATH, context), (BUILD_PATH, build))
    byte_identical = current_ref == build["build_ref"] and current == build
    if byte_identical:
        for path, value in outputs:
            if _read_regular(root, path, max_bytes=MAX_SOURCE_BYTES, missing=True) != canonical(value):
                byte_identical = False
                break
    if byte_identical:
        return {**context, "schema": "app-graph-compile-result.v1", "status": "current", "no_op": True}
    for path, value in outputs:
        _atomic_write(root, path, canonical(value))
    return {**context, "schema": "app-graph-compile-result.v1", "no_op": False}


def process_record_event(arguments: dict[str, Any]) -> dict[str, Any]:
    root = _safe_root(arguments.get("app_root"))
    try:
        manifest = _manifest(root, require_maintainer=True)
        lock = _open_directory(root, ("docs",))
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _process_record_event_locked(root, manifest, arguments)
        finally:
            os.close(lock)
    finally:
        root.close()


def _process_record_event_locked(root: RepoRoot, manifest: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    """Append one event while serialized with compiler publication."""
    event = arguments.get("event")
    if not isinstance(event, dict) or event.get("schema") != "app-process-event.v1":
        raise GraphError("SCHEMA_UNSUPPORTED", "event must be app-process-event.v1")
    required_strings = ("run_ref", "event_ref", "event_kind", "stage", "status", "actor", "origin", "automation_status")
    required_arrays = ("causal_refs", "trace_refs", "artifact_refs")
    if any(not isinstance(event.get(field), str) or not event[field] for field in required_strings):
        raise GraphError("JOURNAL_CORRUPT", "event string fields are incomplete")
    if any(
        not isinstance(event.get(field), list)
        or len(event[field]) != len(set(event[field]))
        or any(not isinstance(item, str) or not item for item in event[field])
        for field in required_arrays
    ):
        raise GraphError("JOURNAL_CORRUPT", "event reference arrays are invalid")
    if event["origin"] not in {"native", "legacy-import"} or event["automation_status"] not in {"unavailable", "not_run", "passed", "failed"}:
        raise GraphError("JOURNAL_CORRUPT", "event origin or automation status is invalid")
    ref, run_ref = event.get("event_ref"), event.get("run_ref")
    if not all(isinstance(value, str) and value and "/" not in value and ".." not in value for value in (ref, run_ref)):
        raise GraphError("PATH_ESCAPE", "event_ref and run_ref must be safe path components")
    relative = f"{manifest['sources']['event_root']}/{run_ref}/{ref}.json"
    payload = canonical(event)
    current = _read_regular(root, relative, max_bytes=MAX_SOURCE_BYTES, missing=True)
    if current is not None:
        if current == payload:
            return {"schema": "app-process-event-result.v1", "status": "current", "event_ref": ref, "no_op": True}
        raise GraphError("EVENT_CONFLICT", "event key already exists with different payload", event_ref=ref)
    for cause in event["causal_refs"]:
        if cause == ref:
            raise GraphError("GRAPH_CYCLE", "an event cannot cause itself", event_ref=ref)
        cause_path = f"{manifest['sources']['event_root']}/{run_ref}/{cause}.json"
        try:
            cause_value, _ = _json(root, cause_path)
            if cause_value.get("run_ref") != run_ref:
                raise GraphError("JOURNAL_CORRUPT", "cross-run causal refs are forbidden", event_ref=ref, cause_ref=cause)
        except GraphError as exc:
            if exc.code == "ARTIFACT_MISSING":
                raise GraphError("DANGLING_REF", "event cause is missing", event_ref=ref, cause_ref=cause) from exc
            raise
    store = GraphStore.load({"app_root": str(root)})
    try:
        for trace_ref in event["trace_refs"]:
            if trace_ref not in store.entities:
                raise GraphError("DANGLING_REF", "event trace ref is missing", event_ref=ref, trace_ref=trace_ref)
    finally:
        store.close()
    parts = _parts(relative)
    parent = _open_directory(root, parts[:-1], create=True)
    temporary = f".{parts[-1]}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0: raise GraphError("JOURNAL_CORRUPT", "event write did not advance")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.link(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
    except FileExistsError:
        current = _read_regular(root, relative, max_bytes=MAX_SOURCE_BYTES, missing=True) or b""
        if current == payload:
            os.unlink(temporary, dir_fd=parent)
            os.close(parent)
            return {"schema": "app-process-event-result.v1", "status": "current", "event_ref": ref, "no_op": True}
        os.unlink(temporary, dir_fd=parent)
        os.close(parent)
        raise GraphError("EVENT_CONFLICT", "event key was concurrently recorded with different payload", event_ref=ref)
    os.unlink(temporary, dir_fd=parent)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return {"schema": "app-process-event-result.v1", "status": "recorded", "event_ref": ref, "event_digest": digest_bytes(payload), "no_op": False}


def _cursor_encode(snapshot: str, query: str, offset: int) -> str:
    body = {"s": snapshot, "q": query, "o": offset}
    packed = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    tag = hashlib.sha256(b"app-graph-cursor-v1\0" + packed).digest()[:12]
    return base64.urlsafe_b64encode(packed + tag).decode().rstrip("=")


def _cursor_decode(token: Any, snapshot: str, query: str) -> int:
    if token is None:
        return 0
    if not isinstance(token, str) or len(token) > 2048:
        raise GraphError("CURSOR_INVALID", "cursor must be an opaque bounded token")
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        packed, tag = raw[:-12], raw[-12:]
        if hashlib.sha256(b"app-graph-cursor-v1\0" + packed).digest()[:12] != tag:
            raise ValueError
        body = json.loads(packed)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise GraphError("CURSOR_INVALID", "cursor is malformed") from exc
    if body.get("q") != query:
        raise GraphError("CURSOR_INVALID", "cursor belongs to a different query")
    if body.get("s") != snapshot:
        raise GraphError("CURSOR_STALE", "cursor belongs to a stale graph snapshot")
    offset = body.get("o")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise GraphError("CURSOR_INVALID", "cursor offset is invalid")
    return offset


@dataclass(frozen=True)
class QueryBounds:
    limit: int
    depth: int
    cursor: str | None

    @classmethod
    def from_args(cls, arguments: dict[str, Any]) -> "QueryBounds":
        limit = arguments.get("limit", 50)
        depth = arguments.get("max_depth", 8)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE:
            raise GraphError("QUERY_LIMIT", "limit must be 1..200")
        if isinstance(depth, bool) or not isinstance(depth, int) or not 1 <= depth <= MAX_DEPTH:
            raise GraphError("QUERY_LIMIT", "max_depth must be 1..32")
        return cls(limit, depth, arguments.get("cursor"))


class GraphStore:
    """Verified build-bound read view with iterative traversals."""

    def __init__(self, root: RepoRoot, trace: dict[str, Any], process: dict[str, Any], build: dict[str, Any], workflow: dict[str, Any]):
        self.root, self.trace, self.process, self.build, self.workflow = root, trace, process, build, workflow
        self.entities = {item["ref"]: item for item in trace.get("entities", [])}
        self.edges = list(trace.get("edges", []))

    @classmethod
    def load(cls, arguments: dict[str, Any]) -> "GraphStore":
        root = _safe_root(arguments.get("app_root"))
        try:
            manifest = _manifest(root)
            trace, _ = _json(root, TRACE_PATH)
            process, _ = _json(root, PROCESS_PATH)
            build, _ = _json(root, BUILD_PATH, max_bytes=256 * 1024)
            workflow, _ = _json(root, manifest["sources"]["workflow"])
            if not (trace.get("schema") == "app-traceability-index.v3" and process.get("schema") == "app-process-index.v2" and build.get("schema") == "app-index-build.v1"):
                raise GraphError("SCHEMA_UNSUPPORTED", "active v3/v2 indexes are required")
            if len(trace.get("entities", [])) > MAX_ENTITIES or len(trace.get("edges", [])) > MAX_EDGES or len(process.get("events", [])) > MAX_EVENTS:
                raise GraphError("SOURCE_LIMIT", "index limits exceeded")
            if trace.get("build_ref") != build.get("build_ref") or process.get("build_ref") != build.get("build_ref"):
                raise GraphError("SOURCE_DRIFT", "index build refs disagree")
            if digest_bytes(canonical(trace)) != build.get("trace_index_digest") or digest_bytes(canonical(process)) != build.get("process_index_digest"):
                raise GraphError("SOURCE_DRIFT", "index digest disagrees with build receipt")
            _, locators, snapshot = _sources(root, manifest)
            if snapshot != build.get("source_snapshot_digest") or locators != trace.get("generated_from"):
                raise GraphError("SOURCE_DRIFT", "structured sources changed; compile is required")
            expected = arguments.get("expected_build_ref")
            if expected is not None and expected != build.get("build_ref"):
                raise GraphError("SOURCE_DRIFT", "expected build is stale", expected=expected, actual=build.get("build_ref"))
            return cls(root, trace, process, build, workflow)
        except Exception:
            root.close()
            raise

    def close(self) -> None:
        self.root.close()

    def _page(self, items: list[Any], bounds: QueryBounds, query: str) -> dict[str, Any]:
        offset = _cursor_decode(bounds.cursor, self.build["build_ref"], query)
        page = items[offset:offset + bounds.limit]
        next_offset = offset + len(page)
        return {"items": page, "truncated": next_offset < len(items), "next_cursor": _cursor_encode(self.build["build_ref"], query, next_offset) if next_offset < len(items) else None, "build_ref": self.build["build_ref"]}

    def dependency_slice(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        refs = arguments.get("refs", [])
        direction = arguments.get("direction", "dependencies")
        if not isinstance(refs, list) or direction not in {"dependencies", "dependents"}:
            raise GraphError("QUERY_INVALID", "refs and direction are invalid")
        registry = self.workflow.get("graph", {}).get("edge_types", {})
        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for edge in self.edges:
            meta = registry.get(edge.get("kind"), {})
            if meta.get("family") != "dependency" or not edge.get("active", True):
                continue
            left, right = edge["from_ref"], edge["to_ref"]
            adjacency[left if direction == "dependencies" else right].append((right if direction == "dependencies" else left, edge))
        seen = set(refs); queue = deque((ref, 0) for ref in refs); found: list[dict[str, Any]] = []
        while queue:
            current, depth = queue.popleft()
            if depth >= bounds.depth: continue
            for target, edge in sorted(adjacency.get(current, []), key=lambda x: (x[0], x[1]["ref"])):
                found.append({"from_ref": current, "to_ref": target, "edge_ref": edge["ref"], "depth": depth + 1})
                if target not in seen and registry[edge["kind"]].get("transitive", False):
                    seen.add(target); queue.append((target, depth + 1))
        return self._page(sorted(found, key=lambda x: (x["depth"], x["from_ref"], x["to_ref"])), bounds, f"dependency:{direction}:{json.dumps(sorted(refs))}:{bounds.depth}")

    def impact_analysis(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.dependency_slice({**arguments, "direction": "dependents"})

    def graph_trace(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        refs = set(arguments.get("refs", []))
        items = [edge for edge in self.edges if not refs or edge["from_ref"] in refs or edge["to_ref"] in refs]
        return self._page(sorted(items, key=lambda x: x["ref"]), bounds, "trace:" + json.dumps(sorted(refs)))

    def diagnostics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        findings = list(self.trace.get("findings", [])) + list(self.process.get("findings", []))
        return self._page(sorted(findings, key=lambda x: str(x.get("ref", ""))), bounds, "diagnostics")

    def topological_plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        tasks = sorted(ref for ref, item in self.entities.items() if item["kind"] == "task")
        prerequisites: dict[str, set[str]] = {ref: set() for ref in tasks}; dependents: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges:
            if edge["kind"] == "depends_on" and edge["from_ref"] in prerequisites and edge["to_ref"] in prerequisites:
                prerequisites[edge["from_ref"]].add(edge["to_ref"]); dependents[edge["to_ref"]].add(edge["from_ref"])
        queue = deque(sorted(ref for ref in tasks if not prerequisites[ref])); ordered: list[str] = []
        while queue:
            ref = queue.popleft(); ordered.append(ref)
            for target in sorted(dependents[ref]):
                prerequisites[target].discard(ref)
                if not prerequisites[target]: queue.append(target)
        if len(ordered) != len(tasks):
            raise GraphError("GRAPH_CYCLE", "task dependency graph contains a cycle")
        return self._page(ordered, bounds, "topological-plan")

    def workflow_state(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        return self._page(sorted(self.process.get("events", []), key=lambda x: x["event_ref"]), bounds, "workflow-state")

    def process_audit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments); findings: list[dict[str, Any]] = []
        run_ref = arguments.get("run_ref")
        if not isinstance(run_ref, str) or not run_ref:
            raise GraphError("QUERY_INVALID", "process_audit requires an exact run_ref")
        events = {item["event_ref"]: item for item in self.process.get("events", []) if item.get("run_ref") == run_ref}
        if not events:
            raise GraphError("QUERY_INVALID", "run_ref does not identify a compiled run", run_ref=run_ref)
        indegree = {ref: 0 for ref in events}; outgoing: dict[str, list[str]] = defaultdict(list)
        allowed_kinds = {"stage-handoff", "delegation", "task-result", "review", "remediation", "repo-handoff"}
        stages = set(self.workflow.get("stages", []))
        for event in events.values():
            if event.get("event_kind") not in allowed_kinds:
                findings.append(_finding("EVENT-KIND", "needs-graph", event["event_ref"]))
            if event.get("stage") not in stages:
                findings.append(_finding("STAGE-UNKNOWN", "needs-graph", event["event_ref"]))
            for trace_ref in event.get("trace_refs", []):
                if trace_ref not in self.entities:
                    findings.append(_finding("TRACE-REF", "needs-graph", event["event_ref"]))
            for cause in event.get("causal_refs", []):
                if cause not in events:
                    findings.append(_finding("PROCESS-DANGLING", "needs-graph", event["event_ref"]))
                else: indegree[event["event_ref"]] += 1; outgoing[cause].append(event["event_ref"])
            owner = self.workflow.get("stage_owners", {}).get(event.get("stage"))
            if owner and event.get("actor") not in owner:
                findings.append(_finding("STAGE-OWNERSHIP", "needs-plan", event["event_ref"]))
            if event.get("origin") != "legacy-import" and event.get("event_kind") == "stage-handoff":
                for cause in event.get("causal_refs", []):
                    parent = events.get(cause)
                    if not parent or parent.get("origin") == "legacy-import" or parent.get("event_kind") != "stage-handoff":
                        continue
                    expected_stage = self.workflow.get("routes", {}).get(parent.get("status"))
                    if expected_stage != event.get("stage"):
                        findings.append(_finding("ILLEGAL-TRANSITION", "needs-graph", event["event_ref"]))
            if event.get("origin") != "legacy-import":
                parents = [events.get(ref) for ref in event.get("causal_refs", [])]
                parent_kinds = {parent.get("event_kind") for parent in parents if parent}
                if event.get("event_kind") == "review" and not parent_kinds.intersection({"task-result", "remediation", "stage-handoff"}):
                    findings.append(_finding("REVIEW-LIFECYCLE", "needs-plan", event["event_ref"]))
                if event.get("event_kind") == "task-result" and not parent_kinds.intersection({"delegation", "stage-handoff"}):
                    findings.append(_finding("TASK-LIFECYCLE", "needs-plan", event["event_ref"]))
                if event.get("event_kind") == "remediation" and not parent_kinds.intersection({"stage-handoff", "review"}):
                    findings.append(_finding("REMEDIATION-LIFECYCLE", "needs-plan", event["event_ref"]))
                if event.get("event_kind") == "stage-handoff" and event.get("stage") == "app-dev" and event.get("status") == "implemented" and not parent_kinds.intersection({"review", "task-result"}):
                    findings.append(_finding("DEV-LIFECYCLE", "needs-plan", event["event_ref"]))
        queue = deque(sorted(ref for ref, degree in indegree.items() if degree == 0)); visited = 0
        while queue:
            ref = queue.popleft(); visited += 1
            for target in outgoing[ref]:
                indegree[target] -= 1
                if indegree[target] == 0: queue.append(target)
        if visited != len(events): findings.append(_finding("CAUSAL-CYCLE", "needs-graph", run_ref))
        candidates = [
            event for event in events.values()
            if event.get("status") == "audited"
            and not outgoing[event["event_ref"]]
        ]
        terminal = arguments.get("terminal") is True
        if terminal and not candidates:
            findings.append(_finding("TERMINAL-MISSING", "needs-plan", str(run_ref or "journal")))
        for candidate in candidates:
            if candidate.get("stage") != "app-analyze" or candidate.get("event_kind") != "stage-handoff":
                findings.append(_finding("TERMINAL-NOT-FINAL", "needs-plan", candidate["event_ref"]))
                continue
            event_path = f"{_manifest(self.root)['sources']['event_root']}/{candidate['run_ref']}/{candidate['event_ref']}.json"
            prior_locators = [item for item in self.trace.get("generated_from", []) if item.get("path") != event_path]
            prior_snapshot = digest_bytes(canonical([[item["path"], item["digest"]] for item in prior_locators]))
            prior_events = sorted(
                (event for event in events.values() if event["event_ref"] != candidate["event_ref"]),
                key=lambda item: item["event_ref"],
            )
            audit_build = candidate.get("build_ref")
            process_refs = candidate.get("process_audit_refs")
            trace_refs = candidate.get("trace_audit_refs")
            if (
                candidate.get("source_snapshot_digest") != prior_snapshot
                or candidate.get("journal_digest") != digest_bytes(canonical(prior_events))
                or not isinstance(audit_build, str)
                or not audit_build
                or not isinstance(process_refs, list)
                or not process_refs
                or not isinstance(trace_refs, list)
                or not trace_refs
                or any(not isinstance(ref, str) for ref in [*process_refs, *trace_refs])
                or any(audit_build not in ref for ref in [*process_refs, *trace_refs])
            ):
                findings.append(_finding("TERMINAL-SNAPSHOT", "needs-plan", candidate["event_ref"]))
        manifest = _manifest(self.root)
        ledger, _ = _json(self.root, manifest["sources"]["task_ledger"])
        open_remediation = sorted(
            task["task_id"] for task in ledger.get("tasks", [])
            if task.get("task_kind") == "remediation" and task.get("status") not in {"done", "superseded"}
        )
        if open_remediation:
            findings.extend(_finding("OPEN-REMEDIATION", "needs-plan", ref) for ref in open_remediation)
        complete = not findings and (not terminal or bool(candidates))
        result = {"schema": "app-process-audit-result.v1", "profile": "terminal" if terminal else "handoff", "run_ref": run_ref, "complete": complete, "build_ref": self.build["build_ref"], "journal_digest": self.build["journal_digest"], "candidate_final_event_refs": sorted(event["event_ref"] for event in candidates), "open_remediation_task_refs": open_remediation, "findings": findings, "route": "none" if complete else _route(findings)}
        return _bounded_audit(result, bounds, selector={"run_ref": run_ref, "terminal": terminal})

    def trace_audit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments); profile = arguments.get("profile", "semantic")
        if profile not in {"semantic", "planning", "convergence"}: raise GraphError("QUERY_INVALID", "unknown trace audit profile")
        adjacency: dict[tuple[str, str], set[str]] = defaultdict(set)
        for edge in self.edges:
            if edge.get("active", True):
                adjacency[(edge["from_ref"], edge["kind"])].add(edge["to_ref"])
        findings: list[dict[str, Any]] = []
        replaced = {item.get("old_ref") for item in self.trace.get("replacements", []) if isinstance(item, dict)}
        steps = [
            ("requirement", "defines", {"functionality", "behavior"}, "requirement-to-functionality"),
            ("functionality", "decomposes_to", {"task"}, "functionality-to-task"),
            ("task", "implemented_by", {"code"}, "task-to-code"),
            ("code", "verified_by", {"test"}, "code-to-test"),
            ("test", "evidenced_by", {"evidence"}, "test-to-evidence"),
        ]
        end_index = {"semantic": 1, "planning": 2, "convergence": 5}[profile]
        for req, entity in sorted(self.entities.items()):
            if entity["kind"] != "requirement" or entity.get("active") is False or req in replaced:
                continue
            decisions = sorted(source for (source, kind), targets in adjacency.items() if kind == "defines" and req in targets and self.entities.get(source, {}).get("kind") == "decision")
            specs = sorted(source for (source, kind), targets in adjacency.items() if kind == "defines" and any(decision in targets for decision in decisions) and self.entities.get(source, {}).get("kind") == "spec")
            missing_segment: str | None = None
            route = "needs-graph"
            if not decisions:
                missing_segment, route = "decision-to-requirement", "needs-spec"
            elif not specs:
                missing_segment, route = "spec-to-decision", "needs-research"
            states = {req}
            if missing_segment is None:
                for _, edge_kind, target_kinds, label in steps[:end_index]:
                    targets = {target for state in states for target in adjacency.get((state, edge_kind), set()) if self.entities.get(target, {}).get("kind") in target_kinds and self.entities.get(target, {}).get("active", True)}
                    if not targets:
                        missing_segment = label
                        route = "needs-graph" if profile == "semantic" else "needs-plan"
                        break
                    states = targets
            if missing_segment is not None:
                findings.append({"ref": f"TRACE-GAP:{req}:{missing_segment}", "kind": "trace-gap", "subject_ref": req, "missing_segment": missing_segment, "route": route})
        result = {"schema": "app-trace-audit-result.v1", "profile": profile, "complete": not findings, "truncated": False, "build_ref": self.build["build_ref"], "source_snapshot_digest": self.build["source_snapshot_digest"], "findings": findings, "route": "none" if not findings else _route(findings)}
        return _bounded_audit(result, bounds, selector={"profile": profile})


def _finding(kind: str, route: str, subject: str) -> dict[str, Any]:
    return {"ref": f"{kind}:{subject}", "kind": kind.lower(), "subject_ref": subject, "route": route}


def _route(findings: list[dict[str, Any]]) -> str:
    priority = ("blocked", "needs-research", "needs-spec", "needs-graph", "needs-plan")
    routes = {item.get("route") for item in findings}
    return next((item for item in priority if item in routes), "needs-plan")


def _bounded_audit(result: dict[str, Any], bounds: QueryBounds, *, selector: dict[str, Any]) -> dict[str, Any]:
    findings = result["findings"]
    query = "audit:" + json.dumps({"schema": result["schema"], **selector}, sort_keys=True, separators=(",", ":"))
    offset = _cursor_decode(bounds.cursor, result["build_ref"], query)
    page = findings[offset:offset + bounds.limit]
    next_offset = offset + len(page); truncated = next_offset < len(findings)
    result = {**result, "findings": page, "truncated": truncated}
    result["next_cursor"] = _cursor_encode(result["build_ref"], query, next_offset) if truncated else None
    if truncated: result["complete"] = False
    return result


READ_TOOLS = {"dependency_slice", "impact_analysis", "graph_trace", "graph_diagnostics", "topological_plan", "workflow_state", "process_audit", "trace_audit"}
MAINTAINER_TOOLS = {"graph_compile", "process_record_event"}


def execute_tool(name: str, arguments: dict[str, Any], *, maintainer: bool = False) -> dict[str, Any]:
    if not isinstance(arguments, dict): raise GraphError("QUERY_INVALID", "arguments must be an object")
    if maintainer:
        if name == "graph_compile": return graph_compile(arguments)
        if name == "process_record_event": return process_record_event(arguments)
        raise GraphError("METHOD_NOT_FOUND", "unknown maintainer tool")
    if name not in READ_TOOLS: raise GraphError("METHOD_NOT_FOUND", "unknown read-only tool")
    store = GraphStore.load(arguments)
    try:
        method = "diagnostics" if name == "graph_diagnostics" else name
        return getattr(store, method)(arguments)
    finally:
        store.close()
