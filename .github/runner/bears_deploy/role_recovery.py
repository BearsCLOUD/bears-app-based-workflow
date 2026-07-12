"""Role transaction rollback and owned-registration removal orchestration."""

from __future__ import annotations

import os
from typing import Any

from .constants import (
    CONFIG_MAX_BYTES,
    ROLE_RECEIPT_FILE,
    ROLE_RECEIPT_MAX_BYTES,
    ROLE_RECEIPT_SCHEMA,
)
from .intent_io import mark_role_transaction_committed, save_role_removal_intent
from .intent_schema import validate_intent
from .journal import decode_journal_bytes
from .models import DeployError, FilePublication
from .publication import (
    atomic_config_remove,
    atomic_config_replace,
    atomic_role_receipt_replace,
    finalize_publication,
    publish_journaled_file,
    rollback_publication,
    rollback_role_receipt,
)
from .role_io import (
    build_uninstalled_role_receipt,
    matches_snapshot_metadata,
    open_role_config_lock,
    open_role_receipt_directory,
    parse_role_receipt,
    read_config_at,
    read_config_name_at,
    read_role_receipt_at,
    read_role_receipt_name_at,
    validate_owned_role_state,
)
from .role_profiles import config_with_role_block, config_without_owned_roles
from .standalone_roles import clear_standalone_roles


def rollback_journaled_roles(intent: dict[str, Any]) -> None:
    transaction = intent.get("role_transaction")
    if transaction is None:
        return
    validate_intent(intent)
    if transaction.get("operation") != "install":
        raise DeployError("non-install role transaction must converge forward")
    preimage = decode_journal_bytes(
        transaction["config_preimage_b64"],
        CONFIG_MAX_BYTES,
        "config preimage",
    )
    block = decode_journal_bytes(
        transaction["desired_block_b64"],
        CONFIG_MAX_BYTES,
        "desired role block",
    )
    desired = config_with_role_block(preimage, block)
    desired_receipt = decode_journal_bytes(
        transaction["role_receipt_b64"],
        ROLE_RECEIPT_MAX_BYTES,
        "desired role receipt",
    )
    receipt_preimage_value = transaction["role_receipt_preimage_b64"]
    receipt_preimage = (
        None
        if receipt_preimage_value is None
        else decode_journal_bytes(
            receipt_preimage_value,
            ROLE_RECEIPT_MAX_BYTES,
            "role receipt preimage",
        )
    )
    home_fd, lock_fd = open_role_config_lock()
    receipt_directory = -1
    try:
        receipt_directory = open_role_receipt_directory(home_fd)
        current = read_config_at(home_fd)
        current_bytes = None if current is None else current[0]
        expected_preimage = preimage if transaction["config_preimage_present"] else None
        if current_bytes not in {expected_preimage, desired}:
            raise DeployError("live Codex config cannot be rolled back from its role journal")
        current_receipt = read_role_receipt_at(receipt_directory)
        current_receipt_bytes = None if current_receipt is None else current_receipt[0]
        if current_receipt_bytes not in {receipt_preimage, desired_receipt}:
            raise DeployError("shared role receipt cannot be rolled back from its journal")
        if current_receipt_bytes != receipt_preimage:
            retained = read_role_receipt_name_at(
                receipt_directory, transaction["receipt_exchange_name"]
            )
            if (
                receipt_preimage is not None
                and retained is not None
                and retained[0] == receipt_preimage
                and matches_snapshot_metadata(
                    retained, transaction["role_receipt_preimage_metadata"]
                )
            ):
                rollback_publication(
                    FilePublication(
                        directory=receipt_directory,
                        target=ROLE_RECEIPT_FILE.name,
                        exchange_name=transaction["receipt_exchange_name"],
                        expected=retained,
                        published=current_receipt,
                        reader=read_role_receipt_name_at,
                        label="shared role receipt",
                        retained=True,
                        created=False,
                    )
                )
            elif receipt_preimage is None:
                rollback_role_receipt(receipt_directory, None, desired_receipt)
            else:
                atomic_role_receipt_replace(
                    receipt_directory,
                    current_receipt,
                    receipt_preimage,
                )
        if current_bytes != expected_preimage:
            retained = read_config_name_at(home_fd, transaction["config_exchange_name"])
            if (
                expected_preimage is not None
                and retained is not None
                and retained[0] == expected_preimage
                and matches_snapshot_metadata(retained, transaction["config_preimage_metadata"])
            ):
                rollback_publication(
                    FilePublication(
                        directory=home_fd,
                        target="config.toml",
                        exchange_name=transaction["config_exchange_name"],
                        expected=retained,
                        published=current,
                        reader=read_config_name_at,
                        label="Codex config",
                        retained=True,
                        created=False,
                    )
                )
            elif expected_preimage is None:
                if current is None:
                    raise DeployError("journaled Codex config rollback state is ambiguous")
                atomic_config_remove(home_fd, current)
            else:
                atomic_config_replace(home_fd, current, expected_preimage)
        restored = read_config_at(home_fd)
        restored_receipt = read_role_receipt_at(receipt_directory)
        restored_bytes = None if restored is None else restored[0]
        restored_receipt_bytes = None if restored_receipt is None else restored_receipt[0]
        if restored_bytes != expected_preimage or restored_receipt_bytes != receipt_preimage:
            raise DeployError("journaled role rollback did not converge")
        for directory, exchange_name, reader, replacement, label in (
            (
                home_fd,
                transaction["config_exchange_name"],
                read_config_name_at,
                desired,
                "Codex config",
            ),
            (
                receipt_directory,
                transaction["receipt_exchange_name"],
                read_role_receipt_name_at,
                desired_receipt,
                "shared role receipt",
            ),
        ):
            staged = reader(directory, exchange_name)
            if staged is not None:
                if staged[0] != replacement:
                    raise DeployError(f"{label} rollback exchange file is ambiguous")
                os.unlink(exchange_name, dir_fd=directory)
                os.fsync(directory)
        validate_owned_role_state(b"" if restored is None else restored[0], restored_receipt)
    finally:
        if receipt_directory >= 0:
            os.close(receipt_directory)
        os.close(lock_fd)
        os.close(home_fd)


