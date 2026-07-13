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
from .models import DeployError

BEGIN = b"<!-- >>> bears-app-based-workflow graph behavior (managed by CD) -->"
END = b"<!-- <<< bears-app-based-workflow graph behavior (managed by CD) -->"
TARGET = CODEX_HOME / "AGENTS.md"


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


def _publish(payload: bytes) -> None:
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    if CODEX_HOME.is_symlink() or not CODEX_HOME.is_dir():
        raise DeployError("CODEX_HOME is unsafe")
    current = _read_regular(TARGET, missing=True)
    temporary = CODEX_HOME / f".AGENTS.md.{secrets.token_hex(16)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0: raise DeployError("AGENTS.md publication did not advance")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        if current is not None:
            target_stat = TARGET.lstat()
            if not stat.S_ISREG(target_stat.st_mode) or target_stat.st_nlink != 1:
                raise DeployError("AGENTS.md changed to an unsafe file", error_code="receipt-corruption")
            os.chmod(temporary, stat.S_IMODE(target_stat.st_mode))
        os.replace(temporary, TARGET)
    finally:
        temporary.unlink(missing_ok=True)
    directory = os.open(CODEX_HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def reconcile_graph_instructions(state_directory: int, previous: dict[str, Any] | None) -> dict[str, Any]:
    template = _template(); observed = _read_regular(TARGET, missing=True); current = observed or b""
    desired, separator = _desired(current, template, previous)
    intent = load_intent(state_directory)
    if intent is None: raise DeployError("promotion intent disappeared before graph reconciliation")
    save_graph_intent(state_directory, intent, original=current, original_present=observed is not None, desired=desired)
    _publish(desired)
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
    current = _read_regular(TARGET, missing=True) or b""
    if current == original: return
    if current != desired:
        raise DeployError("AGENTS.md changed during interrupted promotion", error_code="receipt-corruption")
    if transaction["original_present"]:
        _publish(original)
    else:
        TARGET.unlink()
        directory = os.open(CODEX_HOME, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def remove_graph_instructions(state: dict[str, Any] | None) -> None:
    if state is None or not state.get("graph_block_sha256"): return
    current = _read_regular(TARGET, missing=True)
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
    _publish(before + after)
