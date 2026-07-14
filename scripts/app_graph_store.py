"""Safe graph storage, immutable receipts, bounded cursors, and drift-aware caches."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import heapq
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import time
from typing import Any, Iterable

MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 16 * 1024
MAX_GIT_PROVENANCE_BYTES = 2 * 1024 * 1024
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
TRACE_PATH = "docs/app-traceability-index.v4.json"
PROCESS_PATH = "docs/app-process-index.v4.json"
BUILD_ROOT = "docs/app-index-builds/v1"
CONTEXT_PATH = "docs/app-context-index-result.v2.json"
GENERATED_PATHS = {
    "trace_index": TRACE_PATH, "process_index": PROCESS_PATH,
    "current_build": CURRENT_BUILD_PATH, "build_receipt_root": BUILD_ROOT,
    "context_result": CONTEXT_PATH,
}
SOURCE_PATHS = {
    "workflow": "contracts/app-workflow-definition.v3.json",
    "functional_map": "docs/app-functional-map.v4.json",
    "task_ledger": "docs/app-task-ledger.v3.json",
    "artifact_catalog": "docs/app-artifact-catalog.v2.json",
    "event_roots": ["docs/app-process-events/v3"],
}
FIXED_LIMITS = {
    "sources": MAX_SOURCES, "source_bytes": MAX_SOURCE_BYTES,
    "entities": MAX_ENTITIES, "edges": MAX_EDGES, "events": MAX_EVENTS,
    "process_links": MAX_PROCESS_LINKS,
}


def immutable_build_paths(build_ref: str) -> dict[str, str]:
    """Derive immutable artifact paths without expanding the receipt contract."""
    if not valid_build_ref(build_ref):
        raise GraphError("BUILD_RECEIPT_INVALID", "immutable build path needs a valid build ref")
    prefix = f"{BUILD_ROOT}/{build_ref}"
    return {
        "trace": f"{prefix}/app-traceability-index.v4.json",
        "process": f"{prefix}/app-process-index.v4.json",
        "context": f"{prefix}/app-context-index-result.v2.json",
    }


class GraphError(RuntimeError):
    """Stable bounded failure returned by both MCP servers."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message); self.code = code; self.details = details


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def valid_build_ref(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 30
        and value.startswith("BUILD-")
        and all(character in "0123456789ABCDEF" for character in value[6:])
    )


def valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


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
        limit, depth = arguments.get("limit", 10), arguments.get("max_depth", 8)
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


