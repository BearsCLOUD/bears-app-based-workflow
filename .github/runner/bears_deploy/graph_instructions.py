"""Fail-closed transactional ownership of the managed CODEX_HOME/AGENTS.md block."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets
import stat
from typing import Any

from .constants import CODEX_HOME, GRAPH_INSTRUCTIONS_TEMPLATE, GRAPH_MAX_BYTES, MARKETPLACE_ROOT
from .intent_io import load_intent, save_graph_intent
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
            raise DeployError(f"{path.name} is not a bounded regular file", error_code="receipt-corruption")
        data = bytearray()
        while len(data) <= GRAPH_MAX_BYTES:
            chunk = os.read(descriptor, min(8192, GRAPH_MAX_BYTES + 1 - len(data)))
            if not chunk: break
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
            raise DeployError("AGENTS.md is not a bounded regular file", error_code="receipt-corruption")
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
        raise DeployError("managed graph instruction markers are malformed or duplicated", error_code="receipt-corruption")
    if BEGIN not in data:
        return None
    start = data.index(BEGIN)
    end_marker = data.index(END)
    if end_marker < start:
        raise DeployError("managed graph instruction markers are reversed", error_code="receipt-corruption")
    end = end_marker + len(END)
    if end < len(data) and data[end:end + 1] == b"\n": end += 1
    return start, end


def _template() -> bytes:
    path = MARKETPLACE_ROOT / GRAPH_INSTRUCTIONS_TEMPLATE
    value = _read_regular(path)
    assert value is not None
    bounds = _block_bounds(value)
    if bounds != (0, len(value)):
        raise DeployError("pinned graph instruction template must contain exactly one complete block")
    return value


def _desired(current: bytes, template: bytes, previous: dict[str, Any] | None) -> tuple[bytes, bool]:
    bounds = _block_bounds(current)
    if bounds is not None:
        start, end = bounds
        block = current[start:end]
        expected = None if previous is None else previous.get("graph_block_sha256")
        if expected is None or _digest(block) != expected:
            raise DeployError("managed graph instruction block drifted from its receipt", error_code="receipt-corruption")
        if previous.get("graph_separator_added", False) and (start == 0 or current[start - 1:start] != b"\n"):
            raise DeployError("managed graph instruction separator drifted from its receipt", error_code="receipt-corruption")
        return current[:start] + template + current[end:], bool(previous.get("graph_separator_added", False))
    if previous is not None and previous.get("graph_block_sha256"):
        raise DeployError("receipted graph instruction block is missing", error_code="receipt-corruption")
    # The one byte immediately before the managed block is always CD-owned.
    # Recording that boolean is therefore sufficient for exact uninstall.
    separator = bool(current)
    joiner = b"\n" if current else b""
    return current + joiner + template, separator


def _publish(payload: bytes, *, expected: bytes | None = None, expected_present: bool | None = None) -> None:
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
            f".AGENTS.md.{secrets.token_hex(16)}.exchange",
            current,
            payload,
            _read_regular_at,
            "AGENTS.md",
            phase="prepared",
        )
        finalize_publication(publication)
    finally:
        os.close(directory)


def _remove_expected(expected: bytes) -> None:
    directory = os.open(CODEX_HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        current = _read_regular_at(directory, "AGENTS.md")
        if current is None or current[0] != expected:
            raise DeployError("AGENTS.md changed before removal", error_code="receipt-corruption")
        rollback_publication(
            FilePublication(
                directory=directory,
                target="AGENTS.md",
                exchange_name=f".AGENTS.md.{secrets.token_hex(16)}.remove",
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


def reconcile_graph_instructions(state_directory: int, previous: dict[str, Any] | None) -> dict[str, Any]:
    intent = load_intent(state_directory)
    if intent is None: raise DeployError("promotion intent disappeared before graph reconciliation")
    template = _template(); observed = _read_regular(_target(), missing=True); current = observed or b""
    transaction = intent.get("graph_transaction")
    if isinstance(transaction, dict):
        import base64
        original = base64.b64decode(transaction["original_b64"], validate=True)
        journaled_desired = base64.b64decode(transaction["desired_b64"], validate=True)
        if current == journaled_desired:
            desired = journaled_desired
            original_present = bool(transaction["original_present"])
            separator = bool(previous.get("graph_separator_added", False)) if previous else bool(original_present and original)
        elif current == original:
            desired, separator = _desired(current, template, previous)
            if desired != journaled_desired:
                raise DeployError("graph instruction desired state changed during recovery", error_code="receipt-corruption")
            _publish(desired, expected=current, expected_present=bool(transaction["original_present"]))
        else:
            raise DeployError("AGENTS.md is outside the journaled graph transaction", error_code="receipt-corruption")
    else:
        desired, separator = _desired(current, template, previous)
        save_graph_intent(state_directory, intent, original=current, original_present=observed is not None, desired=desired)
        _publish(desired, expected=current, expected_present=observed is not None)
    bounds = _block_bounds(desired)
    assert bounds is not None
    block = desired[bounds[0]:bounds[1]]
    return {"graph_template_sha256": _digest(template), "graph_block_sha256": _digest(block), "graph_separator_added": separator}


def restore_graph_preimage(intent: dict[str, Any]) -> None:
    transaction = intent.get("graph_transaction")
    if not isinstance(transaction, dict): return
    import base64
    original = base64.b64decode(transaction["original_b64"], validate=True)
    desired = base64.b64decode(transaction["desired_b64"], validate=True)
    current = _read_regular(_target(), missing=True) or b""
    if current == original: return
    if current != desired:
        raise DeployError("AGENTS.md changed during interrupted promotion", error_code="receipt-corruption")
    if transaction["original_present"]:
        _publish(original, expected=current, expected_present=True)
    else:
        _remove_expected(current)


def remove_graph_instructions(state: dict[str, Any] | None) -> None:
    if state is None or not state.get("graph_block_sha256"): return
    current = _read_regular(_target(), missing=True)
    if current is None: raise DeployError("receipted AGENTS.md is missing", error_code="receipt-corruption")
    bounds = _block_bounds(current)
    if bounds is None: raise DeployError("receipted graph block is missing", error_code="receipt-corruption")
    start, end = bounds; block = current[start:end]
    if _digest(block) != state["graph_block_sha256"]:
        raise DeployError("managed graph block drifted from receipt", error_code="receipt-corruption")
    before, after = current[:start], current[end:]
    if state.get("graph_separator_added"):
        if not before.endswith(b"\n"):
            raise DeployError("managed graph instruction separator drifted from receipt", error_code="receipt-corruption")
        before = before[:-1]
    _publish(before + after, expected=current, expected_present=True)
