"""Durable deployment receipt writes and receipted installation verification."""

from __future__ import annotations

import json
import os
import secrets
from typing import Any

from .constants import (
    DEPLOY_RECEIPT_SCHEMA,
    LEGACY_VERSION_RE,
    MARKETPLACE,
    MIRROR,
    PLUGIN,
    REPOSITORY,
    STATE_FILE,
)
from .marketplace import legacy_payload_fingerprint, verify_install
from .models import DeployError
from .state_io import validate_deploy_receipt, validate_private_regular


def save_state(
    state_directory: int,
    sha: str,
    version: str,
    role_record: dict[str, Any],
    graph_record: dict[str, Any],
) -> None:
    value = {
        "schema": DEPLOY_RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "marketplace": MARKETPLACE,
        "plugin": PLUGIN,
        "sha": sha,
        "version": version,
        **role_record,
        **graph_record,
    }
    validate_deploy_receipt(value)
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    temporary = f".{PLUGIN}.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=state_directory,
        )
        os.fchmod(descriptor, 0o600)
        validate_private_regular(descriptor, "temporary deployment receipt")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise DeployError("temporary deployment receipt write did not advance")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary,
            STATE_FILE.name,
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


def clear_state(state_directory: int) -> None:
    try:
        os.unlink(STATE_FILE.name, dir_fd=state_directory)
    except FileNotFoundError:
        return
    os.fsync(state_directory)


def verify_receipted_install(state: dict[str, Any]) -> None:
    fingerprint = verify_install(str(state["sha"]), str(state["version"]))
    receipted_fingerprint = str(state["payload_fingerprint"])
    legacy_match = (
        LEGACY_VERSION_RE.fullmatch(str(state["version"])) is not None
        and receipted_fingerprint == legacy_payload_fingerprint(MIRROR, str(state["sha"]))
    )
    if fingerprint != receipted_fingerprint and not legacy_match:
        raise DeployError("active plugin disagrees with its deployment receipt", error_code="receipt-corruption")