def validate_git_commit(root: RepoRoot, ref: str) -> None:
    """Require one exact commit object reachable from the repository HEAD."""
    if (
        not isinstance(ref, str)
        or len(ref) != 40
        or any(character not in "0123456789abcdef" for character in ref)
    ):
        raise GraphError("GIT_PROVENANCE_INVALID", "commit ref must be one full lowercase object name")
    try:
        result = subprocess.run(
            ["git", "-C", f"/proc/self/fd/{root.fd}", "cat-file", "-t", ref],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(root.fd,),
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "commit lookup failed") from exc
    if result.returncode != 0 or result.stdout != b"commit\n":
        raise GraphError("GIT_PROVENANCE_INVALID", "ref is not an exact commit object", commit_ref=ref)
    try:
        reachable = subprocess.run(
            ["git", "-C", f"/proc/self/fd/{root.fd}", "merge-base", "--is-ancestor", ref, "HEAD"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(root.fd,),
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "commit reachability lookup failed") from exc
    if reachable.returncode != 0:
        raise GraphError(
            "GIT_PROVENANCE_INVALID",
            "commit is not reachable from repository HEAD",
            commit_ref=ref,
        )


def validate_git_commit_range(root: RepoRoot, value: str) -> None:
    """Require one exact base..head range whose base is an ancestor of its head."""
    if not isinstance(value, str) or value.count("..") != 1:
        raise GraphError("GIT_PROVENANCE_INVALID", "commit range must be base..head")
    base, head = value.split("..")
    validate_git_commit(root, base)
    validate_git_commit(root, head)
    try:
        result = subprocess.run(
            ["git", "-C", f"/proc/self/fd/{root.fd}", "merge-base", "--is-ancestor", base, head],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(root.fd,),
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "commit ancestry lookup failed") from exc
    if result.returncode != 0:
        raise GraphError(
            "GIT_PROVENANCE_INVALID",
            "commit range base is not an ancestor of its head",
            commit_range=value,
        )


def git_is_ancestor(root: RepoRoot, ancestor: str, descendant: str) -> bool:
    """Return whether two reachable exact commits have ancestor ordering."""
    validate_git_commit(root, ancestor)
    validate_git_commit(root, descendant)
    try:
        result = subprocess.run(
            [
                "git", "-C", f"/proc/self/fd/{root.fd}", "merge-base",
                "--is-ancestor", ancestor, descendant,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(root.fd,),
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "commit ancestry lookup failed") from exc
    if result.returncode not in {0, 1}:
        raise GraphError("GIT_PROVENANCE_INVALID", "commit ancestry lookup failed")
    return result.returncode == 0


def _bounded_git_output(root: RepoRoot, arguments: list[str]) -> bytes:
    """Run one read-only Git query with a time and output bound."""
    try:
        process = subprocess.Popen(
            ["git", "-C", f"/proc/self/fd/{root.fd}", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(root.fd,),
        )
    except OSError as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "git provenance query failed") from exc
    assert process.stdout is not None
    descriptor = process.stdout.fileno()
    os.set_blocking(descriptor, False)
    selector = selectors.DefaultSelector()
    selector.register(descriptor, selectors.EVENT_READ)
    payload = bytearray()
    deadline = time.monotonic() + 5
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GraphError("GIT_PROVENANCE_INVALID", "git provenance query timed out")
            ready = selector.select(remaining)
            if not ready:
                raise GraphError("GIT_PROVENANCE_INVALID", "git provenance query timed out")
            for key, _ in ready:
                try:
                    chunk = os.read(key.fd, min(65_536, MAX_GIT_PROVENANCE_BYTES + 1 - len(payload)))
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fd)
                    continue
                payload.extend(chunk)
                if len(payload) > MAX_GIT_PROVENANCE_BYTES:
                    raise GraphError("GIT_PROVENANCE_INVALID", "git provenance output exceeds its bound")
        remaining = deadline - time.monotonic()
        if remaining <= 0 or process.wait(timeout=remaining) != 0:
            raise GraphError("GIT_PROVENANCE_INVALID", "git provenance query failed")
        return bytes(payload)
    except subprocess.TimeoutExpired as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "git provenance query timed out") from exc
    finally:
        selector.close()
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()


def git_commit_changed_paths(root: RepoRoot, ref: str) -> set[str]:
    """Return every repository path changed by one exact commit object."""
    validate_git_commit(root, ref)
    raw = _bounded_git_output(
        root,
        ["diff-tree", "--root", "-m", "--no-commit-id", "--name-only", "-r", "-z", ref],
    )
    if not raw:
        return set()
    if not raw.endswith(b"\0"):
        raise GraphError("GIT_PROVENANCE_INVALID", "git changed-path output is malformed")
    try:
        paths = {item.decode("utf-8") for item in raw[:-1].split(b"\0")}
    except UnicodeDecodeError as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "git changed paths must be UTF-8") from exc
    if any(not path or Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
        raise GraphError("GIT_PROVENANCE_INVALID", "git changed path escapes repository scope")
    return paths


def git_range_commits(root: RepoRoot, value: str) -> set[str]:
    """Return the complete commit set in one validated base..head range."""
    validate_git_commit_range(root, value)
    raw = _bounded_git_output(root, ["rev-list", "--topo-order", value])
    if not raw:
        return set()
    try:
        refs = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "git range output is malformed") from exc
    if any(
        len(ref) != 40 or any(character not in "0123456789abcdef" for character in ref)
        for ref in refs
    ) or len(refs) != len(set(refs)):
        raise GraphError("GIT_PROVENANCE_INVALID", "git range output is malformed")
    return set(refs)


