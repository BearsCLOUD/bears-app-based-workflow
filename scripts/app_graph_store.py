"""Safe graph storage, immutable receipts, bounded cursors, and drift-aware caches."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
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
CURRENT_BUILD_PATH = "docs/app-index-current.v1.json"
TRACE_PATH = "docs/app-traceability-index.v3.json"
PROCESS_PATH = "docs/app-process-index.v3.json"
BUILD_ROOT = "docs/app-index-builds/v1"
AUDIT_ROOT = "docs/app-audit-receipts/v1"
CONTEXT_PATH = "docs/app-context-index-result.v1.json"
GENERATED_PATHS = {
    "trace_index": TRACE_PATH, "process_index": PROCESS_PATH,
    "current_build": CURRENT_BUILD_PATH, "build_receipt_root": BUILD_ROOT,
    "audit_receipt_root": AUDIT_ROOT, "context_result": CONTEXT_PATH,
}
FIXED_LIMITS = {
    "sources": MAX_SOURCES, "source_bytes": MAX_SOURCE_BYTES,
    "entities": MAX_ENTITIES, "edges": MAX_EDGES, "events": MAX_EVENTS,
    "process_links": MAX_PROCESS_LINKS,
}


class GraphError(RuntimeError):
    """Stable bounded failure returned by both MCP servers."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message); self.code = code; self.details = details


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass
class RepoRoot:
    path: Path
    fd: int
    device: int
    inode: int

    def close(self) -> None:
        if self.fd >= 0: os.close(self.fd); self.fd = -1

    def __str__(self) -> str: return str(self.path)


@dataclass(frozen=True)
class QueryBounds:
    limit: int
    depth: int
    cursor: str | None

    @classmethod
    def from_args(cls, arguments: dict[str, Any]) -> "QueryBounds":
        limit, depth = arguments.get("limit", 50), arguments.get("max_depth", 8)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE:
            raise GraphError("QUERY_LIMIT", "limit must be 1..200")
        if isinstance(depth, bool) or not isinstance(depth, int) or not 1 <= depth <= MAX_DEPTH:
            raise GraphError("QUERY_LIMIT", "max_depth must be 1..32")
        return cls(limit, depth, arguments.get("cursor"))


_HASH_CACHE: dict[tuple[int, int, int, int, int], str] = {}
_ROOT_FINGERPRINT: dict[tuple[int, int], tuple[tuple[str, tuple[int, int, int, int, int]], ...]] = {}
QUERY_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}


def safe_root(value: Any) -> RepoRoot:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise GraphError("INVALID_ROOT", "app_root must be a non-empty absolute path")
    supplied = Path(value)
    try:
        descriptor = os.open(supplied, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        info = os.fstat(descriptor)
    except OSError as exc: raise GraphError("INVALID_ROOT", "app_root must be a real non-symlink directory") from exc
    return RepoRoot(supplied.absolute(), descriptor, info.st_dev, info.st_ino)


def parts(relative: str) -> tuple[str, ...]:
    rel = Path(relative) if isinstance(relative, str) else Path("/")
    if not relative or rel.is_absolute() or ".." in rel.parts or any(p in {"", "."} for p in rel.parts):
        raise GraphError("PATH_ESCAPE", "path must remain below app_root", path=relative)
    return tuple(rel.parts)


def open_directory(root: RepoRoot, names: Iterable[str], *, create: bool = False) -> int:
    descriptor = os.dup(root.fd)
    try:
        for name in names:
            if create:
                try: os.mkdir(name, 0o700, dir_fd=descriptor)
                except FileExistsError: pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor); descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor); raise GraphError("PATH_ESCAPE", "directory path is missing, linked, or unsafe") from exc


