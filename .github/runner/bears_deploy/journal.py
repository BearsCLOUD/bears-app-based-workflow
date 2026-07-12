"""Bounded binary encoding for durable promotion journal payloads."""

from __future__ import annotations

import base64
import binascii

from .models import DeployError


def encode_journal_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def decode_journal_bytes(value: str, maximum: int, label: str) -> bytes:
    if len(value) > ((maximum + 2) // 3) * 4:
        raise DeployError(f"journaled {label} is oversized")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise DeployError(f"journaled {label} is malformed") from exc
    if len(decoded) > maximum:
        raise DeployError(f"journaled {label} is oversized")
    return decoded
