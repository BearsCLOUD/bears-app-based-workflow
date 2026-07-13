"""Durable promotion-intent persistence and role-transaction journal updates."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from typing import Any

from .constants import (
    INTENT_FILE,
    INTENT_MAX_BYTES,
    MARKETPLACE,
    PLUGIN,
    PROMOTION_INTENT_SCHEMA,
    REPOSITORY,
)
from .intent_schema import validate_intent
from .journal import decode_journal_bytes, encode_journal_bytes
from .models import DeployError
from .role_io import snapshot_metadata
from .state_io import build_migration_tombstone, validate_private_regular


def load_intent(state_directory: int) -> dict[str, Any] | None:
    """Load a secure durable promotion journal without following links."""
    try:
        descriptor = os.open(
            INTENT_FILE.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=state_directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("promotion intent is unsafe", error_code="receipt-corruption") from exc
    try:
        file_stat = validate_private_regular(
            descriptor, "promotion intent", error_code="receipt-corruption"
        )
        if file_stat.st_size > INTENT_MAX_BYTES:
            raise DeployError("promotion intent is oversized", error_code="receipt-corruption")
        payload = bytearray()
        while len(payload) <= INTENT_MAX_BYTES:
            chunk = os.read(descriptor, min(4096, INTENT_MAX_BYTES + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > INTENT_MAX_BYTES:
            raise DeployError("promotion intent is oversized", error_code="receipt-corruption")
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeployError("promotion intent is unreadable", error_code="receipt-corruption") from exc
    finally:
        os.close(descriptor)
    return validate_intent(value)


def persist_intent(state_directory: int, value: dict[str, Any]) -> dict[str, Any]:
    value = validate_intent(value)
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    if len(payload) > INTENT_MAX_BYTES:
        raise DeployError("promotion intent is oversized")
    temporary = f".{PLUGIN}.promotion-intent.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=state_directory,
        )
        os.fchmod(descriptor, 0o600)
        validate_private_regular(descriptor, "temporary promotion intent")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise DeployError("temporary promotion intent write did not advance")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary,
            INTENT_FILE.name,
            src_dir_fd=state_directory,
            dst_dir_fd=state_directory,
        )
        temporary = ""
        os.fsync(state_directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=state_directory)
            except FileNotFoundError:
                pass
    return value


def save_intent(
    state_directory: int,
    requested: str,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Atomically persist and fsync the convergence journal before activation."""
    return persist_intent(
        state_directory,
        {
            "schema": PROMOTION_INTENT_SCHEMA,
            "repository": REPOSITORY,
            "marketplace": MARKETPLACE,
            "plugin": PLUGIN,
            "requested_sha": requested,
            "previous_receipt": dict(previous) if previous is not None else None,
            "role_transaction": None,
            "graph_transaction": None,
        },
    )


def save_graph_intent(
    state_directory: int,
    intent: dict[str, Any],
    *,
    original: bytes,
    original_present: bool,
    desired: bytes,
) -> dict[str, Any]:
    """Persist exact AGENTS.md preimage and desired bytes before publication."""
    value = dict(intent)
    value["graph_transaction"] = {
        "original_b64": encode_journal_bytes(original),
        "original_present": original_present,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "desired_b64": encode_journal_bytes(desired),
        "desired_sha256": hashlib.sha256(desired).hexdigest(),
    }
    return persist_intent(state_directory, value)


def save_role_intent(
    state_directory: int,
    intent: dict[str, Any],
    *,
    config_preimage: tuple[bytes, os.stat_result] | None,
    desired_block: bytes,
    role_receipt_preimage: tuple[bytes, os.stat_result] | None,
    role_receipt: bytes,
    role_record: dict[str, Any],
) -> dict[str, Any]:
    value = dict(intent)
    config_bytes = b"" if config_preimage is None else config_preimage[0]
    receipt_bytes = None if role_receipt_preimage is None else role_receipt_preimage[0]
    value["role_transaction"] = {
        "operation": "install",
        "phase": "prepared",
        "config_preimage_b64": encode_journal_bytes(config_bytes),
        "config_preimage_present": config_preimage is not None,
        "config_preimage_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_preimage_metadata": snapshot_metadata(config_preimage),
        "config_exchange_name": f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        "desired_block_b64": encode_journal_bytes(desired_block),
        "desired_block_sha256": hashlib.sha256(desired_block).hexdigest(),
        "role_generation": role_record["role_generation"],
        "role_receipt_b64": encode_journal_bytes(role_receipt),
        "role_receipt_preimage_b64": (
            None if receipt_bytes is None else encode_journal_bytes(receipt_bytes)
        ),
        "role_receipt_preimage_metadata": snapshot_metadata(role_receipt_preimage),
        "role_receipt_sha256": role_record["role_receipt_sha256"],
        "receipt_exchange_name": f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        "role_count": role_record["role_count"],
        "role_record": role_record,
    }
    return persist_intent(state_directory, value)


