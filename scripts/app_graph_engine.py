"""Read-only graph loading and query engine for the bundled app-graph MCP server."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


MAX_FILE_BYTES = 2 * 1024 * 1024
TRACE_FILES = ("app-traceability-index.v2.json", "app-functional-graph.v1.json")
PROCESS_FILE = "app-process-index.v1.json"


class GraphError(RuntimeError):
    """One stable read or query failure safe to return through MCP."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise GraphError("QUERY_LIMIT", f"value must be an integer in {minimum}..{maximum}")
    return value


def _safe_root(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise GraphError("INVALID_ROOT", "app_root must be a non-empty absolute path")
    supplied = Path(value)
    if not supplied.is_absolute():
        raise GraphError("INVALID_ROOT", "app_root must be absolute")
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        raise GraphError("INVALID_ROOT", "app_root must resolve to a directory")
    if not ((root / "docs").is_dir() or (root / ".codex-plugin" / "plugin.json").is_file()):
        raise GraphError("INVALID_ROOT", "app_root has no app docs or plugin marker")
    return root


def _read_allowed(root: Path, relative: str, *, required: bool) -> dict[str, Any] | None:
    path = root / relative
    if not path.exists():
        if required:
            raise GraphError("ARTIFACT_MISSING", f"required artifact is missing: {relative}")
        return None
    if path.is_symlink() or not path.is_file():
        raise GraphError("INVALID_ROOT", f"artifact must be a regular non-symlink file: {relative}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GraphError("INVALID_ROOT", f"artifact escapes app_root: {relative}") from exc
    size = resolved.stat().st_size
    if size > MAX_FILE_BYTES:
        raise GraphError("QUERY_LIMIT", f"artifact exceeds {MAX_FILE_BYTES} bytes: {relative}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GraphError("SCHEMA_UNSUPPORTED", f"artifact is not readable JSON: {relative}") from exc
    if not isinstance(payload, dict):
        raise GraphError("SCHEMA_UNSUPPORTED", f"artifact root must be an object: {relative}")
    return payload


def _current_digest(root: Path, relative: Any) -> str:
    """Return a bounded source digest without following links or escaping root."""
    if not isinstance(relative, str) or not relative:
        raise GraphError("SCHEMA_UNSUPPORTED", "generated source path must be relative")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise GraphError("INVALID_ROOT", "generated source path must stay below app_root", path=relative)
    path = root
    for part in relative_path.parts:
        path /= part
        if path.is_symlink():
            raise GraphError("INVALID_ROOT", "generated source path cannot traverse a symlink", path=relative)
    if not path.exists():
        raise GraphError("SOURCE_DRIFT", "generated source is missing", path=relative)
    if path.is_symlink() or not path.is_file():
        raise GraphError("INVALID_ROOT", "generated source must be a regular non-symlink file", path=relative)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GraphError("INVALID_ROOT", "generated source escapes app_root", path=relative) from exc
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise GraphError("QUERY_LIMIT", "generated source exceeds the file budget", path=relative)
    try:
        return f"sha256:{hashlib.sha256(resolved.read_bytes()).hexdigest()}"
    except OSError as exc:
        raise GraphError("SOURCE_DRIFT", "generated source is unreadable", path=relative) from exc


def _verify_generated_sources(root: Path, trace: dict[str, Any]) -> None:
    """Fail closed when any indexed source content differs from its locator."""
    if trace.get("schema") != "app-traceability-index.v2":
        return
    locators = trace.get("generated_from")
    if not isinstance(locators, list) or not locators:
        raise GraphError("SCHEMA_UNSUPPORTED", "generated_from must be a non-empty array")
    seen: set[str] = set()
    for locator in locators:
        if not isinstance(locator, dict):
            raise GraphError("SCHEMA_UNSUPPORTED", "generated_from entries must be objects")
        relative = locator.get("path")
        if not isinstance(relative, str) or not relative:
            raise GraphError("SCHEMA_UNSUPPORTED", "generated source path must be a non-empty string")
        if relative in seen:
            raise GraphError("SCHEMA_UNSUPPORTED", "generated source paths must be unique", path=relative)
        seen.add(relative)
        expected = locator.get("digest")
        actual = _current_digest(root, relative)
        if expected != actual:
            raise GraphError("SOURCE_DRIFT", "generated source digest does not match the index", path=relative, expected=expected, actual=actual)
    canonical = json.dumps(
        sorted((locator["path"], locator["digest"]) for locator in locators),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    actual_snapshot = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    if trace.get("source_snapshot_digest") != actual_snapshot:
        raise GraphError(
            "SOURCE_DRIFT",
            "source snapshot digest does not match generated_from",
            expected=trace.get("source_snapshot_digest"),
            actual=actual_snapshot,
        )


def _normalize_v1(payload: dict[str, Any]) -> dict[str, Any]:
    app_id = str(payload.get("app_id", "unknown"))
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(ref: str, kind: str, scope: str) -> None:
        if ref and ref not in seen:
            seen.add(ref)
            entities.append({"ref": ref, "kind": kind, "scope": scope, "source": {"path": "docs/app-functional-graph.v1.json", "anchor": ref, "digest": "legacy"}})

    for item in payload.get("functions", []):
        if isinstance(item, dict):
            add(str(item.get("functionality_id", "")), "functionality", app_id)
    for item in payload.get("nodes", []):
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("node_id", ""))
        function_id = str(item.get("functionality_id", ""))
        ref = node_id if ":" in node_id else f"{function_id}:{node_id}" if function_id and node_id else node_id
        kind = str(item.get("kind", "behavior"))
        if kind not in {"behavior", "state", "api", "data", "integration", "error", "task", "code", "test", "evidence"}:
            kind = "behavior"
        add(ref, kind, function_id or app_id)
    edges = []
    for item in payload.get("edges", []):
        if isinstance(item, dict):
            edges.append(
                {
                    "ref": str(item.get("edge_id", "legacy-edge")),
                    "kind": str(item.get("kind", "depends_on")),
                    "from_ref": str(item.get("from_graph_node_ref", "")),
                    "to_ref": str(item.get("to_graph_node_ref", "")),
                    "source_refs": ["docs/app-functional-graph.v1.json"],
                    "condition_refs": list(item.get("condition_refs", [])),
                    "active": True,
                }
            )
    aliases = []
    replacements = []
    for item in payload.get("replacements", []):
        if not isinstance(item, dict):
            continue
        old_ref = str(item.get("old_ref", ""))
        new_refs = [str(ref) for ref in item.get("new_refs", [])]
        if old_ref and len(new_refs) == 1:
            aliases.append({"old_ref": old_ref, "current_ref": new_refs[0]})
        if old_ref:
            replacements.append({"old_ref": old_ref, "new_refs": new_refs, "source_refs": ["docs/app-functional-graph.v1.json"]})
    return {
        "schema": "app-functional-graph.v1-normalized",
        "app_id": app_id,
        "revision": payload.get("revision", 1),
        "source_snapshot_digest": "legacy-v1",
        "generated_from": [{"path": "docs/app-functional-graph.v1.json", "anchor": "", "digest": "legacy"}],
        "roots": [item["ref"] for item in entities if item["kind"] == "functionality"],
        "evidence_sinks": [item["ref"] for item in entities if item["kind"] == "evidence"],
        "entities": entities,
        "edges": edges,
        "aliases": aliases,
        "replacements": replacements,
        "findings": [],
    }


@dataclass(frozen=True)
class QueryBounds:
    """Normalized pagination and traversal limits."""

    limit: int
    depth: int
    cursor: int

    @classmethod
    def from_args(cls, arguments: dict[str, Any]) -> "QueryBounds":
        return cls(
            limit=_bounded_int(arguments.get("limit"), 100, 1, 500),
            depth=_bounded_int(arguments.get("max_depth"), 32, 1, 32),
            cursor=_bounded_int(arguments.get("cursor"), 0, 0, 1_000_000),
        )


class GraphStore:
    """One bounded snapshot of trace, process, and workflow artifacts."""

    def __init__(self, root: Path, trace: dict[str, Any], process: dict[str, Any] | None, workflow: dict[str, Any]) -> None:
        self.root = root
        self.trace = trace
        self.process = process
        self.workflow = workflow
        self.entities = {str(item.get("ref")): item for item in trace.get("entities", []) if isinstance(item, dict) and item.get("ref")}
        self.edges = [item for item in trace.get("edges", []) if isinstance(item, dict) and item.get("active", True)]
        self.edge_types = workflow.get("graph", {}).get("edge_types", {})

    @classmethod
    def load(cls, app_root: Any, expected_digest: Any = None) -> "GraphStore":
        root = _safe_root(app_root)
        trace = None
        for name in TRACE_FILES:
            trace = _read_allowed(root, f"docs/{name}", required=False)
            if trace is not None:
                if name.endswith("v1.json"):
                    trace = _normalize_v1(trace)
                break
        if trace is None:
            raise GraphError("ARTIFACT_MISSING", "no supported traceability index exists under docs/")
        schema = trace.get("schema")
        if schema not in {"app-traceability-index.v2", "app-functional-graph.v1-normalized"}:
            raise GraphError("SCHEMA_UNSUPPORTED", f"unsupported trace schema: {schema}")
        digest = trace.get("source_snapshot_digest")
        if trace.get("stale") is True:
            raise GraphError("INDEX_STALE", "traceability index is marked stale")
        _verify_generated_sources(root, trace)
        if expected_digest is not None and expected_digest != digest:
            raise GraphError("SOURCE_DRIFT", "expected source digest does not match the index", expected=expected_digest, actual=digest)
        process = _read_allowed(root, f"docs/{PROCESS_FILE}", required=False)
        workflow_root = Path(__file__).resolve().parents[1]
        workflow = _read_allowed(workflow_root, "contracts/app-workflow-definition.v1.json", required=True)
        assert workflow is not None
        if process is not None:
            if process.get("schema") != "app-process-index.v1":
                raise GraphError("SCHEMA_UNSUPPORTED", f"unsupported process schema: {process.get('schema')}")
            if process.get("source_snapshot_digest") != digest:
                raise GraphError(
                    "SOURCE_DRIFT",
                    "process and trace indexes use different source digests",
                    process=process.get("source_snapshot_digest"),
                    trace=digest,
                )
            workflow_digest = _current_digest(workflow_root, "contracts/app-workflow-definition.v1.json")
            if process.get("workflow_definition_digest") != workflow_digest:
                raise GraphError(
                    "SOURCE_DRIFT",
                    "process index uses a different workflow definition",
                    process=process.get("workflow_definition_digest"),
                    workflow=workflow_digest,
                )
        return cls(root, trace, process, workflow)

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "app-graph-query-result.v1",
            "app_id": self.trace.get("app_id"),
            "index_schema": self.trace.get("schema"),
            "revision": self.trace.get("revision"),
            "source_snapshot_digest": self.trace.get("source_snapshot_digest"),
            "entity_count": len(self.entities),
            "edge_count": len(self.edges),
            "process_index": self.process is not None,
        }

    def _require_refs(self, refs: Any) -> list[str]:
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref for ref in refs):
            raise GraphError("REF_NOT_FOUND", "refs must be a non-empty string array")
        missing = sorted(set(refs) - self.entities.keys())
        if missing:
            raise GraphError("REF_NOT_FOUND", "one or more refs are absent", refs=missing[:20])
        return sorted(set(refs))

    @staticmethod
    def _page(items: list[Any], bounds: QueryBounds) -> dict[str, Any]:
        page = items[bounds.cursor : bounds.cursor + bounds.limit]
        next_cursor = bounds.cursor + len(page)
        return {"items": page, "truncated": next_cursor < len(items), "next_cursor": next_cursor if next_cursor < len(items) else None}

    def _neighbors(self, direction: str, *, impact: bool = False, forbidden_cycles: bool = False) -> dict[str, list[tuple[str, str, bool]]]:
        neighbors: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
        for edge in self.edges:
            kind = str(edge.get("kind", ""))
            definition = self.edge_types.get(kind, {})
            if impact and not definition.get("impact", False):
                continue
            if forbidden_cycles and definition.get("cycle") != "forbidden":
                continue
            source, target = str(edge.get("from_ref", "")), str(edge.get("to_ref", ""))
            if not source or not target:
                continue
            step = (target, str(edge.get("ref", "")), bool(definition.get("transitive", False)))
            if direction == "dependencies":
                if kind in {"depends_on", "constrains"}:
                    neighbors[source].append(step)
            elif direction == "dependents":
                if kind in {"depends_on", "constrains"}:
                    neighbors[target].append((source, step[1], step[2]))
            elif impact and kind in {"depends_on", "constrains"}:
                neighbors[target].append((source, step[1], step[2]))
            else:
                neighbors[source].append(step)
        for ref in neighbors:
            neighbors[ref].sort()
        return neighbors

    def _walk(
        self,
        seeds: list[str],
        neighbors: dict[str, list[tuple[str, str, bool]]],
        bounds: QueryBounds,
        *,
        respect_transitive: bool = False,
    ) -> list[dict[str, Any]]:
        queue = deque((seed, 0, [seed], []) for seed in seeds)
        best_depth = {seed: 0 for seed in seeds}
        results: dict[str, dict[str, Any]] = {}
        while queue:
            current, depth, path, edge_path = queue.popleft()
            if depth >= bounds.depth:
                continue
            for target, edge_ref, transitive in neighbors.get(current, []):
                next_depth = depth + 1
                if target not in results:
                    results[target] = {"ref": target, "depth": next_depth, "path": path + [target], "edge_path": edge_path + [edge_ref]}
                if (transitive or not respect_transitive) and next_depth < best_depth.get(target, bounds.depth + 1):
                    best_depth[target] = next_depth
                    queue.append((target, next_depth, path + [target], edge_path + [edge_ref]))
        return sorted(results.values(), key=lambda item: (item["depth"], item["ref"]))

    def dependencies(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        direction = arguments.get("direction", "dependencies")
        if direction not in {"dependencies", "dependents"}:
            raise GraphError("QUERY_LIMIT", "direction must be dependencies or dependents")
        refs = self._require_refs(arguments.get("refs"))
        result = self._page(self._walk(refs, self._neighbors(direction), bounds), bounds)
        return {**self.snapshot(), "query": "dependencies", "direction": direction, **result}

    def impact(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        refs = self._require_refs(arguments.get("refs"))
        result = self._page(self._walk(refs, self._neighbors("impact", impact=True), bounds, respect_transitive=True), bounds)
        return {**self.snapshot(), "query": "impact", "seed_refs": refs, **result}

    def _strong_components(self) -> list[list[str]]:
        adjacency = self._neighbors("forward", forbidden_cycles=True)
        index = 0
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        components: list[list[str]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for target, _, _ in adjacency.get(node, []):
                if target not in indices:
                    visit(target)
                    lowlinks[node] = min(lowlinks[node], lowlinks[target])
                elif target in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[target])
            if lowlinks[node] == indices[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node:
                        break
                self_loop = any(target == node for target, _, _ in adjacency.get(node, []))
                if len(component) > 1 or self_loop:
                    components.append(sorted(component))

        for ref in sorted(self.entities):
            if ref not in indices:
                visit(ref)
        return sorted(components)

    def diagnostics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        missing = []
        registry_violations = []
        for edge in self.edges:
            kind = str(edge.get("kind", ""))
            definition = self.edge_types.get(kind)
            if definition is None:
                registry_violations.append({"edge_ref": edge.get("ref"), "reason": "undeclared-kind", "kind": kind})
            for field in ("from_ref", "to_ref"):
                ref = str(edge.get(field, ""))
                if ref and ref not in self.entities:
                    missing.append({"edge_ref": edge.get("ref"), "field": field, "ref": ref})
            if definition is not None:
                source = self.entities.get(str(edge.get("from_ref", "")), {})
                target = self.entities.get(str(edge.get("to_ref", "")), {})
                from_kinds, to_kinds = definition.get("from_kinds", []), definition.get("to_kinds", [])
                if from_kinds and source.get("kind") not in from_kinds:
                    registry_violations.append({"edge_ref": edge.get("ref"), "reason": "invalid-from-kind", "kind": source.get("kind")})
                if to_kinds and target.get("kind") not in to_kinds:
                    registry_violations.append({"edge_ref": edge.get("ref"), "reason": "invalid-to-kind", "kind": target.get("kind")})
        roots = [ref for ref in self.trace.get("roots", []) if ref in self.entities]
        reachable = {item["ref"] for item in self._walk(roots, self._neighbors("forward"), QueryBounds(500, 32, 0))} | set(roots)
        unreachable = sorted(set(self.entities) - reachable) if roots else []
        sinks = set(self.trace.get("evidence_sinks", []))
        trace_gaps = []
        forward = self._neighbors("forward")
        for ref in sorted(self.entities):
            if self.entities[ref].get("kind") == "requirement":
                reached = {item["ref"] for item in self._walk([ref], forward, QueryBounds(500, 32, 0))}
                if not reached.intersection(sinks):
                    trace_gaps.append(ref)
        diagnostics = {
            "missing_edge_refs": sorted(missing, key=lambda item: (str(item["edge_ref"]), item["field"])),
            "edge_registry_violations": sorted(registry_violations, key=lambda item: (str(item["edge_ref"]), item["reason"])),
            "forbidden_cycles": self._strong_components(),
            "unreachable_refs": unreachable,
            "trace_gap_refs": trace_gaps,
            "declared_findings": sorted(self.trace.get("findings", []), key=lambda item: str(item.get("ref", ""))),
        }
        flat = [{"kind": key, "value": value} for key, values in diagnostics.items() for value in values]
        result = self._page(flat, bounds)
        return {**self.snapshot(), "query": "diagnostics", **result}

    def plan(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        tasks = {ref for ref, entity in self.entities.items() if entity.get("kind") == "task"}
        prerequisites: dict[str, set[str]] = {ref: set() for ref in tasks}
        for edge in self.edges:
            if edge.get("kind") != "depends_on":
                continue
            dependent, prerequisite = str(edge.get("from_ref", "")), str(edge.get("to_ref", ""))
            if dependent in tasks and prerequisite in tasks:
                prerequisites[dependent].add(prerequisite)
        remaining = set(tasks)
        layers = []
        while remaining:
            layer = sorted(ref for ref in remaining if not prerequisites[ref].intersection(remaining))
            if not layer:
                break
            layers.append(layer)
            remaining.difference_update(layer)
        layer_items = [{"layer": index, "task_refs": refs} for index, refs in enumerate(layers)]
        blockers = []
        for finding in [*self.trace.get("findings", []), *(self.process or {}).get("findings", [])]:
            if isinstance(finding, dict) and finding.get("status") == "open":
                blockers.append({"kind": "open-finding", "ref": finding.get("ref"), "source_refs": finding.get("source_refs", [])})
        diagnostics = self.diagnostics({"limit": 500, "cursor": 0, "max_depth": bounds.depth})
        for item in diagnostics["items"]:
            if item["kind"] in {"missing_edge_refs", "edge_registry_violations", "forbidden_cycles", "trace_gap_refs"}:
                blockers.append({"kind": item["kind"], "value": item["value"]})
        blockers.sort(key=lambda item: json.dumps(item, sort_keys=True))
        result = self._page(layer_items, bounds)
        return {**self.snapshot(), "query": "plan", "blocked_by_cycle": sorted(remaining), "blockers": blockers, **result}

    def trace_paths(self, arguments: dict[str, Any]) -> dict[str, Any]:
        bounds = QueryBounds.from_args(arguments)
        refs = self._require_refs(arguments.get("refs"))
        target_refs = arguments.get("target_refs")
        targets = set(self._require_refs(target_refs)) if target_refs else set(self.trace.get("evidence_sinks", []))
        walked = self._walk(refs, self._neighbors("forward"), bounds)
        paths = [item for item in walked if item["ref"] in targets]
        result = self._page(paths, bounds)
        return {**self.snapshot(), "query": "trace", "target_refs": sorted(targets), **result}

    def workflow_state(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.process is None:
            raise GraphError("ARTIFACT_MISSING", f"docs/{PROCESS_FILE} is missing")
        expected = self.process.get("source_snapshot_digest")
        actual = self.trace.get("source_snapshot_digest")
        if expected != actual:
            raise GraphError("SOURCE_DRIFT", "process and trace indexes use different source digests", process=expected, trace=actual)
        return {
            **self.snapshot(),
            "query": "workflow-state",
            "workflow_definition": self.process.get("workflow_definition_ref"),
            "runs": sorted(self.process.get("runs", []), key=lambda item: str(item.get("ref", ""))),
            "events": sorted(self.process.get("events", []), key=lambda item: str(item.get("ref", ""))),
            "findings": sorted(self.process.get("findings", []), key=lambda item: str(item.get("ref", ""))),
        }


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Load one current snapshot and execute a bounded read-only tool."""
    store = GraphStore.load(arguments.get("app_root"), arguments.get("expected_digest"))
    handlers = {
        "graph_snapshot": lambda: store.snapshot(),
        "graph_dependencies": lambda: store.dependencies(arguments),
        "graph_impact": lambda: store.impact(arguments),
        "graph_diagnostics": lambda: store.diagnostics(arguments),
        "graph_plan": lambda: store.plan(arguments),
        "graph_trace": lambda: store.trace_paths(arguments),
        "workflow_state": lambda: store.workflow_state(arguments),
    }
    if name not in handlers:
        raise GraphError("SCHEMA_UNSUPPORTED", f"unknown tool: {name}")
    return handlers[name]()
