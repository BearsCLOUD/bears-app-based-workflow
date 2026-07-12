"""Role installation and v1-registration migration transaction orchestration."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from .constants import (
    CONFIG_MAX_BYTES,
    LEGACY_ROLE_RECEIPT_SCHEMA,
    RECEIPT_MAX_BYTES,
    ROLE_RECEIPT_FILE,
    ROLE_RECEIPT_MAX_BYTES,
)
from .intent_io import (
    mark_role_transaction_committed,
    save_registration_migration_intent,
    save_role_intent,
)
from .intent_schema import validate_intent
from .journal import decode_journal_bytes
from .marketplace import plugin_cache, verify_install
from .models import DeployError, FilePublication
from .publication import (
    finalize_publication,
    publish_journaled_file,
    rollback_publication,
)
from .role_io import (
    build_role_receipt,
    open_role_config_lock,
    open_role_receipt_directory,
    parse_role_receipt,
    read_config_at,
    read_config_name_at,
    read_role_receipt_at,
    read_role_receipt_name_at,
    validate_owned_role_state,
)
from .role_profiles import (
    config_with_role_block,
    desired_role_config,
    managed_role_span,
    materialize_role_generation,
    pinned_role_bundle,
    role_block,
    strict_json_loads,
    validate_legacy_registration_payload,
    validate_legacy_role_receipt,
    verify_role_config,
)
from .state_io import (
    build_migration_tombstone,
    load_migration_tombstone,
    parse_migration_tombstone,
    publish_migration_tombstone,
)


def role_deployment_record(
    fingerprint: str,
    bundle: dict[str, Any],
    catalog: dict[str, str],
    role_receipt: bytes,
) -> dict[str, Any]:
    return {
        "payload_fingerprint": fingerprint,
        "role_generation": bundle["generation"],
        "role_count": len(bundle["role_names"]),
        "role_catalog_sha256": bundle["generation"],
        "role_receipt_sha256": hashlib.sha256(role_receipt).hexdigest(),
        "role_source_blobs": {
            relative: {
                "git_oid": record["git_oid"],
                "sha256": record["sha256"],
            }
            for relative, record in sorted(bundle["source_blobs"].items())
        },
        "role_profiles": [
            {
                "name": name,
                "config_file": catalog[name],
                "git_oid": bundle["profiles"][name]["git_oid"],
                "sha256": bundle["profiles"][name]["sha256"],
            }
            for name in bundle["role_names"]
        ],
    }


def reconcile_roles(
    requested: str,
    expected_version: str,
    state_directory: int,
    intent: dict[str, Any] | None,
) -> dict[str, Any]:
    if intent is None or intent.get("requested_sha") != requested:
        raise DeployError("promotion intent does not target the reconciled role revision")
    validate_intent(intent)
    fingerprint = verify_install(requested, expected_version)
    cache = plugin_cache(expected_version)
    bundle = pinned_role_bundle(cache, requested, expected_version)
    catalog = materialize_role_generation(state_directory, bundle)
    home_fd, lock_fd = open_role_config_lock()
    receipt_directory = -1
    config_publication: FilePublication | None = None
    receipt_publication: FilePublication | None = None
    desired = b""
    desired_receipt = b""
    phase = "prepared"
    operation = "install"
    combined_published = False
    try:
        receipt_directory = open_role_receipt_directory(home_fd)
        before = read_config_at(home_fd)
        receipt_before = read_role_receipt_at(receipt_directory)
        original = b"" if before is None else before[0]
        block = role_block(expected_version, catalog)
        transaction = intent.get("role_transaction")
        durable_tombstone = load_migration_tombstone(state_directory)
        live_receipt_value = parse_role_receipt(receipt_before)
        if (
            durable_tombstone is not None
            and live_receipt_value is not None
            and live_receipt_value.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA
        ):
            raise DeployError(
                "legacy registration reappeared after its migration tombstone",
                error_code="receipt-corruption",
            )

        if transaction is None:
            previous_role_receipt = validate_owned_role_state(original, receipt_before)
            desired = desired_role_config(original, expected_version, catalog)
            existing_span = managed_role_span(original)
            added_joiner = (
                bool(previous_role_receipt.get("managed_joiner_added", False))
                if existing_span is not None and previous_role_receipt is not None
                else existing_span is None
                and bool(original)
                and not original.endswith((b"\n", b"\r"))
            )
            desired_receipt = build_role_receipt(
                expected_version,
                block,
                catalog,
                bundle,
                previous_role_receipt,
                added_joiner=added_joiner,
            )
            record = role_deployment_record(fingerprint, bundle, catalog, desired_receipt)
            if (
                previous_role_receipt is not None
                and previous_role_receipt.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA
            ):
                if durable_tombstone is not None:
                    raise DeployError(
                        "legacy registration replay is blocked by its migration tombstone",
                        error_code="receipt-corruption",
                    )
                if before is None or receipt_before is None:
                    raise DeployError("legacy registration migration preimages are incomplete")
                legacy_fingerprint = validate_legacy_registration_payload(
                    before[0], receipt_before[0]
                )
                intent = save_registration_migration_intent(
                    state_directory,
                    intent,
                    config_preimage=before,
                    desired_config=desired,
                    role_receipt_preimage=receipt_before,
                    role_receipt=desired_receipt,
                    role_record=record,
                    legacy_fingerprint=legacy_fingerprint,
                )
            else:
                intent = save_role_intent(
                    state_directory,
                    intent,
                    config_preimage=before,
                    desired_block=block,
                    role_receipt_preimage=receipt_before,
                    role_receipt=desired_receipt,
                    role_record=record,
                )
            transaction = intent["role_transaction"]
        else:
            operation = str(transaction.get("operation"))
            if operation == "install":
                preimage = decode_journal_bytes(
                    transaction["config_preimage_b64"],
                    CONFIG_MAX_BYTES,
                    "config preimage",
                )
                journaled_block = decode_journal_bytes(
                    transaction["desired_block_b64"],
                    CONFIG_MAX_BYTES,
                    "desired role block",
                )
                desired_receipt = decode_journal_bytes(
                    transaction["role_receipt_b64"],
                    ROLE_RECEIPT_MAX_BYTES,
                    "desired role receipt",
                )
                desired = config_with_role_block(preimage, journaled_block)
                record = role_deployment_record(fingerprint, bundle, catalog, desired_receipt)
                if journaled_block != block or transaction["role_record"] != record:
                    raise DeployError(
                        "journaled role transaction disagrees with the exact cached role data"
                    )
            elif operation == "migrate-v1-registration":
                preimage = decode_journal_bytes(
                    transaction["config_preimage_b64"],
                    CONFIG_MAX_BYTES,
                    "config preimage",
                )
                desired = decode_journal_bytes(
                    transaction["desired_config_b64"],
                    CONFIG_MAX_BYTES,
                    "desired config",
                )
                desired_receipt = decode_journal_bytes(
                    transaction["role_receipt_b64"],
                    ROLE_RECEIPT_MAX_BYTES,
                    "desired role receipt",
                )
                receipt_preimage = decode_journal_bytes(
                    transaction["role_receipt_preimage_b64"],
                    ROLE_RECEIPT_MAX_BYTES,
                    "role receipt preimage",
                )
                legacy_fingerprint = validate_legacy_registration_payload(
                    preimage, receipt_preimage
                )
                previous_role_receipt = validate_legacy_role_receipt(
                    strict_json_loads(receipt_preimage, "legacy shared role receipt"),
                    receipt_preimage,
                )
                expected_desired = config_with_role_block(preimage, block)
                expected_receipt = build_role_receipt(
                    expected_version,
                    block,
                    catalog,
                    bundle,
                    previous_role_receipt,
                    added_joiner=False,
                )
                record = role_deployment_record(
                    fingerprint, bundle, catalog, expected_receipt
                )
                expected_tombstone = build_migration_tombstone(
                    legacy_fingerprint,
                    requested,
                    str(record["role_generation"]),
                    str(record["role_receipt_sha256"]),
                )
                journaled_tombstone = decode_journal_bytes(
                    transaction["tombstone_b64"],
                    RECEIPT_MAX_BYTES,
                    "migration tombstone",
                )
                if (
                    transaction["legacy_fingerprint"] != legacy_fingerprint
                    or transaction["role_record"] != record
                    or desired != expected_desired
                    or desired_receipt != expected_receipt
                    or journaled_tombstone != expected_tombstone
                ):
                    raise DeployError(
                        "registration migration journal disagrees with exact old or requested data"
                    )
                current_config = None if before is None else before[0]
                current_receipt = None if receipt_before is None else receipt_before[0]
                config_state = (
                    "old"
                    if current_config == preimage
                    else "desired"
                    if current_config == desired
                    else "third"
                )
                receipt_state = (
                    "old"
                    if current_receipt == receipt_preimage
                    else "desired"
                    if current_receipt == desired_receipt
                    else "third"
                )
                if "third" in {config_state, receipt_state}:
                    raise DeployError(
                        "live registration is outside exact migration recovery states",
                        error_code="receipt-corruption",
                    )
                expected_tombstone_value = parse_migration_tombstone(expected_tombstone)
                if durable_tombstone is not None:
                    if durable_tombstone != expected_tombstone_value:
                        raise DeployError(
                            "registration migration tombstone conflicts with its journal",
                            error_code="receipt-corruption",
                        )
                    if "old" in {config_state, receipt_state}:
                        raise DeployError(
                            "legacy registration rollback or replay detected after tombstone",
                            error_code="receipt-corruption",
                        )
                if config_state == receipt_state == "old":
                    validate_legacy_registration_payload(current_config, current_receipt)
                elif config_state == receipt_state == "desired":
                    validate_owned_role_state(desired, receipt_before)
            else:
                raise DeployError("promotion intent contains a non-install role transaction")

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
            current_config = None if before is None else original
            current_receipt = None if receipt_before is None else receipt_before[0]
            expected_config = preimage if transaction["config_preimage_present"] else None
            if current_config not in {expected_config, desired}:
                raise DeployError("live Codex config is outside the journaled role transaction")
            if current_receipt not in {receipt_preimage, desired_receipt}:
                raise DeployError("shared role receipt is outside the journaled transaction")
            if current_config == desired and current_receipt == desired_receipt:
                validate_owned_role_state(desired, receipt_before)
            elif current_config == expected_config and current_receipt == receipt_preimage:
                validate_owned_role_state(preimage, receipt_before)

        operation = str(transaction["operation"])
        phase = str(transaction["phase"])
        preimage = decode_journal_bytes(
            transaction["config_preimage_b64"],
            CONFIG_MAX_BYTES,
            "config preimage",
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
        config_publication = publish_journaled_file(
            home_fd,
            "config.toml",
            transaction["config_exchange_name"],
            preimage,
            transaction["config_preimage_present"],
            transaction["config_preimage_metadata"],
            desired,
            read_config_name_at,
            "Codex config",
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
            "shared role receipt",
            phase=phase,
        )
        published = config_publication.published
        receipt_published = receipt_publication.published
        verify_role_config(published[0], catalog)
        validate_owned_role_state(published[0], receipt_published)
        if verify_install(requested, expected_version) != fingerprint:
            raise DeployError("installed plugin changed during role reconciliation")
        if pinned_role_bundle(cache, requested, expected_version) != bundle:
            raise DeployError("cached role catalog changed during reconciliation")
        final = read_config_at(home_fd)
        final_receipt = read_role_receipt_at(receipt_directory)
        if final is None or final[0] != desired:
            raise DeployError("live Codex role registration changed after reconciliation")
        if final_receipt is None or final_receipt[0] != desired_receipt:
            raise DeployError("shared live role receipt changed after reconciliation")
        verify_role_config(final[0], catalog)
        validate_owned_role_state(final[0], final_receipt)
        combined_published = True
        if phase == "prepared":
            intent = mark_role_transaction_committed(state_directory, intent)
            transaction = intent["role_transaction"]
            phase = "committed"
        if operation == "migrate-v1-registration":
            publish_migration_tombstone(state_directory, transaction)
            expected_tombstone = parse_migration_tombstone(
                decode_journal_bytes(
                    transaction["tombstone_b64"],
                    RECEIPT_MAX_BYTES,
                    "migration tombstone",
                )
            )
            if load_migration_tombstone(state_directory) != expected_tombstone:
                raise DeployError("registration migration tombstone is not durable")
        finalize_publication(receipt_publication)
        finalize_publication(config_publication)
        return record
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
                "role reconciliation failed and combined rollback is unproven",
                error_code="recovery-failure",
            ) from rollback_failure
        raise exc
    finally:
        if receipt_directory >= 0:
            os.close(receipt_directory)
        os.close(lock_fd)
        os.close(home_fd)
