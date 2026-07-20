#!/usr/bin/env python3
"""SQLite-backed Bears app workflow MCP runtime and validation core."""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
from typing import Any, Callable, Sequence
import uuid

VERSION = "0.6.0"
SCHEMA_VERSION = "app-workflow-db.v1"
REGISTRY_VERSION = 1
DATABASE_RELATIVE = Path(".bears/app-workflow.sqlite3")
REGISTRY_RELATIVE = Path("state/bears-app-based-workflow/registry.sqlite3")
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
DEFAULT_DEPTH = 4
MAX_DEPTH = 16
GENESIS_DIGEST = "sha256:" + "0" * 64
SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18")
PHASES = (
    "app-constitution",
    "app-research",
    "app-specify",
    "app-functional-graph",
    "app-plan",
    "app-dev",
    "app-analyze",
)
RELATION_TYPES = (
    "depends_on",
    "constrains",
    "defines",
    "decomposes_to",
    "implemented_by",
    "evidenced_by",
    "replaces",
    "remediates",
)
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")
EXCLUDED_DIGEST_TABLES = {"request_log", "audit_attestations"}


class WorkflowError(RuntimeError):
    """A stable tool-facing workflow failure."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def require_text(value: Any, name: str, *, ref: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise WorkflowError("INVALID_ARGUMENT", f"{name} must be a non-empty string")
    if ref and not REF_RE.fullmatch(value):
        raise WorkflowError("INVALID_ARGUMENT", f"{name} is not a valid reference")
    return value


def require_digest(value: Any, name: str) -> str:
    text = require_text(value, name)
    if not DIGEST_RE.fullmatch(text):
        raise WorkflowError("INVALID_ARGUMENT", f"{name} must be a sha256 digest")
    return text


def require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise WorkflowError("INVALID_ARGUMENT", f"{name} must be between {minimum} and {maximum}")
    return value


def normalize_refs(value: Any, name: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise WorkflowError("INVALID_ARGUMENT", f"{name} must be an array")
    refs = [require_text(item, f"{name}[]", ref=True) for item in value]
    if nonempty and not refs:
        raise WorkflowError("INVALID_ARGUMENT", f"{name} must not be empty")
    if len(refs) != len(set(refs)):
        raise WorkflowError("INVALID_ARGUMENT", f"{name} contains duplicates")
    return sorted(refs)


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def registry_path() -> Path:
    raw = os.environ.get("BEARS_APP_WORKFLOW_STATE_DIR")
    if raw:
        return Path(raw).expanduser() / REGISTRY_RELATIVE.name
    return codex_home() / REGISTRY_RELATIVE


def apply_pragmas(connection: sqlite3.Connection, *, writable: bool) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    if writable:
        mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if str(mode).lower() != "delete":
            raise WorkflowError("WAL_FORBIDDEN", f"journal mode is {mode}")
        connection.execute("PRAGMA synchronous=FULL")
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    if foreign_keys != 1 or journal_mode != "delete" or synchronous != 2:
        raise WorkflowError("DATABASE_PRAGMA_DRIFT")


def connect_sqlite(path: Path, *, writable: bool) -> sqlite3.Connection:
    if writable:
        connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    else:
        uri = f"file:{path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    apply_pragmas(connection, writable=writable)
    return connection


REGISTRY_SQL = """
CREATE TABLE IF NOT EXISTS registry_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    project_ref TEXT PRIMARY KEY,
    root_path TEXT NOT NULL UNIQUE,
    registered_at TEXT NOT NULL,
    rebound_at TEXT
);
CREATE TABLE IF NOT EXISTS registry_requests (
    request_id TEXT PRIMARY KEY,
    project_ref TEXT NOT NULL,
    operation TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def open_registry(*, writable: bool = True) -> sqlite3.Connection:
    path = registry_path()
    if writable:
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect_sqlite(path, writable=writable)
    if writable:
        connection.executescript(REGISTRY_SQL)
        connection.execute(
            "INSERT OR IGNORE INTO registry_metadata(key,value) VALUES('schema_version',?)",
            (str(REGISTRY_VERSION),),
        )
    return connection


def validate_git_root(raw: Any) -> Path:
    text = require_text(raw, "project_root")
    path = Path(text)
    if not path.is_absolute():
        raise WorkflowError("PROJECT_ROOT_NOT_ABSOLUTE")
    current = Path(path.anchor)
    try:
        for part in path.parts[1:]:
            current = current / part
            if current.is_symlink():
                raise WorkflowError("PROJECT_ROOT_SYMLINK_FORBIDDEN")
        if not path.is_dir():
            raise WorkflowError("PROJECT_ROOT_INVALID")
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except OSError as exc:
        raise WorkflowError("PROJECT_ROOT_INVALID", str(exc)) from None
    except subprocess.TimeoutExpired:
        raise WorkflowError("PROJECT_ROOT_INVALID", "git root check timed out") from None
    if result.returncode != 0:
        raise WorkflowError("PROJECT_ROOT_NOT_GIT")
    reported = Path(result.stdout.strip())
    if reported != path:
        raise WorkflowError("PROJECT_ROOT_NOT_GIT_ROOT")
    return path


def schema_sql() -> str:
    contract = Path(__file__).resolve().parent.parent / "contracts" / "app-workflow-db-v1.sql"
    return contract.read_text(encoding="utf-8")


def initialize_project_database(path: Path, project_ref: str) -> None:
    created = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise WorkflowError("PROJECT_DATABASE_SYMLINK_FORBIDDEN")
    connection = connect_sqlite(path, writable=True)
    try:
        if created:
            connection.executescript(schema_sql())
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                "INSERT INTO metadata(key,value) VALUES(?,?)",
                (
                    ("schema_version", SCHEMA_VERSION),
                    ("project_ref", project_ref),
                    ("revision", "0"),
                ),
            )
            connection.commit()
        metadata = dict(connection.execute("SELECT key,value FROM metadata"))
        if metadata.get("schema_version") != SCHEMA_VERSION:
            raise WorkflowError("PROJECT_SCHEMA_UNSUPPORTED")
        if metadata.get("project_ref") != project_ref:
            raise WorkflowError("PROJECT_REF_MISMATCH")
    except Exception:
        connection.rollback()
        if created:
            with contextlib.suppress(OSError):
                path.unlink()
        raise
    finally:
        connection.close()


GITATTRIBUTES_RULE = ".bears/app-workflow.sqlite3 binary\n"
GITIGNORE_RULES = ".bears/app-workflow.sqlite3-journal\n.bears/app-workflow.sqlite3-wal\n.bears/app-workflow.sqlite3-shm\n.bears/app-workflow.sqlite3.lock\n"


def append_rules(path: Path, rules: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    additions = [line for line in rules.splitlines() if line and line not in existing.splitlines()]
    if not additions:
        return
    separator = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(existing + separator + "\n".join(additions) + "\n", encoding="utf-8")


def ensure_git_rules(root: Path) -> None:
    append_rules(root / ".gitattributes", GITATTRIBUTES_RULE)
    append_rules(root / ".gitignore", GITIGNORE_RULES)


def project_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in connection.execute("SELECT key,value FROM metadata")}