def read_regular(root: RepoRoot, relative: str, *, max_bytes: int = MAX_SOURCE_BYTES, missing: bool = False) -> bytes | None:
    names = parts(relative); parent = open_directory(root, names[:-1]); descriptor = -1
    try:
        try: descriptor = os.open(names[-1], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            if missing: return None
            raise GraphError("ARTIFACT_MISSING", "required regular file is missing", path=relative)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise GraphError("PATH_ESCAPE", "artifact must be an unlinked regular file", path=relative)
        if info.st_size > max_bytes: raise GraphError("SOURCE_LIMIT", "source exceeds byte limit", path=relative)
        data = bytearray()
        while len(data) <= max_bytes:
            chunk = os.read(descriptor, min(65536, max_bytes + 1 - len(data)))
            if not chunk: break
            data.extend(chunk)
        if len(data) > max_bytes: raise GraphError("SOURCE_LIMIT", "source exceeds byte limit", path=relative)
        return bytes(data)
    finally:
        if descriptor >= 0: os.close(descriptor)
        os.close(parent)


def read_json(root: RepoRoot, relative: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> tuple[dict[str, Any], bytes]:
    raw = read_regular(root, relative, max_bytes=max_bytes); assert raw is not None
    try: value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc: raise GraphError("JOURNAL_CORRUPT", "invalid JSON", path=relative) from exc
    if not isinstance(value, dict): raise GraphError("SCHEMA_UNSUPPORTED", "JSON root must be an object", path=relative)
    return value, raw


def manifest(root: RepoRoot, *, require_maintainer: bool = False) -> dict[str, Any]:
    value, _ = read_json(root, MANIFEST_PATH, max_bytes=262144)
    if value.get("schema") != "app-graph-source-manifest.v1": raise GraphError("SCHEMA_UNSUPPORTED", "unsupported graph source manifest")
    if require_maintainer and value.get("maintainer_enabled") is not True: raise GraphError("MAINTAINER_DISABLED", "graph maintenance is disabled")
    if value.get("generated") != GENERATED_PATHS or value.get("limits") != FIXED_LIMITS: raise GraphError("SCHEMA_UNSUPPORTED", "manifest generated paths or limits drifted")
    required = {"workflow", "functional_map", "task_ledger", "artifact_catalog", "event_roots"}
    if set(value.get("sources", {})) != required: raise GraphError("SCHEMA_UNSUPPORTED", "manifest sources drifted")
    return value


def event_paths(root: RepoRoot, roots: list[str]) -> list[str]:
    paths: list[str] = []
    for event_root in roots:
        try: directory = open_directory(root, parts(event_root))
        except GraphError: continue
        stack = [(directory, event_root)]
        while stack:
            descriptor, prefix = stack.pop()
            try:
                for name in sorted(os.listdir(descriptor)):
                    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False); relative = f"{prefix}/{name}"
                    if stat.S_ISDIR(info.st_mode): stack.append((os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=descriptor), relative))
                    elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and name.endswith(".json"): paths.append(relative)
                    else: raise GraphError("JOURNAL_CORRUPT", "unexpected journal entry", path=relative)
            finally: os.close(descriptor)
    if len(paths) > MAX_EVENTS: raise GraphError("SOURCE_LIMIT", "event limit exceeded")
    return sorted(paths)


def source_snapshot(root: RepoRoot, config: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]], str]:
    structured = {MANIFEST_PATH, config["workflow"], config["functional_map"], config["task_ledger"], config["artifact_catalog"]}
    paths = sorted(structured | set(manifest(root).get("tracked_paths", []))) + event_paths(root, config["event_roots"])
    values: dict[str, dict[str, Any]] = {}; locators = []; fingerprint = []; total = 0
    for relative in paths:
        raw = read_regular(root, relative); assert raw is not None; total += len(raw)
        if total > MAX_SOURCE_BYTES: raise GraphError("SOURCE_LIMIT", "aggregate source byte limit exceeded")
        absolute = root.path / relative; info = absolute.stat(); key = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        digest = _HASH_CACHE.get(key)
        if digest is None: digest = _HASH_CACHE[key] = digest_bytes(raw)
        fingerprint.append((relative, key)); locators.append({"path": relative, "digest": digest})
        if relative in structured or any(relative.startswith(item + "/") for item in config["event_roots"]):
            try: values[relative] = json.loads(raw)
            except json.JSONDecodeError as exc: raise GraphError("JOURNAL_CORRUPT", "invalid JSON", path=relative) from exc
    root_key = (root.device, root.inode); current = tuple(fingerprint)
    if _ROOT_FINGERPRINT.get(root_key) not in (None, current):
        QUERY_CACHE.clear()
    _ROOT_FINGERPRINT[root_key] = current
    return values, locators, digest_bytes(canonical([[x["path"], x["digest"]] for x in locators]))


def cursor_encode(build: str, query: str, offset: int) -> str:
    packed = canonical({"s": build, "q": query, "o": offset}).rstrip(b"\n")
    return base64.urlsafe_b64encode(packed + hashlib.sha256(b"app-graph-cursor-v1\0" + packed).digest()[:12]).decode().rstrip("=")


def cursor_decode(token: Any, build: str, query: str) -> int:
    if token is None: return 0
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)); packed, tag = raw[:-12], raw[-12:]
        if hashlib.sha256(b"app-graph-cursor-v1\0" + packed).digest()[:12] != tag: raise ValueError
        body = json.loads(packed)
    except Exception as exc: raise GraphError("CURSOR_INVALID", "cursor is malformed") from exc
    if body.get("q") != query: raise GraphError("CURSOR_INVALID", "cursor belongs to a different query")
    if body.get("s") != build: raise GraphError("CURSOR_STALE", "cursor belongs to a stale build")
    if not isinstance(body.get("o"), int) or body["o"] < 0: raise GraphError("CURSOR_INVALID", "cursor offset is invalid")
    return body["o"]
