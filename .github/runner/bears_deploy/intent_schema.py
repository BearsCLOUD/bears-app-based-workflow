"""Strict schema and binding validation for durable promotion intents."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .constants import (
    CONFIG_MAX_BYTES,
    DEPLOY_RECEIPT_SCHEMA,
    FINGERPRINT_RE,
    MARKETPLACE,
    PLUGIN,
    PROMOTION_INTENT_SCHEMA,
    RECEIPT_MAX_BYTES,
    REPOSITORY,
    ROLE_RECEIPT_MAX_BYTES,
    ROLE_RECEIPT_SCHEMA,
    SHA_RE,
    SNAPSHOT_METADATA_FIELDS,
)
from .journal import decode_journal_bytes
from .models import DeployError
from .role_profiles import (
    config_with_role_block,
    role_block,
    strict_json_loads,
    validate_legacy_registration_payload,
)
from .state_io import parse_migration_tombstone, validate_deploy_receipt


def valid_snapshot_metadata(value: Any, *, present: bool) -> bool:
    if not present:
        return value is None
    return (
        isinstance(value, dict)
        and set(value) == SNAPSHOT_METADATA_FIELDS
        and all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in value.values())
    )


def validate_intent(value: Any) -> dict[str, Any]:
    """Validate one bounded journal entry and its recoverable publication states."""
    fields = {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "requested_sha",
        "previous_receipt",
        "role_transaction",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schema") != PROMOTION_INTENT_SCHEMA
        or value.get("repository") != REPOSITORY
        or value.get("marketplace") != MARKETPLACE
        or value.get("plugin") != PLUGIN
        or not isinstance(value.get("requested_sha"), str)
        or not SHA_RE.fullmatch(value["requested_sha"])
    ):
        raise DeployError("promotion intent identity is invalid", error_code="receipt-corruption")
    previous = value["previous_receipt"]
    if previous is not None:
        try:
            validate_deploy_receipt(previous)
        except DeployError as exc:
            raise DeployError(
                "promotion intent prior convergence state is invalid",
                error_code="receipt-corruption",
            ) from exc
    transaction = value["role_transaction"]
    if transaction is not None:
        common_fields = {
            "operation",
            "phase",
            "config_preimage_b64",
            "config_preimage_present",
            "config_preimage_sha256",
            "config_preimage_metadata",
            "config_exchange_name",
            "role_receipt_b64",
            "role_receipt_preimage_b64",
            "role_receipt_preimage_metadata",
            "role_receipt_sha256",
            "receipt_exchange_name",
            "role_count",
        }
        install_fields = {
            "desired_block_b64",
            "desired_block_sha256",
            "role_generation",
            "role_record",
        }
        remove_fields = {"desired_config_b64", "desired_config_sha256"}
        migration_fields = {
            "desired_config_b64",
            "desired_config_sha256",
            "legacy_fingerprint",
            "role_generation",
            "role_receipt_preimage_sha256",
            "role_record",
            "tombstone_b64",
            "tombstone_exchange_name",
            "tombstone_sha256",
        }
        role_record_fields = {
            "payload_fingerprint",
            "role_generation",
            "role_count",
            "role_catalog_sha256",
            "role_receipt_sha256",
            "role_source_blobs",
            "role_profiles",
        }
        role_record = transaction.get("role_record") if isinstance(transaction, dict) else None
        operation = transaction.get("operation") if isinstance(transaction, dict) else None
        operation_fields = (
            install_fields
            if operation == "install"
            else migration_fields
            if operation == "migrate-v1-registration"
            else remove_fields
        )
        expected_fields = common_fields | operation_fields
        preimage_present = transaction.get("config_preimage_present") if isinstance(transaction, dict) else None
        receipt_preimage_value = (
            transaction.get("role_receipt_preimage_b64") if isinstance(transaction, dict) else None
        )
        if (
            not isinstance(transaction, dict)
            or operation not in {"install", "migrate-v1-registration", "remove"}
            or set(transaction) != expected_fields
            or transaction.get("phase") not in {"prepared", "committed"}
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("config_preimage_sha256", "")))
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("role_receipt_sha256", "")))
            or not isinstance(transaction.get("role_count"), int)
            or isinstance(transaction.get("role_count"), bool)
            or not 0 <= transaction["role_count"] <= 64
            or not isinstance(preimage_present, bool)
            or not isinstance(transaction.get("config_preimage_b64"), str)
            or not isinstance(transaction.get("role_receipt_b64"), str)
            or not valid_snapshot_metadata(
                transaction.get("config_preimage_metadata"), present=bool(preimage_present)
            )
            or not valid_snapshot_metadata(
                transaction.get("role_receipt_preimage_metadata"),
                present=receipt_preimage_value is not None,
            )
            or not re.fullmatch(
                r"\.config\.toml\.bears-gateway\.[0-9a-f]{32}",
                str(transaction.get("config_exchange_name", "")),
            )
            or not re.fullmatch(
                rf"\.{re.escape(PLUGIN)}-role-sync\.[0-9a-f]{{32}}\.tmp",
                str(transaction.get("receipt_exchange_name", "")),
            )
            or (
                receipt_preimage_value is not None
                and not isinstance(receipt_preimage_value, str)
            )
        ):
            raise DeployError("promotion role transaction is invalid", error_code="receipt-corruption")
        if operation == "install" and (
            not isinstance(transaction.get("desired_block_b64"), str)
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("desired_block_sha256", "")))
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("role_generation", "")))
            or not isinstance(role_record, dict)
            or set(role_record) != role_record_fields
        ):
            raise DeployError("promotion install transaction is invalid", error_code="receipt-corruption")
        if operation == "remove" and (
            transaction["role_count"] != 0
            or not isinstance(transaction.get("desired_config_b64"), str)
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("desired_config_sha256", "")))
        ):
            raise DeployError("promotion removal transaction is invalid", error_code="receipt-corruption")
        if operation == "migrate-v1-registration" and (
            preimage_present is not True
            or not isinstance(receipt_preimage_value, str)
            or not isinstance(transaction.get("desired_config_b64"), str)
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("desired_config_sha256", "")))
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("legacy_fingerprint", "")))
            or not FINGERPRINT_RE.fullmatch(
                str(transaction.get("role_receipt_preimage_sha256", ""))
            )
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("role_generation", "")))
            or not isinstance(role_record, dict)
            or set(role_record) != role_record_fields
            or not isinstance(transaction.get("tombstone_b64"), str)
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("tombstone_sha256", "")))
            or not re.fullmatch(
                rf"\.{re.escape(PLUGIN)}-v1-registration\.[0-9a-f]{{32}}\.tmp",
                str(transaction.get("tombstone_exchange_name", "")),
            )
        ):
            raise DeployError(
                "promotion registration migration transaction is invalid",
                error_code="receipt-corruption",
            )
        try:
            config_preimage = decode_journal_bytes(
                transaction["config_preimage_b64"],
                CONFIG_MAX_BYTES,
                "config preimage",
            )
            desired_payload = decode_journal_bytes(
                transaction["desired_block_b64" if operation == "install" else "desired_config_b64"],
                CONFIG_MAX_BYTES,
                "desired role block" if operation == "install" else "desired config",
            )
            role_receipt = decode_journal_bytes(
                transaction["role_receipt_b64"],
                ROLE_RECEIPT_MAX_BYTES,
                "desired role receipt",
            )
            if receipt_preimage_value is not None:
                receipt_preimage = decode_journal_bytes(
                    receipt_preimage_value,
                    ROLE_RECEIPT_MAX_BYTES,
                    "role receipt preimage",
                )
            else:
                receipt_preimage = None
            tombstone = (
                decode_journal_bytes(
                    transaction["tombstone_b64"],
                    RECEIPT_MAX_BYTES,
                    "migration tombstone",
                )
                if operation == "migrate-v1-registration"
                else None
            )
        except DeployError as exc:
            raise DeployError(
                "promotion role transaction payload is invalid",
                error_code="receipt-corruption",
            ) from exc
        if (
            hashlib.sha256(config_preimage).hexdigest()
            != transaction["config_preimage_sha256"]
            or hashlib.sha256(desired_payload).hexdigest()
            != transaction[
                "desired_block_sha256" if operation == "install" else "desired_config_sha256"
            ]
            or hashlib.sha256(role_receipt).hexdigest()
            != transaction["role_receipt_sha256"]
            or (not preimage_present and config_preimage != b"")
            or (
                operation == "migrate-v1-registration"
                and (
                    receipt_preimage is None
                    or hashlib.sha256(receipt_preimage).hexdigest()
                    != transaction["role_receipt_preimage_sha256"]
                    or tombstone is None
                    or hashlib.sha256(tombstone).hexdigest()
                    != transaction["tombstone_sha256"]
                )
            )
        ):
            raise DeployError(
                "promotion role transaction payload digest is invalid",
                error_code="receipt-corruption",
            )
        if operation in {"install", "migrate-v1-registration"}:
            try:
                validate_deploy_receipt(
                    {
                        "schema": DEPLOY_RECEIPT_SCHEMA,
                        "repository": REPOSITORY,
                        "marketplace": MARKETPLACE,
                        "plugin": PLUGIN,
                        "sha": value["requested_sha"],
                        "version": "0.0.0+codex.00000000000000",
                        **role_record,
                    }
                )
            except DeployError as exc:
                raise DeployError(
                    "promotion role transaction record is invalid",
                    error_code="receipt-corruption",
                ) from exc
            if (
                transaction["role_generation"] != role_record["role_generation"]
                or transaction["role_receipt_sha256"] != role_record["role_receipt_sha256"]
                or transaction["role_count"] != role_record["role_count"]
            ):
                raise DeployError(
                    "promotion role transaction disagrees with its role record",
                    error_code="receipt-corruption",
                )
        if operation == "migrate-v1-registration":
            try:
                legacy_fingerprint = validate_legacy_registration_payload(
                    config_preimage, receipt_preimage
                )
                receipt_value = strict_json_loads(role_receipt, "desired v2 role receipt")
                tombstone_value = parse_migration_tombstone(tombstone)
                profiles = role_record["role_profiles"]
                catalog = {
                    row["name"]: row["config_file"]
                    for row in profiles
                    if isinstance(row, dict)
                }
                expected_config = config_with_role_block(
                    config_preimage,
                    role_block(str(receipt_value.get("version", "")), catalog),
                )
            except (AttributeError, DeployError, KeyError, TypeError) as exc:
                raise DeployError(
                    "promotion registration migration payload is invalid",
                    error_code="receipt-corruption",
                ) from exc
            if (
                legacy_fingerprint != transaction["legacy_fingerprint"]
                or not isinstance(receipt_value, dict)
                or receipt_value.get("schema") != ROLE_RECEIPT_SCHEMA
                or receipt_value.get("plugin") != PLUGIN
                or receipt_value.get("status") != "installed"
                or expected_config != desired_payload
                or tombstone_value["legacy_fingerprint"] != legacy_fingerprint
                or tombstone_value["requested_sha"] != value["requested_sha"]
                or tombstone_value["role_generation"] != transaction["role_generation"]
                or tombstone_value["role_receipt_sha256"]
                != transaction["role_receipt_sha256"]
            ):
                raise DeployError(
                    "promotion registration migration binding is invalid",
                    error_code="receipt-corruption",
                )
    return value