def resolve_project(project_ref: str) -> Path:
    require_text(project_ref, "project_ref", ref=True)
    try:
        with contextlib.closing(open_registry(writable=False)) as registry:
            row = registry.execute(
                "SELECT root_path FROM projects WHERE project_ref=?", (project_ref,)
            ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        raise WorkflowError("PROJECT_NOT_REGISTERED")
    root = Path(row["root_path"])
    validate_git_root(str(root))
    database = root / DATABASE_RELATIVE
    if database.is_symlink() or not database.is_file():
        raise WorkflowError("PROJECT_DATABASE_MISSING")
    return root


def open_project(project_ref: str, *, writable: bool = False) -> tuple[Path, sqlite3.Connection]:
    root = resolve_project(project_ref)
    connection = connect_sqlite(root / DATABASE_RELATIVE, writable=writable)
    metadata = project_metadata(connection)
    if metadata.get("project_ref") != project_ref:
        connection.close()
        raise WorkflowError("PROJECT_REF_MISMATCH")
    return root, connection


def list_project_tables(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def logical_lines(connection: sqlite3.Connection) -> list[str]:
    lines: list[str] = []
    for table in list_project_tables(connection):
        if table in EXCLUDED_DIGEST_TABLES:
            continue
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        for row in connection.execute(f"SELECT * FROM {table}"):
            record = {column: row[column] for column in columns}
            if table == "metadata" and record.get("key") == "revision":
                continue
            lines.append(f"{table}\t{canonical_json(record)}")
    return sorted(lines)


def logical_digest(connection: sqlite3.Connection) -> str:
    payload = ("\n".join(logical_lines(connection)) + "\n").encode("utf-8")
    return sha256_bytes(payload)


def current_revision(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
    if row is None:
        raise WorkflowError("PROJECT_METADATA_INVALID")
    return int(row[0])


def database_settings(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "foreign_keys": int(connection.execute("PRAGMA foreign_keys").fetchone()[0]),
        "journal_mode": str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
        "synchronous": int(connection.execute("PRAGMA synchronous").fetchone()[0]),
        "busy_timeout_ms": int(connection.execute("PRAGMA busy_timeout").fetchone()[0]),
    }


def register_backend(args: dict[str, Any]) -> dict[str, Any]:
    root = validate_git_root(args.get("project_root"))
    request_id = require_text(args.get("request_id"), "request_id", ref=True)
    expected_revision = require_int(args.get("expected_revision"), "expected_revision", 0, 2**63 - 1)
    expected_digest = require_digest(args.get("expected_logical_digest"), "expected_logical_digest")
    with contextlib.closing(open_registry()) as registry:
        registry.execute("BEGIN IMMEDIATE")
        try:
            row = registry.execute(
                "SELECT project_ref FROM projects WHERE root_path=?", (str(root),)
            ).fetchone()
            project_ref = row[0] if row else "PROJECT-" + uuid.uuid4().hex.upper()
            database = root / DATABASE_RELATIVE
            if database.exists():
                with contextlib.closing(connect_sqlite(database, writable=False)) as existing:
                    stored = project_metadata(existing).get("project_ref")
                    if stored:
                        project_ref = stored
            bound = registry.execute(
                "SELECT root_path FROM projects WHERE project_ref=?", (project_ref,)
            ).fetchone()
            if bound and bound["root_path"] != str(root):
                raise WorkflowError("PROJECT_REBIND_REQUIRED")
            initialize_project_database(database, project_ref)
            with contextlib.closing(connect_sqlite(database, writable=True)) as project:
                revision = current_revision(project)
                digest = logical_digest(project)
                allowed_digest = GENESIS_DIGEST if revision == 0 and expected_digest == GENESIS_DIGEST else digest
                if expected_revision != revision or expected_digest != allowed_digest:
                    raise WorkflowError("CAS_MISMATCH")
                prior = project.execute(
                    "SELECT operation,payload_digest,result_json FROM request_log WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                payload_digest = sha256_json(args)
                if prior:
                    if prior["operation"] != "project_register" or prior["payload_digest"] != payload_digest:
                        raise WorkflowError("REQUEST_ID_REUSED")
                    return json.loads(prior["result_json"])
                ensure_git_rules(root)
                registry.execute(
                    "INSERT INTO projects(project_ref,root_path,registered_at,rebound_at) VALUES(?,?,?,NULL) "
                    "ON CONFLICT(project_ref) DO UPDATE SET root_path=excluded.root_path,rebound_at=excluded.registered_at",
                    (project_ref, str(root), utc_now()),
                )
                result = {
                    "project_ref": project_ref,
                    "revision": revision,
                    "logical_digest": digest,
                    "database": DATABASE_RELATIVE.as_posix(),
                }
                project.execute("BEGIN IMMEDIATE")
                project.execute(
                    "INSERT INTO request_log VALUES(?,?,?,?,?,?,?)",
                    (request_id, "project_register", payload_digest, revision, digest, canonical_json(result), utc_now()),
                )
                project.commit()
            registry.commit()
            return result
        except Exception:
            registry.rollback()
            raise


def project_list_backend() -> dict[str, Any]:
    try:
        with contextlib.closing(open_registry(writable=False)) as registry:
            rows = list(
                registry.execute(
                    "SELECT project_ref,root_path,registered_at,rebound_at FROM projects ORDER BY project_ref"
                )
            )
    except sqlite3.OperationalError:
        rows = []
    projects: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            _, connection = open_project(item["project_ref"])
            with contextlib.closing(connection):
                item.update(
                    revision=current_revision(connection),
                    logical_digest=logical_digest(connection),
                    available=True,
                )
        except (WorkflowError, sqlite3.Error):
            item["available"] = False
        projects.append(item)
    return {"projects": projects}


def project_status_backend(project_ref: str) -> dict[str, Any]:
    root, connection = open_project(project_ref)
    with contextlib.closing(connection):
        revision = current_revision(connection)
        audit = connection.execute(
            "SELECT wave_id,revision,logical_digest,snapshot_digest,status FROM audit_attestations "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return {
            "project_ref": project_ref,
            "revision": revision,
            "logical_digest": logical_digest(connection),
            "database": DATABASE_RELATIVE.as_posix(),
            "settings": database_settings(connection),
            "audit": dict(audit) if audit else None,
        }


def require_local_file(root: Path, raw: Any, name: str) -> tuple[str, str]:
    relative = require_text(raw, name)
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != relative:
        raise WorkflowError("SOURCE_REF_INVALID", relative)
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise WorkflowError("SOURCE_REF_INVALID", relative) from None
    if path.is_symlink() or not resolved.is_file() or relative == DATABASE_RELATIVE.as_posix():
        raise WorkflowError("SOURCE_REF_INVALID", relative)
    return relative, digest_file(resolved)


def capture_files(
    root: Path, connection: sqlite3.Connection, refs: list[str], revision: int
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for ref in sorted(set(refs)):
        path, digest = require_local_file(root, ref, "source_ref")
        connection.execute(
            "INSERT INTO snapshot_files(path,sha256,captured_revision) VALUES(?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,captured_revision=excluded.captured_revision",
            (path, digest, revision),
        )
        records.append({"path": path, "sha256": digest})
    return records


def set_provenance(
    root: Path,
    connection: sqlite3.Connection,
    object_type: str,
    object_ref: str,
    refs: list[str],
    revision: int,
) -> None:
    if not refs:
        raise WorkflowError("SOURCE_REFS_REQUIRED", object_ref)
    records = capture_files(root, connection, refs, revision)
    connection.execute(
        "DELETE FROM provenance WHERE object_type=? AND object_ref=?", (object_type, object_ref)
    )
    for record in records:
        provenance_ref = "PROV-" + hashlib.sha256(
            f"{object_type}\0{object_ref}\0{record['path']}".encode("utf-8")
        ).hexdigest()[:32].upper()
        connection.execute(
            "INSERT INTO provenance VALUES(?,?,?,?,?,?)",
            (provenance_ref, object_type, object_ref, record["path"], record["sha256"], revision),
        )


def source_refs_for(
    connection: sqlite3.Connection, object_type: str, object_ref: str
) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT source_ref FROM provenance WHERE object_type=? AND object_ref=? ORDER BY source_ref",
            (object_type, object_ref),
        )
    ]


def check_cas(connection: sqlite3.Connection, args: dict[str, Any]) -> tuple[str, int, str, str]:
    request_id = require_text(args.get("request_id"), "request_id", ref=True)
    expected_revision = require_int(
        args.get("expected_revision"), "expected_revision", 0, 2**63 - 1
    )
    expected_digest = require_digest(args.get("expected_logical_digest"), "expected_logical_digest")
    payload_digest = sha256_json(args)
    return request_id, expected_revision, expected_digest, payload_digest


def prior_request(
    connection: sqlite3.Connection, request_id: str, operation: str, payload_digest: str
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT operation,payload_digest,result_json FROM request_log WHERE request_id=?", (request_id,)
    ).fetchone()
    if row is None:
        return None
    if row["operation"] != operation or row["payload_digest"] != payload_digest:
        raise WorkflowError("REQUEST_ID_REUSED")
    return json.loads(row["result_json"])


def require_wave_owner(
    connection: sqlite3.Connection, wave_id: str, owner_session_ref: str
) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM waves WHERE wave_id=?", (wave_id,)).fetchone()
    if row is None:
        raise WorkflowError("WAVE_NOT_FOUND")
    if row["owner_session_ref"] != owner_session_ref:
        raise WorkflowError("OWNER_SESSION_MISMATCH")
    return row


Mutation = Callable[[Path, sqlite3.Connection, int], dict[str, Any]]


def mutate_project(
    operation: str,
    args: dict[str, Any],
    callback: Mutation,
    *,
    wave_owned: bool = False,
) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    root, connection = open_project(project_ref, writable=True)
    with contextlib.closing(connection):
        request_id, expected_revision, expected_digest, payload_digest = check_cas(connection, args)
        connection.execute("BEGIN IMMEDIATE")
        try:
            prior = prior_request(connection, request_id, operation, payload_digest)
            if prior is not None:
                connection.rollback()
                return prior
            revision = current_revision(connection)
            digest = logical_digest(connection)
            if revision != expected_revision or digest != expected_digest:
                raise WorkflowError("CAS_MISMATCH")
            if wave_owned:
                wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
                owner = require_text(args.get("owner_session_ref"), "owner_session_ref", ref=True)
                require_wave_owner(connection, wave_id, owner)
            next_revision = revision + 1
            value = callback(root, connection, next_revision)
            connection.execute("UPDATE metadata SET value=? WHERE key='revision'", (str(next_revision),))
            connection.execute("UPDATE audit_attestations SET status='stale' WHERE status='active'")
            new_digest = logical_digest(connection)
            result = {
                **value,
                "project_ref": project_ref,
                "revision": next_revision,
                "logical_digest": new_digest,
            }
            connection.execute(
                "INSERT INTO request_log VALUES(?,?,?,?,?,?,?)",
                (
                    request_id,
                    operation,
                    payload_digest,
                    next_revision,
                    new_digest,
                    canonical_json(result),
                    utc_now(),
                ),
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise


def registry_request_result(
    connection: sqlite3.Connection, request_id: str, operation: str, payload_digest: str
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT operation,payload_digest,result_json FROM registry_requests WHERE request_id=?",
        (request_id,),
    ).fetchone()
    if row is None:
        return None
    if row["operation"] != operation or row["payload_digest"] != payload_digest:
        raise WorkflowError("REQUEST_ID_REUSED")
    return json.loads(row["result_json"])


def rebind_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    new_root = validate_git_root(args.get("project_root"))
    request_id = require_text(args.get("request_id"), "request_id", ref=True)
    expected_revision = require_int(args.get("expected_revision"), "expected_revision", 0, 2**63 - 1)
    expected_digest = require_digest(args.get("expected_logical_digest"), "expected_logical_digest")
    payload_digest = sha256_json(args)
    database = new_root / DATABASE_RELATIVE
    if not database.is_file() or database.is_symlink():
        raise WorkflowError("PROJECT_DATABASE_MISSING")
    with contextlib.closing(connect_sqlite(database, writable=True)) as project:
        metadata = project_metadata(project)
        if metadata.get("project_ref") != project_ref:
            raise WorkflowError("PROJECT_REF_MISMATCH")
        project.execute("BEGIN IMMEDIATE")
        try:
            prior = prior_request(project, request_id, "project_rebind", payload_digest)
            if prior is not None:
                project.rollback()
                return prior
            revision = current_revision(project)
            digest = logical_digest(project)
            if revision != expected_revision or digest != expected_digest:
                raise WorkflowError("CAS_MISMATCH")
            with contextlib.closing(open_registry()) as registry:
                registry.execute("BEGIN IMMEDIATE")
                try:
                    conflict = registry.execute(
                        "SELECT project_ref FROM projects WHERE root_path=?", (str(new_root),)
                    ).fetchone()
                    if conflict and conflict[0] != project_ref:
                        raise WorkflowError("PROJECT_ROOT_ALREADY_REGISTERED")
                    result = {
                        "project_ref": project_ref,
                        "revision": revision,
                        "logical_digest": digest,
                        "database": DATABASE_RELATIVE.as_posix(),
                    }
                    registry.execute(
                        "INSERT INTO projects VALUES(?,?,?,?) ON CONFLICT(project_ref) DO UPDATE SET "
                        "root_path=excluded.root_path,rebound_at=excluded.rebound_at",
                        (project_ref, str(new_root), utc_now(), utc_now()),
                    )
                    ensure_git_rules(new_root)
                    project.execute(
                        "INSERT INTO request_log VALUES(?,?,?,?,?,?,?)",
                        (request_id, "project_rebind", payload_digest, revision, digest, canonical_json(result), utc_now()),
                    )
                    project.commit()
                    registry.commit()
                    return result
                except Exception:
                    registry.rollback()
                    raise
        except Exception:
            project.rollback()
            raise


def unregister_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    request_id = require_text(args.get("request_id"), "request_id", ref=True)
    expected_revision = require_int(args.get("expected_revision"), "expected_revision", 0, 2**63 - 1)
    expected_digest = require_digest(args.get("expected_logical_digest"), "expected_logical_digest")
    payload_digest = sha256_json(args)
    with contextlib.closing(open_registry()) as registry:
        registry.execute("BEGIN IMMEDIATE")
        try:
            prior = registry_request_result(registry, request_id, "project_unregister", payload_digest)
            if prior is not None:
                registry.rollback()
                return prior
            row = registry.execute(
                "SELECT root_path FROM projects WHERE project_ref=?", (project_ref,)
            ).fetchone()
            if row is None:
                raise WorkflowError("PROJECT_NOT_REGISTERED")
            database = Path(row[0]) / DATABASE_RELATIVE
            with contextlib.closing(connect_sqlite(database, writable=False)) as project:
                metadata = project_metadata(project)
                revision = current_revision(project)
                digest = logical_digest(project)
                if metadata.get("project_ref") != project_ref:
                    raise WorkflowError("PROJECT_REF_MISMATCH")
                if revision != expected_revision or digest != expected_digest:
                    raise WorkflowError("CAS_MISMATCH")
            result = {
                "project_ref": project_ref,
                "revision": revision,
                "logical_digest": digest,
                "unregistered": True,
            }
            registry.execute("DELETE FROM projects WHERE project_ref=?", (project_ref,))
            registry.execute(
                "INSERT INTO registry_requests VALUES(?,?,?,?,?,?)",
                (request_id, project_ref, "project_unregister", payload_digest, canonical_json(result), utc_now()),
            )
            registry.commit()
            return result
        except Exception:
            registry.rollback()
            raise


def wave_initialize_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
        mode = require_text(args.get("mode"), "mode")
        owner = require_text(args.get("owner_session_ref"), "owner_session_ref", ref=True)
        if mode not in {"DIRECT", "DELEGATED"}:
            raise WorkflowError("INVALID_ARGUMENT", "mode must be DIRECT or DELEGATED")
        if connection.execute("SELECT 1 FROM waves WHERE wave_id=?", (wave_id,)).fetchone():
            raise WorkflowError("WAVE_ALREADY_EXISTS")
        connection.execute(
            "INSERT INTO waves VALUES(?,?,?,?,?,?,?)",
            (wave_id, mode, owner, "pending", PHASES[0], revision, revision),
        )
        connection.executemany(
            "INSERT INTO phases VALUES(?,?,?,?,?,?,?)",
            [(wave_id, phase, index + 1, "pending", None, None, revision) for index, phase in enumerate(PHASES)],
        )
        return {"wave_id": wave_id, "mode": mode, "owner_session_ref": owner}

    return mutate_project("wave_initialize", args, apply)


def phase_record_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
        phase = require_text(args.get("phase"), "phase")
        if phase not in PHASES:
            raise WorkflowError("PHASE_INVALID")
        record_ref = require_text(args.get("record_ref"), "record_ref", ref=True)
        outcome = require_text(args.get("outcome"), "outcome")
        if outcome not in {"completed", "skipped-current", "blocked", "pending"}:
            raise WorkflowError("PHASE_OUTCOME_INVALID")
        input_digest = require_digest(args.get("input_digest"), "input_digest")
        output_digest = require_digest(args.get("output_digest"), "output_digest")
        source_refs = normalize_refs(args.get("source_refs", []), "source_refs", nonempty=True)
        artifact_refs = normalize_refs(args.get("artifact_refs", []), "artifact_refs")
        capture_files(root, connection, sorted(set(source_refs + artifact_refs)), revision)
        previous = connection.execute(
            "SELECT record_ref FROM process_records WHERE wave_id=? AND phase=? AND active=1",
            (wave_id, phase),
        ).fetchone()
        if connection.execute("SELECT 1 FROM process_records WHERE record_ref=?", (record_ref,)).fetchone():
            raise WorkflowError("RECORD_REF_EXISTS")
        if previous:
            connection.execute("UPDATE process_records SET active=0 WHERE record_ref=?", (previous[0],))
        owner = require_text(args.get("owner_session_ref"), "owner_session_ref", ref=True)
        connection.execute(
            "INSERT INTO process_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record_ref,
                wave_id,
                phase,
                outcome,
                owner,
                input_digest,
                output_digest,
                canonical_json(artifact_refs),
                canonical_json(source_refs),
                previous[0] if previous else None,
                1,
                revision,
            ),
        )
        phase_status = "completed" if outcome in {"completed", "skipped-current"} else outcome
        connection.execute(
            "UPDATE phases SET status=?,process_record_ref=?,reopened_by=NULL,revision=? WHERE wave_id=? AND phase=?",
            (phase_status, record_ref, revision, wave_id, phase),
        )
        next_phase = None
        if phase_status == "completed":
            index = PHASES.index(phase)
            next_phase = PHASES[index + 1] if index + 1 < len(PHASES) else None
        connection.execute(
            "UPDATE waves SET status=?,current_phase=?,updated_revision=? WHERE wave_id=?",
            ("ready" if phase == "app-analyze" and phase_status == "completed" else phase_status, next_phase or phase, revision, wave_id),
        )
        return {"wave_id": wave_id, "phase": phase, "record_ref": record_ref, "supersedes_ref": previous[0] if previous else None}

    return mutate_project("phase_record", args, apply, wave_owned=True)


def graph_apply_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        operations = args.get("operations")
        if not isinstance(operations, list) or not operations:
            raise WorkflowError("INVALID_ARGUMENT", "operations must not be empty")
        changed: list[str] = []
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                raise WorkflowError("INVALID_ARGUMENT", f"operations[{index}] must be an object")
            action = require_text(operation.get("action"), "action")
            object_type = require_text(operation.get("object_type"), "object_type")
            if action not in {"upsert", "retire"} or object_type not in {"entity", "observation", "relation"}:
                raise WorkflowError("GRAPH_OPERATION_INVALID")
            ref_key = f"{object_type}_ref"
            object_ref = require_text(operation.get(ref_key), ref_key, ref=True)
            table = {"entity": "entities", "observation": "observations", "relation": "relations"}[object_type]
            existing = connection.execute(f"SELECT * FROM {table} WHERE {ref_key}=?", (object_ref,)).fetchone()
            refs = normalize_refs(operation.get("source_refs", []), "source_refs", nonempty=True)
            if action == "retire":
                if existing is None:
                    raise WorkflowError("GRAPH_OBJECT_NOT_FOUND", object_ref)
                replacement = operation.get("replacement_ref")
                if replacement is not None:
                    replacement = require_text(replacement, "replacement_ref", ref=True)
                connection.execute(
                    f"UPDATE {table} SET status='retired',replacement_ref=?,updated_revision=? WHERE {ref_key}=?",
                    (replacement, revision, object_ref),
                )
            elif object_type == "entity":
                kind = require_text(operation.get("kind"), "kind")
                name = require_text(operation.get("name"), "name")
                properties = operation.get("properties", {})
                if not isinstance(properties, dict):
                    raise WorkflowError("INVALID_ARGUMENT", "properties must be an object")
                if existing and existing["status"] == "retired":
                    raise WorkflowError("RETIRED_RECORD_IMMUTABLE")
                connection.execute(
                    "INSERT INTO entities VALUES(?,?,?,'active',NULL,?,?,?) "
                    "ON CONFLICT(entity_ref) DO UPDATE SET kind=excluded.kind,name=excluded.name,"
                    "properties_json=excluded.properties_json,updated_revision=excluded.updated_revision",
                    (object_ref, kind, name, canonical_json(properties), revision, revision),
                )
            elif object_type == "observation":
                entity_ref = require_text(operation.get("entity_ref"), "entity_ref", ref=True)
                content = require_text(operation.get("content"), "content")
                if existing and existing["status"] == "retired":
                    raise WorkflowError("RETIRED_RECORD_IMMUTABLE")
                connection.execute(
                    "INSERT INTO observations VALUES(?,?,?,'active',NULL,?,?) "
                    "ON CONFLICT(observation_ref) DO UPDATE SET entity_ref=excluded.entity_ref,"
                    "content=excluded.content,updated_revision=excluded.updated_revision",
                    (object_ref, entity_ref, content, revision, revision),
                )
            else:
                source = require_text(operation.get("from_entity_ref"), "from_entity_ref", ref=True)
                target = require_text(operation.get("to_entity_ref"), "to_entity_ref", ref=True)
                relation_type = require_text(operation.get("relation_type"), "relation_type")
                if relation_type not in RELATION_TYPES:
                    raise WorkflowError("RELATION_TYPE_CLOSED")
                if existing and existing["status"] == "retired":
                    raise WorkflowError("RETIRED_RECORD_IMMUTABLE")
                connection.execute(
                    "INSERT INTO relations VALUES(?,?,?,?,'active',NULL,?,?) "
                    "ON CONFLICT(relation_ref) DO UPDATE SET from_entity_ref=excluded.from_entity_ref,"
                    "to_entity_ref=excluded.to_entity_ref,relation_type=excluded.relation_type,"
                    "updated_revision=excluded.updated_revision",
                    (object_ref, source, target, relation_type, revision, revision),
                )
            set_provenance(root, connection, object_type, object_ref, refs, revision)
            changed.append(object_ref)
        return {"applied": len(changed), "object_refs": changed}

    return mutate_project("graph_apply", args, apply, wave_owned=True)


def detect_cycle(adjacency: dict[str, set[str]]) -> list[str]:
    active: list[str] = []
    done: set[str] = set()

    def visit(node: str) -> list[str]:
        if node in active:
            return active[active.index(node):] + [node]
        if node in done:
            return []
        active.append(node)
        for target in sorted(adjacency.get(node, set())):
            cycle = visit(target)
            if cycle:
                return cycle
        active.pop()
        done.add(node)
        return []

    for node in sorted(adjacency):
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def plan_replace_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
        owner = require_text(args.get("owner_session_ref"), "owner_session_ref", ref=True)
        tasks = args.get("tasks")
        if not isinstance(tasks, list):
            raise WorkflowError("INVALID_ARGUMENT", "tasks must be an array")
        parsed: list[tuple[str, str, int, list[str], list[str]]] = []
        ids: set[str] = set()
        sequences: set[int] = set()
        for item in tasks:
            if not isinstance(item, dict):
                raise WorkflowError("INVALID_ARGUMENT", "task must be an object")
            task_ref = require_text(item.get("task_ref"), "task_ref", ref=True)
            title = require_text(item.get("title"), "title")
            sequence = require_int(item.get("sequence"), "sequence", 1, max(1, len(tasks)))
            dependencies = normalize_refs(item.get("depends_on", []), "depends_on")
            sources = normalize_refs(item.get("source_refs", []), "source_refs", nonempty=True)
            if task_ref in ids or sequence in sequences:
                raise WorkflowError("PLAN_DUPLICATE")
            ids.add(task_ref)
            sequences.add(sequence)
            parsed.append((task_ref, title, sequence, dependencies, sources))
        if sequences and sequences != set(range(1, len(tasks) + 1)):
            raise WorkflowError("TASK_SEQUENCE_INVALID")
        adjacency = {task_ref: set(deps) for task_ref, _, _, deps, _ in parsed}
        if any(dep not in ids for deps in adjacency.values() for dep in deps):
            raise WorkflowError("TASK_DEPENDENCY_DANGLING")
        if detect_cycle(adjacency):
            raise WorkflowError("TASK_DEPENDENCY_CYCLE")
        active = {
            row["task_ref"]: row
            for row in connection.execute(
                "SELECT * FROM tasks WHERE wave_id=? AND record_status='active'", (wave_id,)
            )
        }
        for task_ref, row in active.items():
            if task_ref not in ids:
                if row["status"] == "done":
                    raise WorkflowError("COMPLETED_TASK_IMMUTABLE")
                connection.execute(
                    "UPDATE tasks SET record_status='retired',status='retired',updated_revision=? WHERE task_ref=?",
                    (revision, task_ref),
                )
        for task_ref, title, sequence, dependencies, sources in parsed:
            previous = active.get(task_ref)
            if previous and previous["status"] == "done" and (
                previous["title"] != title or previous["sequence"] != sequence
            ):
                raise WorkflowError("COMPLETED_TASK_IMMUTABLE")
            connection.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,'pending','active',NULL,?,NULL,NULL,'[]',?,?) "
                "ON CONFLICT(task_ref) DO UPDATE SET title=excluded.title,sequence=excluded.sequence,"
                "record_status='active',owner_session_ref=excluded.owner_session_ref,updated_revision=excluded.updated_revision",
                (task_ref, wave_id, title, sequence, owner, revision, revision),
            )
            connection.execute("DELETE FROM dependencies WHERE task_ref=?", (task_ref,))
            connection.executemany(
                "INSERT INTO dependencies VALUES(?,?,?)",
                [(task_ref, dependency, revision) for dependency in dependencies],
            )
            set_provenance(root, connection, "task", task_ref, sources, revision)
        connection.execute(
            "UPDATE phases SET status='completed',revision=? WHERE wave_id=? AND phase='app-plan'",
            (revision, wave_id),
        )
        connection.execute(
            "UPDATE waves SET status=?,current_phase='app-dev',updated_revision=? WHERE wave_id=?",
            ("no-work" if not parsed else "plan-ready", revision, wave_id),
        )
        return {"wave_id": wave_id, "task_refs": [item[0] for item in sorted(parsed, key=lambda item: item[2])]}

    return mutate_project("plan_replace", args, apply, wave_owned=True)


def digest_ref_set(root: Path, refs: list[str]) -> tuple[str, list[dict[str, str]]]:
    records = []
    for ref in sorted(refs):
        path, digest = require_local_file(root, ref, "change_ref")
        records.append({"path": path, "sha256": digest})
    return sha256_json(records), records


def task_record_change_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        task_ref = require_text(args.get("task_ref"), "task_ref", ref=True)
        worker_ref = require_text(args.get("worker_ref"), "worker_ref", ref=True)
        refs = normalize_refs(args.get("change_refs", []), "change_refs", nonempty=True)
        task = connection.execute("SELECT * FROM tasks WHERE task_ref=? AND record_status='active'", (task_ref,)).fetchone()
        if task is None:
            raise WorkflowError("TASK_NOT_FOUND")
        blocked = connection.execute(
            "SELECT d.depends_on_ref FROM dependencies d JOIN tasks t ON t.task_ref=d.depends_on_ref "
            "WHERE d.task_ref=? AND t.status<>'done'", (task_ref,)
        ).fetchall()
        earlier = connection.execute(
            "SELECT task_ref FROM tasks WHERE wave_id=? AND record_status='active' AND sequence<? AND status<>'done'",
            (task["wave_id"], task["sequence"]),
        ).fetchall()
        if blocked or earlier:
            raise WorkflowError("TASK_NOT_READY")
        change_digest, records = digest_ref_set(root, refs)
        capture_files(root, connection, refs, revision)
        connection.execute(
            "UPDATE tasks SET status='review_pending',worker_ref=?,change_digest=?,change_refs_json=?,updated_revision=? WHERE task_ref=?",
            (worker_ref, change_digest, canonical_json(refs), revision, task_ref),
        )
        return {"task_ref": task_ref, "change_digest": change_digest, "files": records}

    return mutate_project("task_record_change", args, apply, wave_owned=True)


def review_record_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        review_ref = require_text(args.get("review_ref"), "review_ref", ref=True)
        task_ref = require_text(args.get("task_ref"), "task_ref", ref=True)
        reviewer = require_text(args.get("reviewer_ref"), "reviewer_ref", ref=True)
        verdict = require_text(args.get("verdict"), "verdict")
        change_digest = require_digest(args.get("change_digest"), "change_digest")
        source_refs = normalize_refs(args.get("source_refs", []), "source_refs", nonempty=True)
        task = connection.execute("SELECT * FROM tasks WHERE task_ref=? AND record_status='active'", (task_ref,)).fetchone()
        if task is None or task["change_digest"] != change_digest:
            raise WorkflowError("REVIEW_CHANGE_DIGEST_MISMATCH")
        if task["status"] not in {"review_pending", "correction"}:
            raise WorkflowError("TASK_REVIEW_STATE_INVALID")
        if verdict not in {"approved", "changes_requested"}:
            raise WorkflowError("REVIEW_VERDICT_INVALID")
        capture_files(root, connection, source_refs, revision)
        connection.execute(
            "INSERT INTO reviews VALUES(?,?,?,?,?,?,?)",
            (review_ref, task_ref, reviewer, verdict, change_digest, canonical_json(source_refs), revision),
        )
        findings = args.get("findings", [])
        if not isinstance(findings, list):
            raise WorkflowError("INVALID_ARGUMENT", "findings must be an array")
        if verdict == "approved":
            if findings:
                raise WorkflowError("APPROVAL_WITH_FINDINGS")
            change_refs = json.loads(task["change_refs_json"])
            actual_digest, _ = digest_ref_set(root, change_refs)
            if actual_digest != change_digest:
                raise WorkflowError("REVIEW_CHANGE_DIGEST_MISMATCH")
            open_count = connection.execute(
                "SELECT COUNT(*) FROM findings f JOIN reviews r ON r.review_ref=f.review_ref "
                "WHERE r.task_ref=? AND f.status='open'",
                (task_ref,),
            ).fetchone()[0]
            open_corrections = connection.execute(
                "SELECT COUNT(*) FROM corrections WHERE task_ref=? AND status='open'", (task_ref,)
            ).fetchone()[0]
            if open_count or open_corrections:
                raise WorkflowError("OPEN_CORRECTIONS")
            connection.execute("UPDATE tasks SET status='done',updated_revision=? WHERE task_ref=?", (revision, task_ref))
        else:
            if not findings:
                raise WorkflowError("CHANGES_REQUESTED_WITHOUT_FINDINGS")
            for item in findings:
                if not isinstance(item, dict):
                    raise WorkflowError("INVALID_ARGUMENT", "finding must be an object")
                finding_ref = require_text(item.get("finding_ref"), "finding_ref", ref=True)
                kind = require_text(item.get("kind"), "kind")
                summary = require_text(item.get("summary"), "summary")
                refs = normalize_refs(item.get("source_refs", source_refs), "source_refs", nonempty=True)
                capture_files(root, connection, refs, revision)
                connection.execute(
                    "INSERT INTO findings VALUES(?,?,?,?,?,?,?,'open',?,?,?)",
                    (finding_ref, task["wave_id"], review_ref, None, kind, summary, "needs-plan", canonical_json(refs), revision, revision),
                )
            connection.execute("UPDATE tasks SET status='correction',updated_revision=? WHERE task_ref=?", (revision, task_ref))
        return {"review_ref": review_ref, "task_ref": task_ref, "verdict": verdict}

    return mutate_project("review_record", args, apply, wave_owned=True)


def correction_record_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        correction_ref = require_text(args.get("correction_ref"), "correction_ref", ref=True)
        finding_ref = require_text(args.get("finding_ref"), "finding_ref", ref=True)
        task_ref = require_text(args.get("task_ref"), "task_ref", ref=True)
        status = require_text(args.get("status"), "status")
        if status not in {"open", "resolved"}:
            raise WorkflowError("CORRECTION_STATUS_INVALID")
        evidence = normalize_refs(args.get("evidence_refs", []), "evidence_refs", nonempty=status == "resolved")
        sources = normalize_refs(args.get("source_refs", []), "source_refs", nonempty=True)
        finding = connection.execute("SELECT * FROM findings WHERE finding_ref=?", (finding_ref,)).fetchone()
        task = connection.execute("SELECT * FROM tasks WHERE task_ref=?", (task_ref,)).fetchone()
        if finding is None or task is None or finding["wave_id"] != task["wave_id"]:
            raise WorkflowError("CORRECTION_BINDING_INVALID")
        capture_files(root, connection, sorted(set(evidence + sources)), revision)
        connection.execute(
            "INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(correction_ref) DO UPDATE SET "
            "status=excluded.status,evidence_refs_json=excluded.evidence_refs_json,source_refs_json=excluded.source_refs_json,updated_revision=excluded.updated_revision",
            (correction_ref, finding_ref, task_ref, status, canonical_json(evidence), canonical_json(sources), revision, revision),
        )
        connection.execute(
            "UPDATE findings SET status=?,updated_revision=? WHERE finding_ref=?",
            ("resolved" if status == "resolved" else "open", revision, finding_ref),
        )
        connection.execute("UPDATE tasks SET status='review_pending',updated_revision=? WHERE task_ref=?", (revision, task_ref))
        return {"correction_ref": correction_ref, "finding_ref": finding_ref, "status": status}

    return mutate_project("correction_record", args, apply, wave_owned=True)


def analysis_record_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        analysis_ref = require_text(args.get("analysis_ref"), "analysis_ref", ref=True)
        wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
        sources = normalize_refs(args.get("source_refs", []), "source_refs", nonempty=True)
        findings = args.get("findings", [])
        if not isinstance(findings, list):
            raise WorkflowError("INVALID_ARGUMENT", "findings must be an array")
        capture_files(root, connection, sources, revision)
        if findings:
            routes: list[str] = []
            for item in findings:
                if not isinstance(item, dict):
                    raise WorkflowError("INVALID_ARGUMENT", "finding must be an object")
                finding_ref = require_text(item.get("finding_ref"), "finding_ref", ref=True)
                kind = require_text(item.get("kind"), "kind")
                summary = require_text(item.get("summary"), "summary")
                route = require_text(item.get("route"), "route")
                if route not in PHASES[:-1]:
                    raise WorkflowError("ANALYSIS_ROUTE_INVALID")
                refs = normalize_refs(item.get("source_refs", sources), "source_refs", nonempty=True)
                capture_files(root, connection, refs, revision)
                connection.execute(
                    "INSERT INTO findings VALUES(?,?,?,?,?,?,?,'open',?,?,?)",
                    (finding_ref, wave_id, None, analysis_ref, kind, summary, route, canonical_json(refs), revision, revision),
                )
                routes.append(route)
            route = min(routes, key=PHASES.index)
            status = "findings"
            route_index = PHASES.index(route)
            for phase in PHASES[route_index:]:
                connection.execute(
                    "UPDATE phases SET status='pending',reopened_by=?,revision=? WHERE wave_id=? AND phase=?",
                    (analysis_ref, revision, wave_id, phase),
                )
            connection.execute(
                "UPDATE waves SET status='pending',current_phase=?,updated_revision=? WHERE wave_id=?",
                (route, revision, wave_id),
            )
        else:
            open_findings = connection.execute(
                "SELECT COUNT(*) FROM findings WHERE wave_id=? AND status='open' AND analysis_ref IS NULL",
                (wave_id,),
            ).fetchone()[0]
            incomplete = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE wave_id=? AND record_status='active' AND status<>'done'",
                (wave_id,),
            ).fetchone()[0]
            if open_findings or incomplete:
                raise WorkflowError("ANALYSIS_NOT_CLEAN")
            connection.execute(
                "UPDATE findings SET status='resolved',updated_revision=? WHERE wave_id=? AND analysis_ref IS NOT NULL AND status='open'",
                (revision, wave_id),
            )
            route = None
            status = "ready"
            connection.execute(
                "UPDATE phases SET status='ready',reopened_by=NULL,revision=? WHERE wave_id=? AND phase='app-analyze'",
                (revision, wave_id),
            )
            connection.execute(
                "UPDATE waves SET status='ready',current_phase='app-analyze',updated_revision=? WHERE wave_id=?",
                (revision, wave_id),
            )
        connection.execute(
            "INSERT INTO analyses VALUES(?,?,?,?,?,?)",
            (analysis_ref, wave_id, status, route, canonical_json(sources), revision),
        )
        return {"analysis_ref": analysis_ref, "wave_id": wave_id, "status": status, "route": route}

    return mutate_project("analysis_record", args, apply, wave_owned=True)


def add_finding(findings: list[dict[str, str]], code: str, location: str, message: str | None = None) -> None:
    findings.append({"code": code, "location": location, "message": message or code.lower()})


def validation_result(
    root: Path, connection: sqlite3.Connection, wave_id: str
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    revision = current_revision(connection)
    digest = logical_digest(connection)
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        add_finding(findings, "DATABASE_INTEGRITY", "database")
    settings = database_settings(connection)
    if settings != {"foreign_keys": 1, "journal_mode": "delete", "synchronous": 2, "busy_timeout_ms": 5000}:
        add_finding(findings, "DATABASE_PRAGMA_DRIFT", "database.pragmas")
    database_path = root / DATABASE_RELATIVE
    for suffix in ("-wal", "-shm"):
        if Path(str(database_path) + suffix).exists():
            add_finding(findings, "WAL_FORBIDDEN", "database")
    metadata = project_metadata(connection)
    if metadata.get("schema_version") != SCHEMA_VERSION:
        add_finding(findings, "SCHEMA_VERSION", "metadata.schema_version")
    wave = connection.execute("SELECT * FROM waves WHERE wave_id=?", (wave_id,)).fetchone()
    if wave is None:
        add_finding(findings, "WAVE_NOT_FOUND", "waves")
    phases = list(connection.execute("SELECT * FROM phases WHERE wave_id=? ORDER BY ordinal", (wave_id,)))
    if [row["phase"] for row in phases] != list(PHASES):
        add_finding(findings, "PHASE_SET_INVALID", "phases")
    for phase in phases:
        active = list(
            connection.execute(
                "SELECT * FROM process_records WHERE wave_id=? AND phase=? AND active=1",
                (wave_id, phase["phase"]),
            )
        )
        if phase["status"] != "pending" and phase["process_record_ref"] is None:
            add_finding(findings, "PROCESS_CURRENT_INVALID", f"phases.{phase['phase']}")
        if phase["process_record_ref"] is not None and (
            len(active) != 1 or active[0]["record_ref"] != phase["process_record_ref"]
        ):
            add_finding(findings, "PROCESS_CURRENT_INVALID", f"phases.{phase['phase']}")
        if wave and any(row["owner_session_ref"] != wave["owner_session_ref"] for row in active):
            add_finding(findings, "OWNER_DRIFT", f"phases.{phase['phase']}")
    graph_specs = (
        ("entity", "entities", "entity_ref"),
        ("observation", "observations", "observation_ref"),
        ("relation", "relations", "relation_ref"),
    )
    for object_type, table, key in graph_specs:
        for row in connection.execute(f"SELECT {key},status,replacement_ref FROM {table}"):
            count = connection.execute(
                "SELECT COUNT(*) FROM provenance WHERE object_type=? AND object_ref=?",
                (object_type, row[key]),
            ).fetchone()[0]
            if count == 0:
                add_finding(findings, "SOURCE_REFS_MISSING", f"{table}.{row[key]}")
            if row["status"] == "retired" and row["replacement_ref"] == row[key]:
                add_finding(findings, "REPLACEMENT_SELF", f"{table}.{row[key]}")
    graph_adjacency: dict[str, set[str]] = {}
    for row in connection.execute(
        "SELECT from_entity_ref,to_entity_ref FROM relations WHERE status='active' AND relation_type='depends_on'"
    ):
        graph_adjacency.setdefault(row["from_entity_ref"], set()).add(row["to_entity_ref"])
    graph_cycle = detect_cycle(graph_adjacency)
    if graph_cycle:
        add_finding(findings, "GRAPH_CYCLE", "relations.depends_on", canonical_json(graph_cycle))
    tasks = list(
        connection.execute(
            "SELECT * FROM tasks WHERE wave_id=? AND record_status='active' ORDER BY sequence", (wave_id,)
        )
    )
    if tasks and [row["sequence"] for row in tasks] != list(range(1, len(tasks) + 1)):
        add_finding(findings, "TASK_SEQUENCE_INVALID", "tasks")
    task_ids = {row["task_ref"] for row in tasks}
    task_adjacency: dict[str, set[str]] = {task_ref: set() for task_ref in task_ids}
    for row in connection.execute(
        "SELECT d.task_ref,d.depends_on_ref FROM dependencies d JOIN tasks t ON t.task_ref=d.task_ref WHERE t.wave_id=? AND t.record_status='active'",
        (wave_id,),
    ):
        if row["depends_on_ref"] not in task_ids:
            add_finding(findings, "TASK_DEPENDENCY_DANGLING", f"tasks.{row['task_ref']}")
        task_adjacency.setdefault(row["task_ref"], set()).add(row["depends_on_ref"])
    task_cycle = detect_cycle(task_adjacency)
    if task_cycle:
        add_finding(findings, "TASK_CYCLE", "dependencies", canonical_json(task_cycle))
    done_seen = True
    for task in tasks:
        if wave and task["owner_session_ref"] != wave["owner_session_ref"]:
            add_finding(findings, "OWNER_DRIFT", f"tasks.{task['task_ref']}")
        if task["change_digest"]:
            try:
                actual_change_digest, _ = digest_ref_set(root, json.loads(task["change_refs_json"]))
            except (WorkflowError, json.JSONDecodeError):
                add_finding(findings, "TASK_CHANGE_REFS_INVALID", f"tasks.{task['task_ref']}")
            else:
                if actual_change_digest != task["change_digest"]:
                    add_finding(findings, "TASK_CHANGE_DIGEST_DRIFT", f"tasks.{task['task_ref']}")
        if task["status"] == "done":
            review = connection.execute(
                "SELECT * FROM reviews WHERE task_ref=? ORDER BY created_revision DESC,rowid DESC LIMIT 1",
                (task["task_ref"],),
            ).fetchone()
            if review is None or review["verdict"] != "approved" or review["change_digest"] != task["change_digest"]:
                add_finding(findings, "REVIEW_MISSING", f"tasks.{task['task_ref']}")
            open_corrections = connection.execute(
                "SELECT COUNT(*) FROM corrections WHERE task_ref=? AND status='open'", (task["task_ref"],)
            ).fetchone()[0]
            if open_corrections:
                add_finding(findings, "CORRECTION_OPEN", f"tasks.{task['task_ref']}")
            if not done_seen:
                add_finding(findings, "TASK_SEQUENCE", f"tasks.{task['task_ref']}")
        else:
            done_seen = False
    open_findings = connection.execute(
        "SELECT COUNT(*) FROM findings WHERE wave_id=? AND status='open'", (wave_id,)
    ).fetchone()[0]
    if open_findings:
        add_finding(findings, "FINDINGS_OPEN", "findings", str(open_findings))
    latest_analysis = connection.execute(
        "SELECT * FROM analyses WHERE wave_id=? ORDER BY created_revision DESC,rowid DESC LIMIT 1", (wave_id,)
    ).fetchone()
    if latest_analysis is None or latest_analysis["status"] != "ready":
        add_finding(findings, "ANALYSIS_NOT_READY", "analyses")
    file_records: list[dict[str, str]] = []
    for row in connection.execute("SELECT path,sha256 FROM snapshot_files ORDER BY path"):
        try:
            relative, actual = require_local_file(root, row["path"], "snapshot.path")
        except WorkflowError:
            add_finding(findings, "SNAPSHOT_FILE_INVALID", f"snapshot_files.{row['path']}")
            continue
        file_records.append({"path": relative, "sha256": actual})
        if actual != row["sha256"]:
            add_finding(findings, "SNAPSHOT_FILE_DRIFT", f"snapshot_files.{row['path']}")
    for table in list_project_tables(connection):
        if table in {"registry_metadata"}:
            continue
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        text_columns = [column for column in columns if column.endswith("path") or column.endswith("_json") or column == "value"]
        if not text_columns:
            continue
        for row in connection.execute(f"SELECT {','.join(text_columns)} FROM {table}"):
            if any(isinstance(row[column], str) and str(root) in row[column] for column in text_columns):
                add_finding(findings, "ABSOLUTE_PATH_STORED", table)
                break
    snapshot_digest = sha256_json({"logical_digest": digest, "files": file_records})
    audit = connection.execute(
        "SELECT * FROM audit_attestations WHERE wave_id=? AND status='active'", (wave_id,)
    ).fetchone()
    audited = bool(
        audit
        and audit["revision"] == revision
        and audit["logical_digest"] == digest
        and audit["snapshot_digest"] == snapshot_digest
    )
    return {
        "ok": not findings,
        "project_ref": metadata.get("project_ref"),
        "wave_id": wave_id,
        "revision": revision,
        "logical_digest": digest,
        "snapshot_digest": snapshot_digest,
        "audited": audited,
        "findings": findings,
    }


def workflow_validate_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
    root, connection = open_project(project_ref)
    with contextlib.closing(connection):
        result = validation_result(root, connection, wave_id)
        if args.get("_all") is True:
            return result
        page = page_items(
            result["findings"], args, project_ref, result["revision"], {"tool": "workflow_validate", "wave_id": wave_id}
        )
        result["findings"] = page.pop("items")
        result.update(page)
        return result


def workflow_mark_audited_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
    owner = require_text(args.get("owner_session_ref"), "owner_session_ref", ref=True)
    audit_ref = require_text(args.get("audit_ref"), "audit_ref", ref=True)
    root, connection = open_project(project_ref, writable=True)
    with contextlib.closing(connection):
        request_id, expected_revision, expected_digest, payload_digest = check_cas(connection, args)
        connection.execute("BEGIN IMMEDIATE")
        try:
            prior = prior_request(connection, request_id, "workflow_mark_audited", payload_digest)
            if prior is not None:
                connection.rollback()
                return prior
            revision = current_revision(connection)
            digest = logical_digest(connection)
            if revision != expected_revision or digest != expected_digest:
                raise WorkflowError("CAS_MISMATCH")
            require_wave_owner(connection, wave_id, owner)
            result = validation_result(root, connection, wave_id)
            if not result["ok"]:
                raise WorkflowError("AUDIT_VALIDATION_FAILED", canonical_json(result["findings"]))
            connection.execute("UPDATE audit_attestations SET status='stale' WHERE wave_id=?", (wave_id,))
            connection.execute(
                "INSERT INTO audit_attestations VALUES(?,?,?,?,?,'active',?)",
                (audit_ref, wave_id, revision, digest, result["snapshot_digest"], utc_now()),
            )
            value = {
                **result,
                "audited": True,
                "audit_ref": audit_ref,
                "workflow_status": "audited",
            }
            connection.execute(
                "INSERT INTO request_log VALUES(?,?,?,?,?,?,?)",
                (request_id, "workflow_mark_audited", payload_digest, revision, digest, canonical_json(value), utc_now()),
            )
            connection.commit()
            return value
        except Exception:
            connection.rollback()
            raise


def encode_cursor(project_ref: str, revision: int, query_digest: str, offset: int) -> str:
    payload = canonical_json(
        {"project_ref": project_ref, "revision": revision, "query_digest": query_digest, "offset": offset}
    ).encode("utf-8")
    signature = hashlib.sha256(b"bears-app-workflow-cursor-v1\0" + payload).hexdigest()
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=") + "." + signature


def decode_cursor(cursor: str, project_ref: str, revision: int, query_digest: str) -> int:
    try:
        encoded, signature = cursor.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        expected = hashlib.sha256(b"bears-app-workflow-cursor-v1\0" + payload).hexdigest()
        value = json.loads(payload)
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise WorkflowError("CURSOR_INVALID") from None
    if signature != expected or value.get("project_ref") != project_ref or value.get("revision") != revision or value.get("query_digest") != query_digest:
        raise WorkflowError("CURSOR_STALE")
    return require_int(value.get("offset"), "cursor.offset", 0, 2**63 - 1)


def page_items(
    items: list[dict[str, Any]], args: dict[str, Any], project_ref: str, revision: int, binding: Any
) -> dict[str, Any]:
    limit = require_int(args.get("limit", DEFAULT_LIMIT), "limit", 1, MAX_LIMIT)
    query_digest = sha256_json(binding)
    cursor = args.get("cursor")
    offset = decode_cursor(require_text(cursor, "cursor"), project_ref, revision, query_digest) if cursor else 0
    page = items[offset:offset + limit]
    while page and len(canonical_json(page).encode("utf-8")) > MAX_RESPONSE_BYTES - 8192:
        page.pop()
    next_offset = offset + len(page)
    next_cursor = encode_cursor(project_ref, revision, query_digest, next_offset) if next_offset < len(items) else None
    return {"items": page, "next_cursor": next_cursor, "count": len(page), "total": len(items)}


def row_object(connection: sqlite3.Connection, object_type: str, row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    for key in list(value):
        if key.endswith("_json"):
            value[key[:-5]] = json.loads(value.pop(key))
    ref_key = {"entity": "entity_ref", "observation": "observation_ref", "relation": "relation_ref"}[object_type]
    value["source_refs"] = source_refs_for(connection, object_type, value[ref_key])
    value["object_type"] = object_type
    return value


def graph_read_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    object_type = args.get("object_type", "all")
    status = args.get("status", "active")
    if object_type not in {"all", "entity", "observation", "relation"} or status not in {"active", "retired", "all"}:
        raise WorkflowError("INVALID_ARGUMENT")
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        revision = current_revision(connection)
        items: list[dict[str, Any]] = []
        for kind, table in (("entity", "entities"), ("observation", "observations"), ("relation", "relations")):
            if object_type not in {"all", kind}:
                continue
            query = f"SELECT * FROM {table}" + ("" if status == "all" else " WHERE status=?")
            parameters: tuple[Any, ...] = () if status == "all" else (status,)
            items.extend(row_object(connection, kind, row) for row in connection.execute(query, parameters))
        items.sort(key=lambda item: (item["object_type"], next(value for key, value in item.items() if key.endswith("_ref"))))
        return {"project_ref": project_ref, "revision": revision, **page_items(items, args, project_ref, revision, {"tool": "graph_read", "object_type": object_type, "status": status})}


def graph_search_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    query = require_text(args.get("query"), "query").casefold()
    status = args.get("status", "active")
    if status not in {"active", "retired", "all"}:
        raise WorkflowError("INVALID_ARGUMENT")
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        revision = current_revision(connection)
        items: list[dict[str, Any]] = []
        for object_type, table in (("entity", "entities"), ("observation", "observations"), ("relation", "relations")):
            sql = f"SELECT * FROM {table}" + ("" if status == "all" else " WHERE status=?")
            parameters: tuple[Any, ...] = () if status == "all" else (status,)
            for row in connection.execute(sql, parameters):
                item = row_object(connection, object_type, row)
                if query in canonical_json(item).casefold():
                    items.append(item)
        items.sort(key=canonical_json)
        return {"project_ref": project_ref, "revision": revision, **page_items(items, args, project_ref, revision, {"tool": "graph_search", "query": query, "status": status})}


def graph_open_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    refs = normalize_refs(args.get("refs", []), "refs", nonempty=True)
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        items: list[dict[str, Any]] = []
        for object_type, table, key in (
            ("entity", "entities", "entity_ref"),
            ("observation", "observations", "observation_ref"),
            ("relation", "relations", "relation_ref"),
        ):
            for ref in refs:
                row = connection.execute(f"SELECT * FROM {table} WHERE {key}=?", (ref,)).fetchone()
                if row:
                    items.append(row_object(connection, object_type, row))
        missing = sorted(set(refs) - {next(value for key, value in item.items() if key.endswith("_ref")) for item in items})
        return {"project_ref": project_ref, "revision": current_revision(connection), "items": items, "missing_refs": missing}


def traverse_graph(args: dict[str, Any], *, reverse: bool) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    start = require_text(args.get("entity_ref"), "entity_ref", ref=True)
    depth = require_int(args.get("max_depth", DEFAULT_DEPTH), "max_depth", 1, MAX_DEPTH)
    relation_types = args.get("relation_types", ["depends_on"])
    types = normalize_refs(relation_types, "relation_types", nonempty=True)
    if any(item not in RELATION_TYPES for item in types):
        raise WorkflowError("RELATION_TYPE_CLOSED")
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        revision = current_revision(connection)
        seen = {start}
        frontier = [(start, 0)]
        items: list[dict[str, Any]] = []
        while frontier:
            node, level = frontier.pop(0)
            if level >= depth:
                continue
            from_col, to_col = ("to_entity_ref", "from_entity_ref") if reverse else ("from_entity_ref", "to_entity_ref")
            placeholders = ",".join("?" for _ in types)
            rows = connection.execute(
                f"SELECT * FROM relations WHERE {from_col}=? AND status='active' AND relation_type IN ({placeholders}) ORDER BY relation_ref",
                (node, *types),
            )
            for row in rows:
                target = row[to_col]
                items.append({**row_object(connection, "relation", row), "depth": level + 1})
                if target not in seen:
                    seen.add(target)
                    frontier.append((target, level + 1))
        binding = {"tool": "impact_analysis" if reverse else "dependency_slice", "start": start, "depth": depth, "types": types}
        return {"project_ref": project_ref, "revision": revision, "entity_refs": sorted(seen), **page_items(items, args, project_ref, revision, binding)}


def graph_trace_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    source = require_text(args.get("from_entity_ref"), "from_entity_ref", ref=True)
    target = require_text(args.get("to_entity_ref"), "to_entity_ref", ref=True)
    depth = require_int(args.get("max_depth", DEFAULT_DEPTH), "max_depth", 1, MAX_DEPTH)
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        queue: list[tuple[str, list[str], list[str]]] = [(source, [source], [])]
        seen = {source}
        found: tuple[list[str], list[str]] | None = None
        while queue:
            node, nodes, relations = queue.pop(0)
            if len(relations) >= depth:
                continue
            for row in connection.execute(
                "SELECT relation_ref,to_entity_ref FROM relations WHERE from_entity_ref=? AND status='active' ORDER BY relation_ref",
                (node,),
            ):
                new_nodes = nodes + [row["to_entity_ref"]]
                new_relations = relations + [row["relation_ref"]]
                if row["to_entity_ref"] == target:
                    found = (new_nodes, new_relations)
                    queue.clear()
                    break
                if row["to_entity_ref"] not in seen:
                    seen.add(row["to_entity_ref"])
                    queue.append((row["to_entity_ref"], new_nodes, new_relations))
        return {"project_ref": project_ref, "revision": current_revision(connection), "found": found is not None, "entity_refs": found[0] if found else [], "relation_refs": found[1] if found else []}


def graph_diagnostics_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        findings: list[dict[str, str]] = []
        adjacency: dict[str, set[str]] = {}
        for row in connection.execute("SELECT * FROM relations WHERE status='active'"):
            if row["relation_type"] == "depends_on":
                adjacency.setdefault(row["from_entity_ref"], set()).add(row["to_entity_ref"])
        cycle = detect_cycle(adjacency)
        if cycle:
            add_finding(findings, "GRAPH_CYCLE", "relations.depends_on", canonical_json(cycle))
        for object_type, table, key in (("entity", "entities", "entity_ref"), ("observation", "observations", "observation_ref"), ("relation", "relations", "relation_ref")):
            for row in connection.execute(f"SELECT {key} FROM {table} WHERE status='active'"):
                if not source_refs_for(connection, object_type, row[key]):
                    add_finding(findings, "SOURCE_REFS_MISSING", f"{table}.{row[key]}")
        revision = current_revision(connection)
        page = page_items(findings, args, project_ref, revision, {"tool": "graph_diagnostics"})
        return {"project_ref": project_ref, "revision": revision, "ok": not findings, "findings": page.pop("items"), **page}


def topological_plan_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        rows = list(connection.execute("SELECT * FROM tasks WHERE wave_id=? AND record_status='active' ORDER BY sequence", (wave_id,)))
        ids = [row["task_ref"] for row in rows]
        deps = {task_ref: set() for task_ref in ids}
        for row in connection.execute("SELECT d.* FROM dependencies d JOIN tasks t ON t.task_ref=d.task_ref WHERE t.wave_id=? AND t.record_status='active'", (wave_id,)):
            deps[row["task_ref"]].add(row["depends_on_ref"])
        remaining = set(ids)
        done: set[str] = set()
        batches: list[list[str]] = []
        while remaining:
            ready = [task_ref for task_ref in ids if task_ref in remaining and deps[task_ref] <= done]
            if not ready:
                raise WorkflowError("TASK_DEPENDENCY_CYCLE")
            batches.append(ready)
            done.update(ready)
            remaining.difference_update(ready)
        return {"project_ref": project_ref, "wave_id": wave_id, "revision": current_revision(connection), "sequential_order": ids, "dependency_batches": batches}


def workflow_state_backend(args: dict[str, Any]) -> dict[str, Any]:
    project_ref = require_text(args.get("project_ref"), "project_ref", ref=True)
    wave_id = require_text(args.get("wave_id"), "wave_id", ref=True)
    _, connection = open_project(project_ref)
    with contextlib.closing(connection):
        wave = connection.execute("SELECT * FROM waves WHERE wave_id=?", (wave_id,)).fetchone()
        if wave is None:
            raise WorkflowError("WAVE_NOT_FOUND")
        tables = {
            "phases": ("SELECT * FROM phases WHERE wave_id=? ORDER BY ordinal", (wave_id,)),
            "process_records": ("SELECT * FROM process_records WHERE wave_id=? ORDER BY created_revision,record_ref", (wave_id,)),
            "tasks": ("SELECT * FROM tasks WHERE wave_id=? ORDER BY sequence,task_ref", (wave_id,)),
            "reviews": ("SELECT r.* FROM reviews r JOIN tasks t ON t.task_ref=r.task_ref WHERE t.wave_id=? ORDER BY r.created_revision", (wave_id,)),
            "findings": ("SELECT * FROM findings WHERE wave_id=? ORDER BY created_revision,finding_ref", (wave_id,)),
            "corrections": ("SELECT c.* FROM corrections c JOIN tasks t ON t.task_ref=c.task_ref WHERE t.wave_id=? ORDER BY c.created_revision", (wave_id,)),
            "analyses": ("SELECT * FROM analyses WHERE wave_id=? ORDER BY created_revision", (wave_id,)),
        }
        revision = current_revision(connection)
        value: dict[str, Any] = {"project_ref": project_ref, "revision": revision, "logical_digest": logical_digest(connection), "wave": dict(wave)}
        flattened: list[dict[str, Any]] = []
        for name, (query, parameters) in tables.items():
            records = [dict(row) for row in connection.execute(query, parameters)]
            for record in records:
                for key in list(record):
                    if key.endswith("_json"):
                        record[key[:-5]] = json.loads(record.pop(key))
            flattened.extend({"record_type": name, **record} for record in records)
            value[name] = []
        page = page_items(flattened, args, project_ref, revision, {"tool": "workflow_state", "wave_id": wave_id})
        for record in page.pop("items"):
            record_type = record.pop("record_type")
            value[record_type].append(record)
        value.update(page)
        audit = connection.execute("SELECT * FROM audit_attestations WHERE wave_id=? ORDER BY rowid DESC LIMIT 1", (wave_id,)).fetchone()
        value["audit"] = dict(audit) if audit else None
        value["workflow_status"] = "audited" if audit and audit["status"] == "active" and audit["revision"] == value["revision"] and audit["logical_digest"] == value["logical_digest"] else wave["status"]
        return value


def migrate_json_backend(args: dict[str, Any]) -> dict[str, Any]:
    def apply(root: Path, connection: sqlite3.Connection, revision: int) -> dict[str, Any]:
        populated = sum(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("waves", "entities", "observations", "relations", "tasks"))
        if populated:
            raise WorkflowError("MIGRATION_REQUIRES_EMPTY_DATABASE")
        map_ref = require_text(args.get("map_ref"), "map_ref")
        state_ref = require_text(args.get("state_ref"), "state_ref")
        map_path, map_digest = require_local_file(root, map_ref, "map_ref")
        state_path, state_digest = require_local_file(root, state_ref, "state_ref")
        if map_digest != require_digest(args.get("map_sha256"), "map_sha256") or state_digest != require_digest(args.get("state_sha256"), "state_sha256"):
            raise WorkflowError("MIGRATION_SOURCE_DIGEST_MISMATCH")
        try:
            graph = json.loads((root / map_path).read_text(encoding="utf-8"))
            state = json.loads((root / state_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise WorkflowError("MIGRATION_SOURCE_INVALID") from None
        schema = graph.get("schema") if isinstance(graph, dict) else None
        if schema in {"app-functional-map.v4", "app-functional-map.v4.json"}:
            wave_id = require_text(args.get("new_wave_id"), "new_wave_id", ref=True)
            owner = require_text(args.get("owner_session_ref"), "owner_session_ref", ref=True)
            mode = args.get("mode", "DIRECT")
            if mode not in {"DIRECT", "DELEGATED"}:
                raise WorkflowError("INVALID_ARGUMENT")
            connection.execute("INSERT INTO waves VALUES(?,?,?,?,?,?,?)", (wave_id, mode, owner, "pending", PHASES[0], revision, revision))
            connection.executemany("INSERT INTO phases VALUES(?,?,?,?,?,?,?)", [(wave_id, phase, index + 1, "pending", None, "legacy-v4-evidence", revision) for index, phase in enumerate(PHASES)])
            capture_files(root, connection, [map_ref, state_ref], revision)
            return {"migrated": False, "legacy_schema": "v4", "evidence_refs": [map_ref, state_ref], "wave_id": wave_id, "requires_reaudit": True}
        if (
            schema not in {"app-functional-map.v5", "app-functional-map.v5.json"}
            or not isinstance(state, dict)
            or state.get("schema") not in {"workflow-state.v1", "workflow-state.v1.json"}
        ):
            raise WorkflowError("MIGRATION_SCHEMA_UNSUPPORTED")
        wave_id = require_text(state.get("wave_id", args.get("new_wave_id")), "wave_id", ref=True)
        owner = require_text(state.get("owner_session_ref", args.get("owner_session_ref")), "owner_session_ref", ref=True)
        mode = state.get("mode", args.get("mode", "DIRECT"))
        if mode not in {"DIRECT", "DELEGATED"}:
            raise WorkflowError("MIGRATION_SOURCE_INVALID")
        connection.execute("INSERT INTO waves VALUES(?,?,?,?,?,?,?)", (wave_id, mode, owner, "pending", PHASES[0], revision, revision))
        phase_data = {item.get("phase"): item for item in state.get("phases", []) if isinstance(item, dict)}
        connection.executemany("INSERT INTO phases VALUES(?,?,?,?,?,?,?)", [(wave_id, phase, index + 1, phase_data.get(phase, {}).get("status", "pending"), None, None, revision) for index, phase in enumerate(PHASES)])
        nodes = graph.get("nodes", graph.get("entities", []))
        edges = graph.get("edges", graph.get("relations", []))
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise WorkflowError("MIGRATION_SOURCE_INVALID")
        for node in nodes:
            entity_ref = require_text(node.get("id", node.get("entity_ref")), "entity_ref", ref=True)
            kind = require_text(node.get("kind", "functionality"), "kind")
            name = require_text(node.get("label", node.get("name", entity_ref)), "name")
            connection.execute("INSERT INTO entities VALUES(?,?,?,'active',NULL,?,?,?)", (entity_ref, kind, name, canonical_json(node.get("properties", {})), revision, revision))
            set_provenance(root, connection, "entity", entity_ref, [map_ref], revision)
            for index, observation in enumerate(node.get("observations", [])):
                observation_ref = f"{entity_ref}:OBS:{index + 1}"
                content = observation if isinstance(observation, str) else canonical_json(observation)
                connection.execute("INSERT INTO observations VALUES(?,?,?,'active',NULL,?,?)", (observation_ref, entity_ref, content, revision, revision))
                set_provenance(root, connection, "observation", observation_ref, [map_ref], revision)
        for edge in edges:
            relation_ref = require_text(edge.get("id", edge.get("relation_ref")), "relation_ref", ref=True)
            relation_type = edge.get("kind", edge.get("relation_type"))
            if relation_type not in RELATION_TYPES:
                raise WorkflowError("RELATION_TYPE_CLOSED")
            source = require_text(edge.get("from", edge.get("from_entity_ref")), "from_entity_ref", ref=True)
            target = require_text(edge.get("to", edge.get("to_entity_ref")), "to_entity_ref", ref=True)
            connection.execute("INSERT INTO relations VALUES(?,?,?,?,'active',NULL,?,?)", (relation_ref, source, target, relation_type, revision, revision))
            set_provenance(root, connection, "relation", relation_ref, [map_ref], revision)
        ledger = state.get("ledger", {}) if isinstance(state.get("ledger", {}), dict) else {}
        tasks = ledger.get("tasks", state.get("tasks", []))
        if not isinstance(tasks, list):
            raise WorkflowError("MIGRATION_SOURCE_INVALID")
        for index, task in enumerate(tasks):
            task_ref = require_text(task.get("id", task.get("task_ref")), "task_ref", ref=True)
            title = require_text(task.get("title", task_ref), "title")
            sequence = task.get("order", task.get("sequence", index + 1))
            sequence = require_int(sequence, "sequence", 1, max(1, len(tasks)))
            status = task.get("status", "pending")
            change_refs = task.get("change_refs", [])
            if not isinstance(change_refs, list):
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            normalized_change_refs = normalize_refs(change_refs, "change_refs")
            change_digest = task.get("change_digest")
            if normalized_change_refs:
                actual_change_digest, _ = digest_ref_set(root, normalized_change_refs)
                if change_digest is not None and change_digest != actual_change_digest:
                    raise WorkflowError("MIGRATION_PARITY_FAILED")
                change_digest = actual_change_digest
                capture_files(root, connection, normalized_change_refs, revision)
            elif change_digest is not None:
                require_digest(change_digest, "change_digest")
            connection.execute("INSERT INTO tasks VALUES(?,?,?,?,?,'active',NULL,?,?,?, ?,?,?)", (task_ref, wave_id, title, sequence, status, owner, task.get("worker_ref"), change_digest, canonical_json(normalized_change_refs), revision, revision))
            set_provenance(root, connection, "task", task_ref, [state_ref], revision)
        task_ids = {row[0] for row in connection.execute("SELECT task_ref FROM tasks")}
        for task in tasks:
            task_ref = task.get("id", task.get("task_ref"))
            for dependency in task.get("depends_on", []):
                if dependency not in task_ids:
                    raise WorkflowError("MIGRATION_PARITY_FAILED")
                connection.execute("INSERT INTO dependencies VALUES(?,?,?)", (task_ref, dependency, revision))
        processes = state.get("process", state.get("process_records", []))
        reviews = state.get("reviews", [])
        corrections = state.get("corrections", [])
        if not all(isinstance(value, list) for value in (processes, reviews, corrections)):
            raise WorkflowError("MIGRATION_SOURCE_INVALID")
        phase_processes: dict[str, list[dict[str, Any]]] = {phase: [] for phase in PHASES}
        for record in processes:
            if not isinstance(record, dict):
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            phase = require_text(record.get("phase"), "phase")
            if phase not in PHASES:
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            phase_processes[phase].append(record)
        for phase, records in phase_processes.items():
            previous: str | None = None
            for index, record in enumerate(records):
                record_ref = require_text(record.get("id", record.get("record_ref")), "record_ref", ref=True)
                input_digest = record.get("input_digest", state_digest)
                output_digest = record.get("output_digest", state_digest)
                require_digest(input_digest, "input_digest")
                require_digest(output_digest, "output_digest")
                source_refs = [state_ref]
                artifact_refs = [ref for ref in record.get("artifact_refs", []) if isinstance(ref, str)]
                valid_artifacts: list[str] = []
                for ref in artifact_refs:
                    try:
                        require_local_file(root, ref, "artifact_ref")
                    except WorkflowError:
                        continue
                    valid_artifacts.append(ref)
                capture_files(root, connection, sorted(set(source_refs + valid_artifacts)), revision)
                active = 1 if index == len(records) - 1 else 0
                connection.execute(
                    "INSERT INTO process_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        record_ref,
                        wave_id,
                        phase,
                        record.get("outcome", "completed"),
                        record.get("owner_session_ref", owner),
                        input_digest,
                        output_digest,
                        canonical_json(valid_artifacts),
                        canonical_json(source_refs),
                        previous,
                        active,
                        revision,
                    ),
                )
                previous = record_ref
            if previous:
                connection.execute(
                    "UPDATE phases SET process_record_ref=? WHERE wave_id=? AND phase=?",
                    (previous, wave_id, phase),
                )
        review_findings: list[tuple[str, str, str]] = []
        for review in reviews:
            if not isinstance(review, dict):
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            review_ref = require_text(review.get("id", review.get("review_ref")), "review_ref", ref=True)
            task_ref = require_text(review.get("task_ref"), "task_ref", ref=True)
            task = connection.execute("SELECT change_digest FROM tasks WHERE task_ref=?", (task_ref,)).fetchone()
            if task is None:
                raise WorkflowError("MIGRATION_PARITY_FAILED")
            change_digest = review.get("change_digest") or task["change_digest"] or GENESIS_DIGEST
            require_digest(change_digest, "change_digest")
            verdict = str(review.get("verdict", "changes_requested")).replace("-", "_")
            if verdict not in {"approved", "changes_requested"}:
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            connection.execute(
                "INSERT INTO reviews VALUES(?,?,?,?,?,?,?)",
                (review_ref, task_ref, review.get("reviewer_ref", "MIGRATED-REVIEWER"), verdict, change_digest, canonical_json([state_ref]), revision),
            )
            for finding_ref in review.get("finding_refs", []):
                review_findings.append((require_text(finding_ref, "finding_ref", ref=True), review_ref, task_ref))
        correction_refs = {correction.get("finding_ref") for correction in corrections if isinstance(correction, dict)}
        for finding_ref, review_ref, task_ref in review_findings:
            status = "resolved" if finding_ref in correction_refs else "open"
            connection.execute(
                "INSERT INTO findings VALUES(?,?,?,?,?,?,? ,?,?,?,?)",
                (finding_ref, wave_id, review_ref, None, "migrated-review", "Migrated review finding", "needs-plan", status, canonical_json([state_ref]), revision, revision),
            )
        for correction in corrections:
            if not isinstance(correction, dict):
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            correction_ref = require_text(correction.get("id", correction.get("correction_ref")), "correction_ref", ref=True)
            finding_ref = require_text(correction.get("finding_ref"), "finding_ref", ref=True)
            task_ref = require_text(correction.get("task_ref"), "task_ref", ref=True)
            if connection.execute("SELECT 1 FROM findings WHERE finding_ref=?", (finding_ref,)).fetchone() is None:
                connection.execute(
                    "INSERT INTO findings VALUES(?,?,?,?,?,?,?,'open',?,?,?)",
                    (finding_ref, wave_id, None, None, "migrated-correction", "Migrated correction finding", "needs-plan", canonical_json([state_ref]), revision, revision),
                )
            evidence_refs = [ref for ref in correction.get("evidence_refs", []) if isinstance(ref, str)]
            valid_evidence: list[str] = []
            for ref in evidence_refs:
                try:
                    require_local_file(root, ref, "evidence_ref")
                except WorkflowError:
                    continue
                valid_evidence.append(ref)
            status = correction.get("status", "open")
            if status not in {"open", "resolved"}:
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            capture_files(root, connection, sorted(set([state_ref] + valid_evidence)), revision)
            connection.execute(
                "INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?)",
                (correction_ref, finding_ref, task_ref, status, canonical_json(valid_evidence), canonical_json([state_ref]), revision, revision),
            )
            connection.execute("UPDATE findings SET status=?,updated_revision=? WHERE finding_ref=?", (status, revision, finding_ref))
        analysis = state.get("analysis")
        analysis_count = 0
        if isinstance(analysis, dict):
            analysis_ref = require_text(analysis.get("analysis_ref", "MIGRATED-ANALYSIS"), "analysis_ref", ref=True)
            semantic_findings = analysis.get("findings", [])
            if not isinstance(semantic_findings, list):
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            analysis_status = "findings" if semantic_findings else "ready"
            route = None
            for index, finding in enumerate(semantic_findings):
                item = finding if isinstance(finding, dict) else {"summary": str(finding)}
                finding_ref = require_text(item.get("finding_ref", item.get("id", f"MIGRATED-ANALYSIS-FINDING-{index + 1}")), "finding_ref", ref=True)
                candidate_route = item.get("route", "app-plan")
                if candidate_route not in PHASES[:-1]:
                    candidate_route = "app-plan"
                route = candidate_route if route is None or PHASES.index(candidate_route) < PHASES.index(route) else route
                connection.execute(
                    "INSERT INTO findings VALUES(?,?,?,?,?,?,?,'open',?,?,?)",
                    (finding_ref, wave_id, None, analysis_ref, item.get("kind", "migrated-analysis"), item.get("summary", "Migrated semantic finding"), candidate_route, canonical_json([state_ref]), revision, revision),
                )
            connection.execute("INSERT INTO analyses VALUES(?,?,?,?,?,?)", (analysis_ref, wave_id, analysis_status, route, canonical_json([state_ref]), revision))
            analysis_count = 1
        declared_snapshot = state.get("snapshot", {})
        declared_files = declared_snapshot.get("files", []) if isinstance(declared_snapshot, dict) else []
        if not isinstance(declared_files, list):
            raise WorkflowError("MIGRATION_SOURCE_INVALID")
        for record in declared_files:
            if not isinstance(record, dict):
                raise WorkflowError("MIGRATION_SOURCE_INVALID")
            relative, actual = require_local_file(root, record.get("path"), "snapshot.path")
            declared = record.get("sha256")
            if declared is not None and declared != actual:
                raise WorkflowError("MIGRATION_PARITY_FAILED")
            connection.execute(
                "INSERT INTO snapshot_files VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,captured_revision=excluded.captured_revision",
                (relative, actual, revision),
            )
        capture_files(root, connection, [map_ref, state_ref], revision)
        parity = {
            "entities": connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == len(nodes),
            "relations": connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == len(edges),
            "tasks": connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == len(tasks),
            "process_records": connection.execute("SELECT COUNT(*) FROM process_records").fetchone()[0] == len(processes),
            "reviews": connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == len(reviews),
            "corrections": connection.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == len(corrections),
            "analyses": connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == analysis_count,
        }
        if not all(parity.values()):
            raise WorkflowError("MIGRATION_PARITY_FAILED")
        return {"migrated": True, "wave_id": wave_id, "source_sha256": {map_ref: map_digest, state_ref: state_digest}, "parity": parity, "requires_reaudit": True}

    return mutate_project("project_migrate_json", args, apply)


def tool_schema(properties: dict[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


PROJECT_REF_SCHEMA = {"type": "string", "minLength": 1}
TEXT_SCHEMA = {"type": "string", "minLength": 1}
DIGEST_SCHEMA = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
REFS_SCHEMA = {"type": "array", "items": TEXT_SCHEMA, "uniqueItems": True}
LIMIT_SCHEMA = {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT}
DEPTH_SCHEMA = {"type": "integer", "minimum": 1, "maximum": MAX_DEPTH, "default": DEFAULT_DEPTH}
CURSOR_SCHEMA = {"type": "string", "minLength": 1}
CAS_PROPERTIES = {
    "project_ref": PROJECT_REF_SCHEMA,
    "request_id": TEXT_SCHEMA,
    "expected_revision": {"type": "integer", "minimum": 0},
    "expected_logical_digest": DIGEST_SCHEMA,
}
CAS_REQUIRED = tuple(CAS_PROPERTIES)
WAVE_PROPERTIES = {**CAS_PROPERTIES, "wave_id": TEXT_SCHEMA, "owner_session_ref": TEXT_SCHEMA}
WAVE_REQUIRED = tuple(WAVE_PROPERTIES)
READ_TOOLS: dict[str, dict[str, Any]] = {
    "project_list": {
        "description": "List registered workflow projects.",
        "inputSchema": tool_schema({}),
    },
    "project_status": {
        "description": "Read project revision, logical digest, storage settings, and audit state.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA}, ("project_ref",)),
    },
    "graph_read": {
        "description": "Read bounded graph objects at the current project revision.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "object_type": {"enum": ["all", "entity", "observation", "relation"], "default": "all"}, "status": {"enum": ["active", "retired", "all"], "default": "active"}, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref",)),
    },
    "graph_search": {
        "description": "Search graph objects using a bounded case-insensitive text query.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "query": TEXT_SCHEMA, "status": {"enum": ["active", "retired", "all"], "default": "active"}, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref", "query")),
    },
    "graph_open": {
        "description": "Open exact graph object references with provenance.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "refs": {**REFS_SCHEMA, "minItems": 1, "maxItems": MAX_LIMIT}}, ("project_ref", "refs")),
    },
    "dependency_slice": {
        "description": "Traverse outgoing typed graph dependencies.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "entity_ref": TEXT_SCHEMA, "relation_types": REFS_SCHEMA, "max_depth": DEPTH_SCHEMA, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref", "entity_ref")),
    },
    "impact_analysis": {
        "description": "Traverse reverse typed graph dependencies to find impacted objects.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "entity_ref": TEXT_SCHEMA, "relation_types": REFS_SCHEMA, "max_depth": DEPTH_SCHEMA, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref", "entity_ref")),
    },
    "graph_trace": {
        "description": "Find one bounded directed graph path between two entities.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "from_entity_ref": TEXT_SCHEMA, "to_entity_ref": TEXT_SCHEMA, "max_depth": DEPTH_SCHEMA}, ("project_ref", "from_entity_ref", "to_entity_ref")),
    },
    "graph_diagnostics": {
        "description": "Report graph provenance and dependency-cycle diagnostics without writing.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref",)),
    },
    "topological_plan": {
        "description": "Read the dependency and sequential execution order for a wave plan.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "wave_id": TEXT_SCHEMA}, ("project_ref", "wave_id")),
    },
    "workflow_state": {
        "description": "Read the normalized workflow state for one wave.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "wave_id": TEXT_SCHEMA, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref", "wave_id")),
    },
    "workflow_validate": {
        "description": "Validate logical workflow rows and exact source files without writing.",
        "inputSchema": tool_schema({"project_ref": PROJECT_REF_SCHEMA, "wave_id": TEXT_SCHEMA, "limit": LIMIT_SCHEMA, "cursor": CURSOR_SCHEMA}, ("project_ref", "wave_id")),
    },
}
MAINTAINER_TOOLS: dict[str, dict[str, Any]] = {
    "project_register": {
        "description": "Register an absolute non-symlink Git root and create or attach its workflow database.",
        "inputSchema": tool_schema({"project_root": TEXT_SCHEMA, "request_id": TEXT_SCHEMA, "expected_revision": {"type": "integer", "minimum": 0}, "expected_logical_digest": DIGEST_SCHEMA}, ("project_root", "request_id", "expected_revision", "expected_logical_digest")),
    },
    "project_rebind": {
        "description": "Rebind a project reference to a new Git root containing the same database identity.",
        "inputSchema": tool_schema({**CAS_PROPERTIES, "project_root": TEXT_SCHEMA}, (*CAS_REQUIRED, "project_root")),
    },
    "project_unregister": {
        "description": "Remove only a registry binding and retain the project database.",
        "inputSchema": tool_schema(CAS_PROPERTIES, CAS_REQUIRED),
    },
    "project_migrate_json": {
        "description": "Import v5 functional-map and v1 workflow-state JSON into an empty database with exact source digests.",
        "inputSchema": tool_schema({**CAS_PROPERTIES, "map_ref": TEXT_SCHEMA, "state_ref": TEXT_SCHEMA, "map_sha256": DIGEST_SCHEMA, "state_sha256": DIGEST_SCHEMA, "new_wave_id": TEXT_SCHEMA, "mode": {"enum": ["DIRECT", "DELEGATED"]}, "owner_session_ref": TEXT_SCHEMA}, (*CAS_REQUIRED, "map_ref", "state_ref", "map_sha256", "state_sha256")),
    },
    "wave_initialize": {
        "description": "Initialize one seven-phase DIRECT or DELEGATED wave.",
        "inputSchema": tool_schema({**CAS_PROPERTIES, "wave_id": TEXT_SCHEMA, "mode": {"enum": ["DIRECT", "DELEGATED"]}, "owner_session_ref": TEXT_SCHEMA}, (*CAS_REQUIRED, "wave_id", "mode", "owner_session_ref")),
    },
    "phase_record": {
        "description": "Supersede the current phase process record and retain its history.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "phase": {"enum": list(PHASES)}, "record_ref": TEXT_SCHEMA, "outcome": {"enum": ["completed", "skipped-current", "blocked", "pending"]}, "input_digest": DIGEST_SCHEMA, "output_digest": DIGEST_SCHEMA, "source_refs": REFS_SCHEMA, "artifact_refs": REFS_SCHEMA}, (*WAVE_REQUIRED, "phase", "record_ref", "outcome", "input_digest", "output_digest", "source_refs", "artifact_refs")),
    },
    "graph_apply": {
        "description": "Apply one all-or-nothing batch of graph upserts or retirements.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "operations": {"type": "array", "minItems": 1, "maxItems": MAX_LIMIT, "items": {"type": "object"}}}, (*WAVE_REQUIRED, "operations")),
    },
    "plan_replace": {
        "description": "Replace the active wave plan and dependencies in one transaction.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "tasks": {"type": "array", "maxItems": MAX_LIMIT, "items": {"type": "object"}}}, (*WAVE_REQUIRED, "tasks")),
    },
    "task_record_change": {
        "description": "Bind one task to the exact digest of its changed files.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "task_ref": TEXT_SCHEMA, "worker_ref": TEXT_SCHEMA, "change_refs": {**REFS_SCHEMA, "minItems": 1}}, (*WAVE_REQUIRED, "task_ref", "worker_ref", "change_refs")),
    },
    "review_record": {
        "description": "Record an exact-change review and complete only tasks with closed corrections.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "review_ref": TEXT_SCHEMA, "task_ref": TEXT_SCHEMA, "reviewer_ref": TEXT_SCHEMA, "verdict": {"enum": ["approved", "changes_requested"]}, "change_digest": DIGEST_SCHEMA, "source_refs": {**REFS_SCHEMA, "minItems": 1}, "findings": {"type": "array", "items": {"type": "object"}},}, (*WAVE_REQUIRED, "review_ref", "task_ref", "reviewer_ref", "verdict", "change_digest", "source_refs", "findings")),
    },
    "correction_record": {
        "description": "Record or resolve a task correction with exact evidence.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "correction_ref": TEXT_SCHEMA, "finding_ref": TEXT_SCHEMA, "task_ref": TEXT_SCHEMA, "status": {"enum": ["open", "resolved"]}, "evidence_refs": REFS_SCHEMA, "source_refs": {**REFS_SCHEMA, "minItems": 1}}, (*WAVE_REQUIRED, "correction_ref", "finding_ref", "task_ref", "status", "evidence_refs", "source_refs")),
    },
    "analysis_record": {
        "description": "Record semantic findings or a clean ready analysis and reopen the required phase.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "analysis_ref": TEXT_SCHEMA, "source_refs": {**REFS_SCHEMA, "minItems": 1}, "findings": {"type": "array", "items": {"type": "object"}}}, (*WAVE_REQUIRED, "analysis_ref", "source_refs", "findings")),
    },
    "workflow_mark_audited": {
        "description": "Revalidate the same revision inside a transaction and atomically attest audited.",
        "inputSchema": tool_schema({**WAVE_PROPERTIES, "audit_ref": TEXT_SCHEMA}, (*WAVE_REQUIRED, "audit_ref")),
    },
}