def clear_owned_roles(state_directory: int, intent: dict[str, Any]) -> dict[str, Any]:
    home_fd, lock_fd = open_role_config_lock()
    receipt_directory = -1
    before: tuple[bytes, os.stat_result] | None = None
    receipt_before: tuple[bytes, os.stat_result] | None = None
    config_publication: FilePublication | None = None
    receipt_publication: FilePublication | None = None
    outside = b""
    desired_receipt = b""
    phase = "prepared"
    combined_published = False
    try:
        receipt_directory = open_role_receipt_directory(home_fd)
        before = read_config_at(home_fd)
        receipt_before = read_role_receipt_at(receipt_directory)
        current_config = b"" if before is None else before[0]
        transaction = intent.get("role_transaction")
        if transaction is None or transaction.get("operation") == "install":
            previous = validate_owned_role_state(current_config, receipt_before)
            if before is None and previous is None:
                return intent
            outside, span = config_without_owned_roles(current_config)
            if span is None:
                return intent
            if previous is None:
                raise DeployError("managed role removal lacks a shared ownership receipt")
            desired_receipt = build_uninstalled_role_receipt(previous)
            intent = save_role_removal_intent(
                state_directory,
                intent,
                config_preimage=before,
                desired_config=outside,
                role_receipt_preimage=receipt_before,
                role_receipt=desired_receipt,
            )
            transaction = intent["role_transaction"]
        elif transaction.get("operation") != "remove":
            raise DeployError("promotion intent contains an unknown role transition")
        preimage = decode_journal_bytes(
            transaction["config_preimage_b64"], CONFIG_MAX_BYTES, "config preimage"
        )
        outside = decode_journal_bytes(
            transaction["desired_config_b64"], CONFIG_MAX_BYTES, "desired config"
        )
        desired_receipt = decode_journal_bytes(
            transaction["role_receipt_b64"], ROLE_RECEIPT_MAX_BYTES, "uninstalled role receipt"
        )
        receipt_preimage_value = transaction["role_receipt_preimage_b64"]
        receipt_preimage = (
            b""
            if receipt_preimage_value is None
            else decode_journal_bytes(
                receipt_preimage_value,
                ROLE_RECEIPT_MAX_BYTES,
                "role receipt preimage",
            )
        )
        phase = transaction["phase"]
        current_config_bytes = None if before is None else before[0]
        current_receipt_bytes = None if receipt_before is None else receipt_before[0]
        expected_config = preimage if transaction["config_preimage_present"] else None
        expected_receipt = None if receipt_preimage_value is None else receipt_preimage
        if current_config_bytes not in {expected_config, outside}:
            raise DeployError("Codex config is outside the journaled removal transition")
        if current_receipt_bytes not in {expected_receipt, desired_receipt}:
            raise DeployError("shared role receipt is outside the journaled removal transition")
        config_publication = publish_journaled_file(
            home_fd,
            "config.toml",
            transaction["config_exchange_name"],
            preimage,
            transaction["config_preimage_present"],
            transaction["config_preimage_metadata"],
            outside,
            read_config_name_at,
            "Codex config removal",
            phase=phase,
        )
        receipt_publication = publish_journaled_file(
            receipt_directory,
            ROLE_RECEIPT_FILE.name,
            transaction["receipt_exchange_name"],
            receipt_preimage,
            receipt_preimage_value is not None,
            transaction["role_receipt_preimage_metadata"],
            desired_receipt,
            read_role_receipt_name_at,
            "shared role receipt removal",
            phase=phase,
        )
        published = config_publication.published
        receipt_published = receipt_publication.published
        _, remaining_span = config_without_owned_roles(published[0])
        if remaining_span is not None:
            raise DeployError("managed role block remains after journaled removal")
        parsed_receipt = parse_role_receipt(receipt_published)
        if (
            parsed_receipt is None
            or parsed_receipt.get("schema") != ROLE_RECEIPT_SCHEMA
            or parsed_receipt.get("status") != "uninstalled"
        ):
            raise DeployError("shared role receipt did not converge to uninstalled")
        combined_published = True
        if phase == "prepared":
            intent = mark_role_transaction_committed(state_directory, intent)
            phase = "committed"
        clear_standalone_roles(
            home_fd,
            None if receipt_preimage_value is None else receipt_preimage,
        )
        finalize_publication(receipt_publication)
        finalize_publication(config_publication)
        return intent
    except Exception as exc:
        rollback_failure: Exception | None = None
        if phase != "committed" and not combined_published and receipt_publication is not None:
            try:
                rollback_publication(receipt_publication)
            except Exception as failure:
                rollback_failure = failure
        if phase != "committed" and not combined_published and config_publication is not None:
            try:
                rollback_publication(config_publication)
            except Exception as failure:
                rollback_failure = rollback_failure or failure
        if rollback_failure is not None:
            raise DeployError(
                "managed role removal failed and rollback is unproven",
                error_code="recovery-failure",
            ) from rollback_failure
        raise exc
    finally:
        if receipt_directory >= 0:
            os.close(receipt_directory)
        os.close(lock_fd)
        os.close(home_fd)
