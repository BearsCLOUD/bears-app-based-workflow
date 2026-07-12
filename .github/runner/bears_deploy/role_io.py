"""Locked role config and receipt reads, parsing, snapshots, and receipt construction."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any

from .constants import (
    CODEX_HOME,
    CONFIG_LOCK_NAME,
    CONFIG_MAX_BYTES,
    FINGERPRINT_RE,
    LEGACY_ROLE_RECEIPT_SCHEMA,
    PLUGIN,
    PROFILE_MAX_BYTES,
    ROLE_RECEIPT_FILE,
    ROLE_RECEIPT_MAX_BYTES,
    ROLE_RECEIPT_SCHEMA,
    VERSION_RE,
)
from .marketplace import read_regular_bytes
from .models import DeployError
from .role_profiles import (
    config_without_owned_roles,
    parse_config,
    strict_json_loads,
    validate_legacy_registration_payload,
    validate_legacy_role_receipt,
)


def open_role_config_lock() -> tuple[int, int]:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        home_fd = os.open(CODEX_HOME, flags)
        home_stat = os.fstat(home_fd)
        if (
            not stat.S_ISDIR(home_stat.st_mode)
            or home_stat.st_uid != os.geteuid()
            or stat.S_IMODE(home_stat.st_mode) & 0o022
        ):
            raise DeployError("fixed Codex home is unsafe")
        lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        lock_fd = os.open(CONFIG_LOCK_NAME, lock_flags, 0o600, dir_fd=home_fd)
        lock_stat = os.fstat(lock_fd)
        if (
            not stat.S_ISREG(lock_stat.st_mode)
            or lock_stat.st_nlink != 1
            or lock_stat.st_uid != os.geteuid()
            or stat.S_IMODE(lock_stat.st_mode) != 0o600
        ):
            raise DeployError("role config coordination lock is unsafe")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return home_fd, lock_fd
    except Exception:
        if "lock_fd" in locals():
            os.close(lock_fd)
        if "home_fd" in locals():
            os.close(home_fd)
        raise


def read_config_name_at(home_fd: int, name: str) -> tuple[bytes, os.stat_result] | None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(name, flags, dir_fd=home_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("Codex config is missing or unsafe") from exc
    try:
        config_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(config_stat.st_mode)
            or config_stat.st_nlink != 1
            or config_stat.st_uid != os.geteuid()
            or stat.S_IMODE(config_stat.st_mode) & 0o077
            or config_stat.st_size > CONFIG_MAX_BYTES
        ):
            raise DeployError("Codex config is not a bounded private regular file")
        data = b""
        while True:
            chunk = os.read(descriptor, min(64 * 1024, CONFIG_MAX_BYTES + 1 - len(data)))
            if not chunk:
                break
            data += chunk
            if len(data) > CONFIG_MAX_BYTES:
                raise DeployError("Codex config is oversized")
        return data, config_stat
    finally:
        os.close(descriptor)


def read_config_at(home_fd: int) -> tuple[bytes, os.stat_result] | None:
    return read_config_name_at(home_fd, "config.toml")


def open_role_receipt_directory(home_fd: int) -> int:
    try:
        os.mkdir("state", 0o700, dir_fd=home_fd)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(
            "state",
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=home_fd,
        )
        directory_stat = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != os.geteuid()
            or stat.S_IMODE(directory_stat.st_mode) & 0o077
        ):
            raise DeployError("shared role receipt directory is unsafe")
        return descriptor
    except Exception:
        if "descriptor" in locals():
            os.close(descriptor)
        raise


def read_role_receipt_name_at(directory: int, name: str) -> tuple[bytes, os.stat_result] | None:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("shared role receipt is missing or unsafe") from exc
    try:
        receipt_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(receipt_stat.st_mode)
            or receipt_stat.st_nlink != 1
            or receipt_stat.st_uid != os.geteuid()
            or stat.S_IMODE(receipt_stat.st_mode) != 0o600
            or receipt_stat.st_size > ROLE_RECEIPT_MAX_BYTES
        ):
            raise DeployError("shared role receipt is not a bounded private regular file")
        data = bytearray()
        while len(data) <= ROLE_RECEIPT_MAX_BYTES:
            chunk = os.read(
                descriptor,
                min(4096, ROLE_RECEIPT_MAX_BYTES + 1 - len(data)),
            )
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > ROLE_RECEIPT_MAX_BYTES:
            raise DeployError("shared role receipt is oversized")
        return bytes(data), receipt_stat
    finally:
        os.close(descriptor)


def read_role_receipt_at(directory: int) -> tuple[bytes, os.stat_result] | None:
    return read_role_receipt_name_at(directory, ROLE_RECEIPT_FILE.name)


def parse_role_receipt(snapshot: tuple[bytes, os.stat_result] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    value = strict_json_loads(snapshot[0], "shared role receipt")
    if isinstance(value, dict) and value.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA:
        return validate_legacy_role_receipt(value, snapshot[0])
    required = {
        "schema",
        "plugin",
        "version",
        "status",
        "changed",
        "role_count",
        "managed_digest",
        "managed_joiner_added",
        "managed_profiles",
        "archives",
    }
    status = value.get("status") if isinstance(value, dict) else None
    role_count = value.get("role_count") if isinstance(value, dict) else None
    digest = value.get("managed_digest") if isinstance(value, dict) else None
    profiles = value.get("managed_profiles") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("schema") != ROLE_RECEIPT_SCHEMA
        or set(value) != required
        or value.get("plugin") != PLUGIN
        or not VERSION_RE.fullmatch(str(value.get("version", "")))
        or status not in {"installed", "uninstalled"}
        or not isinstance(value.get("changed"), bool)
        or not isinstance(role_count, int)
        or isinstance(role_count, bool)
        or not isinstance(value.get("managed_joiner_added"), bool)
        or (profiles is not None and not isinstance(profiles, list))
        or not isinstance(value.get("archives"), list)
    ):
        raise DeployError("shared role receipt identity is invalid")
    if profiles is None or not isinstance(role_count, int) or isinstance(role_count, bool):
        raise DeployError("shared role receipt role catalog is invalid")
    if status == "installed":
        if (
            not 1 <= role_count <= 64
            or len(profiles) != role_count
            or not isinstance(digest, str)
            or not FINGERPRINT_RE.fullmatch(digest)
        ):
            raise DeployError("installed shared role receipt digest is invalid")
    elif not 0 <= role_count <= 64 or digest is not None or profiles:
        raise DeployError("uninstalled shared role receipt retains managed ownership")
    return value


def validate_owned_role_state(
    config: bytes,
    receipt: tuple[bytes, os.stat_result] | None,
) -> dict[str, Any] | None:
    outside, span = config_without_owned_roles(config)
    del outside
    value = parse_role_receipt(receipt)
    if span is None:
        if value is not None and value.get("status") == "installed":
            raise DeployError("shared role receipt claims a missing managed block")
        return value
    if value is None or value.get("status") != "installed":
        raise DeployError("managed role block has no shared ownership receipt")
    if value.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA:
        if receipt is None:
            raise DeployError("exact legacy shared role receipt is missing")
        validate_legacy_registration_payload(config, receipt[0])
        return value
    block = config[span[0] : span[1]]
    digest = hashlib.sha256(block).hexdigest()
    records = value.get("managed_profiles")
    expected_names = tuple(
        record.get("name")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("name"), str)
    ) if isinstance(records, list) else ()
    if (
        not secrets.compare_digest(str(value.get("managed_digest")), digest)
        or not isinstance(value.get("role_count"), int)
        or isinstance(value.get("role_count"), bool)
        or value["role_count"] != len(expected_names)
        or not 1 <= len(expected_names) <= 64
        or expected_names != tuple(sorted(set(expected_names)))
    ):
        raise DeployError("managed role block disagrees with its shared receipt")
    block_agents = parse_config(block, "managed role block").get("agents")
    if not isinstance(block_agents, dict) or set(block_agents) != set(expected_names):
        raise DeployError("managed role block is not the exact receipted role catalog")
    if records is None:
        raise DeployError("current shared role receipt omits profile ownership")
    if not isinstance(records, list) or [record.get("name") for record in records if isinstance(record, dict)] != list(expected_names):
        raise DeployError("shared role receipt profile catalog is not canonical")
    recorded: dict[str, tuple[str, str]] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"name", "config_file", "sha256"}:
            raise DeployError("shared role receipt profile entry is invalid")
        name, path, content_digest = record["name"], record["config_file"], record["sha256"]
        if (
            not isinstance(name, str)
            or name not in expected_names
            or name in recorded
            or not isinstance(path, str)
            or not Path(path).is_absolute()
            or not isinstance(content_digest, str)
            or not FINGERPRINT_RE.fullmatch(content_digest)
        ):
            raise DeployError("shared role receipt profile ownership is invalid")
        row = block_agents.get(name)
        if not isinstance(row, dict) or row != {"config_file": path}:
            raise DeployError("shared role receipt does not own the managed registration")
        data = read_regular_bytes(Path(path), f"owned role profile {name}", PROFILE_MAX_BYTES)
        if not secrets.compare_digest(hashlib.sha256(data).hexdigest(), content_digest):
            raise DeployError("owned role profile content drifted from its shared receipt")
        recorded[name] = (path, content_digest)
    if set(recorded) != set(block_agents):
        raise DeployError("managed role block has ambiguous shared ownership")
    return value


def build_role_receipt(
    version: str,
    block: bytes,
    catalog: dict[str, str],
    bundle: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    added_joiner: bool,
) -> bytes:
    value = {
        "schema": ROLE_RECEIPT_SCHEMA,
        "plugin": PLUGIN,
        "version": version,
        "status": "installed",
        "changed": True,
        "role_count": len(catalog),
        "managed_digest": hashlib.sha256(block).hexdigest(),
        "managed_joiner_added": added_joiner,
        "managed_profiles": [
            {
                "name": name,
                "config_file": catalog[name],
                "sha256": bundle["profiles"][name]["sha256"],
            }
            for name in sorted(catalog)
        ],
        "archives": [] if previous is None else previous["archives"],
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_uninstalled_role_receipt(previous: dict[str, Any]) -> bytes:
    value = {
        "schema": ROLE_RECEIPT_SCHEMA,
        "plugin": PLUGIN,
        "version": previous["version"],
        "status": "uninstalled",
        "changed": True,
        "role_count": 0,
        "managed_digest": None,
        "managed_joiner_added": False,
        "managed_profiles": [],
        "archives": previous["archives"],
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def same_config_snapshot(
    left: tuple[bytes, os.stat_result] | None,
    right: tuple[bytes, os.stat_result] | None,
) -> bool:
    if left is None or right is None:
        return left is right
    left_stat, right_stat = left[1], right[1]
    return left[0] == right[0] and (
        left_stat.st_dev,
        left_stat.st_ino,
        left_stat.st_mode,
        left_stat.st_uid,
        left_stat.st_gid,
        left_stat.st_nlink,
        left_stat.st_size,
        left_stat.st_mtime_ns,
    ) == (
        right_stat.st_dev,
        right_stat.st_ino,
        right_stat.st_mode,
        right_stat.st_uid,
        right_stat.st_gid,
        right_stat.st_nlink,
        right_stat.st_size,
        right_stat.st_mtime_ns,
    )


def snapshot_metadata(snapshot: tuple[bytes, os.stat_result] | None) -> dict[str, int] | None:
    if snapshot is None:
        return None
    file_stat = snapshot[1]
    return {
        "dev": file_stat.st_dev,
        "ino": file_stat.st_ino,
        "mode": file_stat.st_mode,
        "uid": file_stat.st_uid,
        "gid": file_stat.st_gid,
        "nlink": file_stat.st_nlink,
        "size": file_stat.st_size,
        "mtime_ns": file_stat.st_mtime_ns,
    }


def matches_snapshot_metadata(
    snapshot: tuple[bytes, os.stat_result] | None,
    expected: dict[str, Any] | None,
) -> bool:
    return snapshot_metadata(snapshot) == expected