def execute_tool(mode: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "project_list":
        return project_list_backend()
    if name == "project_status":
        return project_status_backend(require_text(arguments.get("project_ref"), "project_ref", ref=True))
    readers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "graph_read": graph_read_backend,
        "graph_search": graph_search_backend,
        "graph_open": graph_open_backend,
        "dependency_slice": lambda value: traverse_graph(value, reverse=False),
        "impact_analysis": lambda value: traverse_graph(value, reverse=True),
        "graph_trace": graph_trace_backend,
        "graph_diagnostics": graph_diagnostics_backend,
        "topological_plan": topological_plan_backend,
        "workflow_state": workflow_state_backend,
        "workflow_validate": workflow_validate_backend,
    }
    maintainers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "project_register": register_backend,
        "project_rebind": rebind_backend,
        "project_unregister": unregister_backend,
        "project_migrate_json": migrate_json_backend,
        "wave_initialize": wave_initialize_backend,
        "phase_record": phase_record_backend,
        "graph_apply": graph_apply_backend,
        "plan_replace": plan_replace_backend,
        "task_record_change": task_record_change_backend,
        "review_record": review_record_backend,
        "correction_record": correction_record_backend,
        "analysis_record": analysis_record_backend,
        "workflow_mark_audited": workflow_mark_audited_backend,
    }
    if name in readers:
        return readers[name](arguments)
    if mode == "maintainer" and name in maintainers:
        return maintainers[name](arguments)
    raise WorkflowError("TOOL_NOT_FOUND", name)


