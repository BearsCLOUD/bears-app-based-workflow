"""Private state-directory, migration tombstone, and deploy receipt reads."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any

from .constants import (
    DEPLOY_RECEIPT_SCHEMA,
    GRAPH_DEPLOY_RECEIPT_SCHEMA,
    FINGERPRINT_RE,
    LEGACY_DEPLOY_RECEIPT_SCHEMA,
    LEGACY_VERSION_RE,
    PRIOR_DEPLOY_RECEIPT_SCHEMA,
    LOCK_FILE,
    MARKETPLACE,
    MIGRATION_TOMBSTONE_FILE,
    MIRROR,
    PLUGIN,
    RECEIPT_MAX_BYTES,
    RENAME_NOREPLACE,
    REPOSITORY,
    ROLE_GENERATIONS_DIR,
    ROLE_MIGRATION_TOMBSTONE_SCHEMA,
    SHA_RE,
    STATE_DIR,
    STATE_FILE,
    STATE_ROOT,
    VERSION_RE,
)
from .journal import decode_journal_bytes
from .models import DeployError
from .publication import renameat2, write_publication_stage
from .role_profiles import strict_json_loads


def validate_directory_component(
    descriptor: int,
    *,
    expected_uid: int,
    expected_gid: int,
    exact_mode: int | None,
) -> None:
    """Require a trusted directory component opened without link traversal."""
    component_stat = os.fstat(descriptor)
    mode = stat.S_IMODE(component_stat.st_mode)
    unsafe_mode = mode != exact_mode if exact_mode is not None else bool(mode & 0o022)
    if (
        not stat.S_ISDIR(component_stat.st_mode)
        or component_stat.st_uid != expected_uid
        or component_stat.st_gid != expected_gid
        or unsafe_mode
    ):
        raise DeployError("deployment state path component owner, mode, or type is unsafe")


def open_state_directory() -> int:
    """Open and validate every fixed path component without following links."""
    if (
        STATE_ROOT != Path("/var/lib/bears-plugin-deploy")
        or STATE_DIR != STATE_ROOT / "ai1"
        or ROLE_GENERATIONS_DIR != STATE_DIR / "role-generations"
        or MIRROR != STATE_DIR / "repository.git"
    ):
        raise DeployError("deployment state path constants are inconsistent")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    components = ("var", "lib", STATE_ROOT.name, STATE_DIR.name)
    try:
        validate_directory_component(
            descriptor,
            expected_uid=0,
            expected_gid=0,
            exact_mode=None,
        )
        for depth, component in enumerate(components, start=1):
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                raise DeployError("root-provisioned deployment state path is incomplete")
            except OSError as exc:
                raise DeployError("deployment state path component is unsafe") from exc
            try:
                leaf = depth == len(components)
                parent = depth == len(components) - 1
                validate_directory_component(
                    child,
                    expected_uid=os.geteuid() if leaf else 0,
                    expected_gid=os.getegid() if leaf else 0,
                    exact_mode=0o700 if leaf else 0o755 if parent else None,
                )
            except Exception:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def validate_private_regular(descriptor: int, label: str, *, error_code: str | None = None) -> os.stat_result:
    file_stat = os.fstat(descriptor)
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o600
        or file_stat.st_nlink != 1
    ):
        raise DeployError(f"{label} owner, mode, type, or link count is unsafe", error_code=error_code)
    return file_stat


def open_lock_file(state_directory: int) -> int:
    descriptor = os.open(
        LOCK_FILE.name,
        os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
        dir_fd=state_directory,
    )
    try:
        validate_private_regular(descriptor, "deployment lock")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def read_private_state_name_at(
    state_directory: int,
    name: str,
    maximum: int,
    label: str,
) -> tuple[bytes, os.stat_result] | None:
    """Read one private state file relative to the already trusted leaf."""
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=state_directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError(f"{label} is unsafe", error_code="receipt-corruption") from exc
    try:
        file_stat = validate_private_regular(
            descriptor, label, error_code="receipt-corruption"
        )
        if file_stat.st_size > maximum:
            raise DeployError(f"{label} is oversized", error_code="receipt-corruption")
        payload = bytearray()
        while len(payload) <= maximum:
            chunk = os.read(descriptor, min(4096, maximum + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > maximum:
            raise DeployError(f"{label} is oversized", error_code="receipt-corruption")
        return bytes(payload), file_stat
    except OSError as exc:
        raise DeployError(f"{label} is unreadable", error_code="receipt-corruption") from exc
    finally:
        os.close(descriptor)


def parse_migration_tombstone(data: bytes) -> dict[str, Any]:
    """Validate the durable anti-replay record for the one v1 migration."""
    value = strict_json_loads(data, "registration migration tombstone")
    fields = {
        "schema",
        "plugin",
        "legacy_fingerprint",
        "requested_sha",
        "role_generation",
        "role_receipt_sha256",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schema") != ROLE_MIGRATION_TOMBSTONE_SCHEMA
        or value.get("plugin") != PLUGIN
        or not isinstance(value.get("legacy_fingerprint"), str)
        or not FINGERPRINT_RE.fullmatch(value["legacy_fingerprint"])
        or not isinstance(value.get("requested_sha"), str)
        or not SHA_RE.fullmatch(value["requested_sha"])
        or not isinstance(value.get("role_generation"), str)
        or not FINGERPRINT_RE.fullmatch(value["role_generation"])
        or not isinstance(value.get("role_receipt_sha256"), str)
        or not FINGERPRINT_RE.fullmatch(value["role_receipt_sha256"])
    ):
        raise DeployError(
            "registration migration tombstone is invalid",
            error_code="receipt-corruption",
        )
    return value


def build_migration_tombstone(
    legacy_fingerprint: str,
    requested_sha: str,
    role_generation: str,
    role_receipt_sha256: str,
) -> bytes:
    value = {
        "schema": ROLE_MIGRATION_TOMBSTONE_SCHEMA,
        "plugin": PLUGIN,
        "legacy_fingerprint": legacy_fingerprint,
        "requested_sha": requested_sha,
        "role_generation": role_generation,
        "role_receipt_sha256": role_receipt_sha256,
    }
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    parse_migration_tombstone(payload)
    return payload


def load_migration_tombstone(state_directory: int) -> dict[str, Any] | None:
    snapshot = read_private_state_name_at(
        state_directory,
        MIGRATION_TOMBSTONE_FILE.name,
        RECEIPT_MAX_BYTES,
        "registration migration tombstone",
    )
    return None if snapshot is None else parse_migration_tombstone(snapshot[0])


def publish_migration_tombstone(state_directory: int, transaction: dict[str, Any]) -> None:
    """Durably publish the one-shot anti-replay record without replacement."""
    payload = decode_journal_bytes(
        transaction["tombstone_b64"], RECEIPT_MAX_BYTES, "migration tombstone"
    )
    if not secrets.compare_digest(
        hashlib.sha256(payload).hexdigest(), transaction["tombstone_sha256"]
    ):
        raise DeployError("journaled migration tombstone digest is invalid")
    value = parse_migration_tombstone(payload)
    if (
        value["legacy_fingerprint"] != transaction["legacy_fingerprint"]
        or value["role_generation"] != transaction["role_generation"]
        or value["role_receipt_sha256"] != transaction["role_receipt_sha256"]
    ):
        raise DeployError("journaled migration tombstone binding is inconsistent")
    name = MIGRATION_TOMBSTONE_FILE.name
    exchange = transaction["tombstone_exchange_name"]
    current = read_private_state_name_at(
        state_directory, name, RECEIPT_MAX_BYTES, "registration migration tombstone"
    )
    if current is not None:
        if not secrets.compare_digest(current[0], payload):
            raise DeployError("conflicting registration migration tombstone")
        staged = read_private_state_name_at(
            state_directory, exchange, RECEIPT_MAX_BYTES, "migration tombstone staging file"
        )
        if staged is not None:
            if not secrets.compare_digest(staged[0], payload):
                raise DeployError("migration tombstone staging file is ambiguous")
            os.unlink(exchange, dir_fd=state_directory)
        os.fsync(state_directory)
        return
    write_publication_stage(
        state_directory,
        exchange,
        payload,
        0o600,
        lambda directory, target: read_private_state_name_at(
            directory, target, RECEIPT_MAX_BYTES, "migration tombstone staging file"
        ),
        "registration migration tombstone",
    )
    try:
        renameat2(state_directory, exchange, name, RENAME_NOREPLACE)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        current = read_private_state_name_at(
            state_directory, name, RECEIPT_MAX_BYTES, "registration migration tombstone"
        )
        if current is None or not secrets.compare_digest(current[0], payload):
            raise DeployError("registration migration tombstone publication raced") from exc
        os.unlink(exchange, dir_fd=state_directory)
    os.fsync(state_directory)
    durable = read_private_state_name_at(
        state_directory, name, RECEIPT_MAX_BYTES, "registration migration tombstone"
    )
    if durable is None or not secrets.compare_digest(durable[0], payload):
        raise DeployError("registration migration tombstone is not durable")


def validate_deploy_receipt(value: Any) -> dict[str, Any]:
    base_fields = {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "sha",
        "version",
        "payload_fingerprint",
    }
    if (
        not isinstance(value, dict)
        or value.get("schema") not in {LEGACY_DEPLOY_RECEIPT_SCHEMA, PRIOR_DEPLOY_RECEIPT_SCHEMA, GRAPH_DEPLOY_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA}
        or value.get("repository") != REPOSITORY
        or value.get("marketplace") != MARKETPLACE
        or value.get("plugin") != PLUGIN
        or not isinstance(value.get("sha"), str)
        or not SHA_RE.fullmatch(value["sha"])
        or not isinstance(value.get("version"), str)
        or not VERSION_RE.fullmatch(value["version"])
        or not isinstance(value.get("payload_fingerprint"), str)
        or not FINGERPRINT_RE.fullmatch(value["payload_fingerprint"])
    ):
        raise DeployError("deployment receipt identity is invalid", error_code="receipt-corruption")
    if value["schema"] == LEGACY_DEPLOY_RECEIPT_SCHEMA:
        if set(value) != base_fields:
            raise DeployError("legacy deployment receipt shape is invalid", error_code="receipt-corruption")
        return value
    role_fields = {
        "role_generation",
        "role_count",
        "role_catalog_sha256",
        "role_receipt_sha256",
        "role_source_blobs",
        "role_profiles",
    }
    graph_fields = {"graph_template_sha256", "graph_block_sha256", "graph_separator_added"}
    expected_fields = base_fields | role_fields | (graph_fields if value["schema"] in {GRAPH_DEPLOY_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA} else set())
    if set(value) != expected_fields:
        raise DeployError("deployment receipt shape is invalid", error_code="receipt-corruption")
    if value["schema"] in {GRAPH_DEPLOY_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA} and (
        not FINGERPRINT_RE.fullmatch(str(value.get("graph_template_sha256", "")))
        or not FINGERPRINT_RE.fullmatch(str(value.get("graph_block_sha256", "")))
        or not isinstance(value.get("graph_separator_added"), bool)
    ):
        raise DeployError("deployment graph instruction receipt is invalid", error_code="receipt-corruption")
    generation = value.get("role_generation")
    blobs = value.get("role_source_blobs")
    profiles = value.get("role_profiles")
    role_count = value.get("role_count")
    profile_names = tuple(
        record.get("name")
        for record in profiles
        if isinstance(record, dict) and isinstance(record.get("name"), str)
    ) if isinstance(profiles, list) else ()
    expected_sources = {
        ".codex-plugin/plugin.json",
        "agents/README.md",
        *(f"agents/{name}.toml" for name in profile_names),
    }
    legacy_jsonless = value.get("version") == "0.3.0" or (
        isinstance(value.get("version"), str)
        and LEGACY_VERSION_RE.fullmatch(value["version"]) is not None
    )
    has_definition_sources = isinstance(blobs, dict) and any(
        path.startswith("role-definitions/") for path in blobs
    )
    if value["schema"] == DEPLOY_RECEIPT_SCHEMA and (has_definition_sources or not legacy_jsonless):
        expected_sources.update(
            {
                "role-definitions/capability-catalog.v1.json",
                *(f"role-definitions/{name}.json" for name in profile_names),
            }
        )
    if (
        not isinstance(generation, str)
        or not FINGERPRINT_RE.fullmatch(generation)
        or not isinstance(role_count, int)
        or isinstance(role_count, bool)
        or not 1 <= role_count <= 64
        or value.get("role_catalog_sha256") != generation
        or not FINGERPRINT_RE.fullmatch(str(value.get("role_receipt_sha256", "")))
        or not isinstance(blobs, dict)
        or set(blobs) != expected_sources
        or not isinstance(profiles, list)
        or len(profiles) != role_count
        or profile_names != tuple(sorted(set(profile_names)))
    ):
        raise DeployError("deployment role receipt identity is invalid", error_code="receipt-corruption")
    for relative, record in blobs.items():
        if (
            not isinstance(record, dict)
            or set(record) != {"git_oid", "sha256"}
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(record.get("git_oid", "")))
            or not FINGERPRINT_RE.fullmatch(str(record.get("sha256", "")))
        ):
            raise DeployError("deployment role blob record is invalid", error_code="receipt-corruption")
    for name, record in zip(profile_names, profiles, strict=True):
        expected_path = str(ROLE_GENERATIONS_DIR / generation / f"{name}.toml")
        source = blobs[f"agents/{name}.toml"]
        if (
            not isinstance(record, dict)
            or set(record) != {"name", "config_file", "git_oid", "sha256"}
            or record.get("name") != name
            or record.get("config_file") != expected_path
            or record.get("git_oid") != source["git_oid"]
            or record.get("sha256") != source["sha256"]
        ):
            raise DeployError("deployment role profile record is invalid", error_code="receipt-corruption")
    return value


def load_state(state_directory: int) -> dict[str, Any] | None:
    try:
        descriptor = os.open(
            STATE_FILE.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=state_directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("deployment receipt is unsafe", error_code="receipt-corruption") from exc
    try:
        file_stat = validate_private_regular(
            descriptor, "deployment receipt", error_code="receipt-corruption"
        )
        if file_stat.st_size > RECEIPT_MAX_BYTES:
            raise DeployError("deployment receipt is oversized", error_code="receipt-corruption")
        payload = bytearray()
        while len(payload) <= RECEIPT_MAX_BYTES:
            chunk = os.read(descriptor, min(4096, RECEIPT_MAX_BYTES + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > RECEIPT_MAX_BYTES:
            raise DeployError("deployment receipt is oversized", error_code="receipt-corruption")
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeployError("deployment receipt is unreadable", error_code="receipt-corruption") from exc
    finally:
        os.close(descriptor)
    return validate_deploy_receipt(value)