def save_registration_migration_intent(
    state_directory: int,
    intent: dict[str, Any],
    *,
    config_preimage: tuple[bytes, os.stat_result],
    desired_config: bytes,
    role_receipt_preimage: tuple[bytes, os.stat_result],
    role_receipt: bytes,
    role_record: dict[str, Any],
    legacy_fingerprint: str,
) -> dict[str, Any]:
    """Persist the exact one-shot v1 registration migration before publication."""
    value = dict(intent)
    config_bytes = config_preimage[0]
    receipt_bytes = role_receipt_preimage[0]
    tombstone = build_migration_tombstone(
        legacy_fingerprint,
        str(intent["requested_sha"]),
        str(role_record["role_generation"]),
        str(role_record["role_receipt_sha256"]),
    )
    value["role_transaction"] = {
        "operation": "migrate-v1-registration",
        "phase": "prepared",
        "config_preimage_b64": encode_journal_bytes(config_bytes),
        "config_preimage_present": True,
        "config_preimage_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_preimage_metadata": snapshot_metadata(config_preimage),
        "config_exchange_name": f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        "desired_config_b64": encode_journal_bytes(desired_config),
        "desired_config_sha256": hashlib.sha256(desired_config).hexdigest(),
        "legacy_fingerprint": legacy_fingerprint,
        "role_generation": role_record["role_generation"],
        "role_receipt_b64": encode_journal_bytes(role_receipt),
        "role_receipt_preimage_b64": encode_journal_bytes(receipt_bytes),
        "role_receipt_preimage_metadata": snapshot_metadata(role_receipt_preimage),
        "role_receipt_preimage_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "role_receipt_sha256": role_record["role_receipt_sha256"],
        "receipt_exchange_name": f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        "role_count": role_record["role_count"],
        "role_record": role_record,
        "tombstone_b64": encode_journal_bytes(tombstone),
        "tombstone_exchange_name": (
            f".{PLUGIN}-v1-registration.{secrets.token_hex(16)}.tmp"
        ),
        "tombstone_sha256": hashlib.sha256(tombstone).hexdigest(),
    }
    return persist_intent(state_directory, value)


def save_role_removal_intent(
    state_directory: int,
    intent: dict[str, Any],
    *,
    config_preimage: tuple[bytes, os.stat_result] | None,
    desired_config: bytes,
    role_receipt_preimage: tuple[bytes, os.stat_result] | None,
    role_receipt: bytes,
) -> dict[str, Any]:
    value = dict(intent)
    config_bytes = b"" if config_preimage is None else config_preimage[0]
    receipt_bytes = None if role_receipt_preimage is None else role_receipt_preimage[0]
    value["role_transaction"] = {
        "operation": "remove",
        "phase": "prepared",
        "config_preimage_b64": encode_journal_bytes(config_bytes),
        "config_preimage_present": config_preimage is not None,
        "config_preimage_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_preimage_metadata": snapshot_metadata(config_preimage),
        "config_exchange_name": f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        "desired_config_b64": encode_journal_bytes(desired_config),
        "desired_config_sha256": hashlib.sha256(desired_config).hexdigest(),
        "role_receipt_b64": encode_journal_bytes(role_receipt),
        "role_receipt_preimage_b64": (
            None if receipt_bytes is None else encode_journal_bytes(receipt_bytes)
        ),
        "role_receipt_preimage_metadata": snapshot_metadata(role_receipt_preimage),
        "role_receipt_sha256": hashlib.sha256(role_receipt).hexdigest(),
        "receipt_exchange_name": f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        "role_count": 0,
    }
    return persist_intent(state_directory, value)


def mark_role_transaction_committed(
    state_directory: int,
    intent: dict[str, Any],
) -> dict[str, Any]:
    value = dict(intent)
    transaction = dict(value["role_transaction"])
    transaction["phase"] = "committed"
    value["role_transaction"] = transaction
    return persist_intent(state_directory, value)


def clear_intent(state_directory: int) -> None:
    """Durably clear the journal only after verified convergence."""
    try:
        os.unlink(INTENT_FILE.name, dir_fd=state_directory)
    except FileNotFoundError:
        pass
    os.fsync(state_directory)