def git_range_changed_paths(root: RepoRoot, value: str) -> set[str]:
    """Return the exact net path delta of one validated base..head range."""
    validate_git_commit_range(root, value)
    base, head = value.split("..")
    raw = _bounded_git_output(root, ["diff", "--name-only", "-z", base, head])
    if not raw:
        return set()
    if not raw.endswith(b"\0"):
        raise GraphError("GIT_PROVENANCE_INVALID", "git range path output is malformed")
    try:
        paths = {item.decode("utf-8") for item in raw[:-1].split(b"\0")}
    except UnicodeDecodeError as exc:
        raise GraphError("GIT_PROVENANCE_INVALID", "git range paths must be UTF-8") from exc
    if any(not path or Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
        raise GraphError("GIT_PROVENANCE_INVALID", "git range path escapes repository scope")
    return paths


def validate_git_commit_in_range(root: RepoRoot, commit_ref: str, value: str) -> None:
    """Require commit_ref to be included in the exact base..head ancestry range."""
    validate_git_commit_range(root, value)
    validate_git_commit(root, commit_ref)
    base, head = value.split("..")
    if commit_ref == base:
        raise GraphError("GIT_PROVENANCE_INVALID", "review range excludes its base commit", commit_ref=commit_ref)
    for ancestor, descendant in ((base, commit_ref), (commit_ref, head)):
        try:
            result = subprocess.run(
                ["git", "-C", f"/proc/self/fd/{root.fd}", "merge-base", "--is-ancestor", ancestor, descendant],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                pass_fds=(root.fd,),
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GraphError("GIT_PROVENANCE_INVALID", "review range coverage lookup failed") from exc
        if result.returncode != 0:
            raise GraphError(
                "GIT_PROVENANCE_INVALID",
                "task result commit is outside the review range",
                commit_ref=commit_ref,
                commit_range=value,
            )


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
    if value.get("sources") != SOURCE_PATHS: raise GraphError("SCHEMA_UNSUPPORTED", "manifest sources drifted")
    sources = value["sources"]
    for field in required - {"event_roots"}:
        if not isinstance(sources.get(field), str):
            raise GraphError("SCHEMA_UNSUPPORTED", "manifest source path is invalid", field=field)
        parts(sources[field])
    event_roots = sources.get("event_roots")
    if not isinstance(event_roots, list) or len(event_roots) != 1 or not isinstance(event_roots[0], str):
        raise GraphError("SCHEMA_UNSUPPORTED", "manifest needs one event root")
    parts(event_roots[0])
    tracked_paths = value.get("tracked_paths")
    if (
        not isinstance(tracked_paths, list)
        or any(not isinstance(path, str) for path in tracked_paths)
        or len(tracked_paths) != len(set(tracked_paths))
    ):
        raise GraphError("SCHEMA_UNSUPPORTED", "manifest tracked paths are invalid")
    for path in tracked_paths:
        parts(path)
        if (
            path in GENERATED_PATHS.values()
            or path.startswith(BUILD_ROOT + "/")
            or any(path.startswith(event_root + "/") for event_root in event_roots)
        ):
            raise GraphError("SCHEMA_UNSUPPORTED", "tracked path overlaps generated or journal state", path=path)
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
    if len(paths) > MAX_SOURCES:
        raise GraphError("SOURCE_LIMIT", "source limit exceeded")
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


def validate_current_pointer(pointer: Any) -> str:
    """Return the only receipt path allowed for one current-build pointer."""
    required = {"schema", "build_ref", "receipt_ref"}
    if not isinstance(pointer, dict) or set(pointer) != required:
        raise GraphError("BUILD_POINTER_INVALID", "current build pointer has an invalid shape")
    build_ref = pointer.get("build_ref")
    receipt_ref = pointer.get("receipt_ref")
    if (
        pointer.get("schema") != "app-index-current.v1"
        or not valid_build_ref(build_ref)
        or receipt_ref != f"{BUILD_ROOT}/{build_ref}.json"
    ):
        raise GraphError("BUILD_POINTER_INVALID", "current build pointer does not bind its receipt")
    return receipt_ref


def immutable_build_directory_exists(root: RepoRoot, build_ref: str) -> bool:
    """Return False only when a validated immutable build directory is absent."""
    if not valid_build_ref(build_ref):
        raise GraphError("BUILD_RECEIPT_INVALID", "immutable build directory needs a valid build ref")
    build_root = open_directory(root, parts(BUILD_ROOT)); descriptor = -1
    try:
        try:
            descriptor = os.open(
                build_ref,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=build_root,
            )
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise GraphError(
                "BUILD_RECEIPT_INVALID",
                "immutable build directory is linked or unsafe",
                build_ref=build_ref,
            ) from exc
        return True
    finally:
        if descriptor >= 0: os.close(descriptor)
        os.close(build_root)


def read_bound_indexes(
    root: RepoRoot,
    pointer: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read the immutable bundle selected by a pointer, with legacy bootstrap fallback."""
    receipt_ref = validate_current_pointer(pointer)
    build, _ = read_json(root, receipt_ref, max_bytes=262144)
    immutable = immutable_build_paths(pointer["build_ref"])
    if not immutable_build_directory_exists(root, pointer["build_ref"]):
        # Bootstrap only: pre-transaction publications had shared indexes. A new
        # publication materializes an immutable predecessor before switching.
        trace, _ = read_json(root, TRACE_PATH)
        process, _ = read_json(root, PROCESS_PATH)
    else:
        trace_raw = read_regular(root, immutable["trace"], missing=True)
        process_raw = read_regular(root, immutable["process"], missing=True)
        if trace_raw is None or process_raw is None:
            raise GraphError("BUILD_RECEIPT_INVALID", "immutable build bundle is incomplete")
        try:
            trace = json.loads(trace_raw)
            process = json.loads(process_raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise GraphError("BUILD_RECEIPT_INVALID", "immutable build index is invalid JSON") from exc
        if not isinstance(trace, dict) or not isinstance(process, dict):
            raise GraphError("BUILD_RECEIPT_INVALID", "immutable build indexes must be objects")
    validate_build_bundle(pointer, build, trace, process)
    return build, trace, process


def validate_build_bundle(
    pointer: dict[str, Any],
    build: Any,
    trace: Any,
    process: Any,
) -> None:
    """Check one pointer, receipt, and index bundle without consulting live sources."""
    validate_current_pointer(pointer)
    build_fields = {
        "schema", "build_ref", "source_snapshot_digest", "journal_digest",
        "trace_index_digest", "process_index_digest", "source_count",
        "entity_count", "edge_count", "event_count",
    }
    if not isinstance(build, dict) or set(build) != build_fields:
        raise GraphError("BUILD_RECEIPT_INVALID", "build receipt has an invalid shape")
    if build.get("schema") != "app-index-build.v1" or build.get("build_ref") != pointer["build_ref"]:
        raise GraphError("BUILD_RECEIPT_INVALID", "build receipt disagrees with the pointer")
    digest_fields = (
        "source_snapshot_digest", "journal_digest", "trace_index_digest",
        "process_index_digest",
    )
    if any(not valid_digest(build.get(field)) for field in digest_fields):
        raise GraphError("BUILD_RECEIPT_INVALID", "build receipt digests are invalid")
    count_fields = ("source_count", "entity_count", "edge_count", "event_count")
    if any(
        isinstance(build.get(field), bool)
        or not isinstance(build.get(field), int)
        or build[field] < 0
        for field in count_fields
    ):
        raise GraphError("BUILD_RECEIPT_INVALID", "build receipt counts are invalid")
    if not isinstance(trace, dict) or trace.get("schema") != "app-traceability-index.v4":
        raise GraphError("SCHEMA_UNSUPPORTED", "traceability index is unsupported")
    if not isinstance(process, dict) or process.get("schema") != "app-process-index.v4":
        raise GraphError("SCHEMA_UNSUPPORTED", "process index is unsupported")
    build_ref = build["build_ref"]
    if trace.get("build_ref") != build_ref or process.get("build_ref") != build_ref:
        raise GraphError("BUILD_RECEIPT_INVALID", "index build refs disagree with the receipt")
    if (
        trace.get("source_snapshot_digest") != build["source_snapshot_digest"]
        or process.get("source_snapshot_digest") != build["source_snapshot_digest"]
        or process.get("journal_digest") != build["journal_digest"]
    ):
        raise GraphError("BUILD_RECEIPT_INVALID", "index snapshot digests disagree with the receipt")
    if (
        digest_bytes(canonical(trace)) != build["trace_index_digest"]
        or digest_bytes(canonical(process)) != build["process_index_digest"]
    ):
        raise GraphError("BUILD_RECEIPT_INVALID", "index content digests disagree with the receipt")
    locators = trace.get("generated_from")
    entities = trace.get("entities")
    edges = trace.get("edges")
    events = process.get("events")
    if not all(isinstance(items, list) for items in (locators, entities, edges, events)):
        raise GraphError("BUILD_RECEIPT_INVALID", "index collections are invalid")
    locator_paths: set[str] = set()
    for locator in locators:
        if (
            not isinstance(locator, dict)
            or set(locator) != {"path", "digest"}
            or not isinstance(locator.get("path"), str)
            or not locator["path"]
            or locator["path"] in locator_paths
            or not valid_digest(locator.get("digest"))
        ):
            raise GraphError("BUILD_RECEIPT_INVALID", "index source locator is invalid")
        locator_paths.add(locator["path"])
    if digest_bytes(canonical([[item["path"], item["digest"]] for item in locators])) != build["source_snapshot_digest"]:
        raise GraphError("BUILD_RECEIPT_INVALID", "source locators disagree with the snapshot digest")
    if (
        len(locators) != build["source_count"]
        or len(entities) != build["entity_count"]
        or len(edges) != build["edge_count"]
        or len(events) != build["event_count"]
    ):
        raise GraphError("BUILD_RECEIPT_INVALID", "index counts disagree with the receipt")
    if digest_bytes(canonical(events)) != build["journal_digest"]:
        raise GraphError("BUILD_RECEIPT_INVALID", "process records disagree with the journal digest")
    trace_body = {key: value for key, value in trace.items() if key != "build_ref"}
    process_body = {key: value for key, value in process.items() if key != "build_ref"}
    derived_ref = "BUILD-" + digest_bytes(canonical({"trace": trace_body, "process": process_body}))[7:31].upper()
    if derived_ref != build_ref:
        raise GraphError("BUILD_RECEIPT_INVALID", "build ref is not derived from the bound indexes")


def causal_order(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a deterministic run-local causal order or fail closed."""
    records = list(events)
    by_ref: dict[str, dict[str, Any]] = {}
    for event in records:
        ref = event.get("event_ref") if isinstance(event, dict) else None
        if not isinstance(ref, str) or not ref or ref in by_ref:
            raise GraphError("JOURNAL_CORRUPT", "process event identity is missing or duplicated")
        by_ref[ref] = event
    indegree = {ref: 0 for ref in by_ref}
    outgoing: dict[str, list[str]] = {ref: [] for ref in by_ref}
    for ref, event in by_ref.items():
        causes = event.get("causal_refs")
        if (
            not isinstance(causes, list)
            or any(not isinstance(cause, str) or not cause for cause in causes)
            or len(causes) != len(set(causes))
        ):
            raise GraphError("JOURNAL_CORRUPT", "process event causes are invalid", event_ref=ref)
        for cause in causes:
            if cause not in by_ref:
                raise GraphError("DANGLING_REF", "event cause is missing", event_ref=ref, cause_ref=cause)
            if by_ref[cause].get("run_ref") != event.get("run_ref"):
                raise GraphError("JOURNAL_CORRUPT", "cross-run causes are forbidden", event_ref=ref)
            indegree[ref] += 1
            outgoing[cause].append(ref)
    ready = [
        (str(by_ref[ref].get("run_ref", "")), ref)
        for ref, degree in indegree.items() if degree == 0
    ]
    heapq.heapify(ready)
    ordered: list[dict[str, Any]] = []
    while ready:
        _, ref = heapq.heappop(ready)
        ordered.append(by_ref[ref])
        for target in sorted(outgoing[ref]):
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, (str(by_ref[target].get("run_ref", "")), target))
    if len(ordered) != len(records):
        raise GraphError("GRAPH_CYCLE", "process event journal contains a causal cycle")
    return ordered


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
