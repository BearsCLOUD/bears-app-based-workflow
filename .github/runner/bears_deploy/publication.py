"""Compare-and-swap file publication, rollback, and durable journaled writes."""

from __future__ import annotations

import ctypes
import errno
import os
import secrets
import stat
from typing import Any

from .constants import PLUGIN, RENAME_EXCHANGE, RENAME_NOREPLACE, ROLE_RECEIPT_FILE
from .models import DeployError, FilePublication
from .role_io import (
    matches_snapshot_metadata,
    read_config_at,
    read_config_name_at,
    read_role_receipt_at,
    read_role_receipt_name_at,
    same_config_snapshot,
)


def renameat2(directory: int, source: str, target: str, flags: int) -> None:
    """Invoke Linux renameat2 without falling back to a check-then-replace sequence."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = getattr(libc, "renameat2", None)
    if operation is None:
        raise OSError(errno.ENOSYS, "renameat2 is unavailable")
    operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(directory, os.fsencode(source), directory, os.fsencode(target), flags) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), target)


def write_publication_stage(
    directory: int,
    name: str,
    replacement: bytes,
    mode: int,
    reader: Any,
    label: str,
) -> None:
    existing = reader(directory, name)
    if existing is not None:
        if existing[0] != replacement or stat.S_IMODE(existing[1].st_mode) != mode:
            raise DeployError(f"{label} exchange staging file is ambiguous")
        return
    descriptor = -1
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(name, flags, mode, dir_fd=directory)
        os.fchmod(descriptor, mode)
        written = 0
        while written < len(replacement):
            advanced = os.write(descriptor, replacement[written:])
            if advanced <= 0:
                raise DeployError(f"{label} exchange staging write did not advance")
            written += advanced
        os.fsync(descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def publish_file_cas(
    directory: int,
    target: str,
    exchange_name: str,
    expected: tuple[bytes, os.stat_result] | None,
    replacement: bytes,
    reader: Any,
    label: str,
    *,
    phase: str,
) -> FilePublication:
    current = reader(directory, target)
    if (
        expected is not None
        and current is not None
        and current[0] == replacement
        and same_config_snapshot(expected, current)
    ):
        staged = reader(directory, exchange_name)
        if staged is not None:
            if staged[0] != replacement:
                raise DeployError(f"{label} no-op publication has ambiguous staging data")
            os.unlink(exchange_name, dir_fd=directory)
            os.fsync(directory)
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=current,
            published=current,
            reader=reader,
            label=label,
            retained=False,
            created=False,
        )
    if current is not None and current[0] == replacement:
        retained = reader(directory, exchange_name)
        if expected is None:
            if retained is not None:
                raise DeployError(f"{label} absent-preimage publication retained an unexpected inode")
            return FilePublication(
                directory=directory,
                target=target,
                exchange_name=exchange_name,
                expected=None,
                published=current,
                reader=reader,
                label=label,
                retained=False,
                created=True,
            )
        if retained is None:
            if phase != "committed":
                raise DeployError(f"{label} lost its retained preimage before commit")
            return FilePublication(
                directory=directory,
                target=target,
                exchange_name=exchange_name,
                expected=expected,
                published=current,
                reader=reader,
                label=label,
                retained=False,
                created=False,
            )
        if not same_config_snapshot(expected, retained):
            raise DeployError(f"{label} retained preimage disagrees with its journal")
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=expected,
            published=current,
            reader=reader,
            label=label,
            retained=True,
            created=False,
        )
    if phase != "prepared" or not same_config_snapshot(expected, current):
        raise DeployError(f"{label} is outside the publication transaction")
    mode = stat.S_IMODE(expected[1].st_mode) if expected is not None else 0o600
    write_publication_stage(directory, exchange_name, replacement, mode, reader, label)
    exchanged = False
    try:
        if expected is None:
            renameat2(directory, exchange_name, target, RENAME_NOREPLACE)
        else:
            renameat2(directory, exchange_name, target, RENAME_EXCHANGE)
            exchanged = True
            displaced = reader(directory, exchange_name)
            if not same_config_snapshot(expected, displaced):
                raise DeployError(f"{label} publication displaced an unexpected inode")
        os.fsync(directory)
        published = reader(directory, target)
        if published is None or published[0] != replacement:
            raise DeployError(f"{label} publication is unproven")
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=expected,
            published=published,
            reader=reader,
            label=label,
            retained=expected is not None,
            created=expected is None,
        )
    except Exception as exc:
        if exchanged:
            try:
                renameat2(directory, exchange_name, target, RENAME_EXCHANGE)
                os.fsync(directory)
                exchanged = False
            except Exception as restore_error:
                raise DeployError(
                    f"{label} publication race restoration is unproven",
                    error_code="recovery-failure",
                ) from restore_error
        try:
            staged = reader(directory, exchange_name)
            if staged is not None and staged[0] == replacement:
                os.unlink(exchange_name, dir_fd=directory)
                os.fsync(directory)
        except FileNotFoundError:
            pass
        raise exc


def finalize_publication(publication: FilePublication) -> None:
    current = publication.reader(publication.directory, publication.target)
    if not same_config_snapshot(publication.published, current):
        raise DeployError(f"{publication.label} changed before combined commit finalization")
    if publication.retained:
        retained = publication.reader(publication.directory, publication.exchange_name)
        if not same_config_snapshot(publication.expected, retained):
            raise DeployError(f"{publication.label} retained preimage changed before finalization")
        os.unlink(publication.exchange_name, dir_fd=publication.directory)
        os.fsync(publication.directory)
        publication.retained = False


def rollback_publication(publication: FilePublication) -> None:
    if publication.retained:
        renameat2(
            publication.directory,
            publication.exchange_name,
            publication.target,
            RENAME_EXCHANGE,
        )
        os.fsync(publication.directory)
        displaced = publication.reader(publication.directory, publication.exchange_name)
        restored = publication.reader(publication.directory, publication.target)
        if not same_config_snapshot(publication.published, displaced) or not same_config_snapshot(
            publication.expected, restored
        ):
            renameat2(
                publication.directory,
                publication.exchange_name,
                publication.target,
                RENAME_EXCHANGE,
            )
            os.fsync(publication.directory)
            raise DeployError(
                f"{publication.label} rollback encountered a same-user publication race",
                error_code="recovery-failure",
            )
        os.unlink(publication.exchange_name, dir_fd=publication.directory)
        os.fsync(publication.directory)
        publication.retained = False
        return
    if not publication.created:
        current = publication.reader(publication.directory, publication.target)
        if publication.expected is not None and same_config_snapshot(publication.expected, current):
            return
        raise DeployError(f"{publication.label} finalized preimage cannot be rolled back")
    renameat2(
        publication.directory,
        publication.target,
        publication.exchange_name,
        RENAME_NOREPLACE,
    )
    os.fsync(publication.directory)
    displaced = publication.reader(publication.directory, publication.exchange_name)
    if not same_config_snapshot(publication.published, displaced):
        renameat2(
            publication.directory,
            publication.exchange_name,
            publication.target,
            RENAME_NOREPLACE,
        )
        os.fsync(publication.directory)
        raise DeployError(
            f"{publication.label} rollback encountered a same-user publication race",
            error_code="recovery-failure",
        )
    os.unlink(publication.exchange_name, dir_fd=publication.directory)
    os.fsync(publication.directory)
    publication.created = False


def atomic_config_replace(
    home_fd: int,
    expected: tuple[bytes, os.stat_result] | None,
    replacement: bytes,
) -> tuple[bytes, os.stat_result]:
    publication = publish_file_cas(
        home_fd,
        "config.toml",
        f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        expected,
        replacement,
        read_config_name_at,
        "Codex config",
        phase="prepared",
    )
    finalize_publication(publication)
    return publication.published


def atomic_role_receipt_replace(
    directory: int,
    expected: tuple[bytes, os.stat_result] | None,
    replacement: bytes,
) -> tuple[bytes, os.stat_result]:
    publication = publish_file_cas(
        directory,
        ROLE_RECEIPT_FILE.name,
        f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        expected,
        replacement,
        read_role_receipt_name_at,
        "shared role receipt",
        phase="prepared",
    )
    finalize_publication(publication)
    return publication.published


def rollback_role_receipt(
    directory: int,
    before: tuple[bytes, os.stat_result] | None,
    attempted: bytes,
) -> None:
    current = read_role_receipt_at(directory)
    if same_config_snapshot(before, current):
        return
    if current is None or current[0] != attempted:
        raise DeployError("shared role receipt changed outside the attempted mutation")
    if before is None:
        publication = FilePublication(
            directory=directory,
            target=ROLE_RECEIPT_FILE.name,
            exchange_name=f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.rollback",
            expected=None,
            published=current,
            reader=read_role_receipt_name_at,
            label="shared role receipt",
            retained=False,
            created=True,
        )
        rollback_publication(publication)
    else:
        atomic_role_receipt_replace(directory, current, before[0])


def atomic_config_remove(home_fd: int, expected: tuple[bytes, os.stat_result]) -> None:
    publication = FilePublication(
        directory=home_fd,
        target="config.toml",
        exchange_name=f".config.toml.bears-gateway.{secrets.token_hex(16)}.rollback",
        expected=None,
        published=expected,
        reader=read_config_name_at,
        label="Codex config",
        retained=False,
        created=True,
    )
    rollback_publication(publication)


def rollback_role_config(
    home_fd: int,
    before: tuple[bytes, os.stat_result] | None,
    current: tuple[bytes, os.stat_result],
) -> None:
    if before is None:
        atomic_config_remove(home_fd, current)
    else:
        restored = atomic_config_replace(home_fd, current, before[0])
        if restored[0] != before[0] or stat.S_IMODE(restored[1].st_mode) != stat.S_IMODE(before[1].st_mode):
            raise DeployError("Codex config role rollback is unproven")


def rollback_attempted_config(
    home_fd: int,
    before: tuple[bytes, os.stat_result] | None,
    attempted: bytes,
) -> None:
    current = read_config_at(home_fd)
    if same_config_snapshot(before, current):
        return
    if current is None or current[0] != attempted:
        raise DeployError("Codex config changed outside the attempted role mutation")
    rollback_role_config(home_fd, before, current)


def publish_journaled_file(
    directory: int,
    target: str,
    exchange_name: str,
    preimage: bytes,
    preimage_present: bool,
    preimage_metadata: dict[str, Any] | None,
    replacement: bytes,
    reader: Any,
    label: str,
    *,
    phase: str,
) -> FilePublication:
    current = reader(directory, target)
    current_bytes = None if current is None else current[0]
    expected_bytes = preimage if preimage_present else None
    if current_bytes == expected_bytes:
        if preimage_present and not matches_snapshot_metadata(current, preimage_metadata):
            raise DeployError(f"{label} preimage inode disagrees with its journal")
        if not preimage_present and preimage_metadata is not None:
            raise DeployError(f"{label} absent preimage retains metadata")
        return publish_file_cas(
            directory,
            target,
            exchange_name,
            current if preimage_present else None,
            replacement,
            reader,
            label,
            phase=phase,
        )
    if current_bytes != replacement:
        raise DeployError(f"{label} is outside the journaled publication states")
    if not preimage_present:
        return publish_file_cas(
            directory,
            target,
            exchange_name,
            None,
            replacement,
            reader,
            label,
            phase=phase,
        )
    retained = reader(directory, exchange_name)
    if retained is None:
        if phase != "committed":
            raise DeployError(f"{label} prepared transaction lost its retained preimage")
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=None,
            published=current,
            reader=reader,
            label=label,
            retained=False,
            created=False,
        )
    if retained[0] != preimage or not matches_snapshot_metadata(retained, preimage_metadata):
        raise DeployError(f"{label} retained preimage is not the journaled inode")
    return publish_file_cas(
        directory,
        target,
        exchange_name,
        retained,
        replacement,
        reader,
        label,
        phase=phase,
    )