def tool_result(value: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    text = canonical_json(value)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": value,
        **({"isError": True} if is_error else {}),
    }


def emit(message: dict[str, Any]) -> None:
    raw = canonical_json(message).encode("utf-8")
    if len(raw) > MAX_RESPONSE_BYTES:
        fallback = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32603, "message": "RESPONSE_LIMIT_EXCEEDED"},
        }
        raw = canonical_json(fallback).encode("utf-8")
    sys.stdout.buffer.write(raw + b"\n")
    sys.stdout.buffer.flush()


def handle_rpc(mode: str, request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        params = request.get("params") if isinstance(request.get("params"), dict) else {}
        requested = params.get("protocolVersion")
        protocol = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": f"app-workflow-{mode}", "version": VERSION},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        tools = READ_TOOLS if mode == "reader" else MAINTAINER_TOOLS
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [{"name": name, **spec} for name, spec in tools.items()]},
        }
    if method == "tools/call":
        params = request.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("arguments", {}), dict):
            raise WorkflowError("INVALID_ARGUMENT")
        name = require_text(params.get("name"), "name")
        allowed = name in (READ_TOOLS if mode == "reader" else MAINTAINER_TOOLS)
        if not allowed:
            raise WorkflowError("TOOL_NOT_FOUND", name)
        try:
            value = execute_tool(mode, name, params.get("arguments", {}))
            result = tool_result(value)
        except WorkflowError as exc:
            result = tool_result({"ok": False, "code": exc.code, "message": exc.message}, is_error=True)
        except (OSError, sqlite3.Error, ValueError) as exc:
            result = tool_result({"ok": False, "code": "INTERNAL_ERROR", "message": str(exc)}, is_error=True)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


def serve(mode: str) -> int:
    if mode not in {"reader", "maintainer"}:
        raise WorkflowError("INVALID_MODE")
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_REQUEST_BYTES:
            emit({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "REQUEST_LIMIT_EXCEEDED"}})
            continue
        try:
            request = json.loads(raw)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                raise ValueError
            response = handle_rpc(mode, request)
        except (json.JSONDecodeError, UnicodeError, ValueError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        except WorkflowError as exc:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None, "error": {"code": -32602, "message": exc.code}}
        if response is not None:
            emit(response)
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    server = subparsers.add_parser("serve")
    server.add_argument("--mode", choices=("reader", "maintainer"), required=True)
    validator = subparsers.add_parser("validate")
    validator.add_argument("--project-ref", required=True)
    validator.add_argument("--wave-id", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "serve":
        return serve(args.mode)
    if args.command == "validate":
        result = workflow_validate_backend({"project_ref": args.project_ref, "wave_id": args.wave_id, "_all": True})
        print(canonical_json({"ok": result["ok"], "snapshot_digest": result["snapshot_digest"], "findings": result["findings"]}))
        return 0 if result["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
