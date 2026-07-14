"""One-release retirement path for the legacy CD-managed AGENTS.md block.

This module never creates or refreshes instructions. It only removes an exact
receipted legacy block and retains the old transaction shape for crash recovery.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
from pathlib import Path
import stat
from typing import Any

from .constants import CODEX_HOME, GRAPH_MAX_BYTES
from .intent_io import load_intent, save_instruction_removal_intent
from .models import DeployError, FilePublication
from .publication import finalize_publication, publish_file_cas, rollback_publication

BEGIN = b"<!-- >>> bears-app-based-workflow graph behavior (managed by CD) -->"
END = b"<!-- <<< bears-app-based-workflow graph behavior (managed by CD) -->"


def _target() -> Path:
    """Resolve the target at call time so recovery cannot retain another home."""
    return CODEX_HOME / "AGENTS.md"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_regular(path: Path, *, missing: bool = False) -> bytes | None:
    if path.is_symlink():
        raise DeployError(f"{path.name} must not be a symlink", error_code="receipt-corruption")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if missing:
            return None
        raise DeployError(f"{path.name} is missing")
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > GRAPH_MAX_BYTES:
            raise DeployError(
                f"{path.name} is not a bounded regular file",
                error_code="receipt-corruption",
            )
        data = bytearray()
        while len(data) <= GRAPH_MAX_BYTES:
            chunk = os.read(descriptor, min(8192, GRAPH_MAX_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > GRAPH_MAX_BYTES:
            raise DeployError(f"{path.name} is oversized", error_code="receipt-corruption")
        return bytes(data)
    finally:
        os.close(descriptor)


def _read_regular_at(directory: int, name: str) -> tuple[bytes, os.stat_result] | None:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("AGENTS.md is missing or unsafe", error_code="receipt-corruption") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > GRAPH_MAX_BYTES:
            raise DeployError(
                "AGENTS.md is not a bounded regular file",
                error_code="receipt-corruption",
            )
        data = bytearray()
        while len(data) <= GRAPH_MAX_BYTES:
            chunk = os.read(descriptor, min(8192, GRAPH_MAX_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > GRAPH_MAX_BYTES:
            raise DeployError("AGENTS.md is oversized", error_code="receipt-corruption")
        return bytes(data), info
    finally:
        os.close(descriptor)


def _block_bounds(data: bytes) -> tuple[int, int] | None:
    if data.count(BEGIN) != data.count(END) or data.count(BEGIN) > 1:
        raise DeployError(
            "legacy graph instruction markers are malformed or duplicated",
            error_code="receipt-corruption",
        )
    if BEGIN not in data:
        return None
    start = data.index(BEGIN)
    end_marker = data.index(END)
    if end_marker < start:
        raise DeployError(
            "legacy graph instruction markers are reversed",
            error_code="receipt-corruption",
        )
    end = end_marker + len(END)
    if end < len(data) and data[end : end + 1] == b"\n":
        end += 1
    return start, end


def _without_receipted_block(current: bytes, previous: dict[str, Any]) -> bytes:
    bounds = _block_bounds(current)
    if bounds is None:
        return current
    start, end = bounds
    block = current[start:end]
    if _digest(block) != previous.get("graph_block_sha256"):
        raise DeployError(
            "legacy graph instruction block drifted from its receipt",
            error_code="receipt-corruption",
        )
    return _without_block(current, bounds, previous)


def _without_block(
    current: bytes,
    bounds: tuple[int, int],
    previous: dict[str, Any],
) -> bytes:
    start, end = bounds
    before, after = current[:start], current[end:]
    if previous.get("graph_separator_added"):
        if not before.endswith(b"\n"):
            raise DeployError(
                "legacy graph instruction separator drifted from its receipt",
                error_code="receipt-corruption",
            )
        before = before[:-1]
    return before + after


def _transaction_exchange_name(
    original: bytes,
    original_present: bool,
    desired: bytes,
    desired_present: bool,
) -> str:
    """Derive one retry-stable private name from the journaled state pair."""
    digest = hashlib.sha256()
    for payload, present in (
        (original, original_present),
        (desired, desired_present),
    ):
        digest.update(b"\x01" if present else b"\x00")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return f".AGENTS.md.bears-retirement.{digest.hexdigest()}.exchange"


def _publish(
    payload: bytes,
    *,
    expected: bytes | None = None,
    expected_present: bool | None = None,
    exchange_name: str,
) -> None:
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    if CODEX_HOME.is_symlink() or not CODEX_HOME.is_dir():
        raise DeployError("CODEX_HOME is unsafe")
    directory = os.open(CODEX_HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        current = _read_regular_at(directory, "AGENTS.md")
        if expected_present is not None and (
            (current is not None) != expected_present
            or (b"" if current is None else current[0]) != (expected or b"")
        ):
            raise DeployError("AGENTS.md changed before publication", error_code="receipt-corruption")
        publication = publish_file_cas(
            directory,
            "AGENTS.md",
            exchange_name,
            current,
            payload,
            _read_regular_at,
            "AGENTS.md",
            phase="prepared",
        )
        finalize_publication(publication)
    finally:
        os.close(directory)


def _remove_expected(expected: bytes, *, exchange_name: str) -> None:
    directory = os.open(CODEX_HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        current = _read_regular_at(directory, "AGENTS.md")
        if current is None or current[0] != expected:
            raise DeployError("AGENTS.md changed before removal", error_code="receipt-corruption")
        rollback_publication(
            FilePublication(
                directory=directory,
                target="AGENTS.md",
                exchange_name=exchange_name,
                expected=None,
                published=current,
                reader=_read_regular_at,
                label="AGENTS.md",
                retained=False,
                created=True,
            )
        )
    finally:
        os.close(directory)


def _transaction_state(
    transaction: dict[str, Any],
) -> tuple[bytes, bool, bytes, bool]:
    try:
        return (
            base64.b64decode(transaction["original_b64"], validate=True),
            bool(transaction["original_present"]),
            base64.b64decode(transaction["desired_b64"], validate=True),
            bool(transaction.get("desired_present", True)),
        )
    except (binascii.Error, KeyError, TypeError, ValueError) as exc:
        raise DeployError(
            "legacy instruction transaction is invalid",
            error_code="receipt-corruption",
        ) from exc


def _transaction_bytes(transaction: dict[str, Any]) -> tuple[bytes, bytes]:
    """Return journal payloads for compatibility with bounded diagnostics."""
    original, _, desired, _ = _transaction_state(transaction)
    return original, desired


def _matches_state(observed: bytes | None, payload: bytes, present: bool) -> bool:
    return (observed is not None) == present and (not present or observed == payload)


def _finalize_transaction_exchange(
    exchange_name: str,
    *,
    source: bytes,
    source_present: bool,
    target: bytes,
    target_present: bool,
) -> None:
    """Erase only the exact retained source inode after a proven target commit."""
    directory = os.open(CODEX_HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        current = _read_regular_at(directory, "AGENTS.md")
        observed = None if current is None else current[0]
        if not _matches_state(observed, target, target_present):
            raise DeployError(
                "AGENTS.md changed before legacy transaction finalization",
                error_code="receipt-corruption",
            )
        retained = _read_regular_at(directory, exchange_name)
        if retained is None:
            return
        if not source_present or retained[0] != source:
            raise DeployError(
                "legacy instruction exchange disagrees with its journal",
                error_code="receipt-corruption",
            )
        os.unlink(exchange_name, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)


def _apply_state(
    observed: bytes | None,
    original: bytes,
    original_present: bool,
    desired: bytes,
    desired_present: bool,
    *,
    restore: bool = False,
) -> None:
    source, source_present, target, target_present = (
        (desired, desired_present, original, original_present)
        if restore
        else (original, original_present, desired, desired_present)
    )
    exchange_name = _transaction_exchange_name(
        original,
        original_present,
        desired,
        desired_present,
    )
    if _matches_state(observed, target, target_present):
        _finalize_transaction_exchange(
            exchange_name,
            source=source,
            source_present=source_present,
            target=target,
            target_present=target_present,
        )
        return
    if not _matches_state(observed, source, source_present):
        raise DeployError(
            "AGENTS.md is outside the journaled legacy instruction transaction",
            error_code="receipt-corruption",
        )
    if target_present:
        _publish(
            target,
            expected=source,
            expected_present=source_present,
            exchange_name=exchange_name,
        )
    elif source_present:
        _remove_expected(source, exchange_name=exchange_name)


def retire_graph_instructions(
    state_directory: int,
    previous: dict[str, Any] | None,
) -> None:
    """Remove one exact v3/v4 block; graphless states never access AGENTS.md."""
    if previous is None or not previous.get("graph_block_sha256"):
        return
    intent = load_intent(state_directory)
    if intent is None:
        raise DeployError("promotion intent disappeared before legacy instruction retirement")

    observed = _read_regular(_target(), missing=True)
    transaction = intent.get("graph_transaction")
    if isinstance(transaction, dict):
        original, original_present, desired, desired_present = _transaction_state(transaction)
        desired_bounds = _block_bounds(desired)
        if desired_bounds is not None:
            # Convert an interrupted pre-v5 injection journal directly into a
            # removal journal. The live v4 receipt can bind either the old or
            # refreshed block depending on where the prior gateway crashed.
            if _matches_state(observed, original, original_present):
                current = original
            elif _matches_state(observed, desired, desired_present):
                current = desired
            else:
                raise DeployError(
                    "AGENTS.md is outside the journaled legacy injection transaction",
                    error_code="receipt-corruption",
                )
            if current == original:
                clean = _without_receipted_block(original, previous)
            else:
                start, end = desired_bounds
                if _digest(desired[start:end]) == previous.get("graph_block_sha256"):
                    clean = _without_receipted_block(desired, previous)
                else:
                    clean = _without_receipted_block(original, previous)
                    if _without_block(desired, desired_bounds, previous) != clean:
                        raise DeployError(
                            "legacy injection journal changed unmanaged AGENTS.md bytes",
                            error_code="receipt-corruption",
                        )
            updated = save_instruction_removal_intent(
                state_directory,
                intent,
                original=current,
                original_present=observed is not None,
                desired=clean,
                desired_present=original_present,
            )
            converted = updated["graph_transaction"]
            assert isinstance(converted, dict)
            converted_original, converted_original_present, converted_desired, converted_desired_present = (
                _transaction_state(converted)
            )
            _apply_state(
                observed,
                converted_original,
                converted_original_present,
                converted_desired,
                converted_desired_present,
            )
            return
        else:
            expected_desired = _without_receipted_block(original, previous)
            if desired != expected_desired:
                raise DeployError(
                    "legacy instruction removal journal has an invalid desired state",
                    error_code="receipt-corruption",
                )
            _apply_state(
                observed,
                original,
                original_present,
                desired,
                desired_present,
            )
            return

    current = observed or b""
    desired = _without_receipted_block(current, previous)
    if desired == current:
        return
    updated = save_instruction_removal_intent(
        state_directory,
        intent,
        original=current,
        original_present=observed is not None,
        desired=desired,
        desired_present=observed is not None,
    )
    transaction = updated["graph_transaction"]
    assert isinstance(transaction, dict)
    original, original_present, desired, desired_present = _transaction_state(transaction)
    _apply_state(
        observed,
        original,
        original_present,
        desired,
        desired_present,
    )


def restore_graph_preimage(intent: dict[str, Any]) -> None:
    """Rollback only an exact journaled legacy AGENTS.md transaction."""
    transaction = intent.get("graph_transaction")
    if not isinstance(transaction, dict):
        return
    original, original_present, desired, desired_present = _transaction_state(transaction)
    observed = _read_regular(_target(), missing=True)
    _apply_state(
        observed,
        original,
        original_present,
        desired,
        desired_present,
        restore=True,
    )


def converge_graph_absence(
    state: dict[str, Any] | None,
    intent: dict[str, Any],
) -> None:
    """Converge removal fallback without resurrecting a journaled legacy block."""
    transaction = intent.get("graph_transaction")
    if isinstance(transaction, dict):
        original, original_present, desired, desired_present = _transaction_state(transaction)
        if _block_bounds(desired) is None:
            observed = _read_regular(_target(), missing=True)
            _apply_state(
                observed,
                original,
                original_present,
                desired,
                desired_present,
            )
            return
        restore_graph_preimage(intent)
        prior = intent.get("previous_receipt")
        if isinstance(prior, dict) and prior.get("graph_block_sha256"):
            state = prior
    elif state is None or not state.get("graph_block_sha256"):
        prior = intent.get("previous_receipt")
        if isinstance(prior, dict) and prior.get("graph_block_sha256"):
            state = prior
    remove_graph_instructions(state)


def remove_graph_instructions(state: dict[str, Any] | None) -> None:
    """Remove an exact receipted legacy block during plugin removal."""
    if state is None or not state.get("graph_block_sha256"):
        return
    exchange_name = (
        ".AGENTS.md.bears-uninstall."
        f"{state['graph_block_sha256']}.exchange"
    )
    current = _read_regular(_target(), missing=True)
    retained = _read_regular(CODEX_HOME / exchange_name, missing=True)
    if retained is not None:
        if current is None:
            raise DeployError(
                "legacy uninstall exchange exists without AGENTS.md",
                error_code="receipt-corruption",
            )
        if _block_bounds(current) is None:
            if _without_receipted_block(retained, state) != current:
                raise DeployError(
                    "legacy uninstall exchange disagrees with its receipt",
                    error_code="receipt-corruption",
                )
            _finalize_transaction_exchange(
                exchange_name,
                source=retained,
                source_present=True,
                target=current,
                target_present=True,
            )
            return
    if current is None:
        return
    desired = _without_receipted_block(current, state)
    if desired != current:
        if retained is not None and retained != desired:
            raise DeployError(
                "legacy uninstall staging data disagrees with its receipt",
                error_code="receipt-corruption",
            )
        _publish(
            desired,
            expected=current,
            expected_present=True,
            exchange_name=exchange_name,
        )
