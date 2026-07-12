"""Shared gateway state models; entry points are DeployError and DeployContext."""

from __future__ import annotations

import os
from typing import Any


class DeployError(RuntimeError):
    """A promotion invariant failed without authorizing a state advance."""

    def __init__(self, message: str, *, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class FilePublication:
    """One renameat2 publication whose displaced preimage remains recoverable."""

    def __init__(
        self,
        *,
        directory: int,
        target: str,
        exchange_name: str,
        expected: tuple[bytes, os.stat_result] | None,
        published: tuple[bytes, os.stat_result],
        reader: Any,
        label: str,
        retained: bool,
        created: bool,
    ):
        self.directory = directory
        self.target = target
        self.exchange_name = exchange_name
        self.expected = expected
        self.published = published
        self.reader = reader
        self.label = label
        self.retained = retained
        self.created = created


class DeployContext:
    """Sanitized state used to classify one gateway outcome."""

    def __init__(self, sha: str):
        self.sha = sha
        self.version = "unknown"
        self.phase = "pre-mutation"
        self.activation_mutated = False


def begin_activation_mutation(context: DeployContext) -> None:
    """Mark the point after which any failure requires proven recovery."""
    context.phase = "mutation"
    context.activation_mutated = True
