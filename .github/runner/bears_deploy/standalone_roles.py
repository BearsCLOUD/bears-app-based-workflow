"""Secure standalone custom-agent publication under the fixed Codex home.

Entry points: ``reconcile_standalone_roles`` and ``clear_standalone_roles``.
Boundary: mutate only role files owned by the shared plugin receipt; preserve
unrelated custom-agent files and reject linked or ambiguous targets.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets
import stat
from typing import Any

from .constants import (
    FINGERPRINT_RE,
    LEGACY_ROLE_RECEIPT_SCHEMA,
    PLUGIN,
    PROFILE_MAX_BYTES,
    ROLE_RECEIPT_SCHEMA,
)
from .models import DeployError, FilePublication
from .publication import finalize_publication, publish_file_cas, rollback_publication
from .role_profiles import strict_json_loads


AGENTS_DIRECTORY = "agents"


def _profile_filename(name: str) -> str:
    if (
        not name
        or len(name) > 64
        or name in {".", ".."}
        or not all(
            character.isascii() and (character.isalnum() or character in "_-")
            for character in name
        )
    ):
        raise DeployError("standalone role name is not a safe filename")
    return f"{name}.toml"


def open_standalone_agents_directory(home_fd: int, *, create: bool) -> int | None:
    if create:
        try:
            os.mkdir(AGENTS_DIRECTORY, 0o700, dir_fd=home_fd)
            os.fsync(home_fd)
        except FileExistsError:
            pass
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        directory = os.open(AGENTS_DIRECTORY, flags, dir_fd=home_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("standalone Codex agents directory is missing or unsafe") from exc
    directory_stat = os.fstat(directory)
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or directory_stat.st_uid != os.geteuid()
        or stat.S_IMODE(directory_stat.st_mode) & 0o022
    ):
        os.close(directory)
        raise DeployError("standalone Codex agents directory is unsafe")
    return directory


def read_standalone_profile_at(
    directory: int,
    filename: str,
) -> tuple[bytes, os.stat_result] | None:
    descriptor = -1
    try:
        descriptor = os.open(
            filename,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("standalone role profile is missing or unsafe") from exc
    try:
        profile_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(profile_stat.st_mode)
            or profile_stat.st_nlink != 1
            or profile_stat.st_uid != os.geteuid()
            or stat.S_IMODE(profile_stat.st_mode) != 0o600
            or profile_stat.st_size > PROFILE_MAX_BYTES
        ):
            raise DeployError("standalone role profile is not a bounded private regular file")
        data = bytearray()
        while len(data) <= PROFILE_MAX_BYTES:
            chunk = os.read(
                descriptor,
                min(64 * 1024, PROFILE_MAX_BYTES + 1 - len(data)),
            )
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > PROFILE_MAX_BYTES:
            raise DeployError("standalone role profile is oversized")
        return bytes(data), profile_stat
    finally:
        os.close(descriptor)


def receipted_profile_digests(receipt: bytes | None) -> dict[str, str]:
    if not receipt:
        return {}
    value = strict_json_loads(receipt, "standalone role ownership receipt")
    if not isinstance(value, dict):
        raise DeployError("standalone role ownership receipt has an unsupported shape")
    if value.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA:
        return {}
    if value.get("schema") != ROLE_RECEIPT_SCHEMA or value.get("plugin") != PLUGIN:
        raise DeployError("standalone role ownership receipt identity is invalid")
    if value.get("status") != "installed":
        return {}
    profiles = value.get("managed_profiles")
    if not isinstance(profiles, list):
        raise DeployError("standalone role ownership receipt omits its profile catalog")
    owned: dict[str, str] = {}
    for record in profiles:
        if not isinstance(record, dict) or set(record) != {"name", "config_file", "sha256"}:
            raise DeployError("standalone role ownership entry is invalid")
        name = record["name"]
        config_file = record["config_file"]
        digest = record["sha256"]
        if (
            not isinstance(name, str)
            or name in owned
            or not isinstance(config_file, str)
            or not Path(config_file).is_absolute()
            or not isinstance(digest, str)
            or not FINGERPRINT_RE.fullmatch(digest)
        ):
            raise DeployError("standalone role ownership catalog is ambiguous")
        _profile_filename(name)
        owned[name] = digest
    if tuple(owned) != tuple(sorted(owned)):
        raise DeployError("standalone role ownership catalog is not canonical")
    return owned


def _remove_exact_profile(directory: int, name: str, expected_digest: str) -> None:
    filename = _profile_filename(name)
    current = read_standalone_profile_at(directory, filename)
    if current is None:
        return
    if not secrets.compare_digest(hashlib.sha256(current[0]).hexdigest(), expected_digest):
        raise DeployError(f"standalone role profile {name} drifted from owned content")
    publication = FilePublication(
        directory=directory,
        target=filename,
        exchange_name=f".{PLUGIN}.{name}.{secrets.token_hex(16)}.remove",
        expected=None,
        published=current,
        reader=read_standalone_profile_at,
        label=f"standalone role profile {name}",
        retained=False,
        created=True,
    )
    rollback_publication(publication)


def _remove_admitted_staging_files(
    directory: int,
    name: str,
    admitted_digests: set[str],
) -> None:
    """Remove crash-retained CAS preimages while holding the role config lock."""
    prefix = f".{PLUGIN}.{name}."
    for filename in os.listdir(directory):
        if not filename.startswith(prefix) or not filename.endswith(".staging"):
            continue
        snapshot = read_standalone_profile_at(directory, filename)
        if snapshot is None:
            continue
        digest = hashlib.sha256(snapshot[0]).hexdigest()
        if digest not in admitted_digests:
            raise DeployError(f"standalone role staging file {name} has ambiguous content")
        os.unlink(filename, dir_fd=directory)
        os.fsync(directory)


def reconcile_standalone_roles(
    home_fd: int,
    bundle: dict[str, Any],
    receipt_preimage: bytes | None,
) -> dict[str, str]:
    previous = receipted_profile_digests(receipt_preimage)
    desired_names = tuple(bundle["role_names"])
    desired = {
        name: str(bundle["profiles"][name]["sha256"])
        for name in desired_names
    }
    directory = open_standalone_agents_directory(home_fd, create=True)
    if directory is None:
        raise DeployError("standalone Codex agents directory was not created")
    try:
        for name in desired_names:
            filename = _profile_filename(name)
            replacement = bundle["profiles"][name]["data"]
            admitted = {desired[name]}
            if name in previous:
                admitted.add(previous[name])
            _remove_admitted_staging_files(directory, name, admitted)
            current = read_standalone_profile_at(directory, filename)
            if current is not None:
                current_digest = hashlib.sha256(current[0]).hexdigest()
                if current_digest not in admitted:
                    raise DeployError(f"standalone role profile {name} collides with unowned content")
            publication = publish_file_cas(
                directory,
                filename,
                f".{PLUGIN}.{name}.{secrets.token_hex(16)}.staging",
                current,
                replacement,
                read_standalone_profile_at,
                f"standalone role profile {name}",
                phase="prepared",
            )
            finalize_publication(publication)

        for name in sorted(set(previous).difference(desired)):
            _remove_exact_profile(directory, name, previous[name])

        catalog: dict[str, str] = {}
        for name in desired_names:
            filename = _profile_filename(name)
            snapshot = read_standalone_profile_at(directory, filename)
            if (
                snapshot is None
                or not secrets.compare_digest(
                    hashlib.sha256(snapshot[0]).hexdigest(),
                    desired[name],
                )
            ):
                raise DeployError("standalone role catalog did not converge")
            catalog[name] = f"$CODEX_HOME/{AGENTS_DIRECTORY}/{filename}"
        return catalog
    finally:
        os.close(directory)


def clear_standalone_roles(home_fd: int, receipt_preimage: bytes | None) -> None:
    owned = receipted_profile_digests(receipt_preimage)
    if not owned:
        return
    directory = open_standalone_agents_directory(home_fd, create=False)
    if directory is None:
        return
    try:
        for name in sorted(owned):
            _remove_exact_profile(directory, name, owned[name])
    finally:
        os.close(directory)
